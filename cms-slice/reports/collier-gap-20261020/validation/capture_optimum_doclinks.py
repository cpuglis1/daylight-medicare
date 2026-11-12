"""Replay only the public Important Documents modal's inspected search request."""
from datetime import datetime,timezone
from html.parser import HTMLParser
import hashlib,json,time
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.parse import urlencode,urljoin,urlsplit
ROOT=Path(__file__).resolve().parent
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'):self.links.append(a['href'])
receipts=[]
for plan in ['OP27016','OP27017','OP27030','OP27031']:
 try:
  url='https://cwtools.globalmedicareapps.com/Tools/Plan/ImportantDocuemnstGrid';data=urlencode({'planID':plan,'year':'2027','payerID':'OPT'}).encode()
  with urlopen(Request(url,data=data,headers={'User-Agent':'NaplesMedicareResearch/1.0','Content-Type':'application/x-www-form-urlencoded'}),timeout=25) as r:
   if urlsplit(r.url).hostname!='cwtools.globalmedicareapps.com':raise ValueError('Unexpected redirect')
   raw=r.read(12_000_001)
   if len(raw)>12_000_000:raise ValueError('Size cap')
   h=hashlib.sha256(raw).hexdigest();(ROOT/'raw'/h).write_bytes(raw);(ROOT/('optimum-documents-'+plan+'.html')).write_bytes(raw)
   parser=Links();parser.feed(raw.decode());links=[urljoin(r.url,u) for u in parser.links]
   receipts.append({'plan_key':plan,'year':'2027','url':url,'method':'POST','body_sha256':hashlib.sha256(data).hexdigest(),'request_parameters':{'planID':plan,'year':'2027','payerID':'OPT'},'sha256':h,'bytes':len(raw),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'links':links});print(plan,links,flush=True)
  time.sleep(1)
 except Exception as e:receipts.append({'error':type(e).__name__+': '+str(e),'action':'stopped; no retry'});break
(ROOT/'optimum-document-link-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
