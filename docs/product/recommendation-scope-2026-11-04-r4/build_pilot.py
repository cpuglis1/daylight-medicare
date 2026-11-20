"""Build or verify the D91 Collier 2026 comparison candidate offline."""
import argparse
from copy import deepcopy
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent / 'recommendation-scope-2026-11-04-r2/experiment'
PARENT_DIGESTS = {
    'run.py': 'e807117fecf0d41a052671b8d2bd1be545ad2ed51f7fcf2132cf9dad4603595d',
    'evidence.json': 'd61b6b665284485f3c4fa1607bbd6a370a408947dcc7310f2d3b89e80d71768e',
    'fictional-profile.json': 'cf8897fbe8a696f36ba04b1473b39431f746ba119c59b563432265f73aae2c7a',
    'comparison.json': '9087a9d1a76f2090318f493b6051f25435a82c5685143a4cdd445aa6c4f07c23',
}
for name, digest in PARENT_DIGESTS.items():
    if sha256((PARENT / name).read_bytes()).hexdigest() != digest:
        raise ValueError(f'D91 experiment binding changed: {name}')
sys.path.insert(0, str(PARENT))
import run as prior


def refs(*paths):
    return list(paths)


def read_selected_sources(readings):
    evidence = prior.load(PARENT / 'evidence.json')
    prior.check(evidence, prior.load(PARENT / 'fictional-profile.json'))
    for key, source in readings['carrier_files'].items():
        prior.require(prior.file_sha(ROOT / source['path']) == source['sha256'], f'Carrier PDF changed: {key}')

    catalog = prior.load(ROOT / evidence['files']['l02_collier_catalog']['path'])
    prior.require(len(catalog) == 72, 'Frozen Collier catalog changed')
    by_id = {row['id']: row for row in catalog}
    anchor = by_id['2026:H1036:217:000']
    eligible = sorted(row['id'] for row in catalog
                      if (row['category'], row['plan_type'], row['snp'], row['drug']) == ('MA-PD', 'HMO', 'No', 'Yes')
                      and row['parent'] != anchor['parent'])
    prior.require(len(eligible) == 8 and eligible[0] == '2026:H1032:198:000', 'Comparable plan rule changed')
    plans = readings['plans']
    prior.require([(r['offering_id'], r['role']) for r in plans] == [
        (anchor['id'], 'pilot'), (eligible[0], 'pilot'), ('2026:H5652:002:000', 'regression_only')],
        'Pilot or regression identities changed')

    selected_rows = {str(n) for p in plans for n in p['mpf_rows'].values()}
    with (ROOT / evidence['files']['mpf_extract']['path']).open(encoding='utf-8') as extract:
        evidence['mpf_rows'].update({str(row['source_row']): row for row in map(json.loads, extract)
                                     if str(row['source_row']) in selected_rows})
    for plan in plans:
        for number in plan['mpf_rows'].values():
            prior.require(evidence['mpf_rows'][str(number)]['offering_id'] == plan['offering_id'],
                          f'MPF offering mismatch at row {number}')

    premium = evidence['premium_source']
    with ZipFile(ROOT / evidence['files']['landscape_archive']['path']) as archive:
        member = archive.read(premium['member'])
    records = {p['landscape_row']: p for p in plans}
    columns = set(next(iter(premium['records'].values()))['fields']) | {
        'Annual Part D Deductible Amount', 'Part D Basic Premium', 'Part D Supplemental Premium',
    }
    for n, row in enumerate(csv.DictReader(StringIO(member.decode('utf-8-sig'))), 1):
        if n in records:
            plan = records.pop(n)
            oid = plan['offering_id']
            prior.require(row['Plan Name'] == by_id[oid]['name'], 'Exact Landscape name mismatch')
            part_d = by_id[oid]['drug'] == 'Yes'
            premium['records'][oid] = {
                **premium['records'].get(oid, {}), 'record_ordinal': n,
                'fields': {k: row[k] for k in sorted(columns)},
                'amount_field': 'Monthly Consolidated Premium (Part C + D)' if part_d else 'Part C Premium',
            }
        if not records:
            break
    prior.require(not records, 'Landscape rows are incomplete')

    evidence['files'].update(readings['carrier_files'])
    evidence['carrier_regions'].update(readings['carrier_regions'])
    for row in plans:
        evidence['prior_carrier_evidence'][row['carrier'] + '_pilot_office'] = {
            'offering_id': row['offering_id'],
            'source_refs': [f"carrier_regions/{row['carrier']}_office"],
        }
    return evidence, by_id, eligible


def published_fields(reading, catalog, evidence):
    prefix = reading['carrier']
    oid = reading['offering_id']
    rows = reading['mpf_rows']
    landscape_ref = f'premium_source/records/{oid}'

    def carrier(name):
        return f'carrier_regions/{prefix}_{name}'

    def mpf_ref(name):
        return f'mpf_rows/{rows[name]}'

    def mpf_fields(name):
        return evidence['mpf_rows'][str(rows[name])]['fields']

    def fact(value, sources, *, conditions=None):
        return {'state': 'published_candidate', 'value': value, 'source_refs': sources,
                **({'conditions': conditions} if conditions else {})}

    deductible = prior.usd(reading['medical_deductible_usd'], 'plan_year')
    native_deductible = mpf_fields('medical_deductible')['Cost_Share']
    expected_deductible = (0 if deductible['amount'] == '0.00' else '$1,000 In-network')
    prior.require(native_deductible == expected_deductible, 'Medical deductible source mismatch')
    maximum = mpf_fields('medical_maximum')['Cost_Share']
    for network, amount in reading['medical_maximums'].items():
        expected = f'${int(prior.Decimal(amount)):,} {network.replace("_", "-").capitalize()}'
        prior.require(expected in maximum, 'Network-specific medical maximum mismatch')
    drug = reading['part_d_deductible']
    drug_amount = evidence['premium_source']['records'][oid]['fields']['Annual Part D Deductible Amount'].strip()
    if drug:
        prior.require(drug_amount == '$' + drug['annual_usd'], 'Part D deductible source mismatch')
        drug_deductible = fact(prior.usd(drug['annual_usd'], 'plan_year'), refs(landscape_ref, carrier('drug')),
                               conditions={'tiers': drug['tiers'], 'exemptions': ['Covered insulin', 'Most adult Part D vaccines']})
    else:
        prior.require(drug_amount == 'Not Applicable', 'No-Rx source mismatch')
        drug_deductible = {'state': 'not_applicable', 'reason': 'No Part D benefit in this plan.',
                           'source_refs': refs(landscape_ref, carrier('identity'))}

    reduction = reading['part_b_reduction']
    reduction_fact = fact(prior.usd(reduction['monthly_usd'], 'month'), refs(carrier('part_b')),
                          conditions={'maximum': reduction['maximum'], 'qualification': reduction['condition'],
                                      'application_to_plan_premium_scenario': 'excluded'})

    return {
        'coverage': fact({'plan_type': catalog['plan_type'], 'category': catalog['category'],
                          'includes_part_d': catalog['drug'] == 'Yes', 'snp': catalog['snp'] == 'Yes',
                          'residence_requirement': reading.get('residence_requirement')},
                         refs('files/l02_collier_catalog', landscape_ref, carrier('identity'))),
        'part_b_reduction': reduction_fact,
        'medical_deductible': fact(deductible, refs(mpf_ref('medical_deductible'), carrier('medical_rules')),
                                  conditions={'applies_to_ordinary_pcp': reading['pcp_deductible'],
                                              'applies_to_inpatient': reading['inpatient_deductible']}),
        'medical_maximums': fact({network: prior.usd(amount, 'plan_year')
                                  for network, amount in reading['medical_maximums'].items()},
                                 refs(mpf_ref('medical_maximum'), carrier('medical_rules')),
                                 conditions={'scope': 'Covered medical costs counted under the applicable limit. Premiums, Part D and listed exclusions are separate.'}),
        'part_d_deductible': drug_deductible,
        'specialist_in_network': fact(mpf_fields('specialist')['Cost_Share'],
                                      refs(mpf_ref('specialist'), carrier('office')),
                                      conditions={'access': reading['specialist_access']}),
        'hospital_in_network': fact(mpf_fields('hospital')['Cost_Share'].replace('<br />', '\n'),
                                    refs(mpf_ref('hospital'), carrier('hospital'), carrier('medical_rules')),
                                    conditions={'access': reading['hospital_access'], 'scope': reading['hospital_scope']}),
        'personal_checks': {check: {'state': 'not_checked'} for check in (
            'enrollment_and_eligibility', 'doctor_and_site_network', 'medicine_formulary_and_cost',
            'personal_part_b_billing', 'stated_must_haves')},
    }


def build_offer(reading, catalog, evidence, scenario):
    oid = reading['offering_id']
    carrier = reading['carrier']
    rows = reading['mpf_rows']
    deductible = reading['inpatient_deductible']
    plan = {
        'offering_id': oid, 'name': catalog['name'],
        'mpf_pcp_row': rows['primary'], 'mpf_hospital_row': rows['hospital'],
        'mpf_deductible_row': rows['medical_deductible'],
        'pcp_source': carrier + '_pilot_office', 'cost_rules_source': carrier + '_medical_rules',
        'hospital_source': carrier + '_hospital',
        'pcp_deductible': {'applies': reading['pcp_deductible'], 'reason': (
            'The selective medical deductible excludes ordinary PCP visits.' if deductible else
            'The medical plan deductible is $0.')},
        'hospital_deductible': {'applies': deductible, 'annual_usd': reading['medical_deductible_usd'],
                               'reason': 'Selective annual deductible precedes copays.' if deductible else 'No medical deductible.'},
        'last_confirmed_charged_day': reading['first_band']['end_day'],
        'paid_daily_band_usd': reading['first_band']['usd_per_day'],
        'in_network_medical_maximum_usd': reading['medical_maximums']['in_network'],
    }
    premium = prior.premium(evidence, plan, scenario['premium_months'])
    premium['source_refs'].append(f'carrier_regions/{carrier}_premium')
    premium['exclusions'].append('Published Part B premium reduction')
    pcp = prior.pcp(evidence, plan, scenario['ordinary_pcp_office_visits'])
    inpatient = {}
    for days in (3, 4):
        variant = prior.hospital(evidence, plan, {**scenario, 'inpatient_days': days})
        variant['conditions']['authorization'] = reading['hospital_access']
        variant['conditions']['counted_days'] = 'Formally admitted covered inpatient days. Discharge day is excluded.'
        inpatient[str(days)] = variant
    return {
        'offering_id': oid, 'name': catalog['name'], 'role': reading['role'],
        'published': published_fields(reading, catalog, evidence),
        'scenarios': {'premium_12_months': premium, 'pcp_four_visits': pcp, 'hospital_days': inpatient},
    }


def prior_reference(readings):
    r4 = ROOT / 'docs/data/l03-ma-benefits-2026-10-25/bounded-reference-r4'
    manifest = prior.file_sha(r4 / 'manifest.json')
    prior.require(manifest == readings['review']['prior_r4_reference_manifest_sha256'], 'Accepted r4 manifest changed')
    entries_digest = prior.file_sha(r4 / 'entries.json')
    prior.require(entries_digest == prior.load(r4 / 'manifest.json')['files_sha256']['entries.json'],
                  'Accepted r4 entries changed')
    entries = prior.load(r4 / 'entries.json')
    fields = readings['review']['prior_r4_humana_fields']
    overlap = {row['field']: row['id'] for row in entries
               if row['offering_id'] == '2026:H1036:217:000' and row['field'] in fields}
    prior.require(set(overlap) == set(fields), 'Exact Humana prior reference overlap changed')
    return {'manifest_sha256': manifest, 'entries_sha256': entries_digest, 'humana_entry_ids': overlap,
            'purpose': 'Existing bounded published-reference lookup only'}


def build(readings):
    evidence, catalog, eligible = read_selected_sources(readings)
    fixture = prior.load(PARENT / 'fictional-profile.json')
    scenario = deepcopy(fixture['scenario'])
    scenario.pop('inpatient_days')
    scenario['supported_inpatient_days'] = [3, 4]
    scenario['required_referral_hypothetically_obtained'] = True
    plans = [build_offer(row, catalog[row['offering_id']], evidence, scenario) for row in readings['plans']]
    output = {
        'schema': 'daylight-d91-collier-pilot/1',
        'release_candidate_id': 'D91-2026-COLLIER-EDUCATIONAL-PILOT-r4',
        'state': 'producer_reviewed_pending_independent_review_and_acceptance',
        'scope': {'coverage_year': 2026, 'county_fips': '12021', 'county': 'Collier', 'state': 'FL',
                  'market': 'Medicare Advantage', 'retained_catalog_count': 72,
                  'pilot_ids': [p['offering_id'] for p in plans if p['role'] == 'pilot'],
                  'regression_only_ids': [p['offering_id'] for p in plans if p['role'] == 'regression_only']},
        'purpose': {'proposed': 'limited_educational_comparison_with_fictional_components',
                    'accepted_release_id': None, 'consumer_usable': False,
                    'personal_comparison': 'held', 'recommendation': 'held'},
        'selection': {'method': 'Lowest exact offering ID among retained non-SNP MA-PD HMOs from a parent other than the Humana anchor.',
                      'eligible_ids': eligible, 'comparison_order_is_rank': False},
        'profile_binding': prior.profile_binding(fixture),
        'scenario': scenario,
        'methods': {'parent': 'd91-mpf-experiment-20261104-r1', 'parent_sha256': PARENT_DIGESTS,
                    'supported_requests': ['12_month_plan_premium', 'four_ordinary_in_network_pcp_visits',
                                           'one_acute_in_network_admission_3_or_4_covered_days'],
                    'reduction_treatment': 'Published separately. No offset in the plan-premium calculation.'},
        'review': {**readings['review'], 'prior_reference': prior_reference(readings),
                   'source_readings_sha256': prior.file_sha(HERE / 'source-readings.json'),
                   'builder_sha256': prior.file_sha(Path(__file__).resolve())},
        'source_bindings': {k: v for k, v in evidence.items() if k != 'plans'},
        'plans': plans,
    }
    prior.reject_economic_fields(output)
    return output


def verify(data):
    expected = [('540.00', '720.00'), ('1200.00', '1600.00'), (None, None)]
    def amount(result):
        return result['amount']['amount'] if result['amount'] else None

    for plan, amounts in zip(data['plans'], expected, strict=True):
        scenario = plan['scenarios']
        prior.require(amount(scenario['premium_12_months']) == amount(scenario['pcp_four_visits']) == '0.00',
                      'Baseline premium or visit amount changed')
        three, four = (scenario['hospital_days'][days] for days in ('3', '4'))
        prior.require((amount(three), amount(four)) == amounts
                      and three['source_refs'] == four['source_refs']
                      and three['conditions'] == four['conditions'], 'Hospital correction changed amounts or conditions')
        if plan['role'] == 'regression_only':
            prior.require(three['reason_codes'] == four['reason_codes'] == ['INPATIENT_DEDUCTIBLE_STATUS_UNSPECIFIED'],
                          'Erickson inpatient hold was lost')
        else:
            prior.require(four['lines'][:3] == three['lines'] and four['lines'][-1]['day'] == 4,
                          'Only one covered inpatient day should be added')

    def source_refs(value):
        if isinstance(value, dict):
            yield from value.get('source_refs', [])
            for child in value.values():
                yield from source_refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from source_refs(child)

    for ref in source_refs(data['plans']):
        target = data['source_bindings']
        for key in ref.split('/'):
            target = target[key]
        prior.require(bool(target), f'Empty source reference: {ref}')
    prior.require(data['purpose']['consumer_usable'] is False and data['purpose']['accepted_release_id'] is None,
                  'Candidate cannot grant consumer authority')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--check', action='store_true', help='Replay sources and compare with the committed candidate.')
    args = cli.parse_args()
    output = build(prior.load(HERE / 'source-readings.json'))
    verify(output)
    path = HERE / 'pilot.json'
    contents = json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    if args.check:
        prior.require(path.read_text(encoding='utf-8') == contents, 'Frozen pilot candidate does not replay')
        print('PASS: two pilot plans, one regression, exact source replay, purpose holds, 3 → 4 days.')
    else:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(contents)


if __name__ == '__main__':
    main()
