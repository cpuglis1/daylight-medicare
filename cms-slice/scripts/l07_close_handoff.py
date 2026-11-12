#!/usr/bin/env python3
"""Seal validated additive L07 evidence and advance only the research selection."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l07-pharmacy-networks-2026-10-27'
OUT=BASE/'closeout-r1'


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    if (OUT/'SEALED').exists():raise ValueError('Closeout is sealed; create a new revision')
    validation=json.loads((OUT/'validation.json').read_text())
    package=BASE/'location-build-r4'
    assert validation['passed'] and validation['manifest_sha256']==sha(package/'manifest.json')
    assert validation['validator_sha256']==sha(ROOT/'cms-slice/scripts/l07_close_validate.py')
    assert json.loads((OUT/'test-results.json').read_text())['passed']
    observations=json.loads((OUT/'directory-observations.json').read_text())
    by_npi=defaultdict(list)
    for i,r in enumerate(observations):by_npi[r['npi']].append(i)
    current={(r['npi'],r['network_zip']):r for r in json.loads((package/'exceptions.json').read_text())}
    parent_cases=json.loads((BASE/'gap-cases.json').read_text())
    remaining=[{**r,'additional_directory_observation_indices':by_npi[r['npi']]} for r in parent_cases if (r['npi'],r['network_zip']) in current]
    assert len(remaining)==len(current)==1262
    assert {(r['npi'],r['network_zip']) for r in remaining}==set(current)
    con=sqlite3.connect('file:'+str(BASE/'build-r1/inventory.sqlite3')+'?mode=ro',uri=True)
    references_checked=0
    for r in remaining:
        for s in r['affected_source_rows']:
            actual=con.execute('SELECT pharmacy_npi,PHARMACY_ZIPCODE,offering_id FROM network WHERE source_part=? AND source_ordinal=?',(s['source_part'],s['source_ordinal'])).fetchone()
            assert actual==(r['npi'],r['network_zip'],s['offering_id'])
            references_checked+=1
    con.close();write(OUT/'remaining-gap-cases.json',remaining)
    old={(r['npi'],r['network_zip']):r for r in map(json.loads,gzip.open(BASE/'location-build-r3/locations.jsonl.gz','rt'))}
    comparisons=[]
    for d in json.loads((OUT/'decisions.json').read_text()):
        r=old[(d['npi'],d['network_zip'])];x=observations[d['directory_observation_index']]
        a=r['candidate_locations'][0]['registry_address'] if r['candidate_locations'] else None
        comparison={}
        for field,k,v in [('city','city','city'),('ZIP','postal_code','postal_code'),('phone','telephone_number','phone')]:
            if not a:state='registry_unavailable'
            elif a[k]==x[v]:state='same_literal'
            elif field=='phone' and re.sub(r'\D','',a[k])==re.sub(r'\D','',x[v] or ''):state='same_number_format_differs'
            elif field=='ZIP' and a[k][:5]==x[v][:5]:state='same_ZIP5_extension_or_format_differs'
            else:state='different_dated_values_retained'
            comparison[field]=state
        comparisons.append({'npi':d['npi'],'directory_observation_index':d['directory_observation_index'],
            'registry_address':a,'directory_address':{k:x[k] for k in ['street','city','state','postal_code','phone']},
            'native_CMS_ZIP':d['network_zip'],'phone_selection_added':False,'comparison':comparison})
    write(OUT/'field-comparisons.json',comparisons)
    qa=json.loads((OUT/'render-QA.json').read_text())
    qa['render_sha256']={str(OUT/f'page-{i}.png'):sha(OUT/f'page-{i}.png') for i in qa['one_based_PDF_pages']}
    write(OUT/'render-QA.json',qa)
    baseline=json.loads((OUT/'baseline.json').read_text())
    baseline_checks={p:sha(OUT/'previous-selection.json' if p==str(BASE.relative_to(ROOT)/'CURRENT_REFERENCE.json') else ROOT/p)==h for p,h in baseline.items()}
    prior=json.loads((BASE/'preservation-before.json').read_text())
    prior_checks={p:sha(ROOT/p)==h for p,h in prior['sha256'].items()}
    assert all(baseline_checks.values()) and all(prior_checks.values())
    write(OUT/'preservation.json',{'passed':True,'baseline_checks':baseline_checks,'prior_reference_checks':prior_checks,
        'note':'Only CURRENT_REFERENCE.json advances. Exact previous selection preserved; original sealed evidence, code, reports, UI and other-layer reference artifacts unchanged.'})
    files=[p for p in OUT.iterdir() if p.is_file() and p.name not in ['manifest.json','handoff.json','SEALED','amerihealth.txt']]
    files+=list((ROOT/'cms-slice/scripts').glob('l07_close_*.py'))
    write(OUT/'manifest.json',{'schema':'l07-additive-closeout-manifest/1','date_local':'2026-10-27',
        'sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},
        'composite_manifest':{'path':str((package/'manifest.json').relative_to(ROOT)),'sha256':sha(package/'manifest.json')},
        'raw_source_receipts':'sources.json','consumer_release_enabled':False,'human_acceptance':None})
    selection=json.loads((OUT/'previous-selection.json').read_text())
    selection['components']['locations']={'package':'location-build-r4','manifest_sha256':sha(package/'manifest.json'),
        'validation':'closeout-r1/validation.json','validation_sha256':sha(OUT/'validation.json')}
    selection['gaps']={'path':'closeout-r1/gaps.json','sha256':sha(OUT/'gaps.json')}
    selection['followup']={'package':'closeout-r1','report':'closeout-r1/README.md','manifest_sha256':sha(OUT/'manifest.json'),
        'previous_selection':'closeout-r1/previous-selection.json','new_resolutions':379}
    write(BASE/'CURRENT_REFERENCE.json',selection)
    handoff={'schema':'l07-additive-closeout-handoff/1','passed':True,'date_local':'2026-10-27',
        'manifest_sha256':sha(OUT/'manifest.json'),'selection_sha256':sha(BASE/'CURRENT_REFERENCE.json'),
        'validation_sha256':sha(OUT/'validation.json'),'source_rows_in_remaining_case_register_checked':references_checked,
        'remaining_cases':len(remaining),'new_resolutions':379,'known_regional_resolutions':9,'known_regional_cases':10,
        'prior_reference_files_preserved':len(prior_checks),'baseline_files_preserved_or_selection_archived':len(baseline_checks),
        'phone_comparisons':dict(Counter(r['comparison']['phone'] for r in comparisons)),
        'consumer_release_enabled':False,'human_acceptance':None}
    write(OUT/'handoff.json',handoff)
    (OUT/'SEALED').write_text(sha(OUT/'manifest.json')+'\n')
    print(json.dumps(handoff,indent=2))


if __name__=='__main__':main()
