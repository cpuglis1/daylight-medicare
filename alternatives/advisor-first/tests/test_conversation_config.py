"""Editable checks, ordering guidance and the dev checks routes (D155 Q2, Q8; step 7).

Covers: (1) the checked-in checks and instructions files are valid and the
built-in guidance file matches natural_agent's paragraph byte for byte;
(2) save_checks changes only editable fields of editable checks, refuses gate
edits, unknown IDs and fields, bad floors, and writes nothing on refusal;
(3) compose_instructions() returns COMPOSE_INSTRUCTIONS unchanged by default
and swaps only the ordering paragraph for a valid override, falling back on a
missing or invalid file; (4) over loopback HTTP, /api/dev/checks needs a cookie
(401), a same-origin request (403) and the CSRF header on POST, refuses gate
edits (422), saves editable edits, and does not exist on a plain build(),
in the pilot or on a hosted origin. Fictional data, no live models; every
write goes to a temporary copy, never the repo files.
"""
import http.client
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from server import build  # First: it puts the pinned engine on sys.path.
import conversation_config as cc
import dev_checks_http
import natural_agent


class TempConfig(unittest.TestCase):
    """Copies both config files to a temp dir so saves never touch the repo."""

    def setUp(self):
        """Copy the real files into a fresh temporary directory."""
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.checks = self.dir / 'conversation-checks.json'
        self.guidance = self.dir / 'conversation-instructions.json'
        shutil.copy(cc.CHECKS_PATH, self.checks)
        shutil.copy(cc.INSTRUCTIONS_PATH, self.guidance)


class FileTests(TempConfig):
    """The checked-in files and the save rules."""

    def test_checked_in_files_are_valid_and_guidance_matches_the_built_in_text(self):
        """Both repo files load; the stored guidance equals natural_agent's default paragraph."""
        ids = [c['id'] for c in cc.load_checks()['checks']]
        self.assertIn('privacy', ids)
        self.assertEqual(cc.ordering_guidance(), natural_agent.ORDERING_GUIDANCE)
        self.assertTrue(natural_agent.ORDERING_GUIDANCE.startswith('Ordering guidance:'))
        self.assertTrue(natural_agent.ORDERING_GUIDANCE.endswith('calibrating explanations.'))

    def test_gates_are_read_only(self):
        """A changed question on a gate is refused and the file is unchanged."""
        before = self.checks.read_bytes()
        for edit in ({'id': 'privacy', 'question': 'Anything goes here, really, any text at all.'},
                     {'id': 'cites_sources', 'floor': 0.5}):
            with self.assertRaisesRegex(cc.ConfigError, 'read-only gate'):
                cc.save_checks([edit], self.checks)
        self.assertEqual(self.checks.read_bytes(), before)

    def test_unchanged_gate_values_are_accepted(self):
        """Sending a gate's current values back (no change) is not an edit and is allowed."""
        privacy = next(c for c in cc.load_checks(self.checks)['checks'] if c['id'] == 'privacy')
        cc.save_checks([{'id': 'privacy', 'floor': privacy['floor']}], self.checks)

    def test_editable_check_saves_only_allowed_fields(self):
        """Title, question, floor and failOnAny change; gate, editable and id cannot."""
        saved = cc.save_checks([{'id': 'no_reask', 'floor': 0.9, 'title': 'No repeats'}], self.checks)
        row = next(c for c in saved['checks'] if c['id'] == 'no_reask')
        self.assertEqual((row['floor'], row['title']), (0.9, 'No repeats'))
        self.assertEqual(json.loads(self.checks.read_text())['checks'][6]['floor'], 0.9)
        for edit in ({'id': 'no_reask', 'gate': True}, {'id': 'no_reask', 'editable': False},
                     {'id': 'no_reask', 'floor': 1.5}, {'id': 'no_reask', 'floor': True},
                     {'id': 'no_reask', 'question': 'short'}, {'id': 'made_up', 'floor': 0.5}):
            with self.subTest(edit=edit), self.assertRaises(cc.ConfigError):
                cc.save_checks([edit], self.checks)

    def test_a_refused_batch_writes_nothing(self):
        """One bad edit in a batch leaves the earlier good edit unsaved."""
        before = self.checks.read_bytes()
        with self.assertRaises(cc.ConfigError):
            cc.save_checks([{'id': 'no_reask', 'floor': 0.5}, {'id': 'privacy', 'floor': 0.5}], self.checks)
        self.assertEqual(self.checks.read_bytes(), before)

    def test_a_gate_marked_editable_is_invalid(self):
        """The loader refuses a file where a gate claims to be editable."""
        value = json.loads(self.checks.read_text())
        value['checks'][2]['editable'] = True
        self.checks.write_text(json.dumps(value))
        with self.assertRaisesRegex(cc.ConfigError, 'gate cannot be editable'):
            cc.load_checks(self.checks)


class GuidanceTests(TempConfig):
    """compose_instructions() and its fallbacks."""

    def test_default_is_byte_identical(self):
        """With the checked-in default the instructions object is the built-in one."""
        self.assertIs(natural_agent.compose_instructions(), natural_agent.COMPOSE_INSTRUCTIONS)

    def test_override_replaces_only_the_ordering_paragraph(self):
        """A valid override appears once, the old paragraph is gone and the rest is unchanged."""
        cc.save_ordering_guidance('Ordering guidance: ask the ZIP first.', self.guidance)
        with mock.patch.object(cc, 'INSTRUCTIONS_PATH', self.guidance), \
                mock.patch.object(cc.ordering_guidance, '__defaults__', (self.guidance,)):
            text = natural_agent.compose_instructions()
        base = natural_agent.COMPOSE_INSTRUCTIONS
        self.assertEqual(text.count('ask the ZIP first.'), 1)
        self.assertNotIn(natural_agent.ORDERING_GUIDANCE, text)
        self.assertEqual(text.replace('Ordering guidance: ask the ZIP first.', natural_agent.ORDERING_GUIDANCE), base)

    def test_missing_or_invalid_file_falls_back(self):
        """No file, bad JSON, empty or oversized text all mean the built-in text."""
        for raw in (None, '{not json', json.dumps({'orderingGuidance': '  '}),
                    json.dumps({'orderingGuidance': 'x' * (cc.MAX_GUIDANCE + 1)})):
            with self.subTest(raw=(raw or '')[:20]):
                if raw is None:
                    self.guidance.unlink(missing_ok=True)
                else:
                    self.guidance.write_text(raw)
                with mock.patch.object(cc.ordering_guidance, '__defaults__', (self.guidance,)):
                    self.assertIs(natural_agent.compose_instructions(), natural_agent.COMPOSE_INSTRUCTIONS)


class HttpTests(TempConfig):
    """The dev routes over real loopback HTTP."""

    def serve(self, service):
        """Run a service on a thread; returns its port."""
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (service.shutdown(), service.server_close(), thread.join(5)))
        return service.server_port

    def call(self, port, path, payload=None, cookie=None, csrf=None, origin=None):
        """One request; returns (status, json)."""
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
        headers = {'Origin': origin or f'http://127.0.0.1:{port}'}
        if cookie:
            headers['Cookie'] = cookie
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        if csrf:
            headers['X-Daylight-CSRF'] = csrf
        connection.request('POST' if payload is not None else 'GET', path,
                           None if payload is None else json.dumps(payload), headers)
        response = connection.getresponse()
        self.last_cookie = (response.getheader('Set-Cookie') or '').split(';', 1)[0] or None
        body = response.read()
        connection.close()
        return response.status, json.loads(body or b'{}')

    def local_service(self):
        """A fixture service with the dev checks routes pointed at the temp files."""
        service = build(0, fixture=True, database=self.dir / 'g.sqlite3')
        dev_checks_http.install_dev_checks(service, checks_path=self.checks, instructions_path=self.guidance)
        port = self.serve(service)
        _, session = self.call(port, '/api/guest/session')
        return port, self.last_cookie, session['csrf']

    def test_needs_cookie_origin_and_csrf(self):
        """No cookie is 401, a cross origin is 403, a missing CSRF header is refused."""
        port, cookie, csrf = self.local_service()
        self.assertEqual(self.call(port, '/api/dev/checks')[0], 401)
        self.assertEqual(self.call(port, '/api/dev/checks', cookie=cookie, origin='http://evil.example')[0], 403)
        status, _ = self.call(port, '/api/dev/checks', {'checks': [{'id': 'no_reask', 'floor': 0.9}]}, cookie=cookie)
        self.assertIn(status, {401, 403})
        self.assertEqual(json.loads(self.checks.read_text())['checks'][6]['floor'], 0.95)
        status, value = self.call(port, '/api/dev/checks', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(value['instructions']['default'], natural_agent.ORDERING_GUIDANCE)
        self.assertEqual(len(value['checks']), 9)

    def test_post_saves_editable_and_refuses_gates(self):
        """An editable edit and guidance save; a gate edit is 422 and nothing is written."""
        port, cookie, csrf = self.local_service()
        status, value = self.call(port, '/api/dev/checks', {'checks': [{'id': 'privacy', 'floor': 0.1}],
                                                            'orderingGuidance': 'Ordering guidance: new.'},
                                  cookie=cookie, csrf=csrf)
        self.assertEqual(status, 422, value)
        self.assertEqual(cc.ordering_guidance(self.guidance), natural_agent.ORDERING_GUIDANCE)
        status, value = self.call(port, '/api/dev/checks', {'checks': [{'id': 'no_reask', 'floor': 0.9}],
                                                            'orderingGuidance': 'Ordering guidance: new.'},
                                  cookie=cookie, csrf=csrf)
        self.assertEqual(status, 200, value)
        self.assertEqual(value['instructions']['orderingGuidance'], 'Ordering guidance: new.')
        self.assertEqual(next(c for c in value['checks'] if c['id'] == 'no_reask')['floor'], 0.9)
        status, _ = self.call(port, '/api/dev/checks', {'surprise': 1}, cookie=cookie, csrf=csrf)
        self.assertEqual(status, 422)

    def test_bad_guidance_blocks_the_whole_save(self):
        """Oversized guidance is refused before the valid check edit is written."""
        port, cookie, csrf = self.local_service()
        status, _ = self.call(port, '/api/dev/checks', {'checks': [{'id': 'no_reask', 'floor': 0.9}],
                                                        'orderingGuidance': 'x' * 5000}, cookie=cookie, csrf=csrf)
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(self.checks.read_text())['checks'][6]['floor'], 0.95)

    def test_routes_exist_only_with_traces(self):
        """A plain build() has no route; build(turn_traces=...) has it; pilot and hosted are refused."""
        plain = self.serve(build(0, fixture=True, database=self.dir / 'p.sqlite3'))
        self.call(plain, '/api/guest/session')
        self.assertNotEqual(self.call(plain, '/api/dev/checks', cookie=self.last_cookie)[0], 200)
        traced = self.serve(build(0, fixture=True, database=self.dir / 't.sqlite3', turn_traces=self.dir / 'traces'))
        self.call(traced, '/api/guest/session')
        self.assertEqual(self.call(traced, '/api/dev/checks', cookie=self.last_cookie)[0], 200)
        for kwargs in ({'pilot': True}, {'hosted': True}):
            with self.subTest(**kwargs), self.assertRaises(dev_checks_http.DevChecksDisabled):
                dev_checks_http.install_dev_checks(object(), **kwargs)


if __name__ == '__main__':
    unittest.main()
