"""Brand audit using mocked failures and temporary fixtures; no live model traffic."""
import importlib.util, io, json, socket, sys, tempfile
from pathlib import Path
from unittest.mock import patch, Mock
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'alternatives/advisor-first'),str(ROOT/'alternatives/advisor-first/tests')]
from server import build
from adaptive_flow import Q
spec=importlib.util.spec_from_file_location('proxy8894',ROOT/'alternatives/advisor-first/ui-8894/serve.py')
proxy=importlib.util.module_from_spec(spec);spec.loader.exec_module(proxy)
results={}
def blocked(*a,**k):raise AssertionError('No network transport permitted')
with patch.object(socket.socket,'connect',blocked),patch.object(socket,'create_connection',blocked):
 with tempfile.TemporaryDirectory() as temp:
  service=build(0,fixture=True,database=Path(temp)/'fictional.sqlite3')
  try:
   questions=[service.adaptive.question(key) for key in Q]
   assert 'Daylight' not in json.dumps(questions)
   results['approved_question_copies_checked']=len(questions)
   cls=next(c for c in service.RequestHandlerClass.__mro__ if c.__module__=='session_recovery')
   handler=object.__new__(service.RequestHandlerClass)
   handler.path='/api/conversation/recover';handler.safe=lambda:True
   handler.csrf=lambda:'fictional';handler.token=lambda:'fictional'
   handler.body=lambda:{};handler.respond=Mock()
   with patch.object(service.adaptive,'recover',side_effect=RuntimeError('fictional failure')):
    cls.do_POST(handler)
   code,body=handler.respond.call_args.args
   assert code==503 and body['error']=='MidMorning could not reconnect just now.'
   results['reconnect_error']=body
  finally:service.server_close()
 opener=Mock();opener.open.side_effect=OSError('fictional upstream unavailable')
 with patch.object(proxy.urllib.request,'build_opener',return_value=opener):
  cls=proxy.handler('http://127.0.0.1:1')
  handler=object.__new__(cls);handler.path='/api/status';handler.command='GET'
  handler.headers={};handler.rfile=io.BytesIO();handler.send=Mock()
  handler.forward()
  code,body,headers=handler.send.call_args.args
  assert code==502 and 'MidMorning' in body.decode() and 'Daylight' not in body.decode()
  results['unavailable_proxy_error']=json.loads(body)
  assert cls.server_version=='Daylight8894'
  assert 'X-Daylight-CSRF' in proxy.FORWARD
results['paid_model_calls']=0
print(json.dumps(results,indent=2))
