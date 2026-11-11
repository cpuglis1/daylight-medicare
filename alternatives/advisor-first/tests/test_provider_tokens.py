"""Exact local counter payload and fail-closed behavior; no live network."""
import copy
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from ai_budget import BudgetError
from provider_tokens import TokenCountUnavailable, count_input_tokens
from provider_transport import ProviderTransportError


class ProviderTokenTests(unittest.TestCase):
    def setUp(self):
        self.client = SimpleNamespace(key='PRIVATE-KEY-CANARY')
        self.payload = {'model':'gpt-5.4','instructions':'Exact instructions.',
            'input':[{'role':'user','content':'Fictional text.'}], 'tools':[],
            'text':{'format':{'type':'json_schema','schema':{'type':'object'}}},
            'stream':True, 'max_output_tokens':900}

    def test_same_exact_counted_fields_and_no_payload_mutation(self):
        before = copy.deepcopy(self.payload)
        calls = []
        def transport(request, **kwargs):
            calls.append((request,kwargs))
            return io.BytesIO(b'{"object":"response.input_tokens","input_tokens":16000}')
        with patch('provider_tokens.urlopen',side_effect=transport):
            self.assertEqual(count_input_tokens(self.client,self.payload),16000)
        self.assertEqual(len(calls),1)
        request, kwargs = calls[0]
        self.assertEqual(request.full_url,'https://api.openai.com/v1/responses/input_tokens')
        self.assertEqual(kwargs,{'timeout':15})
        self.assertEqual(json.loads(request.data),{key:self.payload[key] for key in
            ('model','instructions','input','tools','text')})
        self.assertEqual(self.payload,before)

    def test_connection_failure_never_retries_or_exposes_provider_text(self):
        with patch('provider_tokens.urlopen',side_effect=URLError('PRIVATE-CANARY')) as transport:
            with self.assertRaises(BudgetError) as caught:
                count_input_tokens(self.client,self.payload)
        self.assertEqual(transport.call_count,1)
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_unverifiable_or_oversized_counts_fail_closed(self):
        for body in (b'{"object":"wrong","input_tokens":100}',
                     b'{"object":"response.input_tokens","input_tokens":true}',
                     b'{"object":"response.input_tokens","input_tokens":-1}', b'not json', b'x'*10001):
            with self.subTest(body_length=len(body)), patch('provider_tokens.urlopen',return_value=io.BytesIO(body)):
                with self.assertRaises(BudgetError):
                    count_input_tokens(self.client,self.payload)

    def test_transport_category_survives_without_provider_or_user_text(self):
        with patch('provider_tokens.urlopen',side_effect=ProviderTransportError('tls',35)) as transport:
            with self.assertRaises(TokenCountUnavailable) as caught:
                count_input_tokens(self.client,self.payload)
        self.assertEqual(caught.exception.failure_code,'input_token_verification')
        self.assertEqual(caught.exception.diagnostic,{'phase':'preflight','exception':'ProviderTransportError',
            'curl_exit_code':35,'transport_category':'tls'})
        self.assertNotIn('budget',str(caught.exception).lower())
        transport.assert_called_once()

    def test_dropped_count_connection_recovers_once_with_identical_request(self):
        with patch('provider_tokens.time.sleep'), patch('provider_tokens.urlopen', side_effect=[
                ProviderTransportError('receive', 56),
                io.BytesIO(b'{"object":"response.input_tokens","input_tokens":350}')]) as transport:
            self.assertEqual(count_input_tokens(self.client, self.payload), 350)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(transport.call_args_list[0].args[0].data,
                         transport.call_args_list[1].args[0].data)


if __name__ == '__main__':
    unittest.main()
