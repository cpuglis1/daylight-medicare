"""Real HTTP restart/recovery over an isolated guest database; no paid AI."""
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


class RecoveryHttpTests(unittest.TestCase):
    def start_service(self):
        self.service = build(0, fixture=True, database=self.database)
        self.thread = threading.Thread(target=self.service.serve_forever, daemon=True)
        self.thread.start()

    def stop_service(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='daylight-recovery-')
        self.database = Path(self.tmp.name)/'profiles.sqlite3'
        self.start_service()
        self.cookie = None
        _, self.session = self.request('/api/guest/session')
        _, self.state = self.request('/api/conversation/initial')
        self.payload = self.action({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'someone'}})
        code, self.state = self.request('/api/conversation/turn', self.payload)
        self.assertEqual(code, 200)

    def tearDown(self):
        self.stop_service()
        self.tmp.cleanup()

    def action(self, action):
        return {'guide': copy.deepcopy(self.state['guide']), 'record': copy.deepcopy(self.state['record']),
            'requestId': str(uuid.uuid4()), 'action': action,
            **({'continuation': self.state['continuation']} if self.state.get('continuation') else {})}

    def request(self, path, body=None, *, origin=None, csrf=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.service.server_port, timeout=10)
        headers = {'Origin': origin or f'http://127.0.0.1:{self.service.server_port}'}
        if self.cookie:
            headers['Cookie'] = self.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'
            if csrf:
                headers['X-Daylight-CSRF'] = self.session['csrf']
        conn.request('POST' if body is not None else 'GET', path,
                     json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        if response.getheader('Set-Cookie'):
            self.cookie = response.getheader('Set-Cookie').split(';')[0]
        code, result = response.status, json.loads(response.read())
        conn.close()
        return code, result

    def test_actual_server_replacement_reconnects_and_next_send_succeeds(self):
        payload = self.action({'type': 'message', 'message': 'She has Original Medicare.'})
        self.stop_service()
        self.start_service()
        code, error = self.request('/api/conversation/turn', payload)
        self.assertEqual(code, 409)
        self.assertEqual(error['recovery'], 'conversation_state')
        code, recovered = self.request('/api/conversation/recover', payload)
        self.assertEqual(code, 200, recovered)
        self.assertEqual(recovered['status'], 'reset')
        self.assertTrue(recovered.get('requestId'))
        self.assertEqual(self.request('/api/conversation/resume', {'requestId': recovered['requestId']})[1]['status'], 'resumed')
        self.state = recovered['response']
        self.assertEqual(self.state['guide']['fields']['subject.role']['value'], 'someone')
        code, out = self.request('/api/conversation/turn', self.action(payload['action']))
        self.assertEqual(code, 200, out)
        self.assertFalse(out['personalRecommendation'])

    def test_completed_request_and_advanced_state_have_distinct_results(self):
        code, completed = self.request('/api/conversation/recover', self.payload)
        self.assertEqual(code, 200)
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['requestId'], self.payload['requestId'])
        self.assertEqual(completed['response']['continuation'], self.state['continuation'])
        stale = self.action({'type': 'message', 'message': 'A draft against the earlier question.'})
        code, current = self.request('/api/conversation/turn', self.action({'type': 'choice', 'id': 'T02', 'fields': {'choice': 'comfortable'}}))
        self.assertEqual(code, 200)
        code, recovered = self.request('/api/conversation/recover', stale)
        self.assertEqual(code, 200)
        self.assertEqual(recovered['status'], 'resumed')
        self.assertEqual(recovered['response']['continuation'], current['continuation'])
        self.assertEqual(self.request('/api/conversation/resume', {'requestId': recovered['requestId']})[1]['response']['continuation'], current['continuation'])

    def test_origin_csrf_and_query_boundaries(self):
        self.assertEqual(self.request('/api/conversation/recover', self.payload, origin='https://example.com')[0], 403)
        self.assertEqual(self.request('/api/conversation/recover', self.payload, csrf=False)[0], 403)
        self.assertEqual(self.request('/api/conversation/recover?private=disallowed', self.payload)[0], 422)
        self.assertEqual(self.request('/api/conversation/recover', {})[0], 422)

    def test_foreign_session_cannot_read_a_completed_reply(self):
        self.cookie = None
        _, self.session = self.request('/api/guest/session')
        code, result = self.request('/api/conversation/recover', self.payload)
        self.assertEqual(code, 200)
        self.assertEqual(result['status'], 'reset')

    def test_reload_restores_trusted_current_state_without_resubmission(self):
        reference = {'requestId': self.payload['requestId']}
        payload = self.action({'type': 'choice', 'id': 'T02', 'fields': {'choice': 'comfortable'}})
        code, latest = self.request('/api/conversation/turn', payload)
        self.assertEqual(code, 200)
        before = len(self.service.adaptive.turn_journal)
        code, resumed = self.request('/api/conversation/resume', reference)
        self.assertEqual(code, 200)
        self.assertEqual(resumed['status'], 'resumed')
        self.assertEqual(resumed['response']['continuation'], latest['continuation'])
        self.assertEqual(resumed['requestId'], payload['requestId'])
        self.assertEqual(resumed['response']['guide']['fields']['knowledge.general']['value'], 'comfortable')
        self.assertFalse(resumed['response']['guide']['preferences']['saveGuide'])
        self.assertFalse(resumed['response']['guide']['preferences']['saveSensitive'])
        self.assertEqual(len(self.service.adaptive.turn_journal), before)
        missing = {'requestId': str(uuid.uuid4()), 'previousRequestId': reference['requestId']}
        self.assertEqual(self.request('/api/conversation/resume', missing)[1]['status'], 'resumed')

    def test_reload_checks_inflight_and_expired_state(self):
        reference = {'requestId': self.payload['requestId']}
        owner = next(iter(self.service.adaptive.current_chain))
        self.service.adaptive.natural_active.add(owner)
        self.assertEqual(self.request('/api/conversation/resume', reference)[1], {'status': 'working'})
        self.service.adaptive.natural_active.remove(owner)
        self.stop_service()
        self.start_service()
        self.assertEqual(self.request('/api/conversation/resume', reference)[1], {'status': 'expired'})

    def test_reload_returns_prior_replies_in_order_after_a_silent_action(self):
        owner = next(iter(self.service.adaptive.current_chain))
        chain = self.state['continuation'].split('.')[0]
        from advisor_memory import CONTEXT_POLICY
        turns = []
        for words, reply in (('I am learning about Medicare.', 'Fictional reply one.'),
                             ('What are the two paths?', 'Fictional reply two.')):
            payload = self.action({'type': 'message', 'message': words})
            payload.update(aiConsent=True, contextPolicy=CONTEXT_POLICY)
            code, self.state = self.request('/api/conversation/turn', payload)
            self.assertEqual(code, 200, self.state)
            # The HTTP fixture bypasses composition. Seed a completed reply
            # and the bounded exchange without an external model request.
            self.service.adaptive.turn_journal[(owner, payload['requestId'])]['response'].update(
                reply=reply, generated={'status': 'complete'})
            self.service.adaptive.memory.remember(owner, chain, CONTEXT_POLICY,
                words, reply, '', request_id=payload['requestId'])
            turns.append((payload['requestId'], words, reply))
        silent = self.action({'type': 'before_enroll_open'})
        code, self.state = self.request('/api/conversation/turn', silent)
        self.assertEqual(code, 200, self.state)
        code, resumed = self.request('/api/conversation/resume', {'requestId': turns[0][0]})
        self.assertEqual(code, 200, resumed)
        self.assertEqual(resumed['requestId'], silent['requestId'])
        self.assertEqual([(turn['requestId'], turn['user'], turn['reply'])
                          for turn in resumed['history'] if turn.get('reply')], turns)
        self.assertTrue(all('guide' not in turn and 'continuation' not in turn for turn in resumed['history']))
        self.service.adaptive.turn_journal[(owner, turns[0][0])]['response']['plansContext'] = {'old_view': True}
        code, resumed = self.request('/api/conversation/resume', {'requestId': turns[0][0]})
        self.assertEqual(code, 200, resumed)
        self.assertNotIn(turns[0][2], json.dumps(resumed['history']))
        self.assertEqual(resumed['history'][0]['notice'], 'This earlier reply used a previous Plans view.')

    def test_free_opening_choices_retain_the_selected_goal_and_next_question(self):
        for choice in ('learn', 'compare', 'review'):
            with self.subTest(choice=choice):
                _, initial = self.request('/api/conversation/initial')
                payload = {'guide': initial['guide'], 'record': initial['record'],
                           'action': {'type': 'choice', 'id': 'T01', 'fields': {'choice': choice}},
                           'requestId': str(uuid.uuid4()), 'aiConsent': False}
                code, result = self.request('/api/conversation/turn', payload)
                self.assertEqual(code, 200, result)
                self.assertEqual(result['openingChoice'], choice)
                self.assertEqual(result['guide']['fields']['intent.goal']['value'], choice)
                self.assertEqual(result['metrics']['llmCalls'], 0)
                self.assertTrue(result['assessment']['nextQuestion']['question'])
                code, resumed = self.request('/api/conversation/resume', {'requestId': payload['requestId']})
                self.assertEqual(code, 200, resumed)
                self.assertEqual([turn.get('openingChoice') for turn in resumed['history']], [choice])

    def test_reload_reference_requires_same_guest_csrf_and_origin(self):
        reference = {'requestId': self.payload['requestId']}
        self.assertEqual(self.request('/api/conversation/resume', reference, csrf=False)[0], 403)
        self.assertEqual(self.request('/api/conversation/resume', reference, origin='https://example.com')[0], 403)
        self.assertEqual(self.request('/api/conversation/resume?token=bad', reference)[0], 422)
        self.assertEqual(self.request('/api/conversation/resume', {**reference, 'guide': self.state['guide']})[0], 422)
        self.cookie = None
        _, self.session = self.request('/api/guest/session')
        self.assertEqual(self.request('/api/conversation/resume', reference)[1], {'status': 'expired'})

    def test_deleted_visit_cannot_resume(self):
        reference = {'requestId': self.payload['requestId']}
        owner = next(iter(self.service.adaptive.current_chain))
        self.service.adaptive.forget_owner(owner)
        self.assertEqual(self.request('/api/conversation/resume', reference)[0], 401)


if __name__ == '__main__':
    unittest.main()
