"""D161 enrollment record contracts; fictional reports, no network or models."""
import copy
from datetime import date
import json
import unittest
from unittest.mock import patch

import test_natural_flow as harness
import enrollment_flow
import enrollment_journey
import ux_flow


TODAY = date(2026, 11, 12)


class EnrollmentJourneyTests(unittest.TestCase):
    def setUp(self):
        # Reuse PP16's real conversation harness without inheriting its tests.
        harness.NaturalFlowTests.setUp(self)
        for guard in (patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')),
                      patch.object(self.flow.agent.client, 'create',
                                   side_effect=AssertionError('Model calls forbidden'))):
            guard.start()
            self.addCleanup(guard.stop)

    def put(self, key, value):
        self.flow.put(self.g, key, value, 'user_text')

    def fact(self, identifier, **value):
        self.flow.fact(self.r, identifier, value, 'user_text')

    def part(self, part, state, when=None, kind='application'):
        self.put('enrollment.part' + part,
                 {'status': state, 'date': when, 'date_kind': kind})

    def turning_65(self, choice='neither', coverage='cobra'):
        self.put('situation.age65', {'month': 11, 'year': 2026, 'first_day': False})
        self.put('coverage.current', [coverage])
        self.fact('RC04', choice=choice)

    def components(self, medigap='not_needed', part_d='not_needed'):
        self.put('intent.components', {'medigap': medigap, 'part_d': part_d})

    def status(self, today=TODAY):
        before = copy.deepcopy((self.g, self.r, self.flow.contract))
        out = enrollment_journey.status(self.flow, self.g, self.r, today=today)
        self.assertEqual((self.g, self.r, self.flow.contract), before)
        self.assertEqual(self.calls, [])
        self.assertEqual(json.loads(json.dumps(out)), out)
        self.assertEqual(set(out), {'version', 'parts', 'window', 'route',
                                    'next_step', 'components', 'finish', 'unsupported', 'coverage_end'})
        self.assertEqual(out['version'], 'enrollment-journey-v2')
        self.assertEqual(set(out['parts']), {'A', 'B'})
        for part in out['parts'].values():
            self.assertEqual(set(part), {'state', 'start'})
            self.assertEqual(set(part['start']), {'date', 'basis'})
            self.assertIn(part['state'], {'active', 'pending', 'approved_future',
                                         'expected_automatically', 'needed', 'needs_info', 'unknown'})
            self.assertIn(part['start']['basis'], {'reported', 'estimated', None})
        self.assertEqual(set(out['next_step']), {'id', 'by', 'basis'})
        self.assertIn(out['next_step']['id'], {'sign_up', 'wait_for_decision', 'answer_request',
            'confirm_start_date', 'choose_path', 'choose_medigap', 'choose_part_d',
            'choose_advantage_plan', 'nothing_needed', 'confirm_with_social_security'})
        self.assertIn(out['route'], {'sign_up_a_and_b', 'add_part_b', 'add_part_a',
                                    'automatic', 'none_needed', 'confirm_with_social_security'})
        return out

    def test_turning_65_on_cobra(self):
        self.turning_65()
        out = self.status()
        self.assertEqual([p['state'] for p in out['parts'].values()], ['needed', 'needed'])
        self.assertEqual(out['route'], 'sign_up_a_and_b')
        self.assertEqual(out['window'], {'start': '2026-08-01', 'end': '2027-02-28', 'phase': 'inside'})
        self.assertEqual(out['parts']['B']['start'], {'date': '2026-12-01', 'basis': 'estimated'})
        self.assertEqual(out['next_step'], {'id': 'sign_up', 'by': '2027-02-28', 'basis': 'estimated'})

    def test_application_changes_only_that_part_and_waits(self):
        self.turning_65()
        before = self.status()
        self.part('B', 'applied', '2026-11-05')
        out = self.status()
        self.assertEqual(out['parts']['A'], before['parts']['A'])
        self.assertEqual(out['parts']['B'], {'state': 'pending', 'start': {'date': None, 'basis': None}})
        self.assertEqual(out['next_step']['id'], 'wait_for_decision')
        self.assertNotIn('active', [p['state'] for p in out['parts'].values()])

    def test_a_active_b_approved_future(self):
        self.turning_65('a_only')
        self.part('B', 'approved', '2026-12-01', 'start')
        out = self.status()
        self.assertEqual(out['parts']['A']['state'], 'active')
        self.assertEqual(out['parts']['A']['start'], {'date': None, 'basis': None})
        self.assertEqual(out['parts']['B'], {'state': 'approved_future',
                         'start': {'date': '2026-12-01', 'basis': 'reported'}})
        self.assertEqual(out['next_step'], {'id': 'confirm_start_date', 'by': '2026-12-01', 'basis': 'reported'})

    def test_a_and_b_only_is_a_finish_without_a_path_or_supplement(self):
        self.fact('RC04', choice='both')
        self.components()
        out = self.status()
        self.assertEqual(out['finish'], 'ab_only')
        self.assertEqual(out['next_step']['id'], 'nothing_needed')
        self.assertEqual(out['route'], 'none_needed')

    def test_existing_medigap_and_undecided_part_d(self):
        self.fact('RC04', choice='both')
        self.put('intent.coveragePath', 'original_medigap')
        self.components('keep_existing', 'decide_later')
        out = self.status()
        self.assertIsNone(out['finish'])
        self.assertEqual(out['next_step']['id'], 'choose_part_d')

    def test_current_work_withdraws_estimates_but_keeps_window(self):
        self.turning_65(coverage='employer')
        out = self.status()
        self.assertEqual(out['route'], 'confirm_with_social_security')
        self.assertIn('current_work_coverage', out['unsupported'])
        self.assertIsNotNone(out['window'])
        for part in out['parts'].values():
            self.assertEqual(part['start'], {'date': None, 'basis': None})
        self.assertIsNone(out['next_step']['by'])

    def test_d164_current_work_before_and_after_i_applied(self):
        today = date(2026, 11, 13)
        self.put('subject.role', 'self')
        self.put('situation.age65', {'month': 10, 'year': 2026, 'first_day': False})
        self.put('coverage.current', ['employer'])
        self.fact('RC09', choice='my_job')
        self.put('situation.retirement', {'status': 'retiring', 'when': 'in December 2026'})
        start = {'date': None, 'basis': None}
        expected = {
            'version': 'enrollment-journey-v2',
            'parts': {'A': {'state': 'unknown', 'start': start}, 'B': {'state': 'unknown', 'start': start}},
            'window': {'start': '2026-07-01', 'end': '2027-01-31', 'phase': 'inside'},
            'route': 'confirm_with_social_security',
            'next_step': {'id': 'confirm_with_social_security', 'by': None, 'basis': None},
            'components': {'medigap': 'unknown', 'part_d': 'unknown'}, 'finish': None,
            'unsupported': ['current_work_coverage'],
            'coverage_end': {'date': '2026-12-31', 'precision': 'month', 'basis': 'reported',
                             'source': 'S_RETIREMENT'},
        }
        self.assertEqual(self.status(today), expected)
        with patch.object(ux_flow, 'TODAY', today):
            enrollment_flow.capture(self.flow, self.g, self.r, 'I applied')
        expected['parts'] = {part: {'state': 'pending', 'start': start} for part in ('A', 'B')}
        expected['route'] = 'none_needed'
        expected['next_step']['id'] = 'wait_for_decision'
        self.assertEqual(self.status(today), expected)

    def test_held_status_follows_only_settled_part_reports(self):
        self.turning_65('a_only', 'employer')
        self.part('A', 'needs_info')
        self.assertEqual(self.status()['next_step']['id'], 'confirm_with_social_security')
        self.part('B', 'approved', '2026-12-01', 'start')
        self.assertEqual(self.status()['next_step']['id'], 'answer_request')
        self.part('A', 'active', '2026-12-01', 'start')
        self.assertEqual(self.status()['next_step']['id'], 'confirm_start_date')
        self.part('A', 'applied')
        self.put('intent.coveragePath', 'medicare_advantage')
        self.assertEqual(self.status()['next_step']['id'], 'wait_for_decision')
        self.part('A', 'active')
        out = self.status()
        self.assertEqual(out['route'], 'none_needed')
        self.assertEqual(out['next_step'], {'id': 'confirm_start_date', 'by': None, 'basis': None})
        self.assertEqual(out['parts']['B']['start'], {'date': '2026-12-01', 'basis': 'reported'})
        self.part('A', 'denied')
        self.assertEqual(self.status()['next_step']['id'], 'confirm_with_social_security')

    def test_reported_coverage_end_precedence_and_precision(self):
        self.turning_65(coverage='employer')
        self.put('situation.retirement', {'status': 'retiring', 'when': 'at the end of the year'})
        self.assertIsNone(self.status()['coverage_end'])
        self.put('situation.retirement', {'status': 'retiring', 'when': 'December 2026'})
        self.fact('RC11', coverageEnd='2028-02', jobEnd='2027-01-03')
        self.assertEqual(self.status()['coverage_end'], {
            'date': '2028-02-29', 'precision': 'month', 'basis': 'reported', 'source': 'RC11.coverageEnd'})
        self.fact('RC11', coverageEnd='2027-02-29', jobEnd='2027-01-03')
        self.assertEqual(self.status()['coverage_end'], {
            'date': '2027-01-03', 'precision': 'day', 'basis': 'reported', 'source': 'RC11.jobEnd'})
        self.r['facts']['RC11']['stale'] = True
        self.assertEqual(self.status()['coverage_end']['source'], 'S_RETIREMENT')

    def test_requests_and_denials_override_active_rc04(self):
        for state, action in [('needs_info', 'answer_request'), ('denied', 'confirm_with_social_security')]:
            with self.subTest(state=state):
                self.turning_65('both')
                self.part('B', state)
                out = self.status()
                self.assertEqual(out['parts']['A']['state'], 'active')
                self.assertEqual(out['parts']['B']['state'], 'needs_info')
                self.assertEqual(out['next_step']['id'], action)
                self.assertIsNone(out['finish'])

    def test_advantage_can_be_explored_with_b_pending(self):
        self.turning_65('a_only')
        self.part('B', 'applied', '2026-11-05')
        self.put('intent.coveragePath', 'medicare_advantage')
        out = self.status()
        self.assertEqual(out['parts']['B']['state'], 'pending')
        self.assertEqual(out['next_step']['id'], 'choose_advantage_plan')
        self.assertEqual(out['unsupported'], [])
        self.assertIsNone(out['finish'])

    def test_birthday_correction_changes_only_dependent_dates(self):
        self.turning_65()
        self.components('keep_existing', 'decide_later')
        self.put('intent.coveragePath', 'original_medigap')
        before = self.status()
        self.put('situation.age65', {'month': 2, 'year': 2027, 'first_day': False})
        after = self.status()
        self.assertEqual(after['window'], {'start': '2026-11-01', 'end': '2027-05-31', 'phase': 'inside'})
        self.assertEqual(after['parts']['B']['start'], {'date': '2027-02-01', 'basis': 'estimated'})
        self.assertEqual(after['next_step']['by'], '2027-05-31')
        for value in (before, after):
            value.pop('window')
            value['next_step']['by'] = None
            for part in value['parts'].values():
                part['start']['date'] = None
        self.assertEqual(before, after)

    def test_unanswered_and_explicitly_unknown_are_distinct(self):
        out = self.status()
        self.assertEqual([p['state'] for p in out['parts'].values()], ['unknown', 'unknown'])
        self.assertEqual(out['components'], {'medigap': 'unknown', 'part_d': 'unknown'})
        self.assertIsNone(out['window'])
        self.assertIsNone(out['finish'])
        self.assertEqual(out['unsupported'], [])
        self.assertEqual(out['route'], 'none_needed')
        self.assertEqual(out['next_step'], {'id': 'nothing_needed', 'by': None, 'basis': None})
        self.fact('RC04', choice='unknown')
        out = self.status()
        self.assertEqual(out['next_step']['id'], 'confirm_with_social_security')
        self.assertIn('unclear_status', out['unsupported'])

    def test_part_b_only_adds_a_and_retiree_uses_age_window(self):
        self.turning_65('b_only', 'retiree')
        out = self.status()
        self.assertEqual(out['route'], 'add_part_a')
        self.assertEqual(out['parts']['B']['state'], 'active')
        self.assertEqual(out['parts']['B']['start'], {'date': None, 'basis': None})
        self.assertEqual(out['parts']['A']['start'], {'date': '2026-11-01', 'basis': 'estimated'})

    def test_part_a_only_adds_b(self):
        self.turning_65('a_only')
        self.assertEqual(self.status()['route'], 'add_part_b')

    def test_general_pending_never_becomes_active(self):
        self.turning_65('pending')
        for today in (TODAY, date(2026, 12, 12)):
            out = self.status(today)
            self.assertEqual([p['state'] for p in out['parts'].values()], ['pending', 'pending'])
            self.assertTrue(all(p['start']['date'] is None for p in out['parts'].values()))

    def test_original_path_does_not_choose_medigap(self):
        self.fact('RC04', choice='both')
        for path in ('original_only', 'original_medigap'):
            with self.subTest(path=path):
                self.put('intent.coveragePath', path)
                out = self.status()
                self.assertEqual(out['components']['medigap'], 'unknown')
                self.assertIsNone(out['finish'])
                self.assertEqual(out['next_step']['id'], 'choose_medigap')
        self.components()
        self.assertEqual(self.status()['finish'], 'ab_only')

    def test_components_must_both_be_resolved_to_finish_original_plus(self):
        self.fact('RC04', choice='both')
        for component in ('chosen', 'keep_existing'):
            self.components(component, 'decide_later')
            self.assertIsNone(self.status()['finish'])
            self.components(component, 'not_needed')
            out = self.status()
            self.assertEqual(out['finish'], 'original_plus')
            self.assertEqual(out['next_step']['id'], 'nothing_needed')

    def test_keep_and_wait_are_explicit_finishes(self):
        self.turning_65()
        for path in ('keep_current', 'wait'):
            self.put('intent.coveragePath', path)
            out = self.status()
            self.assertEqual(out['finish'], path)
            self.assertEqual(out['next_step'], {'id': 'nothing_needed', 'by': None, 'basis': None})

    def test_pending_ab_only_is_a_finish_but_still_waits(self):
        self.fact('RC04', choice='pending')
        self.components()
        out = self.status()
        self.assertEqual(out['finish'], 'ab_only')
        self.assertEqual(out['next_step']['id'], 'wait_for_decision')

    def test_scope_guards(self):
        cases = [('RC06', 'disability', 'not_age_based'), ('RC06', 'esrd', 'not_age_based'),
                 ('RC06', 'als', 'not_age_based'), ('RC06', 'railroad', 'railroad'),
                 ('RC06', 'other', 'unclear_status'),
                 ('RC09', 'spouse_job', 'current_work_coverage'),
                 ('RC09', 'family_job', 'current_work_coverage')]
        for identifier, choice, reason in cases:
            with self.subTest(choice=choice):
                self.g, self.r = self.flow.initial()
                self.turning_65()
                self.fact(identifier, choice=choice)
                out = self.status()
                self.assertEqual(out['route'], 'confirm_with_social_security')
                self.assertIn(reason, out['unsupported'])
                self.assertTrue(all(p['start']['date'] is None for p in out['parts'].values()))
                self.assertIsNone(out['next_step']['by'])

    def test_closed_window_has_no_start_estimates(self):
        self.turning_65()
        out = self.status(date(2027, 3, 1))
        self.assertEqual(out['window']['phase'], 'after')
        self.assertIn('window_passed', out['unsupported'])
        self.assertEqual(out['route'], 'confirm_with_social_security')
        self.assertTrue(all(p['start']['date'] is None for p in out['parts'].values()))

    def test_scope_hold_does_not_erase_resolved_coverage_decisions(self):
        self.turning_65('both')
        self.components()
        out = self.status(date(2027, 3, 1))
        self.assertEqual(out['finish'], 'ab_only')
        self.assertEqual(out['route'], 'none_needed')
        self.assertEqual(out['next_step']['id'], 'nothing_needed')
        self.assertEqual(out['unsupported'], ['window_passed'])

    def test_unsupported_case_preserves_reported_date(self):
        self.turning_65('a_only', 'employer')
        self.part('B', 'approved', '2026-12-01', 'start')
        out = self.status()
        self.assertEqual(out['parts']['B']['start'], {'date': '2026-12-01', 'basis': 'reported'})
        self.assertIsNone(out['next_step']['by'])

    def test_first_day_and_window_boundaries_come_from_helper(self):
        self.turning_65()
        self.put('situation.age65', {'month': 11, 'year': 2026, 'first_day': True})
        for today, phase in [(date(2026, 6, 30), 'before'), (date(2026, 7, 1), 'inside'),
                             (date(2027, 1, 31), 'inside'), (date(2027, 2, 1), 'after')]:
            with self.subTest(today=today):
                out = self.status(today)
                self.assertEqual(out['window'], {'start': '2026-07-01', 'end': '2027-01-31', 'phase': phase})

    def test_helper_is_the_only_estimate_source(self):
        self.turning_65()
        with patch.object(enrollment_journey, 'enrollment_timing', wraps=enrollment_journey.enrollment_timing) as timing:
            self.status()
        timing.assert_called_once_with(self.flow.value(self.g, 'situation.age65'), TODAY, 'neither')

    def test_application_date_is_never_a_start(self):
        self.turning_65('both')
        for state in ('applied', 'approved', 'active'):
            with self.subTest(state=state):
                self.part('B', state, '2026-11-01', 'application')
                out = self.status()
                self.assertEqual(out['parts']['B']['start'], {'date': None, 'basis': None})
                if state == 'approved':
                    self.assertEqual(out['parts']['B']['state'], 'unknown')
                    self.assertEqual(out['next_step']['id'], 'confirm_start_date')

    def test_only_reported_approved_start_can_mature_into_active(self):
        self.turning_65('a_only')
        self.part('B', 'approved', '2026-12-01', 'start')
        self.assertEqual(self.status()['parts']['B']['state'], 'approved_future')
        self.assertEqual(self.status(date(2026, 12, 1))['parts']['B']['state'], 'active')
        self.part('B', 'applied', '2026-11-01', 'start')
        self.assertEqual(self.status()['parts']['B']['state'], 'pending')

    def test_invalid_dates_and_statuses_do_not_resurrect_rc04_active(self):
        self.turning_65('both')
        for when in ('2026-02-30', '20261201', 'next month'):
            self.part('B', 'approved', when, 'start')
            out = self.status()
            self.assertEqual(out['parts']['B']['state'], 'unknown')
            self.assertIsNone(out['parts']['B']['start']['date'])
        for value in ({}, {'status': 'unexpected'}, 'applied'):
            self.put('enrollment.partB', value)
            out = self.status()
            self.assertEqual(out['parts']['B']['state'], 'unknown')
            self.assertIn('unclear_status', out['unsupported'])

    def test_reported_starts_and_preferences_survive_birthday_correction(self):
        self.turning_65('a_only')
        self.part('B', 'approved', '2026-12-01', 'start')
        self.put('intent.coveragePath', 'medicare_advantage')
        before = self.status()
        self.put('situation.age65', {'month': 2, 'year': 2027, 'first_day': True})
        after = self.status()
        self.assertNotEqual(before.pop('window'), after.pop('window'))
        self.assertEqual(before, after)

    def test_absent_birthday_or_parts_does_not_invent_estimates(self):
        self.fact('RC04', choice='neither')
        self.assertIsNone(self.status()['window'])
        self.g, self.r = self.flow.initial()
        self.put('situation.age65', {'month': 11, 'year': 2026})
        out = self.status()
        self.assertIsNotNone(out['window'])
        self.assertTrue(all(p['start']['date'] is None for p in out['parts'].values()))
        self.assertEqual(out['next_step']['id'], 'nothing_needed')

    def test_generic_benefits_receipt_does_not_prove_automatic_enrollment(self):
        self.turning_65()
        self.put('coverage.socialBenefits', 'yes')
        out = self.status()
        self.assertEqual(out['route'], 'sign_up_a_and_b')
        self.assertTrue(all(p['state'] == 'needed' for p in out['parts'].values()))

    def test_active_with_a_future_date_keeps_the_conflict_visible(self):
        self.fact('RC04', choice='both')
        self.part('B', 'active', '2026-12-01', 'start')
        out = self.status()
        self.assertEqual(out['parts']['B']['state'], 'needs_info')
        self.assertEqual(out['next_step']['id'], 'confirm_start_date')
        self.assertIsNone(out['finish'])

    def test_stale_reports_are_not_reused(self):
        self.part('A', 'active')
        self.g['fields']['enrollment.partA']['status'] = 'stale'
        self.fact('RC04', choice='both')
        self.r['facts']['RC04']['stale'] = True
        out = self.status()
        self.assertEqual([p['state'] for p in out['parts'].values()], ['unknown', 'unknown'])

    def test_reports_resolve_rc04_uncertainty_independently(self):
        self.fact('RC04', choice='unknown')
        self.part('A', 'active')
        self.assertIn('unclear_status', self.status()['unsupported'])
        self.part('B', 'applied', '2026-11-01')
        out = self.status()
        self.assertEqual(out['unsupported'], [])
        self.assertEqual([p['state'] for p in out['parts'].values()], ['active', 'pending'])

    def test_unknown_component_and_malformed_birthday_stay_unknown(self):
        self.fact('RC04', choice='both')
        self.put('intent.components', {'medigap': 'chosen', 'part_d': 'not_a_choice'})
        self.put('situation.age65', {'month': 13, 'year': 2026})
        out = self.status()
        self.assertIsNone(out['window'])
        self.assertIsNone(out['finish'])
        self.assertEqual(out['components']['part_d'], 'unknown')
        self.assertEqual(out['next_step']['id'], 'choose_part_d')

    def test_railroad_and_other_coverage_require_confirmation(self):
        for coverage, reason in [('railroad', 'railroad'), ('other', 'unclear_status')]:
            with self.subTest(coverage=coverage):
                self.turning_65(coverage=coverage)
                out = self.status()
                self.assertIn(reason, out['unsupported'])
                self.assertEqual(out['route'], 'confirm_with_social_security')
                self.assertTrue(all(p['start']['date'] is None for p in out['parts'].values()))

    def test_advantage_path_does_not_finish_before_a_plan_decision(self):
        self.fact('RC04', choice='both')
        self.put('intent.coveragePath', 'medicare_advantage')
        self.components()
        out = self.status()
        self.assertIsNone(out['finish'])
        self.assertEqual(out['next_step']['id'], 'choose_advantage_plan')

    def test_date_default_and_repeated_calls(self):
        self.turning_65()
        with patch.object(enrollment_journey, 'date', wraps=date) as clock:
            clock.today.return_value = TODAY
            out = enrollment_journey.status(self.flow, self.g, self.r)
        self.assertEqual(out, self.status())
        self.assertEqual(self.status(), self.status())


if __name__ == '__main__':
    unittest.main()
