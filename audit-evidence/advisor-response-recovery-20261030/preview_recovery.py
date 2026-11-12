"""Disposable no-credit preview injecting one labelled synthetic compose failure."""
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];V=ROOT/'alternatives/advisor-first';sys.path.insert(0,str(V))
from server import build
with tempfile.TemporaryDirectory(prefix='daylight-recovery-preview-') as tmp:
 app=build(8892,fixture=True,database=Path(tmp)/'guides.sqlite3');original=app.adaptive.message;seen=set()
 def message(owner,*args,**kwargs):
  out=original(owner,*args,**kwargs)
  if owner not in seen:
   seen.add(owner);out['reply']='';out['notice']='I couldn’t finish that reply. You can keep going.';out['generated']={'status':'unavailable','retryable':False,'code':'composition_unavailable'}
  return out
 app.adaptive.message=message
 print('Synthetic recovery preview at http://127.0.0.1:8892/',flush=True)
 try:app.serve_forever()
 except KeyboardInterrupt:pass
 finally:app.server_close()
