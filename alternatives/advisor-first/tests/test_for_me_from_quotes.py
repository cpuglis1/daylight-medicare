"""Who the visit is for comes only from the person's own words (Q10, D155).

Fix 2 removed code's "for me" guess (any "I'm"/"I'll" in a turning-65 or
retirement message used to set subject.role to self). These tests check that
(1) the extraction instructions tell the AI to report RC01 self only from a
first-person statement about the person's own Medicare, and that "I'm signing
up my parents" is someone; (2) test mode, which stands in for the instructed
extractor, records self for a first-person retirement message; and (3) test mode
records nothing for a helper message, so Daylight asks RC01 instead of saying
"you". All data is fictional.
"""
import unittest

import test_natural_flow as flow_harness
from natural_agent import NaturalAgent


class ForMeFromQuotesTests(unittest.TestCase):
    def fixture_case(self):
        """Return a flow harness switched to the synthetic test-mode extractor."""
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        case.flow.fixture = True
        return case

    def test_instructions_tie_self_to_first_person_quotes(self):
        """The extractor is told to quote first-person words and that signing up parents is someone."""
        # dev made `instructions` a property that picks the :8895 prompts; the
        # base interpreter text is interpretation_instructions.
        text = NaturalAgent.interpretation_instructions
        self.assertIn("Report RC01 self only from the person's own first-person statement", text)
        self.assertIn("I'm signing up my parents\n-> someone", text)
        self.assertIn('Nothing else records RC01 for you', text)

    def test_first_person_retirement_records_self_in_test_mode(self):
        """'I've been retired ... turning 65' records subject.role self from the person's words."""
        case = self.fixture_case()
        out = case.message("I've been retired for a few years, and am turning 65 in November.")
        self.assertEqual(case.flow.value(out['guide'], 'subject.role'), 'self')
        self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'RC01')

    def test_helper_retirement_message_records_no_self_in_test_mode(self):
        """'I'm signing up my parents, who are retiring' records no role, so RC01 is asked."""
        for message in ("I'm signing up my parents, who are retiring next year.",
                        "My mom is retiring and turns 65 in March; I'll handle her paperwork."):
            with self.subTest(message=message):
                case = self.fixture_case()
                out = case.message(message)
                self.assertNotEqual(case.flow.value(out['guide'], 'subject.role'), 'self')
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC01')


if __name__ == '__main__':
    unittest.main()
