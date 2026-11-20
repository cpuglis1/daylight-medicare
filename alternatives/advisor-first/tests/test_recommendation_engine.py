"""D147 tiered recommendation: deterministic rules on synthetic plans. No network or model."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recommendation_engine as engine


def inputs(**changes):
    value = {'version': engine.INPUTS_VERSION,
             'scope': {'zipcode': '34102', 'county_fips': '12021', 'year': 2026},
             'medigap': {'status': 'ready', 'zipcode': '34102', 'age': 66, 'reported_age': 66,
                         'gender': 'Female', 'tobacco': 'Non-Tobacco', 'first_eligible': None},
             'part_d_status': 'ready', 'doctors': None, 'medicines': 'no', 'travel': [],
             'cost_preference': None, 'priorities': [], 'current_coverage': [], 'medicaid': None}
    for key, item in changes.items():
        if key in value['medigap'] and key not in value:
            value['medigap'][key] = item
        else:
            value[key] = item
    return value


MA = [
    {'id': 'hmo-cheap', 'name': 'A HMO', 'type': 'HMO', 'restrictions': [], 'drugs': True,
     'premium': '0', 'in_network_limit': '6700'},
    {'id': 'ppo-mid', 'name': 'B PPO', 'type': 'PPO', 'restrictions': [], 'drugs': True,
     'premium': '25', 'in_network_limit': '4500'},
    {'id': 'ppo-nodrug', 'name': 'C PPO', 'type': 'PPO', 'restrictions': [], 'drugs': False,
     'premium': '0', 'in_network_limit': '5000'},
    {'id': 'dsnp', 'name': 'D D-SNP', 'type': 'HMO D-SNP', 'restrictions': ['Dual Eligible Special Needs Plan'],
     'drugs': True, 'premium': '0', 'in_network_limit': '3000'},
    {'id': 'csnp', 'name': 'E C-SNP', 'type': 'HMO C-SNP', 'restrictions': ['Chronic Condition Special Needs Plan'],
     'drugs': True, 'premium': '0', 'in_network_limit': '3000'},
    {'id': 'held', 'name': 'F PPO', 'type': 'PPO', 'restrictions': [], 'drugs': True,
     'premium': None, 'in_network_limit': '4000'},
]


def medigap(*rows):
    return {'status': 'matched_source_prices', 'plans': [
        {'id': f'{letter}-{cents}', 'variant': letter, 'monthly_cents': cents, 'select_observed': select}
        for letter, cents, select in rows]}


GAP = medigap(('G', 15000, False), ('N', 11000, False), ('HDG', 6000, False), ('F', 20000, False),
              ('A', 12000, False), ('G', 14000, True))


def part_d(*rows):
    def field(cents):
        return {'state': 'published', 'value_encoding': 'integer_cents', 'value': cents}
    return {'status': 'published_plans', 'plans': [
        {'id': name, 'fields': {'total_premium': field(premium), 'annual_deductible': field(deductible)}}
        for name, premium, deductible in rows]}


PDP = part_d(('pdp-zero', 0, 61500), ('pdp-low-ded', 9800, 0), ('pdp-mid', 2590, 60100))


def run(**changes):
    return engine.evaluate(inputs(**changes), ma_plans=copy.deepcopy(MA), medigap_result=copy.deepcopy(GAP),
                           part_d_result=copy.deepcopy(PDP))


class TieredRecommendationTests(unittest.TestCase):
    def test_eligibility_unknown_or_failed_is_never_recommended(self):
        result = run()['advantage']['plans']
        self.assertEqual(result['csnp']['group'], 'excluded')     # joining rule not confirmed
        self.assertEqual(result['dsnp']['group'], 'excluded')     # Medicaid not reported
        self.assertEqual(run(medicaid=True)['advantage']['plans']['dsnp']['group'], 'priority')
        self.assertEqual(run(medicaid=False)['advantage']['plans']['dsnp']['checks'][0]['state'], 'not_met')

    def test_hard_need_filters_and_unknown_is_never_a_miss(self):
        result = run(medicines='yes', doctors='list', priorities=['doctors'])['advantage']
        plans = result['plans']
        self.assertEqual(plans['ppo-nodrug']['group'], 'excluded')   # medicines reported, no drug coverage
        self.assertEqual(plans['hmo-cheap']['group'], 'priority')    # doctors not checked: stays in
        doctors = next(c for c in plans['hmo-cheap']['checks'] if c['id'] == 'doctors')
        self.assertEqual((doctors['state'], doctors['kind']), ('unknown', 'priority'))
        self.assertEqual(result['recommended_ids'], [])              # medicines not checked: no pick
        self.assertIn('not checked against plan drug lists', result['no_pick_reason'])

    def test_failed_priority_moves_a_plan_to_the_middle_group(self):
        plans = run(travel=['elsewhere_us'], priorities=['travel'])['advantage']['plans']
        self.assertEqual(plans['hmo-cheap']['group'], 'needs')       # HMO: mostly emergencies elsewhere
        self.assertEqual(plans['ppo-mid']['group'], 'priority')
        self.assertTrue(plans['ppo-mid']['recommended'])             # the PPO with drug coverage

    def test_cost_preference_orders_inside_a_group_and_ties_share_a_rank(self):
        cheap = run()['advantage']
        self.assertEqual(cheap['plans']['hmo-cheap']['rank'], 1)
        self.assertEqual(cheap['plans']['ppo-mid']['rank'], 2)
        self.assertEqual(cheap['recommended_ids'], ['hmo-cheap'])
        # No drug coverage is a need failure unless other drug coverage was reported.
        self.assertEqual(cheap['plans']['ppo-nodrug']['group'], 'excluded')
        self.assertEqual(run(current_coverage=['military'])['advantage']['recommended_ids'], ['ppo-nodrug'])
        predictable = run(cost_preference='predictable')['advantage']
        self.assertEqual(predictable['recommended_ids'], ['ppo-mid'])  # lowest yearly limit
        self.assertIsNone(predictable['plans']['held']['rank'])       # missing premium: unranked, not worse
        tie = engine.evaluate(inputs(), ma_plans=[dict(MA[0], id='x'), dict(MA[0], id='y')],
                              medigap_result=GAP, part_d_result=PDP)['advantage']
        self.assertEqual(tie['recommended_ids'], ['x', 'y'])

    def test_medigap_letters_cf_rule_and_select(self):
        result = run(cost_preference='predictable', priorities=['bills'], doctors='list')['medigap']
        plans = result['plans']
        self.assertEqual(plans['F-20000']['group'], 'excluded')      # eligibility unconfirmed
        self.assertEqual(plans['N-11000']['group'], 'needs')         # copays
        self.assertEqual(plans['G-15000']['group'], 'priority')
        self.assertTrue(all(next(c for c in plan['checks'] if c['id'] == 'doctors')['state'] == 'unknown'
                            for plan in plans.values()))
        self.assertEqual(run(first_eligible='2019-12')['medigap']['plans']['F-20000']['group'], 'priority')
        self.assertEqual(run(reported_age=72)['medigap']['plans']['F-20000']['group'], 'excluded')
        self.assertEqual(run(reported_age=71)['medigap']['plans']['F-20000']['group'], 'excluded')
        abroad = run(travel=['outside_us'], priorities=['travel'])['medigap']['plans']
        self.assertEqual(abroad['A-12000']['group'], 'needs')
        self.assertEqual(abroad['HDG-6000']['group'], 'priority')

    def test_part_d_names_a_pick_only_without_medicines(self):
        none = run()['part_d']
        self.assertEqual(none['recommended_ids'], ['pdp-zero'])
        self.assertEqual(run(cost_preference='predictable')['part_d']['recommended_ids'], ['pdp-low-ded'])
        for medicines in ('yes', 'unknown', None):
            with self.subTest(medicines=medicines):
                result = run(medicines=medicines)['part_d']
                self.assertEqual(result['recommended_ids'], [])
                self.assertEqual(result['groups'][0]['ids'][0], 'pdp-zero')  # still ordered

    def test_coverage_path(self):
        doctors = run(doctors='list', priorities=['doctors', 'bills'], cost_preference='predictable')['path']
        self.assertEqual(doctors['recommended_ids'], [])  # doctor evidence remains unknown
        self.assertIn('unresolved', doctors['no_pick_reason'])
        self.assertEqual(doctors['plans']['advantage']['group'], 'needs')   # predictable: copays
        cheap = run(cost_preference='lower_monthly')['path']
        self.assertEqual(cheap['recommended_ids'], ['advantage'])           # $0 MA vs $60 + $0
        self.assertEqual(run(current_coverage=['employer'])['path']['state'], 'held')
        self.assertEqual(run()['path']['recommended_ids'], [])              # nothing stated yet
        abroad = run(travel=['outside_us'], priorities=['travel'], cost_preference='lower_monthly')['path']
        self.assertEqual(abroad['recommended_ids'], ['original'])            # a met priority outranks a met preference
        tie = run(medicines='yes')['path']                                  # nothing separates them
        self.assertEqual(tie['recommended_ids'], [])
        self.assertIn('unresolved', tie['no_pick_reason'])

    def test_unavailable_tabs_do_not_guess(self):
        result = run(medigap={'status': 'unsupported', 'zipcode': '34110', 'age': None, 'reported_age': None,
                              'gender': None, 'tobacco': None})
        self.assertEqual(result['medigap']['state'], 'unavailable')
        lower = engine.evaluate(dict(inputs(cost_preference='lower_monthly'),
                                     medigap={'status': 'missing', 'zipcode': None, 'age': None, 'reported_age': None,
                                              'gender': None, 'tobacco': None}),
                                ma_plans=MA, medigap_result=None, part_d_result=PDP)['path']
        self.assertEqual(lower['plans']['original']['checks'][0]['state'], 'unknown')

    def test_commission_values_cannot_change_a_result(self):
        base = run(doctors='list', priorities=['doctors'])
        paid = copy.deepcopy(MA)
        for i, plan in enumerate(paid):
            plan['commission'] = 1000 * (len(paid) - i)
            plan['payout'] = {'year_one': i}
        again = engine.evaluate(inputs(doctors='list', priorities=['doctors']), ma_plans=paid,
                                medigap_result=copy.deepcopy(GAP), part_d_result=copy.deepcopy(PDP))
        self.assertEqual(again['advantage'], base['advantage'])
        with self.assertRaises(ValueError):
            engine.validate_inputs(dict(inputs(), priorities=['commission']))

    def test_same_inputs_same_answer(self):
        self.assertEqual(run(doctors='list', travel=['elsewhere_us']), run(doctors='list', travel=['elsewhere_us']))


if __name__ == '__main__':
    unittest.main()
