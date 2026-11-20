"""Offline money/reset isolation checks: fictional visits and synthetic receipts only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
import functools
import json
from unittest.mock import patch
import server
from ai_budget import BudgetError, NANO
from pilot_access import PilotAccess, HISTORY_NOTICE, ProfileError, participant
from pilot_budget import PilotBudget
from natural_agent import TurnReservation
import test_hosted_history as base
from hosted_server import build_hosted

MODEL = 'gpt-6.1-sol'


class HostedPolicy(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root = Path(folder.name); self.end = int(time.time())+3600
        self.access = PilotAccess.initialize(self.root/'pilot',ends_at=self.end)
        self.budget = PilotBudget.open(self.access,initialize=True)
        self.budget.configure_hosted('accelerator')
        self.budget.clock = lambda:datetime.fromisoformat(self.budget.rates['verified_at']).timestamp()
        for flag in ('all_chat','guest_chat'): self.access.set_flag(flag,True)
        self.link,self.token = self.access.issue_shared(expires_at=self.end,max_visits=20)
        session,_ = self.access.redeem(self.token,consent_version=HISTORY_NOTICE)
        self.owner = self.access.authenticate(session)[0]
        context = participant.set(self.owner); self.addCleanup(participant.reset,context)

    def charge(self, amount, owner=None):
        # Make an explicitly attributed synthetic settled charge, in nano-USD.
        owner = owner or self.owner
        context = participant.set(owner)
        try: key = self.budget.reserve(1000,2400,MODEL)
        finally: participant.reset(context)
        with self.budget.db() as db:
            db.execute("UPDATE ai_charges SET charged=?,measured=?,status='settled' WHERE id=?",(amount,amount,key))
        return key

    def test_four_resets_preserve_invite_and_share_original_five_dollars(self):
        self.charge(4_900_000_000)
        original = self.owner
        for left in (3,2,1,0):
            session,_,remaining = self.access.restart(self.owner)
            self.owner = self.access.authenticate(session)[0]; participant.set(self.owner)
            self.assertEqual(remaining,left)
            self.assertEqual(self.access.session_root(self.owner),original)
            with self.assertRaises(BudgetError): self.budget.reserve(1000,2400,MODEL)
        with self.assertRaises(ProfileError): self.access.restart(self.owner)
        self.assertEqual(self.access.token_parts(self.token)[0],self.link)
        with self.access.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM visit_policy WHERE id NOT IN (SELECT id FROM visit_restarts)').fetchone()[0],1)
        reopened = PilotBudget.open(self.access)
        reopened.configure_hosted('accelerator')
        with reopened.db() as db: self.assertEqual(reopened._invite_spend(db,self.owner),4_900_000_000)

    def test_earlier_charges_are_not_forgotten_when_reset_has_its_own_charges(self):
        self.charge(NANO)
        session,_,_ = self.access.restart(self.owner)
        self.owner = self.access.authenticate(session)[0]; participant.set(self.owner)
        self.charge(2*NANO)
        session,_,_ = self.access.restart(self.owner)
        self.owner = self.access.authenticate(session)[0]; participant.set(self.owner)
        with self.budget.db() as db: self.assertEqual(self.budget._invite_spend(db,self.owner),3*NANO)

    def test_ultrafast_reservation_and_actual_receipt_price(self):
        key = self.budget.reserve(1000,2400,MODEL)
        with self.budget.db() as db:
            self.assertEqual(db.execute('SELECT reserved FROM ai_charges WHERE id=?',(key,)).fetchone()[0],159_000_000)
        receipt = {'model':MODEL,'service_tier':'ultrafast','status':'completed',
                   'usage':{'input_tokens':1000,'output_tokens':100,'total_tokens':1100,
                            'input_tokens_details':{'cached_tokens':100,'cache_write_tokens':200}}}
        self.budget.settle_model(key,receipt,MODEL)
        with self.budget.db() as db:
            self.assertEqual(db.execute('SELECT measured FROM ai_charges WHERE id=?',(key,)).fetchone()[0],17_460_000)

    def test_turn_reservations_and_input_resize_also_use_ultrafast_rates(self):
        reservation = TurnReservation(self.budget,MODEL)
        self.addCleanup(reservation.close)
        stage = reservation.stages['extract']; stage.check_input(1000)
        with self.budget.db() as db:
            self.assertEqual(db.execute('SELECT reserved FROM ai_charges WHERE id=?',(stage.key,)).fetchone()[0],159_000_000)
        with self.assertRaises(BudgetError): stage.check_input(272001)

    def test_unknown_receipt_tier_holds_money_and_blocks_further_spending(self):
        key = self.budget.reserve(1000,2400,MODEL)
        with self.assertRaises(BudgetError):
            self.budget.settle_model(key,{'model':MODEL,'service_tier':'mystery','status':'completed',
                'usage':{'input_tokens':1000,'output_tokens':100,'total_tokens':1100,'input_tokens_details':{'cached_tokens':0}}},MODEL)
        with self.assertRaises(BudgetError): self.budget.reserve(1000,2400,MODEL)

    def test_owner_budget_and_speed_are_unchanged_on_shared_ledger(self):
        owner_access = PilotAccess.initialize(self.root/'test',ends_at=self.end)
        owner_budget = PilotBudget.open(owner_access,ledger_path=self.budget.path)
        owner_budget.configure_hosted('owner')
        self.assertEqual(owner_budget.invite_cap,2*NANO)
        self.assertEqual(owner_budget.link_cap,20*NANO)
        self.assertEqual(owner_budget.service_tier,'default')
        self.assertEqual(owner_budget.model_spec(MODEL).input_rate,2000)
        self.assertEqual(self.budget.model_spec(MODEL).input_rate,12000)
        self.assertFalse(hasattr(owner_access,'restart_limit'))
        self.assertEqual(owner_budget.daily_cap_nano_usd,50*NANO)

    def test_shared_50_dollars_includes_existing_spending_and_concurrent_holds(self):
        # Synthetic preexisting spend from other visits, without replacing the ledger.
        key = self.charge(NANO)
        with self.budget.db() as db:
            db.execute('UPDATE pilot_charge_owner SET participant=? WHERE charge_id=?',('legacy-other',key))
            db.execute('UPDATE ai_charges SET charged=?,measured=? WHERE id=?',(49_800_000_000,49_800_000_000,key))
        def reserve(_):
            token = participant.set(self.owner)
            try:
                self.budget.reserve(1000,2400,MODEL); return True
            except BudgetError: return False
            finally: participant.reset(token)
        with ThreadPoolExecutor(2) as pool: self.assertEqual(sum(pool.map(reserve,range(2))),1)
        with self.budget.db() as db: self.assertLessEqual(self.budget._total(db)[0],50*NANO)


class HostedPolicyRoutes(unittest.TestCase):
    setUp, app, join = base.HostedTests.setUp, base.HostedTests.app, base.HostedTests.join

    def test_accelerator_http_reset_limit_and_model_configuration(self):
        with patch.object(base,'build_hosted',functools.partial(build_hosted,demo_policy='accelerator')):
            app = self.app(base.MemoryHistory())
        agent = app.adaptive.agent
        self.assertEqual(agent.client.service_tier,'ultrafast')
        self.assertEqual((agent.reasoning_effort,agent.composition_reasoning_effort),('low','low'))
        _, invite = self.access.issue_shared(expires_at=self.end,max_visits=20)
        cookies,csrf = self.join(app,token=invite)
        for left in range(4,-1,-1):
            code,body,_ = base.request(app,'/api/pilot/restart',cookies=cookies)
            self.assertEqual((code,json.loads(body)),(200,{'left':left,'limit':4}))
            if not left: break
            code,body,headers = base.request(app,'/api/pilot/restart',{'confirm':True},cookies,csrf)
            self.assertEqual((code,json.loads(body)['limit']),(200,4))
            fresh = headers['Set-Cookie'].split(';')[0]
            code,body,headers = base.request(app,'/api/guest/session',cookies=fresh)
            self.assertEqual(code,200)
            cookies = fresh+'; '+headers['Set-Cookie'].split(';')[0];csrf=json.loads(body)['csrf']
        self.assertEqual(base.request(app,'/api/pilot/restart',{'confirm':True},cookies,csrf)[0],409)

    def test_owner_keeps_standard_speed_and_five_in_visit_resets(self):
        with patch.object(base,'build_hosted',functools.partial(build_hosted,demo_policy='owner')):
            app = self.app(base.MemoryHistory())
        self.assertEqual(app.adaptive.agent.client.service_tier,'default')
        self.assertEqual(app.hosted_budget.invite_cap,2*NANO)
        _, invite = self.access.issue_shared(expires_at=self.end,max_visits=100)
        cookies,_ = self.join(app,token=invite)
        self.assertEqual(json.loads(base.request(app,'/api/pilot/restart',cookies=cookies)[1]),{'left':5,'limit':5})


if __name__=='__main__': unittest.main()
