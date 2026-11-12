#!/usr/bin/env python3
"""Bounded supplementary official evidence, no denial retries or Plan Finder.
Inputs are explicit reviewed official URLs. Raw documents are not AI context.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import subprocess
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from urllib.request import build_opener,HTTPRedirectHandler,Request
import cms_slice as cms
from evidence_store import html_text
STATE=cms.ROOT.parent/'docs/data/l02-ma-availability-2026-10-25/source-access-state.json'

HOSTS={'www.cms.gov','assets.humana.com','www.uhc.com','www.aetna.com','www.wellcare.com','www.healthspring.com','www.floridablue.com','files.guidewell.com','www.youroptimumhealthcare.com','www.freedomhealth.com'}
class Redirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if urlsplit(newurl).scheme!='https' or urlsplit(newurl).hostname not in HOSTS:raise cms.SourceError('Unreviewed redirect; no request made')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def capture(config,out,*,access_state=STATE,opener=None):
 out=Path(out)
 if out.exists():raise cms.SourceError('Use a new immutable supplemental version')
 out.mkdir(parents=True);(out/'raw').mkdir();(out/'extracted').mkdir();state=cms.load_json(access_state) if Path(access_state).exists() else {'origins':{},'Plan_Finder':'STOP'}
 stops={h for h,v in state['origins'].items() if v['status']=='stopped'};receipts=[];opener=opener or build_opener(Redirect)
 def stop(host,reason):
  stops.add(host);state['origins'][host]={'status':'stopped','reason':reason,'observed_at_utc':datetime.now(timezone.utc).isoformat(),'reopen_authorization':None};cms.write_json(access_state,state)
 for source in cms.load_json(config):
  host=urlsplit(source['url']).hostname;r={**source,'observed_at_utc':datetime.now(timezone.utc).isoformat(),'allowed_use':'research acquisition; R07 redisplay/use acceptance pending','reviewer':None,'status':'unavailable'}
  if host not in HOSTS or host in stops:r['reason']='Unreviewed or stopped host; no request made'
  else:
   try:
    with opener.open(Request(source['url'],headers={'User-Agent':'Daylight-L02-Public-Research/1'}),timeout=30) as response:
     raw=response.read(25_000_001)
     if len(raw)>25_000_000:raise cms.SourceError('Source exceeds bound')
     if b'access denied' in raw[:10000].lower():stop(host,'Access challenge');raise cms.SourceError('Access denial; stopped host')
     sha=cms.sha256(raw);p=out/'raw'/sha
     if not p.exists():p.write_bytes(raw)
     r.update(status='acquired',sha256=sha,bytes=len(raw),final_url=response.url,content_type=response.headers.get('Content-Type'),last_modified=response.headers.get('Last-Modified'))
     text=out/'extracted'/(sha+'.txt')
     if raw.startswith(b'%PDF'):subprocess.run(['pdftotext','-layout',str(p),str(text)],check=True,stderr=subprocess.PIPE);r['extraction']='pdftotext -layout'
     else:text.write_text(html_text(raw));r['extraction']='VisibleHTML'
     r['extracted_sha256']=cms.file_hash(text)
   except (HTTPError,URLError,ValueError,OSError,subprocess.CalledProcessError) as e:
    r['reason']=str(e)
    if isinstance(e,HTTPError) and e.code in {401,403,429}:stop(host,'HTTP '+str(e.code))
  receipts.append(r);cms.write_json(out/'source-manifest.json',{'sources':receipts,'stopped_hosts':sorted(stops),'Plan_Finder':'STOP; no request attempted'})
  print(source['id'],r['status'],r.get('bytes',r.get('reason')),flush=True)
 return receipts
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();capture(a.config,a.out)
