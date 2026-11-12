"""Explicit fictional teaching scenarios, using the existing exact arithmetic.

These are invented prices with declared quantities, not plan data or user facts.
Nothing in this module supplies Medicare source or personal method authority.
"""
import copy
from comparison_methods import QUESTION_IDS, CostScenario, ScenarioLine, evaluate_cost_scenario


def cost_example(visits=2, *, unknown_drug=True):
    """Explicit fictional quantities using the existing comparison arithmetic.

    These figures are invented demonstrations, never Medicare prices or quotes.
    No medical cap, deductible or benefit rule is applied by this example.
    """
    ref = {'path': 'fixture:declared-scenario', 'item_id': None, 'subject_id': 'beneficiary',
           'scope': 'intended', 'report_revision': 1, 'record_revision': 1}
    profile = {'profile_binding': {'subject_id': 'beneficiary'},
        'questions': [{'id': q} for q in sorted(QUESTION_IDS)],
        'facts': [{'ref': ref, 'report_state': 'reported', 'capture_subject': 'beneficiary',
                   'usable_as_report': True, 'usable_for_bound_subject': True}]}
    components, lines, display = [], [], []
    declarations = [('premium', 'Each month', '100.00', '12', 'month', 'premium'),
                    ('visits', 'Visits in this example', '25.00', str(visits), 'visit', 'medical_cost_sharing')]
    if not unknown_drug:
        declarations.append(('drug', 'Drug fills in this example', '15.00', '12', 'fill', 'drug_cost_sharing'))
    for name, label, amount, quantity, period, scope in declarations:
        value = {'type': 'decimal', 'amount': amount, 'currency': 'USD', 'unit': name,
            'period': period, 'cost_type': 'scenario_estimate', 'scope_key': 'fixture:2026',
            'population_basis': 'fictional', 'network': None, 'channel': None, 'phase': None,
            'included_components': [scope], 'excluded_components': [],
            'assumptions': ['Invented amounts; no Medicare benefit rules are applied.']}
        basis = {key: copy.deepcopy(val) for key, val in value.items() if key not in {'type', 'amount'}}
        finding = {'finding_id': 'fixture:' + name, 'unit_id': 'fixture:example', 'fictional': True,
            'result': 'supports', 'evidence_state': 'reviewed',
            'policy_state': 'reviewed_for_exact_purpose', 'output_state': 'fictional_fixture_only',
            'evidence_refs': ['fixture:invented-amounts'], 'rule_refs': ['fixture:arithmetic'],
            'condition_set': {'completeness': 'complete', 'root': {'op': 'predicate',
                'id': 'fixture:declared', 'evaluation': 'true', 'source_locator': 'fixture:example'},
                'missing_predicates': []}, 'value': value}
        components.append(finding)
        lines.append(ScenarioLine('fixture:' + name, quantity, name, period, basis))
        display.append({'label': label, 'amount': amount, 'quantity': quantity, 'priced_period': period})
    excluded = ('unpriced_services', 'drug_costs') if unknown_drug else ('unpriced_services',)
    scenario = CostScenario('fixture:example', 'fixture:example', 'beneficiary', 'fixture:2026',
        'USD', '2026', tuple(lines), excluded,
        ('12 explicitly declared monthly payments; invented prices and visit counts.',), (ref,))
    receipt = evaluate_cost_scenario(profile, scenario, components)
    return {'label': 'Fictional arithmetic example — invented prices, not Medicare costs',
        'fictional': True, 'components': display, 'unknown_components': list(excluded),
        'receipt': receipt}

