"""Plans page: the stated priority order comes from the conversation (owner direction, Nov 8, 2026)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Registers the pinned engine paths before service imports.
from plans_service import PlansService


def fact(path, value, state='reported', scope='current', usable=True, subject='beneficiary-1'):
    return {'ref': {'path': path, 'item_id': None, 'subject_id': subject, 'scope': scope},
            'value': value, 'report_state': state, 'usable_as_report': usable, 'usable_for_bound_subject': usable}


def profile(*facts):
    return {'profile_binding': {'subject_id': 'beneficiary-1'}, 'facts': list(facts)}


class DerivedPriorityOrderTests(unittest.TestCase):
    def test_cost_preference_decides_first(self):
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.costPreference', 'predictable'))),
                         ('in_network_medical_limit', 'monthly_plan_premium'))
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.costPreference', 'lower_monthly'),
                                                             fact('guide.fields.needs.priorities', ['bills']))),
                         ('monthly_plan_premium', 'in_network_medical_limit'))

    def test_priorities_decide_when_cost_preference_is_open(self):
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.priorities', ['doctors', 'bills']))),
                         ('in_network_medical_limit', 'monthly_plan_premium'))
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.priorities', ['total_cost']))),
                         ('monthly_plan_premium', 'in_network_medical_limit'))

    def test_nothing_stated_or_unusable_gives_no_order(self):
        self.assertEqual(PlansService.derived_order(profile()), ())
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.priorities', ['doctors']))), ())
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.costPreference', 'predictable', state='unanswered'))), ())
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.costPreference', 'predictable', usable=False))), ())
        self.assertEqual(PlansService.derived_order(profile(fact('guide.fields.needs.costPreference', 'predictable', scope='intended'))), ())
        self.assertEqual(PlansService.derived_order({'facts': []}), ())


if __name__ == '__main__':
    unittest.main()
