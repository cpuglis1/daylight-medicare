"""Fictional ongoing-advisor journey: <=12 paid stages, no retries or saving."""
import json
import argparse
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

PACKET=Path(__file__).resolve().parent
ROOT=PACKET.parents[1]
VARIANT=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

def write(name,value):
    (PACKET/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

parser=argparse.ArgumentParser()
parser.add_argument('--resume-from',type=Path)
args=parser.parse_args()
def accepted_seed(source):
    data=json.loads((source/'live-results.json').read_text())
    rows={}
    prior=data.get('resumedAcceptedFictionalTurnsFrom')
    if prior:
        prior=Path(prior)
        if not prior.is_absolute(): prior=ROOT/prior
        rows.update({row['turn']:(location,row) for location,row in accepted_seed(prior)})
    for row in data.get('turns',[]):
        if row.get('generated',{}).get('status')=='complete': rows[row['turn']]=(source,row)
    return [rows[index] for index in sorted(rows)]
seed_sources=accepted_seed(args.resume_from) if args.resume_from else []
seed_turns=[row for _,row in seed_sources]
max_stages=2*(6-len(seed_turns))
receipts=[];turns=[];case=['setup'];result={'fictionalInputs':True,'savedProfile':False,
    'automaticRetries':False,'maximumGenerationStages':max_stages,'maximumReservationUsd':round(0.0335*max_stages,4),
    'model':'gpt-5.4','reasoning':'none','contextPolicy':CONTEXT_POLICY}
with tempfile.TemporaryDirectory(prefix='ongoing-advisor-check-',dir=VARIANT/'var') as directory:
    app=build(0,database=Path(directory)/'guides.sqlite3')
    agent=app.adaptive.agent
    reserve=agent.reserve_turn
    validate_extract=agent.validate_output
    validate_compose=agent.validate_composition
    def audited_reserve(*args,**kwargs):
        stages=kwargs.get('stages',('extract','compose'))
        if len(receipts)+len(stages)>max_stages:
            raise AssertionError('Paid stage ceiling reached; no retry.')
        reservation=reserve(*args,**kwargs)
        receipts.extend(stage.key for stage in reservation.stages.values())
        return reservation
    def audited_extract(value,message,guide,facts,eligible,owner):
        output=validate_extract(value,message,guide,facts,eligible,owner)
        write(case[0]+'-extraction.json',{'message':message,'raw':value,'validated':output})
        return output
    def audited_compose(value,context,candidates):
        capture={'output':value,'context':context,'question_candidates':candidates}
        try:
            output=validate_compose(value,context,candidates);capture['accepted']=True
            return output
        except Exception as error:
            capture.update(accepted=False,error=str(error));raise
        finally:
            write(case[0]+'-composition.json',capture)
    agent.reserve_turn=audited_reserve
    agent.validate_output=audited_extract
    agent.validate_composition=audited_compose
    owner=uuid.uuid4().hex
    g,r=app.adaptive.initial()
    state=app.adaptive.turn(owner,{'guide':g,'record':r,'action':{'type':'start'},'requestId':str(uuid.uuid4())})
    if seed_turns:
        last=seed_turns[-1]['turn']
        seed=json.loads((seed_sources[-1][0]/('turn-'+str(last)+'.json')).read_text())
        state=app.adaptive.turn(owner,{'guide':seed['guide'],'record':seed['record'],'action':{'type':'refresh'},'requestId':str(uuid.uuid4())})
        for source,row in seed_sources:
            index=row['turn']
            extraction=json.loads((source/('turn-'+str(index)+'-extraction.json')).read_text())
            composition=json.loads((source/('turn-'+str(index)+'-composition.json')).read_text())
            target=row.get('target')
            app.adaptive.memory.remember(owner,app.adaptive.current_chain[owner],CONTEXT_POLICY,
                row['message'],row.get('reply') or '',row.get('question') or '',
                question_target=target,candidate_ids=[target] if target else [],
                goal=extraction['validated'].get('goal_quote') or None,
                agenda_update=composition['output'].get('agenda_update'))
        result['resumedAcceptedFictionalTurnsFrom']=str(args.resume_from)
        result['resumedTurnCount']=len(seed_turns)
    script=[
        "I am turning 65 years old in november and want to enroll in medicare soon. I don't know much about my options.",
        "I'm not sure when coverage should start. What do you suggest?",
        "Before I answer, what does Part B mean?",
        "Okay, let's continue. My health insurance is through my wife's current job.",
        "Her job ends in March 2027, and that health insurance ends in April 2027.",
        "Actually, I turn 65 in December, not November."
    ]
    try:
        for index,message in enumerate(script,1):
            if index <= len(seed_turns): continue
            case[0]='turn-'+str(index)
            payload={'guide':state['guide'],'record':state['record'],'continuation':state['continuation'],
                'action':{'type':'message','message':message},'requestId':str(uuid.uuid4()),
                'aiConsent':True,'contextPolicy':CONTEXT_POLICY}
            started=time.monotonic()
            state=app.adaptive.turn(owner,payload)
            row={'turn':index,'message':message,'reply':state.get('reply'),
                 'question':(state['assessment'].get('nextQuestion') or {}).get('question'),
                 'target':(state['assessment'].get('nextQuestion') or {}).get('id'),
                 'generated':state.get('generated'),'seconds':round(time.monotonic()-started,3)}
            turns.append(row);write(case[0]+'.json',state)
            print(json.dumps(row,ensure_ascii=False),flush=True)
            assert state.get('generated',{}).get('status')=='complete',state.get('generated')
            assert not state.get('review'),'No routine report confirmation.'
            assert state['metrics']['llmCalls']==2
            assert state['guide']['fields']['situation.age65']['value']['year'] is None
            if index==1:
                assert state['guide']['fields']['situation.age65']['value']['month']==11
                assert 'coverage.requestedStartMonth' not in state['guide']['fields']
            if index==2:
                assert row['reply'],'Answer the timing question.'
                assert row['target']=='T05','Current insurance is the unresolved timing dependency.'
            if index==3:
                assert state['advisor']['teachingFactIds'],'Ground the Part B explanation.'
            if index==4:
                assert state['guide']['fields']['coverage.current']['value']==['employer']
                assert state['record']['facts']['RC09']['value']['choice']=='spouse_job'
                assert row['target']!='T05','Do not repeat known current insurance.'
            if index==5:
                assert state['record']['facts']['RC11']['value']['jobEnd']=='2027-03'
                assert state['record']['facts']['RC11']['value']['coverageEnd']=='2027-04'
            if index==6:
                assert state['guide']['fields']['situation.age65']['value']=={'month':12,'year':None}
        result['checks']='passed'
    except Exception as error:
        result.update(checks='failed',failure=str(error));raise
    finally:
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            columns=[item[1] for item in db.execute('PRAGMA table_info(ai_charges)')]
            rows=[dict(zip(columns,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipts]
            result.update(generationStageCount=len(rows),measuredEstimateUsd=sum(row['measured'] or 0 for row in rows)/1e9,
                accountedUsd=sum(row['charged'] for row in rows)/1e9,
                heldUsd=sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9)
        finally:
            db.close()
        result['turns']=turns;write('live-results.json',result)
        app.server_close()
