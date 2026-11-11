#!/usr/bin/env python3
"""Independent complete-source L05 audit; does not import builder/normalizers."""
import argparse
from collections import Counter,defaultdict
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()


def read(path):return json.loads(path.read_text())


def validate(package,output=None):
    checks,failures=Counter(),[]
    failed=0
    def check(ok,kind,detail=None):
        nonlocal failed
        checks[kind]+=1
        if not ok:
            failed+=1
            if len(failures)<100:failures.append({'check':kind,'detail':detail})
    manifest=read(package/'manifest.json')
    check(manifest.get('year')==2026 and manifest.get('schema')=='l05-build/1','package_year_and_schema')
    for group,base in [('files',package),('inputs',ROOT),('code',ROOT)]:
        for name,digest in manifest[group].items():check((base/name).is_file() and sha(base/name)==digest,'bound_'+group+'_hash',name)
    acquisition=ROOT/manifest['acquisition'];source=read(acquisition/'source-manifest.json');supplement=read(ROOT/manifest['supplemental']/'source-manifest.json')
    check(source.get('year')==2026 and not source.get('error'),'complete_2026_acquisition')
    pre=read(BASE/'planning-preflight.json')
    ma=read(ROOT/'docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json')
    pdp=read(ROOT/'docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json')
    ids={r['id'] for r in ma if r['drug']=='Yes'}|{r['offering_id'] for r in pdp}
    check(len(ids)==71 and set(pre['plan_to_formulary_ids'])==ids,'raw_upstream_target_population')
    db=sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','sqlite_integrity')
    plans=read(package/'plans.json');plan_by_id={p['offering_id']:p for p in plans}
    check(set(plan_by_id)==ids and len(plans)==71,'all_71_plan_records_present')
    db_plans={r[0]:json.loads(r[1]) for r in db.execute('SELECT offering_id,payload FROM plans')}
    check(db_plans==plan_by_id,'all_plan_json_sqlite_fields')
    old=read(ROOT/'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json')['sources']['monthly']
    gm=next(r for r in old['members'] if r['name'].startswith('geographic'))
    with zipfile.ZipFile(ROOT/gm['path']) as z:
        gn=next(n for n in z.namelist() if n.endswith('.txt'))
        geos=[r for r in csv.DictReader(io.StringIO(z.read(gn).decode('cp1252')),delimiter='|') if r['COUNTY']=='Collier' and r['STATENAME']=='Florida']
    check(len(geos)==1 and (geos[0]['COUNTY_CODE'],geos[0]['MA_REGION_CODE'],geos[0]['PDP_REGION_CODE'])==('10100','09','11'),'Collier_geography_from_raw_source')
    check(source['reused_l04_manifest_sha256']==sha(ROOT/'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json'),'pinned_acquisition_parent')
    with zipfile.ZipFile(ROOT/old['index']['synthetic_index']['path']) as z:
        central={i.filename:i for i in z.infolist()}
    for part in old['index'].values():
        if isinstance(part,dict) and 'path' in part:check(sha(ROOT/part['path'])==part['sha256'],'pinned_parent_index_hash')
    tail=source['sources']['drug_tables']['tail_recheck']
    check(sha(ROOT/tail['path'])==tail['sha256']==old['index']['tail']['sha256'],'remote_tail_matches_pinned_parent')
    ms=next(r for r in old['members'] if r['name'].startswith('plan information'))
    with zipfile.ZipFile(ROOT/ms['path']) as z:
        name=next(n for n in z.namelist() if n.endswith('.txt'));rows=list(csv.DictReader(io.StringIO(z.read(name).decode('cp1252')),delimiter='|'))
    expected_plans={}
    for ordinal,r in enumerate(rows,2):
        ident='2026:'+':'.join([r['CONTRACT_ID'],r['PLAN_ID'],r['SEGMENT_ID']])
        applies=(r['CONTRACT_ID'].startswith('H') and r['STATE']=='FL' and r['COUNTY_CODE']=='10100' or
                 r['CONTRACT_ID'].startswith('R') and r['MA_REGION_CODE']=='09' or
                 r['CONTRACT_ID'].startswith('S') and r['PDP_REGION_CODE']=='11')
        if ident in ids and applies:
            check(ident not in expected_plans,'unambiguous_plan_geography',ident);expected_plans[ident]=(ordinal,r)
    check(set(expected_plans)==ids,'all_plan_geography_joins')
    forms={r['FORMULARY_ID'] for _,r in expected_plans.values() if r['PLAN_SUPPRESSED_YN']=='N'}
    pairs={tuple(k.split(':')[1:3]) for k in expected_plans}
    for ident,(ordinal,r) in expected_plans.items():
        p=plan_by_id.get(ident)
        if not p:continue
        check(p['monthly_raw']==r and p['formulary_id']==r['FORMULARY_ID'] and p['source']['record_ordinal']==ordinal
              and p['source']['member']==name and p['source']['archive_sha256']==ms['sha256'],'every_plan_mapping_source_field',ident)
        upstream=next((m for m in ma if m['id']==ident),None)
        if upstream:
            label,parent,kind=upstream['name'],upstream['parent'],'MA-PD'
        else:
            upstream=next(m for m in pdp if m['offering_id']==ident)
            label,parent,kind=upstream['fields']['plan_name']['value'],upstream['fields']['parent_organization']['value'],'PDP'
        check((p['name'],p['parent'],p['kind'],p['suppressed'])==(label,parent,kind,r['PLAN_SUPPRESSED_YN']=='Y'),'all_upstream_plan_labels_and_states',ident)
    check(len(forms)==26,'all_26_formularies_expected')
    fieldmap=read(package/'field-map.json');db_rows={(r['table_name'],r['ordinal']):r for r in db.execute('SELECT * FROM drug_rows')}
    counts,fields_checked,national=Counter(),Counter(),Counter();versions=defaultdict(set);code_ids=set();expected_gap_rows=set();export_cells=0
    expected_sets={};table_stats={};flag_counts=defaultdict(Counter);quality={}
    for m in source['sources']['drug_tables']['members']:
        table='basic' if m['name'].startswith('basic') else 'excluded' if m['name'].startswith('excluded') else 'indication'
        member=m['inner_members'][0]
        info=central[m['name']];block=m['compressed_block'];header=m['local_header']
        check(sha(ROOT/block['path'])==block['sha256'] and sha(ROOT/header['path'])==header['sha256'],'range_receipt_hashes',table)
        raw_block=(ROOT/block['path']).read_bytes();h=struct.unpack('<4s5H3I2H',raw_block[:30]);start=30+h[-2]+h[-1]
        decoded=zlib.decompress(raw_block[start:],-15) if info.compress_type==8 else raw_block[start:]
        check(raw_block[:30]==(ROOT/header['path']).read_bytes() and raw_block[30:30+h[-2]].decode('utf-8')==info.filename
              and len(raw_block)==start+info.compress_size and len(decoded)==info.file_size
              and zlib.crc32(decoded)==info.CRC and decoded==(ROOT/m['path']).read_bytes(),'whole_selected_member_range_and_CRC',table)
        check(block['http_status']==206 and block['headers']['content-range']==f'bytes {info.header_offset}-{info.header_offset+len(raw_block)-1}/{old["archive_bytes"]}','range_offsets_and_parent_size',table)
        check(sha(ROOT/m['path'])==m['sha256'],'drug_archive_hash',table)
        with zipfile.ZipFile(ROOT/m['path']) as z:
            data=z.read(member['name'])
        check(hashlib.sha256(data).hexdigest()==member['sha256'] and len(data)==member['bytes'],'complete_uncompressed_member_hash',table)
        reader=csv.DictReader(io.StringIO(data.decode('cp1252')),delimiter='|')
        columns=reader.fieldnames
        check(set(columns)==set(fieldmap[table]) and len(columns)==len(fieldmap[table]),'every_source_column_modeled',table)
        for col in columns:
            kind='boolean' if col.endswith('_YN') else 'decimal' if col=='QUANTITY_LIMIT_AMOUNT' else 'integer' if col in ('TIER','TIER_LEVEL_VALUE','QUANTITY_LIMIT_DAYS') else 'text'
            check(fieldmap[table].get(col)=={'type':kind,'source_column':col,'flag_encoding':('0/1' if table=='excluded' and col=='QUANTITY_LIMIT_YN' else 'Y/N') if col.endswith('_YN') else None,'physical_quantity_unit_in_source':False if col=='QUANTITY_LIMIT_AMOUNT' else None},'field_map_semantics',(table,col))
        expected_set=set()
        with gzip.open(package/(table+'.csv.gz'),'rt',newline='') as stream:
            exported=csv.reader(stream);header=next(exported);check(header==['source_row']+columns,'export_headers',table)
            for ordinal,r in enumerate(reader,2):
                national[table]+=1
                if table=='basic':check(r['CONTRACT_YEAR']=='2026','national_source_year',ordinal)
                keep=r['FORMULARY_ID'] in forms if table=='basic' else (r['CONTRACT_ID'],r['PLAN_ID']) in pairs
                if not keep:continue
                counts[table]+=1;code_ids.add(r['RXCUI']);expected_set.add(ordinal)
                actual=db_rows.get((table,ordinal))
                check(actual is not None,'every_scoped_source_row_present',(table,ordinal))
                if actual is None:continue
                check(json.loads(actual['raw_json'])==r,'all_raw_source_columns_preserved',(table,ordinal))
                check(actual['rxcui']==r['RXCUI'] and actual['formulary_id']==r.get('FORMULARY_ID')
                      and actual['contract_id']==r.get('CONTRACT_ID') and actual['plan_id']==r.get('PLAN_ID')
                      and actual['ndc']==r.get('NDC'),'indexed_identity_and_grain',(table,ordinal))
                modeled=json.loads(actual['modeled_json']);check(set(modeled)==set(columns),'no_modeled_field_omission',(table,ordinal))
                for col,value in r.items():
                    state='absent' if value is None else 'empty' if value=='' else 'blank_space' if value.isspace() else 'reported'
                    kind='boolean' if col.endswith('_YN') else 'decimal' if col=='QUANTITY_LIMIT_AMOUNT' else 'integer' if col in ('TIER','TIER_LEVEL_VALUE','QUANTITY_LIMIT_DAYS') else 'text'
                    expected=None
                    if state=='reported':
                        if kind=='boolean':
                            codes={'0':False,'1':True} if table=='excluded' and col=='QUANTITY_LIMIT_YN' else {'N':False,'Y':True}
                            check(value in codes,'documented_flag_encoding',(table,ordinal,col));expected=codes.get(value)
                            if expected is True:flag_counts[table][col]+=1
                        elif kind=='integer':expected=int(Decimal(value));check(Decimal(value)==expected and expected>=0,'integer_semantics',(table,ordinal,col))
                        elif kind=='decimal':expected=str(Decimal(value));check(Decimal(value).is_finite() and Decimal(value)>=0,'quantity_decimal_semantics',(table,ordinal))
                        else:expected=value
                    check(modeled.get(col)=={'raw':value,'state':state,'type':kind,'value':expected},'every_modeled_source_field',(table,ordinal,col));fields_checked[table]+=1
                got=next(exported,None);check(got==[str(ordinal)]+[r[c] for c in columns],'all_exported_source_cells',(table,ordinal));export_cells+=len(columns)+1
                if table=='basic':versions[r['FORMULARY_ID']].add(r['FORMULARY_VERSION'])
                for col,fact,need in [('PRIOR_AUTHORIZATION_YN','prior_authorization_criteria','Exact applicable 2026 Part D carrier PA criteria'),('PRIOR_AUTH_YN','prior_authorization_criteria','Exact applicable 2026 Part D carrier PA criteria'),('STEP_THERAPY_YN','step_therapy_criteria','Exact applicable 2026 Part D carrier ST criteria'),('QUANTITY_LIMIT_YN','physical_quantity_unit','Exact applicable carrier quantity-unit statement; no inference from proxy NDC'),('CAPPED_BENEFIT_YN','supplemental_cap_qualification','Exact applicable published cap qualification')]:
                    if col in r and r[col] in ('Y','1'):expected_gap_rows.add((table,ordinal,fact,need))
            check(next(exported,None) is None,'no_extra_export_rows',table)
        expected_sets[table]=expected_set
        check({o for t,o in db_rows if t==table}==expected_set,'two_way_raw_row_set_reconciliation',table)
        table_stats[table]={'national_rows':national[table],'scoped_rows':counts[table],'outside_scope_rows':national[table]-counts[table],'quarantined_rows':0,'all_source_columns_modeled':columns,'modeled_field_observations':fields_checked[table]}
        keys='formulary_id,rxcui,ndc' if table=='basic' else 'contract_id,plan_id,rxcui'+(',json_extract(raw_json,\'$.DISEASE\')' if table=='indication' else '')
        duplicates=db.execute(f'SELECT count(*) FROM (SELECT {keys},count(*) c FROM drug_rows WHERE table_name=? GROUP BY {keys} HAVING c>1)',(table,)).fetchone()[0]
        absent_limits=db.execute("SELECT count(*) FROM drug_rows WHERE table_name=? AND json_extract(modeled_json,'$.QUANTITY_LIMIT_YN.value')=1 AND (json_extract(modeled_json,'$.QUANTITY_LIMIT_AMOUNT.value') IS NULL OR json_extract(modeled_json,'$.QUANTITY_LIMIT_DAYS.value') IS NULL)",(table,)).fetchone()[0]
        wrong_identifier=sum(1 for (t,_),r in db_rows.items() if t==table and (not r['rxcui'].isdigit() or table=='basic' and (len(r['ndc'])!=11 or not r['ndc'].isdigit())))
        quality[table]={'duplicate_natural_keys':duplicates,'flagged_QL_missing_amount_or_days':absent_limits,'invalid_exact_identifier_formats':wrong_identifier}
        check(duplicates==0 and absent_limits==0 and wrong_identifier==0,'whole_population_source_quality',table)
        stats=read(package/'source-row-accounting.json')[table]
        check(stats=={'rows':national[table],'columns':columns,'encoding':'cp1252','inner_member':member['name'],'outer_member':Path(m['path']).name,'uncompressed_sha256':hashlib.sha256(data).hexdigest(),'non_ascii_bytes':dict(Counter(b for b in data if b>127))},'all_parser_accounting_fields',table)
        check(read(package/'source-members.json')[table]=={'outer':m,'inner':member},'source_member_projection',table)
    check(set(versions)==forms and all(len(v)==1 for v in versions.values()),'all_expected_formulary_versions_present')
    for ident,p in plan_by_id.items():
        check(p['formulary_version'] in versions[p['formulary_id']],'plan_formulary_version_exact',ident)
        expected_basic=sum(1 for (t,o),r in db_rows.items() if t=='basic' and r['formulary_id']==p['formulary_id'])
        check(p['basic_rows']==expected_basic and expected_basic>0,'plan_basic_inventory_complete',ident)
        for table in ['excluded','indication']:
            pair=tuple(ident.split(':')[1:3]);expected=sum(1 for (t,o),r in db_rows.items() if t==table and (r['contract_id'],r['plan_id'])==pair)
            check(p[table+'_rows']==expected,'supplemental_plan_grain_preserved',(ident,table))
    # Drug name/identity fields independently re-read from their exact sources.
    frf=source['sources']['drug_identity_reference']
    with zipfile.ZipFile(ROOT/frf['path']) as z:
        frf_name=next(n for n in z.namelist() if n.endswith('.csv'));frf_rows=list(csv.DictReader(io.StringIO(z.read(frf_name).decode('cp1252'))))
    frf_index={r['RxCUI']:(i,r) for i,r in enumerate(frf_rows,2)}
    identities=read(package/'identities.json');by_rx={r['rxcui']:r for r in identities}
    check(set(by_rx)==code_ids and len(by_rx)==len(identities),'every_scoped_drug_has_exact_identity_evidence')
    check({r[0]:json.loads(r[1]) for r in db.execute('SELECT * FROM drug_identities')}==by_rx,'all_identity_json_sqlite_fields')
    for code,got in by_rx.items():
        if code in frf_index:
            ordinal,r=frf_index[code]
            expected={'rxcui':code,'name':r['RxNorm Description'],'type':r['TTY'],'ingredient_strength_description':r['Related SCDC'],
                      'dose_form':r['Related DF'],'related_brand':r['Related BN'],'raw':r,
                      'source':{'kind':'CMS_2026_FRF','archive_path':frf['path'],'archive_sha256':frf['sha256'],'member':frf_name,'record_ordinal':ordinal},'coverage_inferred':False}
        else:
            s=supplement['sources']['rxnorm-history-'+code];body=read(ROOT/s['path'])['rxcuiStatusHistory'];a=body['attributes']
            expected={'rxcui':code,'name':a['name'],'type':a.get('tty'),'definitional_features':body.get('definitionalFeatures',{}),'history':body['metaData'],
                      'raw':body,'source':{'kind':'NLM_RxNorm_history','path':s['path'],'sha256':s['sha256'],'url':s['requested_url'],'retrieved_at_utc':s['retrieved_at_utc']},'coverage_inferred':False}
            check(a['rxcui']==code,'history_original_code_not_substituted',code)
        check(got==expected,'every_identity_field_against_source',code)
    gap_rows={tuple(r) for r in db.execute('SELECT * FROM condition_gaps')};check(gap_rows==expected_gap_rows,'all_flagged_condition_details_explicit')
    with (package/'condition-gaps.csv').open(newline='') as f:
        rows=list(csv.reader(f));check({(r[0],int(r[1]),r[2],r[3]) for r in rows[1:]}==expected_gap_rows and len(rows)-1==len(expected_gap_rows),'condition_gap_export_complete')
    with (package/'plans.csv').open(newline='') as f:
        r=list(csv.reader(f));check(r[1:]==[[str(p[k]) for k in ['offering_id','name','kind','formulary_id','formulary_version','basic_rows','excluded_rows','indication_rows']] for p in plans],'all_plan_export_cells')
    pbp=ROOT/'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw/65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3'
    with gzip.open(package/'benefit-context.jsonl.gz','rt') as f:contexts=[json.loads(l) for l in f]
    check({r['offering_id'] for r in contexts}==ids and len(contexts)==71,'all_existing_benefit_context_reused')
    with zipfile.ZipFile(pbp) as z:
        for context in contexts:
            original=json.loads(z.read(context['member']))['pbp'][0].get('rx')
            check(context['rx']==original and context['pointer']=='/pbp/0/rx','all_reused_PBP_Rx_fields_preserved',context['offering_id'])
            row=db.execute('SELECT payload FROM benefit_context WHERE offering_id=?',(context['offering_id'],)).fetchone();check(row is not None and json.loads(row[0])==context,'benefit_context_sqlite_projection',context['offering_id'])
    coverage=read(package/'coverage.json')
    check((coverage['year'],coverage['county_fips'],coverage['pdp_region'],coverage['source_period'],coverage['evidence_cutoff'])==(2026,'12021','11','2026-09','2026-10-25'),'exact_published_reference_scope')
    check(coverage['source_row_accounting']==table_stats,'complete_source_row_and_field_accounting')
    check(coverage['scoped_rows']=={t:counts[t] for t in ['basic','excluded','indication']} and coverage['source_fields_checked']=={t:fields_checked[t] for t in ['basic','excluded','indication']},'coverage_scoped_counts')
    check(coverage['formulary_versions']=={f:sorted(v) for f,v in sorted(versions.items())},'coverage_version_matrix')
    check(coverage['flag_counts']=={t:dict(c) for t,c in flag_counts.items()},'coverage_all_restriction_flag_counts')
    check(coverage['condition_details_not_supplied_by_CMS_tables']==dict(Counter(r[2] for r in expected_gap_rows)),'CMS_payload_detail_needs_not_claimed_as_missing_documents')
    check(coverage['plan_drug_relationships']==sum(p['basic_rows']+p['excluded_rows']+p['indication_rows'] for p in plans),'coverage_all_plan_drug_relationships')
    check(coverage['target_plans']==71 and coverage['formulary_ids']==26 and coverage['distinct_drug_identifiers']==len(code_ids),'coverage_identity_counts')
    check(not coverage['consumer_release_enabled'] and coverage['human_acceptance'] is None and not coverage['full_published_condition_reference_complete'],'no_unearned_condition_or_consumer_acceptance')
    before=read(BASE/'preservation-before.json')['files'];check(all((ROOT/n).is_file() and sha(ROOT/n)==v for n,v in before.items()),'protected_upstream_and_runtime_files_unchanged')
    db.close()
    result={'schema':'l05-independent-validation/1','manifest_sha256':sha(package/'manifest.json'),'passed':failed==0,'failed':failed,'failure_examples':failures,
            'checks':dict(checks),'national_rows_accounted':dict(national),'scoped_rows_checked':{t:counts[t] for t in ['basic','excluded','indication']},'modeled_source_fields_checked':{t:fields_checked[t] for t in ['basic','excluded','indication']},
            'drug_identity_records_checked':len(identities),'export_cells_checked':export_cells,'target_plans_checked':len(ids),'formulary_ids_checked':len(forms),
            'condition_detail_gaps_explicit':len(expected_gap_rows),'protected_files_checked':len(before),'independent_human_acceptance':False}
    result['source_quality']=quality
    if output:output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args()
    r=validate(a.package.resolve(),a.out or a.package.parent/(a.package.name+'-validation.json'))
    print(json.dumps({k:r[k] for k in ['passed','failed','target_plans_checked','formulary_ids_checked','scoped_rows_checked','modeled_source_fields_checked','drug_identity_records_checked']},indent=2));raise SystemExit(0 if r['passed'] else 1)
