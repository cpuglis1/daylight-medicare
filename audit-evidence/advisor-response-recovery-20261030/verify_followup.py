"""One captured follow-up after head-command quarantine; no opening re-extraction."""
import copy,http.cookiejar,json,sqlite3,sys,tempfile,threading,time,urllib.request,urllib.error,uuid
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];V=ROOT/'alternatives/advisor-first';sys.path.insert(0,str(V))
from server import build
from natural_flow import CONTEXT_POLICY

def write(n,v):(P/n).write_text(json.dumps(v,indent=2)+'\n')
source=json.loads((P/'opening-response.json').read_text());receipts=[];result={'fictionalInputs':True,'automaticRetries':False,'maximumGenerationStages':2,'maximumReservationUsd':0.067,'openingExtractionRepeated':False}
with tempfile.TemporaryDirectory(prefix='response-followup-',dir=V/'var') as tmp:
 app=build(0,database=Path(tmp)/'guides.sqlite3');agent=app.adaptive.agent;reserve=agent.reserve_turn;validate=agent.validate_composition;validate_extract=agent.validate_output
 def reserve_checked(*args,**kwargs):
  assert not receipts,'Only this follow-up turn is allowed.'
  r=reserve(*args,**kwargs);receipts.extend(s.key for s in r.stages.values());return r
 def capture_extract(value,*args,**kwargs):
  data={'value':value}
  try:out=validate_extract(value,*args,**kwargs);data['checked']=out;return out
  except Exception as e:data['error']=str(e);raise
  finally:write('followup-extraction.json',data)
 def capture(value,context,moves):
  data={'value':value,'context':context,'moves':moves}
  try:out=validate(value,context,moves);data['accepted']=True;return out
  except Exception as e:data.update(accepted=False,error=str(e));raise
  finally:write('followup-composition.json',data)
 agent.reserve_turn=reserve_checked;agent.validate_composition=capture;agent.validate_output=capture_extract
 thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{app.server_port}'
 jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));session=json.load(opener.open(base+'/api/guest/session'))
 def turn(state,action,**extra):
  data={'guide':state['guide'],'record':state['record'],'action':action,'requestId':uuid.uuid4().hex,**extra}
  if state.get('continuation'):data['continuation']=state['continuation']
  req=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
  try:return json.load(opener.open(req,timeout=90))
  except urllib.error.HTTPError as e:write('followup-http-error.json',{'status':e.code,'body':e.read().decode()});raise
 try:
  state=turn({'guide':source['guide'],'record':source['record']},{'type':'refresh'});owner=app.profiles.digest(next(c.value for c in jar if c.name=='daylight_advisor_dev'))
  memory=copy.deepcopy(source);memory.update(guide=state['guide'],record=state['record']);app.adaptive.remember_exchange(owner,'I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options',memory,CONTEXT_POLICY)
  start=time.monotonic();state=turn(state,{'type':'message','message':"My health insurance is through my wife's current job."},aiConsent=True,contextPolicy=CONTEXT_POLICY)
  result.update(seconds=round(time.monotonic()-start,3),reply=state.get('reply'),generated=state.get('generated'),nextQuestion=state['assessment'].get('nextQuestion'));write('followup-response.json',state)
  print(json.dumps({k:v for k,v in result.items() if k!='nextQuestion'}),flush=True)
  assert state.get('generated',{}).get('status')=='complete',state.get('generated')
  assert state['guide']['fields']['coverage.current']['value']==['employer']
  assert state['record']['facts']['RC09']['value']['choice']=='spouse_job'
  assert state['assessment']['nextQuestion']['id']=='T04'
  before=agent.calls;state=turn(state,{'type':'choice','id':'T04','fields':{'choice':'soonest'}})
  assert agent.calls==before and state['guide']['fields']['coverage.requestedStart']['value']=='soonest'
  assert (state['assessment'].get('nextQuestion') or {}).get('id')!='T04'
  result.update(checks='passed',freeChoiceAdvanced=True);write('followup-after-free-choice.json',state)
 except Exception as e:result.update(checks='failed',failure=str(e));raise
 finally:
  db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
  try:
   cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')];rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(k,)).fetchone())) for k in receipts]
   result.update(generationStages=len(rows),measuredEstimateUsd=sum(r['measured'] or 0 for r in rows)/1e9,heldUsd=sum(r['charged'] for r in rows if r['status'] in {'reserved','uncertain'})/1e9)
  finally:db.close()
  write('followup-results.json',result);app.shutdown();app.server_close();thread.join(timeout=5)
