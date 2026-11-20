"""D161 over real HTTP: what the browser receives, from the first screen on.

Fixture server, synthetic database, no model calls. Added November 12, 2026
after the two-path dashboard failed to reach the page: the first screen's
response did not carry the enrollment view, so opening Plans before any turn
showed the three old tabs. The first test fails without that fix.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
import http.client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
import enrollment_flow


class Surface(unittest.TestCase):
    enable = True

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = build(0, fixture=True, database=Path(cls.tmp.name) / 'private/test.sqlite3')
        if cls.enable:
            enrollment_flow.enable(cls.server.adaptive)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def request(self, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        if getattr(self, 'cookie', None):
            headers['Cookie'] = self.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'
            headers['X-Daylight-CSRF'] = self.session['csrf']
        connection.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse(); raw = response.read(); cookie = response.getheader('Set-Cookie')
        if cookie:
            self.cookie = cookie.split(';')[0]
        connection.close()
        return response.status, json.loads(raw)

    def setUp(self):
        self.cookie = None
        status, self.session = self.request('/api/guest/session')
        self.assertEqual(status, 200)
        status, self.state = self.request('/api/conversation/initial')
        self.assertEqual(status, 200)

    def turn(self, action):
        payload = {'guide': self.state['guide'], 'record': self.state['record'], 'action': action, 'requestId': str(uuid.uuid4())}
        if self.state.get('continuation'):
            payload['continuation'] = self.state['continuation']
        status, out = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 200, out)
        self.state = out
        return out


class FirstScreen(Surface):
    def test_the_first_screen_carries_the_two_path_dashboard_before_any_turn(self):
        view = self.state.get('enrollment')
        self.assertIsNotNone(view, 'the Plans page falls back to three tabs without this')
        self.assertEqual(list(view['dashboard']['paths']), ['original', 'advantage'])
        self.assertEqual([step['id'] for step in view['dashboard']['paths']['original']['steps']], ['ab', 'medigap', 'part_d'])
        self.assertEqual([step['id'] for step in view['dashboard']['paths']['advantage']['steps']], ['ab', 'plan', 'drugs'])
        self.assertIsNone(view['line'])            # nothing reported yet, so no status is asserted

    def test_the_parts_a_and_b_step_is_never_empty_and_every_guide_is_reachable(self):
        # Found on screen November 12, 2026: before a birthday was known the step was a
        # heading and nothing else, and no guide could be opened from anywhere.
        view = self.state['enrollment']
        self.assertIsNone(view['route'])           # no route is asserted for this person yet
        how = view['signup']
        self.assertEqual(how['guides'], ['online_ab', 'add_part_b', 'phone'])
        self.assertEqual(how['statement_ids'], ['signup_routes', 'never_ids'])
        self.assertTrue(all(source['url'].startswith('https://') for source in how['sources']))
        content = enrollment_flow.content()
        self.assertEqual({guide['id'] for guide in content['guides']}, set(how['guides']))

    def test_every_later_response_carries_it_and_tapped_answers_reach_the_status_line(self):
        self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertIn('enrollment', self.state)
        self.turn({'type': 'choice', 'id': 'T05', 'fields': {'choice': 'none'}})
        out = self.turn({'type': 'choice', 'id': 'RC04', 'fields': {'choice': 'a_only'}})
        self.assertTrue(out['enrollment']['line']['text'].startswith('Part A: active · Part B: not yet.'), out['enrollment']['line'])
        self.assertEqual(out['enrollment']['route']['title'], 'How to add Part B')
        self.assertIsNone(out['enrollment']['signup'])   # once there is a route for this person, only that one shows

    def test_a_tapped_decision_is_saved_with_the_profile_and_comes_back(self):
        self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
        out = self.turn({'type': 'enrollment_decision', 'component': 'medigap', 'value': 'not_needed'})
        self.assertEqual(out['enrollment']['dashboard']['paths']['original']['steps'][1]['state'], 'not_needed')
        self.state['guide']['preferences'].update(saveGuide=True, saveSensitive=False)
        payload = {'guide': self.state['guide'], 'record': self.state['record'], 'expectedVersion': 0,
                   'expectedReadinessVersion': 0, 'operationId': str(uuid.uuid4())}
        code, receipt = self.request('/api/conversation/save', payload)
        self.assertEqual(code, 200, receipt)
        _, saved = self.request('/api/guest/profile')
        self.assertEqual(saved['guide']['fields']['intent.components']['value'], {'medigap': 'not_needed'})


class NotEnabled(Surface):
    """:8893, and so :8894: nothing changes until the owner releases it."""
    enable = False

    def test_no_enrollment_view_and_no_decision_action(self):
        self.assertNotIn('enrollment', self.state)
        self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertNotIn('enrollment', self.state)
        payload = {'guide': self.state['guide'], 'record': self.state['record'], 'requestId': str(uuid.uuid4()),
                   'continuation': self.state['continuation'], 'action': {'type': 'enrollment_decision', 'component': 'medigap', 'value': 'chosen'}}
        self.assertEqual(self.request('/api/conversation/turn', payload)[0], 422)


if __name__ == '__main__':
    unittest.main()
