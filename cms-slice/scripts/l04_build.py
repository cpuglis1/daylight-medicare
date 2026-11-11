"""Offline, immutable build of the published 2026 Florida standalone PDP reference."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l04-pdp-availability-2026-10-25'
L02 = ROOT / 'docs/data/l02-ma-availability-2026-10-25'
CODE = ('l04_build.py', 'l04_validate.py', 'l04_reference.py', 'l04_acquire.py')
PUF_COLUMNS = ['CONTRACT_ID','PLAN_ID','SEGMENT_ID','CONTRACT_NAME','PLAN_NAME','FORMULARY_ID','PREMIUM','DEDUCTIBLE','MA_REGION_CODE','PDP_REGION_CODE','STATE','COUNTY_CODE','SNP','PLAN_SUPPRESSED_YN']
GEO_COLUMNS = ['COUNTY_CODE','STATENAME','COUNTY','MA_REGION_CODE','MA_REGION','PDP_REGION_CODE','PDP_REGION']
AREA_COLUMNS = ['Contract ID','Organization Name','Organization Type','Plan Type','Partial','EGHP','SSA','FIPS','COUNTY','STCD','Notes']


class BuildError(ValueError):
    pass


def read(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def identity(year, contract, plan, segment):
    values = [str(x).strip() for x in (year, contract, plan, segment)]
    if (values[0] != '2026' or not re.fullmatch('[A-Z][0-9]{4}', values[1])
            or not re.fullmatch('[0-9]{1,3}', values[2]) or not re.fullmatch('[0-9]{1,3}', values[3])):
        raise BuildError('Invalid/wrong-year offering identity')
    return ':'.join([values[0], values[1], values[2].zfill(3), values[3].zfill(3)])


def money(value):
    text = str(value).strip()
    if text in ('', 'Not Applicable', 'Not Available'):
        return None
    if not re.fullmatch(r'\(?-?\$?[0-9,]+(?:\.[0-9]{1,2})?\)?', text):
        raise BuildError('Unrecognized monetary representation: ' + text)
    if text.startswith('(') != text.endswith(')'):
        raise BuildError('Unbalanced monetary parentheses')
    amount = Decimal(text.replace('$', '').replace(',', '').strip('()'))
    if text.startswith('('):
        amount = -amount
    return int(amount * 100)


def fact(raw, field):
    text = raw.strip()
    state = 'missing' if text == '' else 'not_applicable' if text == 'Not Applicable' else 'unavailable' if text == 'Not Available' else 'published'
    value = None if state != 'published' else text
    kind = field['type']
    if value is not None:
        if kind.startswith('money_'):
            value = money(raw)
        elif kind == 'year':
            if text != '2026':
                raise BuildError('Wrong benefit year')
            value = int(text)
        elif kind == 'id3':
            if not re.fullmatch(r'\d{1,3}', text):
                raise BuildError('Malformed plan/segment')
            value = text.zfill(3)
        elif kind == 'region':
            if not re.fullmatch(r'\d{1,2}', text) or not 1 <= int(text) <= 39:
                raise BuildError('Unreviewed PDP region')
            value = text.zfill(2)
        elif kind == 'flag' and text not in ('Yes', 'No'):
            raise BuildError('Unreviewed flag: ' + text)
    return {'raw': raw, 'value': value, 'state': state, 'unit': field['unit'], 'basis': field['basis'],
            'value_encoding':'integer_cents' if kind.startswith('money_') else 'literal'}


def pin(spec, artifacts, name):
    path = Path(spec.get('path', ''))
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file() or path.stat().st_size != spec['bytes'] or digest(path) != spec['sha256']:
        raise BuildError('Source evidence changed: ' + name)
    artifacts[name] = {'path': str(path.relative_to(ROOT)), 'sha256': spec['sha256'], 'bytes': spec['bytes']}
    return path


def zip_rows(path, suffix, delimiter=',', encoding='utf-8-sig'):
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.endswith(suffix)]
        if len(members) != 1:
            raise BuildError('Ambiguous archive member')
        name = members[0]
        raw = archive.read(name)
    reader = csv.DictReader(io.StringIO(raw.decode(encoding), newline=''), delimiter=delimiter)
    return name, hashlib.sha256(raw).hexdigest(), reader


def export(db, path, table, order):
    cursor = db.execute(f'SELECT * FROM {table} ORDER BY {order}')
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow([x[0] for x in cursor.description])
        writer.writerows(cursor)


def build(out, acquisition=BASE/'acquisition-r1'):
    out, acquisition = Path(out).resolve(), Path(acquisition).resolve()
    if out.exists():
        raise BuildError('Immutable build directory exists; use a new revision')
    fields = read(BASE/'field-map.json')
    scope = read(BASE/'scope.json')
    if fields['year'] != 2026 or scope['year'] != 2026 or scope['state'] != 'FL' or scope['pdp_region_code'] != '11':
        raise BuildError('This release contract is 2026 Florida only')
    old = read(L02/'acquisition-r1/source-manifest.json')['sources']
    captured = read(acquisition/'source-manifest.json')
    artifacts, sources = {}, {}
    for name, old_name, sid in [('landscape','landscape','P26-S04B'), ('pbp','pbp','P26-S08B-JSON')]:
        spec = old[old_name]
        if spec['benefit_year'] != '2026':
            raise BuildError('Wrong-year source manifest')
        path = L02/'acquisition-r1/raw'/spec['sha256']
        pin({**spec, 'path':str(path)}, artifacts, name)
        sources[name] = {k:spec[k] for k in ('requested_url','final_url','retrieved_at_utc','benefit_year','source_period','sha256','bytes')}
        sources[name]['id'] = sid
    for name, spec in captured['sources'].items():
        sources[name] = spec
        if spec['status'] != 'captured':
            continue
        if spec.get('path'):
            pin(spec, artifacts, name)
        if name == 'monthly':
            for label in ('tail','central_directory','synthetic_index'):
                pin(spec['index'][label], artifacts, 'monthly-index-'+label)
            for i, member in enumerate(spec['members']):
                for label, value in [('member', member), ('compressed', member['compressed_block']), ('header', member['local_header'])]:
                    pin(value, artifacts, f'monthly-{i}-{label}')
    for required in ('monthly','area-september','area-october'):
        if sources[required]['status'] != 'captured':
            raise BuildError('Required source unavailable: ' + required)
    old_geo = read(L02/'build-r5/geography-manifest.json')
    geo_path = ROOT/'cms-slice'/old_geo['path']
    pin({**old_geo, 'path':str(geo_path)}, artifacts, 'census-counties')
    out.mkdir(parents=True)
    db = sqlite3.connect(out/'inventory.sqlite3')
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE ledger(source TEXT,ordinal INTEGER,offering_id TEXT,category TEXT,region TEXT,state TEXT,route TEXT,reason TEXT,PRIMARY KEY(source,ordinal));
      CREATE TABLE quarantine(source TEXT,ordinal INTEGER,reason TEXT,raw_json TEXT);
      CREATE TABLE catalog(ordinal INTEGER PRIMARY KEY,offering_id TEXT,region TEXT,state TEXT,raw_json TEXT,fields_json TEXT,locator_json TEXT);
      CREATE INDEX catalog_scope ON catalog(region,state,offering_id);
      CREATE TABLE secondary(source TEXT,ordinal INTEGER,offering_id TEXT,region TEXT,disposition TEXT,raw_json TEXT,locator_json TEXT,PRIMARY KEY(source,ordinal));
      CREATE TABLE counties(fips TEXT PRIMARY KEY,state TEXT,name TEXT,ssa TEXT,region TEXT,locator_json TEXT);
      CREATE TABLE comparisons(offering_id TEXT,source TEXT,field TEXT,primary_json TEXT,secondary_json TEXT,status TEXT,disposition TEXT);
    ''')
    counts, routes, duplicates, math_checks, primary_members = {}, Counter(), [], [], {}
    schema = read(L02/'schemas.json')['years']['2026']
    member, member_sha, reader = zip_rows(ROOT/artifacts['landscape']['path'], '.csv')
    if reader.fieldnames != schema['columns']:
        raise BuildError('Landscape schema changed')
    primary_members['landscape'] = {'member':member,'sha256':member_sha,'encoding':'utf-8-sig','data_updated':'2026-09-02'}
    seen = set()
    for ordinal, row in enumerate(reader, 2):
        route, reason, key = 'investigate', '', None
        try:
            if None in row or any(v is None for v in row.values()):
                raise BuildError('Malformed source row')
            key = identity(*(row[c] for c in ('Contract Year','Contract ID','Plan ID','Segment ID')))
            if row['Contract Category Type'] not in schema['categories']:
                raise BuildError('Unknown product category')
            route = 'L04' if row['Contract Category Type'] == 'PDP' else 'other_layer'
            if int(row['Plan ID']) >= 800:
                route, reason = 'employer_group_excluded', 'Landscape README excludes plan IDs >=800 from individual population'
            composite = row['Contract ID']+'_'+row['Plan ID']
            if row['ContractPlanID'] != composite or row['ContractPlanSegmentID'] != composite+'_'+row['Segment ID']:
                raise BuildError('Source composite identity disagreement')
            if route == 'L04':
                if not row['Contract ID'].startswith('S') or row['Part D Coverage Indicator'] != 'Yes':
                    raise BuildError('Unexpected PDP classification')
                values = {f['key']: fact(row[f['source_column']], f) for f in fields['fields']}
                region = values['pdp_region_code']['value']
                if region is None:
                    raise BuildError('PDP region missing')
                observation = (key,region,row['State Territory Abbreviation'],row['County Name'])
                if observation in seen:
                    duplicates.append({'ordinal':ordinal,'observation':observation})
                seen.add(observation)
                locator = {'source':'landscape','member':member,'member_sha256':member_sha,'record_ordinal':ordinal}
                db.execute('INSERT INTO catalog VALUES(?,?,?,?,?,?,?)',(ordinal,key,region,row['State Territory Abbreviation'],canonical(row),canonical(values),canonical(locator)))
                basic, supplemental, total = [values[k]['value'] for k in ('basic_premium','supplemental_premium','total_premium')]
                math_checks.append({'offering_id':key,'ordinal':ordinal,'status':'passed' if None not in (basic,supplemental,total) and basic+supplemental == total else 'not_comparable' if None in (basic,supplemental,total) else 'conflict'})
        except (ValueError, TypeError, KeyError) as error:
            route, reason = 'quarantine', str(error)
            db.execute('INSERT INTO quarantine VALUES(?,?,?,?)',('landscape',ordinal,reason,canonical(row)))
        routes[route] += 1
        db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)',('landscape',ordinal,key,row.get('Contract Category Type'),row.get('PDP Region Code'),row.get('State Territory Abbreviation'),route,reason))
    counts['landscape'] = {'raw':sum(routes.values()),'parsed':sum(routes.values())-routes['quarantine'],'quarantined':routes['quarantine'],'routes':dict(routes)}
    florida = db.execute("SELECT * FROM catalog WHERE region='11' AND state='FL' ORDER BY offering_id").fetchall()
    keys = {r['offering_id'] for r in florida}
    if len(keys) != len(florida) or duplicates:
        raise BuildError('Duplicate offering/location observations require disposition')
    pdp_keys = {r[0] for r in db.execute('SELECT DISTINCT offering_id FROM catalog')}
    # Every S-contract PBP member is inspected, including employer records.
    pbp_keys, pbp_fl, pbp_raw, pbp_groups, pbp_deductibles = set(), set(), 0, [], {}
    with zipfile.ZipFile(ROOT/artifacts['pbp']['path']) as archive:
        for ordinal, name in enumerate(sorted(archive.namelist()), 1):
            if not name.startswith('S') or not name.endswith('.json'):
                continue
            pbp_raw += 1
            raw = archive.read(name)
            try:
                data = json.loads(raw)
                if set(data) != {'contractYear','section','pbp'} or len(data['pbp']) != 1:
                    raise BuildError('Unreviewed PBP cardinality/layout')
                p = data['pbp'][0]
                key = identity(data['contractYear'],p['contractId'],p['planId'],p['segmentId'])
                if '-'.join(key.split(':')[1:])+ '-2026.json' != name:
                    raise BuildError('PBP filename/payload disagreement')
                c = p['planCharacteristics']
                employer = c.get('isEmployerOnlyPlan')
                if employer not in ('Yes','No'):
                    raise BuildError('Unknown employer population')
                disposition = 'employer_group_excluded' if employer == 'Yes' or int(p['planId']) >= 800 else 'individual_pdp'
                if disposition == 'individual_pdp':
                    pbp_keys.add(key)
                    if c.get('geographicName') in ('Florida','State of Florida'):
                        pbp_fl.add(key)
                elif 'Florida' in c.get('geographicName',''):
                    pbp_groups.append(key)
                loc = {'source':'pbp','member':name,'member_sha256':hashlib.sha256(raw).hexdigest(),'json_pointer':'/pbp/0/planCharacteristics'}
                db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?)',('pbp',ordinal,key,None,disposition,canonical(c),canonical(loc)))
                if key in keys:
                    details = p['rx']['rxDetails']['rxSetup']['rxCostShare']['rxCostShareDetails']
                    rx_loc = {**loc,'source':'pbp-rx','json_pointer':'/pbp/0/rx/rxDetails/rxSetup/rxCostShare/rxCostShareDetails'}
                    db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?)',('pbp-rx',ordinal,key,None,disposition,canonical(details),canonical(rx_loc)))
                    if details.get('costShareDeductibleAmount') is not None:
                        pbp_deductibles[key] = money(details['costShareDeductibleAmount'])
            except (ValueError,KeyError,TypeError) as error:
                db.execute('INSERT INTO quarantine VALUES(?,?,?,?)',('pbp',ordinal,str(error),raw.decode(errors='replace')))
    counts['pbp_s_contract_members'] = {'raw':pbp_raw,'individual_identities':len(pbp_keys),'florida_individual_identities':len(pbp_fl),'florida_group_exclusions':pbp_groups}
    monthly_fl, monthly_keys, puf_geo = set(), set(), []
    for member_spec in sources['monthly']['members']:
        name, member_sha, reader = zip_rows(ROOT/member_spec['path'], '.txt', '|', 'cp1252')
        is_plan = 'plan information' in member_spec['name']
        expected = PUF_COLUMNS if is_plan else GEO_COLUMNS
        if reader.fieldnames != expected:
            raise BuildError('Monthly member schema changed')
        source = 'monthly-plan' if is_plan else 'monthly-geo'
        primary_members[source] = {'member':name,'sha256':member_sha,'encoding':'cp1252','outer_member':member_spec['name']}
        total = parsed = 0
        for ordinal, row in enumerate(reader, 2):
            total += 1
            region_raw = row.get('PDP_REGION_CODE','').strip()
            key, region, disposition = None, region_raw.zfill(2) if region_raw else None, 'other_layer'
            try:
                if None in row or any(v is None for v in row.values()):
                    raise BuildError('Malformed monthly row')
                if is_plan:
                    key = identity('2026',row['CONTRACT_ID'],row['PLAN_ID'],row['SEGMENT_ID'])
                    if row['PLAN_SUPPRESSED_YN'] not in ('Y','N'):
                        raise BuildError('Unknown suppression flag')
                    if row['CONTRACT_ID'].startswith('S'):
                        disposition = 'employer_group_excluded' if int(row['PLAN_ID']) >= 800 else 'individual_pdp'
                        if disposition == 'individual_pdp':
                            monthly_keys.add(key)
                            if region == '11': monthly_fl.add(key)
                        # Values stay as source observations. PREMIUM is not promoted
                        # to a standard or subsidized premium by this build.
                        money(row['PREMIUM']); money(row['DEDUCTIBLE'])
                    else:
                        continue
                else:
                    if not re.fullmatch(r'\d{5}', row['COUNTY_CODE']):
                        raise BuildError('Malformed SSA county code')
                    puf_geo.append((ordinal,row))
                    disposition = 'geography'
                locator = {'source':source,'member':name,'member_sha256':member_sha,'record_ordinal':ordinal}
                db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?)',(source,ordinal,key,region,disposition,canonical(row),canonical(locator)))
            except (ValueError,KeyError,TypeError) as error:
                db.execute('INSERT INTO quarantine VALUES(?,?,?,?)',(source,ordinal,str(error),canonical(row)))
                disposition = 'quarantine'
            finally:
                parsed += disposition != 'quarantine'
                db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)',(source,ordinal,key,None,region,row.get('STATE'),disposition,''))
        counts[source] = {'raw':total,'parsed':parsed,'quarantined':total-parsed}
    areas = {}
    fl_area_codes = {}
    for label in ('area-september','area-october'):
        name, member_sha, reader = zip_rows(ROOT/artifacts[label]['path'],'.csv')
        if reader.fieldnames != AREA_COLUMNS:
            raise BuildError('PDP service-area schema changed')
        primary_members[label] = {'member':name,'sha256':member_sha,'encoding':'utf-8-sig'}
        contracts, total, relevant = set(), 0, 0
        for ordinal, row in enumerate(reader, 2):
            total += 1
            if (None in row or any(v is None for v in row.values()) or row['Partial'] not in ('','*') or row['EGHP'] not in ('','*')):
                db.execute('INSERT INTO quarantine VALUES(?,?,?,?)',(label,ordinal,'Unreviewed service area row',canonical(row)))
                continue
            if row['STCD'] == 'FL':
                relevant += 1
                disposition = 'employer_group_excluded' if row['EGHP'] == '*' else 'contract_area_only'
                locator = {'source':label,'member':name,'member_sha256':member_sha,'record_ordinal':ordinal}
                db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?)',(label,ordinal,row['Contract ID'],None,disposition,canonical(row),canonical(locator)))
                if disposition == 'contract_area_only':
                    contracts.add(row['Contract ID'])
                    if row['FIPS']:
                        old_pair = fl_area_codes.get(row['FIPS'])
                        pair = (row['SSA'],row['COUNTY'])
                        if old_pair and old_pair != pair:
                            raise BuildError('Conflicting FIPS/SSA county crosswalk')
                        fl_area_codes[row['FIPS']] = pair
        quarantined = db.execute('SELECT count(*) FROM quarantine WHERE source=?',(label,)).fetchone()[0]
        counts[label] = {'raw':total,'parsed':total-quarantined,'quarantined':quarantined,'florida_rows':relevant}
        areas[label] = contracts
    # County count/identity derives from the pinned national Census file, not
    # a four-ZIP sample, guessed SSA code, or plan county-name expansion.
    with zipfile.ZipFile(geo_path) as archive:
        census = csv.DictReader(io.StringIO(archive.read(old_geo['member']).decode()),delimiter='|')
        census_fl = [r for r in census if r['USPS'] == 'FL']
    geo_by_ssa = {r['COUNTY_CODE']: (ordinal,r) for ordinal,r in puf_geo}
    geography_gaps = []
    for county in census_fl:
        fips = county['GEOID']
        pair = fl_area_codes.get(fips)
        observation = geo_by_ssa.get(pair[0]) if pair else None
        if (not observation or observation[1]['STATENAME'] != 'Florida' or observation[1]['PDP_REGION_CODE'] != '11'):
            geography_gaps.append(fips)
            continue
        ordinal, row = observation
        if row['COUNTY'] != pair[1]:
            geography_gaps.append(fips)
            continue
        db.execute('INSERT INTO counties VALUES(?,?,?,?,?,?)',(fips,'FL',county['NAME'],pair[0],'11',canonical({'census_geoid':fips,'area_sources':['area-september','area-october'],'monthly_geo_ordinal':ordinal})))
    comparison_rows = []
    def compare(key, source, field, primary, other, status, disposition):
        row = (key,source,field,canonical(primary),canonical(other),status,disposition)
        db.execute('INSERT INTO comparisons VALUES(?,?,?,?,?,?,?)',row)
        comparison_rows.append(dict(zip(('offering_id','source','field','primary_json','secondary_json','status','disposition'),row)))
    for row in florida:
        key, values = row['offering_id'], json.loads(row['fields_json'])
        for source, second, disposition in [('pbp',pbp_fl,'PBP individual Florida classification'),('monthly-plan',monthly_fl,'Monthly PDP region 11')]:
            compare(key,source,'identity',key,key if key in second else None,'agrees' if key in second else 'missing',disposition)
        pbp = db.execute("SELECT raw_json FROM secondary WHERE source='pbp' AND offering_id=?",(key,)).fetchone()
        if pbp:
            raw = json.loads(pbp[0])
            for field,other_col in [('plan_name','planName'),('contract_name','contractLegalName'),('marketing_name','organizationMarketingName'),('drug_coverage','isOfferRx'),('category','organizationType')]:
                a,b = values[field]['value'],raw.get(other_col)
                compare(key,'pbp',field,a,b,'agrees' if a == b else 'conflict','Exact corresponding plan-characteristic source values; raw source labels remain distinct')
        if key in pbp_deductibles:
            a,b = values['annual_deductible']['value'],pbp_deductibles[key]
            compare(key,'pbp-rx','annual_deductible',a,b,'agrees' if a == b else 'conflict','Explicit PBP deductible amount only; conditional fields retained without default imputation or tier-rule execution')
        puf = db.execute("SELECT raw_json FROM secondary WHERE source='monthly-plan' AND offering_id=? AND region='11'",(key,)).fetchall()
        for observation in puf:
            raw = json.loads(observation[0])
            for field,other_col in [('plan_name','PLAN_NAME'),('contract_name','CONTRACT_NAME'),('pdp_region_code','PDP_REGION_CODE')]:
                a,b = values[field]['value'],raw[other_col].strip()
                compare(key,'monthly-plan',field,a,b,'agrees' if a == b else 'conflict','Exact corresponding plan information field')
            for field, other_col in [('annual_deductible','DEDUCTIBLE'),('total_premium','PREMIUM')]:
                other = money(raw[other_col]); primary = values[field]['value']
                status = 'agrees' if primary == other else 'different_basis_unresolved' if field == 'total_premium' else 'conflict'
                compare(key,'monthly-plan',field,primary,other,status,'Keep original source values; monthly PREMIUM basis is not mapped to a personal or standard bill')
            compare(key,'monthly-plan','premium_equals_published_lis_observation',values['low_income_beneficiary_premium']['value'],money(raw['PREMIUM']),'numeric_agreement_distinct_basis' if values['low_income_beneficiary_premium']['value'] == money(raw['PREMIUM']) else 'expected_basis_difference','Compare distinct standard and subsidy-adjusted published bases; this diagnostic is not a source conflict or personal subsidy calculation')
        for label, contracts in areas.items():
            compare(key,label,'contract_area',key.split(':')[1],key.split(':')[1] if key.split(':')[1] in contracts else None,'agrees' if key.split(':')[1] in contracts else 'missing','Contract-grain evidence; does not establish each plan or personal eligibility')
    carrier_observations = read(BASE/'carrier-observations.json')
    for observation in carrier_observations:
        for label in ('extracted','visual'):
            path = ROOT/observation[label+'_path']
            pin({'path':str(path),'sha256':observation[label+'_sha256'],'bytes':path.stat().st_size},artifacts,observation['source']+'-'+label)
        if sources[observation['source']]['status'] != 'captured' or observation['offering_id'] not in keys:
            raise BuildError('Carrier observation is not bound to an acquired source and scoped offering')
        primary = next(json.loads(r['fields_json']) for r in florida if r['offering_id'] == observation['offering_id'])
        for field, value in observation['values_cents'].items():
            compare(observation['offering_id'],observation['source'],field,primary[field]['value'],value,'agrees' if primary[field]['value'] == value else 'conflict','AI table transcription; exact PDF/page and rendered evidence retained; human acceptance pending')
    set_differences = {
        'florida_pbp':{'landscape_only':sorted(keys-pbp_fl),'secondary_only':sorted(pbp_fl-keys)},
        'florida_monthly':{'landscape_only':sorted(keys-monthly_fl),'secondary_only':sorted(monthly_fl-keys)},
        'national_pbp_individual_ids':{'landscape_only':sorted(pdp_keys-pbp_keys),'secondary_only':sorted(pbp_keys-pdp_keys)},
        'national_monthly_individual_ids':{'landscape_only':sorted(pdp_keys-monthly_keys),'secondary_only':sorted(monthly_keys-pdp_keys)},
    }
    contracts = {key.split(':')[1] for key in keys}
    for label, observed in areas.items():
        set_differences[label] = {'landscape_only':sorted(contracts-observed),'secondary_only':sorted(observed-contracts)}
    db.commit()
    records = [{'offering_id':r['offering_id'],'region':r['region'],'state':r['state'],'ordinal':r['ordinal'],
                'fields':json.loads(r['fields_json']),'source':json.loads(r['locator_json'])} for r in florida]
    missing = [{'offering_id':r['offering_id'],'field':k,'state':v['state']} for r in records for k,v in r['fields'].items() if v['state'] in ('missing','unavailable')]
    coverage = {'schema':'l04-completeness/1','scope':scope,'observed_fl_offerings':len(keys),'observed_fl_contracts':len(contracts),
                'national_pdp_rows':db.execute('SELECT count(*) FROM catalog').fetchone()[0],'national_pdp_identities':len(pdp_keys),
                'expected_offering_count':None,'denominator_status':'three CMS published sets reconciled; independent population acceptance pending',
                'observed_set_agrees_pbp_monthly':keys == pbp_fl == monthly_fl,
                'florida_counties_expected':len(census_fl),'florida_counties_joined':db.execute('SELECT count(*) FROM counties').fetchone()[0],
                'geography_gaps':geography_gaps,'source_set_differences':set_differences,
                'primary_field_count_per_plan':len(fields['fields']),'primary_field_observations':len(records)*len(fields['fields']),
                'missing_or_unavailable_primary_fields':missing,'quarantine_count':db.execute('SELECT count(*) FROM quarantine').fetchone()[0],
                'whole_population_accounting':counts,'premium_component_math':math_checks,
                'material_source_differences':[r for r in comparison_rows if r['status'] in ('conflict','missing','different_basis_unresolved')],
                'premium_basis_context':[r for r in comparison_rows if r['field']=='premium_equals_published_lis_observation'],
                'carrier_corroborated_plan_ids':sorted({r['offering_id'] for r in carrier_observations}),
                'pbp_explicit_deductible_plan_ids':sorted(pbp_deductibles),
                'consumer_reference_accepted':False,'personal_applicability':'not_assessed','live_enrollment_status':'not_established'}
    modeled = {f['source_column'] for f in fields['fields']}
    column_ledger = [{'column':c,'disposition':'modeled' if c in modeled else 'retained_raw_for_other_layer_or_scope_check','recoverable_from':'pinned landscape CSV plus source ordinal'} for c in schema['columns']]
    write(out/'records.json',records); write(out/'coverage.json',coverage); write(out/'source-manifest.json',sources)
    write(out/'source-members.json',primary_members); write(out/'column-ledger.json',column_ledger)
    field_coverage = []
    identity_fields = {'year','contract_id','plan_id','segment_id'}
    for record in records:
        for field in fields['fields']:
            comparisons = [{'source':r['source'],'field':r['field'],'status':r['status']} for r in comparison_rows if r['offering_id']==record['offering_id'] and (r['field']==field['key'] or field['key'] in identity_fields and r['field']=='identity')]
            field_coverage.append({'offering_id':record['offering_id'],'field':field['key'],'primary_source':{**record['source'],'source_column':field['source_column']},'primary_state':record['fields'][field['key']]['state'],'cross_source_observations':sorted(comparisons,key=lambda x:(x['source'],x['field']))})
    write(out/'field-coverage.json',field_coverage)
    with (out/'florida-pdp-reference.csv').open('w',newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['offering_id']+[f['key']+('_cents' if f['type'].startswith('money_') else '') for f in fields['fields']]+['source_record_ordinal'])
        for record in records:
            writer.writerow([record['offering_id']]+[record['fields'][f['key']]['value'] if record['fields'][f['key']]['state']=='published' else '['+record['fields'][f['key']]['state']+']' for f in fields['fields']]+[record['ordinal']])
    gaps = [
        {'id':'L04-X01','state':'pending_review','scope':'published_reference','detail':'Published Florida sets reconcile mechanically; independent scoped population/data/source-use acceptance has not occurred.','consequence':'Research lookup works; accepted consumer mode remains held.'},
        {'id':'L04-X02','state':'resolved_for_snapshot','scope':'premium_basis','detail':'For this 2026 snapshot, all ten monthly PREMIUM values agree numerically with landscape standard totals. Eight differ from the separately published subsidy-adjusted amounts. These expected basis differences are not source conflicts.','unexpected_standard_premium_difference_ids':sorted({r['offering_id'] for r in comparison_rows if r['status']=='different_basis_unresolved'}),'different_standard_and_lis_ids':sorted({r['offering_id'] for r in comparison_rows if r['status']=='expected_basis_difference'}),'consequence':'Retain standard and subsidy-adjusted amounts separately; do not infer a personal subsidy or carry this observed mapping into another release without validation.'},
        {'id':'L04-X03','state':'partial','scope':'carrier_corroboration','detail':'Official carrier SB tables corroborate five plans. Wellcare and UHC STOPs persist; an exact official Aetna document was not acquired.','affected_ids':sorted(keys-{r['offering_id'] for r in carrier_observations}),'consequence':'No plan is omitted. CMS-source validation is distinguished from carrier corroboration.'},
        {'id':'L04-X04','state':'outside_reference_scope','scope':'live_enrollment','detail':'Annual sanction flags are preserved as published. A complete effective-dated status history and live enrollment confirmation are not established.','consequence':'No enroll-now or whole-calendar-year availability claim.'},
        {'id':'L04-X05','state':'outside_reference_scope','scope':'personal_applicability','detail':'Compatibility, subsidy eligibility, drug coverage, pharmacy networks, personal prices and recommendations remain separate layers.','consequence':'No personal eligibility, total-cost or recommendation claim.'},
        {'id':'L04-X06','state':'source_format_limit','scope':'corroboration','detail':'PBP JSON has no premium fields and provides explicit deductible amounts for only five of these ten plans. Conditional fields remain raw; missing amounts are not imputed.','consequence':'PBP monetary consistency is claimed only for the five explicit amounts.'},
        {'id':'L04-X07','state':'source_coverage_limit','scope':'field_corroboration','detail':'Every modeled field is checked against the primary landscape. Some have no direct second-source comparison; source-copy fidelity does not establish independent corroboration.','primary_only_field_keys':sorted({r['field'] for r in field_coverage if not r['cross_source_observations']}),'consequence':'Inspect field-coverage.json for the evidence and remaining corroboration limits for each plan and field.'}
    ]
    write(out/'gaps.json',gaps)
    for name in ('field-map.json','scope.json','carrier-observations.json'):
        shutil.copyfile(BASE/name,out/name)
    for table, order in [('catalog','ordinal'),('ledger','source,ordinal'),('secondary','source,ordinal'),('comparisons','offering_id,source,field'),('counties','fips'),('quarantine','source,ordinal')]:
        export(db,out/(table+'.csv'),table,order)
    db.close()
    (out/'code').mkdir()
    for name in CODE:
        shutil.copyfile(ROOT/'cms-slice/scripts'/name,out/'code'/name)
    manifest = {'schema':'l04-build/1','package_id':'L04-PUBLISHED-FL-2026-'+out.name,'year':2026,'state':'FL','region':'11',
                'files_sha256':{str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()},
                'evidence':artifacts,'code_sha256':{n:digest(ROOT/'cms-slice/scripts'/n) for n in CODE},
                'source_review_after_utc':scope['source_review_after_utc'],'review':'pending','consumer_enabled':False}
    write(out/'manifest.json',manifest)
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--acquisition',type=Path,default=BASE/'acquisition-r1')
    args = parser.parse_args()
    result = build(args.out,args.acquisition)
    print(json.dumps({k:result[k] for k in ('observed_fl_offerings','observed_fl_contracts','national_pdp_rows','quarantine_count','observed_set_agrees_pbp_monthly')},indent=2))
