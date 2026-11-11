#!/usr/bin/env python3
"""Independent row/field/page verification of the L05 condition assessment."""
import argparse
from collections import Counter,defaultdict
from contextlib import closing
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def validate(package,assessment):
    errors=[];checks=Counter()
    def check(ok,kind):
        checks[kind]+=1
        if not ok and len(errors)<100:errors.append(kind)
    manifest=read(assessment/'manifest.json')
    for name,value in manifest['inputs'].items():check(sha(ROOT/name)==value,'bound_input_hash')
    for name,value in manifest['files'].items():check(sha(assessment/name)==value,'bound_output_hash')
    report=read(assessment/'assessment.json');docs=read(assessment/'documents.json');plans=read(package/'plans.json');by_id={p['offering_id']:p for p in plans}
    review=read(assessment.parent/'condition-source-review.json');by_source={r['source_id']:r for r in review['reviews']}
    check(len(docs)==16 and {d['source_id'] for d in docs}==set(by_source),'complete_document_population')
    for d in docs:
        original=by_source[d['source_id']]
        check(all(d[k]==v for k,v in original.items()),'all_review_fields_retained')
        check(sha(ROOT/d['path'])==d['sha256'] and sha(ROOT/d['full_text_path'])==d['full_text_sha256'],'raw_PDF_and_full_text_hashes')
        pages=(ROOT/d['full_text_path']).read_text().split('\f')
        if pages and not pages[-1].strip():pages.pop()
        check(d['page_count']==len(pages)==len(d['page_locators']),'all_continuation_pages_retained')
        for i,page in enumerate(pages,1):check(d['page_locators'][i-1]=={'pdf_page':i,'text_sha256':hashlib.sha256(page.encode()).hexdigest()},'every_full_page_and_footnote_locator')
        check(d['snapshot_condition_claim_accepted'] is False,'no_unearned_historical_criterion_binding')
    matrix=read(assessment/'plan-condition-matrix.json');check(len(matrix)==71 and {r['offering_id'] for r in matrix}==set(by_id),'all_71_plans_assessed')
    with closing(sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True)) as db:
        raw={(r[0],str(r[1]),r[2]):r[3:] for r in db.execute('''SELECT g.table_name,g.ordinal,g.missing_fact,d.rxcui,d.formulary_id,d.contract_id,d.plan_id
 FROM condition_gaps g JOIN drug_rows d ON g.table_name=d.table_name AND g.ordinal=d.ordinal''')}
        observed=set();count=Counter();plan_count=defaultdict(Counter)
        with gzip.open(assessment/'condition-contexts.csv.gz','rt',newline='') as f:
            for r in csv.DictReader(f):
                key=(r['table'],r['source_row'],r['missing_CMS_detail']);check(key in raw and key not in observed,'every_condition_context_exactly_once');observed.add(key)
                if key not in raw:continue
                rx,form,contract,number=raw[key]
                check((r['rxcui'],r['formulary_id'],r['contract_id'],r['plan_id'])==(rx,form or '',contract or '',number or ''),'every_condition_identity_field')
                affected=sorted(p['offering_id'] for p in plans if (p['formulary_id']==form if r['table']=='basic' else tuple(p['offering_id'].split(':')[1:3])==(contract,number)))
                check(sorted(json.loads(r['affected_offering_ids']))==affected,'all_affected_plan_links_and_no_segment_invention')
                allowed_kind={'prior_authorization_criteria':'PA','step_therapy_criteria':'ST','physical_quantity_unit':'QL'}[key[2]]
                candidate=sorted(d['source_id'] for d in docs if d['content_kind'] in ('formulary',allowed_kind) and any(by_id[i]['formulary_id'] in d['candidate_formulary_ids'] for i in affected))
                check(json.loads(r['candidate_document_ids'])==candidate,'every_candidate_document_link')
                check(r['resolution_state']==('unit_not_asserted; numeric_amount_and_days_complete' if key[2]=='physical_quantity_unit' else 'snapshot_criterion_text_not_bound'),'every_condition_state_preserves_uncertainty')
                check(bool(r['additional_source_needed']),'missing_fact_source_route_explicit')
                count[key[2]]+=1
                for ident in affected:plan_count[ident][key[2]]+=1
        check(observed==set(raw),'no_missing_or_added_flagged_contexts')
        for r in matrix:
            p=by_id[r['offering_id']]
            check(all(r[k]==p[k] for k in ['offering_id','parent','name','formulary_id','formulary_version']),'all_plan_matrix_source_fields')
            check(all(r[fact+'_source_contexts']==n for fact,n in plan_count[p['offering_id']].items()),'every_plan_condition_count')
            check(r['candidate_document_ids']==[d['source_id'] for d in docs if p['formulary_id'] in d['candidate_formulary_ids']],'every_plan_document_matrix')
    check(report['package_manifest_sha256']==sha(package/'manifest.json') and report['flagged_source_contexts']==dict(count),'report_binding_and_condition_totals')
    check(report['accepted_snapshot_criterion_bindings']==0 and not report['published_condition_reference_complete'],'no_false_condition_completion')
    result={'schema':'l05-condition-independent-audit/1','passed':not errors,'failure_examples':errors,'checks':dict(checks),'assessment_manifest_sha256':sha(assessment/'manifest.json'),'package_manifest_sha256':sha(package/'manifest.json'),'condition_contexts_checked':len(observed),'PDF_documents_checked':len(docs),'PDF_pages_checked':checks['every_full_page_and_footnote_locator'],'plan_records_checked':len(matrix)}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',required=True,type=Path);p.add_argument('--assessment',required=True,type=Path);a=p.parse_args()
    r=validate(a.package.resolve(),a.assessment.resolve());a.assessment.with_name(a.assessment.name+'-validation.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 1)
