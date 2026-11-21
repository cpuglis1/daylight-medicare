"""Localhost turn traces and the dev turn routes (D155 Q6, step 6 of the rebalance).

Covers: (1) a traced turn returns the turn's own result and saves one record
keyed by its request ID with facts saved, source lookups, model calls (full
prompt, raw output, model, tokens, latency, status), checks fired and the next
question; (2) a failing turn re-raises its own error and is still saved;
(3) a client with no transport is left without one (behavior unchanged), and
extraction requests sent through urlopen are noted without headers;
(4) the pilot and hosted runs refuse traces; build() saves none unless asked;
(5) over real loopback HTTP, the caller sees only their own turns, the config
advertises devTraces and /api/status reports logging honestly;
(6) tools/show_turn.py retrieves a turn by ID. All data is fictional; no live
models.
"""
import http.client
import io
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
from server import build  # First: it puts the pinned engine on sys.path.
import narrative_agent
import turn_trace

PROMPT = {'model': 'fictional-model', 'instructions': 'Compose.',
          'input': [{'role': 'user', 'content': json.dumps({'resolved_context': {
              'current_message': 'What is Part B?', 'message_evidence_ids': ['partb'],
              'evidence': [{'id': 'partb', 'title': 'Part B basics', 'kind': 'teaching'}]}})}]}
RESPONSE = {'status': 'completed', 'usage': {'input_tokens': 120, 'output_tokens': 30, 'total_tokens': 150}}


class FakeAgent:
    """A stand-in agent whose compose call returns a canned response."""

    def __init__(self, transport=None):
        """Set a fictional client; `transport` None means the urlopen path."""
        self.client = SimpleNamespace(model='fictional-model', transport=transport)
        self.usage = []

    def _complete(self, payload, raw):
        """Record usage like the real agent and return (response, text)."""
        self.usage.append(RESPONSE['usage'])
        logging.getLogger('natural_agent').warning('Daylight composition repair code=ungrounded_literal')
        return RESPONSE, '{"reply":"Part B covers doctor visits."}'

    def run(self, *args):
        """Extraction stand-in that makes no model call (a cache hit)."""
        return {'updates': []}


class FakeService:
    """The minimum of a built server that install_turn_traces touches."""

    def __init__(self, agent, turn):
        """Attach the agent and turn callable the way the engine does."""
        self.adaptive = SimpleNamespace(agent=agent, model_agents={}, turn=turn)
        self.RequestHandlerClass = type('Handler', (), {})


class TraceUnitTests(unittest.TestCase):
    def setUp(self):
        """Give each test its own trace directory."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'traces'

    def install(self, turn, agent=None):
        """Install traces on a fake service and return (service, agent)."""
        agent = agent or FakeAgent()
        service = FakeService(agent, turn)
        return turn_trace.install_turn_traces(service, self.root), agent

    def test_traced_turn_saves_every_panel_section_and_returns_the_result(self):
        """One record keyed by requestId holds facts, lookups, calls, checks and next question."""
        result = {'guide': {'fields': {'helpingFor': 'self', 'zip': '00000'}}, 'reply': 'Part B covers doctor visits.',
                  'assessment': {'nextQuestion': {'id': 'T05', 'text': 'What insurance do you have now?'}},
                  'generated': {'source_fallback': {'kind': 'quoted'}}}
        holder = {}

        def turn(owner, payload):
            holder['agent']._complete(PROMPT, b'')
            holder['agent'].run()
            return result
        service, agent = self.install(turn)
        holder['agent'] = agent
        request_id = str(uuid.uuid4())
        payload = {'requestId': request_id, 'guide': {'fields': {'zip': '00000'}},
                   'action': {'type': 'message', 'message': 'What is Part B?'}}
        self.assertIs(service.adaptive.turn('owner-a', payload), result)
        record = turn_trace.TraceStore(self.root).get(request_id, 'owner-a')
        self.assertEqual(record['message'], 'What is Part B?')
        self.assertEqual(record['factsSaved'], [{'field': 'helpingFor', 'before': None, 'after': 'self'}])
        self.assertEqual(record['toolCalls'][0]['output']['messageEvidenceIds'], ['partb'])
        compose, extract = record['modelCalls']
        self.assertEqual((compose['kind'], compose['model'], compose['status']), ('compose', 'fictional-model', 'ok'))
        self.assertEqual(compose['tokens'], {'input_tokens': 120, 'output_tokens': 30, 'total_tokens': 150})
        self.assertEqual(compose['request'], PROMPT)
        self.assertIn('Part B covers', compose['rawOutput'])
        self.assertIsInstance(compose['latencyMs'], int)
        self.assertEqual(extract['status'], 'cached')
        messages = [check['message'] for check in record['checks']]
        self.assertIn('Daylight composition repair code=ungrounded_literal', messages)
        self.assertIn('source_fallback', messages)
        self.assertEqual(record['nextQuestion']['id'], 'T05')
        self.assertNotEqual(record['owner'], 'owner-a')
        self.assertIsNone(turn_trace.TraceStore(self.root).get(request_id, 'owner-b'))

    def test_failing_turn_reraises_its_error_and_is_still_saved(self):
        """The turn's own exception propagates and the record says error."""
        class Refused(Exception):
            pass

        def turn(owner, payload):
            raise Refused('held')
        service, _ = self.install(turn)
        request_id = str(uuid.uuid4())
        with self.assertRaises(Refused):
            service.adaptive.turn('owner-a', {'requestId': request_id})
        record = turn_trace.TraceStore(self.root).get(request_id)
        self.assertEqual((record['status'], record['error']), ('error', 'Refused: held'))

    def test_logs_outside_a_turn_are_not_collected(self):
        """A warning on another thread or outside a turn never enters a trace."""
        service, _ = self.install(lambda owner, payload: {})
        logging.getLogger('natural_agent').warning('outside any turn')
        worker = threading.Thread(target=lambda: logging.getLogger('natural_flow').warning('other thread'))
        request_id = str(uuid.uuid4())

        def turn(owner, payload):
            worker.start(); worker.join()
            return {}
        service.adaptive.turn = lambda owner, payload: turn_trace.trace_turn(service.turn_traces, turn, owner, payload)
        service.adaptive.turn('owner-a', {'requestId': request_id})
        self.assertEqual(turn_trace.TraceStore(self.root).get(request_id)['checks'], [])

    def test_missing_transport_stays_missing(self):
        """Wrapping never gives a no-transport client a transport (that would change its path)."""
        _, agent = self.install(lambda owner, payload: {}, FakeAgent(transport=None))
        self.assertIsNone(agent.client.transport)

    def test_existing_transport_is_noted_and_delegates(self):
        """A set transport still returns its own answer; the payload is noted for the trace."""
        calls = []
        _, agent = self.install(lambda o, p: {}, FakeAgent(transport=lambda payload: calls.append(payload) or RESPONSE))
        collector = turn_trace._Collector()
        turn_trace._local.collector = collector
        try:
            self.assertIs(agent.client.transport(PROMPT), RESPONSE)
        finally:
            turn_trace._local.collector = None
        self.assertEqual(calls, [PROMPT])
        self.assertEqual(collector.requests, [PROMPT])

    def test_extraction_urlopen_notes_only_the_body(self):
        """The urlopen wrapper copies the JSON body (never headers) and delegates."""
        seen = []
        original = narrative_agent.urlopen
        narrative_agent.urlopen = lambda request, *a, **k: seen.append(request) or 'stream'
        self.addCleanup(setattr, narrative_agent, 'urlopen', original)
        self.install(lambda o, p: {})
        request = SimpleNamespace(data=json.dumps(PROMPT).encode(), headers={'Authorization': 'Bearer sk-canary-key'})
        collector = turn_trace._Collector()
        turn_trace._local.collector = collector
        try:
            self.assertEqual(narrative_agent.urlopen(request, timeout=40), 'stream')
        finally:
            turn_trace._local.collector = None
        self.assertEqual(seen, [request])
        self.assertEqual(collector.requests, [PROMPT])
        self.assertNotIn('sk-canary-key', json.dumps(collector.requests))

    def test_pilot_and_hosted_refuse_traces(self):
        """D155 Q6a: the pilot and a hosted origin are hard-off."""
        for flags in ({'pilot': True}, {'hosted': True}):
            with self.assertRaises(turn_trace.TraceDisabled):
                turn_trace.install_turn_traces(FakeService(FakeAgent(), lambda o, p: {}), self.root, **flags)
        self.assertFalse(self.root.exists())

    def test_store_prunes_to_its_limit_and_rejects_path_ids(self):
        """The store keeps the newest files only and never reads outside its root."""
        store = turn_trace.TraceStore(self.root, max_turns=2)
        ids = [f'turn-{index:06d}' for index in range(3)]
        for turn_id in ids:
            store.save({'turnId': turn_id, 'owner': 'x'})
        self.assertEqual(sorted(p.stem for p in self.root.glob('*.json')), ids[1:])
        self.assertIsNone(store.get('../../etc/passwd'))

    def test_show_turn_cli_prints_a_turn_by_id(self):
        """Agents retrieve a saved turn by ID; --summary shows each panel section."""
        import show_turn
        store = turn_trace.TraceStore(self.root)
        store.save({'turnId': 'turn-cli-000001', 'owner': 'x', 'message': 'What is Part B?', 'status': 'ok',
                    'factsSaved': [{'field': 'zip', 'before': None, 'after': '00000'}],
                    'toolCalls': [], 'modelCalls': [], 'checks': [], 'nextQuestion': {'id': 'T05'}})
        out = io.StringIO()
        with unittest.mock.patch.dict('os.environ', {'DAYLIGHT_TURN_TRACES_DIR': str(self.root)}), redirect_stdout(out):
            self.assertEqual(show_turn.main(['turn-cli-000001', '--summary']), 0)
        self.assertIn('zip', out.getvalue())
        self.assertIn('T05', out.getvalue())


class TraceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Run a fixture server on loopback with traces in a temporary directory."""
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / 'traces'
        cls.server = build(0, fixture=True, database=Path(cls.tmp.name) / 'private/test.sqlite3', turn_traces=cls.root)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        """Stop the server and remove its files."""
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def request(self, path, body=None, cookie=None):
        """Send one same-origin request; return (status, json, cookie)."""
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        if cookie:
            headers['Cookie'] = cookie
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'X-Daylight-CSRF': self.csrf})
        connection.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        raw, set_cookie = response.read(), response.getheader('Set-Cookie')
        connection.close()
        return response.status, json.loads(raw), (set_cookie.split(';')[0] if set_cookie else cookie)

    def visit(self):
        """Start a fictional visit; return (cookie, state)."""
        _, session, cookie = self.request('/api/guest/session')
        self.csrf = session['csrf']
        _, state, cookie = self.request('/api/conversation/initial', cookie=cookie)
        return cookie, state

    def test_turn_is_traced_and_only_its_owner_can_read_it(self):
        """A choice turn is saved; its owner lists and reads it; another visit gets 404."""
        cookie, state = self.visit()
        request_id = str(uuid.uuid4())
        status, out, cookie = self.request('/api/conversation/turn', {
            'guide': state['guide'], 'record': state['record'], 'requestId': request_id,
            'action': {'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}}}, cookie)
        self.assertEqual(status, 200, out)
        status, listing, _ = self.request('/api/dev/turns', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(request_id, [row['turnId'] for row in listing['turns']])
        status, record, _ = self.request('/api/dev/turns/' + request_id, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(record['action'], 'choice')
        self.assertTrue(record['factsSaved'])
        other, _ = self.visit()
        self.assertEqual(self.request('/api/dev/turns/' + request_id, cookie=other)[0], 404)
        self.assertNotIn(request_id, json.dumps(self.request('/api/dev/turns', cookie=other)[1]))

    def test_config_and_status_report_traces(self):
        """The UI sees devTraces, and /api/status no longer claims no chat logging."""
        cookie, _ = self.visit()
        self.assertTrue(self.request('/ten-config.json', cookie=cookie)[1]['devTraces'])
        status = self.request('/api/status', cookie=cookie)[1]
        self.assertTrue(status['conversation_logging'])
        self.assertTrue(status['dev_turn_traces'])


class DefaultBuildTests(unittest.TestCase):
    def test_build_saves_no_traces_unless_asked(self):
        """A plain build() (tests, other callers) has no trace routes or devTraces flag."""
        with tempfile.TemporaryDirectory() as tmp:
            server = build(0, fixture=True, database=Path(tmp) / 'private/test.sqlite3')
            try:
                self.assertFalse(hasattr(server, 'turn_traces'))
                self.assertNotIn('TraceHandler', [cls.__name__ for cls in server.RequestHandlerClass.__mro__])
            finally:
                server.server_close()


import unittest.mock  # noqa: E402  (used by the CLI test's environment patch)

if __name__ == '__main__':
    unittest.main()
