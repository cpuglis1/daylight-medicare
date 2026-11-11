"""Adversarial profile assessment. Desired invariants fail visibly when unmet."""
import copy
import unittest
import uuid
import test_ui2_personas as base
import edge_persona_scenarios as edge

TRACES=[]


class EdgeProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.PersonaHTTPTests.setUpClass.__func__(cls);edge.install(cls.server)
    @classmethod
    def tearDownClass(cls):base.PersonaHTTPTests.tearDownClass.__func__(cls)
    http=base.PersonaHTTPTests.http
    turn=base.PersonaHTTPTests.turn
    def setUp(self):
        base.PersonaHTTPTests.setUp(self);self.checks=[]
    def tearDown(self):
        id=self._testMethodName.split('_')[1]
        TRACES.append({'id':id,'definition':next((p for p in edge.PROFILES if p['id']==id),{}),'trace':self.trace,'checks':self.checks,'finalGuide':self.g,'finalRecord':self.r,'finalAssessment':self.assessment})
    def check(self,label,actual,expected):
        self.checks.append({'label':label,'passed':actual==expected,'actual':actual,'expected':expected});self.assertEqual(actual,expected,label)
    def msg(self,s):return self.turn(s['action'])
    def choose(self,id,**fields):return self.turn({'type':'choice','id':id,'fields':fields})
    def q(self):return self.assessment['nextQuestion']
    def sample_roundtrip(self):
        before=copy.deepcopy((self.g,self.r['facts']));self.turn({'type':'next','step':'samples'})
        self.check('explicit samples visible',self.assessment['journey']['samplesVisible'],True)
        self.check('five samples',len(self.http('GET','/api/sample-plans')['plans']),5)
        self.turn({'type':'next','step':'resume'});self.check('sample navigation preserves reports',(self.g,self.r['facts']),before)
        self.check('fictional profile never saved',self.http('GET','/api/guest/profile')['guide'],None)
    def reject(self,s,status):
        before=copy.deepcopy((self.g,self.r));data=self.http('POST','/api/conversation/turn',{'guide':self.g,'record':self.r,'action':s['action'],'requestId':str(uuid.uuid4()),'aiConsent':True,'pendingId':self.pending},expected=status)
        self.trace.append({'rejectedAction':s['action'],'expectedHttpStatus':status,'error':data['error']})
        self.check('rejected turn preserves current visit',(self.g,self.r),before)

    def test_P6_conflict_and_correction(self):
        self.msg(edge.P6_START);self.check('all reported dates reused',self.q(),None)
        self.msg(edge.P6_AMBIGUOUS);self.check('ambiguous replacement requires confirmation',bool(self.pending),True)
        self.check('unconfirmed end date not applied',self.r['facts']['RC11']['value']['coverageEnd'],'2026-12')
        self.turn({'type':'reject'});self.check('reject clears pending',self.pending,None)
        self.check('reject preserves previous date',self.r['facts']['RC11']['value']['coverageEnd'],'2026-12')
        self.msg(edge.P6_AMBIGUOUS);self.turn({'type':'confirm'});self.check('confirmed replacement applied',self.r['facts']['RC11']['value']['coverageEnd'],'2027-01')
        self.msg(edge.P6_CORRECT);self.check('explicit correction needs no repeat confirmation',self.pending,None)
        self.check('correction applies only insurance end',self.r['facts']['RC11']['value']['coverageEnd'],'2027-02')
        self.check('desired start stays January',self.g['fields']['coverage.requestedStartMonth']['value'],'2027-01');self.sample_roundtrip()

    def test_P7_unknown_answers(self):
        self.choose('T01',choice='compare');asked=[]
        for _ in range(15):
            q=self.q()
            if not q:break
            asked.append(q['id']);self.turn({'type':'unknown','id':q['id']})
        self.check('unknowns terminate',self.q(),None)
        self.check('no repeat unknown question',len(asked),len(set(asked)))
        self.check('only goal was reported',sorted(self.g['fields']),['intent.goal'])
        self.check('unknowns do not fabricate Medicare status','RC04' in self.r['facts'],False)
        open_count=len(self.assessment['unresolvedReportedInputs'])
        self.sample_roundtrip();self.check('return does not reopen unknowns',self.q(),None)
        self.check('required unknowns remain visible',open_count,7)

    def test_P8_goal_changes(self):
        self.choose('T01',choice='compare');self.choose('RC01',choice='self');self.choose('T04',choice='month',month='12/26');self.choose('T05',choice='cobra');self.choose('T03',zip='34102')
        original=self.q()['signature'];self.msg(edge.P8_SIDE)
        self.check('side question preserves task',self.assessment['task'],'compare');self.check('side question preserves active question',self.q()['signature'],original)
        self.msg(edge.P8_LEARN);self.check('explicit learning changes task',self.assessment['task'],'learn');self.check('learning has no intake',self.q(),None)
        self.msg(edge.P8_DRUG);self.check('drug request reuses subject',self.q()['id'],'T07');self.turn({'type':'message','message':'None'})
        self.check('none does not trigger product or fill intake',self.q(),None)
        self.msg(edge.P8_RETURN);self.check('return reuses location/date/coverage',self.q()['id'],'T06')
        self.choose('T06',choice='none');self.choose('T08',choice='local');self.check('comparison terminates',self.q(),None)
        self.check('original start retained',self.g['fields']['coverage.requestedStartMonth']['value'],'2026-12');self.sample_roundtrip()

    def test_P9_multiple_people(self):
        self.msg(edge.P9_START);self.check('mother profile complete for preparation',self.q(),None)
        self.reject(edge.P9_HELPER,503);self.reject(edge.P9_SWITCH,422)
        self.check('beneficiary role stays someone',self.g['fields']['subject.role']['value'],'someone')
        self.check('mother coverage not replaced by helper coverage',self.g['fields']['coverage.current']['value'],['cobra']);self.sample_roundtrip()

    def test_P10_same_name_different_strength(self):
        self.msg(edge.P10_SAME)
        items=self.r['facts']['RC22']['value']['items']
        self.sample_roundtrip()
        self.check('two explicitly reported medicines remain distinct',len(items),2)
        self.check('both reported strengths retained',sorted(x['strength']for x in items),['10 mg','5 mg'])


class ItemBindingGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):EdgeProfiles.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):EdgeProfiles.tearDownClass.__func__(cls)
    setUp=EdgeProfiles.setUp;http=EdgeProfiles.http;turn=EdgeProfiles.turn;msg=EdgeProfiles.msg;check=EdgeProfiles.check;reject=EdgeProfiles.reject
    def test_ambiguous_fill_cannot_choose_an_arbitrary_medicine(self):
        self.msg(edge.P10_DISTINCT);self.msg(edge.P10_FILL1);self.msg(edge.P10_FILL2)
        self.check('both fills supplied',len(self.r['facts']['RC23']['value']['items']),2)
        self.reject(edge.P10_AMBIGUOUS,422)


if __name__=='__main__':unittest.main()
