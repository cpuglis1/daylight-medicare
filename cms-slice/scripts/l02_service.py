#!/usr/bin/env python3
"""Loopback-only L02 developer service. No guest/profile/AI/legacy catalog dependency.

Research observations are readable. Consumer claims require an operator-installed
independent receipt for the exact build, claim, service code, scope and validity.
This service cannot release personal eligibility, ranking or recommendations.
"""
import argparse
from datetime import datetime,timezone,date
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,parse_qs
import cms_slice as cms
import l02_inventory as inv

class Held(cms.SourceError):pass

def verify_build(root):
 root=Path(root);manifest=cms.load_json(root/'build-manifest.json')
 if manifest['parser_version']!=inv.VERSION or manifest['policy_version']!=inv.POLICY or manifest['claim_version']!=inv.CLAIM or manifest['code_sha256']!=cms.file_hash(inv.__file__):raise Held('Parser/policy/claim/code binding changed; rebuild and review')
 if manifest['schema_sha256']!=cms.file_hash(inv.SPEC/'schemas.json'):raise Held('Current schema binding changed')
 if manifest.get('transformation_dependencies')!={'cms_slice.py':cms.file_hash(cms.__file__)}:raise Held('Shared transformation helper changed; rebuild and review')
 for rel,h in manifest['outputs'].items():
  p=(root/rel).resolve()
  if not p.is_relative_to(root.resolve()) or not p.is_file() or cms.file_hash(p)!=h:raise Held('Build integrity failure: '+rel)
 return manifest

class Inventory:
 def __init__(self,build,receipts=None):
  self.root=Path(build).resolve();self.manifest=verify_build(self.root);self.build_hash=cms.file_hash(self.root/'build-manifest.json');self.receipts=Path(receipts) if receipts else None
  self.policy=cms.load_json(self.root/'scope-policy.json')
 def query(self,*,year,county,capability='research_inventory',coverage_date=None,now=None):
  if cms.file_hash(self.root/'build-manifest.json')!=self.build_hash or self.manifest['schema_sha256']!=cms.file_hash(inv.SPEC/'schemas.json') or self.manifest['transformation_dependencies']!={'cms_slice.py':cms.file_hash(cms.__file__)}:raise Held('Build/schema/helper changed after service startup')
  if not re.fullmatch(r'\d{4}',str(year)) or not re.fullmatch(r'\d{5}',str(county)):raise Held('Explicit year and Census county FIPS required')
  if str(year)!=self.manifest['year'] or county not in self.policy['county_scopes']:raise Held('Unsupported year/county; no fallback or healthy empty market')
  if capability not in {'research_inventory','published_inventory'}:raise Held('L02 cannot release this capability')
  if coverage_date is not None:
   day=date.fromisoformat(coverage_date)
   if str(day.year)!=year:raise Held('Coverage date/year mismatch')
  # Recheck every response artifact to detect changes after process startup.
  for rel in [f'{county}/offerings.json',f'{county}/completeness-report.json','scope-policy.json']:
   if cms.file_hash(self.root/rel)!=self.manifest['outputs'][rel]:raise Held('Response artifact changed')
  receipt=None
  if capability=='published_inventory':
   now=now or datetime.now(timezone.utc)
   if now.tzinfo is None:raise Held('Timezone-aware acceptance time required')
   receipts=cms.load_json(self.receipts) if self.receipts and self.receipts.is_file() else {'receipts':[]}
   if not isinstance(receipts,dict) or not isinstance(receipts.get('receipts'),list):raise Held('Malformed acceptance registry')
   for r in receipts['receipts']:
    if not isinstance(r,dict) or r.get('reviewer_role') not in {'independent_medicare_reviewer','qualified_domain_reviewer'}:continue
    if not isinstance(r.get('gates'),dict) or not isinstance(r.get('coverage_dates'),list) or not isinstance(r.get('expected_offering_count'),int) or isinstance(r.get('expected_offering_count'),bool) or r['expected_offering_count']<0:continue
    if (r.get('decision')=='accepted' and r.get('benefit_year')==year and r.get('county_fips')==county and r.get('population')==self.policy['population'] and r.get('capability')==capability and r.get('build_manifest_sha256')==self.build_hash and r.get('source_manifest_sha256')==self.manifest['source_manifest_sha256'] and r.get('claim_version')==inv.CLAIM and r.get('service_code_sha256')==cms.file_hash(__file__) and r.get('reviewer') and r.get('reviewer_role') and r.get('independent_of_sales') is True and r.get('review_evidence') and r.get('accepted_claims')==['published_inventory'] and r.get('expected_offering_count') is not None and all(r.get('gates',{}).get(g)=='accepted' for g in ['G01','G02','G03','G04','G05'])):
     try:
      if not datetime.fromisoformat(r['accepted_at_utc'])<=now<datetime.fromisoformat(r['expires_at_utc']):continue
      if coverage_date is None or coverage_date not in r.get('coverage_dates',[]):continue
     except (KeyError,ValueError,TypeError):continue
     receipt=r;break
   if not receipt:raise Held('Consumer inventory held: exact independent source/build/claim/scope/freshness receipt absent')
  records=cms.load_json(self.root/county/'offerings.json')
  if receipt and (isinstance(receipt['expected_offering_count'],bool) or receipt['expected_offering_count']!=len(records)):raise Held('Accepted denominator disagrees with inventory')
  if receipt and not records and not receipt.get('negative_search_receipt'):raise Held('Empty accepted scope requires a positive negative-search evidence receipt')
  return {'capability':capability,'research_only':capability=='research_inventory','year':year,'county_fips':county,'count':len(records),'records':records,'claims':{'published_observations':True,'verified_address_availability':False,'open_to_enroll':False,'personal_eligibility':False},'bindings':{'build_manifest_sha256':self.build_hash,'source_manifest_sha256':self.manifest['source_manifest_sha256'],'claim_version':inv.CLAIM,'parser_version':inv.VERSION},'acceptance_receipt_id':receipt.get('id') if receipt else None,'completeness':cms.load_json(self.root/county/'completeness-report.json'),'personal_recommendations_accepted':False}

def make_server(build,port=8897,receipts=None):
 inventory=Inventory(build,receipts)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   code=200
   try:
    if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:raise Held('Loopback host required')
    if self.headers.get('Origin') not in {None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:raise Held('Cross-origin access rejected')
    url=urlsplit(self.path)
    if url.path!='/inventory' or len(url.query)>512:raise Held('Use the bounded inventory endpoint')
    q=parse_qs(url.query,strict_parsing=True)
    if set(q)-{'year','county','capability','coverage_date'} or any(len(v)!=1 for v in q.values()):raise Held('Unknown or repeated query field')
    result=inventory.query(**{k:v[0] for k,v in q.items()})
   except (ValueError,KeyError,TypeError,OSError) as e:code=503;result={'held':True,'error':str(e),'records':None,'personal_recommendations_accepted':False}
   raw=json.dumps(result).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
  def do_POST(self):self.send_error(405)
 return ThreadingHTTPServer(('127.0.0.1',port),Handler)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);group=p.add_mutually_exclusive_group(required=True);group.add_argument('--build',type=Path);group.add_argument('--selection',type=Path);p.add_argument('--receipts',type=Path);p.add_argument('--port',type=int,default=8897);a=p.parse_args()
 build=a.build
 if a.selection:
  selected=cms.load_json(a.selection)
  if selected['purpose']!='research_service_only' or cms.file_hash(Path(selected['build'])/'build-manifest.json')!=selected['sha256']:raise Held('Research selection integrity failure')
  build=Path(selected['build'])
 s=make_server(build,a.port,a.receipts);print(f'L02 research service http://127.0.0.1:{s.server_port}/inventory',flush=True)
 try:s.serve_forever()
 except KeyboardInterrupt:pass
 finally:s.server_close()
