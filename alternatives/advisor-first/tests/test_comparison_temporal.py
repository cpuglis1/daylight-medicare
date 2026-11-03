"""Time-scoped reports cannot suppress a different approved question meaning."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_engine import build_comparison
from comparison_profile import build_comparison_profile
from natural_state import ensure_state

NOW = '2026-11-01T15:00:00+00:00'
TEMPLATE = json.loads((HERE.parent / 'chat-first/cms-slice/config/profile/customer-profile.template.json').read_text())


def snapshot(task, *, guide_reports=(), readiness_reports=()):
    guide, record = copy.deepcopy(TEMPLATE['guide']), copy.deepcopy(TEMPLATE['readiness'])
    guide['stateVersion'] = record['stateVersion'] = 5
    record['conversation'] = {'task': task, 'preparing': True}
    provenance = ensure_state(record)['provenance']
    for prefix, container, reports in [('guide.', guide['fields'], guide_reports),
                                        ('readiness.', record['facts'], readiness_reports)]:
        for name, value, scope in reports:
            container[name] = {'value': value, 'status': 'reported', 'source': 'user_text',
                               'revision': 2, 'confirmation': 'reported_by_user'}
            provenance[prefix + name] = {'method': 'direct_report', 'status': 'user_reported',
                'subject': 'beneficiary', 'scope': scope, 'revision': 2, 'supersedesRevision': None}
    return build_comparison_profile(guide, record)


def compare(case, question):
    return build_comparison(case, generated_at=NOW, eligible_questions=[question])


def accounting(out, identifier):
    return next(row for row in out['decision_record']['question_accounting'] if row['question_id'] == identifier)


class ComparisonTemporalTests(unittest.TestCase):
    def test_historical_coverage_does_not_answer_current_controller_question(self):
        case = snapshot('compare', guide_reports=[('coverage.current', ['employer'], 'historical')])
        out = compare(case, {'id': 'T05', 'question': 'What coverage do you have now?'})
        self.assertEqual(out['next_question']['question_id'], 'T05')
        row = accounting(out, 'T05')
        self.assertEqual(row['accounting_state'], 'missing_for_requested_finding')
        self.assertEqual(len(row['report_refs']), 1)
        self.assertEqual(row['bound_subject_report_refs'], [])

    def test_historical_provider_and_medicine_items_do_not_suppress_current_item_check(self):
        for identifier, task, entity, value, field in [
            ('RC21', 'providers', 'doctor-1', {'practice': 'Synthetic former office'}, 'practice'),
            ('RC22', 'drug_coverage', 'medicine-1', {'strength': '5 mg'}, 'strength')]:
            case = snapshot(task, readiness_reports=[(identifier,
                {'choice': 'details', 'items': [{'entity': entity, **value}]}, 'historical')])
            out = compare(case, {'id': identifier, 'entity': entity, 'fields': [{'key': field}],
                                 'question': 'What should we check for the current situation?'})
            with self.subTest(identifier=identifier):
                self.assertEqual(out['next_question']['question_id'], identifier)
                self.assertEqual(out['next_question']['item_id'], entity)
                self.assertEqual(out['next_question']['report_refs'], [])
                self.assertNotEqual(accounting(out, identifier)['accounting_state'], 'used')

    def test_historical_unknown_does_not_defer_a_new_current_question(self):
        case = snapshot('compare', guide_reports=[('coverage.current', 'unknown', 'historical')])
        out = compare(case, {'id': 'T05', 'question': 'What coverage do you have now?'})
        self.assertEqual(out['next_question']['question_id'], 'T05')
        self.assertNotEqual(accounting(out, 'T05')['accounting_state'], 'deferred_for_requested_finding')

    def test_current_unknown_and_baseline_defer_still_suppress_repeat_questions(self):
        for word in ['unknown', 'later']:
            case = snapshot('compare', guide_reports=[('coverage.current', word, 'current')])
            self.assertIsNone(compare(case, {'id': 'T05'})['next_question'])
        case = snapshot('compare', guide_reports=[('coverage.current', ['employer'], 'historical')])
        case['extensions']['baseline_dispositions']['T05'] = 'deferred'
        out = compare(case, {'id': 'T05'})
        self.assertIsNone(out['next_question'])
        self.assertEqual(accounting(out, 'T05')['accounting_state'], 'deferred_for_requested_finding')

    def test_unscoped_unknown_disposition_stays_unknown_and_is_not_repeated(self):
        guide, record = copy.deepcopy(TEMPLATE['guide']), copy.deepcopy(TEMPLATE['readiness'])
        guide['stateVersion'] = 1
        guide['fields']['coverage.current'] = {'value': 'unknown', 'status': 'unknown', 'source': 'user_choice',
                                               'revision': 1, 'confirmation': 'confirmed_by_user'}
        record['conversation'] = {'task': 'compare', 'preparing': True}
        case = build_comparison_profile(guide, record)
        out = compare(case, {'id': 'T05'})
        self.assertIsNone(out['next_question'])
        self.assertEqual(accounting(out, 'T05')['accounting_state'], 'deferred_for_requested_finding')
        self.assertEqual(accounting(out, 'T05')['bound_subject_report_refs'], [])

    def test_intended_requested_start_is_reused_without_becoming_actual_start(self):
        case = snapshot('timing', guide_reports=[
            ('coverage.requestedStart', 'month', 'intended'),
            ('coverage.requestedStartMonth', '2027-01', 'intended')])
        out = compare(case, {'id': 'T04', 'question': 'When would you like coverage to start?'})
        self.assertIsNone(out['next_question'])
        self.assertEqual(accounting(out, 'T04')['accounting_state'], 'used')
        self.assertEqual(accounting(out, 'RC05')['bound_subject_report_refs'], [])

    def test_historical_desired_start_cannot_answer_current_intention(self):
        case = snapshot('timing', guide_reports=[
            ('coverage.requestedStart', 'month', 'historical'),
            ('coverage.requestedStartMonth', '2025-01', 'historical')])
        out = compare(case, {'id': 'T04'})
        self.assertEqual(out['next_question']['question_id'], 'T04')
        self.assertEqual(accounting(out, 'T04')['accounting_state'], 'missing_for_requested_finding')

    def test_actual_historical_part_b_and_advantage_chronology_are_reused(self):
        case = snapshot('medigap', readiness_reports=[
            ('RC05', {'choice': 'details', 'month': '2024-05'}, 'historical'),
            ('RC16', {'choice': 'yes', 'start': '2025-01', 'priorMedigap': 'yes'}, 'historical')])
        for identifier, field in [('RC05', 'month'), ('RC16.C1', 'start'), ('RC16.C2', 'priorMedigap')]:
            with self.subTest(identifier=identifier):
                out = compare(case, {'id': identifier, 'fields': [{'key': field}]})
                self.assertIsNone(out['next_question'])
                self.assertEqual(accounting(out, identifier)['accounting_state'],
                                 'alias_reused' if identifier.startswith('RC16.') else 'used')
        case = snapshot('timing', readiness_reports=[
            ('RC11', {'choice': 'dates', 'jobEnd': '2026-09', 'coverageEnd': '2026-10'}, 'historical')])
        self.assertIsNone(compare(case, {'id': 'RC11.C1', 'fields': [{'key': 'coverageEnd'}]})['next_question'])

    def test_future_intention_does_not_answer_actual_advantage_episode_start(self):
        case = snapshot('medigap', readiness_reports=[
            ('RC16', {'choice': 'yes', 'start': '2027-01', 'priorMedigap': 'yes'}, 'intended')])
        out = compare(case, {'id': 'RC16.C1', 'fields': [{'key': 'start'}]})
        self.assertEqual(out['next_question']['question_id'], 'RC16.C1')
        self.assertNotEqual(accounting(out, 'RC16.C1')['accounting_state'], 'alias_reused')

    def test_current_reports_still_suppress_redundant_current_questions(self):
        case = snapshot('compare', guide_reports=[('coverage.current', ['original'], 'current')])
        out = compare(case, {'id': 'T05'})
        self.assertIsNone(out['next_question'])
        self.assertEqual(accounting(out, 'T05')['accounting_state'], 'used')
        self.assertTrue(all(value['state'] == 'held' for value in out['authority'].values()))


if __name__ == '__main__':
    unittest.main()
