"""Bounded fictional probes of one shared framework, with unchanged accounting."""
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid

PACKET = Path(__file__).resolve().parent
VARIANT = PACKET.parents[1] / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

MODEL = 'gpt-6.1-sol'
CASES = [
    {'name': 'newcomer_self', 'message': "I'm turning 65 next year and this is all new to me. I don't understand what Medicare is. Where do I start?",
     'expectation': 'Small useful foundation, no assumption of coverage or eligibility, at most one consequential next question.'},
    {'name': 'caregiver_mixed', 'message': "I'm reviewing Mom's Original Medicare and supplement. I understand the premium is the monthly payment, but I don't understand what a deductible does. Keeping her doctors matters. How should we think about this?",
     'expectation': 'Distinguish understood premium from uncertain deductible; explain the latter and connect it to the coverage review, retaining doctor uncertainty.'},
    {'name': 'experienced_self', 'message': "I'm reviewing my Medicare Advantage plan. I know the premium is what I pay monthly and copays are what I pay for care. Please skip the basics. I want help finding out if my cardiologist is in network next year.",
     'expectation': 'Honor the requested depth; work toward exact plan, year and clinician checks without asserting network participation.'},
    {'name': 'confident_misconception', 'message': "I'm researching options for myself. I know a zero premium means all my medical care is free, so I just need a zero premium plan. Is that the right way to choose?",
     'expectation': 'Correct the cost misconception without shaming, explain a bounded distinction and avoid treating confidence as understanding or suggesting an unsupported plan.'},
]


def run():
    started = time.monotonic()
    result = {'model': MODEL, 'fictional': True, 'scope': 'four independent first-turn probes; not complete journeys',
              'cases': [], 'stage_limit': 8}
    path = PACKET / 'live.json'
    keys = []
    with tempfile.TemporaryDirectory(prefix='framework-eval-', dir=VARIANT / 'var') as temporary:
        app = build(0, database=Path(temporary) / 'fictional.sqlite3')
        agent = app.adaptive.model_agents[MODEL]
        agent.connection_retries = 0
        original_reserve = agent.reserve_turn
        original_validate = agent.validate_composition
        captured = {}
        def reserve(stages=('extract', 'compose')):
            if len(keys) + len(stages) > result['stage_limit']:
                raise RuntimeError('Evaluation stage ceiling reached.')
            receipt = original_reserve(stages=stages)
            keys.extend(s.key for s in receipt.stages.values() if s.key is not None)
            return receipt
        def validate(value, context, moves):
            captured.update(proposed=value, learner_context=context.get('learner_context'),
                            task_work=context.get('task_work'), comparison_status=context.get('comparison_status'))
            return original_validate(value, context, moves)
        agent.reserve_turn, agent.validate_composition = reserve, validate
        try:
            for case in CASES:
                owner = uuid.uuid4().hex
                guide, record = app.adaptive.initial()
                out = app.adaptive.turn(owner, {'guide': guide, 'record': record,
                    'action': {'type': 'start'}, 'requestId': str(uuid.uuid4())})
                captured.clear()
                tick = time.monotonic()
                out = app.adaptive.turn(owner, {'guide': out['guide'], 'record': out['record'],
                    'continuation': out['continuation'], 'requestId': str(uuid.uuid4()),
                    'action': {'type': 'message', 'message': case['message']},
                    'model': MODEL, 'aiProvider': 'OpenAI', 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
                row = {**case, **captured, 'reply': out.get('reply'),
                       'question': (out['assessment'].get('nextQuestion') or {}).get('question'),
                       'generated': out.get('generated'), 'notice': out.get('notice'),
                       'elapsed_seconds': round(time.monotonic() - tick, 2)}
                result['cases'].append(row)
                path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
                print(json.dumps({k:v for k,v in row.items()
                    if k not in {'proposed','task_work','comparison_status'}}, ensure_ascii=False), flush=True)
                if (out.get('generated') or {}).get('status') != 'complete':
                    result['stop'] = 'response unavailable; no further paid probes'
                    break
        finally:
            with agent.budget.db() as db:
                rows = [db.execute('SELECT charged, measured FROM ai_charges WHERE id=?', (key,)).fetchone() for key in keys]
            result['elapsed_seconds'] = round(time.monotonic() - started, 2)
            result['accounted_usd'] = sum(row[0] or 0 for row in rows if row) / 1e9
            result['measured_usd'] = sum(row[1] or 0 for row in rows if row) / 1e9
            path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
            app.server_close()


if __name__ == '__main__':
    run()
