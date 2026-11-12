"""One final composition only, after constraining the pause schema to no question."""
import copy, http.cookiejar, json, sqlite3, sys, tempfile, threading, time, urllib.request, uuid
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];V=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(V))
from server import build
from natural_flow import CONTEXT_POLICY

def write(name,value):(P/name).write_text(json.dumps(value,indent=2)+'\n')
source=json.loads((P/'education.json').read_text());receipts=[]
result={'maxAdditionalGenerationStages':1,'maximumAdditionalReservationUsd':0.0335,'fictionalInputs':True,'automaticRetries':False,'extractionRepeated':False}
with tempfile.TemporaryDirectory(prefix='education-final-',dir=V/'var') as tmp:
 app=build(0,database=Path(tmp)/'guides.sqlite3');agent=app.adaptive.agent;reserve=agent.reserve_turn;validate=agent.validate_composition
 def checked(*args,**kwargs):
  assert not receipts and kwargs.get('stages')==('compose',),'Only one final composition is allowed.'
  r=reserve(*args,**kwargs);receipts.extend(stage.key for stage in r.stages.values());return r
 def inspect(value,context,moves):
  data={'value':value,'context':context,'moves':moves}
  try:out=validate(value,context,moves);data['accepted']=True;return out
  finally:write('final-education-composition.json',data)
 agent.reserve_turn=checked;agent.validate_composition=inspect
 thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{app.server_port}'
 jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));session=json.load(opener.open(base+'/api/guest/session'))
 payload={'guide':source['guide'],'record':source['record'],'action':{'type':'refresh'},'requestId':str(uuid.uuid4())}
 req=urllib.request.Request(base+'/api/conversation/turn',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Daylight-CSRF':session['csrf']})
 state=json.load(opener.open(req));owner=app.profiles.digest(next(c.value for c in jar if c.name=='daylight_advisor_dev'))
 try:
  out=copy.deepcopy(source);out.update(guide=state['guide'],record=state['record'],continuation=state['continuation'])
  start=time.monotonic()
  with agent.reserve_turn(stages=('compose',)) as reservation:
   out=app.adaptive.compose_response(owner,out,"I haven't applied yet. Before we keep going, what is Part B?",app.adaptive.eligible(owner,out['guide'],out['record'],answer_only=True),CONTEXT_POLICY,str(uuid.uuid4()),reservation)
  result.update(seconds=round(time.monotonic()-start,3),reply=out.get('reply'),generated=out.get('generated'),intakePaused=out['assessment'].get('intakePaused'))
  assert out.get('generated',{}).get('status')=='complete',out.get('generated')
  assert out['assessment'].get('nextQuestion') is None and out['assessment'].get('intakePaused') is True
  assert 'RC04' not in out['record']['facts']
  assert out['guide']['fields']['coverage.requestedStart']['value']=='soonest'
  result['checks']='passed';write('final-education.json',out)
 except Exception as error:result.update(checks='failed',failure=str(error));raise
 finally:
  db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
  try:
   cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')];rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(key,)).fetchone())) for key in receipts]
   result.update(measuredEstimateUsd=sum(r['measured'] or 0 for r in rows)/1e9,heldUsd=sum(r['charged'] for r in rows if r['status'] in {'reserved','uncertain'})/1e9,generationStageCount=len(rows))
  finally:db.close()
  write('final-education-results.json',result);print(json.dumps(result),flush=True);app.shutdown();app.server_close();thread.join(timeout=5)
