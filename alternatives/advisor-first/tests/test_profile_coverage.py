"""Coverage accounting is traceable to executed assertions, never declarative IDs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'scripts'))
from profile_coverage import load_catalog, build_report, CATALOG_PATH, ROOT


class ProfileCoverageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.path = 'guide.fields.coverage.current'

    def result(self, *, state='known', mode='volunteered', passed=True, path=None):
        item = {'scenario_id': 'independent-fixture', 'step': 1,
            'assertion': 'guide.coverage.current', 'expected': ['cobra'],
            'actual': ['cobra'], 'passed': passed,
            'covered_path': path or self.path, 'state': state, 'mode': mode}
        return {'scenario_id': 'independent-fixture', 'assertions': [item],
            'coverage': [{**item, 'path': path or self.path, 'state': state, 'mode': mode}],
            'paid_model_calls': 0}

    def row(self, report, path=None):
        return next(item for item in report['fields'] if item['path'] == (path or self.path))

    def test_exact_original_78_additive_14_current_4_and_question_41_denominators(self):
        contract = json.loads((ROOT / self.catalog['sources']['profile_contract']['path']).read_text())
        original = [item['path'] for item in self.catalog['fields'] if item['inventory'] == 'original_78']
        self.assertEqual(original, list(contract['fields']))
        self.assertEqual(len(original), 78)
        self.assertEqual([item['path'] for item in self.catalog['fields'] if item['inventory'] == 'additive_14'],
            contract['additive_optional_report_paths'])
        self.assertEqual(len(contract['additive_optional_report_paths']), 14)
        self.assertEqual(len(self.catalog['fields']), 96)
        self.assertEqual(len(set(self.catalog['question_ids'])), 41)
        self.assertEqual({item for item in self.catalog['question_ids'] if '.' in item},
            {'RC11.C1', 'RC16.C1', 'RC16.C2'})

    def test_every_field_retains_explicit_state_expectations_and_unsupported_statuses(self):
        expected = {'known', 'unanswered', 'unknown', 'deferred', 'explicit_absence', 'correction', 'rejected'}
        for field in self.catalog['fields']:
            self.assertEqual(set(field['state_expectations']), expected)
        statuses = {item['path']: item['status'] for item in self.catalog['fields']}
        self.assertEqual(statuses['guide.fields.needs.pharmacies'], 'legacy')
        self.assertEqual(statuses['readiness.conversation.details.G01.value'], 'held')
        self.assertEqual(statuses['readiness.conversation.details.G13.value'], 'derived')

    def test_missing_source_path_is_not_silently_removed(self):
        changed = copy.deepcopy(self.catalog)
        changed['fields'] = changed['fields'][1:]
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'catalog.json'
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_DENOMINATOR_DRIFT'):
                load_catalog(target)

    def test_changed_source_digest_fails_closed(self):
        changed = copy.deepcopy(self.catalog)
        changed['sources']['original_adaptive']['sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'catalog.json'
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'):
                load_catalog(target)

    def test_only_assertion_backed_exact_known_value_earns_capture(self):
        report = build_report([self.result()], self.catalog)
        self.assertTrue(self.row(report)['successful_capture'])
        self.assertEqual(report['summary']['inventories']['original_78']['successful_capture_paths'], 1)
        changed = self.result()
        changed['coverage'][0]['expected'] = ['retiree']
        with self.assertRaisesRegex(ValueError, 'ORPHAN_COVERAGE_WITNESS'):
            build_report([changed], self.catalog)

    def test_orphan_declared_field_and_unknown_field_cannot_earn_coverage(self):
        changed = self.result()
        changed['assertions'] = []
        with self.assertRaisesRegex(ValueError, 'ORPHAN_COVERAGE_WITNESS'):
            build_report([changed], self.catalog)
        with self.assertRaisesRegex(ValueError, 'UNCATALOGED_COVERAGE_PATH'):
            build_report([self.result(path='guide.fields.invented')], self.catalog)

    def test_existing_guide_oracle_cannot_be_relabelled_as_supply_or_capture_mode(self):
        result = self.result(path='guide.fields.intent.goal')
        result['coverage'][0]['path'] = 'readiness.facts.RC23.value.items[].supply'
        with self.assertRaisesRegex(ValueError, 'ORPHAN_COVERAGE_WITNESS'):
            build_report([result], self.catalog)

    def test_executed_f01_goal_oracle_cannot_be_borrowed_for_supply(self):
        sys.path.insert(0, str(HERE / 'tests'))
        from persona_runner import load_scenarios, run_scenario, assert_scenario
        scenario = next(item for item in load_scenarios(HERE / 'tests/fixtures/field_scenarios.json') if item['id'] == 'F01')
        result = assert_scenario(run_scenario(scenario))
        witness = next(item for item in result['coverage'] if item['path'] == 'guide.fields.intent.goal')
        witness['path'] = 'readiness.facts.RC23.value.items[].supply'
        witness['covered_path'] = witness['path']
        with self.assertRaisesRegex(ValueError, 'ORPHAN_COVERAGE_WITNESS'):
            build_report([result], self.catalog)
        result = self.result(mode='reused')
        result['coverage'][0]['mode'] = 'volunteered'
        with self.assertRaisesRegex(ValueError, 'ORPHAN_COVERAGE_WITNESS'):
            build_report([result], self.catalog)

    def test_absence_unknown_deferred_stale_conflict_rejection_and_reuse_are_not_capture(self):
        for state in ('unknown', 'deferred', 'unanswered', 'conflicting', 'stale', 'superseded', 'declined', 'not_applicable'):
            with self.subTest(state=state):
                self.assertFalse(self.row(build_report([self.result(state=state)], self.catalog))['successful_capture'])
        for mode in ('explicit_absence', 'rejected', 'reused', 'derived'):
            with self.subTest(mode=mode):
                self.assertFalse(self.row(build_report([self.result(mode=mode)], self.catalog))['successful_capture'])

    def test_failed_assertion_is_preserved_without_coverage(self):
        report = build_report([self.result(passed=False)], self.catalog)
        self.assertEqual(report['summary']['failed_assertion_count'], 1)
        self.assertFalse(report['summary']['passed'])
        self.assertFalse(self.row(report)['successful_capture'])
        self.assertEqual(self.row(report)['witness_count'], 0)

    def test_value_oracle_cannot_upgrade_stale_envelope_to_known_capture(self):
        result = self.result()
        result['steps'] = [{'step': 1, 'observed': {'guide_status': {'coverage.current': 'stale'}}}]
        row = self.row(build_report([result], self.catalog))
        self.assertFalse(row['successful_capture'])
        self.assertEqual(row['state_counts'], {'stale': 1})

    def test_derived_links_and_metadata_are_separate_from_personal_capture(self):
        report = build_report([self.result(path='guide.fields.subject.role', mode='derived')], self.catalog)
        self.assertFalse(self.row(report, 'guide.fields.subject.role')['successful_capture'])
        self.assertTrue(self.row(report, 'guide.fields.subject.role')['derived_witness'])
        report = build_report([self.result(path='readiness.natural.agenda.concerns')], self.catalog)
        self.assertEqual(report['summary']['inventories']['original_78']['successful_capture_paths'], 0)
        self.assertEqual(len(next(item for item in report['metadata'] if item['path'] == 'readiness.natural.agenda.concerns')['witnesses']), 1)

    def test_paid_calls_or_duplicate_scenarios_fail_closed(self):
        changed = self.result()
        changed['paid_model_calls'] = 1
        with self.assertRaisesRegex(ValueError, 'PAID_CALL_IN_OFFLINE_REPORT'):
            build_report([changed], self.catalog)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SCENARIO_ID'):
            build_report([self.result(), self.result()], self.catalog)


if __name__ == '__main__':
    unittest.main()
