"""D166: fictional journeys through the real read/resolve/compose boundary.

The transport is scripted; socket access is forbidden. These check software,
not the quality of a live model conversation.
"""
import copy
import json
import unittest
from unittest.mock import patch

import test_natural_flow as harness
import enrollment_flow
import conversation_planner as planner
from adaptive_flow import metadata


class ConversationPlannerTests(unittest.TestCase):
    update = staticmethod(harness.NaturalFlowTests.update)
    @staticmethod
    def extraction(updates=(), **extra):
        return {'updates': list(updates), 'requests': [], 'fact_ids': [],
                'agenda': {'concerns': [], 'priorityReason': {}}, 'situation_proposals': [],
                'goal_quote': '', 'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''}, **extra}

    @staticmethod
    def proposal(text, purpose='understand', focus='medigap', **extra):
        return {**planner.empty_proposal(), 'purpose': purpose, 'focus': focus, 'quote': text, **extra}
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task',
                 'stage_payloads', 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)

    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        self.script_legacy_discussion = True
        enrollment_flow.enable(self.flow)
        planner.enable(self.flow)
        def forbidden(*args, **kwargs):
            raise AssertionError('D165 journeys forbid network access')
        for target in ('socket.create_connection', 'socket.getaddrinfo', 'socket.socket.connect'):
            guard = patch(target, forbidden); guard.start(); self.addCleanup(guard.stop)

    def test_curiosity_is_neither_a_choice_nor_pricing(self):
        out = self.message('I want to understand Medigap',
                           extraction=self.extraction(goal_quote='I want to understand Medigap'))
        self.assertIsNone(self.flow.value(self.g, 'intent.coveragePath'))
        self.assertNotEqual(metadata(self.r)['task'], 'medigap')
        self.assertFalse(out.get('whatsLeft'))
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_cost_preference_is_not_a_path_lean(self):
        self.choice('RC01', choice='self')
        out = self.message('Predictable costs matter to me.',
            [self.update('T09', {'choice': 'predictable'}, 'Predictable costs matter to me.')])
        self.assertEqual(self.flow.value(self.g, 'needs.costPreference'), 'predictable')
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_path_start_is_exploration_only(self):
        self.choice('RC01', choice='self')
        out = self.turn({'type': 'enrollment_decision', 'start_with': 'original_medigap'}, aiConsent=False)
        self.assertIsNone(self.flow.value(self.g, 'intent.coveragePath'))
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_reported_doctor_starts_a_check_and_a_concept_question_can_interrupt(self):
        import conversation_planner

        self.choice('RC01', choice='self')
        self.task('providers')
        self.choice('T06', text='Dr. Fiction')
        self.assertTrue(conversation_planner.checks_relevant(self.flow, self.owner, self.g))
        self.message('What does Medigap cover?', extraction=self.extraction())
        self.assertFalse(conversation_planner.checks_relevant(self.flow, self.owner, self.g))

    def test_general_paths_question_needs_no_personal_intake(self):
        text = 'What are the two Medicare paths?'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text,
            focus='coverage_paths', question_quote=text)),
            compose={'education': {'purpose':'teach', 'updates':[], 'visual':'discussion_paths'}})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual([c['kind'] for c in out['cards']], ['discussion_paths'])
        self.assertTrue(all(line for c in out['cards'][0]['columns'] for line in c['lines']))
        self.assertFalse(out['whatsLeft'])
        self.assertNotIn(text, json.dumps(self.r))
        self.assertEqual(len(self.calls), 2)
        self.assertIn('natural conversation flow', self.calls[0]['instructions'])
        self.assertNotIn('mode find means', self.calls[-1]['instructions'])
        self.assertEqual(self.composed_context()['discussion_plan']['question_to_answer'], text)

    def test_adversarial_decision_hints_never_turn_curiosity_into_choice(self):
        for text in ['I want to understand Medigap.', 'I want Medigap prices.',
                     'If I choose Medigap, can I travel?', 'Maybe I want Medigap.',
                     'I do not want Medigap.', 'My friend says I choose Medigap.',
                     'I have Medigap.', 'Show me Medigap.', 'I want to explore Medigap.',
                     'Predictable costs matter.', 'I travel all over the US.',
                     'Would I choose Medigap?', 'I used to want Medigap.']:
            with self.subTest(text=text):
                hint = self.proposal(text, purpose='compare', decision={'stance':'chosen', 'path':'original_medigap', 'quote':text})
                self.assertEqual(planner.validate_proposal(hint, text)['decision']['stance'], 'none')

    def test_explicit_choice_is_separate_from_component_decisions(self):
        text = 'I choose Medigap.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='compare',
            decision={'stance':'chosen', 'path':'original_medigap', 'quote':text})))
        self.assertEqual(out['coveragePath']['state'], 'chosen')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_medigap')
        self.assertIsNone(self.flow.value(self.g, 'intent.components'))
        self.assertEqual(out['conversationPlanner']['investigations'], [])

    def test_original_medicare_choice_leaves_medigap_open(self):
        text = 'I choose Original Medicare.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='compare',
            decision={'stance':'chosen', 'path':'original', 'quote':text})))
        self.assertEqual(out['coveragePath']['path'], 'original')
        self.assertIsNone(self.flow.value(self.g, 'intent.components'))

    def test_explicit_lean_is_not_a_saved_decision(self):
        text = 'I am leaning toward Medicare Advantage.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='compare',
            focus='advantage', decision={'stance':'leaning', 'path':'medicare_advantage', 'quote':text})))
        self.assertEqual(out['coveragePath']['state'], 'leaning')
        self.assertIsNone(self.flow.value(self.g, 'intent.coveragePath'))

    def test_prices_on_both_paths_without_a_preference(self):
        self.choice('RC01', choice='self')
        self.choice('T03', zip='34102')
        text = 'Show me prices on both paths.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='investigate',
            focus='coverage_paths', investigate=['medigap','advantage','part_d'], request_quote=text)))
        self.assertEqual(out['coveragePath']['state'], 'undecided')
        self.assertEqual(set(out['conversationPlanner']['investigations']), {'medigap','advantage','part_d'})
        self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'T03')
        self.assertNotIn('MG_SEX', self.r.get('facts', {}))

    def test_direct_prices_request_does_not_require_lessons(self):
        out = self.message('Show me Medigap prices.')
        self.assertEqual(out['conversationPlanner']['purpose'], 'investigate')
        self.assertIn(out['assessment']['nextQuestion']['id'], ['RC01','T03','MG_AGE','MG_SEX','MG_TOBACCO'])
        self.assertNotIn('discussion_paths', [c['kind'] for c in out.get('cards', [])])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_a_question_interrupts_prices_and_preserves_reports(self):
        self.message('Show me Medigap prices.')
        self.choice('T03', zip='34102')
        text = 'What does Medigap mean?'
        out = self.message(text, compose={'question_target':None,
            'question':'Would you like to return to the pricing details after this explanation?'})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['conversationPlanner']['investigations'], [])
        self.assertEqual(self.flow.value(self.g, 'comparison.scope.zip'), '34102')
        self.assertNotIn('plans_ready', [c['kind'] for c in out.get('cards', [])])

    def test_unknown_plan_category_is_clarified_without_medigap_guess(self):
        text = 'Show me plans.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, focus='')),
            compose={'question_target':None,'question':'Which coverage would you like to explore?'})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_current_coverage_does_not_mean_keep_it(self):
        self.choice('RC01', choice='self')
        text = 'I have Medigap.'
        out = self.message(text, [self.update('T05', {'choice':'original,medigap'}, text)])
        self.assertIn('medigap', self.flow.value(self.g, 'coverage.current'))
        self.assertIsNone(self.flow.value(self.g, 'intent.components'))
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_reason_already_given_is_not_asked_again(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='advantage')
        text = 'My coverage changed and I want to review my options.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='review',
            focus='coverage_paths', reason_quote='My coverage changed')))
        self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'CP_REASON')

    def test_repeat_and_deferred_questions_do_not_loop(self):
        self.message('Explain Medigap.')
        out = self.message('skip this')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'), 'CP_UNDERSTANDING')
        for _ in range(3):
            out = self.message('Thanks.')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'), 'CP_UNDERSTANDING')

    def test_explicit_keep_wait_and_undecided_are_supported(self):
        for path in ['keep_current', 'wait', 'undecided']:
            out = self.turn({'type':'enrollment_decision', 'path':path}, aiConsent=False)
            self.assertFalse(out['conversationPlanner']['investigations'])
            self.assertEqual(out['coveragePath']['state'], 'undecided' if path == 'undecided' else 'chosen')
        self.assertEqual(len(self.calls), 0)

    def test_refresh_retains_the_actual_question(self):
        out = self.message('Explain Medigap.')
        target = out['assessment']['nextQuestion']
        out = self.turn({'type':'refresh'}, aiConsent=False)
        self.assertEqual(out['assessment']['nextQuestion'], target)
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_invalid_investigation_hint_has_no_unmentioned_product(self):
        text = 'Show me Medicare Advantage plans.'
        p = self.proposal(text, purpose='investigate', focus='advantage',
            request_quote=text, investigate=['advantage','medigap'])
        p['guidance'] = dict(mode='work',task='advantage',checks=[],quote=text,finish='')
        out = self.message(text, extraction=self.extraction(discussion=p))
        self.assertEqual(out['conversationPlanner']['investigations'], ['advantage'])

    def test_failed_answer_keeps_question_open_without_price_intake(self):
        from chat import ModelUnavailable
        out = self.message('What does Medigap mean?', compose=ModelUnavailable('Offline fictional failure'))
        self.assertEqual(out['conversationPlanner']['answer_state'], 'unresolved')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_legacy_surface_does_not_get_the_planner(self):
        self.flow.d166 = False
        out = self.message('Explain Medigap.')
        self.assertNotIn('conversationPlanner', out)
        self.assertNotIn('discussion proposes', self.calls[0]['instructions'])

    def test_visit_state_is_removed_with_the_owner(self):
        self.message('Explain Medigap.')
        self.assertTrue(any(key[0] == self.owner for key in self.flow.discussion_visits.visits))
        self.flow.forget_owner(self.owner)
        self.assertFalse(any(key[0] == self.owner for key in self.flow.discussion_visits.visits))

    def test_prefer_never_becomes_chosen_even_if_model_labels_it_so(self):
        text = 'I prefer Medigap.'
        p = self.proposal(text, purpose='compare', decision={'stance':'chosen','path':'original_medigap','quote':text})
        self.assertEqual(planner.validate_proposal(p, text)['decision']['stance'], 'leaning')

    def test_a_changed_lean_supersedes_an_earlier_choice(self):
        self.turn({'type':'enrollment_decision','path':'original_medigap'}, aiConsent=False)
        text = 'I am leaning toward Medicare Advantage.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='compare',
            focus='advantage', decision={'stance':'leaning','path':'medicare_advantage','quote':text})))
        self.assertEqual(out['coveragePath']['state'], 'leaning')
        self.assertEqual(out['coveragePath']['path'], 'medicare_advantage')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'undecided')

    def test_helper_priorities_drive_useful_detail_not_prices(self):
        text = 'I am helping my mother review her coverage because her doctor is important to her.'
        updates = [self.update('RC01', {'choice':'someone'}, 'I am helping my mother'),
                   self.update('T10', {'choice':'doctors'}, 'her doctor is important to her')]
        self.message(text, extraction=self.extraction(updates, discussion=self.proposal(text, purpose='review',
            focus='coverage_paths', reason_quote='her doctor is important to her')))
        out = self.message('She has Medicare Advantage.', [self.update('T05', {'choice':'advantage'}, 'She has Medicare Advantage.')],
            compose=lambda sent: dict(question_target='T06',question=next(c['question']['question'] for c in sent['question_candidates'] if c['id']=='T06')))
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'someone')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T06')
        self.assertEqual(out['coveragePath']['state'], 'undecided')
        self.assertEqual(out['conversationPlanner']['investigations'], [])

    def test_known_familiarity_and_reports_are_not_reasked(self):
        self.choice('RC01', choice='self')
        self.choice('T02', choice='comfortable')
        self.choice('T05', choice='advantage')
        text = 'I want to review costs because the bills concern me.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='review',
            focus='costs', reason_quote='the bills concern me')))
        self.assertNotIn(out['assessment']['nextQuestion']['id'], ['RC01','T02','T05','CP_REASON'])
        self.assertEqual(self.flow.value(self.g, 'knowledge.general'), 'comfortable')

    def test_legacy_inferred_choice_is_not_presented_as_a_decision(self):
        self.flow.put(self.g, 'intent.coveragePath', 'original_medigap', 'user_text')
        self.flow.put(self.g, 'intent.components', {'medigap':'chosen','part_d':'chosen'}, 'user_text')
        self.assertEqual(planner.path(self.flow, self.owner, self.g, self.r)['state'], 'undecided')
        self.assertIsNone(enrollment_flow.context(self.flow,self.g,self.r)['chosen_plan'])
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_medigap')

    def test_reference_to_prices_can_use_the_topic_without_choosing_it(self):
        self.message('Explain Medigap.')
        text = 'Show me those prices.'
        p = self.proposal(text,purpose='investigate',focus='medigap',request_quote=text,investigate=['medigap'])
        out = self.message(text, extraction=self.extraction(discussion=p))
        self.assertEqual(out['conversationPlanner']['investigations'], ['medigap'])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_question_without_punctuation_interrupts_pricing(self):
        self.message('Show me Medigap prices.')
        out = self.message('Why do you need my age')
        self.assertEqual(out['conversationPlanner']['investigations'], [])
        self.assertTrue(out['conversationPlanner']['answer_first'])

    def test_a_reported_preference_can_be_corrected_without_a_path_choice(self):
        self.choice('RC01', choice='self')
        self.choice('T09', choice='predictable')
        text = 'Actually, lower monthly premiums matter more to me.'
        out = self.message(text, [self.update('T09', {'choice':'lower_monthly'}, text, correction=True)])
        self.assertEqual(self.flow.value(self.g, 'needs.costPreference'), 'lower_monthly')
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_factual_guards_still_reject_an_invented_personal_recommendation(self):
        out = self.message('Explain Medigap.', compose={'reply':"I'd choose Medigap for you."})
        self.assertNotIn("I'd choose Medigap", out['reply'])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_adding_part_d_to_original_only_does_not_choose_medigap(self):
        self.turn({'type':'enrollment_decision','path':'original_only'}, aiConsent=False)
        out = self.turn({'type':'enrollment_decision','component':'part_d','value':'chosen'}, aiConsent=False)
        self.assertEqual(out['coveragePath']['path'], 'original')
        self.assertEqual(self.flow.value(self.g, 'intent.components')['medigap'], 'not_needed')

    def test_unsupported_pricing_does_not_keep_collecting_price_details(self):
        self.choice('RC01', choice='self')
        self.choice('MG_AGE', choice='80')
        out = self.message('Show me Medigap prices.')
        self.assertNotIn((out['assessment']['nextQuestion'] or {}).get('id'), ['MG_SEX','MG_TOBACCO','T03'])
        self.assertEqual(out['medigapProfile']['status'], 'unsupported')
        self.assertNotIn('plans_ready', [c['kind'] for c in out.get('cards',[])])

    def test_new_path_choice_does_not_validate_old_inferred_components(self):
        self.flow.put(self.g, 'intent.components', {'medigap':'chosen','part_d':'chosen'}, 'user_text')
        self.turn({'type':'enrollment_decision','path':'original'}, aiConsent=False)
        self.assertIsNone(enrollment_flow.context(self.flow,self.g,self.r)['chosen_plan'])
        out = self.turn({'type':'enrollment_decision','component':'part_d','value':'chosen'}, aiConsent=False)
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'part_d':'chosen'})

    def test_discussion_followup_does_not_repeat_after_a_specific_answer(self):
        self.message('What are the two Medicare paths?')
        out = self.message('Help me understand Original Medicare and its options.')
        self.assertEqual(out['conversationPlanner']['focus'], 'original')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_explicit_parts_a_and_b_only_retains_the_valid_finish(self):
        text = 'I want Parts A and B only.'
        out = self.message(text, extraction=self.extraction(discussion=self.proposal(text, purpose='compare',
            focus='original', decision={'stance':'chosen','path':'original_only','quote':text})))
        self.assertEqual(out['coveragePath']['path'], 'original_only')
        self.assertEqual(enrollment_flow.context(self.flow,self.g,self.r)['chosen_plan'], 'ab_only')
        self.assertEqual(out['conversationPlanner']['investigations'], [])


if __name__ == '__main__':
    unittest.main()
