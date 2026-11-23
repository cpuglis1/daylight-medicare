"""D221 offline hosted integration: fictional invitations, local receipts, no provider."""
import functools
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import server
sys.path.insert(0, str(server.REPO / 'alternatives/one-call'))
sys.path.insert(0, str(server.REPO / 'alternatives/one-call/tests'))
sys.path.insert(0, str(server.REPO / 'infrastructure/daylight-data/src'))
import _one_call_support as support
from one_call_flow import OneCallConversation
from hosted_server import build_hosted
from pilot_access import participant
from ai_budget import BudgetError
import test_hosted_history as base
from test_d206_hosted_policy import HostedPolicy
from test_d207_hosted_selectors import HostedSelectors, Drugs
from hosted_doctors import DoctorClient, serve
from daylight_data.serving.binding import ResearchServingError


class Integration(unittest.TestCase):
    setUp, app, join = base.HostedTests.setUp, base.HostedTests.app, base.HostedTests.join

    def test_both_policies_use_one_call_keep_budget_history_and_checks(self):
        for policy, tier, cap in [('owner','default',2),('accelerator','ultrafast',5)]:
            with self.subTest(policy=policy), patch.object(base,'build_hosted',functools.partial(
                    build_hosted,one_call=True,demo_policy=policy,checks=(object(),Drugs()))):
                app = self.app(base.MemoryHistory())
                self.assertIsInstance(app.adaptive,OneCallConversation)
                self.assertEqual(app.adaptive.pilot_knowledge.surface,'hosted-demo')
                self.assertEqual(app.adaptive.agent.client.service_tier,tier)
                self.assertEqual(app.hosted_budget.invite_cap,cap*10**9)
                self.assertIs(app.adaptive.agent.budget,app.hosted_budget)
                self.assertFalse(app.adaptive.one_call_eval)
                self.assertIsNone(getattr(app.adaptive,'one_call_trace',None))
                cookies,_=self.join(app)
                code,raw,_=base.request(app,'/api/status',cookies=cookies)
                status=json.loads(raw)
                self.assertEqual(code,200)
                self.assertEqual(status['one_call']['loop'],'one-call')
                self.assertTrue(status['local_demo']['conversation_checks'])
                self.assertNotEqual(base.request(app,'/api/status')[0],200)

    def test_typed_turn_uses_scripted_one_call_and_archives_before_delivery(self):
        from chat import ResponsesClient
        from natural_flow import CONTEXT_POLICY
        history=base.MemoryHistory()
        with patch.object(base,'build_hosted',functools.partial(build_hosted,one_call=True,demo_policy='accelerator')):
            app=self.app(history)
        script=support.Script()
        script.steps.append([support.message(support.reply(question='What would you like help with?'))])
        def transport(payload):
            receipt=script(payload);receipt['model']='gpt-6.1-sol';receipt['service_tier']='ultrafast';return receipt
        agent=app.adaptive.agent
        agent.client=ResponsesClient(key='offline',model='gpt-6.1-sol',transport=transport)
        agent.client.service_tier='ultrafast';agent.enabled=True
        agent.count_tokens=lambda *_:300
        app.adaptive.fixture=False;app.adaptive.model_agents={'gpt-6.1-sol':agent}
        app.adaptive.reconciler.enabled=False
        app.hosted_budget.clock=self.budget.clock
        cookies,csrf=self.join(app)
        _,raw,_=base.request(app,'/api/conversation/initial',cookies=cookies)
        state=json.loads(raw)
        payload={k:state[k] for k in ('guide','record','continuation') if k in state}
        payload.update(requestId='d221-scripted-turn',action={'type':'message','message':'I have a question.'},
            aiConsent=True,contextPolicy=CONTEXT_POLICY)
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No provider network')):
            code,raw,_=base.request(app,'/api/conversation/turn',payload,cookies,csrf)
        self.assertEqual(code,200,raw)
        self.assertEqual(len(script.sent),1,raw)
        self.assertEqual(script.sent[0]['service_tier'],'ultrafast')
        self.assertEqual(script.sent[0]['reasoning']['effort'],'low')
        self.assertTrue(any(v['status']=='response_ready' for v in history.rows.values()))
        with app.hosted_budget.db() as db:
            self.assertGreater(db.execute("SELECT sum(measured) FROM ai_charges").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM ai_charges WHERE status='reserved'").fetchone()[0],0)


class OneCallSelectors(HostedSelectors):
    def turn(self, action):
        out=super().turn(action)
        if action.get('type') == 'task':
            from natural_flow import CONTEXT_POLICY
            flow=self.service.adaptive
            owner=next(iter(flow.current_chain))
            # Fixture begins after agreeing to work on the profile.
            flow.one_call_visits.add(owner,flow.current_chain[owner],CONTEXT_POLICY,detail_permission='granted')
        return out

    def start(self):
        with patch('test_d207_hosted_selectors.build_hosted',functools.partial(build_hosted,one_call=True)):
            super().start()

    def test_timing_journey_reaches_doctors_then_medicine_strength_choices(self):
        # Same existing HTTP journey, with one-call's compact matched-product result.
        self.start();self.choice('T06',text='Fictional Doctor in Naples');self.choice('T07',text='Fictional medicine')
        self.choice('T03',zip='34102')
        q=self.state['conversationCheck']['question'];self.assertEqual(q['field'],'doctor')
        self.turn({'type':'check_answer','token':q['token'],'value':'__later__'})
        q=self.state['conversationCheck']['question'];self.assertEqual(q['field'],'formulary_product')
        self.assertEqual(len(q['choices']),9)
        self.turn({'type':'check_answer','token':q['token'],'value':q['choices'][0]['value']})
        self.assertTrue(any(r['kind']=='note' for r in self.state['conversationCheck']['results']))


class WorkerBudget(HostedPolicy):
    def run_worker(self, work):
        from one_call_reconcile import Reconciler
        from types import SimpleNamespace
        done=threading.Event();errors=[]
        flow=SimpleNamespace(fixture=False,agent=SimpleNamespace(enabled=True,client=SimpleNamespace(available=True)))
        worker=Reconciler(flow)
        def execute(job):
            try:work()
            except BaseException as error:errors.append(error)
            finally:done.set()
        with patch('one_call_reconcile.legacy_projection',return_value=({},{})), \
             patch('one_call_reconcile.extraction_context',return_value={}), \
             patch.object(worker,'_work',side_effect=execute):
            self.assertTrue(worker.schedule('fictional-owner','chain',message='A fictional question',guide={},record={}))
            self.assertTrue(done.wait(5))
        if errors:raise errors[0]

    def test_background_call_is_attributed_and_settled_in_original_session(self):
        def work():
            self.assertEqual(participant.get(),self.owner)
            key=self.budget.reserve(1000,2400,'gpt-6.1-sol')
            self.budget.settle_model(key,{'model':'gpt-6.1-sol','service_tier':'ultrafast','status':'completed',
                'usage':{'input_tokens':1000,'output_tokens':100,'total_tokens':1100,
                         'input_tokens_details':{'cached_tokens':0}}},'gpt-6.1-sol')
        self.run_worker(work)
        with self.budget.db() as db:
            self.assertEqual(db.execute('SELECT participant FROM pilot_charge_owner').fetchone()[0],self.owner)
            self.assertGreater(self.budget._invite_spend(db,self.owner),0)

    def test_background_call_cannot_exceed_original_session_cap_after_reset(self):
        self.charge(4_900_000_000)
        session,_,_=self.access.restart(self.owner)
        self.owner=self.access.authenticate(session)[0];participant.set(self.owner)
        def work():
            with self.assertRaises(BudgetError):self.budget.reserve(1000,2400,'gpt-6.1-sol')
        self.run_worker(work)


class SocketChecks(unittest.TestCase):
    def test_shared_reader_preserves_payload_and_fails_closed(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        temp=tempfile.TemporaryDirectory(prefix='d221-',dir='/tmp');self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'doctors.sock'
        doctors=SimpleNamespace(reader=SimpleNamespace(snapshot=lambda **_:nullcontext()),
            search=lambda **q:{'candidates':[{'label':'Fictional Doctor'}],'query':q},
            sites=lambda *a,**kw:{'sites':[]},network_matrix=lambda *a,**kw:{'plans':{}})
        try:app=serve(path,doctors,'a'*64)
        except PermissionError:self.skipTest('Local sandbox disallows Unix listeners; run on hosted staging')
        thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
        self.addCleanup(app.server_close);self.addCleanup(thread.join,5);self.addCleanup(app.shutdown)
        client=DoctorClient(path)
        self.assertEqual(client.health()['release'],'a'*64)
        self.assertEqual(client.search(name='Fictional Doctor'),doctors.search(name='Fictional Doctor'))
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        with self.assertRaises(ResearchServingError):client.call('__dict__')
        def withdrawn(**_):raise ResearchServingError('PILOT_SOURCE_WITHDRAWAL_OR_CONTROL_CHANGE')
        doctors.search=withdrawn
        with self.assertRaisesRegex(ResearchServingError,'WITHDRAWAL'):client.search(name='Fictional Doctor')
