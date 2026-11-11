#!/usr/bin/env python3
"""Offline cross-build L02 evidence audit; no external requests or customer data."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import sqlite3
import zipfile
import cms_slice as cms
import l02_inventory as inv
from l02_service import Inventory,verify_build,Held

def validate(package):
 p=Path(package);results={};root=p/'build-r5'
 for name in ['build-r5','build-replay-final','build-refresh-final','build-2027-final']:
  build=p/name;manifest=verify_build(build);service=Inventory(build,p/'acceptance-receipts.json');year=manifest['year'];scopes={}
  for county in ['12021','12071','36061']:
   response=service.query(year=year,county=county);assert response['research_only'];assert not response['personal_recommendations_accepted'];assert response['completeness']['denominator']['expected_offering_count'] is None
   try:service.query(year=year,county=county,capability='published_inventory',coverage_date=year+'-10-25')
   except Held:pass
   else:raise AssertionError('Consumer gate unexpectedly open')
   scopes[county]=response['count']
  results[name]={'build_manifest_sha256':cms.file_hash(build/'build-manifest.json'),'scopes':scopes,'integrity':'pass','consumer_claims':'held'}
 assert cms.file_hash(root/'build-manifest.json')==cms.file_hash(p/'build-replay-final/build-manifest.json')
 replay=cms.load_json(p/'replay-verification.json');refresh=cms.load_json(p/'refresh-diff.json');assert replay['identical_outputs'];assert not refresh['added'] and not refresh['removed_tombstones'] and not refresh['changed'];assert refresh['source_changed'];assert not refresh['consumer_promotion']
 db=sqlite3.connect(root/'inventory.sqlite3');db.row_factory=sqlite3.Row
 # Real partial-county evidence remains contract-level. Inspect an overlapping
 # published offering without turning the contract flag into a plan boundary.
 partial=db.execute("SELECT a.contract,a.county_fips,a.state,a.county,a.locator,a.raw_json FROM areas a WHERE a.source='contract-area' AND a.extent='partial' ORDER BY a.contract,a.county_fips LIMIT 1").fetchone()
 assert partial is not None
 case=dict(partial);case['evidence_kind']='real_CMS_October_2026_contract_partial_flag';case['offering_observations']=[dict(r) for r in db.execute("SELECT o.id,a.extent FROM offerings o JOIN areas a ON o.id=a.offering_id WHERE o.contract=? AND a.county_fips=? AND a.source='landscape' ORDER BY o.id",(partial['contract'],partial['county_fips']))];case['result']='partial boundary requires offering-specific evidence; no expansion or address claim'
 cms.write_json(p/'partial-area-real-case.json',case)
 keys={r['id'] for r in cms.load_json(root/'12021/offerings.json')};ind=cms.load_json(p/'independent-parent-set-comparison.json');assert ind['set_equal'] and ind['count']==len(keys)==72
 assert {r['id'] for r in db.execute("SELECT id FROM offerings WHERE route='L02' AND id IN (SELECT offering_id FROM areas WHERE county_fips='12021' AND source='landscape')")}==keys
 db.close();results['replay']='identical outputs and build manifest';results['real_refresh']='identical publisher bytes, new acquisition receipt, no promotion';results['independent_parent_key_comparison']='72 identities; exact set match';results['partial_area']=case;results['recommendations']='held'
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,default=inv.SPEC);p.add_argument('--out',type=Path);a=p.parse_args();r=validate(a.package);cms.write_json(a.out or a.package/'validation-results.json',r);print(json.dumps({k:v for k,v in r.items() if k!='partial_area'},indent=2))
