"""One fictional PCP turn, at most two paid stages, no retry or profile saving."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import uuid

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
sys.path[:0] = [str(VARIANT), str(VARIANT/'tests')]
from server import build
from natural_flow import CONTEXT_POLICY
from test_provider_capture_regression import ProviderCaptureRegressionTests

seed = ProviderCaptureRegressionTests().case_at_provider_question()
receipts = []
result = {'fictionalInputs': True, 'savedProfile': False, 'automaticRetries': False,
          'maximumGenerationStages': 2, 'maximumReservationUsd': 0.067,
          'model': 'gpt-5.4', 'contextPolicy': CONTEXT_POLICY}
with tempfile.TemporaryDirectory(prefix='provider-capture-check-', dir=VARIANT/'var') as directory:
    app = build(0, database=Path(directory)/'guides.sqlite3')
    agent = app.adaptive.agent
    original_reserve = agent.reserve_turn
    original_extract = agent.validate_output
    def reserve(*args, **kwargs):
        stages = kwargs.get('stages', ('extract', 'compose'))
        if len(receipts)+len(stages)>2:
            raise AssertionError('Paid stage ceiling; no retry.')
        reservation = original_reserve(*args, **kwargs)
        receipts.extend(stage.key for stage in reservation.stages.values())
        return reservation
    def extract(value, *args):
        (PACKET/'fictional-extraction.json').write_text(json.dumps(value, indent=2)+'\n')
        return original_extract(value, *args)
    agent.reserve_turn = reserve
    agent.validate_output = extract
    owner = uuid.uuid4().hex
    state = app.adaptive.turn(owner, {'guide':copy.deepcopy(seed.g), 'record':copy.deepcopy(seed.r),
                                    'action':{'type':'refresh'}, 'requestId':str(uuid.uuid4())})
    try:
        out = app.adaptive.turn(owner, {'guide':state['guide'], 'record':state['record'],
            'continuation':state['continuation'], 'requestId':str(uuid.uuid4()),
            'action':{'type':'message', 'message':'My PCP is robin example in naples'},
            'aiConsent':True, 'contextPolicy':CONTEXT_POLICY})
        json.dumps(out)
        result.update(generated=out.get('generated'), nextQuestion=out['assessment'].get('nextQuestion'),
                      providerCaptured=app.adaptive.value(out['guide'],'needs.providersStatus')=='list',
                      providerValue=app.adaptive.value(out['guide'],'needs.providers'),
                      reply=out.get('reply'), checks='passed')
        assert result['providerCaptured']
        assert out.get('generated',{}).get('status')=='complete'
    except Exception as error:
        result.update(checks='failed', exceptionType=type(error).__name__)
        raise
    finally:
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            rows=[db.execute('SELECT charged,measured,status FROM ai_charges WHERE id=?',(key,)).fetchone() for key in receipts]
            result.update(generationStageCount=len(rows), accountedUsd=sum(row[0] for row in rows)/1e9,
                          measuredUsd=sum(row[1] or 0 for row in rows)/1e9,
                          heldUsd=sum(row[0] for row in rows if row[2] in {'reserved','uncertain'})/1e9)
        finally: db.close()
        (PACKET/'live-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        app.server_close()
