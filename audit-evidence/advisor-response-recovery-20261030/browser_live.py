"""One real browser check, isolated cookie/profile; at most two paid stages."""
import json,sqlite3,sys,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];V=ROOT/'alternatives/advisor-first';sys.path.insert(0,str(V))
import server
original_factory=server.make_server
# Test-only cookie isolation; the product factory/controller are unchanged.
def isolated(*args,**kwargs):
 kwargs['cookie_namespace']='daylight_advisor_recovery_live_test'
 return original_factory(*args,**kwargs)
server.make_server=isolated
receipts=[]
with tempfile.TemporaryDirectory(prefix='browser-live-',dir=V/'var') as tmp:
 app=server.build(8894,database=Path(tmp)/'guides.sqlite3');reserve=app.adaptive.agent.reserve_turn;compose=app.adaptive.compose_response
 def checked(*args,**kwargs):
  assert not receipts,'Only one paid browser turn is allowed.'
  r=reserve(*args,**kwargs);receipts.extend(s.key for s in r.stages.values());return r
 def captured(*args,**kwargs):
  out=compose(*args,**kwargs);(P/'browser-live-response.json').write_text(json.dumps(out,indent=2)+'\n');return out
 app.adaptive.agent.reserve_turn=checked;app.adaptive.compose_response=captured
 print('Isolated real-model browser check at http://127.0.0.1:8894/',flush=True)
 try:app.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  db=sqlite3.connect((ROOT/'cms-slice/var/ai-budget/usage.sqlite3').as_uri()+'?mode=ro',uri=True)
  try:
   cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')];rows=[dict(zip(cols,db.execute('SELECT * FROM ai_charges WHERE id=?',(k,)).fetchone())) for k in receipts]
   result={'generationStages':len(rows),'maximumReservationUsd':0.067,'fictionalInputs':True,'cookieAndDatabaseIsolated':True,'measuredEstimateUsd':sum(r['measured'] or 0 for r in rows)/1e9,'heldUsd':sum(r['charged'] for r in rows if r['status'] in {'reserved','uncertain'})/1e9}
   (P/'browser-live-cost.json').write_text(json.dumps(result,indent=2)+'\n')
  finally:db.close();app.server_close()
