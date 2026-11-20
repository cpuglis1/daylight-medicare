"""D202: fictional, offline controller tests; no paid or live model calls."""
import unittest
import test_pending_questions as pending
import conversation_records as records
import conversation_prompts as prompts


class QuestionTiers(pending.PendingBase):
    def test_both_stages_receive_tiers_and_unanswered_core(self):
        self.opening()
        for context in (self.extracted_context(), self.composed_context()):
            profile = context['profile_record']
            tiers = profile['question_tiers']
            self.assertTrue({'T01', 'T03', 'T05', 'T06', 'T07', 'T09', 'T10', 'RC04'} <= set(tiers['1']))
            self.assertTrue({'RC10', 'RC11', 'RC12', 'RC14'} <= set(tiers['2']))
            self.assertTrue({'T03', 'T06', 'T07', 'T10'} <= set(profile['tier_1_open']))
            self.assertIn('enrollment_help', context['readiness'])
        profile = self.composed_context()['profile_record']
        self.assertNotIn('T05', profile['tier_1_open'])  # captured from opening
        moves = self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertTrue({'T03', 'T06', 'T07', 'T10'} <= {m['id'] for m in moves})
        self.assertEqual(next(m['tier'] for m in moves if m['id'] == 'RC10'), 2)
        self.assertEqual(next(m['tier'] for m in moves if m['id'] == 'T06'), 1)

    def test_composer_can_choose_core_instead_of_interpreter_timing_target(self):
        def choose_core(sent):
            q = next(m for m in sent['question_candidates'] if m['id'] == 'T06')
            return dict(reply='Let’s focus on what matters to you.', question_target='T06',
                        question=q['question']['question'])
        out = self.opening(compose_override=choose_core)
        self.assertEqual(self.asked(out), 'T06')
        self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_specific_conditional_request_can_override_core_and_pending(self):
        self.first(parts='neither')
        out = self.say('First, can I delay Part B while working?', targets=['RC10'],
                       reason='person_raised', disposition='detour')
        self.assertEqual(self.asked(out), 'RC10')
        self.assertIn('T03', self.available())
        self.assertIn('T07', self.available())
        self.assertIsNone(self.flow.report(self.r, 'RC10').get('choice'))

    def test_no_medicare_can_lead_with_enrollment_understanding_without_extra_offer(self):
        self.opening()
        text = 'Neither, I do not have Part A or Part B.'
        question = 'Do you know how to sign up for Medicare, or would you like help with the steps?'
        out = self.say(text, updates=[self.update('RC04', {'choice': 'neither'}, text)],
                       targets=[], disposition='answered', compose=dict(
                           reply='We can work through the next step together.', question_target=None,
                           question=question,
                           conversation_assessment=dict(goal_progress='open', next_move='clarify')))
        self.assertIsNone(self.asked(out))
        self.assertIn(question, out['reply'])
        self.assertEqual(self.offers(out), [])
        self.assertEqual(self.flow.report(self.r, 'RC04')['choice'], 'neither')
        self.assertEqual(out['metrics']['llmCalls'], 2)
        self.assertNotIn('_records_clarification_lead', out)
        # Understanding does not become a made-up profile answer or force intake.
        after = self.say('Yes, I know the steps. Let us look at doctors.', targets=['T06'],
                         reason='person_raised', disposition='none')
        self.assertEqual(self.asked(after), 'T06')

    def test_structured_answer_does_not_default_to_next_conditional_detail(self):
        self.opening()
        text = 'Neither.'
        self.say(text, updates=[self.update('RC04', {'choice': 'neither'}, text)],
                 targets=['RC10'], disposition='answered')
        self.compositions.append(self.ask_recommended())
        out = self.turn({'type': 'choice', 'id': 'RC10', 'fields': {'choice': 'yes'}})
        self.assertEqual(records.QUESTION_TIERS[self.asked(out)], 1)
        self.assertIn('RC11', self.available())  # still available to the model
        self.assertIn('RC12', self.available())

    def test_prompt_bounds_still_hold(self):
        for name in ('INTERPRETATION_RECORDS', 'INTERPRETATION_PENDING', 'COMPOSITION_RECORDS'):
            self.assertLessEqual(len(getattr(prompts, name)), 8500, name)


if __name__ == '__main__':
    unittest.main()
