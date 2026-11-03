"""Offline synthetic journeys through the current :8893 C1/resolve/C2 contract.

This is a deterministic controller regression harness, not an LLM quality test.
Expectations are authored separately in fixtures, never recorded from observations.
There is no server, fixture=True shortcut, disk profile store, budget or live key.
"""
import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import sys
import uuid
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Register the pinned retained dependency modules; never start it.
from adaptive_flow import metadata
from chat import ResponsesClient, ModelUnavailable
from natural_flow import CONTEXT_POLICY, NaturalConversation

FIXTURES = Path(__file__).parent / 'fixtures' / 'persona_journeys.json'
CATALOG = json.loads((Path(__file__).parent / 'fixtures/profile_field_catalog.json').read_text())['fields']
CATALOG_PATHS = {item['path'] for item in CATALOG}


def _forbidden_network(*args, **kwargs):
    raise AssertionError('Network forbidden in synthetic persona test')


@contextmanager
def offline_network():
    with patch.object(socket, 'create_connection', _forbidden_network), \
         patch.object(socket, 'getaddrinfo', _forbidden_network), \
         patch.object(socket.socket, 'connect', _forbidden_network), \
         patch.object(socket.socket, 'connect_ex', _forbidden_network):
        yield


def load_scenarios(path=FIXTURES):
    value = json.loads(Path(path).read_text())
    return value['scenarios'] if isinstance(value, dict) else value


def canonical_path(path):
    if path.startswith(('guide.fields.', 'readiness.facts.', 'readiness.conversation.')):
        return path
    if path.startswith('guide.'):
        return 'guide.fields.' + path[6:]
    if path.startswith('readiness.'):
        parts = path.split('.')
        if len(parts) >= 4:
            identifier, entity, field = parts[1], parts[2], '.'.join(parts[3:])
            path = 'readiness.facts.' + identifier + '.value.' + ('items[].' if entity != 'profile' else '') + field
            return path + '[]' if path + '[]' in CATALOG_PATHS else path
    if path.startswith('reports.'):
        identifier, *rest = path[8:].split('.')
        return 'readiness.facts.' + identifier + '.value' + ('.' + '.'.join(rest) if rest else '')
    if path.startswith('details.'):
        return 'readiness.conversation.details.' + path[8:] + '.value'
    return path


def _precision(value):
    if isinstance(value, str) and len(value) == 7 and value[4] == '-' and value[:4].isdigit() and value[5:].isdigit():
        return 'month_and_year'
    if isinstance(value, dict) and set(value) >= {'month', 'year'}:
        return 'month_and_year' if value['year'] is not None else 'month_only_year_unknown'
    return None


def _snapshot(flow, guide, record):
    meta = metadata(record)
    return {
        'guide': {key: copy.deepcopy(flow.value(guide, key)) for key in guide['fields'] if flow.value(guide, key) is not None},
        'reports': {key: copy.deepcopy(flow.report(record, key)) for key in record['facts'] if flow.report(record, key)},
        'raw_guide': {key: copy.deepcopy(value['value']) for key, value in guide['fields'].items()},
        'raw_reports': {key: copy.deepcopy(value['value']) for key, value in record['facts'].items()},
        'dispositions': {key: value['state'] for key, value in record['dispositions'].items()},
        'baseline_dispositions': copy.deepcopy(meta['baselineDispositions']),
        'skipped_details': copy.deepcopy(meta['skippedDetails']),
        'details': copy.deepcopy(meta.get('details', {})),
        'provenance': copy.deepcopy(record['natural']['provenance']),
        'stale_reports': sorted(key for key, value in record['facts'].items() if value.get('stale')),
        'stale_guide': sorted(key for key, value in guide['fields'].items() if value.get('status') == 'stale'),
        'guide_status': {key: value.get('status') for key, value in guide['fields'].items()},
        'report_status': {key: 'stale' if value.get('stale') else 'reported' for key, value in record['facts'].items()},
    }


def _leaf_reports(identifier, expected):
    """Expand only explicitly asserted fields; structural matching never adds coverage."""
    for field, value in expected.items():
        if field == 'items':
            for item in value:
                entity = item['entity']
                for key, item_value in item.items():
                    yield f'readiness.{identifier}.{entity}.{key}', item_value, entity
        else:
            yield f'readiness.{identifier}.profile.{field}', value, 'profile'


def _path_exists(observed, path):
    kind, name = path.split('.', 1)
    if kind == 'guide':
        return name in observed['guide']
    if kind == 'reports':
        identifier, *rest = name.split('.')
        value = observed['reports'].get(identifier)
        if value is None:
            return False
        for segment in rest:
            if segment.endswith('[]'):
                key = segment[:-2]
                values = value.get(key, []) if isinstance(value, dict) else []
                tail = '.'.join(rest[rest.index(segment) + 1:])
                return bool(values) if not tail else any(_path_exists({'reports': {'X': item}}, 'reports.X.' + tail) for item in values)
            if not isinstance(value, dict) or segment not in value:
                return False
            value = value[segment]
        return True
    return name in observed.get(kind, {})


def _personal_shape(actual, expected):
    if isinstance(actual, dict) and isinstance(expected, dict):
        return {key: _personal_shape(value, expected.get(key)) for key, value in actual.items() if key != 'choice' or key in expected}
    if isinstance(actual, list) and isinstance(expected, list):
        return [_personal_shape(value, expected[index] if index < len(expected) else {}) for index, value in enumerate(actual)]
    return actual


def _subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and _subset(actual[key], value) for key, value in expected.items())
    # Lists are exact. This detects dropped, merged, invented or duplicated items.
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_subset(a, e) for a, e in zip(actual, expected))
    return actual == expected


class JourneyRunner:
    def __init__(self, scenario):
        self.scenario = copy.deepcopy(scenario)
        self.calls = []
        self.current_step = None
        self.current_index = 0
        self.assertions = []
        self.coverage = []
        self.results = []
        self.flow = NaturalConversation(None, None,
            json.loads((HERE / 'web/guide-contract.json').read_text()),
            json.loads((HERE / 'web/teaching-facts.json').read_text()),
            json.loads((HERE / 'web/readiness-content.json').read_text()),
            ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=self.transport),
            True, None, fixture=False)
        self.guide, self.record = self.flow.initial()
        self.owner = uuid.uuid4().hex
        self.continuation = None
        self.out = None
        self.before_question = None

    def transport(self, payload):
        name = payload['text']['format']['name']
        sent = json.loads(payload['input'][0]['content'])
        self.calls.append({'step': self.current_index, 'schema': name,
                           'store': payload.get('store'), 'tools': payload.get('tools'),
                           'question_candidates': [item['id'] for item in sent.get('question_candidates', [])]})
        step = self.current_step
        if name == 'daylight_guide_commands':
            raw = copy.deepcopy(step.get('interpretation', {}))
            message = step['action']['message']
            updates = []
            for proposed in raw.get('updates', []):
                item = {'entity': 'profile', 'subject': 'beneficiary', 'scope': 'current',
                        'uncertain': False, 'correction': False, 'quote': message, **proposed}
                if isinstance(item['fields'], dict):
                    item['fields'] = [{'key': key, 'value': value} for key, value in item['fields'].items()]
                updates.append(item)
            situations = []
            for proposed in raw.get('situation_proposals', []):
                situations.append({'subject': 'beneficiary', 'scope': 'current', 'quote': message,
                    'uncertain': False, 'correction': False, 'month': None, 'year': None,
                    'status': '', 'when': '', **proposed})
            value = {'updates': updates,
                'requests': [{'id': item, 'quote': message} if isinstance(item, str)
                             else {'quote': message, **item} for item in raw.get('requests', [])],
                'fact_ids': raw.get('fact_ids', []),
                'agenda': raw.get('agenda', {'concerns': [], 'priorityReason': {}}),
                'situation_proposals': situations, 'goal_quote': raw.get('goal_quote', '')}
            value['education_request'] = raw.get('education_request', {'kind': 'none', 'concept_ids': [], 'quote': ''})
        elif name == 'daylight_resolved_conversation':
            proposed = copy.deepcopy(step.get('composition', {}))
            if proposed.pop('fail', False):
                raise ModelUnavailable('Synthetic composition interruption.')
            candidates = sent.get('question_candidates', [])
            target = proposed.pop('question_target', candidates[0]['id'] if candidates else None)
            candidate = next((item for item in candidates if item['id'] == target), {})
            question = candidate.get('question') or {}
            value = {'question_target': target,
                'reply': 'We can work through the next useful detail together.',
                'question': question.get('question', '') if target is not None else '',
                'report_refs': [], 'evidence_refs': [],
                'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                'agenda_update': {'current_concern': '', 'pause': False},
                'education_followups': [], **proposed}
        else:
            raise AssertionError('Unexpected synthetic model contract: ' + name)
        return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                      'input_tokens_details': {'cached_tokens': 0}},
            'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}

    def check(self, label, actual, expected, *, path=None, state='known', mode='volunteered', entity=None, subset=False):
        passed = _subset(actual, expected) if subset else actual == expected
        item = {'scenario_id': self.scenario['id'], 'step': self.current_index,
                'assertion': label, 'actual': copy.deepcopy(actual),
                'expected': copy.deepcopy(expected), 'passed': passed}
        canonical = canonical_path(path) if path else None
        if canonical in CATALOG_PATHS:
            item.update(covered_path=canonical, native_path=path, state=state, mode=mode)
        self.assertions.append(item)
        if path:
            canonical = canonical_path(path)
            if canonical not in CATALOG_PATHS:
                return
            provenance = self.record['natural']['provenance'].get(path, {})
            self.coverage.append({**item, 'path': canonical, 'native_path': path,
                'state': state, 'mode': mode, 'item_id': entity,
                'source': provenance.get('method'), 'subject': provenance.get('subject'),
                'status': provenance.get('status'), 'precision': _precision(expected), 'assertion_type': label.split('.')[0]})

    def state_paths(self, identifier):
        return [item['path'] for item in CATALOG if identifier in item.get('question_ids', []) and item.get('inventory') != 'additive_14']

    def expectations(self, expected, observed, *, final=False):
        current = (self.out or {}).get('assessment', {})
        for key, value in expected.get('guide', {}).items():
            path = 'guide.' + key
            status = observed['guide_status'].get(key)
            mode = 'derived' if status == 'derived' else 'reused' if final else 'questioned' if any(canonical_path(path) == item['path'] and self.before_question in item.get('question_ids', []) for item in CATALOG) else 'volunteered'
            state = 'explicit_none' if key in {'needs.providersStatus','needs.medicinesStatus'} and value in ('none','no') or key == 'coverage.current' and value == ['none'] else 'known'
            self.check(path, observed['guide'].get(key), value, path=path, state=state, mode=mode)
        for identifier, value in expected.get('reports', {}).items():
            actual = observed['reports'].get(identifier)
            self.check('reports.' + identifier, actual, value, subset=True)
            if final:
                self.check('report_personal_fields_exact.' + identifier, _personal_shape(actual, value), value)
            for path, leaf, entity in _leaf_reports(identifier, value):
                keys = path.split('.')
                report = actual or {}
                item = report if entity == 'profile' else next((item for item in report.get('items', []) if item.get('entity') == entity), {})
                state = 'stale' if entity != 'profile' and self.flow.item_stale(self.record, identifier, entity) else 'known'
                mode = 'derived' if keys[-1] == 'entity' else 'reused' if final else 'questioned' if self.before_question == identifier else 'volunteered'
                self.check(path, item.get(keys[-1]), leaf, path=path, entity=entity, state=state, mode=mode)
        for key in ('dispositions', 'baseline_dispositions', 'skipped_details', 'details', 'guide_status', 'report_status'):
            for identifier, value in expected.get(key, {}).items():
                self.check(key + '.' + identifier, observed[key].get(identifier), value, subset=key == 'details')
                if key in {'dispositions','baseline_dispositions'}:
                    state = 'unknown' if value in {'unknown','explicit_unknown'} else 'deferred' if value == 'deferred' else value
                    for path in self.state_paths(identifier):
                        self.check(key + '.' + identifier, observed[key].get(identifier), value, path=path, state=state, mode='questioned')
                elif key == 'skipped_details':
                    q, entity, field = identifier.split('.', 2)
                    self.check(key + '.' + identifier, observed[key].get(identifier), value, path=f'readiness.{q}.{entity}.{field}', state='unknown' if value == 'unknown' else 'deferred', entity=entity, mode='questioned')
                elif key == 'details':
                    self.check(key + '.' + identifier, observed[key].get(identifier), value, path='details.' + identifier, subset=True, mode='reused' if final else 'volunteered')
        for path in expected.get('item_stale', []):
            identifier, entity = path.split('.', 1)
            self.check('item_stale.' + path, self.flow.item_stale(self.record, identifier, entity), True)
        for path in expected.get('item_current', []):
            identifier, entity = path.split('.', 1)
            self.check('item_current.' + path, self.flow.item_stale(self.record, identifier, entity), False)
        for key in ('stale_reports', 'stale_guide'):
            if key in expected:
                self.check(key, observed[key], expected[key])
                for identifier in expected[key]:
                    paths = ['guide.' + identifier] if key == 'stale_guide' else self.state_paths(identifier)
                    for path in paths:
                        self.check(key, observed[key], expected[key], path=path, state='stale', mode='reused')
        for key, value in expected.get('provenance', {}).items():
            self.check('provenance.' + key, observed['provenance'].get(key), value, subset=True)
        for path in expected.get('absent', []):
            kind, name = path.split('.', 1)
            actual = not _path_exists(observed, path)
            self.check('absent.' + path, actual, True)
            canonical = canonical_path(path)
            matches = [item['path'] for item in CATALOG if item['path'] == canonical or item['path'].startswith(canonical + '.') or item['path'] == canonical + '[]']
            for covered in matches:
                self.check('absent.' + path, actual, True, path=covered, state='unanswered', mode='explicit_absence')
        if 'exact_detail_keys' in expected:
            self.check('exact_detail_keys', sorted(observed['details']), sorted(expected['exact_detail_keys']))
        for key in ('dispositions','baseline_dispositions','skipped_details'):
            if 'exact_' + key in expected:
                self.check('exact_' + key, observed[key], expected['exact_' + key])
        for key, actual in (('exact_guide_paths', sorted(observed['guide'])), ('exact_report_ids', sorted(observed['reports']))):
            if key in expected:
                self.check(key, actual, sorted(expected[key]))
        if 'question' in expected:
            self.check('next_question', (current.get('nextQuestion') or {}).get('id'), expected['question'])
        if 'question_fields' in expected:
            self.check('question_fields', [f['key'] for f in (current.get('nextQuestion') or {}).get('fields', [])], expected['question_fields'])
        if 'pending' in expected:
            self.check('pending_clarification', bool(self.flow.pending_for(self.owner)), expected['pending'])
        if 'pending_id' in expected:
            self.check('pending_target', ((self.flow.pending_for(self.owner) or {}).get('update') or {}).get('id'), expected['pending_id'])
        for key in ('intakePaused', 'conversationOpen'):
            if key in expected:
                self.check(key, current.get(key), expected[key])
        if 'generated_status' in expected:
            self.check('generated_status', (self.out or {}).get('generated', {}).get('status'), expected['generated_status'])
        if 'task' in expected:
            self.check('task', metadata(self.record)['task'], expected['task'])

    def capture_witnesses(self):
        """Locate when each independently asserted final value was captured.

        The expected value comes only from the authored final oracle. Observed
        history selects its first successful witness; it never supplies a golden.
        A failed final oracle cannot create a passing capture witness.
        """
        final_rows = [row for row in self.coverage if row['step'] == 'final'
                      and row['state'] in {'known','explicit_none'} and row['mode'] == 'reused' and row['passed']]
        for row in final_rows:
            native = row['native_path']
            for index, step in enumerate(self.results):
                snapshot = step['observed']
                if native.startswith('guide.'):
                    key = native[6:]
                    actual = snapshot['guide'].get(key)
                    status = snapshot['guide_status'].get(key)
                    if status == 'derived':
                        continue
                elif native.startswith('readiness.'):
                    _, identifier, entity, field = native.split('.', 3)
                    report = snapshot['reports'].get(identifier, {})
                    item = report if entity == 'profile' else next((item for item in report.get('items', []) if item.get('entity') == entity), {})
                    actual = item.get(field)
                else:
                    continue
                provenance = snapshot['provenance'].get(native, {})
                if actual != row['expected'] or provenance.get('status') not in {'user_reported','explicitly_confirmed'}:
                    continue
                previous_question = self.results[index - 1]['question'] if index else None
                question_ids = next((item.get('question_ids', []) for item in CATALOG if item['path'] == row['path']), [])
                mode = 'questioned' if previous_question in question_ids else 'volunteered'
                witness = {**copy.deepcopy(row), 'step': step['step'], 'assertion': 'captured.' + native,
                    'actual': copy.deepcopy(actual), 'mode': mode, 'source': provenance['method'],
                    'subject': provenance['subject'], 'status': provenance['status'], 'assertion_type': 'capture'}
                self.coverage.append(witness)
                self.assertions.append({**{key: copy.deepcopy(witness[key]) for key in ('scenario_id','step','assertion','actual','expected','passed','native_path','state','mode')}, 'covered_path': witness['path']})
                break

    def run(self):
        # Fail closed if any code bypasses the injected Responses transport.
        with offline_network():
            for index, step in enumerate(self.scenario['steps'], 1):
                self.current_step, self.current_index = step, index
                action = copy.deepcopy(step['action'])
                payload = {'guide': copy.deepcopy(self.guide), 'record': copy.deepcopy(self.record),
                    'action': action, 'requestId': str(uuid.uuid4()),
                    'aiConsent': step.get('aiConsent', action['type'] == 'message'),
                    'contextPolicy': CONTEXT_POLICY}
                if self.continuation:
                    payload['continuation'] = self.continuation
                self.before_question = ((self.out or {}).get('assessment', {}).get('nextQuestion') or {}).get('id')
                before = copy.deepcopy((self.guide, self.record))
                submitted_profile = copy.deepcopy((payload['guide'], payload['record']))
                trusted_chain = self.flow.current_chain.get(self.owner)
                trusted_head = self.flow.state_heads.get((self.owner, trusted_chain)) if trusted_chain else None
                call_count = len(self.calls)
                error = None
                try:
                    self.out = self.flow.turn(self.owner, payload)
                    self.guide, self.record = self.out['guide'], self.out['record']
                    self.continuation = self.out['continuation']
                except Exception as caught:
                    error = {'type': type(caught).__name__, 'status': getattr(caught, 'status', getattr(caught, 'code', None))}
                    if 'expected_error' not in step:
                        raise AssertionError(f"{self.scenario['id']} step {index}: {error}") from caught
                if 'expected_error' in step:
                    self.check('expected_error', error, step['expected_error'], subset=True)
                    self.check('error_preserves_profile', (self.guide, self.record), before)
                    self.check('error_preserves_submitted_profile', (payload['guide'], payload['record']), submitted_profile)
                    if trusted_head is not None:
                        self.check('error_preserves_trusted_head', self.flow.state_heads.get((self.owner, trusted_chain)), trusted_head)
                        self.check('error_preserves_trusted_chain', self.flow.current_chain.get(self.owner), trusted_chain)
                    identifier = action.get('id', '')
                    if identifier.startswith('G') and canonical_path('details.' + identifier) in CATALOG_PATHS:
                        self.check('rejected_legacy_target.' + identifier, error, step['expected_error'],
                            path='details.' + identifier, state='unanswered', mode='rejected', subset=True)
                else:
                    self.check('no_unexpected_error', error, None)
                snapshot = _snapshot(self.flow, self.guide, self.record)
                self.expectations(step.get('expected', {}), snapshot)
                self.check('recommendation_hold', (self.out or {}).get('assessment', {}).get('personalizedRecommendationAllowed', False), False)
                self.check('external_verification_hold', (self.out or {}).get('assessment', {}).get('externalVerificationReady', False), False)
                new_calls = self.calls[call_count:]
                if not error and action['type'] == 'message':
                    self.check('typed_message_stages', [item['schema'] for item in new_calls],
                        ['daylight_guide_commands', 'daylight_resolved_conversation'])
                if action['type'] != 'message' and not payload['aiConsent']:
                    self.check('manual_action_has_no_model_stage', new_calls, [])
                self.results.append({'step': index, 'action': action,
                    'observed': snapshot, 'question': ((self.out or {}).get('assessment', {}).get('nextQuestion') or {}).get('id'),
                    'error': error, 'model_contracts': [item['schema'] for item in new_calls]})
            self.current_index = 'final'
            observed = _snapshot(self.flow, self.guide, self.record)
            self.expectations(self.scenario.get('expected', {}), observed, final=True)
            self.capture_witnesses()
            self.check('no_provider_storage_or_tools', all(item['store'] is False and item['tools'] == [] for item in self.calls), True)
        return {'scenario_id': self.scenario['id'], 'name': self.scenario['name'],
            'expected': copy.deepcopy(self.scenario.get('expected', {})), 'observed': observed,
            'steps': self.results, 'assertions': self.assertions, 'coverage': self.coverage,
            'synthetic_contract_calls': len(self.calls), 'paid_model_calls': 0,
            'passed': all(item['passed'] for item in self.assertions)}


def run_scenario(scenario):
    return JourneyRunner(scenario).run()


def assert_scenario(result):
    failures = [item for item in result['assertions'] if not item['passed']]
    if failures:
        raise AssertionError(json.dumps({'scenario': result['scenario_id'], 'failures': failures}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=FIXTURES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    results = [run_scenario(scenario) for scenario in load_scenarios(args.fixtures)]
    payload = {'kind': 'offline_current_8893_persona_regression', 'paid_model_calls': 0,
               'scenario_count': len(results), 'passed': all(result['passed'] for result in results), 'results': results}
    if args.output:
        args.output.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'scenario_count': len(results), 'passed': payload['passed'],
        'assertions': sum(len(result['assertions']) for result in results),
        'failed': [result['scenario_id'] for result in results if not result['passed']], 'paid_model_calls': 0}))
    raise SystemExit(0 if payload['passed'] else 1)
