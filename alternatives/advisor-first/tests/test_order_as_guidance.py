"""Question order is AI guidance; only code gates force the next question (Q2, D155).

Covers step 4 of the rebalance: (1) a decision-relevant question reaches the
composer as "must be answered before plans", not "ask now"; (2) an unresolved
report still must be asked now (a code gate); (3) the composer instructions
state the ordering guidance (who it's for first, current insurance before a
preferred start when timing matters, COBRA enrollment first, familiarity
optional) and treat question text as example wording; (4) the timing guidance
reaches the AI as the current-insurance candidate's purpose. All data is
fictional.
"""
import unittest

import test_natural_flow as flow_harness
from natural_agent import COMPOSE_INSTRUCTIONS

TEXT = "I've been retired for a few years, and am turning 65 in November."


class OrderAsGuidanceTests(unittest.TestCase):
    def setUp(self):
        """Start a self visit whose first message reports retirement and turning 65."""
        self.case = flow_harness.NaturalFlowTests()
        self.case.setUp()
        self.case.message(TEXT, [self.case.update('RC01', {'choice': 'self'}, TEXT)])

    def test_decision_question_is_required_before_plans_not_now(self):
        """A current-decision target carries ask_now False and the before-plans rule."""
        target = self.case.composed_context()['required_target']
        self.assertEqual(target['reason'], 'current_decision')
        self.assertFalse(target['ask_now'])
        self.assertIn('before plans can be shown', target['rule'])
        self.assertNotIn('must target this meaning', target['rule'])

    def test_unresolved_report_must_still_be_asked_now(self):
        """An unresolved (uncertain) report stays a code gate: ask_now True and the must-target rule."""
        quote = 'I think my insurance is through my old job.'
        self.case.message(quote, [self.case.update('T05', {'choice': 'employer'}, quote, uncertain=True)])
        target = self.case.composed_context()['required_target']
        self.assertEqual((target['id'], target['reason']), ('T05', 'clarification'))
        self.assertTrue(target['ask_now'])
        self.assertIn('must target this meaning', target['rule'])

    def test_compose_instructions_state_ordering_as_guidance(self):
        """The composer is told the ordering guidance and that question text is example wording."""
        self.assertIn('example phrasing of its meaning', COMPOSE_INSTRUCTIONS)
        self.assertIn('current insurance usually comes\nbefore a preferred start date', COMPOSE_INSTRUCTIONS)
        self.assertIn('required_target.ask_now', COMPOSE_INSTRUCTIONS)
        self.assertIn('must be answered before plans can be shown', COMPOSE_INSTRUCTIONS)

    def test_timing_guidance_reaches_the_current_insurance_candidate(self):
        """With turning 65 known, T05's purpose explains why it usually precedes a start date."""
        moves = self.case.flow.eligible(self.case.owner, self.case.g, self.case.r)
        t05 = next(m for m in moves if m['id'] == 'T05')
        self.assertIn('decides which enrollment rules apply', t05['purpose'])


if __name__ == '__main__':
    unittest.main()
