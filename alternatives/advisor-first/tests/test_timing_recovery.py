"""Recovery preserves existing context and required clarification, not optional routing."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_flow as flow_support
from adaptive_flow import metadata


class TimingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = flow_support.NaturalFlowTests()
        self.case.setUp()
        self.case.task('timing')

    def self_report(self, message):
        return self.case.update('RC01', {'choice': 'self'}, message)

    def assert_no_inferred_dates(self):
        fields = self.case.g['fields']
        self.assertNotIn('situation.age65', fields)
        self.assertNotIn('coverage.requestedStart', fields)
        self.assertNotIn('coverage.requestedStartMonth', fields)

    @staticmethod
    def timing_explanation(message):
        return {'kind': 'clarify', 'concept_ids': ['enrollment_timing'], 'quote': message}

    @staticmethod
    def explanation_extraction(request, updates=(), goal=''):
        # Use the current wire contract: the legacy fixture adapter intentionally
        # drops modern request metadata while converting its older mode format.
        return {'updates': list(updates), 'requests': [], 'fact_ids': [],
                'agenda': {'concerns': [], 'priorityReason': {}},
                'situation_proposals': [], 'goal_quote': goal,
                'education_request': request}

    def test_failed_fresh_explanation_does_not_create_an_intake_target(self):
        self.case = flow_support.NaturalFlowTests()
        self.case.setUp()
        self.assertEqual(metadata(self.case.r)['task'], '')
        message = ('I am 64 and looking to enroll in medicare when eligible, '
                   "but don't really know when that is")
        out = self.case.message(message,
            extraction=self.explanation_extraction(self.timing_explanation(message),
                [self.self_report(message)], 'looking to enroll in medicare when eligible'),
            compose={'question_target': 'T05', 'reply': 'You are eligible for Medicare.',
                     'question': 'What health insurance do you have now?',
                     'evidence_refs': ['enrollment_intro']})
        self.assertEqual(metadata(self.case.r)['task'], 'compare')
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['generated']['code'], 'unsupported_finding')
        # Never-blank floor (November 8, 2026): a failed turn shows the approved
        # question the server selected (an approved meaning, never case prose).
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(self.case.r['natural']['dialogue']['lastTarget']['id'], 'T05')
        self.assert_no_inferred_dates()
        self.assertEqual(self.case.turn({'type': 'refresh'})['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(len(self.case.calls), 2)

    def test_unvalidated_timing_request_does_not_change_default_recovery(self):
        self.case.task('compare')
        self.case.choice('RC01', choice='self')
        before = self.case.flow.assess(self.case.g, self.case.r)['nextQuestion']['id']
        message = 'Please continue.'
        out = self.case.message(message,
            extraction=self.explanation_extraction({
                'kind': 'clarify', 'concept_ids': ['enrollment_timing'],
                'quote': 'not in this message'}),
            compose=TimeoutError('fictional composition interruption'))
        self.assertEqual(out['assessment']['nextQuestion']['id'], before)

    def test_failed_turns_never_trigger_a_case_specific_question_or_lesson(self):
        self.case = flow_support.NaturalFlowTests()
        self.case.setUp()
        message = ("I'm 64 and retired last month. I want to get Medicare when I can, "
                   "but I don't understand when that is.")
        opening = self.case.message(message,
            extraction=self.explanation_extraction(self.timing_explanation(message),
                [self.self_report(message)], 'I want to get Medicare when I can'),
            compose=TimeoutError('fictional composition interruption'))
        # Never-blank floor (November 8, 2026): a failed turn shows the approved
        # question the server selected (an approved meaning, never case prose).
        self.assertEqual(opening['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual([fact['id'] for fact in opening['facts']], ['enrollment_intro'])
        self.assertNotIn('Do not turn', opening['facts'][0]['text'])
        self.case.compositions.append(TimeoutError('fictional composition interruption'))
        cobra = self.case.turn({'type': 'choice', 'id': 'T05', 'fields': {'choice': 'cobra'}})
        self.assertEqual(self.case.flow.value(cobra['guide'], 'coverage.current'), ['cobra'])
        self.assertIsNone(cobra['assessment']['nextQuestion'])
        self.assertEqual(cobra['facts'], [])
        self.assertNotIn('current_coverage_timing',
                         [item['concept_id'] for item in cobra.get('education', {}).get('covered', [])])
        self.assert_no_inferred_dates()

    def test_failed_timing_opening_keeps_reports_without_choosing_a_question(self):
        message = ('I am 64 and looking to enroll in medicare when eligible, '
                   "but don't really know when that is")
        out = self.case.message(message,
            extraction=self.case.extraction([self.self_report(message)],
                goal_quote='looking to enroll in medicare when eligible'),
            compose=TimeoutError('fictional composition interruption'))
        self.assertEqual(out['generated']['status'], 'unavailable')
        # Never-blank floor (November 8, 2026): a failed turn shows the approved
        # question the server selected (an approved meaning, never case prose).
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(self.case.flow.value(self.case.g, 'subject.role'), 'self')
        self.assert_no_inferred_dates()
        self.assertEqual(len(self.case.calls), 2)

    def test_general_eligibility_explanation_can_precede_current_insurance_question(self):
        message = ('I am 64 and looking to enroll in medicare when eligible, '
                   "but don't really know when that is")
        reply = ('Most people first become eligible at 65. The initial sign-up '
                 'window begins 3 months before the birthday month.')
        out = self.case.message(message,
            extraction=self.case.extraction([self.self_report(message)],
                goal_quote='looking to enroll in medicare when eligible'),
            compose={'question_target': 'T05', 'reply': reply,
                     'question': 'What health insurance do you have now?',
                     'evidence_refs': ['enrollment_intro']})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(out['reply'], reply)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assert_no_inferred_dates()

    def test_subject_and_editing_dependencies_keep_precedence(self):
        self.assertEqual(self.case.flow.eligible(
            self.case.owner, self.case.g, self.case.r)[0]['id'], 'RC01')
        self.case.choice('RC01', choice='self')
        metadata(self.case.r)['editing'] = 'T04'
        candidates = self.case.flow.eligible(self.case.owner, self.case.g, self.case.r)
        self.assertEqual([item['id'] for item in candidates], ['T04'])

    def test_pending_coverage_ambiguity_remains_required(self):
        self.case.choice('RC01', choice='self')
        message = 'I think my coverage is through an employer.'
        out = self.case.message(message,
            [self.case.update('T05', {'choice': 'employer'}, message, uncertain=True)],
            compose=TimeoutError('fictional composition interruption'))
        candidates = self.case.flow.eligible(self.case.owner, self.case.g, self.case.r)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['id'], 'T05')
        self.assertTrue(candidates[0]['required'])
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')

    def test_unknown_or_deferred_insurance_is_not_reasked_by_new_priority(self):
        self.case.choice('RC01', choice='self')
        for disposition in ('unknown', 'deferred'):
            with self.subTest(disposition=disposition):
                metadata(self.case.r)['baselineDispositions']['T05'] = disposition
                candidates = self.case.flow.eligible(
                    self.case.owner, self.case.g, self.case.r)
                self.assertNotIn('T05', [item['id'] for item in candidates])

    def test_existing_conversational_return_point_survives_failed_reply(self):
        self.case.choice('RC01', choice='self')
        first = self.case.message('I would like to consider the timing.',
            compose={'question_target': 'T04',
                     'question': 'When would you like Medicare coverage to start?'})
        self.assertEqual(first['assessment']['nextQuestion']['id'], 'T04')
        message = 'Could you explain that?'
        out = self.case.message(message,
            extraction=self.explanation_extraction(self.timing_explanation(message)),
            compose=TimeoutError('fictional composition interruption'))
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T04')

    def test_comparison_can_choose_location_or_coverage_without_forced_sequence(self):
        self.case.task('compare')
        self.case.choice('RC01', choice='self')
        candidates = self.case.flow.eligible(self.case.owner, self.case.g, self.case.r)
        ranked, _ = self.case.flow.decision_candidates(
            self.case.owner, self.case.g, self.case.r, candidates)
        self.assertEqual([item['id'] for item in ranked], [item['id'] for item in candidates])
        for identifier in ('T03', 'T05'):
            self.assertEqual(next(item for item in ranked if item['id'] == identifier)
                             ['decision_relevance'], 'current_decision')


if __name__ == '__main__':
    unittest.main()
