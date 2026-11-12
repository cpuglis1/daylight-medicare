"""Typed desired dates and committed preferences; synthetic model, no paid calls."""
import copy
import unittest

import test_natural_flow as support
from natural_state import classify_update


class TimingChoiceOverrideTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.case.task('timing')
        self.case.choice('RC01', choice='self')

    def month_update(self, text, month='December 2026', **extra):
        return self.case.update('T04', {'choice': 'month', 'month': month}, text,
                                scope='intended', **extra)

    def test_plain_typed_month_works_without_any_committed_button_selection(self):
        # An unsent highlighted button is browser state, never a profile report.
        text = 'December 2026'
        self.case.message(text, [self.month_update(text)])
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStart'), 'month')
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStartMonth'), '2026-12')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))

    def test_clear_desired_month_refines_committed_soonest_without_another_confirmation(self):
        self.case.choice('T04', choice='soonest')
        prior_revision = self.case.g['fields']['coverage.requestedStart']['revision']
        text = 'I want my Medicare coverage to start in December 2026.'
        out = self.case.message(text, [self.month_update(text)])
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStart'), 'month')
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStartMonth'), '2026-12')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))
        self.assertNotIn('review', out)
        self.assertFalse(any(item['id'] == 'T04' for item in out['assessment']['unresolvedReportedInputs']))
        provenance = self.case.r['natural']['provenance']['guide.coverage.requestedStart']
        self.assertEqual(provenance['scope'], 'intended')
        self.assertEqual(provenance['supersedesRevision'], prior_revision)
        for identifier in ('RC04', 'RC05'):
            self.assertNotIn(identifier, self.case.r['facts'])
        self.assertNotIn('situation.age65', self.case.g['fields'])
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertFalse(out['assessment']['externalVerificationReady'])

    def test_an_educational_question_with_a_month_never_becomes_a_start_report(self):
        self.case.choice('T04', choice='soonest')
        previous = copy.deepcopy(self.case.g['fields']['coverage.requestedStart'])
        self.case.message('What happens if I wait until December 2026?')
        self.assertEqual(self.case.g['fields']['coverage.requestedStart'], previous)
        self.assertNotIn('coverage.requestedStartMonth', self.case.g['fields'])
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))

    def test_a_reported_birthday_does_not_replace_soonest_or_establish_start(self):
        self.case.choice('T04', choice='soonest')
        text = 'I turn 65 in December 2026.'
        # Even an erroneous birthday-as-start proposal must be rejected by the
        # existing interpreter safeguards before the refinement rule applies.
        self.case.message(text, [self.month_update(text)])
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStart'), 'soonest')
        self.assertNotIn('coverage.requestedStartMonth', self.case.g['fields'])
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65'),
                         {'month': 12, 'year': 2026})

    def test_tentative_month_still_requires_clarification(self):
        self.case.choice('T04', choice='soonest')
        text = 'I think I want coverage to start in December 2026.'
        self.case.message(text, [self.month_update(text, uncertain=True)])
        self.assertEqual(self.case.flow.pending_for(self.case.owner)['update']['id'], 'T04')
        self.assertNotIn('coverage.requestedStartMonth', self.case.g['fields'])
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['value'], 'soonest')
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['status'], 'stale')

    def test_refinement_requires_beneficiary_intended_scope_and_complete_month(self):
        text = 'I want coverage to start in December 2026.'
        existing = {'value': {'choice': 'soonest', 'month': None}, 'status': 'reported'}
        valid = self.month_update(text)
        self.assertEqual(classify_update(valid, text, existing)['reason'], 'explicit_start_refinement')
        for changes in ({'subject': 'learner'}, {'subject': 'unclear'},
                        {'scope': 'current'}, {'scope': 'historical'}, {'scope': 'unknown'},
                        {'uncertain': True}):
            with self.subTest(changes=changes):
                self.assertNotEqual(classify_update({**valid, **changes}, text, existing)['decision'], 'accept')
        incomplete = copy.deepcopy(valid)
        incomplete['fields'] = [{'key': 'choice', 'value': 'month'}]
        self.assertNotEqual(classify_update(incomplete, text, existing)['decision'], 'accept')

    def test_an_existing_exact_month_keeps_the_normal_conflict_guard(self):
        self.case.choice('T04', choice='month', month='November 2026')
        text = 'I want my Medicare coverage to start in December 2026.'
        self.case.message(text, [self.month_update(text)])
        self.assertEqual(self.case.flow.pending_for(self.case.owner)['update']['id'], 'T04')
        self.assertEqual(self.case.g['fields']['coverage.requestedStartMonth']['value'], '2026-11')
        self.assertEqual(self.case.g['fields']['coverage.requestedStartMonth']['status'], 'stale')
        corrected = 'Actually, I want coverage to start in December 2026.'
        self.case.message(corrected, [self.month_update(corrected, correction=True)])
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStartMonth'), '2026-12')
        self.assertIsNone(self.case.flow.pending_for(self.case.owner))


if __name__ == '__main__':
    unittest.main()
