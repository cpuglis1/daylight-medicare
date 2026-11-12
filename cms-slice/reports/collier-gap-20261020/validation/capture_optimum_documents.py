"""Bounded public carrier searches/details only; never application/contact paths."""
from datetime import datetime,timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import hashlib,json,time
from pathlib import Path
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlencode,urljoin,urlsplit
ROOT=Path(__file__).resolve().parent
class Forms(HTMLParser):
 def __init__(self):super().__init__();self.current=None;self.forms=[];self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='form':self.current={'action':a.get('action'),'inputs':{}}
  if tag=='input' and self.current and a.get('type')=='hidden':self.current['inputs'][a.get('name')]=a.get('value','')
  if tag=='a' and a.get('href'):self.links.append(a['href'])
 def handle_endtag(self,tag):
  if tag=='form' and self.current:self.forms.append(self.current);self.current=None
opener=build_opener(HTTPCookieProcessor(CookieJar()));receipts=[]
def read(url,data=None):
 p=urlsplit(url)
 if p.hostname!='cwtools.globalmedicareapps.com' or p.path not in ['/Tools/Plan/PlanSearchInitial','/Tools/Plan/PlanDetails']:raise ValueError('Only inspected search/detail routes allowed')
 with opener.open(Request(url,data=data,headers={'User-Agent':'NaplesMedicareResearch/1.0','Accept':'text/html'}),timeout=25) as r:
  if urlsplit(r.url).hostname!=p.hostname:raise ValueError('Unexpected redirect')
  raw=r.read(12_000_001)
  if len(raw)>12_000_000:raise ValueError('Size cap')
  h=hashlib.sha256(raw).hexdigest();(ROOT/'raw'/h).write_bytes(raw)
  receipt={'url':url,'final_url':r.url,'sha256':h,'bytes':len(raw),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'method':'POST' if data else 'GET'};receipts.append(receipt)
  parser=Forms();parser.feed(raw.decode());time.sleep(1);return raw,parser,receipt
try:
 for zipcode in ['34102','34109','34145','34142']:
  url='https://cwtools.globalmedicareapps.com/Tools/Plan/PlanSearchInitial?'+urlencode({'payerid':'OPT','year':'2027','zip':zipcode,'county':'Collier','fb':'False'})
  raw,forms,receipt=read(url);receipt['zip']=zipcode
  (ROOT/('optimum-all-plans-'+zipcode+'.html')).write_bytes(raw)
  plans=[f for f in forms.forms if f['action']=='/Tools/Plan/PlanDetails']
  receipt['observed_plan_keys']=[f['inputs'].get('PlanID') for f in plans];print(zipcode,receipt['observed_plan_keys'],flush=True)
  if zipcode=='34102':
   for form in plans:
    inp=form['inputs'];key=inp['PlanID']
    if inp.get('Year')!='2027' or inp.get('County')!='Collier':raise ValueError('Unexpected scope')
    detail,parsed,rec=read(urljoin(url,form['action']),urlencode(inp).encode());rec['plan_key']=key;rec['synthetic_input']={k:inp[k] for k in ['PayerId','Year','Zip','County','PlanID']}
    (ROOT/('optimum-detail-'+key+'.html')).write_bytes(detail)
    rec['document_links']=[urljoin(rec['final_url'],a) for a in parsed.links if any(x in a.lower() for x in ['dlsecure','.pdf','benefit','coverage'])]
    print(key,rec['document_links'],flush=True)
except Exception as e:receipts.append({'error':type(e).__name__+': '+str(e),'action':'stopped; no retries'});print(type(e).__name__,str(e),flush=True)
(ROOT/'optimum-document-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
