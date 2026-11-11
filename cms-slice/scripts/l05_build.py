#!/usr/bin/env python3
"""Offline L05 build: reuse 2026 plan/benefit data and capture all drug fields."""
import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from prescription import raw_state, source_rows, market_plan

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l05-drug-coverage-2026-10-25'
L04 = ROOT / 'docs/data/l04-pdp-availability-2026-10-25'
L02 = ROOT / 'docs/data/l02-ma-availability-2026-10-25'
FIELDS = {
 'basic': ['FORMULARY_ID','FORMULARY_VERSION','CONTRACT_YEAR','RXCUI','NDC','TIER_LEVEL_VALUE','QUANTITY_LIMIT_YN','QUANTITY_LIMIT_AMOUNT','QUANTITY_LIMIT_DAYS','PRIOR_AUTHORIZATION_YN','STEP_THERAPY_YN','SELECTED_DRUG_YN'],
 'excluded': ['CONTRACT_ID','PLAN_ID','RXCUI','TIER','QUANTITY_LIMIT_YN','QUANTITY_LIMIT_AMOUNT','QUANTITY_LIMIT_DAYS','PRIOR_AUTH_YN','STEP_THERAPY_YN','CAPPED_BENEFIT_YN'],
 'indication': ['CONTRACT_ID','PLAN_ID','RXCUI','DISEASE']}


def read(p):
    return json.loads(p.read_text())


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while b := f.read(4*1024*1024):
            h.update(b)
    return h.hexdigest()


def dump(p, value):
    p.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'))


def normalized(table, field, value):
    state = raw_state(value)
    kind = 'boolean' if field.endswith('_YN') else 'decimal' if field == 'QUANTITY_LIMIT_AMOUNT' else 'integer' if field in ('TIER','TIER_LEVEL_VALUE','QUANTITY_LIMIT_DAYS') else 'text'
    result = {'raw':value, 'state':state, 'type':kind, 'value':None}
    if state != 'reported':
        return result
    if kind == 'boolean':
        codes = {'0':False,'1':True} if table == 'excluded' and field == 'QUANTITY_LIMIT_YN' else {'Y':True,'N':False}
        if value not in codes:
            return {**result,'state':'unresolved_code'}
        result['value'] = codes[value]
    elif kind in ('integer','decimal'):
        try:
            number = Decimal(value)
            if not number.is_finite() or number < 0 or kind == 'integer' and number != int(number):
                raise InvalidOperation
            result['value'] = int(number) if kind == 'integer' else str(number)
        except (InvalidOperation, ValueError):
            return {**result,'state':'invalid_numeric'}
    else:
        result['value'] = value
    return result


def extract_zip_member(path, predicate):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if predicate(n)]
        if len(names) != 1:
            raise ValueError('Missing/ambiguous member: ' + str(path))
        return names[0], z.read(names[0])


def build(acquisition, supplemental, out):
    if out.exists():
        raise ValueError('Immutable output already exists')
    pre = read(BASE/'planning-preflight.json')
    for name, value in pre['inputs'].items():
        if digest(ROOT/name) != value:
            raise ValueError('Changed preflight input: '+name)
    ma = read(L02/'build-r5/12021/offerings.json')
    pdp = read(L04/'build-r4/records.json')
    targets = {r['id']:{'name':r['name'],'parent':r['parent'],'kind':'MA-PD'} for r in ma if r['drug']=='Yes'}
    targets.update({r['offering_id']:{'name':r['fields']['plan_name']['value'],'parent':r['fields']['parent_organization']['value'],'kind':'PDP'} for r in pdp})
    if len(targets)!=71 or set(targets)!=set(pre['plan_to_formulary_ids']):
        raise ValueError('Changed target identity population')
    source = read(acquisition/'source-manifest.json')
    if source.get('error'):
        raise ValueError('Incomplete acquisition')
    sup = read(supplemental/'source-manifest.json')
    old = read(L04/'acquisition-r1/source-manifest.json')['sources']['monthly']
    geo_spec = next(m for m in old['members'] if m['name'].startswith('geographic'))
    geo_name, geo_raw = extract_zip_member(ROOT/geo_spec['path'], lambda n:n.endswith('.txt'))
    geo_rows = list(csv.DictReader(io.StringIO(geo_raw.decode('cp1252')),delimiter='|'))
    geo = [r for r in geo_rows if r['COUNTY']=='Collier' and r['STATENAME']=='Florida']
    if len(geo)!=1 or geo[0]['COUNTY_CODE']!='10100' or geo[0]['PDP_REGION_CODE']!='11' or geo[0]['MA_REGION_CODE']!='09':
        raise ValueError('Collier geography mismatch')
    plan_spec = next(m for m in old['members'] if m['name'].startswith('plan information'))
    plan_name, plan_raw = extract_zip_member(ROOT/plan_spec['path'],lambda n:n.endswith('.txt'))
    selected = defaultdict(list)
    for ordinal, row in enumerate(csv.DictReader(io.StringIO(plan_raw.decode('cp1252')),delimiter='|'),2):
        ident='2026:'+':'.join(row[k] for k in ('CONTRACT_ID','PLAN_ID','SEGMENT_ID'))
        if ident in targets and market_plan(row,geo[0]):
            selected[ident].append((ordinal,row))
    if set(selected)!=set(targets) or any(len(v)!=1 for v in selected.values()):
        raise ValueError('Missing/ambiguous exact plan/geography mapping')
    plans=[]
    for ident in sorted(targets):
        ordinal,row=selected[ident][0]
        plans.append({'offering_id':ident,**targets[ident], 'formulary_id':row['FORMULARY_ID'],
                      'suppressed':row['PLAN_SUPPRESSED_YN']=='Y','monthly_raw':row,
                      'source':{'archive_path':plan_spec['path'],'archive_sha256':plan_spec['sha256'],
                                'member':plan_name,'record_ordinal':ordinal}})
    forms={p['formulary_id'] for p in plans if not p['suppressed']}
    pairs={tuple(p['offering_id'].split(':')[1:3]) for p in plans if not p['suppressed']}
    out.mkdir()
    db=sqlite3.connect(out/'inventory.sqlite3')
    db.executescript('''CREATE TABLE plans(offering_id TEXT PRIMARY KEY,formulary_id TEXT,payload TEXT);
CREATE TABLE drug_rows(table_name TEXT,ordinal INTEGER,formulary_id TEXT,contract_id TEXT,plan_id TEXT,rxcui TEXT,ndc TEXT,raw_json TEXT,modeled_json TEXT,PRIMARY KEY(table_name,ordinal));
CREATE TABLE drug_identities(rxcui TEXT PRIMARY KEY,payload TEXT);
CREATE TABLE benefit_context(offering_id TEXT PRIMARY KEY,payload TEXT);
CREATE TABLE condition_gaps(table_name TEXT,ordinal INTEGER,missing_fact TEXT,source_needed TEXT,PRIMARY KEY(table_name,ordinal,missing_fact));''')
    config={'members':{}}
    source_members={}
    for m in source['sources']['drug_tables']['members']:
        table='basic' if m['name'].startswith('basic') else 'excluded' if m['name'].startswith('excluded') else 'indication'
        if digest(ROOT/m['path'])!=m['sha256'] or len(m['inner_members'])!=1:
            raise ValueError('Changed/ambiguous acquired drug member')
        inner=m['inner_members'][0]
        config['members'][table]={'outer_member':Path(m['path']).name,'inner_member':inner['name'],
                                  'columns':FIELDS[table],'uncompressed_bytes':inner['bytes'],'encoding':'cp1252'}
        source_members[table]={'outer':m,'inner':inner}
    counts, versions, stats, flag_counts, code_ids = Counter(),defaultdict(set),{},defaultdict(Counter),set()
    row_accounting={}
    captures={}
    field_observations=Counter()
    for table in FIELDS:
        fields=FIELDS[table]
        dest=out/(table+'.csv.gz')
        with dest.open('wb') as raw_out, gzip.GzipFile(filename='',fileobj=raw_out,mode='wb',mtime=0) as zip_out, io.TextIOWrapper(zip_out,encoding='utf-8',newline='') as text_out:
            writer=csv.writer(text_out);writer.writerow(['source_row']+fields)
            for ordinal,row,raw_line in source_rows(config,acquisition/'raw',table,stats):
                if table=='basic' and row['CONTRACT_YEAR']!='2026':
                    raise ValueError('Wrong drug-table contract year')
                keep=row['FORMULARY_ID'] in forms if table=='basic' else (row['CONTRACT_ID'],row['PLAN_ID']) in pairs
                if not keep:
                    continue
                modeled={f:normalized(table,f,row[f]) for f in fields}
                if any(v['state'] in ('unresolved_code','invalid_numeric') for v in modeled.values()):
                    raise ValueError('Unresolved typed source value; do not drop row')
                counts[table]+=1;field_observations[table]+=len(fields);code_ids.add(row['RXCUI'])
                if table=='basic':versions[row['FORMULARY_ID']].add(row['FORMULARY_VERSION'])
                for f,v in modeled.items():
                    if v['type']=='boolean' and v['value'] is True:
                        flag_counts[table][f]+=1
                db.execute('INSERT INTO drug_rows VALUES(?,?,?,?,?,?,?,?,?)',(table,ordinal,row.get('FORMULARY_ID'),row.get('CONTRACT_ID'),row.get('PLAN_ID'),row['RXCUI'],row.get('NDC'),packed(row),packed(modeled)))
                writer.writerow([ordinal]+[row[f] for f in fields])
                for field,fact,need in [('PRIOR_AUTHORIZATION_YN','prior_authorization_criteria','Exact applicable 2026 Part D carrier PA criteria'),('PRIOR_AUTH_YN','prior_authorization_criteria','Exact applicable 2026 Part D carrier PA criteria'),('STEP_THERAPY_YN','step_therapy_criteria','Exact applicable 2026 Part D carrier ST criteria'),('QUANTITY_LIMIT_YN','physical_quantity_unit','Exact applicable carrier quantity-unit statement; no inference from proxy NDC'),('CAPPED_BENEFIT_YN','supplemental_cap_qualification','Exact applicable published cap qualification')]:
                    if field in modeled and modeled[field]['value'] is True:
                        db.execute('INSERT INTO condition_gaps VALUES(?,?,?,?)',(table,ordinal,fact,need))
        row_accounting[table]={'national_rows':stats[table]['rows'],'scoped_rows':counts[table],
                               'outside_scope_rows':stats[table]['rows']-counts[table],'quarantined_rows':0,
                               'all_source_columns_modeled':fields,'modeled_field_observations':field_observations[table]}
        captures[table]={'path':dest.name,'rows':counts[table]}
    missing_forms=sorted(forms-set(versions))
    if missing_forms or any(len(v)!=1 for v in versions.values()):
        raise ValueError('Missing or ambiguous actual formulary version')
    for p in plans:
        p['formulary_version']=next(iter(versions[p['formulary_id']])) if not p['suppressed'] else None
        p['basic_rows']=db.execute('SELECT count(*) FROM drug_rows WHERE table_name="basic" AND formulary_id=?',(p['formulary_id'],)).fetchone()[0]
        pair=p['offering_id'].split(':')[1:3]
        for t in ('excluded','indication'):
            p[t+'_rows']=db.execute('SELECT count(*) FROM drug_rows WHERE table_name=? AND contract_id=? AND plan_id=?',(t,*pair)).fetchone()[0]
        p['supplemental_source_grain']='contract/plan; segment is not asserted by these files'
        db.execute('INSERT INTO plans VALUES(?,?,?)',(p['offering_id'],p['formulary_id'],packed(p)))
    # Exact identity dictionary; it never supplies coverage or a physical QL unit.
    frf=source['sources']['drug_identity_reference']
    frf_name,frf_bytes=extract_zip_member(ROOT/frf['path'],lambda n:n.endswith('.csv'))
    reference_rows=list(csv.DictReader(io.StringIO(frf_bytes.decode('cp1252'))))
    reference={}
    for ordinal,row in enumerate(reference_rows,2):
        if row['RxCUI'] in reference:
            raise ValueError('Ambiguous FRF identifier')
        reference[row['RxCUI']]=(ordinal,row)
    identities=[]
    for code in sorted(code_ids):
        if code in reference:
            ordinal,row=reference[code]
            identity={'rxcui':code,'name':row['RxNorm Description'],'type':row['TTY'],
                      'ingredient_strength_description':row['Related SCDC'],'dose_form':row['Related DF'],
                      'related_brand':row['Related BN'],'raw':row,
                      'source':{'kind':'CMS_2026_FRF','archive_path':frf['path'],'archive_sha256':frf['sha256'],
                                'member':frf_name,'record_ordinal':ordinal},'coverage_inferred':False}
        else:
            s=sup['sources'].get('rxnorm-history-'+code,{})
            if s.get('status')!='captured' or digest(ROOT/s['path'])!=s['sha256']:
                raise ValueError('Unresolved drug identity: '+code)
            body=read(ROOT/s['path'])['rxcuiStatusHistory'];attrs=body.get('attributes',{})
            if attrs.get('rxcui')!=code or not attrs.get('name'):
                raise ValueError('No exact historical name for '+code)
            identity={'rxcui':code,'name':attrs['name'],'type':attrs.get('tty'),
                      'definitional_features':body.get('definitionalFeatures',{}),'history':body['metaData'],
                      'raw':body,'source':{'kind':'NLM_RxNorm_history','path':s['path'],'sha256':s['sha256'],
                                          'url':s['requested_url'],'retrieved_at_utc':s['retrieved_at_utc']},'coverage_inferred':False}
        identities.append(identity);db.execute('INSERT INTO drug_identities VALUES(?,?)',(code,packed(identity)))
    # Reuse exact Rx source objects rather than recollecting/renormalizing benefits.
    pbp=L02/'acquisition-r1/raw/65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3'
    with zipfile.ZipFile(pbp) as z, (out/'benefit-context.jsonl.gz').open('wb') as out_raw, gzip.GzipFile(filename='',fileobj=out_raw,mode='wb',mtime=0) as stream:
        for ident in sorted(targets):
            member='-'.join([*ident.split(':')[1:],'2026'])+'.json'
            obj=json.loads(z.read(member));context={'offering_id':ident,'source_archive':str(pbp.relative_to(ROOT)),
                'member':member,'pointer':'/pbp/0/rx','rx':obj['pbp'][0].get('rx'),
                'interpretation':'Reused raw plan-level drug-benefit context; not a price or drug-coverage assertion.'}
            stream.write((packed(context)+'\n').encode());db.execute('INSERT INTO benefit_context VALUES(?,?)',(ident,packed(context)))
    db.executescript('CREATE INDEX drug_form ON drug_rows(formulary_id); CREATE INDEX drug_rx ON drug_rows(rxcui); CREATE INDEX drug_plan ON drug_rows(contract_id,plan_id);')
    gap_counts=dict(db.execute('SELECT missing_fact,count(*) FROM condition_gaps GROUP BY missing_fact'))
    coverage={'year':2026,'county_fips':'12021','pdp_region':'11','source_period':'2026-09','evidence_cutoff':'2026-10-25',
              'target_plans':len(plans),'ma_pd_plans':61,'pdp_plans':10,'formulary_ids':len(forms),
              'source_row_accounting':row_accounting,'scoped_rows':{t:counts[t] for t in FIELDS},'source_fields_checked':{t:field_observations[t] for t in FIELDS},
              'formulary_versions':{f:sorted(v) for f,v in sorted(versions.items())},'flag_counts':{t:dict(c) for t,c in flag_counts.items()},
              'distinct_drug_identifiers':len(code_ids),'identity_names_resolved':len(identities),'missing_formularies':missing_forms,
              'suppressed_target_plans':[p['offering_id'] for p in plans if p['suppressed']],
              'plan_drug_relationships':sum(p['basic_rows']+p['excluded_rows']+p['indication_rows'] for p in plans),
              'cms_published_row_inventory_complete':not missing_forms,'condition_details_not_supplied_by_CMS_tables':gap_counts,
              'condition_detail_ledger_basis':'CMS payload limitations only; this ledger does not assert that carrier documents are unavailable. See the separate dated condition-source assessment.',
              'full_published_condition_reference_complete':False,'human_acceptance':None,'consumer_release_enabled':False}
    fieldmap={t:{f:{'type':normalized(t,f,'0' if f in ('TIER','TIER_LEVEL_VALUE','QUANTITY_LIMIT_DAYS','QUANTITY_LIMIT_AMOUNT') else '')['type'],
                    'source_column':f,'flag_encoding':('0/1' if t=='excluded' and f=='QUANTITY_LIMIT_YN' else 'Y/N') if f.endswith('_YN') else None,
                    'physical_quantity_unit_in_source':False if f=='QUANTITY_LIMIT_AMOUNT' else None} for f in fs} for t,fs in FIELDS.items()}
    for name,data in [('plans.json',plans),('identities.json',identities),('coverage.json',coverage),('field-map.json',fieldmap),
                      ('source-members.json',source_members),('source-row-accounting.json',stats)]:dump(out/name,data)
    with (out/'plans.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['offering_id','name','kind','formulary_id','formulary_version','basic_rows','excluded_rows','indication_rows'])
        for p in plans:writer.writerow([p[k] for k in ['offering_id','name','kind','formulary_id','formulary_version','basic_rows','excluded_rows','indication_rows']])
    with (out/'condition-gaps.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['table_name','source_row','missing_fact','source_needed']);writer.writerows(db.execute('SELECT * FROM condition_gaps ORDER BY table_name,ordinal,missing_fact'))
    db.commit();db.close()
    inputs=[BASE/'planning-preflight.json',L02/'build-r5/12021/offerings.json',L04/'build-r4/records.json',L04/'acquisition-r1/source-manifest.json',
            acquisition/'source-manifest.json',supplemental/'source-manifest.json',pbp,ROOT/plan_spec['path'],ROOT/geo_spec['path'],ROOT/frf['path']]
    inputs += [ROOT/m['path'] for m in source['sources']['drug_tables']['members']]
    inputs += [ROOT/m[k]['path'] for m in source['sources']['drug_tables']['members'] for k in ['compressed_block','local_header']]
    inputs += [ROOT/v['path'] for v in source['sources']['drug_tables']['reused_index'].values() if isinstance(v,dict) and 'path' in v]
    inputs += [ROOT/source['sources']['drug_tables']['tail_recheck']['path']]
    inputs += [ROOT/s['path'] for s in sup['sources'].values() if s.get('status')=='captured']
    inputs += [ROOT/s['text_path'] for s in sup['sources'].values() if s.get('status')=='captured' and 'text_path' in s]
    code=[ROOT/'cms-slice/scripts'/n for n in ['l05_acquire.py','l05_collect.py','l05_build.py','l05_validate.py','l05_reference.py','prescription.py','cms_slice.py','l04_acquire.py']]
    manifest={'schema':'l05-build/1','package_id':'L05-PUBLISHED-2026-'+out.name,'year':2026,
              'acquisition':str(acquisition.relative_to(ROOT)),'supplemental':str(supplemental.relative_to(ROOT)),
              'inputs':{str(p.relative_to(ROOT)):digest(p) for p in sorted(set(inputs))},
              'code':{str(p.relative_to(ROOT)):digest(p) for p in code},
              'files':{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()},
              'actual_human_acceptance':None,'consumer_release_enabled':False}
    dump(out/'manifest.json',manifest)
    return coverage


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition',type=Path,required=True);parser.add_argument('--supplemental',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(build(a.acquisition.resolve(),a.supplemental.resolve(),a.out.resolve()),indent=2))
