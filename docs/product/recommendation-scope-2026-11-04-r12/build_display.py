"""Build or replay the offline 72-plan published benefits display candidate."""

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
PREFIX = 'recommendation-scope-2026-11-04-'
INPUTS = {
    'r5/catalog': ('r5/catalog.json', '2c0198a2b848a26e09440e3daf1355c0ec5e45b107ef7de63784cd48f1aa3756'),
    'r10/critical-benefits': ('r10/critical-benefits.json', 'b677e66bd53d429d0e1aa7d1a563401d274f9fc95aee65c0a907a8e3b1cdd5a1'),
    'r11/listing': ('r11/display-candidate.json', '7a5f572334d0c47a019e2ce397cf26e16f3ecd7a8114fd28604e501eaabda382'),
}
FIELDS = {
    'plan_premium': 'Monthly plan premium',
    'part_b_reduction': 'Monthly Part B reduction',
    'medical_deductible': 'Annual medical deductible',
    'medical_maximums': 'Annual medical spending limits',
    'part_d_deductible': 'Annual Part D deductible',
    'primary_care_in_network': 'Primary care',
    'specialist_in_network': 'Specialist',
    'hospital_in_network': 'Inpatient hospital, first four covered days',
    'emergency': 'Emergency visit',
    'urgent': 'Urgent care visit',
}
NETWORK_LABELS = {'in_network': 'in network', 'out_of_network': 'out of network', 'combined': 'combined'}
VARIANT_CODES = {'DUAL_COST_SHARE_BASIS_UNRESOLVED', 'HEALTH_CONDITION_COST_VARIANT_UNRESOLVED'}
SPECIALIST_RATE = re.compile(r'\$([\d,.]+)(?:-\$?([\d,.]+))? copay(?: per visit)?')


def load():
    data, bindings = {}, {}
    for label, (path, expected) in INPUTS.items():
        relative = '../' + PREFIX + path
        raw = (HERE / relative).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f'Reviewed input bytes changed for {label}')
        data[label] = json.loads(raw)
        bindings[label] = {'path': relative, 'sha256': expected}
    return data, bindings


def money(amount):
    value = Decimal(amount)
    return f'${value:,.0f}' if value == value.to_integral_value() else f'${value:,.2f}'


def cell(value, *, state='published_candidate', conditions=(), reasons=()):
    if (value is None) != (state == 'held') or (state == 'held') != bool(reasons):
        raise ValueError('A held cell must have reasons and no display value')
    return {'state': state, 'value': value, 'conditions': list(conditions),
            'reason_codes': list(dict.fromkeys(reasons))}


def part_b(review):
    evidence = review['candidate']
    if review['state'] == 'explicit_pbp_no_part_b_rebate':
        return cell('Plan reports no reduction')
    if review['state'] in {'pbp_matches_retained_carrier_amount', 'pbp_matches_new_carrier_reading'}:
        prefix = 'Up to ' if (evidence.get('conditions') or {}).get('maximum') else ''
        return cell(prefix + money(evidence['amount']),
                    conditions=('Applies to member-paid Part B. Actual credit and timing need confirmation.',))
    return cell(None, state='held', reasons=('PART_B_REDUCTION_TERMS_UNRESOLVED',))


def published_amount(name, field):
    if field['state'] == 'held':
        return cell(None, state='held', reasons=field['reason_codes'])
    if field['state'] == 'not_applicable':
        return cell('Does not apply', state='not_applicable')
    if field['state'] != 'published_candidate':
        raise ValueError(f'Unknown field state for {name}')
    value, conditions = field['value'], field['conditions']
    if name == 'medical_maximums':
        return cell(' / '.join(f'{money(amount["amount"])} {NETWORK_LABELS[network]}'
                               for network, amount in value.items()))
    display_conditions = []
    if name == 'medical_deductible':
        if scope := conditions.get('scope'):
            display_conditions.append(scope)
        elif conditions['applies_to_inpatient']:
            display_conditions.append('Selective in-network deductible. Applies to covered inpatient care. Ordinary in-network primary care is excluded.')
    if name == 'part_d_deductible' and conditions.get('tiers'):
        display_conditions.append('Published tiers ' + ', '.join(map(str, conditions['tiers'])) + '.')
        if exemptions := conditions.get('exemptions'):
            display_conditions.append('Listed exemptions include ' + ', '.join(exemptions) + '.')
    return cell(money(value['amount']), conditions=display_conditions)


def office_or_hospital(field, scenario, *, hospital=False):
    reasons = [*field.get('reason_codes', []), *scenario.get('reason_codes', [])]
    if reasons:
        return cell(None, state='held', reasons=reasons)
    if field['state'] != 'published_candidate' or scenario['status'] != 'computed_research_only':
        raise ValueError('Unexpected published or rate-screen state')
    lines = scenario['lines']
    rate = lines[0]['rate']
    if hospital:
        scope = 'One covered acute admission. Transfers, later days and separately billed services may have different terms.'
        if len(lines) == 1 and rate['unit'] == 'admission':
            return cell(money(rate['amount']) + ' per admission', conditions=(scope,))
        if len(lines) == 4 and rate['unit'] == 'inpatient_day' and all(line['rate'] == rate for line in lines):
            return cell(money(rate['amount']) + ' per day, days 1–4', conditions=(scope,))
    elif len(lines) == 1 and rate['unit'] == 'visit':
        return cell(money(rate['amount']) + ' per visit', conditions=('Ordinary covered in-network office visit.',))
    raise ValueError('Previously checked charge basis changed')


def specialist(field, variant_reasons, comparisons):
    reasons = [*field.get('reason_codes', []), *variant_reasons]
    if reasons:
        return cell(None, state='held', reasons=reasons)
    rate = SPECIALIST_RATE.fullmatch(field['value'])
    if field['state'] != 'published_candidate' or rate is None:
        return cell(None, state='held', reasons=('SPECIALIST_CHARGE_BASIS_UNRESOLVED',))
    low, high = (Decimal(amount.replace(',', '')) for amount in (rate[1], rate[2] or rate[1]))
    named = [record.get('published_SB_USD_per_office_visit', record.get('expected_from_SB', record.get('value')))
             for record in comparisons]
    if any(record.get('unit', 'USD') != 'USD' for record in comparisons) or any(
            amount is None or not low <= Decimal(amount) <= high for amount in named):
        return cell(None, state='held', reasons=('SPECIALIST_CARRIER_AMOUNT_OUTSIDE_PUBLISHED_TERM',))
    if not named and not any(ref.startswith('carrier_regions/') for ref in field['source_refs']):
        return cell(None, state='held', reasons=('SPECIALIST_CHARGE_BASIS_UNRESOLVED',))
    scope = 'The charge can vary by covered specialist service. Check which term applies.' if rate[2] else 'Covered in-network specialist visit.'
    return cell(field['value'], conditions=(scope,))


def unscheduled_visit(service):
    reasons = service['flags']
    if service['source_screen'] != 'charge_shape_and_values_align' or reasons or service['historical_hold_ids']:
        return cell(None, state='held', reasons=reasons or ('EXACT_CHARGE_BASIS_REVIEW_REQUIRED',))
    row, = (row for row in service['mpf'] if row['network'] == 'In-Network')
    term = row['terms'].removesuffix(' (always covered)')
    return cell(term, conditions=('Published visit term. Location, setting and an admission waiver can affect the charge.',))


def plan_display(identity, plan, critical, retained):
    oid = identity['offering_id']
    published = plan['published']
    scenarios = plan['scenarios']
    premium = scenarios['premium_12_months']
    pcp = scenarios['pcp_four_visits']
    hospital = scenarios['hospital_days']['4']
    variant_reasons = [code for code in pcp.get('reason_codes', []) if code in VARIANT_CODES]
    specialist_source = published['specialist_in_network']
    refs = specialist_source['source_refs']
    comparisons = [retained[ref.split('/', 1)[1]]['record'] for ref in refs if ref.startswith('retained_comparisons/')]
    if any(record['offering_id'] != oid for record in comparisons):
        raise ValueError(f'Mismatched specialist source identity for {oid}')
    if premium['status'] == 'computed_research_only':
        premium_cell = cell(money(premium['monthly_rate']['amount']))
    else:
        premium_cell = cell(None, state='held', reasons=premium['reason_codes'])
    fields = {
        'plan_premium': premium_cell,
        'part_b_reduction': part_b(critical['part_b_reduction_review']),
        **{name: published_amount(name, published[name])
           for name in ('medical_deductible', 'medical_maximums', 'part_d_deductible')},
        'primary_care_in_network': office_or_hospital(published['primary_care_in_network'], pcp),
        'specialist_in_network': specialist(specialist_source, variant_reasons, comparisons),
        'hospital_in_network': office_or_hospital(published['hospital_in_network'], hospital, hospital=True),
        **{name: unscheduled_visit(critical['medical_services'][name]) for name in ('emergency', 'urgent')},
    }
    return {
        'display_candidate': {**identity, 'benefits': fields},
        'review_evidence': {
            'r11_listing_row': oid,
            'r5_source_refs': {
                'plan_premium': premium['source_refs'],
                **{name: published[name]['source_refs'] for name in (
                    'medical_deductible', 'medical_maximums', 'part_d_deductible',
                    'primary_care_in_network', 'specialist_in_network', 'hospital_in_network')},
            },
            'r5_rate_screen_source_refs': {
                'primary_care_in_network': pcp['source_refs'],
                'specialist_in_network': pcp['source_refs'] if variant_reasons else [],
                'hospital_in_network': hospital['source_refs'],
            },
            'r10_plan_key': oid,
            'r10_sections': {'part_b_reduction': 'part_b_reduction_review',
                             'part_d_deductible': 'part_d_deductible_review',
                             'emergency': 'medical_services/emergency', 'urgent': 'medical_services/urgent'},
        },
    }


def build():
    data, bindings = load()
    catalog = data['r5/catalog']
    critical = data['r10/critical-benefits']
    listing = data['r11/listing']
    listed = [plan['display_candidate'] for plan in listing['plans']]
    catalog_ids = [plan['offering_id'] for plan in catalog['plans']]
    if (len(set(catalog_ids)) != 72 or [plan['offering_id'] for plan in listed] != catalog_ids
            or sorted(critical['plans']) != catalog_ids
            or critical['inputs']['catalog']['sha256'] != bindings['r5/catalog']['sha256']
            or listing['evidence_bindings']['r5_catalog_sha256'] != bindings['r5/catalog']['sha256']):
        raise ValueError('The three packets do not bind the same exact 72 offerings')
    plans = []
    for identity, plan in zip(listed, catalog['plans'], strict=True):
        oid = identity['offering_id']
        if (identity['name'], identity['type']) != (plan['name'], plan['published']['coverage']['value']['plan_type']):
            raise ValueError(f'Listing name or type differs for {oid}')
        plans.append(plan_display(identity, plan, critical['plans'][oid],
                                  catalog['source_bindings']['retained_comparisons']))
    counts = {field: dict(Counter(row['display_candidate']['benefits'][field]['state'] for row in plans))
              for field in FIELDS}
    return {'schema': 'daylight-d91-published-benefits-review/1', 'decision': 'pending', 'accepted_release_id': None,
            'proposed_purpose': 'published_benefit_display', 'scope': listing['scope'],
            'inputs': bindings, 'fields': FIELDS, 'counts': counts, 'plans': plans}


def render(packet):
    lines = [
        '# Proposed published costs and benefits for 72 Collier plans',
        '',
        '2026 Collier County Medicare Advantage · September 2, 2026 CMS Landscape listing · Offline review candidate',
        '',
        'See [all plan types and published restrictions](../recommendation-scope-2026-11-04-r11/CATALOG.md). '
        'Each table uses exact offering ID order. **Held** means a charge or term is withheld pending review. '
        'The [review record](REVIEW.md) explains the scope and the [evidence packet](display-candidate.json) '
        'gives the reason codes and source references for each cell.',
        '',
        'The plan premium includes the plan’s Part D premium where applicable. Part B reductions are shown separately. '
        'Actual Part B credits depend on member-paid premiums and billing. '
        'The medical spending limits cover eligible medical costs and exclude premiums and Part D. '
        'A published Part D deductible can depend on tier and exceptions. Drug coverage and fill costs require a separate check.',
        '',
        'Primary care, specialist and inpatient figures are for covered in-network care. Emergency and urgent care figures '
        'use the selected published visit row. Check plan rules, the applicable setting, referrals, authorization, '
        'deductible and any waiver before relying on a charge. The inpatient column describes one acute admission. '
        'Transfers, later days and separately billed services can have different terms. Published terms do not quote your bill.',
    ]
    for title, fields in (('Premiums, deductibles and limits', list(FIELDS)[:5]),
                          ('Selected care charges', list(FIELDS)[5:])):
        lines.extend(['', '## ' + title, '',
                      '| Plan and exact offering ID | ' + ' | '.join(FIELDS[field] for field in fields) + ' |',
                      '| ' + ' | '.join(['---'] * (len(fields) + 1)) + ' |'])
        for row in packet['plans']:
            plan = row['display_candidate']
            values = [plan['name'] + ' · ' + plan['offering_id']]
            for name in fields:
                field = plan['benefits'][name]
                value = field['value'] or '**Held**'
                if name in {'medical_deductible', 'part_d_deductible'} and field['conditions']:
                    value += '<br>' + ' '.join(field['conditions'])
                values.append(value)
            lines.append('| ' + ' | '.join(value.replace('|', r'\|') for value in values) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    packet = build()
    outputs = {'display-candidate.json': json.dumps(packet, ensure_ascii=False, indent=2) + '\n',
               'CATALOG.md': render(packet)}
    for name, data in outputs.items():
        path = HERE / name
        if args.check:
            if path.read_text(encoding='utf-8') != data:
                raise SystemExit(f'Replay differs for {name}')
        else:
            path.write_text(data, encoding='utf-8')
    print(json.dumps(packet['counts'], indent=2))
