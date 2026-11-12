"""Five personas and variants across real HTTP, validation and controller paths."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chat_server import build
from adaptive_flow import Q
from persona_scenarios import SCENARIOS, install_scripted_transport
import guide_server

TRACES = []


class PersonaHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=build(0,fixture=True,database=Path(cls.tmp.name)/'private/personas.sqlite3')
        cls.original_clock=guide_server.time
        cls.flow=install_scripted_transport(cls.server,virtual_pacing=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup();guide_server.time=cls.original_clock

    def setUp(self):
        self.cookie='';self.csrf=''
        info=self.http('GET','/api/guest/session');self.csrf=info['csrf']
        result=self.http('GET','/api/conversation/initial');self.g=result['guide'];self.r=result['record'];self.assessment=result['assessment'];self.pending=None
        self.trace=[]

    def http(self,method,path,body=None,expected=200):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=20)
        headers={'Content-Type':'application/json','Origin':f'http://127.0.0.1:{self.server.server_port}','Cookie':self.cookie,'X-Daylight-CSRF':self.csrf}
        c.request(method,path,json.dumps(body) if body is not None else None,headers);response=c.getresponse()
        if response.getheader('Set-Cookie'):self.cookie=response.getheader('Set-Cookie').split(';')[0]
        data=json.loads(response.read());self.assertEqual(response.status,expected,data);c.close();return data

    def turn(self,action):
        before=copy.deepcopy(self.assessment)
        result=self.http('POST','/api/conversation/turn',{'guide':self.g,'record':self.r,'action':action,'requestId':str(uuid.uuid4()),'aiConsent':True,'pendingId':self.pending})
        self.g=result['guide'];self.r=result['record'];self.assessment=result['assessment'];self.pending=result['pendingId']
        self.assertFalse(result['personalRecommendation']);self.assertFalse(self.assessment['personalizedRecommendationAllowed']);self.assertFalse(self.assessment['externalVerificationReady'])
        self.assertEqual(set(self.assessment['ruleDecisions']),set(Q))
        self.trace.append({'action':action,'askedBefore':before['nextQuestion'],'nextQuestion':self.assessment['nextQuestion'],'pendingInterpretation':bool(self.pending),
                           'ruleDecisions':self.assessment['ruleDecisions'],'reportedGroups':sorted(self.r['facts']),
                           'guideFields':sorted(self.g['fields']),'unresolved':self.assessment['unresolvedReportedInputs'],
                           'metrics':result['metrics'],'recommendationAllowed':False})
        return result

    def run_case(self,case):
        steps=[]
        for original in case['steps']:
            if original.get('ambiguousCounty'):
                zip,rows=next((z,rs) for z,rs in self.flow.reference['zips'].items() if len(rs)>1 and rs[0][2]=='FL')
                expanded=[{'action':{'type':'message','message':zip},'expectedNext':'RC02'},
                          {'action':{'type':'choice','id':'RC02','fields':{'county':rows[0][0]}},'expectedNext':'T06'}]
            else:expanded=[original]
            for step in expanded:
                steps.append(step);result=self.turn(step['action']);q=result['assessment']['nextQuestion']
                self.assertEqual(q['id'] if q else None,step['expectedNext'],(case['id'],step['action'],q))
                if 'expectedFields' in step:self.assertEqual([f['key'] for f in q['fields']],step['expectedFields'])
        self.assertIsNone(self.assessment['nextQuestion']);self.assertIsNone(self.pending)
        before=copy.deepcopy((self.g,self.r));self.turn({'type':'next','step':'samples'})
        self.assertTrue(self.assessment['journey']['samplesVisible']);samples=self.http('GET','/api/sample-plans');self.assertEqual(len(samples['plans']),5)
        self.turn({'type':'next','step':'resume'});self.assertIsNone(self.assessment['nextQuestion'])
        # Navigation only changes navigation metadata, never customer fact values.
        self.assertEqual(self.g,before[0]);self.assertEqual(self.r['facts'],before[1]['facts'])
        TRACES.append({'id':case['id'],'persona':case['persona'],'name':case['name'],'steps':steps,'trace':self.trace,'finalGuide':self.g,'finalRecord':self.r,'allCapabilitiesHeld':True})


for case in SCENARIOS:
    def test(self,case=case):self.run_case(case)
    setattr(PersonaHTTPTests,'test_'+case['id'].replace('-','_'),test)


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):PersonaHTTPTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):PersonaHTTPTests.tearDownClass.__func__(cls)
    def test_provider_name_is_reported_once_without_ai_and_question_is_not_name(self):
        q=self.flow.question('T06');name='Dr. Rivera at Example Clinic; Dr. Lee at Example Hospital'
        result=self.flow.direct(name,q);self.assertEqual(result['updates'][0]['fields']['text'],name)
        for message in ['What is Medicare?','Dr. Rivera also prescribed something; what is covered?','Correction: Dr. Rivera moved.']:
            self.assertIsNone(self.flow.direct(message,q))
    def test_named_programs_multi_select_and_decline_conflict(self):
        g,r=self.flow.initial();self.flow.apply(g,r,{'id':'RC18','fields':{'choice':'medicaid,extra_help'}})
        self.assertEqual(r['facts']['RC18']['value']['programs'],['extra_help','medicaid'])
        from guest_profiles import ProfileError
        with self.assertRaises(ProfileError):self.flow.apply(g,r,{'id':'RC18','fields':{'choice':'medicaid,declined'}})
    def test_internal_and_optional_questions_not_forced_by_all_unknowns(self):
        g,r=self.flow.initial();r['conversation'].update(task='compare',preparing=True)
        asked=[]
        for n in range(15):
            q=self.flow.assess(g,r)['nextQuestion']
            if not q:break
            asked.append(q['id']);result=self.flow.turn('unknown-owner',{'guide':g,'record':r,'requestId':str(uuid.uuid4()),'action':{'type':'unknown','id':q['id']}});g,r=result['guide'],result['record']
        self.assertIsNone(self.flow.assess(g,r)['nextQuestion']);self.assertFalse(self.flow.assess(g,r)['personalizedRecommendationAllowed'])
        self.assertFalse(set(asked)&{'T02','T09','T10','RC08','RC14','RC15','RC19','RC24','RC27','RC28'})


if __name__=='__main__':unittest.main()
