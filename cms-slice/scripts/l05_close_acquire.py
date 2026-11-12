#!/usr/bin/env python3
"""Bounded public NLM concept capture; no approximate/clinical/coverage inference."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import time
from urllib.parse import urlparse,parse_qs

from l05_acquire import request
from l04_acquire import put,write


def acquire(out,entries):
    if (out/'SEALED').exists():raise ValueError('Sealed acquisition')
    out.mkdir(parents=True,exist_ok=True);(out/'raw').mkdir(exist_ok=True)
    manifest_path=out/'source-manifest.json';m=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema':'l05-close-NLM-acquisition/1','sources':{}}
    todo=[]
    for e in entries:
        u=urlparse(e['url']);q=parse_qs(u.query)
        if u.scheme!='https' or u.hostname!='rxnav.nlm.nih.gov' or u.path!='/REST/rxcui.json' or q.get('search')!=['1'] or q.get('allsrc')!=['0']:raise ValueError('Unsupported NLM operation')
        if e['id'] in m['sources']:
            if m['sources'][e['id']]['requested_url']!=e['url']:raise ValueError('ID/URL collision')
            continue
        todo.append(e)
    def capture(e):
        time.sleep(.25)  # At most three concurrent requests; below NLM's public cap.
        try:
            body,r=request(e['url'],out);data=json.loads(body)
            if 'idGroup' not in data:raise ValueError('Unexpected NLM response schema')
            return e['id'],{**e,**r,**put(out,body),'status':'captured','human_acceptance':None}
        except Exception as exc:return e['id'],{**e,'requested_url':e['url'],'status':'unavailable','http_status':getattr(exc,'code',None),'reason':str(exc)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,f in enumerate(as_completed([pool.submit(capture,e) for e in todo]),1):
            ident,s=f.result();m['sources'][ident]=s;write(manifest_path,m)
            if i%100==0 or i==len(todo):print('captured',i,'of',len(todo),'identity responses',flush=True)
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--entries',type=Path,required=True);a=p.parse_args();acquire(a.out.resolve(),json.loads(a.entries.read_text()))
