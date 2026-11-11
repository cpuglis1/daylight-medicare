"""Two opt-in live fictional conversations against the unchanged advisor backend.

Six prewritten turns per case; no auto retry, persona rescue or profile saving.
Shares the real approved budget ledger and current model/policy. Captured text
is fictional evaluation evidence, never production guest dialogue.
"""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid
from zoneinfo import ZoneInfo

VARIANT = Path(__file__).resolve().parents[1]
ROOT = VARIANT.parents[1]
sys.path.insert(0, str(VARIANT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from journey_evaluator import completion_observer, safe_diagnostic_text

CASES = [
    {'id':'provider_and_costs','title':'Keeping a cardiologist and understanding visit costs',
     'fictional':True,'messages':[
        "I'm checking Medicare coverage for myself in Collier County. I'd like to keep my cardiologist and understand what visits could cost. Where should I start?",
        "I currently have Aetna Medicare Advantage. My cardiologist is Dr. Maya Reed at Cypress Heart Clinic in Naples. I don't know the exact plan name.",
        "Before we go further, what does Medicare Advantage mean? Does the office accepting Aetna prove it takes my particular plan?",
        "Actually, the office is in Bonita Springs, not Naples. My home ZIP is 34102. I still don't have the exact plan name.",
        "My main concern is being able to see that doctor. I don't have a firm budget. What can we establish now, and what would still need checking?",
        "Please give me a short list of what to ask the plan and the office. Don't contact anyone. No more questions."
     ]},
    {'id':'caregiver_and_coverage','title':'Helping a parent understand coverage and practical help',
     'fictional':True,'messages':[
        "I'm helping my mother understand Medicare. She lives in Naples. We need to work out coverage and practical help, and I'm not sure where to start.",
        "This is for my mother. She has Original Medicare. I help her with rides and paperwork, but I don't make health decisions for her. I want to understand coverage before we choose anything.",
        "I'm confused about Medigap and Medicare Advantage. Are they the same thing, and which one goes with Original Medicare?",
        "She wants to keep her own doctor. Please don't assume she wants to change coverage. Transport to appointments matters too. Do those needs tell us whether Medicare will pay for rides?",
        "I don't know her exact coverage dates or whether she qualifies for financial help. Can we keep those open and focus on what to ask next?",
        "Summarize what we know, what remains unverified, and who we should ask. No calls or referrals. No more questions."
     ]}
]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def hashes():
    paths = [*VARIANT.glob('*.py'), *VARIANT.glob('*.json'), Path(__file__)]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def run_live(case_id=None):
    from server import build
    from natural_flow import CONTEXT_POLICY
    from request_limits import INPUT_TOKENS, OUTPUT_TOKENS
    packet = ROOT/'audit-evidence/live-sample-conversations-20261103'
    packet.mkdir(parents=True, exist_ok=True)
    attempt = packet/(datetime.now(ZoneInfo('America/New_York')).strftime('%Y%m%dT%H%M%S%z')+'-'+uuid.uuid4().hex[:6])
    attempt.mkdir()
    frozen = hashes()
    cases=[case for case in CASES if case_id is None or case['id']==case_id]
    maximum_stages=2*sum(len(case['messages']) for case in cases)
    if not cases:raise ValueError('Use a retained fictional case.')
    write(attempt/'spec.json',{'cases':cases,'maximum_generation_stages':maximum_stages,
        'automatic_retries':False,'source_changes_during_run':False,
        'rubric':['task_recognition','verification_distinctions','teaching_in_context',
            'continuity_and_corrections','useful_next_step','burden_and_control'],
        'score_anchors':{'0':'material failure','1':'partly successful with a material gap','2':'successful in the observed conversation'},
        'performance':['backend_wall_seconds','extraction_and_composition_seconds','input_and_output_tokens','measured_estimated_cost'],
        'consumer_comprehension':'unobserved','personas':'fictional, prewritten, no adaptive rescue'})
    result = {'fictional':True,'attempt':str(attempt),'source_before':frozen,'cases':[],
        'receipts':[],'maximum_generation_stages':maximum_stages,'saved_profile':False,
        'automatic_retries':False,'errors':[]}
    active = {'case':'setup','turn':0}
    stage_ids=[]
    app=None
    def save():write(attempt/'result.json',result)
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='live-samples-',dir=VARIANT/'var') as temporary:
            app=build(0,database=Path(temporary)/'fictional.sqlite3')
            flow,agent=app.adaptive,app.adaptive.agent
            if (agent.client.model!='gpt-5.4' or agent.reasoning_effort!='none'
                    or agent.composition_reasoning_effort!='none'
                    or agent.budget.daily_cap_nano_usd!=15_000_000_000):
                raise RuntimeError('Use the current approved model and budget policy.')
            result['model']='gpt-5.4'
            result['budget_before']=agent.budget.summary()
            result['maximum_reserved_usd'] = (result['budget_before']['remainingUsd'] if INPUT_TOKENS is None
                else maximum_stages*(INPUT_TOKENS*2500+OUTPUT_TOKENS*15000)/1e9)
            if not result['budget_before']['canRequest']:
                raise RuntimeError(result['budget_before']['reason'])
            if result['budget_before']['remainingUsd'] < result['maximum_reserved_usd']:
                raise RuntimeError('Insufficient remaining shared allowance for the frozen two-case evaluation ceiling.')
            reserve,extract,compose,count = agent.reserve_turn,agent.validate_output,agent.validate_composition,agent.count_tokens
            def observe_completion(capture):
                write(attempt/(active['case']+'-turn-'+str(active['turn'])+'-provider-completion.json'),capture)
            agent._complete=completion_observer(agent._complete,observe_completion,agent.client.key)
            def audited_reserve(stages=('extract','compose')):
                if len(stage_ids)+len(stages)>maximum_stages:raise RuntimeError('Evaluation generation-stage ceiling reached.')
                reservation=reserve(stages)
                stage_ids.extend(stage.key for stage in reservation.stages.values() if stage.key is not None)
                return reservation
            def audited_count(client,payload):
                started=time.perf_counter()
                check={**active,'stage':payload['text']['format']['name']}
                try:
                    tokens=count(client,payload)
                    check['input_tokens']=tokens
                    return tokens
                except Exception as error:
                    check['failure_code']=getattr(error,'failure_code','count_unavailable')
                    check['diagnostic']=copy.deepcopy(getattr(error,'diagnostic',{}))
                    raise
                finally:
                    check['seconds']=round(time.perf_counter()-started,3)
                    result.setdefault('token_checks',[]).append(check)
                    save()
            def audited_extract(value,message,guide,facts,eligible,owner):
                capture={'raw_proposal':copy.deepcopy(value)}
                try:
                    accepted=extract(value,message,guide,facts,eligible,owner)
                    capture['validated']=copy.deepcopy(accepted)
                    return accepted
                finally:
                    write(attempt/(active['case']+'-turn-'+str(active['turn'])+'-interpretation.json'),capture)
            def audited_compose(value,context,candidates):
                capture={'raw_proposal':copy.deepcopy(value),'resolved_context':copy.deepcopy(context),
                    'candidates':copy.deepcopy(candidates)}
                try:
                    accepted=compose(value,context,candidates)
                    capture['validated']=copy.deepcopy(accepted)
                    return accepted
                finally:
                    write(attempt/(active['case']+'-turn-'+str(active['turn'])+'-composition.json'),capture)
            agent.reserve_turn,agent.count_tokens=audited_reserve,audited_count
            agent.validate_output,agent.validate_composition=audited_extract,audited_compose
            terminal=False
            for case in cases:
                if terminal:break
                owner=uuid.uuid4().hex
                guide,record=flow.initial()
                state=flow.turn(owner,{'guide':guide,'record':record,'requestId':uuid.uuid4().hex,'action':{'type':'start'}})
                conversation={'id':case['id'],'title':case['title'],'turns':[],'all_turns_complete':False}
                result['cases'].append(conversation)
                for number,message in enumerate(case['messages'],1):
                    if hashes()!=frozen:raise RuntimeError('Source changed during evaluation.')
                    active.update(case=case['id'],turn=number)
                    row={'turn':number,'user':message}
                    conversation['turns'].append(row)
                    started=time.perf_counter()
                    try:
                        state=flow.turn(owner,{'guide':state['guide'],'record':state['record'],
                            'continuation':state['continuation'],'requestId':uuid.uuid4().hex,
                            'action':{'type':'message','message':message},'aiConsent':True,'contextPolicy':CONTEXT_POLICY})
                        row.update(reply=state.get('reply',''),question=state['assessment'].get('nextQuestion'),
                            notice=state.get('notice'),generated=state.get('generated'),metrics=state.get('metrics'),
                            advisor=state.get('advisor'),task_work=state.get('task_work'),education=state.get('education'))
                        write(attempt/(case['id']+'-turn-'+str(number)+'-state.json'),{k:v for k,v in state.items() if k!='continuation'})
                    except Exception as error:
                        row['error']={'type':type(error).__name__,'message':safe_diagnostic_text(error,agent.client.key)}
                    finally:
                        row['elapsed_seconds']=round(time.perf_counter()-started,3)
                        save()
                    print(json.dumps({'case':case['id'],'turn':number,'seconds':row['elapsed_seconds'],
                        'generated':row.get('generated',{}).get('status'),'error':row.get('error',{}).get('type')}),flush=True)
                    if row.get('error') or row.get('generated',{}).get('status')!='complete':
                        provider=(row.get('generated') or {}).get('providerFailure') or {}
                        terminal=provider.get('provider_code') in {'credit_balance_exhausted','insufficient_quota'}
                        break
                conversation['all_turns_complete']=(len(conversation['turns'])==6 and
                    all(row.get('generated',{}).get('status')=='complete' for row in conversation['turns']))
                save()
            result['completed_two_conversations']=len(result['cases'])==2 and all(c['all_turns_complete'] for c in result['cases'])
            result['completed_selected_conversations']=all(c['all_turns_complete'] for c in result['cases'])
    except Exception as error:
        result['errors'].append({'type':type(error).__name__,'message':safe_diagnostic_text(error,
            app.adaptive.agent.client.key if app else ''),**active})
    finally:
        if app:
            try:
                budget=app.adaptive.agent.budget
                with budget.db() as db:
                    for identifier in stage_ids:
                        row=db.execute('SELECT status,charged,measured,input_tokens,output_tokens FROM ai_charges WHERE id=?',(identifier,)).fetchone()
                        if row:result['receipts'].append(dict(zip(('status','charged_nano_usd','measured_nano_usd','input_tokens','output_tokens'),row)))
                result['budget_after']=budget.summary()
            except Exception as error:
                result['accounting_error']=safe_diagnostic_text(error,app.adaptive.agent.client.key)
            app.server_close()
        result['source_unchanged']=hashes()==frozen
        result['generation_stages_reserved']=len(stage_ids)
        result['measured_usd']=sum(r['measured_nano_usd'] or 0 for r in result['receipts'])/1e9
        result['accounted_usd']=sum(r['charged_nano_usd'] or 0 for r in result['receipts'])/1e9
        result['held_usd']=sum(r['charged_nano_usd'] or 0 for r in result['receipts'] if r['status'] in {'reserved','uncertain'})/1e9
        save()
    print(json.dumps({'attempt':str(attempt),'completed_two_conversations':result.get('completed_two_conversations',False),
        'source_unchanged':result['source_unchanged'],'measured_usd':result['measured_usd'],
        'accounted_usd':result['accounted_usd'],'held_usd':result['held_usd'],'errors':result['errors']}),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--case',choices=[case['id'] for case in CASES])
    args=parser.parse_args()
    if args.live:run_live(args.case)
    else:print(json.dumps({'live':False,'cases':CASES},indent=2))
