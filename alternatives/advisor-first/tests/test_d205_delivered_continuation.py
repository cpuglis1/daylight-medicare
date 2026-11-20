"""Whole-controller fictional journeys, scripted transport only; no paid calls."""
import copy
import unittest

import test_pending_questions as pending
import test_guided_close as closing
import conversation_planner as planner
import conversation_records as records


QUESTION = 'Do you understand the steps to sign up, or would you like enrollment help?'
EARLIER = 'Understanding the steps to sign up helps you decide whether you need enrollment help.'


def clarification(question=QUESTION):
    return dict(reply='We can work through this together.', question_target=None, question=question,
                conversation_assessment=dict(goal_progress='open', next_move='clarify'))


class DeliveredContinuation(pending.PendingBase):
    def valid(self, out, kind=None):
        self.assertTrue(planner.valid_delivered_next(out), out.get('conversationNext'))
        if kind:
            self.assertEqual(out['conversationNext']['kind'], kind)
        self.assertNotIn('_records_next_move', out)
        self.assertNotIn('_records_clarification_lead', out)

    def test_short_button_answer_preserves_question_after_overlapping_teaching(self):
        self.opening()
        state = planner.state(self.flow, self.owner)
        records.record_shown(state, EARLIER, {})
        # Demonstrate this is the diagnosed collision, rather than an easy new question.
        self.assertEqual(records.filter_blocks(state, QUESTION)[0], '')
        self.compositions.append(clarification())
        out = self.turn({'type': 'choice', 'id': 'RC04', 'fields': {'choice': 'neither'}})
        self.valid(out, 'clarification')
        self.assertEqual(out['reply'].count(QUESTION), 1)
        self.assertFalse(self.offers(out))
        self.assertEqual(self.flow.report(self.r, 'RC04')['choice'], 'neither')
        self.assertEqual(out['metrics']['llmCalls'], 1)
        self.assertNotIn(sorted(records.tokens(QUESTION)), state['records_education']['shown'])
        # The actual question reaches conversational memory, not teaching credit.
        later = self.say('Yes, I know the steps. Let us discuss my doctors.', targets=['T06'],
                         reason='person_raised', disposition='none')
        self.valid(later, 'profile_question')
        self.assertEqual(self.asked(later), 'T06')
        self.assertIn(QUESTION, str(self.stage_payloads('daylight_guide_commands')[-1]))
        for context in (self.extracted_context(), self.composed_context()):
            self.assertIn('profile_record', context)
            self.assertIn('education_record', context)
            self.assertNotIn('RC04', context['profile_record']['open'])
            self.assertIn('education_record', context['readiness']['selection_rule'])

    def test_confusion_detour_correction_and_resume_keep_the_pending_question(self):
        self.opening()
        first = self.say('Neither, I have not enrolled.',
            updates=[self.update('RC04', {'choice': 'neither'}, 'Neither, I have not enrolled.')],
            targets=['T06'], disposition='answered', compose=self.ask_recommended(target='T06'))
        self.valid(first, 'profile_question')
        detour = self.say('What does keeping a doctor mean?', targets=['T06'], disposition='detour',
            compose=self.ask_recommended(reply='We can work through that question together.', target='T06'))
        self.valid(detour, 'profile_question')
        self.assertEqual(self.asked(detour), 'T06')
        self.assertTrue(self.trace(detour)['returned'])
        self.assertEqual(self.trace(detour)['passes'], 0)
        corrected = self.say('Correction: I have COBRA, not coverage through my current job.',
            updates=[self.update('T05', {'choice': 'cobra'}, 'I have COBRA', correction=True)],
            targets=['T06'], disposition='detour', compose=self.ask_recommended(target='T06'))
        self.valid(corrected, 'profile_question')
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['cobra'])
        self.assertEqual(self.asked(corrected), 'T06')
        self.compositions.append(self.ask_recommended(target='T07'))
        answered = self.turn({'type': 'choice', 'id': 'T06', 'fields': {'choice': 'none'}})
        self.valid(answered, 'profile_question')
        self.assertEqual(self.asked(answered), 'T07')
        self.assertFalse(self.offers(answered))

    def test_clarification_survives_ready_profile_then_review_and_return(self):
        closing.GuidedClose.fill(self)
        out = self.say('I want to talk about changing coverage.', targets=[], task='compare', disposition='none',
            compose=clarification())
        self.valid(out, 'clarification')
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertFalse(out.get('comparisonClose', {}).get('show'))
        self.assertFalse(self.offers(out))
        ready = self.say('Let us compare the options now.', task='compare', disposition='none',
            compose=dict(reply='We can use your priorities to focus the comparison.', question_target=None, question=''))
        self.valid(ready, 'action')
        self.assertEqual(ready['conversationNext']['action'], 'plan_review')
        review = self.turn({'type': 'review_plans'}, aiConsent=False)
        self.valid(review, 'action')
        self.assertEqual(review['conversationNext']['action'], 'review')
        handoff = self.turn({'type': 'confirm_plan_review', 'token': review['review']['token']}, aiConsent=False)
        self.valid(handoff, 'action')
        self.assertIn('plansHandoff', handoff)
        returned = self.say('Back from Plans: I have a question about these choices.', task='compare',
            targets=[], disposition='none', compose=clarification('Which part would you like to work through?'))
        self.valid(returned, 'clarification')
        self.assertEqual(returned['metrics']['llmCalls'], 2)

    def test_real_pause_has_no_forced_question_or_offer(self):
        self.opening()
        out = self.say('Stop for today.', targets=[], mode='pause', disposition='none',
                       compose=dict(reply='We can leave this here for today.', question_target=None, question=''))
        self.valid(out, 'finish')
        self.assertIsNone(self.asked(out))
        self.assertFalse(self.offers(out))

    def test_slow_down_retains_pace_choices_without_a_competing_profile_question(self):
        self.opening()
        out = self.say('Slow down, why do you need that information?', mode='detour',
                       disposition='detour', targets=['RC04'])
        self.valid(out, 'action')
        self.assertEqual(out['conversationNext']['card'], 'next_step_offer')
        self.assertTrue(self.offers(out)[0]['pace'])
        self.assertIsNone(self.asked(out))

    def test_consumed_offers_recover_a_real_question_and_final_check_rejects_dead_end(self):
        self.opening()
        state = planner.state(self.flow, self.owner)
        state['records_offers'] = {task: {'shown': 1, 'accepted': True} for task in records.OFFER_LABELS}
        out = self.say('Neither, I have not enrolled.',
            updates=[self.update('RC04', {'choice': 'neither'}, 'Neither, I have not enrolled.')],
            targets=['T06'], disposition='answered',
            compose=dict(reply='We can work through this together.', question_target=None, question=''))
        self.valid(out, 'profile_question')
        self.assertFalse(self.offers(out))
        broken = copy.deepcopy(out)
        broken['assessment']['nextQuestion'] = None
        self.assertFalse(planner.valid_delivered_next(broken))

    def test_replay_is_idempotent_and_stale_source_withdraws_clarification(self):
        self.opening()
        out = self.say('Neither, I have not enrolled.',
            updates=[self.update('RC04', {'choice': 'neither'}, 'Neither, I have not enrolled.')],
            targets=[], disposition='answered', compose=clarification())
        ledger = copy.deepcopy(self.ledger())
        replayed = self.flow.replay_response(self.owner, out)
        self.valid(replayed, 'clarification')
        self.assertEqual(replayed['reply'], out['reply'])
        self.assertEqual(self.ledger(), ledger)
        from unittest.mock import patch
        with patch.object(self.flow.pilot_knowledge, 'current', return_value=False):
            stale = self.flow.replay_response(self.owner, out)
        self.valid(stale, 'unavailable')
        self.assertNotIn(QUESTION, stale['reply'])
        self.assertEqual(stale['generated']['code'], 'knowledge_source_stale')
        broken = copy.deepcopy(out)
        broken.setdefault('cards', []).append(records.offer_card('compare'))
        self.assertFalse(planner.valid_delivered_next(broken))

    def test_current_task_record_reaches_controls_before_deferred_memory_commit(self):
        from advisor_memory import CONTEXT_POLICY
        self.opening()
        draft = clarification()
        draft['task_work'] = {'check_ids': ['enrollment_timing'], 'blocking_concepts': [], 'next_step': 'review'}
        out = self.say('Neither, I have not enrolled.',
            updates=[self.update('RC04', {'choice': 'neither'}, 'Neither, I have not enrolled.')],
            targets=[], disposition='answered', compose=draft)
        self.valid(out, 'clarification')
        saved = self.flow.memory.task_work(self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)
        self.assertIn('enrollment_timing', saved['selection']['check_ids'])
        self.assertEqual([row['check_id'] for row in out['task_work']['checks']], saved['selection']['check_ids'])
        self.assertEqual(out['task_work']['next_step'], saved['selection']['next_step'])


if __name__ == '__main__':
    unittest.main()
