#!/usr/bin/env python3
"""Explicit official-public L02 acquisition; never uses Medicare Plan Finder.

An immutable capture directory is one acquisition version. Re-running verifies cached
bytes. A refresh requires a new directory; source rights/review remain separate.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import zipfile
from urllib.error import HTTPError
import cms_slice as cms
from evidence_store import PublicSources

BASE = 'https://www.cms.gov/'
SOURCES = {
 'landscape': ('P26-S04A', 'files/zip/cy2026-landscape-202609.zip', '2026', '2026-09'),
 'pbp': ('P26-S08A-JSON', 'files/zip/pbp-benefits-2026-json.zip', '2026', '2026 annual; revision date not declared'),
 'contract-area': ('L02-S03', 'files/zip/ma-contract-service-area-state-county-october-2026.zip', '2026', '2026-10'),
 'snp': ('L02-S04', 'files/zip/snp-comprehensive-report-october-2026.zip', '2026', '2026-10'),
 'enforcement': ('L02-S05', 'medicare/audits-compliance/part-c-d/part-c-and-part-d-enforcement-actions', None, 'observed page; not complete historical status'),
 'cms-policy': ('L02-USE', 'about-cms/web-policies-important-links/about-website', None, 'observed policy'),
}

def acquire(out, only=None):
 out=Path(out); cache=PublicSources(out/'receipts.json', out/'raw')
 manifest={'schema_version':'l02-sources-v1','sources':{},'collection_stop':{'P26-S06':'STOP; no request attempted'},
           'use_review':'pending R07; public acquisition is not consumer redistribution approval'}
 if (out/'source-manifest.json').exists(): manifest=cms.load_json(out/'source-manifest.json')
 for name, (sid,path,year,period) in SOURCES.items():
  if only and name not in only: continue
  try:
   spec,raw=cache.capture(sid,BASE+path,max_bytes=400_000_000,review_days=0)
  except HTTPError as e:
   manifest['sources'][name]={'id':sid,'requested_url':BASE+path,'status':'unavailable','http_status':e.code,'benefit_year':year,'source_period':period}
   cms.write_json(out/'source-manifest.json',manifest)
   print(name,'unavailable',e.code,flush=True);continue
  item={**spec,'benefit_year':year,'source_period':period,'layout_review':'pending',
        'allowed_use':'research capture authorized; domain/source acceptance pending'}
  if raw[:2]==b'PK':
   with zipfile.ZipFile(cache.raw/spec['sha256']) as z:
    if len(z.namelist())!=len(set(z.namelist())): raise cms.SourceError('Duplicate archive members')
    item['members']=[{'name':m.filename,'bytes':m.file_size,'sha256':cms.sha256(z.read(m))} for m in z.infolist()]
  manifest['sources'][name]=item
  cms.write_json(out/'source-manifest.json',manifest)
  print(name,spec['bytes'],spec['sha256'],flush=True)
 return manifest

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--only',nargs='+',choices=SOURCES)
 a=p.parse_args();acquire(a.out,a.only)
