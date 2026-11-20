"""Fictional closing summary checks using the existing conversation reports."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

import test_natural_flow as harness
import closing_options


def listing(identifier, company, letter, cents):
    return {'id': identifier, 'company': company, 'variant': letter,
            'monthly_cents': cents, 'source_effective_date': '2026-10-01'}


class ClosingOptionsTests(TestCase):
    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)
        for field, value in {
            'subject.role': 'self', 'comparison.scope.zip': '34102',
            'situation.age65': {'month': 10, 'year': 2026, 'first_day': False},
            'medigap.pricingSex': 'Male', 'medigap.tobaccoCategory': 'Non-Tobacco',
            'needs.costPreference': 'predictable', 'needs.priorities': ['bills', 'doctors'],
            'needs.providers': 'Dr. Fiction; Dr. Example',
        }.items():
            self.put(field, value)
        self.rates = {
            'status': 'matched_source_prices',
            'profile': {'zip': '34102', 'age': 65, 'gender': 'Male', 'tobacco': 'Non-Tobacco',
                        'requested_effective_date': '2026-11-10'},
            'plans': [listing('g-z', 'Zeta Mutual', 'G', 16000), listing('g-a', 'Acme Mutual', 'G', 16000),
                      listing('g-a2', 'Acme Mutual', 'G', 17000), listing('n-z', 'Zeta Mutual', 'N', 13000),
                      listing('f', 'Acme Mutual', 'F', 10000), listing('hdg', 'Acme Mutual', 'HDG', 10000)],
        }
        self.checks = [
            {'kind': 'doctor', 'key': 'doctor:doctor-1',
             'original_medicare': {'state': 'may_accept', 'record_date': '2026-10-02'}},
            {'kind': 'doctor', 'key': 'doctor:doctor-2', 'state': 'confirmed'},
        ]

    def put(self, field, value):
        self.flow.put(self.g, field, value, 'user_text')

    def summary(self):
        before = deepcopy((self.g, self.r, self.rates, self.checks))
        result = closing_options.status(self.flow, self.g, self.r,
                                        medigap_result=self.rates, doctor_results=self.checks)
        self.assertEqual((self.g, self.r, self.rates, self.checks), before)
        self.assertFalse(self.calls)
        return result

    def test_exact_result(self):
        self.assertEqual(self.summary(), {'version': 'closing-options-v1', 'reason': None, 'options': {
            'basis': {'path': 'original_medigap', 'path_state': 'leaning',
                      'cost_preference': 'predictable', 'priorities': ['bills', 'doctors']},
            'medigap': {'status': 'ready', 'still_needed': [], 'excluded_count': 1,
                        'first': {'letter': 'G', 'company': 'Acme Mutual', 'rate_id': 'g-a',
                                  'monthly_cents': 16000, 'rate_date': '2026-10-01', 'company_count': 2},
                        'alternative': {'letter': 'N', 'company': 'Zeta Mutual', 'rate_id': 'n-z',
                                        'monthly_cents': 13000, 'rate_date': '2026-10-01', 'company_count': 1}},
            'part_d': {'address': True, 'named': None, 'reason': 'medicines_not_checked'},
            'doctors': [{'id': 'doctor-1', 'state': 'may_accept', 'record_date': '2026-10-02'},
                        {'id': 'doctor-2', 'state': 'unknown', 'record_date': None}],
        }})

    def test_missing_detail_and_mismatched_source_profile(self):
        self.rates['profile']['zip'] = '34103'
        medigap = self.summary()['options']['medigap']
        self.assertEqual((medigap['status'], medigap['first']), ('unsupported', None))
        self.put('medigap.tobaccoCategory', 'unknown')
        medigap = self.summary()['options']['medigap']
        self.assertEqual((medigap['status'], medigap['still_needed']), ('missing', ['MG_TOBACCO']))

    def test_missing_letter_keeps_listed_option(self):
        self.rates['plans'][3]['monthly_cents'] = None
        medigap = self.summary()['options']['medigap']
        self.assertEqual((medigap['status'], medigap['first']['letter'], medigap['alternative']),
                         ('unsupported', 'G', None))

    def test_advantage_and_original_without_predictable_costs_have_no_rule(self):
        empty = {'version': 'closing-options-v1', 'options': None, 'reason': 'no_rule_yet'}
        for start in ('medicare_advantage', 'both'):
            self.put('intent.pathStart', start)
            self.assertEqual(self.summary(), empty)
        self.put('intent.coveragePath', 'medicare_advantage')
        self.put('intent.pathStart', 'original_medigap')
        self.assertEqual(self.summary(), empty)
        self.put('intent.coveragePath', 'original_medigap')
        self.put('needs.costPreference', 'lower_monthly')
        self.assertEqual(self.summary(), empty)

    def test_priority_alone_is_a_reported_basis_and_payments_have_no_effect(self):
        self.put('needs.costPreference', 'unknown')
        expected = self.summary()
        self.assertEqual(expected['options']['basis']['priorities'], ['bills', 'doctors'])
        self.assertIsNone(expected['options']['basis']['cost_preference'])
        for index, plan in enumerate(self.rates['plans']):
            plan.update(commission=1000 * index, monthly_with_discounts_cents=0)
        self.assertEqual(self.summary(), expected)

    def test_the_current_visit_summary_pairs_dated_rates_with_unresolved_checks(self):
        self.put('intent.coveragePath', 'original_medigap')
        self.flow.closing_price_read = lambda _: self.rates
        payload = {'guide': self.g, 'record': self.r, 'medigapProfile': closing_options.medigap_profile.profile(self.g),
                   'enrollment': {'line': {'plan': 'original_plus', 'next': {'text': 'Compare the listed rates.'}},
                                  'record': {'components': {'medigap': 'chosen', 'part_d': 'chosen'}}},
                   'conversationCheck': {'results': self.checks}}
        closing_options.attach(self.flow, payload)
        rows = {row['label']: row['value'] for row in payload['closingResearch']['rows']}
        self.assertIn('$160.00/month listed', rows['Medigap Plan G'])
        self.assertIn('$130.00/month listed', rows['Medigap Plan N'])
        self.assertIn('0 of 2', rows['Doctors'])
        self.assertIn('Confirm your exact medicines', rows['Medicines'])
        self.assertEqual(rows['Next'], 'Compare the listed rates.')
