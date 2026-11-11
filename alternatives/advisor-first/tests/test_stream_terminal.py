"""Terminal provider events finish each paid stage without another stream read."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_agent as fixtures
from chat import ModelUnavailable


def event(value):
    return b'data: ' + json.dumps(value).encode() + b'\n'


class ScriptedStream:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        self.reads += 1
        line = next(self.lines)
        if isinstance(line, BaseException):
            raise line
        return line


class StreamTerminalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NaturalAgentTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def run_stage(self, stage, lines):
        fixture = self.fixture
        agent = fixture.agent
        agent.budget = fixture.ledger()
        agent.client.transport = None
        stream = ScriptedStream(lines)
        target = 'narrative_agent.urlopen' if stage == 'extract' else 'natural_agent.urlopen'
        with patch(target, return_value=stream) as request:
            with agent.reserve_turn() as reservation:
                if stage == 'extract':
                    result = agent.extract('owner', 'I am retired.', fixture.g, {},
                                           str(uuid.uuid4()), reservation)
                else:
                    result = agent.compose('owner', fixture.context, fixture.moves,
                                           str(uuid.uuid4()), reservation)
        self.assertEqual(request.call_count, 1)
        with agent.budget.db() as db:
            statuses = sorted(row[0] for row in db.execute('SELECT status FROM ai_charges'))
        self.assertEqual(statuses, ['cancelled', 'settled'])
        self.assertEqual(len(agent.usage), 1)
        return result, stream

    def answer(self, stage):
        return (self.fixture.extraction([]) if stage == 'extract'
                else self.fixture.composition())

    def completed(self, stage, *, canonical=True):
        response = {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70,
                              'total_tokens': 370,
                              'input_tokens_details': {'cached_tokens': 0}}}
        if canonical:
            response['output'] = [{'content': [
                {'type': 'output_text', 'text': json.dumps(self.answer(stage))}]}]
        return event({'type': 'response.completed', 'response': response})

    def test_completion_stops_before_done_or_a_trailing_connection_failure(self):
        for stage in ('extract', 'compose'):
            for tail in (b'data: [DONE]\n', ConnectionResetError('private transport canary')):
                with self.subTest(stage=stage, tail=type(tail).__name__):
                    self.setUp()
                    _, stream = self.run_stage(stage, [self.completed(stage), tail])
                    self.assertEqual(stream.reads, 1)
                    self.assertEqual(self.fixture.agent.local.stream_status,
                                     {'terminal': True, 'delta_events': 0,
                                      'text_chars': len(json.dumps(self.answer(stage)))})

    def test_canonical_output_replaces_partial_deltas(self):
        for stage in ('extract', 'compose'):
            with self.subTest(stage=stage):
                self.setUp()
                result, stream = self.run_stage(stage, [
                    event({'type': 'response.output_text.delta', 'delta': '{"partial":'}),
                    self.completed(stage)])
                self.assertEqual(stream.reads, 2)
                self.assertIsInstance(result, dict)
                self.assertEqual(self.fixture.agent.local.stream_status['delta_events'], 1)

    def test_delta_output_remains_supported_without_canonical_output(self):
        for stage in ('extract', 'compose'):
            with self.subTest(stage=stage):
                self.setUp()
                result, _ = self.run_stage(stage, [
                    event({'type': 'response.output_text.delta',
                           'delta': json.dumps(self.answer(stage))}),
                    self.completed(stage, canonical=False)])
                self.assertIsInstance(result, dict)

    def test_done_without_completion_and_incomplete_events_still_fail(self):
        for stage in ('extract', 'compose'):
            for terminal in (b'data: [DONE]\n', event({'type': 'response.incomplete',
                    'response': {'status': 'incomplete',
                                 'incomplete_details': {'reason': 'max_output_tokens'}}})):
                with self.subTest(stage=stage, terminal=terminal[:40]):
                    self.setUp()
                    with self.assertRaises(ModelUnavailable):
                        self.run_stage(stage, [terminal])
                    with self.fixture.agent.budget.db() as db:
                        statuses = sorted(row[0] for row in db.execute('SELECT status FROM ai_charges'))
                    self.assertEqual(statuses, ['cancelled', 'uncertain'])
                    self.assertEqual(self.fixture.agent.calls, 1)

    def test_canonical_output_keeps_the_existing_text_bound(self):
        terminal = event({'type': 'response.completed', 'response': {
            'output': [{'content': [{'type': 'output_text', 'text': 'x' * 20001}]}]}})
        for stage in ('extract', 'compose'):
            with self.subTest(stage=stage):
                self.setUp()
                with self.assertRaisesRegex(ModelUnavailable, 'exceeded'):
                    self.run_stage(stage, [terminal])


if __name__ == '__main__':
    unittest.main()
