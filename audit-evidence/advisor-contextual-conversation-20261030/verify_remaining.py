"""Resume accepted fictional reports; one compose and two turns, five stages max."""
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

PACKET=Path(__file__).resolve().parent;ROOT=PACKET.parents[1];VARIANT=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY

def write(name,value):(PACKET/name).write_text(json.dumps(value,indent=2)+'\n')
earlier=json.loads((PACKET/'attempt-2/turn-1.json').read_text());receipts=[];phase=['targeted-compose'];timings=[];outputs=[]
result={'maximumAdditionalReservationUsd':0.1675,'maxAdditionalGenerationStages':5,'fictionalInputs':True,
        'automaticRetries':False,'savedProfile':False,'extractReasoning':'none',
        'resume':'Prior accepted fictional reports refreshed into a new server visit; no extraction repeated.'}
with tempfile.TemporaryDirectory(prefix='context-remainder-',dir=VARIANT/'var') as temp:
    app=build(0,database=Path(temp)/'guides.sqlite3');agent=app.adaptive.agent;agent.reasoning_effort='none'
    reserve=agent.reserve_turn;validate=agent.validate_composition;count=agent.count_tokens
    def reserve_checked(*args,**kwargs):
        n=len(kwargs.get('stages',('extract','compose')))
        assert len(receipts)+n<=5,'No paid stages beyond this ceiling.'
        reservation=reserve(*args,**kwargs);receipts.extend(stage.key for stage in reservation.stages.values());return reservation
    def count_timed(client,payload):
        start=time.monotonic()
        try:return count(client,payload)
        finally:timings.append({'case':phase[0],'stage':payload['text']['format']['name'],'part':'count_tokens','seconds':round(time.monotonic()-start,3)})
    def inspect_fictional(value,context,moves):
        data={'value':value,'context':context,'moves':moves}
        try:out=validate(value,context,moves);data['accepted']=True;return out
        except Exception as error:data.update(accepted=False,error=str(error));raise
        finally:write(phase[0]+'-composition.json',data)
    agent.reserve_turn=reserve_checked;agent.validate_composition=inspect_fictional;agent.count_tokens=count_timed
    for method in ('extract','compose'):
        original=getattr(agent,method)
        def wrapped(*args,_original=original,_method=method,**kwargs):
            start=time.monotonic()
            try:return _original(*args,**kwargs)
            finally:timings.append({'case':phase[0],'stage':_method,'part':'whole_stage','seconds':round(time.monotonic()-start,3)})
        setattr(agent,method,wrapped)
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{app.server_port}';jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def get(path):return json.load(opener.open(base+path,timeout=90))
    session=get('/api/guest/session')
    def turn(state,action,**extra):
        payload={'guide':state['guide'],'record':state['record'],'action':action,'requestId':str(uuid.uuid4()),**extra}
        if state.get('continuation'):payload['continuation']=state['continuation']
        req=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
        return json.load(opener.open(req,timeout=90))
    def record(state,message,elapsed):
        row={'case':phase[0],'message':message,'seconds':round(elapsed,3),'reply':state.get('reply'),
            'question':(state['assessment'].get('nextQuestion') or {}).get('question'),
            'target':(state['assessment'].get('nextQuestion') or {}).get('id'),'generated':state.get('generated')}
        outputs.append(row);print(json.dumps(row),flush=True);write(phase[0]+'.json',state)
        assert state.get('generated',{}).get('status')=='complete',state.get('generated')
        assert not state.get('review')
    try:
        state=turn({'guide':earlier['response']['guide'],'record':earlier['response']['record']},{'type':'refresh'})
        owner=app.profiles.digest(next(cookie.value for cookie in jar if cookie.name=='daylight_advisor_dev'))
        out=copy.deepcopy(state);message=earlier['message'];start=time.monotonic()
        with agent.reserve_turn(stages=('compose',)) as reservation:
            out=app.adaptive.compose_response(owner,out,message,app.adaptive.eligible(owner,out['guide'],out['record']),CONTEXT_POLICY,str(uuid.uuid4()),reservation)
        record(out,message,time.monotonic()-start)
        assert out['guide']['fields']['situation.age65']['value']=={'month':11,'year':None}
        assert out['guide']['fields']['situation.retirement']['value']['status']=='retired'
        assert out['guide']['fields']['coverage.current']['value']==['employer']
        assert out['record']['facts']['RC09']['value']['choice']=='spouse_job'
        assert out['assessment']['nextQuestion']['id']=='T04'
        # Actual generated first exchange enters the same current visit memory;
        # it is not browser-authored history or a saved transcript.
        app.adaptive.remember_exchange(owner,message,out,CONTEXT_POLICY);state=out
        for name,message in [('asap','ASAP!!'),('education',"I haven't applied yet. Before we keep going, what is Part B?")]:
            phase[0]=name;start=time.monotonic()
            state=turn(state,{'type':'message','message':message},aiConsent=True,contextPolicy=CONTEXT_POLICY)
            record(state,message,time.monotonic()-start)
            composed=json.loads((PACKET/(name+'-composition.json')).read_text())
            assert composed['context']['recent_exchanges'],'Conversation history was not supplied.'
            if name=='asap':
                assert state['guide']['fields']['coverage.requestedStart']['value']=='soonest'
                assert 'coverage.requestedStartMonth' not in state['guide']['fields']
                assert (state['assessment'].get('nextQuestion') or {}).get('id')!='T04'
            else:
                assert state['assessment'].get('nextQuestion') is None
                assert state['assessment'].get('intakePaused') is True
                assert any(f.get('id')=='partb' for f in state.get('facts',[]))
                assert 'RC04' not in state['record']['facts'],'Not applied is not actual A/B status.'
        result['checks']='passed'
    except Exception as error:result.update(checks='failed',failure=str(error));raise
    finally:
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            cols=[x[1] for x in db.execute('PRAGMA table_info(ai_charges)')]
            rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipts]
            result.update(generationStageCount=len(rows),measuredEstimateUsd=sum(row['measured'] or 0 for row in rows)/1e9,
                heldUsd=sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9)
        finally:db.close()
        result.update(outputs=outputs,timings=timings);write('remaining-results.json',result)
        app.shutdown();app.server_close();thread.join(timeout=5)
