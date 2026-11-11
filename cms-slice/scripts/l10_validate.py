"""Independent L10 source audit. Does not import the builder or its parsers."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'


def digest(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text())


def cents(value):
    if value is None: return None
    n = Decimal(str(value).replace(',', '').replace('$', ''))
    assert n.is_finite() and n >= 0 and n == n.quantize(Decimal('.01'))
    return int(n * 100)


def poppler(path, page, mode='-layout'):
    return subprocess.run(['pdftotext', '-f', str(page), '-l', str(page), mode, str(path), '-'],
                          check=True, capture_output=True, text=True).stdout


def validate(package):
    package = Path(package).resolve(); manifest = read(package / 'manifest.json')
    assert manifest['schema'] == 'l10-build/1' and manifest['year'] == 2026
    assert manifest['human_acceptance'] is None and manifest['consumer_release_enabled'] is False
    assert manifest['full_l10_complete'] is False and manifest['research_only'] is True
    assert (package / 'SEALED').read_text().strip() == digest(package / 'manifest.json')
    for rel, expected in manifest['files_sha256'].items():
        path = (package / rel).resolve(); assert path.is_relative_to(package) and digest(path) == expected
    for group in ['input_sha256', 'code_sha256']:
        for rel, expected in manifest[group].items():
            path = (ROOT / rel).resolve(); assert path.is_relative_to(ROOT) and digest(path) == expected
    sources = read(package / 'sources.json')
    for sid, s in sources.items():
        raw = ROOT / s['path']; receipt = ROOT / s['receipt']
        assert digest(raw) == s['sha256'] and raw.stat().st_size == s['bytes']
        assert digest(receipt) == s['receipt_sha256'] and read(receipt)['source_id'] == sid
    def raw(sid, floats=False):
        return json.loads((ROOT / sources[sid]['path']).read_text(), parse_float=str) if floats else read(ROOT / sources[sid]['path'])
    acq = BASE / 'acquisition-r1'
    queries = read(acq / 'irfs-index.json')['partitions']
    used = [x for x in queries if x['used']]
    # Every year is covered by a complete annual query or all twelve months.
    for year in range(2001, 2027):
        parts = [p['partition'] for p in used if p['partition'].startswith(str(year))]
        assert parts == [str(year)] or set(parts) == {f'{year}-{m:02}' for m in range(1, 13)}
    expected_metadata = []
    associations = defaultdict(set)
    for p in used:
        sid = p['receipt'][:-5]; data = raw(sid)['Data']
        assert len(data) == p['row_count'] and len(data) < 1000
        fields = json.loads(sources[sid]['inputs']['criteria'])
        first = datetime.fromisoformat(fields['fileDtFrom']); last = datetime.fromisoformat(fields['fileDtTo'])
        for i, r in enumerate(data):
            assert first <= datetime.strptime(r['FileDt'], '%m/%d/%Y') <= last
            expected_metadata.append((f'{sid}:{i}', sid, f'/Data/{i}', r))
            if r['NaicCoCd']: associations[r['CoNm']].add(r['NaicCoCd'])
    with (package / 'filing-metadata.jsonl').open() as f:
        actual = [json.loads(line) for line in f]
    assert len(actual) == len(expected_metadata)
    for row, expected in zip(actual, expected_metadata):
        identity, sid, pointer, native = expected
        assert row == {'id': identity, 'source_id': sid, 'source_pointer': pointer,
                       'source_native': native, 'current_collier_sale': 'unknown'}
    detail_index = read(acq / 'irfs-details-index.json')['filings']
    expected_details = [(x['receipt'][:-5], raw(x['receipt'][:-5])) for x in detail_index if 'receipt' in x]
    details = read(package / 'filing-details.json')
    assert len(details) == len(expected_details)
    for r, (sid, native) in zip(details, expected_details):
        assert r == {'source_id': sid, 'source_native': native,
                     'current_sale': 'not_established', 'filed_rate_pages': 'not_obtained'}
    leads = read(package / 'product-form-leads.json')
    expected_leads = []
    for sid, d in expected_details:
        for co in d.get('Companies') or []:
            for form in d.get('Forms') or [None]:
                expected_leads.append((sid, d['FileLogNumber'], co['CoNm'], co['NaicCoCd'], d.get('ProdNm'), form))
    assert len(leads) == len(expected_leads)
    for lead, e in zip(leads, expected_leads):
        assert (lead['source_id'], lead['file_log_number'], lead['company_name_raw'], lead['naic_raw'], lead['product_type_raw'], lead['form_raw']) == e
        assert lead['standardized_variant'] is None and lead['listing_join'] is None and lead['current_collier_sale'] == 'unknown'
    # Source-listed geography and synthetic extent, not postal/all-market proof.
    zips = {x['zipcodE_DS'] for x in raw('choices-collier-zips')}
    assert len(zips) == 25
    grid = read(acq / 'choices-index.json')['captures']
    assert len(grid) == 500 and len({x['receipt'] for x in grid}) == 500
    expected_combinations = {(z, a, g, t) for z in zips for a in ['0-64', '65', '70', '75', '80'] for g in ['f', 'm'] for t in ['o', 's']}
    combinations = set(); observations = 0; display_cells = 0; not_displayed = 0
    listing_counts = Counter(); listing_zips = defaultdict(set); listing_ages = defaultdict(set)
    company_counts = Counter()
    with sqlite3.connect(f'file:{package}/inventory.sqlite3?mode=ro', uri=True) as db, (package / 'illustrations.jsonl').open() as f:
        for entry in grid:
            sid = entry['receipt'][:-5]; payload = raw(sid, True); inputs = sources[sid]['inputs']
            combinations.add((inputs['zipCode'], inputs['age'], inputs['gender'], inputs['smoker']))
            assert inputs['effectiveDate'] == '11/01/2026'
            assert inputs['insuranceType'] == '0' and inputs['groupCode'] == 'B'
            by_id = {str(r['ratE_ID']): r for r in payload['rates']}; shown = set()
            for d in payload['rateDisplays']:
                for key, link in d.items():
                    if not key.endswith('url') or link is None: continue
                    if key == 'companyUrl': continue
                    assert str(link) in by_id
                    prefix = key[:-3]
                    assert cents(d[prefix + 'value']) == cents(by_id[str(link)]['ratE_AM'])
                    shown.add(str(link)); display_cells += 1
            not_displayed += len(set(by_id) - shown)
            for i, native in enumerate(payload['rates']):
                row = json.loads(next(f)); identity = f'{sid}:{i}'
                assert row['id'] == identity and row['source_id'] == sid and row['source_pointer'] == f'/rates/{i}'
                assert row['source_native'] == native and row['synthetic_inputs'] == inputs
                assert row['source_rate_id'] == str(native['ratE_ID']) and row['annual_premium_cents'] == cents(native['ratE_AM'])
                assert row['unit'] == 'USD/year' and row['price_basis'] == 'illustrative_public_comparison'
                assert row['actual_rate_effective_date'] is None and row['policy_form'] is None and row['personal_quote'] is False
                assert row['fee_inclusion'] == 'unknown'
                assert row['amount_state'] == ('unknown' if native['ratE_AM'] is None else 'value')
                assert row['displayed_by_source_grid'] == (str(native['ratE_ID']) in shown)
                assert native['zipcodE_DS'] == inputs['zipCode'] and native['agE_CD'] == inputs['age']
                assert native['seX_CD'] in [inputs['gender'], 'n']
                key_names = ['companY_NM', 'plaN_CD', 'inS_TYPE_ID', 'grouP_CD', 'ratinG_CLASS_NM', 'eligibilitY_DS',
                             'policY_FEE_AM', 'policY_FEE_ASSESSED_CD', 'guaranteeD_ISSUE_CD', 'marketinG_METHOD_CD']
                key = {k: native.get(k) for k in key_names}
                lid = 'L10-' + hashlib.sha256(json.dumps(key, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()[:20]
                assert row['listing_id'] == lid
                assert json.loads(db.execute('SELECT payload FROM illustrations WHERE id=?', (identity,)).fetchone()[0]) == row
                listing_counts[lid] += 1; listing_zips[lid].add(inputs['zipCode']); listing_ages[lid].add(inputs['age'])
                company_counts[native['companY_NM']] += 1; observations += 1
        assert f.readline() == ''
        assert db.execute('SELECT count(*) FROM illustrations').fetchone()[0] == observations
        assert db.execute('SELECT count(*) FROM filing_metadata').fetchone()[0] == len(expected_metadata)
    assert combinations == expected_combinations
    listings = read(package / 'source-listings.json')
    ledger = read(package / 'required-coverage-ledger.json')
    assert ledger['universe']['complete_2026_effective_Collier_denominator'] is False
    assert {x['listing_id'] for x in ledger['listings']} == {x['id'] for x in listings}
    assert all(x['status'] == 'open' and x['required'] is True for x in ledger['listings'])
    assert ledger['internal_work_remaining'] and ledger['not_waived_by_mvp']
    assert {x['id'] for x in listings} == set(listing_counts)
    for x in listings:
        assert x['observations'] == listing_counts[x['id']] and set(x['observed_zips']) == listing_zips[x['id']]
        assert set(x['observed_age_classes']) == listing_ages[x['id']]
        name = x['source_listing_key']['companY_NM']; codes = associations[name]
        assert x['naic'] == (next(iter(codes)) if len(codes) == 1 else None)
        assert x['policy_form'] is None and x['actual_rate_effective_date'] is None
        assert x['sale_status'] == 'not_independently_verified' and x['personal_eligibility'] == 'not_determined'
        assert x['source_ui_underwriting_label'] == {'y': 'Underwritten', 'n': 'Guarenteed Issue'}.get(x['raw_underwriting_code'], 'Unknown')
        assert x['source_ui_label_is_personal_right'] is False
        assert x['select'] == ('Select' in x['source_listing_key']['grouP_CD'])
    products = read(package / 'product-discovery-map.json')
    assert products['all_market_complete'] is False
    assert set(l for p in products['products'] for l in p['listing_ids']) == set(listing_counts)
    carrier_only = [p for p in products['products'] if not p['listing_ids']]
    assert {p['variant'] for p in carrier_only} == {'B', 'C', 'D', 'M'} and len(carrier_only) == 4
    assert all(p['select'] is True and p['sale_status'] == 'unknown' and p['complete_product_identity'] is False for p in carrier_only)
    # Independent Poppler bounding boxes verify all 90 base cells, including
    # visually offset C/F cells that table extractors can otherwise lose.
    benefit = read(package / 'standardized-benefits.json')
    pdf = ROOT / sources['oir-faq-2026']['path']
    xml = ET.fromstring(poppler(pdf, 12, '-bbox'))
    words = [(float(w.attrib['xMin']), float(w.attrib['yMin']), float(w.attrib['xMax']), float(w.attrib['yMax']), w.text or '')
             for w in xml.iter() if w.tag.endswith('word')]
    xs = [150, 186.7, 221.5, 257.8, 293.6, 348.5, 402.6, 437.6, 479.2, 516.4, 557.5]
    ys = [157.1, 258.7, 312.7, 339.2, 377.6, 416.0, 446.0, 473.5, 499.4, 538.3]
    col_names = ['A', 'B', 'D', 'G', 'K', 'L', 'M', 'N', 'C', 'F']
    b_names = ['part_a_hospital', 'part_b_cost_sharing', 'blood_first_three_pints', 'part_a_hospice',
               'snf_coinsurance', 'part_a_deductible', 'part_b_deductible', 'part_b_excess', 'foreign_emergency']
    expected = {}
    for ri, name in enumerate(b_names):
        for ci, plan in enumerate(col_names):
            tokens = [t for x0, y0, x1, y1, t in words if xs[ci] < (x0+x1)/2 < xs[ci+1] and ys[ri] < (y0+y1)/2 < ys[ri+1]]
            expected[(plan, name)] = ''.join(tokens)
    assert len(benefit['cells']) == 108 and len(benefit['plans']) == 12
    for row in benefit['cells']:
        token = expected[(row['variant'].rstrip('*'), row['benefit'])]
        assert ''.join(row['source_cell_raw'].split()) == token
        assert row['included'] == bool(token)
        assert row['share_of_standard_benefit_percent'] == (50 if token == '50%' else 75 if token == '75%' else 100 if token else 0)
        if row['variant'].endswith('*'): assert 'high-deductible' in row['condition_ids']
        if row['variant'] in ['C', 'F', 'F*']: assert 'pre-2020' in row['condition_ids']
        if row['benefit'] == 'foreign_emergency' and row['included']: assert 'foreign' in row['condition_ids']
    conditions = {c['id']: c for c in benefit['conditions']}
    p2 = poppler(pdf, 2); p12 = poppler(pdf, 12)
    assert '$8,000' in p2 and '$4,000' in p2 and '$2,950' in p12 and '$283' in p2
    assert 'inpatient admission' in p12 and 'Part B deductible toward meeting' in p12
    assert conditions['foreign']['values'] == {'first_trip_days': 60, 'covered_charge_percent': 80, 'separate_deductible_cents': 25000, 'lifetime_limit_cents': 5000000}
    assert conditions['kl-limits']['values']['part_b_deductible_also_required'] is True
    assert conditions['n-copays']['values'] == {'office_max_cents': 2000, 'er_max_cents': 5000, 'er_inpatient_exception': True}
    expected_values = {
        'covered-scope': {}, 'hospital': {'additional_lifetime_days': 365, 'days_61_90_daily_cents': 43400, 'lifetime_reserve_daily_cents': 86800},
        'part-b-deductible': {'annual_part_b_deductible_cents': 28300},
        'snf': {'first_day': 21, 'last_day': 100, 'daily_coinsurance_cents': 21700},
        'kl-limits': {'K_annual_limit_cents': 800000, 'L_annual_limit_cents': 400000, 'part_b_deductible_also_required': True},
        'high-deductible': {'annual_plan_deductible_cents': 295000, 'part_b_counts_toward_threshold': True, 'separate_foreign_deductible_covered': False},
        'pre-2020': {'first_eligible_before': '2020-01-01'}, 'select': {},
        'part-a-deductible': {'per_benefit_period_cents': 173600}}
    for cid, values in expected_values.items(): assert conditions[cid]['values'] == values
    assert all(c['acceptance'] == 'pending' and c['source_id'] == 'oir-faq-2026' for c in conditions.values())
    for plan in benefit['plans']:
        assert plan['annual_plan_deductible_cents'] == (295000 if plan['variant'].endswith('*') else None)
        assert plan['standardized_annual_oop_limit_cents'] == {'K': 800000, 'L': 400000}.get(plan['variant'])
        assert plan['first_eligible_before'] == ('2020-01-01' if plan['variant'] in ['C', 'F', 'F*'] else None)
    # Carrier rate cells independently extracted as text rows, not tables.
    tables = read(package / 'carrier-table-observations.json'); checked = 0
    carrier_expected = {}
    for sid in ['florida-blue-standard-2026', 'florida-blue-select-2026']:
        path = ROOT / sources[sid]['path']
        columns = ['Plan A', 'Plan B', 'Plan C', 'Plan D', 'Plan F', 'Plan G', 'Plan K', 'Plan L', 'Plan M', 'Plan N'] if 'standard' in sid else ['Plan A', 'Plan C', 'Plan F', 'Select B', 'Select C', 'Select D', 'Select M']
        for page in range(8, 12):
            text = poppler(path, page); assert 'Collier' in text and 'Area 2' in text
            lines = []
            for line in text.splitlines():
                match = re.match(r'^\s*(Under 65|6[5-9]|70-71|72-74|75-79|80\+)\s{2,}(.*)$', line)
                if match:
                    # Large under-65 currency cells can have a single space
                    # between columns in Poppler text; parse numeric tokens.
                    lines.append([match[1]] + re.findall(r'\$?[\d,]+\.\d{2}', match[2]))
            assert len(lines) == 10
            for ri, line in enumerate(lines, 1):
                assert len(line) == len(columns) + 1
                for ci, header in enumerate(columns, 1):
                    carrier_expected[(sid, page, ri, ci)] = (line[0], header, cents(line[ci]))
    for row in tables:
        e = carrier_expected.pop((row['source_id'], row['page'], row['table_row'], row['table_column']))
        assert (row['age_band_raw'], row['header_raw'], row['premium_cents']) == e
        assert row['select'] == row['header_raw'].startswith('Select')
        assert row['unit'] == 'USD/month' and row['personal_quote'] is False and row['filed_table_reproduction'] is False
        assert row['actual_filed_rate_effective_date'] is None and row['policy_form'] is None
        assert row['county_fips'] == '12021' and row['rating_area'] == 'Area 2' and row['source_edition_year'] == 2026
        assert row['tobacco'] == ('non-tobacco' if row['page'] in [8, 10] else 'tobacco')
        assert row['payment_basis'] == ('automatic_payment_option' if row['page'] >= 10 else 'regular_monthly')
        checked += 1
    assert checked == 680 and not carrier_expected
    coverage = read(package / 'coverage.json')
    assert coverage['illustrative_observations'] == observations and coverage['filing_metadata_rows'] == len(expected_metadata)
    assert coverage['source_display_cells_checked'] == display_cells and coverage['raw_observations_not_in_grid'] == not_displayed
    assert coverage['listing_variants'] == len(listings) and coverage['choices_company_names'] == len(company_counts)
    assert coverage['complete_all_market_2026_denominator'] is False and coverage['verified_filed_rate_models'] == 0
    assert all(g['state'] == 'open' and g['required'] for g in read(package / 'gaps.json')['gaps'])
    preserved = read(BASE / 'preservation-before.json')
    assert all(digest(ROOT / rel) == expected for rel, expected in preserved.items())
    return {'schema': 'l10-independent-validation/1', 'passed': True,
            'manifest_sha256': digest(package / 'manifest.json'), 'source_files_checked': len(sources),
            'choices_scenarios_checked': len(grid), 'illustrative_rows_checked': observations,
            'filing_metadata_rows_checked': len(expected_metadata), 'filing_details_checked': len(details),
            'source_display_cells_checked': display_cells, 'raw_omitted_display_rows_preserved': not_displayed,
            'standardized_cells_checked': 108, 'carrier_table_cells_checked': checked,
            'protected_files_unchanged': len(preserved), 'unexplained_modeled_value_mismatches': 0,
            'human_acceptance': None, 'consumer_release_enabled': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('package', type=Path); p.add_argument('--out', type=Path)
    args = p.parse_args(); result = validate(args.package)
    if args.out: args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))
