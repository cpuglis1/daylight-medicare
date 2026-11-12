"""Explicit fictional live check: at most 14 generation stages, no retry/save.

Uses the existing key loading, model settings and shared ledger. Only synthetic
conversation traces and this run's own charge receipts are written here.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

SELF_OPENING = {'type':'message','message':
    'Turning 65 in november and looking to understand my medicare options'}


def load_replay_prefix(path):
    """Read only explicitly fictional archived captures, never a guest profile.

    Replay is a diagnostic continuation of successful captured stages. It is
    deliberately not evidence of an uninterrupted final-version live run.
    """
    source = Path(path).resolve()
    if source.parent != PACKET or not re.fullmatch(r'attempt-[1-9][0-9]*',source.name):
        raise ValueError('Replay requires an archived fictional attempt in this evidence packet.')
    results = json.loads((source/'live-results.json').read_text())
    if (results.get('fictional_inputs') is not True or results.get('saved_profile') is not False
            or results.get('automatic_retries') is not False or results.get('model') != 'gpt-5.4'):
        raise ValueError('Replay source must be explicitly fictional, unsaved and without retries.')
    turns = results.get('turns',[])
    if (len(turns) < 2 or any(turns[index].get('case') != 'self'
            or turns[index].get('turn') != index+1
            or turns[index].get('generated',{}).get('status') != 'complete' for index in range(2))
            or turns[0].get('action') != SELF_OPENING):
        raise ValueError('Replay requires the exact two successful fictional opening turns.')
    question = (turns[0].get('question') or {}).get('id')
    expected = ({'type':'choice','id':'T05','fields':{'choice':'employer'}} if question == 'T05'
        else {'type':'choice','id':'RC01','fields':{'choice':'self'}} if question == 'RC01' else None)
    if expected is None or turns[1].get('action') != expected:
        raise ValueError('The archived finite answer does not match the expected opening action.')
    interpretation = json.loads((source/'self-1-interpretation.json').read_text())
    compositions = [json.loads((source/f'self-{index}-composition.json').read_text()) for index in (1,2)]
    if (interpretation.get('message') != SELF_OPENING['message']
            or not isinstance(interpretation.get('raw'),dict)
            or not isinstance(interpretation.get('accepted'),dict)
            or any(item.get('accepted') is not True or not isinstance(item.get('raw'),dict)
                   for item in compositions)
            or compositions[0].get('context',{}).get('current_message') != SELF_OPENING['message']):
        raise ValueError('Replay requires accepted raw captures for the exact fictional actions.')
    submitted = compositions[1].get('context',{}).get('submitted_answer',{})
    if submitted.get('question_id') != expected['id'] or submitted.get('fields') != expected['fields']:
        raise ValueError('The archived composition is not bound to the expected finite answer.')
    return {'source':str(source), 'turns':{
        ('self',1):{'action':SELF_OPENING,'frames':[
            ('daylight_guide_commands',interpretation['raw']),
            ('daylight_resolved_conversation',compositions[0]['raw'])]},
        ('self',2):{'action':expected,'frames':[
            ('daylight_resolved_conversation',compositions[1]['raw'])]}}}


def replay_transport(frames):
    """Return accepted archived outputs without invented provider usage."""
    remaining = copy.deepcopy(frames)
    def transport(payload):
        name = payload['text']['format']['name']
        if not remaining or name != remaining[0][0]:
            raise AssertionError('Unexpected replay stage; no provider request was started.')
        _, raw = remaining.pop(0)
        return {'status':'completed','output':[{'content':[
            {'type':'output_text','text':json.dumps(raw,ensure_ascii=False)}]}]}
    return transport, remaining


def write(name, value):
    (PACKET / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def run(replay_prefix=None, case='all'):
    prefix = load_replay_prefix(replay_prefix) if replay_prefix is not None else None
    stages = []
    traces = []
    token_checks = []
    context = {'case': 'setup', 'turn': 0}
    ceiling = 6 if case == 'caregiver' else 14
    checks = {}
    result = {'fictional_inputs': True, 'saved_profile': False, 'automatic_retries': False,
              'selected_case': case, 'checks_passed': False, 'quality_checks': checks,
              'maximum_generation_stages': ceiling, 'maximum_reservation_usd': ceiling * 0.0335,
              'model': 'gpt-5.4', 'reasoning': 'none', 'turns': traces,
              'token_checks': token_checks}
    if prefix:
        result.update(replay_prefix=prefix['source'],synthetic_prefix_replay=True,
            uninterrupted_final_live_run=False,
            evidence_note='The first two turns replay accepted fictional captures; only subsequent stages use the provider.')
    with tempfile.TemporaryDirectory(prefix='curriculum-live-', dir=VARIANT/'var') as temporary:
        app = build(0, database=Path(temporary)/'fictional.sqlite3')
        agent = app.adaptive.agent
        original_reserve = agent.reserve_turn
        original_extract = agent.validate_output
        original_compose = agent.validate_composition
        original_count = agent.count_tokens
        def count(client, payload):
            number = original_count(client, payload)
            content = json.loads(payload['input'][0]['content'])
            resolved = content.get('confirmed_context', content.get('resolved_context', {}))
            token_checks.append({'case': context['case'], 'turn': context['turn'],
                'contract': payload['text']['format']['name'], 'tokens': number,
                'history_exchanges': len(resolved.get('recent_exchanges', []))})
            write(f"{context['case']}-{context['turn']}-counted-input.json", payload)
            write('live-results.json', result)
            return number
        agent.count_tokens = count
        def reserve(*args, **kwargs):
            names = kwargs.get('stages', ('extract', 'compose'))
            if len(stages) + len(names) > ceiling:
                raise AssertionError('Explicit generation-stage ceiling reached; no retry.')
            reservation = original_reserve(*args, **kwargs)
            stages.extend(stage.key for stage in reservation.stages.values() if stage.key is not None)
            return reservation
        def extract(value, message, guide, facts, eligible, owner):
            accepted = original_extract(value, message, guide, facts, eligible, owner)
            write(f"{context['case']}-{context['turn']}-interpretation.json",
                  {'message': message, 'raw': value, 'accepted': accepted,
                   'reviewed_fact_ids': [item['id'] for item in facts],
                   **({'synthetic_replay':True} if context.get('synthetic_replay') else {})})
            return accepted
        def compose(value, resolved, candidates):
            capture = {'raw': value, 'context': resolved, 'candidates': candidates,
                **({'synthetic_replay':True} if context.get('synthetic_replay') else {})}
            try:
                accepted = original_compose(value, resolved, candidates)
                capture.update(accepted=True, validated=accepted)
                return accepted
            except Exception as error:
                capture.update(accepted=False, error=str(error))
                raise
            finally:
                write(f"{context['case']}-{context['turn']}-composition.json", capture)
        agent.reserve_turn, agent.validate_output, agent.validate_composition = reserve, extract, compose
        def initial(case):
            context.update(case=case, turn=0)
            owner = uuid.uuid4().hex
            g, r = app.adaptive.initial()
            state = app.adaptive.turn(owner, {'guide': g, 'record': r,
                'action': {'type': 'start'}, 'requestId': str(uuid.uuid4())})
            return owner, state
        def take(owner, state, action):
            context['turn'] += 1
            payload = {'guide': state['guide'], 'record': state['record'],
                       'continuation': state['continuation'], 'requestId': str(uuid.uuid4()),
                       'action': action, 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY}
            started = time.perf_counter()
            replay = prefix['turns'].get((context['case'],context['turn'])) if prefix else None
            context['synthetic_replay'] = bool(replay)
            if replay:
                if action != replay['action']:
                    raise AssertionError('Replay action changed; no provider request was started.')
                budget, transport, counter = agent.budget, agent.client.transport, agent.count_tokens
                replayed, remaining = replay_transport(replay['frames'])
                def no_token_endpoint(*_):
                    raise AssertionError('Replay must never call the provider token endpoint.')
                agent.budget, agent.client.transport, agent.count_tokens = None, replayed, no_token_endpoint
                try:
                    out = app.adaptive.turn(owner,payload)
                    if remaining:
                        raise AssertionError('Replay stages did not complete; no automatic retry.')
                finally:
                    agent.budget, agent.client.transport, agent.count_tokens = budget, transport, counter
            else:
                out = app.adaptive.turn(owner, payload)
            row = {'case': context['case'], 'turn': context['turn'], 'action': action,
                   'elapsed_seconds': round(time.perf_counter()-started, 3),
                   'reply': out.get('reply'), 'question': out['assessment'].get('nextQuestion'),
                   'generated': out.get('generated'), 'advisor': out.get('advisor'),
                   'education': out.get('education'), 'metrics': out.get('metrics'),
                   'guide': out['guide']['fields'], 'facts': out['record']['facts']}
            if replay:
                row.update(synthetic_replay=True,replay_source=prefix['source'],
                           shared_budget_charged=False)
            traces.append(row)
            write('live-results.json', result)
            print(json.dumps({'case': row['case'], 'turn': row['turn'],
                              'generated': row['generated'], 'reply': row['reply'],
                              'question': (row['question'] or {}).get('question'),
                              'visual': (row['advisor'] or {}).get('visual'),
                              'seconds': row['elapsed_seconds'],
                              **({'synthetic_replay':True} if replay else {})}, ensure_ascii=False), flush=True)
            if out.get('generated', {}).get('status') != 'complete':
                raise AssertionError('Live composition did not complete; inspect trace before further calls.')
            return out
        def require(name, passed):
            checks[name] = bool(passed)
            if not passed:
                raise AssertionError('Fictional quality check failed: ' + name)
        try:
            if case == 'all':
                owner, state = initial('self')
                state = take(owner, state, copy.deepcopy(SELF_OPENING))
                require('self_reference_captured', app.adaptive.value(state['guide'], 'subject.role') == 'self')
                require('birthday_precision_preserved', app.adaptive.value(state['guide'], 'situation.age65') == {'month': 11, 'year': None})
                q = state['assessment'].get('nextQuestion') or {}
                action = ({'type': 'choice', 'id': 'T05', 'fields': {'choice': 'employer'}} if q.get('id') == 'T05'
                          else {'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}} if q.get('id') == 'RC01'
                          else {'type': 'message', 'message': 'I have health insurance through my current job.'})
                state = take(owner, state, action)
                return_point = (state['assessment'].get('nextQuestion') or {}).get('id')
                state = take(owner, state, {'type': 'message', 'message':
                    'Could you explain the two Medicare paths again?'})
                require('requested_revisit_recorded', any(item['concept_id'] == 'coverage_paths' and item['deliveries'] >= 2
                    for item in (state.get('education') or {}).get('covered', [])))
                require('self_return_point_preserved', (state['assessment'].get('nextQuestion') or {}).get('id') == return_point)
            owner, state = initial('caregiver')
            state = take(owner, state, {'type': 'message', 'message':
                'I am helping my mother, who turns 65 in November. I have insurance through my current job, but she has no health insurance. She wants to understand her Medicare options.'})
            require('caregiver_scope_preserved', app.adaptive.value(state['guide'], 'subject.role') == 'someone'
                and app.adaptive.value(state['guide'], 'coverage.current') == ['none'])
            require('caregiver_role_not_reasked', (state['assessment'].get('nextQuestion') or {}).get('id') != 'RC01')
            return_point = (state['assessment'].get('nextQuestion') or {}).get('id')
            state = take(owner, state, {'type': 'message', 'message': 'Before I answer, what does Part B cover?'})
            require('caregiver_return_point_preserved', app.adaptive.memory.brief(owner,
                app.adaptive.current_chain[owner], CONTEXT_POLICY).get('pending_question') == return_point)
            state = take(owner, state, {'type': 'message', 'message': 'Actually, she turns 65 in December, not November.'})
            require('caregiver_correction_preserved', app.adaptive.value(state['guide'], 'situation.age65') == {'month': 12, 'year': None})
            result['checks_passed'] = all(checks.values())
            result['all_turns_complete'] = True
        except Exception as error:
            result['error'] = {'type': type(error).__name__, 'message': str(error)}
            result['all_turns_complete'] = False
        finally:
            receipts = []
            with agent.budget.db() as db:
                for identifier in stages:
                    row = db.execute('SELECT id,status,charged,measured,input_tokens,output_tokens FROM ai_charges WHERE id=?', (identifier,)).fetchone()
                    if row: receipts.append(dict(zip(('id','status','charged_nano_usd','measured_nano_usd','input_tokens','output_tokens'), row)))
            result['generation_stages_reserved'] = len(stages)
            result['receipts'] = receipts
            result['measured_usd'] = sum(row['measured_nano_usd'] or 0 for row in receipts)/1e9
            result['accounted_usd'] = sum(row['charged_nano_usd'] or 0 for row in receipts)/1e9
            write('live-results.json', result)
            app.server_close()
        print(json.dumps({key:value for key,value in result.items() if key not in {'turns','receipts'}}, indent=2))
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', help='Explicitly allow the bounded fictional provider check.')
    parser.add_argument('--case', choices=('all', 'caregiver'), default='all',
                        help='Run the whole check or only the three caregiver turns.')
    parser.add_argument('--replay-prefix',type=Path,
        help='Replay two accepted fictional opening turns from a local archived attempt before continuing live.')
    args = parser.parse_args()
    if not args.run_live:
        parser.error('Use --run-live only for the explicitly authorized bounded fictional check.')
    result = run(args.replay_prefix, args.case)
    raise SystemExit(0 if result.get('all_turns_complete') and result.get('checks_passed') else 1)
