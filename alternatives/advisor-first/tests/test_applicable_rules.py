"""Deterministic rule selection and the redirect-not-deflect question guard (Nov 8, 2026)."""
from datetime import date
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from applicable_rules import applicable_rules, required_target, floor_statement, offer_pattern, referral_pattern


def make(reports=None, values=None):
    reports, values = reports or {}, values or {}
    return (lambda identifier: reports.get(identifier, {}), lambda path: values.get(path))


class RuleSelectionTests(unittest.TestCase):
    def test_statements_exist_for_every_rule(self):
        facts = {f['id'] for path in sorted(HERE.glob('pilot-rules*.json')) for f in json.loads(path.read_text())['facts']}
        for reports, values in [
                ({'RC09': {'choice': 'my_job'}, 'RC10': {'choice': 'yes'}, 'RC07': {'choice': 'advantage'}},
                 {'coverage.current': ['employer', 'advantage', 'original'], 'situation.age65': True}),
                ({'RC09': {'choice': 'my_job'}, 'RC10': {'choice': 'no'}}, {'coverage.current': ['employer'], 'situation.age65': True}),
                ({'RC04': {'choice': 'both'}, 'RC12': {'choice': 'yes'}}, {'coverage.current': ['original', 'retiree']})]:
            report, value = make(reports, values)
            for rule in applicable_rules(report, value, focus='drugs', today=date(2026, 11, 8)):
                self.assertIn(rule['fact_id'], facts)

    def test_second_set_rules_drop_out_until_the_owner_accepts_them(self):
        # The service keeps only rules whose statement is loaded; a pending
        # draft file (review_state not owner_accepted) contributes nothing.
        accepted = {f['id'] for path in sorted(HERE.glob('pilot-rules*.json'))
                    for document in [json.loads(path.read_text())]
                    if str(document.get('review_state', '')).startswith('owner_accepted')
                    for f in document['facts']}
        report, value = make({'RC09': {'choice': 'my_job'}, 'RC10': {'choice': 'no'}}, {'coverage.current': ['employer'], 'situation.age65': True})
        kept = [r['rule_id'] for r in applicable_rules(report, value, today=date(2026, 11, 8)) if r['fact_id'] in accepted]
        self.assertIn('working_coverage_small_employer', kept)
        self.assertIn('hsa_medicare', kept)

    def test_working_coverage_with_large_employer(self):
        report, value = make({'RC09': {'choice': 'my_job'}, 'RC10': {'choice': 'yes'}},
                             {'coverage.current': ['employer'], 'situation.age65': True})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        ids = [r['rule_id'] for r in rules]
        self.assertEqual(ids[:2], ['working_coverage_sep', 'hsa_medicare'])
        self.assertEqual(rules[0]['confirm_with'], ['RC14'])

    def test_unknown_employer_size_asks_for_it(self):
        report, value = make({'RC09': {'choice': 'spouse_job'}}, {'coverage.current': ['employer']})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        self.assertEqual(rules[0]['confirm_with'], ['RC10'])

    def test_advantage_gets_trial_right_and_nationwide(self):
        report, value = make({}, {'coverage.current': ['advantage']})
        ids = [r['rule_id'] for r in applicable_rules(report, value, focus='travel', today=date(2026, 11, 8))]
        self.assertEqual(ids, ['ma_trial_right', 'original_nationwide', 'annual_enrollment'])

    def test_original_without_drug_plan_gets_penalty_and_extra_help(self):
        report, value = make({}, {'coverage.current': ['original']})
        ids = [r['rule_id'] for r in applicable_rules(report, value, focus='drugs', today=date(2026, 11, 8))]
        # D157 (CV-04): Extra Help is raised by income or affordability trouble or by
        # asking how to lower drug costs, not by a drug focus alone.
        self.assertEqual(ids, ['partd_penalty', 'partd_cap', 'annual_enrollment'])
        asked = [r['rule_id'] for r in applicable_rules(report, value, focus='drugs', today=date(2026, 11, 8),
                                                        concern='asks how to lower prescription costs')]
        self.assertIn('extra_help', asked)

    def test_cobra_comes_before_any_plan_choice(self):
        report, value = make({}, {'coverage.current': ['cobra']})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        self.assertEqual(rules[0]['rule_id'], 'cobra_not_current_employment')
        self.assertEqual(rules[0]['fact_id'], 'cobra_timing')
        self.assertEqual(rules[0]['confirm_with'], ['RC04'])

    def test_holding_medigap_gets_the_return_underwriting_rule(self):
        report, value = make({}, {'coverage.current': ['original', 'medigap', 'drug']})
        ids = [r['rule_id'] for r in applicable_rules(report, value, today=date(2026, 11, 8))]
        self.assertEqual(ids, ['medigap_return_underwriting', 'annual_enrollment'])

    def test_no_rules_without_reports(self):
        self.assertEqual(applicable_rules(*make(), today=date(2026, 6, 1)), [])

    def test_open_enrollment_window_only_in_season(self):
        report, value = make({}, {'coverage.current': ['original', 'drug']})
        self.assertEqual([r['rule_id'] for r in applicable_rules(report, value, today=date(2026, 8, 1))], [])


class RequiredTargetTests(unittest.TestCase):
    moves = [{'id': 'RC10', 'question': {'id': 'RC10', 'question': 'Does the employer have 20 or more employees?'}},
             {'id': 'T06', 'question': {'id': 'T06', 'question': 'Which doctors or hospitals would you like to keep?'}},
             {'id': 'T10', 'question': {'id': 'T10', 'question': 'What matters most when we compare your options?'}}]

    def ranked(self, *relevant):
        return [{**m, 'decision_relevance': 'current_decision' if m['id'] in relevant else 'available_if_useful'} for m in self.moves]

    def test_required_clarification_wins(self):
        moves = [{**self.moves[1], 'required': True}, *self.moves[:1]]
        self.assertEqual(required_target(moves, self.ranked('RC10')), ('T06', 'clarification'))

    def test_pending_then_rule_then_relevance(self):
        self.assertEqual(required_target(self.moves, self.ranked('T10'), pending_id='T06'), ('T06', 'pending'))
        rules = [{'rule_id': 'working_coverage_sep', 'confirm_with': ['RC10']}]
        self.assertEqual(required_target(self.moves, self.ranked('T10'), rules=rules), ('RC10', 'rule:working_coverage_sep'))
        self.assertEqual(required_target(self.moves, self.ranked('T10')), ('T10', 'current_decision'))

    def test_deferred_answers_are_not_reasked(self):
        self.assertEqual(required_target(self.moves, self.ranked('T10'), dispositions={'T10': 'deferred'}), (None, None))

    def test_offer_and_referral_patterns(self):
        for text in ['Would you like help putting together a short list of questions for your benefits administrator?',
                     'Would it help to look more closely at how the costs differ?', 'Do you want me to draft that?']:
            self.assertTrue(offer_pattern.match(text), text)
        for text in ['Here are questions to ask Social Security.', 'Shall we prepare for that call?',
                     'Would you like a checklist for your conversation with Medicare?']:
            self.assertTrue(referral_pattern.search(text), text)
        for text in ['Which doctors would you like to keep?', 'Does the employer have 20 or more employees?',
                     'What part of that feels unclear?']:
            self.assertFalse(offer_pattern.match(text) or referral_pattern.search(text), text)


class RetestNov9RuleTests(unittest.TestCase):
    """Defects found in the Nov 9 live retest (R4, R6)."""
    TODAY = date(2026, 11, 9)

    def ids(self, reports, values, **kw):
        report, value = make(reports, values)
        return {r['rule_id']: r for r in applicable_rules(report, value, today=self.TODAY, **kw)}

    def test_paraphrased_money_pressure_selects_extra_help(self):
        for concern in ['Affording prescription drug costs', 'affordability of inhaler and insulin',
                        'Managing high prescription costs', 'financial strain from drug bills']:
            with self.subTest(concern=concern):
                rules = self.ids({}, {'coverage.current': ['original', 'drug']}, concern=concern)
                self.assertIn('extra_help', rules)

    def test_unrelated_concerns_do_not_select_extra_help(self):
        for concern in ['Part B timing after losing coverage', 'whether to keep the retiree package']:
            with self.subTest(concern=concern):
                self.assertNotIn('extra_help', self.ids({}, {'coverage.current': ['original', 'drug']}, concern=concern))

    def test_part_a_only_in_the_plans_view_hears_advantage_needs_part_b(self):
        rules = self.ids({'RC04': {'choice': 'a_only'}}, {'coverage.current': ['original']}, plans_view=True)
        self.assertEqual(rules['ma_requires_a_and_b']['status'], 'met')
        self.assertNotIn('ma_requires_a_and_b', self.ids({'RC04': {'choice': 'both'}}, {'coverage.current': ['original']}, plans_view=True))


if __name__ == '__main__':
    unittest.main()


class TrialRightResolutionTests(unittest.TestCase):
    """The 12-month trial right is resolved against the reported start (Nov 9, 2026)."""

    def test_first_plan_started_years_ago_is_not_met(self):
        report, value = make({'RC16': {'choice': 'yes', 'start': '2021-03'}}, {'coverage.current': ['advantage']})
        rule = applicable_rules(report, value, today=date(2026, 11, 8))[0]
        self.assertEqual((rule['rule_id'], rule['status']), ('ma_trial_right', 'not_met'))
        self.assertIn('March 2021', rule['applies_because'][1])
        self.assertIn('March 2022', rule['how_to_use'])

    def test_first_plan_started_this_year_is_met(self):
        report, value = make({'RC16': {'choice': 'yes', 'start': '2026-04'}}, {'coverage.current': ['advantage']})
        rule = applicable_rules(report, value, today=date(2026, 11, 8))[0]
        self.assertEqual(rule['status'], 'met')
        self.assertIn('April 2027', rule['how_to_use'])

    def test_not_first_plan_is_not_met_and_unknown_history_stays_conditional(self):
        report, value = make({'RC16': {'choice': 'no'}}, {'coverage.current': ['advantage']})
        self.assertEqual(applicable_rules(report, value, today=date(2026, 11, 8))[0]['status'], 'not_met')
        report, value = make({}, {'coverage.current': ['advantage']})
        self.assertEqual(applicable_rules(report, value, today=date(2026, 11, 8))[0]['status'], 'conditional')

    def test_floor_never_uses_a_rule_the_reports_rule_out(self):
        report, value = make({'RC16': {'choice': 'yes', 'start': '2019-06'}}, {'coverage.current': ['advantage']})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        chosen = floor_statement(rules)
        self.assertEqual(chosen['rule_id'], 'original_nationwide')
        # The confirming rule wins when the required question belongs to it.
        report, value = make({'RC09': {'choice': 'my_job'}}, {'coverage.current': ['employer'], 'situation.age65': True})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        self.assertEqual(floor_statement(rules, 'rule:working_coverage_sep')['rule_id'], 'working_coverage_sep')

    def test_floor_is_none_when_only_the_calendar_applies(self):
        report, value = make({}, {'coverage.current': ['original', 'drug']})
        rules = applicable_rules(report, value, today=date(2026, 11, 8))
        self.assertEqual([r['rule_id'] for r in rules], ['annual_enrollment'])
        self.assertIsNone(floor_statement(rules))


class SecondSetRuleTests(unittest.TestCase):
    """Triggers drafted from the 20-persona run (Nov 9, 2026); statements live in pilot-rules-r2.json."""
    TODAY = date(2026, 11, 9)

    def ids(self, reports, values, **kw):
        report, value = make(reports, values)
        return {r['rule_id']: r for r in applicable_rules(report, value, today=self.TODAY, **kw)}

    def test_job_coverage_that_ended_gets_the_eight_month_window_resolved(self):
        rules = self.ids({'RC04': {'choice': 'a_only'}, 'RC11': {'choice': 'dates', 'coverageEnd': '2026-10'}, 'RC09': {'choice': 'spouse_job'}},
                         {'coverage.current': ['original'], 'situation.age65': {'month': 3, 'year': 2024}})
        self.assertEqual(rules['partb_sep_coverage_ended']['status'], 'met')
        self.assertIn('June 2027', rules['partb_sep_coverage_ended']['how_to_use'])
        self.assertNotIn('working_coverage_sep', rules)
        self.assertNotIn('hsa_medicare', rules)
        self.assertIn('medigap_open_enrollment', rules)

    def test_lost_creditable_drug_coverage_opens_the_part_d_window(self):
        rules = self.ids({'RC04': {'choice': 'a_only'}, 'RC11': {'choice': 'dates', 'coverageEnd': '2026-10'}, 'RC12': {'choice': 'yes'}},
                         {'coverage.current': ['original']})
        self.assertEqual(rules['partd_sep_lost_creditable']['status'], 'met')

    def test_missed_part_b_without_job_coverage_gets_gep_and_penalty(self):
        rules = self.ids({'RC04': {'choice': 'a_only'}}, {'coverage.current': ['original'], 'situation.age65': {'month': 7, 'year': 2025}})
        self.assertEqual(rules['partb_gep_penalty']['status'], 'met')
        self.assertIn('medigap_open_enrollment', rules)
        # Not yet 65: no GEP rule.
        self.assertNotIn('partb_gep_penalty', self.ids({'RC04': {'choice': 'neither'}}, {'coverage.current': ['cobra'], 'situation.age65': {'month': 12, 'year': 2026}}))

    def test_cost_pressure_selects_the_assistance_rules_from_the_first_turn(self):
        rules = self.ids({}, {'coverage.current': ['original', 'drug']}, concern='cannot pay Medicare and groceries')
        self.assertEqual(rules['msp_extra_help_basics']['confirm_with'], ['RC18'])
        self.assertIn('extra_help', rules)
        self.assertNotIn('msp_extra_help_basics', self.ids({}, {'coverage.current': ['original', 'drug']}, concern='wants to understand networks'))
        # D157 (CV-04): a cost preference or priority is not a report of money trouble.
        self.assertNotIn('msp_extra_help_basics', self.ids({}, {'coverage.current': ['original', 'drug'], 'needs.costPreference': 'lower_monthly'}))
        self.assertNotIn('msp_extra_help_basics', self.ids({}, {'coverage.current': ['original', 'drug'], 'needs.priorities': ['total_cost', 'bills']}))

    def test_medicaid_or_part_b_help_gets_the_qmb_billing_rule(self):
        rules = self.ids({'RC18': {'choice': 'medicaid'}}, {'coverage.current': ['original', 'drug', 'medicaid']})
        self.assertEqual(rules['qmb_billing_protection']['status'], 'met')

    def test_move_out_of_area_gets_the_move_rules(self):
        rules = self.ids({'RC08': {'choice': 'move'}}, {'coverage.current': ['advantage']})
        self.assertEqual(rules['move_sep']['status'], 'met')
        self.assertEqual(rules['move_medigap_guaranteed_issue']['status'], 'met')

    def test_va_and_disability_and_former_medigap(self):
        self.assertEqual(self.ids({'RC26': {'choice': 'va'}}, {'coverage.current': ['military']})['va_and_medicare']['status'], 'met')
        self.assertIn('medigap_open_enrollment', self.ids({'RC06': {'choice': 'disability'}, 'RC04': {'choice': 'both'}}, {'coverage.current': ['advantage']}))
        rules = self.ids({'RC16': {'choice': 'yes', 'start': '2022-01', 'priorMedigap': 'yes'}}, {'coverage.current': ['advantage']})
        self.assertIn('medigap_return_underwriting', rules)
        self.assertEqual(rules['ma_trial_right']['status'], 'not_met')
