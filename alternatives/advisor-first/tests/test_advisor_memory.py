"""Bounded visit-only context contracts; no network, model or profile store."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_memory import (CONTEXT_POLICY, HISTORY_LIMIT, HISTORY_TTL,
                            VISIT_LIMIT, VisitMemory)


class VisitMemoryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.memory = VisitMemory(clock=lambda: self.now)

    def remember(self, **changes):
        values = dict(owner='owner', chain='chain', policy=CONTEXT_POLICY,
                      user='My question', reply='An explanation', question='',
                      candidate_ids=('T05', 'RC11'))
        values.update(changes)
        return self.memory.remember(**values)

    def recent(self, owner='owner', chain='chain', policy=CONTEXT_POLICY):
        return self.memory.recent(owner, chain, policy)

    def brief(self, owner='owner', chain='chain', policy=CONTEXT_POLICY):
        return self.memory.brief(owner, chain, policy)

    def test_cross_topic_side_answer_preserves_goal_and_return_point(self):
        self.remember(question='What insurance do you have?', question_target='T05',
                      goal='Understand my options and prepare to enroll',
                      agenda_update={'current_concern': 'enrollment timing', 'pause': False})
        self.remember(user='What is Part B?', reply='A reviewed explanation',
                      agenda_update={'current_concern': 'Part B'})
        self.assertEqual([x['user'] for x in self.recent()],
                         ['My question', 'What is Part B?'])
        self.assertEqual(self.brief(), {
            'goal': 'Understand my options and prepare to enroll',
            'current_concern': 'Part B', 'pending_question': 'T05', 'paused': False})
        self.remember(question_target='', agenda_update={'pause': True})
        self.assertEqual(self.brief()['pending_question'], 'T05')
        self.assertTrue(self.brief()['paused'])
        self.remember(question_target='RC11', agenda_update={'pause': False})
        self.assertEqual(self.brief()['pending_question'], 'RC11')

    def test_owner_chain_isolation_and_exact_text(self):
        self.remember(user='  I said "November".\n', reply='First', question='Which year?')
        self.remember(owner='other', reply='Another owner')
        self.remember(chain='other-chain', reply='Another visit')
        self.assertEqual(self.recent(), [{'user': '  I said "November".\n',
                                         'assistant': 'First', 'question': 'Which year?'}])
        self.assertEqual(self.recent(owner='unknown'), [])
        self.memory.clear('owner', 'chain')
        self.assertEqual(self.recent(), [])
        self.assertEqual(self.recent(owner='other')[0]['assistant'], 'Another owner')
        self.assertEqual(self.recent(chain='other-chain')[0]['assistant'], 'Another visit')

    def test_older_permissions_cannot_read_or_extend_cross_topic_memory(self):
        for policy in (None, 'natural-context-v1', 'natural-context-v2', 'unknown'):
            with self.subTest(policy=policy):
                self.remember(goal='My explicit goal', question_target='T05')
                self.assertEqual(self.recent(policy=policy), [])
                self.assertEqual(self.brief(), {})
                self.assertFalse(self.remember(policy=policy, goal='Not authorized'))
                self.assertEqual(self.recent(), [])
                self.remember(question_target='T05')
                self.assertEqual(self.brief(policy=policy), {})
                self.assertEqual(self.recent(), [])

    def test_ttl_expires_without_read_renewal(self):
        self.remember(goal='My goal')
        self.now += HISTORY_TTL - 1
        self.assertTrue(self.recent())
        self.now += 1
        self.assertEqual(self.recent(), [])
        self.assertEqual(self.brief(), {})

    def test_new_exchange_renews_ttl(self):
        self.remember()
        self.now += HISTORY_TTL - 1
        self.remember(user='Another question')
        self.now += 2
        self.assertEqual(len(self.recent()), 2)

    def test_chronological_six_exchange_limit_with_brief_surviving_eviction(self):
        self.remember(user='0', goal='Explicit goal', question_target='T05')
        for index in range(1, 9):
            self.remember(user=str(index))
        self.assertEqual([x['user'] for x in self.recent()], list(map(str, range(3, 9))))
        self.assertEqual(self.brief()['goal'], 'Explicit goal')
        self.assertEqual(self.brief()['pending_question'], 'T05')

    def test_total_character_bound_preserves_complete_exchanges(self):
        for index in range(6):
            self.remember(user=str(index) * 1200, reply='r' * 200)
        exchanges = self.recent()
        self.assertLessEqual(sum(len(v) for item in exchanges for v in item.values()), HISTORY_LIMIT)
        self.assertEqual(len(exchanges), 3)
        self.assertEqual(exchanges[0]['user'], '3' * 1200)

    def test_oversize_exchange_is_omitted_without_clipping_or_losing_brief(self):
        self.remember(user='Earlier complete message')
        self.remember(user='x' * (HISTORY_LIMIT + 1), goal='Updated explicit goal',
                      question_target='RC11', agenda_update={'current_concern': 'Timing'})
        self.assertEqual(len(self.recent()), 1)
        self.assertEqual(self.recent()[0]['user'], 'Earlier complete message')
        self.assertEqual(self.brief()['goal'], 'Updated explicit goal')
        self.assertEqual(self.brief()['pending_question'], 'RC11')

    def test_invalid_mutations_are_atomic(self):
        self.remember(goal='Original goal', question_target='T05')
        before_history, before_brief = self.recent(), self.brief()
        invalid = [
            {'question_target': 'RC11', 'candidate_ids': ('T05',)},
            {'question_target': 'not-a-question', 'candidate_ids': ('not-a-question',)},
            {'agenda_update': {'goal': 'Unvalidated goal'}},
            {'agenda_update': {'pending_question': 'RC11'}},
            {'agenda_update': {'current_concern': 'x' * 161}},
            {'agenda_update': {'pause': 1}},
            {'goal': 'x' * 201}, {'user': 'x' * 8001},
            {'reply': None}, {'question': 'x' * 2001},
            {'candidate_ids': 'T05'}, {'owner': None}, {'chain': None},
        ]
        for changes in invalid:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError):
                    self.remember(**changes)
                self.assertEqual(self.recent(), before_history)
                self.assertEqual(self.brief(), before_brief)

    def test_explicit_clear_and_copy_isolation(self):
        update = {'current_concern': 'Part B', 'pause': True}
        self.remember(goal='Explicit goal', agenda_update=update)
        update['current_concern'] = 'Mutated outside memory'
        self.brief()['goal'] = 'Changed returned value'
        self.recent()[0]['user'] = 'Changed returned history'
        self.assertEqual(self.brief()['goal'], 'Explicit goal')
        self.assertEqual(self.brief()['current_concern'], 'Part B')
        self.assertEqual(self.recent()[0]['user'], 'My question')
        self.remember(goal='', agenda_update={'current_concern': None, 'pause': False})
        self.assertEqual(self.brief(), {'paused': False})

    def test_visit_count_bound_evicts_oldest_updated_visit(self):
        for index in range(VISIT_LIMIT):
            self.remember(chain=str(index))
        self.remember(chain='0', user='Renewed visit')
        self.remember(chain='new')
        self.assertEqual(self.recent(chain='1'), [])
        self.assertEqual(self.recent(chain='0')[-1]['user'], 'Renewed visit')
        self.assertEqual(len(self.memory._visits), VISIT_LIMIT)

    def test_missing_visit_reads_are_empty(self):
        self.assertEqual(self.recent(chain=None), [])
        self.assertEqual(self.brief(owner=None), {})
        self.memory.clear(None, None)


if __name__ == '__main__':
    unittest.main()
