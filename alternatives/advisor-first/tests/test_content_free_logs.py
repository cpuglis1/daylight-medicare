"""HP-09: logs and diagnostics carry no health content or identifiers.

A fictional journey full of canary health details runs through the real HTTP
server in fixture mode; every log record and console line is captured and
scanned. Static checks keep future log calls on fixed format strings."""
import ast
import contextlib
import http.client
import io
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from server import build
from controller_diagnostics import unexpected_failure
from log_guard import WITHHELD, ContentFreeFilter
from transport_diagnostics import failure_details

HEALTH_CANARIES = ['Larkspur Canaryfield', 'Zylotrexin', 'Quillmont Pharmacy', 'canary-condition-x']
IDENTIFIER_CANARIES = ['1EG4-TE5-MK73', '123-45-6789', '4111 1111 1111 1111']
LOG_METHODS = {'debug', 'info', 'warning', 'error', 'exception', 'critical'}
LOG_OWNERS = {'LOGGER', 'logger', 'access_log', 'logging'}
CONTENT_NAMES = {'message', 'text', 'payload', 'body', 'prompt', 'reply', 'content', 'guide', 'record',
                 'g', 'r', 'out', 'answer', 'response', 'action', 'fields', 'value', 'raw', 'data'}


def source_files():
    for path in sorted(HERE.glob('*.py')):
        yield path


class StaticLogCallTests(unittest.TestCase):
    def test_log_calls_use_fixed_formats_and_no_content_variables(self):
        problems = []
        for path in source_files():
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in LOG_METHODS and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in LOG_OWNERS):
                    continue
                if not node.args or not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    problems.append(f'{path.name}:{node.lineno} format is not a fixed string')
                for argument in node.args[1:]:
                    for name in ast.walk(argument):
                        if isinstance(name, ast.Name) and name.id in CONTENT_NAMES:
                            problems.append(f'{path.name}:{node.lineno} logs {name.id}')
        self.assertEqual(problems, [])


class DiagnosticTests(unittest.TestCase):
    def test_provider_error_bodies_are_not_logged(self):
        body = json.dumps({'error': {'type': 'invalid_request_error',
                                     'message': 'Echo: Zylotrexin for Larkspur Canaryfield 1EG4-TE5-MK73'}}).encode()
        error = HTTPError('https://api.openai.com/v1/responses', 400, 'Bad Request', {}, io.BytesIO(body))
        details = json.dumps(failure_details(error, 'stream'))
        for canary in HEALTH_CANARIES + IDENTIFIER_CANARIES:
            self.assertNotIn(canary, details)

    def test_controller_failures_omit_exception_messages(self):
        try:
            raise KeyError('Zylotrexin Larkspur Canaryfield')
        except KeyError as error:
            details = json.dumps(unexpected_failure(error))
        for canary in HEALTH_CANARIES:
            self.assertNotIn(canary, details)

    def test_filter_withholds_identifier_lines(self):
        record = logging.LogRecord('natural_agent', logging.WARNING, __file__, 1, 'Daylight value %s',
                                   ('1EG4-TE5-MK73',), None)
        ContentFreeFilter().filter(record)
        self.assertEqual(record.getMessage(), WITHHELD)

    def test_filter_is_installed_on_daylight_loggers(self):
        for name in ('natural_flow', 'natural_agent', 'session_recovery', 'comparison_service'):
            self.assertTrue(any(isinstance(f, ContentFreeFilter) for f in logging.getLogger(name).filters), name)


class JourneyLogScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = build(0, fixture=True, database=Path(cls.tmp.name) / 'private/test.sqlite3')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def call(self, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        if self.cookie: headers['Cookie'] = self.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'; headers['X-Daylight-CSRF'] = self.session['csrf']
        connection.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse(); raw = response.read(); cookie = response.getheader('Set-Cookie')
        if cookie: self.cookie = cookie.split(';')[0]
        connection.close()
        return response.status, json.loads(raw)

    def turn(self, action, expect=200):
        payload = {'guide': self.state['guide'], 'record': self.state['record'], 'action': action,
                   'requestId': str(uuid.uuid4())}
        if self.state.get('continuation'): payload['continuation'] = self.state['continuation']
        status, out = self.call('/api/conversation/turn', payload)
        if expect is not None:
            self.assertEqual(status, expect, out)
        if status == 200:
            self.state = out
        return status, out

    def test_fictional_journey_leaves_no_health_content_in_logs(self):
        captured = io.StringIO()
        handler = logging.StreamHandler(captured); handler.setLevel(logging.DEBUG)
        root = logging.getLogger(); level = root.level
        root.addHandler(handler); root.setLevel(logging.DEBUG)
        console = io.StringIO()
        try:
            with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console):
                self.cookie = None
                status, self.session = self.call('/api/guest/session'); self.assertEqual(status, 200)
                _, self.state = self.call('/api/conversation/initial')
                self.turn({'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}})
                self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
                self.turn({'type': 'choice', 'id': 'T06', 'fields': {'text': 'Dr. Larkspur Canaryfield'}})
                self.turn({'type': 'choice', 'id': 'T07', 'fields': {'text': 'Zylotrexin 40 mg from Quillmont Pharmacy'}}, expect=None)
                self.turn({'type': 'message', 'message': 'I take Zylotrexin for canary-condition-x and see Dr. Larkspur Canaryfield.'})
                self.turn({'type': 'message', 'message': 'My Medicare number is 1EG4-TE5-MK73'}, expect=422)
                self.call('/api/conversation/turn', {'guide': {}, 'record': {}, 'action': {'type': 'message',
                          'message': 'Zylotrexin Larkspur Canaryfield'}, 'requestId': 'bad'})
        finally:
            root.removeHandler(handler); root.setLevel(level)
        text = captured.getvalue() + console.getvalue()
        for canary in HEALTH_CANARIES + IDENTIFIER_CANARIES:
            self.assertNotIn(canary, text)


if __name__ == '__main__':
    unittest.main()
