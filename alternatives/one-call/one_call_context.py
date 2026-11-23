"""Current, server-owned evidence for a deliberate one-call Send.

No browser prose, hidden candidates, cached network conclusions or new model call.
The existing Plans permission and source readers remain the authority.
"""
from copy import deepcopy

from plan_review import input_digest
from plans_context import context_evidence
import plans_fixes


def plans(flow, guide, record):
    context = deepcopy(flow._plans_context.get())
    if not context:
        return None, []
    context['profile_changed'] = bool(context['input_digest'] and
                                      input_digest(guide, record) != context['input_digest'])
    if context['profile_changed']:
        context['recommendation'] = {'state': 'held', 'top_three': [], 'priority_order': [],
                                     'reason_codes': ['CONFIRM_CURRENT_PROFILE']}
    selection = context.pop('selection_request', None)
    if plans_fixes.enabled(flow):
        plans_fixes.selection(flow, guide, record, context, selection or {})
    return context, context_evidence(context)


def research(flow, owner, guide, record, plans_context):
    controller = flow.conversation_checks
    if not controller:
        return None
    # Reconcile through the real controller: correction, STOP and expiry remove
    # stale findings. Never use the short display view or an old transcript card.
    view = controller.reconcile(owner, guide, record)
    from conversation_checks import doctor_reports, digest, scope_profile
    from daylight_data.serving.pilot_doctors import place_office
    state = controller.visits.get(owner) or {}
    scope = scope_profile(guide, record)
    confirmed = []
    if scope['status'] == 'ready':
        for key, report in doctor_reports(guide, record).items():
            detail = (state.get('doctors') or {}).get(key) or {}
            if (detail.get('stamp') == digest([state.get('subject'), scope['inputs'], report])
                    and detail.get('doctor') and detail.get('office')):
                confirmed.append({'name': detail['doctor']['label'], 'identity_confirmed': True,
                                  'office_parts': place_office(detail['office']['address'], report.get('location'))})
    focused = set((plans_context or {}).get('compared_ids') or [])
    if (plans_context or {}).get('selected_id'):
        focused.add(plans_context['selected_id'])
    rows = []
    for result in view.get('results') or []:
        if result.get('kind') not in ('doctor', 'doctor_matrix', 'formulary'):
            continue
        row = {key: deepcopy(result[key]) for key in
               ('kind', 'name', 'office', 'office_parts', 'date', 'state', 'details', 'original_medicare', 'evidence_date')
               if key in result}
        if result['kind'] in ('doctor', 'doctor_matrix'):
            row['identity_confirmed'] = True
        if focused:
            row['plans'] = {key: deepcopy(value) for key, value in (result.get('plans') or {}).items() if key in focused}
        rows.append(row)
    question = view.get('question') or {}
    return {'confirmed_doctors': confirmed, 'results': rows,
            'pending': {key: question[key] for key in ('kind', 'field', 'question') if key in question},
            'identity_is_not_network_participation': True}
