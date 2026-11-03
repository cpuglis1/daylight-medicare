"""Education/profile continuity through the real controller, with no paid calls.

These independently scripted conversations verify the handoff and service gates.
They do not establish that a live model reliably chooses useful teaching depth.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_flow as support
from chat import ModelUnavailable
from education import catalog_context, learning_context
import natural_flow as flow_module
from natural_flow import CONTEXT_POLICY


class CurriculumFlowTests(unittest.TestCase):
    # Borrow just the real-controller/injected-transport harness, not its tests.
    setUp = support.NaturalFlowTests.setUp
    update = staticmethod(support.NaturalFlowTests.update)
    payload = support.NaturalFlowTests.payload
    take = support.NaturalFlowTests.take
    turn = support.NaturalFlowTests.turn
    message = support.NaturalFlowTests.message
    stage_payloads = support.NaturalFlowTests.stage_payloads
    extracted_context = support.NaturalFlowTests.extracted_context
    composed_context = support.NaturalFlowTests.composed_context

    OPENING = 'Turning 65 in november and looking to understand my medicare options'
    OVERVIEW = ('Medicare generally has two coverage paths, Original Medicare and '
                'Medicare Advantage, with different rules and costs.')
    INSURANCE = 'What health insurance do you have now?'
    BENEFICIARY = 'Is this for you, someone you help, or just general research?'

    @staticmethod
    def extraction(updates=(), *, facts=(), situations=(), goal='', education_request=None):
        return {'updates': list(updates), 'requests': [], 'fact_ids': list(facts),
                'agenda': {'concerns': [], 'priorityReason': {}},
                'situation_proposals': list(situations), 'goal_quote': goal,
                'education_request': education_request or {
                    'kind': 'none', 'concept_ids': [], 'quote': ''}}

    @staticmethod
    def request(kind, concept, quote):
        return {'kind': kind, 'concept_ids': [concept], 'quote': quote}

    @staticmethod
    def delivery(concept='coverage_paths', depth='introduced', reason='new',
                 refs=('routesintro',)):
        return {'concept_id': concept, 'depth': depth, 'reason': reason,
                'evidence_refs': list(refs)}

    @staticmethod
    def education(purpose='advance', updates=(), visual='none'):
        return {'purpose': purpose, 'updates': list(updates), 'visual': visual}

    def composition(self, *, target='T05', question=None, reply='', refs=(),
                    education=None):
        if question is None:
            question = self.INSURANCE if target == 'T05' else ''
        return {'question_target': target, 'question': question, 'reply': reply,
                'report_refs': [], 'evidence_refs': list(refs),
                'education_followups': [],
                'agenda_update': {'current_concern': '', 'pause': False},
                'education': education or self.education()}

    def opening(self, *, role_known=False):
        """Retain the observed extra Me step to test that answer's continuation.

        The role-missing branch deliberately simulates the reported extraction
        miss; it is not an assertion that the interpreter should miss My.
        """
        text = self.OPENING
        updates = [self.update('RC01', {'choice': 'self'}, text)] if role_known else []
        birthday = {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'intended',
                    'quote': text, 'uncertain': False, 'correction': False,
                    'month': 11, 'year': None, 'status': '', 'when': ''}
        return self.message(text,
            extraction=self.extraction(updates, facts=['routesintro'], situations=[birthday],
                                       goal='looking to understand my medicare options'),
            compose=self.composition(
                target='T05' if role_known else 'RC01',
                question=self.INSURANCE if role_known else self.BENEFICIARY,
                reply=self.OVERVIEW, refs=['routesintro'],
                education=self.education('teach', [self.delivery()], 'routes')))

    def finite_me(self, composition):
        self.compositions.append(composition)
        return self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})

    def record(self):
        return self.flow.memory.education(
            self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)

    def assert_complete(self, out):
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))

    def test_reported_two_turn_sequence_reuses_citation_without_repeating_visual_or_receipt(self):
        first = self.opening()
        self.assert_complete(first)
        self.assertEqual(first['assessment']['nextQuestion']['id'], 'RC01')
        self.assertEqual(first['advisor']['visual'], 'routes')
        before = copy.deepcopy(self.record())
        self.assertEqual(before['concepts']['coverage_paths']['depth'], 'introduced')
        self.assertEqual(before['concepts']['coverage_paths']['deliveries'], 1)
        bridge = 'Your current insurance helps determine what comes next.'
        second = self.finite_me(self.composition(reply=bridge, refs=['routesintro']))
        self.assert_complete(second)
        self.assertEqual(second['reply'], bridge)
        self.assertEqual(second['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(second['assessment']['nextQuestion']['question'], self.INSURANCE)
        self.assertEqual(second['advisor']['visual'], 'none')
        self.assertTrue(second['advisor']['sources'], 'Citations remain available without teaching again.')
        self.assertEqual(self.record(), before, 'A cited source is not another delivered lesson.')
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
        self.assertNotIn('coverage.current', self.g['fields'])
        recent = self.flow.memory.recent(
            self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)
        self.assertEqual([item['assistant'] for item in recent], [self.OVERVIEW, bridge])
        self.assertEqual([call['text']['format']['name'] for call in self.calls],
            ['daylight_guide_commands', 'daylight_resolved_conversation',
             'daylight_resolved_conversation'])
        sent = self.composed_context()
        self.assertEqual(sent['submitted_answer']['question_id'], 'RC01')
        self.assertEqual(sent['submitted_answer']['fields'], {'choice': 'self'})

    def test_routine_me_answer_cannot_reintroduce_the_same_overview(self):
        self.opening()
        before = copy.deepcopy(self.record())
        out = self.finite_me(self.composition(reply=self.OVERVIEW, refs=['routesintro'],
            education=self.education('teach', [self.delivery()], 'routes')))
        self.assert_complete(out)
        self.assertEqual(out['reply'], '', 'Rejected redundant teaching must not remain as repeated prose.')
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(out['advisor']['sources'], [])
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(out['assessment']['nextQuestion']['question'], self.INSURANCE)
        self.assertEqual(self.record(), before)
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        self.assertFalse(out.get('notice'), 'A routine continuation is not an error recovery.')

    def test_explicit_request_to_explain_again_authorizes_recap_and_visual(self):
        self.opening(role_known=True)
        before = copy.deepcopy(self.record())
        text = 'Could you explain the two Medicare paths again?'
        out = self.message(text, extraction=self.extraction(facts=['routesintro'],
                education_request=self.request('revisit', 'coverage_paths', text)),
            compose=self.composition(target=None, reply=self.OVERVIEW, refs=['routesintro'],
                education=self.education('recap',
                    [self.delivery(reason='requested_revisit')], 'routes')))
        self.assert_complete(out)
        self.assertEqual(out['reply'], self.OVERVIEW)
        self.assertEqual(out['advisor']['visual'], 'routes')
        after = self.record()
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertEqual(after['concepts']['coverage_paths']['deliveries'], 2)
        self.assertEqual(after['visuals']['routes'], 2)
        self.assertEqual(self.flow.memory.brief(
            self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)['pending_question'], 'T05')

    def test_new_layer_can_reuse_evidence_without_repeating_the_paths(self):
        self.opening(role_known=True)
        overview = copy.deepcopy(self.record()['concepts']['coverage_paths'])
        text = 'How do I check whether I can keep my doctor?'
        out = self.message(text, extraction=self.extraction(facts=['checks'],
                education_request=self.request('explain', 'provider_checks', text)),
            compose=self.composition(
                reply='Doctor and hospital participation needs checking for the exact plan.',
                refs=['checks'], education=self.education('teach',
                    [self.delivery('provider_checks', refs=['checks'])])))
        self.assert_complete(out)
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(self.record()['concepts']['coverage_paths'], overview)
        self.assertEqual(self.record()['concepts']['provider_checks']['depth'], 'introduced')
        self.assertNotIn('medicine_checks', self.record()['concepts'],
                         'The shared checks source must not check off every supported concept.')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        text = 'Does seeing a plan on a list mean my doctor participates?'
        out = self.message(text,
            extraction=self.extraction(facts=['checks'],
                education_request=self.request('explain', 'provider_checks', text)),
            compose=self.composition(
                reply='A plan list does not establish doctor participation; the exact plan’s providers still need checking.', refs=['checks'],
                education=self.education('answer', [self.delivery(
                    'provider_checks', 'explored', 'deepen', ['checks'])])))
        self.assert_complete(out)
        self.assertEqual(self.record()['concepts']['provider_checks']['depth'], 'explored')
        self.assertEqual(self.record()['concepts']['provider_checks']['deliveries'], 2)
        self.assertEqual(self.record()['concepts']['coverage_paths'], overview)
        self.assertEqual(self.record()['visuals'], {'routes': 1})

    def test_failed_composition_does_not_advance_education_or_drop_the_question(self):
        self.opening(role_known=True)
        before = copy.deepcopy(self.record())
        text = 'How does prescription coverage fit?'
        out = self.message(text,
            extraction=self.extraction(facts=['drugbasics'],
                education_request=self.request('explain', 'prescription_coverage', text)),
            compose=ModelUnavailable('Synthetic composition failure.'))
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['reply'], '')
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(self.record(), before)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertNotIn('prescription_coverage', self.record()['concepts'])
        self.assertEqual(len(self.calls), 4)

    def test_ordinary_typed_coverage_answer_and_citation_do_not_authorize_revisit(self):
        self.opening(role_known=True)
        before = copy.deepcopy(self.record())
        text = 'I have no health insurance.'
        out = self.message(text,
            extraction=self.extraction(
                [self.update('T05', {'choice': 'none'}, text)], facts=['routesintro']),
            compose=self.composition(target='T04',
                question='When would you like Medicare coverage to start?',
                reply=self.OVERVIEW, refs=['routesintro'],
                education=self.education('recap',
                    [self.delivery(reason='requested_revisit')], 'routes')))
        self.assert_complete(out)
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['none'])
        self.assertEqual(out['reply'], self.OVERVIEW,
                         'The finite-answer guard must not erase an otherwise accepted typed response.')
        self.assertTrue(out['advisor']['sources'])
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(self.record(), before)
        self.assertFalse(self.composed_context()['education_context']['requested_revisit'])
        self.assertEqual(self.composed_context()['education_context']['revisit_concepts'], [])
        self.assertEqual(len(self.calls), 4)

    def test_invalid_optional_new_metadata_does_not_blank_valid_finite_prose(self):
        self.opening()
        before = copy.deepcopy(self.record())
        bridge = 'Your current insurance helps determine what comes next.'
        invalid_new = self.delivery('provider_checks', refs=['not_a_reviewed_source'])
        out = self.finite_me(self.composition(reply=bridge, refs=['routesintro'],
            education=self.education('teach', [self.delivery(), invalid_new], 'routes')))
        self.assert_complete(out)
        self.assertEqual(out['reply'], bridge,
                         'Discarding invalid optional metadata cannot erase useful accepted prose.')
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(self.record(), before)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')

    def test_post_composition_failure_does_not_commit_a_planned_delivery(self):
        self.opening(role_known=True)
        before = copy.deepcopy(self.record())
        actual_move = flow_module.record_advisor_move
        actual_metadata = flow_module.metadata
        after_move = {'ready': False, 'injected': False}

        def record_move(*args, **kwargs):
            result = actual_move(*args, **kwargs)
            after_move['ready'] = True
            return result

        def metadata(*args, **kwargs):
            if after_move['ready'] and not after_move['injected']:
                after_move['injected'] = True
                raise ValueError('Synthetic failure after planning education memory.')
            return actual_metadata(*args, **kwargs)

        text = 'How do I check whether I can keep my doctor?'
        with patch.object(flow_module, 'record_advisor_move', side_effect=record_move), \
                patch.object(flow_module, 'metadata', side_effect=metadata):
            out = self.message(text,
                extraction=self.extraction(facts=['checks'],
                    education_request=self.request('explain', 'provider_checks', text)),
                compose=self.composition(
                    reply='Doctor and hospital participation needs checking for the exact plan.',
                    refs=['checks'], education=self.education('teach',
                        [self.delivery('provider_checks', refs=['checks'])])))
        self.assertTrue(after_move['injected'], 'The fault must happen after composition, not before it.')
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['reply'], '')
        self.assertEqual(out['advisor']['visual'], 'none')
        self.assertEqual(self.record(), before)
        if 'education' in out:
            self.assertEqual(out['education'], learning_context(before),
                             'The response must not expose a planned-but-undelivered learning record.')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(len(self.calls), 4)

    def test_typed_and_finite_turns_both_receive_the_prior_concept_map(self):
        self.opening()
        prior = learning_context(self.record())
        self.finite_me(self.composition())
        finite = self.composed_context()['education_context']
        self.assertEqual(finite['learning'], prior)
        self.assertEqual(finite['catalog'], catalog_context())
        self.assertEqual(finite['turn_kind'], 'submitted_answer')
        self.assertFalse(finite['requested_revisit'])
        self.assertEqual(finite['revisit_concepts'], [])
        self.message('What should I do next?', extraction=self.extraction(),
                     compose=self.composition())
        typed = self.composed_context()['education_context']
        self.assertEqual(typed['learning'], prior)
        self.assertEqual(typed['catalog'], finite['catalog'])
        self.assertEqual(typed['turn_kind'], 'message')
        self.assertEqual(self.extracted_context()['education_context'], {'learning': prior})
        self.assertEqual(len(self.calls), 5, 'No third teaching or planning model call is added.')

    def test_duplicate_question_in_prose_is_removed_while_dedicated_question_is_retained(self):
        self.opening()
        bridge = 'Your current insurance helps determine what comes next.'
        out = self.finite_me(self.composition(reply=bridge + ' ' + self.INSURANCE))
        self.assert_complete(out)
        self.assertEqual(out['reply'], bridge)
        self.assertEqual(out['assessment']['nextQuestion']['question'], self.INSURANCE)
        self.assertNotIn(self.INSURANCE, out['reply'])
        self.assertEqual(out['advisor']['visual'], 'none')

    def test_delivery_record_stays_outside_saved_profile_facts_and_has_no_comprehension_claim(self):
        self.opening(role_known=True)
        self.assertTrue(self.record()['concepts'])
        persisted = json.dumps({'guide': self.g, 'record': self.r})
        for forbidden in ('education-v1', 'coverage_paths', 'delivery_record', 'deliveries',
                          'needs_clarification', 'mastered', 'comprehension'):
            self.assertNotIn(forbidden, persisted)
        self.assertNotIn('knowledge.general', self.g['fields'])
        self.assertEqual(set(self.record()['concepts']), {'coverage_paths'})
        for call in self.calls:
            self.assertIs(call['store'], False)
            self.assertEqual(call['tools'], [])


if __name__ == '__main__':
    unittest.main()
