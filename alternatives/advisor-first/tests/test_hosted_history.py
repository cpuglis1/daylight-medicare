"""Fictional, provider-free hosted journeys and failure/abuse checks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import http.client
import io
import json
from pathlib import Path
import socketserver
import tempfile
from threading import RLock
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import server
from ai_budget import BudgetError, NANO
from guest_profiles import ProfileError
from hosted_history import content, install, HistoryUnavailable, PostgresHistory, durable_delete
from hosted_server import build_hosted
from pilot_access import PilotAccess, HISTORY_NOTICE, participant
from pilot_budget import PilotBudget


class MemoryHistory:
    """Fault-injectable storage double; PostgreSQL has a separate integration test."""
    def __init__(self):
        self.rows={}; self.fail_begin=False; self.fail_finish=False
    def begin(self,visit,request,policy,payload,metadata):
        if self.fail_begin: raise HistoryUnavailable()
        key=(visit,request)
        if key in self.rows:
            if self.rows[key]['payload'] != payload: raise ProfileError('Conflict',409)
            return self.rows[key]['status']
        self.rows[key]={'payload':payload,'status':'accepted','metadata':metadata}
    def finish(self,visit,request,response,usage,error_code=None):
        if self.fail_finish: raise HistoryUnavailable()
        self.rows[visit,request].update(response=response,status='failed' if error_code else 'response_ready',error=error_code)
    def ready(self,visit,request):
        return self.rows.get((visit,request),{}).get('status')=='response_ready'
    def delete(self,visit):
        self.rows={k:v for k,v in self.rows.items() if k[0]!=visit}


class Wire:
    def __init__(self,data): self.input=io.BytesIO(data); self.output=bytearray()
    def makefile(self,*args,**kwargs): return self.input
    def sendall(self,data): self.output.extend(data)
    def settimeout(self,*args): pass


def request(app,path,body=None,cookies='',csrf=None,extra_headers=None):
    payload=json.dumps(body).encode() if body is not None else b''
    headers={'Host':'daylight.example','Origin':'https://daylight.example','Connection':'close'}
    if body is not None: headers.update({'Content-Type':'application/json','Content-Length':str(len(payload))})
    if cookies: headers['Cookie']=cookies
    if csrf: headers['X-Daylight-CSRF']=csrf
    if extra_headers:
        for k,v in extra_headers.items():
            if v is None:headers.pop(k,None)
            else:headers[k]=v
    raw=(('POST' if body is not None else 'GET')+' '+path+' HTTP/1.1\r\n'
         +''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n').encode()+payload
    wire=Wire(raw)
    app.RequestHandlerClass(wire,('127.0.0.1',1),app)
    response=http.client.HTTPResponse(Wire(bytes(wire.output)));response.begin()
    data=response.read()
    return response.status,data,response.headers


class HostedTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.end=int(time.time())+7200
        self.access=PilotAccess.initialize(self.root/'pilot',ends_at=self.end)
        self.budget=PilotBudget.open(self.access,initialize=True)
        self.budget.clock=lambda:datetime.fromisoformat(self.budget.rates['verified_at']).timestamp()
        for flag in ('guest_chat','all_chat'):self.access.set_flag(flag,True)

    def visit(self,consent=HISTORY_NOTICE):
        key,token=self.access.issue(expires_at=self.end)
        session,_=self.access.redeem(token,consent_version=consent)
        return key,session

    def app(self,history,*,synthetic=True,key=None,paused=False):
        def bind(service): service.server_name='localhost';service.server_port=19013
        with patch('http.server.HTTPServer.server_bind',bind),patch.object(socketserver.TCPServer,'server_activate'):
            app=build_hosted(0,state=self.access.root,origin='https://daylight.example',
                ledger=self.budget.path,history=history,binding={'snapshot_id':'a'*64},
                medigap=Mock(),pdp=Mock(),release='b'*64,synthetic=synthetic,key=key,paused=paused)
        self.addCleanup(app.server_close)
        return app

    def join(self,app,*,consent=True,token=None):
        if token is None: _,token=self.access.issue(expires_at=self.end)
        body={'invitation':token}
        if consent:body['historyConsent']=HISTORY_NOTICE
        code,_,headers=request(app,'/pilot/redeem',body)
        self.assertEqual(code,200)
        cookies=headers['Set-Cookie'].split(';')[0]
        code,data,headers=request(app,'/api/guest/session',cookies=cookies)
        self.assertEqual(code,200)
        cookies+='; '+headers['Set-Cookie'].split(';')[0]
        return cookies,json.loads(data)['csrf']

    def initial(self,app,cookies):
        code,data,_=request(app,'/api/conversation/initial',cookies=cookies)
        self.assertEqual(code,200)
        data=json.loads(data)
        return {'guide':data['guide'],'record':data['record'],'requestId':'fictional-turn-001',
                'action':{'type':'message','message':'I would like to understand Medicare.'},'aiConsent':True}

    def test_shared_link_creates_isolated_visits_and_revokes_children(self):
        link,token=self.access.issue_shared(expires_at=self.end,max_visits=2)
        a,_=self.access.redeem(token);b,_=self.access.redeem(token)
        self.assertNotEqual(self.access.authenticate(a)[0],self.access.authenticate(b)[0])
        with self.assertRaises(ProfileError):self.access.redeem(token)
        self.access.revoke_shared(link)
        for cookie in (a,b):
            with self.assertRaises(ProfileError):self.access.authenticate(cookie)

    def test_shared_redemption_is_atomic(self):
        _,token=self.access.issue_shared(expires_at=self.end,max_visits=3)
        def attempt(_):
            try:self.access.redeem(token);return True
            except ProfileError:return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt,range(12))),3)

    def test_bad_consent_does_not_consume_invitation(self):
        _,token=self.access.issue(expires_at=self.end)
        with self.assertRaises(ProfileError):self.access.redeem(token,consent_version='old')
        self.access.redeem(token,consent_version=HISTORY_NOTICE)

    def test_both_environments_share_one_cumulative_hard_cap(self):
        other=PilotAccess.initialize(self.root/'test',ends_at=self.end)
        for flag in ('guest_chat','all_chat'):other.set_flag(flag,True)
        shared=PilotBudget.open(other,ledger_path=self.budget.path);shared.clock=self.budget.clock
        for i in range(10):
            access,budget=(self.access,self.budget) if i%2==0 else (other,shared)
            key,token=access.issue(expires_at=self.end);access.redeem(token)
            context=participant.set(key)
            try:budget.reserve(790400,2400,'gpt-6.1-sol')
            finally:participant.reset(context)
        key,_=self.visit();context=participant.set(key)
        try:
            with self.assertRaises(BudgetError):self.budget.reserve(1,2400,'gpt-6.1-sol')
        finally:participant.reset(context)
        with shared.db() as db:self.assertEqual(shared._total(db)[0],20*NANO)

    def test_shared_link_budget_attribution_and_session_cap(self):
        link,token=self.access.issue_shared(expires_at=self.end)
        session,_=self.access.redeem(token);key,_=self.access.authenticate(session)
        context=participant.set(key)
        try:
            self.budget.reserve(790400,2400,'gpt-6.1-sol')
            with self.assertRaises(BudgetError):self.budget.reserve(1,2400,'gpt-6.1-sol')
        finally:participant.reset(context)
        with self.budget.db() as db:
            self.assertEqual(db.execute('SELECT link_id FROM pilot_visit_link WHERE participant=?',(key,)).fetchone()[0],link)
            self.assertEqual(self.budget._link_spend(db,key),2*NANO)

    def test_identifier_and_secret_rejected_before_archive(self):
        for value in ('123-45-6789','1EG4-TE5-MK73','0EG4-TE5-MK73','sk-abcdefghijklmnopqrstuvwx'):
            with self.subTest(value=value):
                with self.assertRaises(ProfileError):content({'action':{'text':value}},submitted=True)
        self.assertEqual(content({'csrf':'x','nested':{'reviewToken':'y'},'reply':'Hello'}),{'nested':{},'reply':'Hello'})

    def test_consent_notice_unchecked_and_one_public_join_action(self):
        app=self.app(MemoryHistory())
        code,body,_=request(app,'/pilot/join')
        self.assertEqual(code,200);self.assertIn(b'90 days',body)
        self.assertNotIn(b'type="checkbox" checked',body);self.assertEqual(body.count(b'<button '),1)

    def test_invitation_opens_from_accelerator_link_but_cross_site_fetch_is_denied(self):
        app=self.app(MemoryHistory())
        navigation={'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document','Origin':None}
        self.assertEqual(request(app,'/pilot/join',extra_headers=navigation)[0],200)
        self.assertEqual(request(app,'/pilot/join',extra_headers={**navigation,'Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':'empty'})[0],403)
        self.assertEqual(request(app,'/api/status',extra_headers=navigation)[0],403)

    def test_decline_keeps_browsing_without_history_or_paid_chat(self):
        history=MemoryHistory();app=self.app(history);cookies,csrf=self.join(app,consent=False)
        payload=self.initial(app,cookies)
        code,_,_=request(app,'/api/conversation/turn',payload,cookies,csrf)
        self.assertEqual(code,428);self.assertEqual(history.rows,{})
        self.assertEqual(request(app,'/',cookies=cookies)[0],200)
        session=cookies.split(';')[0].split('=',1)[1]
        key,_=self.access.authenticate(session);context=participant.set(key)
        try:
            with self.assertRaises(BudgetError):app.hosted_budget.assert_issue_allowed()
        finally:participant.reset(context)

    def test_accepted_turn_and_checked_reply_saved_with_release(self):
        history=MemoryHistory();app=self.app(history);cookies,csrf=self.join(app)
        payload=self.initial(app,cookies)
        code,body,headers=request(app,'/api/conversation/turn',payload,cookies,csrf)
        self.assertEqual(code,200,body)
        row=next(iter(history.rows.values()))
        self.assertEqual(row['status'],'response_ready');self.assertEqual(row['metadata']['model'],'gpt-6.1-sol')
        self.assertEqual(row['metadata']['reasoning'],'low');self.assertEqual(headers['X-Daylight-Release'],'b'*64)
        self.assertEqual(row['response'],json.loads(body))
        code,resumed,_=request(app,'/api/conversation/resume',{'requestId':payload['requestId']},cookies,csrf)
        self.assertEqual(code,200,resumed)
        self.assertEqual(json.loads(resumed)['status'],'resumed')
        self.assertEqual(len(history.rows),1)
        # D199: evaluation-only sorting is installed on the hosted demo; empty inputs are refused.
        self.assertEqual(request(app,'/api/recommendation',{},cookies,csrf)[0],422)

    def test_input_archive_failure_prevents_conversation_execution(self):
        history=MemoryHistory();history.fail_begin=True;app=self.app(history);cookies,csrf=self.join(app)
        payload=self.initial(app,cookies)
        with patch.object(app.adaptive,'_selected_turn',side_effect=AssertionError('must not execute')):
            self.assertEqual(request(app,'/api/conversation/turn',payload,cookies,csrf)[0],503)

    def test_reply_archive_failure_blocks_delivery_and_recovery(self):
        history=MemoryHistory();history.fail_finish=True;app=self.app(history);cookies,csrf=self.join(app)
        payload=self.initial(app,cookies)
        self.assertEqual(request(app,'/api/conversation/turn',payload,cookies,csrf)[0],503)
        row=next(iter(history.rows.values()));self.assertEqual(row['status'],'accepted')
        recovery={k:v for k,v in payload.items() if k!='aiConsent'}
        code,body,_=request(app,'/api/conversation/recover',recovery,cookies,csrf)
        self.assertNotIn('response',json.loads(body))
        self.assertNotEqual(code,200,body)
        code,body,_=request(app,'/api/conversation/progress',{'requestId':payload['requestId']},cookies,csrf)
        self.assertEqual(code,200)
        self.assertNotEqual(json.loads(body).get('state'),'complete')

    def test_progress_never_carries_unarchived_reply_blocks(self):
        app=self.app(MemoryHistory());progress=app.adaptive.turn_progress
        key=('fictional-owner','request-one')
        progress.begin(key);progress.publish(key,['Not archived yet'])
        self.assertNotIn('blocks',progress.read(*key))

    def test_hosted_startup_refuses_early_block_delivery(self):
        with patch.dict('os.environ',{'DAYLIGHT_BLOCK_RELEASE':'on'}):
            with self.assertRaises(ValueError):self.app(MemoryHistory())

    def test_live_wiring_has_only_sol61_low_and_shared_ledger_without_dev_secrets(self):
        history=PostgresHistory('fictional-unused-dsn',connect=Mock(side_effect=AssertionError('No database probe')))
        with patch.dict('os.environ',{'DAYLIGHT_MODEL_ENVIRONMENT':'hosted-demo'}), \
             patch('model_router.allowed_models',return_value={'gpt-6.1-sol'}), \
             patch.object(history,'check_runtime_role'), \
             patch('server.load_model_env',side_effect=AssertionError('Must not read development secrets')):
            app=self.app(history,synthetic=False,key='fictional-key-not-a-credential')
        self.assertFalse(app.adaptive.fixture)
        self.assertEqual(set(app.adaptive.model_agents),{'gpt-6.1-sol'})
        agent=app.adaptive.agent
        self.assertEqual((agent.reasoning_effort,agent.composition_reasoning_effort),('low','low'))
        self.assertEqual(agent.budget.path,self.budget.path)
        self.assertIsNone(app.budget)  # Pinned factory never creates/seeds its development ledger.
        self.assertFalse(app.agent.enabled)  # All non-adaptive model routes remain disabled.

    def test_paused_real_runtime_needs_no_provider_route_or_key_and_cannot_chat(self):
        history=PostgresHistory('fictional-unused-dsn',connect=Mock(side_effect=AssertionError('No database probe')))
        with patch.dict('os.environ',{'DAYLIGHT_MODEL_ENVIRONMENT':'hosted-demo'}), \
             patch('model_router.allowed_models',side_effect=AssertionError('No provider setup needed')), \
             patch.object(history,'check_runtime_role'), \
             patch('server.load_model_env',side_effect=AssertionError('No development secrets')):
            app=self.app(history,synthetic=False,key=None,paused=True)
        self.assertFalse(app.adaptive.fixture)
        self.assertFalse(app.adaptive.agent.enabled)
        self.assertFalse(app.adaptive.agent.client.available)
        self.assertTrue(app.hosted_paused)
        cookies,csrf=self.join(app)
        # Even if operators accidentally enable ledger flags, paused mode refuses
        # a message before touching history or attempting a provider request.
        payload=self.initial(app,cookies)
        self.assertEqual(request(app,'/api/conversation/turn',payload,cookies,csrf)[0],503)

    def test_live_runtime_refuses_unconfigured_dedicated_project(self):
        history=PostgresHistory('fictional-unused-dsn',connect=Mock())
        with patch.dict('os.environ',{'DAYLIGHT_MODEL_ENVIRONMENT':'hosted-demo'}), \
             patch('model_router.allowed_models',return_value=frozenset()), \
             patch.object(history,'check_runtime_role'):
            with self.assertRaisesRegex(ValueError,'provider route is not configured'):
                self.app(history,synthetic=False,key='fictional-key')

    def test_durable_delete_requires_broker_ack_and_never_falls_back_to_sql(self):
        history=PostgresHistory('fictional-unused-dsn',connect=Mock(side_effect=AssertionError('No direct SQL deletion')),
                                deletion_environment='pilot')
        with patch('hosted_history.durable_delete') as broker:
            history.delete('a'*32)
            broker.assert_called_once_with('pilot','a'*32)
        with patch('hosted_history.durable_delete',side_effect=HistoryUnavailable()):
            with self.assertRaises(HistoryUnavailable):history.delete('a'*32)

    def test_deletion_broker_client_handles_fragmented_ack_and_fails_closed(self):
        peer=Mock();peer.__enter__=Mock(return_value=peer);peer.__exit__=Mock(return_value=False)
        peer.recv.side_effect=[b'{"deleted":',b'true}\n']
        with patch('hosted_history.socket.socket',return_value=peer):
            durable_delete('test','b'*32)
        sent=json.loads(peer.sendall.call_args[0][0]);self.assertEqual(sent,{'environment':'test','visit':'b'*32})
        for reply in (b'{"deleted":false}\n',b'not json\n',b'x'*129,b''):
            peer.recv.side_effect=[reply]
            with patch('hosted_history.socket.socket',return_value=peer):
                with self.assertRaises(ProfileError):durable_delete('test','b'*32)

    def test_two_reviewers_cannot_read_or_delete_each_others_visit(self):
        history=MemoryHistory();app=self.app(history)
        _,token=self.access.issue_shared(expires_at=self.end)
        first,csrf1=self.join(app,token=token);second,csrf2=self.join(app,token=token)
        self.assertEqual(request(app,'/api/conversation/turn',self.initial(app,first),first,csrf1)[0],200)
        first_key=next(iter(history.rows))[0]
        self.assertEqual(request(app,'/api/pilot/history/delete',{'confirm':True},second,csrf1)[0],403)
        self.assertEqual(request(app,'/api/pilot/history/delete',{'confirm':True},second,csrf2)[0],200)
        self.assertTrue(any(k[0]==first_key for k in history.rows))
        self.assertEqual(request(app,'/api/pilot/history/delete',{'confirm':True},first,csrf1)[0],200)
        self.assertEqual(history.rows,{})
        self.assertEqual(request(app,'/',cookies=first)[0],303)
        self.assertEqual(request(app,'/api/guest/session',cookies=first)[0],401)


if __name__=='__main__':unittest.main()
