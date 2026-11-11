"""General learner evidence, privacy and independent concept scopes."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_memory import VisitMemory, CONTEXT_POLICY, HISTORY_TTL
from education import catalog_context
import learner_state as learner


def observation(concept='cost_components', aspects=('premiums',), signal='applied',
                quote='The premium is what I pay every month.'):
    return {'concept_id': concept, 'aspect_ids': list(aspects), 'signal': signal,
            'subject': 'learner', 'quote': quote,
            'interpretation': 'Explains this specific idea in their own words.'}


class LearnerStateTests(unittest.TestCase):
    def test_all_curriculum_concepts_have_outcomes_without_case_routing(self):
        concepts = catalog_context()['concepts']
        self.assertEqual(len(concepts), 17)
        for concept in concepts:
            self.assertTrue(concept['learning_outcome'])
            item = observation(concept['concept_id'], [next(iter(concept['aspects']))])
            self.assertEqual(learner.observations([item], item['quote']), [item])

    def test_known_premiums_and_unclear_deductibles_remain_distinct(self):
        known = observation()
        uncertain = observation(aspects=['deductible'], signal='uncertain',
            quote='I am not sure how a deductible works.')
        record = learner.merge(learner.empty_record(), [known, uncertain])
        self.assertEqual(record['observations'], [known, uncertain])
        clarified = observation(aspects=['deductible'], quote='That is what I pay before coverage pays its share.')
        revised = learner.merge(record, [clarified])
        self.assertEqual(revised['observations'], [known, clarified])
        self.assertEqual(record['observations'], [known, uncertain])

    def test_only_exact_learner_evidence_and_supported_aspects_survive(self):
        good = observation()
        for change in ({'subject': 'beneficiary'}, {'quote': 'Invented words'},
                       {'aspect_ids': ['invented']}, {'concept_id': 'invented'},
                       {'signal': 'mastered'}, {'interpretation': ''}):
            self.assertEqual(learner.observations([{**good, **change}], good['quote']), [])
        self.assertEqual(learner.observations([{}, good], good['quote']), [good])

    def test_memory_is_visit_only_owner_bound_and_expires(self):
        now = [0]
        memory = VisitMemory(clock=lambda: now[0])
        record = learner.merge(learner.empty_record(), [observation()])
        memory.remember('one', 'chain', CONTEXT_POLICY, 'Words', 'Reply', '', learner_record=record)
        self.assertEqual(memory.learner('one', 'chain', CONTEXT_POLICY), record)
        self.assertEqual(memory.learner('two', 'chain', CONTEXT_POLICY), learner.empty_record())
        self.assertEqual(memory.learner('one', 'other', CONTEXT_POLICY), learner.empty_record())
        now[0] += HISTORY_TTL
        self.assertEqual(memory.learner('one', 'chain', CONTEXT_POLICY), learner.empty_record())

    def test_bad_record_cannot_mutate_memory_or_bypass_older_permission(self):
        memory = VisitMemory()
        record = learner.merge(learner.empty_record(), [observation()])
        memory.remember('one', 'chain', CONTEXT_POLICY, 'Words', 'Reply', '', learner_record=record)
        bad = copy.deepcopy(record)
        bad['observations'][0]['signal'] = 'verified'
        with self.assertRaises(ValueError):
            memory.remember('one', 'chain', CONTEXT_POLICY, 'New', 'Reply', '', learner_record=bad)
        self.assertEqual(memory.learner('one', 'chain', CONTEXT_POLICY), record)
        self.assertEqual(memory.learner('one', 'chain', 'natural-context-v2'), learner.empty_record())
