#!/usr/bin/env python3
"""Run the D91 two-plan research scenario from its selected, retained evidence."""
import argparse
from copy import deepcopy
import csv
from decimal import Decimal, localcontext
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / path) for path in ('alternatives/advisor-first',
    'alternatives/chat-first/cms-slice/scripts', 'cms-slice/scripts')]

from comparison_evidence import canonical_sha256, reject_economic_fields
from comparison_profile import build_comparison_profile
from l03_benefit_normalization import decimal_text, price_cell
from natural_state import record_capture


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def usd(value, unit):
    exact = decimal_text(value)
    require(len(exact.partition('.')[2]) <= 2, 'Source amount has sub-cent precision')
    return {'type': 'decimal', 'amount': format(Decimal(exact), '.2f'),
            'currency': 'USD', 'unit': unit}


def subtotal(lines, unit):
    with localcontext() as context:
        context.prec = 300
        total = sum(Decimal(line['rate']['amount']) * line['quantity'] for line in lines)
    return usd(str(total), unit)


def profile_binding(fixture):
    guide = {'schemaVersion': 2, 'stateVersion': 0, 'fields': {}}
    record = {'schemaVersion': 1, 'stateVersion': 0, 'facts': {}}
    prior_guide, prior_record = deepcopy(guide), deepcopy(record)
    for target, key, values in (
        (guide, 'fields', fixture['fictional_guide_reports']),
        (record, 'facts', fixture['fictional_readiness_reports']),
    ):
        target['stateVersion'] = 1
        target[key] = {k: {'value': v, 'status': 'reported', 'revision': 1,
                           'source': 'user_text'} for k, v in values.items()}
    record_capture(guide, record, prior_guide, prior_record)
    view = build_comparison_profile(guide, record, requested_scope=fixture['requested_scope'],
                                    subject_id=fixture['subject_id'])
    require(len(view['questions']) == 41 and not view['integrity_issues'],
            'Fictional input failed the current report contract')
    reports = [fact for fact in view['facts'] if fact['report_state'] == 'reported']
    require(reports and all(fact['usable_for_bound_subject'] and not fact['externally_verified']
                            for fact in reports), 'Fictional report provenance mismatch')
    return {**view['profile_binding'], 'fictional': True, 'conditional_question_count': 41,
            'report_refs': [fact['ref'] for fact in reports]}


def mpf(evidence, plan, row_number, category, service, network):
    row = evidence['mpf_rows'][str(row_number)]
    fields = row['fields']
    identity = f"{fields['Contract_Year']}:{fields['Contract_ID']}:{fields['Plan_ID']:03d}:{fields['Segment_ID']:03d}"
    require(row['offering_id'] == plan == identity and row['source_row'] == row_number
            and (fields['Category Name'], fields['Service_Desc'], fields['Network_Description'])
            == (category, service, network), f'MPF row scope mismatch at {row_number}')
    return fields


def mpf_price(text):
    # Translate only the MPF notation present in these selected price cells.
    clean = text.replace('<br />', '\n')
    clean = re.sub(r'(\$[\d,.]+) per day for days ', r'\1 copay per day for days ', clean)
    clean = re.sub(r'(days \d+) through (\d+)', r'\1-\2', clean)
    clean = re.sub(r'^\$(\d+)-(\d+) copay per visit$', r'$\1-$\2 copay', clean)
    clean = re.sub(r'^(\d+)% per stay$', r'\1% coinsurance per stay', clean)
    return price_cell(clean)


def exact_copay(parsed, denominator, *, zero_unit_confirmed=False):
    if parsed['form'] == 'range':
        return 'RANGE_CONDITION_UNRESOLVED', None
    if parsed.get('kind') == 'coinsurance':
        return 'PERCENTAGE_CHARGE_BASE_UNSPECIFIED', None
    if parsed['form'] == 'amount' and parsed.get('kind') == 'copayment' and not parsed['issues']:
        if parsed['denominator'] == denominator or (
                zero_unit_confirmed and parsed['amount'] == '0'
                and parsed['denominator'] == {'state': 'unresolved'}):
            return None, usd(parsed['amount'], denominator)
    return 'EXACT_COPAY_OR_CHARGING_UNIT_UNRESOLVED', None


def premium(evidence, plan, months):
    oid = plan['offering_id']
    source = evidence['premium_source']['records'][oid]
    row = source['fields']
    require(f"2026:{row['Contract ID']}:{row['Plan ID']}:{row['Segment ID'].zfill(3)}" == oid
            and (row['County Name'], row['State Territory Abbreviation'], row['Plan Name'])
            == ('Collier', 'FL', plan['name']), 'Premium scope mismatch')
    field = source['amount_field']
    part_c = usd(row['Part C Premium'].strip().removeprefix('$'), 'month')
    part_d_text = row['Part D Total Premium'].strip()
    part_d = None if part_d_text == 'Not Applicable' else usd(part_d_text.removeprefix('$'), 'month')
    monthly = usd(row[field].strip().removeprefix('$'), 'month')
    if part_d is None:
        require(field == 'Part C Premium' and row['Monthly Consolidated Premium (Part C + D)'] == 'Not Applicable'
                and source.get('monthly_unit_review') == 'erickson_premium_review', 'MA-only premium basis mismatch')
    else:
        require(field == 'Monthly Consolidated Premium (Part C + D)'
                and Decimal(monthly['amount']) == Decimal(part_c['amount']) + Decimal(part_d['amount']),
                'Consolidated premium component mismatch')
    lines = [{'rate': monthly, 'quantity': months, 'quantity_unit': 'months'}]
    refs = [f'premium_source/records/{oid}', 'files/landscape_readme']
    if part_d is None:
        refs.append('files/erickson_premium_review')
    return {'status': 'computed_research_only', 'amount': subtotal(lines, 'plan_year'),
            'monthly_rate': monthly, 'lines': lines, 'source_refs': refs,
            'conditions': {'calendar_year': 2026, 'basis': field,
                           'part_c': part_c, 'part_d': part_d,
                           'part_d_applicability': 'not_applicable' if part_d is None else 'included_once'},
            'exclusions': ['Federal premiums', 'Optional packages', 'Subsidies and member-specific adjustments',
                           'Medical and prescription spending']}


def pcp(evidence, plan, visits):
    number = plan['mpf_pcp_row']
    fields = mpf(evidence, plan['offering_id'], number, 'Doctor visits', 'Primary', 'In-Network')
    carrier = evidence['prior_carrier_evidence'][plan['pcp_source']]
    require(carrier['offering_id'] == plan['offering_id'], 'Office source identity mismatch')
    code, rate = exact_copay(mpf_price(fields['Cost_Share']), 'visit', zero_unit_confirmed=True)
    refs = [f'mpf_rows/{number}', f"mpf_rows/{plan['mpf_deductible_row']}",
            f"prior_carrier_evidence/{plan['pcp_source']}", f"carrier_regions/{plan['cost_rules_source']}"]
    conditions = {'network': 'in_network', 'setting': 'ordinary in-person primary care office visit',
                  'deductible': plan['pcp_deductible'],
                  'mpf_flags': {key: fields[key] for key in ('Limit_Flag', 'Authorization_Flag', 'Referral_Flag')}}
    result = {'source_refs': refs, 'conditions': conditions,
              'exclusions': ['Procedures and separately billed services', 'Lab work', 'Specialist and telehealth visits']}
    if code or plan['pcp_deductible']['applies'] is not False:
        return {**result, 'status': 'held', 'amount': None,
                'reason_codes': [code or 'PCP_DEDUCTIBLE_APPLICATION_UNRESOLVED']}
    lines = [{'rate': rate, 'quantity': visits, 'quantity_unit': 'visits'}]
    return {**result, 'status': 'computed_research_only', 'amount': subtotal(lines, 'scenario'), 'lines': lines}


def hospital(evidence, plan, scenario):
    oid, number = plan['offering_id'], plan['mpf_hospital_row']
    fields = mpf(evidence, oid, number, 'Inpatient hospital coverage', None, 'In-Network')
    parsed = mpf_price(fields['Cost_Share'])
    require(parsed['form'] == 'day_schedule' and not parsed['issues'], 'Unsupported inpatient schedule')
    first = parsed['bands'][0]
    published = usd(first['amount'], 'inpatient_day')
    require(first['begin_day'] == 1
            and first['end_day'] == {'state': 'finite', 'value': plan['last_confirmed_charged_day']}
            and published['amount'] == plan['paid_daily_band_usd'],
            'MPF inpatient band diverges from the targeted carrier reading')
    days = scenario['inpatient_days']
    require(type(days) is int and days in (3, 4) and days <= first['end_day']['value'],
            'This proof covers only a three- or four-day stay within the verified first band')
    result = {'source_refs': [f'mpf_rows/{number}', f"mpf_rows/{plan['mpf_deductible_row']}",
                              f"carrier_regions/{plan['cost_rules_source']}",
                              f"carrier_regions/{plan['hospital_source']}"],
              'requested_inpatient_days': days,
              'published_first_band': {'start_day': 1, 'end_day': first['end_day']['value'], 'rate': published},
              'conditions': {'network': 'in_network', 'admissions': 1, 'reset': 'Starts at day one for this admission',
                             'counted_days': 'Formally admitted covered inpatient days, excluding discharge day',
                             'authorization': 'Required per MPF and assumed obtained for this scenario',
                             'referral_flag': fields['Referral_Flag'],
                             'in_network_medical_maximum': usd(plan['in_network_medical_maximum_usd'], 'plan_year'),
                             'deductible': plan['hospital_deductible']},
              'exclusions': ['Professional fees and separately billed services', 'Observation and outpatient stays',
                             'Transfers, readmissions and later charging bands', 'Unrelated services']}
    if plan['hospital_deductible']['applies']:
        return {**result, 'status': 'held', 'amount': None,
                'reason_codes': ['INPATIENT_DEDUCTIBLE_STATUS_UNSPECIFIED'],
                'unresolved': ['Whether the $1,000 annual medical deductible was met before admission. '
                               'If it was not met, the remaining balance and applicable covered charges '
                               'would be needed to establish when copays begin.']}
    lines = [{'day': day, 'rate': published, 'quantity': 1, 'quantity_unit': 'inpatient_day'}
             for day in range(1, days + 1)]
    return {**result, 'status': 'computed_research_only', 'amount': subtotal(lines, 'admission'), 'lines': lines}


def comparison(evidence, fixture):
    reject_economic_fields({'evidence': evidence, 'fixture': fixture})
    scope = fixture['requested_scope']
    scenario = fixture['scenario']
    require(scope == {'task': 'compare', 'year': 2026, 'county_fips': '12021',
                      'state': 'FL', 'mode': 'fictional_research_scenario'},
            'Only the 2026 Collier research scenario is supported')
    ids = [plan['offering_id'] for plan in evidence['plans']]
    require(ids == fixture['requested_offering_ids'] == ['2026:H1036:217:000', '2026:H5652:002:000'],
            'Only the two experiment offering identities are supported')
    require({k: v for k, v in scenario.items() if k != 'inpatient_days'} ==
                        {'premium_months': 12, 'ordinary_pcp_office_visits': 4,
                         'network': 'in_network', 'acute_inpatient_admissions': 1,
                         'all_services_hypothetically_covered': True,
                         'required_authorization_hypothetically_obtained': True,
                         'transfer_or_readmission': False, 'assistance_reduces_cost_sharing': False,
                         'enough_remaining_in_network_out_of_pocket_limit': True,
                         'inpatient_deductible_status': 'unspecified'},
            'Fictional scenario inputs are outside this proof')
    bindings = {k: v for k, v in evidence.items() if k != 'plans'}
    return {'schema': 'daylight-d91-mpf-comparison/1', 'purpose': 'fictional_research_comparison',
            'method_version': 'd91-mpf-experiment-20261104-r1',
            'accepted_for_reference': False, 'consumer_usable': False, 'recommendation_state': 'held',
            'scope': scope, 'profile_binding': profile_binding(fixture), 'scenario': deepcopy(scenario),
            'fictional_profile_sha256': canonical_sha256({k: v for k, v in fixture.items() if k != 'scenario'}),
            'scenario_sha256': canonical_sha256(scenario),
            'evidence_sha256': canonical_sha256(evidence), 'source_bindings': bindings,
            'unresolved_for_personal_use': ['Actual eligibility and enrollment for either plan',
                'Applicability of Erickson’s published Erickson Retirement Community residence requirement and any state variant',
                'Actual provider/network status, covered services and required authorization',
                'Any material source amendments and exact-purpose review'],
            'plans': [{'offering_id': plan['offering_id'], 'name': plan['name'],
                       'premium': premium(evidence, plan, scenario['premium_months']),
                       'pcp': pcp(evidence, plan, scenario['ordinary_pcp_office_visits']),
                       'hospital': hospital(evidence, plan, scenario)} for plan in evidence['plans']]}


def correct_hospital(result, evidence, days):
    corrected = deepcopy(result)
    corrected['scenario']['inpatient_days'] = days
    corrected['scenario_sha256'] = canonical_sha256(corrected['scenario'])
    for row, plan in zip(corrected['plans'], evidence['plans'], strict=True):
        row['hospital'] = hospital(evidence, plan, corrected['scenario'])
    return corrected


def source_replay(evidence):
    """Check the compact inputs against the retained records used in the proof."""
    files = evidence['files']
    paths = {key: ROOT / ref['path'] for key, ref in files.items()}
    for key, path in paths.items():
        require(file_sha(path) == files[key]['sha256'], f'Retained source changed: {key}')

    expected = evidence['mpf_rows']
    with paths['mpf_extract'].open(encoding='utf-8') as extract:
        actual = {str(row['source_row']): row for row in map(json.loads, extract)
                  if str(row['source_row']) in expected}
    require(actual == expected, 'MPF selected rows do not replay')

    source = evidence['premium_source']
    with ZipFile(paths['landscape_archive']) as archive:
        member = archive.read(source['member'])
    require(sha256(member).hexdigest() == source['member_sha256'], 'Landscape member changed')
    records = {x['record_ordinal']: x['fields'] for x in source['records'].values()}
    actual = {n: {k: row[k] for k in records[n]}
              for n, row in enumerate(csv.DictReader(StringIO(member.decode('utf-8-sig'))), 1)
              if n in records}
    require(actual == records, 'Exact premium records do not replay')
    catalog = {p['id']: p['name'] for p in load(paths['l02_collier_catalog'])}
    require(all(catalog.get(p['offering_id']) == p['name'] for p in evidence['plans']),
            'Frozen Collier identities do not match')

    expected_pages = {(region['offering_id'], page['physical_pdf_page']):
                      (region['document_sha256'], page['source_export'],
                       page['source_row_zero_based'], page['source_record_sha256'])
                      for region in evidence['carrier_regions'].values() for page in region['pages']}
    with gzip.open(paths['carrier_page_packet'], 'rt', encoding='utf-8') as packet:
        selected = {(p['offering_id'], p['record']['pdf_page']):
                    (p['record']['document_sha256'], p['source_export'], p['source_row'],
                     p['source_record_sha256']) for p in map(json.loads, packet)
                    if p['document_kind'] == 'EOC'
                    and (p['offering_id'], p['record']['pdf_page']) in expected_pages}
    require(selected == expected_pages, 'Targeted EOC pages do not replay')
    prior = evidence['prior_carrier_evidence']
    regions = {region['id']: region for region in load(paths['erickson_carrier_regions'])}
    for key in ('erickson_pcp', 'erickson_membership'):
        entry = prior[key]
        fragments = regions[entry['region_id']]['fragments']
        require(len(fragments) == len(entry['fragments']) and all(
            all(source[k] == v for k, v in bound.items())
            for source, bound in zip(fragments, entry['fragments'], strict=True)),
            'Retained Erickson evidence region does not replay')
    humana = prior['humana_pcp']
    with gzip.open(paths['carrier_normalization_candidates'], 'rt', encoding='utf-8') as candidates:
        normalized = next((row for row in map(json.loads, candidates)
                           if row['id'] == humana['candidate_id']), None)
    require(normalized is not None and normalized['source'] == humana['source']
            and normalized['offering_id'] == humana['offering_id']
            and normalized['context']['setting']['value'] == "PCP's office",
            'Retained Humana PCP office evidence does not replay')


def check(evidence, fixture):
    source_replay(evidence)
    result = comparison(evidence, fixture)
    corrected = correct_hospital(result, evidence, 4)
    require([p['premium']['amount']['amount'] for p in result['plans']] == ['0.00', '0.00']
            and [p['premium']['monthly_rate']['amount'] for p in result['plans']] == ['0.00', '0.00']
            and [p['pcp']['amount']['amount'] for p in result['plans']] == ['0.00', '0.00'],
            'Premium or PCP regression')
    require(result['scenario']['inpatient_days'] == 3, 'Correction check requires the saved three-day fixture')
    for observed, days, total in ((result, 3, '540.00'), (corrected, 4, '720.00')):
        humana, erickson = [p['hospital'] for p in observed['plans']]
        require(humana['amount']['amount'] == total
                and [(x['day'], x['rate']['amount']) for x in humana['lines']]
                    == [(day, '180.00') for day in range(1, days + 1)],
                'Humana inpatient day arithmetic regression')
        require(erickson['status'] == 'held' and erickson['amount'] is None
                and erickson['requested_inpatient_days'] == days
                and erickson['reason_codes'] == ['INPATIENT_DEDUCTIBLE_STATUS_UNSPECIFIED'],
                'Erickson inpatient hold was lost')
    unchanged = deepcopy(corrected)
    unchanged['scenario'] = result['scenario']
    unchanged['scenario_sha256'] = result['scenario_sha256']
    for before, after in zip(result['plans'], unchanged['plans'], strict=True):
        require(before['hospital']['source_refs'] == after['hospital']['source_refs'],
                'Correction changed a hospital source binding')
        after['hospital'] = before['hospital']
    require(unchanged == result, 'Correction changed data outside the hospital scenario')

    plan = '2026:H5652:002:000'
    negative = evidence['negative_check_rows']
    cases = [
        (negative['specialist_range'], 'Doctor visits', 'Specialist', 'In-Network',
         'visit', 'RANGE_CONDITION_UNRESOLVED'),
        (negative['out_of_network_hospital_percent'], 'Inpatient hospital coverage', None,
         'Out-of-Network', 'stay', 'PERCENTAGE_CHARGE_BASE_UNSPECIFIED'),
    ]
    for row, category, service, network, denominator, expected in cases:
        fields = mpf(evidence, plan, row, category, service, network)
        outcome = exact_copay(mpf_price(fields['Cost_Share']), denominator)
        require(outcome == (expected, None), f'Ambiguous MPF price was not held at {row}')
        print(f"MPF {row}: {fields['Cost_Share']} → {expected} (no dollar amount)")
    print('PASS: source replay, all six result cells, and hospital-only 3 → 4 day correction ($540 → $720).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hospital-days', type=int, choices=(3, 4))
    parser.add_argument('--check', action='store_true', help='Replay retained sources and exercise the experiment checks')
    args = parser.parse_args()
    evidence = load(HERE / 'evidence.json')
    fixture = load(HERE / 'fictional-profile.json')
    if args.check:
        check(evidence, fixture)
        return
    result = comparison(evidence, fixture)
    if args.hospital_days is not None and args.hospital_days != result['scenario']['inpatient_days']:
        result = correct_hospital(result, evidence, args.hospital_days)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
