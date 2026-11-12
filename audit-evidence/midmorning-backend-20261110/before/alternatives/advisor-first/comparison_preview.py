"""D91 server-owned educational preview for a fresh local fixture session."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from guest_profiles import ProfileError

EXPERIMENT = Path(__file__).resolve().parents[2] / 'docs/product/recommendation-scope-2026-11-04-r2/experiment'
PINNED = {
    'comparison.json': '9087a9d1a76f2090318f493b6051f25435a82c5685143a4cdd445aa6c4f07c23',
    'run.py': 'e807117fecf0d41a052671b8d2bd1be545ad2ed51f7fcf2132cf9dad4603595d',
    'evidence.json': 'd61b6b665284485f3c4fa1607bbd6a370a408947dcc7310f2d3b89e80d71768e',
    'fictional-profile.json': 'cf8897fbe8a696f36ba04b1473b39431f746ba119c59b563432265f73aae2c7a',
}
OFFERINGS = ('2026:H1036:217:000', '2026:H5652:002:000')
MPF_URL = 'https://www.cms.gov/files/zip/cy-2026-mpf-benefit-summary.zip'
LANDSCAPE_URL = 'https://www.cms.gov/files/zip/cy2026-landscape-202609.zip'


def load_preview():
    """Replay exact inputs once. Requests use two cached, server-computed views."""
    for name, expected in PINNED.items():
        if sha256((EXPERIMENT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'D91 preview evidence changed: {name}')
    command = [sys.executable, '-B', str(EXPERIMENT / 'run.py')]
    subprocess.run([*command, '--check'], check=True, capture_output=True, timeout=20)
    results = {
        3: json.loads((EXPERIMENT / 'comparison.json').read_text()),
        4: json.loads(subprocess.check_output([*command, '--hospital-days', '4'], timeout=20)),
    }
    evidence = results[3]['source_bindings']
    mpf_path = EXPERIMENT.parents[3] / evidence['files']['mpf_extract']['path']
    with mpf_path.open(encoding='utf-8') as extract:
        selected = [row for row in map(json.loads, extract) if row['offering_id'] in OFFERINGS]
    return {days: project(result, selected, days) for days, result in results.items()}


def project(result, selected, days):
    if (result['consumer_usable'] is not False or result['accepted_for_reference'] is not False
            or result['recommendation_state'] != 'held'
            or tuple(plan['offering_id'] for plan in result['plans']) != OFFERINGS
            or result['scope']['year'] != 2026 or result['scope']['county_fips'] != '12021'
            or result['scenario']['inpatient_days'] != days):
        raise ValueError('Unexpected D91 experiment scope')
    evidence = result['source_bindings']
    plans = []
    for plan in result['plans']:
        oid = plan['offering_id']

        def term(category, service=None, networks=('In-Network',)):
            rows = [r for r in selected if r['offering_id'] == oid
                    and (r['fields']['Category Name'], r['fields']['Service_Desc']) == (category, service)
                    and r['fields']['Network_Description'] in networks]
            if len(rows) != 1:
                raise ValueError('D91 display source row is ambiguous')
            row = rows[0]
            return row['fields'], row['source_row']

        specialist, specialist_row = term('Doctor visits', 'Specialist')
        maximum, maximum_row = term(
            'Maximum out-of-pocket enrollee responsibility (does not include prescription drugs)',
            networks=('In-Network', None))
        inpatient, hospital_row = term('Inpatient hospital coverage')
        premium, pcp, hospital = (plan[key] for key in ('premium', 'pcp', 'hospital'))
        part_d = premium['conditions']['part_d_applicability'] == 'included_once'
        pcp_row, deductible_row = (int(ref.split('/')[1]) for ref in pcp['source_refs'][:2])
        landscape = evidence['premium_source']['records'][oid]['record_ordinal']
        hospital_deductible = hospital['conditions']['deductible']
        plans.append({
            'id': oid.split(':', 1)[1].replace(':', '-'), 'name': plan['name'],
            'premium_monthly': premium['monthly_rate']['amount'],
            'premium_12_months': premium['amount']['amount'],
            'pcp_rate': pcp['lines'][0]['rate']['amount'],
            'pcp_four_visits': pcp['amount']['amount'],
            'pcp_deductible': ('The medical deductible does not apply to these visits.' if
                               hospital_deductible['applies'] else
                               'The medical deductible is $0.'),
            'hospital_rate': hospital['published_first_band']['rate']['amount'],
            'hospital_band_end': hospital['published_first_band']['end_day'],
            'hospital_copay': hospital['amount']['amount'] if hospital['amount'] else None,
            'hospital_hold': ('The balance on the $1,000 annual medical deductible at admission is unspecified.'
                              if hospital['status'] == 'held' else None),
            'medical_deductible': hospital_deductible.get('annual_usd', '0.00'),
            'medical_maximum': maximum['Cost_Share'].replace('<br />', '\n'),
            'specialist': specialist['Cost_Share'],
            'specialist_access': ('MPF flags prior authorization and referral.' if
                                  specialist['Referral_Flag'] == 'Yes' else
                                  'MPF flags prior authorization and lists no referral requirement.'),
            'inpatient_schedule': inpatient['Cost_Share'].replace('<br />', '\n'),
            'short_name': 'Humana Gold Plus' if part_d else 'Erickson Liberty no Rx',
            'coverage': ('HMO · Includes Part D prescription coverage.' if part_d else
                         'HMO-POS · No Part D prescription coverage. Erickson Retirement Community residence required.'),
            'drug_deductible': '$615 annually on tiers 4 and 5' if part_d else 'No Part D benefit in this plan',
            'drug_deductible_note': ('Covered insulin and most adult Part D vaccines are exempt.'
                                     if part_d else None),
            'source_locations': [
                f'CMS September 2026 Landscape, Collier data record {landscape}.',
                f'CMS MPF workbook dated 2025-12-23, rows {pcp_row} (PCP), {specialist_row} (specialist), '
                f'{deductible_row} (deductible), {maximum_row} (medical maximum) and {hospital_row} (hospital).',
                ('2026 Evidence of Coverage, PDF pages 12 and 110 (drug deductible) and '
                 'chapter 4, PDF pages 43 and 56–57. '
                 'Summary of Benefits, PDF page 4.' if part_d else
                 '2026 Evidence of Coverage, PDF page 7 (residence) and chapter 4, '
                 'PDF pages 39–40, 68–70 and 91–92.'),
            ],
        })
    return {'state': 'local_fixture_only', 'days': days, 'plans': plans,
            'sources': [{'label': 'CMS September 2026 plan landscape ZIP', 'url': LANDSCAPE_URL},
                        {'label': 'CMS 2026 benefit summary ZIP', 'url': MPF_URL}]}


def preview_for_snapshot(previews, days, response):
    if type(days) is not int or days not in previews:
        raise ProfileError('Choose three or four covered inpatient days.', 422)
    fields = response['guide']['fields']
    county = fields.get('comparison.scope.county', {}).get('value')
    year_report = response['record']['facts'].get('RC03', {}).get('value', {})
    year = year_report.get('year') or year_report.get('choice')
    if (isinstance(county, dict) and county.get('fips') not in (None, '12021')
            or year and str(year).isdigit() and str(year) != '2026'):
        raise ProfileError('This example uses 2026 Collier County data. Your comparison needs sources for the year and county you reported.', 422)
    return deepcopy(previews[days])
