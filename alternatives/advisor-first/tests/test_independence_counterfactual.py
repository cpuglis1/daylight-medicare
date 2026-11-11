"""I01 commission counterfactual and I02 leak check for the :8893 ranking code.

Holds confirmed facts, priorities, plan evidence and versions fixed, then zeroes,
multiplies, swaps and removes carrier payouts attached to the plan records. Every
substantive output must stay identical, and no commercial value may appear in
any output. Fictional fixtures; no network, no paid calls. Added November 5, 2026.

Run from this directory: python3 -m unittest test_independence_counterfactual
"""
import copy
import json
import unittest

# test_plans_workspace (via test_http) puts the advisor modules on sys.path; import it first.
from test_plans_workspace import accepted_fixture, allow
from plans_adapters import metric_payload
from plans_authority import METHOD
from plans_ranking import CHECKS, METRICS, recommend, reference_ordering

CANARY = 'CANARY-COMMERCIAL-7f3a'
BASE_PAYOUTS = [694, 0, 347, 694]


def payout_fields(amount, rank):
    """The commercial facts a carrier or FMO record might carry."""
    return {'initial_commission_cents': amount * 100, 'renewal_commission_cents': amount * 50,
            'carrier_payout_note': f'{CANARY}:{amount}', 'carrier_contract': f'{CANARY}:contract',
            'fmo_bonus_tier': rank, 'referral_fee_cents': amount * 10}


def variants(plan_count):
    swapped = list(reversed(BASE_PAYOUTS[:plan_count]))
    adversarial = [0] + [10_000] * (plan_count - 1)   # cheapest plan pays nothing
    return {
        'baseline': BASE_PAYOUTS[:plan_count],
        'zeroed': [0] * plan_count,
        'multiplied': [amount * 10 for amount in BASE_PAYOUTS[:plan_count]],
        'swapped': swapped,
        'adversarial': adversarial,
        'removed': None,
    }


class CounterfactualFixture:
    def __init__(self, amounts, tie=False):
        self.authority = accepted_fixture()
        self.plans = [{'id': f'fictional:{i}'} for i in range(len(amounts))]
        self.order = list(METRICS)
        self.metrics, self.checks = {}, {}
        for i, plan in enumerate(self.plans):
            self.checks[plan['id']] = {key: {'state': 'meets', 'reason_codes': []} for key in CHECKS}
            first = '5' if tie and i in (1, 2) else str(i)
            second = '5' if tie and i in (1, 2) else str(10 - i)
            self.metrics[plan['id']] = {key: {'state': 'available', 'amount': amount}
                                        for key, amount in zip(METRICS, [first, second])}
        allow(self.authority, 'recommendation_method', {'method': METHOD, 'metrics': list(METRICS),
              'checks': list(CHECKS), 'offering_ids': [p['id'] for p in self.plans]})
        for plan in self.plans:
            for key, fact in self.metrics[plan['id']].items():
                allow(self.authority, 'ranking_metric', metric_payload(plan['id'], key, fact))

    def with_payouts(self, amounts):
        plans = copy.deepcopy(self.plans)
        if amounts is not None:
            for rank, (plan, amount) in enumerate(zip(plans, amounts)):
                plan.update(payout_fields(amount, rank))
        return plans

    def recommend(self, plans):
        return recommend('fixture:profile', self.order, plans, copy.deepcopy(self.authority),
                         metrics=copy.deepcopy(self.metrics), checks=copy.deepcopy(self.checks))

    def reference(self, plans):
        return reference_ordering(self.order, plans, copy.deepcopy(self.metrics), scope_supported=True)


def canonical(value):
    return json.dumps(value, sort_keys=True, default=str)


class CommissionCounterfactualTests(unittest.TestCase):
    def assert_invariant(self, tie):
        fixture = CounterfactualFixture(BASE_PAYOUTS, tie=tie)
        baseline_rec = fixture.recommend(fixture.with_payouts(None))
        baseline_ref = fixture.reference(fixture.with_payouts(None))
        # The comparison is only meaningful if the baseline actually ranks plans.
        self.assertTrue(baseline_rec['top_three'], baseline_rec['reason_codes'])
        self.assertTrue(baseline_ref['ordered_ids'], baseline_ref['reason_codes'])
        for name, amounts in variants(len(BASE_PAYOUTS)).items():
            with self.subTest(variant=name, tie=tie):
                plans = fixture.with_payouts(amounts)
                rec, ref = fixture.recommend(plans), fixture.reference(plans)
                self.assertEqual(canonical(rec), canonical(baseline_rec))
                self.assertEqual(canonical(ref), canonical(baseline_ref))
                for output in (rec, ref):
                    text = canonical(output)
                    self.assertNotIn(CANARY, text)
                    self.assertNotIn('commission', text.lower())
                    self.assertNotIn('payout', text.lower())

    def test_recommendation_and_published_ordering_ignore_payouts(self):
        self.assert_invariant(tie=False)

    def test_ties_are_not_broken_by_payouts(self):
        self.assert_invariant(tie=True)

    def test_the_fixture_is_sensitive_to_real_evidence(self):
        # Guard against a vacuous pass: changing a published amount does change the result.
        fixture = CounterfactualFixture(BASE_PAYOUTS)
        before = fixture.reference(fixture.with_payouts(None))
        fixture.metrics['fictional:3'][METRICS[0]]['amount'] = '-1'
        after = fixture.reference(fixture.with_payouts(None))
        self.assertNotEqual(canonical(before), canonical(after))


if __name__ == '__main__':
    unittest.main()
