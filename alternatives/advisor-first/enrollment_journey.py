"""D161: a read-only enrollment view of the current conversation's reports.

No registration, storage, model calls or eligibility findings. Computed dates
come exclusively from the D157 timing helper and remain estimates. The caller
owns report validation, subject binding, capture and presentation.
"""
from calendar import monthrange
from datetime import date
import re

from guest_profiles import ProfileError
from timing_language import reported_end_date
from ux_pass import enrollment_timing

__all__ = ['status']


def _coverage_end(flow, guide, record):
    work = flow.report(record, 'RC11')
    retirement = flow.value(guide, 'situation.retirement')
    retirement_when = (retirement.get('when') if isinstance(retirement, dict)
                       and retirement.get('status') in ('retired', 'retiring') else None)
    if isinstance(retirement_when, str):
        retirement_when = re.sub(r'^(?:in|on)\s+', '', retirement_when.strip(), flags=re.I)
    for source, value in (('RC11.coverageEnd', work.get('coverageEnd')),
                          ('RC11.jobEnd', work.get('jobEnd')),
                          ('S_RETIREMENT', retirement_when)):
        if not value:
            continue
        try:
            normalized = reported_end_date(value)
            month_only = len(normalized) == 7
            day = date.fromisoformat(normalized + '-01' if month_only else normalized)
        except (ProfileError, ValueError):
            continue
        if month_only:
            day = day.replace(day=monthrange(day.year, day.month)[1])
        return {'date': day.isoformat(), 'precision': 'month' if month_only else 'day',
                'basis': 'reported', 'source': source}
    return None


def status(flow, guide, record, today=None) -> dict:
    """Derive enrollment-journey-v2 without changing the supplied aggregates.

    Pin ``today`` for reproducible results; otherwise use the current local day.
    Missing reports assert no action: ``none_needed`` / ``nothing_needed`` with
    unknown parts and a null finish is a quiet sentinel, not completed coverage.
    Automatic enrollment cannot be established by the v1 input reports, so its
    reserved state/route are never inferred from age or generic benefits receipt.
    """
    today = today if today is not None else date.today()
    rc04 = flow.report(record, 'RC04').get('choice')
    birthday = flow.value(guide, 'situation.age65')
    timing = enrollment_timing(birthday, today, rc04)
    window = None
    if timing:
        iep = timing['iep']
        window = {'start': iep['start'].isoformat(), 'end': iep['end'].isoformat(),
                  'phase': 'inside' if iep['phase'] == 'open' else iep['phase']}

    coverage = flow.value(guide, 'coverage.current')
    coverage = coverage if isinstance(coverage, list) else []
    basis = flow.report(record, 'RC06').get('choice')
    job = flow.report(record, 'RC09').get('choice')
    social = flow.value(guide, 'coverage.socialBenefits')
    unsupported = []
    if 'employer' in coverage or job in ('my_job', 'spouse_job', 'family_job'):
        unsupported.append('current_work_coverage')
    if window and window['phase'] == 'after':
        unsupported.append('window_passed')
    if basis in ('disability', 'esrd', 'als'):
        unsupported.append('not_age_based')
    if basis in ('railroad', 'rrb') or social in ('railroad', 'rrb') or 'railroad' in coverage:
        unsupported.append('railroad')
    work = None
    if getattr(flow, 'records_v1', False):
        # D183 / C46: when the person's own or spouse's job coverage is ending and
        # its dates are reported, code computes the window from accepted facts
        # (pk_work_sep and related). It replaces "confirm with Social Security"
        # for current-work coverage; the age-based window no longer governs.
        import conversation_records
        work = conversation_records.work_window(flow, guide, record, today)
        if work:
            unsupported = [item for item in unsupported if item not in ('current_work_coverage', 'window_passed')]
    supported_coverage = ('cobra', 'retiree', 'original', 'advantage', 'medigap', 'drug',
                          'none', 'employer', 'railroad')
    unclear = (any(item not in supported_coverage for item in coverage)
               or basis not in (None, '', 'age65', 'disability', 'esrd', 'als', 'railroad', 'rrb')
               or job not in (None, '', 'my_job', 'spouse_job', 'family_job', 'cobra', 'retiree'))

    baseline = {'both': ('active', 'active'), 'a_only': ('active', 'needed'),
                'b_only': ('needed', 'active'), 'neither': ('needed', 'needed'),
                'pending': ('pending', 'pending')}.get(rc04, ('unknown', 'unknown'))
    parts = {}
    reported_statuses = []
    confirm_dates = False
    for index, part in enumerate(('A', 'B')):
        state = baseline[index]
        start = {'date': None, 'basis': None}
        report = flow.value(guide, 'enrollment.part' + part)
        # A present but unrecognized report must not fall back to an old RC04.
        if report is not None:
            report = report if isinstance(report, dict) else {}
            reported = report.get('status')
            reported_statuses.append(reported)
            raw_date = report.get('date')
            start_date = None
            if report.get('date_kind') == 'start' and isinstance(raw_date, str):
                try:
                    parsed = date.fromisoformat(raw_date)
                    if parsed.isoformat() == raw_date:
                        start_date = parsed
                except ValueError:
                    pass
            if start_date is not None:
                start = {'date': raw_date, 'basis': 'reported'}
                if report.get('precision') == 'month': start['precision'] = 'month'
            if reported == 'applied':
                state = 'pending'
            elif reported in ('needs_info', 'denied'):
                # The output vocabulary has no denied state; the original
                # report retains that distinction and the next action differs.
                state = 'needs_info'
                unclear = unclear or reported == 'denied'
            elif reported == 'approved':
                state = ('approved_future' if start_date > today else 'active') if start_date else 'unknown'
                confirm_dates = confirm_dates or start_date is None
            elif reported == 'not_enrolled':
                state = 'needed'
                start = {'date': None, 'basis': None}
            elif reported == 'active':
                if start_date is not None and start_date > today:
                    state = 'needs_info'
                    confirm_dates = True
                else:
                    state = 'active'
            else:
                state = 'unknown'
                start = {'date': None, 'basis': None}
                unclear = True
        parts[part] = {'state': state, 'start': start}

    # Explicit uncertainty is different from a question not yet answered.
    if rc04 not in (None, '', 'both', 'a_only', 'b_only', 'neither', 'pending'):
        unclear = unclear or any(part['state'] == 'unknown' for part in parts.values())
    if unclear:
        unsupported.append('unclear_status')

    # Pending/approved/active reports never receive a hypothetical signup-today
    # estimate. In particular, an application date is not an effective date.
    if timing and not unsupported and not work:
        for part in ('A', 'B'):
            estimated = timing['part_' + part.lower() + '_start']
            if parts[part]['state'] == 'needed' and estimated is not None:
                parts[part]['start'] = {'date': estimated.isoformat(), 'basis': 'estimated'}

    decisions = flow.value(guide, 'intent.components')
    decisions = decisions if isinstance(decisions, dict) else {}
    components = {name: decisions.get(name) if decisions.get(name) in
                  ('chosen', 'not_needed', 'keep_existing', 'decide_later') else 'unknown'
                  for name in ('medigap', 'part_d')}
    path = flow.value(guide, 'intent.coveragePath')
    states = [part['state'] for part in parts.values()]
    settled_parts = all(state in ('active', 'pending') for state in states)
    settled_components = all(value in ('chosen', 'not_needed', 'keep_existing')
                             for value in components.values())
    finish = None
    if path in ('keep_current', 'wait'):
        finish = path
    elif settled_parts and path != 'medicare_advantage' and settled_components:
        finish = 'ab_only' if all(value == 'not_needed' for value in components.values()) else 'original_plus'
    # Choosing the Advantage path still leaves a plan decision. V1 has no
    # selected-plan report, so its finish stays null while that action is open.

    needed = [part for part in ('A', 'B') if parts[part]['state'] == 'needed']
    route = ('sign_up_a_and_b' if len(needed) == 2 else
             'add_part_a' if needed == ['A'] else
             'add_part_b' if needed == ['B'] else 'none_needed')
    next_step = {'id': 'nothing_needed', 'by': None, 'basis': None}
    if unsupported:
        if 'denied' in reported_statuses or any(state in ('needed', 'unknown') for state in states):
            route = 'confirm_with_social_security'
            next_step['id'] = 'confirm_with_social_security'
        elif 'needs_info' in reported_statuses:
            next_step['id'] = 'answer_request'
        elif confirm_dates:
            next_step['id'] = 'confirm_start_date'
        elif 'pending' in states:
            next_step['id'] = 'wait_for_decision'
        elif 'approved_future' in states:
            next_step['id'] = 'confirm_start_date'
    elif 'needs_info' in reported_statuses:
        next_step['id'] = 'answer_request'
    elif confirm_dates:
        next_step['id'] = 'confirm_start_date'
    elif path in ('keep_current', 'wait'):
        pass
    elif path == 'medicare_advantage':
        # Exploration remains possible with either part needed or pending.
        next_step['id'] = 'choose_advantage_plan'
    elif 'pending' in states:
        next_step['id'] = 'wait_for_decision'
    elif 'approved_future' in states:
        next_step = {'id': 'confirm_start_date', 'by': min(
            part['start']['date'] for part in parts.values() if part['state'] == 'approved_future'),
            'basis': 'reported'}
    elif needed and work:
        # The last day of the Part B window from the dates the person gave.
        import conversation_records
        y, m = (int(x) for x in work['part_b_window'][1].split('-'))
        next_step = {'id': 'sign_up', 'by': conversation_records.end_date('%04d-%02d' % (y, m)).isoformat(),
                     'basis': 'job_dates'}
    elif needed:
        next_step = {'id': 'sign_up', 'by': window['end'] if window else None,
                     'basis': 'estimated' if window else None}
    elif finish is not None:
        pass
    elif settled_parts:
        if path in ('original_only', 'original', 'original_medigap') or any(
                value in ('chosen', 'keep_existing') for value in components.values()):
            next_step['id'] = ('choose_medigap' if components['medigap'] in ('unknown', 'decide_later')
                               else 'choose_part_d')
        else:
            next_step['id'] = 'choose_path'

    result = {'version': 'enrollment-journey-v2', 'parts': parts, 'window': window,
              'route': route, 'next_step': next_step, 'components': components,
              'finish': finish, 'unsupported': unsupported,
              'coverage_end': _coverage_end(flow, guide, record)}
    if getattr(flow, 'records_v1', False):
        result['work_window'] = work
    return result
