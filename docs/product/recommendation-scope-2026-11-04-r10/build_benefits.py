"""Prepare and screen recommendation-critical medical terms across the sealed r9 scope."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRODUCT = HERE.parent
DATA = ROOT / 'docs/data/l03-ma-benefits-2026-10-25'
MPF = ROOT / 'docs/data/mpf-benefit-summary-2026-11-04-r1'
sys.path.insert(0, str(ROOT / 'cms-slice/scripts'))
from l03_reconcile import component_costs

INPUTS = {
    'catalog': PRODUCT / 'recommendation-scope-2026-11-04-r5/catalog.json',
    'matrix': PRODUCT / 'recommendation-scope-2026-11-04-r9/offering-gaps.json',
    'mpf': MPF / 'collier-main.jsonl',
    'optional': MPF / 'collier-optional.jsonl',
    'pbp_instances': DATA / 'build-r1/benefit-instances.jsonl.gz',
    'service_context': DATA / 'source-reconciliation-r7/service-reconciliation.jsonl.gz',
    'carrier_named_checks': DATA / 'source-reconciliation-r7/erickson-source-led-comparisons.json',
    'historical_holds': DATA / 'bounded-reference-r4/held-claims.json',
    'published_reference': DATA / 'bounded-reference-r4/entries.json',
    'component_decoder': ROOT / 'cms-slice/scripts/l03_reconcile.py',
    'pbp_table_bundles': DATA / 'build-r1/normalized-source-bundles.jsonl.gz',
    'carrier_pages': DATA / 'build-r1/carrier-pages.jsonl.gz',
    'drug_schedules': ROOT / 'docs/data/l06-drug-costs-2026-10-27/build-cost-r1/beneficiary-native.psv.gz',
}

PART_B_FIELDS = ('pbp_d_mco_pay_reduct_yn', 'pbp_d_mco_pay_reduct_amt')
AETNA_GIVEBACK = '2026:H5521:306:000'

# The MPF category and service must match literally. PBP category codes refer
# to Medicare services in the retained r7 context for the same exact offering.
DIAGNOSTICS = 'Diagnostic procedures/lab services/imaging'
EQUIPMENT = 'Medical equipment/supplies'
SERVICES = {
    'emergency': ('4a', 'Emergency care/urgent care', 'Emergency'),
    'urgent': ('4b', 'Emergency care/urgent care', 'Urgent care'),
    'outpatient_hospital': ('9a1', 'Outpatient hospital coverage', None),
    'hospital_observation': ('9a2', None, None),
    'ambulatory_surgery_center': ('9b', None, None),
    'diagnostic_tests': ('8a1', DIAGNOSTICS, 'Diagnostic tests and procedures'),
    'laboratory': ('8a2', DIAGNOSTICS, 'Lab services'),
    'diagnostic_radiology': ('8b1', DIAGNOSTICS, 'Diagnostic radiology services <i>(e.g., MRI)</i>'),
    'therapeutic_radiology': ('8b2', None, None),
    'outpatient_xray': ('8b3', DIAGNOSTICS, 'Outpatient x-rays'),
    'ground_ambulance': ('10a1', 'Ground Ambulance', None),
    'air_ambulance': ('10a2', None, None),
    'skilled_nursing': ('2', 'Skilled Nursing Facility', None),
    'home_health': ('6', None, None),
    'occupational_therapy': ('7c', 'Rehabilitation services', 'Occupational therapy visit'),
    'physical_and_speech_therapy': ('7i', 'Rehabilitation services', 'Physical therapy and speech and language therapy visit'),
    'durable_medical_equipment': ('11a', EQUIPMENT, 'Durable medical equipment <i>(e.g., wheelchairs, oxygen)</i>'),
    'prosthetics': ('11b1', EQUIPMENT, 'Prosthetics <i>(e.g., braces, artificial limbs)</i>'),
    'medical_supplies': ('11b2', None, None),
    'diabetes_monitoring_supplies': ('11c1', EQUIPMENT, 'Diabetes supplies'),
}

NAMED_FIELDS = {
    'emergency': 'INN_emergency_visit', 'urgent': 'INN_urgent_visit',
    'outpatient_hospital': 'INN_outpatient', 'hospital_observation': 'INN_observation',
    'ambulatory_surgery_center': 'INN_asc', 'diagnostic_tests': 'INN_diagnostic',
    'laboratory': 'INN_lab', 'diagnostic_radiology': 'INN_radiology',
    'therapeutic_radiology': 'INN_therapeutic', 'outpatient_xray': 'INN_xray',
    'ground_ambulance': 'INN_ground_ambulance', 'air_ambulance': 'INN_air_ambulance',
    'home_health': 'INN_home_health', 'occupational_therapy': 'INN_occupational',
    'physical_and_speech_therapy': 'INN_rehab', 'durable_medical_equipment': 'INN_dme',
    'prosthetics': 'INN_prosthetics',
}

NUMBER = r'(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?'
FLAT = re.compile(rf'\$(?P<low>{NUMBER})(?:-\$?(?P<high>{NUMBER}))? copay(?: per (?P<basis>visit|item|trip|stay|service))?(?: \(always covered\))?')
PERCENT = re.compile(rf'(?P<low>{NUMBER})(?:-(?P<high>{NUMBER}))?% coinsurance(?: per (?P<basis>visit|item|trip|stay|service))?(?: \(always covered\))?')
BAND = re.compile(rf'\$({NUMBER})(?: copay)? per day for days ([0-9]+) through ([0-9]+)')


def number(value):
    return format(Decimal(str(value).replace(',', '')).normalize(), 'f')


def mpf_expression(text):
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    for pattern, unit in ((FLAT, 'USD'), (PERCENT, 'percent')):
        match = pattern.fullmatch(text)
        if match:
            low, high = number(match['low']), match['high']
            if high is None:
                return {'shape': 'amount', 'unit': unit, 'amount': low, 'basis': match['basis']}
            if Decimal(low) <= Decimal(number(high)):
                return {'shape': 'range', 'unit': unit, 'minimum': low, 'maximum': number(high), 'basis': match['basis']}
    bands = []
    for line in re.split(r'<br\s*/?>|\n', text):
        match = BAND.fullmatch(line.strip())
        if not match:
            return None
        amount, begin, end = match.groups()
        first, last = int(begin), int(end)
        if first != (bands[-1]['end_day'] + 1 if bands else 1) or last < first:
            return None
        bands.append({'amount': number(amount), 'begin_day': first, 'end_day': last})
    return {'shape': 'day_bands', 'unit': 'USD', 'basis': 'day', 'bands': bands}


def pbp_expression(components):
    """Screen only a single default charge shape or a single complete USD stay schedule."""
    selected = [c for c in components if c['state'] not in {'no_this_cost_type', 'explicit_network_component'}]
    if len(selected) == 1:
        c = selected[0]
        if c['state'] == 'amount':
            return {'shape': 'amount', 'unit': c['unit'], 'amount': number(c['amount'])}
        if (c['state'] == 'range' and c['minimum'] is not None and c['maximum'] is not None
                and Decimal(c['minimum']) <= Decimal(c['maximum'])):
            return {'shape': 'range', 'unit': c['unit'], 'minimum': number(c['minimum']), 'maximum': number(c['maximum'])}
    if not selected or any(c['state'] != 'day_band' or c['unit'] != 'USD' or
                           c.get('stay_or_reserve') != 'stay' or
                           None in (c['amount'], c['begin_day'], c['end_day']) for c in selected):
        return None
    if len({c['subcomponent'] for c in selected}) != 1:
        return None
    bands = sorted(({'amount': number(c['amount']), 'begin_day': int(c['begin_day']),
                     'end_day': int(c['end_day'])} for c in selected), key=lambda row: row['begin_day'])
    for index, band in enumerate(bands):
        first = bands[index - 1]['end_day'] + 1 if index else 1
        if band['begin_day'] != first or band['end_day'] < first:
            return None
    return {'shape': 'day_bands', 'unit': 'USD', 'bands': bands}


def project(plan, name, mpf_rows, service, raw, historical, named, variant, references):
    in_network = [row for row in mpf_rows if row['fields']['Network_Description'] == 'In-Network']
    display = mpf_expression(in_network[0]['fields']['Cost_Share']) if len(in_network) == 1 else None
    components = service['PBP_cost_sharing']
    details = raw['raw']['benefitDetails']
    nested_charges = {}
    if name in {'emergency', 'urgent'}:
        nested_charges = {
            'CopaymentComponent': details.get('CopayAdmWaivedTimelineComponent', {}).get('CopayAdmWaivedTimelineComptCopayment', {}),
            'CoinsuranceComponent': details.get('CoinsAdmWaivedTimelineComponent', {}).get('CoinsAdmWaivedTimelineComptCoinsurance', {}),
        }
    elif name == 'hospital_observation':
        nested_charges = {'CopaymentComponent': details.get('CopayObservationServiceComponent', {}).get('bdcopayComponent', {})}
    nested_components = component_costs(nested_charges)
    if name in {'emergency', 'urgent'} and len(nested_components) != 2:
        pbp = None
    else:
        pbp = pbp_expression([*components, *nested_components])
    if display and pbp and name == 'diabetes_monitoring_supplies':
        screening = 'service_subtype_requires_review'
    elif display and pbp:
        match = {key: value for key, value in display.items() if key != 'basis'} == pbp
        screening = 'charge_shape_and_values_align' if match else 'charge_shape_or_values_differ'
    elif in_network:
        screening = 'published_expression_preserved_for_targeted_review'
    else:
        screening = 'pbp_and_carrier_context_only'
    checks = ['exact_service_setting_and_network', 'applicable_deductible_limit_and_authorization']
    if name in {'emergency', 'urgent'}:
        checks.append('admission_waiver_and_timing')
    if name == 'skilled_nursing':
        checks.append('qualifying_stay_counted_days_and_reset_period')
    if name == 'home_health':
        checks.append('home_health_eligibility_and_separate_equipment')
    if name in {'durable_medical_equipment', 'prosthetics', 'medical_supplies', 'diabetes_monitoring_supplies'}:
        checks.append('exact_item_supplier_channel_and_rental_or_purchase')
    flags = []
    if historical:
        flags.append('RETAINED_SOURCE_CONFLICT')
    if screening == 'charge_shape_or_values_differ':
        flags.append('MPF_PBP_CHARGE_DIFFERENCE')
    if plan['published']['coverage']['value'].get('snp_type') == 'Dual-Eligible':
        flags.append('ASSISTANCE_COST_SHARE_BASIS_REQUIRED')
    if variant['fields']['Cost_Share'] != 'No':
        flags.append('HEALTH_CONDITION_VARIANT_REQUIRES_CHECK')
    if screening != 'charge_shape_and_values_align':
        flags.append('EXACT_CHARGE_BASIS_REVIEW_REQUIRED')
    return {
        'service_code': service['category_code'], 'service': service['service_name'],
        'source_screen': screening, 'flags': flags, 'personal_checks_if_material': checks,
        'mpf': [{'row': row['source_row'], 'source_range': row['source_range'],
                 'network': row['fields']['Network_Description'], 'terms': row['fields']['Cost_Share'],
                 'limit_flag': row['fields']['Limit_Flag'], 'authorization_flag': row['fields']['Authorization_Flag'],
                 'referral_flag': row['fields']['Referral_Flag']} for row in mpf_rows],
        'mpf_in_network_expression': display,
        'pbp': {'record_id': service['id'], 'locator': service['PBP_source'],
                'default_charge_expression': pbp, 'native_cost_components': components,
                'decoded_nested_charge_components': nested_components,
                'source_conditions': {key: value for key, value in details.items()
                    if key.startswith(('CopayAdmWaived', 'CoinsAdmWaived', 'CopayObservation',
                                       'Deductible', 'PriorAuthorization', 'Moop', 'MaxPlan',
                                       'CostShareGroups', 'OneToggle', 'Snf'))},
                'coverage_controls': service['PBP_coverage_controls'],
                'authorization_and_referral': {key: {k: value[k] for k in ('required_control_raw', 'selected_service', 'scope')}
                    for key, value in service['PBP_authorization_referral'].items()}},
        'carrier': {'exact_service_page_locators': service['EOC_source_evidence'],
                    'chart_row_ids': service['EOC_chart_row_ids'],
                    'existing_named_check': named},
        'historical_hold_ids': historical,
        'original_published_reference_ids': references,
        'source_approval': 'pending_exact_source_method_and_purpose_review',
        'personal_cost': None,
    }


def read_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        yield from map(json.loads, stream)


def review_part_b(catalog):
    fields_by_plan = {}
    for row in read_rows(INPUTS['pbp_table_bundles']):
        if row['source_table'] == 'pbp_Section_D.txt':
            fields = {f['source']['field']: f for f in row['fields'] if f['source']['field'] in PART_B_FIELDS}
            if not fields:
                continue
            if set(fields) != set(PART_B_FIELDS) or row['offering_id'] in fields_by_plan:
                raise ValueError('Part B PBP field binding is incomplete or ambiguous')
            fields_by_plan[row['offering_id']] = fields
    aetna_eoc = catalog['source_bindings']['documents'][AETNA_GIVEBACK]['document_matches']['EOC']['sha256']
    for page in read_rows(INPUTS['carrier_pages']):
        if page['document_sha256'] == aetna_eoc and page['pdf_page'] == 7:
            carrier = re.search(r'reduce the Part B premium .*? by \$([0-9.]+) per month', ' '.join(page['text'].split()))
            if carrier:
                aetna_term = {'document_sha256': aetna_eoc, 'pdf_page': 7,
                              'text_sha256': page['text_sha256'], 'amount': number(carrier[1]), 'unit': 'USD/month'}
                break
    else:
        raise ValueError('Aetna Part B carrier statement unavailable')

    result = {}
    for plan in catalog['plans']:
        oid = plan['offering_id']
        fields = fields_by_plan[oid]
        flag, amount = (fields[key]['normalized'].get('value') for key in PART_B_FIELDS)
        old = plan['published']['part_b_reduction']
        record = {'state': 'held_source_basis', 'retained_r5_state': old['state'],
                  'PBP_fields': fields, 'carrier_ref_ids': old['source_refs'], 'candidate': None,
                  'source_approval': 'pending_exact_source_method_and_purpose_review',
                  'personal_check': 'actual_part_b_billing_credit_eligibility_and_timing'}
        if flag == 'No' and amount is None and old['state'] == 'held':
            record.update(state='explicit_pbp_no_part_b_rebate', candidate={'uses_ma_rebate_for_part_b': False})
        elif flag == 'Yes' and amount is not None and old['state'] == 'published_candidate':
            if number(amount) == number(old['value']['amount']):
                record.update(state='pbp_matches_retained_carrier_amount',
                              candidate={'amount': number(amount), 'unit': 'USD/month',
                                         'conditions': old.get('conditions')})
        elif oid == AETNA_GIVEBACK and flag == 'Yes' and amount is not None and number(amount) == aetna_term['amount']:
            record.update(state='pbp_matches_new_carrier_reading', candidate={'amount': aetna_term['amount'], 'unit': 'USD/month'},
                          carrier_page=aetna_term)
        result[oid] = record
    return result


def review_part_d(catalog):
    schedules = defaultdict(list)
    with gzip.open(INPUTS['drug_schedules'], 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='|'):
            if row['COVERAGE_LEVEL'] == '1' and row['DAYS_SUPPLY'] == '1':
                oid = ':'.join(('2026', row['CONTRACT_ID'], row['PLAN_ID'], row['SEGMENT_ID']))
                schedules[oid].append({'source_ordinal': int(row['SOURCE_ORDINAL']), 'tier': int(row['TIER']),
                                       'deductible_applies_source_flag': row['DED_APPLIES_YN']})
    result = {}
    for plan in catalog['plans']:
        oid = plan['offering_id']
        old = plan['published']['part_d_deductible']
        rows = sorted(schedules.get(oid, []), key=lambda row: row['tier'])
        state = 'held_source_basis'
        tiers = [row['tier'] for row in rows if row['deductible_applies_source_flag'] == 'Y']
        if old['state'] == 'not_applicable' and not rows:
            state = 'no_included_part_d'
        elif (rows and len({row['tier'] for row in rows}) == len(rows)
              and all(row['deductible_applies_source_flag'] in {'Y', 'N'} for row in rows)
              and old.get('value')):
            old_tiers = old.get('conditions', {}).get('tiers')
            if old_tiers is not None:
                state = 'schedule_tiers_match_retained_carrier' if sorted(old_tiers) == tiers else 'held_tier_scope_difference'
            elif Decimal(old['value']['amount']) == 0:
                state = 'zero_published_deductible_with_tier_schedule'
            elif old.get('reason_codes') == ['DRUG_DEDUCTIBLE_TIERS_UNRESOLVED'] and tiers:
                state = 'schedule_tiers_prepared_carrier_scope_review'
        result[oid] = {'state': state, 'retained_r5_state': old['state'],
                       'published_deductible_observation': old.get('value'), 'retained_source_refs': old['source_refs'],
                       'source_scope': 'Initial coverage schedule, 30-day supply, no subsidy basis',
                       'schedule_rows': rows, 'tiers_flagged_applicable': tiers,
                       'source_approval': 'pending_exact_source_method_and_purpose_review',
                       'personal_check': 'exact_drug_tier_exceptions_subsidy_and_remaining_deductible'}
    return result


def build():
    catalog = json.loads(INPUTS['catalog'].read_bytes())
    matrix = json.loads(INPUTS['matrix'].read_bytes())
    ids = [p['offering_id'] for p in catalog['plans']]
    if len(ids) != 72 or ids != [p['offering_id'] for p in matrix['offerings']]:
        raise ValueError('The 72-offering gap matrix scope changed')
    by_mpf = defaultdict(list)
    for row in read_rows(INPUTS['mpf']):
        fields = row['fields']
        by_mpf[row['offering_id'], fields['Category Name'], fields['Service_Desc']].append(row)
    context = {(r['offering_id'], r['category_code']): r for r in read_rows(INPUTS['service_context'])
               if r['category_type_interpretation'] == 'medicare'}
    instances = {r['id']: r for r in read_rows(INPUTS['pbp_instances'])}
    historical = defaultdict(list)
    for row in json.loads(INPUTS['historical_holds'].read_bytes()):
        historical[row['offering_id'], row['category_code']].append(row['issue_id'])
    references = defaultdict(list)
    for row in json.loads(INPUTS['published_reference'].read_bytes()):
        references[row['offering_id'], row['field'].split(':')[0]].append(row['id'])
    named = {(r['offering_id'], r['field']): r for r in json.loads(INPUTS['carrier_named_checks'].read_bytes())}
    optional = defaultdict(list)
    for row in read_rows(INPUTS['optional']):
        optional[row['offering_id']].append(row['source_row'])
    part_b_review = review_part_b(catalog)
    part_d_review = review_part_d(catalog)
    plans = {}
    review = Counter()
    flag_counts = Counter()
    for plan, matrix_plan in zip(catalog['plans'], matrix['offerings']):
        oid = plan['offering_id']
        variant, = by_mpf[oid, 'Additional benefits and/or reduced cost-sharing for enrollees with certain health conditions?', None]
        terms = {}
        for name, (code, category, service_desc) in SERVICES.items():
            source = context[oid, code]
            raw = instances[source['id']]
            if raw['pbp'] != source['PBP_source'] or raw['offering_id'] != oid or raw['category_code'] != code:
                raise ValueError(f'PBP provenance mismatch for {oid}/{code}')
            mpf_rows = by_mpf.get((oid, category, service_desc), []) if category else []
            if category and sum(r['fields']['Network_Description'] == 'In-Network' for r in mpf_rows) != 1:
                raise ValueError(f'MPF in-network scope mismatch for {oid}/{name}')
            result = project(plan, name, mpf_rows, source, raw, historical[oid, code],
                             named.get((oid, NAMED_FIELDS.get(name))), variant, references[oid, code])
            terms[name] = result
            review[result['source_screen']] += 1
            flag_counts.update(result['flags'])
        plans[oid] = {'medical_services': terms,
                      'part_b_reduction_review': part_b_review[oid],
                      'part_d_deductible_review': part_d_review[oid],
                      'retained_baseline_states': {k: matrix_plan['families'][k] for k in
                          ('identity', 'premium_deductible', 'limits', 'office_hospital')},
                      'retained_scenario_states': matrix_plan['scenarios'],
                      'supplemental_source_rows': matrix_plan['families']['supplemental']['mpf_source_rows'],
                      'optional_package_source_rows': optional.get(oid, []),
                      'conditional_follow_up': ['away_care_by_destination_and_service', 'supplemental_benefit_if_material',
                          'doctor_site_and_access', 'medicine_formulary_and_exact_pharmacy_fill',
                          'enrollment_timing_and_assistance', 'coverage_path_alternatives']}
    return {'schema': 'daylight-d91-collier-critical-benefits/1', 'scope': catalog['scope'],
            'purpose': catalog['purpose'], 'services_per_plan': len(SERVICES),
            'source_screen_counts': dict(review), 'flag_counts': dict(flag_counts),
            'part_b_review_counts': dict(Counter(row['state'] for row in part_b_review.values())),
            'part_d_review_counts': dict(Counter(row['state'] for row in part_d_review.values())),
            'inputs': {key: {'path': str(path.relative_to(ROOT)), 'sha256': sha256(path.read_bytes()).hexdigest()}
                       for key, path in INPUTS.items()}, 'plans': plans}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    output = HERE / 'critical-benefits.json'
    rendered = json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
    if args.check:
        if output.read_text(encoding='utf-8') != rendered:
            raise SystemExit('Critical benefit projection differs from recorded inputs')
    else:
        output.write_text(rendered, encoding='utf-8')
    print(json.dumps({'offerings': len(result['plans']), 'services_per_plan': result['services_per_plan'],
                      'source_screen_counts': result['source_screen_counts'], 'flags': result['flag_counts'],
                      'part_b_review': result['part_b_review_counts'],
                      'part_d_review': result['part_d_review_counts']}, indent=2))
