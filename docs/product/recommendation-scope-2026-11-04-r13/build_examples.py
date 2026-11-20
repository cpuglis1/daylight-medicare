"""Add the checked r5 cost examples to the offline r12 catalog."""

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUTS = {
    'scenario_catalog': {
        'path': '../recommendation-scope-2026-11-04-r5/catalog.json',
        'sha256': '2c0198a2b848a26e09440e3daf1355c0ec5e45b107ef7de63784cd48f1aa3756',
    },
    'display_catalog': {
        'path': '../recommendation-scope-2026-11-04-r12/display-candidate.json',
        'sha256': '62ae73885700fb67d3f171d6807aaf6101f27801ab48246191cda34ab022e32f',
    },
}
EXAMPLES = {
    'premium_12_months': '12 months of plan premiums',
    'pcp_four_visits': 'Four in-network primary care office visits',
    'hospital_3': 'One in-network admission, three covered days',
    'hospital_4': 'Same admission, four covered days',
}
HOSPITAL_FIELDS = ('hospital_in_network', 'medical_deductible', 'medical_maximums')
DEPENDENCIES = {
    'premium_12_months': ('plan_premium',),
    'pcp_four_visits': ('primary_care_in_network', 'medical_deductible'),
    'hospital_3': HOSPITAL_FIELDS,
    'hospital_4': HOSPITAL_FIELDS,
}


def load(name):
    binding = INPUTS[name]
    raw = (HERE / binding['path']).read_bytes()
    if sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError(f'Input changed. Review the new {name} before rebuilding.')
    return json.loads(raw)


def project_example(source, fields, dependencies):
    missing = {key: fields[key] for key in dependencies if fields[key]['state'] != 'published_candidate'}
    source_held = source['status'] == 'held'
    if source_held:
        if source['amount'] is not None or not source['reason_codes']:
            raise ValueError('Invalid source hold')
    elif source['status'] != 'computed_research_only' or source['amount'] is None:
        raise ValueError('Unexpected scenario status')
    reasons = [*source.get('reason_codes', []),
               *(reason for field in missing.values() for reason in field['reason_codes'])]
    if missing:
        reasons.append('DEPENDENT_PUBLISHED_FIELD_UNAVAILABLE')
    held = source_held or bool(missing)
    return {'state': 'held' if held else 'numeric_candidate',
            'amount': None if held else source['amount'], 'reason_codes': list(dict.fromkeys(reasons))}


def build():
    research = load('scenario_catalog')
    catalog = load('display_catalog')
    ids = [row['display_candidate']['offering_id'] for row in catalog['plans']]
    if len(set(ids)) != 72 or ids != [p['offering_id'] for p in research['plans']]:
        raise ValueError('The two inputs must cover the same 72 exact offerings in the same order')
    if (catalog['scope']['year'], catalog['scope']['county_fips']) != (
            research['scope']['coverage_year'], research['scope']['county_fips']):
        raise ValueError('The year or county differs between inputs')
    if catalog['inputs']['r5/catalog']['sha256'] != INPUTS['scenario_catalog']['sha256']:
        raise ValueError('The display input did not use this scenario catalog')

    plans = []
    for row, previous in zip(catalog['plans'], research['plans'], strict=True):
        display = row['display_candidate']
        if (display['name'], display['type']) != (previous['name'], previous['published']['coverage']['value']['plan_type']):
            raise ValueError(f'Identity mismatch for {previous["offering_id"]}')
        scenarios = previous['scenarios']
        outcomes = {
            'premium_12_months': scenarios['premium_12_months'],
            'pcp_four_visits': scenarios['pcp_four_visits'],
            'hospital_3': scenarios['hospital_days']['3'],
            'hospital_4': scenarios['hospital_days']['4'],
        }
        examples = {key: project_example(outcomes[key], display['benefits'], DEPENDENCIES[key])
                    for key in EXAMPLES}
        plans.append({
            'display_candidate': {**display, 'cost_examples': examples},
            'review_evidence': {
                **row['review_evidence'],
                'r5_scenario_plan': previous['offering_id'],
                'r5_scenario_source_refs': {key: outcomes[key]['source_refs'] for key in EXAMPLES},
            },
        })
    counts = {key: dict(Counter(row['display_candidate']['cost_examples'][key]['state'] for row in plans))
              for key in EXAMPLES}
    return {
        'schema': 'daylight-d91-published-benefits-and-cost-examples-review/1',
        'decision': 'pending',
        'accepted_release_id': None,
        'proposed_purpose': 'published_benefits_and_fictional_cost_example_display',
        'consumer_usable': False,
        'scope': catalog['scope'],
        'inputs': INPUTS,
        'fields': catalog['fields'],
        'counts': catalog['counts'],
        'example_columns': EXAMPLES,
        'example_counts': counts,
        'example_assumptions': research['scenario'],
        'example_methods': research['methods'],
        'example_source_paths': {
            'premium_12_months': 'scenarios/premium_12_months',
            'pcp_four_visits': 'scenarios/pcp_four_visits',
            'hospital_3': 'scenarios/hospital_days/3',
            'hospital_4': 'scenarios/hospital_days/4',
        },
        'example_display_dependencies': DEPENDENCIES,
        'example_hold_reasons': {
            **research['hold_dictionary'],
            'DEPENDENT_PUBLISHED_FIELD_UNAVAILABLE': 'A published field required by this example is unavailable.',
        },
        'plans': plans,
    }


def render(packet):
    lines = [
        '# Bounded cost examples for 72 Collier plans',
        '',
        '2026 Collier County Medicare Advantage · Fictional utilization · Offline review candidate',
        '',
        '[Plan names, IDs, types and restrictions](../recommendation-scope-2026-11-04-r11/CATALOG.md) · '
        '[Published costs and benefits](../recommendation-scope-2026-11-04-r12/CATALOG.md) · '
        '[Methods, holds and approvals](REVIEW.md)',
        '',
        '- **Premiums.** Twelve months at the published monthly plan premium. The plan’s Part D premium is included once '
        'where applicable. Part B premiums, Part B reductions, optional packages and personal adjustments are separate.',
        '- **Primary care.** Four ordinary covered in-person office visits with in-network primary care. '
        'The example covers visit copays only. Labs, procedures and other charges are separate.',
        '- **Inpatient hospital.** One covered in-network acute admission, counted from day one and excluding discharge day. '
        'The example assumes any required referral or authorization, enough room under the applicable medical limit, and '
        'no assistance adjustment. Facility copays exclude professional fees, transfers, readmissions and later days. '
        'A daily copay counts once per covered day. A per-admission copay counts once.',
        '',
        'Each column shows a separate component under these assumptions. **Held** means an unresolved input or condition '
        'prevents showing an amount. The [structured packet](display-candidate.json) records the reason for each hold.',
        '',
        '| Plan and exact offering ID | ' + ' | '.join(EXAMPLES.values()) + ' |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for row in packet['plans']:
        plan = row['display_candidate']
        cells = [f'{plan["name"]} · {plan["offering_id"]}']
        for name in EXAMPLES:
            result = plan['cost_examples'][name]
            cells.append('**Held**' if result['state'] == 'held' else
                         f'${Decimal(result["amount"]["amount"]):,.2f}')
        lines.append('| ' + ' | '.join(cell.replace('|', r'\|') for cell in cells) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    packet = build()
    outputs = {
        'display-candidate.json': json.dumps(packet, ensure_ascii=False, indent=2) + '\n',
        'COST_EXAMPLES.md': render(packet),
    }
    for name, data in outputs.items():
        path = HERE / name
        if args.check:
            if path.read_text(encoding='utf-8') != data:
                raise SystemExit(f'Replay differs for {name}')
        else:
            path.write_text(data, encoding='utf-8')
    print(json.dumps(packet['example_counts'], indent=2))
