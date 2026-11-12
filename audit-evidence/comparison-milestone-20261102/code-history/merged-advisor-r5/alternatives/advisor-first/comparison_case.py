"""Prepare declared comparison checks from the approved question meanings.

These are technical research-input receipts, not accepted personal policy rules.
They do not route the conversation or turn preferences into hard constraints.
"""
import copy

from comparison_methods import (METHOD_VERSION, RequiredInput, assess_required_inputs,
                                assess_identity_binding)


DECLARED_ITEM_CHECKS = {
    'provider_access': ('provider_site', 'RC21', ('practice', 'city')),
    'drug_coverage': ('drug_product', 'RC22', ('name', 'strength', 'form')),
    'fill_price': ('drug_product', 'RC22', ('name', 'strength', 'form')),
}
LABELS = {'guide.fields.coverage.current': 'Current coverage',
          'readiness.facts.RC07.value.choice': 'Medicare arrangement',
          'readiness.facts.RC26.value.choice': 'Other reported coverage',
          'guide.fields.coverage.requestedStartMonth': 'Requested start month',
          'guide.fields.coverage.requestedStart': 'Requested timing'}


def prepare_case(profile, comparison):
    facts = profile['facts']
    subject = profile['profile_binding']['subject_id']
    available_paths = {fact['ref']['path'] for fact in facts}
    assessments, seen = [], set()
    for finding in comparison['findings']:
        dimension, item = finding['dimension_id'], finding['subject_or_item_id']
        key = (dimension, item)
        if key in seen:
            continue
        seen.add(key)
        declaration = DECLARED_ITEM_CHECKS.get(dimension)
        if declaration is None:
            continue
        related_findings = [row for row in comparison['findings']
                            if (row['dimension_id'], row['subject_or_item_id']) == key]
        if related_findings and all(row['result'] == 'not_applicable'
                and 'REPORTED_REQUIREMENT_ABSENT' in row['reason_codes'] for row in related_findings):
            assessments.append({'dimension_id': dimension, 'item_id': item,
                'state': 'reported_requirement_absent', 'input_state': 'not_required',
                'reason_codes': ['REPORTED_REQUIREMENT_ABSENT'],
                'method_version': METHOD_VERSION, 'output_state': 'held'})
            continue
        kind, question, leaves = declaration
        if item is None:
            assessments.append({'dimension_id': dimension, 'item_id': None,
                'state': 'item_representation_unresolved',
                'reason_codes': ['EXACT_ITEM_REPORT_REQUIRED'],
                'method_version': METHOD_VERSION, 'output_state': 'held'})
            continue
        requirements = [RequiredInput('readiness.facts.' + question + '.value.items[].' + leaf,
                                     item_id=item) for leaf in leaves]
        if dimension == 'fill_price':
            requirements += [RequiredInput('readiness.facts.RC23.value.items[].' + leaf,
                                           item_id=item)
                             for leaf in ('quantity', 'daysSupply', 'pharmacy', 'channel')]
        # The original contract lists every leaf even when unanswered. A future
        # changed adapter cannot silently omit a declared dependency.
        if any(requirement.path not in available_paths for requirement in requirements):
            assessments.append({'dimension_id': dimension, 'item_id': item,
                'state': 'item_representation_unresolved',
                'reason_codes': ['DECLARED_ITEM_LEAF_UNREPRESENTED'],
                'method_version': METHOD_VERSION, 'output_state': 'held'})
            continue
        inputs = assess_required_inputs(profile, requirements,
            finding_id='research-input:' + dimension + ':' + item)
        identity = assess_identity_binding(profile, (), kind=kind, item_id=item,
                                           scope={'year': comparison['binding']['scope'].get('year')})
        assessments.append({'dimension_id': dimension, 'item_id': item,
            'state': 'research_input_preparation_only', 'input_assessment': inputs,
            'identity_assessment': identity, 'output_state': 'held',
            'scope_note': 'Declared source-query leaves, not sufficient inputs for an accepted personal finding.'})
    baseline = []
    for fact in facts:
        path = fact['ref']['path']
        required_scope = 'intended' if path.startswith('guide.fields.coverage.requestedStart') else 'current'
        if (path in LABELS and fact['ref']['subject_id'] == subject
                and fact['ref']['scope'] == required_scope
                and fact.get('usable_as_report') is True
                and fact.get('usable_for_bound_subject') is True
                and fact['report_state'] in {'reported', 'explicit_none'}):
            baseline.append({'label': LABELS[path], 'value': copy.deepcopy(fact['value']),
                             'state': 'reported_not_verified',
                             'report_ref': copy.deepcopy(fact['ref'])})
    return {
        'version': 'comparison-case-preparation-20261101-r1',
        'method_version': METHOD_VERSION, 'assessments': assessments,
        'baseline_reports': baseline, 'declared_constraints': [], 'declared_scenarios': [],
        'constraint_state': 'explicit_scoped_interpretation_required',
        'scenario_state': 'explicit_basis_components_and_accepted_method_required',
        'personal_output_state': 'held', 'question_routing_changed': False,
    }
