import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock
import deploy_hosted_d207 as d
import server
from pilot_access import PilotAccess,HISTORY_NOTICE,participant
from pilot_budget import PilotBudget
from ai_budget import NANO,BudgetError

class AllowanceReset(unittest.TestCase):
    def test_reset_preserves_url_history_billing_global_cap_and_owner_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'operations').mkdir();(root/'config').mkdir();(root/'cohorts').mkdir()
            access=PilotAccess.initialize(root/'cohorts/pilot',ends_at=int(time.time())+3600)
            budget=PilotBudget.open(access,initialize=True);budget.configure_hosted('accelerator')
            for flag in ('all_chat','guest_chat'):access.set_flag(flag,True)
            link,token=access.issue_shared(expires_at=int(time.time())+3000,max_visits=20)
            cookie,_=access.redeem(token,consent_version=HISTORY_NOTICE);owner=access.authenticate(cookie)[0]
            context=participant.set(owner)
            self.addCleanup(participant.reset,context)
            key=budget.reserve(1000,2400,'gpt-6.1-sol')
            with budget.db() as db:db.execute("UPDATE ai_charges SET charged=?,measured=?,status='settled' WHERE id=?",(4*NANO,4*NANO,key))
            (root/'config/pilot.json').write_text(json.dumps({'demo_policy':'accelerator','ledger':str(budget.path)}))
            flags={'test':{'all_chat':1,'guest_chat':1},'pilot':{'all_chat':1,'guest_chat':1}}
            runtime=SimpleNamespace(STATE=root,CONFIG=root/'config',drained=Mock(return_value=True),chat_flags=Mock(return_value=flags))
            before_key=access.key
            report=d.reset_accelerator(runtime)
            self.assertEqual(report['admissions_available'],20)
            self.assertEqual(report['actual_shared_spend_usd'],4)
            self.assertEqual(report['allowance_credit_usd'],4)
            self.assertEqual(access.key,before_key);self.assertEqual(access.token_parts(token)[0],link)
            with budget.db() as db:
                self.assertEqual(budget._invite_spend(db,owner),0)
                self.assertEqual(budget._link_spend(db,owner),0)
                self.assertEqual(budget._total(db)[0],4*NANO)
                db.execute('UPDATE ai_charges SET charged=?,measured=? WHERE id=?',(50*NANO,50*NANO,key))
            with self.assertRaises(BudgetError):budget.reserve(1000,2400,'gpt-6.1-sol')
            self.assertTrue(d.reset_accelerator(runtime)['already_applied'])
            (root/'operations/d207-accelerator-reset.json').unlink()
            self.assertTrue(d.reset_accelerator(runtime)['already_applied'])
            with access.db() as db:self.assertEqual(db.execute('SELECT max_visits FROM shared_links').fetchone()[0],21)
            budget.configure_hosted('owner')
            with budget.db() as db:self.assertEqual(budget._invite_spend(db,owner),50*NANO)
            self.assertEqual(budget.invite_cap,2*NANO)
            runtime.chat_flags.assert_called_with(['test','pilot'],flags)
