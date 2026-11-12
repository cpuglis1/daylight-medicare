"""Pure, source-held comparison responses over the existing profile adapter.

This is an additive decision/evidence layer, not another intake controller. Only
questions supplied by the session-owning controller can be selected. It performs
no network, store, AI, release, enrollment or source-acceptance operation.
"""
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from itertools import combinations
import copy
import re

from comparison_evidence import (EVIDENCE_VERSION, canonical_sha256,
                                 purpose_authorities, read_snapshot, reject_economic_fields)


CONTRACT_ID = 'daylight-comparison-response-r1'
RULE_VERSION = 'daylight-comparison-structural-r2'
METHOD_VERSION = 'condition-aware-dimensions-r1'
QUESTION_IDS = tuple([f'T{x:02d}' for x in range(1, 11)]
                     + [f'RC{x:02d}' for x in range(1, 29)]
                     + ['RC11.C1', 'RC16.C1', 'RC16.C2'])
ALIASES = {'RC11.C1': 'RC11', 'RC16.C1': 'RC16', 'RC16.C2': 'RC16'}
TASK_CAPABILITIES = {
    'browse': ('availability',), 'compare': ('availability', 'route_comparison', 'provider_fit', 'drug_coverage'),
    'review': ('route_comparison', 'provider_fit', 'drug_coverage'), 'timing': ('timing',),
    'providers': ('provider_fit',), 'drug_coverage': ('drug_coverage',),
    'drug_pricing': ('drug_pricing',), 'medigap': ('medigap_rights',),
    'snp': ('snp',), 'costs': ('drug_pricing',), 'learn': (), '': (),
}
DIMENSIONS = {
    'coverage_structure': ('Coverage structure', ('T05', 'RC04', 'RC07', 'RC26'), 'R03'),
    'monthly_plan_premium': ('Published plan premium', ('RC03',), 'R11'),
    'provider_access': ('Doctors and hospitals', ('T06', 'RC21'), 'R06'),
    'drug_coverage': ('Medicine coverage and restrictions', ('T07', 'RC22', 'RC24'), 'R07'),
    'fill_price': ('Specified medicine fill cost', ('T07', 'RC22', 'RC23', 'RC18'), 'R08'),
    'routine_away_access': ('Routine care away from home', ('T08', 'RC20'), 'R09'),
    'eligibility_transition': ('Eligibility and transition checks', ('T04', 'RC02', 'RC03', 'RC04', 'RC05', 'RC06', 'RC07', 'RC08',
        'RC09', 'RC10', 'RC11', 'RC12', 'RC13', 'RC14', 'RC15', 'RC16', 'RC17', 'RC18',
        'RC19', 'RC26', 'RC27', 'RC11.C1', 'RC16.C1', 'RC16.C2'), 'R04'),
}
TRANSITION_QUESTIONS = {
    'timing': ('T04', 'RC04', 'RC05', 'RC06', 'RC08', 'RC09', 'RC10', 'RC11', 'RC12',
               'RC13', 'RC14', 'RC26', 'RC27', 'RC11.C1'),
    'medigap': ('RC02', 'RC05', 'RC06', 'RC07', 'RC11', 'RC15', 'RC16', 'RC17', 'RC16.C1', 'RC16.C2'),
    'snp': ('RC02', 'RC03', 'RC04', 'RC18', 'RC19'),
}
TASK_DIMENSIONS = {
    'browse': ('coverage_structure', 'monthly_plan_premium'), 'learn': ('coverage_structure',),
    'compare': tuple(DIMENSIONS), 'review': tuple(DIMENSIONS), '': ('coverage_structure',),
    'timing': ('coverage_structure', 'eligibility_transition'),
    'providers': ('provider_access', 'routine_away_access'), 'drug_coverage': ('drug_coverage',),
    'drug_pricing': ('drug_coverage', 'fill_price'),
    'medigap': ('coverage_structure', 'monthly_plan_premium', 'eligibility_transition'),
    'snp': ('coverage_structure', 'eligibility_transition'),
    'costs': ('monthly_plan_premium', 'fill_price'),
}
UNRESOLVED_REPORTS = {'unanswered', 'unknown', 'deferred', 'declined', 'tentative',
                      'conflicting', 'stale', 'superseded'}
KNOWN_REPORTS = {'reported', 'explicit_none'}
REF_KEYS = ('path', 'item_id', 'subject_id', 'scope', 'report_revision', 'record_revision')
PRIORITY_DIMENSIONS = {
    'doctors': ('provider_access',), 'drugs': ('drug_coverage', 'fill_price'),
    'travel': ('routine_away_access',), 'total_cost': ('monthly_plan_premium', 'fill_price'),
    'bills': ('monthly_plan_premium', 'fill_price'), 'other': (),
}
# These meanings explicitly concern the present request/arrangement/care list.
# This is a report-reuse guard, not a required-input or Medicare rule classifier.
# Chronology (including RC11/RC16 aliases) keeps its own historical meaning.
CURRENT_QUESTION_IDS = frozenset({
    'T01', 'T02', 'T05', 'T06', 'T07', 'T09', 'T10', 'RC01', 'RC04', 'RC07',
    'RC09', 'RC18', 'RC21', 'RC22', 'RC23', 'RC24', 'RC25', 'RC26', 'RC27',
})


class ComparisonError(ValueError):
    """A fixed-code structural failure without customer/source values."""


def _ref(value):
    return {key: value.get(key) for key in REF_KEYS}


def _ref_key(value):
    return tuple(value.get(key) for key in REF_KEYS)


def _validate_profile(profile):
    if not isinstance(profile, Mapping):
        raise ComparisonError('SERVER_PROFILE_ADAPTER_REQUIRED')
    reject_economic_fields(profile)
    binding, questions, facts = profile.get('profile_binding'), profile.get('questions'), profile.get('facts')
    if (not isinstance(binding, Mapping) or not isinstance(questions, list) or not isinstance(facts, list)
            or len(questions) != 41 or len(facts) > 5000
            or any(not isinstance(q, dict) for q in questions)
            or {q.get('id') for q in questions} != set(QUESTION_IDS)):
        raise ComparisonError('PROFILE_CONTRACT_MISMATCH')
    for q in questions:
        if (q.get('parent_alias_of') != ALIASES.get(q['id'])
                or not isinstance(q.get('canonical_paths'), list)
                or not isinstance(q.get('fact_refs'), list)):
            raise ComparisonError('PROFILE_QUESTION_BINDING_MISMATCH')
    for fact in facts:
        if (not isinstance(fact, dict) or not isinstance(fact.get('ref'), dict)
                or not isinstance(fact['ref'].get('path'), str)
                or fact.get('report_state') not in UNRESOLVED_REPORTS | KNOWN_REPORTS):
            raise ComparisonError('PROFILE_FACT_MISMATCH')
    try:
        canonical_sha256({'binding': dict(binding), 'questions': questions, 'facts': facts,
                          'scope': profile.get('requested_scope'), 'extensions': profile.get('extensions'),
                          'integrity': profile.get('integrity_issues')})
    except (TypeError, ValueError):
        raise ComparisonError('NON_JSON_PROFILE') from None


def evaluate_conditions(condition_set):
    """Four-valued structural logic; incomplete/empty sets never prove absence.

    This evaluates only supplied predicate evaluations. It does not interpret
    Medicare source prose or establish an accepted executable policy.
    """
    if (not isinstance(condition_set, dict) or condition_set.get('completeness') != 'complete'
            or condition_set.get('missing_predicates') or not condition_set.get('root')):
        return 'unknown'

    def visit(node, depth=0):
        if not isinstance(node, dict) or depth > 32:
            return 'unknown'
        op = node.get('op')
        if op == 'predicate':
            return node.get('evaluation') if node.get('evaluation') in {'true', 'false', 'unknown', 'conflicting'} else 'unknown'
        children = node.get('children')
        if not isinstance(children, list) or not children or len(children) > 200:
            return 'unknown'
        values = [visit(child, depth + 1) for child in children]
        if 'conflicting' in values:
            return 'conflicting'
        if op == 'not' and len(values) == 1:
            return {'true': 'false', 'false': 'true'}.get(values[0], 'unknown')
        if op == 'and':
            return 'false' if 'false' in values else 'unknown' if 'unknown' in values else 'true'
        if op == 'or':
            return 'true' if 'true' in values else 'unknown' if 'unknown' in values else 'false'
        return 'unknown'

    return visit(condition_set['root'])


def compare_dimension_values(left, right):
    """Exact differences within a declared common basis; never a fit score.

    Caller must separately establish conditions/method/output authority. Keeping
    this pure helper separate lets fictional tests exercise arithmetic without
    creating any production release or fake personal recommendation.
    """
    unresolved = {'relation': 'unresolved', 'difference': None, 'reason_codes': ['INCOMPARABLE_BASIS']}
    if not isinstance(left, dict) or not isinstance(right, dict):
        return unresolved
    kind = left.get('type')
    if kind != right.get('type') or kind not in {'decimal', 'category'}:
        return unresolved
    basis = ('currency', 'unit', 'period', 'cost_type', 'scope_key', 'population_basis',
             'network', 'channel', 'phase', 'included_components', 'excluded_components', 'assumptions')
    if (any(key not in left or key not in right or left[key] != right[key] for key in basis)
            or not left.get('unit') or not left.get('period') or not left.get('scope_key')
            or not left.get('population_basis')):
        return unresolved
    if kind == 'category':
        if left.get('value') is None or right.get('value') is None:
            return unresolved
        return {'relation': 'equal' if left['value'] == right['value'] else 'different',
                'difference': None, 'reason_codes': []}
    try:
        if not isinstance(left.get('amount'), str) or not isinstance(right.get('amount'), str):
            return unresolved
        if any(not re.fullmatch(r'-?\d{1,80}(?:\.\d{1,40})?', value)
               for value in (left['amount'], right['amount'])):
            return unresolved
        a, b = Decimal(left['amount']), Decimal(right['amount'])
        if not a.is_finite() or not b.is_finite():
            return unresolved
    except (InvalidOperation, ValueError):
        return unresolved
    with localcontext() as context:
        context.prec = max(len(left['amount']), len(right['amount'])) + 4
        difference = str(a - b)
    return {'relation': 'equal' if a == b else 'left_lower' if a < b else 'left_higher',
            'difference': difference, 'reason_codes': []}


def _question_facts(question, facts):
    keys = {_ref_key(ref) for ref in question['fact_refs']}
    return [fact for fact in facts if _ref_key(fact['ref']) in keys]


def _bound_report(fact, subject):
    return (fact['ref'].get('subject_id') == subject
            and fact.get('usable_for_bound_subject') is True
            and fact.get('usable_as_report') is True
            and fact['report_state'] in KNOWN_REPORTS)


def _dimension_question_ids(dimension, task):
    if dimension == 'eligibility_transition' and task in TRANSITION_QUESTIONS:
        return TRANSITION_QUESTIONS[task]
    return DIMENSIONS[dimension][1]


def _relevant(question, task):
    return (question['id'] in {'T01', 'RC01', 'RC28'}
            or bool(set(question.get('source_capabilities', ())) & set(TASK_CAPABILITIES.get(task, ())))
            or task in {'compare', 'review', 'costs'} and question['id'] in {'T09', 'T10', 'RC25'})


def _question_scope_compatible(identifier, fact):
    """Reuse a report only for the same declared time meaning.

    Keep unscoped missing/uncertain dispositions eligible for the existing
    controller's clarification/defer handling; never upgrade them to reports.
    Historical deferral cannot suppress a current-meaning target. Actual Part B
    and Advantage chronology accept history, while a desired start accepts an
    intention and never substitutes for actual enrollment history.
    """
    identifier = ALIASES.get(identifier, identifier)
    scope = fact['ref'].get('scope')
    if scope == 'unknown' and fact['report_state'] not in KNOWN_REPORTS:
        return True
    if identifier in CURRENT_QUESTION_IDS:
        return scope == 'current'
    if identifier == 'T04':
        return scope in {'current', 'intended'}
    if identifier in {'RC05', 'RC16'}:
        return scope in {'current', 'historical'}
    return True


def _account_questions(questions, facts, task, next_id, subject, baseline_dispositions=None):
    rows = []
    by_id = {q['id']: q for q in questions}
    dispositions = baseline_dispositions if isinstance(baseline_dispositions, dict) else {}
    for identifier in QUESTION_IDS:
        q = by_id[identifier]
        related = _question_facts(q, facts)
        active = [f for f in related if _question_scope_compatible(identifier, f)]
        states = sorted({f['report_state'] for f in active}) or ['unanswered']
        relevant = _relevant(q, task) or identifier == next_id
        known = any(_bound_report(f, subject) for f in active)
        disposition = dispositions.get(identifier)
        if identifier == 'T02':
            known = any(f['report_state'] in KNOWN_REPORTS and f.get('usable_as_report') is True for f in active)
        if identifier in ALIASES:
            state = 'alias_reused' if known else 'not_relevant'
        elif not relevant:
            state = 'not_relevant'
        elif disposition in {'unknown', 'deferred', 'declined'}:
            state = 'deferred_for_requested_finding'
        elif any(x in states for x in ('conflicting', 'tentative', 'stale')):
            state = 'clarification_needed'
        elif all(x in {'unknown', 'deferred', 'declined'} for x in states):
            state = 'deferred_for_requested_finding'
        elif known:
            state = 'used'
        elif q.get('source_requiredness') in {'optional_preference', 'optional_learning'}:
            state = 'optional_unset'
        else:
            state = 'missing_for_requested_finding'
        rows.append({'question_id': identifier, 'accounting_state': state,
                     'parent_alias_of': ALIASES.get(identifier),
                     'report_states': sorted({f['report_state'] for f in related}) or ['unanswered'],
                     'active_report_states': states,
                     'report_refs': [_ref(f['ref']) for f in related],
                     'bound_subject_report_refs': [_ref(f['ref']) for f in active if _bound_report(f, subject)],
                     'out_of_scope_report_refs': [_ref(f['ref']) for f in related
                                                   if not _question_scope_compatible(identifier, f)],
                     'relevant_to_requested_task': relevant,
                     'additional_alias_obligation': False})
    return rows


def _input_state(facts):
    states = {f['report_state'] for f in facts}
    for state in ('conflicting', 'stale', 'tentative', 'deferred', 'declined', 'unknown'):
        if state in states:
            return state
    known = [f for f in facts if f.get('usable_for_bound_subject') is True
             and f.get('usable_as_report') is True and f['report_state'] in KNOWN_REPORTS]
    # There is no reviewed universal required-fields classifier in this slice.
    # Existing reports are useful, but must not invent sufficiency from counts.
    return 'partial' if known else 'unanswered'


def _dimension_facts(dimension, item, questions, facts, subject, task):
    ids = _dimension_question_ids(dimension, task)
    refs = set()
    for q in questions:
        if q['id'] in ids:
            refs.update(_ref_key(r) for r in q['fact_refs'])
    selected = [f for f in facts if _ref_key(f['ref']) in refs and _bound_report(f, subject)]
    if dimension in {'coverage_structure', 'provider_access', 'drug_coverage', 'fill_price'}:
        selected = [fact for fact in selected if fact['ref'].get('scope') == 'current']
    if item is not None:
        selected = [f for f in selected if f['ref'].get('item_id') in {None, item}]
    return selected


def _items(dimension, facts, subject):
    if dimension not in {'provider_access', 'drug_coverage', 'fill_price'}:
        return [None]
    names = ('RC21', 'needs.providers') if dimension == 'provider_access' else ('RC22', 'RC23', 'needs.medications')
    ids = {f['ref'].get('item_id') for f in facts if f['ref'].get('item_id')
           and any(name in f['ref']['path'] for name in names)
           and f['ref'].get('scope') == 'current'
           and _bound_report(f, subject)}
    return sorted(ids) or [None]


def _preference_context(profile, facts, subject):
    """Explicit owner-bound reports for emphasis, never inferred fit features."""
    selected = [f for f in facts if _bound_report(f, subject)
                and f['ref'].get('scope') == 'current'
                and (f['ref']['path'] in {'guide.fields.needs.costPreference', 'guide.fields.needs.priorities',
                                         'guide.fields.needs.priorityOther'}
                     or f['ref']['path'].startswith('readiness.facts.RC25.value.'))]
    priorities = next((f for f in selected if f['ref']['path'] == 'guide.fields.needs.priorities'), None)
    topics = sorted({value for value in (priorities['value'] if priorities and isinstance(priorities['value'], list) else [])
                     if isinstance(value, str) and value in PRIORITY_DIMENSIONS})
    emphasized = {dimension for topic in topics for dimension in PRIORITY_DIMENSIONS[topic]}
    cost = next((f for f in selected if f['ref']['path'] == 'guide.fields.needs.costPreference'), None)
    cost_preference = cost['value'] if cost and isinstance(cost['value'], str) and cost['value'] in {'lower_monthly', 'predictable', 'no_preference'} else None
    if cost_preference in {'lower_monthly', 'predictable'}:
        emphasized.update(('monthly_plan_premium', 'fill_price'))
    reasons = []
    for reason in profile.get('extensions', {}).get('agenda', {}).get('priorityReasons', []):
        if (priorities and isinstance(reason, dict) and reason.get('topic') in topics
                and reason.get('subject') == 'beneficiary' and reason.get('scope') == 'current'
                and reason.get('priorityRevision') == priorities['ref']['report_revision']
                and isinstance(reason.get('reason'), str) and len(reason['reason']) <= 160):
            reasons.append({key: copy.deepcopy(reason.get(key)) for key in
                            ('topic', 'reason', 'priorityRevision', 'revision')})
    reports = []
    for f in selected:
        value = f['value']
        representable = (isinstance(value, str) and len(value) <= 160
                         or type(value) in {int, float}
                         or isinstance(value, list) and len(value) <= 10
                         and all(isinstance(v, str) and len(v) <= 160 for v in value))
        reports.append({'question_id': 'T09' if f is cost else 'T10' if f['ref']['path'].startswith('guide.') else 'RC25',
                        'report_ref': _ref(f['ref']), 'report_state': f['report_state'],
                        'reported_value': copy.deepcopy(value) if representable else None,
                        'value_representation': 'reported_only' if representable else 'held_unreviewed_representation'})
    return {'ordering': 'unordered_set', 'priority_topics': topics, 'cost_preference': cost_preference,
            'reports': reports, 'current_priority_reasons': reasons,
            'emphasized_dimensions': sorted(emphasized), 'inferred_weights': None,
            'hard_constraints_evaluated': False,
            'constraint_evaluation': {'state': 'held_not_implemented', 'gap_ids': ['G12'],
                                      'reason_codes': ['POLICY_NOT_ACCEPTED', 'SCOPED_CONSTRAINT_METHOD_REQUIRED']}}


def _choose_question(profile, eligible_questions, questions, facts, task):
    if eligible_questions is None:
        return None
    if not isinstance(eligible_questions, (list, tuple)) or len(eligible_questions) > 50:
        raise ComparisonError('CONTROLLER_QUESTIONS_REQUIRED')
    reject_economic_fields(eligible_questions)
    by_id = {q['id']: q for q in questions}
    candidates = []
    for question in eligible_questions:
        if question is None:
            continue
        if not isinstance(question, Mapping):
            raise ComparisonError('CONTROLLER_QUESTION_INVALID')
        identifier = question.get('id', question.get('question_id'))
        extension = identifier in {'orientation', 'S_AGE65', 'S_RETIREMENT'}
        if identifier not in by_id and not extension:
            continue
        q = by_id.get(identifier)
        if q and identifier != 'T02' and not _relevant(q, task):
            continue
        paths = list(q['canonical_paths']) if q else []
        field_keys = [x.get('key') for x in question.get('fields', []) if isinstance(x, dict)]
        if field_keys:
            paths = [p for p in paths if p.rsplit('.', 1)[-1] in field_keys]
        item = question.get('entity', question.get('item_id', 'profile'))
        item = None if item == 'profile' else item
        related = _question_facts(q, facts) if q else []
        related = [f for f in related if f['ref']['path'] in paths
                   and f['ref'].get('subject_id') == profile['profile_binding'].get('subject_id')
                   and _question_scope_compatible(identifier, f)
                   and (item is None or f['ref'].get('item_id') in {None, item})]
        dispositions = profile.get('extensions', {}).get('baseline_dispositions', {})
        if isinstance(dispositions, dict) and dispositions.get(identifier) in {'unknown', 'deferred', 'declined'}:
            continue
        if related and all(f['report_state'] in {'unknown', 'deferred', 'declined'} for f in related):
            continue
        # Respect controller-provided partial-field targets. Clear facts are
        # not asked again just because the legacy question has other fields.
        if related and all(_bound_report(f, profile['profile_binding'].get('subject_id')) for f in related):
            continue
        blocking = 0 if any(f['report_state'] in {'conflicting', 'tentative', 'stale'} for f in related) else 1
        burden = 0 if question.get('choices') else 1 if len(paths) <= 1 else 2
        key = (blocking, 0, burden, QUESTION_IDS.index(identifier) if identifier in QUESTION_IDS else 41,
               item or '', paths[0] if paths else '')
        target = {'question_id': identifier, 'item_id': item,
                  'subject_id': profile['profile_binding'].get('subject_id'),
                  'target_paths': paths, 'question': question.get('question', ''),
                  'purpose': question.get('why') or (q.get('ask_only_when') if q else 'Clarify the current reported circumstance.'),
                  'source': 'existing_controller_eligible_move',
                  'report_refs': [_ref(f['ref']) for f in related],
                  'scheduling_key': list(key), 'affected_findings': [],
                  'answer_cannot_verify_external_evidence': True}
        candidates.append((key, target))
    return min(candidates, key=lambda x: x[0])[1] if candidates else None


def _finding(unit, dimension, item, related, row, fixture, integrity_ok=True, *, question_ids=(), gap_ids=()):
    identifier = 'finding:' + canonical_sha256([unit['unit_id'], dimension, item])[:20]
    conditions = copy.deepcopy(row.get('condition_set')) if row else None
    if not isinstance(conditions, dict):
        conditions = {'completeness': 'unknown', 'predicates': [],
                      'missing_predicates': ['exact_identity_period_conditions_and_authority']}
    condition_state = evaluate_conditions(conditions)
    source_state = row.get('source_use_state', 'not_newly_reviewed') if row else 'missing'
    evidence_state = row.get('evidence_state', 'observed') if row else 'missing'
    if source_state in {'source_STOP', 'source_stopped', 'source_STOP_preserved'}:
        evidence_state = 'source_stopped'
    policy_state = row.get('policy_state', 'unreviewed') if row else 'unreviewed'
    requirements = row.get('required_report_refs', []) if row else []
    usable = {_ref_key(f['ref']) for f in related if f.get('usable_for_bound_subject') is True
              and f.get('usable_as_report') is True
              and f['report_state'] in KNOWN_REPORTS}
    required_inputs_ready = (isinstance(requirements, list)
                             and all(isinstance(ref, dict) and _ref_key(ref) in usable for ref in requirements))
    permitted_fixture = bool(fixture and row and integrity_ok and required_inputs_ready
                             and policy_state == 'reviewed_for_exact_purpose'
                             and evidence_state == 'reviewed' and source_state == 'fixture_only'
                             and row.get('evidence_refs') and row.get('rule_refs'))
    result, value, applicability = 'unresolved', None, 'undetermined'
    reasons = [] if fixture else ['EXACT_RELEASE_REQUIRED', 'POLICY_NOT_ACCEPTED']
    if not row:
        reasons.append('SOURCE_MISSING')
    if evidence_state == 'source_stopped':
        reasons.append('SOURCE_STOPPED')
    if condition_state not in {'true', 'false'}:
        reasons.append('CONDITION_UNRESOLVED')
    if not integrity_ok:
        reasons.append('PROFILE_INTEGRITY_HOLD')
    if not required_inputs_ready:
        reasons.append('INPUT_PRECISION_MISSING')
    if permitted_fixture and condition_state in {'true', 'false'}:
        applicability = 'applies' if condition_state == 'true' else 'does_not_apply'
        # Fixture assertions are explicit; no generic "false means bad plan".
        result = row.get('result') if (condition_state == 'true' and row.get('result') in {'supports', 'conflicts', 'not_applicable'}) else 'unresolved'
        value = copy.deepcopy(row.get('value')) if condition_state == 'true' else None
    none_fields = ({'guide.fields.needs.providersStatus', 'readiness.facts.RC21.value.choice'}
                   if dimension == 'provider_access' else
                   {'guide.fields.needs.medicinesStatus', 'readiness.facts.RC22.value.choice'}
                   if dimension in {'drug_coverage', 'fill_price'} else set())
    explicit_none = any(f['ref']['path'] in none_fields and f.get('usable_for_bound_subject') is True
                        and f.get('usable_as_report') is True
                        and f['report_state'] == 'explicit_none' for f in related)
    active_item = any(f['ref'].get('item_id') and f.get('usable_for_bound_subject') is True
                      and f.get('usable_as_report') is True
                      and f['report_state'] == 'reported' for f in related)
    if explicit_none and item is None and not active_item and integrity_ok:
        result, applicability, value = 'not_applicable', 'does_not_apply', None
        reasons = ['REPORTED_REQUIREMENT_ABSENT']
        conditions = {'completeness': 'complete', 'root': {'op': 'predicate', 'evaluation': 'true',
                      'meaning': 'Explicitly reported no items requested for this check.'},
                      'predicates': [], 'missing_predicates': [],
                      'scope': 'reported_requirement_only_not_external_care_needs'}
    report_refs = [_ref(f['ref']) for f in related]
    return {'finding_id': identifier, 'unit_id': unit['unit_id'], 'dimension_id': dimension,
            'subject_or_item_id': item, 'report_refs': report_refs,
            'question_ids': list(question_ids), 'gap_ids': sorted(set(gap_ids)),
            'input_state': _input_state(related), 'evidence_state': evidence_state,
            'applicability': applicability, 'policy_state': policy_state,
            'output_state': 'fictional_fixture_only' if permitted_fixture else 'held',
            'result': result, 'value': value, 'condition_set': conditions,
            'reason_codes': sorted(set(reasons)),
            'evidence_refs': copy.deepcopy(row.get('evidence_refs', [])) if permitted_fixture else [],
            'rule_refs': [DIMENSIONS[dimension][2], 'R14', 'R18'],
            'dependency_refs': report_refs,
            'invalidation_keys': ['profile.item_revision', 'scope', 'evidence.manifest', 'rule.version'],
            'fictional': fixture}


def build_comparison(profile_adapter_result, evidence_source=None, generated_at=None, *, eligible_questions=None):
    """Return one minimized JSON-safe response from a consistent server snapshot.

    ``eligible_questions`` comes only from the current conversation controller.
    All profile-carried release/evidence/readiness flags are ignored. A current
    production response remains research preparation with no released plans.
    """
    _validate_profile(profile_adapter_result)
    profile = copy.deepcopy(profile_adapter_result)
    scope = copy.deepcopy(profile.get('requested_scope') or {})
    snapshot, evidence_digest = read_snapshot(evidence_source, scope)
    fixture = snapshot.source_kind == 'fictional_fixture'
    questions, facts = profile['questions'], profile['facts']
    subject = profile['profile_binding'].get('subject_id')
    task = scope.get('task') or profile.get('extensions', {}).get('task', '')
    task = task if task in TASK_CAPABILITIES else ''
    dimensions = TASK_DIMENSIONS[task]
    preferences = _preference_context(profile, facts, subject)
    question = _choose_question(profile, eligible_questions, questions, facts, task)
    accounting = _account_questions(questions, facts, task, question['question_id'] if question else None,
                                    subject, profile.get('extensions', {}).get('baseline_dispositions'))
    baseline_facts = _dimension_facts('coverage_structure', None, questions, facts, subject, task)
    baseline = {'unit_id': 'current-arrangement', 'kind': 'current_arrangement',
                'identity_state': 'reported_unbound' if any(f.get('usable_as_report') for f in baseline_facts) else 'unknown',
                'report_refs': [_ref(f['ref']) for f in baseline_facts],
                'external_binding_state': 'unverified', 'period_state': 'reported_or_unknown'}
    # Real research rows cannot enter the consumer unit list through this path.
    # Fictional units are supplied by tests only and retain their fixture labels.
    units = [baseline] + (copy.deepcopy(list(snapshot.units)) if fixture else [])
    rows = {(r['unit_id'], r['dimension_id'], r.get('item_id')): r for r in snapshot.observations} if fixture else {}
    findings = []
    items = {dimension: _items(dimension, facts, subject) for dimension in dimensions}
    if sum(len(ids) for ids in items.values()) * len(units) > 5000:
        raise ComparisonError('COMPARISON_SCOPE_TOO_LARGE')
    for unit in units:
        for dimension in dimensions:
            ids = _dimension_question_ids(dimension, task)
            gaps = {gap for q in questions if q['id'] in ids for gap in q.get('gap_ids', [])}
            for item in items[dimension]:
                related = _dimension_facts(dimension, item, questions, facts, subject, task)
                findings.append(_finding(unit, dimension, item, related,
                                         rows.get((unit['unit_id'], dimension, item)), fixture,
                                         not profile.get('integrity_issues'), question_ids=ids, gap_ids=gaps))
    if question:
        refs = set(question['target_paths'])
        question['affected_findings'] = [f['finding_id'] for f in findings
                                        if any(r['path'] in refs for r in f['report_refs'])]
    work = []
    for finding in findings:
        if finding['result'] == 'unresolved':
            work.append({'work_item_id': 'work:' + finding['finding_id'].split(':', 1)[1],
                         'type': 'resolve_evidence_conditions_and_authority',
                         'status': 'proposed_not_started', 'owner_role': 'evidence_research',
                         'unit_id': finding['unit_id'], 'dimension_id': finding['dimension_id'],
                         'item_id': finding['subject_or_item_id'], 'affected_findings': [finding['finding_id']],
                         'gap_ids': finding['gap_ids'],
                         'reason_codes': finding['reason_codes'],
                         'closure_evidence': ['exact_entity_and_effective_scope', 'complete_conditions',
                                              'reviewed_method', 'source_use_and_original_release_authority'],
                         'external_action_completed': False})
    tradeoffs = []
    for left, right in combinations(units[1:], 2):
        for dimension in dimensions:
            for item in items[dimension]:
                lf = next(f for f in findings if (f['unit_id'], f['dimension_id'], f['subject_or_item_id']) == (left['unit_id'], dimension, item))
                rf = next(f for f in findings if (f['unit_id'], f['dimension_id'], f['subject_or_item_id']) == (right['unit_id'], dimension, item))
                comparison = compare_dimension_values(lf['value'], rf['value'])
                tradeoffs.append({'unit_ids': [left['unit_id'], right['unit_id']], 'dimension_id': dimension,
                                  'item_id': item, **comparison, 'finding_refs': [lf['finding_id'], rf['finding_id']],
                                  'overall_relation': 'tradeoff_or_unresolved', 'fictional': True})
    authority = purpose_authorities(snapshot)
    binding = {**{k: copy.deepcopy(profile['profile_binding'].get(k)) for k in
                 ('guide_revision', 'readiness_revision', 'subject_id', 'adapter_version',
                  'normalized_sha256', 'contract_sha256', 'item_revisions')},
               'scope': scope, 'rule_version': RULE_VERSION, 'method_version': METHOD_VERSION,
               'evidence_version': EVIDENCE_VERSION, 'evidence_manifest': snapshot.manifest_id,
               'evidence_sha256': evidence_digest, 'serving_build_id': snapshot.serving_build_id,
               'research_build_id': snapshot.research_build_id, 'accepted_release_id': None}
    trace = {'question_accounting': accounting,
             'gap_accounting': [{'gap_id': gap['id'], 'gap_closed': False,
                                 'report_refs': [_ref(f['ref']) for f in gap.get('reports', [])]}
                                for gap in profile.get('gap_reports', [])],
             'source_order': [unit['unit_id'] for unit in units],
             'selection': copy.deepcopy(question),
             'integrity_issues': [{k: issue.get(k) for k in ('code', 'path', 'item_id', 'severity')}
                                  for issue in profile.get('integrity_issues', []) if isinstance(issue, dict)],
             'finding_dependencies': {f['finding_id']: f['dependency_refs'] for f in findings}}
    content_id = canonical_sha256({'binding': binding, 'task': task, 'trace': trace,
                                   'units': units, 'findings': findings, 'authority': authority,
                                   'preference_context': preferences})
    trace_ref = 'decision:' + content_id
    # The trace is owner-bound response data only, never persisted by this module.
    return {'contract_id': CONTRACT_ID, 'comparison_id': 'comparison:' + content_id,
            'generated_at': generated_at or datetime.now(timezone.utc).isoformat(),
            'mode': 'research_preparation', 'fictional': fixture,
            'binding': binding, 'authority': authority,
            'task': {'key': task, 'preparing': bool(profile.get('extensions', {}).get('preparing')),
                     'requested_scope': scope},
            'capabilities': [{'key': key, 'report_sufficiency': 'not_evaluated_by_accepted_method',
                              'report_states': dict(Counter(f['report_state'] for f in facts
                                  if f['ref'].get('subject_id') == subject
                                  if any(f['ref']['path'] == path for q in questions
                                         if key in q.get('source_capabilities', []) for path in q['canonical_paths']))),
                              'external_evidence_state': 'held', 'policy_state': 'unreviewed',
                              'output_authority': 'held'} for key in TASK_CAPABILITIES[task]],
            'universe': {'completeness': 'unknown' if not fixture else snapshot.completeness,
                         'discovered_count': None if not fixture else len(snapshot.units),
                         'evaluated_count': 0 if not fixture else len(snapshot.units),
                         'candidate_set_ref': snapshot.manifest_id if fixture else None,
                         'unsupported_categories': ['consumer_release_not_implemented'],
                         'exclusions': [], 'ordering': 'source_order', 'automatic_personal_order': None},
            'research': {'state': 'connected_research_only' if snapshot.research_build_id else 'not_connected',
                         'research_build_id': snapshot.research_build_id,
                         'retained_identity_count': len(snapshot.units) if snapshot.research_build_id else None,
                         'scope': scope, 'consumer_evaluated_count': 0,
                         'population_basis': 'selected_frozen_research_scope_not_all_market',
                         'source_kind': snapshot.source_kind},
            'units': units, 'dimensions': [{'dimension_id': d, 'label': DIMENSIONS[d][0],
                                           'user_relevance': 'explicit_preference_emphasis' if d in preferences['emphasized_dimensions'] else 'requested_check_or_common_dimension',
                                           'personal_suitability_score': None} for d in dimensions],
            'preference_context': preferences,
            'findings': findings, 'tradeoffs': tradeoffs,
            'outcomes': [{'kind': 'continue_checking', 'state': 'available_preparation'},
                         {'kind': 'keep_current', 'state': 'consequences_unresolved'},
                         {'kind': 'defer_decision', 'state': 'consequences_unresolved'}],
            'next_question': question, 'work_items': work,
            'decision_record_ref': trace_ref, 'decision_record': trace,
            'validity': {'bound_profile_sha256': binding['normalized_sha256'],
                         'bound_evidence_sha256': evidence_digest, 'stale_action_replay_allowed': False,
                         'reassessment_required_on': ['profile_revision', 'item_revision', 'scope',
                                                      'source_edition_or_revocation', 'rule_version']},
            'personalized_recommendation_allowed': False,
            'external_action_completed': False}
