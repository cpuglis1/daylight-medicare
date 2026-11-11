"""Shared conversation boundaries; these are controller tests, not quality scores."""
import unittest

import test_natural_flow as support
from chat import ModelUnavailable
from decision_guidance import guidance


class ConversationFrameworkTests(unittest.TestCase):
    def test_accepted_answer_followed_by_failure_never_advances_optional_intake(self):
        examples = (
            ('T05', 'What health insurance do you have now?', 'I have COBRA.',
             {'choice': 'cobra'}, 'coverage.current', ['cobra']),
            ('T06', 'Which doctors would you like to keep?', 'Dr. Rowan at Example Clinic',
             {'text': 'Dr. Rowan at Example Clinic'}, 'needs.providers', 'Dr. Rowan at Example Clinic'),
            ('T07', 'Which prescriptions should we include?', 'Example Med',
             {'text': 'Example Med'}, 'needs.medications', 'Example Med'),
        )
        for target, question, answer, fields, stored_field, stored_value in examples:
            with self.subTest(target=target):
                case = support.NaturalFlowTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                case.choice('RC01', choice='self')
                case.message('I would like to work through this.',
                             compose={'question_target': target, 'question': question})
                out = case.message(answer, [case.update(target, fields, answer)],
                                   compose=ModelUnavailable('Synthetic interruption'))
                self.assertEqual(out['generated']['status'], 'unavailable')
                self.assertEqual(case.flow.value(case.g, stored_field), stored_value)
                # Never-blank floor (owner direction, November 8, 2026): a failed
                # generation still shows one reviewed statement and the approved
                # question the server selected, never a bare status line.
                self.assertTrue(out['reply'])
                self.assertIsNotNone(out['assessment']['nextQuestion'])
                self.assertNotEqual(out['assessment']['nextQuestion']['id'], target)
                self.assertTrue(out['assessment']['conversationOpen'])
                self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
                # The selected question was shown, so it survives a refresh.
                self.assertIsNotNone(case.turn({'type': 'refresh'})['assessment']['nextQuestion'])
                calls = len(case.calls)
                case.message("I don't know.", compose={
                    'question_target': None, 'question': '', 'reply': 'We can leave that open.'})
                # The question was shown, so a short "I don't know" resolves it
                # locally as an explicit unknown without a paid model call.
                self.assertEqual(len(case.calls), calls,
                                 'A short reply to the shown question needs no model call.')
                self.assertIsNone(case.flow.value(case.g, 'coverage.requestedStart'))

    def test_inherited_task_label_does_not_override_an_expressed_concern(self):
        candidates = [{'id': 'T03', 'question': {'id': 'T03'}},
                      {'id': 'T05', 'question': {'id': 'T05'}}]
        for task in ('compare', 'review', 'browse'):
            with self.subTest(task=task):
                offered, brief = guidance(candidates, task=task, concerns=[{
                    'status': 'open', 'subject': 'beneficiary', 'topic': 'timing'}])
                self.assertEqual(brief['practical_focus'], 'timing')
                self.assertEqual([x['id'] for x in offered], ['T03', 'T05'])
                self.assertEqual(offered[1]['decision_relevance'], 'current_decision')
                self.assertTrue(brief['relevance_is_advisory'])

    def test_short_supported_reply_can_end_without_another_profile_question(self):
        case = support.NaturalFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        reply = 'We can leave it there for now.'
        out = case.message('That is enough for now. No more questions.', compose={
            'question_target': None, 'question': '', 'reply': reply,
            'agenda_update': {'current_concern': '', 'pause': True}})
        self.assertEqual(out['reply'], reply)
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['generated']['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
