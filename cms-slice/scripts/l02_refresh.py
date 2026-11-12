#!/usr/bin/env python3
"""Review-only immutable L02 refresh diff, deterministic replay and research rollback.
No acceptance is inherited. Selection affects only the standalone research service.
"""
import argparse
import csv
import json
from pathlib import Path
import cms_slice as cms
import l02_inventory as inv
from l02_service import verify_build

def table(root):
 with (Path(root)/'offerings.csv').open() as f:return {r['id']:r for r in csv.DictReader(f)}
def compare(previous,current):
 a=verify_build(previous);b=verify_build(current);left=table(previous);right=table(current)
 changed=[]
 for key in sorted(left.keys()&right.keys()):
  fields={f:{'before':left[key][f],'after':right[key][f]} for f in left[key] if left[key][f]!=right[key][f] and f!='locator'}
  if fields:changed.append({'id':key,'fields':fields})
 areas=[]
 for root in [previous,current]:
  with (Path(root)/'service-areas.csv').open() as f:areas.append({inv.canonical({k:v for k,v in r.items() if k not in {'id','locator'}}) for r in csv.DictReader(f)})
 return {'previous_build':cms.file_hash(Path(previous)/'build-manifest.json'),'current_build':cms.file_hash(Path(current)/'build-manifest.json'),'years':[a['year'],b['year']],'added':sorted(right.keys()-left.keys()),'removed_tombstones':[{'id':i,'prior_record':left[i],'status':'removed_from_source_snapshot_not_proof_unavailable'} for i in sorted(left.keys()-right.keys())],'changed':changed,'geography_added':len(areas[1]-areas[0]),'geography_removed':len(areas[0]-areas[1]),'identical_outputs':a['outputs']==b['outputs'],'source_changed':a['source_manifest_sha256']!=b['source_manifest_sha256'],'affected_claims':'all claims bound to a different build require new acceptance','consumer_promotion':False}
def select(root,pointer):
 verify_build(root);value={'purpose':'research_service_only','build':str(Path(root).resolve()),'sha256':cms.file_hash(Path(root)/'build-manifest.json'),'consumer_acceptance_inherited':False}
 if Path(pointer).exists():value['previous_selection']=cms.load_json(pointer)
 cms.write_json(pointer,value);return value
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 d=sub.add_parser('diff');d.add_argument('previous',type=Path);d.add_argument('current',type=Path);d.add_argument('--out',type=Path,required=True)
 s=sub.add_parser('select-research');s.add_argument('build',type=Path);s.add_argument('--pointer',type=Path,required=True);a=p.parse_args()
 if a.action=='diff':
  if a.out.exists():raise cms.SourceError('Preserve existing diff; choose a new output')
  cms.write_json(a.out,compare(a.previous,a.current))
 else:select(a.build,a.pointer)
