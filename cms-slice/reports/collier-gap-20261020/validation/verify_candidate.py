"""Isolated portable replay of the actual candidate; no network-enabled identities."""
import json,os,select,subprocess,sys,tarfile,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parent
bundle=Path((ROOT/'bundle-path.txt').read_text().strip())
env={**os.environ,'PATH':'','OPENAI_API_KEY':'','OPENAI_MODEL':''}
with tempfile.TemporaryDirectory(prefix='collier-validated-gate-') as folder:
 work=Path(folder)
 with tarfile.open(bundle) as archive:archive.extractall(work,filter='data')
 run=subprocess.run([sys.executable,'scripts/demo.py','verify','--release','snapshot'],cwd=work,env=env,capture_output=True,text=True,timeout=25)
 assert run.returncode==0,run.stderr
 status=json.loads(run.stdout);assert status['source_records']==70 and status['packaged_pharmacy_networks']==61 and status['star_contracts']==24 and status['consumer_ready'] is False
 cases=[]
 for message in ['H1889-026-000-2027 premium','RXCUI 1551300 for all plans','What changed at NCH for 2027?']:
  run=subprocess.run([sys.executable,'scripts/demo.py','ask',message,'--release','snapshot'],cwd=work,env=env,capture_output=True,text=True,timeout=25)
  assert run.returncode!=0 and 'Data validation is incomplete' in run.stderr+run.stdout
  assert not run.stdout.strip()
  cases.append({'synthetic_query':message,'blocked':True,'fact_payload_returned':False})
 script="import sys;sys.path.insert(0,'scripts');from demo import make_server;from chat import Chat,ResponsesClient;from demo_tools import DemoTools;s=make_server(Chat(DemoTools(release='snapshot'),ResponsesClient(key='',model='')),0);print(s.server_port,flush=True);s.serve_forever()"
 child=subprocess.Popen([sys.executable,'-u','-c',script],cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 responses=[]
 try:
  assert select.select([child.stdout],[],[],25)[0],'Server startup timeout'
  port=int(child.stdout.readline().strip());base=f'http://127.0.0.1:{port}'
  for path,body in [('/api/status',None),('/',None),('/api/catalog',{'priorities':['monthly_premium']}),('/api/chat',{'message':'Show premium'}),('/api/live-chat',{'message':'Show plans'}),('/api/conversation',{'message':'Show costs','profile':{}}),('/api/local-resources',None),('/app.js',None)]:
   req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
   try:
    with urlopen(req,timeout=10) as r:code,raw=r.status,r.read().decode()
   except HTTPError as e:
    with e:code,raw=e.code,e.read().decode()
   if path=='/api/status':assert json.loads(raw)['consumer_ready'] is False and json.loads(raw)['catalog_count']==0
   elif path=='/':assert code==200 and 'Data validation is in progress' in raw and 'app.js' not in raw
   else:assert code==503 and 'Data validation is incomplete' in raw and '"facts"' not in raw and '"plans"' not in raw
   responses.append({'path':path,'http_status':code,'consumer_fact_payload':False})
 finally:
  child.terminate();child.wait(timeout=10)
 result={'bundle':str(bundle),'isolated_replay':True,'national_source_archives_available':False,'pdf_tools_available':False,'model_configured':False,'source_records':status['source_records'],'pharmacy_networks':status['packaged_pharmacy_networks'],'star_contracts':status['star_contracts'],'consumer_ready':False,'cli_cases':cases,'http_cases':responses,'domain_signoff':'pending'}
 (ROOT/'extracted-replay.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['isolated_replay','source_records','pharmacy_networks','star_contracts','consumer_ready']},indent=2))
