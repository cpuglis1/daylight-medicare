"""October 28 live-review regressions: actual routes and state invariants."""
import copy
import unittest
import test_adaptive_flow as foundation
from adaptive_flow import month, validate_metadata
from guest_profiles import ProfileError


class ReviewFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):foundation.AdaptiveTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):foundation.AdaptiveTests.tearDownClass.__func__(cls)
    setUp=foundation.AdaptiveTests.setUp
    turn=foundation.AdaptiveTests.turn
    choice=foundation.AdaptiveTests.choice
    task=foundation.AdaptiveTests.task
    q=foundation.AdaptiveTests.q

    def next(self,step):return self.turn({'type':'next','step':step})

    def test_reviewed_learning_to_samples_journey(self):
        self.turn({'type':'start'})
        intro=self.choice('T01',choice='learn')
        self.assertEqual([f['id'] for f in intro['facts']],['basics'])
        self.assertEqual(len(intro['assessment']['journey']['nextStep']['choices']),2)
        self.assertEqual([f['id'] for f in self.next('learn_next')['facts']],['parts'])
        self.next('explore');self.assertEqual(self.q()['id'],'RC01')
        self.choice('RC01',choice='self');self.assertEqual(self.q()['id'],'T04')
        self.choice('T04',choice='month',month='1226');self.assertEqual(self.q()['id'],'T05')
        self.choice('T05',choice='cobra');self.assertEqual(self.q()['id'],'T03')
        self.choice('T03',zip='34102');self.assertEqual(self.q()['id'],'T06')
        self.choice('T06',choice='none');self.choice('T07',choice='no');result=self.choice('T08',choice='local')
        self.assertIsNone(self.q());self.assertFalse(result['assessment']['journey']['samplesVisible'])
        self.assertFalse(result['assessment']['personalizedRecommendationAllowed'])
        result=self.next('samples');self.assertTrue(result['assessment']['journey']['samplesVisible'])
        self.assertFalse(result['assessment']['externalVerificationReady'])
        self.assertEqual(result['assessment']['journey']['phase'],3)
        self.next('resume');self.next('explore');self.assertIsNone(self.q())
        self.assertEqual(self.g['fields']['coverage.requestedStartMonth']['value'],'2026-12')
        self.assertNotIn('RC04',self.r['facts'])

    def test_learning_actions_never_repeat_completed_lesson(self):
        self.choice('T01',choice='learn');seen=['basics']
        for _ in range(8):
            result=self.next('learn_next');seen.extend(f['id'] for f in result['facts'])
        self.assertEqual(len(seen),len(set(seen)))
        self.assertNotIn('learn_next',[c['value'] for c in result['assessment']['journey']['nextStep']['choices']])
        self.assertFalse(self.g['fields'].keys()-{'intent.goal'})

    def test_cobra_transition_reuses_type_without_inventing_parts_or_job_end(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T04',choice='month',month='December 2026')
        self.choice('T05',choice='cobra')
        self.assertEqual(self.q()['id'],'RC11')
        self.assertEqual([f['key'] for f in self.q()['fields']],['coverageEnd'])
        self.assertEqual(self.r['facts']['RC09']['value']['choice'],'cobra')
        self.assertNotIn('RC04',self.r['facts'])
        self.choice('RC11',coverageEnd='November 2026')
        self.assertIsNone(self.q());self.assertEqual(self.r['facts']['RC11']['value']['coverageEnd'],'2026-11')
        self.assertEqual(self.g['fields']['coverage.requestedStartMonth']['value'],'2026-12')

    def test_specific_payer_check_can_still_require_separate_medicare_status(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T04',choice='month',month='December 2026');self.choice('T05',choice='cobra')
        self.r['conversation']['checks']=['payer_order']
        self.assertEqual(self.q()['id'],'RC04')

    def test_year_only_browse_then_transition_asks_only_missing_precision(self):
        self.task('browse');self.choice('T03',zip='34102');self.choice('RC03',year='2026')
        self.task('timing');self.choice('RC01',choice='self')
        self.assertEqual(self.q()['knownYear'],'2026');self.assertIn('Which month',self.q()['question'])
        self.choice('T04',choice='month',month='December')
        self.assertEqual(self.g['fields']['coverage.requestedStartMonth']['value'],'2026-12')

    def test_browse_date_is_reused_by_later_transition(self):
        self.task('browse');self.choice('T03',zip='34102');self.choice('RC03',year='12/26')
        self.task('timing');self.choice('RC01',choice='self');self.assertEqual(self.q()['id'],'T05')

    def test_compact_date_text_is_free_without_ai_consent(self):
        self.task('timing');self.choice('RC01',choice='self')
        result=self.turn({'type':'message','message':'1226'},aiConsent=False)
        self.assertEqual(result['metrics']['llmCalls'],0)
        self.assertEqual(self.g['fields']['coverage.requestedStartMonth']['value'],'2026-12')
        for value in ['12/26','12/2026','1226','December 2026']:
            self.assertEqual(month(value),'2026-12')

    def test_typed_next_step_label_does_not_need_ai(self):
        self.choice('T01',choice='learn')
        result=self.turn({'type':'message','message':'Explore my coverage options'},aiConsent=False)
        self.assertEqual(result['metrics']['llmCalls'],0);self.assertEqual(self.q()['id'],'RC01')

    def test_sample_navigation_does_not_erase_unanswered_question(self):
        self.task('timing');signature=self.q()['signature'];before=copy.deepcopy(self.g)
        self.next('samples');self.assertEqual(self.g,before)
        self.next('resume');self.assertEqual(self.q()['signature'],signature)

    def test_unknown_goal_offers_learning_without_fabricating_reported_goal(self):
        result=self.turn({'type':'unknown','id':'T01'})
        self.assertTrue(result['facts']);self.assertIsNone(self.q());self.assertNotIn('intent.goal',self.g['fields'])
        self.assertEqual(len(result['assessment']['journey']['nextStep']['choices']),2)

    def test_completed_no_prescriptions_price_task_has_visible_next_step(self):
        self.task('drug_pricing');self.choice('RC01',choice='self');result=self.choice('T07',choice='no')
        self.assertIsNone(self.q());self.assertTrue(result['assessment']['journey']['nextStep'])
        self.assertIn('price',result['assessment']['journey']['summary'])

    def test_old_metadata_is_compatible_and_invalid_navigation_is_rejected(self):
        old=copy.deepcopy(self.r['conversation']);old.pop('journey')
        self.assertIn('journey',validate_metadata(old))
        old['journey']['learningSeen']=[{'untrusted':'object'}]
        with self.assertRaises(ProfileError):validate_metadata(old)

    def test_sensitive_date_omission_stays_missing_without_repeating_known_cobra_type(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T04',choice='month',month='December 2026');self.choice('T05',choice='cobra')
        self.g['fields'].pop('coverage.requestedStartMonth');self.r['facts']={}
        self.assertEqual(self.q()['id'],'T04')
        self.choice('T04',choice='month',month='December 2026')
        self.assertEqual(self.q()['id'],'RC11')
        self.assertEqual([f['key'] for f in self.q()['fields']],['coverageEnd'])

    def test_structured_partial_dates_keep_known_and_unknown_without_ai(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T04',choice='month',month='December 2026');self.choice('T05',choice='employer');self.choice('RC09',choice='my_job')
        result=self.choice('RC11',jobEnd='1126',coverageEnd='unknown')
        self.assertEqual(result['metrics']['llmCalls'],0);self.assertIsNone(self.q())
        self.assertEqual(result['assessment']['journey']['phase'],1)
        self.assertEqual(self.r['facts']['RC11']['value']['jobEnd'],'2026-11')
        self.assertEqual(self.r['conversation']['skippedDetails']['RC11.profile.coverageEnd'],'unknown')

    def test_research_only_routes_to_scope_without_personal_intake(self):
        self.choice('T01',choice='compare');self.choice('RC01',choice='research')
        self.assertEqual(self.r['conversation']['task'],'browse');self.assertEqual(self.q()['id'],'T03')
        self.choice('T03',zip='34102');self.choice('RC03',year='2026')
        self.assertIsNone(self.q());self.assertNotIn('coverage.current',self.g['fields'])

    def test_something_else_invites_actual_goal_instead_of_a_menu(self):
        result=self.choice('T01',choice='unresolved')
        self.assertEqual(result['assessment']['journey']['nextStep']['choices'],[])
        self.assertIn('type it below',result['assessment']['journey']['nextStep']['question'])

    def test_literal_none_in_current_provider_or_prescription_question_is_free(self):
        for task,key in [('providers','needs.providersStatus'),('drug_coverage','needs.medicinesStatus')]:
            self.task(task);self.choice('RC01',choice='self')
            result=self.turn({'type':'message','message':'None'},aiConsent=False)
            self.assertEqual(result['metrics']['llmCalls'],0);self.assertIsNone(self.q())
            self.assertIn(self.g['fields'][key]['value'],{'none','no'})


if __name__=='__main__':unittest.main()
