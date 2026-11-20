"""D201: fictional offline controller checks, no model-quality claim."""
import unittest
import test_pending_questions as pending
import test_quiet_recovery as recovery
import conversation_records as records


class PriorityContext(pending.PendingBase):
    def test_both_stages_distinguish_orientation_from_conditional_checks(self):
        self.first(parts='neither')
        for context in (self.extracted_context(), self.composed_context()):
            scope = context['readiness']['enrollment_scope']
            self.assertNotIn('RC12', scope['orientation'])
            self.assertNotIn('RC14', scope['orientation'])
            self.assertEqual(set(scope['conditional_checks']), {'RC10', 'RC11', 'RC12', 'RC14'})
        # Existing safety needs remain intact; no readiness gate was relaxed.
        needs = self.composed_context()['readiness']['outcomes']['enrollment_step']['needs']
        self.assertIn('RC12', needs)
        self.assertIn('RC10', needs)
        self.assertNotIn('RC04', self.available())

    def test_user_raised_drug_coverage_can_still_take_priority(self):
        self.first(parts='neither')
        out = self.say('First, help me understand my drug coverage.', targets=['RC12'],
                       reason='person_raised', disposition='detour', task='drug_coverage')
        self.assertEqual(self.asked(out), 'RC12')
        self.assertIsNone(self.flow.report(self.r, 'RC12').get('choice'))


class HonestRecovery(recovery.QuietRecovery):
    # Reuse the real controller fixture without rerunning inherited suites here.
    for name in dir(recovery.QuietRecovery):
        if name.startswith('test_'):
            locals()[name] = None

    def test_withheld_explanation_cannot_leave_a_claim_of_understanding(self):
        records.enable(self.flow)
        self.choice('RC01', choice='self')
        text = 'I do not understand what that means.'
        extracted = self.interpreted(text, task='compare', mode='detour')
        extracted['discussion']['question_quote'] = text
        canonical = []
        def draft(sent):
            move = sent['question_candidates'][0]
            canonical.append(move['question']['question'])
            return dict(reply='Your premium is $99999.', question_target=move['id'],
                        question='With that meaning in mind, ' + canonical[-1])
        out = self.message(text, extraction=extracted, compose=draft)
        self.assertEqual(out['generated']['answer_state'], 'unanswered')
        self.assertEqual(out['assessment']['nextQuestion']['question'], canonical[-1])
        self.assertNotIn('99999', out['reply'])
        self.assertEqual(out['metrics']['llmCalls'], 2)


if __name__ == '__main__':
    unittest.main()
