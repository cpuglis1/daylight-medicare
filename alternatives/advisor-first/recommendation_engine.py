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
checks. Dated coverage observations can affect fit. Named drug picks remain
held pending review of the comparison method and evidence.
Commission and other commercial values are never read.
"""
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

METHOD = 'daylight-tiered-v3-20261114'
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
    first = first_eligibility(guide, record)
    return {
        'version': INPUTS_VERSION,
        'scope': {'zipcode': pd.get('zipcode') or mg.get('zipcode'), 'county_fips': pd.get('county_fips'),
                  'year': pd.get('year')},
        'medigap': {'status': medigap_view.get('status'), 'zipcode': mg.get('zipcode'), 'age': mg.get('age'),
                    'reported_age': reported_age, 'gender': mg.get('gender'), 'tobacco': mg.get('tobacco'),
                    'first_eligible': first},
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


def checked_preferences(inp, plans):
    prefs, priorities = preferences(inp)
    checked = {check['id'] for plan in plans.values() for check in plan['checks']
               if check['state'] != 'unknown'}
    return [{'id': pref, 'label': LABELS[pref], 'priority': pref in priorities,
             'checked': pref in checked} for pref in prefs]


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
        if gid == 'priority' and any(c['state'] == 'unknown' and c['kind'] in ('priority', 'preference')
                                   for i in members for c in plans[i]['checks']):
            label = 'Available options · personal checks remain'
        groups.append({'id': gid, 'label': label, 'ids': members})
    recommended = []
    if not no_pick:
        recommended = [i for i in groups[0]['ids'] if plans[i]['rank'] == 1
                       and not any(c['state'] == 'unknown' for c in plans[i]['checks'])]
        for i in recommended:
            plans[i]['recommended'] = True
        if not recommended and any(c['state'] == 'unknown' for p in plans.values() for c in p['checks']):
            no_pick = 'Personal checks remain unresolved. The order reflects the published terms shown, not a completed personal match.'
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
DRUG_EVIDENCE_NO_PICK = ('Daylight can show the dated drug-list results. '
                         'Compare the restrictions and your costs before choosing a plan.')
UNDERWRITING = ('Outside the 6-month Medigap Open Enrollment Period that starts with Part B at 65 or older, '
                'an insurer can usually ask health questions and may decline or charge more.')


# ---------------------------------------------------------------- Medicare Advantage

def medicine_fit(rows):
    if rows and all(row['state'] == 'covered' for row in rows):
        return 'met', 'All your exact medicines are listed in the dated formulary.'
    if any(row['state'] == 'not_listed' for row in rows):
        return 'not_met', 'At least one exact medicine is absent from the dated formulary.'
    return 'unknown', 'Your medicines could not all be checked against this drug list.'


def doctor_fit(rows, *, original=False):
    if original:
        if rows and all(row.get('state') == 'accepts' for row in rows):
            return 'met', 'Published Medicare records list assignment at your selected offices.'
        return 'unknown', 'Medicare assignment is unresolved for at least one selected office.'
    if any(row.get('membership') == 'out_of_network' for row in rows):
        return 'not_met', 'At least one selected office was confirmed out of network.'
    if rows and all(row.get('membership') in {'listed_in_network', 'in_network'} for row in rows):
        return 'met', 'Dated evidence lists all your selected offices in this network.'
    return 'unknown', 'Network evidence is incomplete for your selected offices.'


def evaluate_ma(inp, plans, *, medicines=None, doctors=None, drug_costs=None):
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
        includes_drugs = plan['id'] in (medicines or {}) or plan['drugs']
        if not set(inp['current_coverage']) & OTHER_DRUG_COVERAGE:
            checks.append(_check('drug_coverage', 'met' if includes_drugs else 'not_met',
                                 'Includes drug coverage' if includes_drugs
                                 else 'No drug coverage; a Part D late penalty may apply', 'need'))
            checks[-1]['label'] = 'Drug coverage'
        family = 'PPO' if 'PPO' in plan['type'] else 'HMO-POS' if 'HMO-POS' in plan['type'] else 'HMO'
        for pref in prefs:
            if pref == 'doctors':
                checks.append(_check(pref, *doctor_fit((doctors or {}).get(plan['id'], ())), 'preference'))
            elif pref == 'medicines' and includes_drugs:
                checks.append(_check(pref, *medicine_fit((medicines or {}).get(plan['id'], ())), 'preference'))
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
        if drug_costs is not None:
            checks.extend(drug_comparison_checks(drug_costs.get(plan['id'], {})))
            key = (drug_cost_key(drug_costs.get(plan['id'], {})),)
        rows.append({'id': plan['id'], 'checks': checks, 'key': key})
    no_pick = (DRUG_EVIDENCE_NO_PICK if medicines else DRUG_NO_PICK) if inp.get('medicines') != 'no' else None
    sort_note = ('Ordered by lowest yearly in-network limit, then premium, because you want predictable costs.'
                 if inp.get('cost_preference') == 'predictable' or 'bills' in inp['priorities']
                 else 'Ordered by lowest monthly premium, then yearly in-network limit.')
    result = _assemble('advantage', rows, priorities, no_pick=no_pick, sort_note=sort_note)
    if drug_costs is not None: result['sort_note'] = DRUG_COST_ORDER
    result['minimum_monthly'] = _minimum(plans, result, lambda p: _money(p.get('premium')))
    return result


# ---------------------------------------------------------------- Medigap

def first_eligibility(guide, record):
    explicit = _usable(guide, 'enrollment.firstEligible')
    if isinstance(explicit, str) and re.fullmatch(r'(?:19|20)\d\d-(?:0[1-9]|1[0-2])', explicit):
        return explicit
    facts = record.get('facts', {}) if record else {}
    eligibility = facts.get('RC06', {})
    basis = (eligibility.get('value') or {}).get('choice') if not eligibility.get('stale') else None
    if basis in ('disability', 'esrd', 'als'):
        return None
    # Part B may have started later. A pre-2020 start proves eligibility
    # existed by then; a later start alone does not establish the first date.
    part_b = _usable(guide, 'enrollment.partB')
    if isinstance(part_b, dict) and part_b.get('status') == 'active' and part_b.get('date_kind') == 'start':
        reported = str(part_b.get('date') or '')[:7]
        if re.fullmatch(r'(?:19|20)\d\d-(?:0[1-9]|1[0-2])', reported) and reported < '2020-01':
            return reported
    birthday = _usable(guide, 'situation.age65')
    if basis == 'age65' and isinstance(birthday, dict):
        year, month = birthday.get('year'), birthday.get('month')
        if type(year) is int and 1900 <= year <= 2099 and type(month) is int and 1 <= month <= 12:
            # The first-of-month exception can put a January 1 birthday into
            # the previous year. A January 2020 month alone cannot decide C/F.
            if (year, month) == (2020, 1) and birthday.get('first_day') is True:
                return '2019-12'
            if (year, month) != (2020, 1) or birthday.get('first_day') is False:
                return f'{year:04d}-{month:02d}'
    return None


def medigap_letter_eligibility(letter, first_eligible):
    if letter not in CF_LETTERS:
        return 'met', ''
    note = 'Only for people eligible for Medicare before January 1, 2020'
    if not isinstance(first_eligible, str) or not re.fullmatch(r'(?:19|20)\d\d-(?:0[1-9]|1[0-2])', first_eligible):
        return 'unknown', note + '. Your first eligibility date is still open.'
    return ('met', 'First Medicare eligibility was before 2020') if first_eligible < '2020-01' else ('not_met', note)


def evaluate_medigap(inp, result, *, doctors=()):
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
            state, note = medigap_letter_eligibility(letter, inp['medigap'].get('first_eligible'))
            checks.append(_check('eligibility', state, note, 'eligibility'))
            checks[-1]['label'] = 'Who can buy it'
        for pref in prefs:
            if pref == 'doctors':
                select = plan.get('select_observed')
                state, note = (doctor_fit(doctors, original=True) if select is False else
                               ('unknown', 'Medicare SELECT network needs checking' if select is True else
                                'Medicare SELECT status is unspecified; doctor fit is unresolved'))
                checks.append(_check(pref, state, note, 'preference'))
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
    no_pick = ('Doctor fit is still unresolved for these rates.'
               if 'doctors' in priorities and not any(
                   check['id'] == 'doctors' and check['state'] == 'met'
                   for row in rows for check in row['checks']) else None)
    out = _assemble('medigap', rows, priorities, no_pick=no_pick,
                    sort_note='Ordered by lowest listed monthly premium.', notes=notes)
    out['minimum_monthly_cents'] = _minimum_cents(result['plans'], out, 'monthly_cents')
    return out


# ---------------------------------------------------------------- Part D

def _field_cents(plan, key):
    field = (plan.get('fields') or {}).get(key) or {}
    if field.get('state') != 'published' or field.get('value_encoding') != 'integer_cents':
        return None
    return _money(field.get('value'))


DRUG_COST_ORDER = ('Within each fit group, ordered by estimated plan premiums plus drug spending for your selected refill dates. '
                   'Uses retail averages, not exact-store prices. Unresolved estimates remain visible and unranked; medical costs are excluded.')


def drug_cost_key(row):
    if row.get('state') != 'offline_average_candidate': return None
    return _money(row.get('plan_premium_plus_drugs_cents'))


def drug_comparison_checks(row):
    status = row.get('pharmacy', {}).get('state')
    pharmacy = _check('pharmacy', 'met' if status in ('preferred', 'standard') else 'unknown',
        'Dated listing: ' + status if status in ('preferred', 'standard') else 'Pharmacy participation is unresolved.', 'observation')
    pharmacy['label'] = 'Your pharmacy'
    cost = _check('drug_cost', 'met' if drug_cost_key(row) is not None else 'unknown',
        'Retail-average estimate for the selected refills; excludes medical costs.' if drug_cost_key(row) is not None
        else 'A comparable drug-cost estimate is still unresolved.', 'observation')
    cost['label'] = 'Premiums and drug spending'
    return [pharmacy, cost]


def evaluate_part_d(inp, result, *, medicines=None, drug_costs=None):
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
            checks.append(_check('medicines', *medicine_fit((medicines or {}).get(plan['id'], ())), 'preference'))
        if 'total_cost' in prefs:
            checks.append(_check('total_cost', 'unknown', 'Needs your medicines and pharmacy', 'preference'))
        premium, deductible = _field_cents(plan, 'total_premium'), _field_cents(plan, 'annual_deductible')
        key = (deductible, premium) if predictable else (premium, deductible)
        if drug_costs is not None:
            checks.extend(drug_comparison_checks(drug_costs.get(plan['id'], {})))
            key = (drug_cost_key(drug_costs.get(plan['id'], {})),)
        rows.append({'id': plan['id'], 'checks': checks, 'key': key})
    no_pick = None if inp.get('medicines') == 'no' else DRUG_EVIDENCE_NO_PICK if medicines else DRUG_NO_PICK
    sort_note = ('Ordered by lowest yearly drug deductible, then premium, because you want predictable costs.'
                 if predictable else 'Ordered by lowest monthly premium, then yearly drug deductible.')
    out = _assemble('part_d', rows, priorities, no_pick=no_pick, sort_note=sort_note)
    if drug_costs is not None: out['sort_note'] = DRUG_COST_ORDER
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

def evaluate_path(inp, ma, medigap, part_d, *, doctors=()):
    if not inp['scope'].get('zipcode'):
        return _unavailable('path', 'The coverage-path comparison needs your ZIP first.')
    if 'employer' in inp['current_coverage']:
        out = _unavailable('path', 'You reported coverage through a current job. When to sign up comes '
                                   'before choosing a path, so Daylight does not suggest one yet.')
        out['state'] = 'held'
        return out
    held = [name for key, name in (('advantage', 'a Medicare Advantage plan'), ('medigap', 'a Medigap policy'))
            if key in inp['current_coverage']]
    if held:
        # Owner, November 13, 2026: being in a plan today holds the suggestion, as current job coverage
        # does (profile PP02, an HMO member, saw Original Medicare tagged "Suggested path").
        out = _unavailable('path', 'You have %s now. Keeping it and changing it are both open, so Daylight '
                                   'does not suggest a path yet.' % held[0])
        out['state'] = 'held'
        return out
    prefs, priorities = preferences(inp)
    original, advantage = [], []
    for pref in prefs:
        if pref == 'doctors':
            original.append(_check(pref, *doctor_fit(doctors, original=True), 'preference'))
            advantage.append(path_check(pref, ma))
        elif pref == 'medicines':
            original.append(path_check(pref, part_d))
            advantage.append(path_check(pref, ma))
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

def path_check(pref, tab):
    support = [check for plan in tab.get('plans', {}).values() if plan['group'] != 'excluded'
               for check in plan['checks'] if check['id'] == pref and check['state'] == 'met']
    return (_check(pref, 'met', support[0]['note'], 'preference') if support else
            _check(pref, 'unknown', 'Plan-by-plan evidence is incomplete.', 'preference'))


def evaluate(inp, *, ma_plans, medigap_result, part_d_result, medicines=None, networks=None, doctors=(), drug_costs=None):
    inp = validate_inputs(inp)
    ma = evaluate_ma(inp, ma_plans, medicines=medicines, doctors=networks,
                     drug_costs=drug_costs if drug_costs is not None and any(not k.startswith('2026:S') for k in drug_costs) else None)
    medigap = evaluate_medigap(inp, medigap_result, doctors=doctors)
    part_d = evaluate_part_d(inp, part_d_result, medicines=medicines,
                            drug_costs=drug_costs if drug_costs is not None and any(k.startswith('2026:S') for k in drug_costs) else None)
    path = evaluate_path(inp, ma, medigap, part_d, doctors=doctors)
    for tab in (ma, medigap, part_d, path):
        tab['preferences'] = checked_preferences(inp, tab.get('plans', {}))
    return {'method': METHOD, 'evaluation_only': True, 'inputs_digest': digest(inp),
            'preferences': path['preferences'],
            'path': path, 'advantage': ma, 'medigap': medigap, 'part_d': part_d,
            'notice': ('Evaluation mode: Daylight’s tiered sorting is on for fictional testing only. '
                       'It is not shown to pilot participants.')}
