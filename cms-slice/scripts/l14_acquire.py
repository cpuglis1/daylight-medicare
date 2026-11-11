"""Additive public-source intake for the L14 other-coverage reference."""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler,Request,build_opener

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l14-other-coverage-2026-10-29'
ACQ=BASE/'acquisition-r1'
HOSTS={'www.myflfamilies.com','ffic.myflfamilies.com','library.floridahealthjustice.org',
       'www.cms.gov','secure.ssa.gov','www.ecfr.gov','www.govinfo.gov','flrules.org','laws.flrules.org',
       'www.hhs.gov','www.floridashine.org','elderaffairs.org','www.irs.gov','www.tricare.mil','tricare.mil','www.va.gov','www.opm.gov','www.rrb.gov','hopepace.org','hopehcs.org','fenyxhealth.com','www.flpace.org','flpace.org','www.humana.com','www.flsenate.gov'}
STOPPED={'www.medicaid.gov','www.ssa.gov','www.medicare.gov','ahca.myflorida.com'}

def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

class Redirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlparse(newurl).scheme!='https' or urlparse(newurl).hostname not in HOSTS:raise ValueError('Unexpected redirect '+newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def collect(sid,url):
    if (BASE/'build-r1/manifest.json').exists():raise ValueError('Sealed L14 r1; new revision required')
    if urlparse(url).hostname in STOPPED or urlparse(url).hostname not in HOSTS or urlparse(url).scheme!='https':raise ValueError('Source stop or outside allowlist')
    (ACQ/'receipts').mkdir(parents=True,exist_ok=True);(ACQ/'raw').mkdir(exist_ok=True)
    dest=ACQ/'receipts'/f'{sid}.json'
    if dest.exists():
        old=json.loads(dest.read_text())
        if old['url']!=url or old['status']!='retained':raise ValueError('Changed URL or failed route; no retry')
        assert hashlib.sha256((ROOT/old['path']).read_bytes()).hexdigest()==old['sha256']
        return old
    for p in (ACQ/'receipts').glob('*.json'):
        old=json.loads(p.read_text())
        if old.get('access_stop') and urlparse(old['url']).hostname==urlparse(url).hostname:raise ValueError('Existing host stop')
    try:
        req=Request(url,headers={'User-Agent':'DaylightPublicEvidenceResearch/1.0','Accept-Encoding':'gzip'})
        try:response=build_opener(Redirects()).open(req,timeout=40)
        except HTTPError as e:response=e
        with response:
            wire=response.read(12_000_001);data=gzip.decompress(wire) if response.headers.get('Content-Encoding')=='gzip' else wire
            sha=hashlib.sha256(data).hexdigest()
            challenge=any(x in data[:100000].lower() for x in [b'challenge-platform',b'captcha-delivery',b'just a moment...'])
            wrong_payload=(urlparse(url).path.endswith('.pdf') and not data.startswith(b'%PDF')) or urlparse(response.url).path=='/error'
            row={'id':sid,'url':url,'final_url':response.url,'http_status':response.code,
                 'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(data),'sha256':sha,
                 'path':str((ACQ/'raw'/sha).relative_to(ROOT)),'content_type':response.headers.get('Content-Type'),
                 'last_modified':response.headers.get('Last-Modified'),'status':'retained' if response.code==200 and len(data)<=12_000_000 and not challenge and not wrong_payload else 'failed',
                 'payload_error':'Requested PDF returned non-PDF/error page' if wrong_payload else None,
                 'access_stop':response.code in [401,403,429] or challenge,'retry_count':0}
            (ROOT/row['path']).write_bytes(data)
    except (URLError,TimeoutError) as e:
        row={'id':sid,'url':url,'status':'failed','reason':str(e),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'access_stop':False,'retry_count':0}
    except ValueError as e:
        row={'id':sid,'url':url,'status':'failed','reason':str(e),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'access_stop':True,'retry_count':0}
    write(dest,row);return row

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--targets',type=Path,required=True);a=p.parse_args()
    for target in json.loads(a.targets.read_text()):
        r=collect(target['id'],target['url']);print(json.dumps({k:r.get(k) for k in ['id','status','bytes','http_status','access_stop','reason']}),flush=True)
