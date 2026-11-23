"""D214: exact evidence, conditional drugs, cost scope and unchanged ranking.

Fictional records only; no model, database, network or profile persistence.
The separate journey suite exercises retained local evidence through real turns.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(_paths.REPO / 'infrastructure/daylight-data/src'))
import one_call_plan_checks as cards

MA = '2026:H0000:001:000'
PDP = '2026:S0000:001:000'
OTHER = '2026:H0000:002:000'


def inputs(**extra):
    return {'scope': {'year': 2026, 'county_fips': '12021'}, 'doctors': 'list', 'medicines': 'yes', **extra}


def medicine(**extra):
    return {'name': 'Fictional tablet 20 mg', 'rxcui': '123', 'state': 'covered', 'evidence_date': '2026-09-16',
            'prior_authorization': False, 'step_therapy': False, 'quantity_limit': False, **extra}


def formulary(*meds):
    return {'kind': 'formulary', 'products': [m['rxcui'] for m in meds],
            'plans': {p: {'medicines': list(meds)} for p in (MA, PDP)}}


def matrix(**row):
    return {'kind': 'doctor_matrix', 'key': 'doctor:doctor-1', 'name': 'Dr. Fictional Vale',
            'office_parts': {'street': '1 Fictional St', 'city': 'Naples'}, 'date': '2026-11-22',
            'plans': {MA: {'state': 'dated_listing', 'membership': 'listed_in_network',
                           'evidence_dates': ['2026-09-23'], **row}},
            'original_medicare': {'state': 'accepts', 'record_date': '2026-09-16'}}


def price(**extra):
    return {'state': 'offline_average_candidate', 'start': '2026-12-01', 'end': '2026-12-31',
            'plan_premium_cents': 1000, 'drug_spending_cents': 1234, 'plan_premium_plus_drugs_cents': 2234, **extra}


class Medicines(unittest.TestCase):
    def check(self, *rows):
        return cards.medicines(inputs(), MA, formulary(*rows))

    def test_exact_products_with_negative_restriction_flags_have_dated_listing(self):
        out = self.check(medicine(), medicine(name='Other fictional tablet', rxcui='456'))
        self.assertEqual(out['indicator'], 'supported')
        self.assertIn('2 of 2', out['note'])
        self.assertIn('2026-09-16', out['note'])

    def test_each_restriction_and_unresolved_flag_requires_warning(self):
        for key, word in cards.RESTRICTIONS:
            with self.subTest(key=key):
                out = self.check(medicine(**{key: True}))
                self.assertEqual((out['state'], out['indicator']), ('unknown', 'warning'))
                self.assertIn(word, out['note'])
                self.assertIn('not an approval', out['note'])
                out = self.check(medicine(**{key: None}))
                self.assertEqual(out['indicator'], 'warning')

    def test_known_absence_and_missing_evidence_are_different(self):
        absent = self.check(medicine(state='not_listed'))
        unknown = self.check(medicine(state='unknown'))
        self.assertEqual((absent['state'], unknown['state']), ('not_met', 'unknown'))
        self.assertIn('Not listed', absent['note'])
        self.assertIn('Could not verify', unknown['note'])

    def test_missing_date_or_incomplete_list_cannot_be_green(self):
        self.assertEqual(self.check(medicine(evidence_date=None))['indicator'], 'warning')
        evidence = formulary(medicine())
        evidence['products'].append('456')
        self.assertEqual(cards.medicines(inputs(), MA, evidence)['indicator'], 'warning')

    def test_no_drug_benefit_and_no_medicine_report_are_not_coverage_findings(self):
        out = cards.medicines(inputs(), MA, {}, includes_drugs=False)
        self.assertEqual((out['state'], out['outcome']), ('not_met', 'No Part D drug coverage'))
        out = cards.medicines(inputs(medicines='no'), MA, {})
        self.assertEqual(out['indicator'], 'information')
        self.assertIn('not a drug-coverage check', out['note'])


class Doctors(unittest.TestCase):
    def check(self, rows, expected=None, **extra):
        return cards.doctors(inputs(), MA, rows, expected or {'doctor-1': {'name': 'Dr. Fictional Vale'}}, **extra)

    def test_all_exact_offices_need_dated_applicable_evidence(self):
        out = self.check({'doctor:doctor-1': matrix()})
        self.assertEqual(out['indicator'], 'supported')
        self.assertIn('1 of 1', out['note'])
        self.assertIn('does not confirm appointment', out['note'])
        out = self.check({'doctor:doctor-1': matrix()}, {'doctor-1': {}, 'doctor-2': {'name': 'Dr. Fictional Other'}})
        self.assertEqual((out['indicator'], out['state']), ('warning', 'unknown'))
        self.assertIn('Dr. Fictional Other', out['note'])

    def test_conflict_stale_and_out_of_network_are_not_conflated(self):
        for state, word in (('conflict', 'records disagree'), ('stale', 'newer evidence needed')):
            out = self.check({'doctor:doctor-1': matrix(state=state)})
            self.assertEqual(out['state'], 'unknown')
            self.assertIn(word, out['note'])
        out = self.check({'doctor:doctor-1': matrix(state='confirmed', membership='out_of_network')})
        self.assertEqual(out['state'], 'not_met')
        self.assertIn('Confirmed out of network', out['note'])

    def test_medicare_record_is_not_select_network_evidence(self):
        for select in (None, True):
            out = self.check({'doctor:doctor-1': matrix()}, medigap={'select_observed': select})
            self.assertEqual(out['indicator'], 'warning')
            self.assertIn('SELECT', out['note'])
        out = self.check({'doctor:doctor-1': matrix()}, medigap={'select_observed': False})
        self.assertEqual(out['indicator'], 'supported')
        self.assertIn('Medicare assignment', out['note'])


class Costs(unittest.TestCase):
    def test_scoped_components_and_exact_period_are_visible(self):
        out = cards.estimate(price())
        self.assertEqual(out['indicator'], 'supported')
        for text in ('$22.34', '$10.00', '$12.34', 'Dec 01, 2026', 'Dec 31, 2026', 'retail averages', 'Excludes Part B', 'not total'):
            self.assertIn(text, out['note'])
        self.assertEqual(cards.total_cost()['indicator'], 'warning')

    def test_bad_sum_missing_period_wrong_year_or_unaccepted_state_is_held(self):
        for change in ({'drug_spending_cents': -1}, {'plan_premium_plus_drugs_cents': 1234}, {'start': None},
                       {'start': '2027-01-01'}, {'state': 'held'}, {'drug_spending_cents': True}):
            self.assertEqual(cards.estimate(price(**change))['indicator'], 'warning', change)

    def test_zero_estimate_and_explicit_days_supply_assumption(self):
        row = price(plan_premium_cents=0, drug_spending_cents=0, plan_premium_plus_drugs_cents=0,
                    summary={'medicines': [{'name': 'Fictional tablet', 'days_supply_assumed': True}]})
        out = cards.estimate(row)
        self.assertEqual(out['indicator'], 'supported')
        self.assertIn('$0.00', out['note'])
        self.assertIn('30-day supply assumption', out['note'])

    def test_unsupported_case_gets_human_reason_not_an_internal_code(self):
        out = cards.estimate({'state': 'held', 'hold': 'criteria_unresolved'})
        self.assertIn('coverage requirements', out['note'])
        self.assertNotIn('criteria_unresolved', out['note'])


class Projection(unittest.TestCase):
    def fixture(self):
        row = {'checks': [{'id': 'doctors', 'state': 'unknown', 'note': 'old', 'kind': 'priority'}],
               'group': 'priority', 'rank': 1, 'key': ['0'], 'recommended': False}
        return {kind: {'plans': {key: deepcopy(row) for key in ids}, 'recommended_ids': [],
                       'groups': [{'ids': ids}]} for kind, ids in
                (('advantage', [MA, OTHER]), ('part_d', [PDP]), ('medigap', ['gap']))}

    def project(self, out, **extra):
        return cards.project(out, inputs(), ma_plans=[{'id': MA, 'drugs': True}, {'id': OTHER, 'drugs': False}],
                             medigap_result={'plans': [{'id': 'gap', 'monthly_cents': 15000, 'select_observed': None}]}, **extra)

    def test_additive_projection_covers_all_three_plan_types_without_ranking_changes(self):
        out = self.fixture(); before = deepcopy(out)
        self.project(out, checks=[formulary(medicine()), matrix()], expected_doctors={'doctor-1': {}})
        for kind in ('advantage', 'part_d', 'medigap'):
            for key, row in out[kind]['plans'].items():
                display = row.pop('card_checks')
                self.assertEqual(row, before[kind]['plans'][key])
                self.assertEqual(next(c for c in display if c['id'] == 'total_cost')['indicator'], 'warning')
                if kind == 'medigap':
                    self.assertEqual(next(c for c in display if c['id'] == 'premium')['indicator'], 'supported')
                    self.assertIn('$150.00', next(c for c in display if c['id'] == 'premium')['note'])
                    self.assertEqual(next(c for c in display if c['id'] == 'medicines')['indicator'], 'information')
                elif kind == 'part_d':
                    self.assertFalse(any(c['id'] == 'doctors' for c in display))
        self.assertFalse(out['plan_card_checks']['ranking_changed'])

    def test_single_plan_cost_uses_exact_offering_never_plan_name(self):
        out = self.fixture()
        result = {'kind': 'prescription', 'offering_id': PDP, 'name': 'Shared plan name',
                  'amounts': {key: val for key, val in price().items() if key.endswith('_cents')},
                  'start': '2026-12-01', 'end': '2026-12-31'}
        self.project(out, checks=[result])
        pdp = out['part_d']['plans'][PDP]['card_checks']
        ma = out['advantage']['plans'][MA]['card_checks']
        self.assertEqual(next(c for c in pdp if c['id'] == 'drug_cost')['indicator'], 'supported')
        self.assertEqual(next(c for c in ma if c['id'] == 'drug_cost')['indicator'], 'warning')

    def test_wrong_year_or_county_has_no_positive_finding(self):
        for scope in ({'year': 2027, 'county_fips': '12021'}, {'year': 2026, 'county_fips': '12071'}):
            out = self.fixture()
            cards.project(out, inputs(scope=scope), checks=[formulary(medicine()), matrix()])
            self.assertTrue(all(c['indicator'] == 'warning' for kind in ('advantage', 'part_d', 'medigap')
                                for row in out[kind]['plans'].values() for c in row['card_checks']))


class ReceiptBoundReuse(unittest.TestCase):
    def test_reuse_requires_current_inputs_and_source_controls_on_every_read(self):
        import drug_comparison

        class Service:
            def __init__(self):
                self.calls = 0
                self.stopped = False

            def _scope(self):
                if self.stopped:
                    raise RuntimeError('SOURCE_STOP')

            def pharmacy(self, refs, identifier, outlet):
                return {'status': 'preferred'}, {}

            def estimate(self, report, revision):
                self.calls += 1
                return {**price(), 'receipt': repr((report, revision))}

            def check_receipt(self, report, revision, receipt):
                return not self.stopped and receipt == repr((report, revision))

        service, cache = Service(), {}
        report = {'pharmacy': {'channel': 'retail'}, 'quantity': 30}
        plans = {PDP: {'name': 'Fictional plan'}}
        first = drug_comparison.compare(service, report, 1, plans, costs=True, cache=cache)
        again = drug_comparison.compare(service, report, 1, plans, costs=True, cache=cache)
        self.assertEqual(first, again)
        self.assertEqual(service.calls, 1)
        drug_comparison.compare(service, {**report, 'quantity': 60}, 2, plans, costs=True, cache=cache)
        self.assertEqual(service.calls, 2)
        service.stopped = True
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_STOP'):
            drug_comparison.compare(service, report, 1, plans, costs=True, cache=cache)


if __name__ == '__main__':
    unittest.main()
