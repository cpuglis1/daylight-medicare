"""Evidence, presentation and authority boundaries for problems 1–3."""
import copy
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from understanding import (FILES, UnderstandingError, UnderstandingRegistry,
    attach_understanding, reported_dates)
from understanding_examples import cost_example, examples
from understanding_reference import PublishedCostReference


class UnderstandingTests(unittest.TestCase):
    def test_inventory_preserves_thirteen_exact_statements_and_personal_gaps(self):
        inventory = UnderstandingRegistry().inventory()
        self.assertEqual(inventory['fact_count'], 13)
        self.assertFalse(inventory['official_quotation_verified_by_this_registry'])
        for name in ('transition', 'coverage_paths', 'costs'):
            capability = inventory['capabilities'][name]
            self.assertEqual(capability['personal_state'], 'held')
            self.assertTrue(capability['dependencies'])
            self.assertTrue(capability['gaps'])
            self.assertTrue(capability['required_case_families'])
        originals = {fact['id']: fact for name in FILES[1:]
                     for fact in json.loads((HERE / name).read_text())['facts']}
        for claim in inventory['claims']:
            self.assertEqual(claim['retained_statement'], originals[claim['claim_id']]['text'])
            self.assertEqual(claim['permitted_uses'], ['general_education'])
            self.assertEqual(claim['personal_use'], 'held')
            self.assertTrue(claim['official_source_urls'])

    def test_source_and_catalog_drift_fail_on_every_read_without_repinning(self):
        for name in FILES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                for relative in (*FILES, 'understanding-lock.json'):
                    path = target / relative;path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(HERE / relative, path)
                registry = UnderstandingRegistry(target)
                self.assertEqual(registry.inventory()['fact_count'], 13)
                (target / name).write_text((target / name).read_text() + '\n')
                with self.assertRaisesRegex(UnderstandingError, 'SOURCE_CHANGED'):
                    registry.guides(['costs'])

    def test_missing_files_and_review_deadline_fail_closed(self):
        registry = UnderstandingRegistry()
        self.assertTrue(registry.guides(['costs'], today=date(2026, 11, 23)))
        for day in (date(2026, 11, 24), date(2027, 1, 1)):
            with self.assertRaisesRegex(UnderstandingError, 'REVIEW_DUE'):
                registry.guides(['costs'], today=day)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UnderstandingError):
                UnderstandingRegistry(tmp).inventory()

    def test_only_current_supported_depth_is_returned(self):
        registry = UnderstandingRegistry()
        guide = registry.guides(['routesintro'])[0]
        self.assertEqual([b['id'] for b in guide['blocks']], ['original_base', 'advantage_base'])
        self.assertNotIn('Part D', json.dumps(guide['blocks']))
        self.assertEqual(registry.guides(['costs'])[0]['evidence_refs'], ['costs'])
        self.assertEqual([b['id'] for b in registry.guides(['costs'])[0]['blocks']], ['premiums', 'care'])
        self.assertEqual([b['id'] for b in registry.guides(['medical_limit'])[0]['blocks']],
                         ['medical_cap', 'original_limit'])
        self.assertEqual(registry.guides(['unrelated']), [])

    def test_reported_dates_preserve_precision_and_never_infer_calendar_values(self):
        rows = [
            {'id': 'S_AGE65', 'value': 'November (year not given)', 'status': 'reported'},
            {'id': 'T04', 'value': 'soonest', 'status': 'reported'},
            {'id': 'T04', 'value': 'January 2027', 'label': 'Preferred coverage start', 'status': 'reported'},
            {'id': 'RC11', 'value': {'jobEnd': 'October 2026', 'coverageEnd': 'December 15th'}, 'status': 'reported'},
            {'id': 'RC05', 'value': '2026-11', 'status': 'reported'}]
        dates = reported_dates(rows)
        self.assertEqual([(row['label'], row['value']) for row in dates], [
            ('65th birthday', 'November (year not given)'), ('Preferred coverage start', 'January 2027'),
            ('Job end', 'October 2026'), ('Insurance end', 'December 15th')])
        self.assertNotIn('effective', json.dumps(dates))
        for state in ('unknown', 'deferred', 'stale', 'conflicting', 'derived'):
            self.assertEqual(reported_dates([{**row, 'status': state} for row in rows]), [])
        self.assertEqual(reported_dates([{'id': 'T04', 'value': 'after_coverage', 'status': 'reported'}]), [])

    @staticmethod
    def turn(visual='costs', refs=None):
        return {'guide': {'stateVersion': 3}, 'record': {'stateVersion': 4},
            'advisor': {'visual': visual, 'teachingFactIds': ['costs'] if refs is None else refs},
            'reportedRows': []}

    def test_visual_requires_explicit_intent_and_supported_delivered_teaching(self):
        self.assertNotIn('understanding', attach_understanding(self.turn('none')))
        for turn in (self.turn(refs=[]), self.turn('costs', ['routesintro'])):
            self.assertEqual(attach_understanding(turn)['understanding']['state'], 'unavailable')
        turn = self.turn();before = copy.deepcopy(turn)
        attach_understanding(turn)
        self.assertEqual(turn['guide'], before['guide'])
        self.assertEqual(turn['record'], before['record'])
        self.assertIsNone(turn['understanding']['personal_result'])
        self.assertEqual(turn['understanding']['personal_authority'], 'held')

    def test_parts_backed_original_guide_never_adds_optional_drugs_or_medigap(self):
        turn = self.turn('original', ['parts'])
        attach_understanding(turn)
        guide = turn['understanding']
        self.assertEqual([block['id'] for block in guide['blocks']], ['original_base', 'original_access'])
        self.assertEqual(guide['evidence_refs'], ['parts'])
        self.assertNotIn('Medigap', json.dumps(guide['blocks']))
        self.assertNotIn('Part D', json.dumps(guide['blocks']))

    def test_replay_rechecks_evidence_and_suppresses_historical_or_failed_guides(self):
        turn = self.turn();attach_understanding(turn)
        self.assertIn('understanding', turn)
        attach_understanding(turn, historical=True)
        self.assertNotIn('understanding', turn)
        turn['generated'] = {'status': 'unavailable'}
        attach_understanding(turn)
        self.assertNotIn('understanding', turn)
        turn.pop('generated')
        with patch.object(UnderstandingRegistry, 'guides', side_effect=UnderstandingError('CHANGED')):
            attach_understanding(turn)
        self.assertEqual(turn['understanding']['state'], 'unavailable')
        self.assertIsNone(turn['understanding']['visual'])

    def test_correction_rebuilds_the_report_snapshot_without_creating_a_deadline(self):
        turn = self.turn('transition', ['dates'])
        turn['reportedRows'] = [{'id': 'T04', 'label': 'Preferred coverage start',
                                 'status': 'reported', 'value': 'December 2026'}]
        attach_understanding(turn);first = copy.deepcopy(turn['understanding'])
        turn['guide']['stateVersion'] += 1
        turn['reportedRows'][0]['value'] = 'January 2027'
        attach_understanding(turn);second = turn['understanding']
        self.assertNotEqual(first['snapshot_binding'], second['snapshot_binding'])
        self.assertEqual(first['reported_dates'][0]['value'], 'December 2026')
        self.assertEqual(second['reported_dates'][0]['value'], 'January 2027')
        self.assertEqual(second['date_basis'], 'reported_only_no_personal_window_calculated')
        self.assertIsNone(second['personal_result'])

    def test_fictional_cost_scenarios_keep_unknowns_and_explicit_quantities_out_of_totals(self):
        low, high = cost_example(2), cost_example(12)
        self.assertEqual(low['receipt']['subtotal']['amount'], '1250.00')
        self.assertEqual(high['receipt']['subtotal']['amount'], '1500.00')
        for sample in (low, high, cost_example(2, unknown_drug=False)):
            receipt = sample['receipt']
            self.assertTrue(sample['fictional'])
            self.assertIsNone(receipt['complete_total'])
            self.assertIsNone(receipt['quote'])
            self.assertFalse(receipt['automatic_annualization'])
            self.assertFalse(receipt['personalized_recommendation_allowed'])
            self.assertEqual(receipt['output_state'], 'fictional_fixture_only')
            self.assertIn('unpriced_services', receipt['excluded_components'])
        self.assertIn('drug_costs', low['unknown_components'])
        self.assertEqual(low['components'][0]['quantity'], '12')
        self.assertEqual(low['components'][1]['quantity'], '2')
        self.assertEqual(cost_example(2, unknown_drug=False)['receipt']['subtotal']['amount'], '1430.00')

    def test_three_examples_are_generated_from_the_same_registry(self):
        result = examples()
        self.assertTrue(result['fictional_reports'])
        self.assertEqual([g['capability'] for g in result['guides']], ['transition', 'coverage_paths', 'costs'])
        self.assertEqual(len({g['registry_binding'] for g in result['guides']}), 1)

    def test_view_contract_and_local_scenario_interactions(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for the guide interaction checks.')
        run = subprocess.run([node, '--test', str(HERE / 'tests/test_understanding_view.js')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_published_reference_rejects_personal_inputs_before_starting_worker(self):
        with patch('understanding_reference.subprocess.run') as run:
            for request in ({'year': 2027}, {'year': 2026, 'income': 50000},
                            {'year': 2026, 'research': True}, {'year': True},
                            {'year': 2026, 'ids': ['b_premium', 'b_premium']}):
                with self.assertRaisesRegex(UnderstandingError, 'REQUEST_INVALID'):
                    PublishedCostReference().lookup(request)
            run.assert_not_called()

    def test_published_reference_has_no_research_override_and_preserves_full_envelope(self):
        reference = {'qualifications': ['fixture:condition'], 'personal_total_available': False}
        with patch('understanding_reference.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps({'ok': True, 'reference': reference, 'binding': {'manifest': 'fixture:hash'}})
            out = PublishedCostReference().lookup({'year': 2026, 'ids': ['b_premium']})
            self.assertEqual(out['reference'], reference)
            self.assertEqual(out['personal_authority'], 'held')
            self.assertEqual(run.call_args.kwargs['env'], {})
            self.assertIn('research=False', run.call_args.args[0][-2])


if __name__ == '__main__':
    unittest.main()
