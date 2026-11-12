"""Opt-in seven-turn fictional provider check; never retries or resumes a prefix.

Default invocation describes the frozen persona without building a server or
contacting the provider. --live requires separate task authorization. Each run
creates a new immutable-named attempt directory; earlier evidence is preserved.
Technical success does not automatically pass semantic quality or comprehension.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError
import uuid

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
SPEC_PATH = PACKET / 'journey-spec.json'


def safe_diagnostic_text(value, secret='', limit=2000):
    """Never retain credentials, headers or a raw unparsed HTTP body."""
    text = str(value)
    if secret:
        text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)\bBearer\s+[^\s,;]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[REDACTED]', text)
    text = re.sub(r'(?i)(authorization|api[_-]?key)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', text)
    return text[:limit]


def provider_error_receipt(error, secret=''):
    """Observe a failed fictional call without changing its charge or retry state.

    HTTPError's bounded response body is consumed solely to select the provider's
    error type/code/message. No request object, headers or raw body is serialized.
    Any inspection failure is reported without replacing the original exception.
    """
    receipt = {'exception_class': type(error).__name__,
               'message': safe_diagnostic_text(error, secret), 'http_status': None}
    reason = getattr(error, 'reason', None)
    if reason is not None:
        receipt['reason_class'] = type(reason).__name__
        receipt['reason'] = safe_diagnostic_text(reason, secret)
    cause = error
    for _ in range(3):
        if isinstance(cause, HTTPError):
            receipt['http_status'] = cause.code
            try:
                raw = cause.read(16385)
                if len(raw) > 16384:
                    receipt['provider_body'] = 'exceeds diagnostic bound; omitted'
                else:
                    body = json.loads(raw)
                    detail = body.get('error') if isinstance(body, dict) else None
                    if isinstance(detail, dict):
                        receipt['provider_error'] = {
                            key: safe_diagnostic_text(detail[key], secret)
                            for key in ('type', 'code', 'message')
                            if detail.get(key) is not None and isinstance(detail[key], (str, int, float))}
                    else:
                        receipt['provider_body'] = 'no structured error fields; omitted'
            except Exception as inspection_error:
                receipt['diagnostic_read_error_class'] = type(inspection_error).__name__
            break
        cause = getattr(cause, '__cause__', None)
        if cause is None:
            break
    return receipt


def completion_observer(original, emit, secret=''):
    """Harness-only observer around the existing composition provider boundary."""
    def observed(payload, raw):
        started = time.perf_counter()
        capture = {'contract': payload.get('text', {}).get('format', {}).get('name'),
                   'stage': 'composition', 'request_bytes': len(raw),
                   'automatic_retry': False}
        try:
            response, text = original(payload, raw)
            capture['returned'] = {
                'status': safe_diagnostic_text(response.get('status'), secret, 80),
                'usage': copy.deepcopy(response.get('usage')),
                'text': safe_diagnostic_text(text, secret, 20000),
            }
            return response, text
        except Exception as error:
            capture['error'] = provider_error_receipt(error, secret)
            raise
        finally:
            capture['elapsed_seconds'] = round(time.perf_counter() - started, 6)
            emit(capture)
    return observed


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def source_hashes():
    paths = [*VARIANT.glob('*.py'), *VARIANT.glob('*.json')]
    paths += [p for p in (VARIANT / 'web').rglob('*')
              if p.is_file() and p.suffix in {'.js', '.css', '.html', '.json'}]
    paths += [Path(__file__), SPEC_PATH]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths))}


def action_for(event, previous):
    """Only finite prewritten wording branches; no model-driven persona rescue."""
    target = ((previous.get('assessment') or {}).get('nextQuestion') or {}).get('id')
    branches = event.get('when_previous_target', {})
    message = branches.get(target, event['message'])
    return {'type': 'message', 'message': message}, {
        'previous_target': target,
        'wording_branch': target if target in branches else 'default',
        'facts_added_to_rescue_route': False,
    }


def technical_checks(flow, state, event_id):
    assessment = state['assessment']
    checks = {
        'generated_complete': state.get('generated', {}).get('status') == 'complete',
        'no_recommendation_release': not assessment.get('personalizedRecommendationAllowed', False),
        'no_external_verification_release': not assessment.get('externalVerificationReady', False),
        'two_existing_generation_calls': state.get('metrics', {}).get('llmCalls') == 2,
        'birthday_year_not_invented': (flow.value(state['guide'], 'situation.age65') or {}).get('year') is None,
        'no_exact_start_invented': flow.value(state['guide'], 'coverage.requestedStartMonth') is None,
    }
    if event_id == 'opening':
        checks.update(self_report_retained=flow.value(state['guide'], 'subject.role') == 'self',
                      no_insurance_retained=flow.value(state['guide'], 'coverage.current') == ['none'],
                      birthday_month_retained=flow.value(state['guide'], 'situation.age65') == {'month': 11, 'year': None})
    if event_id in {'unknown_preference_and_misconception', 'explicit_defer_and_detour', 'closure'}:
        checks['no_start_preference_invented'] = flow.value(state['guide'], 'coverage.requestedStart') in (None, 'unknown', 'deferred')
        disposition = state['record'].get('conversation', {}).get('baselineDispositions', {}).get('T04')
        checks['requested_start_disposition_retained'] = disposition == (
            'unknown' if event_id == 'unknown_preference_and_misconception' else 'deferred')
    if event_id in {'correction_and_synthesis', 'closure'}:
        checks['corrected_month_retained'] = flow.value(state['guide'], 'situation.age65') == {'month': 12, 'year': None}
    if event_id == 'closure':
        checks['no_practical_question_after_stop'] = assessment.get('nextQuestion') is None
        checks['no_suggestions_after_stop'] = not (state.get('advisor') or {}).get('educationFollowups', [])
    return checks


def run_live():
    spec = json.loads(SPEC_PATH.read_text())
    attempt = PACKET / 'live-attempts' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    write(attempt / 'run-build.json', {'before_sha256': before})
    write(attempt / 'journey-spec.json', spec)
    result = {
        'fictional_inputs': True, 'saved_profile': False, 'automatic_retries': False,
        'fresh_uninterrupted_visit': True, 'prefix_replay': False,
        'maximum_generation_stages': 14, 'maximum_reservation_usd': 0.469,
        'model': 'gpt-5.4', 'context_policy': 'natural-context-v3',
        'technical_complete': False, 'quality_pass': None, 'human_comprehension': 'unobserved',
        'review_status': 'independent transcript review required', 'turns': [],
        'token_checks': [], 'receipts': [], 'provider_diagnostics': [],
    }
    stage_ids = []
    active = {'turn': 0, 'event': 'setup'}
    app = None
    def save():
        write(attempt / 'result.json', result)
    save()
    try:
        sys.path.insert(0, str(VARIANT))
        from server import build
        from natural_flow import CONTEXT_POLICY
        policy = json.loads((VARIANT / 'model-policy.json').read_text())
        if policy.get('reasoning_effort') != 'none' or policy.get('composition_reasoning_effort') != 'none' or policy.get('output_tokens') != 900:
            raise AssertionError('Reviewed model policy changed; no provider call authorized by this harness.')
        with tempfile.TemporaryDirectory(prefix='advisor-quality-', dir=VARIANT / 'var') as temporary:
            app = build(0, database=Path(temporary) / 'fictional.sqlite3')
            flow, agent = app.adaptive, app.adaptive.agent
            if agent.client.model != 'gpt-5.4' or agent.budget.daily_cap_nano_usd != 15_000_000_000:
                raise AssertionError('Use the existing reviewed model and $15 UTC ledger policy.')
            result['budget_before'] = agent.budget.summary()
            reserve, extract, compose, count = agent.reserve_turn, agent.validate_output, agent.validate_composition, agent.count_tokens
            def capture_completion(capture):
                filename = f"turn-{active['turn']}-provider-completion-{len(result['provider_diagnostics']) + 1}.json"
                capture.update(turn=active['turn'], event=active['event'], fictional_inputs=True)
                write(attempt / filename, capture)
                result['provider_diagnostics'].append({'turn': active['turn'], 'file': filename,
                    'stage': 'composition', 'completed': 'returned' in capture,
                    'elapsed_seconds': capture['elapsed_seconds']})
                save()
            agent._complete = completion_observer(agent._complete, capture_completion, agent.client.key)
            def audited_reserve(*args, **kwargs):
                names = kwargs.get('stages', ('extract', 'compose'))
                if len(stage_ids) + len(names) > 14:
                    raise AssertionError('Generation-stage ceiling reached; no retry.')
                reservation = reserve(*args, **kwargs)
                stage_ids.extend(stage.key for stage in reservation.stages.values() if stage.key is not None)
                return reservation
            def audited_count(client, payload):
                started = time.perf_counter()
                contract = payload['text']['format']['name']
                request_file = f"turn-{active['turn']}-{contract}-count-{len(result['token_checks']) + 1}-request.json"
                write(attempt / request_file, payload)
                receipt = {'turn': active['turn'], 'contract': contract, 'request_file': request_file}
                try:
                    receipt['input_tokens'] = count(client, payload)
                    return receipt['input_tokens']
                except Exception as error:
                    receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
                    raise
                finally:
                    receipt['seconds'] = round(time.perf_counter() - started, 6)
                    result['token_checks'].append(receipt)
                    save()
            def audited_extract(value, message, guide, facts, eligible, owner):
                capture = {'message': message, 'raw_proposal': value}
                try:
                    accepted = extract(value, message, guide, facts, eligible, owner)
                    capture['validated'] = accepted
                    return accepted
                except Exception as error:
                    capture['error'] = {'type': type(error).__name__, 'message': str(error)}
                    raise
                finally:
                    write(attempt / f"turn-{active['turn']}-interpretation.json", capture)
            def audited_compose(value, context, candidates):
                capture = {'raw_proposal': value, 'resolved_context': context, 'candidates': candidates}
                try:
                    accepted = compose(value, context, candidates)
                    capture['validated'] = accepted
                    return accepted
                except Exception as error:
                    capture['error'] = {'type': type(error).__name__, 'message': str(error)}
                    raise
                finally:
                    write(attempt / f"turn-{active['turn']}-composition.json", capture)
            agent.reserve_turn, agent.count_tokens = audited_reserve, audited_count
            agent.validate_output, agent.validate_composition = audited_extract, audited_compose
            owner = uuid.uuid4().hex
            guide, record = flow.initial()
            state = flow.turn(owner, {'guide': guide, 'record': record, 'action': {'type': 'start'}, 'requestId': uuid.uuid4().hex})
            for index, event in enumerate(spec['events'], 1):
                if source_hashes() != before:
                    raise AssertionError('Source changed during evaluation; stop rather than mix builds.')
                active.update(turn=index, event=event['id'])
                action, persona = action_for(event, state)
                row = {'turn': index, 'event': event['id'], 'action': action, 'persona_policy': persona,
                       'expected_outcome': event['expect'], 'technical_checks': {}}
                result['turns'].append(row)
                started = time.perf_counter()
                try:
                    state = flow.turn(owner, {'guide': state['guide'], 'record': state['record'],
                        'continuation': state['continuation'], 'requestId': uuid.uuid4().hex,
                        'action': action, 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
                    row.update(reply=state.get('reply'), question=state['assessment'].get('nextQuestion'),
                               generated=state.get('generated'), metrics=state.get('metrics'),
                               advisor=state.get('advisor'), education=state.get('education'))
                    write(attempt / f'turn-{index}-resolved-display.json', {
                        key: value for key, value in state.items() if key != 'continuation'})
                    row['technical_checks'] = technical_checks(flow, state, event['id'])
                finally:
                    row['elapsed_seconds'] = round(time.perf_counter() - started, 6)
                    save()
                print(json.dumps({'turn': index, 'event': event['id'], 'generated': row['generated'],
                                  'technical_checks': row['technical_checks'], 'seconds': row['elapsed_seconds']}), flush=True)
                if not all(row['technical_checks'].values()):
                    raise AssertionError('Technical outcome failed; retain this complete prefix and stop without retry.')
            result['technical_complete'] = True
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error), **active}
    finally:
        if app is not None:
            try:
                with app.adaptive.agent.budget.db() as db:
                    for identifier in stage_ids:
                        row = db.execute('SELECT id,status,charged,measured,input_tokens,output_tokens FROM ai_charges WHERE id=?', (identifier,)).fetchone()
                        if row:
                            result['receipts'].append(dict(zip(('id','status','charged_nano_usd','measured_nano_usd','input_tokens','output_tokens'), row)))
                result['budget_after'] = app.adaptive.agent.budget.summary()
            except Exception as error:
                result['accounting_error'] = {'type': type(error).__name__, 'message': str(error)}
            app.server_close()
        result['generation_stages_reserved'] = len(stage_ids)
        result['measured_usd'] = sum(row['measured_nano_usd'] or 0 for row in result['receipts']) / 1e9
        result['accounted_usd'] = sum(row['charged_nano_usd'] or 0 for row in result['receipts']) / 1e9
        result['held_usd'] = sum(row['charged_nano_usd'] or 0 for row in result['receipts'] if row['status'] in {'reserved', 'uncertain'}) / 1e9
        after = source_hashes()
        result['source_unchanged'] = before == after
        if before != after:
            result['technical_complete'] = False
        write(attempt / 'run-build.json', {'before_sha256': before, 'after_sha256': after})
        write(attempt / 'quality-review.json', {
            'reviewer': None, 'milestone_reached': None, 'critical_failures': [], 'stuck_spans': [],
            'scores': {key: {'score': None, 'transcript_spans': [], 'reason': None}
                       for key in spec['evaluation']['anchors']},
            'quality_pass': None, 'rules': spec['evaluation'], 'human_comprehension': 'unobserved'})
        save()
    print(json.dumps({'attempt': str(attempt), 'technical_complete': result['technical_complete'],
                      'quality_pass': None, 'accounted_usd': result['accounted_usd'], 'held_usd': result['held_usd']}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicit paid fresh-run execution; no automatic retry or resume.')
    args = parser.parse_args()
    if args.live:
        sys.exit(0 if run_live()['technical_complete'] else 1)
    print(json.dumps({'live_execution': False, 'spec': json.loads(SPEC_PATH.read_text())}, indent=2))
