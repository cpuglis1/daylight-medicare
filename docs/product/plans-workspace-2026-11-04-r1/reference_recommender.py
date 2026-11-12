"""D92 strict-priority recommendation reference. FICTIONAL INPUTS ONLY.

No API, model, store, acceptance loader or real-offering ranking. This makes the
proposed heuristic executable without turning r13 display candidates into advice.
Production must use trusted accepted findings and the SPEC.md admission contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

VERSION = 'd92-fictional-priority-reference-r1'
METRICS = ('monthly_plan_premium', 'in_network_medical_limit')
State = Literal['meets', 'known_conflict', 'needs_check', 'outside_scope']


@dataclass(frozen=True)
class Case:
    profile_revision: str
    confirmed_revision: str | None
    priorities: tuple[str, ...]
    checks: tuple[str, ...]
    origin: str = 'fictional_fixture'
    year: int = 2026
    county_fips: str = '12021'


@dataclass(frozen=True)
class Plan:
    id: str
    checks: tuple[tuple[str, State], ...]
    metrics: tuple[tuple[str, Decimal | None], ...]
    origin: str = 'fictional_fixture'
    year: int = 2026
    county_fips: str = '12021'


def shortlist(case: Case, plans: tuple[Plan, ...]) -> dict:
    """Demonstrate constraint partitioning and lexicographic ordering.

    Checks are fictional pre-evaluated predicates, never inferred insurance
    eligibility. Unknown contenders hold the top-three result. ID breaks exact
    ties for presentation only, with all tied plans returned separately.
    """
    if type(case) is not Case or any(type(p) is not Plan for p in plans):
        raise ValueError('TYPED_FIXTURE_REQUIRED')
    if (case.origin != 'fictional_fixture'
            or any(p.origin != 'fictional_fixture' or not p.id.startswith('fictional:') for p in plans)):
        raise ValueError('REAL_PLAN_RECOMMENDATIONS_NOT_IMPLEMENTED')
    if not case.profile_revision or not plans or len({p.id for p in plans}) != len(plans):
        raise ValueError('INVALID_FIXTURE_IDENTITY')
    if (len(set(case.priorities)) != len(case.priorities)
            or any(k not in METRICS for k in case.priorities)
            or len(set(case.checks)) != len(case.checks)
            or not {'eligibility', 'drug_arrangement'}.issubset(case.checks)):
        raise ValueError('INVALID_DECISION_BASIS')
    if any(p.year != case.year or p.county_fips != case.county_fips for p in plans):
        raise ValueError('SCOPE_MISMATCH')
    result = {'version': VERSION, 'consumer_usable': False, 'mode': 'fictional_only',
              'profile_revision': case.profile_revision, 'top_three': [],
              'priority_order': list(case.priorities), 'plans': [], 'tie_groups': [],
              'reason_codes': [], 'state': 'held'}
    eligible = []
    for p in sorted(plans, key=lambda p: p.id):
        if len(dict(p.checks)) != len(p.checks) or len(dict(p.metrics)) != len(p.metrics):
            raise ValueError('DUPLICATE_FINDING')
        checks, metrics = dict(p.checks), dict(p.metrics)
        if (any(v not in {'meets', 'known_conflict', 'needs_check', 'outside_scope'} for v in checks.values())
                or set(metrics) - set(METRICS)
                or any(v is not None and (type(v) is not Decimal or not v.is_finite() or v < 0)
                       for v in metrics.values())):
            raise ValueError('INVALID_FINDING')
        required = {k: checks.get(k, 'needs_check') for k in case.checks}
        missing = [k for k in case.priorities if metrics.get(k) is None]
        if 'outside_scope' in required.values():
            state = 'outside_scope'
        elif 'known_conflict' in required.values():
            state = 'known_conflict'
        elif 'needs_check' in required.values() or missing:
            state = 'needs_check'
        else:
            state = 'meets'
        row = {'id': p.id, 'state': state, 'checks': required,
               'missing_priority_fields': missing,
               'ordered_values': {k: str(metrics[k]) if metrics.get(k) is not None else None
                                  for k in case.priorities}}
        result['plans'].append(row)
        if state == 'meets':
            eligible.append((tuple(metrics[k] for k in case.priorities), p.id))
    if case.confirmed_revision != case.profile_revision:
        result['reason_codes'].append('CONFIRM_CURRENT_PROFILE')
    if not case.priorities:
        result['reason_codes'].append('EXPLICIT_PRIORITY_ORDER_REQUIRED')
    if any(p['state'] == 'needs_check' for p in result['plans']):
        result['reason_codes'].append('MATERIAL_UNKNOWN_CONTENDER')
    if result['reason_codes']:
        return result
    ordered = sorted(eligible)
    result['top_three'] = [id for vector, id in ordered[:3]]
    result['state'] = 'fictional_shortlist' if ordered else 'no_supported_candidate'
    groups = {}
    for vector, id in ordered:
        groups.setdefault(vector, []).append(id)
    result['tie_groups'] = [ids for ids in groups.values() if len(ids) > 1]
    result['reason_codes'] = ['EXPLICIT_PRIORITY_ORDER', 'ID_ORDER_WITHIN_EQUAL_VECTORS']
    return result


def demo():
    case = Case('fictional-profile-v1', 'fictional-profile-v1', METRICS,
                ('eligibility', 'drug_arrangement', 'doctor_site', 'medicines'))
    checks = tuple((k, 'meets') for k in case.checks)
    values = [('A', '0', '4500'), ('B', '0', '6500'), ('C', '25', '3500'), ('D', '45', '5000')]
    plans = tuple(Plan('fictional:' + id, checks, tuple(zip(METRICS, map(Decimal, (premium, limit)))))
                  for id, premium, limit in values)
    return case, plans


if __name__ == '__main__':
    import json
    print(json.dumps(shortlist(*demo()), indent=2))
