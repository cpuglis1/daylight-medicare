"""One targeted composition and the remaining educational turn; no re-extraction."""
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

earlier=json.loads((PACKET/'turn-2.json').read_text())
first=json.loads((PACKET/'turn-1.json').read_text())
receipts=[];phase=['targeted-turn-2']
result={'maximumAdditionalReservationUsd':0.1005,'maxAdditionalGenerationRequests':3,
        'fictionalInputs':True,'automaticRetries':False,'savedProfile':False}
with tempfile.TemporaryDirectory(prefix='live-remainder-',dir=VARIANT/'var') as temp:
    app=build(0,database=Path(temp)/'guides.sqlite3')
    agent=app.adaptive.agent;reserve=agent.reserve_turn;validate=agent.validate_composition
    def audited_reserve(*args,**kwargs):
        count=len(kwargs.get('stages',('extract','compose')))
        assert len(receipts)+count<=3,'No further paid stages are authorized by this harness.'
        reservation=reserve(*args,**kwargs)
        receipts.extend(stage.key for stage in reservation.stages.values())
        return reservation
    def inspect_fictional(value,context,moves):
        data={'value':value,'context':context,'moves':moves}
        try:
            checked=validate(value,context,moves);data['accepted']=True;return checked
        except Exception as error:
            data.update(accepted=False,error=str(error));raise
        finally:write(phase[0]+'-composition.json',data)
    agent.reserve_turn=audited_reserve;agent.validate_composition=inspect_fictional
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
        # Resume the fictional accepted reports through the actual refresh path;
        # the prior visit's continuation cannot be reused in a fresh process.
        state=turn({'guide':earlier['response']['guide'],'record':earlier['response']['record']},{'type':'refresh'})
        owner=app.profiles.digest(next(cookie.value for cookie in jar if cookie.name=='daylight_advisor_dev'))
        out=copy.deepcopy(earlier['response']);out.update(guide=state['guide'],record=state['record'],continuation=state['continuation'])
        start=time.monotonic()
        with agent.reserve_turn(stages=('compose',)) as reservation:
            out=app.adaptive.compose_response(owner,out,earlier['message'],app.adaptive.eligible(owner,out['guide'],out['record']),
                CONTEXT_POLICY,str(uuid.uuid4()),reservation,first['response']['record']['natural']['dialogue'])
        result['targetedComposition']={'elapsedSeconds':round(time.monotonic()-start,3),'reply':out.get('reply'),
            'question':(out['assessment'].get('nextQuestion') or {}).get('question'),'generated':out.get('generated')}
        write('targeted-turn-2.json',out)
        print(json.dumps(result['targetedComposition']),flush=True)
        assert out.get('generated',{}).get('status')=='complete',out.get('generated')
        phase[0]='turn-3';start=time.monotonic()
        state=turn(state,{'type':'message','message':'Before we get into dates, what is Medicare Part B?'},
                   aiConsent=True,contextPolicy=CONTEXT_POLICY)
        result['educationalTurn']={'elapsedSeconds':round(time.monotonic()-start,3),'reply':state.get('reply'),
            'question':(state['assessment'].get('nextQuestion') or {}).get('question'),'generated':state.get('generated')}
        write('turn-3.json',state);print(json.dumps(result['educationalTurn']),flush=True)
        assert state.get('generated',{}).get('status')=='complete',state.get('generated')
        assert not state.get('review') and state['assessment'].get('nextQuestion') is None
        assert any(f.get('id')=='partb' for f in state.get('facts',[]))
        g,r=state['guide'],state['record']
        assert g['fields']['situation.age65']['value']=={'month':11,'year':None}
        assert g['fields']['coverage.current']['value']==['employer']
        assert r['facts']['RC09']['value']['choice']=='spouse_job'
        assert 'RC04' not in r['facts'] and 'knowledge.general' not in g['fields']
        assert app.adaptive.assess(g,r)['nextQuestion']['id']=='T04','Unanswered target was lost during education.'
        result['checks']='passed'
    except Exception as error:
        result['checks']='failed';result['failure']=str(error);raise
    finally:
        write('final-status.json',get('/api/status'))
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            cols=[x[1] for x in db.execute('PRAGMA table_info(ai_charges)')]
            rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipts]
            result.update(generationStageCount=len(rows),measuredEstimateUsd=sum(row['measured'] or 0 for row in rows)/1e9,
                heldUsd=sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9,
                accountedUsd=sum(row['charged'] for row in rows)/1e9)
        finally:db.close()
        write('remaining-results.json',result)
        app.shutdown();app.server_close();thread.join(timeout=5)
