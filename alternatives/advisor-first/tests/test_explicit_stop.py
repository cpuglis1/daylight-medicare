"""Explicit conversational control survives both accepted and rejected prose."""
import unittest
import test_natural_flow as support


class ExplicitStopTests(unittest.TestCase):
    def case(self):
        case = support.NaturalFlowTests()
        case.setUp()
        case.task('timing')
        return case

    def test_failed_summary_does_not_reask_after_explicit_stop(self):
        case = self.case()
        out = case.message('Summarize what we covered. No more questions.',
            compose={'reply': 'Your premium will be $20.', 'report_refs': []})
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertTrue(out['assessment']['conversationOpen'])
        self.assertEqual(out['reply'], '')
        self.assertNotIn('education', out)

    def test_explicit_stop_overrides_generated_question(self):
        case = self.case()
        out = case.message('Please no more questions.', compose={})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertEqual(out['advisor']['educationFollowups'], [])

    def test_quoted_or_historical_stop_is_not_current_control(self):
        for text in ('She said "No more questions."', 'Yesterday I said no more questions.',
                     'What happens if I say no more questions?'):
            with self.subTest(text=text):
                case = self.case()
                out = case.message(text, compose={'reply': 'Your premium will be $20.'})
                self.assertEqual(out['generated']['status'], 'unavailable')
                self.assertIsNotNone(out['assessment']['nextQuestion'])
                self.assertFalse(out['assessment']['intakePaused'])
