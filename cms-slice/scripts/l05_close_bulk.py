#!/usr/bin/env python3
"""Capture one explicitly public NLM subset with a 128 MiB size/hash bound."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
import zipfile

from l04_acquire import put,write

URL='https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_10052026.zip'
EXPECTED_MD5='a3bfab544c6a67c127ebcd10ab914aa9'
LIMIT=128*1024*1024


def acquire(out):
    if out.exists():raise ValueError('Immutable bulk acquisition exists')
    out.mkdir();(out/'raw').mkdir()
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            u=urlparse(newurl)
            if u.scheme!='https' or u.hostname!='download.nlm.nih.gov' or '/rxnorm/' not in u.path:raise ValueError('No login/alternate-origin redirect allowed')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    with build_opener(Redirect).open(Request(URL,headers={'User-Agent':'Daylight published Medicare reference research'}),timeout=45) as r:
        if r.status!=200 or 'zip' not in r.headers.get('Content-Type','').lower():raise ValueError('Expected public ZIP, never a login page')
        length=int(r.headers.get('Content-Length','0'))
        if length>LIMIT:raise ValueError('NLM subset exceeds declared 128 MiB bound')
        print('Public NLM subset content length',length,flush=True)
        data=r.read(LIMIT+1)
        if len(data)>LIMIT or length and len(data)!=length:raise ValueError('Oversize/truncated public ZIP')
        if hashlib.md5(data).hexdigest()!=EXPECTED_MD5:raise ValueError('NLM published MD5 differs')
        receipt={'requested_url':URL,'final_url':r.url,'http_status':r.status,'headers':{k.lower():v for k,v in r.headers.items() if k.lower() in ['content-length','content-type','last-modified']},'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),**put(out,data),'published_md5':EXPECTED_MD5,'published_md5_matches':True,'source_index':'https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html','source_use':'NLM explicitly describes this exact prescribable subset as public domain, no license/login required; identity evidence only'}
    with zipfile.ZipFile(Path(__file__).resolve().parents[2]/receipt['path']) as z:
        receipt['members']=[{'name':i.filename,'bytes':i.file_size,'CRC32':f'{i.CRC:08x}'} for i in z.infolist()]
    write(out/'source-manifest.json',receipt);print('captured public ZIP',len(data),'bytes; published MD5 matches',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args();acquire(a.out.resolve())
