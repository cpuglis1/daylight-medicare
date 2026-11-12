"""D147 tiered recommendation, evaluation mode only. Deterministic; no model calls.

Owner-approved structure (November 12, 2026):
  Tier 1  eligibility and scope           fail or unknown -> "not filtered to"
  Tier 2  hard needs                        fail            -> "not filtered to"
  Tier 3  the person's stated priorities   any fail        -> "filtered, but not your priorities"
                                            none fail       -> "priority group"
  Tier 4  inside a group: stated priorities met, then other preferences met,
          then the tab's cost order
Unknown is never a miss for tiers 3 and 4: a plan we cannot check stays in its
group, marked "not checked". Eligibility (tier 1) must be established to be
recommended, so a plan a person may not qualify for is never recommended.
Cost preferences choose the order inside a tab; across coverage paths they are
checks. No pick is named for drug coverage (Part D, or Medicare Advantage with
drugs) unless the person reported no medicines: drug lists are not checked yet.
Commission and other commercial values are never read.
"""
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json

METHOD = 'daylight-tiered-v1-20261112'
INPUTS_VERSION = 'recommendation-inputs-v1'
GROUPS = ('priority', 'needs', 'excluded')
GROUP_LABELS = {
    'priority': 'Matches your priorities',
    'needs': 'Meets your needs, not all your priorities',
    'excluded': 'Doesn’t meet your needs, or you may not qualify',
}
GROUP_LABELS_NO_PRIORITIES = {'priority': 'Meets your needs'}
TRAVEL_ABROAD_LETTERS = {'C', 'D', 'F', 'HDF', 'G', 'HDG', 'M', 'N'}
PREDICTABLE_LETTERS = {'C', 'D', 'F', 'G'}
PREDICTABLE_NOTES = {
    'N': 'Copays for some office and emergency visits',
    'K': 'You pay a share of costs until a yearly limit',
    'L': 'You pay a share of costs until a yearly limit',
    'HDF': 'A yearly deductible before it pays',
    'HDG': 'A yearly deductible before it pays',
    'A': 'Leaves the Part A deductible to you',
    'B': 'Leaves some Part B costs to you',
    'M': 'Leaves half the Part A deductible to you',
}
CF_LETTERS = {'C', 'F', 'HDF'}
OTHER_DRUG_COVERAGE = {'military', 'retiree'}
LABELS = {
    'doctors': 'Keep your doctors',
    'medicines': 'Your medicines',
    'travel_us': 'Care in other states',
    'travel_abroad': 'Care outside the U.S.',
    'predictable': 'Predictable costs',
    'lower_monthly': 'Lower monthly cost',
    'total_cost': 'Total yearly cost',
}
PRIORITY_MAP = {'doctors': 'doctors', 'drugs': 'medicines', 'bills': 'predictable',
                'total_cost': 'total_cost'}
COMMERCIAL = ('commission', 'payout', 'compensation', 'referral_fee', 'lifetime_value', 'revenue')
INF = Decimal('Infinity')


# ---------------------------------------------------------------- inputs

def _usable(guide, field):
    item = (guide.get('fields') or {}).get(field) or {}
    if item.get('status') not in {'reported', 'derived'}:
        return None
    value = item.get('value')
    return None if value in ('unknown', 'deferred') else value


def _as_list(value):
    if value is None:
        return []
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


def inputs(guide, record, medigap_view, part_d_view):
    """The person's reported details that the method reads; nothing inferred."""
    facts = (record or {}).get('facts') or {}
    medicaid_reports = _as_list(((facts.get('RC18') or {}).get('value') or {}).get('choice'))
    current = _as_list(_usable(guide, 'coverage.current'))
    medicaid = (True if 'medicaid' in current or 'medicaid' in medicaid_reports
                else False if 'none' in medicaid_reports else None)
    reported_age = next((d.get('value') for d in medigap_view.get('details', [])
                         if d.get('id') == 'MG_AGE' and type(d.get('value')) is int), None)
    mg = medigap_view.get('inputs') or {}
    pd = part_d_view.get('inputs') or {}
    return {
        'version': INPUTS_VERSION,
        'scope': {'zipcode': pd.get('zipcode') or mg.get('zipcode'), 'county_fips': pd.get('county_fips'),
                  'year': pd.get('year')},
        'medigap': {'status': medigap_view.get('status'), 'zipcode': mg.get('zipcode'), 'age': mg.get('age'),
                    'reported_age': reported_age, 'gender': mg.get('gender'), 'tobacco': mg.get('tobacco')},
        'part_d_status': part_d_view.get('status'),
        'doctors': _usable(guide, 'needs.providersStatus'),
        'medicines': _usable(guide, 'needs.medicinesStatus'),
        'travel': _as_list(_usable(guide, 'needs.travel')),
        'cost_preference': _usable(guide, 'needs.costPreference'),
        'priorities': _as_list(_usable(guide, 'needs.priorities')),
        'current_coverage': current,
        'medicaid': medicaid,
    }


def validate_inputs(value):
    if not isinstance(value, dict) or value.get('version') != INPUTS_VERSION:
        raise ValueError('Use current recommendation inputs.')
    expected = {'version', 'scope', 'medigap', 'part_d_status', 'doctors', 'medicines', 'travel',
                'cost_preference', 'priorities', 'current_coverage', 'medicaid'}
    if set(value) != expected:
        raise ValueError('Use current recommendation inputs.')
    text = json.dumps(value).casefold()
    if any(word in text for word in COMMERCIAL):
        raise ValueError('Commercial values are not accepted.')
    for key in ('travel', 'priorities', 'current_coverage'):
        if not isinstance(value[key], list) or not all(isinstance(v, str) and len(v) < 40 for v in value[key]):
            raise ValueError('Use current recommendation inputs.')
    if value['medicaid'] not in (True, False, None):
        raise ValueError('Use current recommendation inputs.')
    return copy.deepcopy(value)


def preferences(inp):
    """Stated preferences, and which of them the person named as priorities."""
    prefs = []
    if inp.get('doctors') == 'list' or 'doctors' in inp['priorities']:
        prefs.append('doctors')
    if inp.get('medicines') == 'yes' or 'drugs' in inp['priorities']:
        prefs.append('medicines')
    travel = set(inp['travel'])
    if 'elsewhere_us' in travel or ('travel' in inp['priorities'] and not travel & {'outside_us'}):
        prefs.append('travel_us')
    if 'outside_us' in travel:
        prefs.append('travel_abroad')
    if inp.get('cost_preference') == 'predictable' or 'bills' in inp['priorities']:
        prefs.append('predictable')
    if inp.get('cost_preference') == 'lower_monthly':
        prefs.append('lower_monthly')
    if 'total_cost' in inp['priorities']:
        prefs.append('total_cost')
    priorities = {PRIORITY_MAP[p] for p in inp['priorities'] if p in PRIORITY_MAP}
    if 'travel' in inp['priorities']:
        priorities |= {p for p in ('travel_us', 'travel_abroad') if p in prefs}
    return prefs, sorted(priorities)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


# ---------------------------------------------------------------- shared

def _check(identifier, state, note, kind):
    return {'id': identifier, 'label': LABELS.get(identifier, identifier), 'state': state, 'note': note, 'kind': kind}


def _money(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _group(checks, priorities):
    if any(c['kind'] in {'eligibility', 'need'} and c['state'] != 'met' for c in checks):
        return 'excluded'
    if any(c['kind'] == 'priority' and c['state'] == 'not_met' for c in checks):
        return 'needs'
    return 'priority'


def _assemble(kind, rows, priorities, *, no_pick=None, sort_note='', notes=()):
    """rows: [{'id', 'checks', 'key': tuple of Decimal}] -> grouped, ranked result."""
    plans = {}
    for row in rows:
        checks = row['checks']
        for c in checks:
            if c['kind'] == 'preference' and c['id'] in priorities:
                c['kind'] = 'priority'
        group = _group(checks, priorities)
        met = sum(c['state'] == 'met' for c in checks if c['kind'] in {'priority', 'preference'})
        met_priorities = sum(c['state'] == 'met' for c in checks if c['kind'] == 'priority')
        plans[row['id']] = {'group': group, 'met': met, 'met_priorities': met_priorities, 'checks': checks,
                            'complete': all(v is not None and v != INF for v in row['key']),
                            'key': row['key'], 'rank': None, 'recommended': False}
    groups = []
    for gid in GROUPS:
        members = [i for i, p in plans.items() if p['group'] == gid]
        # Plans missing an amount stay in their group but are unranked: listed
        # after the ranked plans, never treated as worse and never recommended.
        # Stated priorities met count first, then other preferences met.
        members.sort(key=lambda i: (not plans[i]['complete'], -plans[i]['met_priorities'], -plans[i]['met'])
                     + tuple(v if v is not None else INF for v in plans[i]['key']) + (i,))
        rank, previous, position = 0, None, 0
        for identifier in members:
            p = plans[identifier]
            if not p['complete']:
                p['rank'] = None
                continue
            position += 1
            signature = (p['met_priorities'], p['met'], p['key'])
            if signature != previous:
                rank, previous = position, signature
            p['rank'] = rank
        label = (GROUP_LABELS_NO_PRIORITIES.get(gid) if not priorities else None) or GROUP_LABELS[gid]
        groups.append({'id': gid, 'label': label, 'ids': members})
    recommended = []
    if not no_pick:
        recommended = [i for i in groups[0]['ids'] if plans[i]['rank'] == 1]
        for i in recommended:
            plans[i]['recommended'] = True
    for p in plans.values():
        p['key'] = [str(v) if v is not None and v != INF else None for v in p['key']]
    return {'kind': kind, 'state': 'ready', 'method': METHOD, 'groups': groups, 'plans': plans,
            'recommended_ids': recommended, 'no_pick_reason': no_pick, 'sort_note': sort_note,
            'notes': list(notes), 'priorities': priorities}


def _unavailable(kind, message):
    return {'kind': kind, 'state': 'unavailable', 'method': METHOD, 'message': message,
            'groups': [], 'plans': {}, 'recommended_ids': [], 'no_pick_reason': None, 'notes': []}


DRUG_NO_PICK = ('No pick yet: your medicines are not checked against plan drug lists. '
                'Plans are grouped and ordered by the details that can be checked.')
UNDERWRITING = ('Outside the 6-month Medigap Open Enrollment Period that starts with Part B at 65 or older, '
                'an insurer can usually ask health questions and may decline or charge more.')


# ---------------------------------------------------------------- Medicare Advantage

def evaluate_ma(inp, plans):
    if not plans:
        return _unavailable('advantage', 'Medicare Advantage plan information is not available.')
    if inp['scope'].get('county_fips') not in (None, '12021'):
        return _unavailable('advantage', 'Medicare Advantage plans in this pilot cover Collier County, Florida.')
    prefs, priorities = preferences(inp)
    rows = []
    for plan in plans:
        restrictions = ' '.join(plan.get('restrictions') or [])
        checks = []
        if restrictions:
            if 'Dual Eligible' in restrictions:
                state = 'met' if inp['medicaid'] is True else 'not_met' if inp['medicaid'] is False else 'unknown'
                note = {'met': 'You reported Medicaid', 'not_met': 'For people with both Medicare and Medicaid',
                        'unknown': 'For people with both Medicare and Medicaid; not confirmed'}[state]
            else:
                state, note = 'unknown', 'Has joining rules you have not confirmed'
            checks.append(_check('eligibility', state, note, 'eligibility'))
            checks[-1]['label'] = 'Who can join'
        # Most people in a Medicare Advantage plan cannot add a separate drug
        # plan, and going without drug coverage can bring a Part D late penalty.
        # Drug coverage is a need unless other drug coverage was reported.
        if not set(inp['current_coverage']) & OTHER_DRUG_COVERAGE:
            checks.append(_check('drug_coverage', 'met' if plan['drugs'] else 'not_met',
                                 'Includes drug coverage' if plan['drugs']
                                 else 'No drug coverage; a Part D late penalty may apply', 'need'))
            checks[-1]['label'] = 'Drug coverage'
        family = 'PPO' if 'PPO' in plan['type'] else 'HMO-POS' if 'HMO-POS' in plan['type'] else 'HMO'
        for pref in prefs:
            if pref == 'doctors':
                checks.append(_check(pref, 'unknown', "Network not checked for your doctors", 'preference'))
            elif pref == 'medicines' and plan['drugs']:
                checks.append(_check(pref, 'unknown', "Not checked against the plan's drug list", 'preference'))
            elif pref == 'travel_us':
                state, note = {'PPO': ('met', 'Covers out-of-network care'),
                               'HMO-POS': ('unknown', 'Some out-of-network coverage'),
                               'HMO': ('not_met', 'Mostly emergencies outside the network')}[family]
                checks.append(_check(pref, state, note, 'preference'))
            elif pref == 'travel_abroad':
                checks.append(_check(pref, 'unknown', 'Not in the plan information', 'preference'))
            elif pref == 'total_cost':
                checks.append(_check(pref, 'unknown', 'Needs your medicines and care use', 'preference'))
        premium, limit = _money(plan.get('premium')), _money(plan.get('in_network_limit'))
        predictable = inp.get('cost_preference') == 'predictable' or 'bills' in inp['priorities']
        key = (limit, premium) if predictable else (premium, limit)
        rows.append({'id': plan['id'], 'checks': checks, 'key': key})
    no_pick = DRUG_NO_PICK if inp.get('medicines') != 'no' else None
    sort_note = ('Ordered by lowest yearly in-network limit, then premium, because you want predictable costs.'
                 if inp.get('cost_preference') == 'predictable' or 'bills' in inp['priorities']
                 else 'Ordered by lowest monthly premium, then yearly in-network limit.')
    result = _assemble('advantage', rows, priorities, no_pick=no_pick, sort_note=sort_note)
    result['minimum_monthly'] = _minimum(plans, result, lambda p: _money(p.get('premium')))
    return result


# ---------------------------------------------------------------- Medigap

def _cf_state(age):
    if type(age) is not int:
        return 'unknown', 'Only for people eligible for Medicare before 2020; age not known'
    if age >= 72:
        return 'met', 'Eligible for Medicare before 2020 by age'
    if age <= 70:
        return 'not_met', 'Only for people eligible for Medicare before 2020'
    return 'unknown', 'Only for people eligible for Medicare before 2020; check your start date'


def evaluate_medigap(inp, result):
    if inp['medigap'].get('status') != 'ready':
        return _unavailable('medigap', 'Medigap needs your ZIP, age, sex category and tobacco category first.')
    if not result or result.get('status') != 'matched_source_prices':
        return _unavailable('medigap', (result or {}).get('message') or 'Medigap prices are not available.')
    prefs, priorities = preferences(inp)
    rows = []
    for plan in result['plans']:
        letter = plan['variant']
        checks = []
        if letter in CF_LETTERS:
            state, note = _cf_state(inp['medigap'].get('reported_age'))
            checks.append(_check('eligibility', state, note, 'eligibility'))
            checks[-1]['label'] = 'Who can buy it'
        for pref in prefs:
            if pref == 'doctors':
                if plan.get('select_observed') is True:
                    checks.append(_check(pref, 'unknown', 'Medicare SELECT uses a network', 'preference'))
                else:
                    checks.append(_check(pref, 'met', 'Any doctor who takes Medicare; not marked as Medicare SELECT',
                                         'preference'))
            elif pref == 'travel_us':
                checks.append(_check(pref, 'met', 'Original Medicare works in every state', 'preference'))
            elif pref == 'travel_abroad':
                ok = letter in TRAVEL_ABROAD_LETTERS
                checks.append(_check(pref, 'met' if ok else 'not_met',
                                     'Foreign travel emergency coverage' if ok else 'No foreign travel coverage',
                                     'preference'))
            elif pref == 'predictable':
                ok = letter in PREDICTABLE_LETTERS
                checks.append(_check(pref, 'met' if ok else 'not_met',
                                     'No per-visit copays; pays most Part A and B costs' if ok
                                     else PREDICTABLE_NOTES.get(letter, 'Leaves some costs to you'), 'preference'))
            elif pref == 'total_cost':
                checks.append(_check(pref, 'unknown', 'Needs your care use', 'preference'))
        cents = plan.get('monthly_cents')
        rows.append({'id': plan['id'], 'checks': checks, 'key': (_money(cents),)})
    notes = [UNDERWRITING, 'Medigap does not cover prescription drugs; drug coverage is a separate Part D plan.']
    out = _assemble('medigap', rows, priorities, sort_note='Ordered by lowest listed monthly premium.', notes=notes)
    out['minimum_monthly_cents'] = _minimum_cents(result['plans'], out, 'monthly_cents')
    return out


# ---------------------------------------------------------------- Part D

def _field_cents(plan, key):
    field = (plan.get('fields') or {}).get(key) or {}
    if field.get('state') != 'published' or field.get('value_encoding') != 'integer_cents':
        return None
    return _money(field.get('value'))


def evaluate_part_d(inp, result):
    if inp.get('part_d_status') != 'ready':
        return _unavailable('part_d', 'Part D needs your ZIP and county first.')
    if not result or result.get('status') != 'published_plans':
        return _unavailable('part_d', (result or {}).get('message') or 'Part D plan information is not available.')
    prefs, priorities = preferences(inp)
    predictable = inp.get('cost_preference') == 'predictable' or 'bills' in inp['priorities']
    rows = []
    for plan in result['plans']:
        checks = []
        if 'medicines' in prefs:
            checks.append(_check('medicines', 'unknown', "Not checked against the plan's drug list", 'preference'))
        if 'total_cost' in prefs:
            checks.append(_check('total_cost', 'unknown', 'Needs your medicines and pharmacy', 'preference'))
        premium, deductible = _field_cents(plan, 'total_premium'), _field_cents(plan, 'annual_deductible')
        rows.append({'id': plan['id'], 'checks': checks,
                     'key': (deductible, premium) if predictable else (premium, deductible)})
    no_pick = None if inp.get('medicines') == 'no' else DRUG_NO_PICK
    sort_note = ('Ordered by lowest yearly drug deductible, then premium, because you want predictable costs.'
                 if predictable else 'Ordered by lowest monthly premium, then yearly drug deductible.')
    out = _assemble('part_d', rows, priorities, no_pick=no_pick, sort_note=sort_note)
    out['minimum_monthly_cents'] = None
    values = [_field_cents(p, 'total_premium') for p in result['plans']]
    values = [v for v in values if v is not None]
    if values:
        out['minimum_monthly_cents'] = str(min(values))
    return out


def _minimum(plans, result, read):
    values = [read(p) for p in plans if result['plans'][p['id']]['group'] != 'excluded']
    values = [v for v in values if v is not None]
    return str(min(values)) if values else None


def _minimum_cents(plans, result, key):
    values = [_money(p.get(key)) for p in plans if result['plans'][p['id']]['group'] != 'excluded']
    values = [v for v in values if v is not None]
    return str(min(values)) if values else None


# ---------------------------------------------------------------- coverage path

def evaluate_path(inp, ma, medigap, part_d):
    if not inp['scope'].get('zipcode'):
        return _unavailable('path', 'The coverage-path comparison needs your ZIP first.')
    if 'employer' in inp['current_coverage']:
        out = _unavailable('path', 'You reported coverage through a current job. When to sign up comes '
                                   'before choosing a path, so Daylight does not suggest one yet.')
        out['state'] = 'held'
        return out
    prefs, priorities = preferences(inp)
    original, advantage = [], []
    for pref in prefs:
        if pref == 'doctors':
            original.append(_check(pref, 'met', 'Any doctor in the U.S. who takes Medicare', 'preference'))
            advantage.append(_check(pref, 'unknown', "Depends on each plan's network; not checked", 'preference'))
        elif pref == 'medicines':
            for side in (original, advantage):
                side.append(_check(pref, 'unknown', 'Not checked against drug lists', 'preference'))
        elif pref == 'travel_us':
            original.append(_check(pref, 'met', 'Works in every state', 'preference'))
            advantage.append(_check(pref, 'unknown', 'PPO plans cover out-of-network care; HMO plans mostly emergencies',
                                    'preference'))
        elif pref == 'travel_abroad':
            original.append(_check(pref, 'met', 'Medigap Plans C, D, F, G, M and N cover foreign travel emergencies',
                                   'preference'))
            advantage.append(_check(pref, 'unknown', 'Not in the plan information', 'preference'))
        elif pref == 'predictable':
            original.append(_check(pref, 'met', 'Medigap Plans C, D, F and G pay most costs with no per-visit copays',
                                   'preference'))
            advantage.append(_check(pref, 'not_met', 'Copays and coinsurance until the yearly limit', 'preference'))
        elif pref == 'lower_monthly':
            mg = _money(medigap.get('minimum_monthly_cents')) if medigap.get('state') == 'ready' else None
            pdp = _money(part_d.get('minimum_monthly_cents')) if part_d.get('state') == 'ready' else None
            ma_low = _money(ma.get('minimum_monthly')) if ma.get('state') == 'ready' else None
            if mg is None or pdp is None or ma_low is None:
                for side in (original, advantage):
                    side.append(_check(pref, 'unknown', 'Needs Medigap prices for your details', 'preference'))
            else:
                orig_dollars = (mg + pdp) / 100
                a_state = 'met' if ma_low <= orig_dollars else 'not_met'
                o_state = 'met' if orig_dollars <= ma_low else 'not_met'
                original.append(_check(pref, o_state, f'Lowest listed Medigap plus drug plan: ${orig_dollars:,.2f} a month',
                                       'preference'))
                advantage.append(_check(pref, a_state, f'Lowest listed premium: ${ma_low:,.2f} a month', 'preference'))
        elif pref == 'total_cost':
            for side in (original, advantage):
                side.append(_check(pref, 'unknown', 'Needs your medicines and care use', 'preference'))
    rows = [{'id': 'original', 'checks': original, 'key': ()}, {'id': 'advantage', 'checks': advantage, 'key': ()}]
    notes = [UNDERWRITING]
    if inp['medicaid'] is True:
        notes.append('You reported Medicaid. Special Needs Plans and help with costs may apply; check those first.')
    out = _assemble('path', rows, priorities, notes=notes)
    out['labels'] = {'original': 'Original Medicare with Medigap and a Part D plan', 'advantage': 'Medicare Advantage'}
    if not priorities and not prefs:
        out['no_pick_reason'] = 'Tell Daylight what matters most to you to compare the two paths.'
        out['recommended_ids'] = []
        for p in out['plans'].values():
            p['recommended'] = False
    elif len(out['recommended_ids']) > 1:
        out['no_pick_reason'] = ('Both paths fit what you told Daylight equally so far; '
                                 'nothing checked yet separates them.')
        out['recommended_ids'] = []
        for p in out['plans'].values():
            p['recommended'] = False
    return out


# ---------------------------------------------------------------- entry point

def evaluate(inp, *, ma_plans, medigap_result, part_d_result):
    inp = validate_inputs(inp)
    ma = evaluate_ma(inp, ma_plans)
    medigap = evaluate_medigap(inp, medigap_result)
    part_d = evaluate_part_d(inp, part_d_result)
    path = evaluate_path(inp, ma, medigap, part_d)
    prefs, priorities = preferences(inp)
    return {'method': METHOD, 'evaluation_only': True, 'inputs_digest': digest(inp),
            'preferences': [{'id': p, 'label': LABELS[p], 'priority': p in priorities} for p in prefs],
            'path': path, 'advantage': ma, 'medigap': medigap, 'part_d': part_d,
            'notice': ('Evaluation mode: Daylight’s tiered sorting is on for fictional testing only. '
                       'It is not shown to pilot participants.')}
