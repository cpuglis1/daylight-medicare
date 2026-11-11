"""Fictional COBRA timing incidents; no provider calls or personal date advice."""
import copy
import unittest

import test_natural_flow as support
from natural_state import classify_update
from timing_language import reported_end_date, end_date_supported, after_coverage_supported
from guest_profiles import ProfileError


class CobraConversationTests(unittest.TestCase):
    def setUp(self):
        self.case=support.NaturalFlowTests()
        self.case.setUp()
        self.case.task('timing')
        self.case.choice('RC01',choice='self')
        self.case.choice('T05',choice='cobra')

    def update(self,id,fields,text,**extra):
        return self.case.update(id,fields,text,**extra)

    def test_cobra_end_question_does_not_call_it_current_work_insurance(self):
        q=next(x['question'] for x in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r) if x['id']=='RC11')
        self.assertEqual(q['question'],'When does your COBRA coverage end?')
        self.assertEqual([x['key'] for x in q['fields']],['coverageEnd'])
        self.assertFalse(self.case.flow.agent._valid_question('When does that work insurance end?',{'question':q,'id':'RC11'}))

    def test_month_only_is_retained_without_year_or_repeat(self):
        out=self.case.message('August',[self.update('RC11',{'coverageEnd':'August'},'August')])
        self.assertEqual(self.case.flow.report(self.case.r,'RC11')['coverageEnd'],'august')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertNotIn('RC11',{x['id'] for x in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r)})
        self.assertFalse(out['assessment']['externalVerificationReady'])

    def test_after_coverage_is_a_complete_preference_without_computed_start(self):
        self.case.choice('RC11',coverageEnd='August')
        text='I would like Medicare to start after my COBRA ends.'
        out=self.case.message(text,[self.update('T04',{'choice':'after_coverage'},text,scope='intended')])
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStart'),'after_coverage')
        self.assertNotIn('coverage.requestedStartMonth',self.case.g['fields'])
        self.assertNotIn('T04',{x['id'] for x in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r)})
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertIn({'id':'T04','label':'Exact coverage start month','state':'not established'},out['assessment']['unresolvedReportedInputs'])

    def test_relative_preference_can_be_changed_to_soonest_without_conflict(self):
        self.case.choice('T04',choice='after_coverage')
        text='I want Medicare to start as soon as possible.'
        self.case.message(text,[self.update('T04',{'choice':'soonest'},text,scope='intended')])
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStart'),'soonest')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))

    def test_month_can_gain_day_and_year_without_becoming_a_conflict(self):
        self.case.choice('RC11',coverageEnd='August')
        text='My COBRA coverage ends August 15th 2027.'
        self.case.message(text,[self.update('RC11',{'coverageEnd':'August 15th 2027'},text)])
        self.assertEqual(self.case.flow.report(self.case.r,'RC11')['coverageEnd'],'2027-08-15')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertNotIn('RC11',{x['id'] for x in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r)})

    def test_different_month_still_requires_correction(self):
        self.case.choice('RC11',coverageEnd='August')
        text='My COBRA coverage ends September 2027.'
        self.case.message(text,[self.update('RC11',{'coverageEnd':'September 2027'},text)])
        self.assertIsNotNone(self.case.flow.pending_for(self.case.owner))

    def test_mixed_unknown_job_and_known_partial_coverage_end_stay_separate(self):
        text='I do not know the job end date. COBRA ends in August.'
        self.case.message(text,[self.update('RC11',{'jobEnd':'unknown','coverageEnd':'August'},text)])
        self.assertEqual(self.case.flow.report(self.case.r,'RC11')['coverageEnd'],'august')
        self.assertNotIn('jobEnd',self.case.flow.report(self.case.r,'RC11'))
        self.assertEqual(self.case.r['conversation']['skippedDetails']['RC11.profile.jobEnd'],'unknown')

    def test_coverage_change_invalidates_relative_preference(self):
        self.case.choice('T04',choice='after_coverage')
        self.case.choice('T05',choice='none')
        self.assertIsNone(self.case.flow.value(self.case.g,'coverage.requestedStart'))
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['status'],'stale')

    def test_relative_preference_never_accepts_a_date_field(self):
        with self.assertRaises(ProfileError):
            self.case.choice('T04',choice='after_coverage',month='September 2027')
        text='I want Medicare to start after COBRA ends.'
        update=self.update('T04',{'choice':'after_coverage','month':'2027-09'},text,scope='intended')
        self.assertEqual(classify_update(update,text)['decision'],'reject')

    def test_relative_phrase_support_keeps_scope_and_negation(self):
        self.assertTrue(after_coverage_supported('after cobra ends',{'id':'T04'}))
        self.assertFalse(after_coverage_supported('after cobra ends',{'id':'RC11'}))
        for text in ('Can Medicare start after COBRA ends?', 'If I want it after COBRA ends, what happens?',
                     'I do not want Medicare to start after COBRA ends.'):
            self.assertFalse(after_coverage_supported(text,{'id':'T04'}))

    def test_partial_and_ordinal_precision_never_invents_year(self):
        self.assertEqual(reported_end_date('August'),'august')
        self.assertEqual(reported_end_date('August 15th'),'august 15')
        self.assertEqual(reported_end_date('August 15th 2027'),'2027-08-15')
        self.assertTrue(end_date_supported('August 15th 2027','Ends August 15th 2027.'))
        self.assertFalse(end_date_supported('2027-08','Ends in August.'))
        self.assertFalse(end_date_supported('2027-08-01','Ends in August 2027.'))
        with self.assertRaises(ProfileError):reported_end_date('February 30th')

    def test_tentative_sounding_relative_preference_does_not_demand_calendar_precision(self):
        text='I would like Medicare to start after COBRA ends I guess.'
        out=self.case.message(text,[self.update('T04',{'choice':'after_coverage'},text,scope='intended')])
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStart'),'after_coverage')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'),'T04')

    def test_evidence_packing_keeps_claim_text_and_display_sources_separate(self):
        import json
        evidence={'id':'cobra_timing','title':'COBRA and timing','question':'How does it work?',
                  'text':'COBRA is not current-employment coverage. Do not infer a personal deadline.',
                  'summary':'A preference is not a safe start-date finding.',
                  'source':'https://www.medicare.gov/example','sources':[{'url':'https://www.ssa.gov/example'}]}
        content={'resolved_context':{'evidence':[evidence],'reports':[{'id':'keep'}],
                                     'recent_exchanges':[]},'question_candidates':[]}
        before=copy.deepcopy(content)
        payload={'input':[{'role':'user','content':json.dumps(content)}]}
        self.case.flow.agent.count_tokens=lambda *_:7000
        self.assertEqual(self.case.flow.agent.count_request_tokens(None,payload),7000)
        packed=json.loads(payload['input'][0]['content'])['resolved_context']
        self.assertEqual(packed['evidence'],[{key:evidence[key] for key in ('id','text','summary')}])
        self.assertEqual(content,before)
        self.assertEqual(packed['reports'],content['resolved_context']['reports'])
