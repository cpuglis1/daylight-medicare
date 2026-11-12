"""Fictional 3-turn check: bounded six paid stages; no retry, saving or real data."""
import copy
import http.cookiejar
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
import uuid

PACKET=Path(__file__).resolve().parent
ROOT=PACKET.parents[1];VARIANT=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY


def write(name,value):(PACKET/name).write_text(json.dumps(value,indent=2)+'\n')

receipts=[];timings=[];case=['setup'];outputs=[]
result={'maximumReservationUsd':0.201,'maximumGenerationStages':6,'fictionalInputs':True,
        'automaticRetries':False,'savedProfile':False,'extractReasoning':'none'}
with tempfile.TemporaryDirectory(prefix='contextual-check-',dir=VARIANT/'var') as temp:
    app=build(0,database=Path(temp)/'guides.sqlite3')
    agent=app.adaptive.agent;agent.reasoning_effort='none'
    reserve=agent.reserve_turn;count=agent.count_tokens;validate=agent.validate_composition
    def audited_reserve(*args,**kwargs):
        stages=kwargs.get('stages',('extract','compose'))
        assert len(receipts)+len(stages)<=6,'The paid stage ceiling is final.'
        reservation=reserve(*args,**kwargs)
        receipts.extend(stage.key for stage in reservation.stages.values())
        return reservation
    def timed_count(client,payload):
        start=time.monotonic()
        try:return count(client,payload)
        finally:timings.append({'case':case[0],'stage':payload['text']['format']['name'],
            'part':'count_tokens','seconds':round(time.monotonic()-start,3)})
    def audited_composition(value,context,moves):
        # Only this harness's fictional conversation is retained for review.
        data={'value':value,'context':context,'moves':moves}
        try:
            out=validate(value,context,moves);data['accepted']=True;return out
        except Exception as error:
            data.update(accepted=False,error=str(error));raise
        finally:write(case[0]+'-composition.json',data)
    agent.reserve_turn=audited_reserve;agent.count_tokens=timed_count;agent.validate_composition=audited_composition
    for method in ('extract','compose'):
        original=getattr(agent,method)
        def wrapped(*args,_original=original,_method=method,**kwargs):
            start=time.monotonic()
            try:return _original(*args,**kwargs)
            finally:timings.append({'case':case[0],'stage':_method,'part':'whole_stage',
                'seconds':round(time.monotonic()-start,3)})
        setattr(agent,method,wrapped)
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{app.server_port}';jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def get(path):return json.load(opener.open(base+path,timeout=90))
    session=get('/api/guest/session')
    def turn(state,action,**extra):
        payload={'guide':state['guide'],'record':state['record'],'action':action,'requestId':str(uuid.uuid4()),**extra}
        if state.get('continuation'):payload['continuation']=state['continuation']
        request=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
        return json.load(opener.open(request,timeout=90))
    try:
        g,r=app.adaptive.initial();state=turn({'guide':g,'record':r},{'type':'start'})
        scripts=[
          ('turn-1',"I've been retired for a few years and turn 65 in November. I'm new to Medicare and want to find coverage that includes my prescriptions. My health insurance is through my wife's current job."),
          ('turn-2','ASAP!!'),
          ('turn-3',"I haven't applied yet. Before we keep going, what is Part B?")]
        for name,message in scripts:
            case[0]=name;start=time.monotonic()
            state=turn(state,{'type':'message','message':message},aiConsent=True,contextPolicy=CONTEXT_POLICY)
            row={'case':name,'message':message,'seconds':round(time.monotonic()-start,3),
                'reply':state.get('reply'),'question':(state['assessment'].get('nextQuestion') or {}).get('question'),
                'target':(state['assessment'].get('nextQuestion') or {}).get('id'),'generated':state.get('generated')}
            outputs.append(row);write(name+'.json',{'message':message,'response':state})
            print(json.dumps(row),flush=True)
            assert state.get('generated',{}).get('status')=='complete',state.get('generated')
            assert not state.get('review'),'Routine reports must not open acceptance review.'
            if name=='turn-1':
                assert state['guide']['fields']['situation.age65']['value']=={'month':11,'year':None}
                assert state['guide']['fields']['coverage.current']['value']==['employer']
                assert state['record']['facts']['RC09']['value']['choice']=='spouse_job'
                assert row['target']=='T04',row
            elif name=='turn-2':
                assert state['guide']['fields']['coverage.requestedStart']['value']=='soonest'
                assert 'coverage.requestedStartMonth' not in state['guide']['fields'],'ASAP is not an exact month.'
                assert row['target']!='T04','ASAP should advance instead of looping.'
            else:
                assert state['assessment'].get('nextQuestion') is None,'Answer the requested explanation without another intake question.'
                assert any(f.get('id')=='partb' for f in state.get('facts',[]))
                assert 'RC04' not in state['record']['facts'],'Not applied is not actual A/B status.'
        result['checks']='passed'
    except Exception as error:
        result['checks']='failed';result['failure']=str(error);raise
    finally:
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            cols=[x[1] for x in db.execute('PRAGMA table_info(ai_charges)')]
            rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipts]
            result.update(generationStageCount=len(rows),measuredEstimateUsd=sum(row['measured'] or 0 for row in rows)/1e9,
                heldUsd=sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9,
                accountedUsd=sum(row['charged'] for row in rows)/1e9)
        finally:db.close()
        result.update(outputs=outputs,timings=timings)
        write('live-results.json',result)
        app.shutdown();app.server_close();thread.join(timeout=5)
