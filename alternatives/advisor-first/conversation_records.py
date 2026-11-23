"""D183: the profile and education records drive the :8895 conversation.

Owner direction, November 17, 2026 (Brain: Inbox/Profile and education records
2026-11-17; repo: docs/product/PROFILE_AND_EDUCATION_RECORDS.md). Two records
fill as the conversation goes: the profile (what Daylight has learned) and the
education record (what Daylight has explained). Code keeps both, computes
readiness and dates; the interpreter proposes the next profile target; the
composer answers, teaches what has not been shown and ends on a lead.

On only where ``enable`` is called (the :8895 demo and its fixtures), and off
with DAYLIGHT_RECORDS=0. No new fact store: the profile is a projection of the
existing guide/readiness reports and question-progress receipts; the education
ledger lives in the planner's visit-only RAM. No model calls, no network.
"""
import calendar
import copy
import hashlib
import os
import re
from collections import OrderedDict
from datetime import date

from adaptive_flow import Q, metadata
import medigap_profile

VERSION = 'records-v1'
EDUCATION_VERSION = 'education-v2'
TODAY = None  # tests pin the date; production uses the local day


def _today():
    return TODAY or date.today()


def switch_on():
    return os.environ.get('DAYLIGHT_RECORDS', '1').strip().lower() not in {'0', 'off', 'false', 'no'}


def enable(flow):
    flow.records_v1 = True


def enabled(flow):
    return bool(getattr(flow, 'records_v1', False))


# D188 (November 18, 2026): pending questions, passes, single-field targets and
# offers.
# Its own switch under the records switch: DAYLIGHT_PENDING=0 turns it off on
# :8895 alone and restores the D183 behavior exactly.
def pending_switch_on():
    return os.environ.get('DAYLIGHT_PENDING', '1').strip().lower() not in {'0', 'off', 'false', 'no'}


def enable_pending(flow):
    flow.records_pending = True


def pending_on(flow):
    return enabled(flow) and bool(getattr(flow, 'records_pending', False))


# D190 (November 18, 2026): five conversation fixes from visit a912962310.
# DAYLIGHT_CONVERSATION_FIXES=0 turns them off on :8895 alone.
def fixes_switch_on():
    return os.environ.get('DAYLIGHT_CONVERSATION_FIXES', '1').strip().lower() not in {'0', 'off', 'false', 'no'}


def enable_fixes(flow):
    flow.records_fixes = True


def fixes_on(flow):
    return enabled(flow) and bool(getattr(flow, 'records_fixes', False))


# ---------------------------------------------------------------------------
# The profile record: every field, its group, level and what uses it.
# Data, not flow logic. Levels: core, when_relevant, optional, system.
# "used_by" names code that reads the answer today (spec, "The profile record").
# ---------------------------------------------------------------------------

def _f(group, label, level, *used_by):
    return {'group': group, 'label': label, 'level': level, 'used_by': list(used_by)}


PROFILE_FIELDS = OrderedDict([
    ('RC01', _f('who', 'Who the coverage is for', 'core', 'every personal fact', 'plan readiness')),
    ('T01', _f('who', 'What they want help with', 'core', 'plan readiness', 'task')),
    ('T02', _f('who', 'How familiar they are with Medicare', 'education', 'education record (learner signal)')),
    ('T03', _f('where', 'Home ZIP', 'core', 'plan views', 'recommendation')),
    ('RC02', _f('where', 'County and permanent home', 'when_relevant', 'plan views when a ZIP spans counties')),
    ('RC03', _f('where', 'Coverage year', 'optional', 'plan readiness (defaults to 2026)')),
    ('S_AGE65', _f('age', 'Birth month and year (the age anchor; the 65th birthday is derived)', 'when_relevant', 'timing card', 'rules', 'status line')),
    ('MG_AGE', _f('age', 'Age (Medigap pricing)', 'when_relevant', 'Medigap prices', 'recommendation', 'age anchor')),
    ('RC06', _f('age', 'How they qualify for Medicare', 'when_relevant', 'rules', 'journey', 'Medigap')),
    ('RC04', _f('medicare', 'Parts A and B now', 'core', 'status line', 'timing', 'rules', 'plan readiness')),
    ('RC05', _f('medicare', 'Part B start month', 'when_relevant', 'Medigap window rule')),
    ('RC07', _f('medicare', 'Original Medicare or Medicare Advantage now', 'when_relevant', 'rules')),
    ('RC16', _f('medicare', 'First Medicare Advantage plan history', 'when_relevant', 'trial-right card', 'rules')),
    ('RC17', _f('medicare', 'Replacing a Medigap policy', 'when_relevant')),
    ('RC15', _f('medicare', 'Event behind a Medigap purchase', 'when_relevant')),
    ('T05', _f('other_coverage', 'Current coverage types', 'core', 'nearly everything', 'recommendation')),
    ('RC09', _f('other_coverage', 'Whose job the coverage is through', 'when_relevant', 'rules', 'journey', 'timing card')),
    ('RC10', _f('other_coverage', 'Employer has 20 or more employees', 'when_relevant', 'rules', 'timing card')),
    ('RC11', _f('other_coverage', 'Job end and coverage end', 'when_relevant', 'timing card', 'rules', 'phone guide')),
    ('RC12', _f('other_coverage', 'Drug coverage counts as creditable', 'when_relevant', 'rules', 'timing card')),
    ('RC13', _f('other_coverage', 'Whether a change affects anyone else', 'optional')),
    ('RC14', _f('other_coverage', 'HSA contributions', 'when_relevant', 'rules', 'timing card')),
    ('RC26', _f('other_coverage', 'Military or VA coverage', 'when_relevant', 'rules')),
    ('RC08', _f('other_coverage', 'A coverage change and its date', 'when_relevant', 'rules')),
    ('S_RETIREMENT', _f('other_coverage', 'Retiring, retired or still working', 'when_relevant', 'rules')),
    ('RC27', _f('other_coverage', 'An interruption needing help now', 'system')),
    ('RC18', _f('costs', 'Help with costs now', 'when_relevant', 'recommendation (Medicaid)', 'rules', 'plan views')),
    ('T09', _f('costs', 'Monthly payments vs. costs when using care', 'core', 'recommendation', 'plan readiness')),
    ('RC25', _f('costs', 'Monthly budget', 'optional', 'rules', 'plan filters')),
    ('T06', _f('care', 'Doctors and hospitals to keep', 'core', 'plan readiness', 'recommendation', 'doctor checks')),
    ('RC21', _f('care', "Each doctor's practice and town", 'checks', 'doctor checks')),
    ('T07', _f('care', 'Medicines', 'core', 'plan readiness', 'recommendation', 'drug checks')),
    ('RC22', _f('care', "Each medicine's strength, form, brand", 'checks', 'drug checks')),
    ('RC23', _f('care', 'Fill amount, supply, pharmacy, mail order', 'checks', 'drug costs')),
    ('RC24', _f('care', 'Given at a clinic or filled at a pharmacy', 'checks')),
    ('T08', _f('care', 'Routine care away from home', 'core', 'recommendation', 'plan readiness')),
    ('RC20', _f('care', 'Where routine care away from home happens', 'when_relevant', 'recommendation')),
    ('MG_SEX', _f('care', 'Medigap price detail: sex', 'when_relevant', 'Medigap prices', 'recommendation')),
    ('MG_TOBACCO', _f('care', 'Medigap price detail: tobacco', 'when_relevant', 'Medigap prices', 'recommendation')),
    ('RC19', _f('care', 'Special Needs Plan qualification', 'when_relevant')),
    ('T10', _f('preferences', 'What matters most', 'core', 'recommendation', 'plan readiness', 'closing')),
    ('T04', _f('preferences', 'When they want Medicare to start', 'when_relevant', 'timing')),
    ('RC28', _f('preferences', 'Conflicting reports', 'system', 'correction step')),
])
# Fields the profile holds that are not questions (recorded from choices or controls).
RECORDED_FIELDS = OrderedDict([
    ('coverage.birth', _f('age', 'Birth month and year (age anchor)', 'core', 'Medigap age', 'age anchor')),
    ('coverage.reported', _f('medicare', 'What they already have, by name', 'core', 'plans steps')),
    ('intent.coveragePath', _f('preferences', 'Coverage path: chosen, leaning or undecided', 'core', 'plans', 'closing')),
    ('intent.components', _f('preferences', 'Parts of the path decided', 'system', 'plans dashboard')),
    ('intent.selectedPlan', _f('preferences', 'The plan they chose', 'system', 'Before you enroll')),
])
# Asked by the doctor and medicine checks, not offered as general intake.
CHECK_OWNED = frozenset({'RC21', 'RC22', 'RC23', 'RC24'})
NEVER_ASK = frozenset({'T02', 'RC27', 'RC28'}) | CHECK_OWNED
# D202: question importance is catalog data, not a prescribed interview order.
QUESTION_TIERS = {identifier: 1 if meta['level'] == 'core' else 2
                  for identifier, meta in PROFILE_FIELDS.items() if identifier not in NEVER_ASK}
SELECTED_PLAN_FIELD = 'intent.selectedPlan'
# Owner review (D183): the age anchor's question. The 65th birthday is derived.
BIRTH_QUESTION = 'What month and year were you born?'
REPORTED_FIELD = 'coverage.reported'
REASONS = ('goal', 'readiness', 'answer_follow_up', 'person_raised', 'clarify')


def target_ids():
    """Every meaning the interpreter may name as next_target."""
    return [identifier for identifier in PROFILE_FIELDS if identifier not in NEVER_ASK]


def _question(flow, g, r, identifier):
    if identifier in medigap_profile.FIELDS:
        return medigap_profile.question(identifier, flow.value(g, 'subject.role'))
    if identifier == 'T06' and 'doctors' in (flow.value(g, 'needs.priorities') or []):
        return flow.provider_detail_question()
    if identifier == 'RC02' and flow.value(g, 'comparison.scope.zip'):
        # The home ZIP is known: only its county can still be open (a ZIP that spans
        # counties). Ask that, not "where is your permanent home" again.
        try:
            q = flow.question('RC02', ['county'])
        except Exception:
            return None
        q['question'] = 'Which county and state is that home ZIP in?'
        choices = (getattr(flow, 'reference', None) or {}).get('zips', {}).get(flow.value(g, 'comparison.scope.zip'), [])
        if len(choices) > 1 and q.get('fields'):
            q['fields'][0].update(type='select', options=[[x[0], x[1] + ', ' + x[2]] for x in choices])
        return q
    if pending_on(flow):
        narrowed = _one_field(flow, g, r, identifier)      # D188: one target, one field
        if narrowed:
            return narrowed
    try:
        q = flow.question(identifier)
    except Exception:  # an unknown or unavailable meaning is simply not offered
        return None
    return flow.contextual_question(g, r, q) if q else None


def _parked(identifier, ledger, flow=None):
    import question_progress
    if flow is not None and pending_on(flow):
        # D188: parked on passes (or the delivery cap), never on times shown alone.
        return any(key.split('|')[0] == identifier and at_limit(receipt) for key, receipt in (ledger or {}).items())
    return any(key.split('|')[0] == identifier and (receipt.get('parked') or receipt.get('shown', 0) >= question_progress.LIMIT)
               for key, receipt in (ledger or {}).items())


def field_state(flow, owner, g, r, identifier, ledger=None):
    """reported / open / pending / unknown / deferred / parked / conflicting, from real reports only."""
    import question_progress
    pending = flow.pending_for(owner) if owner is not None else None
    if pending and any(item.get('id') == identifier for item in [pending['update'], *pending.get('remaining', [])]):
        return 'conflicting'
    if identifier == 'S_RETIREMENT':
        value = flow.value(g, 'situation.retirement')
        return 'reported' if value else 'open'
    if identifier == 'RC02' and flow.value(g, 'comparison.scope.county'):
        return 'reported'                         # derived from a home ZIP in one county
    q = _question(flow, g, r, identifier)
    if not q:
        return 'open'
    projected = question_progress.project(flow, g, r, q)
    states = set(projected['fields'].values())
    if not projected['open_fields']:
        return 'reported' if 'reported' in states and states <= {'reported'} else (
            'deferred' if 'deferred' in states else 'unknown' if 'unknown' in states else 'reported')
    if _parked(identifier, ledger, flow):
        return 'parked'
    if pending_on(flow) and (pending_receipt(ledger)[1] or {}).get('pending', {}).get('id') == identifier:
        return 'pending'                          # D188: asked and still waiting for an answer
    return 'open'


_PURPOSES = None


def purposes():
    """Each meaning's purpose, from the sealed contract's decision_affected text (read only)."""
    global _PURPOSES
    if _PURPOSES is None:
        import json
        from comparison_profile import CONTRACT_PATH
        try:
            contract = json.loads(CONTRACT_PATH.read_text())
            crosswalk = contract.get('field_review_crosswalk') or {}
            _PURPOSES = {}
            for item in contract.get('questions') or []:
                for field in item.get('fields') or []:
                    row = crosswalk.get(field) or {}
                    if row.get('decision_affected'):
                        _PURPOSES[item['id']] = row['decision_affected']
                        break
        except (OSError, ValueError):
            _PURPOSES = {}
    return _PURPOSES


def value_summary(flow, g, r, identifier):
    """A short, code-made summary of what is on record (never sent to a model)."""
    if identifier in PROFILE_FIELDS:
        if identifier in medigap_profile.FIELDS:
            field = (g.get('fields') or {}).get(medigap_profile.FIELDS[identifier]) or {}
            return field.get('value') if field.get('status') == 'reported' else None
        if identifier == 'S_AGE65':
            return flow.value(g, 'situation.age65')
        if identifier == 'S_RETIREMENT':
            return flow.value(g, 'situation.retirement')
        try:
            report = flow.report(r, identifier)
        except Exception:
            report = {}
        return {k: v for k, v in (report or {}).items() if k in ('choice', 'jobEnd', 'coverageEnd', 'text')} or None
    return flow.value(g, identifier)


def profile_view(flow, owner, g, r, ledger=None):
    """The full profile record: id, group, label, state, value, level, purpose, used_by."""
    rows = []
    known = purposes()
    for identifier, meta in PROFILE_FIELDS.items():
        rows.append({'id': identifier, **meta, 'state': field_state(flow, owner, g, r, identifier, ledger),
                     'value': value_summary(flow, g, r, identifier), 'purpose': known.get(identifier) or meta['label']})
    for path, meta in RECORDED_FIELDS.items():
        value = flow.value(g, path)
        rows.append({'id': path, **meta, 'state': 'reported' if value not in (None, '', [], {}) else 'open',
                     'value': value, 'purpose': meta['label']})
    return {'version': VERSION, 'fields': rows}


def compact_profile(view):
    """States by ID for the models; meanings and purposes are in question_table."""
    out = OrderedDict((state, []) for state in ('reported', 'open', 'unknown', 'deferred', 'parked', 'conflicting'))
    # D188 adds 'pending' (only present when a question is waiting; setdefault below).
    for row in view['fields']:
        out.setdefault(row['state'], []).append(row['id'])
    levels = {'core': [row['id'] for row in view['fields'] if row['level'] == 'core'],
              'when_relevant': [row['id'] for row in view['fields'] if row['level'] == 'when_relevant']}
    return {'version': VERSION, **out, 'levels': levels,
            'question_tiers': {str(tier): [i for i, value in QUESTION_TIERS.items() if value == tier]
                               for tier in (1, 2)},
            'tier_1_open': [i for i in out['open'] if QUESTION_TIERS.get(i) == 1],
            'never_ask': sorted(NEVER_ASK), 'familiarity_is_a_learner_signal': True}


# ---------------------------------------------------------------------------
# Age anchor: one source for every age reader.
# ---------------------------------------------------------------------------

def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def age_view(flow, g, today=None):
    """Birth month/year when given, otherwise the reported age (Medigap pricing age).

    Never invents a birth month. The 65th-birthday month exists only from a
    birth month or a reported 65th birthday."""
    today = today or _today()
    view = {'age': None, 'age_65_or_older': None, 'turns_65': None, 'medigap_age': None,
            'band': None, 'source': None}
    birth = flow.value(g, 'coverage.birth')
    age65 = flow.value(g, 'situation.age65')
    reported_age = None
    field = (g.get('fields') or {}).get(medigap_profile.FIELDS['MG_AGE']) or {}
    if field.get('status') == 'reported':
        reported_age = _int(field.get('value'))
    if isinstance(birth, str) and re.fullmatch(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])', birth):
        year, month = int(birth[:4]), int(birth[5:7])
        view.update(age=today.year - year - (1 if today.month < month else 0), source='birth',
                    turns_65='%04d-%02d' % (year + 65, month))
    elif isinstance(age65, dict) and age65.get('year') and age65.get('month'):
        view.update(turns_65='%04d-%02d' % (int(age65['year']), int(age65['month'])), source='age65')
    if view['age'] is None and reported_age is not None:
        view.update(age=reported_age, source=view['source'] or 'reported_age')
    if view['turns_65']:
        y, m = int(view['turns_65'][:4]), int(view['turns_65'][5:7])
        view['age_65_or_older'] = (y, m) <= (today.year, today.month)
    elif view['age'] is not None:
        view['age_65_or_older'] = view['age'] >= 65
    if view['age'] is not None:
        view['medigap_age'] = view['age']
        view['band'] = 'under_65' if view['age'] < 65 else '65_74' if view['age'] < 75 else '75_plus'
    return view


# ---------------------------------------------------------------------------
# Dates for job coverage (C46). Month arithmetic from accepted facts only.
# ---------------------------------------------------------------------------

MONTH_NAMES = [calendar.month_name[i] for i in range(13)]


def _month_add(year, month, n):
    total = year * 12 + (month - 1) + n
    return total // 12, total % 12 + 1


def _label(year, month):
    return '%s %d' % (MONTH_NAMES[month], year)


def end_date(value):
    """A reported end as a date: the stated day, or the last day of a stated month."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if re.fullmatch(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])', value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    if re.fullmatch(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])', value):
        y, m = int(value[:4]), int(value[5:7])
        return date(y, m, calendar.monthrange(y, m)[1])
    return None


WORK_JOBS = ('my_job', 'spouse_job')


def work_window(flow, g, r, today=None):
    """Part B, plan and Medigap windows when current-work coverage is ending.

    Inputs are the person's own reports. Returns None unless every input the
    accepted facts need is present: whose job, an end date with a year, age 65
    or older, and Parts A/B not both in place."""
    today = today or _today()
    job = flow.report(r, 'RC09').get('choice')
    if job not in WORK_JOBS:
        return None
    rc11 = flow.report(r, 'RC11')
    job_end, coverage_end = end_date(rc11.get('jobEnd')), end_date(rc11.get('coverageEnd'))
    ends = [d for d in (job_end, coverage_end) if d]
    if not ends:
        return None
    ages = age_view(flow, g, today)
    if ages['age_65_or_older'] is not True:
        return None
    parts = flow.report(r, 'RC04').get('choice')
    if parts in ('both', 'b_only', 'pending'):
        return None
    first = min(ends)
    start = _month_add(first.year, first.month, 1)
    last = _month_add(first.year, first.month, 8)
    plan_end_month = _month_add((coverage_end or first).year, (coverage_end or first).month, 2)
    window_open = (today.year, today.month) <= last
    signup_now = _month_add(today.year, today.month, 1) if window_open else None
    medigap = None
    if signup_now:
        medigap = (signup_now, _month_add(signup_now[0], signup_now[1], 5))
    size = flow.report(r, 'RC10').get('choice')
    hsa = flow.report(r, 'RC14').get('choice')
    drug = flow.report(r, 'RC12').get('choice')
    facts = ['pk_work_sep', 'pk_work_sep_start', 'pk_plan_coverage_loss_window']
    if medigap:
        facts.append('pk_medigap_window')
    if size in ('yes', 'no'):
        facts.append('pk_payer_order')
    if hsa == 'yes':
        facts.append('pk_hsa')
    return {'basis': 'reported', 'job': job, 'first_end': first.isoformat(),
            'still_covered': bool(coverage_end and today <= coverage_end),
            # pk_work_sep_start: a delayed start can be asked for while covered or in
            # the first full month after employer coverage ends.
            'delay_allowed': bool((coverage_end or first) and (today.year, today.month) <= _month_add(
                (coverage_end or first).year, (coverage_end or first).month, 1)),
            'part_b_window': ['%04d-%02d' % start, '%04d-%02d' % last],
            'part_b_window_open': window_open,
            'part_b_start_if_signed_now': ('%04d-%02d-01' % signup_now) if signup_now else None,
            'plan_window_end': '%04d-%02d' % plan_end_month,
            'medigap_window_if_signed_now': ['%04d-%02d' % medigap[0], '%04d-%02d' % medigap[1]] if medigap else None,
            'employer_20_or_more': {'yes': True, 'no': False}.get(size),
            'hsa': hsa, 'creditable_drug_coverage': drug, 'facts': facts}


def work_card(window, today=None):
    """Code-built card; dates never appear in model prose. Wording: owner review."""
    if not window:
        return None
    today = today or _today()
    y1, m1 = int(window['part_b_window'][0][:4]), int(window['part_b_window'][0][5:7])
    y2, m2 = int(window['part_b_window'][1][:4]), int(window['part_b_window'][1][5:7])
    rows = [{'label': 'Part B sign-up window',
             'value': '%s through %s' % (_label(y1, m1), _label(y2, m2)),
             'note': 'The eight months after your job or its coverage ends, whichever comes first. You can also sign up while you are still covered.'}]
    if window['part_b_start_if_signed_now']:
        s = date.fromisoformat(window['part_b_start_if_signed_now'])
        note = 'Coverage generally starts the month after you sign up.'
        if window.get('delay_allowed'):
            note += (' While you are still covered, or in the first full month after that coverage ends, '
                     'you can ask for a Part B start up to three months later.')
        rows.append({'label': 'If you sign up in %s' % _label(today.year, today.month),
                     'value': 'Part B generally starts %s %d, %d' % (MONTH_NAMES[s.month], s.day, s.year),
                     'note': note})
    py, pm = int(window['plan_window_end'][:4]), int(window['plan_window_end'][5:7])
    rows.append({'label': 'Joining a drug or Medicare Advantage plan',
                 'value': 'Through %s' % _label(py, pm),
                 'note': 'Two full months after the month your coverage ends. Going 63 days or more without creditable drug coverage can mean a Part D penalty.'})
    if window['medigap_window_if_signed_now']:
        a, b = window['medigap_window_if_signed_now']
        rows.append({'label': 'Medigap window',
                     'value': '%s through %s' % (_label(int(a[:4]), int(a[5:7])), _label(int(b[:4]), int(b[5:7]))),
                     'note': 'Six months from the first month you are 65 or older and have Part B; this assumes Part B starts %s.' % _label(int(a[:4]), int(a[5:7]))})
    if window['employer_20_or_more'] is True:
        rows.append({'label': 'Your employer', 'value': '20 or more employees',
                     'note': 'With 20 or more employees, the group plan generally pays first while you work.'})
    elif window['employer_20_or_more'] is False:
        # The contrast leads: with a small employer, Medicare generally pays first.
        rows.insert(0, {'label': 'Your employer', 'value': 'Fewer than 20 employees',
                        'note': 'With fewer than 20 employees, Medicare generally pays first.'})
    if window['hsa'] == 'yes':
        rows.append({'label': 'Your HSA', 'value': 'Contributions need timing',
                     'note': 'Premium-free Part A can start up to six months back when you sign up later, so HSA contributions are usually stopped ahead of time.'})
    return {'kind': 'enrollment_timing', 'title': 'Your sign-up timing, from the dates you told me',
            'rows': rows, 'footnote': 'Estimates from the dates you told me and Medicare’s published rules. Social Security sets the actual start date.',
            'facts': list(window['facts']), 'records': VERSION}


# ---------------------------------------------------------------------------
# Readiness: the outcomes the profile is filled toward. Existing code only.
# ---------------------------------------------------------------------------

def readiness(flow, owner, g, r, s=None, today=None):
    import plan_review
    import part_d_profile
    import enrollment_flow
    s = s or {}
    coverage = set(flow.value(g, 'coverage.current') or [])
    parts = flow.report(r, 'RC04').get('choice')
    part_reports = [(flow.value(g, field) or {}).get('status') for field in enrollment_flow.PART_FIELDS.values()]
    both_active = bool(part_reports) and all(status == 'active' for status in part_reports)
    on_medicare = parts == 'both' or bool(coverage & {'original', 'advantage', 'medigap'}) or both_active
    job = flow.report(r, 'RC09').get('choice')
    working = 'employer' in coverage or job in ('my_job', 'spouse_job', 'family_job')
    ages = age_view(flow, g, today)
    outcomes = OrderedDict()
    role = flow.value(g, 'subject.role')
    research = flow.report(r, 'RC01').get('choice') == 'research'
    enrollment = []
    if not role and not research:
        enrollment.append('RC01')
    if not on_medicare and not research:
        if not parts:
            enrollment.append('RC04')
        if working or 'retiree' in coverage or 'cobra' in coverage:
            if not job:
                enrollment.append('RC09')
            if job in WORK_JOBS or 'employer' in coverage:
                enrollment += ['RC11', 'RC10', 'RC12']
                if ages['age_65_or_older'] is not False:
                    enrollment.append('RC14')
            elif job in ('retiree', 'cobra') or coverage & {'retiree', 'cobra'}:
                enrollment += ['RC11', 'RC12']
        if ages['turns_65'] is None and ages['age_65_or_older'] is not True:
            enrollment.append('S_AGE65')          # the age anchor, when timing needs a birth month
    window = work_window(flow, g, r, today)
    outcomes['enrollment_step'] = {'needs': list(dict.fromkeys(enrollment)),
                                   'applies': not on_medicare and not research,
                                   'timing_card_ready': bool(window)}
    plans = plan_review.readiness(g, r, pending=flow.pending_for(owner) if owner is not None else None)
    plan_needs = [item['question_id'] for item in plans['missing'] if item['question_id'] not in ('T01', 'RC03')]
    outcomes['plan_comparison'] = {'needs': list(dict.fromkeys(plan_needs)), 'can_review': plans['canReview']}
    investigate = set(s.get('investigate') or []) | set(s.get('task_investigate') or [])
    path = flow.value(g, enrollment_flow.PATH_FIELD)
    medigap_view = medigap_profile.for_flow(flow, g, r)
    medigap_needs = [i for i in medigap_view.get('missing', []) if i not in medigap_view.get('held', [])]
    outcomes['medigap_prices'] = {'needs': medigap_needs, 'status': medigap_view.get('status'),
                                  'in_play': 'medigap' in investigate or path in ('original', 'original_medigap')}
    pd_view = part_d_profile.profile(g, r)
    outcomes['part_d_plans'] = {'needs': [i for i in pd_view.get('missing', []) if i not in pd_view.get('held', [])],
                                'status': pd_view.get('status'), 'in_play': 'part_d' in investigate}
    outcomes['recommendation'] = {'needs': list(dict.fromkeys(plan_needs + (medigap_needs if outcomes['medigap_prices']['in_play'] else [])))}
    outcomes['before_you_enroll'] = {'chosen_plan': bool(flow.value(g, SELECTED_PLAN_FIELD)),
                                     'needs': [] if flow.value(g, SELECTED_PLAN_FIELD) else ['chosen plan (Plans page)']}
    goal = flow.value(g, 'intent.goal')
    task = s.get('active_task') or ''
    order = []
    if outcomes['enrollment_step']['applies'] and enrollment:
        order.append('enrollment_step')
    if goal in ('compare', 'review') or task in ('compare', 'review', 'advantage', 'costs'):
        order.append('plan_comparison')
    if outcomes['medigap_prices']['in_play']:
        order.append('medigap_prices')
    if outcomes['part_d_plans']['in_play']:
        order.append('part_d_plans')
    if 'plan_comparison' not in order:
        order.append('plan_comparison')
    return {'version': VERSION, 'order': order, 'outcomes': outcomes, 'age': ages,
            'work_window': window}


def compact_readiness(bundle):
    return {'goal_order': bundle['order'],
            'selection_rule': (
                'Answer the current concern first; use known answers before more intake. '
                'Read profile_record and education_record together: use reported facts, unresolved needs, '
                'teaching depth and learner signals; delivered teaching never proves understanding. '
                'Prioritize a natural useful conversation, then consequential missing details, then teaching. '
                'Prefer open Tier 1 topics in profile_record.question_tiers: goal, current coverage/Medicare, '
                'location, doctors, medicines, priorities and care/cost preferences. The model chooses the '
                'most useful one, not catalog order. Tier 2 is conditional: ask when Tier 1 is addressed '
                'or the person specifically requests an answer/action that needs that detail. Broad interest '
                'in enrollment, timing or options does not by itself call for an employer-size, creditable-'
                'coverage or HSA interview. Even after Tier 1, ask only consequential details, not every field. '
                'Readiness needs are requirements for specific conclusions, not question order. Preserve '
                'all safety/source holds: qualify or withhold a dependent personal conclusion until checked. '
                'Respect reported/unknown/deferred/parked states; do not re-ask to complete a tier. '
                'Explain unfamiliar terms plainly; repeating why you ask does not resolve confusion.'),
            'switching_goal': (
                'When someone already has Medicare coverage and is considering a switch, first understand '
                'what they want to improve: ask naturally whether anything about their current coverage is '
                'not working for them, and what they want to keep. Reuse a reason already stated instead of '
                'asking again. They may be satisfied and simply comparing; do not assume dissatisfaction or '
                'that switching is best. Treat this as clarifying their goal before generic comparison intake '
                'or a handoff. Use existing concern/history and approved goal/priority reports where supported; '
                'a null question_target with next_move=clarify is available. No new required field or fixed branch.'),
            'enrollment_help': (
                'For someone not enrolled in Medicare, first establish whether they know how to sign up. '
                'This orientation comes before more profile intake unless they ask to focus elsewhere. '
                'Use their own words and prior conversation; if unclear, '
                'ask one short natural clarification about whether they know the enrollment steps or want '
                'help. This is understanding, not a new profile field: next_target.ids may be empty and '
                'composition may use null question_target with next_move=clarify. If help is wanted, use '
                'the supported enrollment guide in this visit. Do not infer understanding from teaching '
                'delivered, repeat a resolved question, force an application, or block requested exploration.'),
            'enrollment_scope': {
                'orientation': [i for i in bundle['outcomes']['enrollment_step']['needs']
                                if QUESTION_TIERS.get(i) == 1],
                'conditional_checks': {
                    'RC10': 'Employer size before personal payer-order or delayed-enrollment conclusions.',
                    'RC11': 'Coverage end before coordinating personal transition dates.',
                    'RC12': 'Creditable drug coverage before personal drug timing or penalty conclusions.',
                    'RC14': 'HSA contributions before personal Part A start/backdating advice.'},
                'rule': 'These checks protect specific conclusions, not explanations of enrollment steps or coverage paths.'},
            'outcomes': {name: {k: v for k, v in item.items() if k in ('needs', 'can_review', 'status', 'in_play',
                                                                        'applies', 'timing_card_ready', 'chosen_plan')}
                         for name, item in bundle['outcomes'].items()},
            'age_65_or_older': bundle['age']['age_65_or_older']}


# ---------------------------------------------------------------------------
# The profile drives the next question.
# ---------------------------------------------------------------------------

def _dispositions(r):
    held = dict(metadata(r).get('baselineDispositions', {}))
    for identifier, item in (r.get('dispositions') or {}).items():
        held[identifier] = item.get('state')
    return held


def candidates(flow, owner, g, r, s, checked):
    """Every open, unparked, askable field, ordered: the pending question (D188),
    the interpreter's target, then core topics, then conditional outcome needs."""
    import conversation_planner
    bundle = readiness(flow, owner, g, r, s)
    s['records_bundle'] = bundle
    held = _dispositions(r)
    skip = set(s.get('deferred') or [])
    role = flow.value(g, 'subject.role')
    pend = None
    if pending_on(flow):
        pend = standing_pending(flow, owner, g, r, s)
        if s.get('records_passed_now'):
            skip.add(s['records_passed_now'])     # not asked again in the reply that passed it
    pool = []
    if not role and flow.report(r, 'RC01').get('choice') != 'research' and 'RC01' not in held:
        pool.append('RC01')                      # the subject comes first
    if pend:
        pool.append(pend)                         # stays the target until answered, passed or parked
    if pending_on(flow) and s.get('records_offer_task'):
        pool += task_fields(flow, g, r, s['records_offer_task'], bundle)   # an offer just taken
    targets = [t for t in s.get('next_target') or [] if t in PROFILE_FIELDS and t not in NEVER_ASK]
    pool += targets
    raised = set(targets) if s.get('next_target_reason') in ('person_raised', 'answer_follow_up', 'clarify') else set()
    for name in bundle['order']:
        pool += bundle['outcomes'][name]['needs']
    pool += [i for i, meta in PROFILE_FIELDS.items() if meta['level'] == 'core']
    items = []
    for identifier in dict.fromkeys(pool):
        if (identifier in NEVER_ASK or identifier not in PROFILE_FIELDS
                or held.get(identifier) in ('deferred', 'explicit_unknown', 'unknown') or identifier in skip):
            continue
        if PROFILE_FIELDS[identifier]['level'] == 'optional' and identifier not in raised and identifier != pend:
            continue                              # optional: only when the person raised it
        if not role and identifier != 'RC01' and identifier not in ('T01',):
            continue
        q = _question(flow, g, r, identifier)
        if not q:
            continue
        items.append(dict(id=identifier, question=copy.deepcopy(q), topic='', priority=QUESTION_TIERS[identifier], tier=QUESTION_TIERS[identifier], required=False,
                          purpose=q.get('why') or PROFILE_FIELDS[identifier]['label']))
    # Reserve the bounded menu for pending/model-selected questions and core
    # topics before conditional details. Neither tier removes a model choice.
    pinned = set(targets) | ({pend} if pend else set())
    items.sort(key=lambda item: (item['id'] not in pinned, item['tier']))
    result = checked(items)[:12]          # the composer accepts at most 12 candidates
    ids = [item['id'] for item in result]
    s['records_open_count'] = len(ids)
    s['records_pending_return'] = pend if pend in ids else None
    if s['records_pending_return']:
        # D188: on a return the pending question is the only candidate, so the
        # reply cannot lead with a different one.
        result = [item for item in result if item['id'] == pend]
        s['records_target'], s['records_target_source'] = pend, 'pending'
        return result
    # Validated target: the interpreter's first open, unparked choice; otherwise
    # the first eligible core topic, then conditional needs if core is addressed.
    s['records_target'] = next((t for t in targets if t in ids), None) or (ids[0] if ids else None)
    s['records_target_source'] = ('interpreter' if s['records_target'] in targets else
                                  'readiness' if s['records_target'] else None)
    return result


def precedence(flow, owner, g, r):
    """A pending one-tap confirmation or an RC28 correction comes before any new target."""
    pending = flow.pending_for(owner) if owner is not None else None
    if pending:
        return 'confirmation'
    if flow.report(r, 'RC28').get('choice') not in (None, '', 'none', 'no'):
        return 'correction'
    return None


def validate_next_target(value):
    """Interpreter proposal: up to two askable IDs plus one reason code.
    Returns {'ids': [...], 'reason': code}, or {} when malformed."""
    if not isinstance(value, dict) or set(value) != {'ids', 'reason'}:
        return {}
    ids = value['ids']
    if (not isinstance(ids, list) or len(ids) > 2 or value['reason'] not in REASONS
            or any(not isinstance(i, str) or i not in PROFILE_FIELDS or i in NEVER_ASK for i in ids)):
        return {}
    return {'ids': list(dict.fromkeys(ids)), 'reason': value['reason']}


def next_target_schema(make):
    return make({'ids': {'type': 'array', 'maxItems': 2, 'items': {'type': 'string', 'enum': target_ids()}},
                 'reason': {'type': 'string', 'enum': list(REASONS)}})


# ---------------------------------------------------------------------------
# Education record v2: concepts with a core fact and detail facts.
# ---------------------------------------------------------------------------

CONCEPTS = OrderedDict([
    ('medicare_basics', ('What Medicare is', 'pk_parts', ['basics', 'pk_disability_eligibility', 'pk_esrd_eligibility', 'pk_ssa_disability_definition'])),
    ('part_a', ('Part A', 'pk_part_a_benefits', ['parta', 'pk_part_a_premium', 'pk_snf', 'pk_custodial'])),
    ('part_b', ('Part B', 'pk_part_b_benefits_premium', ['partb', 'parts'])),
    ('coverage_paths', ('The two coverage paths', 'pk_routes', ['routesintro', 'options', 'pk_costs', 'pk_travel', 'original_nationwide'])),
    ('original_medicare', ('Original Medicare', 'original', ['pk_access'])),
    ('medicare_advantage', ('Medicare Advantage', 'pk_part_c_premium', ['advantage', 'pk_ma_approval', 'pk_snp', 'ma_trial_right', 'cms_special_needs_plans'])),
    ('prescription_coverage', ('Where prescription coverage fits', 'pk_part_d_optional', ['drugbasics', 'drugs', 'pk_part_d_cap', 'pk_creditable', 'pk_formulary_tiers'])),
    ('medigap', ('Where Medigap fits', 'pk_medigap', ['medigap', 'pk_medigap_standard', 'pk_medigap_premium', 'pk_medigap_drug_exclusion', 'pk_fl_rating'])),
    ('medigap_switching', ('Medigap switching rights', 'pk_medigap_window', ['switching', 'pk_medigap_window_scope', 'pk_medigap_underwriting', 'medigap_window'])),
    ('provider_checks', ('Checking doctors and hospitals', 'checks', ['pk_ma_approval'])),
    ('medicine_checks', ('Checking medicines and pharmacies', 'pk_formulary', ['pk_pharmacies', 'pk_drug_rules', 'pk_transition', 'pk_formulary_exception', 'pk_tiering_exception', 'glp1_prior_authorization'])),
    ('cost_components', ('Monthly costs and costs when using care', 'costs', [])),
    ('medical_spending_limits', ('Medical spending limits', 'medical_limit', [])),
    ('routine_extra_benefits', ('Dental, vision and hearing', 'extras', [])),
    ('enrollment_timing', ('Sign-up timing and coverage start', 'pk_iep', ['dates', 'enrollment_intro', 'pk_start', 'pk_first_day_birthday', 'pk_gep', 'pk_enrollment_windows', 'pk_join', 'pk_initial_plan_window', 'pk_new_part_b_plan_window', 'initial_enrollment_window'])),
    ('current_coverage_timing', ('Working past 65 and other coverage', 'pk_work_sep', ['cobra_timing', 'pk_work_sep_start', 'pk_payer_order', 'pk_hsa', 'pk_cobra', 'pk_other_coverage', 'pk_plan_coverage_loss_window', 'pk_payer_retiree_cobra', 'pk_payer_disability', 'pk_payer_esrd', 'pk_payer_injury', 'working_coverage_sep', 'hsa_medicare', 'cobra_initial_window', 'cobra_pays_second', 'cms_current_coverage', 'partb_sep_coverage_ended', 'small_employer_pays_first'])),
    ('late_penalties', ('Late sign-up penalties', 'pk_penalties', ['pk_penalty_a', 'pk_penalty_b', 'pk_penalty_d', 'partd_penalty'])),
    ('help_paying_costs', ('Help paying costs', 'pk_extra_help', ['pk_extra_help_auto', 'pk_msp', 'pk_qmb', 'pk_medicaid_governance', 'pk_fl_help', 'pk_shine', 'extra_help'])),
    ('yearly_review', ('Reviewing coverage each year', 'pk_aep', ['pk_annual_changes', 'pk_ma_oep', 'pk_ma_oep_effective', 'pk_move', 'annual_enrollment', 'cms_plan_year_eoc'])),
    ('your_rights', ('Your rights', 'pk_appeals', ['pk_complaints', 'cms_complaints', 'cms_right_to_cancel'])),
    ('research_checks', ('What still needs checking', 'next', ['cms_outside_us'])),
])
NEW_CONCEPTS = ('late_penalties', 'help_paying_costs', 'yearly_review', 'your_rights')
FACT_CONCEPT = {}
for _concept, (_title, _core, _details) in CONCEPTS.items():
    FACT_CONCEPT.setdefault(_core, (_concept, 'core'))
    for _detail in _details:
        FACT_CONCEPT.setdefault(_detail, (_concept, 'detail'))
# The CMS pre-enrollment checklist topics (cms_checklist.TOPICS) by concept.
CHECKLIST_CONCEPTS = OrderedDict([
    ('plan_type_and_network_providers', 'provider_checks'), ('formulary_coverage', 'medicine_checks'),
    ('other_needed_benefits', 'routine_extra_benefits'), ('premiums_including_part_b', 'cost_components'),
    ('cost_sharing', 'cost_components'), ('out_of_network_rules', 'medicare_advantage'),
    ('coverage_outside_us', 'coverage_paths'), ('effect_on_current_coverage', 'current_coverage_timing'),
    ('plan_year_changes_and_eoc', 'yearly_review'), ('how_to_file_complaints', 'your_rights'),
    ('special_needs_plan_requirements', 'medicare_advantage'), ('right_to_cancel', 'your_rights'),
])
# Code cards teach too; their facts are recorded when shown.
CARD_FACTS = {'discussion_paths': ['pk_routes', 'routesintro']}
DEPTH = {'introduced': 1, 'explored': 2}


def unmapped(fact_ids):
    return sorted(i for i in fact_ids if i not in FACT_CONCEPT)


def _ledger(s):
    ledger = s.setdefault('records_education', {})
    ledger.setdefault('version', EDUCATION_VERSION)
    ledger.setdefault('facts', {})
    ledger.setdefault('concepts', {})
    ledger.setdefault('shown', [])
    return ledger


STOP = frozenset('''this that with from your have will they them their there what when where which about would could
should into than then also only just more most some such each other these those been being does were while after
before because until over under same like very much many make made need needs your you'll you're it's that's
medicare'''.split())


def tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or '').lower().replace('’', "'")) if len(w) > 3 and w not in STOP}


def _repeat(block, prior):
    words = tokens(block)
    if len(words) < 5:
        return False
    for other in prior:
        other = set(other)
        if other and len(words & other) / len(words) >= 0.6:
            return True
    return False


def concepts_of(fact_ids):
    return {FACT_CONCEPT[f][0] for f in fact_ids or () if f in FACT_CONCEPT}


def filter_blocks(s, reply, block_refs=None, requested=False, allowed_concepts=(), keep=()):
    """Say each fact once (V2), per block. A block whose cited facts were all
    delivered already is held back, unless the person asked, was confused or
    their circumstances changed for that concept. A block that cites nothing
    is held back only when it restates one block already shown (content-word
    overlap, never a vocabulary list). Returns (reply, held_count, held_facts)."""
    ledger = _ledger(s)
    blocks = [b for b in (reply or '').split('\n\n') if b.strip()]
    if requested or not blocks:
        return reply, 0, []
    refs = {' '.join(k.split()): list(v or []) for k, v in (block_refs or {}).items()}
    delivered = set(ledger['facts'])
    allowed = set(allowed_concepts or ())
    prior = list(ledger['shown'])
    kept, held_facts = [], []
    # Blocks already shown by checked-block release (:8895) are never taken back.
    released = {' '.join(b.split()) for b in keep or ()}
    for block in blocks:
        if ' '.join(block.split()) in released:
            kept.append(block)
            continue
        cited = refs.get(' '.join(block.split()))
        if cited:
            if set(cited) <= delivered and not (concepts_of(cited) & allowed):
                held_facts += cited
                continue
        elif cited is None or not cited:
            if _repeat(block, prior):
                continue
        kept.append(block)
    return '\n\n'.join(kept), len(blocks) - len(kept), sorted(set(held_facts))


def offer_allowed(s, concept, requested=False, allowed_concepts=()):
    """An offer to explain a concept already introduced is filtered unless asked."""
    if not concept or concept not in CONCEPTS or requested or concept in set(allowed_concepts or ()):
        return True
    return _ledger(s)['concepts'].get(concept) not in ('introduced', 'explored')


TASK_FOR_OUTCOME = {'plan_comparison': 'compare', 'medigap_prices': 'medigap', 'part_d_plans': 'drug_coverage',
                    'enrollment_step': 'timing', 'recommendation': 'compare', 'before_you_enroll': 'compare'}


def lead_task(s):
    """The work to offer when a turn has no question: the suggested or active
    task, else the first outcome the goal is filling toward."""
    task = s.get('suggested_task') or s.get('active_task')
    if task in OFFER_LABELS:
        return task
    for name in (s.get('records_bundle') or {}).get('order') or []:
        if TASK_FOR_OUTCOME.get(name) in OFFER_LABELS:
            return TASK_FOR_OUTCOME[name]
    return 'compare'


def filter_repeats(s, reply, requested=False):
    """Hold back whole reply blocks that restate what this visit already showed.

    A block is a repeat when most of its content words come from one block
    already shown or from one fact already delivered. A request, confusion or
    changed circumstances (requested=True) allows the repeat."""
    ledger = _ledger(s)
    blocks = [b for b in (reply or '').split('\n\n') if b.strip()]
    if requested or not blocks:
        return reply, 0
    prior = list(ledger['shown']) + [v.get('words', []) for v in ledger['facts'].values()]
    kept = [b for b in blocks if not _repeat(b, prior)]
    return '\n\n'.join(kept), len(blocks) - len(kept)


def record_shown(s, reply, evidence, cards=()):
    """Record what was actually displayed: blocks, facts (with words) and concepts."""
    ledger = _ledger(s)
    for block in [b for b in (reply or '').split('\n\n') if b.strip()]:
        words = sorted(tokens(block))
        if len(words) >= 5:
            ledger['shown'].append(words)
    del ledger['shown'][:-40]
    facts = dict(evidence or {})
    for card in cards or ():
        for fact in CARD_FACTS.get(card.get('kind'), []) + list(card.get('facts') or []):
            facts.setdefault(fact, '')
    for fact, text in facts.items():
        row = ledger['facts'].setdefault(fact, {'times': 0, 'words': sorted(tokens(text))})
        row['times'] += 1
        if text and not row['words']:
            row['words'] = sorted(tokens(text))
        concept, role = FACT_CONCEPT.get(fact, (None, None))
        if concept:
            depth = 'introduced' if role == 'core' else 'explored'
            if DEPTH.get(depth, 0) > DEPTH.get(ledger['concepts'].get(concept), 0):
                ledger['concepts'][concept] = depth
    return ledger


def education_view(s, learner=None):
    ledger = _ledger(s)
    concepts = dict(ledger['concepts'])
    if learner:
        for item in (learner.get('observations') or [])[-12:]:
            if item.get('signal') in ('uncertain', 'misconception') and item.get('concept_id') in CONCEPTS:
                concepts[item['concept_id']] = 'needs_clarification'
    checklist = {topic: concepts.get(concept) in ('introduced', 'explored') for topic, concept in CHECKLIST_CONCEPTS.items()}
    return {'version': EDUCATION_VERSION, 'concepts': concepts,
            'delivered_facts': sorted(ledger['facts']),
            'checklist_covered': sorted(t for t, v in checklist.items() if v),
            'rule': 'Facts listed as delivered were already shown in this visit. Do not restate them '
                    'unless the person asks, is confused or their circumstances changed; refer back in a clause.'}


def flagged_concepts(learner):
    """Concepts the interpreter flagged this turn: confusion or a request to revisit."""
    out = set()
    for item in (learner or {}).get('observations') or []:
        if item.get('signal') in ('uncertain', 'misconception') and item.get('concept_id') in CONCEPTS:
            out.add(item['concept_id'])
    return out


def concept_map():
    return [{'concept_id': c, 'title': t, 'core': core, 'details': list(details), 'new': c in NEW_CONCEPTS}
            for c, (t, core, details) in CONCEPTS.items()]


# ---------------------------------------------------------------------------
# Every turn ends on a lead: an offer of work becomes a button.
# ---------------------------------------------------------------------------

OFFER_LABELS = {
    'providers': 'Check my doctors', 'drug_coverage': 'Check my medicines', 'drug_pricing': 'Price my medicines',
    'compare': 'Compare my options', 'review': 'Review my coverage', 'timing': 'Work out my sign-up timing',
    'medigap': 'See Medigap prices', 'advantage': 'See Medicare Advantage plans', 'costs': 'Work through costs',
}


# Button words the person sends as their own: first person only when the
# coverage is for them, so a researcher or helper is never made to say "my".
OFFER_LABELS_NEUTRAL = {
    'providers': 'Check doctors', 'drug_coverage': 'Check medicines', 'drug_pricing': 'Price medicines',
    'compare': 'Compare the options', 'review': 'Review current coverage', 'timing': 'Work out sign-up timing',
    'medigap': 'See Medigap prices', 'advantage': 'See Medicare Advantage plans', 'costs': 'Work through costs',
}
# Work that needs one person's details is not offered for research only.
PERSONAL_TASKS = {'providers', 'drug_coverage', 'drug_pricing', 'review', 'timing'}


def offer_card(task=None, role=None):
    if role == 'research' and task in PERSONAL_TASKS:
        task = 'compare'
    labels = OFFER_LABELS if role == 'self' else OFFER_LABELS_NEUTRAL
    label = labels.get(task or '', 'Yes, let’s do that')
    say = ('Yes, let’s do that: ' + label.lower() + '.') if task in labels else 'Yes, let’s do that.'
    return {'kind': 'next_step_offer', 'title': '', 'actions': [{'label': label, 'say': say}], 'records': VERSION}


def role_of(out):
    record = out.get('readiness') if isinstance(out.get('readiness'), dict) else out.get('record') or {}
    choice = (((record.get('facts') or {}).get('RC01') or {}).get('value') or {}).get('choice')
    if choice:
        return choice
    field = ((out.get('guide') or {}).get('fields') or {}).get('subject.role') or {}
    return field.get('value')


def strip_flow_instructions(rules):
    """Rules supply facts and conditions; the profile and models choose questions."""
    out = []
    for rule in rules:
        rule = dict(rule)
        note = rule.get('how_to_use') or ''
        sentences = re.split(r'(?<=[.;])\s+', note)
        kept = [x for x in sentences if not re.search(r'(?i)\b(?:then )?(?:ask|confirm whose|settle it)\b', x)]
        rule['how_to_use'] = ' '.join(kept).strip()
        rule['depends_on'] = [i for i in rule.pop('confirm_with', []) if i]
        out.append(rule)
    return out


def fingerprint(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Semantic capture of Medicare status, plans already held and the birth month
# (fix a). The interpreter proposes; code checks structure and grounding only:
# the quote is in the message, stated values appear in it, the person is the
# beneficiary. No vocabulary decides what the person meant.
# ---------------------------------------------------------------------------

COVERAGE_KINDS = ('part_a', 'part_b', 'held_plan', 'birth')
PART_STATUSES = ('applied', 'approved', 'active', 'not_enrolled', 'needs_info', 'denied')
PRODUCTS = ('medigap', 'advantage', 'part_d')
LETTERS = ('A', 'B', 'C', 'D', 'F', 'G', 'K', 'L', 'M', 'N')
_MONTH_WORDS = [None, 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def coverage_reports_schema(make):
    return {'type': 'array', 'maxItems': 4, 'items': make({
        'kind': {'type': 'string', 'enum': list(COVERAGE_KINDS)},
        'subject': {'type': 'string', 'enum': ['beneficiary', 'learner', 'unclear']},
        'quote': {'type': 'string', 'maxLength': 300},
        'status': {'type': 'string', 'enum': ['', *PART_STATUSES]},
        'month': {'type': ['integer', 'null'], 'minimum': 1, 'maximum': 12},
        'year': {'type': ['integer', 'null'], 'minimum': 1900, 'maximum': 2099},
        'product': {'type': 'string', 'enum': ['', *PRODUCTS]},
        'name': {'type': 'string', 'maxLength': 80},
        'carrier': {'type': 'string', 'maxLength': 80},
        'letter': {'type': 'string', 'enum': ['', *LETTERS]}})}


def _grounded_month(quote, month):
    text = quote.casefold()
    return bool(re.search(r'\b' + _MONTH_WORDS[month], text) or re.search(r'(?<!\d)0?%d\s*[/-]' % month, text))


def _grounded_year(quote, year):
    return bool(re.search(r'(?<!\d)%d(?!\d)' % year, quote) or re.search(r"[/'’-]\s*%02d(?!\d)" % (year % 100), quote))


def validate_coverage_reports(value, message):
    """Returns (accepted, needs_confirmation). Structure and grounding only."""
    keys = {'kind', 'subject', 'quote', 'status', 'month', 'year', 'product', 'name', 'carrier', 'letter'}
    accepted, confirm = [], []
    if not isinstance(value, list) or len(value) > 4:
        return accepted, confirm
    folded = (message or '').casefold()
    for item in value:
        if not isinstance(item, dict) or set(item) != keys or item['kind'] not in COVERAGE_KINDS:
            continue
        quote = item['quote'] if isinstance(item['quote'], str) else ''
        if not quote.strip() or quote.casefold() not in folded:
            continue
        month, year = item['month'], item['year']
        if (month is not None and (type(month) is not int or not 1 <= month <= 12 or not _grounded_month(quote, month))
                or year is not None and (type(year) is not int or not 1900 <= year <= 2099 or not _grounded_year(quote, year))):
            continue
        if any(item[k] and (not isinstance(item[k], str) or item[k].casefold() not in folded) for k in ('name', 'carrier')):
            continue
        if item['letter'] and (item['letter'] not in LETTERS or not re.search(r'(?i)\b%s\b' % item['letter'], quote)):
            continue
        kind = item['kind']
        well_formed = (kind in ('part_a', 'part_b') and item['status'] in PART_STATUSES
                       or kind == 'held_plan' and item['product'] in PRODUCTS
                       or kind == 'birth' and month is not None and year is not None)
        if not well_formed:
            continue
        clean = {k: item[k] for k in keys}
        (accepted if item['subject'] == 'beneficiary' else confirm).append(clean)
    return accepted, confirm


def apply_coverage_reports(flow, g, r, reports, today=None):
    """Write accepted reports into the existing fields. Returns changed field names."""
    import enrollment_flow
    today = today or _today()
    changed, statuses = [], {}
    for item in reports:
        kind = item['kind']
        if kind == 'birth':
            value = '%04d-%02d' % (item['year'], item['month'])
            if flow.value(g, 'coverage.birth') != value:
                flow.put(g, 'coverage.birth', value, 'user_text')
                changed.append('coverage.birth')
            # The 65th-birthday month is derived from the anchor, never asked separately.
            derived = {'month': item['month'], 'year': item['year'] + 65}
            current = flow.value(g, 'situation.age65') or {}
            if (current.get('month'), current.get('year')) != (derived['month'], derived['year']):
                flow.put(g, 'situation.age65', derived, 'user_text')
                changed.append('situation.age65')
        elif kind in ('part_a', 'part_b'):
            part = 'A' if kind == 'part_a' else 'B'
            statuses[part] = item['status']
            if item['status'] == 'not_enrolled':
                continue
            when = (date(item['year'], item['month'], 1).isoformat()
                    if item['year'] and item['month'] else None)
            report = {'status': 'approved' if item['status'] == 'active' and when and when > today.isoformat() else item['status'],
                      'date': when, 'date_kind': 'start' if item['status'] in ('active', 'approved') and when else
                      ('application' if item['status'] in ('applied', 'needs_info', 'denied', 'approved') else 'start')}
            if when:
                report['precision'] = 'month'
            previous = flow.value(g, enrollment_flow.PART_FIELDS[part])
            if isinstance(previous, dict) and not when and previous.get('status') == report['status']:
                continue                          # the same report without its date never erases the date
            if previous != report:
                flow.put(g, enrollment_flow.PART_FIELDS[part], report, 'user_text')
                changed.append(enrollment_flow.PART_FIELDS[part])
        elif kind == 'held_plan':
            known = flow.value(g, enrollment_flow.HAVE_FIELD)
            merged = dict(known) if isinstance(known, dict) else {}
            if item['product'] == 'medigap' and item['letter']:
                merged['medigap_letter'] = item['letter']
            if item['name'] or item['carrier'] or item['product'] != 'medigap':
                merged[item['product']] = {k: item[k] for k in ('name', 'carrier') if item[k]}
                merged[item['product']]['basis'] = 'reported'   # what they said, not verified
            if merged != known:
                flow.put(g, enrollment_flow.HAVE_FIELD, merged, 'user_text')
                changed.append(enrollment_flow.HAVE_FIELD)
    if statuses:
        current = {part: (flow.value(g, field) or {}).get('status') for part, field in enrollment_flow.PART_FIELDS.items()}
        current.update(statuses)
        on = {part: current.get(part) in ('active', 'approved') for part in ('A', 'B')}
        known = {part: current.get(part) in ('active', 'approved', 'not_enrolled') for part in ('A', 'B')}
        if all(known.values()):
            choice = {(True, True): 'both', (True, False): 'a_only', (False, True): 'b_only',
                      (False, False): 'neither'}[(on['A'], on['B'])]
            if flow.report(r, 'RC04').get('choice') != choice:
                flow.fact(r, 'RC04', {'choice': choice}, 'confirmed_agent_interpretation')
                changed.append('RC04')
    return changed


# ---------------------------------------------------------------------------
# The plan the person chooses (intent.selectedPlan), from the Plans page.
# ---------------------------------------------------------------------------

def select_plan(flow, g, value, year=2026):
    """A tapped "Choose this plan". Code-checked shape; the person's own choice."""
    if not isinstance(value, dict) or set(value) - {'product', 'plan_id', 'name', 'year'}:
        raise ValueError('Use a current plan choice.')
    product, plan_id, name = value.get('product'), value.get('plan_id'), value.get('name')
    if (product not in ('advantage', 'medigap', 'part_d') or not isinstance(plan_id, str) or not 1 <= len(plan_id) <= 80
            or not isinstance(name, str) or not 1 <= len(name) <= 160):
        raise ValueError('Use a current plan choice.')
    plan_year = value.get('year', year)
    if plan_year not in (year, year + 1):
        raise ValueError('Use a current plan choice.')
    flow.put(g, SELECTED_PLAN_FIELD, {'product': product, 'plan_id': plan_id, 'name': name,
                                      'year': plan_year, 'source': 'plans_page'}, 'user_choice')


# ---------------------------------------------------------------------------
# D188 (November 18, 2026): pending questions, passes, single-field targets and
# offers. Spec: docs/product/PROFILE_AND_EDUCATION_RECORDS.md, "Pending
# questions, passes, single-field targets and offers". Everything here is under
# pending_on(flow). The pending question lives on its receipt in the existing
# question-progress ledger (no second store); offers live in the planner's
# visit-only state. No model call, no word list.
# ---------------------------------------------------------------------------

DISPOSITIONS = ('answered', 'detour', 'passed', 'does_not_know', 'none')
PASS_LIMIT = 2          # Chris, November 13: a question passed twice is parked
DELIVERY_CAP = 4        # proposed default, for Chris to confirm: bounds the detour loop
OFFER_LIMIT = 2         # an offer shown twice and not taken is not shown a third time
# What kind of value each field holds. Fields that are not listed are their own
# kind. A question never asks for two open values of one kind at once.
VALUE_KIND = {'jobEnd': 'date', 'coverageEnd': 'date', 'eventDate': 'date', 'start': 'date', 'month': 'date',
              'amount': 'amount', 'quantity': 'amount', 'daysSupply': 'amount'}
# Order of same-kind fields within a meaning: what the readiness views read
# first (work_window's plan window reads the insurance end, then the job end).
FIELD_ORDER = {'RC11': ('coverageEnd', 'jobEnd')}
# Guidance for the two models. It travels in the turn context only while a
# question is pending, so the standing prompts do not grow. Never shown to a person.
DISPOSITION_RULE = ('pending_disposition says what this message did with the pending question: answered; '
                    'detour = they asked or raised something they need before they can answer; '
                    'passed = they declined or moved on without engaging; does_not_know; none. '
                    'A plain reply to a pending question that asks for one field fills that field; '
                    'mark it uncertain only for doubt in their own words.')
RETURN_RULE = ('This question was asked and is still waiting. Answer what the person just asked or raised, '
               'then come back to this same question simply. Explain an unfamiliar term itself, not just why '
               'it matters. Do not assume the explanation established understanding or present the question '
               'as new. Make no other offer.')


def validate_pending_disposition(value):
    return value if isinstance(value, str) and value in DISPOSITIONS else 'none'


def pending_disposition_schema():
    return {'type': 'string', 'enum': list(DISPOSITIONS)}


def value_fields(identifier):
    """A meaning's value fields (its status choice aside), in asking order."""
    from natural_state import FIELD_NAMES, SITUATION_TARGETS
    names = set(SITUATION_TARGETS.get(identifier) or FIELD_NAMES.get(identifier) or ()) - {'choice'}
    first = [f for f in FIELD_ORDER.get(identifier, ()) if f in names]
    return first + sorted(names - set(first))


def same_kind_groups(identifier):
    groups = OrderedDict()
    for field in value_fields(identifier):
        groups.setdefault(VALUE_KIND.get(field, field), []).append(field)
    return [fields for fields in groups.values() if len(fields) > 1]


def multi_field_inventory():
    """Every meaning with more than one field, and what is narrowed or left whole."""
    from natural_state import FIELD_NAMES, SITUATION_TARGETS
    rows = []
    for identifier in list(FIELD_NAMES) + list(SITUATION_TARGETS):
        names = set(SITUATION_TARGETS.get(identifier) or FIELD_NAMES[identifier])
        if len(names) < 2:
            continue
        groups = same_kind_groups(identifier)
        rows.append({'id': identifier, 'fields': (['choice'] if 'choice' in names else []) + value_fields(identifier),
                     'kinds': {f: VALUE_KIND.get(f, f) for f in value_fields(identifier)},
                     'narrowed': groups[0] if groups else [],
                     'asked_by_records': identifier in PROFILE_FIELDS and identifier not in NEVER_ASK})
    return rows


def _one_field(flow, g, r, identifier):
    """Two or more open values of one kind become a question about the first.
    Uses the narrowing that already exists (flow.question(id, [field]))."""
    import question_progress
    if identifier not in Q:
        return None
    for group in same_kind_groups(identifier):
        try:
            projected = question_progress.project(flow, g, r, flow.question(identifier, list(group)))
        except Exception:
            continue
        if 'reported' in projected['fields'].values() or not projected['open_fields']:
            continue        # one value is in: the sibling is taken if offered, not asked on its own
        first = next(f for f in group if f in projected['open_fields'])
        return flow.contextual_question(g, r, flow.question(identifier, [first]))
    return None


def at_limit(receipt):
    return bool(receipt.get('parked') or receipt.get('passes', 0) >= PASS_LIMIT
                or receipt.get('shown', 0) >= DELIVERY_CAP)


def confirmation_waiting(flow, owner, identifier):
    waiting = flow.pending_for(owner) if owner is not None else None
    return bool(waiting and any(item.get('id') == identifier
                                for item in [waiting['update'], *waiting.get('remaining', [])]))


def should_park(flow, owner, identifier, receipt):
    """Two passes, or the delivery cap. A field with a confirmation waiting is never parked."""
    return bool(receipt) and at_limit(receipt) and not confirmation_waiting(flow, owner, identifier)


def pending_receipt(ledger):
    for key, receipt in (ledger or {}).items():
        if isinstance(receipt.get('pending'), dict):
            return key, receipt
    return None, None


def mark_delivered(ledger, key, receipt, question, g, r, prior_key):
    """Called when a question is actually delivered: it becomes the one pending question."""
    for other in ledger.values():
        other.pop('pending', None)
    identifier = question['id'].split('.')[0]
    if identifier in PROFILE_FIELDS and identifier not in NEVER_ASK and question.get('entity', 'profile') == 'profile':
        receipt['pending'] = {'id': identifier, 'fields': [f['key'] for f in question.get('fields', [])],
                              'revision': [g['stateVersion'], r['stateVersion']], 'returned': prior_key == key}


def _still_open(flow, g, r, receipt):
    import question_progress
    identifier = receipt['pending']['id']
    if fixes_on(flow) and identifier in medigap_profile.FIELDS:
        # D190: a Medigap price detail code can derive (the age from a 65th-birthday month) is not open.
        return identifier in medigap_profile.for_flow(flow, g, r).get('missing', [])
    if not question_progress.project(flow, g, r, receipt['question'])['open_fields']:
        return False
    current = _question(flow, g, r, identifier)
    return bool(current and question_progress.project(flow, g, r, current)['open_fields'])


def resolve_pending(flow, owner, g, r, s, disposition, outcomes=()):
    """Once per message, after capture: what the reply did with the pending
    question. The interpreter's code is checked by structure, never by words."""
    ledger = s.setdefault('question_progress', {})
    key, receipt = pending_receipt(ledger)
    s['records_passed_now'] = None
    s['records_pending_proposed'] = validate_pending_disposition(disposition)
    s['records_pending_code'] = None
    if not receipt:
        return None
    identifier = receipt['pending']['id']
    targets = [t for t in s.get('next_target') or [] if t in PROFILE_FIELDS]
    touched = any(item.get('target') == identifier for item in outcomes or ())
    if not _still_open(flow, g, r, receipt) or confirmation_waiting(flow, owner, identifier):
        code = 'answered'                         # a saved value, an explicit unknown, or a one-tap confirmation queued
    elif identifier in (s.get('deferred') or []) or _dispositions(r).get(identifier) in ('deferred', 'explicit_unknown', 'unknown'):
        code = 'does_not_know'
    elif s['records_pending_proposed'] == 'does_not_know' and not touched:
        if identifier not in s.setdefault('deferred', []):
            s['deferred'].append(identifier)      # set aside for this visit, like the "I don't know" control
        code = 'does_not_know'
    elif s.get('next_target_reason') == 'person_raised' and targets and identifier not in targets:
        code = 'released'                         # the person raised a new subject: open again, no pass
    elif s['records_pending_proposed'] == 'passed' and not touched:
        receipt['passes'] = receipt.get('passes', 0) + 1
        s['records_passed_now'] = identifier
        code = 'passed'
    else:
        code = 'detour'                           # includes "answered" with nothing saved or queued
    if at_limit(receipt) and code in ('passed', 'detour'):
        receipt['parked'] = True
        if code == 'detour':
            code = 'parked'
    if code != 'detour':
        receipt.pop('pending', None)
    s['records_pending_code'] = code
    return code


def standing_pending(flow, owner, g, r, s):
    """The pending question's ID while it still stands. Idempotent; also settles
    a tapped answer, an "I don't know" control or a queued confirmation."""
    ledger = s.setdefault('question_progress', {})
    key, receipt = pending_receipt(ledger)
    if not receipt:
        return None
    identifier = receipt['pending']['id']
    settled = (not _still_open(flow, g, r, receipt) or confirmation_waiting(flow, owner, identifier)
               or identifier in (s.get('deferred') or [])
               or _dispositions(r).get(identifier) in ('deferred', 'explicit_unknown', 'unknown'))
    if settled or at_limit(receipt):
        if at_limit(receipt) and not settled:
            receipt['parked'] = True
        receipt.pop('pending', None)
        s.setdefault('records_pending_code', None)
        if s['records_pending_code'] is None:
            s['records_pending_code'] = 'answered' if settled else 'parked'
        return None
    return identifier


def release_pending(s, code='released'):
    """A task control the person tapped is a new subject: open again, no pass."""
    key, receipt = pending_receipt(s.get('question_progress'))
    if receipt:
        receipt.pop('pending', None)
        s['records_pending_code'] = code


def pending_view(flow, owner, g, r, s):
    """For the interpreter: the question that was asked and is waiting."""
    key, receipt = pending_receipt(s.get('question_progress'))
    if not receipt or at_limit(receipt) or not _still_open(flow, g, r, receipt):
        return None
    marker = receipt['pending']
    return {'id': marker['id'], 'fields': list(marker['fields']), 'delivered': receipt.get('shown', 0),
            'rule': DISPOSITION_RULE}


def pending_plan(s, moves):
    """For the composer: the target is a return, with its delivery count."""
    identifier = s.get('records_pending_return')
    key, receipt = pending_receipt(s.get('question_progress'))
    if not identifier or not receipt or not any(m['id'] == identifier for m in moves):
        return None
    return {'id': identifier, 'fields': list(receipt['pending']['fields']), 'returning': True,
            'delivered': receipt.get('shown', 0), 'rule': RETURN_RULE}


def task_fields(flow, g, r, task, bundle):
    """The fields an accepted offer's task works through, from existing code."""
    import conversation_tasks
    ids = [item['id'] for item in conversation_tasks.candidates(flow, g, r, task)]
    for name in bundle.get('order') or []:
        if TASK_FOR_OUTCOME.get(name) == task:
            ids += bundle['outcomes'][name]['needs']
    return list(dict.fromkeys(ids))


def _offer_order(s):
    order = []
    first = s.get('suggested_task') or s.get('active_task')
    if first in OFFER_LABELS:
        order.append(first)
    for name in (s.get('records_bundle') or {}).get('order') or []:
        if TASK_FOR_OUTCOME.get(name) in OFFER_LABELS:
            order.append(TASK_FOR_OUTCOME[name])
    return list(dict.fromkeys(order + ['compare'] + list(OFFER_LABELS)))


def next_offer(s, role=None):
    """The next work to offer: never one already taken, never a third showing."""
    offers = s.setdefault('records_offers', {})
    for task in _offer_order(s):
        if role == 'research' and task in PERSONAL_TASKS:
            task = 'compare'
        row = offers.get(task) or {}
        if row.get('accepted') or row.get('shown', 0) >= OFFER_LIMIT:
            continue
        return {'task': task, 'card': offer_card(task, role)}
    return None


def record_offer(s, task, card):
    row = s.setdefault('records_offers', {}).setdefault(task, {'shown': 0, 'accepted': False})
    row['shown'] += 1
    s['records_last_offer'] = {'task': task, 'say': card['actions'][0]['say']}


def accept_offer(s, message):
    """A tap sends the button's own words, issued by this server on the last
    turn. An exact match is the tap; anything typed is left to the interpreter."""
    last = s.get('records_last_offer')
    if not last or not isinstance(message, str) or message.strip() != last['say']:
        return None
    s.pop('records_last_offer', None)
    s.setdefault('records_offers', {}).setdefault(last['task'], {'shown': 1, 'accepted': False})['accepted'] = True
    return last['task']


def offers_trace(s):
    offers = s.get('records_offers') or {}
    return {'shown': {task: row['shown'] for task, row in offers.items()},
            'accepted': [task for task, row in offers.items() if row.get('accepted')]}


def pending_trace(s):
    """Codes for the turn trace: never message text."""
    key, receipt = pending_receipt(s.get('question_progress'))
    marker = (receipt or {}).get('pending') or {}
    field = marker.get('id')
    if field and marker.get('fields'):
        field += '.' + ','.join(marker['fields'])
    return {'pending_field': field, 'pending_disposition': s.get('records_pending_code') or 'none',
            'pending_proposed': s.get('records_pending_proposed') or 'none',
            'passes': (receipt or {}).get('passes', 0) if receipt else None,
            'deliveries': (receipt or {}).get('shown') if receipt else None,
            'returned': bool(marker.get('returned')), 'offers': offers_trace(s)}


# ---------------------------------------------------------------------------
# D190 (November 18, 2026): conversation fixes from visit a912962310. Under
# fixes_on(flow). Evidence: audit-evidence/conversation-fixes-20261118.
# ---------------------------------------------------------------------------

# 1. "I'm turning 65 next month" names no month. The interpreter says which
# month relative to today (one code); code does the arithmetic.
RELATIVE_MONTHS = OrderedDict([('none', None), ('last_month', -1), ('this_month', 0), ('next_month', 1)])


def relative_month_schema():
    return {'type': 'string', 'enum': list(RELATIVE_MONTHS),
            'description': 'age65 only: the person places the 65th birthday relative to today and names no month '
                           '("next month"). Leave month and year null. Otherwise none.'}


def resolve_relative_month(proposal, today=None):
    """A copy with month and year computed from today, for an age65 proposal that names no month."""
    out = dict(proposal)
    offset = RELATIVE_MONTHS.get(out.pop('relative_month', 'none'))
    if out.get('kind') != 'age65' or offset is None or out.get('month') is not None:
        return out
    today = today or _today()
    year, month = _month_add(today.year, today.month, offset)
    if out.get('year') in (None, year):
        out.update(month=month, year=year)
    return out


# 2. A reply the checks rejected, on a turn that did save answers: say what was
# saved. Owner-review wording; labels and values are the profile's own rows.
SAVED_PREFIX = 'I’ve saved what you told me: '


def saved_acknowledgement(flow, g, r, outcomes):
    saved = [item.get('target') for item in outcomes or () if item.get('status') == 'accepted']
    parts = []
    for row in flow.rows(g, r):
        if row.get('id') in saved and row.get('status') == 'reported' and row.get('value') not in (None, '', []):
            value = row['value'] if isinstance(row['value'], str) else ', '.join(map(str, row['value'])) if isinstance(row['value'], list) else str(row['value'])
            parts.append('%s: %s' % (row['label'], value))
    return (SAVED_PREFIX + '; '.join(dict.fromkeys(parts)) + '.') if parts else ''


# 3. A detail asked before the close must not come ahead of the person's own question.
ANSWER_FIRST_RULE = ('This detail is asked before the close so listed prices can be shown. If the person asked or '
                     'requested something in this message, answer that first, including what Daylight can and cannot '
                     'tell them yet. Then say in one clause why this detail is needed. Do not open with the detail.')


def pre_close_plan(flow, s, moves):
    if not fixes_on(flow) or not s.get('records_preclose') or not moves:
        return None
    return {'id': moves[0]['id'], 'rule': ANSWER_FIRST_RULE}
