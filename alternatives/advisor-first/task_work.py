"""Task coordination over existing reports, teaching and actual operation receipts.

The agent selects relevant connections. Software owns verification/completion
states. This is visit-only working context, never a profile, a source acceptance
loader, an action executor or a new intake sequence.
"""
import copy
import hashlib
import json
import re

VERSION = 'task-work-20261103-r1'
STEPS = ('answer', 'clarify', 'teach', 'prepare', 'review', 'pause')
LIMIT = 4
CHECKS = {
    'coverage_identity': ('Exact coverage', ('guide.coverage.current', 'readiness.RC07.', 'readiness.RC26.'),
        'Use the exact plan name, identifier and year from the coverage documents.',
        'A reported carrier or coverage type is not an independently identified exact plan.'),
    'provider_identity': ('Clinician and office', ('guide.people.doctors', 'readiness.RC21.'),
        'Confirm the intended clinician and exact office location.',
        'A name or office report is not a source identity or a participation check.'),
    'provider_participation': ('Plan participation', ('guide.people.doctors', 'readiness.RC21.', 'guide.coverage.current'),
        'Ask the intended office and plan to confirm participation for the exact plan, location and period.',
        'An office accepting a carrier does not establish participation in an exact plan.'),
    'service_benefit': ('Service and benefit conditions', ('guide.coverage.current',),
        'Check the exact service against the published benefit terms and applicable conditions.',
        'Provider participation does not establish service coverage or required authorization.'),
    'personal_cost': ('Personal payment', ('guide.needs.costPreference', 'readiness.RC25.', 'readiness.RC23.'),
        'Identify the cost basis, included components and missing prices before describing what someone may pay.',
        'A published amount or partial subtotal is not a personal total or quote.'),
    'enrollment_timing': ('Enrollment steps and dates', ('guide.coverage.current', 'guide.situation.', 'readiness.RC04.', 'readiness.RC09.', 'readiness.RC11.'),
        'Confirm applicable enrollment rules and actual dates with the appropriate official service.',
        'A desired start or birthday does not establish eligibility or an effective date.'),
    'coverage_paths': ('Coverage choices', ('guide.coverage.current', 'guide.needs.priorities'),
        'Explain the relevant coverage pieces and consequential tradeoffs before comparing policies.',
        'Understanding a path does not establish personal eligibility or plan fit.'),
    'help_and_logistics': ('Practical help and coordination', ('guide.subject.role',),
        'Identify the specific unresolved practical need and prepare questions for the appropriate service.',
        'Helping a relative does not establish permission, financial eligibility or available care.'),
}
CHECK_IDS = tuple(CHECKS)


def neutral_selection():
    return {'check_ids': [], 'blocking_concepts': [], 'next_step': 'answer'}


def validate_selection(value, *, limit=LIMIT):
    if (not isinstance(value, dict) or set(value) != {'check_ids', 'blocking_concepts', 'next_step'}
            or not isinstance(value['check_ids'], list) or len(value['check_ids']) > limit
            or any(not isinstance(item, str) or item not in CHECKS for item in value['check_ids'])
            or len(set(value['check_ids'])) != len(value['check_ids'])
            or not isinstance(value['blocking_concepts'], list) or len(value['blocking_concepts']) > 2
            or any(not isinstance(item, str) or len(item) > 64 for item in value['blocking_concepts'])
            or len(set(value['blocking_concepts'])) != len(value['blocking_concepts'])
            or not isinstance(value['next_step'], str) or value['next_step'] not in STEPS):
        raise ValueError('TASK_WORK_SELECTION_INVALID')
    return copy.deepcopy(value)


def empty_record():
    return {'version': VERSION, 'task_binding': None, 'selection': neutral_selection()}


def validate_record(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'task_binding', 'selection'}
            or value['version'] != VERSION or value['task_binding'] is not None and (
                not isinstance(value['task_binding'], str) or not re.fullmatch('[a-f0-9]{64}', value['task_binding']))):
        raise ValueError('TASK_WORK_RECORD_INVALID')
    return {**copy.deepcopy(value), 'selection': validate_selection(value['selection'], limit=len(CHECKS))}


def _binding(context):
    brief = context.get('advisor_brief', {})
    # The goal already has explicit-report validation. Keep its fingerprint in
    # server RAM only, never the model context or a second copy of the goal.
    key = [context.get('task'), brief.get('goal'), brief.get('reported_goal')]
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def _blockers(context):
    education = context.get('education_context', {})
    learning = education.get('learning', {})
    blockers = [row['concept_id'] for row in learning.get('covered', [])
        if isinstance(row, dict) and row.get('needs_clarification') is True]
    request = education.get('current_clarification', [])
    blockers += [item for item in request if isinstance(item, str)]
    blockers += [item['concept_id'] for item in context.get('learner_context', {}).get('observations', [])
                 if item['signal'] in {'uncertain', 'misconception'}]
    return list(dict.fromkeys(blockers))


def _rows(context, check):
    prefixes = CHECKS[check][1]
    reports = [row for row in context.get('reports', []) if isinstance(row, dict)
        and isinstance(row.get('id'), str) and row['id'].startswith(prefixes)]
    available = [row['id'] for row in reports if row.get('status') == 'reported']
    known = [row for row in context.get('known', []) if isinstance(row, dict)
        and isinstance(row.get('id'), str) and row['id'].startswith(prefixes)]
    states = sorted({row.get('status') for row in known + reports
                     if isinstance(row.get('status'), str) and row['status'] != 'reported'})
    return {'report_refs': list(dict.fromkeys(available)), 'input_states': states,
            'input_state': 'reported_inputs_available' if available else
                'open_in_current_context' if states else 'not_in_current_context'}


def build_context(context, previous=None):
    """Only derive states from the already permission-minimized model context."""
    prior = validate_record(previous) if previous is not None else empty_record()
    selection = prior['selection'] if prior['task_binding'] == _binding(context) else neutral_selection()
    checks = []
    for identifier, (label, _, next_step, distinction) in CHECKS.items():
        checks.append({'check_id': identifier, 'label': label, **_rows(context, identifier),
            'verification_state': 'not_verified', 'execution_state': 'not_started',
            'next_step': next_step, 'distinction': distinction})
    decision = context.get('advisor_brief', {}).get('decision', {})
    return {'version': VERSION, 'task_source': 'existing_user_goal_and_agenda',
        'task_focus': decision.get('practical_focus', context.get('task', '')),
        'active_checks': selection['check_ids'], 'checks': checks,
        'blocking_concepts': _blockers(context),
        'return_point': context.get('advisor_brief', {}).get('pending_question'),
        'personal_findings_available': False, 'external_actions_available': False}


def plan(context, proposed=None, previous=None, *, accepted_teaching=(), paused=False):
    """Validate the agent's choice without inventing findings or new reports."""
    base = build_context(context, previous)
    try:
        selection = validate_selection(proposed) if proposed is not None else neutral_selection()
    except ValueError:
        selection = neutral_selection()
    selection['check_ids'] = list(dict.fromkeys([*base['active_checks'], *selection['check_ids']]))
    selection['blocking_concepts'] = [item for item in selection['blocking_concepts']
                                     if item in base['blocking_concepts']]
    delivered = {row['concept_id'] for row in accepted_teaching
                 if row.get('depth') != 'needs_clarification'}
    teaching = [{'concept_id': identifier,
        'state': 'explanation_delivered_not_comprehension' if identifier in delivered else 'still_open'}
        for identifier in selection['blocking_concepts']]
    if paused is True:
        selection['next_step'] = 'pause'
    record = {'version': VERSION, 'task_binding': _binding(context), 'selection': selection}
    result = {'version': VERSION, 'task_focus': base['task_focus'],
        'checks': [row for row in base['checks'] if row['check_id'] in selection['check_ids']],
        'teaching': teaching, 'next_step': selection['next_step'],
        'return_point': base['return_point'], 'task_resolved': False,
        'supported_findings': [], 'completed_external_actions': [],
        'outcome': 'open_check_with_next_step' if selection['check_ids'] else
                   'explanation_delivered' if delivered else 'conversation_continues'}
    return record, result


def attach_result(out, record=None, *, historical=False, action=None, preparation_valid=False):
    """Rebuild current check states without retaining private values in the ledger.

    No production external-result loader exists in this increment. Successful
    local preparation is a distinct receipt and never completes outside checks.
    """
    previous = out.pop('task_work', None)
    if historical or out.get('generated', {}).get('status') == 'unavailable':
        return out
    if record is None and isinstance(previous, dict) and previous.get('version') == VERSION:
        # An authenticated current-head replay retains its server-built result;
        # HTTP clients cannot submit task_work as response authority.
        out['task_work'] = previous
        return out
    checked = validate_record(record) if record is not None else empty_record()
    selection = checked['selection']
    rows = []
    for identifier in selection['check_ids']:
        label, _, next_step, distinction = CHECKS[identifier]
        rows.append({'check_id': identifier, 'label': label, 'verification_state': 'not_verified',
            'execution_state': 'not_started', 'next_step': next_step, 'distinction': distinction})
    result = {'version': VERSION, 'checks': rows, 'next_step': selection['next_step'],
        'task_resolved': False, 'supported_findings': [], 'completed_external_actions': [],
        'outcome': 'open_check_with_next_step' if rows else 'conversation_continues'}
    if isinstance(previous, dict) and previous.get('version') == VERSION:
        for key in ('task_focus', 'teaching', 'return_point', 'outcome'):
            if key in previous:
                result[key] = copy.deepcopy(previous[key])
        selected = {row['check_id']: row for row in previous.get('checks', [])}
        result['checks'] = [copy.deepcopy(selected.get(row['check_id'], row)) for row in rows]
    if action == 'run_preparation' and preparation_valid:
        result['local_operation'] = {'kind': 'preparation', 'state': 'completed',
            'receipt_ref': out['preparation']['id']}
        result['outcome'] = 'preparation_completed'
    out['task_work'] = result
    return out


_ACTION = re.compile(r"\b(?:i|we)(?:'ve| have)?\s+(?:(?:already|just)\s+)?(?:called|contacted|sent|booked|scheduled|submitted|arranged|requested a referral)\b|\b(?:i|we)(?:'ll| will)\s+(?:call|contact|send|book|schedule|submit|arrange|get back|follow up)\b", re.I)
_IDENTIFIED = re.compile(r"\b(?:i|we)(?:'ve| have)?\s+(?:(?:already|just)\s+)?(?:identified|matched|confirmed)\s+(?:your|the)\s+(?:exact\s+)?(?:plan|provider|office)\b", re.I)


def unsupported_action_claim(text):
    """Bounded literal guard, not semantic proof. No external actions are enabled."""
    text = text.replace('’', "'")
    return bool(_ACTION.search(text) or _IDENTIFIED.search(text))
