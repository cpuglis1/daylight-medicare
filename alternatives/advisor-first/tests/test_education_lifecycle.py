"""Real HTTP deletion and free lesson continuity with private fictional RAM/DB.

The server runs in fixture mode. These tests neither inherit the existing HTTP
tests nor make model calls; they borrow only its isolated server/request helpers.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_http as support
from advisor_memory import CONTEXT_POLICY
from education import empty_record, plan_update
from guest_profiles import ProfileError


class EducationLifecycleTests(unittest.TestCase):
    setUpClass = classmethod(support.HttpTests.setUpClass.__func__)
    tearDownClass = classmethod(support.HttpTests.tearDownClass.__func__)
    request = support.HttpTests.request
    turn = support.HttpTests.turn

    def setUp(self):
        support.HttpTests.setUp(self)
        self.turn({'type': 'start'})
        self.flow = self.server.adaptive
        self.owner = self.server.profiles.digest(self.cookie.split('=', 1)[1])
        self.chain = self.flow.current_chain[self.owner]

    @staticmethod
    def receipt():
        return plan_update(None, {'purpose': 'teach', 'visual': 'routes', 'updates': [{
            'concept_id': 'coverage_paths', 'depth': 'introduced', 'reason': 'new',
            'evidence_refs': ['routesintro']}]}, ['routesintro'])['record']

    def seed_memory(self, owner=None, chain=None, *, education=True):
        self.flow.memory.remember(owner or self.owner, chain or self.chain, CONTEXT_POLICY,
            'Fictional user context', 'Fictional accepted explanation', '',
            education_record=self.receipt() if education else None)

    def record(self, owner=None, chain=None):
        return self.flow.memory.education(owner or self.owner, chain or self.chain, CONTEXT_POLICY)

    def delete(self, expected=0, **extra):
        return self.request('/api/guest/profile', {'expectedVersion': expected, 'confirmed': True},
                            method='DELETE', **extra)

    def test_successful_authenticated_delete_clears_all_owner_ram_and_revokes_old_authority(self):
        self.seed_memory()
        self.seed_memory(chain='other-chain')
        self.seed_memory(owner='other-owner')
        state = copy.deepcopy(self.state)
        old_owner = self.owner
        self.assertTrue(any(key[0] == old_owner for key in self.flow.turn_journal))
        code, out = self.delete()
        self.assertEqual(code, 200, out)
        self.assertTrue(out['deleted'])
        self.assertEqual(self.record(), empty_record())
        self.assertEqual(self.record(chain='other-chain'), empty_record())
        self.assertEqual(self.record(owner='other-owner'), self.receipt())
        self.assertNotIn(old_owner, self.flow.current_chain)
        self.assertIn(old_owner, self.flow.revoked_owners)
        for collection in (self.flow.turn_journal, self.flow.state_heads, self.flow.clarifications):
            self.assertFalse(any(key[0] == old_owner for key in collection))
        payload = {'guide': state['guide'], 'record': state['record'],
                   'continuation': state['continuation'], 'action': {'type': 'refresh'},
                   'requestId': str(uuid.uuid4())}
        with self.assertRaises(ProfileError) as raised:
            self.flow.turn(old_owner, payload)
        self.assertEqual(raised.exception.code, 401)
        self.assertEqual(self.record(), empty_record())
        with self.server.profiles.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM guests WHERE token_hash=?',
                                        (old_owner,)).fetchone()[0], 0)

    def test_conflicting_delete_retains_dialogue_curriculum_session_and_visit(self):
        self.seed_memory()
        before = copy.deepcopy(self.flow.memory._visits[(self.owner, self.chain)])
        code, out = self.delete(expected=1)
        self.assertEqual(code, 409, out)
        self.assertEqual(self.flow.memory._visits[(self.owner, self.chain)], before)
        self.assertEqual(self.flow.current_chain[self.owner], self.chain)
        self.assertNotIn(self.owner, self.flow.revoked_owners)
        self.assertEqual(self.request('/api/guest/profile')[0], 200)

    def test_inflight_message_prevents_delete_before_database_or_ram_change(self):
        self.seed_memory()
        self.flow.natural_active.add(self.owner)
        try:
            code, out = self.delete()
            self.assertEqual(code, 409, out)
            self.assertEqual(self.record(), self.receipt())
            self.assertEqual(self.request('/api/guest/profile')[0], 200)
            self.assertNotIn(self.owner, self.flow.revoked_owners)
        finally:
            self.flow.natural_active.discard(self.owner)

    def test_unauthenticated_delete_cannot_clear_curriculum(self):
        self.seed_memory()
        code, out = self.delete(csrf=False)
        self.assertEqual(code, 403, out)
        self.assertEqual(self.record(), self.receipt())
        self.assertNotIn(self.owner, self.flow.revoked_owners)

    def test_explicit_free_lesson_records_primary_concept_and_preserves_current_question(self):
        self.seed_memory(education=False)
        before_question = copy.deepcopy(self.state['assessment']['nextQuestion'])
        before_exchanges = self.flow.memory.recent(self.owner, self.chain, CONTEXT_POLICY)
        before_calls = self.flow.agent.calls
        out = self.turn({'type': 'read_concept', 'id': 'checks'})
        self.assertEqual(out['assessment']['nextQuestion'], before_question)
        self.assertEqual([fact['id'] for fact in out['facts']], ['checks'])
        self.assertEqual(set(self.record()['concepts']), {'research_checks'})
        self.assertEqual(self.record()['concepts']['research_checks']['depth'], 'introduced')
        self.assertEqual(self.flow.memory.recent(self.owner, self.chain, CONTEXT_POLICY), before_exchanges)
        self.assertEqual(self.flow.agent.calls, before_calls)
        self.assertNotIn('understood', json.dumps(self.record()))
        self.assertNotIn('research_checks', json.dumps({'guide': out['guide'], 'record': out['record']}))

    def test_repeated_explicit_lesson_is_allowed_and_counts_once_per_distinct_request(self):
        self.seed_memory(education=False)
        self.turn({'type': 'read_concept', 'id': 'routesintro'})
        self.assertEqual(self.record()['concepts']['coverage_paths']['deliveries'], 1)
        self.turn({'type': 'read_concept', 'id': 'routesintro'})
        self.assertEqual(self.record()['concepts']['coverage_paths']['deliveries'], 2)
        self.assertEqual(set(self.record()['concepts']), {'coverage_paths'})

    def test_free_lesson_without_prior_v3_permission_cannot_create_memory_or_consent(self):
        self.assertNotIn((self.owner, self.chain), self.flow.visit_memory)
        out = self.turn({'type': 'read_concept', 'id': 'parts'})
        self.assertEqual([fact['id'] for fact in out['facts']], ['parts'])
        self.assertEqual(self.record(), empty_record())
        self.assertNotIn((self.owner, self.chain), self.flow.visit_memory)
        self.assertNotIn('education', out)

    def test_explicit_parts_lesson_records_both_parts_without_marking_other_sections(self):
        self.seed_memory(education=False)
        self.turn({'type': 'read_concept', 'id': 'parts'})
        self.assertEqual(set(self.record()['concepts']), {'part_a', 'part_b'})
        self.assertTrue(all(item['deliveries'] == 1 for item in self.record()['concepts'].values()))


if __name__ == '__main__':
    unittest.main()
