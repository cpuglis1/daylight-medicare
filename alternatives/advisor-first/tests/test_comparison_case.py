"""Current subject/time scope, method binding and derived-view invalidation."""
import copy
import unittest
from unittest.mock import patch

from test_comparison_engine import profile, fact, build_comparison
from comparison_case import prepare_case
from comparison_service import ComparisonService


class ComparisonCaseTests(unittest.TestCase):
    def test_historical_coverage_is_retained_but_not_current_baseline(self):
        case = profile()
        fact(case, 'guide.fields.coverage.current', ['employer'], scope='historical')
        out = build_comparison(case)
        prepared = prepare_case(case, out)
        self.assertEqual(prepared['baseline_reports'], [])
        self.assertEqual(out['units'][0]['identity_state'], 'unknown')
        self.assertEqual(case['facts'][next(i for i,f in enumerate(case['facts']) if f['ref']['path']=='guide.fields.coverage.current')]['value'], ['employer'])

    def test_requested_timing_never_becomes_current_coverage(self):
        case = profile()
        fact(case, 'guide.fields.coverage.requestedStartMonth', '2026-12', scope='intended')
        prepared = prepare_case(case, build_comparison(case))
        self.assertEqual([(r['label'], r['value']) for r in prepared['baseline_reports']],
                         [('Requested start month', '2026-12')])
        self.assertTrue(all(row['state']=='reported_not_verified' for row in prepared['baseline_reports']))

    def test_historical_priorities_do_not_become_current_emphasis(self):
        case = profile()
        fact(case, 'guide.fields.needs.priorities', ['doctors'], scope='historical')
        fact(case, 'guide.fields.needs.costPreference', 'lower_monthly', scope='historical')
        out = build_comparison(case)
        self.assertEqual(out['preference_context']['priority_topics'], [])
        self.assertEqual(out['preference_context']['emphasized_dimensions'], [])

    def test_historical_none_is_not_current_no_medicine_requirement(self):
        case = profile()
        fact(case, 'guide.fields.needs.medicinesStatus', 'no', 'explicit_none', scope='historical')
        out = build_comparison(case)
        self.assertTrue(all(f['result']=='unresolved' for f in out['findings'] if f['dimension_id']=='drug_coverage'))

    def test_preparation_does_not_invent_hard_constraints_or_scenarios(self):
        case = profile()
        fact(case, 'guide.fields.needs.priorities', ['doctors'])
        prepared = prepare_case(case, build_comparison(case))
        self.assertEqual(prepared['declared_constraints'], [])
        self.assertEqual(prepared['declared_scenarios'], [])
        self.assertFalse(prepared['question_routing_changed'])
        self.assertEqual(prepared['personal_output_state'], 'held')

    def test_reported_no_items_does_not_create_an_identity_intake_task(self):
        case = profile()
        fact(case, 'guide.fields.needs.providersStatus', 'none', 'explicit_none')
        fact(case, 'guide.fields.needs.medicinesStatus', 'no', 'explicit_none')
        prepared = prepare_case(case, build_comparison(case))
        self.assertTrue(prepared['assessments'])
        self.assertTrue(all(row['state']=='reported_requirement_absent' for row in prepared['assessments']))
        self.assertNotIn('EXACT_ITEM_REPORT_REQUIRED', str(prepared))

    def test_method_revision_changes_result_and_decision_reference(self):
        case = profile()
        service = ComparisonService()
        with patch('comparison_service.build_comparison_profile', return_value=case):
            first = service.evaluate({}, {})
            with patch('comparison_service.prepare_case', return_value={
                    **first['case_preparation'], 'method_version': 'fixture:next-method'}):
                second = service.evaluate({}, {})
        self.assertNotEqual(first['comparison_id'], second['comparison_id'])
        self.assertNotEqual(first['decision_record_ref'], second['decision_record_ref'])

    def test_stale_replay_clears_preparation_and_research_markers(self):
        case = profile()
        fact(case, 'guide.fields.coverage.current', ['employer'])
        service = ComparisonService()
        response = {'guide': {}, 'record': {}, 'assessment': {}, 'reply': 'fixture stale prose'}
        with patch('comparison_service.build_comparison_profile', return_value=case):
            first = service.attach(copy.deepcopy(response))
            self.assertTrue(first['comparison']['case_preparation']['baseline_reports'])
            out = service.attach(first, historical=True)
        prepared = out['comparison']['case_preparation']
        self.assertEqual(prepared['state'], 'stale')
        self.assertEqual(prepared['baseline_reports'], [])
        self.assertEqual(prepared['assessments'], [])
        self.assertEqual(out['comparison']['research']['state'], 'stale')
        self.assertEqual(out['reply'], '')


if __name__ == '__main__':
    unittest.main()
