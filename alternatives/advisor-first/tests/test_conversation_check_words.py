"""Offline own-words contract for integrated conversation checks."""
from unittest import TestCase
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'infrastructure/daylight-data/src'))
import test_natural_flow as harness
from conversation_checks import ConversationChecks


class ConversationWordsTests(TestCase):
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context','composed_context'):
        locals()[name]=getattr(harness.NaturalFlowTests,name)

    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        class Doctors:
            def search(inner,**query):
                inner.query=query
                return {'candidates':[{'candidate_id':'source-only-id', 'kind':'clinician','site_count':1,
                    'label':'Jovan Baker','source_npis':['123'],
                    'office_previews':[{'street':'Fictional office','city':'Bonita Springs','state':'FL','postal':'34134'}]}],
                    'next_offset':None}
        self.doctors=Doctors()
        self.flow.conversation_checks=ConversationChecks(self.flow,self.doctors,None,lambda:[])
        self.choice('RC01',choice='self');self.choice('T03',zip='34102');self.choice('RC03',year='2026')

    def test_own_words_reach_exact_choice_and_model_only_gets_capability_status(self):
        text='My doctor is Jovan Baker in Bonita Springs.'
        result=self.message(text,updates=[self.update('T06',{'text':'Jovan Baker in Bonita Springs'},'Jovan Baker in Bonita Springs')])
        self.assertEqual(result['conversationCheck']['question']['field'],'doctor')
        self.assertEqual(self.doctors.query['location'],'Bonita Springs')
        context=self.composed_context()
        self.assertIn('conversation_checks',context)
        import json
        self.assertNotIn('source-only-id',json.dumps(context))
        self.assertNotIn('Fictional office',json.dumps(context))
        self.assertEqual(result['assessment']['nextQuestion']['localCheck'],True)

    def test_ordinary_surface_has_no_added_tool_context(self):
        del self.flow.conversation_checks
        from natural_flow import CONTEXT_POLICY
        self.assertNotIn('conversation_checks',self.flow.context(self.g,self.r,CONTEXT_POLICY))

    def test_shared_plan_is_reused_only_for_a_check_request(self):
        checks=self.flow.conversation_checks
        checks.plans=lambda:[{'id':'2026:H1234:001:000','name':'Fictional Plan'}]
        ctx={'selected_id':'2026:H1234:001:000'}
        checks.observe(self.owner,self.g,self.r,{'type':'message','message':'I am reading this plan.'},ctx)
        self.assertNotIn('doctor_plan',checks.visits[self.owner])
        checks.observe(self.owner,self.g,self.r,{'type':'message','message':'Does this plan cover my doctor?'},ctx)
        self.assertEqual(checks.visits[self.owner]['doctor_plan'],ctx['selected_id'])
