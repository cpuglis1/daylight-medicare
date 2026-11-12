"""Precise failure categories without customer text or provider error bodies."""
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transport_diagnostics import failure_details


class TransportDiagnosticTests(unittest.TestCase):
    def test_http_failure_exposes_status_and_known_code_only(self):
        error = HTTPError('https://private-canary.invalid', 400, 'PRIVATE-CANARY', {},
            io.BytesIO(json.dumps({'error':{'code':'invalid_json_schema',
                'message':'PRIVATE-CANARY','param':'PRIVATE-CANARY'}}).encode()))
        actual = failure_details(error, 'stream', {'terminal':False,'delta_events':0,
            'text_chars':0,'private':'PRIVATE-CANARY'})
        self.assertEqual(actual, {'exception':'HTTPError','phase':'stream','http_status':400,
            'provider_code':'invalid_json_schema','terminal':False,'delta_events':0,'text_chars':0})
        self.assertNotIn('PRIVATE',json.dumps(actual))

    def test_untrusted_codes_and_malformed_body_do_not_break_failure_handling(self):
        for body in ({'error':{'code':{'private':'CANARY'}}}, {'error':{'code':'private_canary'}}, ['CANARY']):
            error = HTTPError('https://private.invalid', 500, 'CANARY', {}, io.BytesIO(json.dumps(body).encode()))
            actual = failure_details(error, 'stream')
            self.assertNotIn('CANARY',json.dumps(actual))
        error = HTTPError('https://private.invalid', 500, 'CANARY', {}, io.BytesIO(b'bad body'))
        self.assertEqual(failure_details(error,'stream')['provider_code'],'unknown')

    def test_decode_failure_distinguishes_phase_without_retaining_json(self):
        try:
            json.loads('PRIVATE-CANARY')
        except ValueError as error:
            actual = failure_details(error,'decode',{'terminal':True,'delta_events':1,'text_chars':14})
        self.assertEqual(actual['exception'],'JSONDecodeError')
        self.assertEqual(actual['phase'],'decode')
        self.assertTrue(actual['terminal'])
        self.assertNotIn('PRIVATE',json.dumps(actual))


if __name__ == '__main__':
    unittest.main()
