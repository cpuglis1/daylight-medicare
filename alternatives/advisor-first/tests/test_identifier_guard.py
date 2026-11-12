"""HP-07: SSNs, Medicare numbers and card numbers never reach the model, storage or logs.

All identifiers below are fictional test values (CMS's published sample MBI shape,
the standard 4111 test card, an SSN-shaped placeholder)."""
import http.client
import io
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
from identifier_guard import (IDENTIFIER_MESSAGE, find_identifiers, find_transport_identifiers,
                              submitted_strings)
from provider_transport import ProviderTransportError, _configuration
from transport_diagnostics import failure_details

CANARIES = ['123 45 6789', '123456789', '1EG4-TE5-MK73', '1EG4TE5MK73', '4111 1111 1111 1111', '4111111111111111']


class DetectorTests(unittest.TestCase):
    def test_finds_each_identifier_shape(self):
        expected = {
            '123-45-6789': ['ssn'], 'my number is 123 45 6789': ['ssn'], 'ssn 123456789': ['ssn'],
            '1EG4-TE5-MK73': ['medicare_number'], 'card: 1eg4te5mk73': ['medicare_number'],
            '1EG4 TE5 MK73': ['medicare_number'], '4111 1111 1111 1111': ['payment_card'],
            '4111-1111-1111-1111': ['payment_card'], '4111111111111111': ['payment_card'],
        }
        for text, categories in expected.items():
            self.assertEqual(find_identifiers(text), categories, text)

    def test_ignores_ordinary_numbers(self):
        for text in ['ZIP 34102', '34102-1234', 'born 1960, call 239-555-0100', 'NPI 1234567893',
                     'NDC 00093-7180-56', 'plan H1234-005-0', 'Part B $202.90', '2027-01-01',
                     'hash a1b2c3123456789d', '000-12-3456', '666-12-3456', '912-34-5678',
                     '1SG4TE5MK73', '4111-1111-1111-1112', '0000 0000 0000 0000']:
            self.assertEqual(find_identifiers(text), [], text)

    def test_transport_check_is_narrower(self):
        self.assertEqual(find_transport_identifiers('{"id": 123456789}'), [])
        self.assertEqual(find_transport_identifiers('{"t": 4111111111111111}'), [])
        self.assertEqual(find_transport_identifiers('{"m": "1EG4-TE5-MK73"}'), ['medicare_number'])
        self.assertEqual(find_transport_identifiers('{"s": "123-45-6789"}'), ['ssn'])
        self.assertEqual(find_transport_identifiers('{"c": "4111 1111 1111 1111"}'), ['payment_card'])

    def test_results_never_echo_values(self):
        result = json.dumps(find_identifiers(' '.join(CANARIES)))
        for canary in CANARIES:
            self.assertNotIn(canary, result)

    def test_submitted_strings_reach_nested_fields(self):
        action = {'type': 'choice', 'id': 'T06', 'fields': {'text': 'a', 'items': [{'name': 'b'}]}}
        self.assertEqual(sorted(submitted_strings(action)), ['T06', 'a', 'b', 'choice'])


class TransportBackstopTests(unittest.TestCase):
    URL = 'https://api.openai.com/v1/responses'

    def request(self, body):
        return Request(self.URL, data=json.dumps(body).encode(), method='POST',
                       headers={'Content-Type': 'application/json'})

    def test_clean_request_is_configured(self):
        # AI-04: a clean request still has to name an allowlisted model.
        self.assertIn(b'data-binary', _configuration(self.request({'model': 'gpt-6.1-sol',
                                                                   'input': 'ZIP 34102, turning 65'})))

    def test_identifier_in_request_is_refused_with_category_only(self):
        for text in ['1EG4-TE5-MK73', '123-45-6789', '4111 1111 1111 1111']:
            with self.assertRaises(ProviderTransportError) as caught:
                _configuration(self.request({'input': 'Fictional ' + text}))
            self.assertEqual(caught.exception.transport_category, 'identifier_blocked')
            details = json.dumps(failure_details(caught.exception, 'preflight'))
            self.assertIn('identifier_blocked', details)
            self.assertNotIn(text, details)


class ConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = build(0, fixture=True, database=Path(cls.tmp.name) / 'private/test.sqlite3')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def setUp(self):
        self.log = io.StringIO()
        self.handler = logging.StreamHandler(self.log)
        self.handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        self.level = root.level
        root.addHandler(self.handler); root.setLevel(logging.DEBUG)
        self.cookie = None
        status, self.session = self.call('/api/guest/session'); self.assertEqual(status, 200)
        _, self.state = self.call('/api/conversation/initial')

    def tearDown(self):
        root = logging.getLogger()
        root.removeHandler(self.handler); root.setLevel(self.level)
        for canary in CANARIES:
            self.assertNotIn(canary, self.log.getvalue())

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

    def turn(self, action):
        payload = {'guide': self.state['guide'], 'record': self.state['record'], 'action': action,
                   'requestId': str(uuid.uuid4())}
        if self.state.get('continuation'): payload['continuation'] = self.state['continuation']
        return self.call('/api/conversation/turn', payload)

    def test_messages_with_identifiers_are_refused_and_not_stored(self):
        for text in ['My SSN is 123 45 6789', 'Medicare card 1EG4-TE5-MK73', 'Pay with 4111 1111 1111 1111']:
            status, out = self.turn({'type': 'message', 'message': text})
            self.assertEqual(status, 422, out)
            self.assertIn(IDENTIFIER_MESSAGE, json.dumps(out))
        status, out = self.turn({'type': 'message', 'message': "I'm turning 65 in November and live in ZIP 34102."})
        self.assertEqual(status, 200, out)
        stored = json.dumps(out)
        for canary in CANARIES:
            self.assertNotIn(canary, stored)

    def test_answers_with_identifiers_are_refused(self):
        status, out = self.turn({'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}})
        self.assertEqual(status, 200, out); self.state = out
        status, out = self.turn({'type': 'choice', 'id': 'T06', 'fields': {'text': 'Dr. Example, card 4111111111111111'}})
        self.assertEqual(status, 422, out)
        self.assertIn(IDENTIFIER_MESSAGE, json.dumps(out))
        status, out = self.turn({'type': 'choice', 'id': 'T06', 'fields': {'text': 'Dr. Example Canary'}})
        self.assertEqual(status, 200, out)


if __name__ == '__main__':
    unittest.main()
