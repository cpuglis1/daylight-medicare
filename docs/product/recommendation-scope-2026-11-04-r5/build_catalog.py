"""Rebuild or verify the offline D91 comparison for the retained Collier catalog."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from decimal import Decimal
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
PILOT_SHA = 'd56444e9235701ad063e79e2fc2a38f85a8ed5d9f0167cf440882aacccbb12e8'
CALCULATOR_SHA = 'e807117fecf0d41a052671b8d2bd1be545ad2ed51f7fcf2132cf9dad4603595d'
calculator = ROOT / SOURCES['experiment_builder']['path']
if sha256(calculator.read_bytes()).hexdigest() != CALCULATOR_SHA:
    raise ValueError('The retained calculation method has changed.')
sys.path.insert(0, str(calculator.parent))
import run as prior

DEDUCTIBLE = 'Health plan deductible'
OTHER_DEDUCTIBLE = 'Other health plan deductibles?'
MAXIMUM = 'Maximum out-of-pocket enrollee responsibility (does not include prescription drugs)'
HOSPITAL = 'Inpatient hospital coverage'
HEALTH_CONDITION = 'Additional benefits and/or reduced cost-sharing for enrollees with certain health conditions?'
SELECTORS = {
    'medical_deductible': (DEDUCTIBLE, None, (None, 'In-Network')),
    'other_medical_deductibles': (OTHER_DEDUCTIBLE, None, (None,)),
    'medical_maximums': (MAXIMUM, None, (None, 'In-Network')),
    'primary': ('Doctor visits', 'Primary', ('In-Network',)),
    'specialist': ('Doctor visits', 'Specialist', ('In-Network',)),
    'hospital': (HOSPITAL, None, ('In-Network',)),
    'health_condition': (HEALTH_CONDITION, None, (None,)),
}
NETWORKS = {'in-network': 'in_network', 'out-of-network': 'out_of_network',
            'in and out-of-network': 'combined'}
MONEY = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?'
PART_B_PATTERNS = (
    (True, rf'will pay up to \$({MONEY}) of your Medicare Part B premium'),
    (True, rf'reduction in your Medicare Part B premium up to \$({MONEY})'),
    (True, rf'up to\s*a?\s*\$({MONEY}) reduction of your monthly Medicare Part B premium'),
    (False, rf'reduce your monthly Medicare Part B premium by \$({MONEY})'),
)
DRUG_TIERS = re.compile(
    rf'yearly deductible of \$({MONEY}) on (?:your )?((?:Cost.Sharing )?Tier\s+[1-6][^.]*?)(?:\s+drugs)?\.',
    re.I)
MEDICAL_DEDUCTIBLE_AMOUNT = re.compile(rf'Our plan deductible\?? Your deductible is \$({MONEY})', re.I)
NO_IN_NETWORK_DEDUCTIBLE = re.compile(
    r"doesn.t apply to any in[-‑]network services|"
    r"does not apply to the following in[-‑]network services: All covered in[-‑]network services|"
    r"excluded from the combined in[-‑]network and out[-‑]of[-‑]network deductible: All Services received from In[-‑]Network Providers",
    re.I)
COMBINED_DEDUCTIBLE_LIST = re.compile(
    r'The following services listed are excluded from the combined in-network and out-of-network deductible: In-Network only:',
    re.I)
HOLDS = {
    'PREMIUM_BASIS_CONFLICT': 'Published gross and carrier premium bases differ. Reconcile assistance and gross terms.',
    'PREMIUM_BASIS_UNRESOLVED': 'An exact nominal plan premium with its Part D basis is not established.',
    'MEDICAL_DEDUCTIBLE_UNRESOLVED': 'Verify which medical deductible and service scope apply, and any remaining balance.',
    'PART_B_REDUCTION_UNRESOLVED': 'No exact reduction statement was confirmed in the selected evidence.',
    'PART_B_REDUCTION_CONFLICT': 'Retained reduction statements disagree. Review the exact basis and carrier version.',
    'PART_B_REDUCTION_TERMS_UNRESOLVED': 'Verify the carrier’s exact qualification and whether the amount is a maximum.',
    'DRUG_DEDUCTIBLE_TIERS_UNRESOLVED': 'The Landscape amount is visible. Verify tier and exception scope in the carrier schedule.',
    'DRUG_DEDUCTIBLE_CONFLICT': 'The retained carrier tier statement and Landscape annual amount do not agree.',
    'DUAL_COST_SHARE_BASIS_UNRESOLVED': 'Verify which nominal or Medicaid-protected schedule applies to the scenario.',
    'CARRIER_CMS_COST_SHARE_CONFLICT': 'Retained source evidence has a material charge discrepancy for this service.',
    'HEALTH_CONDITION_COST_VARIANT_UNRESOLVED': 'The MPF reports possible reduced cost sharing. Verify the applicable schedule.',
    'EXACT_PCP_CHARGE_UNRESOLVED': 'The published PCP term is a range, coinsurance or otherwise lacks an exact visit charge.',
    'PCP_OFFICE_BASIS_UNCORROBORATED': 'Verify the exact ordinary in-network office copay and charging unit.',
    'HOSPITAL_CHARGING_UNIT_OR_BAND_UNRESOLVED': 'Verify the daily bands or per-admission charge for both covered stay lengths.',
    'HOSPITAL_CHARGE_UNCORROBORATED': 'Verify the exact carrier rate, charging unit and admission boundaries.',
    'MEDICAL_MAXIMUM_BASIS_UNRESOLVED': 'Verify the medical limit and its basis before applying the hospital scenario.',
    'INPATIENT_DEDUCTIBLE_STATUS_UNSPECIFIED': 'The remaining deductible at admission and charges that could meet it are unspecified.',
}


def inputs():
    paths = {key: ROOT / ref['path'] for key, ref in SOURCES.items()}
    for key, path in paths.items():
        prior.require(prior.file_sha(path) == SOURCES[key]['sha256'], f'Retained source changed: {key}')
    prior.require(SOURCES['pilot']['sha256'] == PILOT_SHA, 'The pilot source binding changed.')
    return paths


def select_mpf(paths, ids, bindings):
    by_offering = defaultdict(list)
    with paths['mpf'].open(encoding='utf-8') as extract:
        for row in map(json.loads, extract):
            by_offering[row['offering_id']].append(row)
    prior.require(set(by_offering) == ids and sum(map(len, by_offering.values())) == 6021,
                  'The exact MPF population changed.')
    selected = {}
    for oid, rows in by_offering.items():
        selected[oid] = {}
        for key, (category, service, networks) in SELECTORS.items():
            matching = [r for r in rows if (
                r['fields']['Category Name'], r['fields']['Service_Desc']) == (category, service)
                and r['fields']['Network_Description'] in networks]
            prior.require(len(matching) == 1, f'Missing or ambiguous retained MPF row: {oid}/{key}')
            row = matching[0]
            f = row['fields']
            raw_id = f"{f['Contract_Year']}:{f['Contract_ID']}:{f['Plan_ID']:03d}:{f['Segment_ID']:03d}"
            prior.require(raw_id == oid, f'MPF offering mismatch: {oid}/{key}')
            bindings['mpf_rows'][str(row['source_row'])] = row
            selected[oid][key] = row
    return selected


def select_landscape(paths, catalog, bindings):
    source = bindings['premium_source']
    with ZipFile(paths['landscape']) as archive:
        member = archive.read(source['member'])
    prior.require(sha256(member).hexdigest() == source['member_sha256'], 'Landscape member changed.')
    columns = sorted(set(next(iter(source['records'].values()))['fields']) | {
        'State Territory Abbreviation', 'County Name', 'Plan Type', 'SNP Type',
        'Offers Drug Tier with No Part D Deductible',
    })
    result = {}
    for n, row in enumerate(csv.DictReader(StringIO(member.decode('utf-8-sig'))), 1):
        if (row['State Territory Abbreviation'], row['County Name']) != ('FL', 'Collier'):
            continue
        oid = f"2026:{row['Contract ID']}:{row['Plan ID']}:{row['Segment ID'].zfill(3)}"
        if oid in catalog:
            prior.require(oid not in result and row['Plan Name'] == catalog[oid]['name'],
                          f'Landscape identity or name mismatch: {oid}')
            result[oid] = {
                **source['records'].get(oid, {}), 'record_ordinal': n,
                'fields': {column: row[column] for column in columns},
                'amount_field': ('Monthly Consolidated Premium (Part C + D)' if catalog[oid]['drug'] == 'Yes'
                                 else 'Part C Premium'),
            }
    prior.require(set(result) == set(catalog), 'Not every offering has an exact Landscape record.')
    source['records'] = result
    return result


def index_comparisons(paths, bindings):
    entries = prior.load(paths['accepted_r4_entries'])
    receipt = prior.load(paths['accepted_r4_receipt'])
    prior.require(receipt['decision'] == 'accepted' and receipt['revoked'] is False
                  and receipt['manifest_sha256'] == SOURCES['accepted_r4_manifest']['sha256']
                  and set(receipt['accepted_entry_ids']) == {entry['id'] for entry in entries}
                  and len(entries) == 535, 'The exact accepted L03 r4 scope changed.')
    accepted_manifest = prior.load(paths['accepted_r4_manifest'])
    for label, filename in [('accepted_r4_entries', 'entries.json'), ('accepted_r4_holds', 'held-claims.json')]:
        prior.require(SOURCES[label]['sha256'] == accepted_manifest['files_sha256'][filename],
                      f'L03 r4 binding changed: {filename}')
    observations = defaultdict(dict)
    for label, rows in [
        ('accepted_r4_entries', entries), ('office_r5', prior.load(paths['office_r5'])),
        ('comparisons_r6', prior.load(paths['comparisons_r6'])), ('comparisons_r7', prior.load(paths['comparisons_r7'])),
    ]:
        for row in rows:
            if label == 'accepted_r4_entries' and not row['field'].startswith((
                    'INN_hospital', 'INN_annual_medical_MOOP', 'combined_annual_medical_MOOP',
                    'published_gross_consolidated_premium')):
                continue
            if label in ('comparisons_r6', 'comparisons_r7') and not any(word in row['field'].casefold() for word in (
                    'premium', 'moop', 'primary', 'pcp', 'specialist', 'hospital', 'medical_deductible')):
                continue
            key = row['field'] if 'field' in row else 'office_' + row['service']
            prior.require(key not in observations[row['offering_id']], f'Duplicate retained comparison: {row["id"]}')
            observations[row['offering_id']][key] = row
            bindings['retained_comparisons'][row['id']] = {'input': label, 'record': row}
    holds = defaultdict(dict)
    historical = prior.load(paths['accepted_r4_holds'])
    prior.require(len(historical) == 153, 'The original held-claim inventory changed.')
    for row in historical:
        bindings['historical_holds'][row['issue_id']] = row
        holds[row['offering_id']].setdefault(row['category_code'], []).append(
            'historical_holds/' + row['issue_id'])
    return observations, holds


def carrier_statements(paths, documents, bindings):
    doc_ids = {doc['document_matches']['EOC']['sha256']: doc['offering_id'] for doc in documents.values()}
    prior.require(len(doc_ids) == 72, 'EOC identities are incomplete or ambiguous.')
    found = defaultdict(lambda: defaultdict(list))
    seen = set()
    continued_deductibles = {}
    for label in ('carrier_pages_r1', 'carrier_pages_r6', 'carrier_pages_r7'):
        with gzip.open(paths[label], 'rt', encoding='utf-8') as source:
            for page in map(json.loads, source):
                doc = page['document_sha256']
                if doc not in doc_ids or (doc, page['pdf_page']) in seen:
                    continue
                seen.add((doc, page['pdf_page']))
                oid = doc_ids[doc]
                text = ' '.join(page['text'].split())
                matches = []
                deductible_amount = MEDICAL_DEDUCTIBLE_AMOUNT.search(text)
                if deductible_amount:
                    exclusion = NO_IN_NETWORK_DEDUCTIBLE.search(text)
                    if exclusion:
                        matches.append(('medical_deductible_scope', exclusion, {
                            'amount': prior.usd(deductible_amount[1], 'plan_year'),
                            'applies_to_ordinary_pcp': False, 'applies_to_inpatient': False,
                            'source_amount_text': deductible_amount[0],
                        }))
                    scope = COMBINED_DEDUCTIBLE_LIST.search(text)
                    if scope:
                        continued_deductibles[(doc, page['pdf_page'] + 1)] = {
                            'amount': prior.usd(deductible_amount[1], 'plan_year'),
                            'prior_page': {'input': label, 'pdf_page': page['pdf_page'],
                                           'text_sha256': page['text_sha256'],
                                           'exact_amount_and_scope_text': [deductible_amount[0], scope[0]]},
                        }
                continuation = continued_deductibles.get((doc, page['pdf_page']))
                if continuation:
                    pcp_exclusion = re.search(
                        r"Primary Care Physician's Office (?:(?!Both In-Network and Out-of-Network).)*Both In-Network and Out-of-Network:",
                        text, re.I)
                    if pcp_exclusion:
                        matches.append(('medical_deductible_scope', pcp_exclusion, {
                            **continuation, 'applies_to_ordinary_pcp': False, 'applies_to_inpatient': None,
                        }))
                if page['pdf_page'] <= 12:
                    for match in re.finditer(r'you live in an Erickson Retirement Community', text, re.I):
                        matches.append(('residence_requirement', match, {
                            'requirement': 'Residence in an Erickson Retirement Community is required.',
                        }))
                if page['pdf_page'] <= 20:
                    for match in re.finditer(rf'Primary care office visits \$({MONEY})(?: copay(?:ment)?)? per visit', text, re.I):
                        matches.append(('ordinary_pcp_rate', match, prior.usd(match[1], 'visit')))
                    for match in re.finditer(
                        r'\$0 copayment for each Medicare-covered hospital stay for unlimited days \(in-\s*network\)',
                        text, re.I):
                        matches.append(('zero_in_network_hospital_per_stay', match, prior.usd('0', 'admission')))
                if page['pdf_page'] <= 25 and 'part b premium' in text.casefold():
                    for maximum, pattern in PART_B_PATTERNS:
                        for match in re.finditer(pattern, text, re.I):
                            matches.append(('part_b_reduction', match, {
                                'amount': prior.usd(match[1], 'month'), 'maximum': maximum,
                            }))
                if 'deductible of $' in text.casefold():
                    for match in DRUG_TIERS.finditer(text):
                        tier_list = re.sub(r'\([^()]*\)', '', match[2])
                        tier_list = re.sub(r':\s*(?:Preferred Brand|Non-Preferred Drug|Specialty Tier)', '', tier_list, flags=re.I)
                        # Reject unsupported prose, ranges and ambiguous layouts.
                        tier_list = re.sub(r'(?:Cost.Sharing )?Tier\s*|\band\b|\bdrugs\b|,', ' ', tier_list, flags=re.I)
                        if re.fullmatch(r'\s*[1-6](?:\s+[1-6])*\s*', tier_list):
                            matches.append(('part_d_deductible', match, {
                                'amount': prior.usd(match[1], 'plan_year'),
                                'tiers': [int(n) for n in tier_list.split()],
                            }))
                for field, match, value in matches:
                    key = f'{oid}:{field}:{page["pdf_page"]}:{len(found[oid][field]) + 1}'
                    bindings['carrier_statements'][key] = {
                        'offering_id': oid, 'input': label, 'document_sha256': doc,
                        'pdf_page': page['pdf_page'], 'text_sha256': page['text_sha256'],
                        'extraction_method': page.get('extraction_method', 'retained_page_text'),
                        'exact_text_with_whitespace_normalized': match[0],
                        'source_value': value,
                    }
                    found[oid][field].append((value, 'carrier_statements/' + key))
    return found


def fact(value, refs, **conditions):
    return {'state': 'published_candidate', 'value': value, 'source_refs': refs,
            **({'conditions': conditions} if conditions else {})}


def hold(codes, refs, *, value=None, scenario=False, **details):
    codes = list(dict.fromkeys(codes))
    return {'status' if scenario else 'state': 'held', 'amount' if scenario else 'value': value,
            'reason_codes': codes, 'unresolved': [HOLDS[code] for code in codes],
            'source_refs': list(dict.fromkeys(refs)), **details}


def cash(text, unit):
    match = re.fullmatch(rf'\$({MONEY})', text.strip())
    return prior.usd(match[1], unit) if match else None


def known_ref(record):
    return 'retained_comparisons/' + record['id']


def published_part_b(statements, observation, eoc_ref):
    refs = [ref for _, ref in statements]
    if observation:
        refs.append(known_ref(observation))
    unique = {(v['amount']['amount'], v['maximum']) for v, _ in statements}
    historical = (Decimal(observation['expected_from_SB']) if observation and 'expected_from_SB' in observation
                  else Decimal(observation['value']) if observation else None)
    if len(unique) > 1 or any(historical is not None and Decimal(amount) != historical for amount, _ in unique):
        return hold(['PART_B_REDUCTION_CONFLICT'], refs)
    if unique:
        amount, maximum = next(iter(unique))
        return fact(prior.usd(amount, 'month'), refs, maximum=maximum,
                    application_to_plan_premium_scenario='excluded',
                    qualification='Published reduction of member-paid Part B only. Actual billing and timing remain unverified.')
    if historical is not None:
        return hold(['PART_B_REDUCTION_TERMS_UNRESOLVED'], refs,
                    value=prior.usd(str(historical), 'month'))
    return hold(['PART_B_REDUCTION_UNRESOLVED'], [eoc_ref])


def published_drug(landscape, statements, landscape_ref, drug):
    if not drug:
        prior.require(landscape['Annual Part D Deductible Amount'] == 'Not Applicable',
                      'No-Rx indication conflicts with the Landscape deductible.')
        return {'state': 'not_applicable', 'reason': 'No Part D benefit in this offering.',
                'source_refs': [landscape_ref]}
    amount = cash(landscape['Annual Part D Deductible Amount'], 'plan_year')
    refs = [landscape_ref, *(ref for _, ref in statements)]
    unique = {(v['amount']['amount'], tuple(v['tiers'])) for v, _ in statements}
    if len(unique) > 1 or any(not amount or n != amount['amount'] for n, _ in unique):
        return hold(['DRUG_DEDUCTIBLE_CONFLICT'], refs, value=amount)
    if unique:
        _, tiers = next(iter(unique))
        return fact(amount, refs, tiers=list(tiers), member_tier_and_exceptions='Check plan and drug-specific terms.')
    if amount and amount['amount'] == '0.00':
        return fact(amount, refs, basis='Published annual Part D deductible. Drug coverage and costs are separate.')
    return hold(['DRUG_DEDUCTIBLE_TIERS_UNRESOLVED'], refs, value=amount)


def mpf_ref(row):
    return f"mpf_rows/{row['source_row']}"


def published_term(row, old_refs=(), conflict_refs=()):
    f = row['fields']
    value = f['Cost_Share'].replace('<br />', '\n')
    refs = [mpf_ref(row), *old_refs, *conflict_refs]
    conditions = {'network': f['Network_Description'],
                  'source_flags': {key: f[key] for key in ('Limit_Flag', 'Authorization_Flag', 'Referral_Flag')},
                  'flags_scope': 'Plan Finder flags alone do not establish a universal requirement or actual approval.'}
    if conflict_refs:
        return hold(['CARRIER_CMS_COST_SHARE_CONFLICT'], refs, value=value, conditions=conditions)
    return fact(value, refs, **conditions)


def medical_deductible(rows, statements):
    row = rows['medical_deductible']
    other = rows['other_medical_deductibles']
    text = row['fields']['Cost_Share']
    refs = [mpf_ref(row), mpf_ref(other)]
    if type(text) is int and text == 0 and other['fields']['Cost_Share'] == 'No':
        return fact(prior.usd('0', 'plan_year'), refs, applies_to_ordinary_pcp=False, applies_to_inpatient=False)
    match = re.fullmatch(rf'\$({MONEY}) (annual deductible|In-network)', str(text), re.I)
    if match and statements:
        amount = prior.usd(match[1], 'plan_year')
        refs.extend(ref for _, ref in statements)
        exact = {(value['applies_to_ordinary_pcp'], value['applies_to_inpatient'])
                 for value, _ in statements if value['amount'] == amount}
        if len(exact) == 1 and all(value['amount'] == amount for value, _ in statements):
            pcp, inpatient = next(iter(exact))
            return fact(amount, refs, applies_to_ordinary_pcp=pcp, applies_to_inpatient=inpatient,
                        scope=('Published annual amount. All in-network care is excluded.'
                               if inpatient is False else
                               'Published annual combined amount. Ordinary in-network PCP office visits are excluded. '
                               'Inpatient applicability remains held.'))
    return hold(['MEDICAL_DEDUCTIBLE_UNRESOLVED'], refs,
                value=prior.usd(match[1], 'plan_year') if match else text,
                published_source_text=text)


def maximums(row, observations):
    text = row['fields']['Cost_Share']
    values = {}
    for line in text.split('<br />'):
        match = re.fullmatch(rf'\$({MONEY}) (In and Out-of-network|In-network|Out-of-network)', line.strip(), re.I)
        if not match:
            return hold(['MEDICAL_MAXIMUM_BASIS_UNRESOLVED'], [mpf_ref(row)], value=text)
        key = NETWORKS[match[2].casefold()]
        prior.require(key not in values, 'Ambiguous medical maximum network.')
        values[key] = prior.usd(match[1], 'plan_year')
    refs = [mpf_ref(row)]
    old = [observations[field] for field in ('INN_annual_medical_MOOP', 'in_network_medical_MOOP',
                                            'combined_annual_medical_MOOP', 'out_of_network_medical_MOOP')
           if field in observations]
    refs.extend(known_ref(x) for x in old)
    for x in old:
        key = ('combined' if x['field'].startswith('combined') else
               'out_of_network' if x['field'].startswith('out_of_network') else 'in_network')
        carrier = x.get('expected_from_SB', x.get('value'))
        if key not in values or carrier is None or Decimal(carrier) != Decimal(values[key]['amount']):
            return hold(['MEDICAL_MAXIMUM_BASIS_UNRESOLVED'], refs, value=values, published_source_text=text)
    return fact(values, refs, scope='Annual covered medical spending. Network limits are separate, and premiums and Part D are excluded.')


def scenario_result(lines, unit, refs, *, conditions, exclusions):
    return {'status': 'computed_research_only', 'amount': prior.subtotal(lines, unit),
            'source_refs': list(dict.fromkeys(refs)), 'conditions': conditions,
            'exclusions': exclusions, 'lines': lines}


def premium_scenario(oid, record, observations, has_drug):
    fields = record['fields']
    refs = [f'premium_source/records/{oid}', 'files/landscape_readme']
    old = [observations[field] for field in ('published_gross_consolidated_premium',
                                             'published_plan_premium', 'monthly_published_plan_premium')
           if field in observations]
    refs.extend(known_ref(x) for x in old)
    part_c = cash(fields['Part C Premium'], 'month')
    part_d = cash(fields['Part D Total Premium'], 'month')
    monthly = cash(fields[record['amount_field']], 'month')
    if not monthly or not part_c or (has_drug and (
            not part_d or Decimal(monthly['amount']) != Decimal(part_c['amount']) + Decimal(part_d['amount']))) or (
            not has_drug and (fields['Part D Total Premium'].strip() != 'Not Applicable'
                              or fields['Monthly Consolidated Premium (Part C + D)'].strip() != 'Not Applicable')):
        return hold(['PREMIUM_BASIS_UNRESOLVED'], refs, scenario=True, monthly_rate=monthly)
    if any(x.get('source_values_equal', x.get('CMS_value_equal')) is False
           or Decimal(x.get('expected_from_SB', x.get('value'))) != Decimal(monthly['amount'])
           for x in old):
        return hold(['PREMIUM_BASIS_CONFLICT'], refs, scenario=True, monthly_rate=monthly)
    result = scenario_result([{'rate': monthly, 'quantity': 12, 'quantity_unit': 'months'}], 'plan_year', refs,
                             conditions={'calendar_year': 2026, 'basis': record['amount_field'],
                                         'part_c': part_c, 'part_d': part_d,
                                         'part_d_applicability': 'included_once' if has_drug else 'not_applicable'},
                             exclusions=['Federal premiums', 'Part B premium reduction', 'Optional packages',
                                         'Assistance, penalties and adjustments', 'Medical and prescription spending'])
    result['monthly_rate'] = monthly
    return result


def service_holds(rows, catalog, historical, category):
    refs = list(historical.get(category, ()))
    codes = ['CARRIER_CMS_COST_SHARE_CONFLICT'] if refs else []
    if catalog['snp_type'] == 'Dual-Eligible':
        codes.append('DUAL_COST_SHARE_BASIS_UNRESOLVED')
        refs.append('files/catalog')
    if rows['health_condition']['fields']['Cost_Share'] != 'No':
        codes.append('HEALTH_CONDITION_COST_VARIANT_UNRESOLVED')
        refs.append(mpf_ref(rows['health_condition']))
    return codes, refs


def pcp_scenario(rows, catalog, observations, historical, deductible, statements):
    row = rows['primary']
    codes, extra = service_holds(rows, catalog, historical, '7a')
    refs = [mpf_ref(row), *deductible['source_refs'], *extra]
    if deductible.get('conditions', {}).get('applies_to_ordinary_pcp') is not False:
        codes.append('MEDICAL_DEDUCTIBLE_UNRESOLVED')
    reason, rate = prior.exact_copay(prior.mpf_price(row['fields']['Cost_Share']), 'visit',
                                    zero_unit_confirmed=True)
    old = [observations[k] for k in ('office_primary_care', 'INN_primary_care', 'INN_pcp') if k in observations]
    refs.extend(known_ref(x) for x in old)
    if reason:
        codes.append('EXACT_PCP_CHARGE_UNRESOLVED')
    else:
        corroborated = bool(statements) and all(value == rate for value, _ in statements)
        refs.extend(ref for _, ref in statements)
        if statements and not corroborated:
            codes.append('CARRIER_CMS_COST_SHARE_CONFLICT')
        for x in old:
            if 'published_SB_USD_per_office_visit' in x:
                match = Decimal(x['published_SB_USD_per_office_visit']) == Decimal(rate['amount'])
                exact_pbp = any(c['kind'] == 'copayment' and c['state'] == 'amount'
                                and Decimal(c['amount']) == Decimal(rate['amount']) for c in x['PBP_cost_components'])
                corroborated |= (match and exact_pbp and bool(x['EOC_evidence'])
                                 and x['literal_amount_or_no_charge_context_present'])
                if not match:
                    codes.append('CARRIER_CMS_COST_SHARE_CONFLICT')
            elif x['unit'] == 'USD':
                match = Decimal(x.get('expected_from_SB', x.get('value'))) == Decimal(rate['amount'])
                agree = x.get('source_values_equal', x.get('CMS_value_equal'))
                corroborated |= match and agree is True and bool(x['EOC_service_evidence'])
                if not match or agree is False:
                    codes.append('CARRIER_CMS_COST_SHARE_CONFLICT')
        if not corroborated:
            codes.append('PCP_OFFICE_BASIS_UNCORROBORATED')
    if codes:
        return hold(codes, refs, scenario=True)
    return scenario_result([{'rate': rate, 'quantity': 4, 'quantity_unit': 'visits'}], 'scenario', refs,
                           conditions={'network': 'in_network', 'setting': 'ordinary in-person PCP office visit',
                                       'medical_deductible_applies': False},
                           exclusions=['Separately billed procedures and lab work', 'Specialist and telehealth visits'])


def hospital_reference(observations, parsed, refs):
    if parsed['form'] == 'day_schedule' and not parsed['issues']:
        first = parsed['bands'][0]
        end = first['end_day']
        if first['begin_day'] != 1 or end['state'] != 'finite' or end['value'] < 4:
            return None, None, 'HOSPITAL_CHARGING_UNIT_OR_BAND_UNRESOLVED'
        amount = first['amount']
        candidates = (
            ('INN_hospital_band1_amount', 'INN_hospital_band1_begin_day', 'INN_hospital_band1_end_day'),
            ('INN_hospital_band1_copayment', 'INN_hospital_band1_begin_day', 'INN_hospital_band1_end_day'),
            ('INN_hospital_first_charge', 'INN_hospital_begin_day', 'INN_hospital_end_day'),
        )
        expected = (Decimal(amount), Decimal(1), Decimal(end['value']))
        unit = 'inpatient_day'
    elif (parsed['form'] == 'amount' and parsed['kind'] == 'copayment'
          and parsed['denominator'] == 'stay' and not parsed['issues']):
        amount = parsed['amount']
        candidates = (('INN_hospital_PBP_base_stay_copayment',), ('INN_hospital_base_stay_copayment',),
                      ('INN_hospital_first_charge',))
        expected = (Decimal(amount),)
        unit = 'admission'
    else:
        return None, None, 'HOSPITAL_CHARGING_UNIT_OR_BAND_UNRESOLVED'

    matched = False
    for keys in candidates:
        if not all(key in observations for key in keys):
            continue
        group = [observations[key] for key in keys]
        source_unit = group[0]['unit']
        if source_unit != ('USD/day' if unit == 'inpatient_day' else 'USD/stay'):
            continue
        refs.extend(known_ref(x) for x in group)
        seen = tuple(Decimal(x.get('expected_from_SB', x.get('value'))) for x in group)
        if seen != expected or any(x.get('source_values_equal', x.get('CMS_value_equal')) is False for x in group):
            return None, None, 'CARRIER_CMS_COST_SHARE_CONFLICT'
        matched |= all(':r4:' in x['id'] or x.get('source_values_equal', x.get('CMS_value_equal')) is True
                       for x in group)
    if not matched:
        return None, None, 'HOSPITAL_CHARGE_UNCORROBORATED'
    return prior.usd(amount, unit), unit, None


def hospital_scenarios(rows, catalog, observations, historical, deductible, maximum, statements):
    row = rows['hospital']
    codes, extra = service_holds(rows, catalog, historical, '1a')
    refs = [mpf_ref(row), *deductible['source_refs'], *maximum['source_refs'], *extra]
    if deductible.get('conditions', {}).get('applies_to_inpatient') is not False:
        codes.append('MEDICAL_DEDUCTIBLE_UNRESOLVED')
    if maximum['state'] != 'published_candidate' or 'in_network' not in maximum['value']:
        codes.append('MEDICAL_MAXIMUM_BASIS_UNRESOLVED')
    text = row['fields']['Cost_Share']
    if text == '$0 copay per stay<br />$0 per day for days 91 and beyond' and statements:
        # This retained carrier wording binds the early per-stay price. The
        # separate late band cannot apply to either modeled admission.
        text = '$0 copay per stay'
        refs.extend(ref for _, ref in statements)
    text = re.sub(r'^(\$' + MONEY + ') per stay$', r'\1 copay per stay', text)
    rate, unit, reason = hospital_reference(observations, prior.mpf_price(text), refs)
    if reason:
        codes.append(reason)
    if rate and 'MEDICAL_MAXIMUM_BASIS_UNRESOLVED' not in codes:
        total = Decimal(rate['amount']) * (4 if unit == 'inpatient_day' else 1)
        if total > Decimal(maximum['value']['in_network']['amount']):
            codes.append('MEDICAL_MAXIMUM_BASIS_UNRESOLVED')
    result = {}
    for days in (3, 4):
        if codes:
            result[str(days)] = hold(codes, refs, scenario=True, requested_inpatient_days=days)
            continue
        if unit == 'inpatient_day':
            lines = [{'day': day, 'rate': rate, 'quantity': 1, 'quantity_unit': unit}
                     for day in range(1, days + 1)]
        else:
            lines = [{'rate': rate, 'quantity': 1, 'quantity_unit': unit}]
        result[str(days)] = {
            **scenario_result(lines, 'admission', refs,
                              conditions={'network': 'in_network', 'admissions': 1, 'charging_unit': unit,
                                          'counted_days': 'Formally admitted covered inpatient days. Discharge day is excluded.',
                                          'scope': 'Acute facility copay only. Required authorization and referral are assumed.',
                                          'in_network_medical_maximum': maximum['value']['in_network'],
                                          'medical_deductible_applies': False},
                              exclusions=['Professional fees and other separately billed services',
                                          'Observation and outpatient stays', 'Transfers and readmissions', 'Later bands']),
            'requested_inpatient_days': days,
        }
    return result


def plan_record(catalog, rows, record, observations, historical, statements, doc_ref, personal_checks):
    oid = catalog['id']
    deductible = medical_deductible(rows, statements.get('medical_deductible_scope', []))
    maximum = maximums(rows['medical_maximums'], observations)
    drug = catalog['drug'] == 'Yes'
    specialist_refs = [known_ref(observations[k]) for k in ('office_specialist', 'INN_specialist') if k in observations]
    residence = statements.get('residence_requirement', [])
    coverage = {
        'plan_type': catalog['plan_type'], 'category': catalog['category'], 'includes_part_d': drug,
        'snp': catalog['snp'] == 'Yes', 'snp_type': catalog['snp_type'],
        'residence_requirement': residence[0][0]['requirement'] if residence else None,
        'residence_requirement_review': ('source_statement_found' if residence else
                                         'exact_requirement_needs_review' if catalog['contract'] == 'H5652' else
                                         'not_checked'),
        'catalog_restriction_fields': json.loads(catalog['restriction_raw']),
        'eligibility_and_geographic_applicability': 'not_checked',
    }
    return {
        'offering_id': oid, 'name': catalog['name'], 'role': 'offline_catalog',
        'published': {
            'coverage': fact(coverage, ['files/catalog', f'premium_source/records/{oid}', doc_ref,
                                        *(ref for _, ref in residence)]),
            'part_b_reduction': published_part_b(
                statements.get('part_b_reduction', []), observations.get('Part_B_premium_reduction'), doc_ref),
            'medical_deductible': deductible, 'medical_maximums': maximum,
            'part_d_deductible': published_drug(record['fields'], statements.get('part_d_deductible', []),
                                               f'premium_source/records/{oid}', drug),
            'primary_care_in_network': published_term(rows['primary'], conflict_refs=historical.get('7a', ())),
            'specialist_in_network': published_term(rows['specialist'], specialist_refs, historical.get('7d', ())),
            'hospital_in_network': published_term(rows['hospital'], conflict_refs=historical.get('1a', ())),
            'personal_checks': deepcopy(personal_checks),
        },
        'scenarios': {
            'premium_12_months': premium_scenario(oid, record, observations, drug),
            'pcp_four_visits': pcp_scenario(rows, catalog, observations, historical, deductible,
                                           statements.get('ordinary_pcp_rate', [])),
            'hospital_days': hospital_scenarios(rows, catalog, observations, historical, deductible, maximum,
                                                statements.get('zero_in_network_hospital_per_stay', [])),
        },
    }


def build(paths):
    pilot = prior.load(paths['pilot'])
    catalog = {row['id']: row for row in prior.load(paths['catalog'])}
    prior.require(len(catalog) == 72 and all(row['year'] == '2026' for row in catalog.values()),
                  'Frozen catalog must have 72 exact 2026 offerings.')
    documents = {row['offering_id']: row for row in prior.load(paths['documents_r7'])}
    prior.require(set(documents) == set(catalog) and all(doc['documented'] for doc in documents.values()),
                  'Carrier identity inventory does not match the retained catalog.')
    bindings = deepcopy(pilot['source_bindings'])
    bindings['files'].update(SOURCES)
    bindings.update(documents=documents, retained_comparisons={}, historical_holds={}, carrier_statements={})
    rows = select_mpf(paths, set(catalog), bindings)
    premiums = select_landscape(paths, catalog, bindings)
    observations, historical = index_comparisons(paths, bindings)
    statements = carrier_statements(paths, documents, bindings)
    pilot_plans = {row['offering_id']: row for row in pilot['plans']}
    checks = pilot['plans'][0]['published']['personal_checks']
    plans = []
    for oid, plan in sorted(catalog.items()):
        if oid in pilot_plans:
            record = deepcopy(pilot_plans[oid])
            record['published']['primary_care_in_network'] = published_term(rows[oid]['primary'])
        else:
            record = plan_record(plan, rows[oid], premiums[oid], observations[oid], historical[oid],
                                 statements[oid], 'documents/' + oid, checks)
        plans.append(record)
    data = {
        'schema': 'daylight-d91-collier-catalog-comparison/1',
        'candidate_id': 'D91-2026-COLLIER-OFFLINE-CATALOG-r5',
        'state': 'offline_comparison_candidates_pending_independent_review_and_acceptance',
        'scope': {**pilot['scope'], 'offering_ids': sorted(catalog), 'plan_order': 'exact_offering_id',
                  'plan_order_is_rank': False},
        'purpose': deepcopy(pilot['purpose']),
        'profile_binding': pilot['profile_binding'],
        'scenario': pilot['scenario'],
        'methods': {**pilot['methods'], 'catalog_builder_sha256': prior.file_sha(Path(__file__).resolve()),
                    'catalog_hospital_rules': [
                        'Exact matching first daily band beginning on day 1 and covering both variants.',
                        'Exact corroborated single per-admission charge when the published row explicitly prices a stay.',
                    ],
                    'carrier_statement_scope': 'Literal template candidates from retained exact-offering EOC pages. Independent review remains pending.'},
        'source_bindings': bindings,
        'hold_dictionary': HOLDS,
        'plans': plans,
    }
    data['coverage_counts'] = summarize(plans)
    verify(data, catalog, pilot_plans)
    return data


def summarize(plans):
    result = {'offerings': len(plans), 'categories': Counter(),
              'scenario_statuses': {key: Counter() for key in ('premium_12_months', 'pcp_four_visits', 'hospital_3', 'hospital_4')},
              'published_statuses': {key: Counter() for key in plans[0]['published'] if key != 'personal_checks'},
              'scenario_hold_reasons': {key: Counter() for key in ('premium_12_months', 'pcp_four_visits', 'hospital_3')},
              'hospital_charging_units': Counter(), 'offerings_with_all_scenarios_numeric': 0}
    for plan in plans:
        fields = plan['published']
        result['categories'][fields['coverage']['value']['category']] += 1
        for key, counts in result['published_statuses'].items():
            counts[fields[key]['state']] += 1
        by_case = scenarios(plan)
        if all(outcome['status'] == 'computed_research_only' for outcome in by_case.values()):
            result['offerings_with_all_scenarios_numeric'] += 1
        for key, outcome in by_case.items():
            result['scenario_statuses'][key][outcome['status']] += 1
            if outcome['status'] == 'held' and key in result['scenario_hold_reasons']:
                result['scenario_hold_reasons'][key].update(outcome['reason_codes'])
        hospital = plan['scenarios']['hospital_days']['3']
        if hospital['amount'] is not None:
            result['hospital_charging_units'][hospital['lines'][0]['rate']['unit']] += 1
    return result


def scenarios(plan):
    value = plan['scenarios']
    return {'premium_12_months': value['premium_12_months'], 'pcp_four_visits': value['pcp_four_visits'],
            'hospital_3': value['hospital_days']['3'], 'hospital_4': value['hospital_days']['4']}


def all_refs(value):
    if isinstance(value, dict):
        yield from value.get('source_refs', ())
        for child in value.values():
            yield from all_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_refs(child)


def verify(data, catalog, pilot_plans):
    records = data['plans']
    prior.require([row['offering_id'] for row in records] == sorted(catalog), 'Offering set changed or was ranked.')
    prior.require(data['purpose']['accepted_release_id'] is None and data['purpose']['consumer_usable'] is False
                  and data['purpose']['recommendation'] == 'held', 'Catalog must stay offline and held.')
    prior.require(data['profile_binding']['conditional_question_count'] == 41 and data['profile_binding']['fictional'],
                  'Fictional profile binding changed.')
    published = set(next(iter(pilot_plans.values()))['published']) | {'primary_care_in_network'}
    for plan in records:
        oid = plan['offering_id']
        prior.require(set(plan['published']) == published, f'Incomplete field set: {oid}')
        prior.require(all(x['state'] == 'not_checked' for x in plan['published']['personal_checks'].values()),
                      f'Unverified personal check became a finding: {oid}')
        if oid in pilot_plans:
            original = deepcopy(plan)
            original['published'].pop('primary_care_in_network')
            prior.require(original == pilot_plans[oid], f'Pilot evidence or amount changed: {oid}')
        for ref in all_refs(plan):
            source = data['source_bindings']
            for key in ref.split('/'):
                source = source[key]
            prior.require(bool(source), f'Empty source reference: {ref}')
        by_case = scenarios(plan)
        for key, outcome in by_case.items():
            prior.require(bool(outcome['source_refs']), f'Missing scenario evidence: {oid}/{key}')
            if outcome['status'] == 'held':
                prior.require(outcome['amount'] is None and outcome['reason_codes'] and outcome['unresolved'],
                              f'An unresolved scenario became a dollar value: {oid}/{key}')
            else:
                prior.require(outcome['status'] == 'computed_research_only'
                              and prior.subtotal(outcome['lines'], outcome['amount']['unit']) == outcome['amount'],
                              f'Scenario arithmetic mismatch: {oid}/{key}')
        three, four = by_case['hospital_3'], by_case['hospital_4']
        prior.require(three['status'] == four['status'] and three['source_refs'] == four['source_refs']
                      and three['requested_inpatient_days'] == 3 and four['requested_inpatient_days'] == 4,
                      f'Hospital correction scope changed: {oid}')
        if three['status'] == 'held':
            prior.require(three['reason_codes'] == four['reason_codes'], f'Hospital hold changed: {oid}')
        elif three['lines'][0]['rate']['unit'] == 'inpatient_day':
            prior.require(four['lines'][:3] == three['lines'] and len(four['lines']) == 4
                          and four['lines'][-1]['day'] == 4, f'Fourth covered day failed: {oid}')
        else:
            prior.require(three['lines'] == four['lines'] and three['amount'] == four['amount'],
                          f'Per-admission charge was repeated by day: {oid}')
        for field, case in (('primary_care_in_network', 'pcp_four_visits'), ('hospital_in_network', 'hospital_3')):
            if plan['published'][field].get('reason_codes') == ['CARRIER_CMS_COST_SHARE_CONFLICT']:
                prior.require(by_case[case]['status'] == 'held'
                              and 'CARRIER_CMS_COST_SHARE_CONFLICT' in by_case[case]['reason_codes'],
                              f'Material source conflict was priced: {oid}/{case}')
        premium = by_case['premium_12_months']
        if premium['status'] == 'computed_research_only':
            prior.require(len(premium['lines']) == 1 and premium['lines'][0]['quantity'] == 12
                          and premium['lines'][0]['rate'] == premium['monthly_rate'],
                          f'Plan premium contains an extra charge or credit: {oid}')
    for text in ('$0-65 copay per visit', '40% per stay', '0-20% coinsurance per visit'):
        prior.require(prior.exact_copay(prior.mpf_price(text), 'visit')[1] is None,
                      f'A range or percentage was converted into an exact charge: {text}')
    prior.reject_economic_fields(records)


def dollars(amount):
    n = Decimal(amount['amount'])
    return '$' + (format(n, ',.0f') if n == n.to_integral_value() else format(n, ',.2f'))


def compact(value):
    return ' / '.join(' '.join(line.split()) for line in str(value).splitlines() if line.strip()).replace('|', '\\|')


def display(field, formatter=compact):
    if field['state'] == 'not_applicable':
        return 'No Part D'
    value = field.get('value')
    visible = formatter(value) if value is not None else ''
    if field['state'] == 'held':
        return (visible + ' · ' if visible else '') + 'Held'
    return visible


def amount_or_text(value):
    return dollars(value) if isinstance(value, dict) and value.get('type') == 'decimal' else compact(value)


def display_maximum(values):
    if not isinstance(values, dict):
        return compact(values)
    suffix = {'in_network': 'IN', 'out_of_network': 'OON', 'combined': 'combined'}
    return ' / '.join(dollars(value) + ' ' + suffix[network] for network, value in values.items())


def scenario_label(outcome):
    return dollars(outcome['amount']) if outcome['amount'] else 'Held'


def render(data):
    intro = [
        '# Offline comparison for 72 retained 2026 Collier plans',
        '',
        'All 72 exact offerings are shown in offering-ID order. Published terms and fictional cost components are separate. '
        'A held field retains the available source value where applicable. Eligibility, doctors, medicine coverage and costs, '
        'individual Part B billing and personal requirements remain unchecked.',
        '',
        'IN means in-network. OON means out-of-network. Combined limits are separate published quantities. '
        'A Part B reduction sits outside the plan premium. For covered visits, the calculation covers the visit copay only. '
        'The admission example counts three or four covered inpatient days, starting on day one and excluding discharge day. '
        'It assumes any required referral and authorization, sufficient room under the medical maximum, and no assistance adjustment.',
        '',
        'Exact source records, qualifiers and all named holds are in [catalog.json](catalog.json). '
        'See [the execution record](REPORT.md) for the scope, replay and timing.',
        '',
        '## Plan costs and coverage',
        '',
        '| Plan and exact offering ID | Type and drug coverage | Plan premium month / 12 months | Part B reduction per month | Medical deductible | Medical maximums | Annual Part D deductible |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    care = [
        '',
        '## Published care terms and scenario components',
        '',
        '| Exact offering ID | In-network PCP term | Four PCP copays | In-network specialist term | In-network published hospital schedule | Facility copays for 3 → 4 days |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    holds = [
        '',
        '## Held fields and scenarios',
        '',
        '| Exact offering ID | Affected scenarios and reasons |',
        '| --- | --- |',
    ]
    for p in data['plans']:
        oid = p['offering_id'].split(':', 1)[1].replace(':', '-')
        f, results = p['published'], scenarios(p)
        coverage = f['coverage']['value']
        eligibility = ' · Erickson residence required' if coverage['residence_requirement'] else ''
        if coverage.get('snp') and coverage.get('snp_type') not in (None, 'Not Applicable'):
            eligibility += ' · ' + coverage['snp_type']
        drug = f['part_d_deductible']
        tiers = drug.get('conditions', {}).get('tiers')
        part_d = display(drug, amount_or_text) + (' · tiers ' + ', '.join(map(str, tiers)) if tiers else '')
        part_b = f['part_b_reduction']
        reduction = display(part_b, amount_or_text)
        if part_b.get('conditions', {}).get('maximum'):
            reduction = 'Up to ' + reduction
        premium = results['premium_12_months']
        monthly = dollars(premium['monthly_rate']) if premium.get('monthly_rate') else 'Held'
        intro.append('| ' + ' | '.join([
            compact(p['name']) + ' · ' + oid,
            compact(coverage['plan_type'] + (' · Part D' if coverage['includes_part_d'] else ' · No Part D') + eligibility),
            monthly + ' / ' + scenario_label(premium), reduction,
            display(f['medical_deductible'], amount_or_text), display(f['medical_maximums'], display_maximum), part_d,
        ]) + ' |')
        care.append('| ' + ' | '.join([
            oid, display(f['primary_care_in_network']), scenario_label(results['pcp_four_visits']),
            display(f['specialist_in_network']), display(f['hospital_in_network']),
            scenario_label(results['hospital_3']) + ' → ' + scenario_label(results['hospital_4']),
        ]) + ' |')
        notes = []
        for key, label in [('premium_12_months', 'Premium'), ('pcp_four_visits', 'PCP'), ('hospital_3', 'Both stays')]:
            if results[key]['status'] == 'held':
                notes.append(label + ' — ' + ' '.join(results[key]['unresolved']))
        for key, label in [('part_b_reduction', 'Part B reduction'), ('medical_deductible', 'Medical deductible'),
                           ('medical_maximums', 'Medical maximum'), ('part_d_deductible', 'Part D deductible'),
                           ('specialist_in_network', 'Specialist term')]:
            if f[key]['state'] == 'held':
                notes.append(label + ' — ' + ' '.join(f[key]['unresolved']))
        if notes:
            holds.append('| ' + oid + ' | ' + '<br>'.join(notes) + ' |')
    return '\n'.join(intro + care + holds) + '\n'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--check', action='store_true', help='Replay and compare both offline outputs.')
    args = cli.parse_args()
    data = build(inputs())
    outputs = {'catalog.json': json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
               'COMPARISON.md': render(data)}
    for name, contents in outputs.items():
        path = HERE / name
        if args.check:
            prior.require(path.read_text(encoding='utf-8') == contents, f'Offline output did not replay: {name}')
        else:
            with path.open('x', encoding='utf-8') as dest:
                dest.write(contents)
    print(json.dumps(data['coverage_counts'], indent=2))
    print('PASS: 72 identities, field completeness, sources, original pilot parity, scoped arithmetic and holds.')


if __name__ == '__main__':
    main()
