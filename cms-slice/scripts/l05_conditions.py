#!/usr/bin/env python3
"""Dated L05 condition-source assessment, separate from the complete CMS lists.

Retains full document/page evidence and enumerates every flagged source context.
Candidate later documents never become accepted historical criteria by inference.
"""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')


def assess(package,out):
    if out.exists():raise ValueError('Immutable assessment already exists')
    from l05_reference import verify
    verify(package)
    review=read(BASE/'condition-source-review.json')
    sup=read(BASE/'supplemental-r1/source-manifest.json')['sources']
    docs=[];bound={};failures=[];checks=Counter()
    for r in review['reviews']:
        s=r.get('reused_source') or sup[r['source_id']]
        raw,text=ROOT/s['path'],ROOT/s['text_path']
        if sha(raw)!=s['sha256'] or sha(text)!=s['text_sha256']:raise ValueError('Changed document '+r['source_id'])
        bound[str(raw.relative_to(ROOT))]=sha(raw);bound[str(text.relative_to(ROOT))]=sha(text)
        # Complete independent re-extraction: includes all continuation pages/footnotes.
        extracted=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout
        checks['full_pdf_text_reextraction']+=1
        if hashlib.sha256(extracted).hexdigest()!=s['text_sha256']:failures.append('pdf_text:'+r['source_id'])
        body=extracted.decode('utf-8');pages=body.split('\f')
        if pages and not pages[-1].strip():pages.pop()
        checks['cover_anchor_and_document_population']+=1
        if ' '.join(r['cover_anchor'].split()) not in ' '.join(body.split()):failures.append('cover_anchor:'+r['source_id'])
        docs.append({**r,'url':s['requested_url'],'path':s['path'],'sha256':s['sha256'],
                     'full_text_path':s['text_path'],'full_text_sha256':s['text_sha256'],
                     'page_count':len(pages),'page_locators':[{'pdf_page':i,'text_sha256':hashlib.sha256(t.encode()).hexdigest()} for i,t in enumerate(pages,1)]})
    plans=read(package/'plans.json');forms=defaultdict(list);pairs=defaultdict(list)
    for p in plans:
        forms[p['formulary_id']].append(p)
        pairs[tuple(p['offering_id'].split(':')[1:3])].append(p)
    docs_by_form=defaultdict(list)
    for d in docs:
        for f in d['candidate_formulary_ids']:docs_by_form[f].append(d)
    db=sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True)
    matrix=[];groups={};source_cases=[]
    for p in plans:
        row={k:p[k] for k in ['offering_id','parent','name','formulary_id','formulary_version']}
        row['candidate_document_ids']=[d['source_id'] for d in docs_by_form[p['formulary_id']]]
        row['criteria_state']='No September-version PA/ST text accepted; later/unbound candidate text is retained where found.'
        g=groups.setdefault(p['parent'],{'plans':0,'formulary_ids':set(),'candidate_document_ids':set(),'source_access_state':'ordinary_public_discovery','unique_basic_source_contexts':Counter()})
        g['plans']+=1;g['formulary_ids'].add(p['formulary_id']);g['candidate_document_ids'].update(row['candidate_document_ids'])
        if p['parent'] in ('UnitedHealth Group, Inc.','Centene Corporation'):g['source_access_state']='inherited_carrier_access_STOP; no alternate route used'
        for fact in ['prior_authorization_criteria','step_therapy_criteria','physical_quantity_unit']:
            contract,number=p['offering_id'].split(':')[1:3]
            row[fact+'_source_contexts']=db.execute('''SELECT count(*) FROM condition_gaps g JOIN drug_rows d ON g.table_name=d.table_name AND g.ordinal=d.ordinal
 WHERE g.missing_fact=? AND ((d.table_name='basic' AND d.formulary_id=?) OR (d.table_name IN ('excluded','indication') AND d.contract_id=? AND d.plan_id=?))''',(fact,p['formulary_id'],contract,number)).fetchone()[0]
        matrix.append(row)
    out.mkdir()
    path=out/'condition-contexts.csv.gz'
    # Each CMS source context once, with its full exact affected-plan list.
    with gzip.open(path,'wt',newline='') as f:
        w=csv.writer(f);w.writerow(['table','source_row','rxcui','formulary_id','contract_id','plan_id','missing_CMS_detail','affected_offering_ids','candidate_document_ids','resolution_state','additional_source_needed'])
        for table,ordinal,fact,rx,form,contract,number in db.execute('''SELECT g.table_name,g.ordinal,g.missing_fact,d.rxcui,d.formulary_id,d.contract_id,d.plan_id
 FROM condition_gaps g JOIN drug_rows d ON g.table_name=d.table_name AND g.ordinal=d.ordinal ORDER BY g.table_name,g.ordinal,g.missing_fact'''):
            affected=forms[form] if table=='basic' else pairs[(contract,number)]
            candidates={d['source_id'] for p in affected for d in docs_by_form[p['formulary_id']] if d['content_kind'] in ('formulary',{'prior_authorization_criteria':'PA','step_therapy_criteria':'ST','physical_quantity_unit':'QL'}[fact])}
            state='snapshot_criterion_text_not_bound' if fact!='physical_quantity_unit' else 'unit_not_asserted; numeric_amount_and_days_complete'
            need='Exact applicable September CMS-version carrier Part D '+('PA' if fact=='prior_authorization_criteria' else 'ST')+' criteria, or dated change evidence connecting retained text to that snapshot' if fact!='physical_quantity_unit' else 'Only if asserting physical units: applicable quantity-unit evidence; do not infer from a proxy NDC or dosage form alone'
            w.writerow([table,ordinal,rx,form or '',contract or '',number or '',fact,json.dumps([p['offering_id'] for p in affected]),json.dumps(sorted(candidates)),state,need])
            source_cases.append((table,ordinal,fact))
            if table=='basic':
                for parent in {p['parent'] for p in affected}:groups[parent]['unique_basic_source_contexts'][fact]+=1
    db.close()
    with (out/'plan-condition-matrix.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader()
        for r in matrix:w.writerow({**r,'candidate_document_ids':json.dumps(r['candidate_document_ids'])})
    for g in groups.values():
        g['formulary_ids']=sorted(g['formulary_ids']);g['candidate_document_ids']=sorted(g['candidate_document_ids']);g['unique_basic_source_contexts']=dict(g['unique_basic_source_contexts'])
    coverage=read(package/'coverage.json')
    actual=Counter(c[2] for c in source_cases);checks['all_flagged_CMS_source_contexts_reconciled']+=1
    if dict(actual)!=coverage['condition_details_not_supplied_by_CMS_tables'] or len(source_cases)!=len(set(source_cases)):failures.append('condition_context_population')
    checks['all_target_plans_and_formularies_assessed']+=1
    if len(matrix)!=71 or len(forms)!=26:failures.append('scope_population')
    result={'schema':'l05-condition-source-assessment/1','package_manifest_sha256':sha(package/'manifest.json'),
            'CMS_lists_complete':True,'published_condition_reference_complete':False,
            'documents_retained_and_fully_reextracted':len(docs),'full_text_is_retained':True,
            'accepted_snapshot_criterion_bindings':0,'flagged_source_contexts':dict(actual),
            'counts_meaning':'Unique source-row/fact contexts, not distinct medicines or patients. Quantity-unit needs are schema limitations, not a count of proven missing carrier documents.',
            'genuine_data_gaps':[{'fact':'Exact applicable PA/ST requirements for the pinned September formulary versions','why':'CMS flags contain no diagnoses, prerequisite treatments, trial duration, age conditions or renewal criteria. Later October documents cannot establish the September requirements by inference.','source_needed':'Applicable dated carrier Part D PA/ST criteria or dated change/version evidence. UHC/Wellcare require a permitted source route; existing access stops remain in force.'},
                                 {'fact':'Physical quantity-unit interpretation where the source amount is ambiguous','why':'CMS supplies exact numeric amount and days but no physical-unit column. Even some captured QL schedules say only a number per period.','source_needed':'Applicable explicit carrier quantity-unit statement or authoritative dispensing-unit evidence before displaying tablets/pens/mL. This does not block storing the published numeric amount and days.'}],
            'not_data_gaps':['All 71 plan mappings, all 26 formulary payloads and all 4547 exact drug names are present.','Indication table was fully acquired; zero rows match the scoped plans.','No scoped capped-benefit flag is true, so no cap-text gap is asserted.','Complete current text retained but not executable is processing work, not a missing-source claim.','Personal drug prices, pharmacy networks and individual clinical approval are outside L05.','No duplicate carrier copy is required solely to corroborate a supported CMS value.'],
            'carrier_groups':groups,'checks':dict(checks),'passed':not failures,'failure_examples':failures}
    dump(out/'documents.json',docs);dump(out/'plan-condition-matrix.json',matrix);dump(out/'assessment.json',result)
    inputs=[BASE/'condition-source-review.json',BASE/'supplemental-r1/source-manifest.json',package/'manifest.json',package/'coverage.json',package/'inventory.sqlite3',Path(__file__).resolve()]
    bound.update({str(p.relative_to(ROOT)):sha(p) for p in inputs})
    dump(out/'manifest.json',{'schema':'l05-condition-assessment-manifest/1','inputs':bound,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=assess(a.package.resolve(),a.out.resolve());print(json.dumps({k:r[k] for k in ['passed','documents_retained_and_fully_reextracted','accepted_snapshot_criterion_bindings','flagged_source_contexts','failure_examples']},indent=2));raise SystemExit(0 if r['passed'] else 1)
