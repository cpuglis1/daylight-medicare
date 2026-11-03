"""Adaptive teaching receipts: current clarification and source-scoped depth.

These tests supply independently chosen teaching aspects and expected results.
They establish bounded metadata behavior, not semantic prose or comprehension.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from advisor_memory import CONTEXT_POLICY, HISTORY_TTL, VisitMemory
from education import catalog_context, empty_record, learning_context, plan_update, validate_record


def receipt(concept='cost_components', depth='introduced', reason='new',
            refs=('costs',), aspects=None):
    value = {'concept_id': concept, 'depth': depth, 'reason': reason, 'evidence_refs': list(refs)}
    if aspects is not None:
        value['aspect_ids'] = aspects
    return value


def output(*updates, purpose='teach', visual='none'):
    return {'purpose': purpose, 'updates': list(updates), 'visual': visual}


def deliver(previous=None, update=None, *, visual='none', **kwargs):
    value = update or receipt()
    return plan_update(previous, output(value, visual=visual), value['evidence_refs'], **kwargs)


class AdaptiveEducationTests(unittest.TestCase):
    def test_aspects_are_bounded_parts_of_the_same_reviewed_concepts(self):
        concepts = {item['concept_id']: item for item in catalog_context()['concepts']}
        self.assertEqual(len(concepts), 17)
        self.assertEqual(concepts['cost_components']['aspects'], {
            'premiums': ['costs'], 'deductible': ['costs'],
            'cost_sharing': ['costs'], 'total_cost': ['costs']})
        self.assertEqual(concepts['provider_checks']['aspects'], {
            'original_provider_access': ['original'],
            'plan_specific_participation': ['checks', 'advantage'],
            'unverified_participation': ['checks']})
        facts = json.loads((ROOT / 'web/teaching-facts.json').read_text())['facts']
        facts += json.loads((ROOT / 'advisor-evidence.json').read_text())['facts']
        by_id = {fact['id']: fact for fact in facts}
        for concept in concepts.values():
            self.assertLessEqual(len(concept['aspects']), 4)
            for refs in concept['aspects'].values():
                self.assertTrue(refs)
                self.assertTrue(set(refs) <= set(concept['evidence_refs']) & set(by_id))
        # Independent examples of the actual retained meaning behind these IDs.
        self.assertIn('premium alone is not your total cost', by_id['costs']['text'])
        self.assertIn('doctor participation', by_id['checks']['text'])
        self.assertIn('current employment', by_id['enrollment_intro']['text'])

    def test_distinct_cost_aspects_continue_after_explored_without_claiming_understanding(self):
        record = empty_record()
        for index, aspect in enumerate(('premiums', 'deductible', 'cost_sharing', 'total_cost')):
            result = deliver(record, receipt(depth='introduced' if index == 0 else 'explored',
                reason='new' if index == 0 else 'deepen', aspects=[aspect]), event_id=f'cost:{index}')
            self.assertEqual(len(result['accepted_updates']), 1)
            self.assertEqual(result['issues'], [])
            record = result['record']
        learned = record['concepts']['cost_components']
        self.assertEqual(learned['deliveries'], 4)
        self.assertEqual(learned['depth'], 'explored')
        self.assertEqual(learned['aspects'], ['cost_sharing', 'deductible', 'premiums', 'total_cost'])
        self.assertEqual(record['visuals'], {})
        context = learning_context(record)
        self.assertEqual(context['covered'][0]['aspects'], learned['aspects'])
        self.assertNotIn('evidence_refs', json.dumps(context))
        self.assertNotIn('understood', json.dumps(record))
        self.assertEqual(validate_record(record), record)

    def test_repeated_or_unspecified_deepening_does_not_create_more_receipts(self):
        record = deliver(update=receipt(depth='explored', aspects=['premiums']))['record']
        for aspects in (None, [], ['premiums']):
            with self.subTest(aspects=aspects):
                result = deliver(record, receipt(depth='explored', reason='deepen', aspects=aspects))
                self.assertEqual(result['record'], record)
                self.assertEqual(result['accepted_updates'], [])
                self.assertIn('redundant_education_delivery', result['issues'])

    def test_new_aspect_needs_its_specific_source_not_only_the_concept_source(self):
        unsupported = receipt('coverage_paths', refs=('routesintro',), aspects=['additional_coverage'])
        result = deliver(update=unsupported, visual='routes')
        self.assertEqual(result['record'], empty_record())
        self.assertIn('invalid_education_update', result['issues'])
        supported = receipt('coverage_paths', refs=('options',), aspects=['additional_coverage'])
        result = deliver(update=supported)
        self.assertEqual(result['record']['concepts']['coverage_paths']['aspects'], ['additional_coverage'])
        # Declaring the correct source still does not authorize an unaccepted citation.
        rejected = plan_update(None, output(supported), ['routesintro'])
        self.assertEqual(rejected['record'], empty_record())

    def test_aspect_ids_cannot_create_new_concepts_raw_text_or_unbounded_details(self):
        for aspects in ('premiums', {}, [None], [[]], ['free text about the person'],
                        ['part_b_premium'], ['premiums', 'premiums'],
                        ['premiums', 'deductible', 'cost_sharing', 'total_cost']):
            with self.subTest(aspects=aspects):
                result = deliver(update=receipt(aspects=aspects))
                self.assertEqual(result['record'], empty_record())
                self.assertEqual(result['accepted_updates'], [])
                self.assertIn('invalid_education_update', result['issues'])

    def test_bad_aspect_receipt_does_not_discard_independent_valid_teaching(self):
        value = output(receipt(aspects=['invented']),
                       receipt('part_b', refs=('partb',), aspects=['outpatient_care']))
        result = plan_update(None, value, ['costs', 'partb'])
        self.assertEqual(set(result['record']['concepts']), {'part_b'})
        self.assertEqual(result['record']['concepts']['part_b']['aspects'], ['outpatient_care'])
        self.assertIn('invalid_education_update', result['issues'])

    def test_new_aspect_does_not_replay_a_previously_shown_broad_visual(self):
        first = deliver(update=receipt('coverage_paths', refs=('routesintro',),
            aspects=['public_private_delivery']), visual='routes')['record']
        result = deliver(first, receipt('coverage_paths', depth='explored', reason='deepen',
            refs=('options',), aspects=['additional_coverage']), visual='routes')
        self.assertEqual(len(result['accepted_updates']), 1)
        self.assertEqual(result['visual'], 'none')
        self.assertEqual(result['record']['visuals'], {'routes': 1})
        self.assertEqual(result['record']['concepts']['coverage_paths']['deliveries'], 2)

    def test_current_scoped_clarification_can_explain_immediately_and_repeat_relevant_visual(self):
        first = deliver(update=receipt('coverage_paths', refs=('routesintro',),
            aspects=['public_private_delivery']), visual='routes')['record']
        before = copy.deepcopy(first)
        value = receipt('coverage_paths', depth='explored', reason='clarify',
            refs=('routesintro',), aspects=['public_private_delivery'])
        result = deliver(first, value, visual='routes', clarification_concepts=['coverage_paths'])
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(result['accepted_updates']), 1)
        self.assertEqual(result['visual'], 'routes')
        self.assertEqual(result['record']['visuals'], {'routes': 2})
        self.assertEqual(result['record']['concepts']['coverage_paths']['deliveries'], 2)
        self.assertFalse(result['record']['concepts']['coverage_paths']['needs_clarification'])
        self.assertEqual(first, before, 'Planning a delivery must not commit it.')

    def test_clarify_label_and_recap_permission_do_not_authorize_current_confusion(self):
        first = deliver(update=receipt('coverage_paths', refs=('routesintro',)), visual='routes')['record']
        value = receipt('coverage_paths', reason='clarify', refs=('routesintro',))
        for kwargs in ({}, {'clarification_concepts': ['part_b']},
                       {'requested_revisit': True, 'revisit_concepts': ['coverage_paths']}):
            with self.subTest(kwargs=kwargs):
                result = deliver(first, value, visual='routes', **kwargs)
                self.assertEqual(result['record'], first)
                self.assertEqual(result['visual'], 'none')
                self.assertIn('redundant_education_delivery', result['issues'])

    def test_open_confusion_never_marks_an_aspect_delivered(self):
        result = deliver(update=receipt(depth='needs_clarification', reason='clarify',
                                        aspects=['premiums']))
        self.assertEqual(result['record'], empty_record())
        self.assertIn('invalid_education_update', result['issues'])
        result = deliver(update=receipt(depth='needs_clarification', reason='clarify',
                                        refs=(), aspects=[]))
        concept = result['record']['concepts']['cost_components']
        self.assertEqual(concept['deliveries'], 0)
        self.assertNotIn('aspects', concept)

    def test_legacy_shapes_remain_unchanged_and_can_gain_only_explicit_new_aspects(self):
        first = deliver(update=receipt(depth='explored'))['record']
        self.assertNotIn('aspects', first['concepts']['cost_components'])
        self.assertEqual(validate_record(first), first)
        self.assertNotIn('aspects', learning_context(first)['covered'][0])
        result = deliver(first, receipt(depth='explored', reason='deepen', aspects=['total_cost']))
        self.assertEqual(result['record']['concepts']['cost_components']['aspects'], ['total_cost'])
        self.assertEqual(first['concepts']['cost_components']['deliveries'], 1)

    def test_record_rejects_unsupported_aspects_and_cross_concept_sources(self):
        first = deliver(update=receipt(aspects=['premiums']))['record']
        for patch in ({'aspects': ['made_up']}, {'aspects': ['premiums', 'premiums']},
                      {'aspects': [None]}, {'aspects': {}}, {'evidence_refs': ['parts']},
                      {'aspects': ['premiums'], 'evidence_refs': []}):
            with self.subTest(patch=patch):
                bad = copy.deepcopy(first)
                bad['concepts']['cost_components'].update(patch)
                with self.assertRaises(ValueError):
                    validate_record(bad)

    def test_replay_and_explicit_revisit_preserve_aspect_accounting(self):
        first = deliver(update=receipt(aspects=['premiums']), event_id='first')['record']
        replay = deliver(first, receipt(depth='explored', reason='deepen', aspects=['total_cost']),
                         event_id='first')
        self.assertEqual(replay['record'], first)
        revisit = deliver(first, receipt(reason='requested_revisit', aspects=['premiums']),
                          requested_revisit=True, revisit_concepts=['cost_components'], event_id='again')
        self.assertEqual(revisit['record']['concepts']['cost_components']['aspects'], ['premiums'])
        self.assertEqual(revisit['record']['concepts']['cost_components']['deliveries'], 2)

    def test_planned_new_depth_does_not_commit_on_failure_and_visit_expiry_is_unchanged(self):
        now = [100]
        memory = VisitMemory(clock=lambda: now[0])
        first = deliver(update=receipt(aspects=['premiums']))['record']
        memory.remember('owner', 'visit', CONTEXT_POLICY, 'Fictional question', 'Delivered reply', '',
                        education_record=first)
        pending = deliver(first, receipt(depth='explored', reason='deepen', aspects=['deductible']))
        self.assertEqual(pending['record']['concepts']['cost_components']['deliveries'], 2)
        # Composition/post-processing failed: no remember/commit call follows.
        self.assertEqual(memory.education('owner', 'visit', CONTEXT_POLICY), first)
        self.assertEqual(memory.education('other', 'visit', CONTEXT_POLICY), empty_record())
        now[0] += HISTORY_TTL
        self.assertEqual(memory.education('owner', 'visit', CONTEXT_POLICY), empty_record())


if __name__ == '__main__':
    unittest.main()
