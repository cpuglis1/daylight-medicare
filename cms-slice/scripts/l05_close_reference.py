#!/usr/bin/env python3
"""Bounded read-only L05 condition/unit lookup with all dates and gaps exposed."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

from l05_reference import project,verify as verify_base

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25/build-r3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())


def verify(package):
    verify_base(BASE);m=read(package/'manifest.json')
    for group,root in [('files',package),('inputs',ROOT),('code',ROOT)]:
        for name,digest in m[group].items():
            if not (root/name).is_file() or sha(root/name)!=digest:raise ValueError('Changed closeout '+group+': '+name)
    audit=read(package.with_name(package.name+'-validation.json'))
    if not audit['passed'] or audit['manifest_sha256']!=sha(package/'manifest.json'):raise ValueError('Exact closeout source audit does not pass')
    return m


def lookup(package,request):
    verify(package)
    # Reuse the existing strict request contract, exact drug identity and scope.
    result=project(BASE,request);ident=request['offering_id']
    plan=next(p for p in read(package/'plans.json') if p['offering_id']==ident)
    docs={d['id']:d for d in read(package/'documents.json')}
    needed={d for kind in ['current_dated_criteria','earlier_dated_criteria'] for ids in plan[kind].values() for d in ids}
    unit_keys={(r['table'],r['source_row']) for r in result['matches']}
    with gzip.open(package/'quantity-units.jsonl.gz','rt') as f:units={(r['table'],r['source_row']):r for r in map(json.loads,f) if (r['table'],r['source_row']) in unit_keys}
    for match in result['matches']:
        match['quantity_unit_evidence']=units.get((match['table'],match['source_row']))
    with gzip.open(package/'condition-reference-links.jsonl.gz','rt') as f:
        conditions=[r for r in map(json.loads,f) if (r['table'],r['source_row']) in unit_keys]
    result['drug_condition_references']=[{**r,'plan_links':[p for p in r['plan_links'] if p['offering_id']==ident]} for r in conditions]
    needed.update(d for r in result['drug_condition_references'] for link in r['plan_links'] for d in link['matching_questionnaire_ids'])
    result['all_plan_questionnaires_in_registry']=len(plan['prescriber_questionnaires'])
    result['condition_source_state']=plan['condition_source_state']
    result['dated_condition_documents']=[{k:docs[d][k] for k in ['id','kind','full_criteria','family','declared_date','archive_timestamp','formulary_id','formulary_version','source_url','path','full_text_path']} for d in sorted(needed)]
    result['historical_alignment']='Documents retain their own dates. Neither a different version number nor unchanged bracketing text proves the exact September rule. No later rule is silently backdated.'
    result['complete_L05_conditions']=False
    result['questionnaires_are_complete_approval_criteria']=False
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',required=True,type=Path);p.add_argument('--offering-id',required=True);p.add_argument('--rxcui',required=True);a=p.parse_args()
    print(json.dumps(lookup(a.package.resolve(),{'year':2026,'offering_id':a.offering_id,'rxcui':a.rxcui}),indent=2))
