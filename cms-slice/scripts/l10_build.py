"""Build the additive 2026 Collier L10 research inventory from retained bytes.

Listings, filing metadata, standardized benefits and published carrier table
observations are deliberately different objects. None implies personal sale,
filed-rate reproduction, eligibility, acceptance or consumer release.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'
ACQ = BASE / 'acquisition-r1'
VARIANTS = ['A', 'B', 'C', 'D', 'F', 'F*', 'G', 'G*', 'K', 'L', 'M', 'N']
BENEFITS = ['part_a_hospital', 'part_b_cost_sharing', 'blood_first_three_pints',
            'part_a_hospice', 'snf_coinsurance', 'part_a_deductible',
            'part_b_deductible', 'part_b_excess', 'foreign_emergency']


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def compact(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def load(path):
    return json.loads(Path(path).read_text())


def source(sid):
    r = load(ACQ / (sid + '.json'))
    p = ACQ / 'raw' / r['sha256']
    if sha(p) != r['sha256'] or p.stat().st_size != r['bytes'] or r['http_status'] != 200:
        raise ValueError('Changed source ' + sid)
    return r, p


def money(value):
    if value is None:
        return None
    n = Decimal(str(value).replace('$', '').replace(',', '')) * 100
    if not n.is_finite() or n < 0 or n != n.to_integral_value():
        raise ValueError('Not an exact nonnegative cent value')
    return int(n)


def standardized():
    r, path = source('oir-faq-2026')
    with pdfplumber.open(path) as doc:
        table = doc.pages[11].extract_tables()[0]
        grouped = []
        for row in table[5:]:
            if row[0]:
                grouped.append([v or '' for v in row])
            else:
                for i, value in enumerate(row):
                    if value:
                        grouped[-1][i] += ('\n' if grouped[-1][i] else '') + value
        if len(grouped) != 10:
            raise ValueError('Standard chart row count changed')
        pages = [p.extract_text() for p in doc.pages]
    columns = ['A', 'B', 'D', 'G', 'K', 'L', 'M', 'N', 'C', 'F']
    base = []
    for ri, benefit in enumerate(BENEFITS):
        for ci, plan in enumerate(columns):
            cell = grouped[ri][ci + 1]
            if cell not in ['', '✔', '50%', '75%', '✔\ncopays\napply3']:
                raise ValueError('Unmodeled standard chart cell ' + repr(cell))
            base.append({'variant': plan, 'benefit': benefit, 'source_cell_raw': cell,
                         'included': bool(cell),
                         'share_of_standard_benefit_percent': 50 if cell == '50%' else 75 if cell == '75%' else 100 if cell else 0,
                         'source_id': r['source_id'], 'page': 12, 'table_row': ri + 1,
                         'table_column': ci + 1})
    rows = []
    for variant in VARIANTS:
        for b in [x for x in base if x['variant'] == variant.rstrip('*')]:
            x = {**b, 'variant': variant, 'condition_ids': ['covered-scope']}
            if b['benefit'] == 'part_a_hospital': x['condition_ids'].append('hospital')
            if b['benefit'] == 'foreign_emergency' and b['included']: x['condition_ids'].append('foreign')
            if b['benefit'] == 'snf_coinsurance' and b['included']: x['condition_ids'].append('snf')
            if b['benefit'] == 'part_b_cost_sharing': x['condition_ids'].append('part-b-deductible')
            if b['benefit'] == 'part_a_deductible': x['condition_ids'].append('part-a-deductible')
            if variant == 'N' and b['benefit'] == 'part_b_cost_sharing': x['condition_ids'].append('n-copays')
            if variant in ['K', 'L']: x['condition_ids'].append('kl-limits')
            if variant.endswith('*'): x['condition_ids'].append('high-deductible')
            if variant in ['C', 'F', 'F*']: x['condition_ids'].append('pre-2020')
            rows.append(x)
    # Conditions are sourced transcriptions, not executable individual rights.
    conditions = [
        ('covered-scope', 1, 'Q1; post-June-2010 standardized issues',
         'Only the specified standardized benefit is represented; this is not all medical expenses or a personal payment promise.', {}),
        ('hospital', 1, 'Q1(b–d)',
         'Medicare hospital cost sharing plus up to 365 additional lifetime days after Medicare hospital benefits are exhausted, at PPS or other appropriate payment standard.',
         {'additional_lifetime_days': 365, 'days_61_90_daily_cents': 43400, 'lifetime_reserve_daily_cents': 86800}),
        ('part-b-deductible', 1, 'Q1(e), Q2(b)',
         'Part B cost sharing applies after the annual Part B deductible; C/F cover that benefit, G/N do not. High-deductible qualification remains separate.', {'annual_part_b_deductible_cents': 28300}),
        ('snf', 2, 'Q2(d), chart p12',
         'Specified plan share of Medicare SNF coinsurance for covered days 21–100; Medicare coverage requirements still apply.', {'first_day': 21, 'last_day': 100, 'daily_coinsurance_cents': 21700}),
        ('foreign', 2, 'Q2(e)',
         'Emergency care during first 60 days of foreign trip: 80% of covered billed charges after separate $250 deductible, subject to $50,000 lifetime maximum; high-deductible plan threshold also applies.',
         {'first_trip_days': 60, 'covered_charge_percent': 80, 'separate_deductible_cents': 25000, 'lifetime_limit_cents': 5000000}),
        ('n-copays', 12, 'footnote 3; Q3(b) qualified by chart',
         'Up to $20 for some office visits; up to $50 for emergency visits that do not result in inpatient admission.', {'office_max_cents': 2000, 'er_max_cents': 5000, 'er_inpatient_exception': True}),
        ('kl-limits', 2, 'Q3(a), chart p12 footnote 2',
         'After the applicable 2026 out-of-pocket limit AND Part B deductible, pays 100% of covered services for rest of calendar year.', {'K_annual_limit_cents': 800000, 'L_annual_limit_cents': 400000, 'part_b_deductible_also_required': True}),
        ('high-deductible', 12, 'footnote 1; Q3(c–d)',
         'F*/G* require $2,950 plan deductible before benefits; separate foreign deductible is not covered. G* does not cover Part B deductible; Part B deductible payments count toward F*/G* plan deductible.',
         {'annual_plan_deductible_cents': 295000, 'part_b_counts_toward_threshold': True, 'separate_foreign_deductible_covered': False}),
        ('pre-2020', 12, 'chart + note; Q22 pp10–11',
         'C/F/F* are restricted to people first eligible for Medicare before January 1, 2020. This reference does not decide personal buying rights.', {'first_eligible_before': '2020-01-01'}),
        ('select', 6, 'Q13(a–c)',
         'SELECT uses specified provider/facility networks for some benefits, with an emergency exception; Medicare pays its portion regardless. Exact product/network/location must be confirmed.', {}),
        ('part-a-deductible', 1, 'Q2(a), chart p12',
         '2026 Medicare Part A deductible is per benefit period; apply the plan share shown in chart, including K/L/M partial shares.', {'per_benefit_period_cents': 173600})]
    normalized = [{'id': cid, 'source_id': r['source_id'], 'page': page, 'locator': locator,
                   'meaning': meaning, 'values': values, 'acceptance': 'pending'}
                  for cid, page, locator, meaning, values in conditions]
    plans = [{'variant': v, 'letter': v.rstrip('*'), 'high_deductible': v.endswith('*'),
              'annual_plan_deductible_cents': 295000 if v.endswith('*') else None,
              'standardized_annual_oop_limit_cents': {'K': 800000, 'L': 400000}.get(v),
              'first_eligible_before': '2020-01-01' if v in ['C', 'F', 'F*'] else None,
              'sale_status': 'not_established_by_standard_chart', 'personal_rights': 'L11_separate',
              'source_id': r['source_id'], 'page': 12} for v in VARIANTS]
    return {'year': 2026, 'scope': 'Post-2010 standardized benefit reference; check means full standardized benefit, not all billed charges. Foreign benefit pays 80% under its conditions. Carrier extras/sale/personal rights are separate.',
            'plans': plans, 'cells': rows, 'conditions': normalized,
            'retained_document_pages': len(pages), 'review_state': 'pending_exact_review'}


def carrier_tables():
    rows = []
    for sid in ['florida-blue-standard-2026', 'florida-blue-select-2026']:
        receipt, path = source(sid)
        with pdfplumber.open(path) as doc:
            for pi in range(7, 11):
                page = doc.pages[pi]
                text = page.extract_text()
                if 'Collier' not in text or 'Area 2' not in text:
                    raise ValueError('Collier area scope changed')
                table = page.extract_tables()[0]
                if len(table) != 11:
                    raise ValueError('Carrier age rows changed')
                for ri, values in enumerate(table[1:], 1):
                    for ci, header in enumerate(table[0][1:], 1):
                        rows.append({'source_id': sid, 'page': pi + 1, 'table_row': ri,
                                     'table_column': ci, 'header_raw': header, 'age_band_raw': values[0],
                                     'variant': header.split()[-1], 'select': header.startswith('Select'),
                                     'county_fips': '12021', 'rating_area': 'Area 2',
                                     'tobacco': 'non-tobacco' if pi in [7, 9] else 'tobacco',
                                     'payment_basis': 'automatic_payment_option' if pi >= 9 else 'regular_monthly',
                                     'amount_raw': values[ci], 'premium_cents': money(values[ci]),
                                     'unit': 'USD/month', 'source_edition_year': 2026,
                                     'actual_filed_rate_effective_date': None, 'policy_form': None,
                                     'filed_table_reproduction': False, 'personal_quote': False})
    if len(rows) != 680:
        raise ValueError('Carrier table cell count changed')
    return rows


def build(out):
    out = Path(out)
    if out.exists(): raise ValueError('Use a new immutable build directory')
    out.mkdir(parents=True)
    sources = {}
    # Retain every acquisition, including capped queries, as source history.
    for p in sorted(ACQ.glob('*.json')):
        r = load(p)
        if 'source_id' in r:
            receipt, raw = source(r['source_id'])
            sources[r['source_id']] = {'receipt': str(p.relative_to(ROOT)), 'receipt_sha256': sha(p),
                                      'path': str(raw.relative_to(ROOT)), **receipt}
    dump(out / 'sources.json', sources)
    benefits = standardized()
    dump(out / 'standardized-benefits.json', benefits)
    carrier = carrier_tables()
    dump(out / 'carrier-table-observations.json', carrier)
    con = sqlite3.connect(out / 'inventory.sqlite3')
    con.executescript('''CREATE TABLE illustrations(id TEXT PRIMARY KEY, listing_id TEXT, zip TEXT,
      age TEXT, sex TEXT, tobacco TEXT, annual_cents INTEGER, payload TEXT);
      CREATE INDEX lookup_illustrations ON illustrations(listing_id,zip,age,sex,tobacco);
      CREATE TABLE listings(id TEXT PRIMARY KEY,payload TEXT);
      CREATE TABLE insurers(name TEXT PRIMARY KEY,payload TEXT);
      CREATE TABLE filing_metadata(id TEXT PRIMARY KEY,payload TEXT);''')
    names = defaultdict(lambda: {'choices_rows': 0, 'naics': set(), 'filings': set(),
                                 'filing_forms': set(), 'source_locators': [], 'filed_2026': False})
    queries = load(ACQ / 'irfs-index.json')
    metadata_count = 0
    form_set = set()
    with (out / 'filing-metadata.jsonl').open('w') as file:
        for part in queries['partitions']:
            if not part['used']: continue
            sid = part['receipt'][:-5]
            r, raw = source(sid)
            data = load(raw)['Data']
            if len(data) != part['row_count'] or len(data) >= 1000:
                raise ValueError('Unaccounted/capped source partition')
            for i, row in enumerate(data):
                # The API exposes company/form filing associations, not a sale roster.
                record = {'id': f'{sid}:{i}', 'source_id': sid, 'source_pointer': f'/Data/{i}',
                          'source_native': row, 'current_collier_sale': 'unknown'}
                file.write(compact(record) + '\n')
                con.execute('INSERT INTO filing_metadata VALUES(?,?)', (record['id'], compact(record)))
                c = names[row['CoNm']]
                if row['NaicCoCd']: c['naics'].add(row['NaicCoCd'])
                c['filings'].add((row['AppSrc'], row['FileLogNumber']))
                if row['FormNum']:
                    c['filing_forms'].add(row['FormNum'])
                    form_set.add((row['CoNm'], row['NaicCoCd'], row['FileLogNumber'], row['FormNum']))
                c['filed_2026'] |= str(row['FileDt']).endswith('/2026')
                if len(c['source_locators']) < 5: c['source_locators'].append(record['id'])
                metadata_count += 1
    # Every 2026 detail remains separate, preserving true product type and Forms.
    details = []
    for item in load(ACQ / 'irfs-details-index.json')['filings']:
        if 'receipt' not in item: continue
        sid = item['receipt'][:-5]
        r, raw = source(sid)
        details.append({'source_id': sid, 'source_native': load(raw),
                        'current_sale': 'not_established', 'filed_rate_pages': 'not_obtained'})
    dump(out / 'filing-details.json', details)
    form_leads = []
    for detail in details:
        d = detail['source_native']
        for company in d.get('Companies') or []:
            for form in d.get('Forms') or [None]:
                form_leads.append({'source_id': detail['source_id'], 'file_log_number': d['FileLogNumber'],
                    'company_name_raw': company['CoNm'], 'naic_raw': company['NaicCoCd'],
                    'product_type_raw': d.get('ProdNm'), 'form_raw': form,
                    'new_business_effective_date_raw': d.get('EffDtNew'),
                    'renewal_effective_date_raw': d.get('EffDtRenew'),
                    'final_action_raw': d.get('FinalAction'), 'current_collier_sale': 'unknown',
                    'standardized_variant': None, 'listing_join': None,
                    'required_missing': ['exact_2026_continuation_and_sale_state', 'Collier_applicability',
                                         'exact_standardized_variant_join', 'filed_rate_pages_and_manual']})
    dump(out / 'product-form-leads.json', form_leads)
    listings = {}
    captures = load(ACQ / 'choices-index.json')['captures']
    count = display_count = raw_without_display = 0
    omitted_listing_ids = set()
    with (out / 'illustrations.jsonl').open('w') as file:
        for item in captures:
            sid = item['receipt'][:-5]
            r, raw = source(sid)
            p = json.loads(raw.read_text(), parse_float=str)
            inputs = r['inputs']
            if inputs['effectiveDate'] != '11/01/2026': raise ValueError('Wrong requested year')
            raw_ids = {str(x['ratE_ID']): x for x in p['rates']}
            displayed = set()
            for d in p['rateDisplays']:
                for variant in VARIANTS:
                    field = variant.lower().replace('*', 'star')
                    link, value = d.get(field + 'url'), d.get(field + 'value')
                    if link is not None:
                        if str(link) not in raw_ids or money(value) != money(raw_ids[str(link)]['ratE_AM']):
                            raise ValueError('Display/source amount disagreement')
                        displayed.add(str(link)); display_count += 1
                    elif value is not None: raise ValueError('Unlinked display amount')
            raw_without_display += len(raw_ids.keys() - displayed)
            for i, row in enumerate(p['rates']):
                if row['plaN_CD'] not in VARIANTS or row['zipcodE_DS'] != inputs['zipCode'] or row['agE_CD'] != inputs['age'] or row['seX_CD'] not in [inputs['gender'], 'n']:
                    raise ValueError('Source filter/variant mismatch')
                # Include class, membership, fee and underwriting distinctions.
                key_fields = ['companY_NM', 'plaN_CD', 'inS_TYPE_ID', 'grouP_CD', 'ratinG_CLASS_NM',
                              'eligibilitY_DS', 'policY_FEE_AM', 'policY_FEE_ASSESSED_CD',
                              'guaranteeD_ISSUE_CD', 'marketinG_METHOD_CD']
                key = {k: row.get(k) for k in key_fields}
                lid = 'L10-' + hashlib.sha256(compact(key).encode()).hexdigest()[:20]
                if lid not in listings:
                    listings[lid] = {'id': lid, 'source_listing_key': key, 'variant': row['plaN_CD'],
                        'select': 'Select' in row['grouP_CD'], 'group': row['grouP_CD'].startswith('Group'),
                        'policy_form': None, 'actual_rate_effective_date': None,
                        'sale_status': 'not_independently_verified', 'personal_eligibility': 'not_determined',
                        'raw_underwriting_code': row['guaranteeD_ISSUE_CD'],
                        'source_ui_underwriting_label': {'y': 'Underwritten', 'n': 'Guarenteed Issue'}.get(row['guaranteeD_ISSUE_CD'], 'Unknown'),
                        'source_ui_label_is_personal_right': False, 'naic': None,
                        'observed_zips': set(), 'observed_age_classes': set(), 'observations': 0,
                        'first_source_id': sid, 'first_source_pointer': f'/rates/{i}'}
                listing = listings[lid]
                listing['observed_zips'].add(inputs['zipCode']); listing['observed_age_classes'].add(inputs['age'])
                listing['observations'] += 1
                if str(row['ratE_ID']) not in displayed: omitted_listing_ids.add(lid)
                n = names[row['companY_NM']]; n['choices_rows'] += 1
                observation = {'id': f'{sid}:{i}', 'listing_id': lid, 'source_id': sid,
                               'source_pointer': f'/rates/{i}', 'source_rate_id': str(row['ratE_ID']),
                               'source_native': row, 'synthetic_inputs': inputs,
                               'annual_premium_cents': money(row['ratE_AM']), 'unit': 'USD/year',
                               'amount_state': 'unknown' if row['ratE_AM'] is None else 'value',
                               'actual_rate_effective_date': None, 'policy_form': None,
                               'price_basis': 'illustrative_public_comparison', 'personal_quote': False,
                               'fee_inclusion': 'unknown', 'displayed_by_source_grid': str(row['ratE_ID']) in displayed}
                file.write(compact(observation) + '\n')
                con.execute('INSERT INTO illustrations VALUES(?,?,?,?,?,?,?,?)',
                            (observation['id'], lid, inputs['zipCode'], inputs['age'], inputs['gender'], inputs['smoker'], observation['annual_premium_cents'], compact(observation)))
                count += 1
    catalog = []
    for name, c in sorted(names.items()):
        row = {'company_name_raw': name, 'observed_naic_codes': sorted(c['naics']),
               'exact_name_unique_naic': next(iter(c['naics'])) if len(c['naics']) == 1 else None,
               'choices_observation_count': c['choices_rows'], 'filed_2026': c['filed_2026'],
               'historical_filing_count': len(c['filings']), 'historical_form_strings': sorted(c['filing_forms']),
               'evidence_locators_sample': c['source_locators'], 'current_collier_sale': 'unknown',
               'complete_2026_forms': False, 'naic_join_basis': 'exact_raw_company_name_only_no_brand_alias_inference'}
        catalog.append(row); con.execute('INSERT INTO insurers VALUES(?,?)', (name, compact(row)))
    by_name = {x['company_name_raw']: x for x in catalog}
    listing_rows = []
    for lid, listing in sorted(listings.items()):
        listing['observed_zips'] = sorted(listing['observed_zips'])
        listing['observed_age_classes'] = sorted(listing['observed_age_classes'])
        listing['naic'] = by_name[listing['source_listing_key']['companY_NM']]['exact_name_unique_naic']
        listing['naic_join_does_not_link_policy_form_or_effective_rate'] = True
        listing_rows.append(listing); con.execute('INSERT INTO listings VALUES(?,?)', (lid, compact(listing)))
    con.commit(); con.execute('VACUUM'); con.close()
    dump(out / 'insurer-catalog.json', catalog)
    dump(out / 'source-listings.json', listing_rows)
    products = {}
    for x in listing_rows:
        name = x['source_listing_key']['companY_NM']; group = x['source_listing_key']['grouP_CD']
        key = (name, x['variant'], group)
        products.setdefault(key, {'company_name_raw': name, 'variant': x['variant'],
            'source_group_type': group, 'select': x['select'], 'listing_ids': [],
            'carrier_table_locators': [], 'sale_status': 'unknown', 'policy_form': None,
            'personal_eligibility': 'not_determined', 'evidence_basis': []})['listing_ids'].append(x['id'])
    for x in carrier:
        name = 'BLUE CROSS & BLUE SHIELD OF FLORIDA, INC.'
        # The SELECT booklet supplies a county/letter product lead; the exact
        # individual/group policy-form basis still needs its own source join.
        group = 'Carrier SELECT; individual/group form basis unresolved' if x['select'] else 'Individual Standard'
        key = (name, x['variant'], group)
        products.setdefault(key, {'company_name_raw': name, 'variant': x['variant'],
            'source_group_type': group, 'select': x['select'], 'listing_ids': [],
            'carrier_table_locators': [], 'sale_status': 'unknown', 'policy_form': None,
            'personal_eligibility': 'not_determined', 'evidence_basis': []})['carrier_table_locators'].append(
                {'source_id': x['source_id'], 'page': x['page'], 'column': x['table_column']})
    product_rows = []
    for key, p in sorted(products.items()):
        p['id'] = 'L10-P-' + hashlib.sha256(compact(key).encode()).hexdigest()[:20]
        p['naic'] = by_name[p['company_name_raw']]['exact_name_unique_naic']
        p['evidence_basis'] = (['OIR_sample_listing'] if p['listing_ids'] else []) + (['carrier_2026_outline_Collier_Area_2_table'] if p['carrier_table_locators'] else [])
        p['carrier_table_locators'] = [dict(t) for t in sorted({tuple(sorted(t.items())) for t in p['carrier_table_locators']})]
        p['complete_product_identity'] = False
        product_rows.append(p)
    dump(out / 'product-discovery-map.json', {'all_market_complete': False, 'products': product_rows,
        'meaning': 'Source-observed company/letter/type discovery groups; rating classes and restrictions remain in listing IDs. These are not exact policy-form identities or confirmed for-sale offerings.'})
    anomalies = {
        'raw_rows_omitted_from_CHOICES_display': raw_without_display,
        'omission_products': [p['id'] for p in product_rows if set(p['listing_ids']) & omitted_listing_ids],
        'carrier_only_discovery_products': [p['id'] for p in product_rows if not p['listing_ids']],
        'resolution': 'Preserve raw observations and carrier-only products with exact source provenance; absence from a displayed sample grid does not establish market absence.',
        'gi_code': {'y': 'Underwritten in source UI', 'n': 'Guarenteed Issue in source UI',
                    'personal_right_established': False, 'source': 'choices-public-script'},
        'historical_name_count_discrepancy': 'Historical prose said 33; retained 2027 captures and new 2026-request grid both contain 34 raw names. No name is discarded or alias inferred.'}
    dump(out / 'source-anomalies.json', anomalies)
    dump(out / 'required-coverage-ledger.json', {
        'universe': {'required': True, 'status': 'unresolved', 'complete_2026_effective_Collier_denominator': False,
                     'reason': 'Source extents are accounted for; actual product continuation/sale/form/area universe is not proven.'},
        'listings': [{'listing_id': x['id'], 'required': True, 'status': 'open',
                      'owner': 'AI collection/reconciliation; source owner for unavailable evidence; specialist for interpretation',
                      'missing': ['exact_policy_form', 'actual_2026_rate_effective_interval', 'current_new_business_in_force_closed_state',
                                  'filed_rate_table_and_rating_manual', 'fee_discount_payment_underwriting_basis'] +
                                 (['membership_evidence'] if x['group'] else []) +
                                 (['exact_SELECT_network_and_location_evidence'] if x['select'] else []),
                      'closure_evidence': 'Dated exact company/NAIC/form/letter/area/class source joins, rate replay where modeled, and applicable review.'}
                     for x in listing_rows],
        'form_lead_count': len(form_leads),
        'not_waived_by_mvp': ['complete_2026_product_universe', 'required_filed_rate_reconstruction', 'source_use_and_exact_acceptance'],
        'internal_work_remaining': ['collect/reconcile applicable public carrier forms/manuals beyond the retained Florida Blue examples',
                                    'resolve historical-to-2026 product continuity, exact letter/form and sale-state joins',
                                    'reconcile modeled CHOICES and carrier rates only after their rating bases/effective periods are supported'],
        'external_or_specialist_needs': ['actual OIR dataset/document delivery through authorized access',
                                         'restricted/trade-secret or ambiguous rating/underwriting evidence', 'R15/source-use/exact-release review']})
    limits = [
        'The authoritative complete 2026-effective Collier company/form/product denominator remains unresolved; a returned listing, filing or standardized chart is not proof of current sale.',
        'All 500 CHOICES scenarios request November 1, 2026. Actual filed effective intervals, forms, discounts, underwriting and fee inclusion are absent; amounts are illustrative annual comparisons, not verified historical 2026 prices or quotes.',
        'IRFS dates are filing/new-business/renewal metadata as labeled, not continuation or current sale. Pre-2001 filings are unavailable; historical and additional company leads remain visible.',
        'Florida Blue outline tables are published monthly observations for Collier Area 2. Edition and annual Medicare constants establish 2026 document context, but exact filed approval, rate-effective interval and policy-form linkage are not established.',
        'No filed rate pages/manuals were obtained via IRFS; its normal document delivery requires email and a challenge, and trade-secret/restricted limits remain. Existing public-records case needs an actual 2026-compatible response.',
        'SELECT provider/hospital participation, group membership, carrier extras and current new-business/in-force/closed status need exact evidence; do not infer from standard benefits or general directories.',
        'L11 buying rights, personal premiums/totals, recommendations, rankings, quote/enrollment operations and consumer activation remain separate and held.',
        'All new evidence remains unaccepted pending exact source-use, specialist and R15 review. Technical checks do not supply acceptance.'
    ]
    gaps = [{'id': f'L10-G{i+1:02}', 'state': 'open', 'required': True, 'description': text,
             'owner': 'data/source review' if i < 6 else 'separate capability/release review',
             'closure_evidence': 'Exact dated source/entity/form/area/rating evidence and applicable independent review; retain unknown until established.'}
            for i, text in enumerate(limits)]
    dump(out / 'gaps.json', {'full_l10_complete': False, 'gaps': gaps, 'limits': limits,
                            'mvp_boundary': 'Product discovery and standardized-benefit research with explicit uncertainty; no accepted consumer release.'})
    coverage = {'schema': 'l10-coverage/1', 'year': 2026, 'county_fips': '12021',
                'choices_scenarios': len(captures), 'oir_listed_county_zips': 25,
                'illustrative_observations': count, 'source_display_cells_checked': display_count,
                'raw_observations_not_in_grid': raw_without_display,
                'listing_variants': len(listing_rows), 'choices_company_names': sum(x['choices_rows'] > 0 for x in names.values()),
                'discovery_company_letter_type_groups': len(product_rows),
                'carrier_only_discovery_groups': sum(not x['listing_ids'] for x in product_rows),
                'source_company_names_including_history': len(catalog),
                'exact_name_unique_naic_choices_companies': sum(x['choices_observation_count'] > 0 and x['exact_name_unique_naic'] is not None for x in catalog),
                'filing_metadata_rows': metadata_count, 'filing_company_case_form_associations': len(form_set),
                'filing_details_2026': len(details), 'standardized_variants': 12, 'standardized_benefit_cells': len(benefits['cells']),
                'product_form_leads_2026_file_metadata': len(form_leads),
                'carrier_monthly_table_cells': len(carrier), 'verified_filed_rate_models': 0,
                'complete_all_market_2026_denominator': False, 'human_acceptance': None,
                'consumer_release_enabled': False, 'full_l10_complete': False}
    dump(out / 'coverage.json', coverage)
    dump(out / 'before-after.json', {'before': {'choices_requested_year': 2027, 'synthetic_scenarios': 17,
        'zips': 1, 'illustrative_rows': 3876, 'raw_names': 34, 'actual_rate_effective_dates': 0,
        'policy_forms': 0, 'filed_rate_models': 0}, 'after': coverage,
        'limits': 'New counts are finite source/accounting extents, not verified product/price counts or inherited acceptance.'})
    input_paths = list(ACQ.glob('*.json')) + [BASE / 'PLAN.md', BASE / 'reuse-audit.json', BASE / 'preservation-before.json']
    code_paths = [ROOT / 'cms-slice/scripts' / name for name in ['l10_acquire.py', 'l10_collect_choices.py', 'l10_collect_irfs.py', 'l10_build.py', 'l10_validate.py', 'l10_reference.py']]
    manifest = {'schema': 'l10-build/1', 'year': 2026, 'county_fips': '12021', 'research_only': True,
                'human_acceptance': None, 'consumer_release_enabled': False, 'full_l10_complete': False,
                'source_review_after_utc': '2026-11-28T00:00:00+00:00',
                'files_sha256': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
                'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(input_paths)},
                'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in code_paths}, 'coverage': coverage}
    dump(out / 'manifest.json', manifest)
    (out / 'SEALED').write_text(sha(out / 'manifest.json') + '\n')
    return coverage


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); print(json.dumps(build(args.out), indent=2))
