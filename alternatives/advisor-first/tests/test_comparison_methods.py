"""Synthetic method contracts; no stores, sources, models or Medicare rules."""
import copy
from dataclasses import replace
from decimal import getcontext
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_evidence import ComparisonEvidenceError
from comparison_methods import (BASIS_KEYS, ComparisonMethodError, CostScenario,
    IdentityBinding, MustHave, RequiredInput, ScenarioLine, assess_identity_binding,
    assess_required_inputs, evaluate_cost_scenario, evaluate_must_have)
from comparison_profile import build_comparison_profile
from natural_state import ensure_state

TEMPLATE = json.loads((HERE.parent / 'chat-first/cms-slice/config/profile/customer-profile.template.json').read_text())
SCOPE = {'year': 2026, 'county_fips': '12021'}
SCOPE_KEY = 'fixture:2026-county-role'
NAME = 'readiness.facts.RC22.value.items[].name'
STRENGTH = 'readiness.facts.RC22.value.items[].strength'


def profile():
    guide, record = copy.deepcopy(TEMPLATE['guide']), copy.deepcopy(TEMPLATE['readiness'])
    guide['stateVersion'] = record['stateVersion'] = 10
    natural = ensure_state(record)

    def put(container, name, value, ref):
        container[name] = {'value': value, 'revision': 2, 'status': 'reported',
                           'confirmation': 'reported_by_user', 'source': 'user_text'}
        natural['provenance'][ref] = {'method': 'direct_report', 'status': 'user_reported',
            'subject': 'beneficiary', 'scope': 'current', 'revision': 2, 'supersedesRevision': None}

    for name, value in {'coverage.current': ['original'], 'needs.priorities': ['doctors', 'drugs'],
                        'situation.age65': {'month': 11, 'year': None}}.items():
        put(guide['fields'], name, value, 'guide.' + name)
    for name, value in {
        'RC11': {'choice': 'dates', 'jobEnd': '2026-11', 'coverageEnd': 'unknown'},
        'RC16': {'choice': 'yes', 'start': '2025-01', 'priorMedigap': 'unknown'},
        'RC21': {'choice': 'details', 'items': [{'entity': 'doctor-1', 'practice': 'Synthetic office', 'city': 'Synthetic city'}]},
        'RC22': {'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'name': 'Synthetic same name', 'strength': '5 mg', 'form': 'tablet'},
            {'entity': 'medicine-2', 'name': 'Synthetic same name', 'strength': '10 mg', 'form': 'tablet'}]},
        'RC23': {'choice': 'details', 'items': [{'entity': 'medicine-1', 'pharmacy': 'Synthetic store'}]},
        'RC25': {'choice': 'amount', 'amount': '100', 'includes': 'premiums'},
    }.items():
        put(record['facts'], name, value, 'readiness.' + name)
    return build_comparison_profile(guide, record, requested_scope=SCOPE)


def fact(case, path, item=None):
    return next(f for f in case['facts'] if f['ref']['path'] == path and f['ref']['item_id'] == item)


def basis(value):
    return {key: copy.deepcopy(value[key]) for key in BASIS_KEYS}


def condition(evaluation='true', **changes):
    return {'completeness': 'complete', 'root': {'op': 'predicate', 'id': 'fixture:predicate',
            'evaluation': evaluation, 'source_locator': 'fixture:page-1'}, 'missing_predicates': [], **changes}


def finding(unit='fixture:a', *, identifier='fixture:premium', dimension='monthly_plan_premium',
            item=None, amount='0.10', result='supports', included=('plan_premium',), **changes):
    return {'finding_id': identifier, 'unit_id': unit, 'dimension_id': dimension,
            'subject_or_item_id': item, 'fictional': True, 'result': result,
            'evidence_state': 'reviewed', 'policy_state': 'reviewed_for_exact_purpose',
            'output_state': 'fictional_fixture_only', 'condition_set': condition(),
            'evidence_refs': ['fixture:source'], 'rule_refs': ['fixture:method'],
            'value': {'type': 'decimal', 'amount': amount, 'currency': 'USD', 'unit': 'plan_premium',
                      'period': 'month', 'cost_type': 'published_component', 'scope_key': SCOPE_KEY,
                      'population_basis': 'published', 'network': None, 'channel': None, 'phase': None,
                      'included_components': list(included), 'excluded_components': ['unpriced_care'],
                      'assumptions': []}, **changes}


class RequiredInputTests(unittest.TestCase):
    def setUp(self):
        self.case = profile()

    def assess(self, *requirements):
        return assess_required_inputs(self.case, requirements, finding_id='fixture:requested-check')

    def test_narrow_pharmacy_check_has_no_fill_pricing_or_assistance_prerequisite(self):
        out = self.assess(RequiredInput('readiness.facts.RC23.value.items[].pharmacy', 'medicine-1'))
        self.assertEqual(out['input_state'], 'sufficient_report')
        self.assertEqual(len(out['requirements']), 1)
        self.assertFalse(out['universal_intake'])
        self.assertEqual(out['policy_state'], 'unreviewed')
        self.assertEqual(out['output_state'], 'held')
        self.assertNotIn('Synthetic store', json.dumps(out))
        self.assertEqual(self.assess()['input_state'], 'not_required')

    def test_alias_reuses_only_actual_start_and_does_not_need_prior_medigap(self):
        out = self.assess(RequiredInput('readiness.facts.RC16.value.start', precisions=('month',)))
        self.assertEqual(out['input_state'], 'sufficient_report')
        self.assertEqual(out['requirements'][0]['question_ids'], ['RC16', 'RC16.C1'])
        self.assertEqual(len(out['dependency_refs']), 1)
        self.assertEqual(out, self.assess(RequiredInput('readiness.facts.RC16.value.start', precisions=('month',)),
                                        RequiredInput('readiness.facts.RC16.value.start', precisions=('month',))))

    def test_all41_paths_are_declared_meanings_without_making_them_universal_requirements(self):
        self.assertEqual({q['id'] for q in self.case['questions']},
                         {f'T{i:02d}' for i in range(1, 11)} | {f'RC{i:02d}' for i in range(1, 29)}
                         | {'RC11.C1', 'RC16.C1', 'RC16.C2'})
        for question in self.case['questions']:
            for path in question['canonical_paths']:
                item = next(f['ref']['item_id'] for f in self.case['facts'] if f['ref']['path'] == path)
                out = self.assess(RequiredInput(path, item))
                self.assertIn(question['id'], out['requirements'][0]['question_ids'])
                self.assertFalse(out['universal_intake'])

    def test_partial_age_milestone_does_not_fill_year_or_enrollment(self):
        req = RequiredInput('guide.fields.situation.age65', parts=('month', 'year'))
        out = self.assess(req)
        self.assertEqual(out['input_state'], 'partial')
        self.assertEqual(out['requirements'][0]['missing_parts'], ['year'])
        self.assertEqual(self.assess(replace(req, parts=('month',)))['input_state'], 'sufficient_report')
        self.assertEqual(fact(self.case, 'readiness.facts.RC04.value.choice')['report_state'], 'unanswered')

    def test_unknown_deferred_conflict_stale_absence_and_known_zero_are_distinct(self):
        row = fact(self.case, 'readiness.facts.RC25.value.amount')
        req = RequiredInput(row['ref']['path'])
        for state in ['unknown', 'deferred', 'declined', 'conflicting', 'stale', 'tentative']:
            row['report_state'] = state
            self.assertEqual(self.assess(req)['input_state'], state)
        row.update(report_state='reported', value='0')
        self.assertEqual(self.assess(req)['input_state'], 'sufficient_report')
        self.assertEqual(self.assess(replace(req, expected_revision=1))['input_state'], 'stale')
        row['report_state'] = 'explicit_none'
        self.assertEqual(self.assess(req)['input_state'], 'unanswered')
        self.assertEqual(self.assess(replace(req, allow_explicit_none=True))['input_state'], 'sufficient_report')

    def test_other_item_helper_legacy_and_wrong_time_never_supply_bound_input(self):
        req = RequiredInput(STRENGTH, 'medicine-1')
        row = fact(self.case, STRENGTH, 'medicine-1')
        row['report_state'] = 'unknown'
        self.assertEqual(self.assess(req)['input_state'], 'unknown')
        self.assertEqual(fact(self.case, STRENGTH, 'medicine-2')['report_state'], 'reported')
        row['report_state'] = 'reported'
        for change in [{'capture_subject': 'learner'}, {'usable_for_bound_subject': False}]:
            before = copy.deepcopy(row)
            row.update(change)
            self.assertEqual(self.assess(req)['input_state'], 'unknown')
            row.clear(); row.update(before)
        self.assertEqual(self.assess(replace(req, scope='historical'))['input_state'], 'unanswered')
        row['capture_method'] = 'location_reference'
        self.assertEqual(self.assess(req)['input_state'], 'unknown')

    def test_unsafe_or_itemless_declarations_fail_fixed_codes(self):
        for req in [RequiredInput(STRENGTH), RequiredInput('invented.question'),
                    RequiredInput(STRENGTH, 'medicine-1', scope='unknown')]:
            with self.assertRaisesRegex(ComparisonMethodError, 'REQUIRED_INPUT_DECLARATION_INVALID'):
                self.assess(req)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.case = profile()
        self.refs = (fact(self.case, NAME, 'medicine-1')['ref'], fact(self.case, STRENGTH, 'medicine-1')['ref'])
        self.binding = IdentityBinding('drug_product', 'fixture:product-registry', 'fixture:exact-product-1',
            'medicine-1', SCOPE, self.refs, ('fixture:identity-locator',))

    def assess(self, *bindings):
        return assess_identity_binding(self.case, bindings, kind='drug_product', item_id='medicine-1', scope=SCOPE)

    def test_exact_identity_is_not_coverage_network_or_service_availability(self):
        out = self.assess(self.binding)
        self.assertEqual(out['identity_state'], 'bound')
        self.assertFalse(out['externally_verified'])
        self.assertEqual(out['access_state'], 'not_evaluated')
        self.assertEqual(out['availability_state'], 'not_evaluated')
        self.assertEqual(out['output_state'], 'held')

    def test_namesakes_ambiguous_candidates_and_registry_namespaces_are_preserved(self):
        second = replace(self.binding, namespace='fixture:other-registry')
        out = self.assess(self.binding, second)
        self.assertEqual(out['identity_state'], 'ambiguous')
        self.assertEqual(len(out['candidates']), 2)
        self.assertEqual(self.assess(self.binding, self.binding)['identity_state'], 'bound')
        same_identity = self.assess(self.binding, replace(self.binding, evidence_refs=('fixture:second-locator',)))
        self.assertEqual(same_identity['candidates'][0]['evidence_refs'],
                         ['fixture:identity-locator', 'fixture:second-locator'])
        self.assertEqual(self.assess(replace(self.binding, item_id='medicine-2'))['identity_state'], 'unresolved')

    def test_wrong_year_or_revised_report_requires_new_binding(self):
        self.assertEqual(self.assess(replace(self.binding, scope={'year': 2027}))['identity_state'], 'unresolved')
        fact(self.case, STRENGTH, 'medicine-1')['ref']['report_revision'] = 3
        # Freeze the old receipt rather than letting the mutable test dictionary
        # change the source binding with the report.
        old = copy.deepcopy(self.binding)
        old.report_refs[1]['report_revision'] = 2
        out = self.assess(old)
        self.assertEqual(out['identity_state'], 'unresolved')
        self.assertIn('IDENTITY_REPORT_BINDING_STALE_OR_UNSCOPED', out['reason_codes'])

    def test_unrelated_parent_revision_preserves_exact_item_lineage_but_not_future_receipts(self):
        bound = copy.deepcopy(self.binding)
        for path in [NAME, STRENGTH]:
            fact(self.case, path, 'medicine-1')['ref']['record_revision'] = 11
        self.assertEqual(self.assess(bound)['identity_state'], 'bound')
        future = copy.deepcopy(bound)
        future.report_refs[0]['record_revision'] = 12
        self.assertEqual(self.assess(future)['identity_state'], 'unresolved')


class MustHaveTests(unittest.TestCase):
    def setUp(self):
        self.case = profile()
        self.ref = fact(self.case, 'readiness.facts.RC25.value.amount')['ref']
        self.constraint = MustHave('fixture:explicit-limit', 'monthly_plan_premium', 'beneficiary',
                                  SCOPE_KEY, (self.ref,), operator='at_most', threshold='0.20', basis=basis(finding()['value']))

    def evaluate(self, rows, **kw):
        return evaluate_must_have(self.case, kw.pop('constraint', self.constraint), rows,
                                  unit_ids=kw.pop('units', ['fixture:b', 'current:reported', 'fixture:a', 'fixture:missing']))

    def test_exact_limit_partition_keeps_conflicts_unknown_current_and_defer(self):
        out = self.evaluate([finding('fixture:a'), finding('fixture:b', amount='0.30')])
        self.assertEqual(out['partitions']['known_meets'], ['fixture:a'])
        self.assertEqual(out['partitions']['known_conflicts'], ['fixture:b'])
        self.assertEqual(out['partitions']['unresolved'], ['current:reported', 'fixture:missing'])
        self.assertEqual(out['candidate_order'], ['fixture:b', 'current:reported', 'fixture:a', 'fixture:missing'])
        self.assertEqual(out['hidden_unit_ids'], [])
        self.assertFalse(out['filter_applied'])
        self.assertIn('keep_current', out['available_outcomes'])
        self.assertIn('defer_decision', out['available_outcomes'])
        self.assertIsNone(out['automatic_personal_order'])

    def test_supports_conflicts_and_unknown_do_not_become_one_boolean(self):
        constraint = replace(self.constraint, operator='supports', threshold=None, basis=None)
        rows = [finding('fixture:a'), finding('fixture:b', result='conflicts')]
        self.assertEqual(self.evaluate(rows, constraint=constraint)['partitions']['known_conflicts'], ['fixture:b'])
        for change in [{'result': 'unresolved'}, {'output_state': 'held'}, {'evidence_state': 'disputed'},
                       {'condition_set': condition('unknown')}, {'condition_set': condition(missing_predicates=['fixture:exception'])}]:
            out = self.evaluate([finding('fixture:a', **change)], constraint=constraint)
            self.assertIn('fixture:a', out['partitions']['unresolved'])
            self.assertNotIn('fixture:a', out['partitions']['known_conflicts'])

    def test_plain_priority_cannot_activate_real_constraint_method(self):
        real = replace(self.constraint, constraint_id='explicit-limit')
        out = self.evaluate([finding()], constraint=real)
        self.assertEqual(out['output_state'], 'held')
        self.assertEqual(out['partitions']['known_meets'], [])
        self.assertIn('SCOPED_CONSTRAINT_METHOD_REQUIRED', out['evaluations'][-2]['reason_codes'])
        self.assertEqual(fact(self.case, 'guide.fields.needs.priorities')['value'], ['doctors', 'drugs'])

    def test_stale_constraint_wrong_basis_scope_or_duplicate_findings_hold_only_use(self):
        stale = copy.deepcopy(self.constraint)
        stale.report_refs[0]['report_revision'] = 1
        self.assertIn('fixture:a', self.evaluate([finding()], constraint=stale)['partitions']['unresolved'])
        for changed in [finding(amount='0'), finding(amount='0.20')]:
            self.assertIn('fixture:a', self.evaluate([changed])['partitions']['known_meets'])
        row = finding(); row['value']['period'] = 'year'
        self.assertIn('fixture:a', self.evaluate([row])['partitions']['unresolved'])
        self.assertIn('fixture:a', self.evaluate([finding(), finding()])['partitions']['unresolved'])
        self.assertIn('fixture:a', self.evaluate([finding(amount=None)])['partitions']['unresolved'])
        constraint = replace(self.constraint, operator='supports', threshold=None, basis=None, scope_key='fixture:wrong')
        self.assertIn('fixture:a', self.evaluate([finding()], constraint=constraint)['partitions']['unresolved'])


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.case = profile()
        self.component = finding()
        self.scenario = CostScenario('fixture:specified-scenario', 'fixture:a', 'beneficiary', SCOPE_KEY,
            'USD', 'year', (ScenarioLine('fixture:premium', '12', 'plan_premium', 'month', basis(self.component['value'])),),
            ('unpriced_care',), ('Explicit fictional twelve-month count; no inferred utilization.',),
            (fact(self.case, 'readiness.facts.RC25.value.amount')['ref'],))

    def evaluate(self, components=None, scenario=None):
        return evaluate_cost_scenario(self.case, scenario or self.scenario,
                                      [self.component] if components is None else components)

    def test_exact_explicit_subtotal_is_never_complete_annual_cost_or_quote(self):
        out = self.evaluate()
        self.assertEqual(out['subtotal']['amount'], '1.20')
        self.assertEqual(out['subtotal']['period'], 'year')
        self.assertEqual(out['claim_kind'], 'declared_scenario_subtotal')
        self.assertEqual(out['excluded_components'], ['unpriced_care'])
        self.assertIsNone(out['complete_total'])
        self.assertIsNone(out['quote'])
        self.assertFalse(out['automatic_annualization'])
        self.assertFalse(out['inferred_utilization'])
        self.assertEqual(out['output_state'], 'fictional_fixture_only')
        self.assertFalse(out['personalized_recommendation_allowed'])

    def test_missing_held_or_unknown_price_never_becomes_zero(self):
        self.assertIsNone(self.evaluate([])['subtotal'])
        self.assertIsNone(self.evaluate([finding(output_state='held')])['subtotal'])
        self.assertIsNone(self.evaluate([finding(condition_set=condition('unknown'))])['subtotal'])
        self.component['value']['amount'] = '0'
        self.assertEqual(self.evaluate()['subtotal']['amount'], '0')
        self.component['value']['amount'] = None
        out = self.evaluate()
        self.assertIsNone(out['subtotal'])
        self.assertIn('COMPONENT_AMOUNT_UNKNOWN_OR_INEXACT', out['reason_codes'])

    def test_exact_sum_is_independent_of_global_decimal_precision(self):
        old_precision = getcontext().prec
        try:
            getcontext().prec = 2
            self.component['value']['amount'] = '123456789012345678901234567890.10'
            out = self.evaluate()
            self.assertEqual(out['subtotal']['amount'], '1481481468148148146814814814681.20')
        finally:
            getcontext().prec = old_precision

    def test_no_substituted_period_currency_pharmacy_scope_or_population(self):
        for key, changed in [('period', 'year'), ('currency', 'EUR'), ('scope_key', 'fixture:other'),
                             ('population_basis', 'personal'), ('network', 'out_of_network'),
                             ('channel', 'mail_order'), ('phase', 'another_phase'),
                             ('included_components', ['different_component'])]:
            row = copy.deepcopy(self.component); row['value'][key] = changed
            with self.subTest(key=key):
                self.assertIsNone(self.evaluate([row])['subtotal'])

    def test_duplicate_or_overlapping_components_do_not_double_count(self):
        with self.assertRaisesRegex(ComparisonMethodError, 'COST_SCENARIO_LINE_INVALID'):
            self.evaluate(scenario=replace(self.scenario, lines=self.scenario.lines * 2))
        second = finding(identifier='fixture:also-premium')
        second_line = replace(self.scenario.lines[0], component_id='fixture:also-premium')
        out = self.evaluate([self.component, second], replace(self.scenario, lines=self.scenario.lines + (second_line,)))
        self.assertIsNone(out['subtotal'])
        self.assertIn('COMPONENT_SCOPE_OVERLAP', out['reason_codes'])

    def test_unaccepted_real_components_and_stale_reports_keep_real_purposes_held(self):
        real = replace(self.scenario, scenario_id='real-scenario')
        out = self.evaluate(scenario=real)
        self.assertEqual(out['output_state'], 'held')
        self.assertIsNone(out['subtotal'])
        self.assertIn('EXACT_RELEASE_REQUIRED', out['reason_codes'])
        stale = copy.deepcopy(self.scenario)
        stale.report_refs[0]['report_revision'] = 1
        out = self.evaluate(scenario=stale)
        self.assertIsNone(out['subtotal'])
        self.assertIn('SCENARIO_REPORT_BINDING_STALE_OR_UNSCOPED', out['reason_codes'])

    def test_floats_nan_negative_and_implicit_quantities_are_rejected(self):
        for quantity in [12, 0.1, 'NaN', '-1', '12 months', '1e2']:
            with self.subTest(quantity=quantity), self.assertRaisesRegex(ComparisonMethodError, 'EXACT_NONNEGATIVE_DECIMAL_REQUIRED'):
                self.evaluate(scenario=replace(self.scenario, lines=(replace(self.scenario.lines[0], quantity=quantity),)))

    def test_methods_do_not_mutate_inputs_or_export_report_text_and_reject_economics(self):
        before = copy.deepcopy((self.case, self.scenario, self.component))
        out = self.evaluate()
        self.assertEqual((self.case, self.scenario, self.component), before)
        self.assertNotIn('Synthetic', json.dumps(out))
        self.assertEqual(out, self.evaluate())
        self.component['commission'] = 'fixture:commercial-canary'
        with self.assertRaisesRegex(ComparisonEvidenceError, 'ECONOMIC_CONTEXT_FORBIDDEN'):
            self.evaluate()


if __name__ == '__main__':
    unittest.main()
