"""D189: plan checks that state their true cause, and a working chat on the Plans pages.

Owner direction, November 18, 2026 (Brain: Inbox/Implementation prompt - plans
checks and plans chat 2026-11-18; evidence: audit-evidence/plans-checks-and-chat-20261118).

On only where ``enable`` is called (the :8895 demo and its fixtures), and off
with DAYLIGHT_PLANS_FIXES=0. Three parts, all code, no model call:

1. ``set_aside`` / ``restore``: every field advisor-first adds outside the
   sealed contract passes through one projection before inherited strict
   validation. Derived from the existing field tables, so a field added later
   cannot break sending.
2. ``annotate``: each check that is not "Meets" or "Does not meet" carries one
   cause code (needs_person, no_data, not_calculated) and a reason that matches
   it. No new scoring: states, order and groups are unchanged.
3. ``selection``: the plans a person added to compare or chose, on any Plans
   view, as code-supplied published fields for the composer.
"""
import copy
import os
from collections import Counter

from guest_profiles import ProfileError, ENVELOPE_KEYS, STATUSES, bounded

VERSION = 'plans-fixes-v1'
CAUSES = ('needs_person', 'no_data', 'not_calculated')


def switch_on():
    return os.environ.get('DAYLIGHT_PLANS_FIXES', '1').strip().lower() not in {'0', 'off', 'false', 'no'}


def enable(flow):
    flow.plans_fixes = True


def enabled(flow):
    return bool(getattr(flow, 'plans_fixes', False))


# ---------------------------------------------------------------------------
# 1. One projection in front of inherited strict validation.
# ---------------------------------------------------------------------------

def advisor_fields():
    """Every guide field advisor-first writes, from the tables that define them."""
    import conversation_records
    import conversation_planner
    import enrollment_flow
    import medigap_profile
    import natural_state
    from natural_flow import SITUATION_FIELDS
    fields = set(conversation_records.RECORDED_FIELDS) | {conversation_records.SELECTED_PLAN_FIELD}
    fields |= set(medigap_profile.FIELDS.values()) | set(SITUATION_FIELDS.values())
    fields |= set(enrollment_flow.FIELDS) | set(enrollment_flow.PART_FIELDS.values())
    fields |= {enrollment_flow.PATH_FIELD, enrollment_flow.HAVE_FIELD,
               conversation_planner.DECISION_VERSION, conversation_planner.COMPONENT_VERSION}
    fields |= set(natural_state.SENSITIVE_GUIDE_FIELDS)
    return fields


def contract_fields(contract):
    """What the inherited validation accepts (mirrors guest_profiles.validate_guide, read only)."""
    return {f for node in contract['nodes'] for f in node['writes']} | {
        'knowledge.general', 'privacy.persistenceChoice', 'intent.goal', 'subject.role',
        'subject.displayLabel', 'intent.timingQuestion'}


def set_aside(flow, guide):
    """Returns (guide for strict validation, the advisor-first fields set aside).

    Only fields advisor-first defines are set aside, and each keeps the same
    envelope checks the inherited validation applies. A field nobody defines
    stays in the guide and is still rejected."""
    known = advisor_fields() - contract_fields(flow.contract)
    fields = guide.get('fields') if isinstance(guide, dict) else None
    if not isinstance(fields, dict) or not known & set(fields):
        return guide, {}
    strict, extras = copy.deepcopy(guide), {}
    for name in sorted(known & set(fields)):
        envelope = strict['fields'].pop(name)
        if (not isinstance(envelope, dict) or set(envelope) - ENVELOPE_KEYS or envelope.get('status') not in STATUSES
                or envelope.get('confirmation') != 'confirmed_by_user'):
            raise ProfileError('Only confirmed reports or explicit unknowns can be recorded.')
        bounded(envelope.get('value')); bounded(envelope.get('rawText', ''))
        if envelope.get('source') not in {'user_choice', 'confirmed_agent_interpretation', 'user_text', 'location_reference'}:
            raise ProfileError('Unsupported fact provenance.')
        extras[name] = envelope
    return strict, extras


def restore(guide, extras):
    if extras:
        guide['fields'].update(copy.deepcopy(extras))
    return guide


# ---------------------------------------------------------------------------
# 2. Every "Not checked" states its true cause.
# Reason sentences: owner review (evidence packet). They sit on plan cards.
# ---------------------------------------------------------------------------

REASONS = {
    'total_cost': 'Daylight does not calculate this yet.',
    'doctors_missing': 'Needs the doctors you want to keep.',
    'doctors_not_run': 'Doctor check not run yet. Ask Daylight to check your doctors.',
    'network_no_data': 'No network record for your doctor’s office in this plan.',
    'network_no_data_path': 'No network record for your doctor’s office in these plans.',
    'assignment_no_data': 'No Medicare assignment record for at least one selected office.',
    'medicines_missing': 'Needs the medicines you take.',
    'medicines_not_run': 'Medicine check not run yet. Ask Daylight to check your medicines.',
    'formulary_no_data': 'This plan’s drug list has no match for at least one of your medicines.',
    'formulary_no_data_path': 'No drug list here has a match for all your medicines.',
    'medigap_no_data': 'Medigap prices are not available for your details.',
    'part_d_zip': 'Needs your ZIP for drug plan prices.',
    'part_d_no_data': 'Drug plan prices are not available for your area.',
    'advantage_no_data': 'No listed premium for these plans.',
    'not_compared': 'Not compared yet.',
}
MEDIGAP_DETAILS = (('age', 'MG_AGE', 'age'), ('gender', 'MG_SEX', 'sex'), ('tobacco', 'MG_TOBACCO', 'tobacco use'))
LISTED = {'listed_in_network', 'in_network'}


def _set(check, cause, note=None, fields=()):
    check['cause'] = cause
    check['cause_fields'] = list(fields)
    if note:
        check['note'] = note


def _words(items):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def _not_run(reason, field, reported):
    """The check has no result. The person is named only when their detail is
    really open; with the detail in, Daylight simply holds no result yet."""
    return ('no_data', REASONS[reason], []) if field in reported else ('needs_person', REASONS[reason], [field])


def _doctor_cause(inp, rows, kind, reported=()):
    """kind: 'network' (one Advantage plan), 'assignment' (Original Medicare)."""
    if inp.get('doctors') != 'list':
        return 'needs_person', REASONS['doctors_missing'], ['T06']
    rows = list(rows or ())
    if not rows or any(not row for row in rows):
        return _not_run('doctors_not_run', 'RC21', reported)
    return 'no_data', REASONS['network_no_data' if kind == 'network' else 'assignment_no_data'], []


def _medicine_cause(inp, rows, reported=()):
    if inp.get('medicines') != 'yes':
        return 'needs_person', REASONS['medicines_missing'], ['T07']
    if not rows:
        return _not_run('medicines_not_run', 'RC22', reported)
    return 'no_data', REASONS['formulary_no_data'], []


def _medigap_gap(inp):
    gap = inp.get('medigap') or {}
    missing = [(code, word) for key, code, word in MEDIGAP_DETAILS if gap.get(key) is None]
    if not gap.get('zipcode'):
        missing.insert(0, ('T03', 'ZIP'))
    if gap.get('status') != 'ready' and missing:
        return 'needs_person', 'Needs your %s for Medigap prices.' % _words(w for _, w in missing), [c for c, _ in missing]
    return 'no_data', REASONS['medigap_no_data'], []


def _money(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rollup(check, tab, path_notes):
    """A path's unknown check takes the cause its own plans share."""
    found = Counter((c.get('cause'), c['note'], tuple(c.get('cause_fields') or ()))
                    for plan in (tab.get('plans') or {}).values() if plan.get('group') != 'excluded'
                    for c in plan['checks'] if c['id'] == check['id'] and c['state'] == 'unknown' and c.get('cause'))
    if not found:
        return False
    (cause, note, fields), _ = found.most_common(1)[0]
    _set(check, cause, path_notes.get(note, note), fields)
    return True


def annotate(result, inp, *, networks=None, original=(), medicines=None, reported=()):
    """Add a cause code and matching reason to every unknown check. States,
    groups, order and recommended IDs are never touched. ``reported``: the
    check details (RC21 office, RC22 exact medicine) the profile already holds."""
    networks, medicines, reported = networks or {}, medicines or {}, set(reported or ())
    ma, medigap, part_d, path = (result.get(k) or {} for k in ('advantage', 'medigap', 'part_d', 'path'))
    for kind, tab in (('advantage', ma), ('medigap', medigap), ('part_d', part_d)):
        for plan_id, plan in (tab.get('plans') or {}).items():
            for check in plan['checks']:
                if check['state'] != 'unknown':
                    continue
                ident = check['id']
                if ident == 'total_cost':
                    _set(check, 'not_calculated', REASONS['total_cost'])
                elif ident == 'doctors' and kind == 'advantage':
                    _set(check, *_doctor_cause(inp, networks.get(plan_id), 'network', reported))
                elif ident == 'doctors':
                    if 'SELECT' in check['note']:
                        _set(check, 'no_data')
                    else:
                        _set(check, *_doctor_cause(inp, original, 'assignment', reported))
                elif ident == 'medicines':
                    _set(check, *_medicine_cause(inp, medicines.get(plan_id), reported))
                elif ident == 'eligibility':
                    _set(check, 'needs_person', None, ['RC18' if 'Medicaid' in check['note'] else 'RC19'])
                else:                       # travel, pharmacy, drug cost: not in the plan information Daylight holds
                    _set(check, 'no_data')
    sides = {key: plan['checks'] for key, plan in (path.get('plans') or {}).items()}
    mg = _money(medigap.get('minimum_monthly_cents')) if medigap.get('state') == 'ready' else None
    pdp = _money(part_d.get('minimum_monthly_cents')) if part_d.get('state') == 'ready' else None
    ma_low = _money(ma.get('minimum_monthly')) if ma.get('state') == 'ready' else None
    if mg is None:
        original_gap = _medigap_gap(inp)
    elif pdp is None:
        original_gap = (('needs_person', REASONS['part_d_zip'], ['T03']) if inp.get('part_d_status') != 'ready'
                        else ('no_data', REASONS['part_d_no_data'], []))
    else:
        original_gap = None
    path_notes = {REASONS['network_no_data']: REASONS['network_no_data_path'],
                  REASONS['formulary_no_data']: REASONS['formulary_no_data_path']}
    for side, checks in sides.items():
        for check in checks:
            if check['state'] != 'unknown':
                continue
            ident = check['id']
            if ident == 'total_cost':
                _set(check, 'not_calculated', REASONS['total_cost'])
            elif ident == 'lower_monthly':
                # Per side: each path shows what is known for it, never the other path's missing input.
                if side == 'original':
                    if original_gap:
                        _set(check, *original_gap)
                    else:
                        _set(check, 'no_data', 'Lowest listed Medigap plus drug plan: $%s a month. %s'
                             % (format((mg + pdp) / 100, ',.2f'), REASONS['not_compared']))
                elif ma_low is None:
                    _set(check, 'no_data', REASONS['advantage_no_data'])
                else:
                    cause, _, fields = original_gap or ('no_data', '', [])
                    _set(check, cause, 'Lowest listed premium: $%s a month. %s'
                         % (format(ma_low, ',.2f'), REASONS['not_compared']), fields)
            elif ident == 'doctors' and side == 'original':
                _set(check, *_doctor_cause(inp, original, 'assignment', reported))
            elif ident in ('doctors', 'medicines'):
                tab = ma if side == 'advantage' else part_d
                if tab.get('state') != 'ready' and side == 'original':
                    _set(check, *(('needs_person', REASONS['part_d_zip'], ['T03']) if inp.get('part_d_status') != 'ready'
                                  else ('no_data', REASONS['part_d_no_data'], [])))
                elif not _rollup(check, tab, path_notes):
                    _set(check, *(_doctor_cause(inp, (), 'network', reported) if ident == 'doctors' else _medicine_cause(inp, (), reported)))
            elif ident == 'travel_us':
                _set(check, 'not_calculated')       # known per plan type; Daylight does not roll it up to the path
            else:
                _set(check, 'no_data')
    result['causes'] = VERSION
    return result


def learned_checks(checks):
    """Which of the person's doctors and medicines the visit has checked (for the closing summary)."""
    kinds = {row.get('kind') for row in checks or ()}
    return {'doctors': 'doctor_matrix' in kinds or 'doctor' in kinds, 'medicines': 'formulary' in kinds}


# ---------------------------------------------------------------------------
# 3. What the person selected on a Plans view, as code-supplied published fields.
# ---------------------------------------------------------------------------

SELECTION_VIEWS = {'supplement': 'medigap', 'part-d': 'part_d'}
PART_D_LABELS = {'total_premium': 'Monthly premium', 'annual_deductible': 'Yearly drug deductible'}
NOTHING_SELECTED = ('No plan is selected or added to compare on this view. Say so, and offer to compare the plans on screen. '
                    'Do not describe any plan as selected.')
COMPARE_RULE = ('Report differences between these plans from the supplied fields and this visit’s doctor and medicine '
                'check results. Do not rank them or say which is better. For "anything to note", give the differences '
                'that touch the person’s stated priorities and anything still not checked.')


def _dollars(cents):
    return '$%s' % format(int(cents) / 100, ',.2f')


def _part_d_plan(plan):
    fields = {}
    for key, cell in (plan.get('fields') or {}).items():
        if key in PART_D_LABELS and isinstance(cell, dict) and cell.get('state') == 'published' and cell.get('value') is not None:
            value = _dollars(cell['value']) if cell.get('value_encoding') == 'integer_cents' else str(cell['value'])
            fields[key] = {'label': PART_D_LABELS[key], 'state': 'published', 'value': value, 'conditions': [],
                           'reason_codes': [], 'evidence_ref': 'part-d:%s:%s' % (plan['id'], key)}
    name = ' '.join(str(plan[k]) for k in ('name', 'company') if plan.get(k)) or plan['id']
    return {'id': plan['id'], 'name': name, 'type': 'Part D drug plan', 'identity_state': 'published', 'fields': fields}


def _medigap_plan(plan):
    fields = {}
    if plan.get('monthly_cents') is not None:
        fields['monthly_premium'] = {'label': 'Listed monthly premium', 'state': 'published',
                                     'value': _dollars(plan['monthly_cents']), 'conditions': [], 'reason_codes': [],
                                     'evidence_ref': 'medigap:%s:monthly_premium' % plan['id']}
    name = ' '.join(str(v) for v in (plan.get('company'), 'Medigap Plan %s' % plan['variant'] if plan.get('variant') else None) if v)
    return {'id': plan['id'], 'name': name or plan['id'], 'type': 'Medigap policy', 'identity_state': 'published', 'fields': fields}


def selection(flow, guide, record, context, request):
    """Add the selected plans of a Medigap or Part D view, and the chosen plan,
    to the Plans context. Identities are checked against what code reads now."""
    import conversation_records
    view = (context.get('navigation') or {}).get('view')
    ids = request.get('selection') or []
    product = SELECTION_VIEWS.get(view)
    if ids and not product:
        raise ProfileError('Use the plan identities visible in this Plans step.', 422)
    if (not isinstance(ids, list) or len(ids) > 3 or len(set(map(str, ids))) != len(ids)
            or any(not isinstance(i, str) or not 1 <= len(i) <= 120 for i in ids)):
        raise ProfileError('Use listed plan identities.', 422)
    if ids:
        reader = getattr(flow, 'plans_selection_read', None)
        listed = {plan['id']: plan for plan in (reader(product, guide, record) if reader else ())}
        if any(i not in listed for i in ids):
            raise ProfileError('Use listed plan identities.', 422)
        build = _part_d_plan if product == 'part_d' else _medigap_plan
        context['plans'] = [build(listed[i]) for i in ids]
        context['compared_ids'] = list(ids)
    chosen = flow.value(guide, conversation_records.SELECTED_PLAN_FIELD)
    context['chosen_plan'] = ({k: chosen[k] for k in ('product', 'plan_id', 'name') if k in chosen}
                              if isinstance(chosen, dict) else None)
    selected = bool(context.get('compared_ids') or context.get('selected_id') or context['chosen_plan'])
    context['selection_rule'] = COMPARE_RULE if selected else NOTHING_SELECTED
    return context
