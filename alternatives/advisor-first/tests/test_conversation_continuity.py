"""Visit dialogue continuity, permission and approved-question regressions.

Scripted Responses transport only: no network, paid calls or customer storage.
"""
import json
import unittest
from unittest.mock import patch

import test_natural_flow as fixtures
from chat import ModelUnavailable
from natural_flow import CONTEXT_POLICY, LEGACY_CONTEXT_POLICY
from session_recovery import resume_visit


class ConversationContinuityTests(unittest.TestCase):
    setUp = fixtures.NaturalFlowTests.setUp
    payload = fixtures.NaturalFlowTests.payload
    take = fixtures.NaturalFlowTests.take
    turn = fixtures.NaturalFlowTests.turn
    message = fixtures.NaturalFlowTests.message
    choice = fixtures.NaturalFlowTests.choice
    task = fixtures.NaturalFlowTests.task
    stage_payloads = fixtures.NaturalFlowTests.stage_payloads
    extracted_context = fixtures.NaturalFlowTests.extracted_context
    composed_context = fixtures.NaturalFlowTests.composed_context
    update = staticmethod(fixtures.NaturalFlowTests.update)
    extraction = staticmethod(fixtures.NaturalFlowTests.extraction)

    def test_both_stages_receive_the_actual_prior_exchange_without_recap_template(self):
        first = self.message('Please keep things simple.', compose={
            'reply':'We can focus on what you need today.',
            'question':'What would you like help with?'})
        self.message('Help me understand my choices.')
        expected = [{'user':'Please keep things simple.',
                     'assistant':first['reply'],
                     'question':first['assessment']['nextQuestion']['question']}]
        self.assertEqual(self.extracted_context()['recent_exchanges'], expected)
        self.assertEqual(self.composed_context()['recent_exchanges'], expected)
        self.assertEqual(self.extracted_context(0)['recent_exchanges'], [])

    def test_old_permission_keeps_profile_context_but_does_not_transfer_dialogue(self):
        self.task('timing')
        self.message('I turn 65 in November.')
        self.message('Please continue.', contextPolicy=LEGACY_CONTEXT_POLICY)
        self.assertNotIn('recent_exchanges', self.extracted_context())
        self.assertNotIn('recent_exchanges', self.composed_context())
        self.assertIn('guide.situation.age65', {item['id'] for item in self.extracted_context()['reports']})
        self.assertNotIn((self.owner, self.flow.current_chain[self.owner]), self.flow.visit_memory)

    def test_previous_v2_permission_does_not_gain_cross_topic_dialogue(self):
        marker = 'A fictional visit-only concern from the timing discussion.'
        self.message(marker)
        self.message('Please continue.', contextPolicy='natural-context-v2')
        self.assertNotIn('recent_exchanges', self.extracted_context())
        self.assertNotIn('recent_exchanges', self.composed_context())
        self.assertNotIn(marker, json.dumps(self.calls[-2:]))
        self.assertNotIn((self.owner, self.flow.current_chain[self.owner]), self.flow.visit_memory)

    def test_no_history_is_serialized_in_profile_or_turn_journal(self):
        marker = 'A fictional conversational detail stays only in this visit memory.'
        self.message(marker)
        self.assertNotIn(marker, json.dumps([self.g, self.r, list(self.flow.turn_journal.values())]))
        self.assertIn(marker, json.dumps(list(self.flow.visit_memory.values())))

    def test_exact_request_replay_does_not_duplicate_memory_or_model_calls(self):
        payload = self.payload({'type':'message', 'message':'Please keep things simple.'})
        self.extractions.append(self.extraction())
        first = self.take(payload)
        calls = len(self.calls)
        replay = self.flow.turn(self.owner, payload)
        self.assertEqual(replay, first)
        self.assertEqual(len(self.calls), calls)
        memory = self.flow.visit_memory[(self.owner, self.flow.current_chain[self.owner])]
        self.assertEqual(len(memory['exchanges']), 1)

    def test_resume_projects_completed_replies_without_recomposing(self):
        first = self.payload({'type': 'message', 'message': 'Please keep things simple.'})
        self.extractions.append(self.extraction())
        first_result = self.take(first)
        second = self.payload({'type': 'message', 'message': 'Help me understand my choices.'})
        self.extractions.append(self.extraction())
        second_result = self.take(second)
        calls = len(self.calls)
        restored = resume_visit(self.flow, self.owner, {'requestId': second['requestId']})
        self.assertEqual([(row['user'], row['reply']) for row in restored['history']], [
            (first['action']['message'], first_result['reply']),
            (second['action']['message'], second_result['reply']),
        ])
        self.assertEqual(len(self.calls), calls)

    def test_new_refresh_chain_and_other_owner_cannot_read_prior_dialogue(self):
        self.message('Please keep things simple.')
        old_chain = self.flow.current_chain[self.owner]
        self.continuation = None
        self.turn({'type':'refresh'})
        self.assertNotEqual(self.flow.current_chain[self.owner], old_chain)
        self.message('Please continue.')
        self.assertEqual(self.extracted_context()['recent_exchanges'], [])
        self.flow.current_chain['another-owner'] = old_chain
        self.assertEqual(self.flow.recent_exchanges('another-owner', '', CONTEXT_POLICY), [])

    def test_history_expires_and_otherwise_keeps_the_whole_visit(self):
        """History expires with the visit; until then every exchange is kept (D155)."""
        self.message('Please keep things simple.')
        chain = self.flow.current_chain[self.owner]
        entry = self.flow.visit_memory[(self.owner, chain)]
        entry['expires'] = 0
        self.message('Please continue.')
        self.assertEqual(self.extracted_context()['recent_exchanges'], [])
        before = len(self.flow.visit_memory[(self.owner, chain)]['exchanges'])
        for _ in range(7):
            self.message('A fictional concern. ' * 45)
        exchanges = self.flow.visit_memory[(self.owner, chain)]['exchanges']
        self.assertEqual(len(exchanges), before + 7)

    def test_old_message_cannot_be_replayed_as_a_new_profile_quote(self):
        text = 'I know a little about Medicare.'
        self.message(text)
        self.message('Please continue.', [self.update('T02', {'choice':'some'}, text)])
        self.assertNotIn('knowledge.general', self.g['fields'])
        self.assertEqual(self.extracted_context()['recent_exchanges'][0]['user'], text)

    def test_v3_topic_change_preserves_visit_continuity_in_both_stages(self):
        self.task('timing')
        self.message('A fictional timing detail to remember for this conversation.')
        self.message('I just want to learn about Medicare.', extraction=self.extraction(
            task='learn', task_quote='I just want to learn about Medicare.'))
        self.assertTrue(self.extracted_context()['recent_exchanges'])
        self.assertEqual(self.composed_context()['recent_exchanges'],
                         self.extracted_context()['recent_exchanges'])

    def test_birthday_uses_approved_familiarity_target_and_options(self):
        out = self.message('I turn 65 in November.', compose={'question_target': 'T02'})
        question = out['assessment']['nextQuestion']
        self.assertEqual(question['id'], 'T02')
        self.assertEqual([option[0] for option in question['choices']], ['new', 'some', 'comfortable', 'unknown'])
        self.assertNotEqual(question['question'], 'Where are you with Medicare so far?')
        self.message('I know a little about Medicare.', [self.update('T02', {'choice':'some'}, 'I know a little about Medicare.')])
        self.assertNotEqual(self.r['natural']['dialogue']['lastTarget']['id'], 'T02')

    def test_question_only_reply_avoids_a_forced_acknowledgment(self):
        out = self.message('Please keep things simple.', compose={'reply':''})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(out['reply'], '')
        self.assertTrue(out['assessment']['nextQuestion']['question'])
        self.assertEqual(set(out['metrics']['stageMs']), {'extraction', 'composition'})
        self.assertTrue(all(type(value) is int and value >= 0 for value in out['metrics']['stageMs'].values()))

    def test_familiarity_generation_cannot_fall_back_to_vague_progress(self):
        out = self.message('I turn 65 in November.', compose={
            'question_target':'T02', 'question':'Where are you with Medicare so far?'})
        self.assertEqual(out['assessment']['nextQuestion']['question'], self.flow.question('T02')['question'])

    def test_education_pause_is_distinct_from_finishing_intake(self):
        self.task('timing')
        out = self.message('Before we go on, what is Medicare Part B?',
            extraction=self.extraction(mode='answer', fact_ids=['partb']),
            compose={'reply':'Part B helps pay for doctors’ services and outpatient care.',
                     'question':'', 'evidence_refs':['partb']})
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertIsNotNone(self.flow.assess(self.g, self.r)['nextQuestion'])

    def test_comparison_start_question_has_resolved_timing_context_in_both_stages(self):
        self.task('compare')
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        self.choice('RC09', choice='spouse_job')
        self.message('I turn 65 in November and I know a little about Medicare.', [
            self.update('T02', {'choice':'some'}, 'I know a little about Medicare.')],
            compose={'question_target':'T04','question':self.flow.question('T04')['question']})
        self.assertEqual(self.flow.assess(self.g, self.r)['nextQuestion']['id'], 'T04')
        self.message('Please continue.',
            compose={'question_target':'T04','question':self.flow.question('T04')['question']})
        for context in [self.extracted_context(), self.composed_context()]:
            reports = {item['id']:item['value'] for item in context['reports']}
            self.assertEqual(reports['readiness.RC09.profile.choice'], 'spouse_job')
            self.assertEqual(reports['guide.situation.age65'], {'month':11, 'year':None})
            self.assertFalse(any(item['id'] == 'readiness.RC09.profile.choice' for item in context['known']))
            self.assertEqual(context['activeQuestion']['id'], 'T04')

    def test_old_profile_permission_does_not_gain_active_timing_scope(self):
        self.task('compare')
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        self.choice('RC09', choice='spouse_job')
        self.message('I turn 65 in November and I know a little about Medicare.', [
            self.update('T02', {'choice':'some'}, 'I know a little about Medicare.')])
        self.message('Please continue.', contextPolicy=LEGACY_CONTEXT_POLICY)
        for context in [self.extracted_context(), self.composed_context()]:
            reports = {item['id']:item['value'] for item in context['reports']}
            self.assertNotIn('readiness.RC09.profile.choice', reports)
            self.assertNotIn('guide.situation.age65', reports)
            self.assertIn('readiness.RC09.profile.choice', {item['id'] for item in context['known']})

    def test_familiarity_scope_has_circumstances_but_not_unneeded_enrollment_dates(self):
        self.task('compare')
        self.choice('RC01', choice='self')
        self.choice('RC05', month='April 2026')
        out = self.message('I have been retired for a few years and I turn 65 in November.',
                           compose={'question_target':'T02'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T02')
        reports = {item['id']:item['value'] for item in self.composed_context()['reports']}
        self.assertEqual(reports['guide.situation.age65'], {'month':11, 'year':None})
        self.assertEqual(reports['guide.situation.retirement']['status'], 'retired')
        self.assertNotIn('readiness.RC05.profile.month', reports)

    def test_practical_enrollment_request_survives_a_separate_learning_label(self):
        text = 'I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options'
        updates = [self.update('T01', {'choice':'learn'}, 'want to explore my options'),
                   self.update('RC01', {'choice':'self'}, 'I turn 65 in November'),
                   self.update('T02', {'choice':'new'}, 'dont know too much')]
        out = self.message(text, extraction=self.extraction(updates, task='learn',
            task_quote='want to explore my options',
            practical_request={'task':'timing', 'quote':'want to enroll in medicare'}))
        self.assertEqual(self.flow.value(self.g, 'knowledge.general'), 'new')
        self.assertEqual(self.flow.value(self.g, 'intent.goal'), 'learn')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(self.composed_context()['advisor_brief']['goal'], 'want to enroll in medicare')

    def test_unquoted_practical_request_does_not_discard_clear_reports(self):
        text = 'I turn 65 in November and know a little about Medicare.'
        out = self.message(text, extraction=self.extraction([
            self.update('T02', {'choice':'some'}, 'know a little about Medicare.')],
            practical_request={'task':'timing', 'quote':'I want to enroll next month'}))
        self.assertEqual(self.flow.value(self.g, 'knowledge.general'), 'some')
        self.assertEqual(self.flow.value(self.g, 'situation.age65')['month'], 11)
        self.assertNotIn('coverage.requestedStartMonth', self.g['fields'])

    def test_legitimate_learning_stays_open_without_reasking_known_goals(self):
        self.task('learn')
        self.choice('T01', choice='learn')
        self.choice('T02', choice='some')
        out = self.message('Please keep the explanations short.',
            extraction=self.extraction(practical_request={'task':'', 'quote':''}),
            compose={'reply':'Tell me which part you would like to understand first.', 'question':''})
        self.assertEqual(out['assessment']['task'], 'learn')
        self.assertTrue(out['assessment']['conversationOpen'])
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_invalid_prose_keeps_the_post_capture_question_without_repeated_failure_reply(self):
        # Q10 (D155): the extractor, not code, reports "for me" from these words.
        self.message('I turn 65 in November.', [self.update('RC01', {'choice':'self'}, 'I turn 65 in November')])
        out = self.message('I know a little about Medicare.',
            [self.update('T02', {'choice':'some'}, 'I know a little about Medicare.')],
            compose={'reply':'Your premium will be $20.', 'report_refs':[]})
        # Never-blank floor (Nov 8, 2026): the invalid prose is gone; one
        # reviewed statement takes its place, never the rejected amount.
        self.assertTrue(out['reply'])
        self.assertNotIn('$20', out['reply'])
        # D157 (CV-03): a failed reply no longer shows "I couldn't finish that answer".
        self.assertNotIn('notice', out)
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertIn(out['assessment']['nextQuestion']['id'], {'T03', 'T05'})
        diagnostic = self.flow.composition_diagnostics[-1]
        self.assertEqual(set(diagnostic), {'code', 'questionAvailable', 'intakePaused'})
        self.assertNotIn('20', json.dumps(diagnostic))
        self.assertNotIn(self.owner, json.dumps(diagnostic))

    def test_composition_failure_preserves_usable_question_and_bounded_diagnostic(self):
        self.task('timing')
        out = self.message('Before we go on, what is Medicare Part B?',
            extraction=self.extraction(mode='answer', fact_ids=['partb']),
            compose={'reply':'Your premium will be $20.', 'question':''})
        self.assertTrue(out['reply'])
        self.assertNotIn('$20', out['reply'])
        self.assertFalse(out['assessment']['intakePaused'])
        self.assertIsNotNone(out['assessment']['nextQuestion'])
        with patch.object(self.flow.agent, 'compose', side_effect=ModelUnavailable('A fictional diagnostic failure.')):
            with self.assertLogs('natural_flow', level='WARNING') as captured:
                for _ in range(55):
                    self.flow.compose_response(self.owner, out, 'A fictional question.',
                        [],
                        CONTEXT_POLICY, 'fictional-diagnostic-key', None)
        self.assertLessEqual(len(self.flow.composition_diagnostics), 50)
        self.assertEqual(len(captured.output), 55)
        self.assertNotIn('fictional', ' '.join(captured.output))
        self.assertNotIn(self.owner, ' '.join(captured.output))
        self.assertTrue(all('code=' in line and 'question_available=' in line for line in captured.output))

    def test_foundation_candidates_do_not_attach_an_unasked_lesson(self):
        out = self.message('I turn 65 in November.')
        extraction = self.stage_payloads('daylight_guide_commands')[-1]
        self.assertEqual([fact['id'] for fact in extraction['reviewed_facts']], ['basics', 'parts', 'routesintro'])
        self.assertEqual(out['facts'], [])
        self.assertTrue(self.composed_context()['evidence'])
        self.assertEqual(out['advisor']['teachingFactIds'], [])

    def test_followup_insurance_reports_advance_even_if_advisory_task_quote_is_bad(self):
        first = 'I turn 65 in November and want to enroll in Medicare. I know very little about it.'
        # Q10 (D155): the instructed extractor reports "for me" from the
        # person's own first-person words; code no longer guesses it.
        self.message(first, extraction=self.extraction([
            self.update('RC01', {'choice':'self'}, 'I turn 65 in November'),
            self.update('T02', {'choice':'new'}, 'I know very little about it.')],
            practical_request={'task':'timing', 'quote':'want to enroll in Medicare'}))
        self.assertIn(self.flow.assess(self.g, self.r)['nextQuestion']['id'], {'T03', 'T05'})
        text = "My health insurance is through my wife's current job."
        out = self.message(text, extraction=self.extraction([
            self.update('T05', {'choice':'employer'}, text),
            self.update('RC09', {'choice':'spouse_job'}, text)],
            task='timing', task_quote='Insurance comes through a spouse employer.',
            requests=[{'id':'payer_order','quote':'Please tell me who pays first.'}]),
            compose={'question_target': 'RC11'})
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(self.flow.report(self.r, 'RC09')['choice'], 'spouse_job')
        # The explicit spouse-job reports keep coverage/job-end clarification
        # available even when ZIP ranks first. Invalid advisory metadata must
        # not block those reports or this explicitly selected approved follow-up.
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC11')
        self.assertEqual(out['assessment']['task'], 'compare')
        self.assertEqual(out['generated']['status'], 'complete')


if __name__ == '__main__':
    unittest.main()


class EveryTurnEndsWithAQuestionTests(unittest.TestCase):
    """Live-run defects of Nov 9, 2026 (P05 'No.', P06/P08 closed floor, one-word chip answers)."""
    setUp = fixtures.NaturalFlowTests.setUp
    payload = fixtures.NaturalFlowTests.payload
    take = fixtures.NaturalFlowTests.take
    turn = fixtures.NaturalFlowTests.turn
    message = fixtures.NaturalFlowTests.message
    choice = fixtures.NaturalFlowTests.choice
    task = fixtures.NaturalFlowTests.task
    stage_payloads = fixtures.NaturalFlowTests.stage_payloads
    composed_context = fixtures.NaturalFlowTests.composed_context
    update = staticmethod(fixtures.NaturalFlowTests.update)
    extraction = staticmethod(fixtures.NaturalFlowTests.extraction)

    def test_yes_or_no_demand_does_not_allow_a_pause(self):
        self.message('I turn 65 in November.')
        out = self.message('Should I throw away the COBRA bill now? Just say yes or no.',
                           compose={'question_target': None, 'reply': 'No.', 'question': '',
                                    'agenda_update': {'current_concern': 'COBRA bill', 'pause': True}})
        self.assertFalse(self.composed_context()['pause_allowed'])
        self.assertIn('No.', out['reply'])
        self.assertTrue(out['assessment']['nextQuestion'] or out['reply'].rstrip().endswith('?'))

    def test_person_words_allow_the_pause(self):
        self.message('I turn 65 in November.')
        out = self.message("That's all for today, thanks.",
                           compose={'question_target': None, 'reply': 'Of course. Come back whenever you like.', 'question': '',
                                    'agenda_update': {'current_concern': '', 'pause': True}})
        self.assertTrue(self.composed_context()['pause_allowed'])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertFalse(out['reply'].rstrip().endswith('?'))

    def test_floor_without_an_approved_question_still_asks_one(self):
        self.message('I turn 65 in November.')
        out = self.message('Does losing my doctor mean they have to let me buy that G policy?',
                           compose=ModelUnavailable('synthetic composition failure'))
        self.assertEqual(out['advisor']['reason'], 'recovery')
        self.assertTrue(out['assessment']['nextQuestion'] or out['reply'].rstrip().endswith('?'))
        self.assertNotIn('could not verify', out.get('notice') or '')

    def test_one_word_answer_matching_the_chip_is_recorded(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        asked = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual((asked or {}).get('id'), 'T04', asked)
        # The scripted extractor proposes nothing; the server recognises the chip label.
        self.message("As soon as possible. I don't want a gap.")
        self.assertEqual(self.flow.value(self.g, 'coverage.requestedStart'), 'soonest')

    def test_direct_choice_matching_is_exact_and_bounded(self):
        from adaptive_flow import Q
        current = lambda identifier: {'id': identifier, 'choices': Q[identifier]['choices']}
        pick = lambda identifier, text: [u['fields']['choice'] for u in self.flow.direct_choices(text, current(identifier), [])]
        self.assertEqual(pick('RC04', 'Neither.'), ['neither'])
        self.assertEqual(pick('RC09', 'Mine. I already told you, 240 employees.'), ['my_job'])
        self.assertEqual(pick('T05', 'An HMO with drugs. Never had Medigap.'), ['advantage'])
        self.assertEqual(pick('T10', 'Keeping my doctor, then total cost. So should I stop?'), ['doctors', 'total_cost'])
        self.assertEqual(pick('RC10', 'About 120 people'), ['yes'])
        self.assertEqual(pick('RC10', '8 people. I run a shop.'), ['no'])
        self.assertEqual(pick('RC04', 'Which parts do I need?'), [])
        self.assertEqual(pick('T05', 'Both, really: Medicare Parts A and B'), [])
        self.assertEqual(pick('RC04', 'Neither of my sisters has signed up and I am not sure what I should do about it either.'), [])
        self.assertEqual(self.flow.direct_choices('Neither.', current('RC04'), [{'id': 'RC04'}]), [])
