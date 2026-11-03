"""Curriculum proposal and presentation boundaries, using no provider calls.

These tests validate the controller/model contract, not the model's ability to
infer a person's circumstances or its quality in a live conversation.
"""
import copy
import json
import unittest
import uuid

import test_natural_agent as agent_helpers
from chat import ModelUnavailable
from education import catalog_context, empty_record, learning_context
from natural_agent import COMPOSE_INSTRUCTIONS, _remove_trailing_question_copy


class EducationContractTests(unittest.TestCase):
    setUp = agent_helpers.NaturalAgentTests.setUp
    composition = agent_helpers.NaturalAgentTests.composition
    compose = agent_helpers.NaturalAgentTests.compose
    extraction = agent_helpers.NaturalAgentTests.extraction
    empty_agenda = agent_helpers.NaturalAgentTests.empty_agenda
    update = agent_helpers.NaturalAgentTests.update

    def prepare(self):
        self.moves = [{'id': 'T05', 'question': {'id': 'T05',
            'question': 'What health insurance do you have now?'}}]
        self.context['evidence'] = [copy.deepcopy(self.agent.facts['routesintro'])]
        self.context['education_context'] = {
            'catalog': catalog_context(), 'learning': learning_context(empty_record()),
            'requested_revisit': False, 'revisit_concepts': [], 'turn_kind': 'submitted_answer'}
        self.answer = self.composition(question_target='T05', reply='',
            question='What health insurance do you have now?')

    @staticmethod
    def event(**extra):
        return {'concept_id': 'coverage_paths', 'depth': 'introduced',
            'reason': 'new', 'evidence_refs': ['routesintro'], **extra}

    def teach(self, **extra):
        self.prepare()
        self.answer.update(reply='Original Medicare is the federal program for Parts A and B.',
            evidence_refs=['routesintro'], education={'purpose': 'teach',
                'updates': [self.event()], 'visual': 'routes'}, **extra)

    def test_live_schema_requires_explicit_small_education_contract(self):
        self.prepare()
        self.compose()
        schema = self.calls[-1]['text']['format']['schema']
        self.assertIn('education', schema['required'])
        education = schema['properties']['education']
        self.assertFalse(education['additionalProperties'])
        self.assertEqual(set(education['required']), {'purpose', 'updates', 'visual'})
        update = education['properties']['updates']['items']
        self.assertEqual(update['properties']['concept_id']['enum'],
                         [item['concept_id'] for item in catalog_context()['concepts']])
        self.assertNotIn('understood', update['properties'])
        self.assertNotIn('thoughts', education['properties'])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.calls[-1]['store'])
        self.assertEqual(self.calls[-1]['tools'], [])

    def test_delivery_context_reaches_composer_without_becoming_profile_facts(self):
        self.prepare()
        self.context['education_context']['learning']['covered'] = [
            {'concept_id': 'coverage_paths', 'depth': 'introduced',
             'needs_clarification': False, 'deliveries': 1}]
        original = copy.deepcopy(self.context)
        self.compose()
        sent = json.loads(self.calls[-1]['input'][0]['content'])['resolved_context']
        self.assertEqual(sent['education_context'], original['education_context'])
        self.assertEqual(sent['reports'], original['reports'])
        self.assertEqual(self.context, original)
        self.assertIn('Do not repeat the overview after a routine profile answer', COMPOSE_INSTRUCTIONS)
        self.assertIn('Put a follow-up or invitation to keep learning only in question', COMPOSE_INSTRUCTIONS)

    def test_source_reference_alone_never_proposes_delivery_or_visual(self):
        self.prepare()
        self.answer.update(reply='We can work through that.', evidence_refs=['routesintro'])
        out = self.compose()
        self.assertEqual(out['evidence_refs'], ['routesintro'])
        self.assertEqual(out['education'], {'purpose': 'advance', 'updates': [], 'visual': 'none'})

    def test_grounded_teaching_proposal_survives_for_controller_transition_checks(self):
        self.teach()
        out = self.compose()
        self.assertEqual(out['education'], self.answer['education'])
        self.assertEqual(out['reply'], self.answer['reply'])
        self.assertIs(out['education_metadata_dropped'], False)

    def test_malformed_optional_metadata_preserves_main_question(self):
        for metadata in (None, [], {'purpose': 'teach'},
                         {'purpose': 'advance', 'updates': 'all', 'visual': 'routes'}):
            with self.subTest(metadata=metadata):
                self.prepare()
                self.answer['education'] = metadata
                out = self.compose()
                self.assertEqual(out['question_target'], 'T05')
                self.assertEqual(out['education']['updates'], [])
                self.assertEqual(out['education']['visual'], 'none')
                self.assertIs(out['education_metadata_dropped'], True)

    def test_missing_wire_metadata_is_not_silently_invented_in_production(self):
        self.prepare()
        self.answer.pop('education')
        with self.assertRaisesRegex(ModelUnavailable, 'could not be checked'):
            self.compose()
        self.assertEqual(len(self.calls), 1)

    def test_bad_event_does_not_discard_independent_valid_delivery(self):
        self.teach()
        self.answer['education']['updates'].insert(0, self.event(concept_id='made_up_concept'))
        out = self.compose()
        self.assertEqual(out['education']['updates'], [self.event()])
        self.assertIs(out['education_metadata_dropped'], True)

    def test_mixed_valid_prior_and_invalid_new_metadata_signals_partial_quarantine(self):
        self.teach()
        self.context['education_context']['learning']['covered'] = [
            {'concept_id':'coverage_paths','depth':'introduced',
             'needs_clarification':False,'deliveries':1}]
        self.answer['education']['updates'].append(self.event(concept_id='made_up_new_topic'))
        out = self.compose()
        self.assertEqual(out['reply'], self.answer['reply'])
        self.assertEqual(out['education']['updates'], [self.event()])
        self.assertIs(out['education_metadata_dropped'], True,
            'A rejected new item must not masquerade as an entirely redundant lesson.')

    def test_metadata_drop_flag_is_internal_and_preserved_by_composition_cache(self):
        self.teach()
        self.answer['education']['updates'].append(self.event(concept_id='made_up_new_topic'))
        request_id = str(uuid.uuid4())
        with self.agent.reserve_turn() as reservation:
            first = self.agent.compose('owner', self.context, self.moves, request_id, reservation)
            second = self.agent.compose('owner', self.context, self.moves, request_id, reservation)
        self.assertIs(first['education_metadata_dropped'], True)
        self.assertEqual(second, first)
        self.assertEqual(len(self.calls), 1)
        wire = self.calls[-1]['text']['format']['schema']['properties']
        self.assertNotIn('education_metadata_dropped', wire)
        sent = json.loads(self.calls[-1]['input'][0]['content'])
        self.assertNotIn('education_metadata_dropped', sent['resolved_context'])

    def test_optional_metadata_wrong_scalar_types_never_raise_an_unhandled_error(self):
        bad_values = [None, 0, True, [], {}, ['teach'], {'untrusted':'teach'}]
        for group, key in [('metadata', key) for key in ('purpose','updates','visual')] + [
                ('update', key) for key in ('concept_id','depth','reason','evidence_refs')]:
            for bad in bad_values:
                with self.subTest(group=group, key=key, value=bad):
                    self.teach()
                    if group == 'metadata':
                        self.answer['education'][key] = bad
                    else:
                        self.answer['education']['updates'][0][key] = bad
                    out = self.compose()
                    self.assertEqual(out['reply'], self.answer['reply'])
                    self.assertEqual(out['question_target'], 'T05')
                    self.assertIs(out['education_metadata_dropped'], True)

    def test_event_may_reference_only_main_replys_accepted_evidence(self):
        self.teach()
        self.context['evidence'].append(copy.deepcopy(self.agent.facts['dates']))
        self.answer['education']['updates'] = [self.event(evidence_refs=['dates'])]
        out = self.compose()
        self.assertEqual(out['reply'], self.answer['reply'])
        self.assertEqual(out['education']['updates'], [])
        self.assertEqual(out['education']['visual'], 'none')

    def test_duplicate_metadata_does_not_double_count_same_concept(self):
        self.teach()
        self.answer['education']['updates'].append(self.event())
        self.assertEqual(self.compose()['education']['updates'], [self.event()])

    def test_empty_reply_cannot_deliver_a_lesson_by_metadata_or_visual(self):
        self.teach()
        self.answer['reply'] = ''
        out = self.compose()
        self.assertEqual(out['education']['updates'], [])
        self.assertEqual(out['education']['visual'], 'none')

    def test_expressed_confusion_can_be_recorded_without_fabricating_delivery(self):
        self.prepare()
        update = self.event(depth='needs_clarification', reason='clarify', evidence_refs=[])
        self.answer['education'] = {'purpose': 'clarify', 'updates': [update], 'visual': 'none'}
        self.assertEqual(self.compose()['education']['updates'], [update])

    def test_exact_trailing_intake_question_is_rendered_only_once(self):
        self.prepare()
        for suffix in ('What health insurance do you have now?',
                       'WHAT  health insurance do you have now ?',
                       'What health insurance do you have now.'):
            with self.subTest(suffix=suffix):
                self.answer['reply'] = 'We can take the next step. ' + suffix
                out = self.compose()
                self.assertEqual(out['reply'], 'We can take the next step.')
                self.assertEqual(out['question'], 'What health insurance do you have now?')
        self.answer['reply'] = 'What health insurance do you have now?'
        self.assertEqual(self.compose()['reply'], '')

    def test_duplicate_recovery_follows_canonical_question_recovery(self):
        self.prepare()
        self.answer.update(question='When is your birthday?',
            reply='We can take the next step. What health insurance do you have now?')
        out = self.compose()
        self.assertEqual(out['question'], 'What health insurance do you have now?')
        self.assertEqual(out['reply'], 'We can take the next step.')

    def test_duplicate_recovery_does_not_paraphrase_or_strip_embedded_clauses(self):
        question = 'What health insurance do you have now?'
        for reply in ('Which insurance covers you now?',
                      'I wonder what health insurance do you have now?',
                      'What health insurance do you have now? We can take our time.',
                      'What health insurance do you have now? Anything else?'):
            with self.subTest(reply=reply):
                self.assertEqual(_remove_trailing_question_copy(reply, question), reply)

    def test_semantic_self_reference_is_an_explicit_quoted_report_not_extra_call(self):
        message = 'Turning 65 in November and looking to understand my Medicare options.'
        proposal = self.update('RC01', {'choice': 'self'}, message)
        self.answer = self.extraction([proposal])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', message, self.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual(out['updates'], [proposal])
        self.assertEqual(len(self.calls), 1)
        instructions = self.calls[0]['instructions']
        self.assertIn('my Medicare options', instructions)
        self.assertIn("my mother's Medicare options identifies someone", instructions)
        self.assertIn('hypothetical situations', instructions)

    def test_revisit_can_select_recent_teaching_without_repeating_retrieval_keywords(self):
        message = 'Could you explain the two Medicare paths again?'
        context = {'activeQuestion': {'id': 'T05'}, 'task': 'timing',
            'lastFactIds': ['routesintro'], 'teachingCandidates': ['basics', 'dates', 'checks'],
            'education_context': {'learning': {'focus': ['coverage_paths']}}}
        self.answer = {**self.extraction([]), 'fact_ids': ['routesintro']}
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', message, self.g, context,
                                     str(uuid.uuid4()), reservation)
        self.assertEqual(out['fact_ids'], ['routesintro'])
        sent = self.calls[-1]
        allowed = sent['text']['format']['schema']['properties']['fact_ids']
        self.assertIn('routesintro', allowed['items']['enum'])
        self.assertIn('checks', allowed['items']['enum'])
        self.assertIn('dates', allowed['items']['enum'])
        self.assertLessEqual(len(allowed['items']['enum']), 6)
        self.assertEqual(allowed['maxItems'], 3)
        self.assertEqual(len(self.calls), 1)

    def test_learning_focus_supplies_reviewed_sources_even_without_legacy_fact_marker(self):
        self.agent.local.turn_context = {
            'lastFactIds': [], 'teachingCandidates': ['basics', 'dates', 'checks'],
            'education_context': {'learning': {'focus': ['coverage_paths', 'invented']}}}
        facts = self.agent.retrieve('Could you explain that again?', 'R00')
        identifiers = [item['id'] for item in facts]
        self.assertIn('routesintro', identifiers)
        self.assertIn('checks', identifiers)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(set(identifiers) <= set(self.agent.facts))
        self.assertLessEqual(len(identifiers), 6)

    def test_explicit_topic_retrieval_precedes_continuity_and_stays_bounded(self):
        self.agent.local.turn_context = {
            'lastFactIds': ['routesintro', 'parts', 'original'],
            'teachingCandidates': ['basics', 'dates', 'checks'],
            'education_context': {'learning': {'focus': ['coverage_paths', 'enrollment_timing']}}}
        facts = self.agent.retrieve('What is Part B?', 'R00')
        identifiers = [item['id'] for item in facts]
        self.assertEqual(identifiers[0], 'partb')
        self.assertLess(identifiers.index('routesintro'), identifiers.index('basics'))
        self.assertNotIn('options', identifiers,
            'A focused concept already supported by actual teaching needs no alternate source.')
        self.assertEqual(len(identifiers), 6)
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_focus_does_not_add_an_alternate_source_beside_the_actual_path_overview(self):
        self.agent.local.turn_context = {
            'lastFactIds':['routesintro'], 'teachingCandidates':['basics','dates','checks'],
            'education_context':{'learning':{'focus':['coverage_paths']}}}
        facts = self.agent.retrieve('Could you explain the two Medicare paths again?', 'R00')
        identifiers = [item['id'] for item in facts]
        self.assertEqual(identifiers,['routesintro','basics','dates','checks'])
        self.assertNotIn('options',identifiers)

    def test_explicit_requested_source_wins_over_a_focus_alternate(self):
        self.agent.local.turn_context = {
            'lastFactIds':['original'], 'teachingCandidates':['dates','checks'],
            'education_context':{'learning':{'focus':['medicare_advantage']}}}
        facts = self.agent.retrieve('What is Medicare Advantage?', 'R00')
        identifiers = [item['id'] for item in facts]
        self.assertEqual(identifiers,['advantage','original','dates','checks'])
        self.assertNotIn('options',identifiers)
        self.assertNotIn('routesintro',identifiers)

    def test_focus_keeps_the_exact_source_that_was_actually_delivered(self):
        self.agent.local.turn_context = {
            'lastFactIds':['options'], 'teachingCandidates':['checks'],
            'education_context':{'learning':{'focus':['coverage_paths']}}}
        facts = self.agent.retrieve('Could you explain that again?', 'R00')
        self.assertEqual([item['id'] for item in facts],['options','checks'])

    def test_focus_fallback_adds_only_one_available_primary_source_per_concept(self):
        self.agent.local.turn_context = {
            'lastFactIds':[], 'teachingCandidates':['checks'],
            'education_context':{'learning':{'focus':['coverage_paths','original_medicare']}}}
        facts = self.agent.retrieve('Could you explain that again?', 'R00')
        self.assertEqual([item['id'] for item in facts],['routesintro','original','checks'])
        self.assertNotIn('options',[item['id'] for item in facts])
        self.assertNotIn('parts',[item['id'] for item in facts])

    def interpret(self, message, request, *, updates=(), facts=(), context=None):
        self.answer = {**self.extraction(list(updates)), 'fact_ids':list(facts),
                       'education_request':request}
        with self.agent.reserve_turn() as reservation:
            return self.agent.extract('owner', message, self.g, context or {},
                                      str(uuid.uuid4()), reservation)

    def test_contextually_selected_evidence_does_not_create_an_education_request(self):
        message = 'I have COBRA insurance.'
        none = {'kind':'none','concept_ids':[],'quote':''}
        context = {'activeQuestion':{'id':'T05'}, 'teachingCandidates':['dates']}
        out = self.interpret(message, none, facts=['dates'], context=context,
            updates=[self.update('T05', {'choice':'cobra'}, message)])
        self.assertEqual(out['education_request'], none)
        self.assertEqual(out['fact_ids'], ['dates'])
        self.assertEqual([item['id'] for item in out['updates']], ['T05'])
        spec = self.calls[-1]['text']['format']['schema']
        self.assertIn('education_request', spec['required'])
        request = spec['properties']['education_request']
        self.assertEqual(request['properties']['kind']['enum'], ['none','explain','clarify','revisit'])
        self.assertFalse(request['additionalProperties'])
        self.assertEqual(request['properties']['concept_ids']['maxItems'], 3)
        self.assertEqual(len(self.calls), 1)

    def test_explicit_revisit_is_quoted_and_scoped_independently_of_sources(self):
        message = 'Could you explain the two Medicare paths again?'
        request = {'kind':'revisit','concept_ids':['coverage_paths'],'quote':message}
        context = {'lastFactIds':['routesintro'], 'teachingCandidates':['dates','checks'],
            'education_context':{'learning':{'focus':['coverage_paths']}}}
        out = self.interpret(message, request, facts=['routesintro'], context=context)
        self.assertEqual(out['education_request'], request)
        self.assertEqual(out['rejected_commands'], [])
        self.assertEqual(out['updates'], [])
        self.assertNotIn('comprehension', out)

    def test_demonstrative_revisit_can_use_supplied_focus_without_storing_dialogue(self):
        message = 'Could you explain that again?'
        request = {'kind':'revisit','concept_ids':['coverage_paths'],'quote':message}
        context = {'education_context':{'learning':{'focus':['coverage_paths']}}}
        out = self.interpret(message, request, context=context)
        self.assertEqual(out['education_request'], request)
        self.assertEqual(out['updates'], [])
        sent = json.loads(self.calls[-1]['input'][0]['content'])['confirmed_context']
        self.assertEqual(sent['education_context'], context['education_context'])

    def test_bad_education_requests_are_quarantined_without_losing_personal_report(self):
        message = 'I have COBRA insurance.'
        none = {'kind':'none','concept_ids':[],'quote':''}
        valid = {'kind':'explain','concept_ids':['coverage_paths'],'quote':message}
        cases = [None, [], {'kind':'explain'}, {**valid,'kind':[]},
            {**valid,'kind':'unknown'}, {**valid,'concept_ids':[]},
            {**valid,'concept_ids':['made_up_topic']},
            {**valid,'concept_ids':['coverage_paths','coverage_paths']},
            {**valid,'concept_ids':[{}]}, {**valid,'quote':''},
            {**valid,'quote':'Explain Medicare again'},
            {**valid,'quote':{}}, {**none,'concept_ids':['coverage_paths']},
            {**none,'quote':message}]
        for bad in cases:
            with self.subTest(request=bad):
                out = self.interpret(message, bad,
                    updates=[self.update('T05', {'choice':'cobra'}, message)])
                self.assertEqual(out['education_request'], none)
                self.assertIn('education_request', out['rejected_commands'])
                self.assertEqual([item['id'] for item in out['updates']], ['T05'])

    def test_missing_education_request_is_a_wire_failure_not_an_implicit_permission(self):
        self.answer = self.extraction([])
        self.answer.pop('education_request')
        with self.agent.reserve_turn() as reservation:
            with self.assertRaisesRegex(ModelUnavailable, 'could not be checked'):
                self.agent.extract('owner', 'Tell me about Medicare.', self.g, {},
                                   str(uuid.uuid4()), reservation)


if __name__ == '__main__':
    unittest.main()
