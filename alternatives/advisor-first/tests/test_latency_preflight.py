"""Local input-token bound on :8895 and per-stage thinking-token metrics; no live network."""
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: F401  (loads the pinned engine paths, as the other provider tests do)
from natural_agent import NaturalAgent
from provider_tokens import (PREFLIGHT_ENV, TokenCountUnavailable, count_input_tokens,
                             local_input_bound, uses_local_bound)


def payload(content='Fictional text.', instructions='Exact instructions.'):
    return {'model': 'gpt-6.2-sol', 'instructions': instructions,
            'input': [{'role': 'user', 'content': content}], 'tools': [],
            'text': {'format': {'type': 'json_schema', 'name': 'daylight_reply', 'strict': True,
                                'schema': {'type': 'object', 'properties': {'reply': {'type': 'string'}},
                                           'required': ['reply'], 'additionalProperties': False}}},
            'stream': True, 'max_output_tokens': 2400}


def no_network(*args, **kwargs):
    raise AssertionError('The local bound must not call the provider.')


class LocalBoundTests(unittest.TestCase):
    def setUp(self):
        self.client = SimpleNamespace(key='PRIVATE-KEY-CANARY', model='gpt-6.2-sol')

    def test_default_mode_still_asks_the_provider(self):
        calls = []
        def transport(request, **kwargs):
            calls.append(request)
            return io.BytesIO(b'{"object":"response.input_tokens","input_tokens":123}')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(PREFLIGHT_ENV, None)
            with patch('provider_tokens.urlopen', side_effect=transport):
                self.assertEqual(count_input_tokens(self.client, payload()), 123)
        self.assertEqual(len(calls), 1)

    def test_local_bound_makes_no_network_call(self):
        with patch.dict(os.environ, {PREFLIGHT_ENV: 'local_bound'}), \
                patch('provider_tokens.urlopen', side_effect=no_network):
            self.assertTrue(uses_local_bound(self.client))
            self.assertEqual(count_input_tokens(self.client, payload()), local_input_bound(payload()))

    def test_bound_covers_every_text_byte_including_non_ascii(self):
        # Byte-level tokenizers emit at most one token per UTF-8 byte of text.
        cases = [payload(), payload(content='Ñandú café 65 años — “quoted” ✓ 🙂' * 200),
                 payload(content=json.dumps({'reports': [{'quote': 'I retire in June'}] * 300}),
                         instructions='Rules. ' * 2000)]
        for case in cases:
            text_bytes = (len(case['instructions'].encode()) + len(case['input'][0]['content'].encode())
                          + len(json.dumps(case['text']).encode()))
            self.assertGreaterEqual(local_input_bound(case), text_bytes + 512)

    def test_bound_does_not_change_the_request(self):
        before = payload('Some text')
        snapshot = json.dumps(before, sort_keys=True)
        local_input_bound(before)
        self.assertEqual(json.dumps(before, sort_keys=True), snapshot)

    def test_client_with_its_own_counter_keeps_the_exact_count(self):
        counted = SimpleNamespace(key='x', model='claude-opus-5-5', count=lambda body: 77)
        with patch.dict(os.environ, {PREFLIGHT_ENV: 'local_bound'}), \
                patch('provider_tokens.urlopen', side_effect=no_network):
            self.assertFalse(uses_local_bound(counted))
            self.assertEqual(count_input_tokens(counted, payload()), 77)

    def test_unknown_mode_fails_closed_without_a_network_call(self):
        with patch.dict(os.environ, {PREFLIGHT_ENV: 'guess'}), \
                patch('provider_tokens.urlopen', side_effect=no_network):
            with self.assertRaises(TokenCountUnavailable):
                count_input_tokens(self.client, payload())


class StageMetricTests(unittest.TestCase):
    def record(self, response, counted=None):
        agent = SimpleNamespace(local=SimpleNamespace(stream_status={'first_text_ms': 900},
            request_sizes={'counted_input_tokens': counted} if counted is not None else None))
        started = time.perf_counter()
        NaturalAgent.record_model_request(agent, payload(), started, started, response)
        return agent.local.model_stages[-1]

    def test_thinking_tokens_and_reserved_ceiling_are_recorded(self):
        row = self.record({'usage': {'input_tokens': 10, 'output_tokens': 300,
            'input_tokens_details': {'cached_tokens': 0},
            'output_tokens_details': {'reasoning_tokens': 120}}}, counted=4000)
        self.assertEqual(row['reasoning_tokens'], 120)
        self.assertEqual(row['output_tokens'], 300)
        self.assertEqual(row['reserved_input_tokens'], 4000)

    def test_missing_details_stay_empty_and_never_carry_text(self):
        row = self.record({'usage': {'input_tokens': 10, 'output_tokens': 5}})
        self.assertIsNone(row['reasoning_tokens'])
        self.assertIsNone(row['reserved_input_tokens'])
        self.assertNotIn('Fictional text.', json.dumps(row))


if __name__ == '__main__':
    unittest.main()
