"""D175: declared fault injection, no live language/model-quality claims."""
import json
import unittest
import test_conversation_contract as contract
import conversation_tasks
from chat import ModelUnavailable
from composition_recovery import normalize_blocks, recovery_display
from conversation_claims import asserted_coverage_text, personal_insurance_assertion, personal_result_assertion
import test_natural_agent as agent_fixture
from advisor_memory import CONTEXT_POLICY


class QuietRecovery(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context', 'interpreted', 'ask', 'reply'):
        locals()[name] = getattr(contract.ConversationContract, name)
    update = staticmethod(contract.ConversationContract.update)
    extraction = staticmethod(contract.ConversationContract.extraction)

    def setUp(self):
        contract.ConversationContract.setUp(self)
        self.flow.agent.composition_recovery = True

    def draft(self, reply, target=None, **extra):
        def compose(sent):
            move = next((m for m in sent['question_candidates'] if m['id'] == target), None)
            if target == 'first':
                move = next(iter(sent['question_candidates']), None)
            return dict(reply=reply, question_target=move['id'] if move else None,
                        question=move['question']['question'] if move else '', **extra)
        return compose

    def test_uncertainty_and_embedded_questions_across_every_task(self):
        self.choice('RC01', choice='self')
        wording = ['Your current coverage is still unknown.',
                   'Your health insurance is not yet confirmed.',
                   'We need to learn whether your coverage is through work.',
                   'We can check if your insurance is through a current job.']
        for task in conversation_tasks.TASKS:
            for reply in wording:
                with self.subTest(task=task, reply=reply):
                    out = self.message('Let us work through the details.',
                        extraction=self.interpreted('Let us work through the details.', task=task),
                        compose=self.draft(reply, 'first'))
                    self.assertEqual(out['reply'], reply)
                    self.assertEqual(out['generated']['status'], 'complete')
                    self.assertNotIn('validation_recovery', out['generated'])
                    self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_real_claims_are_still_blocked_and_valid_question_retained(self):
        self.choice('RC01', choice='self')
        for reply in ['You have employer insurance.', 'Your coverage is through a current job.',
                      'Your coverage is unknown, but you have employer insurance.',
                      'You have employer insurance; we need to check whether it will continue.']:
            with self.subTest(reply=reply):
                # Each fault wording is an independent visit, not permission
                # to repeat an unanswered question beyond the visit allowance.
                self.doCleanups(); self.setUp(); self.choice('RC01',choice='self')
                out = self.message('Continue with the comparison.',
                    extraction=self.interpreted('Continue with the comparison.', task='compare'),
                    compose=self.draft(reply, 'T10'))
                self.assertNotIn(reply, out['reply'])
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'T10')
                self.assertNotIn('notice', out)
                self.assertEqual(out['generated']['answer_state'], 'continued')
                self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_choice_keeps_report_and_continues_quietly_across_tasks(self):
        self.choice('RC01', choice='self')
        for task in conversation_tasks.TASKS:
            with self.subTest(task=task):
                self.doCleanups(); self.setUp(); self.choice('RC01',choice='self')
                self.ask('Help me with this decision.', task=task, target='T09')
                self.compositions.append(self.draft('Your coverage is through a current job.', 'first'))
                out = self.turn({'type':'choice', 'id':'T09', 'fields':{'choice':'predictable'}})
                self.assertEqual(out['metrics']['llmCalls'], 1)
                self.assertEqual(self.flow.value(self.g, 'needs.costPreference'), 'predictable')
                self.assertNotIn('notice', out)
                self.assertIsNotNone(out['assessment']['nextQuestion'])
                self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'T09')
                self.assertNotIn('federal program', out['reply'])
                self.assertNotIn('couldn’t finish', out['reply'])

    def test_unanswered_request_kept_open_while_question_survives(self):
        text = 'What is the total amount I will pay?'
        p = self.interpreted(text, task='costs')
        p['discussion']['question_quote'] = text
        out = self.message(text, extraction=p,
            compose=self.draft('Your premium is $99999.', 'first'))
        self.assertNotIn('99999', out['reply'])
        self.assertEqual(out['generated']['answer_state'], 'unanswered')
        self.assertNotIn('notice', out)
        self.assertIsNotNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_only_whole_independent_blocks_survive(self):
        good = ['We can compare the details that matter for this decision.',
                'The next step depends on what is already in place.']
        out = self.message('Continue with the comparison.',
            extraction=self.interpreted('Continue with the comparison.', task='compare'),
            compose=self.draft('', 'first', reply_blocks=[good[0], 'Your premium is $99999.', good[1]]))
        self.assertEqual(out['reply'], '\n\n'.join(good))
        self.assertEqual(out['generated']['validation_recovery']['component'], 'reply_blocks')
        self.assertNotIn('notice', out)
        self.assertEqual(out['metrics']['llmCalls'], 2)
        self.assertFalse(out.get('cards'))

    def test_partial_answer_does_not_claim_full_delivery(self):
        text = 'What will I pay and how can we compare it?'
        p = self.interpreted(text, task='costs')
        p['discussion']['question_quote'] = text
        out = self.message(text, extraction=p, compose=self.draft('', 'first',
            reply_blocks=['We can compare the details that matter for this decision.', 'Your premium is $99999.']))
        self.assertEqual(out['generated']['answer_state'], 'partial')
        self.assertNotIn('notice', out)
        self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_dropped_teaching_never_marks_a_concept_delivered(self):
        out = self.message('Continue with the comparison.',
            extraction=self.interpreted('Continue with the comparison.', task='compare'),
            compose=self.draft('', 'first', reply_blocks=['We can continue.', 'Your premium is $99999.'],
                evidence_refs=['routesintro'], education={'purpose':'teach', 'visual':'discussion_paths',
                    'updates':[{'concept_id':'coverage_paths', 'depth':'introduced', 'reason':'new',
                        'evidence_refs':['routesintro']}]}))
        self.assertEqual(out['reply'], 'We can continue.')
        self.assertFalse(out.get('cards'))
        ledger = self.flow.memory.education(self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)
        self.assertFalse(ledger.get('concepts', {}).get('coverage_paths', {}).get('deliveries', 0))

    def test_never_split_legacy_prose_or_a_failed_block(self):
        for changes in ({'reply':'Useful first sentence. Your premium is $99999.'},
                        {'reply_blocks':['Useful first sentence. Your premium is $99999.', 'We can continue.']}):
            out = self.message('Continue with the comparison.',
                extraction=self.interpreted('Continue with the comparison.', task='compare'),
                compose=self.draft(changes.get('reply', ''), 'first',
                    **{k:v for k,v in changes.items() if k != 'reply'}))
            self.assertNotIn('Useful first sentence', out['reply'])
            self.assertNotIn('99999', out['reply'])
            self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_wire_schema_uses_blocks_without_changing_call_count(self):
        out = self.message('Continue with the comparison.',
            extraction=self.interpreted('Continue with the comparison.', task='compare'),
            compose=self.draft('', 'first', reply_blocks=['We can continue.']))
        spec = self.calls[-1]['text']['format']['schema']
        self.assertIn('reply_blocks', spec['required'])
        self.assertNotIn('reply', spec['properties'])
        self.assertEqual(out['reply'], 'We can continue.')
        self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_no_question_when_person_pauses(self):
        text = 'Pause the questions for now.'
        out = self.message(text, extraction=self.interpreted(text, mode='pause'),
            compose=dict(reply='Your premium is $99999.', question_target=None, question='',
                agenda_update={'current_concern':'', 'pause':True}))
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('99999', out['reply'])
        self.assertEqual(out['metrics']['llmCalls'], 2)


class RecoveryUnits(unittest.TestCase):
    def test_shape_is_bounded_and_private_marker_cannot_be_injected(self):
        for blocks in ('text', [None], [''], ['x'] * 5):
            with self.subTest(blocks=blocks), self.assertRaises(ModelUnavailable):
                normalize_blocks({'reply_blocks':blocks})
        self.assertNotIn('_reply_blocks', normalize_blocks({'reply':'safe', '_reply_blocks':['invented']}))

    def test_assertions_on_both_sides_of_uncertainty_keep_their_scope(self):
        for text in ('You have employer insurance, but your drug coverage is unknown.',
                     'Your insurance is unknown; you have employer insurance.',
                     'We need to know whether you have drug coverage, but you have employer insurance.',
                     'We need to know whether your coverage is ending, and you have employer insurance.'):
            self.assertTrue(personal_insurance_assertion(asserted_coverage_text(text)), text)

    def test_unanswered_request_is_not_hidden_without_any_usable_question(self):
        out = recovery_display({'discussion_plan':{'answer_first':True}}, None)
        self.assertEqual(out['answer_state'], 'unanswered')
        self.assertIn('reliable answer', out['reply'])

    def test_personal_results_and_questions_are_distinct_across_check_types(self):
        for subject in ('doctor', 'medication', 'care', 'prescription'):
            self.assertTrue(personal_result_assertion(f'Your {subject} is covered.'))
            self.assertTrue(personal_result_assertion(f'Your {subject} is not covered.'))
            self.assertFalse(personal_result_assertion(f'We need to check whether your {subject} is covered.'))
            self.assertFalse(personal_result_assertion(f'Is your {subject} covered?'))


class CoverageSafeguards(unittest.TestCase):
    def setUp(self):
        self.h = agent_fixture.NaturalAgentTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.h.context.update(discussion_plan={'answer_first':False}, current_message='Continue.')
        self.h.context['reports'] = []

    def test_reference_must_resolve_to_matching_reported_coverage(self):
        for status, value in [('reported',['retiree']), ('reported',['none']),
                              ('unknown',['employer']), ('deferred',['employer'])]:
            with self.subTest(status=status, value=value):
                self.h.context['reports'] = [{'id':'guide.coverage.current', 'status':status, 'value':value}]
                self.h.answer = self.h.composition(reply='Your coverage is through a current job.',
                    report_refs=['guide.coverage.current'])
                with self.assertRaises(ModelUnavailable):
                    self.h.compose()
        self.h.context['reports'] = [{'id':'guide.coverage.current', 'status':'reported', 'value':['employer']}]
        self.assertEqual(self.h.compose()['reply'], self.h.answer['reply'])

    def test_helper_and_named_provider_safeguards_remain(self):
        for reply in ["Your insurance through your husband's job gives us a starting point.",
                      'Your doctor is covered by every Medicare Advantage plan.',
                      'Your medications are covered by the plan.']:
            self.h.answer = self.h.composition(reply=reply)
            with self.assertRaises(ModelUnavailable):
                self.h.compose()

    def test_legacy_coverage_validation_is_unchanged(self):
        self.h.context.pop('discussion_plan')
        self.h.answer = self.h.composition(reply='Your current coverage is still unknown.')
        with self.assertRaises(ModelUnavailable):
            self.h.compose()


if __name__ == '__main__':
    unittest.main()
