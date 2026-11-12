"""Read-only activation receipt; stores hashes/counts, never profile contents or credentials."""
from pathlib import Path
import hashlib,json,sqlite3,subprocess,sys,urllib.request,datetime
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
phase=sys.argv[1]
result={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'services':{},'stores':{},'source_hashes':{}}
for port in (8890,8891,8893,8894,8896):
 pids=subprocess.run(['lsof','-t',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.split()
 result['services'][str(port)]={'pids':pids}
 if port not in (8893,8894):continue
 for pid in pids:
  info=subprocess.check_output(['ps','-p',pid,'-o','lstart=,command='],text=True).strip()
  result['services'][str(port)]['process']=info
 for route in ('/ten-config.json','/api/status'):
  with urllib.request.urlopen(f'http://127.0.0.1:{port}{route}',timeout=10) as response:value=json.load(response)
  if route=='/ten-config.json':
   result['services'][str(port)]['config']={k:value.get(k) for k in ['advisorName','variant','mockAI','modelPolicy','responseReliabilityContract','defaultModel']}
  else:
   result['services'][str(port)]['provider_usage']={name:{k:budget.get(k) for k in ['requestCount','accountedUsd','dailyLimitUsd']} for name,budget in value.get('providerBudgets',{}).items()}
for path in (ROOT/'alternatives/advisor-first/var/profiles/guides.sqlite3',ROOT/'cms-slice/var/ai-budget/usage.sqlite3'):
 db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
 tables={}
 try:
  db.execute('BEGIN')
  for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
   quoted='"'+name.replace('"','""')+'"'
   rows=sorted(hashlib.sha256(repr(row).encode()).hexdigest() for row in db.execute('SELECT * FROM '+quoted))
   tables[name]={'rows':len(rows),'sha256':hashlib.sha256(('\n'.join(rows)).encode()).hexdigest(),'schema_sha256':hashlib.sha256((sql or '').encode()).hexdigest()}
 finally:db.close()
 result['stores'][str(path.relative_to(ROOT))]=tables
base=ROOT/'alternatives/advisor-first'
for path in [*base.glob('*.py'),*base.glob('*.json'),base/'ui-8894/serve.py']:
 result['source_hashes'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
(OUT/f'runtime-{phase}.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'phase':phase,'services':result['services'],'store_tables':{name:{k:v['rows'] for k,v in tables.items()} for name,tables in result['stores'].items()}},indent=2))
