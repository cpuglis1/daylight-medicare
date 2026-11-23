"""The one-call model loop: one request, at most one tool round, then the reply.

Each typed turn sends one OpenAI Responses request that carries the function
tools and a strict JSON-schema final output. If the model asks for tools, they
run here through the injected runner and one more request is sent with
``tool_choice: 'none'`` so the model must answer. A turn therefore makes at
most two requests.

Nothing in advisor-first is edited. Requests leave through the base
``NaturalAgent``'s own sender (``_complete``), so they pass the same route
check, identifier backstop, stream bounds and failure categories as today's
composition request. Budget rows are the turn reservation's two existing
stages: the first request uses ``extract`` and the second uses ``compose``.
Each request is counted, funded, issued and settled in that order; the caller
closes the reservation, which releases a stage that was never issued.

Response chaining by id is refused by the route check, so the second request
resends the whole input: the user item, the model's function calls (with any
encrypted reasoning items the first response returned) and one output per call.

Logs and diagnostics carry counts and fixed categories only, never text.
"""
import copy
import json
import logging
from ssl import SSLError
import threading
import time
from urllib.error import HTTPError, URLError

import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

from advisor_models import MODELS
from ai_budget import BudgetError
from chat import ModelUnavailable
from composition_recovery import VALIDATION_CODES
from guest_profiles import ProfileError
from log_guard import install as install_log_guard
from narrative_agent import provider_failure_diagnostic, provider_failure_message
from provider_tokens import TokenCountUnavailable
from transport_diagnostics import failure_details

LOGGER = logging.getLogger(__name__)
install_log_guard((__name__,))  # advisor-first's last-line identifier filter, on this logger too

# advisor-first's existing fixed messages; the conversation layer maps them to codes.
UNAVAILABLE = 'Live composition is unavailable. Your accepted details remain available.'
UNCHECKED = 'The conversational response could not be checked.'
FORMAT_MISMATCH = 'The provider reply did not match the response format.'
UNFINISHED = 'Daylight could not finish the conversational response. Your accepted details are preserved.'
CALL_LIMIT = 'The configured live-request budget is reached. Manual guidance remains available.'
OTHER_BUDGET = 'The composition reservation belongs to another budget.'
REQUEST_BOUND = 'This response context exceeds the reviewed request bounds.'
CODES = {**VALIDATION_CODES, REQUEST_BOUND: 'input_bound'}

FIRST_STAGE, SECOND_STAGE = 'extract', 'compose'
ENCRYPTED_REASONING = 'reasoning.encrypted_content'
BAD_ARGUMENTS = {'ok': False, 'error': 'bad_arguments'}
TOO_MANY_CALLS = {'ok': False, 'error': 'too_many_calls'}


def function_calls(response):
    """The function_call items of a response, in output order."""
    output = response.get('output', [])
    if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
        raise ModelUnavailable(UNCHECKED)
    calls = [item for item in output if item.get('type') == 'function_call']
    for call in calls:
        if (not isinstance(call.get('call_id'), str) or not call['call_id']
                or not isinstance(call.get('name'), str) or not call['name']):
            raise ModelUnavailable(UNCHECKED)
    return calls


def carried_items(response):
    """What the second request must resend from the first response.

    With ``store: False`` the provider keeps nothing, so a reasoning item can be
    passed back only with its encrypted content. When every reasoning item has
    it, reasoning and function calls go back as returned, ids included, in
    their original order. Otherwise reasoning is left out and the function
    calls go back without their item ids, so none refers to an item the
    provider cannot find. Message items are not carried: the second request
    writes the whole reply.
    """
    output = response.get('output', [])
    reasoning = [item for item in output if item.get('type') == 'reasoning']
    keep = bool(reasoning) and all(
        isinstance(item.get('encrypted_content'), str) and item['encrypted_content']
        and isinstance(item.get('id'), str) for item in reasoning)
    items = []
    for item in output:
        if item.get('type') == 'reasoning' and keep:
            summary = item.get('summary')
            items.append({'type': 'reasoning', 'id': item['id'],
                          'summary': copy.deepcopy(summary) if isinstance(summary, list) else [],
                          'encrypted_content': item['encrypted_content']})
        elif item.get('type') == 'function_call':
            arguments = item.get('arguments')
            call = {'type': 'function_call', 'call_id': item['call_id'], 'name': item['name'],
                    'arguments': arguments if isinstance(arguments, str) else ''}
            if keep and isinstance(item.get('id'), str):
                call = {'id': item['id'], **call}
            items.append(call)
    return items, sum(1 for item in items if item['type'] == 'reasoning')


class OneCallAgent:
    """One request per turn, with at most one tool round.

    ``base`` is advisor-first's NaturalAgent: its client, budget, token counter,
    reasoning effort and sender are used as they are. ``tools``, ``reply_schema``
    and ``schema_name`` default to the variant's own modules, loaded on first use.
    """

    def __init__(self, base, *, max_tool_rounds=1, tools=None, reply_schema=None, schema_name=None,
                 max_request_bytes=None, reasoning_effort=None, max_tool_calls=8,
                 prompt_cache_key='daylight-one-call-v1'):
        # The turn reservation has two stage names, so there is one tool round at most.
        if max_tool_rounds not in (0, 1):
            raise ValueError('Use zero or one tool round.')
        if type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 32:
            raise ValueError('Use a bounded number of tool calls.')
        if reasoning_effort not in (None, 'none', 'low', 'medium'):
            raise ValueError('Unsupported reasoning setting.')
        if max_request_bytes is not None and (type(max_request_bytes) is not int or max_request_bytes < 1):
            raise ValueError('Use a positive request bound.')
        if prompt_cache_key is not None and (not isinstance(prompt_cache_key, str) or not 1 <= len(prompt_cache_key) <= 64):
            raise ValueError('Use a short fixed cache key.')
        self.base = base
        self.max_tool_rounds = max_tool_rounds
        self.max_tool_calls = max_tool_calls
        self.max_request_bytes = max_request_bytes
        self.reasoning_effort = reasoning_effort
        self.prompt_cache_key = prompt_cache_key
        self.tools = self._checked_tools(tools) if tools is not None else None
        self.reply_schema = copy.deepcopy(reply_schema)
        self.schema_name = schema_name
        self.lock = threading.Lock()
        self.active = set()

    @staticmethod
    def _checked_tools(tools):
        # The route check refuses anything but client-side function tools.
        if not isinstance(tools, list) or any(
                not isinstance(tool, dict) or tool.get('type') != 'function'
                or not isinstance(tool.get('name'), str) or not tool['name'] for tool in tools):
            raise ValueError('Use Responses API function tools.')
        return copy.deepcopy(tools)

    def _load_defaults(self):
        # Sibling modules are imported here, never when this module is imported.
        if self.tools is None:
            import one_call_tools
            self.tools = self._checked_tools(one_call_tools.TOOLS)
        if self.reply_schema is None or self.schema_name is None:
            import one_call_prompt
            if self.reply_schema is None:
                self.reply_schema = copy.deepcopy(one_call_prompt.REPLY_SCHEMA)
            if self.schema_name is None:
                self.schema_name = one_call_prompt.REPLY_SCHEMA_NAME
        if not isinstance(self.reply_schema, dict) or not isinstance(self.schema_name, str) or not self.schema_name:
            raise ValueError('Use a JSON schema and a schema name for the reply.')

    def _limit(self):
        return self.max_request_bytes or self.base.max_input_bytes

    def _effort(self):
        return self.reasoning_effort or getattr(self.base, 'reasoning_effort', 'low')

    def _payload(self, instructions, items, tool_choice, output_limit, *, include):
        client = self.base.client
        payload = {'model': client.model, 'instructions': instructions, 'input': items,
                   'store': False, 'max_output_tokens': output_limit,
                   'reasoning': {'effort': self._effort()},
                   'tools': copy.deepcopy(self.tools), 'tool_choice': tool_choice,
                   'text': {'format': {'type': 'json_schema', 'name': self.schema_name, 'strict': True,
                                       'schema': copy.deepcopy(self.reply_schema)}},
                   'stream': True, 'service_tier': getattr(client, 'service_tier', 'default')}
        if include:
            payload['include'] = [ENCRYPTED_REASONING]
        if self.prompt_cache_key:
            payload['prompt_cache_key'] = self.prompt_cache_key
        return payload

    def _fail(self, message):
        error = ModelUnavailable(message)
        self.base.local.last_composition_error = CODES.get(message, 'unavailable')
        return error

    def _raw(self, payload):
        raw = json.dumps(payload).encode()
        if len(raw) > self._limit():
            raise ModelUnavailable(REQUEST_BOUND)
        return raw

    def _send(self, payload, stage, output_limit):
        """Count, fund, issue, send and settle one request on its reserved stage."""
        base = self.base
        started = time.perf_counter()
        phase = 'preflight'
        issued_at = response = None
        base.local.request_sizes = None
        try:
            if stage.budget is not base.budget:
                raise BudgetError(OTHER_BUDGET)
            raw = self._raw(payload)
            if base.max_calls is not None and base.calls >= base.max_calls:
                raise ModelUnavailable(CALL_LIMIT)
            if base.budget:
                base.budget.check_rates(base.client.model)
                # The request is counted exactly as it will be sent: the tools,
                # the reply schema and every input item. Nothing is repacked.
                count = base.count_tokens(base.client, payload)
                stage.check_input(count)
                base.local.request_sizes = {'counted_input_tokens': count}
            if base.on_call:
                base.on_call(len(raw), output_limit)
            base.calls += 1
            stage.issued()
            issued_at = time.perf_counter()
            phase = 'stream'
            response, text = base._complete(payload, raw)
            if not isinstance(response, dict):
                raise TypeError('response')
            if response.get('status') != 'completed':
                diagnostic = provider_failure_diagnostic(
                    {'type': 'response.incomplete' if response.get('status') == 'incomplete' else 'response.failed',
                     'response': response})
                base.local.provider_failure = diagnostic
                base.settle_incomplete(response, stage)
                raise ModelUnavailable(provider_failure_message(diagnostic, accepted=True))
            base.usage.append(response.get('usage', {}))
            stage.settle(response)
            phase = 'decode'
            if response.get('structured_output_error'):
                raise ModelUnavailable(FORMAT_MISMATCH)
            return response, text, function_calls(response)
        except ModelUnavailable as error:
            base.local.last_composition_error = ('input_token_verification'
                if isinstance(error, TokenCountUnavailable) else CODES.get(str(error), 'unavailable'))
            if isinstance(error, TokenCountUnavailable):
                base.local.last_token_failure = copy.deepcopy(error.diagnostic)
            raise
        except (HTTPError, URLError, TimeoutError, SSLError, ConnectionError,
                json.JSONDecodeError, KeyError, TypeError) as error:
            failure = failure_details(error, phase, getattr(base.local, 'stream_status', None))
            base.local.last_composition_error = 'transport_or_format'
            base.local.last_transport_failure = failure
            LOGGER.warning('Daylight one-call transport %s', json.dumps(failure, sort_keys=True))
            raise ModelUnavailable(UNFINISHED) from error
        finally:
            log = getattr(base.local, 'one_call_usage', None)
            if isinstance(log, list) and isinstance(response, dict) and isinstance(response.get('usage'), dict):
                # Token counts for the conversation's content-free turn trace. Numbers only.
                usage = response['usage']
                details = usage.get('input_tokens_details') if isinstance(usage.get('input_tokens_details'), dict) else {}
                log.append({'input': usage.get('input_tokens'), 'cached': details.get('cached_tokens'),
                            'output': usage.get('output_tokens')})
            if hasattr(base, 'record_model_request'):
                base.record_model_request(payload, started, issued_at, response)
            # An issued request that did not settle stays held as uncertain.
            stage.finish()

    def _parse(self, text):
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            raise self._fail(UNCHECKED) from None
        required = self.reply_schema.get('required', [])
        if not isinstance(parsed, dict) or any(key not in parsed for key in required if isinstance(key, str)):
            raise self._fail(UNCHECKED)
        return parsed

    def _run_tools(self, calls, runner):
        outputs = []
        for index, call in enumerate(calls):
            if index >= self.max_tool_calls:
                result = dict(TOO_MANY_CALLS)
            else:
                try:
                    arguments = json.loads(call.get('arguments'))
                except (TypeError, ValueError):
                    arguments = None
                # Arguments that are not a JSON object never reach the runner.
                result = runner.run(call['name'], arguments) if isinstance(arguments, dict) else dict(BAD_ARGUMENTS)
            outputs.append({'type': 'function_call_output', 'call_id': call['call_id'],
                            'output': json.dumps(result, ensure_ascii=False, separators=(',', ':'))})
        return outputs

    def reply(self, owner, *, instructions, input_text, runner, request_id, reservation,
              stage=FIRST_STAGE, allow_tools=True, carry=None, carried=()):
        """Return ``{'reply': <parsed reply>, 'requests': 1|2, 'tool_calls': <int>}``.

        Raises chat.ModelUnavailable on a transport, budget, size or format
        failure. The caller closes the reservation.

        ``stage`` and ``allow_tools`` exist for the conversation's one retry
        after a rejected reply: ``stage='compose', allow_tools=False`` sends a
        single request on the turn's unused second stage with tools disabled.
        A request that may call tools always starts on the first stage, so the
        second stage is free for the request that follows the tool round.

        ``carry`` is a list this call fills with the model's tool calls and their
        results once the tools have run. ``carried`` hands such a list back on a
        retry made with tools disabled, so the retried reply is written with the
        tool results already in its input. The retry's reservation is the caller's.
        """
        if stage not in (FIRST_STAGE, SECOND_STAGE) or type(allow_tools) is not bool:
            raise ValueError('Use a reserved stage name and a boolean tool switch.')
        if stage != FIRST_STAGE and allow_tools:
            raise ValueError('A request that may call tools starts on the first stage.')
        if carried and allow_tools:
            raise ValueError('Tool results are carried into a request that cannot call tools.')
        if carry is not None and not isinstance(carry, list):
            raise ValueError('Use a list to receive the tool round.')
        base = self.base
        for name in ('last_composition_error', 'last_transport_failure', 'stream_status',
                     'provider_failure', 'last_token_failure'):
            setattr(base.local, name, None)
        if not isinstance(instructions, str) or not instructions or not isinstance(input_text, str) or not input_text:
            raise ValueError('Use the instructions and the turn input as text.')
        model = getattr(base.client, 'model', None)
        if (not base.enabled or not base.client.available or model not in MODELS
                or MODELS[model].provider != 'OpenAI'):
            # Function tools are sent in the OpenAI Responses shape only.
            raise self._fail(UNAVAILABLE)
        self._load_defaults()
        output_limit = MODELS[model].output_tokens
        key = (owner, 'one-call:' + request_id)
        with self.lock:
            if key in self.active:
                raise ProfileError('This response is still running.', 409)
            self.active.add(key)
        try:
            rounds = self.max_tool_rounds if allow_tools else 0
            user = {'role': 'user', 'content': input_text}
            # Encrypted reasoning is requested only when a second request may need it.
            include = bool(rounds) and self._effort() != 'none'
            payload = self._payload(instructions, [user, *copy.deepcopy(list(carried))], 'auto' if rounds else 'none',
                                    output_limit, include=include)
            response, text, calls = self._send(payload, reservation.stage(stage), output_limit)
            if not calls:
                return {'reply': self._parse(text), 'requests': 1, 'tool_calls': 0}
            if not rounds:
                raise self._fail(UNCHECKED)
            # Confirm the second stage exists before any tool changes anything.
            try:
                second = reservation.stage(SECOND_STAGE)
            except BudgetError:
                base.local.last_composition_error = 'unavailable'
                raise
            items, reasoning = carried_items(response)
            outputs = self._run_tools(calls, runner)
            if carry is not None:
                carry.extend(copy.deepcopy([*items, *outputs]))
            LOGGER.info('Daylight one-call tool round calls=%s reasoning_items=%s', len(calls), reasoning)
            payload = self._payload(instructions, [user, *items, *outputs], 'none', output_limit, include=False)
            response, text, again = self._send(payload, second, output_limit)
            if again:
                # tool_choice was 'none'; a further tool request is not a reply.
                raise self._fail(UNCHECKED)
            return {'reply': self._parse(text), 'requests': 2, 'tool_calls': len(calls)}
        finally:
            with self.lock:
                self.active.discard(key)
