"""Two fictional HTTP turns + a free choice; four paid stages maximum, no retry."""
import copy,http.cookiejar,json,sqlite3,sys,tempfile,threading,time,urllib.request,uuid
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];V=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(V))
from server import build
from natural_flow import CONTEXT_POLICY

def write(name,value):(P/name).write_text(json.dumps(value,indent=2)+'\n')
receipts=[];outputs=[];phase=['opening'];result={'fictionalInputs':True,'automaticRetries':False,'maximumGenerationStages':4,'maximumReservationUsd':0.134}
with tempfile.TemporaryDirectory(prefix='response-verify-',dir=V/'var') as tmp:
 app=build(0,database=Path(tmp)/'guides.sqlite3');agent=app.adaptive.agent;reserve=agent.reserve_turn;validate=agent.validate_composition
 def reserve_checked(*args,**kwargs):
  n=len(kwargs.get('stages',('extract','compose')));assert len(receipts)+n<=4,'Four paid stages is the final ceiling.'
  r=reserve(*args,**kwargs);receipts.extend(s.key for s in r.stages.values());return r
 def inspect(value,context,moves):
  data={'value':value,'context':context,'moves':moves}
  try:out=validate(value,context,moves);data['accepted']=True;return out
  except Exception as e:data.update(accepted=False,error=str(e));raise
  finally:write(phase[0]+'-composition.json',data)
 agent.reserve_turn=reserve_checked;agent.validate_composition=inspect
 thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{app.server_port}'
 jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));session=json.load(opener.open(base+'/api/guest/session'))
 def turn(state,action,**extra):
  data={'guide':state['guide'],'record':state['record'],'action':action,'requestId':uuid.uuid4().hex,**extra}
  if state.get('continuation'):data['continuation']=state['continuation']
  req=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
  return json.load(opener.open(req,timeout=90))
 try:
  g,r=app.adaptive.initial();state=turn({'guide':g,'record':r},{'type':'start'})
  scripts=[('opening','I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options'),('insurance',"My health insurance is through my wife's current job.")]
  for name,message in scripts:
   phase[0]=name;start=time.monotonic();state=turn(state,{'type':'message','message':message},aiConsent=True,contextPolicy=CONTEXT_POLICY)
   row={'case':name,'seconds':round(time.monotonic()-start,3),'reply':state.get('reply'),'generated':state.get('generated'),'question':(state['assessment'].get('nextQuestion') or {}).get('question'),'target':(state['assessment'].get('nextQuestion') or {}).get('id')}
   outputs.append(row);write(name+'-response.json',state);print(json.dumps(row),flush=True)
   assert state.get('generated',{}).get('status')=='complete',state.get('generated')
   assert not state.get('notice') and not state.get('review')
   assert state['guide']['fields']['situation.age65']['value']=={'month':11,'year':None}
   assert state['record']['conversation']['task']=='timing'
   if name=='opening':
    assert row['target']=='T05',row
    assert state['guide']['fields']['knowledge.general']['value'] in {'new','some'}
    assert 'coverage.current' not in state['guide']['fields']
   else:
    assert row['target']=='T04',row
    assert state['guide']['fields']['coverage.current']['value']==['employer']
    assert state['record']['facts']['RC09']['value']['choice']=='spouse_job'
    assert len(json.loads((P/'insurance-composition.json').read_text())['context']['recent_exchanges'])==1
   assert 'coverage.requestedStartMonth' not in state['guide']['fields']
   assert 'RC04' not in state['record']['facts'],'Intending to enroll does not establish actual A/B.'
  before=agent.calls;phase[0]='free-choice';state=turn(state,{'type':'choice','id':'T04','fields':{'choice':'soonest'}})
  assert agent.calls==before,'A finite choice must not consume AI.'
  assert state['guide']['fields']['coverage.requestedStart']['value']=='soonest'
  assert (state['assessment'].get('nextQuestion') or {}).get('id')!='T04'
  result.update(checks='passed',freeChoiceAdvanced=True);write('after-free-choice.json',state)
 except Exception as e:result.update(checks='failed',failure=str(e));raise
 finally:
  db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
  try:
   cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')];rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(k,)).fetchone())) for k in receipts]
   result.update(generationStages=len(rows),measuredEstimateUsd=sum(r['measured'] or 0 for r in rows)/1e9,heldUsd=sum(r['charged'] for r in rows if r['status'] in {'reserved','uncertain'})/1e9,outputs=outputs)
  finally:db.close()
  write('latest-results.json',result);app.shutdown();app.server_close();thread.join(timeout=5)
