"""One six-message fictional incident check; no retries or real customer text."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import uuid
from urllib.error import HTTPError

PACKET=Path(__file__).resolve().parent
ROOT=PACKET.parents[1]
VARIANT=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

MESSAGES=(
    "I'm turning 65 in March and want to understand my Medicare options.",
    'I have COBRA coverage.',
    'My COBRA coverage ends in August.',
    "I'd like Medicare to start after my COBRA ends I guess.",
    'Actually, my COBRA end date is August 15th 2027.',
    "I'm confused. I'm retired and on COBRA; I don't have insurance from a current job. Please explain my options before asking for more dates.",
)

def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted([*VARIANT.glob('*.py'),*VARIANT.glob('*.json')])}

result={'fictional_inputs':True,'profile_saved':False,'automatic_retries':False,
        'maximum_generation_stages':12,'before_sha256':hashes(),'turns':[],
        'technical_pass':False,'human_comprehension':'unobserved'}
stage_ids=[]
def save():
    (PACKET/'live-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')

app=None
try:
    with tempfile.TemporaryDirectory(prefix='cobra-incident-',dir=VARIANT/'var') as tmp:
        app=build(0,database=Path(tmp)/'fictional.sqlite3')
        flow,agent=app.adaptive,app.adaptive.agent
        original_count=agent.count_tokens
        result['token_counts']=[]
        def audited_count(client,payload):
            count=original_count(client,payload)
            result['token_counts'].append({'contract':payload['text']['format']['name'],'input_tokens':count})
            save()
            return count
        agent.count_tokens=audited_count
        reserve=agent.reserve_turn
        def bounded_reserve(*args,**kwargs):
            if len(stage_ids)+2>12:raise AssertionError('No retry or extra generation stages.')
            reservation=reserve(*args,**kwargs)
            stage_ids.extend(s.key for s in reservation.stages.values() if s.key)
            return reservation
        agent.reserve_turn=bounded_reserve
        owner=uuid.uuid4().hex
        g,r=flow.initial()
        state=flow.turn(owner,{'guide':g,'record':r,'action':{'type':'start'},'requestId':uuid.uuid4().hex})
        for index,message in enumerate(MESSAGES,1):
            assert hashes()==result['before_sha256'],'Source changed during run.'
            state=flow.turn(owner,{'guide':state['guide'],'record':state['record'],
                'continuation':state['continuation'],'action':{'type':'message','message':message},
                'requestId':uuid.uuid4().hex,'aiConsent':True,'contextPolicy':CONTEXT_POLICY})
            q=state['assessment'].get('nextQuestion')
            checks={'generated_complete':state.get('generated',{}).get('status')=='complete',
                    'two_calls':state.get('metrics',{}).get('llmCalls')==2,
                    'personal_outputs_held':not state['assessment'].get('personalizedRecommendationAllowed')}
            if index>=2:
                checks['cobra_retained']=flow.value(state['guide'],'coverage.current')==['cobra']
                checks['no_work_insurance_mislabel']=not(q and q['id']=='RC11' and 'work insurance' in q['question'].lower())
            if index==3:
                checks['partial_month_retained']=flow.report(state['record'],'RC11').get('coverageEnd')=='august'
            if index>=4:
                checks['relative_preference_retained']=flow.value(state['guide'],'coverage.requestedStart')=='after_coverage'
                checks['no_start_reask']=not q or q['id']!='T04'
                checks['no_inferred_start']='coverage.requestedStartMonth' not in state['guide']['fields']
            if index>=5:
                checks['ordinal_full_date_retained']=flow.report(state['record'],'RC11').get('coverageEnd')=='2027-08-15'
                checks['no_end_reask']=not q or q['id']!='RC11'
            if index==6:
                checks['retired_report_retained']=(flow.value(state['guide'],'situation.retirement') or {}).get('status')=='retired'
            result['turns'].append({'turn':index,'message':message,'reply':state.get('reply'),
                'question':q,'generated':state.get('generated'),'checks':checks,'metrics':state.get('metrics')})
            save()
            print(json.dumps({'turn':index,'checks':checks}),flush=True)
            assert all(checks.values()),'Stop on the first failed incident check; no retry.'
        result['technical_pass']=True
except Exception as error:
    result['error']={'type':type(error).__name__,'message':str(error)[:300]}
    causes=[]
    cause=error.__cause__
    while cause and len(causes)<4:
        item={'type':type(cause).__name__,'message':str(cause)[:300]}
        if isinstance(cause,HTTPError):
            item['http_status']=cause.code
            try:
                parsed=json.loads(cause.read(16000))
                detail=parsed.get('error',{})
                item['provider_error']={k:detail[k] for k in ('type','code','message') if isinstance(detail.get(k),str)}
            except Exception:pass
        if app and app.adaptive.agent.client.key:
            item=json.loads(json.dumps(item).replace(app.adaptive.agent.client.key,'[REDACTED]'))
        causes.append(item)
        cause=cause.__cause__
    result['error']['causes']=causes
finally:
    if app:
        receipts=[]
        with app.adaptive.agent.budget.db() as db:
            for key in stage_ids:
                row=db.execute('SELECT status,charged,measured FROM ai_charges WHERE id=?',(key,)).fetchone()
                if row:receipts.append(dict(zip(('status','charged_nano_usd','measured_nano_usd'),row)))
        result['receipts']=receipts
        result['accounted_usd']=sum(x['charged_nano_usd'] or 0 for x in receipts)/1e9
        result['measured_usd']=sum(x['measured_nano_usd'] or 0 for x in receipts)/1e9
        app.server_close()
    result['generation_stages']=len(stage_ids)
    result['after_sha256']=hashes()
    result['source_unchanged']=result['before_sha256']==result['after_sha256']
    save()
    print(json.dumps({'technical_pass':result['technical_pass'],'accounted_usd':result.get('accounted_usd'),'error':result.get('error')}))
