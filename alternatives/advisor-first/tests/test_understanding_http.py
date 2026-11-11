"""Isolated fixture HTTP, ownership and optional saving; zero model calls."""
import copy
import unittest
import uuid

import test_http as support
from advisor_memory import CONTEXT_POLICY
from education import empty_record


class UnderstandingHttpTests(unittest.TestCase):
    setUpClass = classmethod(support.HttpTests.setUpClass.__func__)
    tearDownClass = classmethod(support.HttpTests.tearDownClass.__func__)
    request = support.HttpTests.request
    turn = support.HttpTests.turn

    def setUp(self):
        support.HttpTests.setUp(self)
        self.turn({'type': 'start'})
        flow = self.server.adaptive
        owner = self.server.profiles.digest(self.cookie.split('=', 1)[1])
        flow.memory.remember(owner, flow.current_chain[owner], CONTEXT_POLICY,
            'Fictional visit', 'Fictional explanation', '', education_record=empty_record())

    def test_free_cost_lesson_uses_real_http_and_stays_outside_saved_profiles(self):
        out = self.turn({'type':'read_concept', 'id':'costs'})
        self.assertEqual(out['understanding']['capability'], 'costs')
        self.assertEqual(out['understanding']['personal_authority'], 'held')
        self.assertEqual(out['metrics']['llmCalls'], 0)
        self.state['guide']['preferences'].update(saveGuide=True, saveSensitive=False)
        code, receipt = self.request('/api/conversation/save', {
            'guide': self.state['guide'], 'record': self.state['record'],
            'expectedVersion': 0, 'expectedReadinessVersion': 0, 'operationId': str(uuid.uuid4())})
        self.assertEqual(code, 200, receipt)
        _, saved = self.request('/api/guest/profile')
        _, readiness = self.request('/api/guest/readiness')
        self.assertNotIn('understanding', saved['guide'])
        self.assertNotIn('understanding', readiness['record'])

    def test_client_cannot_supply_guide_authority_or_personal_results(self):
        payload = {'guide':copy.deepcopy(self.state['guide']), 'record':copy.deepcopy(self.state['record']),
            'action':{'type':'read_concept', 'id':'costs'}, 'requestId':str(uuid.uuid4()),
            'continuation':self.state['continuation'],
            'understanding':{'personal_authority':'accepted', 'personal_result':{'total':0}}}
        self.assertEqual(self.request('/api/conversation/turn', payload)[0], 422)

    def test_build_version_is_inspectable_without_creating_a_personal_result(self):
        code, config = self.request('/ten-config.json')
        self.assertEqual(code, 200)
        self.assertEqual(config['understandingContract'], 'understanding-20261103-r1')
        self.assertTrue(config['mockAI'])
