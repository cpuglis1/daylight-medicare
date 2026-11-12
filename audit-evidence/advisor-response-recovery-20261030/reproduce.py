"""One anonymous fictional opening, maximum two paid stages; no retry or saving."""
import copy,json,sqlite3,sys,tempfile,time,uuid
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];V=ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(V))
from server import build
from natural_flow import CONTEXT_POLICY

def write(name,value):(P/name).write_text(json.dumps(value,indent=2)+'\n')
receipts=[];result={'fictionalInputs':True,'automaticRetries':False,'maximumGenerationStages':2,'maximumReservationUsd':0.067}
message='I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options'
with tempfile.TemporaryDirectory(prefix='response-repro-',dir=V/'var') as tmp:
 app=build(0,database=Path(tmp)/'guides.sqlite3');agent=app.adaptive.agent;reserve=agent.reserve_turn;validate=agent.validate_composition;validate_extract=agent.validate_output
 def reserve_checked(*args,**kwargs):
  assert not receipts,'Only one turn is allowed.'
  r=reserve(*args,**kwargs);receipts.extend(s.key for s in r.stages.values());return r
 def inspect(value,context,moves):
  data={'value':value,'context':context,'moves':moves}
  try:out=validate(value,context,moves);data['accepted']=True;return out
  except Exception as e:data.update(accepted=False,error=str(e));raise
  finally:write('composition.json',data)
 def inspect_extract(value,*args,**kwargs):
  data={'value':value}
  try:out=validate_extract(value,*args,**kwargs);data['accepted']=out;return out
  except Exception as e:data['error']=str(e);raise
  finally:write('extraction.json',data)
 agent.reserve_turn=reserve_checked;agent.validate_composition=inspect;agent.validate_output=inspect_extract
 owner='fictional-opening-'+uuid.uuid4().hex;g,r=app.adaptive.initial()
 try:
  start=time.monotonic();out=app.adaptive.turn(owner,{'guide':g,'record':r,'action':{'type':'message','message':message},'requestId':uuid.uuid4().hex,'aiConsent':True,'contextPolicy':CONTEXT_POLICY})
  write('response.json',out);result.update(seconds=round(time.monotonic()-start,3),reply=out.get('reply'),generated=out.get('generated'),nextQuestion=out['assessment'].get('nextQuestion'))
  print(json.dumps({k:v for k,v in result.items() if k!='nextQuestion'}),flush=True)
 except Exception as e:result['error']=str(e);raise
 finally:
  db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
  try:
   cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')];rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(k,)).fetchone())) for k in receipts]
   result.update(generationStages=len(rows),measuredEstimateUsd=sum(r['measured'] or 0 for r in rows)/1e9,heldUsd=sum(r['charged'] for r in rows if r['status'] in {'reserved','uncertain'})/1e9)
  finally:db.close()
  write('results.json',result);app.server_close()
