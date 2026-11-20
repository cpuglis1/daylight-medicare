"""Account for each retained offering against the 14 D91 product families."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = {
    'plan': 'docs/product/recommendation-scope-2026-11-04-r1/PLAN.md',
    'catalog': 'docs/product/recommendation-scope-2026-11-04-r5/catalog.json',
    'identities': 'docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json',
    'main_mpf': 'docs/data/mpf-benefit-summary-2026-11-04-r1/collier-main.jsonl',
    'optional_mpf': 'docs/data/mpf-benefit-summary-2026-11-04-r1/collier-optional.jsonl',
    'quality': 'docs/data/l09-star-ratings-2026-10-28/build-r4/offerings.json',
    'case_replay': 'docs/product/recommendation-scope-2026-11-04-r7/case-results.json',
}
FAMILIES = {
    'identity': 'Offering identity and scope',
    'premium_deductible': 'Premiums and deductibles',
    'limits': 'Spending limits',
    'office_hospital': 'Office and hospital',
    'other_core': 'Other core medical costs',
    'extended_care': 'Extended care and equipment',
    'providers': 'Provider access',
    'medicines': 'Medicines',
    'pharmacy_cost': 'Pharmacy and drug costs',
    'away_care': 'Care away from home',
    'supplemental': 'Supplemental benefits',
    'quality': 'Quality',
    'transition': 'Current coverage and transitions',
    'alternatives': 'Alternative paths and next help',
}
OTHER_CORE = ('Emergency care/urgent care', 'Outpatient hospital coverage',
              'Diagnostic procedures/lab services/imaging', 'Ground Ambulance')
EXTENDED = ('Skilled Nursing Facility', 'Rehabilitation services', 'Medical equipment/supplies')
SUPPLEMENTAL = ('Diagnostic and Preventive dental', 'Comprehensive dental', 'Vision', 'Hearing',
                'Optional supplemental benefits?')


def build():
    blobs = {key: (ROOT / path).read_bytes() for key, path in INPUTS.items()}
    table = blobs['plan'].decode().split('## 5. The product data package')[1].split('## 6.')[0]
    names = [line.split(' | ')[0][2:] for line in table.splitlines() if line.startswith('| ')]
    if names[2:] != list(FAMILIES.values()):
        raise ValueError('Product family scope changed')

    catalog = json.loads(blobs['catalog'])
    ids = [p['offering_id'] for p in catalog['plans']]
    identity = {x['id']: x for x in json.loads(blobs['identities'])}
    if len(ids) != 72 or ids != sorted(identity) or ids != catalog['scope']['offering_ids']:
        raise ValueError('Catalog and frozen L02 scope differ')
    if catalog['purpose']['consumer_usable'] or catalog['purpose']['accepted_release_id'] is not None:
        raise ValueError('Catalog purpose changed')
    ratings = {x['offering_id']: x for x in json.loads(blobs['quality'])}
    cases = json.loads(blobs['case_replay'])

    main_rows = defaultdict(lambda: defaultdict(list))
    optional_rows = defaultdict(list)
    for line in blobs['main_mpf'].splitlines():
        row = json.loads(line)
        main_rows[row['offering_id']][row['fields']['Category Name']].append(row['source_row'])
    for line in blobs['optional_mpf'].splitlines():
        row = json.loads(line)
        optional_rows[row['offering_id']].append(row['source_row'])
    if set(main_rows) != set(ids) or set(optional_rows) - set(ids) or set(ids) - set(ratings):
        raise ValueError('Source scope join failed')

    offerings = []
    published_counts, scenario_counts = Counter(), Counter()
    for plan in catalog['plans']:
        oid = plan['offering_id']
        published = plan['published']
        scenarios = plan['scenarios']
        source_rows = main_rows[oid]
        rating = ratings[oid]
        drug_replays = [case['form'] for case in cases['cases'] if oid in case['medicine_by_offering']]
        provider_replay = cases['provider_by_offering'].get(oid, {}).get('december_status')
        fields = {key: {'state': value['state'], 'reason_codes': value.get('reason_codes', [])}
                  for key, value in published.items() if key != 'personal_checks'}
        outcomes = {'premium_12_months': scenarios['premium_12_months'],
                    'pcp_four_visits': scenarios['pcp_four_visits'],
                    **{f'hospital_{day}': value for day, value in scenarios['hospital_days'].items()}}
        prepared_scenarios = {key: {'status': value['status'], 'reason_codes': value.get('reason_codes', [])}
                              for key, value in outcomes.items()}
        published_counts.update(row['state'] for row in fields.values())
        scenario_counts.update(row['status'] for row in prepared_scenarios.values())
        families = {
            'identity': {**fields['coverage'], 'geography': identity[oid]['geography'],
                         'enrollment_status': identity[oid]['enrollment_status']},
            'premium_deductible': {key: fields[key] for key in
                ('part_b_reduction', 'medical_deductible', 'part_d_deductible')},
            'limits': fields['medical_maximums'],
            'office_hospital': {key: fields[key] for key in
                ('primary_care_in_network', 'specialist_in_network', 'hospital_in_network')},
            'other_core': {'mpf_source_rows': {key: source_rows[key] for key in OTHER_CORE}},
            'extended_care': {'mpf_source_rows': {key: source_rows[key] for key in EXTENDED},
                              'home_health': 'carrier_or_pbp_extraction_needed'},
            'providers': {'state': 'requires_case_lookup', 'fictional_r7': provider_replay},
            'medicines': {'state': 'requires_case_lookup' if identity[oid]['drug'] == 'Yes'
                          else 'no_included_part_d', 'fictional_r7_forms': drug_replays},
            'pharmacy_cost': {'state': 'requires_case_lookup' if identity[oid]['drug'] == 'Yes'
                              else 'no_included_part_d', 'fictional_r7_forms': drug_replays},
            'away_care': {'state': 'requires_plan_terms_and_case_destination'},
            'supplemental': {'mpf_source_rows': {key: source_rows[key] for key in SUPPLEMENTAL},
                             'optional_package_rows': optional_rows.get(oid, [])},
            'quality': {key: rating[key] for key in ('contract', 'primary_observation_id', 'source_status')},
            'transition': {'state': 'requires_case_history_and_rule_check'},
            'alternatives': {'state': 'requires_path_level_comparison'},
        }
        offerings.append({'offering_id': oid, 'families': families, 'scenarios': prepared_scenarios})

    return {
        'schema': 'daylight-d91-collier-recommendation-gaps/1',
        'scope': catalog['scope'], 'consumer_purpose': 'held',
        'input_bindings': {key: {'path': path, 'sha256': sha256(blobs[key]).hexdigest()}
                           for key, path in INPUTS.items()},
        'families': FAMILIES, 'published_states': dict(published_counts),
        'scenario_states': dict(scenario_counts), 'offerings': offerings,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = HERE / 'offering-gaps.json'
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if output.read_text(encoding='utf-8') != rendered:
            raise SystemExit('Gap matrix differs from its recorded inputs')
    else:
        output.write_text(rendered, encoding='utf-8')
    print('72 offerings × 14 product families accounted for')
