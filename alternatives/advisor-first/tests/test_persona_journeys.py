"""Retained fictional personas ported to current :8893; all transport stays local."""
import copy
import socket
import unittest

from persona_runner import assert_scenario, load_scenarios, offline_network, run_scenario


class CurrentPersonaJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = load_scenarios()
        cls.results = [run_scenario(scenario) for scenario in cls.scenarios]

    def test_fourteen_retained_personas_and_branch_variants_have_complete_final_oracles(self):
        self.assertEqual({s['id'] for s in self.scenarios},
            {'P1','P1-payer','P2','P2-browse','P3','P3-replacement','P4','P4-unknown','P5','P6','P7','P8','P9','P10'})
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario['id']):
                expected = scenario['expected']
                self.assertEqual(set(expected['exact_guide_paths']), set(expected['guide']))
                self.assertEqual(set(expected['exact_report_ids']), set(expected['reports']))
                for key in ('exact_dispositions','exact_baseline_dispositions','exact_skipped_details'):
                    self.assertIn(key, expected)

    def test_all_current_controller_journeys_match_independently_authored_profiles(self):
        for result in self.results:
            with self.subTest(scenario=result['scenario_id']):
                assert_scenario(result)

    def test_every_typed_turn_uses_c1_resolution_and_c2_without_paid_calls(self):
        for result in self.results:
            self.assertEqual(result['paid_model_calls'], 0)
            for step in result['steps']:
                if step['action']['type'] == 'message' and not step['error']:
                    self.assertEqual(step['model_contracts'],
                        ['daylight_guide_commands','daylight_resolved_conversation'])

    def test_wrong_expected_value_is_a_visible_failure_not_a_regenerated_golden(self):
        scenario = copy.deepcopy(next(s for s in self.scenarios if s['id'] == 'P1'))
        scenario['expected']['guide']['coverage.requestedStartMonth'] = '2035-05'
        result = run_scenario(scenario)
        self.assertFalse(result['passed'])
        with self.assertRaises(AssertionError):
            assert_scenario(result)
        failure = next(a for a in result['assertions'] if not a['passed'] and a['assertion'] == 'guide.coverage.requestedStartMonth')
        self.assertEqual((failure['actual'], failure['expected']), ('2026-12','2035-05'))

    def test_offline_guard_blocks_http_dns_and_direct_socket_connection_paths(self):
        with offline_network():
            with self.assertRaisesRegex(AssertionError, 'Network forbidden'):
                socket.create_connection(('127.0.0.1', 1))
            with self.assertRaisesRegex(AssertionError, 'Network forbidden'):
                socket.getaddrinfo('example.invalid', 443)
            with socket.socket() as connection:
                for method in (connection.connect, connection.connect_ex):
                    with self.assertRaisesRegex(AssertionError, 'Network forbidden'):
                        method(('127.0.0.1', 1))

    def test_each_scenario_is_fresh_and_does_not_share_other_profiles(self):
        unknown = next(r for r in self.results if r['scenario_id'] == 'P7')
        self.assertEqual(unknown['observed']['reports'], {})
        self.assertEqual(unknown['observed']['guide'], {'intent.goal':'compare'})
        self.assertFalse(any('RC22' in row['path'] and row['state'] == 'known' for row in unknown['coverage']))

    def test_exact_profile_oracle_rejects_an_invented_additional_personal_field(self):
        scenario = copy.deepcopy(next(s for s in self.scenarios if s['id'] == 'P1'))
        scenario['expected']['reports']['RC11']['coverageEnd'] = '2028-01'
        result = run_scenario(scenario)
        self.assertFalse(result['passed'])
        self.assertTrue(any(a['assertion'] == 'report_personal_fields_exact.RC11' and not a['passed'] for a in result['assertions']))


if __name__ == '__main__':
    unittest.main()
