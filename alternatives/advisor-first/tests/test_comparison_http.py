"""Comparison derivation through the retained owner/CSRF HTTP turn boundary."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
from comparison_evidence import PURPOSES


class ComparisonHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.server = build(0, fixture=True, database=Path(cls.temporary.name)/'comparison.sqlite3')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temporary.cleanup()

    def request(self, path, payload=None, *, csrf=True, cookie=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        if cookie or getattr(self, 'cookie', None):
            headers['Cookie'] = cookie or self.cookie
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            if csrf:
                headers['X-Daylight-CSRF'] = self.session['csrf']
        connection.request('POST' if payload is not None else 'GET', path,
                           json.dumps(payload) if payload is not None else None, headers)
        result = connection.getresponse()
        new_cookie = result.getheader('Set-Cookie')
        if new_cookie:
            self.cookie = new_cookie.split(';')[0]
        body = json.loads(result.read())
        connection.close()
        return result.status, body

    def setUp(self):
        self.cookie = None
        status, self.session = self.request('/api/guest/session')
        self.assertEqual(status, 200)
        status, self.state = self.request('/api/conversation/initial')
        self.assertEqual(status, 200)

    def payload(self, action):
        return {'guide': copy.deepcopy(self.state['guide']), 'record': copy.deepcopy(self.state['record']),
                'requestId': str(uuid.uuid4()), 'action': action,
                **({'continuation': self.state['continuation']} if self.state.get('continuation') else {})}

    def test_owned_turn_exposes_comparison_but_recommendations_stay_held(self):
        status, out = self.request('/api/conversation/turn', self.payload({'type': 'task', 'task': 'compare', 'preparing': True}))
        self.assertEqual(status, 200, out)
        comparison = out['comparison']
        self.assertEqual(len(comparison['decision_record']['question_accounting']), 41)
        self.assertEqual(set(comparison['authority']), set(PURPOSES))
        self.assertTrue(all(v['state'] == 'held' for v in comparison['authority'].values()))
        self.assertIsNone(comparison['binding']['accepted_release_id'])
        self.assertEqual(comparison['universe']['evaluated_count'], 0)
        self.assertFalse(out['personalRecommendation'])
        self.assertNotIn('comparison', out['guide'])
        self.assertNotIn('comparison', out['record'])
        status, value = self.request('/api/recommendations', {'guide': out['guide'], 'record': out['record']})
        self.assertIn(status, {409, 503})
        self.assertIn('held', value['error'])

    def test_existing_csrf_and_forged_authority_boundaries_are_retained(self):
        payload = self.payload({'type': 'start'})
        self.assertEqual(self.request('/api/conversation/turn', payload, csrf=False)[0], 403)
        payload['comparison'] = {'accepted_release_id': 'forged'}
        self.assertEqual(self.request('/api/conversation/turn', payload)[0], 422)

    def test_saved_profile_does_not_gain_derived_comparison_or_trace(self):
        status, out = self.request('/api/conversation/turn', self.payload({'type': 'start'}))
        self.assertEqual(status, 200, out)
        out['guide']['preferences'].update(saveGuide=True, saveSensitive=False)
        status, receipt = self.request('/api/conversation/save', {
            'guide': out['guide'], 'record': out['record'], 'expectedVersion': 0,
            'expectedReadinessVersion': 0, 'operationId': str(uuid.uuid4()),
        })
        self.assertEqual(status, 200, receipt)
        _, saved = self.request('/api/guest/profile')
        _, readiness = self.request('/api/guest/readiness')
        serialized = json.dumps([saved, readiness])
        self.assertNotIn('comparison:', serialized)
        self.assertNotIn('decision_record', serialized)
        self.assertNotIn('comparison_status', serialized)


if __name__ == '__main__':
    unittest.main()
