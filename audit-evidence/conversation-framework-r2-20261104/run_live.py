"""Opt-in complete fictional journeys through the actual two-stage advisor.

Uses the selected production model, token checks, shared ledger and ordinary
controller. No authored assistant replies, synthetic transport, rescue messages,
replayed prefixes or provider fallback. A failed turn stops the whole attempt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
MODEL = 'gpt-6.1-sol'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def hashes():
    paths = [*VARIANT.glob('*.py'), *VARIANT.glob('*.json'), PACKET/'journeys.json', Path(__file__)]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run():
    sys.path.insert(0, str(VARIANT))
    from server import build
    from natural_flow import CONTEXT_POLICY
    spec = json.loads((PACKET/'journeys.json').read_text())
    attempt = PACKET/'attempts'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    attempt.mkdir(parents=True)
    before = hashes()
    write(attempt/'source-manifest.json', before)
    write(attempt/'journeys.json', spec)
    result = {'model': MODEL, 'fictional_only': True, 'saved_profiles': False,
              'complete': False, 'quality_pass': None, 'human_comprehension': 'unobserved',
              'journeys': [], 'receipts': [], 'run_cap_usd': 1.10}
    app = None
    reservations, keys = [], set()
    started = time.monotonic()
    active = {}

    def receipts():
        for reservation in reservations:
            keys.update(s.key for s in reservation.stages.values() if s.key)
        rows = []
        with app.budget.db() as db:
            for key in sorted(keys):
                row = db.execute('SELECT status,charged,measured,input_tokens,output_tokens FROM ai_charges WHERE id=?', (key,)).fetchone()
                if row:
                    rows.append(dict(zip(('status', 'charged_nano', 'measured_nano', 'input_tokens', 'output_tokens'), row)))
        return rows

    def save():
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        write(attempt/'result.json', result)

    try:
        with tempfile.TemporaryDirectory(prefix='framework-r2-', dir=VARIANT/'var') as directory:
            app = build(0, database=Path(directory)/'fictional.sqlite3')
            flow = app.adaptive
            agent = flow.model_agents[MODEL]
            assert agent.client.available and agent.budget.daily_cap_nano_usd == 5_000_000_000
            result['budget_before'] = agent.budget.summary(MODEL)
            reserve, validate = agent.reserve_turn, agent.validate_composition

            def tracked_reserve(*args, **kwargs):
                reservation = reserve(*args, **kwargs)
                reservations.append(reservation)
                keys.update(s.key for s in reservation.stages.values() if s.key)
                return reservation

            def tracked_validate(value, context, moves):
                # Fictional harness only: preserve rejected proposals for diagnosis.
                write(attempt/f"{active['case']}-{active['turn']}-composition.json",
                      {'proposal': value, 'context': context, 'candidates': moves})
                return validate(value, context, moves)

            agent.reserve_turn, agent.validate_composition = tracked_reserve, tracked_validate
            for journey in spec['journeys']:
                owner = uuid.uuid4().hex
                g, r = flow.initial()
                state = flow.turn(owner, {'guide': g, 'record': r, 'requestId': uuid.uuid4().hex,
                                         'action': {'type': 'start'}})
                entry = {'id': journey['id'], 'complete': False, 'turns': []}
                result['journeys'].append(entry)
                for number, message in enumerate(journey['messages'], 1):
                    if hashes() != before:
                        raise RuntimeError('Source changed during the attempt.')
                    # Budget for two stages plus the permitted one retry per stage.
                    if sum(x['charged_nano'] for x in receipts()) / 1e9 + .256 > result['run_cap_usd']:
                        raise RuntimeError('Evaluation ceiling reached before the next complete turn.')
                    active.update(case=journey['id'], turn=number)
                    tick = time.monotonic()
                    state = flow.turn(owner, {'guide': state['guide'], 'record': state['record'],
                        'continuation': state['continuation'], 'requestId': uuid.uuid4().hex,
                        'action': {'type': 'message', 'message': message}, 'model': MODEL,
                        'aiConsent': True, 'aiProvider': 'OpenAI', 'contextPolicy': CONTEXT_POLICY})
                    row = {'turn': number, 'user': message, 'reply': state.get('reply', ''),
                           'question': state['assessment'].get('nextQuestion'),
                           'generated': state.get('generated'), 'notice': state.get('notice'),
                           'seconds': round(time.monotonic() - tick, 3), 'metrics': state.get('metrics')}
                    entry['turns'].append(row)
                    write(attempt/f"{journey['id']}-{number}-state.json",
                          {k: v for k, v in state.items() if k != 'continuation'})
                    result['receipts'] = receipts()
                    save()
                    print(json.dumps({'case': journey['id'], 'turn': number, 'generated': row['generated'],
                                      'seconds': row['seconds']}), flush=True)
                    if (state.get('generated', {}).get('status') != 'complete'
                            or state['assessment'].get('personalizedRecommendationAllowed')
                            or state['assessment'].get('externalVerificationReady')):
                        raise RuntimeError('Turn failed or exceeded authority; whole attempt stopped.')
                entry['complete'] = True
                save()
            result['complete'] = True
    except Exception as error:
        # Fixed exception class only; ordinary controller notice/diagnostics above
        # contain the permitted provider detail without raw error bodies or keys.
        result['stopped'] = {**active, 'exception': type(error).__name__}
        if isinstance(error, RuntimeError):
            result['stop_reason'] = str(error)
        if app is not None:
            agent = app.adaptive.model_agents[MODEL]
            result['provider_diagnostic'] = getattr(agent.local, 'provider_failure', None)
            result['transport_diagnostic'] = getattr(agent.local, 'last_transport_failure', None)
    finally:
        if app is not None:
            result['receipts'] = receipts()
            result['budget_after'] = app.budget.summary(MODEL)
            app.server_close()
        result['measured_usd'] = sum(x['measured_nano'] or 0 for x in result['receipts']) / 1e9
        result['held_usd'] = sum(x['charged_nano'] for x in result['receipts'] if x['status'] in ('reserved', 'uncertain')) / 1e9
        result['source_unchanged'] = hashes() == before
        save()
    print(json.dumps({'attempt': str(attempt), 'complete': result['complete'],
                      'measured_usd': result['measured_usd'], 'held_usd': result['held_usd']}), flush=True)
    return result['complete']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.live:
        sys.exit(0 if run() else 1)
    print((PACKET/'journeys.json').read_text())
