"""Three fictional live turns; isolated guest store, shared budget, no retries."""
import copy
import http.cookiejar
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

PACKET=Path(__file__).resolve().parent
ROOT=PACKET.parents[1]
VARIANT=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build

MESSAGES=[
    "I've been retired for a few years, and am turning 65 in November.",
    "I'm just getting started. I haven't applied for Medicare yet. My health insurance is through my wife's current job.",
    "Before we get into dates, what is Medicare Part B?",
]

def write(name,value):
    (PACKET/name).write_text(json.dumps(value,indent=2)+'\n')

def check(index,state):
    assert state.get('generated',{}).get('status')=='complete',state.get('generated')
    assert not state.get('review'),'A routine report unexpectedly required acceptance.'
    g,r=state['guide'],state['record']
    assert g['fields']['situation.age65']['value']=={'month':11,'year':None}
    assert g['fields']['situation.retirement']['value']['status']=='retired'
    if index==1:
        assert 'coverage.current' not in g['fields'],'Retirement was treated as insurance.'
    if index>=2:
        assert g['fields'].get('coverage.current',{}).get('value')==['employer'],'Spouse-job insurance omitted.'
        assert r['facts'].get('RC09',{}).get('value',{}).get('choice')=='spouse_job','Worker relationship omitted.'
        assert 'RC04' not in r['facts'],'Application progress became actual A/B enrollment.'
        assert 'knowledge.general' not in g['fields'],'Process progress became expertise.'
        assert (state['assessment'].get('nextQuestion') or {}).get('id')!='T05','Already-reported insurance asked again.'
    if index==3:
        assert state['assessment'].get('nextQuestion') is None,'Educational pause was ignored.'
        assert any(f.get('id')=='partb' for f in state.get('facts',[])),'Missing reviewed Part B teaching.'

receipt_ids=[]
report={'plannedTurns':3,'maxGenerationRequests':6,'maximumReservationUsd':0.201,
        'fictionalInputs':True,'savedProfile':False,'automaticRetries':False,'turns':[]}
with tempfile.TemporaryDirectory(prefix='live-check-',dir=VARIANT/'var') as temp:
    app=build(0,database=Path(temp)/'guides.sqlite3')
    reserve=app.adaptive.agent.reserve_turn
    def audited_reserve(*args,**kwargs):
        assert len(receipt_ids)+2<=6,'No additional live stages are permitted.'
        result=reserve(*args,**kwargs)
        receipt_ids.extend(stage.key for stage in result.stages.values())
        return result
    app.adaptive.agent.reserve_turn=audited_reserve
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{app.server_port}'
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def get(path):return json.load(opener.open(base+path,timeout=90))
    write('status-before.json',get('/api/status'))
    try:
        session=get('/api/guest/session');state=get('/api/conversation/initial')
        for index,message in enumerate(MESSAGES,1):
            payload={'guide':state['guide'],'record':state['record'],
                     'action':{'type':'message','message':message},'aiConsent':True,
                     'contextPolicy':'natural-context-v1','requestId':str(uuid.uuid4())}
            if state.get('continuation'):payload['continuation']=state['continuation']
            req=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(payload).encode(),
                headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
            start=time.monotonic()
            try:state=json.load(opener.open(req,timeout=90))
            except urllib.error.HTTPError as error:
                write('http-error.json',{'turn':index,'status':error.code,'body':error.read().decode()})
                raise
            entry={'turn':index,'message':message,'elapsedSeconds':round(time.monotonic()-start,3),'response':state}
            write(f'turn-{index}.json',entry)
            report['turns'].append({'turn':index,'elapsedSeconds':entry['elapsedSeconds'],
                                  'reply':state.get('reply'),'question':(state['assessment'].get('nextQuestion') or {}).get('question'),
                                  'generated':state.get('generated')})
            print(json.dumps(report['turns'][-1]),flush=True)
            check(index,state)
        report['structuralChecks']='passed'
    except Exception as error:
        report['structuralChecks']='failed';report['failure']=str(error)
        raise
    finally:
        write('status-after.json',get('/api/status'))
        db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            columns=[x[1] for x in db.execute('PRAGMA table_info(ai_charges)')]
            rows=[dict(zip(columns,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipt_ids]
            report['generationStageCount']=len(rows)
            report['measuredEstimateUsd']=sum(row['measured'] or 0 for row in rows)/1e9
            report['heldUsd']=sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9
            report['accountedUsd']=sum(row['charged'] for row in rows)/1e9
            report['stageUsage']=[{key:row[key] for key in ('status','input_tokens','cached_tokens','output_tokens')} for row in rows]
        finally:db.close()
        write('results.json',report)
        app.shutdown();app.server_close();thread.join(timeout=5)
