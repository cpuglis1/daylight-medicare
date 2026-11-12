"""Local desired-start preference contracts. No paid generation or calendar inference."""
import copy
import unittest

import test_natural_flow as support
from guest_profiles import ProfileError
from natural_state import (CONTEXT_VERSION, build_context, classify_update,
                           legacy_projection)
from profile_readiness import ProfileReadiness
from situation import soonest_start_supported


class TimingPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.case=support.NaturalFlowTests()
        self.case.setUp()
        self.case.task('timing')
        self.case.choice('RC01',choice='self')

    def proposal(self,text='ASAP!!',**extra):
        return self.case.update('T04',{'choice':'soonest'},text,
                                scope='intended',**extra)

    def test_actual_question_offers_soonest_without_an_exact_date(self):
        question=self.case.flow.assess(self.case.g,self.case.r)['nextQuestion']
        self.assertEqual(question['id'],'T04')
        self.assertIn(['soonest','As soon as possible'],question['choices'])

    def test_typed_asap_commits_preference_and_advances_to_current_insurance(self):
        out=self.case.message('ASAP!!',[self.proposal()])
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStart'),'soonest')
        self.assertNotIn('coverage.requestedStartMonth',self.case.g['fields'])
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertNotIn('review',out)
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['confirmation'],'reported_by_user')

    def test_structured_soonest_needs_no_model_call_or_confirmation(self):
        out=self.case.choice('T04',choice='soonest')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertEqual(self.case.calls,[])
        self.assertNotIn('review',out)
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['confirmation'],'reported_by_user')
        self.assertEqual(self.case.r['natural']['provenance']['guide.coverage.requestedStart']['scope'],'intended')

    def test_non_date_preference_cannot_include_a_calendar_date(self):
        before=copy.deepcopy((self.case.g,self.case.r))
        with self.assertRaises(ProfileError):
            self.case.choice('T04',choice='soonest',month='November 2026')
        self.assertEqual((self.case.g,self.case.r),before)
        proposal=self.proposal()
        proposal['fields'].append({'key':'month','value':'November 2026'})
        self.assertEqual(classify_update(proposal,'ASAP!!')['decision'],'reject')

    def test_soonest_is_an_intention_not_current_or_past_enrollment(self):
        for scope in ('current','historical'):
            proposal=self.proposal()
            proposal['scope']=scope
            self.assertEqual(classify_update(proposal,'ASAP!!')['decision'],'reject')
        self.assertEqual(classify_update(self.proposal(),'ASAP!!')['decision'],'accept')

    def test_replacing_an_exact_month_retains_it_only_as_stale_history(self):
        self.case.choice('T04',choice='month',month='April 2027')
        self.case.choice('RC03',year='2027')
        self.case.choice('T04',choice='soonest')
        old=self.case.g['fields']['coverage.requestedStartMonth']
        self.assertEqual(old['value'],'2027-04')
        self.assertEqual(old['status'],'stale')
        self.assertTrue(self.case.r['facts']['RC03']['stale'])
        context=build_context(self.case.g,self.case.r,'timing',consent_version=CONTEXT_VERSION)
        sent={item['id']:item for item in context['reports']}
        self.assertEqual(sent['guide.coverage.requestedStart']['value'],'soonest')
        self.assertNotIn('guide.coverage.requestedStartMonth',sent)

    def test_a_later_explicit_month_replaces_the_preference(self):
        self.case.choice('T04',choice='soonest')
        out=self.case.choice('T04',choice='month',month='April 2027')
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStart'),'month')
        self.assertEqual(self.case.flow.value(self.case.g,'coverage.requestedStartMonth'),'2027-04')
        self.assertFalse(any(x['id']=='T04' for x in out['assessment']['unresolvedReportedInputs']))

    def test_unknown_after_soonest_does_not_repeat_or_reuse_the_preference(self):
        self.case.choice('T04',choice='soonest')
        out=self.case.choice('T04',choice='unknown')
        self.assertIsNone(self.case.flow.value(self.case.g,'coverage.requestedStart'))
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'),'T04')

    def test_exact_month_is_explicitly_unestablished_and_comparison_gate_stays_held(self):
        out=self.case.choice('T04',choice='soonest')
        self.assertIn({'id':'T04','label':'Exact coverage start month','state':'not established'},
                      out['assessment']['unresolvedReportedInputs'])
        g,r=legacy_projection(self.case.g,self.case.r)
        gate=ProfileReadiness(None,None,self.case.flow.contract,
                             {'triggers':list(self.case.flow.content.values())},[])
        assessment=gate.assess(g,r,requested=['route_comparison'])
        desired=[x for x in assessment['missingInformation'] if x['key']=='coverage.requestedStart']
        self.assertTrue(desired)
        self.assertFalse(assessment['capabilities']['route_comparison']['intakeReady'])
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertFalse(out['assessment']['externalVerificationReady'])

    def test_both_reviewed_profile_permissions_share_same_relevant_values_without_history(self):
        self.case.choice('T04',choice='soonest')
        self.case.r['history'].append({'previous':{'message':'private history canary'}})
        v1=build_context(self.case.g,self.case.r,'timing',consent_version='natural-context-v1')
        v2=build_context(self.case.g,self.case.r,'timing',consent_version='natural-context-v2')
        self.assertEqual(v1,v2)
        self.assertNotIn('private history canary',str(v2))
        self.assertIn('soonest',str(v2))
        unknown=build_context(self.case.g,self.case.r,'timing',consent_version='natural-context-v3')
        self.assertNotIn('soonest',str(unknown['reports']))

    def test_short_urgency_inherits_only_the_desired_start_question(self):
        for text in ('ASAP!!','As soon as possible','The earliest possible.','Right away!'):
            with self.subTest(text=text):
                self.assertTrue(soonest_start_supported(text,{'id':'T04'}))
                self.assertFalse(soonest_start_supported(text,{'id':'T05'}))
                self.assertFalse(soonest_start_supported(text))

    def test_explicit_desired_coverage_preference_can_be_reported_without_active_timing(self):
        self.assertTrue(soonest_start_supported('I need Medicare to start as soon as possible.'))
        self.assertTrue(soonest_start_supported('I want coverage ASAP because I have no insurance.'))
        for text in ('Can Medicare start ASAP?', 'My job ends ASAP.',
                     'I need help ASAP.', 'I do not want Medicare as soon as possible.',
                     'If I want Medicare ASAP, what happens?'):
            with self.subTest(text=text):self.assertFalse(soonest_start_supported(text,{'id':'T04'}))


if __name__=='__main__':unittest.main()
