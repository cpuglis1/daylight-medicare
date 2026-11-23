"""The one-call model loop. Offline: scripted transport, temporary ledger, fictional text."""
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _paths

from ai_budget import BudgetError, DailyBudget
from chat import ModelUnavailable, ResponsesClient
from guest_profiles import ProfileError
import model_router
from natural_agent import NaturalAgent
import provider_tokens
import provider_transport

import one_call_agent
from one_call_agent import OneCallAgent

ADVISOR = _paths.ADVISOR
RESPONSES = 'https://api.openai.com/v1/responses'
HEADERS = (('Authorization', 'Bearer FICTIONAL-KEY'), ('Content-type', 'application/json'))
INSTRUCTIONS = 'Fictional fixed instructions for the test. CANARY-INSTRUCTIONS'
INPUT = json.dumps({'transcript': [{'role': 'person', 'text': 'CANARY-MESSAGE from a fictional person'}]})
TOOLS = [
    {'type': 'function', 'name': 'save_note', 'description': 'Save a fictional note.', 'strict': True,
     'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['note'],
                    'properties': {'note': {'type': 'string'}}}},
    {'type': 'function', 'name': 'get_dates', 'description': 'Return fictional dates.', 'strict': True,
     'parameters': {'type': 'object', 'additionalProperties': False, 'required': [], 'properties': {}}},
]
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['reply_blocks', 'pause'],
          'properties': {'reply_blocks': {'type': 'array', 'items': {'type': 'string'}},
                         'pause': {'type': 'boolean'}}}
REPLY = {'reply_blocks': ['A fictional reply. CANARY-REPLY'], 'pause': False}


def completed(output, **changes):
    response = {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                          'input_tokens_details': {'cached_tokens': 0}},
                'output': output}
    response.update(changes)
    return response


def message(value):
    text = value if isinstance(value, str) else json.dumps(value)
    return {'type': 'message', 'id': 'msg_1', 'role': 'assistant',
            'content': [{'type': 'output_text', 'text': text}]}


def call(call_id, name, arguments, **extra):
    return {'type': 'function_call', 'id': 'fc_' + call_id, 'call_id': call_id, 'name': name,
            'arguments': arguments if isinstance(arguments, str) else json.dumps(arguments), **extra}


class Runner:
    def __init__(self, during=None):
        self.calls = []
        self.during = during

    def run(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if self.during:
            self.during()
        return {'ok': True, 'tool': name, 'number': len(self.calls)}


class OneCallAgentTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.counted = []
        self.script = []

        def transport(payload):
            self.sent.append(copy.deepcopy(payload))
            step = self.script.pop(0)
            if isinstance(step, BaseException):
                raise step
            return copy.deepcopy(step)

        def count(client, payload):
            self.counted.append(copy.deepcopy(payload))
            return 300

        self.base = NaturalAgent(json.loads((ADVISOR/'web/guide-contract.json').read_text()),
            json.loads((ADVISOR/'web/teaching-facts.json').read_text()),
            client=ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport),
            enabled=True, max_calls=None, count_tokens=count, reasoning_effort='low')
        self.agent = self.make()
        self.runner = Runner()

    def make(self, **options):
        return OneCallAgent(self.base, **{'tools': TOOLS, 'reply_schema': SCHEMA, 'schema_name': 'fictional_reply', **options})

    def ledger(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name)
        path.chmod(0o700)
        rates = json.loads((_paths.REPO/'alternatives/chat-first/cms-slice/config/ai-pricing.json').read_text())
        rates['verified_at'] = '2026-10-30T00:00:00Z'
        rates['valid_until'] = '2026-11-04T00:00:00Z'
        pricing = path/'pricing.json'
        pricing.write_text(json.dumps(rates))
        self.base.budget = DailyBudget(path/'usage.sqlite3', pricing_path=pricing,
            clock=lambda: datetime(2026, 10, 30, 16, tzinfo=timezone.utc).timestamp())
        return self.base.budget

    def rows(self, budget):
        with budget.db() as db:
            return sorted(row[0] for row in db.execute('SELECT status FROM ai_charges'))

    def turn(self, agent=None, runner=None, stages=('extract', 'compose'), **changes):
        arguments = {'instructions': INSTRUCTIONS, 'input_text': INPUT, 'runner': runner or self.runner,
                     'request_id': str(uuid.uuid4()), **changes}
        with self.base.reserve_turn(stages) as reservation:
            self.reservation = reservation
            return (agent or self.agent).reply('owner', reservation=reservation, **arguments)

    def test_importing_the_agent_does_not_import_the_sibling_modules(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import one_call_agent; '
                'print(sorted({"one_call_tools", "one_call_prompt", "one_call_check"} & set(sys.modules)))')
        done = subprocess.run([sys.executable, '-c', code, str(_paths.HERE)], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        self.assertEqual(done.stdout.strip(), '[]')

    def test_turn_without_tools_makes_one_request_and_releases_the_second_stage(self):
        budget = self.ledger()
        self.script = [completed([message(REPLY)])]
        out = self.turn()
        self.assertEqual(out, {'reply': REPLY, 'requests': 1, 'tool_calls': 0})
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(len(self.sent), 1)
        sent = self.sent[0]
        self.assertEqual(sent['model'], 'gpt-5.4')
        self.assertEqual(sent['instructions'], INSTRUCTIONS)
        self.assertEqual(sent['input'], [{'role': 'user', 'content': INPUT}])
        self.assertEqual(sent['tools'], TOOLS)
        self.assertEqual(sent['tool_choice'], 'auto')
        self.assertEqual(sent['text'], {'format': {'type': 'json_schema', 'name': 'fictional_reply',
                                                   'strict': True, 'schema': SCHEMA}})
        self.assertIs(sent['store'], False)
        self.assertIs(sent['stream'], True)
        self.assertEqual(sent['max_output_tokens'], 900)
        self.assertEqual(sent['reasoning'], {'effort': 'low'})
        self.assertEqual(sent['include'], ['reasoning.encrypted_content'])
        self.assertEqual(sent['service_tier'], 'default')
        self.assertFalse(set(sent) & set(model_router.OPENAI_STATEFUL))
        # The funded count is of the request exactly as sent.
        self.assertEqual(self.counted, self.sent)
        self.assertEqual(self.rows(budget), ['cancelled', 'settled'])
        self.assertEqual(self.reservation.stage('extract').status, 'settled')
        self.assertEqual(self.reservation.stage('compose').status, 'released')
        self.assertEqual(self.reservation.trace_usage(),
                         {'settled_nano_usd': 300*2500 + 70*15000, 'unresolved_attempts': 0})
        self.assertIsNone(self.base.local.last_composition_error)

    def test_tool_turn_makes_two_requests_and_resends_the_whole_input(self):
        budget = self.ledger()
        self.script = [completed([call('call_a', 'save_note', {'note': 'CANARY-ARGUMENT'}),
                                  call('call_b', 'get_dates', {})]),
                       completed([message(REPLY)])]
        out = self.turn()
        self.assertEqual(out, {'reply': REPLY, 'requests': 2, 'tool_calls': 2})
        self.assertEqual(self.runner.calls, [('save_note', {'note': 'CANARY-ARGUMENT'}), ('get_dates', {})])
        self.assertEqual(len(self.sent), 2)
        first, second = self.sent
        self.assertEqual(first['tool_choice'], 'auto')
        self.assertEqual(second['tool_choice'], 'none')
        self.assertNotIn('include', second)
        for key in ('model', 'instructions', 'tools', 'text', 'store', 'max_output_tokens', 'reasoning'):
            self.assertEqual(second[key], first[key], key)
        self.assertEqual(second['input'], [
            {'role': 'user', 'content': INPUT},
            {'type': 'function_call', 'call_id': 'call_a', 'name': 'save_note',
             'arguments': json.dumps({'note': 'CANARY-ARGUMENT'})},
            {'type': 'function_call', 'call_id': 'call_b', 'name': 'get_dates', 'arguments': '{}'},
            {'type': 'function_call_output', 'call_id': 'call_a',
             'output': json.dumps({'ok': True, 'tool': 'save_note', 'number': 1}, separators=(',', ':'))},
            {'type': 'function_call_output', 'call_id': 'call_b',
             'output': json.dumps({'ok': True, 'tool': 'get_dates', 'number': 2}, separators=(',', ':'))}])
        self.assertFalse(set(second) & set(model_router.OPENAI_STATEFUL))
        self.assertEqual(self.counted, self.sent)
        self.assertEqual(self.rows(budget), ['settled', 'settled'])
        self.assertEqual([self.reservation.stage(name).attempts for name in ('extract', 'compose')], [1, 1])
        self.assertEqual(self.reservation.trace_usage()['unresolved_attempts'], 0)
        with budget.db() as db:
            self.assertIsNone(db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone())

    def test_a_message_beside_tool_calls_is_not_taken_as_the_reply(self):
        self.script = [completed([message({'reply_blocks': ['early'], 'pause': True}), call('call_a', 'get_dates', {})]),
                       completed([message(REPLY)])]
        out = self.turn()
        self.assertEqual(out['reply'], REPLY)
        self.assertEqual([item.get('type', 'user') for item in self.sent[1]['input']],
                         ['user', 'function_call', 'function_call_output'])

    def test_encrypted_reasoning_items_are_carried_in_order(self):
        self.script = [completed([{'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'FICTIONAL-OPAQUE',
                                   'status': 'completed'},
                                  call('call_a', 'get_dates', {}, status='completed')]),
                       completed([message(REPLY)])]
        self.assertEqual(self.turn()['requests'], 2)
        self.assertEqual(self.sent[1]['input'][1:], [
            {'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'FICTIONAL-OPAQUE'},
            {'id': 'fc_call_a', 'type': 'function_call', 'call_id': 'call_a', 'name': 'get_dates', 'arguments': '{}'},
            {'type': 'function_call_output', 'call_id': 'call_a',
             'output': json.dumps({'ok': True, 'tool': 'get_dates', 'number': 1}, separators=(',', ':'))}])

    def test_reasoning_without_encrypted_content_is_left_out(self):
        self.script = [completed([{'type': 'reasoning', 'id': 'rs_1', 'summary': []}, call('call_a', 'get_dates', {})]),
                       completed([message(REPLY)])]
        self.assertEqual(self.turn()['requests'], 2)
        items = self.sent[1]['input']
        self.assertEqual([item.get('type', 'user') for item in items], ['user', 'function_call', 'function_call_output'])
        self.assertNotIn('id', items[1])

    def test_no_reasoning_setting_requests_no_encrypted_reasoning(self):
        self.script = [completed([message(REPLY)])]
        self.turn(self.make(reasoning_effort='none'))
        self.assertEqual(self.sent[0]['reasoning'], {'effort': 'none'})
        self.assertNotIn('include', self.sent[0])

    def test_bad_tool_arguments_return_an_error_output_without_raising(self):
        self.script = [completed([call('call_a', 'save_note', '{"note": '), call('call_b', 'save_note', '[1]'),
                                  call('call_c', 'get_dates', {})]),
                       completed([message(REPLY)])]
        out = self.turn()
        self.assertEqual(out, {'reply': REPLY, 'requests': 2, 'tool_calls': 3})
        self.assertEqual(self.runner.calls, [('get_dates', {})])
        outputs = [item for item in self.sent[1]['input'] if item.get('type') == 'function_call_output']
        self.assertEqual([item['call_id'] for item in outputs], ['call_a', 'call_b', 'call_c'])
        self.assertEqual([json.loads(item['output']) for item in outputs],
                         [{'ok': False, 'error': 'bad_arguments'}, {'ok': False, 'error': 'bad_arguments'},
                          {'ok': True, 'tool': 'get_dates', 'number': 1}])

    def test_calls_beyond_the_bound_are_answered_but_not_run(self):
        self.script = [completed([call('call_a', 'get_dates', {}), call('call_b', 'get_dates', {})]),
                       completed([message(REPLY)])]
        out = self.turn(self.make(max_tool_calls=1))
        self.assertEqual(out['tool_calls'], 2)
        self.assertEqual(len(self.runner.calls), 1)
        self.assertEqual(json.loads(self.sent[1]['input'][-1]['output']), {'ok': False, 'error': 'too_many_calls'})

    def test_second_response_that_calls_a_tool_again_raises(self):
        budget = self.ledger()
        self.script = [completed([call('call_a', 'get_dates', {})]),
                       completed([call('call_b', 'get_dates', {}), message(REPLY)])]
        with self.assertRaises(ModelUnavailable) as caught:
            self.turn()
        self.assertEqual(str(caught.exception), 'The conversational response could not be checked.')
        self.assertEqual(self.base.local.last_composition_error, 'invalid_structure')
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(len(self.runner.calls), 1)
        self.assertEqual(self.rows(budget), ['settled', 'settled'])

    def test_final_text_that_is_not_the_reply_object_raises(self):
        budget = self.ledger()
        for text in ('not json', json.dumps(['a list']), json.dumps({'reply_blocks': ['no pause key']}), ''):
            self.script = [completed([message(text)])]
            with self.assertRaises(ModelUnavailable) as caught:
                self.turn()
            self.assertEqual(str(caught.exception), 'The conversational response could not be checked.')
            self.assertEqual(self.base.local.last_composition_error, 'invalid_structure')
        self.assertEqual(len(self.sent), 4)
        self.assertEqual(self.rows(budget), ['cancelled'] * 4 + ['settled'] * 4)

    def test_incomplete_or_failed_response_raises_and_its_stage_stays_held(self):
        budget = self.ledger()
        for status in ('incomplete', 'failed'):
            self.script = [completed([], status=status, incomplete_details={'reason': 'max_output_tokens'})]
            with self.assertRaises(ModelUnavailable) as caught:
                self.turn()
            self.assertEqual(str(caught.exception), 'The model could not finish. Accepted details are preserved.')
            self.assertEqual(self.base.local.provider_failure['event'], 'response.' + status)
        self.assertEqual(len(self.sent), 2)
        # As in advisor-first, an issued request without verified usage is never refunded.
        self.assertEqual(self.rows(budget), ['cancelled', 'cancelled', 'uncertain', 'uncertain'])

    def test_incomplete_second_response_raises_after_the_tool_round(self):
        budget = self.ledger()
        self.script = [completed([call('call_a', 'get_dates', {})]),
                       completed([], status='incomplete', incomplete_details={'reason': 'max_output_tokens'})]
        with self.assertRaises(ModelUnavailable):
            self.turn()
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.rows(budget), ['settled', 'uncertain'])

    def test_incomplete_response_with_usage_is_settled_for_the_newer_models(self):
        # advisor-first settles a reported incomplete response for models other than gpt-5.4.
        self.base.client.model = 'gpt-6.1-sol'
        self.script = [completed([], status='incomplete', model='gpt-6.1-sol',
                                 incomplete_details={'reason': 'max_output_tokens'})]
        with self.assertRaises(ModelUnavailable):
            self.turn()
        self.assertEqual(self.sent[0]['max_output_tokens'], 2400)
        self.assertEqual(self.reservation.stage('extract').status, 'settled')
        self.assertEqual(self.base.local.provider_failure['incomplete_reason'], 'max_output_tokens')

    def test_transport_failure_is_reported_by_category_and_not_retried(self):
        budget = self.ledger()
        self.script = [TimeoutError('fictional interruption CANARY-ERROR')]
        with self.assertLogs('one_call_agent', level='WARNING') as logs:
            with self.assertRaises(ModelUnavailable) as caught:
                self.turn()
        self.assertEqual(str(caught.exception),
                         'Daylight could not finish the conversational response. Your accepted details are preserved.')
        self.assertEqual(self.base.local.last_composition_error, 'transport_or_format')
        self.assertEqual(self.base.local.last_transport_failure, {'exception': 'TimeoutError', 'phase': 'stream'})
        self.assertNotIn('CANARY', '\n'.join(logs.output))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.rows(budget), ['cancelled', 'uncertain'])

    def test_request_over_the_byte_bound_is_not_sent(self):
        budget = self.ledger()
        with self.assertRaises(ModelUnavailable) as caught:
            self.turn(self.make(max_request_bytes=500))
        self.assertEqual(str(caught.exception), 'This response context exceeds the reviewed request bounds.')
        self.assertEqual(self.base.local.last_composition_error, 'input_bound')
        self.assertEqual((self.sent, self.counted), ([], []))
        self.assertEqual(self.rows(budget), ['cancelled', 'cancelled'])

    def test_byte_bound_defaults_to_the_existing_limit_and_covers_the_second_request(self):
        self.assertEqual(self.agent._limit(), 96_000)
        budget = self.ledger()
        first = len(json.dumps(self.agent._payload(INSTRUCTIONS, [{'role': 'user', 'content': INPUT}], 'auto', 900,
                                                   include=True)).encode())
        self.script = [completed([call('call_a', 'save_note', {'note': 'x' * 400})])]
        with self.assertRaises(ModelUnavailable):
            self.turn(self.make(max_request_bytes=first + 100))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.rows(budget), ['cancelled', 'settled'])

    def test_missing_second_stage_stops_before_any_tool_runs(self):
        self.script = [completed([call('call_a', 'save_note', {'note': 'fictional'})])]
        with self.assertRaises(BudgetError):
            self.turn(stages=('extract',))
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(len(self.sent), 1)

    def test_token_count_over_the_allowance_starts_no_request(self):
        budget = self.ledger()
        self.base.count_tokens = lambda *_: 1_000_000
        with self.assertRaises(BudgetError):
            self.turn()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.rows(budget), ['cancelled', 'cancelled'])

    def test_reservation_from_another_budget_is_refused(self):
        self.ledger()
        with self.base.reserve_turn() as reservation:
            self.ledger()
            with self.assertRaises(BudgetError):
                self.agent.reply('owner', instructions=INSTRUCTIONS, input_text=INPUT, runner=self.runner,
                                 request_id='r1', reservation=reservation)
        self.assertEqual(self.sent, [])

    def test_zero_tool_rounds_sends_one_request_that_must_answer(self):
        self.script = [completed([message(REPLY)])]
        self.assertEqual(self.turn(self.make(max_tool_rounds=0))['requests'], 1)
        self.assertEqual(self.sent[0]['tool_choice'], 'none')
        self.assertNotIn('include', self.sent[0])
        with self.assertRaises(ValueError):
            self.make(max_tool_rounds=2)

    def test_only_function_tools_and_reviewed_openai_models_are_used(self):
        with self.assertRaises(ValueError):
            self.make(tools=[{'type': 'web_search'}])
        self.base.client.model = 'claude-opus-5-5'
        with self.assertRaises(ModelUnavailable):
            self.turn()
        self.base.client.model = 'fictional-model'
        with self.assertRaises(ModelUnavailable):
            self.turn()
        self.assertEqual(self.sent, [])

    def test_same_request_cannot_run_twice_at_once(self):
        seen = []

        def again():
            with self.assertRaises(ProfileError) as caught:
                self.agent.reply('owner', instructions=INSTRUCTIONS, input_text=INPUT, runner=Runner(),
                                 request_id='same', reservation=self.reservation)
            seen.append(caught.exception.code)

        self.script = [completed([call('call_a', 'get_dates', {})]), completed([message(REPLY)])]
        self.turn(runner=Runner(again), request_id='same')
        self.assertEqual(seen, [409])
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.agent.active, set())

    def test_both_payloads_pass_the_development_route_check(self):
        self.script = [completed([{'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'FICTIONAL-OPAQUE'},
                                  call('call_a', 'save_note', {'note': 'fictional'})]),
                       completed([message(REPLY)])]
        self.turn()
        self.assertEqual(len(self.sent), 2)
        with patch.dict(os.environ, {model_router.ENVIRONMENT_VARIABLE: 'development'}):
            for payload in self.sent:
                allowed = model_router.authorize(RESPONSES, HEADERS, payload)
                self.assertEqual(allowed.route, 'development-openai')
                self.assertEqual(allowed.url, RESPONSES)
                self.assertFalse(allowed.changed)
                self.assertEqual(allowed.body, payload)
                # The token counter reads these keys from the same payload.
                self.assertGreater(provider_tokens.local_input_bound(payload), 0)
            # The check is live: chaining by id would be refused.
            with self.assertLogs('model_router', level='WARNING'):
                with self.assertRaises(model_router.RouteBlocked):
                    model_router.authorize(RESPONSES, HEADERS, {**self.sent[1], 'previous_response_id': 'resp_1'})

    def test_streamed_tool_turn_goes_through_the_existing_sender_and_its_presend_checks(self):
        # No scripted transport: the base agent's own stream reader runs, with
        # the curl transport replaced by fictional event lines.
        budget = self.ledger()
        self.base.client.transport = None
        requests = []
        streams = [
            [{'type': 'response.created', 'response': {'status': 'in_progress'}},
             {'type': 'response.output_item.done', 'item': call('call_a', 'save_note', {'note': 'fictional'})},
             {'type': 'response.completed', 'response': completed([
                 {'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'FICTIONAL-OPAQUE'},
                 call('call_a', 'save_note', {'note': 'fictional'})])}],
            [{'type': 'response.output_text.delta', 'delta': json.dumps(REPLY)},
             {'type': 'response.completed', 'response': completed([message(REPLY)])}],
        ]

        @contextmanager
        def fake_urlopen(request, timeout=40):
            requests.append(request)
            events = streams.pop(0)
            yield iter([b'event: fictional\n', *[b'data: ' + json.dumps(event).encode() + b'\n' for event in events],
                        b'data: [DONE]\n'])

        with patch('natural_agent.urlopen', fake_urlopen):
            out = self.turn()
        self.assertEqual(out, {'reply': REPLY, 'requests': 2, 'tool_calls': 1})
        self.assertEqual(self.runner.calls, [('save_note', {'note': 'fictional'})])
        self.assertEqual(self.rows(budget), ['settled', 'settled'])
        self.assertEqual([request.full_url for request in requests], [RESPONSES, RESPONSES])
        second = json.loads(requests[1].data)
        self.assertEqual(second['tool_choice'], 'none')
        self.assertEqual([item.get('type', 'user') for item in second['input']],
                         ['user', 'reasoning', 'function_call', 'function_call_output'])
        self.assertEqual({item['call_id'] for item in second['input'][2:]}, {'call_a'})
        # The transport's own checks (identifier backstop and route list) accept both bodies.
        with patch.dict(os.environ, {model_router.ENVIRONMENT_VARIABLE: 'development'}):
            for request in requests:
                configuration = provider_transport._configuration(request).decode()
                self.assertIn('url = "' + RESPONSES + '"', configuration)

    def test_logs_carry_counts_only(self):
        self.script = [completed([call('call_a', 'save_note', {'note': 'CANARY-ARGUMENT'})]),
                       completed([message(REPLY)])]
        with self.assertLogs('one_call_agent', level='DEBUG') as logs:
            self.turn()
        self.assertEqual(logs.output, ['INFO:one_call_agent:Daylight one-call tool round calls=1 reasoning_items=0'])

    def test_request_metrics_are_recorded_without_text(self):
        self.base.local.model_stages = []
        self.script = [completed([call('call_a', 'get_dates', {})]), completed([message(REPLY)])]
        self.turn()
        rows = self.base.local.model_stages
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['issued'] and row['input_tokens'] == 300 for row in rows))
        self.assertNotIn('CANARY', json.dumps(rows))


if __name__ == '__main__':
    unittest.main()
