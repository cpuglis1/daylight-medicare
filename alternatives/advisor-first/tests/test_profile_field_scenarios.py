"""Current :8893 field/state closure cases; scripted transport, never a provider.

Expected reports live in hand-authored JSON. They are not snapshots regenerated
from the controller, and these tests never emit or rewrite evidence artifacts.
"""
from pathlib import Path
import unittest

from persona_runner import load_scenarios, run_scenario, assert_scenario


FIXTURES = Path(__file__).with_name('fixtures') / 'field_scenarios.json'


class ProfileFieldScenarioTests(unittest.TestCase):
    def test_explicit_field_and_state_closure_scenarios(self):
        scenarios = load_scenarios(FIXTURES)
        self.assertGreaterEqual(len(scenarios), 10)
        self.assertEqual(len({case['id'] for case in scenarios}), len(scenarios))
        for scenario in scenarios:
            with self.subTest(scenario=scenario['id']):
                assert_scenario(run_scenario(scenario))

    def test_each_closure_case_declares_its_own_manual_expectations_and_scope(self):
        states = set()
        for scenario in load_scenarios(FIXTURES):
            with self.subTest(scenario=scenario['id']):
                self.assertTrue(scenario.get('purpose'))
                self.assertTrue(scenario.get('expected'))
                self.assertTrue(scenario.get('coverage_witnesses'))
                for witness in scenario['coverage_witnesses']:
                    self.assertTrue(witness['path'].startswith(('guide.fields.', 'readiness.')))
                    self.assertIn(witness['state'], {
                        'known', 'unknown', 'deferred', 'not_applicable',
                        'unanswered', 'derived', 'explicit_absence', 'rejected',
                        'corrected', 'conflicting', 'stale'})
                    self.assertIn(witness['mode'], {
                        'questioned', 'volunteered', 'reused', 'derived', 'absence', 'rejected'})
                    states.add(witness['state'])
        self.assertTrue({'known', 'unknown', 'deferred', 'corrected',
                         'conflicting', 'stale', 'rejected'}.issubset(states))


if __name__ == '__main__':
    unittest.main()
