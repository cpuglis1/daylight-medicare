"""Synthetic-only service tests; no real model, profile, credentials or external requests."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guest_profiles import GuestProfiles,ProfileError,validate_guide
from guide_agent import GuideAgent
from guide_server import make_server
from chat import ResponsesClient,ModelUnavailable
WEB=ROOT/'apps/chat'
CONTRACT=json.loads((WEB/'guide-contract.json').read_text());FACTS=json.loads((WEB/'teaching-facts.json').read_text())

def guide(save=True,sensitive=False):
    def e(v,raw=''):return {'value':v,'status':'reported','confirmation':'confirmed_by_user','source':'user_choice','rawText':raw,'revision':1,'confirmedAt':'2026-10-21T00:00:00Z'}
    return {'schemaVersion':2,'stateVersion':1,'fields':{'intent.goal':e('learn','private original text'),'subject.role':e('self'),'knowledge.general':e('new'),'privacy.persistenceChoice':e('save' if save else 'visit'),'needs.medications':e('Synthetic medicine 5 mg')},'flow':{'node':'L00','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'A01','invalidations':[],'scroll':0},'topics':{},'preferences':{'saveGuide':save,'saveSensitive':sensitive,'noticeVersion':'guest-notice-2026-10-21-v1'}}

def reply(**changes):
    return {'acknowledgment':'review','fact_ids':['basics'],'patches':[{'field':'intent.goal','value':'learn','status':'reported','quote':'understand Medicare'}],'suggested_node':'L00',**changes}

def client(value=None,seen=None):
    def transport(payload):
        if seen is not None:seen.append(payload)
        return {'model':'gpt-5.4','status':'completed','service_tier':'default','usage':{'input_tokens':100,'output_tokens':30,'total_tokens':130,'input_tokens_details':{'cached_tokens':0}},'output':[{'content':[{'type':'output_text','text':json.dumps(value or reply())}]}]}
    return ResponsesClient(key='synthetic-test-key',model='gpt-5.4',transport=transport)

class ProfileTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'private/guides.db';self.store=GuestProfiles(self.db,CONTRACT);self.token,self.info,_=self.store.session()
    def tearDown(self):self.tmp.cleanup()
    def test_cookie_token_is_opaque_and_only_hash_is_stored(self):
        self.assertEqual(len(self.token),43);self.assertNotIn(self.token,self.db.read_bytes().decode('latin1'));self.assertEqual(self.db.stat().st_mode&0o777,0o600)
    def test_new_session_has_no_profile(self):self.assertIsNone(self.store.get(self.token)['guide']);self.assertFalse(self.info['hasSaved'])
    def test_confirmed_save_survives_store_restart(self):
        receipt=self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide());self.assertEqual(receipt['version'],1);restored=GuestProfiles(self.db,CONTRACT).get(self.token);self.assertEqual(restored['guide']['fields']['intent.goal']['value'],'learn')
    def test_raw_and_sensitive_details_are_omitted_by_default(self):
        self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide());s=self.store.get(self.token)['guide'];self.assertNotIn('needs.medications',s['fields']);self.assertNotIn('rawText',s['fields']['intent.goal']);self.assertNotIn(b'private original',self.db.read_bytes())
    def test_sensitive_save_is_separate_and_removal_is_real(self):
        self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide(sensitive=True));self.assertIn('needs.medications',self.store.get(self.token)['guide']['fields']);self.store.save(self.token,self.info['csrf'],1,'operation-0002',guide(sensitive=False));self.assertNotIn('needs.medications',self.store.get(self.token)['guide']['fields'])
    def test_visit_choice_cannot_persist(self):
        with self.assertRaises(ProfileError):self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide(save=False))
    def test_csrf_and_unknown_session_cannot_update(self):
        with self.assertRaises(ProfileError):self.store.save(self.token,'wrong',0,'operation-0001',guide())
        with self.assertRaises(ProfileError):self.store.get('x'*43)
    def test_two_guests_are_isolated(self):
        other,_,_=self.store.session();self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide());self.assertIsNone(self.store.get(other)['guide']);self.assertNotEqual(self.token,other)
    def test_stale_save_cannot_overwrite(self):
        self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide())
        with self.assertRaises(ProfileError) as e:self.store.save(self.token,self.info['csrf'],0,'operation-0002',guide())
        self.assertEqual(e.exception.code,409)
    def test_idempotency_replays_once_and_rejects_payload_changes(self):
        self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide());self.assertTrue(self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide())['replayed']);changed=guide();changed['fields']['intent.goal']['value']='compare'
        with self.assertRaises(ProfileError):self.store.save(self.token,self.info['csrf'],0,'operation-0001',changed)
    def test_expiry_removes_profile_and_receipts(self):
        now=[1000000];s=GuestProfiles(self.db,CONTRACT,clock=lambda:now[0]);token,info,_=s.session();s.save(token,info['csrf'],0,'operation-0001',guide());now[0]+=8*86400;s.session()
        with self.assertRaises(ProfileError):s.get(token)
    def test_delete_revokes_session_and_cannot_delete_another_guest(self):
        self.store.save(self.token,self.info['csrf'],0,'operation-0001',guide());other,info,_=self.store.session()
        with self.assertRaises(ProfileError):self.store.delete(self.token,info['csrf'],1)
        self.assertTrue(self.store.delete(self.token,self.info['csrf'],1)['deleted']);self.assertIsNone(self.store.get(other)['guide'])
        with self.assertRaises(ProfileError):self.store.get(self.token)
    def test_verified_and_arbitrary_fields_are_rejected(self):
        for change in ['status','field','node']:
            g=guide()
            if change=='status':g['fields']['intent.goal']['status']='verified'
            if change=='field':g['fields']['insurance.approved']=g['fields']['intent.goal']
            if change=='node':g['flow']['node']='https://attacker.example'
            with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)
    def test_id_numbers_and_unsupported_schema_are_rejected(self):
        g=guide();g['fields']['intent.goal']['rawText']='123-45-6789'
        with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)
        g=guide();g['schemaVersion']=99
        with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)

    def test_concurrent_updates_cannot_both_win_the_same_version(self):
        results=[]
        def update(i):
            try:results.append(self.store.save(self.token,self.info['csrf'],0,'concurrent-'+str(i),guide())['version'])
            except ProfileError as e:results.append(e.code)
        threads=[threading.Thread(target=update,args=(i,)) for i in [1,2]]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(results,[1,409])
    def test_expiry_cleanup_does_not_require_a_resume_request(self):
        now=[1000000];s=GuestProfiles(self.db,CONTRACT,clock=lambda:now[0]);token,info,_=s.session();s.save(token,info['csrf'],0,'operation-0001',guide());now[0]+=8*86400;self.assertEqual(s.purge_expired(),1)
    def test_notice_version_is_required_before_saving(self):
        g=guide();g['preferences']['noticeVersion']='old-notice'
        with self.assertRaises(ProfileError):self.store.save(self.token,self.info['csrf'],0,'operation-0001',g)

class AgentTests(unittest.TestCase):
    def run_agent(self,value=None,seen=None):
        a=GuideAgent(CONTRACT,FACTS,client(value,seen),enabled=True);return a,a.run('owner','I want to understand Medicare',guide(),['L00'],'request-00001')
    def test_live_commands_do_not_commit_fields(self):a,r=self.run_agent();self.assertFalse(r['profileChanged']);self.assertEqual(r['patches'][0]['status'],'reported');self.assertTrue(r['facts']);self.assertEqual(r['mode'],'live_agent')
    def test_sensitive_lists_raw_profile_and_drafts_never_enter_model_context(self):
        seen=[];a,r=self.run_agent(seen=seen);raw=json.dumps(seen);self.assertNotIn('Synthetic medicine',raw);self.assertNotIn('private original',raw);self.assertFalse(seen[0]['store']);self.assertTrue(seen[0]['stream']);self.assertEqual(seen[0]['tools'],[])
    def test_proposal_is_owned_and_version_bound(self):
        a,r=self.run_agent();self.assertTrue(a.confirm('owner',r['proposalId'],1)['confirmed'])
        for who,revision in [('another',1),('owner',2)]:
            with self.assertRaises(ProfileError):a.confirm(who,r['proposalId'],revision)
    def test_unrecognized_fact_or_route_is_rejected(self):
        for value in [reply(fact_ids=['invented-price']),reply(suggested_node='O09'),reply(patches=[{'field':'insurance.approved','value':'yes','status':'reported','quote':'understand Medicare'}])]:
            with self.assertRaises((ModelUnavailable,ProfileError)):self.run_agent(value)
    def test_extraction_must_quote_latest_user_words(self):
        with self.assertRaises(ModelUnavailable):self.run_agent(reply(patches=[{'field':'intent.goal','value':'compare','status':'reported','quote':'not in message'}]))
    def test_budget_and_disabled_mode_do_not_silently_call_model(self):
        seen=[];a=GuideAgent(CONTRACT,FACTS,client(seen=seen),enabled=False)
        with self.assertRaises(ModelUnavailable):a.run('owner','understand Medicare',guide(),['L00'],'request-00001')
        self.assertFalse(seen);a.enabled=True;a.max_calls=1;a.run('owner','understand Medicare',guide(),['L00'],'request-00001')
        with self.assertRaises(ModelUnavailable):a.run('owner','understand Medicare',guide(),['L00'],'request-00002')
        self.assertEqual(len(seen),1)
    def test_retry_same_request_uses_completed_result(self):
        seen=[];a=GuideAgent(CONTRACT,FACTS,client(seen=seen),enabled=True);a.run('owner','understand Medicare',guide(),['L00'],'request-00001');a.run('owner','understand Medicare',guide(),['L00'],'request-00001');self.assertEqual(len(seen),1)
    def test_grounding_output_contains_only_selected_immutable_facts(self):
        a,r=self.run_agent(reply(patches=[]));self.assertEqual(r['facts'][0],a.facts['basics']);self.assertNotIn('reply',r);self.assertFalse(r['personalRecommendation'])

    def test_multi_component_coverage_is_normalized_without_inventing_a_component(self):
        a=GuideAgent(CONTRACT,FACTS,client(),enabled=True)
        self.assertEqual(a.interpret_value('coverage.current','original, medigap'),['original','medigap'])
        with self.assertRaises(ProfileError):a.interpret_value('coverage.current','none,original')
        self.assertEqual(a.field_rules()['coverage.enrollment']['b_only'],'Part B only, explicitly reported')
    def test_agent_cannot_propose_privacy_consent_or_claim_completed_outcomes(self):
        a=GuideAgent(CONTRACT,FACTS,client(),enabled=True)
        self.assertNotIn('privacy.persistenceChoice',a.fields);self.assertNotIn('outcome.status',a.fields);self.assertNotIn('comparison.snapshot',a.fields)

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,database=Path(self.tmp.name)/'private/guides.db',client=client(),enable_live=True,web=WEB,budget_database=Path(self.tmp.name)/'budget/usage.db',count_tokens=lambda *_:1000);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.origin=f'http://127.0.0.1:{self.server.server_port}';status,data,headers=self.request('GET','/api/guest/session');self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=data['csrf']
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);h={'Origin':self.origin,'Content-Type':'application/json',**({'Cookie':self.cookie,'X-Daylight-CSRF':self.csrf} if hasattr(self,'cookie') else {}),**(headers or {})};c.request(method,path,json.dumps(body) if body is not None else None,h);r=c.getresponse();raw=r.read();mime=r.getheader('Content-Type','');value=json.loads(raw) if 'application/json' in mime else raw.decode(errors='replace');out=(r.status,value,dict(r.getheaders()));c.close();return out
    def test_app_agent_and_samples_are_independent_of_plan_gate(self):
        self.assertIn('Your coverage',self.request('GET','/')[1]);s=self.request('GET','/api/status')[1];self.assertFalse(s['consumer_ready']);self.assertTrue(s['agent_available']);self.assertEqual(len(self.request('GET','/api/sample-plans')[1]['plans']),5);self.assertEqual(self.request('POST','/api/catalog',{})[0],503)
    def test_cookie_http_only_same_site_and_no_url_ids(self):
        _,data,headers=self.request('GET','/api/guest/session',headers={'Cookie':''});cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie);self.assertNotIn('Secure',cookie);self.assertNotIn('token',data);self.assertEqual(self.request('GET','/api/guest/profile?token=guess')[0],422)
    def test_missing_csrf_wrong_origin_and_cross_site_are_blocked(self):
        b={'expectedVersion':0,'operationId':'operation-0001','guide':guide()}
        for h in [{'X-Daylight-CSRF':''},{'Origin':'https://evil.invalid'},{'Sec-Fetch-Site':'cross-site'}]:self.assertEqual(self.request('PUT','/api/guest/profile',b,h)[0],403)
    def test_save_resume_delete_receipts(self):
        self.assertEqual(self.request('PUT','/api/guest/profile',{'expectedVersion':0,'operationId':'operation-0001','guide':guide()})[0],200);self.assertTrue(self.request('GET','/api/guest/profile')[1]['hasSaved']);r=self.request('DELETE','/api/guest/profile',{'expectedVersion':1,'confirmed':True});self.assertTrue(r[1]['deleted']);self.assertIn('Max-Age=0',r[2]['Set-Cookie'])
    def test_stream_has_status_then_validated_result_without_profile_write(self):
        status,body,_=self.request('POST','/api/agent',{'message':'understand Medicare','guide':guide(),'eligible':['L00'],'requestId':'request-00001','aiConsent':True},{'Accept':'text/event-stream'});self.assertEqual(status,200);self.assertIn('event: status',body);self.assertIn('event: complete',body);self.assertIsNone(self.request('GET','/api/guest/profile')[1]['guide'])
    def test_ai_consent_and_payload_bounds(self):
        self.assertEqual(self.request('POST','/api/agent',{'message':'hello'})[0],422);self.assertEqual(self.request('POST','/api/agent',{'message':'x'*90000})[0],413)
    def test_no_query_or_path_traversal_static_access(self):
        self.assertEqual(self.request('GET','/../scripts/guide_server.py')[0],404);self.assertEqual(self.request('GET','/.env')[0],404)
    def test_samples_are_source_labeled_and_do_not_supply_fit(self):
        s=self.request('GET','/api/sample-plans')[1];self.assertTrue(s['not_recommendation']);self.assertTrue(s['not_comprehensive'])
        for p in s['plans']:self.assertEqual(p['provider_fit'],'unknown');self.assertEqual(p['validation_status'],'sample_unvalidated');self.assertTrue(p['source']['archive_sha256']);self.assertTrue(p['source']['record_ordinal'])

class SourceAndProductionTests(unittest.TestCase):
    def test_sample_identities_match_actual_locally_captured_cms_rows(self):
        from research import ReadModel
        snapshot=ReadModel().catalog('2027','12021');rows={r['id']:r for r in snapshot['options']+snapshot['exclusions']};samples=json.loads((WEB/'sample-plans.json').read_text())
        for p in samples['plans']:
            row=rows[p['id']];self.assertEqual(p['name'],row['name']);self.assertEqual(p['source']['archive_sha256'],row['source']['archive_sha256']);self.assertEqual(p['source']['record_ordinal'],row['source']['record_ordinal']);self.assertEqual(p['geography'],row['source_geography'])
    def test_production_requires_https_and_uses_secure_host_cookie(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):make_server(0,database=Path(directory)/'private/db',production=True,web=WEB)
            server=make_server(0,database=Path(directory)/'private/db',production=True,public_origin='https://example.invalid',web=WEB);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('GET','/api/guest/session',headers={'Host':'example.invalid','Origin':'https://example.invalid'});r=c.getresponse();r.read();cookie=r.getheader('Set-Cookie');self.assertIn('__Host-daylight_guest=',cookie);self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);c.close()
            finally:server.shutdown();server.server_close();thread.join()
