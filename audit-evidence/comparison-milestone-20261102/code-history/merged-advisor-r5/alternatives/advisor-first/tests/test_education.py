"""Pure curriculum receipts and bounded RAM lifecycle; no model or network."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from education import (CONCEPTS, EVENT_LIMIT, catalog_context, concepts_for_evidence, concepts_for_lesson,
                       empty_record, learning_context, plan_update, validate_record)
from advisor_memory import CONTEXT_POLICY, HISTORY_TTL, VISIT_LIMIT, VisitMemory


def update(concept='coverage_paths', depth='introduced', reason='new', refs=('routesintro',)):
    return {'concept_id': concept, 'depth': depth, 'reason': reason, 'evidence_refs': list(refs)}


def output(*updates, visual='none', purpose='teach'):
    return {'purpose': purpose, 'updates': list(updates), 'visual': visual}


class EducationTests(unittest.TestCase):
    def plan(self, previous=None, value=None, **extra):
        return plan_update(previous, value if value is not None else output(update(), visual='routes'),
                           ('routesintro', 'options', 'parts', 'parta', 'partb', 'costs', 'checks'), **extra)

    def test_catalog_uses_only_retained_evidence_and_no_mandatory_curriculum(self):
        retained = json.loads((ROOT / 'web' / 'teaching-facts.json').read_text())['facts']
        retained += json.loads((ROOT / 'advisor-evidence.json').read_text())['facts']
        fact_ids = {item['id'] for item in retained}
        catalog = catalog_context()
        self.assertEqual(len({item['concept_id'] for item in CONCEPTS}), len(CONCEPTS))
        self.assertEqual(len(CONCEPTS), 17)
        for concept in catalog['concepts']:
            self.assertTrue(set(concept['evidence_refs']) <= fact_ids)
        self.assertTrue(catalog['delivery_is_not_comprehension'])
        self.assertFalse(catalog['required_for_recommendations'])
        catalog['concepts'][0]['title'] = 'External mutation'
        self.assertNotEqual(catalog_context()['concepts'][0]['title'], 'External mutation')

    def test_initial_delivery_is_receipt_not_comprehension(self):
        result = self.plan(event_id='request-1')
        concept = result['record']['concepts']['coverage_paths']
        self.assertEqual(concept, {'depth': 'introduced', 'needs_clarification': False,
                                  'deliveries': 1, 'last_revision': 1,
                                  'evidence_refs': ['routesintro']})
        self.assertEqual(result['visual'], 'routes')
        self.assertEqual(result['record']['revision'], 1)
        self.assertNotIn('understood', json.dumps(result))
        self.assertNotIn('comprehension', result['record'])
        self.assertEqual(validate_record(result['record']), result['record'])

    def test_plan_never_mutates_original_record_or_output(self):
        original = self.plan()['record']
        before = copy.deepcopy(original)
        value = output(update(depth='explored', reason='deepen'), visual='routes')
        value_before = copy.deepcopy(value)
        self.plan(original, value)
        self.assertEqual(original, before)
        self.assertEqual(value, value_before)

    def test_citations_alone_never_check_off_or_show_a_visual(self):
        result = self.plan(value=output(visual='routes', purpose='answer'))
        self.assertEqual(result['record'], empty_record())
        self.assertEqual(result['visual'], 'none')
        self.assertEqual(result['accepted_updates'], [])

    def test_delivered_paths_do_not_claim_every_subtopic(self):
        result = self.plan()
        self.assertEqual(set(result['record']['concepts']), {'coverage_paths'})
        for concept in ('medigap', 'prescription_coverage', 'provider_checks'):
            self.assertNotIn(concept, result['record']['concepts'])

    def test_me_answer_cannot_authorize_a_repeated_intro_or_visual(self):
        before = self.plan()['record']
        repeated = self.plan(before, output(update(), visual='routes'))
        self.assertEqual(repeated['record'], before)
        self.assertEqual(repeated['visual'], 'none')
        self.assertEqual(repeated['accepted_updates'], [])
        self.assertIn('redundant_education_delivery', repeated['issues'])

    def test_model_revisit_claim_cannot_authorize_itself(self):
        before = self.plan()['record']
        value = output(update(reason='requested_revisit'), visual='routes', purpose='recap')
        for extra in ({}, {'requested_revisit': True}, {'revisit_concepts': ['coverage_paths']},
                      {'requested_revisit': True, 'revisit_concepts': ['part_a']}):
            with self.subTest(extra=extra):
                result = self.plan(before, value, **extra)
                self.assertEqual(result['record'], before)
                self.assertEqual(result['visual'], 'none')
                self.assertIn('unrequested_education_revisit', result['issues'])

    def test_explicit_scoped_revisit_can_repeat_without_downgrading_depth(self):
        first = self.plan(value=output(update(depth='explored'), visual='routes'))['record']
        result = self.plan(first, output(update(reason='requested_revisit'), visual='routes'),
                           requested_revisit=True, revisit_concepts=['coverage_paths'])
        concept = result['record']['concepts']['coverage_paths']
        self.assertEqual(concept['depth'], 'explored')
        self.assertEqual(concept['deliveries'], 2)
        self.assertEqual(result['visual'], 'routes')
        self.assertEqual(result['record']['visuals']['routes'], 2)

    def test_depth_can_progress_once_without_blanket_evidence_reuse_ban(self):
        first = self.plan()['record']
        deeper = self.plan(first, output(update(depth='explored', reason='deepen'), visual='routes'))
        self.assertEqual(deeper['record']['concepts']['coverage_paths']['depth'], 'explored')
        self.assertEqual(deeper['record']['concepts']['coverage_paths']['deliveries'], 2)
        self.assertEqual(deeper['visual'], 'none')  # The same broad picture adds nothing.
        repeated = self.plan(deeper['record'], output(update(depth='explored', reason='deepen')))
        self.assertEqual(repeated['record'], deeper['record'])
        self.assertIn('redundant_education_delivery', repeated['issues'])

    def test_new_subtopic_can_use_same_source(self):
        first = self.plan(value=output(update(refs=('options',))))['record']
        result = self.plan(first, output(update('medigap', refs=('options',))))
        self.assertEqual(set(result['record']['concepts']), {'coverage_paths', 'medigap'})
        self.assertEqual(result['record']['concepts']['medigap']['evidence_refs'], ['options'])

    def test_clarification_keeps_highest_depth_and_open_question_separate(self):
        first = self.plan(value=output(update(depth='explored'), visual='routes'))['record']
        unclear = self.plan(first, output(update(depth='needs_clarification', reason='clarify', refs=()),
                                         purpose='clarify'))
        concept = unclear['record']['concepts']['coverage_paths']
        self.assertEqual(concept['depth'], 'explored')
        self.assertTrue(concept['needs_clarification'])
        self.assertEqual(concept['deliveries'], 1)
        explained = self.plan(unclear['record'], output(update(reason='clarify'), visual='routes'))
        concept = explained['record']['concepts']['coverage_paths']
        self.assertEqual(concept['depth'], 'explored')
        self.assertFalse(concept['needs_clarification'])
        self.assertEqual(concept['deliveries'], 2)
        self.assertEqual(explained['visual'], 'routes')

    def test_unexplained_topic_can_have_open_clarification_without_delivery(self):
        result = self.plan(value=output(update('part_a', 'needs_clarification', 'clarify', ())))
        concept = result['record']['concepts']['part_a']
        self.assertEqual(concept['depth'], 'not_covered')
        self.assertEqual(concept['deliveries'], 0)
        self.assertTrue(concept['needs_clarification'])
        self.assertEqual(validate_record(result['record']), result['record'])

    def test_delivery_requires_relevant_already_accepted_evidence(self):
        for item in (update(refs=()), update(refs=('costs',)), update(refs=('not_a_source',))):
            with self.subTest(item=item):
                result = self.plan(value=output(item, visual='routes'))
                self.assertEqual(result['record'], empty_record())
        result = plan_update(None, output(update()), ())
        self.assertEqual(result['record'], empty_record())

    def test_unrelated_visual_cannot_follow_valid_delivery(self):
        result = self.plan(value=output(update(), visual='partb'))
        self.assertEqual(result['visual'], 'none')
        self.assertEqual(result['record']['concepts']['coverage_paths']['deliveries'], 1)
        self.assertNotIn('partb', result['record']['visuals'])

    def test_one_bad_optional_event_does_not_discard_good_event(self):
        result = self.plan(value=output(update('unknown_concept'), update()))
        self.assertEqual(set(result['record']['concepts']), {'coverage_paths'})
        self.assertEqual(len(result['accepted_updates']), 1)
        self.assertIn('invalid_education_update', result['issues'])

    def test_duplicate_updates_only_count_once(self):
        result = self.plan(value=output(update(), update()))
        self.assertEqual(result['record']['concepts']['coverage_paths']['deliveries'], 1)
        self.assertEqual(len(result['accepted_updates']), 1)
        self.assertIn('duplicate_education_update', result['issues'])

    def test_invalid_optional_metadata_fails_soft(self):
        invalid = [None, [], {}, {'purpose': [], 'updates': [], 'visual': 'none'},
                   {'purpose': 'teach', 'updates': [], 'visual': []},
                   output(*[update()] * 5), {**output(), 'raw_message': 'Not allowed'}]
        for value in invalid:
            with self.subTest(value=value):
                result = plan_update(None, value, ('routesintro',))
                self.assertEqual(result['record'], empty_record())
                self.assertEqual(result['visual'], 'none')
                self.assertIn('invalid_education_metadata', result['issues'])
        for field in ('concept_id', 'depth', 'reason', 'evidence_refs'):
            item = update()
            item[field] = []
            result = self.plan(value=output(item))
            self.assertEqual(result['record'], empty_record())

    def test_idempotent_replay_preserves_later_state(self):
        first = self.plan(event_id='request-1')['record']
        second = self.plan(first, output(update('part_a', refs=('parts',))), event_id='request-2')['record']
        result = self.plan(second, event_id='request-1', requested_revisit=True,
                           revisit_concepts=['coverage_paths'])
        self.assertEqual(result['record'], second)
        self.assertEqual(result['visual'], 'none')
        self.assertIn('replayed_education_event', result['issues'])

    def test_event_ids_and_counts_are_bounded(self):
        record = self.plan(event_id='request-0')['record']
        for index in range(EVENT_LIMIT + 2):
            record = self.plan(record, output(update(reason='requested_revisit')),
                               requested_revisit=True, revisit_concepts=['coverage_paths'],
                               event_id='request-' + str(index + 1))['record']
        self.assertEqual(len(record['event_ids']), EVENT_LIMIT)
        self.assertNotIn('request-0', record['event_ids'])
        self.assertEqual(validate_record(record), record)

    def test_model_context_omits_event_ids_raw_text_and_detail_receipts(self):
        record = self.plan(event_id='request-1')['record']
        context = learning_context(record)
        self.assertEqual(context['covered'], [{'concept_id': 'coverage_paths', 'depth': 'introduced',
                                              'needs_clarification': False, 'deliveries': 1}])
        self.assertEqual(context['visuals_shown'], ['routes'])
        self.assertNotIn('event_ids', context)
        self.assertNotIn('evidence_refs', json.dumps(context))
        self.assertNotIn('profile', context)

    def test_explicit_evidence_request_has_finite_public_concept_scope(self):
        self.assertEqual(concepts_for_evidence(['routesintro']), ['coverage_paths', 'medicare_advantage'])
        self.assertEqual(concepts_for_evidence(['unknown', 5]), [])

    def test_explicit_lessons_use_narrow_primary_concepts_not_all_shared_source_concepts(self):
        self.assertEqual(concepts_for_lesson('parts'), ['part_a', 'part_b'])
        self.assertEqual(concepts_for_lesson('options'), ['coverage_paths'])
        self.assertEqual(concepts_for_lesson('routesintro'), ['coverage_paths'])
        self.assertEqual(concepts_for_lesson('checks'), ['research_checks'])
        self.assertEqual(concepts_for_lesson('dates'), ['enrollment_timing'])
        self.assertEqual(concepts_for_lesson('enrollment_intro'), ['enrollment_timing'])
        self.assertNotEqual(concepts_for_lesson('options'), concepts_for_evidence(['options']))
        for invalid in ('unknown', '', None, [], {}):
            self.assertEqual(concepts_for_lesson(invalid), [])

    def test_every_retained_explicit_lesson_has_supported_primary_receipts(self):
        retained = json.loads((ROOT / 'web' / 'teaching-facts.json').read_text())['facts']
        retained += json.loads((ROOT / 'advisor-evidence.json').read_text())['facts']
        catalog = {item['concept_id']: item for item in CONCEPTS}
        for fact in retained:
            with self.subTest(lesson=fact['id']):
                concepts = concepts_for_lesson(fact['id'])
                self.assertTrue(concepts)
                for identifier in concepts:
                    self.assertIn(fact['id'], catalog[identifier]['evidence_refs'])

    def test_server_record_validation_rejects_extra_raw_data(self):
        record = self.plan()['record']
        invalid = copy.deepcopy(record)
        invalid['raw_message'] = 'Private text'
        with self.assertRaises(ValueError):
            validate_record(invalid)
        invalid = copy.deepcopy(record)
        invalid['concepts']['coverage_paths']['understood'] = True
        with self.assertRaises(ValueError):
            validate_record(invalid)
        invalid = copy.deepcopy(record)
        invalid['focus'] = [[]]
        with self.assertRaises(ValueError):
            validate_record(invalid)


class EducationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.memory = VisitMemory(clock=lambda: self.now)
        self.record = plan_update(None, output(update(), visual='routes'), ('routesintro',))['record']

    def remember(self, **changes):
        values = dict(owner='owner', chain='chain', policy=CONTEXT_POLICY,
                      user='Me', reply='Accepted response', question='Current insurance?',
                      education_record=self.record)
        values.update(changes)
        return self.memory.remember(**values)

    def read(self, owner='owner', chain='chain', policy=CONTEXT_POLICY):
        return self.memory.education(owner, chain, policy)

    def test_same_owner_and_chain_lifecycle_as_dialogue(self):
        self.remember()
        self.assertEqual(self.read(), self.record)
        self.assertEqual(self.read(owner='other'), empty_record())
        self.assertEqual(self.read(chain='other'), empty_record())
        self.memory.clear('owner', 'chain')
        self.assertEqual(self.read(), empty_record())
        self.assertEqual(self.memory.recent('owner', 'chain', CONTEXT_POLICY), [])

    def test_old_permission_revokes_education_and_dialogue(self):
        for policy in (None, 'natural-context-v1', 'natural-context-v2', 'unknown'):
            with self.subTest(policy=policy):
                self.remember()
                self.assertEqual(self.read(policy=policy), empty_record())
                self.assertEqual(self.read(), empty_record())
                self.assertEqual(self.memory.recent('owner', 'chain', CONTEXT_POLICY), [])

    def test_ttl_read_never_renews_and_history_eviction_keeps_curriculum(self):
        self.remember()
        for index in range(10):
            self.remember(user=str(index), education_record=None)
        self.assertEqual(self.read(), self.record)
        self.now += HISTORY_TTL - 1
        self.assertEqual(self.read(), self.record)
        self.now += 1
        self.assertEqual(self.read(), empty_record())

    def test_visit_eviction_removes_education_together(self):
        for index in range(VISIT_LIMIT + 1):
            self.remember(chain=str(index))
        self.assertEqual(self.read(chain='0'), empty_record())
        self.assertEqual(self.read(chain=str(VISIT_LIMIT)), self.record)

    def test_failed_validation_never_commits_and_copies_are_isolated(self):
        self.remember()
        before = copy.deepcopy(self.record)
        invalid = dict(self.record, user_text='Disallowed extra personal text')
        with self.assertRaises(ValueError):
            self.remember(user='Bad attempt', education_record=invalid)
        self.assertEqual(self.read(), before)
        self.assertEqual(len(self.memory.recent('owner', 'chain', CONTEXT_POLICY)), 1)
        self.record['focus'].clear()
        self.read()['concepts'].clear()
        self.assertEqual(self.read(), before)

    def test_forget_owner_removes_all_chains_and_preserves_other_owners(self):
        self.remember()
        self.remember(chain='second')
        self.remember(owner='other')
        self.memory.forget_owner('owner')
        self.assertEqual(self.read(), empty_record())
        self.assertEqual(self.read(chain='second'), empty_record())
        self.assertEqual(self.memory.recent('owner', 'chain', CONTEXT_POLICY), [])
        self.assertEqual(self.memory.brief('owner', 'second', CONTEXT_POLICY), {})
        self.assertEqual(self.read(owner='other'), self.record)
        for invalid in (None, [], '', 'x' * 257):
            self.memory.forget_owner(invalid)
        self.assertEqual(self.read(owner='other'), self.record)

    def test_lesson_commit_needs_existing_current_permission_without_fake_exchange(self):
        self.assertFalse(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, self.record))
        self.assertEqual(len(self.memory._visits), 0)
        self.remember(education_record=None)
        before = self.memory.recent('owner', 'chain', CONTEXT_POLICY)
        before_expiry = self.memory._visits[('owner', 'chain')]['expires']
        self.now += 100
        self.assertTrue(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, self.record))
        self.assertEqual(self.read(), self.record)
        self.assertEqual(self.memory.recent('owner', 'chain', CONTEXT_POLICY), before)
        self.assertEqual(self.memory._visits[('owner', 'chain')]['expires'], before_expiry)
        self.now = before_expiry
        self.assertFalse(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, self.record))
        self.assertEqual(self.read(), empty_record())

    def test_old_permission_cannot_commit_a_lesson_and_revokes_existing_entry(self):
        for policy in (None, 'natural-context-v1', 'natural-context-v2'):
            with self.subTest(policy=policy):
                self.remember()
                self.assertFalse(self.memory.commit_education('owner', 'chain', policy, self.record))
                self.assertEqual(self.read(), empty_record())

    def test_lesson_commit_validation_is_atomic_copy_isolated_and_cannot_roll_back(self):
        self.remember(education_record=None)
        malformed = {**self.record, 'raw_text': 'Not allowed'}
        with self.assertRaises(ValueError):
            self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, malformed)
        self.assertEqual(self.read(), empty_record())
        self.assertTrue(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, self.record))
        self.assertTrue(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, self.record))
        self.assertFalse(self.memory.commit_education('owner', 'chain', CONTEXT_POLICY, empty_record()))
        self.record['focus'].clear()
        self.assertEqual(self.read()['focus'], ['coverage_paths'])
        self.assertEqual(len(self.memory.recent('owner', 'chain', CONTEXT_POLICY)), 1)


if __name__ == '__main__':
    unittest.main()
