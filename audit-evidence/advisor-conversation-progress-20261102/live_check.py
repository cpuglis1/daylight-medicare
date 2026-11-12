"""Three fictional turns testing progress, not coverage verification."""
import hashlib
import json
from pathlib import Path
import signal
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
PACKET = Path(__file__).resolve().parent
VARIANT = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

def hashes():
    return {name: hashlib.sha256((VARIANT / name).read_bytes()).hexdigest()
            for name in ('natural_agent.py', 'decision_guidance.py')}

result = {'fictional_inputs': True, 'profile_saved': False,
          'maximum_generation_stages': 6, 'automatic_retries': False,
          'source_before': hashes(), 'turns': []}
keys = []
app = None
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Bounded check timed out')))
signal.alarm(50)
try:
    with tempfile.TemporaryDirectory(prefix='conversation-progress-', dir=VARIANT / 'var') as tmp:
        app = build(0, database=Path(tmp) / 'fictional.sqlite3')
        flow = app.adaptive
        reserve = flow.agent.reserve_turn
        def bounded(*args, **kwargs):
            if len(keys) >= 6:
                raise AssertionError('No additional model call permitted')
            reservation = reserve(*args, **kwargs)
            keys.extend(stage.key for stage in reservation.stages.values() if stage.key)
            return reservation
        flow.agent.reserve_turn = bounded
        owner = uuid.uuid4().hex
        guide, record = flow.initial()
        for identifier, fields in [('T01', {'choice': 'compare'}),
                                   ('RC01', {'choice': 'self'}),
                                   ('T05', {'choice': 'retiree'}),
                                   ('T04', {'choice': 'soonest'})]:
            flow.capture(guide, record, {'id': identifier, 'entity': 'profile', 'fields': fields})
        state = flow.turn(owner, {'guide': guide, 'record': record,
            'action': {'type': 'start'}, 'requestId': uuid.uuid4().hex})
        messages = [
            ('I turn 65 in July and want to compare my plan options. Please move on from the introductory explanations.', 'T03'),
            ('60614', 'T06'),
            ('No doctors to include.', 'T07'),
        ]
        for message, expected in messages:
            state = flow.turn(owner, {'guide': state['guide'], 'record': state['record'],
                'continuation': state['continuation'], 'action': {'type': 'message', 'message': message},
                'requestId': uuid.uuid4().hex, 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
            question = state['assessment'].get('nextQuestion')
            entry = {'message': message, 'reply': state.get('reply'),
                'question': question, 'generated': state.get('generated'),
                'expected_next': expected, 'metrics': state.get('metrics'),
                'pass': state.get('generated', {}).get('status') == 'complete'
                        and bool(question) and question['id'] == expected}
            result['turns'].append(entry)
            if not entry['pass']:
                break
        result['pass'] = len(result['turns']) == 3 and all(turn['pass'] for turn in result['turns'])
except Exception as error:
    result['error_type'] = type(error).__name__
finally:
    signal.alarm(0)
    if app:
        with app.adaptive.agent.budget.db() as db:
            charges = [db.execute('SELECT status,charged,measured FROM ai_charges WHERE id=?', (key,)).fetchone() for key in keys]
        result['receipts'] = [dict(zip(('status', 'charged_nano_usd', 'measured_nano_usd'), row)) for row in charges if row]
        result['accounted_usd'] = sum(row['charged_nano_usd'] or 0 for row in result['receipts']) / 1e9
        app.server_close()
    result['source_after'] = hashes()
    (PACKET / 'live-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
