"""Public carrier search; fixed synthetic input only. Never enrollment/contact forms."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import hashlib,json
from pathlib import Path
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlencode,urljoin,urlsplit
ROOT=Path(__file__).resolve().parent
class Form(HTMLParser):
 def __init__(self):super().__init__();self.inside=False;self.hidden={};self.action=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='form' and a.get('id')=='FormQuestionaire':self.inside=True;self.action=a['action']
  if tag=='input' and self.inside and a.get('type')=='hidden' and a.get('name') not in ['MedicareMedicaid','Diabetes','Cardiovascular','Asthma']:self.hidden[a['name']]=a.get('value','')
 def handle_endtag(self,tag):
  if tag=='form':self.inside=False
opener=build_opener(HTTPCookieProcessor(CookieJar()))
def read(url,data=None):
 if urlsplit(url).hostname!='cwtools.globalmedicareapps.com':raise ValueError('Host rejected')
 with opener.open(Request(url,data=data,headers={'User-Agent':'NaplesMedicareResearch/1.0','Accept':'text/html'}),timeout=25) as r:
  if urlsplit(r.url).hostname!='cwtools.globalmedicareapps.com':raise ValueError('Unexpected redirect')
  b=r.read(12_000_001)
  if len(b)>12_000_000:raise ValueError('Size cap')
  h=hashlib.sha256(b).hexdigest();(ROOT/'raw'/h).write_bytes(b)
  return b,{'url':url,'final_url':r.url,'sha256':h,'bytes':len(b),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'method':'POST' if data else 'GET'}
receipts=[]
try:
 page,receipt=read('https://cwtools.globalmedicareapps.com/Tools/Plan/PlanSearch?year=2027&zip=34102&payerid=OPT');receipts.append(receipt)
 parser=Form();parser.feed(page.decode());inputs=parser.hidden
 if not parser.action or inputs.get('Year')!='2027' or inputs.get('County')!='Collier' or inputs.get('Zip')!='34102':raise ValueError('Search scope changed')
 inputs.update(MedicareMedicaid='True',Diabetes='False',Cardiovascular='False',Asthma='False')
 page,receipt=read(urljoin(receipt['final_url'],parser.action),urlencode(inputs).encode());receipt['synthetic_scenario']={'zip':'34102','year':'2027','county':'Collier','medicare_medicaid':True,'diabetes':False,'cardiovascular':False,'asthma':False};receipts.append(receipt)
 (ROOT/'optimum-search-result.html').write_bytes(page)
 print(receipt['final_url'],len(page))
except Exception as e:
 receipts.append({'error':type(e).__name__+': '+str(e),'action':'stop; no alternate route/retry'})
 print(type(e).__name__,str(e))
(ROOT/'optimum-search-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
