"""Shared chat/Plans pricing fields through real HTTP and disposable storage."""
import copy
import json
import unittest
import uuid
import test_http as http
import test_medigap_pilot as medigap
from medigap_profile import FIELDS, DATE


class MedigapProfileHttpTests(unittest.TestCase):
    setUpClass = classmethod(medigap.MedigapHttpTests.setUpClass.__func__)
    tearDownClass = classmethod(medigap.MedigapHttpTests.tearDownClass.__func__)
    request = http.HttpTests.request
    setUp = http.HttpTests.setUp
    turn = http.HttpTests.turn

    def seed(self):
        for identifier, fields in [('RC01', {'choice': 'self'}), ('T03', {'zip': '34108'}),
                ('MG_AGE', {'choice': '74'}), ('MG_SEX', {'choice': 'Male'}),
                ('MG_TOBACCO', {'choice': 'Tobacco User'})]:
            self.turn({'type': 'choice', 'id': identifier, 'fields': fields, 'source': 'plans_filter'})

    def save_profile(self, sensitive, version=0):
        self.state['guide']['preferences'].update(saveGuide=True, saveSensitive=sensitive)
        return self.request('/api/conversation/save', {'guide': self.state['guide'], 'record': self.state['record'],
            'expectedVersion': version, 'expectedReadinessVersion': version, 'operationId': str(uuid.uuid4())})

    def test_profile_to_prices_correction_and_sensitive_save_roundtrip(self):
        self.assertEqual(self.state['medigapProfile']['status'], 'missing')
        self.assertIn('RC01', self.state['medigapProfile']['missing'])
        self.seed()
        view = self.state['medigapProfile']
        self.assertEqual(view['status'], 'ready')
        code, rates = self.request('/api/plans/medigap', {**view['inputs'], 'effective_date': DATE})
        self.assertEqual(code, 200);self.assertEqual(rates['profile']['age'], 74)
        self.assertEqual(rates['profile']['zip'], '34108');self.assertEqual(rates['profile']['tobacco'], 'Tobacco User')
        code, receipt = self.save_profile(False)
        self.assertEqual(code, 200, receipt)
        _, saved = self.request('/api/guest/profile');_, ready = self.request('/api/guest/readiness')
        self.assertTrue(set(FIELDS.values()).isdisjoint(saved['guide']['fields']))
        self.assertNotIn('guide.medigap.', json.dumps(ready))
        code, receipt = self.save_profile(True, 1)
        self.assertEqual(code, 200, receipt)
        _, saved = self.request('/api/guest/profile');_, ready = self.request('/api/guest/readiness')
        self.assertEqual(saved['guide']['fields'][FIELDS['MG_SEX']]['value'], 'Male')
        self.assertNotIn('monthly_cents', json.dumps([saved, ready]))
        self.turn({'type': 'choice', 'id': 'MG_AGE', 'fields': {'choice': '75'}, 'source': 'plans_filter'})
        self.assertEqual(self.state['medigapProfile']['status'], 'unsupported')
        self.assertEqual(self.state['medigapProfile']['questions'], [])

    def test_no_silent_defaults_and_stale_visit_cannot_change_answer(self):
        self.seed();old = copy.deepcopy(self.state)
        self.turn({'type': 'choice', 'id': 'MG_TOBACCO', 'fields': {'choice': 'unknown'}, 'source': 'plans_filter'})
        self.assertIsNone(self.state['medigapProfile']['inputs']['tobacco'])
        code, error = self.request('/api/conversation/turn', {
            'guide': old['guide'], 'record': old['record'], 'continuation': old['continuation'],
            'requestId': str(uuid.uuid4()), 'action': {'type': 'choice', 'id': 'MG_SEX', 'fields': {'choice': 'Female'}}})
        self.assertEqual(code, 409)
        for fields in ({'choice': 'female'}, {'choice': 'Male', 'commission': '10'}, {'choice': True}):
            code, error = self.request('/api/conversation/turn', {
                'guide': self.state['guide'], 'record': self.state['record'], 'continuation': self.state['continuation'],
                'requestId': str(uuid.uuid4()), 'action': {'type': 'choice', 'id': 'MG_SEX', 'fields': fields}})
            self.assertEqual(code, 422, error)


if __name__ == '__main__':
    unittest.main()
