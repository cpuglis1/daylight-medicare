"""Independent raw-source audit. Does not import/call the builder or its parser.

Expected sets and values are reconstructed directly from pinned source bytes.
Hash integrity, semantic fidelity and cross-source agreement are separate results.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/data/l04-pdp-availability-2026-10-25'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def source_rows(path, suffix, delimiter=',', encoding='utf-8-sig'):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(suffix)]
        if len(names) != 1:
            raise ValueError('Expected one unambiguous source table')
        name = names[0]
        raw = archive.read(name)
    parsed = csv.reader(io.StringIO(raw.decode(encoding),newline=''),delimiter=delimiter)
    header = next(parsed)
    return name,hashlib.sha256(raw).hexdigest(),header,[(i,dict(zip(header,row))) for i,row in enumerate(parsed,2)]


def key(year,contract,plan,segment):
    return f'{int(year):04d}:{contract}:{int(plan):03d}:{int(segment):03d}'


def cents(raw):
    # Independent integer arithmetic, including the actual negative component.
    value = raw.strip()
    if value in ('','Not Applicable','Not Available'):
        return None
    negative = value.startswith('(') or value.startswith('-')
    text = value.replace('$','').replace(',','').strip('()-')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?',text):
        raise ValueError('Unexpected source currency')
    whole,_,fraction = text.partition('.')
    result = int(whole)*100+int((fraction+'00')[:2])
    return -result if negative else result


def expected_fact(raw,field):
    stripped = raw.strip()
    states = {'':'missing','Not Applicable':'not_applicable','Not Available':'unavailable'}
    state = states.get(stripped,'published')
    value = None
    if state == 'published':
        kind = field['type']
        if kind in ('money_annual','money_monthly'):
            value = cents(raw)
        elif kind == 'year':
            value = int(stripped)
        elif kind == 'id3':
            value = f'{int(stripped):03d}'
        elif kind == 'region':
            value = f'{int(stripped):02d}'
        else:
            value = stripped
    return {'raw':raw,'value':value,'state':state,'unit':field['unit'],'basis':field['source_column'],
            'value_encoding':'integer_cents' if field['type'] in ('money_annual','money_monthly') else 'literal'}


def validate(package, output=None):
    package = Path(package).resolve()
    manifest, mapping = read(package/'manifest.json'),read(package/'field-map.json')
    checks, failures = Counter(),[]
    def check(condition,label,context=None):
        checks[label] += 1
        if not condition:
            checks['FAILED'] += 1
            if len(failures) < 100:
                failures.append({'check':label,'context':context})
    for relative,digest in manifest['files_sha256'].items():
        path = (package/relative).resolve()
        check(path.is_relative_to(package) and path.is_file() and sha(path) == digest,'output_hash',relative)
    for name,artifact in manifest['evidence'].items():
        path = (ROOT/artifact['path']).resolve()
        check(path.is_relative_to(ROOT) and path.is_file() and path.stat().st_size == artifact['bytes'] and sha(path) == artifact['sha256'],'source_hash',name)
    for name,digest in manifest['code_sha256'].items():
        check(sha(ROOT/'cms-slice/scripts'/name) == digest,'implementation_hash',name)
    check(mapping == read(BASE/'field-map.json'),'declared_field_contract')
    check(read(package/'scope.json') == read(BASE/'scope.json'),'declared_scope_contract')
    evidence = manifest['evidence']
    sources = read(package/'source-manifest.json')
    member_metadata = read(package/'source-members.json')
    db = sqlite3.connect(f'file:{package}/inventory.sqlite3?mode=ro',uri=True)
    db.row_factory = sqlite3.Row
    _,landscape_hash,headers,landscape = source_rows(ROOT/evidence['landscape']['path'],'.csv')
    check(landscape_hash == member_metadata['landscape']['sha256'],'landscape_member_hash')
    catalog = {r['ordinal']:dict(r) for r in db.execute('SELECT * FROM catalog')}
    ledger = {(r['source'],r['ordinal']):dict(r) for r in db.execute('SELECT * FROM ledger')}
    expected_pdp,expected_fl,route_counts = {},{},Counter()
    primary_facts,national_facts = 0,0
    for ordinal,row in landscape:
        identity = key(row['Contract Year'],row['Contract ID'],row['Plan ID'],row['Segment ID'])
        route = 'employer_group_excluded' if int(row['Plan ID']) >= 800 else 'L04' if row['Contract Category Type'] == 'PDP' else 'other_layer'
        route_counts[route] += 1
        actual = ledger.get(('landscape',ordinal),{})
        check((actual.get('offering_id'),actual.get('route'),actual.get('category'),actual.get('state'),actual.get('region')) == (identity,route,row['Contract Category Type'],row['State Territory Abbreviation'],row['PDP Region Code']),'whole_landscape_routing',ordinal)
        if route != 'L04':continue
        expected_pdp[ordinal] = row
        stored = catalog.get(ordinal,{})
        check(bool(stored),'pdp_row_present',ordinal)
        region = f"{int(row['PDP Region Code']):02d}"
        check((stored.get('offering_id'),stored.get('region'),stored.get('state')) == (identity,region,row['State Territory Abbreviation']),'pdp_identity_geography',ordinal)
        check(json.loads(stored.get('raw_json','{}')) == row,'all_raw_landscape_columns_preserved',ordinal)
        expected_values = {f['key']:expected_fact(row[f['source_column']],f) for f in mapping['fields']}
        actual_values = json.loads(stored.get('fields_json','{}'))
        check(set(actual_values) == set(expected_values),'modeled_field_set',ordinal)
        for name,value in expected_values.items():
            check(actual_values.get(name) == value,'modeled_field_semantics',{'ordinal':ordinal,'field':name})
            national_facts += 1
        expected_locator = {'source':'landscape','member':member_metadata['landscape']['member'],'member_sha256':landscape_hash,'record_ordinal':ordinal}
        check(json.loads(stored.get('locator_json','{}')) == expected_locator,'primary_locator',ordinal)
        if region == '11' and row['State Territory Abbreviation'] == 'FL':
            check(row['County Name'] == 'All Counties','florida_statewide_label',identity)
            expected_fl[identity] = {'offering_id':identity,'region':region,'state':'FL','ordinal':ordinal,'fields':expected_values,'source':expected_locator}
            primary_facts += len(expected_values)
    check(set(catalog) == set(expected_pdp),'whole_pdp_population_rows')
    check(len({r['offering_id'] for r in catalog.values() if r['region']=='11' and r['state']=='FL'}) == len(expected_fl),'no_fl_identity_omissions_or_duplicates')
    secondary = {(r['source'],r['ordinal']):dict(r) for r in db.execute('SELECT * FROM secondary')}
    secondary_expected = set()
    secondary_field_checks = Counter()
    pbp_fl,pbp_national,pbp_group_fl,pbp_chars,pbp_deductibles = set(),set(),set(),{},{}
    pbp_count = 0
    with zipfile.ZipFile(ROOT/evidence['pbp']['path']) as archive:
        for ordinal,name in enumerate(sorted(archive.namelist()),1):
            if not name.startswith('S') or not name.endswith('.json'):continue
            pbp_count += 1
            raw = archive.read(name)
            payload = json.loads(raw)
            p = payload['pbp'][0]
            identity = key(payload['contractYear'],p['contractId'],p['planId'],p['segmentId'])
            original = p['planCharacteristics']
            individual = original['isEmployerOnlyPlan'] == 'No' and int(p['planId']) < 800
            disposition = 'individual_pdp' if individual else 'employer_group_excluded'
            if individual:
                pbp_national.add(identity)
                if original['geographicName'] in ('Florida','State of Florida'):pbp_fl.add(identity)
            elif 'Florida' in original['geographicName']:pbp_group_fl.add(identity)
            stored = secondary.get(('pbp',ordinal),{})
            secondary_expected.add(('pbp',ordinal))
            check(stored.get('offering_id') == identity and stored.get('disposition') == disposition,'pbp_identity_population',name)
            check(json.loads(stored.get('raw_json','{}')) == original,'pbp_all_retained_characteristics',name)
            secondary_field_checks['pbp_characteristic_values'] += len(original)
            loc = json.loads(stored.get('locator_json','{}'))
            check(loc == {'source':'pbp','member':name,'member_sha256':hashlib.sha256(raw).hexdigest(),'json_pointer':'/pbp/0/planCharacteristics'},'pbp_locator',name)
            if identity in expected_fl:
                pbp_chars[identity] = original
                details = p['rx']['rxDetails']['rxSetup']['rxCostShare']['rxCostShareDetails']
                secondary_expected.add(('pbp-rx',ordinal))
                stored_rx = secondary.get(('pbp-rx',ordinal),{})
                check(json.loads(stored_rx.get('raw_json','{}')) == details,'pbp_all_retained_cost_share_details',name)
                secondary_field_checks['pbp_rx_raw_values'] += len(details)
                expected_rx_locator = {'source':'pbp-rx','member':name,'member_sha256':hashlib.sha256(raw).hexdigest(),'json_pointer':'/pbp/0/rx/rxDetails/rxSetup/rxCostShare/rxCostShareDetails'}
                check(json.loads(stored_rx.get('locator_json','{}')) == expected_rx_locator,'pbp_rx_locator',name)
                if details.get('costShareDeductibleAmount') is not None:
                    pbp_deductibles[identity] = cents(details['costShareDeductibleAmount'])
    monthly_fl,monthly_national,puf_by_key,puf_geo = set(),set(),{},{}
    monthly_counts = {}
    for member in sources['monthly']['members']:
        _,raw_hash,header,rows = source_rows(ROOT/member['path'],'.txt','|','cp1252')
        is_plan = 'plan information' in member['name']
        label = 'monthly-plan' if is_plan else 'monthly-geo'
        check(raw_hash == member_metadata[label]['sha256'],'monthly_inner_member_hash',label)
        monthly_counts[label] = len(rows)
        # Verify the retained public HTTP compressed block against the complete
        # selected ZIP member; deliberately no whole-archive hash claim.
        block = (ROOT/member['compressed_block']['path']).read_bytes()
        info = struct.unpack_from('<4s5H3I2H',block)
        compressed = block[30+info[-2]+info[-1]:]
        recovered = zlib.decompress(compressed,-15) if info[3] == 8 else compressed
        check(hashlib.sha256(recovered).hexdigest() == member['sha256'] and f'{zlib.crc32(recovered):08x}' == member['crc32'],'http_range_member_chain',member['name'])
        for ordinal,row in rows:
            if is_plan and not row['CONTRACT_ID'].startswith('S'):continue
            secondary_expected.add((label,ordinal))
            stored = secondary.get((label,ordinal),{})
            check(json.loads(stored.get('raw_json','{}')) == row,'monthly_all_source_columns',{'source':label,'ordinal':ordinal})
            secondary_field_checks[label+'_raw_values'] += len(row)
            locator = json.loads(stored.get('locator_json','{}'))
            check(locator == {'source':label,'member':member_metadata[label]['member'],'member_sha256':raw_hash,'record_ordinal':ordinal},'monthly_locator',{'source':label,'ordinal':ordinal})
            if is_plan:
                identity = key(2026,row['CONTRACT_ID'],row['PLAN_ID'],row['SEGMENT_ID'])
                region = f"{int(row['PDP_REGION_CODE']):02d}"
                individual = int(row['PLAN_ID']) < 800
                check(stored.get('offering_id') == identity and stored.get('region') == region and stored.get('disposition') == ('individual_pdp' if individual else 'employer_group_excluded'),'monthly_population_and_region',identity)
                if individual:
                    monthly_national.add(identity)
                    if region == '11':
                        monthly_fl.add(identity)
                        check(identity not in puf_by_key,'monthly_fl_duplicate',identity)
                        puf_by_key[identity] = row
            else:
                puf_geo[row['COUNTY_CODE']] = (ordinal,row)
    area_fl,area_counts,area_crosswalk = {},{},{}
    for label in ('area-september','area-october'):
        _,raw_hash,header,rows = source_rows(ROOT/evidence[label]['path'],'.csv')
        check(raw_hash == member_metadata[label]['sha256'],'area_member_hash',label)
        area_counts[label] = len(rows)
        contracts = set()
        for ordinal,row in rows:
            if row['STCD'] != 'FL':continue
            secondary_expected.add((label,ordinal))
            stored = secondary.get((label,ordinal),{})
            check(json.loads(stored.get('raw_json','{}')) == row,'area_all_source_columns',{'source':label,'ordinal':ordinal})
            secondary_field_checks[label+'_raw_values'] += len(row)
            disposition = 'employer_group_excluded' if row['EGHP'] == '*' else 'contract_area_only'
            check(stored.get('offering_id') == row['Contract ID'] and stored.get('disposition') == disposition,'area_contract_population',{'source':label,'ordinal':ordinal})
            if row['EGHP'] != '*':
                contracts.add(row['Contract ID'])
                if row['FIPS']:
                    area_crosswalk.setdefault(row['FIPS'],set()).add((row['SSA'],row['COUNTY']))
        area_fl[label] = contracts
    check(set(secondary) == secondary_expected,'all_secondary_observations_accounted')
    expected_keys = set(expected_fl)
    check(expected_keys == pbp_fl == monthly_fl,'three_fl_published_sets_equal',{'landscape':len(expected_keys),'pbp':len(pbp_fl),'monthly':len(monthly_fl)})
    expected_contracts = {k.split(':')[1] for k in expected_keys}
    for label,contracts in area_fl.items():
        check(contracts == expected_contracts,'two_way_contract_service_area',label)
    census_path = ROOT/evidence['census-counties']['path']
    with zipfile.ZipFile(census_path) as archive:
        text = archive.read(next(n for n in archive.namelist() if n.endswith('.txt'))).decode()
    census = [r for r in csv.DictReader(io.StringIO(text),delimiter='|') if r['USPS'] == 'FL']
    counties = {r['fips']:dict(r) for r in db.execute('SELECT * FROM counties')}
    check(set(counties) == {r['GEOID'] for r in census},'whole_fl_county_denominator')
    for county in census:
        fips = county['GEOID']
        pair = area_crosswalk.get(fips,set())
        check(len(pair) == 1,'unique_fips_ssa_relationship',fips)
        if len(pair) != 1:continue
        ssa,name = next(iter(pair))
        ordinal,original = puf_geo[ssa]
        stored = counties.get(fips,{})
        check((stored.get('fips'),stored.get('state'),stored.get('name'),stored.get('ssa'),stored.get('region')) == (fips,'FL',county['NAME'],ssa,original['PDP_REGION_CODE']),'county_source_relationship',fips)
        check(original['PDP_REGION_CODE'] == '11' and original['STATENAME'] == 'Florida' and original['COUNTY'] == name,'county_region_source_codes',fips)
        check(json.loads(stored.get('locator_json','{}')) == {'census_geoid':fips,'area_sources':['area-september','area-october'],'monthly_geo_ordinal':ordinal},'county_relationship_locator',fips)
    # Exact checks for every derived comparison, independent of builder logic.
    expected_comparisons = {}
    def add(k,s,f,a,b,state):
        expected_comparisons[k,s,f] = (a,b,state)
    math = []
    for identity,record in expected_fl.items():
        values = record['fields']
        add(identity,'pbp','identity',identity,identity if identity in pbp_fl else None,'agrees' if identity in pbp_fl else 'missing')
        add(identity,'monthly-plan','identity',identity,identity if identity in monthly_fl else None,'agrees' if identity in monthly_fl else 'missing')
        original = pbp_chars[identity]
        for field,other in [('plan_name','planName'),('contract_name','contractLegalName'),('marketing_name','organizationMarketingName'),('drug_coverage','isOfferRx'),('category','organizationType')]:
            a,b = values[field]['value'],original.get(other)
            add(identity,'pbp',field,a,b,'agrees' if a == b else 'conflict')
        if identity in pbp_deductibles:
            a,b = values['annual_deductible']['value'],pbp_deductibles[identity]
            add(identity,'pbp-rx','annual_deductible',a,b,'agrees' if a == b else 'conflict')
        raw = puf_by_key[identity]
        for field,other in [('plan_name','PLAN_NAME'),('contract_name','CONTRACT_NAME'),('pdp_region_code','PDP_REGION_CODE')]:
            a,b = values[field]['value'],raw[other].strip()
            add(identity,'monthly-plan',field,a,b,'agrees' if a == b else 'conflict')
        for field,column in [('annual_deductible','DEDUCTIBLE'),('total_premium','PREMIUM')]:
            a,b = values[field]['value'],cents(raw[column])
            add(identity,'monthly-plan',field,a,b,'agrees' if a == b else 'different_basis_unresolved' if field == 'total_premium' else 'conflict')
        a,b = values['low_income_beneficiary_premium']['value'],cents(raw['PREMIUM'])
        add(identity,'monthly-plan','premium_equals_published_lis_observation',a,b,'numeric_agreement_distinct_basis' if a == b else 'expected_basis_difference')
        for label,contracts in area_fl.items():
            c = identity.split(':')[1]
            add(identity,label,'contract_area',c,c if c in contracts else None,'agrees' if c in contracts else 'missing')
        basic,supplemental,total = [values[k]['value'] for k in ('basic_premium','supplemental_premium','total_premium')]
        check(basic+supplemental == total,'fl_premium_components_sum',identity)
        math.append({'offering_id':identity,'basic_cents':basic,'supplemental_cents':supplemental,'total_cents':total})
    carrier_checks = []
    for observation in read(package/'carrier-observations.json'):
        source,identity,page = observation['source'],observation['offering_id'],observation['pdf_page']
        pdf = ROOT/evidence[source]['path']
        process = subprocess.run(['pdftotext','-f',str(page),'-l',str(page),'-layout',str(pdf),'-'],capture_output=True,check=True)
        text = process.stdout.decode()
        lines = text.splitlines()
        premium_line = next(line for line in lines if re.search('Monthly [Pp]lan [Pp]remium',line))
        deductible_at = next(i for i,line in enumerate(lines) if ('Pharmacy (Part D) deductible' in line if source.startswith('humana') else line.strip().startswith('Deductible')))
        premium_amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?',premium_line)
        if source.startswith('humana'):
            deductible_amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?',' '.join(lines[deductible_at:deductible_at+2]))
            premium_value,deductible_value = cents(premium_amounts[0]),max(cents(v) for v in deductible_amounts)
            check(''.join(identity.split(':')[1:]) in text,'carrier_exact_segment_token',identity)
        else:
            column = 0 if identity.split(':')[2] == '001' else 1
            deductible_amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?',lines[deductible_at])
            premium_value,deductible_value = cents(premium_amounts[column]),cents(deductible_amounts[column])
            check(identity.split(':')[1]+'-'+identity.split(':')[2] in text,'carrier_plan_token',identity)
        expected = {'total_premium':premium_value,'annual_deductible':deductible_value}
        check(expected == observation['values_cents'],'carrier_table_transcription',identity)
        check(sha(ROOT/observation['extracted_path']) == observation['extracted_sha256'] and sha(ROOT/observation['visual_path']) == observation['visual_sha256'],'carrier_extraction_and_visual_binding',identity)
        for field,value in expected.items():
            a = expected_fl[identity]['fields'][field]['value']
            add(identity,source,field,a,value,'agrees' if a == value else 'conflict')
        carrier_checks.append({'offering_id':identity,'source':source,'pdf_page':page,'values_cents':expected,'identity_grain':observation['identity_grain']})
    actual_comparisons = {}
    for row in db.execute('SELECT * FROM comparisons'):
        ident = (row['offering_id'],row['source'],row['field'])
        actual_comparisons[ident] = (json.loads(row['primary_json']),json.loads(row['secondary_json']),row['status'])
    check(set(actual_comparisons) == set(expected_comparisons),'comparison_set_complete')
    for ident,value in expected_comparisons.items():
        check(actual_comparisons.get(ident) == value,'derived_source_comparison',ident)
    # All CSV exports are checked cell-by-cell against SQLite; the Florida JSON
    # and the actual lookup projection are also checked against raw expectations.
    export_cells = 0
    for table,order in [('catalog','ordinal'),('ledger','source,ordinal'),('secondary','source,ordinal'),('comparisons','offering_id,source,field'),('counties','fips'),('quarantine','source,ordinal')]:
        with (package/(table+'.csv')).open(newline='') as stream:
            rows = list(csv.reader(stream))
        cursor = db.execute(f'SELECT * FROM {table} ORDER BY {order}')
        check(rows[0] == [c[0] for c in cursor.description],'export_header',table)
        actual_rows = list(cursor)
        check(len(rows)-1 == len(actual_rows),'export_row_count',table)
        for number,(exported,stored) in enumerate(zip(rows[1:],actual_rows),2):
            check(exported == ['' if x is None else str(x) for x in stored],'export_row_cells',{'table':table,'ordinal':number})
            export_cells += len(exported)
    expected_records = [expected_fl[k] for k in sorted(expected_fl)]
    check(read(package/'records.json') == expected_records,'florida_json_all_modeled_fields')
    with (package/'florida-pdp-reference.csv').open(newline='') as stream:
        flat = list(csv.reader(stream))
    expected_flat = [['offering_id']+[f['key']+('_cents' if f['type'].startswith('money_') else '') for f in mapping['fields']]+['source_record_ordinal']]
    for record in expected_records:
        expected_flat.append([record['offering_id']]+[str(record['fields'][f['key']]['value']) if record['fields'][f['key']]['state']=='published' else '['+record['fields'][f['key']]['state']+']' for f in mapping['fields']]+[str(record['ordinal'])])
    check(flat == expected_flat,'flat_csv_all_modeled_fields')
    from l04_reference import project
    for request in ({'year':2026,'state':'FL'},{'year':2026,'county_fips':'12021'},{'year':2026,'county_fips':'12071'},{'year':2026,'pdp_region':'11'}):
        check(project(request,package) == expected_records,'lookup_projection_all_modeled_fields',request)
    coverage = read(package/'coverage.json')
    check(coverage['observed_fl_offerings'] == len(expected_fl) and coverage['observed_fl_contracts'] == len(expected_contracts),'coverage_counts')
    check(coverage['primary_field_observations'] == primary_facts and coverage['primary_field_count_per_plan'] == len(mapping['fields']),'coverage_field_counts')
    check(coverage['whole_population_accounting']['landscape'] == {'raw':len(landscape),'parsed':len(landscape),'quarantined':0,'routes':dict(route_counts)},'source_row_accounting')
    check(coverage['whole_population_accounting']['pbp_s_contract_members']['raw'] == pbp_count,'pbp_member_accounting')
    check(coverage['pbp_explicit_deductible_plan_ids'] == sorted(pbp_deductibles),'pbp_explicit_amount_coverage')
    check(set(coverage['whole_population_accounting']['pbp_s_contract_members']['florida_group_exclusions']) == pbp_group_fl,'fl_group_exclusions_retained')
    for label,count in monthly_counts.items():
        check(coverage['whole_population_accounting'][label]['raw'] == count,'monthly_row_accounting',label)
    for label,count in area_counts.items():
        check(coverage['whole_population_accounting'][label]['raw'] == count,'area_row_accounting',label)
    check(db.execute('SELECT count(*) FROM quarantine').fetchone()[0] == coverage['quarantine_count'] == 0,'no_hidden_quarantine')
    check(coverage['expected_offering_count'] is None and coverage['consumer_reference_accepted'] is False,'no_self_awarded_acceptance')
    check(not coverage['missing_or_unavailable_primary_fields'] and not coverage['geography_gaps'],'no_unreported_fl_primary_gaps')
    gaps = {r['id']:r for r in read(package/'gaps.json')}
    premium_differences = {ident[0] for ident,value in expected_comparisons.items() if value[2]=='different_basis_unresolved'}
    carrier_ids = {r['offering_id'] for r in carrier_checks}
    check(set(gaps['L04-X02']['unexpected_standard_premium_difference_ids']) == premium_differences,'premium_gaps_match_source_differences')
    check(set(gaps['L04-X02']['different_standard_and_lis_ids']) == {k[0] for k,v in expected_comparisons.items() if v[2]=='expected_basis_difference'},'different_premium_bases_disclosed')
    material_rows = list(db.execute("SELECT * FROM comparisons WHERE status IN ('conflict','missing','different_basis_unresolved')"))
    check(coverage['material_source_differences'] == [dict(r) for r in material_rows],'only_material_conflicts_labeled_conflicts')
    check(set(gaps['L04-X03']['affected_ids']) == expected_keys-carrier_ids,'carrier_gaps_match_universe')
    expected_field_coverage = []
    for identity in sorted(expected_fl):
        record = expected_fl[identity]
        for field in mapping['fields']:
            related = [{'source':k[1],'field':k[2],'status':v[2]} for k,v in expected_comparisons.items() if k[0]==identity and (k[2]==field['key'] or field['key'] in ('year','contract_id','plan_id','segment_id') and k[2]=='identity')]
            expected_field_coverage.append({'offering_id':identity,'field':field['key'],'primary_source':{**record['source'],'source_column':field['source_column']},'primary_state':record['fields'][field['key']]['state'],'cross_source_observations':sorted(related,key=lambda x:(x['source'],x['field']))})
    check(read(package/'field-coverage.json') == expected_field_coverage,'all_field_evidence_coverage')
    check(gaps['L04-X07']['primary_only_field_keys'] == sorted({r['field'] for r in expected_field_coverage if not r['cross_source_observations']}),'single_source_fields_disclosed')
    column_ledger = read(package/'column-ledger.json')
    check([r['column'] for r in column_ledger] == headers,'all_landscape_columns_dispositioned')
    check({r['column'] for r in column_ledger if r['disposition']=='modeled'} == {f['source_column'] for f in mapping['fields']},'column_ledger_matches_field_map')
    national_keys = {key(r['Contract Year'],r['Contract ID'],r['Plan ID'],r['Segment ID']) for r in expected_pdp.values()}
    diffs = coverage['source_set_differences']
    for label,secondary_set,primary_set in [('florida_pbp',pbp_fl,expected_keys),('florida_monthly',monthly_fl,expected_keys),('national_pbp_individual_ids',pbp_national,national_keys),('national_monthly_individual_ids',monthly_national,national_keys),*[(label,contracts,expected_contracts) for label,contracts in area_fl.items()]]:
        check(diffs[label] == {'landscape_only':sorted(primary_set-secondary_set),'secondary_only':sorted(secondary_set-primary_set)},'two_way_set_difference_accuracy',label)
    failed = checks['FAILED']
    result = {'schema':'l04-independent-validation/1','manifest_sha256':sha(package/'manifest.json'),
              'source_fidelity_passed':failed == 0,'failed':failed,'failure_examples':failures,
              'checks_by_kind':dict(checks),'primary_field_observations_checked':primary_facts,
              'national_pdp_field_observations_checked':national_facts,'secondary_values_checked':dict(secondary_field_checks),
              'export_cells_checked':export_cells,'source_landscape_rows_accounted':len(landscape),
              'florida_offering_ids':sorted(expected_fl),'published_fl_sets':{'landscape':len(expected_fl),'pbp':len(pbp_fl),'monthly':len(monthly_fl)},
              'florida_counties_checked':len(census),'premium_component_checks':math,'carrier_checks':carrier_checks,
              'source_agreement_separate_from_fidelity':{'monthly_standard_premium_differences':sum(v[2]=='different_basis_unresolved' for v in expected_comparisons.values()),'expected_standard_vs_lis_basis_differences':sum(v[2]=='expected_basis_difference' for v in expected_comparisons.values()),'carrier_plan_count':len(carrier_checks),'independent_human_acceptance':False}}
    if output:
        Path(output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    db.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    result = validate(args.package,args.out or args.package.parent/(args.package.name+'-validation.json'))
    print(json.dumps({k:result[k] for k in ('source_fidelity_passed','failed','primary_field_observations_checked','national_pdp_field_observations_checked','published_fl_sets')},indent=2))
    raise SystemExit(1 if result['failed'] else 0)
