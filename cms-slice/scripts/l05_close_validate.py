#!/usr/bin/env python3
"""Independent complete-field L05 closeout audit; does not import the builder."""
import argparse
import base64
from collections import Counter,defaultdict
from contextlib import closing
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import unicodedata
import zipfile

from l05_close_aliases import alias_key

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25'
CLOSE=BASE/'closeout-r1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]


def validate(package):
    checks=Counter();errors=[];failed=0
    def check(ok,name):
        nonlocal failed
        checks[name]+=1
        if not ok:
            failed+=1
            if len(errors)<100:errors.append(name)
    m=read(package/'manifest.json')
    for group,root in [('files',package),('inputs',ROOT),('code',ROOT)]:
        for name,value in m[group].items():check((root/name).exists() and sha(root/name)==value,'all_bound_'+group)
    plans=read(package/'plans.json');base_plans=read(BASE/'build-r3/plans.json');by_id={p['offering_id']:p for p in base_plans};docs={d['id']:d for d in read(package/'documents.json')}
    check(len(plans)==71 and {p['offering_id'] for p in plans}==set(by_id),'complete_71_plan_denominator')
    raw_sources=read(BASE/'supplemental-r1/source-manifest.json')['sources']|read(CLOSE/'acquisition/source-manifest.json')['sources']
    full_text={}
    for ident,d in docs.items():
        text=(ROOT/d['full_text_path']).read_text();full_text[ident]=text
        reextract=subprocess.run(['pdftotext','-layout',str(ROOT/d['path']),'-'],check=True,capture_output=True).stdout
        check(hashlib.sha256(reextract).hexdigest()==d['full_text_sha256'],'every_complete_PDF_text_reextracted')
        pages=text.split('\f')
        if not pages[-1].strip():pages.pop()
        check(d['page_count']==len(pages) and d['page_sha256']==[hashlib.sha256(p.encode()).hexdigest() for p in pages],'every_page_and_footnote_preserved')
        check(not d['historical_snapshot_asserted'] and not d['personal_approval_inferred'],'no_unearned_date_or_personal_inference')
        check(set(d['scope_offering_ids'])<=set(by_id),'document_scopes_only_known_target_plans')
        header=text[:2500];date=re.search(r'(?:Effective|Last Updated:?)\s*(\d{1,2})/(\d{1,2})/(2026)',header,re.I) or re.search(r'updated on\s*(\d{1,2})/(\d{1,2})/(2026)',header,re.I)
        expected_date=f'{date[3]}-{int(date[1]):02}-{int(date[2]):02}' if date else None
        check(d['declared_date']==expected_date,'every_declared_date_against_full_source_header')
        if ident in raw_sources:
            source=raw_sources[ident]
            check(d['source_url']==source['requested_url'] and d['source_delivery_path']==source['path'] and d['source_delivery_sha256']==source['sha256'],'every_document_delivery_locator')
        if d['archive_timestamp']:
            source=raw_sources[ident];expected=source.get('archive_digest')
            if expected is None:
                index=read(ROOT/raw_sources['archive-humana-plus5-PA-september-index']['path']);expected=next(r[2] for r in index[1:] if r[0]==d['archive_timestamp'])
            check(base64.b32encode(hashlib.sha1((ROOT/d['source_delivery_path']).read_bytes()).digest()).decode().rstrip('=')==expected,'archive_payload_matches_independent_CDX_digest')
        if d['full_criteria'] and d['family']=='Humana':
            match=re.search(r'Formulary ID\s*0*(\d{5})\s+Version\s+(\d+)',text[:2500],re.I)
            check(match is not None and d['formulary_id']==match[1].zfill(8) and d['formulary_version']==match[2],'every_Humana_family_identity_against_cover')
            expected={p['offering_id'] for p in base_plans if p['parent']=='Humana Inc.' and p['formulary_id']==d['formulary_id']}
            check(set(d['scope_offering_ids'])==expected,'exact_Humana_plan_formulary_links')
        if d['full_criteria'] and d['family']=='HealthSpring':check(set(d['scope_offering_ids'])=={p['offering_id'] for p in base_plans if p['parent']=='Health Care Service Corporation'},'all_HealthSpring_plan_document_links')
        if d['full_criteria'] and d['family'] in ['Freedom','Optimum']:check(set(d['scope_offering_ids'])=={p['offering_id'] for p in base_plans if p['offering_id'].split(':')[1]==('H5427' if d['family']=='Freedom' else 'H5594')},'all_brand_specific_plan_document_links')
        if d['kind']=='PA_questionnaire':check(not d['full_criteria'] and bool(re.search(r'PRESCRIBER\s+FAX\s+FORM',text[:2500],re.I)),'questionnaires_never_promoted_to_complete_rules')
        if d['kind']=='out_of_scope_Illinois_FIDE_candidate':check(not d['scope_offering_ids'] and not d['full_criteria'] and 'FIDE' in text[:500],'out_of_scope_Aetna_candidate_rejected')
    sections=lines(package/'criteria-sections.jsonl.gz');by_section={s['section_id']:s for s in sections}
    check(len(by_section)==len(sections),'no_lost_or_overwritten_criterion_sections')
    for s in sections:
        pages=full_text[s['document_id']].split('\f');p=s['pdf_page_start'];end=s['pdf_page_end'];start=s['page_char_start'];offset=s['page_char_end']
        raw=pages[p-1][start:offset] if p==end else '\f'.join([pages[p-1][start:]]+pages[p:end-1]+[pages[end-1][:offset]])
        raw=re.split(r'\f\s*(?:INDEX|Index)\b',raw)[0]
        check(s['full_text']==raw and s['text_sha256']==hashlib.sha256(raw.encode()).hexdigest(),'every_full_criterion_source_range')
        clean=[]
        for line in raw.splitlines():
            if re.match(r'^\s*(?:Y0040_|Y0114_|\d{7}MUMENMUB|\d+\s*$)',line):continue
            if re.match(r'^\s*(?:2026 (?:FREEDOM|OPTIMUM) (?:Prior Authorization|Step Therapy) Criteria|EFFECTIVE DATE\s+\d)',line):continue
            clean.append(line)
        expected_text=' '.join(' '.join(clean).split())
        check(s['comparison_text']==expected_text and s['comparison_sha256']==hashlib.sha256(expected_text.encode()).hexdigest(),'comparison_fingerprint_from_complete_source_text')
    comparisons=lines(package/'criteria-comparisons.jsonl.gz')
    for c in comparisons:
        a=[by_section[k] for k in c['before_section_ids']];b=[by_section[k] for k in c['after_section_ids']]
        state='ambiguous_duplicate_heading' if len(a)>1 or len(b)>1 else 'same_published_text_at_both_observations' if a and b and a[0]['comparison_sha256']==b[0]['comparison_sha256'] else 'published_text_changed' if a and b else 'only_in_earlier_capture' if a else 'only_in_later_capture'
        check(c['comparison_state']==state and not c['September_continuity_inferred'],'all_before_after_states_no_backdating')
    case_links=lines(package/'condition-reference-links.jsonl.gz');case_index={(r['table'],r['source_row'],r['fact']):r for r in case_links}
    with closing(sqlite3.connect('file:'+str(BASE/'build-r3/inventory.sqlite3')+'?mode=ro',uri=True)) as db:
        expected_cases={(r[0],r[1],r[2]):r[3:] for r in db.execute('''SELECT g.table_name,g.ordinal,g.missing_fact,d.rxcui,d.formulary_id,d.contract_id,d.plan_id FROM condition_gaps g JOIN drug_rows d ON g.table_name=d.table_name AND g.ordinal=d.ordinal WHERE g.missing_fact IN ('prior_authorization_criteria','step_therapy_criteria')''')}
    check(set(case_index)==set(expected_cases) and len(case_index)==len(case_links)==24518,'all_24518_PA_ST_source_contexts_retained')
    plan_index={p['offering_id']:p for p in plans};identity_index={r['rxcui']:r for r in read(BASE/'build-r3/identities.json')};heading_index=defaultdict(lambda:defaultdict(list))
    def normalized_name(x):return ' '.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKC',x).lower()))
    for block in sections:heading_index[block['document_id']][normalized_name(block['title'].split(' - ',1)[0])].append(block['section_id'])
    for key,r in case_index.items():
        code,form,contract,number=expected_cases[key];kind='PA' if key[2]=='prior_authorization_criteria' else 'ST'
        expected_ids={p['offering_id'] for p in base_plans if (p['formulary_id']==form if key[0]=='basic' else tuple(p['offering_id'].split(':')[1:3])==(contract,number))}
        check(r['rxcui']==code and r['formulary_id']==form and r['kind']==kind and {p['offering_id'] for p in r['plan_links']}==expected_ids,'every_restriction_identity_kind_and_affected_plan')
        for link in r['plan_links']:
            p=plan_index[link['offering_id']];check(link['current_full_document_ids']==p['current_dated_criteria'][kind] and link['earlier_full_document_ids']==p['earlier_dated_criteria'][kind] and not link['September_continuity_asserted'] and not link['personal_approval'],'every_row_specific_full_text_reference_and_uncertainty')
            check(all(sid in by_section and by_section[sid]['document_id'] in link['current_full_document_ids']+link['earlier_full_document_ids'] for sid in link['named_section_locator_candidates']),'all_named_locators_within_applicable_documents')
            identity=identity_index[code];names={normalized_name(identity.get('related_brand','')),normalized_name(re.split(r'\d',identity.get('ingredient_strength_description',''),1)[0].strip())}-{''}
            expected_named=sorted({sid for d in link['current_full_document_ids']+link['earlier_full_document_ids'] for name in names for sid in heading_index[d].get(name,[])})
            expected_questions=[d for d in p['prescriber_questionnaires'] if any(normalized_name(label) in names for label in docs[d]['printed_product_labels'])]
            check(link['named_section_locator_candidates']==expected_named and link['matching_questionnaire_ids']==expected_questions,'every_named_heading_and_questionnaire_product_locator')
    statements={s['statement_id']:s for s in read(package/'quantity-statements.json')};evidence=read(package/'quantity-query-evidence.json');mapping=read(package/'quantity-code-mapping.json');units=lines(package/'quantity-units.jsonl.gz')
    # Re-read the exact public NLM/FDA rows. Alias canonicalization is a shared
    # declared vocabulary contract; source fields and global ambiguity are checked here.
    bulk=read(CLOSE/'bulk-acquisition/source-manifest.json');archive=ROOT/bulk['path'];check(hashlib.md5(archive.read_bytes()).hexdigest()==bulk['published_md5'],'NLM_published_full_archive_checksum')
    alias_queries=[v for v in evidence.values() if v.get('kind')=='NLM_public_RRF_alias'];wanted_keys={v['alias_evidence']['normalization_key'] for v in alias_queries};global_codes=defaultdict(set);needed_ordinals={r['record_ordinal'] for v in alias_queries for r in v['alias_evidence']['matched_alias_rows']};rrf_rows={};product_types=set()
    with zipfile.ZipFile(archive) as z:
        with z.open('rrf/RXNCONSO.RRF') as f:
            for raw in f:
                r=raw.decode().rstrip('\r\n').split('|')
                if r[11]=='RXNORM' and r[12] in ['SCD','SBD','GPCK','BPCK'] and r[16]=='N':product_types.add(r[0])
        with z.open('rrf/RXNCONSO.RRF') as f:
            for ordinal,raw in enumerate(f,1):
                r=raw.decode().rstrip('\r\n').split('|')
                if ordinal in needed_ordinals:rrf_rows[ordinal]=r
                if r[0] in product_types and r[1]=='ENG' and r[11] in ['RXNORM','MTHSPL'] and r[16]=='N':
                    for k in {alias_key(r[14]),alias_key(r[14],True)}&wanted_keys:global_codes[k].add(r[0])
    for sid,s in statements.items():
        pages=full_text[s['source_id']].split('\f');page=pages[s['pdf_page']-1].splitlines();check(s['raw_lines']==page[s['line_start']-1:s['line_end']],'all_quantity_statement_source_lines')
        header=next(l for l in page if re.search(r'Drug\s+name',l,re.I) and re.search(r'Drug\s+tier',l,re.I) and 'Requirements' in l)
        tier_at=re.search(r'Drug\s+tier',header,re.I).start();req_at=header.index('Requirements')
        label=[];limit=[]
        for i,line in enumerate(s['raw_lines']):
            cells=re.fullmatch(r'\s*(.+?)\s{2,}([1-6])(?:\s{2,}(.*)|\s*)',line)
            if i==0:
                label.append(cells[1].strip() if cells else line[:tier_at].strip());limit.append((cells[3] or '') if cells else line[req_at:].strip())
            else:
                left=line[:tier_at].strip()
                if left and (re.search(r'\d',left) or re.match(r'^(?:ml\b|release|extended|delayed|hydrochloride|sodium|capsule|tablet|suspension|solution|inhalation|inject|oral|acetate|powder)\b',left,re.I)) and not re.search(r'Updated|You can find|Note:|2026 B2|^page\b|\bFormulary\b',left,re.I):label.append(left);limit.append(line[req_at:].strip())
                elif not left and line[req_at:].strip():limit.append(line[req_at:].strip())
        check(s['product_label']==' '.join(label) and ' '.join(s['limit_text'].split())==' '.join(' '.join(limit).split()),'all_product_labels_and_limit_text_against_source_columns')
        match=re.findall(r'QL\s*\(\s*(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z .-]*?)\s*(?:/|per)\s*(\d+)\s+days?\s*\)',s['limit_text'],re.I)
        check(len(match)==1 and match[0]==(s['amount'],s['unit_raw'],str(s['days'])),'all_quantity_numbers_and_raw_units_against_statement')
        unit_codes={'mls':'mL','ml':'mL','ea':'each','gm':'g','gms':'g','grams':'g','tablets':'tablets','capsules':'capsules','patches':'patches','units':'units','syringes':'syringes','pens':'pens','vials':'vials','inhalers':'inhalers','packets':'packets','doses':'doses'}
        check(s['unit']==unit_codes[s['unit_raw'].lower()] and all(re.search(r'\b0*'+str(int(fid))+r'\b',full_text[s['source_id']][:2500]) for fid in s['formulary_ids']),'all_unit_codes_and_declared_formulary_scopes')
        for code,qid in mapping[sid].items():
            source=evidence[qid]
            if source.get('kind')=='NLM_public_RRF_alias':
                a=source['alias_evidence'];check(global_codes[a['normalization_key']]=={code} and a['rxcui']==code,'globally_unique_public_RRF_drug_identity')
                check(a['normalization_key']==alias_key(source['query_name'],bool(re.search(r'\binjection\b',source['query_name'],re.I)) and not re.search(r'auto|pen|syringe',source['query_name'],re.I)) and source['query_name'] in s['query_products'],'controlled_alias_query_not_approximate')
                for alias in a['matched_alias_rows']:
                    r=rrf_rows[alias['record_ordinal']]
                    check(alias=={'rxcui':r[0],'record_ordinal':alias['record_ordinal'],'RXAUI':r[7],'SAB':r[11],'TTY':r[12],'name':r[14],'raw_fields':r} and r[0]==code and a['normalization_key'] in [alias_key(r[14]),alias_key(r[14],True)],'every_public_NLM_alias_field_from_raw_RRF')
            else:
                body=read(ROOT/source['path']);check(body.get('idGroup',{}).get('rxnormId')==[code] and source['query_name'] in s['query_products'],'every_unique_NLM_identity_binding')
    with closing(sqlite3.connect('file:'+str(BASE/'build-r3/inventory.sqlite3')+'?mode=ro',uri=True)) as db:
        expected={(r[0],r[1]):json.loads(r[2]) for r in db.execute('SELECT table_name,ordinal,raw_json FROM drug_rows WHERE json_extract(modeled_json,\'$.QUANTITY_LIMIT_YN.value\')=1')}
    check(len(units)==len(expected)==37675 and {(r['table'],r['source_row']) for r in units}==set(expected),'all_37675_quantity_contexts_retained')
    unit_index=defaultdict(list);other_index=defaultdict(dict);unit_forms=set()
    for sid,s in statements.items():
        for form in s['formulary_ids']:
            unit_forms.add(form)
            for code,qid in mapping[sid].items():unit_index[(form,code,Decimal(s['amount']),s['days'])].append((s,qid));other_index[(form,code)][sid]=(s,qid)
    for u in units:
        r=expected[(u['table'],u['source_row'])]
        check((u['rxcui'],u['formulary_id'],u['quantity_amount_raw'],u['quantity_days_raw'])==(r['RXCUI'],r.get('FORMULARY_ID'),r['QUANTITY_LIMIT_AMOUNT'],r['QUANTITY_LIMIT_DAYS']),'every_CMS_quantity_identity_and_value')
        values=set()
        exact=unit_index[(u['formulary_id'],u['rxcui'],Decimal(u['quantity_amount_raw']),int(u['quantity_days_raw']))] if u['table']=='basic' else []
        expected_links=[{'statement_id':s['statement_id'],'source_id':s['source_id'],'NLM_query_source_id':q,'document_date':docs[s['source_id']]['declared_date']} for s,q in exact]
        check(u['evidence']==expected_links,'no_missing_or_added_exact_unit_bindings')
        for link in u['evidence']:
            s=statements[link['statement_id']];values.add(s['unit'])
            check(u['table']=='basic' and u['formulary_id'] in s['formulary_ids'] and u['rxcui'] in mapping[s['statement_id']] and mapping[s['statement_id']][u['rxcui']]==link['NLM_query_source_id'] and Decimal(u['quantity_amount_raw'])==Decimal(s['amount']) and int(u['quantity_days_raw'])==s['days'] and link['source_id']==s['source_id'] and link['document_date']==docs[s['source_id']]['declared_date'],'every_quantity_unit_source_field_and_join')
        state='explicit_carrier_unit_matched' if len(values)==1 else 'conflicting_carrier_units' if len(values)>1 else 'unit_not_bound_to_exact_CMS_row'
        check(u['state']==state and u['unit']==(next(iter(values)) if len(values)==1 else None),'every_quantity_unit_state_and_no_guessing')
        other=[{'statement_id':s['statement_id'],'source_id':s['source_id'],'amount':s['amount'],'unit':s['unit'],'days':s['days'],'NLM_query_source_id':q,'document_date':docs[s['source_id']]['declared_date']} for s,q in other_index[(u['formulary_id'],u['rxcui'])].values() if Decimal(s['amount'])!=Decimal(u['quantity_amount_raw']) or s['days']!=int(u['quantity_days_raw'])]
        reason=None if len(values)==1 else 'explicit_units_conflict' if len(values)>1 else 'no_applicable_explicit_unit_document_held' if u['formulary_id'] not in unit_forms else 'carrier_publishes_different_number_or_period; conversion_or_date_reconciliation_required' if other else 'printed_product_not_uniquely_linked_or_not_in_held_edition; retained_text_is_not_missing_data'
        check(u['other_dated_carrier_limits']==other and u['unresolved_reason']==reason,'all_different_limits_and_real_gap_reasons_preserved')
    for p in plans:
        base=by_id[p['offering_id']];check(all(p[k]==base[k] for k in ['offering_id','name','parent','formulary_id','formulary_version']),'every_plan_source_field')
        for label,archived in [('current_dated_criteria',False),('earlier_dated_criteria',True)]:
            for kind in ['PA','ST']:
                expected_docs=[d['id'] for d in docs.values() if d['full_criteria'] and bool(d['archive_timestamp'])==archived and d['kind']==kind and p['offering_id'] in d['scope_offering_ids']]
                check(p[label][kind]==expected_docs,'every_plan_kind_date_document_link')
        questions=[d['id'] for d in docs.values() if d['kind']=='PA_questionnaire' and p['offering_id'] in d['scope_offering_ids']]
        expected_state='full_dated_documents_available' if p['current_dated_criteria']['PA'] and p['current_dated_criteria']['ST'] else 'questionnaires_available_complete_approval_rules_not_established' if questions else 'source_access_STOP' if p['parent'] in ['UnitedHealth Group, Inc.','Centene Corporation'] else 'applicable_complete_criteria_not_located'
        check(p['prescriber_questionnaires']==questions and p['condition_source_state']==expected_state and p['CMS_snapshot_backdating_assumed'] is False and p['clinical_approval'] is False,'every_plan_source_state_and_no_false_completion')
        check(p['QL_rows_with_carrier_unit']==sum(u['formulary_id']==p['formulary_id'] and u['state']=='explicit_carrier_unit_matched' for u in units),'every_plan_unit_count')
    coverage=read(package/'coverage.json');check(coverage['quantity_states']==dict(Counter(u['state'] for u in units)) and coverage['criteria_comparison_states']==dict(Counter(c['comparison_state'] for c in comparisons)) and coverage['criteria_sections']==len(sections),'all_output_totals_from_actual_records')
    check(coverage['unresolved_unit_reasons']==dict(Counter(u['unresolved_reason'] for u in units if u['unresolved_reason'])) and not coverage['full_L05_condition_reference_complete'] and not coverage['consumer_release_enabled'],'all_gap_totals_and_release_boundaries')
    check(coverage['target_plans']==len(plans) and coverage['documents']==len(docs) and coverage['PDF_pages_retained']==sum(d['page_count'] for d in docs.values()) and coverage['quantity_rows_accounted']==len(units) and coverage['explicit_unit_statements_retained']==len(statements) and coverage['full_criteria_current_documents']==sum(d['full_criteria'] and not d['archive_timestamp'] for d in docs.values()) and coverage['full_criteria_earlier_documents']==sum(d['full_criteria'] and bool(d['archive_timestamp']) for d in docs.values()) and coverage['plan_source_states']==dict(Counter(p['condition_source_state'] for p in plans)),'all_document_plan_and_evidence_population_totals')
    check(coverage['PA_ST_source_contexts_accounted']==len(case_links) and coverage['PA_ST_plan_reference_links']==sum(len(r['plan_links']) for r in case_links),'all_restriction_reference_link_totals')
    before=read(CLOSE/'preservation-before.json')['files'];changed=[n for n,v in before.items() if not (ROOT/n).exists() or sha(ROOT/n)!=v];check(not changed,'all_previous_sources_code_and_selected_artifacts_preserved')
    return {'schema':'l05-closeout-independent-validation/1','manifest_sha256':sha(package/'manifest.json'),'passed':failed==0,'failed':failed,'failure_examples':errors,'checks':dict(checks),'plans_checked':len(plans),'documents_checked':len(docs),'criterion_sections_checked':len(sections),'PA_ST_source_contexts_checked':len(case_links),'quantity_contexts_checked':len(units),'carrier_unit_rows':sum(u['state']=='explicit_carrier_unit_matched' for u in units),'preserved_files_checked':len(before),'preservation_mismatches':changed}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);a=p.parse_args();r=validate(a.package.resolve());a.package.with_name(a.package.name+'-validation.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 1)
