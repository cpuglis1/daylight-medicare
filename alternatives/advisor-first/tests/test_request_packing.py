"""Lossless request-only packing, with fictional inputs and no provider calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from education import catalog_context
from request_packing import compact_context, json_bytes, request_sizes


def expand(value):
    if isinstance(value, dict) and set(value) == {'columns', 'rows'}:
        return [dict(zip(value['columns'], row)) for row in value['rows']]
    return value


class RequestPackingTests(unittest.TestCase):
    def test_complete_catalog_and_learning_roundtrip_in_both_stages(self):
        for key in ('confirmed_context', 'resolved_context'):
            with self.subTest(stage=key):
                original = {key: {'education_context': {
                    'catalog': catalog_context(), 'learning': {'focus': ['coverage_paths'],
                        'covered': [{'concept_id': concept['concept_id'], 'depth': 'introduced',
                            'needs_clarification': True, 'deliveries': 1,
                            'aspects': list(concept['aspects'])} for concept in catalog_context()['concepts']]}},
                    'reports': [{'id': 'keep', 'value': None, 'status': 'unknown'}],
                    'resolved_changes': [{'id': 'keep', 'previous_value': 'old', 'current_value': None}],
                    'recent_exchanges': [{'user': 'I corrected that.', 'assistant': 'A whole exchange.'}],
                    'question_table': {'columns': ['id', 'cannotInfer'],
                        'rows': [[str(i), 'Explicit scoped report only.'] for i in range(41)]},
                    'evidence': [{'id':'held', 'text':'Only if all conditions apply; coverage is unverified.'}]},
                    'question_candidates': [{'id':str(i),'required':False} for i in range(41)]}
                packed = copy.deepcopy(original)
                compact_context(packed)
                self.assertLess(json_bytes(packed), json_bytes(original))
                education = packed[key]['education_context']
                education['catalog']['concepts'] = expand(education['catalog']['concepts'])
                education['learning']['covered'] = expand(education['learning']['covered'])
                self.assertEqual(packed, original)

    def test_sparse_records_preserve_missing_versus_explicit_null(self):
        content = {'resolved_context': {'education_context': {'learning': {'covered': [
            {'concept_id':'a','depth':'introduced'},
            {'concept_id':'b','depth':'introduced','aspects':None}]}}}}
        before = copy.deepcopy(content)
        compact_context(content)
        self.assertEqual(content, before)

    def test_only_exact_unique_current_extractor_duplicates_are_removed(self):
        context = {'safeReports':{'intent.goal':'compare','coverage.current':['cobra'],
                    'knowledge.general':'new','subject.role':'self','extra':'retained'},
            'reports':[{'id':'guide.intent.goal','value':'compare','status':'reported'},
                {'id':'guide.coverage.current','value':['cobra'],'status':'stale'},
                {'id':'guide.knowledge.general','value':'some','status':'reported'},
                {'id':'guide.subject.role','value':'self','status':'reported'},
                {'id':'guide.subject.role','value':'helper','status':'reported'}]}
        content = {'confirmed_context':copy.deepcopy(context), 'resolved_context':copy.deepcopy(context)}
        compact_context(content)
        self.assertEqual(content['confirmed_context']['safeReports'],
            {key:value for key,value in context['safeReports'].items() if key != 'intent.goal'})
        self.assertEqual(content['confirmed_context']['reports'],context['reports'])
        self.assertEqual(content['resolved_context'],context)

    def test_packing_is_idempotent_and_preserves_unknown_context(self):
        content = {'resolved_context': {'education_context':{'catalog':catalog_context()},
                   'future_extension':{'unfamiliar':'retain exactly'}}}
        compact_context(content)
        before = copy.deepcopy(content)
        compact_context(content)
        self.assertEqual(content,before)

    def test_size_diagnostics_have_no_personal_values_and_do_not_mutate(self):
        payload = {'instructions':'PRIVATE-INSTRUCTION-CANARY', 'input':[{'role':'user','content':json.dumps({
            'resolved_context':{'reports':[{'id':'PRIVATE-ID-CANARY','value':'PRIVATE-VALUE-CANARY'}],
                'recent_exchanges':[{'user':'PRIVATE-HISTORY-CANARY'}],
                'unexpected-private-key':'PRIVATE-CANARY'}, 'question_candidates':[]})}],
            'text':{'schema':'PRIVATE-SCHEMA-CANARY'}}
        before = copy.deepcopy(payload)
        metrics = request_sizes(payload)
        self.assertEqual(payload,before)
        self.assertNotIn('PRIVATE',json.dumps(metrics))
        self.assertNotIn('unexpected',json.dumps(metrics))
        self.assertEqual(metrics['payload_bytes'],len(json.dumps(payload).encode()))
        self.assertLess(metrics['zero_history_payload_bytes'],metrics['payload_bytes'])
        self.assertTrue(all(isinstance(value,int) for key,value in metrics.items() if key != 'stage'))

    def test_claude_saves_space_without_losing_teaching_or_candidate_meaning(self):
        blocks = [{'id': 'window', 'label': 'Enrollment window', 'text': 'Coverage has separate start rules.',
                   'evidence_refs': ['timing']},
                  {'id': 'exception', 'label': 'First day', 'text': 'First-of-month birthdays have special rules.',
                   'evidence_refs': ['timing']}]
        candidates = [{'id': 'T05', 'question': {'id': 'T05', 'signature': 'server-only-version',
            'question': 'What coverage do you have now?', 'entity': 'profile',
            'fields': [], 'choices': [['cobra', 'COBRA']], 'multi': False}}]
        active = {'check_id': 'timing', 'report_refs': ['guide.coverage.current'],
                  'next_step': 'Check applicable rules.', 'distinction': 'A report does not verify timing.'}
        inactive = {'check_id': 'cost', 'report_refs': [], 'next_step': 'Look up actual components.',
                    'distinction': 'A partial amount is not a personal total.', 'verification_state': 'not_verified'}
        original = {'resolved_context': {'understanding_guides': [{'capability': 'transition', 'blocks': blocks}],
            'task_work': {'active_checks': [], 'checks': [active, inactive]},
            'education_context': {'catalog': {'concepts': [
                {'concept_id': 'timing', 'aspects': {'window': ['timing'], 'other': ['future']}}]}},
            'evidence': [{'id': 'timing', 'text': 'The window has separate start rules.'}]},
            'question_candidates': candidates}
        packed = copy.deepcopy(original)
        compact_context(packed, claude=True)
        self.assertLess(json_bytes(packed), json_bytes(original))
        context = packed['resolved_context']
        self.assertEqual(expand(context['understanding_guides'][0]['blocks']), blocks)
        self.assertEqual(expand(context['task_work']['checks']), [active, inactive])
        self.assertEqual(context['education_context']['catalog']['concepts'],
                         [{'concept_id': 'timing', 'aspects': {'window': ['timing']}}])
        choice = packed['question_candidates'][0]
        self.assertEqual(choice['id'], 'T05')
        self.assertEqual(choice['question']['question'], candidates[0]['question']['question'])
        self.assertEqual(choice['question']['choices'], candidates[0]['question']['choices'])
        self.assertNotIn('signature', choice['question'])


if __name__ == '__main__':
    unittest.main()
