"""Independent, deterministic comparison and gated personal recommendations."""
from decimal import Decimal
from comparison_evidence import canonical_sha256
from plans_authority import METHOD, permits
from plans_adapters import METRICS, CHECKS, metric_payload, work_items


def method_payload(plans):
    return {'method': METHOD, 'metrics': list(METRICS), 'checks': list(CHECKS),
            'offering_ids': [p['id'] for p in plans]}


def _groups(ordered):
    groups = {}
    for values, identifier in ordered:
        groups.setdefault(values, []).append(identifier)
    return [ids for ids in groups.values() if len(ids) > 1]


def reference_ordering(order, plans, metrics, *, scope_supported):
    """Arithmetic over published terms, explicitly not personal plan suitability."""
    result = {'state': 'held', 'purpose': 'published_term_comparison', 'ordered_ids': [],
              'first_three': [], 'tie_groups': [], 'unranked_ids': [], 'reason_codes': [],
              'priority_order': list(order), 'personal_recommendation': False,
              'limitation': 'Orders available published terms only. Restrictions and personal fit are not cleared; missing values are unranked, not worse.'}
    if not scope_supported:
        result['reason_codes'].append('REQUESTED_SCOPE_UNSUPPORTED')
    if not order:
        result['reason_codes'].append('EXPLICIT_PRIORITY_ORDER_REQUIRED')
    if result['reason_codes']:
        return result
    ordered = []
    for plan in plans:
        values = [metrics[plan['id']][key] for key in order]
        if all(v['state'] == 'available' for v in values):
            ordered.append((tuple(Decimal(v['amount']) for v in values), plan['id']))
        else:
            result['unranked_ids'].append(plan['id'])
    ordered.sort()
    result.update(state='available' if ordered else 'no_supported_terms',
                  ordered_ids=[identifier for _, identifier in ordered],
                  first_three=[identifier for _, identifier in ordered[:3]], tie_groups=_groups(ordered))
    return result


def recommend(profile_digest, order, plans, authority, *, metrics, checks, scope_supported=True):
    if len(set(order)) != len(order) or any(key not in METRICS for key in order):
        raise ValueError('INVALID_PRIORITY_ORDER')
    result = {'method': METHOD, 'state': 'held', 'top_three': [], 'tie_groups': [],
              'priority_order': list(order), 'reason_codes': [], 'plans': [],
              'work_items': work_items(checks), 'scope': 'retained_2026_collier_ma_only',
              'limitation': 'A confirmed priority comparison within the retained MA listings, not a total-cost estimate or an all-market recommendation.'}
    if not scope_supported:
        result['reason_codes'].append('REQUESTED_SCOPE_UNSUPPORTED')
    if not order:
        result['reason_codes'].append('EXPLICIT_PRIORITY_ORDER_REQUIRED')
    if not permits(authority, 'recommendation_method', method_payload(plans)):
        result['reason_codes'].append('RECOMMENDATION_REVIEW_REQUIRED')
    eligible, unknown = [], []
    for plan in plans:
        identifier = plan['id']
        plan_checks = checks[identifier]
        values, missing = [], []
        for key in order:
            fact = metrics[identifier][key]
            accepted = (fact['state'] == 'available'
                        and permits(authority, 'ranking_metric', metric_payload(identifier, key, fact)))
            values.append(Decimal(fact['amount']) if accepted else None)
            if not accepted:
                missing.append(key)
        states = [v['state'] for v in plan_checks.values()]
        state = ('known_conflict' if 'known_conflict' in states else
                 'needs_check' if missing or any(s not in {'meets', 'not_required'} for s in states) else 'meets')
        result['plans'].append({'id': identifier, 'state': state, 'checks': plan_checks,
                               'missing_metrics': missing})
        if state == 'meets':
            eligible.append((tuple(values), identifier))
        elif state == 'needs_check':
            # Nonnegative money dimensions give a safe optimistic bound. An
            # unresolved lower-ranked plan cannot block a stronger top three.
            unknown.append((tuple(v if v is not None else Decimal(0) for v in values), identifier))
    eligible.sort()
    contenders = [identifier for values, identifier in unknown
                  if len(eligible) < 3 or values <= eligible[2][0]]
    if contenders:
        result['reason_codes'].append('MATERIAL_UNKNOWN_CONTENDER')
    result['unresolved_contender_ids'] = contenders
    result['supported_candidate_ids'] = [identifier for _, identifier in eligible]
    if not result['reason_codes']:
        result['state'] = 'supported' if eligible else 'no_supported_match'
        result['top_three'] = [identifier for _, identifier in eligible[:3]]
        result['tie_groups'] = _groups(eligible)
        result['reasons'] = [{'id': identifier, 'ordered_values': [str(v) for v in values],
                             'basis': list(order), 'limitation': result['limitation']}
                            for values, identifier in eligible[:3]]
    result['decision_id'] = canonical_sha256({'profile': profile_digest,
        'release': authority.get('release_id'), 'decision': result})
    return result
