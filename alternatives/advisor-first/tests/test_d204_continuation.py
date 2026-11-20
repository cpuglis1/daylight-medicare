"""D204 fictional offline controller regressions."""
import unittest
import test_pending_questions as pending
import test_guided_close as closing


class Continuation(pending.PendingBase):
    def test_ready_checkpoint_does_not_get_a_second_work_offer(self):
        closing.GuidedClose.fill(self)
        out = self.say('Please compare these options.', task='compare', disposition='none',
                       compose=dict(reply='We can use your priorities to focus the comparison.',
                                    question_target=None, question=''))
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertTrue(out['comparisonClose']['show'])
        self.assertFalse(self.offers(out))
        self.assertFalse(out['metrics']['records']['offer_button'])
        self.assertEqual(out['metrics']['llmCalls'], 2)
        # A later turn with the same ready profile must not restart the task.
        later = self.say('Continue with the comparison.', task='compare', disposition='none',
                         compose=dict(reply='Your reported details carry forward.',
                                      question_target=None, question=''))
        self.assertTrue(later['planReadiness']['canReview'])
        self.assertFalse(self.offers(later))
        review = self.turn({'type': 'review_plans'}, aiConsent=False)
        self.assertEqual(review['review']['kind'], 'plan_profile')

    def test_switching_goal_can_be_clarified_without_forcing_new_intake(self):
        self.choice('RC01', choice='self')
        text = 'I have Medicare Advantage and I am thinking about switching.'
        question = 'Is there anything about your current plan you would like to improve, or something you want to keep?'
        out = self.say(text, updates=[self.update('T05', {'choice': 'advantage'}, 'I have Medicare Advantage')],
                       targets=[], mode='discuss', task='review', disposition='none',
                       compose=dict(reply='Let’s start with what you want from a change.',
                                    question_target=None, question=question,
                                    conversation_assessment=dict(goal_progress='open', next_move='clarify')))
        self.assertIn(question, out['reply'])
        self.assertIsNone(self.asked(out))
        self.assertFalse(self.offers(out))
        for context in (self.extracted_context(), self.composed_context()):
            self.assertIn('switching_goal', context['readiness'])
        self.assertEqual(out['metrics']['llmCalls'], 2)
        self.assertIsNone(self.flow.value(self.g, 'needs.priorities'))


if __name__ == '__main__':
    unittest.main()
