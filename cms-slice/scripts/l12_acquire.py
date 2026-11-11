"""Retain public L12 evidence within an explicit official-source allowlist."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
ACQ=BASE/'acquisition-r1'
ALLOWED={'www.cms.gov','www.medicaid.gov','secure.ssa.gov','www.myflfamilies.com',
         'ffic.myflfamilies.com','www.floridashine.org','elderaffairs.org',
         'www.govinfo.gov','www.ecfr.gov','uscode.house.gov','aspe.hhs.gov',
         'flrules.org','www.flrules.org','laws.flrules.org',
         'library.floridahealthjustice.org'} # Public archive of an original dated DCF memorandum, provenance explicit.


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme!='https' or urlparse(newurl).hostname not in ALLOWED:
            raise ValueError('Unexpected redirect: '+newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def collect(sid,url):
    if (BASE/'build-r1/manifest.json').exists():raise ValueError('r1 sealed; use a new revision')
    if urlparse(url).scheme!='https' or urlparse(url).hostname not in ALLOWED:raise ValueError('Source not allowlisted')
    (ACQ/'raw').mkdir(parents=True,exist_ok=True);(ACQ/'receipts').mkdir(exist_ok=True)
    target=ACQ/'receipts'/(sid+'.json')
    if target.exists():
        r=json.loads(target.read_text())
        if r['url']!=url:raise ValueError('Source URL changed; new ID required')
        if r['status']!='retained':raise ValueError('Existing failed route; no retry')
        if hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Changed retained bytes')
        return r
    for old in (ACQ/'receipts').glob('*.json'):
        r=json.loads(old.read_text())
        if r.get('access_stop') and urlparse(r['url']).hostname==urlparse(url).hostname:
            raise ValueError('Existing host access stop')
    req=Request(url,headers={'User-Agent':'DaylightPublicEvidenceResearch/1.0','Accept-Encoding':'gzip'})
    try:
        try:response=build_opener(Redirects()).open(req,timeout=40)
        except HTTPError as e:response=e
        with response:
            wire=response.read(12_000_001)
            data=gzip.decompress(wire) if response.headers.get('Content-Encoding')=='gzip' else wire
            h=hashlib.sha256(data).hexdigest()
            challenge=any(s in data[:100000].lower() for s in [b'challenge-platform',b'captcha-delivery',b'just a moment...'])
            ok=response.code==200 and len(data)<=12_000_000 and not challenge
            r={'id':sid,'url':url,'final_url':response.url,'http_status':response.code,
               'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
               'last_modified':response.headers.get('Last-Modified'),
               'content_type':response.headers.get('Content-Type'),'sha256':h,'bytes':len(data),
               'path':str((ACQ/'raw'/h).relative_to(ROOT)),'status':'retained' if ok else 'failed',
               'access_stop':response.code in [401,403,429] or challenge,
               'retry_count':0}
        (ROOT/r['path']).write_bytes(data)
    except (URLError,TimeoutError) as e:
        r={'id':sid,'url':url,'status':'failed','reason':str(e),'access_stop':False,
           'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'retry_count':0}
    target.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--targets',type=Path,required=True);args=p.parse_args()
    for t in json.loads(args.targets.read_text()):
        r=collect(t['id'],t['url'])
        print(json.dumps({k:r.get(k) for k in ['id','status','bytes','access_stop','reason']}),flush=True)
