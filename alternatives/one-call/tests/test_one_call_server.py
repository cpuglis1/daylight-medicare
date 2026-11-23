"""The 8897 server: built offline, protected ports refused, one scripted turn over loopback HTTP.

No database, no model, no outside network: sockets may connect to 127.0.0.1
only, and the server is bound to 127.0.0.1 on a free port. The live start
(model key, budget ledger, display database) is not exercised by any test.
"""
import http.client
import json
import logging
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat import ResponsesClient
from log_guard import ContentFreeFilter
from natural_flow import CONTEXT_POLICY, NaturalConversation
import conversation_planner
import conversation_records

import _one_call_support as support
from _one_call_support import Script, call, message, reply, save, update
import one_call_flow
import one_call_server
from one_call_flow import OneCallConversation

LOOPBACK = '127.0.0.1'


class FictionalStore:
    """Stands where a display repository would. Any read fails loudly; none is expected."""

    def query(self, *args, **kwargs):
        raise RuntimeError('fictional store: no rows')


def loopback_only(test):
    """Sockets may reach 127.0.0.1 and nothing else."""
    real = {'create_connection': socket.create_connection, 'getaddrinfo': socket.getaddrinfo,
            'connect': socket.socket.connect, 'connect_ex': socket.socket.connect_ex}

    def host_of(address):
        return address[0] if isinstance(address, tuple) else address

    def create_connection(address, *args, **kwargs):
        if host_of(address) != LOOPBACK:
            raise AssertionError('Only loopback connections are allowed in this test')
        return real['create_connection'](address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        if host != LOOPBACK:
            raise AssertionError('Only loopback lookups are allowed in this test')
        return real['getaddrinfo'](host, *args, **kwargs)

    def connect(sock, address):
        if host_of(address) != LOOPBACK:
            raise AssertionError('Only loopback connections are allowed in this test')
        return real['connect'](sock, address)

    def connect_ex(sock, address):
        if host_of(address) != LOOPBACK:
            raise AssertionError('Only loopback connections are allowed in this test')
        return real['connect_ex'](sock, address)

    for owner, name, guard in ((socket, 'create_connection', create_connection), (socket, 'getaddrinfo', getaddrinfo),
                               (socket.socket, 'connect', connect), (socket.socket, 'connect_ex', connect_ex)):
        item = patch.object(owner, name, guard)
        item.start()
        test.addCleanup(item.stop)


class Refusals(unittest.TestCase):
    def test_protected_and_advisor_ports_are_refused(self):
        for port in (8890, 8891, 8893, 8894, 8895, 8896):
            with self.assertRaises(ValueError):
                one_call_server.build_one_call(port, fixture=True)
        self.assertEqual(one_call_server.PORT, 8897)
        self.assertNotIn(one_call_server.PORT, one_call_server.REFUSED_PORTS)

    def test_an_injected_client_needs_the_fixture_mode(self):
        client = ResponsesClient(key='synthetic', model='gpt-5.4', transport=Script())
        with self.assertRaises(ValueError):
            one_call_server.build_one_call(0, client=client)

    def test_the_surface_label_is_not_an_accepted_pilot_knowledge_surface(self):
        import pilot_knowledge
        self.assertNotIn(one_call_server.SURFACE, pilot_knowledge.HOLD_SURFACES)


@unittest.skipUnless(support.READY, support.NOT_READY)
class ServerCase(unittest.TestCase):
    def setUp(self):
        loopback_only(self)
        support.pin_today(self)

    def build(self, **options):
        service = one_call_server.build_one_call(0, fixture=True, **options)
        self.addCleanup(one_call_server.close, service)
        return service

    def serve(self, service):
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(service.shutdown)
        return service.server_port

    def request(self, port, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(LOOPBACK, port, timeout=30)
        sent = {'Host': '%s:%d' % (LOOPBACK, port), **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            sent.update({'Content-Type': 'application/json', 'Origin': 'http://%s:%d' % (LOOPBACK, port)})
        try:
            connection.request(method, path, body=data, headers=sent)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def session(self, port):
        status, headers, raw = self.request(port, 'GET', '/api/guest/session')
        self.assertEqual(status, 200)
        auth = {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-Daylight-CSRF': json.loads(raw)['csrf']}
        status, _, raw = self.request(port, 'GET', '/api/conversation/initial', headers=auth)
        self.assertEqual(status, 200)
        return auth, json.loads(raw)

    def turn(self, port, auth, state, action, *, consent, policy):
        payload = {'guide': state['guide'], 'record': state['record'], 'action': action,
                   'requestId': str(uuid.uuid4()), 'aiConsent': consent, 'contextPolicy': policy}
        if state.get('continuation'):
            payload['continuation'] = state['continuation']
        status, _, raw = self.request(port, 'POST', '/api/conversation/turn', payload, auth)
        return status, json.loads(raw)


class OfflineFixture(ServerCase):
    def test_builds_with_no_database_no_model_and_no_network(self):
        service = self.build()
        flow = service.adaptive
        self.assertIs(type(flow), OneCallConversation)
        self.assertEqual(service.server_address[0], LOOPBACK)
        self.assertTrue(flow.fixture)
        # The switches the :8895 demo turns on.
        self.assertTrue(conversation_planner.enabled(flow) and conversation_records.enabled(flow))
        self.assertTrue(conversation_records.pending_on(flow) and conversation_records.fixes_on(flow))
        self.assertTrue(flow.guided_close and flow.composed_opening and flow.d161 and flow.plans_fixes)
        self.assertIsNotNone(flow.turn_progress)
        # State the subclass adds is initialised on the adopted object.
        self.assertEqual(flow.one_call_request_bytes, one_call_flow.ONE_CALL_REQUEST_BYTES)
        self.assertEqual(flow.one_call_visits.turns('nobody', 'nowhere'), 0)
        self.assertIs(flow.reconciler.flow, flow)
        self.assertIsNone(flow.conversation_checks)
        # No display stores were given, so the engine hook and the closing price read stay off.
        self.assertIsNone(flow.one_call_recommendation)
        self.assertFalse(hasattr(flow, 'closing_price_read'))
        # Pilot knowledge keeps whatever the flow's own configuration yields: no accepted surface here.
        self.assertIsNone(flow.pilot_knowledge.surface)
        for name in one_call_flow.LOGGERS:
            self.assertTrue(any(isinstance(item, ContentFreeFilter) for item in logging.getLogger(name).filters), name)

    def test_the_two_call_wiring_builds_the_same_way_for_comparison(self):
        service = self.build(one_call=False)
        self.assertIs(type(service.adaptive), NaturalConversation)
        self.assertTrue(service.adaptive.guided_close and conversation_records.enabled(service.adaptive))

    def test_a_typed_message_in_synthetic_mode_gets_the_fallback_over_http(self):
        port = self.serve(self.build())
        auth, state = self.session(port)
        status, out = self.turn(port, auth, state, {'type': 'start'}, consent=False, policy=None)
        self.assertEqual(status, 200)
        status, out = self.turn(port, auth, out, {'type': 'message', 'message': 'Hello, this is for me.'},
                                consent=True, policy=CONTEXT_POLICY)
        self.assertEqual(status, 200)
        self.assertEqual(out['generated']['code'], 'synthetic_fixture')
        self.assertTrue(out['metrics']['synthetic'])
        self.assertTrue(conversation_planner.valid_delivered_next(out))

    def test_one_scripted_turn_over_http_with_the_engine_hook_wired(self):
        script = Script()
        service = self.build(client=ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=script),
                             medigap_repository=FictionalStore(), part_d_repository=FictionalStore(), reconcile=False)
        flow = service.adaptive
        self.assertFalse(flow.fixture)
        self.assertTrue(callable(flow.one_call_recommendation))
        self.assertTrue(hasattr(flow, 'closing_price_read'))
        budget = support.temporary_ledger(self, flow.agent)
        port = self.serve(service)

        status, _, raw = self.request(port, 'GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'/advisor.js', raw)                              # the same interface files as :8895
        auth, state = self.session(port)
        status, _, raw = self.request(port, 'GET', '/api/status', headers=auth)
        info = json.loads(raw)
        self.assertEqual(info['one_call'], {'loop': 'one-call', 'request_bytes': 400000, 'reconcile': False,
                                            'discovery': 'permission_before_profile',
                                            'recommendation_engine': True, 'reasoning_effort': 'low',
                                            'turn_trace': False, 'live_runs': 'owner_only'})
        self.assertEqual(info['local_demo']['surface'], one_call_server.SURFACE)
        self.assertFalse(info['local_demo']['block_release'])
        self.assertTrue(info['local_demo']['discussion_planner'] and info['local_demo']['guided_close'])
        self.assertFalse(info['pilotKnowledge'].get('enabled'))

        status, out = self.turn(port, auth, state, {'type': 'start'}, consent=False, policy=None)
        self.assertEqual(status, 200)
        text = 'This coverage is for me. Please help me check which parts of Medicare I have.'
        script.add([save(update('RC01', {'choice': 'self'}, 'This coverage is for me')), call('c2', 'get_plan_status', {})],
                   [message(reply('Thank you, I have noted that.', question='Do you have any part of Medicare yet?',
                                  target='RC04', detail_step='requested_work'))])
        status, out = self.turn(port, auth, out, {'type': 'message', 'message': text}, consent=True, policy=CONTEXT_POLICY)
        self.assertEqual(status, 200, out)
        self.assertEqual(out['reply'], 'Thank you, I have noted that.')
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'RC04'})
        # The answer buttons come with the catalog's own wording, not the model's.
        catalog = conversation_records._question(flow, out['guide'], out['record'], 'RC04')
        self.assertEqual(out['assessment']['nextQuestion']['question'], catalog['question'])
        self.assertTrue(out['assessment']['nextQuestion']['choices'])
        self.assertNotIn('Do you have any part of Medicare yet?', json.dumps(out))
        self.assertEqual(out['guide']['fields']['subject.role']['value'], 'self')
        one = out['metrics']['oneCall']
        self.assertEqual((one['requests'], one['toolCalls'], one['saved'], one['fallback']), (2, 2, 1, False))
        self.assertEqual(out['metrics']['llmCalls'], 2)
        for key in support.UI_KEYS:
            self.assertIn(key, out)
        # The engine hook answered through advisor-first's own evaluate; no ranking came from here.
        status_output = json.loads(script.sent[-1]['input'][-1]['output'])
        self.assertTrue(status_output['recommendation']['available'])
        self.assertEqual(support.charge_rows(budget), ['settled', 'settled'])
        self.assertEqual(len(script.sent[0]['instructions'].encode()), len(script.sent[1]['instructions'].encode()))

        # A request without the current context policy is refused over HTTP too, with nothing sent.
        status, refused = self.turn(port, auth, out, {'type': 'message', 'message': 'And now?'}, consent=True, policy=None)
        self.assertEqual(status, 428)
        self.assertEqual(refused['error'], one_call_flow.POLICY_MESSAGE)
        self.assertEqual(len(script.sent), 2)

    def test_turn_traces_record_a_scripted_turn_for_the_side_panel(self):
        """With turn traces on, a typed turn is saved with its model and tool calls and the
        panel's routes return it to the same visit only (D155 Q6, local testing)."""
        script = Script()
        folder = Path(self.enterContext(TemporaryDirectory(prefix='daylight-one-call-traces-')))
        service = self.build(client=ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=script),
                             reconcile=False, turn_traces=folder)
        support.temporary_ledger(self, service.adaptive.agent)
        port = self.serve(service)
        auth, state = self.session(port)
        status, _, raw = self.request(port, 'GET', '/ten-config.json', headers=auth)
        self.assertEqual(status, 200)
        self.assertIs(json.loads(raw).get('devTraces'), True)        # the panel mounts only when this is true
        status, _, raw = self.request(port, 'GET', '/api/status', headers=auth)
        info = json.loads(raw)
        self.assertTrue(info['dev_turn_traces'] and info['conversation_logging'])
        self.assertEqual(info['local_demo']['surface'], one_call_server.SURFACE)   # one-call's own status survives

        status, out = self.turn(port, auth, state, {'type': 'start'}, consent=False, policy=None)
        self.assertEqual(status, 200)
        script.add([save(update('RC01', {'choice': 'self'}, 'This coverage is for me')), call('c2', 'get_plan_status', {})],
                   [message(reply('Thank you, I have noted that.', question='Do you have any part of Medicare yet?',
                                  target='RC04', detail_step='requested_work'))])
        text = 'This coverage is for me. Please help me check which parts of Medicare I have.'
        status, out = self.turn(port, auth, out, {'type': 'message', 'message': text}, consent=True, policy=CONTEXT_POLICY)
        self.assertEqual(status, 200, out)

        status, _, raw = self.request(port, 'GET', '/api/dev/turns', headers=auth)
        self.assertEqual(status, 200)
        turns = json.loads(raw)['turns']
        typed = [row for row in turns if row.get('action') == 'message']
        self.assertEqual(len(typed), 1, turns)
        status, _, raw = self.request(port, 'GET', '/api/dev/turns/' + typed[0]['turnId'], headers=auth)
        self.assertEqual(status, 200)
        record = json.loads(raw)
        self.assertEqual((record['status'], record['message'], record['reply']),
                         ('ok', text, 'Thank you, I have noted that.'))
        # Both requests of the one-call turn, each with its full prompt and raw output.
        self.assertEqual([call_['kind'] for call_ in record['modelCalls']], ['compose', 'compose'])
        self.assertTrue(all(call_['request'] and call_['status'] == 'ok' for call_ in record['modelCalls']))
        self.assertEqual(record['modelCalls'][0]['request']['instructions'], script.sent[0]['instructions'])
        # The variant's own tools, with the model's arguments and what code sent back.
        tools = {item['tool']: item for item in record['toolCalls']}
        self.assertIn('save_profile_fields', tools)
        self.assertIn('get_plan_status', tools)
        self.assertIsNotNone(tools['save_profile_fields']['output'])
        self.assertIn('subject.role', json.dumps(record['factsSaved']))
        self.assertEqual(len(list(folder.glob('*.json'))), len(turns))

        # Another visit sees none of these turns.
        other, _ = self.session(port)
        status, _, raw = self.request(port, 'GET', '/api/dev/turns', headers=other)
        self.assertEqual((status, json.loads(raw)['turns']), (200, []))
        status, _, _ = self.request(port, 'GET', '/api/dev/turns/' + typed[0]['turnId'], headers=other)
        self.assertEqual(status, 404)

    def test_turn_traces_are_off_unless_asked(self):
        port = self.serve(self.build())
        auth, _ = self.session(port)
        status, _, raw = self.request(port, 'GET', '/ten-config.json', headers=auth)
        self.assertNotEqual(json.loads(raw).get('devTraces'), True)
        status, _, _ = self.request(port, 'GET', '/api/dev/turns', headers=auth)
        self.assertNotEqual(status, 200)

    def test_requests_from_another_host_name_are_rejected(self):
        port = self.serve(self.build())
        connection = http.client.HTTPConnection(LOOPBACK, port, timeout=30)
        try:
            connection.request('GET', '/api/status', headers={'Host': 'example.invalid'})
            self.assertEqual(connection.getresponse().status, 403)
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()
