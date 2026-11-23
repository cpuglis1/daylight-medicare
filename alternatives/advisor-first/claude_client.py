"""Translate the advisor's two tool-free structured requests to Claude Messages."""
from importlib.util import find_spec
import json
from urllib.request import Request

from provider_transport import urlopen

MESSAGES = 'https://api.anthropic.com/v1/messages'
COUNT_TOKENS = MESSAGES + '/count_tokens'
CONSTRAINTS = {'minLength': 'At least {} characters.', 'maxLength': 'At most {} characters.',
               'minimum': 'At least {}.', 'maximum': 'At most {}.',
               'minItems': 'At least {} items.', 'maxItems': 'At most {} items.',
               'pattern': 'Match this pattern: {}.', 'uniqueItems': 'Use distinct items.'}


def provider_schema(schema):
    # Keep application-side validation against the full schema. Claude accepts
    # a smaller JSON Schema vocabulary than the one used by the advisor.
    output = {key: ({name: provider_schema(value) for name, value in item.items()}
                  if key == 'properties' else provider_schema(item) if key == 'items' else item)
            for key, item in schema.items() if key not in CONSTRAINTS}
    hints = [CONSTRAINTS[key].format(item) for key, item in schema.items()
             if key in CONSTRAINTS and (key != 'uniqueItems' or item)]
    if hints:
        output['description'] = ' '.join(filter(None, [output.get('description'), *hints]))
    if isinstance(output.get('type'), list):
        output['anyOf'] = [{'type': kind} for kind in output.pop('type')]
    return output


class ClaudeClient:
    model = 'claude-opus-5-5'
    # body() sends no tools and transport() returns text only, so this route
    # keeps the per-message keyword retrieval instead of the on-demand source
    # lookup tool (D155 Q5; NaturalAgent.source_lookup_enabled).
    supports_function_tools = False

    def __init__(self, key):
        self.key = key

    @property
    def available(self):
        return bool(self.key and find_spec('jsonschema'))

    def request(self, endpoint, payload, timeout, limit):
        request = Request(endpoint, data=json.dumps(payload).encode(), method='POST',
                          headers={'x-api-key': self.key, 'anthropic-version': '2023-06-01',
                                   'Content-Type': 'application/json'})
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('The provider response exceeded its bound.')
        return json.loads(raw)

    def body(self, payload):
        schema = payload['text']['format']['schema']
        return {'model': self.model, 'system': payload['instructions'], 'messages': payload['input'],
                'thinking': {'type': 'adaptive'},
                'output_config': {'effort': 'low', 'format': {'type': 'json_schema', 'schema': provider_schema(schema)}}}

    def count(self, payload):
        return self.request(COUNT_TOKENS, self.body(payload), 15, 10_000)['input_tokens']

    def transport(self, payload):
        body = self.body(payload)
        body['max_tokens'] = payload['max_output_tokens']
        message = self.request(MESSAGES, body, 55, 250_000)
        usage = message['usage']
        cached = usage.get('cache_read_input_tokens', 0)
        written = usage.get('cache_creation_input_tokens', 0)
        inputs = usage['input_tokens'] + cached + written
        output = usage['output_tokens']
        text = ''.join(block['text'] for block in message['content'] if block['type'] == 'text')
        stop = message['stop_reason']
        complete = stop == 'end_turn'
        contract_error = None
        if complete:
            from jsonschema import Draft202012Validator

            try:
                parsed = json.loads(text)
            except ValueError:
                contract_error = 'invalid_json'
            else:
                format_spec = payload['text']['format']
                validator = Draft202012Validator(format_spec['schema'])
                errors = list(validator.iter_errors(parsed))
                if errors and format_spec.get('name') == 'daylight_resolved_conversation':
                    defaults = {'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                                'education_followups': [],
                                'task_work': {'check_ids': [], 'blocking_concepts': [], 'next_step': 'answer'}}
                    optional = {error.path[0] for error in errors if error.path and error.path[0] in defaults}
                    if optional:
                        # Preserve the answer and references. A malformed
                        # optional draft must not erase validated teaching.
                        for key in optional:
                            parsed[key] = defaults[key]
                        errors = list(validator.iter_errors(parsed))
                        text = json.dumps(parsed, ensure_ascii=False)
                if errors:
                    contract_error = 'schema_constraints'
        return {'status': 'completed' if complete else 'incomplete',
                **({'structured_output_error': contract_error} if contract_error else {}),
                'incomplete_details': {'reason': 'max_output_tokens' if stop == 'max_tokens' else 'provider_stop'},
                'model': message['model'], 'service_tier': usage.get('service_tier', 'standard'),
                'usage': {'input_tokens': inputs, 'output_tokens': output, 'total_tokens': inputs + output,
                          'input_tokens_details': {'cached_tokens': cached, 'cache_write_tokens': written}},
                'output': [{'content': [{'type': 'output_text', 'text': text}]}]}
