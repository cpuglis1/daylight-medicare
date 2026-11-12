"""Deterministic, private comparison mechanics; no Medicare policy or release.

Callers supply a current adapter snapshot and finding-specific declarations.
This module never chooses a universal intake, infers a hard constraint from a
preference, resolves names by similarity, queries evidence or authorizes output.
Fixture policy/arithmetic is explicitly separated from real source authority.
"""
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
import copy
import re

from comparison_evidence import canonical_sha256, reject_economic_fields


METHOD_VERSION = 'comparison-mechanics-20261101-r1'
QUESTION_IDS = frozenset([f'T{i:02d}' for i in range(1, 11)]
                        + [f'RC{i:02d}' for i in range(1, 29)]
                        + ['RC11.C1', 'RC16.C1', 'RC16.C2'])
REF_KEYS = ('path', 'item_id', 'subject_id', 'scope', 'report_revision', 'record_revision')
KNOWN = {'reported', 'explicit_none'}
STATES = KNOWN | {'unanswered', 'tentative', 'unknown', 'deferred', 'declined',
                  'stale', 'conflicting', 'superseded'}
SCOPES = {'current', 'intended', 'historical'}
IDENTITY_KINDS = {'provider_site', 'drug_product', 'pharmacy_site', 'coverage_component'}
DECIMAL = re.compile(r'\d{1,80}(?:\.\d{1,40})?\Z')
BASIS_KEYS = ('currency', 'unit', 'period', 'cost_type', 'scope_key', 'population_basis',
              'network', 'channel', 'phase', 'included_components', 'excluded_components', 'assumptions')


class ComparisonMethodError(ValueError):
    """Fixed-code failure without supplied values or personal identifiers."""


@dataclass(frozen=True)
class RequiredInput:
    path: str
    item_id: str | None = None
    scope: str = 'current'
    precisions: tuple = ()
    parts: tuple = ()
    expected_revision: int | None = None
    allow_explicit_none: bool = False
    allow_derived: bool = False


@dataclass(frozen=True)
class IdentityBinding:
    """Server-supplied exact source key, never a fuzzy candidate/name match."""
    kind: str
    namespace: str
    entity_id: str
    item_id: str | None
    scope: dict
    report_refs: tuple
    evidence_refs: tuple


@dataclass(frozen=True)
class MustHave:
    """Explicit interpreted requirement, not a T10 priority or care-item label.

    Real interpretation/policy authority is deliberately unavailable here.
    ``fixture:`` records exercise the method under fictional findings only.
    """
    constraint_id: str
    dimension_id: str
    subject_id: str
    scope_key: str
    report_refs: tuple
    item_id: str | None = None
    operator: str = 'supports'
    threshold: str | None = None
    basis: dict | None = None


@dataclass(frozen=True)
class ScenarioLine:
    component_id: str
    quantity: str
    priced_unit: str
    priced_period: str
    basis: dict


@dataclass(frozen=True)
class CostScenario:
    scenario_id: str
    unit_id: str
    subject_id: str
    scope_key: str
    currency: str
    period: str
    lines: tuple
    excluded_components: tuple
    assumptions: tuple
    report_refs: tuple


def _json(value):
    reject_economic_fields(value)
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError, RecursionError):
        raise ComparisonMethodError('METHOD_INPUT_NOT_JSON') from None


def _ref(ref):
    if (not isinstance(ref, Mapping) or not isinstance(ref.get('path'), str)
            or not isinstance(ref.get('subject_id'), str) or not isinstance(ref.get('scope'), str)
            or ref.get('item_id') is not None and not isinstance(ref['item_id'], str)
            or any(ref.get(k) is not None and (type(ref[k]) is not int or ref[k] < 0)
                   for k in ('report_revision', 'record_revision'))):
        raise ComparisonMethodError('REPORT_REF_INVALID')
    return {k: copy.deepcopy(ref.get(k)) for k in REF_KEYS}


def _key(ref):
    return _json(_ref(ref))


def _profile(profile):
    if (not isinstance(profile, Mapping) or not isinstance(profile.get('profile_binding'), Mapping)
            or not isinstance(profile.get('facts'), list) or len(profile['facts']) > 5000
            or not isinstance(profile.get('questions'), list)
            or len(profile['questions']) != 41
            or any(not isinstance(q, dict) or not isinstance(q.get('id'), str) for q in profile['questions'])
            or {q.get('id') for q in profile['questions']} != QUESTION_IDS
            or not isinstance(profile['profile_binding'].get('subject_id'), str)):
        raise ComparisonMethodError('PROFILE_ADAPTER_REQUIRED')
    _json(profile)
    keys = set()
    for fact in profile['facts']:
        if (not isinstance(fact, dict) or not isinstance(fact.get('report_state'), str)
                or fact['report_state'] not in STATES):
            raise ComparisonMethodError('PROFILE_REPORT_INVALID')
        key = _key(fact.get('ref'))
        if key in keys:
            raise ComparisonMethodError('PROFILE_REPORT_BINDING_DUPLICATE')
        keys.add(key)
    return profile['profile_binding']['subject_id'], profile['facts']


def _usable(fact, subject, scope=None):
    return (fact['ref']['subject_id'] == subject
            and fact.get('capture_subject') == 'beneficiary'
            and fact.get('usable_as_report') is True
            and fact.get('usable_for_bound_subject') is True
            and fact['report_state'] in KNOWN
            and fact['ref']['scope'] in SCOPES
            and (scope is None or fact['ref']['scope'] == scope))


def _receipt(method, **values):
    out = {'method': method, 'method_version': METHOD_VERSION,
           'policy_state': 'unreviewed', 'output_state': 'held',
           'personalized_recommendation_allowed': False, **values}
    out['receipt_sha256'] = _json(out)
    return out


def assess_required_inputs(profile, requirements, *, finding_id):
    """Check exact declared leaves only; aliases reuse the same report refs.

    A sufficient *report* does not establish external evidence, eligibility,
    method acceptance or output authority. Missing optional leaves that were not
    declared have no effect. This helper does not generate consumer questions.
    """
    subject, facts = _profile(profile)
    if (not isinstance(finding_id, str) or not finding_id or not isinstance(requirements, (list, tuple))
            or len(requirements) > 100):
        raise ComparisonMethodError('REQUIRED_INPUT_DECLARATION_INVALID')
    paths = {f['ref']['path'] for f in facts}
    seen, rows = set(), []
    for req in requirements:
        if (type(req) is not RequiredInput or not isinstance(req.path, str) or req.path not in paths
                or not isinstance(req.scope, str) or req.scope not in SCOPES
                or not isinstance(req.precisions, tuple) or not isinstance(req.parts, tuple)
                or any(not isinstance(x, str) or not x for x in req.precisions + req.parts)
                or req.expected_revision is not None and (type(req.expected_revision) is not int or req.expected_revision < 0)
                or type(req.allow_explicit_none) is not bool or type(req.allow_derived) is not bool
                or req.item_id is not None and not isinstance(req.item_id, str)
                or ('.items[].' in req.path) != (req.item_id is not None)):
            raise ComparisonMethodError('REQUIRED_INPUT_DECLARATION_INVALID')
        marker = _json(asdict(req))
        if marker in seen:
            continue
        seen.add(marker)
        related = [f for f in facts if f['ref']['path'] == req.path and f['ref']['item_id'] == req.item_id]
        selected = [f for f in related if f['ref']['subject_id'] == subject and f['ref']['scope'] == req.scope]
        reasons, missing_parts = [], []
        state = 'unanswered'
        if len(selected) > 1:
            state, reasons = 'conflicting', ['REPORT_BINDING_AMBIGUOUS']
        elif not selected:
            reasons = ['REPORT_SCOPE_UNRESOLVED' if related else 'INPUT_MISSING']
        else:
            fact = selected[0]
            state = fact['report_state']
            if req.expected_revision is not None and fact['ref']['report_revision'] != req.expected_revision:
                state, reasons = 'stale', ['DEPENDENCY_STALE']
            elif state not in KNOWN:
                reasons = ['REPORT_' + state.upper()]
            elif not _usable(fact, subject, req.scope):
                state, reasons = 'unknown', ['REPORT_SUBJECT_OR_PROVENANCE_UNRESOLVED']
            elif fact.get('capture_method') == 'location_reference' and not req.allow_derived:
                state, reasons = 'unknown', ['DERIVED_LOCATION_NOT_PERSONAL_REPORT']
            elif state == 'explicit_none' and not req.allow_explicit_none:
                state, reasons = 'unanswered', ['REPORTED_ABSENCE_NOT_POSITIVE_INPUT']
            else:
                value = fact.get('value')
                missing_parts = [key for key in req.parts if not isinstance(value, dict)
                                 or key not in value or value[key] is None or value[key] == '']
                if missing_parts or req.precisions and fact.get('precision') not in req.precisions:
                    state, reasons = 'partial', ['INPUT_PRECISION_MISSING']
                else:
                    state = 'sufficient_report'
        rows.append({'path': req.path, 'item_id': req.item_id, 'subject_id': subject,
                     'scope': req.scope, 'input_state': state, 'reason_codes': reasons,
                     'question_ids': [q['id'] for q in profile['questions'] if req.path in q['canonical_paths']],
                     'report_refs': [_ref(f['ref']) for f in selected],
                     'required_parts': list(req.parts), 'missing_parts': missing_parts,
                     'allowed_precisions': list(req.precisions)})
    states = [row['input_state'] for row in rows]
    if not rows:
        overall = 'not_required'
    elif all(state == 'sufficient_report' for state in states):
        overall = 'sufficient_report'
    else:
        overall = next((state for state in ('conflicting', 'stale', 'tentative', 'deferred', 'declined', 'unknown')
                        if state in states), 'partial' if 'sufficient_report' in states or 'partial' in states else 'unanswered')
    return _receipt('declared_finding_inputs', finding_id=finding_id, input_state=overall,
                    requirements=rows, dependency_refs=[ref for row in rows for ref in row['report_refs']],
                    universal_intake=False, evidence_state='not_evaluated')


def _current_refs(profile, refs, subject, *, item_id=None):
    """Keep unchanged field lineage across monotonic parent bookkeeping.

    A whole-record revision is a snapshot binding, not a revision of every care
    item. The exact report revision must remain unchanged; a parent rollback or
    future receipt is held. Callers still bind the complete result to the live
    adapter snapshot and recheck it before returning.
    """
    if not isinstance(refs, (tuple, list)) or not refs or len(refs) > 100:
        return False
    for ref in refs:
        expected = _ref(ref)
        related = [f for f in profile['facts']
                   if all(f['ref'][k] == expected[k] for k in REF_KEYS if k != 'record_revision')]
        if len(related) != 1:
            return False
        fact = related[0]
        if (type(expected['record_revision']) is not int or type(expected['report_revision']) is not int
                or type(fact['ref']['record_revision']) is not int
                or fact['ref']['record_revision'] < expected['record_revision']
                or not _usable(fact, subject)
                or item_id is not None and fact['ref']['item_id'] != item_id
                or fact.get('capture_method') == 'location_reference'):
            return False
    return True


def assess_identity_binding(profile, bindings, *, kind, item_id, scope):
    """Inspect exact identity lineage; bound identity proves no service access."""
    subject, _ = _profile(profile)
    if (not isinstance(kind, str) or kind not in IDENTITY_KINDS
            or not isinstance(bindings, (tuple, list)) or len(bindings) > 100
            or not isinstance(scope, dict) or not scope
            or item_id is not None and not isinstance(item_id, str)):
        raise ComparisonMethodError('IDENTITY_DECLARATION_INVALID')
    _json(scope)
    candidates, reasons = {}, []
    for binding in bindings:
        if (type(binding) is not IdentityBinding or not isinstance(binding.kind, str) or binding.kind not in IDENTITY_KINDS
                or not isinstance(binding.namespace, str) or not binding.namespace
                or not isinstance(binding.entity_id, str) or not binding.entity_id
                or not isinstance(binding.scope, dict) or not isinstance(binding.report_refs, tuple)
                or not isinstance(binding.evidence_refs, tuple)
                or not binding.evidence_refs or any(not isinstance(x, str) or not x for x in binding.evidence_refs)):
            raise ComparisonMethodError('IDENTITY_BINDING_INVALID')
        _json(asdict(binding))
        if binding.kind != kind or binding.item_id != item_id:
            continue
        if binding.scope != scope:
            reasons.append('WRONG_EFFECTIVE_SCOPE')
            continue
        if not _current_refs(profile, binding.report_refs, subject, item_id=item_id):
            reasons.append('IDENTITY_REPORT_BINDING_STALE_OR_UNSCOPED')
            continue
        key = (binding.namespace, binding.entity_id)
        candidate = candidates.setdefault(key, {'namespace': binding.namespace, 'entity_id': binding.entity_id,
                                                'report_refs': [], 'evidence_refs': []})
        for ref in binding.report_refs:
            normalized = _ref(ref)
            if normalized not in candidate['report_refs']:
                candidate['report_refs'].append(normalized)
        for ref in binding.evidence_refs:
            if ref not in candidate['evidence_refs']:
                candidate['evidence_refs'].append(ref)
    state = 'bound' if len(candidates) == 1 else 'ambiguous' if candidates else 'unresolved'
    if state != 'bound':
        reasons.append('IDENTITY_AMBIGUOUS' if candidates else 'ITEM_IDENTITY_UNRESOLVED')
    return _receipt('exact_source_identity_binding', identity_state=state, kind=kind,
                    item_id=item_id, subject_id=subject, scope=copy.deepcopy(scope),
                    candidates=list(candidates.values()),
                    reason_codes=sorted(set(reasons)), externally_verified=False,
                    access_state='not_evaluated', availability_state='not_evaluated')


def _decimal(value):
    if not isinstance(value, str) or not DECIMAL.fullmatch(value):
        raise ComparisonMethodError('EXACT_NONNEGATIVE_DECIMAL_REQUIRED')
    return Decimal(value)


def _valid_basis(value):
    return (isinstance(value, dict) and set(value) == set(BASIS_KEYS)
            and all(isinstance(value[key], str) and value[key] for key in
                    ('currency', 'unit', 'period', 'cost_type', 'scope_key', 'population_basis'))
            and all(value[key] is None or isinstance(value[key], str) and value[key]
                    for key in ('network', 'channel', 'phase'))
            and all(isinstance(value[key], list) and all(isinstance(x, str) and x for x in value[key])
                    for key in ('included_components', 'excluded_components', 'assumptions')))


def _fixture_finding(row):
    """Existing engine's fixture receipt is not a real authority receipt."""
    from comparison_engine import evaluate_conditions
    return (isinstance(row, dict) and row.get('fictional') is True
            and isinstance(row.get('unit_id'), str) and row['unit_id'].startswith('fixture:')
            and row.get('output_state') == 'fictional_fixture_only'
            and row.get('policy_state') == 'reviewed_for_exact_purpose'
            and row.get('evidence_state') == 'reviewed'
            and row.get('evidence_refs') and row.get('rule_refs')
            and evaluate_conditions(row.get('condition_set')) == 'true')


def evaluate_must_have(profile, constraint, findings, *, unit_ids):
    """Partition an explicit requirement; never hide, score or rank candidates.

    Real requirement interpretation/release is held. Fictional fixtures may
    exercise truth tables. A missing, disputed, stale or held cell is unresolved.
    """
    subject, _ = _profile(profile)
    if (type(constraint) is not MustHave or not isinstance(constraint.operator, str)
            or constraint.operator not in {'supports', 'at_most', 'at_least', 'equals'}
            or not all(isinstance(x, str) and x for x in (constraint.constraint_id, constraint.dimension_id,
                                                        constraint.subject_id, constraint.scope_key))
            or not isinstance(constraint.report_refs, tuple) or not isinstance(findings, (tuple, list))
            or not isinstance(unit_ids, (tuple, list)) or len(unit_ids) > 100
            or any(not isinstance(x, str) for x in unit_ids) or len(set(unit_ids)) != len(unit_ids)):
        raise ComparisonMethodError('MUST_HAVE_DECLARATION_INVALID')
    _json({'constraint': asdict(constraint), 'findings': findings, 'unit_ids': unit_ids})
    if constraint.operator != 'supports':
        _decimal(constraint.threshold)
        if not _valid_basis(constraint.basis):
            raise ComparisonMethodError('CONSTRAINT_COST_BASIS_REQUIRED')
    elif constraint.threshold is not None or constraint.basis is not None:
        raise ComparisonMethodError('MUST_HAVE_DECLARATION_INVALID')
    bound = (constraint.subject_id == subject and _current_refs(profile, constraint.report_refs, subject))
    fixture = constraint.constraint_id.startswith('fixture:') and constraint.scope_key.startswith('fixture:')
    rows, groups = [], {key: [] for key in ('known_meets', 'known_conflicts', 'unresolved')}
    for unit in unit_ids:
        related = [f for f in findings if isinstance(f, dict) and f.get('unit_id') == unit
                   and f.get('dimension_id') == constraint.dimension_id
                   and f.get('subject_or_item_id') == constraint.item_id]
        group, reasons = 'unresolved', []
        if not bound:
            reasons.append('CONSTRAINT_REPORT_BINDING_STALE_OR_UNSCOPED')
        if not fixture:
            reasons.extend(['SCOPED_CONSTRAINT_METHOD_REQUIRED', 'EXACT_RELEASE_REQUIRED'])
        if len(related) != 1:
            reasons.append('FINDING_MISSING_OR_AMBIGUOUS')
        elif not _fixture_finding(related[0]):
            reasons.append('FINDING_CONDITIONS_OR_AUTHORITY_UNRESOLVED')
        elif bound and fixture:
            row = related[0]
            value = row.get('value')
            if not isinstance(value, dict) or value.get('scope_key') != constraint.scope_key:
                reasons.append('WRONG_EFFECTIVE_SCOPE')
            elif constraint.operator == 'supports':
                group = {'supports': 'known_meets', 'conflicts': 'known_conflicts'}.get(row.get('result'), 'unresolved')
            else:
                if (not isinstance(value, dict) or value.get('type') != 'decimal'
                        or any(k not in value or value[k] != constraint.basis[k] for k in BASIS_KEYS)
                        or value.get('scope_key') != constraint.scope_key
                        or row.get('result') != 'supports'):
                    reasons.append('INCOMPARABLE_CONSTRAINT_BASIS')
                else:
                    try:
                        amount = _decimal(value.get('amount'))
                    except ComparisonMethodError:
                        reasons.append('COMPONENT_AMOUNT_UNKNOWN_OR_INEXACT')
                    else:
                        limit = _decimal(constraint.threshold)
                        meets = (amount <= limit if constraint.operator == 'at_most' else
                                 amount >= limit if constraint.operator == 'at_least' else amount == limit)
                        group = 'known_meets' if meets else 'known_conflicts'
        if group == 'unresolved' and not reasons:
            reasons.append('FINDING_UNRESOLVED')
        groups[group].append(unit)
        rows.append({'unit_id': unit, 'partition': group, 'reason_codes': sorted(set(reasons)),
                     'finding_refs': [f['finding_id'] for f in related if isinstance(f.get('finding_id'), str)]})
    return _receipt('explicit_must_have_partition', constraint_id=constraint.constraint_id,
                    interpretation_state='fictional_fixture_only' if fixture and bound else 'held',
                    output_state='fictional_fixture_only' if fixture and bound else 'held',
                    candidate_order=list(unit_ids), partitions=groups, evaluations=rows,
                    dependency_refs=[_ref(r) for r in constraint.report_refs],
                    hidden_unit_ids=[], filter_applied=False, automatic_personal_order=None,
                    available_outcomes=['keep_current', 'defer_decision', 'continue_checking'])


def evaluate_cost_scenario(profile, scenario, components):
    """Exact declared scenario subtotal; no utilization or annualization defaults.

    Components are existing typed finding objects, indexed by ``finding_id``.
    Quantities explicitly count each value's priced unit/period within the
    scenario period. Currency conversion, benefit accumulation, offsets, caps,
    annual predictions, taxes, personal quotes and complete totals are absent.
    Real component/method/output authority remains held in this implementation.
    """
    subject, _ = _profile(profile)
    if (type(scenario) is not CostScenario or not isinstance(components, (tuple, list)) or len(components) > 100
            or not isinstance(scenario.lines, tuple) or not scenario.lines or len(scenario.lines) > 100
            or not all(isinstance(x, str) and x for x in (scenario.scenario_id, scenario.unit_id,
                       scenario.subject_id, scenario.scope_key, scenario.currency, scenario.period))
            or not isinstance(scenario.excluded_components, tuple) or not isinstance(scenario.assumptions, tuple)
            or any(not isinstance(x, str) or not x for x in scenario.excluded_components + scenario.assumptions)
            or not isinstance(scenario.report_refs, tuple)):
        raise ComparisonMethodError('COST_SCENARIO_DECLARATION_INVALID')
    _json({'scenario': asdict(scenario), 'components': components})
    identifiers, component_scopes, operands, rows = set(), set(), [], []
    fixture = all(x.startswith('fixture:') for x in (scenario.scenario_id, scenario.unit_id, scenario.scope_key))
    bound = scenario.subject_id == subject and _current_refs(profile, scenario.report_refs, subject)
    for line in scenario.lines:
        if (type(line) is not ScenarioLine or not isinstance(line.component_id, str) or not line.component_id
                or not isinstance(line.priced_unit, str) or not line.priced_unit
                or not isinstance(line.priced_period, str) or not line.priced_period
                or not _valid_basis(line.basis)
                or line.basis.get('unit') != line.priced_unit or line.basis.get('period') != line.priced_period
                or line.component_id in identifiers or line.component_id in scenario.excluded_components):
            raise ComparisonMethodError('COST_SCENARIO_LINE_INVALID')
        quantity = _decimal(line.quantity)
        identifiers.add(line.component_id)
        related = [c for c in components if isinstance(c, dict) and c.get('finding_id') == line.component_id]
        reasons = []
        if not bound:
            reasons.append('SCENARIO_REPORT_BINDING_STALE_OR_UNSCOPED')
        if len(related) != 1:
            reasons.append('COMPONENT_MISSING_OR_AMBIGUOUS')
        else:
            component = related[0]
            value = component.get('value')
            if (not isinstance(value, dict) or value.get('type') != 'decimal'
                    or any(key not in value for key in BASIS_KEYS)
                    or component.get('unit_id') != scenario.unit_id
                    or value.get('scope_key') != scenario.scope_key
                    or value.get('currency') != scenario.currency
                    or value.get('unit') != line.priced_unit or value.get('period') != line.priced_period
                    or any(value.get(key) != line.basis[key] for key in BASIS_KEYS)
                    or value.get('cost_type') not in {'published_component', 'scenario_estimate'}
                    or not isinstance(value.get('included_components'), list) or not value['included_components']
                    or any(not isinstance(x, str) or not x for x in value['included_components'])
                    or not isinstance(value.get('excluded_components'), list)
                    or not isinstance(value.get('assumptions'), list)
                    or component.get('result') != 'supports'):
                reasons.append('INCOMPARABLE_COMPONENT_BASIS')
            elif component_scopes.intersection(value['included_components']):
                reasons.append('COMPONENT_SCOPE_OVERLAP')
            elif not fixture or not _fixture_finding(component):
                reasons.extend(['COMPONENT_OR_SCENARIO_METHOD_NOT_ACCEPTED', 'EXACT_RELEASE_REQUIRED'])
            elif bound:
                try:
                    amount = _decimal(value.get('amount'))
                except ComparisonMethodError:
                    reasons.append('COMPONENT_AMOUNT_UNKNOWN_OR_INEXACT')
                else:
                    component_scopes.update(value['included_components'])
                    operands.append((amount, quantity))
        rows.append({'component_id': line.component_id, 'quantity': line.quantity,
                     'priced_unit': line.priced_unit, 'priced_period': line.priced_period,
                     'state': 'ready' if not reasons else 'unresolved', 'reason_codes': reasons})
    ready = all(row['state'] == 'ready' for row in rows) and len(operands) == len(rows)
    subtotal = None
    if ready:
        # Bound lexical decimal lengths permit exact products/sums independent
        # of the process/global Decimal context, including zero and large sums.
        with localcontext() as context:
            context.prec = 300
            subtotal = format(sum((amount * quantity for amount, quantity in operands), Decimal(0)), 'f')
    return _receipt('declared_cost_scenario_subtotal', scenario_id=scenario.scenario_id,
                    unit_id=scenario.unit_id, subject_id=subject, scope_key=scenario.scope_key,
                    arithmetic_state='computed' if ready else 'held',
                    output_state='fictional_fixture_only' if ready else 'held',
                    subtotal=({'amount': subtotal, 'currency': scenario.currency, 'period': scenario.period,
                               'cost_type': 'scenario_estimate'} if ready else None),
                    claim_kind='declared_scenario_subtotal', complete_total=None, quote=None,
                    lines=rows, included_components=[line.component_id for line in scenario.lines],
                    excluded_components=list(scenario.excluded_components), assumptions=list(scenario.assumptions),
                    dependency_refs=[_ref(r) for r in scenario.report_refs],
                    reason_codes=[] if ready else sorted({r for row in rows for r in row['reason_codes']}),
                    inferred_utilization=False, automatic_annualization=False)
