"""One fictional opening, two bounded model stages, no saved profile or retry."""
import json
from pathlib import Path
import signal
import sys
import tempfile
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

result = {'fictional': True, 'maximum_generation_stages': 2, 'automatic_retry': False}
app = None
keys = []
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Bounded check timed out')))
signal.alarm(55)
try:
    with tempfile.TemporaryDirectory(prefix='eligibility-opening-', dir=VARIANT / 'var') as temp:
        app = build(0, database=Path(temp) / 'fictional.sqlite3')
        flow = app.adaptive
        reserve = flow.agent.reserve_turn
        def bounded(*args, **kwargs):
            if keys:
                raise AssertionError('Only one two-stage turn is authorized by this harness')
            reservation = reserve(*args, **kwargs)
            keys.extend(stage.key for stage in reservation.stages.values() if stage.key)
            return reservation
        flow.agent.reserve_turn = bounded
        validate = flow.agent.validate_composition
        def capture(value, context, moves):
            result['proposed_composition'] = value
            result['candidate_ids'] = [move['id'] for move in moves]
            try:
                return validate(value, context, moves)
            except Exception as error:
                result['validation_error'] = str(error)
                raise
        flow.agent.validate_composition = capture
        owner = uuid.uuid4().hex
        guide, record = flow.initial()
        state = flow.turn(owner, {'guide': guide, 'record': record,
            'action': {'type':'start'}, 'requestId':uuid.uuid4().hex})
        state = flow.turn(owner, {'guide':state['guide'],'record':state['record'],
            'continuation':state['continuation'],'requestId':uuid.uuid4().hex,
            'action':{'type':'message','message':"I am 64 and looking to enroll in medicare when eligible, but don't really know when that is"},
            'aiConsent':True,'contextPolicy':CONTEXT_POLICY})
        result.update(reply=state.get('reply'),question=state['assessment'].get('nextQuestion'),
            generated=state.get('generated'),notice=state.get('notice'),metrics=state.get('metrics'),
            task=state['record']['conversation']['task'])
except Exception as error:
    result['error_type'] = type(error).__name__
    result['error'] = str(error)
    result['error_chain'] = traceback.format_exception(error)
finally:
    signal.alarm(0)
    if app:
        with app.adaptive.agent.budget.db() as db:
            receipts = [db.execute('SELECT status,charged,measured FROM ai_charges WHERE id=?',(key,)).fetchone() for key in keys]
        result['receipts'] = [dict(zip(('status','charged_nano_usd','measured_nano_usd'),row)) for row in receipts if row]
        result['accounted_usd'] = sum(row['charged_nano_usd'] for row in result['receipts']) / 1e9
        app.server_close()
    destination = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('reproduction.json')
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
