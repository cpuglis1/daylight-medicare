"""D79 executable task traces. Synthetic data, isolated SQLite, no paid provider."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chat_server import build
from adaptive_flow import CONTRACT, Q, month
from guest_profiles import ProfileError

class AdaptiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=build(0,fixture=True,database=Path(cls.tmp.name)/'private/test.sqlite3')
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.flow=cls.server.adaptive
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def setUp(self):self.g,self.r=self.flow.initial();self.owner=uuid.uuid4().hex
    def turn(self,action,**extra):
        p={'guide':self.g,'record':self.r,'action':action,'requestId':str(uuid.uuid4()),'aiConsent':True,**extra}
        result=self.flow.turn(self.owner,p);self.g=result['guide'];self.r=result['record'];return result
    def choice(self,id,**fields):return self.turn({'type':'choice','id':id,'fields':fields})
    def task(self,task):return self.turn({'type':'task','task':task,'preparing':True})
    def q(self):return self.flow.assess(self.g,self.r)['nextQuestion']
    def known(self):
        self.choice('RC01',choice='self');self.choice('T03',zip='34102');self.choice('T04',choice='month',month='January 2027');self.choice('T05',choice='employer')
    def test_exact_inventory_and_seven_part_maps(self):
        self.assertEqual(len(Q),41);self.assertEqual(len(CONTRACT['fields']),78);self.assertEqual(len(CONTRACT['gaps']),14)
        for row in [*CONTRACT['fields'].values(),*CONTRACT['gaps']]:
            for key in ['decision_affected','requirement','trigger','acceptable_evidence_or_confirmation','unknown_conflict_handling','source_data_layer','readiness_gate']:self.assertTrue(row[key])
        self.assertEqual(set(self.flow.assess(self.g,self.r)['ruleDecisions']),set(Q))
    def test_explicit_learning_question_has_no_intake(self):
        result=self.turn({'type':'message','message':'What is Medicare Advantage?'})
        self.assertTrue(result['facts']);self.assertEqual(result['assessment']['task'],'learn');self.assertIsNone(self.q());self.assertLessEqual(set(self.g['fields']),{'intent.goal'})
    def test_browsing_requires_scope_only(self):
        self.task('browse');self.assertEqual(self.q()['id'],'T03');self.choice('T03',zip='34102');self.assertEqual(self.q()['id'],'RC03');self.choice('RC03',year='2026');self.assertIsNone(self.q());self.assertEqual(set(self.g['fields']),{'intent.goal','comparison.scope.zip','comparison.scope.county','comparison.scope.locationEvidence'})
    def test_compare_limit_does_not_force_preparation(self):
        result=self.turn({'type':'task','task':'compare','preparing':False});self.assertIsNone(self.q());self.assertIn('held',result['assessment']['limitation']);self.assertFalse(result['assessment']['personalizedRecommendationAllowed'])
    def test_unknowns_terminate_without_readiness(self):
        self.task('compare')
        for _ in range(12):
            q=self.q()
            if not q:break
            self.turn({'type':'unknown','id':q['id']})
        self.assertIsNone(self.q());self.assertFalse(self.flow.assess(self.g,self.r)['externalVerificationReady']);self.assertFalse(self.flow.assess(self.g,self.r)['personalizedRecommendationAllowed'])
    def test_job_dates_group_only_missing_and_child_not_repeated(self):
        self.task('timing');self.known();self.choice('RC04',choice='neither');self.choice('RC09',choice='my_job');self.assertEqual([f['key'] for f in self.q()['fields']],['jobEnd','coverageEnd']);self.choice('RC11',jobEnd='December 2026');self.assertEqual([f['key'] for f in self.q()['fields']],['coverageEnd']);self.turn({'type':'unknown','id':'RC11'});self.assertIsNone(self.q());self.assertEqual(self.r['facts']['RC11']['value']['jobEnd'],'2026-12')
    def test_known_fields_reused_after_task_change(self):
        self.known();self.task('timing');self.assertEqual(self.q()['id'],'RC09');self.assertNotIn('T02',[self.q()['id']]);self.choice('RC09',choice='my_job');self.choice('RC11',jobEnd='December 2026',coverageEnd='January 2027');self.assertIsNone(self.q())
    def test_direct_choice_uses_no_llm(self):
        self.task('compare');result=self.choice('RC01',choice='self');self.assertEqual(result['metrics']['llmCalls'],0)
    def test_full_message_only_fast_path(self):
        q=self.flow.question('RC10');self.assertIsNotNone(self.flow.direct('20 or more',q));self.assertIsNone(self.flow.direct('Yes, and my insurance ends in January 2027',q))
    def test_provider_list_is_preserved_without_fake_match(self):
        self.task('providers');self.choice('RC01',choice='self');self.choice('T06',text='Dr Example One at Office A; Dr Example Two at Office B');self.assertIsNone(self.q());self.assertIn('Two',self.g['fields']['needs.providers']['value']);self.assertFalse(self.flow.assess(self.g,self.r)['externalVerificationReady'])
    def test_drug_coverage_does_not_collect_fill(self):
        self.task('drug_coverage');self.choice('RC01',choice='self');self.choice('T07',text='Example medicine 5 mg tablet');self.assertEqual(self.q()['id'],'RC22');self.choice('RC22',name='Example medicine',strength='5 mg',form='tablet');self.assertIsNone(self.q());self.assertNotIn('RC23',self.r['facts'])
    def test_price_group_only_missing_fill_fields(self):
        self.task('drug_pricing');self.choice('RC01',choice='self');self.choice('RC22',name='Example medicine',strength='5 mg',form='tablet');self.assertEqual(self.q()['id'],'RC23');self.choice('RC23',quantity='30 tablets',daysSupply='30');self.assertEqual([f['key'] for f in self.q()['fields']],['pharmacy','channel']);self.choice('RC23',pharmacy='Example pharmacy, Naples FL',channel='retail');self.assertIsNone(self.q())
    def test_multiple_medicines_are_item_scoped(self):
        self.task('drug_pricing');self.choice('RC01',choice='self');self.choice('RC22',name='Example One',strength='5 mg',form='tablet');self.choice('RC22',name='Example Two',strength='10 mg',form='tablet');self.assertEqual(len(self.r['facts']['RC22']['value']['items']),2);self.assertIn('Two',self.g['fields']['needs.medications']['value'])
    def test_correction_invalidates_only_dependent_reports(self):
        self.known();self.choice('RC11',jobEnd='2026-12',coverageEnd='2027-01');self.choice('RC22',name='Example',strength='5 mg',form='tablet');self.choice('RC23',quantity='30 tablets',daysSupply='30');self.choice('RC22',name='Example',strength='10 mg',form='tablet');self.assertTrue(self.flow.item_stale(self.r,'RC23','medicine-1'));self.assertFalse(self.r['facts']['RC11']['stale'])
    def test_optional_familiarity_preferences_hsa_never_routine(self):
        self.task('compare');asked=[]
        for _ in range(12):
            q=self.q()
            if not q:break
            asked.append(q['id']);self.turn({'type':'defer','id':q['id']})
        for id in ['T02','T09','T10','RC14','RC25']:self.assertNotIn(id,asked)
    def test_medigraph_children_within_parent(self):
        self.task('medigap');self.known();self.choice('T05',choice='advantage');self.choice('RC04',choice='both');self.choice('RC05',month='October 2020');q=self.q();self.assertEqual(q['id'],'RC16');self.choice('RC16',start='January 2026',priorMedigap='no');self.assertIsNone(self.q());self.assertEqual(self.r['facts']['RC16']['value']['priorMedigap'],'no')
    def test_elsewhere_us_includes_same_state(self):
        self.task('compare');self.known();self.choice('T06',choice='none');self.choice('T07',choice='no');self.choice('T08',choice='elsewhere_us');self.assertEqual(self.q()['id'],'RC20');self.choice('RC20',location='Tampa, Florida');self.assertIsNone(self.q())
    def test_explicit_date_precision(self):
        self.assertEqual(month('January 2027'),'2027-01');self.assertEqual(month('December 31, 2026'),'2026-12-31');self.assertEqual(month('January 1999'),'1999-01');self.assertEqual(month('2027-01-03'),'2027-01-03');self.assertEqual(month('no scheduled end'),'no scheduled end')
        for value in ['January','next January','2027-02-31']:
            with self.assertRaises(ProfileError):month(value)
    def test_missing_status_never_defaults_to_first_choice(self):
        with self.assertRaises(ProfileError):self.choice('RC04')
        self.choice('RC16',start='January 2026',priorMedigap='no');self.assertEqual(self.r['facts']['RC16']['value']['choice'],'partial')
    def test_numeric_quantity_asks_only_missing_units(self):
        self.task('drug_pricing');self.choice('RC01',choice='self');self.choice('RC22',name='Example',strength='5 mg',form='tablet');self.choice('RC23',quantity='30',daysSupply='30',pharmacy='Example pharmacy',channel='retail');self.assertEqual([f['key'] for f in self.q()['fields']],['quantity']);self.assertIn('units',self.q()['fields'][0]['label']);self.choice('RC23',quantity='tablets');self.assertEqual(self.r['facts']['RC23']['value']['items'][0]['quantity'],'30 tablets');self.assertIsNone(self.q())
    def test_changed_recipient_never_merges_people(self):
        self.known()
        with self.assertRaises(ProfileError):self.choice('RC01',choice='someone')
    def test_idempotency_same_key_different_payload_rejected(self):
        p={'guide':self.g,'record':self.r,'action':{'type':'start'},'requestId':'synthetic-idempotency-123'};a=self.flow.turn(self.owner,p);self.assertEqual(a,self.flow.turn(self.owner,p));p['action']={'type':'refresh'}
        with self.assertRaises(ProfileError):self.flow.turn(self.owner,p)
    def test_no_source_failure_becomes_more_provider_intake(self):
        self.task('providers');self.choice('RC01',choice='self');self.choice('T06',text='Example doctor');q=self.q();self.assertIsNone(q);self.assertIn('identity',self.flow.assess(self.g,self.r)['limitation'])
    def test_sensitive_identifiers_rejected(self):
        with self.assertRaises(ProfileError):self.turn({'type':'message','message':'My SSN: 123-45-6789'})
    def test_atomic_save_receipt_and_sensitive_omission(self):
        token,info,_=self.server.profiles.session();self.known();self.choice('RC22',name='Private Example',strength='5 mg',form='tablet');self.g['preferences'].update(saveGuide=True,saveSensitive=False)
        p={'guide':self.g,'record':self.r,'expectedVersion':0,'expectedReadinessVersion':0,'operationId':'synthetic-atomic-save-123'}
        receipt=self.flow.save(token,info['csrf'],p);self.assertEqual(receipt['version'],1);self.assertEqual(receipt['readinessVersion'],1);self.assertTrue(self.flow.save(token,info['csrf'],p)['replayed']);saved=self.server.profiles.get(token)['guide'];r=self.server.readiness.get(token)['record'];self.assertNotIn('needs.medications',saved['fields']);self.assertFalse(r['facts']);self.assertFalse(r['conversation']['details'])
        p['operationId']='synthetic-conflict-save-123'
        with self.assertRaises(ProfileError):self.flow.save(token,info['csrf'],p)
        self.assertEqual(self.server.profiles.get(token)['version'],1);self.assertEqual(self.server.readiness.get(token)['version'],1)
    def test_legacy_profile_hydration_does_not_migrate_or_overwrite(self):
        self.known();self.r.pop('conversation');g,r=self.flow.validate(self.g,self.r);self.assertEqual(g,self.g);self.assertEqual(r['facts'],self.r['facts']);self.assertIn('conversation',r)
    def test_endpoint_origin_csrf_and_recommendation_hold(self):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET','/api/guest/session');res=c.getresponse();info=json.loads(res.read());cookie=res.getheader('Set-Cookie').split(';')[0]
        body={'guide':self.g,'record':self.r,'action':{'type':'refresh'},'requestId':str(uuid.uuid4())};headers={'Content-Type':'application/json','Cookie':cookie}
        c.request('POST','/api/conversation/turn',json.dumps(body),headers);res=c.getresponse();self.assertEqual(res.status,403);res.read();headers['X-Daylight-CSRF']=info['csrf'];headers['Origin']='https://untrusted.invalid';c.request('POST','/api/conversation/turn',json.dumps(body),headers);res=c.getresponse();self.assertEqual(res.status,403);res.read();headers.pop('Origin');c.request('POST','/api/conversation/turn',json.dumps(body),headers);res=c.getresponse();data=json.loads(res.read());self.assertEqual(res.status,200,data);self.assertFalse(data['personalRecommendation']);c.close()

class LanguageTests(unittest.TestCase):
    """Run the real structured-output adapter against deterministic synthetic outputs."""
    @classmethod
    def setUpClass(cls):AdaptiveTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):AdaptiveTests.tearDownClass.__func__(cls)
    turn=AdaptiveTests.turn
    choice=AdaptiveTests.choice
    task=AdaptiveTests.task
    q=AdaptiveTests.q
    known=AdaptiveTests.known
    def setUp(self):
        AdaptiveTests.setUp(self);self.original=(self.flow.fixture,self.flow.agent.client,self.flow.agent.enabled);self.calls=[]
        self.output={'mode':'report','task':'','task_quote':'','requests':[],'updates':[],'fact_ids':[],'reflection':'','confirmation':''}
        def transport(payload):
            self.calls.append(copy.deepcopy(payload))
            return {'output':[{'content':[{'type':'output_text','text':json.dumps(self.output)}]}],'usage':{'input_tokens':10,'output_tokens':10}}
        self.flow.fixture=False;self.flow.agent.enabled=True;self.flow.agent.client=SimpleNamespace(available=True,model='synthetic',transport=transport)
        self.addCleanup(self.restore)
    def restore(self):self.flow.fixture,self.flow.agent.client,self.flow.agent.enabled=self.original
    def update(self,id,fields,quote,**kw):
        return {'id':id,'fields':[{'key':k,'value':v} for k,v in fields.items()],'entity':kw.get('entity','profile'),'scope':kw.get('scope','current'),'subject':kw.get('subject','beneficiary'),'quote':quote,'uncertain':kw.get('uncertain',False),'correction':kw.get('correction',False)}
    def test_multi_fact_retirement_reuses_all_reports(self):
        message='I am retiring in December 2026 and need coverage in January 2027. I have insurance through my job.'
        self.output.update(task='timing',task_quote=message,updates=[self.update('RC01',{'choice':'self'},message),self.update('T04',{'choice':'month','month':'2027-01'},message,scope='intended'),self.update('T05',{'choice':'employer'},message),self.update('RC09',{'choice':'my_job'},message),self.update('RC11',{'jobEnd':'2026-12'},message,scope='intended')])
        result=self.turn({'type':'message','message':message});self.assertEqual(len(self.calls),1);self.assertEqual(result['metrics']['llmCalls'],1);self.assertEqual(self.g['fields']['coverage.requestedStartMonth']['value'],'2027-01');self.assertEqual(self.r['facts']['RC11']['value']['jobEnd'],'2026-12');self.assertNotIn('coverageEnd',self.r['facts']['RC11']['value'])
    def test_side_question_does_not_erase_task_or_request_answer(self):
        self.task('timing');q=self.q()['signature'];self.output.update(mode='answer',task='learn',task_quote='What is Medicare Advantage?',fact_ids=['advantage']);result=self.turn({'type':'message','message':'What is Medicare Advantage?'});self.assertEqual(self.q()['signature'],q);self.assertEqual(result['assessment']['task'],'timing');self.assertTrue(result['facts'])
    def test_sensitive_prior_values_not_attached_to_model(self):
        self.known();self.choice('T06',text='PRIVATE PROVIDER CANARY');self.choice('T07',text='PRIVATE MEDICINE CANARY');self.output.update(mode='answer',fact_ids=['basics']);self.turn({'type':'message','message':'What is Medicare?'});sent=json.dumps(self.calls[-1]);self.assertNotIn('PRIVATE PROVIDER CANARY',sent);self.assertNotIn('PRIVATE MEDICINE CANARY',sent);self.assertNotIn('2027-01',sent);self.assertFalse(self.calls[-1]['store']);self.assertTrue(self.calls[-1]['text']['format']['strict']);self.assertEqual(self.calls[-1]['max_output_tokens'],900)
    def test_explicit_correction_applies_without_second_confirmation(self):
        self.choice('RC11',coverageEnd='2027-01');msg='Correction: my coverage ends in February 2027.';self.output['updates']=[self.update('RC11',{'coverageEnd':'2027-02'},msg,correction=True)];result=self.turn({'type':'message','message':msg});self.assertIsNone(result['pendingId']);self.assertEqual(self.r['facts']['RC11']['value']['coverageEnd'],'2027-02')
    def test_ambiguous_interpretation_waits_for_confirmation(self):
        msg='That coverage might be Original Medicare.';self.output['updates']=[self.update('RC07',{'choice':'original'},msg,uncertain=True)];result=self.turn({'type':'message','message':msg});self.assertTrue(result['pendingId']);self.assertNotIn('RC07',self.r['facts']);result=self.turn({'type':'confirm'},pendingId=result['pendingId']);self.assertEqual(self.r['facts']['RC07']['value']['choice'],'original')
    def test_yes_and_additional_facts_are_all_processed(self):
        msg='That might be Original Medicare.';self.output['updates']=[self.update('RC07',{'choice':'original'},msg,uncertain=True)];pending=self.turn({'type':'message','message':msg})['pendingId'];msg='Yes, and my coverage ends in January 2027.';self.output['updates']=[self.update('RC11',{'coverageEnd':'2027-01'},msg)];self.output['confirmation']='yes';self.turn({'type':'message','message':msg},pendingId=pending);self.assertEqual(self.r['facts']['RC07']['value']['choice'],'original');self.assertEqual(self.r['facts']['RC11']['value']['coverageEnd'],'2027-01')
    def test_explicit_transition_changes_learning_and_update_order_is_atomic(self):
        self.task('learn');msg='I need help preparing a Medicare transition. My insurance is through my current job. My job ends in December 2026. I need coverage in January 2027.'
        self.output['updates']=[self.update('RC11',{'jobEnd':'2026-12'},msg),self.update('T01',{'choice':'learn'},msg),self.update('T04',{'choice':'month','month':'2027-01'},msg,scope='intended'),self.update('T05',{'choice':'employer'},msg),self.update('RC04',{'choice':'neither'},msg)]
        result=self.turn({'type':'message','message':msg});self.assertEqual(result['assessment']['task'],'timing');self.assertFalse(self.r['facts']['RC11']['stale']);self.assertEqual(self.q()['id'],'RC11');self.assertEqual([f['key'] for f in self.q()['fields']],['coverageEnd'])
    def test_mixed_known_date_and_unknown_insurance_end_never_reasks(self):
        self.task('timing');self.known();self.choice('RC04',choice='neither');self.choice('RC09',choice='my_job');msg="My job ends in December 2026. I don't know when that insurance ends.";self.output['updates']=[self.update('RC11',{'jobEnd':'2026-12','coverageEnd':'unknown'},msg)];result=self.turn({'type':'message','message':msg});self.assertEqual(self.r['facts']['RC11']['value']['jobEnd'],'2026-12');self.assertIsNone(self.q());self.assertTrue(any(x['label']=='When that health insurance ends' for x in result['assessment']['unresolvedReportedInputs']))
    def test_partial_product_unknown_is_bound_to_its_actual_item(self):
        self.task('drug_pricing');self.choice('RC01',choice='self');msg="I take Example medicine tablets but don't know the strength.";self.output['updates']=[self.update('RC22',{'name':'Example medicine','form':'tablets','strength':'unknown'},msg,entity='new')];result=self.turn({'type':'message','message':msg});self.assertEqual(self.r['conversation']['skippedDetails']['RC22.medicine-1.strength'],'unknown');self.assertIsNone(self.q());self.assertNotIn('RC23',self.r['facts'])
    def test_unstated_date_is_rejected_without_partial_change(self):
        msg='I have insurance through my job.';self.output['updates']=[self.update('RC11',{'coverageEnd':'2027-01'},msg)];before=copy.deepcopy(self.r)
        with self.assertRaises(Exception):self.turn({'type':'message','message':msg})
        self.assertEqual(self.r,before)
    def test_future_coverage_never_records_as_current(self):
        msg='I want Medicare Advantage next year.';self.output['updates']=[self.update('T05',{'choice':'advantage'},msg,scope='intended')]
        with self.assertRaises(Exception):self.turn({'type':'message','message':msg})
        self.assertNotIn('coverage.current',self.g['fields'])
    def test_ai_failure_preserves_reports_and_not_retried(self):
        self.known();before=copy.deepcopy(self.g)
        def fail(payload):self.calls.append(payload);raise ModelUnavailable('Synthetic provider failure')
        from chat import ModelUnavailable
        self.flow.agent.client.transport=fail
        with self.assertRaises(ModelUnavailable):self.turn({'type':'message','message':'Please explain my options.'})
        self.assertEqual(len(self.calls),1);self.assertEqual(self.g,before)

if __name__=='__main__':unittest.main()
