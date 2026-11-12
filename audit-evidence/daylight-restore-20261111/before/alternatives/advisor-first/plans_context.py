"""Minimized, Send-bound view context; browser observations are not preferences."""
from comparison_evidence import canonical_sha256
from guest_profiles import ProfileError

POLICY = 'plans-context-v1'
KEYS = {'version', 'reviewToken', 'viewDigest', 'visibleIds', 'comparedIds', 'selectedId', 'field', 'mode'}


def rehydrate(service, owner, request, handoff):
    if (not isinstance(request, dict) or set(request) != KEYS or request['version'] != POLICY
            or not isinstance(request['mode'], str) or request['mode'] not in {'all', 'recommended', 'compare', 'costs'}):
        raise ProfileError('Use the current Plans view context.', 422)
    if request['reviewToken'] is not None and not isinstance(request['reviewToken'], str):
        raise ProfileError('Use the current reviewed-profile receipt.', 422)
    view = service.for_handoff(owner, handoff)
    if request['viewDigest'] != view['view_digest']:
        raise ProfileError('The plans or your priorities changed. Refresh Plans before sending.', 409)
    plans = {p['id']: p for p in view['plans']}
    for key, bound in [('visibleIds', 12), ('comparedIds', 3)]:
        ids = request[key]
        if (not isinstance(ids, list) or len(ids) > bound
                or any(not isinstance(i, str) or i not in plans for i in ids) or len(set(ids)) != len(ids)):
            raise ProfileError('Use listed plan identities.', 422)
    selected = request['selectedId']
    if selected is not None and (not isinstance(selected, str) or selected not in plans):
        raise ProfileError('Use a listed plan identity.', 422)
    field = request['field']
    if field is not None and (not selected or not isinstance(field, str) or field not in plans[selected]['fields']):
        raise ProfileError('Use a displayed plan field.', 422)
    ids = list(dict.fromkeys(([selected] if selected else []) + request['comparedIds'] + request['visibleIds']))[:16]
    context = {'version': POLICY, 'view_digest': view['view_digest'],
        'input_digest': handoff['inputDigest'] if handoff else None, 'catalog_sha256': view['catalog_sha256'],
        'projection_digest': view['projection_digest'],
        'decision_evidence_digest': view['decision_evidence_digest'],
        'publication': view['publication'],
        'scope': view['scope'], 'requested_scope': handoff['scope'] if handoff else None,
        'scope_supported': view['recommendation']['scope_supported'],
        'selected_id': selected, 'focused_field': field, 'mode': request['mode'],
        'visible_ids': list(request['visibleIds']), 'compared_ids': list(request['comparedIds']),
        'attention_is_not_preference': True, 'plans': [], 'reference_notice': REFERENCE_NOTICE,
        'recommendation': {k: view['recommendation'][k] for k in
                           ('state', 'top_three', 'priority_order', 'reason_codes')}}
    for identifier in ids:
        plan = plans[identifier]
        # Only server-projected fields; no hidden candidates, profile or browser prose.
        # A selected or compared plan carries every server-projected field the
        # person can see in its details or the compare table (held fields keep
        # no value). Other visible plans carry identity only.
        focus = identifier == selected or identifier in request['comparedIds']
        context['plans'].append({'id': identifier, 'name': plan['name'], 'type': plan.get('type') if focus else None,
            'identity_state': plan['identity_state'], 'fields': {
                key: {k: cell[k] for k in ('label', 'state', 'value', 'conditions', 'reason_codes', 'evidence_ref')}
                for key, cell in plan['fields'].items() if focus}})
    return context


REFERENCE_MARKER = ' (published 2026 term; shown for review, not yet confirmed by MidMorning)'
REFERENCE_NOTICE = ('Plan figures marked "shown for review" are the published 2026 terms as filed; MidMorning has not yet '
                    'finished its own check of them. Say so once in plain words when you use them; never as '
                    '"independent consumer review is pending". Refer to plans by the name shown on the screen '
                    '(for example "CareFlex FL-34"), not by contract number.')


def context_evidence(context):
    """Consumer-accepted facts or explicitly authorized local reference context."""
    # Reference-state cells carry one short reader-facing marker; the full
    # explanation lives once in ``context['reference_notice']`` (Nov 9, 2026:
    # the old per-cell sentence was echoed to readers as "independent consumer
    # review is pending" and tripled the size of a three-plan comparison).
    marker = REFERENCE_MARKER
    return [{'id': cell['evidence_ref'], 'text': f"{plan['name']} ({plan['id']}) {cell['label']}: {cell['value']}. "
              + ' '.join(cell['conditions'])
              + (marker if cell['state'] == 'reference' else ''), 'catalog_sha256': context['catalog_sha256'],
              'offering_id': plan['id'], 'scope': context['scope'], 'kind': 'published_plan_field',
              'review_state': cell['state']}
            for plan in context['plans'] for cell in plan['fields'].values()
            if cell['state'] in {'published', 'reference', 'not_applicable'}] + [
        # The published listing type (HMO, PPO, ...) of a plan the person is
        # comparing or has selected. A label only: it carries no network rules.
        {'id': f"plan-type:{plan['id']}", 'text': f"{plan['name']} ({plan['id']}) published plan type: {plan['type']}.{marker}",
         'catalog_sha256': context['catalog_sha256'], 'offering_id': plan['id'], 'scope': context['scope'],
         'kind': 'published_plan_listing', 'review_state': 'reference'}
        for plan in context['plans'] if plan.get('type') and plan['fields']]


def public_binding(context):
    return {k: context[k] for k in ('version', 'view_digest', 'projection_digest', 'decision_evidence_digest',
                                  'input_digest', 'selected_id', 'focused_field')}
