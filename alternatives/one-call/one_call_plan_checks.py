"""D214: evidence-backed card checks for the active :8897 variant.

An additive display projection over the existing, freshly reconciled doctor,
formulary and receipt-validated estimate results. It neither reads new sources
nor changes the pinned evaluation method, plan universe, scores or ordering.
Missing evidence, adverse evidence and conditional listings remain distinct.
"""
from datetime import date

VERSION = 'collier-plan-card-checks-v1'
REPLACED = {'doctors', 'medicines', 'pharmacy', 'drug_cost', 'total_cost'}
LISTED = {'listed_in_network', 'in_network'}
RESTRICTIONS = (
    ('prior_authorization', 'prior authorization'),
    ('step_therapy', 'step therapy'),
    ('quantity_limit', 'a quantity limit'),
)
HOLD_REASONS = {
    'assistance_unresolved_or_unsupported': 'Help paying for prescriptions is not supported by this estimate.',
    'prior_spending_unresolved_or_unsupported': 'Earlier drug spending or deductible credit is unresolved.',
    'criteria_unresolved': 'Drug coverage requirements still need checking.',
    'quantity_limit_rule_unresolved': 'A drug quantity limit still needs checking.',
    'only_in_area_retail_average_available': 'The available price basis supports local retail refills only.',
    'special_plan_rules_unresolved': 'This plan has special cost rules that are not supported by this estimate.',
    'multiple_outlets_unsupported': 'This estimate does not support medicines filled at different pharmacies.',
    'reported_fill_unsupported': 'These refill details are not supported by this estimate.',
    'result_changed': 'The inputs or evidence changed; the estimate needs to be recalculated.',
    'PILOT_SOURCE_STOP': 'The source is unavailable; the earlier result has been withdrawn.',
    'PILOT_EVIDENCE_STALE': 'The evidence is due for review; the earlier result has been withdrawn.',
}


def check(identifier, label, status, outcome, note, *, adverse=False, **extra):
    return {'id': identifier, 'label': label, 'kind': 'observation',
            'state': 'met' if status == 'supported' else 'not_met' if adverse else 'unknown',
            'indicator': status, 'outcome': outcome, 'note': note, **extra}


def _names(rows):
    return '; '.join(dict.fromkeys(str(row.get('label') or row.get('name') or 'Selected medicine')
                                  for row in rows))


def medicines(inputs, plan, formulary, *, includes_drugs=True):
    label = 'Your medicines'
    if not includes_drugs:
        return check('medicines', label, 'warning', 'No Part D drug coverage',
                     'This plan does not include a Part D drug benefit.', adverse=True)
    if inputs.get('medicines') == 'no':
        return check('medicines', label, 'information', 'No medicines reported',
                     'You reported that you do not take medicines. This is not a drug-coverage check.')
    if inputs.get('medicines') != 'yes':
        return check('medicines', label, 'warning', 'Not checked',
                     'Tell Daylight which medicines you want checked, or that you take none.')
    rows = ((formulary.get('plans') or {}).get(plan) or {}).get('medicines') or []
    products = formulary.get('products') or []
    if not rows or not products or len(rows) != len(products):
        return check('medicines', label, 'warning', 'Not checked',
                     'The complete, confirmed medicine list has not been checked for this plan.')
    absent = [row for row in rows if row.get('state') == 'not_listed']
    unresolved = [row for row in rows if row.get('state') not in {'covered', 'not_listed'}]
    restricted = []
    for row in rows:
        if row.get('state') != 'covered':
            continue
        flags = [word for key, word in RESTRICTIONS if row.get(key) is True]
        if flags:
            restricted.append(_names([row]) + ': ' + ', '.join(flags))
        elif any(row.get(key) is not False for key, _ in RESTRICTIONS):
            restricted.append(_names([row]) + ': coverage restrictions are unresolved')
    listed = sum(row.get('state') == 'covered' for row in rows)
    dates = sorted({row['evidence_date'] for row in rows if row.get('evidence_date')})
    note = f'{listed} of {len(rows)} exact medicines listed.'
    if absent:
        note += ' Not listed in the dated drug list: ' + _names(absent) + '.'
    if unresolved:
        note += ' Could not verify: ' + _names(unresolved) + '.'
    if restricted:
        note += ' ' + '; '.join(restricted) + '. These requirements are not an approval.'
    if dates:
        note += ' Drug list dated ' + ', '.join(dates) + '.'
    supported = not (absent or unresolved or restricted) and all(row.get('evidence_date') for row in rows)
    if supported:
        note = f'{listed} of {len(rows)} exact medicines listed: {_names(rows)}. Drug list dated {", ".join(dates)}.'
    return check('medicines', label, 'supported' if supported else 'warning',
                 'Listed in the drug list' if supported else 'Not listed' if absent else 'Needs checking',
                 note, adverse=bool(absent), evidence_dates=dates)


def doctors(inputs, identifier, selected, expected, *, medigap=None):
    label = 'Keep your doctors'
    if inputs.get('doctors') in {'no', 'none'}:
        return check('doctors', label, 'information', 'No doctors to check',
                     'You reported no doctors you want to keep. No network finding is implied.')
    if inputs.get('doctors') != 'list' or not expected:
        return check('doctors', label, 'warning', 'Not checked',
                     'Tell Daylight which doctors and offices you want to keep.')
    positive, open_, adverse, dates = [], [], [], set()
    for key in expected:
        result = selected.get('doctor:' + key, {})
        name = result.get('name') or (expected[key].get('name') if isinstance(expected, dict) else None) or 'Selected doctor'
        office = result.get('office_parts') or {}
        location = ', '.join(str(value) for value in (office.get('line') or office.get('street'), office.get('city')) if value)
        who = name + (' at ' + location if location else '')
        row = (result.get('original_medicare') or {}) if medigap is not None else (result.get('plans') or {}).get(identifier, {})
        if medigap is not None:
            supported = row.get('state') == 'accepts' and bool(row.get('record_date'))
            observed = [row['record_date']] if row.get('record_date') else []
        else:
            supported = (row.get('state') in {'dated_listing', 'confirmed'}
                         and row.get('membership') in LISTED and bool(row.get('evidence_dates')))
            observed = row.get('evidence_dates') or []
        dates.update(observed)
        if supported:
            positive.append(who)
        elif row.get('membership') == 'out_of_network' and row.get('state') == 'confirmed':
            adverse.append(who)
        else:
            reason = {'conflict': 'records disagree', 'stale': 'newer evidence needed'}.get(row.get('state'), 'no applicable record')
            open_.append(who + ' (' + reason + ')')
    count = f'{len(positive)} of {len(expected)} selected offices'
    note = count + (' have published Medicare assignment records.' if medigap is not None else ' listed in this plan’s network.')
    if positive:
        note += ' Listed: ' + '; '.join(positive) + '.'
    if open_:
        note += ' Still open: ' + '; '.join(open_) + '.'
    if adverse:
        note += ' Confirmed out of network: ' + '; '.join(adverse) + '.'
    if dates:
        note += ' Records dated ' + ', '.join(sorted(dates)) + '.'
    if medigap is not None and medigap.get('select_observed') is not False:
        note += (' This policy uses Medicare SELECT.' if medigap.get('select_observed') is True else
                 ' The source leaves this policy’s Medicare SELECT status unspecified.')
        return check('doctors', label, 'warning', 'SELECT network needs checking',
                     note + ' Confirm policy-specific access with the insurer.', evidence_dates=sorted(dates))
    supported = bool(positive) and not (open_ or adverse)
    if supported and medigap is None:
        note += ' A dated listing does not confirm appointment availability or participation on a future visit date.'
    return check('doctors', label, 'supported' if supported else 'warning',
                 'Medicare assignment listed' if supported and medigap is not None else
                 'Listed in network' if supported else 'Out of network' if adverse else 'Needs checking',
                 note, adverse=bool(adverse), evidence_dates=sorted(dates))


def _cents(value):
    return value if type(value) is int and value >= 0 else None


def _money(value):
    return f'${value // 100:,}.{value % 100:02d}'


def estimate(row):
    values = [_cents(row.get(key)) for key in ('plan_premium_cents', 'drug_spending_cents', 'plan_premium_plus_drugs_cents')]
    try:
        start, end = date.fromisoformat(row.get('start', '')), date.fromisoformat(row.get('end', ''))
        period_ok = start.year == end.year == 2026 and start <= end
    except (ValueError, TypeError):
        period_ok = False
    if (row.get('state') == 'offline_average_candidate' and all(v is not None for v in values)
            and values[0] + values[1] == values[2] and period_ok):
        premium, drugs, total = values
        summary = row.get('summary') or {}
        assumptions = [med.get('name') or 'Selected medicine' for med in summary.get('medicines', [])
                       if med.get('days_supply_assumed')]
        assumption_note = (' Uses an editable 30-day supply assumption for ' + '; '.join(assumptions) + '.') if assumptions else ''
        return check('drug_cost', 'Premiums and drug spending', 'supported', 'Estimate available',
                     f'{_money(total)} for {start.strftime("%b %d, %Y")} through {end.strftime("%b %d, %Y")}: '
                     f'{_money(premium)} plan premiums + {_money(drugs)} drug spending. '
                     'Uses retail averages for the selected refills, not exact-store prices. '
                     'Excludes Part B premiums and medical costs; this is not total annual healthcare cost.' + assumption_note,
                     amounts={key: row[key] for key in ('plan_premium_cents', 'drug_spending_cents', 'plan_premium_plus_drugs_cents')},
                     start=row['start'], end=row['end'])
    return check('drug_cost', 'Premiums and drug spending', 'warning', 'Estimate unavailable',
                 HOLD_REASONS.get(row.get('hold'), 'A supported, comparable estimate has not been calculated for this plan. '
                                  'Any published premium is separate from drug and medical spending.'))


def pharmacy(row):
    state = (row.get('pharmacy') or {}).get('state')
    return check('pharmacy', 'Your pharmacy', 'supported' if state in {'preferred', 'standard'} else 'warning',
                 'Listed as ' + state if state in {'preferred', 'standard'} else 'Needs checking',
                 'Your selected outlet is listed for this plan and dispensing channel. This does not establish its exact prices.'
                 if state in {'preferred', 'standard'} else
                 'This plan’s participation for your exact pharmacy outlet and channel is unresolved.')


def total_cost():
    return check('total_cost', 'Total yearly cost', 'warning', 'Not calculated',
                 'A complete medical-plus-drug estimate is not available. Published premiums and any drug estimate are only components.')


def project(result, inputs, *, checks=(), expected_doctors=(), ma_plans=(), medigap_result=None, **_):
    """Called only on :8897, after source controls and report revisions reconcile."""
    formulary = next((r for r in checks if r.get('kind') == 'formulary'), {})
    comparison = next((r for r in checks if r.get('kind') == 'drug_comparison'), {})
    costs = {key: {**row, 'summary': comparison.get('summary')} for key, row in comparison.get('plans', {}).items()}
    for row in checks:
        if row.get('kind') == 'prescription' and row.get('offering_id') and row.get('amounts'):
            costs.setdefault(row['offering_id'], {**row['amounts'], 'start': row.get('start'), 'end': row.get('end'),
                                                 'state': 'offline_average_candidate', 'summary': row.get('summary')})
    selected = {r['key']: r for r in checks if r.get('kind') == 'doctor_matrix'}
    ma = {p['id']: p for p in ma_plans}
    gaps = {p['id']: p for p in (medigap_result or {}).get('plans', [])}
    scope = inputs.get('scope') or {}
    applicable = scope.get('year') == 2026 and scope.get('county_fips') == '12021'
    for kind in ('advantage', 'medigap', 'part_d'):
        for identifier, plan in (result.get(kind, {}).get('plans') or {}).items():
            rows = [{**c, 'indicator': 'supported' if c['state'] == 'met' else 'warning',
                     'outcome': 'Meets' if c['state'] == 'met' else 'Does not meet' if c['state'] == 'not_met' else 'Needs checking'}
                    for c in plan.get('checks', []) if c['id'] not in REPLACED]
            if not applicable:
                plan['card_checks'] = [check(key, label, 'warning', 'Outside supported scope',
                                            'These checks require confirmed 2026 Collier County scope. No finding has been carried to another year or county.')
                                       for key, label in (('doctors', 'Keep your doctors'), ('medicines', 'Your medicines'),
                                                          ('total_cost', 'Total yearly cost'))]
                continue
            if kind != 'part_d':
                rows.append(doctors(inputs, identifier, selected, expected_doctors,
                                    medigap=gaps.get(identifier, {}) if kind == 'medigap' else None))
            if kind == 'medigap':
                rows.append(check('medicines', 'Your medicines', 'information', 'Separate Part D plan',
                                  'Check your medicines on the separate Part D plan you pair with Original Medicare. '
                                  'This Medigap premium does not include a drug plan.'))
                cents = _cents(gaps.get(identifier, {}).get('monthly_cents'))
                rows.append(check('premium', 'Medigap premium', 'supported' if cents is not None else 'warning',
                                  'Published price available' if cents is not None else 'Price unavailable',
                                  f'{_money(cents)} per month for the exact displayed quote profile and source date. '
                                  'This is a published rate, not a binding quote or an eligibility finding.' if cents is not None else
                                  'No exact-profile premium is available for this policy.'))
            else:
                included = kind == 'part_d' or ma.get(identifier, {}).get('drugs', False)
                rows.append(medicines(inputs, identifier, formulary, includes_drugs=included))
                if included:
                    row = costs.get(identifier, {})
                    rows.extend((pharmacy(row), estimate(row)))
            rows.append(total_cost())
            plan['card_checks'] = rows
    result['plan_card_checks'] = {'version': VERSION, 'scope': '2026 Collier County',
                                 'ranking_changed': False, 'total_cost_supported': False}
    return result
