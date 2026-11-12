"""Executable D86 report, branch, privacy and action invariants; no paid calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import server
from advisor_flow import AdvisorConversation, NarrativeAgent, fingerprint
from adaptive_flow import Q, CONTRACT
from chat import ResponsesClient, ModelUnavailable
from guest_profiles import ProfileError

class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.answer=None;self.calls=[]
        def transport(payload):
            self.calls.append(payload)
            value=copy.deepcopy(self.answer)
            if value is None:
                value={'mode':'answer','task':'learn','task_quote':'What is Medicare?','requests':[],'updates':[],
                    'fact_ids':['basics'],'reflection':'','confirmation':'','move_id':'explain','reason_id':'learning'}
            return {'output':[{'content':[{'type':'output_text','text':json.dumps(value)}]}]}
        self.flow=AdvisorConversation(None,None,
            json.loads((HERE/'web/guide-contract.json').read_text()),
            json.loads((HERE/'web/teaching-facts.json').read_text()),
            json.loads((HERE/'web/readiness-content.json').read_text()),
            ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),True,None,fixture=False)
        self.g,self.r=self.flow.initial();self.owner=uuid.uuid4().hex
    def payload(self,action,**extra):return {'guide':self.g,'record':self.r,'action':action,'requestId':str(uuid.uuid4()),'aiConsent':True,**extra}
    def turn(self,action,**extra):
        out=self.flow.turn(self.owner,self.payload(action,**extra));self.g,self.r=out['guide'],out['record'];return out
    def choice(self,id,**fields):return self.turn({'type':'choice','id':id,'fields':fields})
    def task(self,task):return self.turn({'type':'task','task':task,'preparing':True})
    def accept(self,result):return self.turn({'type':'accept_review','token':result['review']['token']})
    def ready_timing(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T04',choice='month',month='April 2027');self.choice('T05',choice='employer');self.choice('RC09',choice='my_job')
    def update(self,id,fields,quote,entity='profile',subject='beneficiary',uncertain=False):
        return {'id':id,'entity':entity,'fields':[{'key':k,'value':v} for k,v in fields.items()],'quote':quote,'scope':'current','subject':subject,'uncertain':uncertain,'correction':False}
    def scripted(self,message,updates,task='timing',move='ask'):
        self.answer={'mode':'report','task':task,'task_quote':message if task else '', 'requests':[],'updates':updates,'fact_ids':[],'reflection':'','confirmation':'','move_id':move,'reason_id':'timing'}

    def test_inventory_preserved(self):
        a=self.flow.assess(self.g,self.r)
        self.assertEqual(set(a['ruleDecisions']),set(Q));self.assertEqual(len(Q),41)
        self.assertEqual(len(CONTRACT['fields']),78);self.assertEqual(len(CONTRACT['gaps']),14)
        self.assertTrue(a['narrative']['opener']);self.assertFalse(a['personalizedRecommendationAllowed'])
    def test_form_stages_before_applying(self):
        self.task('compare');before=fingerprint(self.g,self.r)
        out=self.turn({'type':'stage','id':'RC01','entity':'profile','fields':{'choice':'self'}})
        self.assertEqual(before,fingerprint(self.g,self.r));self.assertEqual(out['review']['kind'],'form')
        self.accept(out);self.assertEqual(self.g['fields']['subject.role']['value'],'self')
    def test_discard_and_restage(self):
        self.task('compare');out=self.turn({'type':'stage','id':'RC01','entity':'profile','fields':{'choice':'self'}})
        self.turn({'type':'discard_review','token':out['review']['token']});self.assertNotIn('subject.role',self.g['fields'])
        out=self.turn({'type':'stage','id':'RC01','entity':'profile','fields':{'choice':'someone'}});self.accept(out)
        self.assertEqual(self.g['fields']['subject.role']['value'],'someone')
    def test_stale_review_fails(self):
        self.task('compare');out=self.turn({'type':'stage','id':'RC01','entity':'profile','fields':{'choice':'self'}})
        self.choice('T02',choice='comfortable')
        with self.assertRaises(ProfileError):self.accept(out)
    def test_review_owner_isolation(self):
        self.task('compare');out=self.turn({'type':'stage','id':'RC01','entity':'profile','fields':{'choice':'self'}})
        with self.assertRaises(ProfileError):self.flow.turn('another-owner',self.payload({'type':'accept_review','token':out['review']['token']}))
    def test_partial_dates_do_not_supply_insurance_end(self):
        self.ready_timing();a=self.flow.assess(self.g,self.r);self.assertEqual(a['nextQuestion']['id'],'RC11')
        out=self.turn({'type':'stage','id':'RC11','entity':'profile','fields':{'jobEnd':'March 2027','coverageEnd':'unknown'}});self.accept(out)
        self.assertEqual(self.r['facts']['RC11']['value']['jobEnd'],'2027-03')
        self.assertNotIn('coverageEnd',self.r['facts']['RC11']['value'])
        self.assertIsNone(self.flow.assess(self.g,self.r)['nextQuestion'])
    def test_unknowns_stop_and_stay_visible(self):
        self.task('compare');asked=[]
        for _ in range(20):
            current=self.flow.assess(self.g,self.r)['nextQuestion']
            if not current:break
            self.assertNotIn(current['signature'],asked);asked.append(current['signature'])
            self.turn({'type':'unknown','id':current['id']})
        a=self.flow.assess(self.g,self.r);self.assertIsNone(a['nextQuestion']);self.assertFalse(a['personalizedRecommendationAllowed'])
        self.assertIn('RC01',[row['id'] for row in a['unresolvedReportedInputs']])
    def test_learning_does_not_collect_personal_facts(self):
        out=self.turn({'type':'message','message':'What is Medicare?'})
        self.assertEqual(out['assessment']['task'],'learn');self.assertIsNone(out['assessment']['nextQuestion']);self.assertTrue(out['facts'])
        self.assertLessEqual(set(self.g['fields']),{'intent.goal'})
    def test_message_multi_fact_is_reviewed_once_and_reused(self):
        text='My health insurance is through my current job. I want help with my transition. I need coverage in April 2027.'
        self.scripted(text,[self.update('RC01',{'choice':'self'},text),self.update('T05',{'choice':'employer'},text),self.update('RC09',{'choice':'my_job'},text),self.update('T04',{'choice':'month','month':'April 2027'},text)])
        out=self.turn({'type':'message','message':text});self.assertEqual(self.g['fields'],{});self.assertEqual(out['review']['kind'],'interpretation')
        self.accept(out);self.assertEqual(self.flow.assess(self.g,self.r)['nextQuestion']['id'],'RC11')
        self.assertEqual(len(self.calls),1)
    def test_two_same_named_medicines_stay_distinct(self):
        self.task('drug_coverage');self.choice('RC01',choice='self');self.choice('T07',text='Example Med')
        text='Example Med 5 mg tablet and Example Med 10 mg tablet'
        self.scripted(text,[self.update('RC22',{'name':'Example Med','strength':'5 mg','form':'tablet'},text,entity='new'),self.update('RC22',{'name':'Example Med','strength':'10 mg','form':'tablet'},text,entity='new')],task='')
        out=self.turn({'type':'message','message':text});self.accept(out)
        items=self.r['facts']['RC22']['value']['items'];self.assertEqual(len(items),2);self.assertNotEqual(items[0]['entity'],items[1]['entity'])
    def test_helper_reports_do_not_become_beneficiary_facts(self):
        self.task('compare');self.choice('RC01',choice='someone')
        text='I have employer insurance, but this is for my mother.'
        self.scripted(text,[self.update('T05',{'choice':'employer'},text,subject='learner')],task='')
        before=fingerprint(self.g,self.r)
        with self.assertRaises(ModelUnavailable):self.turn({'type':'message','message':text})
        self.assertEqual(before,fingerprint(self.g,self.r))
    def test_prepare_requires_review_and_has_receipt(self):
        with self.assertRaises(ProfileError):self.turn({'type':'run_preparation','token':'invented'})
        out=self.turn({'type':'review_preparation'});self.assertNotIn('preparation',out)
        token=out['review']['token'];payload=self.payload({'type':'run_preparation','token':token})
        one=self.flow.turn(self.owner,payload);two=self.flow.turn(self.owner,payload)
        self.assertEqual(one['preparation']['id'],two['preparation']['id']);self.assertEqual(one['preparation']['status'],'prepared')
        self.assertIn('No outside party was contacted',one['preparation']['text'])
        with self.assertRaises(ProfileError):self.turn({'type':'run_preparation','token':token})
    def test_preparation_invalidated_by_edit(self):
        out=self.turn({'type':'review_preparation'});self.choice('T02',choice='comfortable')
        with self.assertRaises(ProfileError):self.turn({'type':'run_preparation','token':out['review']['token']})
    def test_unavailable_ai_does_not_change_reports(self):
        self.flow.agent.enabled=False;before=fingerprint(self.g,self.r)
        with self.assertRaises(ModelUnavailable):self.turn({'type':'message','message':'I am retiring soon'})
        self.assertEqual(before,fingerprint(self.g,self.r))
    def test_ai_context_does_not_include_earlier_sensitive_values(self):
        self.ready_timing();self.choice('T06',text='Private Clinic Canary');self.choice('RC11',jobEnd='March 2027')
        text='Explain Medicare basics'
        self.answer={'mode':'answer','task':'','task_quote':'','requests':[],'updates':[],'fact_ids':['basics'],'reflection':'','confirmation':'','move_id':'explain','reason_id':'learning'}
        self.turn({'type':'message','message':text})
        sent=json.loads(self.calls[0]['input'][0]['content'])['confirmed_context']
        self.assertNotIn('Private Clinic Canary',json.dumps(sent));self.assertNotIn('2027-03',json.dumps(sent));self.assertNotIn('March 2027',json.dumps(sent))
    def test_only_eligible_model_moves_are_accepted(self):
        text='What is Medicare?';self.scripted(text,[],task='learn',move='enroll')
        with self.assertRaises(ModelUnavailable):self.turn({'type':'message','message':text})
    def test_future_date_is_not_an_actual_part_b_date(self):
        text='I plan to start Part B in April 2027'
        update=self.update('RC05',{'month':'April 2027'},text);update['scope']='intended'
        self.scripted(text,[update],task='')
        with self.assertRaises(ModelUnavailable):self.turn({'type':'message','message':text})
    def test_form_cannot_target_an_unrelated_question(self):
        self.task('compare')
        with self.assertRaises(ProfileError):self.turn({'type':'stage','id':'RC23','entity':'medicine-1','fields':{'quantity':'30 tablets'}})
    def test_planner_can_offer_preparation_after_report_review(self):
        text='My insurance is through my current job. Help me prepare my transition.'
        self.scripted(text,[self.update('RC01',{'choice':'self'},text),self.update('T05',{'choice':'employer'},text)],move='prepare')
        out=self.turn({'type':'message','message':text});accepted=self.accept(out)
        self.assertEqual(accepted['assessment']['narrative']['focus'],'prepare')
    def test_county_derivation_is_visible_but_not_residence_verification(self):
        self.task('browse');out=self.turn({'type':'stage','id':'T03','entity':'profile','fields':{'zip':'34102'}})
        county=next(row for row in out['review']['rows'] if row['id']=='RC02')
        self.assertEqual(county['status'],'derived');self.assertIn('Collier',county['value'])
    def test_held_comparison_can_offer_useful_work_without_intake(self):
        out=self.turn({'type':'task','task':'compare','preparing':False})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertIn('prepare',out['assessment']['narrative']['eligibleMoves'])
        self.assertFalse(out['assessment']['externalVerificationReady'])
    def test_unknown_edit_invalidates_previously_known_start(self):
        self.ready_timing();self.turn({'type':'edit','id':'T04'})
        out=self.turn({'type':'unknown','id':'T04'})
        self.assertIsNone(self.flow.value(self.g,'coverage.requestedStartMonth'))
        self.assertFalse(self.r['conversation']['editing'])
        self.assertIn('T04',[x['id'] for x in out['assessment']['unresolvedReportedInputs']])
    def test_unknown_form_values_are_visible_in_review(self):
        self.ready_timing()
        out=self.turn({'type':'stage','id':'RC11','entity':'profile','fields':{'jobEnd':'March 2027','coverageEnd':'unknown'}})
        self.assertTrue(any(row['value']=='unknown' for row in out['review']['rows']))

if __name__=='__main__':unittest.main()
