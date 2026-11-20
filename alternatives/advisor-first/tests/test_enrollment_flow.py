"""D161 acceptance stories (PLAN.md section 7) as offline scripted journeys.

Fictional people. Scripted transport: no network, no model billing. Each test
starts from the person's own words or previously entered reports. These prove
the code-side behaviour (capture, status line, cards, dashboard summary), not
how a live model replies (UX playbook lesson 10). The enrollment record itself
is Codex's ``enrollment_journey.status``; nothing here edits or re-tests it.
"""
import copy
from datetime import date
import json
import re
import unittest
from unittest.mock import patch

import test_natural_flow as harness
from guest_profiles import ProfileError
import enrollment_flow
import part_d_profile
import ux_flow
import ux_pass

TODAY = date(2026, 11, 12)
QUIET = {'question_target': None, 'question': '', 'reply': 'Okay.'}
PP16_LINE = ('Part A: not yet · Part B: not yet. Next: sign up through Social Security by '
             'February 28, 2027 (from your birthday month).')
ISO = re.compile(r'\b20\d{2}-\d{2}-\d{2}\b')
LONG_DATE = re.compile(r'(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, 20\d{2}')


class Journey(unittest.TestCase):
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)
    enable = True

    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        ux_flow.TODAY = TODAY
        self.addCleanup(setattr, ux_flow, 'TODAY', None)
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)
        if self.enable:
            enrollment_flow.enable(self.flow)

    @staticmethod
    def situation(kind, text, **value):
        return {'kind': kind, 'subject': 'beneficiary', 'scope': 'current', 'quote': text,
                'uncertain': False, 'correction': False, 'month': value.get('month'),
                'year': value.get('year'), 'status': value.get('status', ''), 'when': value.get('when', '')}

    def say(self, text, updates=(), compose=QUIET, **extra):
        return self.message(text, updates, compose=compose, extraction=self.extraction(updates, **extra))

    def pick(self, identifier, **fields):
        return self.turn({'type': 'choice', 'id': identifier, 'fields': fields})

    def decide(self, **fields):
        return self.turn({'type': 'enrollment_decision', **fields}, aiConsent=False, contextPolicy=None)

    def put(self, key, value):
        self.flow.put(self.g, key, value, 'user_text')

    def fact(self, identifier, **value):
        self.flow.fact(self.r, identifier, value, 'user_text')

    def person(self, coverage='cobra', month=11, year=2026, parts='neither', role='self'):
        """The live run's order: who, coverage, birthday month, then Parts A and B."""
        self.choice('RC01', choice=role)
        self.choice('T05', choice=coverage)
        text = '%s 65 on %s 8 %d' % ('She turns' if role == 'someone' else 'I turn', ux_pass.MONTH_NAMES[month - 1], year)
        self.say(text, situation_proposals=[self.situation('age65', text, month=month, year=year)])
        return self.pick('RC04', choice=parts)

    def seen(self):
        """The view rebuilt from the reports alone, as a reload or return gets it."""
        return enrollment_flow.view(self.flow, self.g, self.r)

    def cards(self, out, kind):
        return [card for card in out.get('cards', []) if card['kind'] == kind]

    def assert_dates_labelled(self, text):
        """An estimated date is never shown as confirmed; a reported one says so."""
        for found in LONG_DATE.finditer(text):
            after = text[found.end():found.end() + 40]
            self.assertTrue(after.startswith((' (from your birthday month)', ' (you told me)', ' (the date you told me)'))
                            or 'start date of' in text[max(0, found.start() - 20):found.start()],
                            'unlabelled date in: ' + text)


class Stories(Journey):
    # 1. Turning 65, neither part, wants predictable costs ---------------------
    def test_01_turning_65_neither_part(self):
        out = self.person()
        self.assertEqual(out['enrollment']['line']['text'], PP16_LINE)
        self.assert_dates_labelled(PP16_LINE)
        self.assertEqual(out['enrollment']['record']['route'], 'sign_up_a_and_b')
        # One card a turn: the timing card first, the route on the next quiet turn, once.
        self.assertTrue(self.cards(out, 'enrollment_timing'))
        self.assertFalse(self.cards(out, 'signup_route'))
        after = self.say('ok')
        route = self.cards(after, 'signup_route')
        self.assertEqual(len(route), 1)
        self.assertEqual(route[0]['title'], 'How to sign up for Part A and Part B')
        self.assertIn('1-800-772-1213', route[0]['text'])
        self.assertIn('never needs your Social Security number', route[0]['text'])
        self.assertTrue(all(source['url'].startswith('https://') for source in route[0]['sources']))
        self.assertEqual(route[0]['guides'], ['online_ab', 'phone'])
        self.assertFalse(self.cards(self.say('thanks'), 'signup_route'))
        self.assertEqual(len(self.cards(self.say('how do I sign up again?'), 'signup_route')), 1)   # asked
        # Both paths stay open; Original Medicare opens on its plans, with the A/B step still shown.
        board = self.seen()['dashboard']
        self.assertEqual(set(board['paths']), {'original', 'advantage'})
        self.assertEqual(board['paths']['original']['open'], 'ab')      # step 1 until both parts are in place (owner, Nov 13)
        self.assertEqual(board['paths']['advantage']['open'], 'ab')
        self.assertEqual([step['id'] for step in board['paths']['original']['steps']], ['ab', 'medigap', 'part_d'])
        self.assertEqual([step['id'] for step in board['paths']['advantage']['steps']], ['ab', 'plan', 'drugs'])
        self.assertEqual(board['paths']['original']['steps'][0]['state'], 'open')
        self.assertEqual(self.seen()['line']['text'], PP16_LINE)     # the next action is retained

    # 2. Automatic enrollment expected -----------------------------------------
    def test_02_benefits_already_paid_gets_no_duplicate_application_instruction(self):
        self.put('coverage.socialBenefits', 'yes')
        out = self.person(coverage='none')
        line = out['enrollment']['line']['text']
        self.assertIn('Next: check with Social Security whether you’re being signed up automatically.', line)
        self.assertNotIn('sign up through Social Security by', line)
        route = self.cards(self.say('ok'), 'signup_route')[0]
        self.assertEqual(route['statement_ids'][:2], ['automatic', 'automatic_check'])
        self.assertIn('at least 4 months before you turn 65', route['text'])
        # The record cannot establish automatic enrollment from a generic yes, so it is never asserted.
        self.assertNotIn('expected_automatically', json.dumps(out['enrollment']['record']))
        # Separate effective dates, captured when the person reports them.
        self.say('Part A starts November 1 and Part B starts December 1.')
        self.assertEqual(self.flow.value(self.g, 'enrollment.partA'),
                         {'status': 'active', 'date': '2026-11-01', 'date_kind': 'start'})
        self.assertEqual(self.flow.value(self.g, 'enrollment.partB'),
                         {'status': 'approved', 'date': '2026-12-01', 'date_kind': 'start'})
        text = self.seen()['line']['text']
        self.assertIn('Part A: active since November 1, 2026 (you told me)', text)
        self.assertIn('Part B: starts December 1, 2026 (you told me)', text)
        self.assert_dates_labelled(text)

    # 3. Part A active, Part B pending ------------------------------------------
    def test_03_part_a_active_part_b_pending(self):
        self.person(parts='a_only')
        out = self.say('I applied for Part B last week.')
        self.assertEqual(self.flow.value(self.g, 'enrollment.partB'),
                         {'status': 'applied', 'date': None, 'date_kind': 'application'})
        self.assertIsNone(self.flow.value(self.g, 'enrollment.partA'))
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')
        self.assertEqual(out['enrollment']['line']['text'],
                         'Part A: active · Part B: applied, waiting to hear. Next: wait for Social Security’s decision letter.')
        self.assertEqual(out['enrollment']['dashboard']['paths']['original']['steps'][0]['state'], 'pending')
        # Time passing never turns an application into coverage, and nobody is told to apply again.
        ux_flow.TODAY = date(2027, 1, 20)
        later = self.say('ok')
        self.assertEqual(later['enrollment']['record']['parts']['B']['state'], 'pending')
        self.assertFalse(self.cards(later, 'signup_route'))
        self.assertFalse(self.cards(self.say('anything else?'), 'signup_route'))
        # Plan research continues: both paths and their steps are still there.
        self.assertEqual(later['enrollment']['dashboard']['paths']['original']['open'], 'ab')

    # 4. Part B only -------------------------------------------------------------
    def test_04_part_b_only_is_guided_to_part_a(self):
        out = self.person(parts='b_only')
        self.assertEqual(out['enrollment']['record']['route'], 'add_part_a')
        self.assertTrue(out['enrollment']['line']['text'].startswith(
            'Part A: not yet · Part B: active. Next: sign up for Part A through Social Security by'))
        route = out['enrollment']['route']
        self.assertEqual(route['title'], 'How to sign up for Part A')
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'b_only')    # never silently "both"
        self.assertEqual(out['enrollment']['before']['applies'], True)

    # 5. Still working with group coverage ---------------------------------------
    def test_05_coverage_from_current_work_gets_the_rule_and_no_personal_date(self):
        out = self.person(coverage='employer')
        view = out['enrollment']
        self.assertEqual(view['record']['unsupported'], ['current_work_coverage'])
        self.assertEqual(view['line']['text'], 'Part A: not yet · Part B: not yet. Next: confirm your sign-up timing '
                                               'with Social Security at 1-800-772-1213.')
        self.assertEqual(view['dates'], [])
        self.assertFalse(LONG_DATE.search(json.dumps(view['line'])))
        route = view['route']
        self.assertEqual(route['title'], 'Confirm with Social Security')
        # Redirect, don't deflect: the accepted general rule comes before who confirms.
        self.assertEqual(route['statement_ids'][:2], ['current_work', 'confirm_ssa'])
        self.assertIn('eight-month Special Enrollment Period', route['text'])
        self.assertNotIn('sign up through Social Security by', json.dumps(view))    # no automatic advice to enroll

    # 6. PP16: 65, COBRA, neither part -------------------------------------------
    def test_06_pp16_reuses_reports_and_shows_the_route_once(self):
        out = self.person()
        calls = len(self.calls)
        self.assertEqual(out['enrollment']['line']['text'], PP16_LINE)     # as soon as Parts A and B are known
        routes = 0
        for words in ('ok', 'thanks', 'I see', 'what about my doctors'):
            routes += len(self.cards(self.say(words), 'signup_route'))
        self.assertEqual(routes, 1)
        self.assertGreater(len(self.calls), calls)
        # Nothing already reported is asked again on the way.
        asked = [item['id'] for item in self.flow.eligible(self.owner, self.g, self.r)]
        for known in ('RC01', 'T05', 'S_AGE65', 'RC04'):
            self.assertNotIn(known, asked)

    # 7. Both parts, existing Medigap, needs only Part D ---------------------------
    def test_07_only_drug_coverage_opens_at_step_three(self):
        self.put('subject.role', 'self')
        self.put('coverage.current', ['original', 'medigap'])
        self.fact('RC04', choice='both')
        view = self.seen()
        original = view['dashboard']['paths']['original']
        self.assertEqual(original['open'], 'part_d')
        self.assertEqual(original['steps'][0]['state'], 'done')
        self.assertEqual(original['steps'][1]['text'], 'You have a Medigap policy.')   # owner sign-off, November 13, 2026
        self.assertIsNone(view['route'])                         # no first-enrollment loop
        self.assertEqual(view['line']['text'], 'Part A: active · Part B: active. Next: decide on prescription coverage.')

    def test_07b_asking_for_drug_plans_opens_at_step_three(self):
        self.person(parts='both', coverage='none')
        self.task('drug_pricing')
        self.assertEqual(self.seen()['dashboard']['paths']['original']['open'], 'part_d')

    # 8. Wants Medicare Advantage before Parts A and B begin -----------------------
    def test_08_advantage_before_parts_begin(self):
        self.person()
        out = self.say('I want Medicare Advantage.')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'medicare_advantage')
        view = out['enrollment']
        self.assertEqual(view['line']['text'], 'Part A: not yet · Part B: not yet. Next: choose a Medicare Advantage plan, and '
                         'sign up for Parts A and B through Social Security by February 28, 2027 (from your birthday month).')
        before = view['before']
        self.assertEqual((before['applies'], before['action'], before['ready']), (True, 'a Medicare Advantage plan', False))
        self.assertIn('requires both Parts A and B', before['needs'])
        # Research stays open: the path is not marked unavailable anywhere.
        self.assertEqual(view['dashboard']['paths']['advantage']['open'], 'ab')
        self.assertEqual([step['id'] for step in view['dashboard']['paths']['advantage']['steps']], ['ab', 'plan', 'drugs'])
        self.assertNotIn('unsuitable', json.dumps(view).casefold())

    # 9. First-day birthday, missed window, disability, restarting Part B ----------
    def test_09a_first_day_birthday_moves_the_window_a_month_earlier(self):
        self.put('situation.age65', {'month': 12, 'year': 2026, 'first_day': True})
        self.put('coverage.current', ['none'])
        self.fact('RC04', choice='neither')
        window = next(row for row in self.seen()['dates'] if row['label'] == 'Sign-up window')
        self.assertEqual((window['value'], window['basis']), ('August 1, 2026 to February 28, 2027', 'estimated'))

    def test_09b_missed_window_gets_the_general_rule_not_a_date(self):
        self.put('situation.age65', {'month': 3, 'year': 2026, 'first_day': False})
        self.put('coverage.current', ['none'])
        self.fact('RC04', choice='a_only')       # restarting or adding Part B after the window
        view = self.seen()
        self.assertIn('window_passed', view['record']['unsupported'])
        self.assertEqual(view['dates'], [])        # no ordinary-birthday date and no invented Medigap window
        self.assertIn('window_passed', view['route']['statement_ids'])
        self.assertIn('January 1 through March 31', view['route']['text'])
        self.assertIn('Next: confirm your sign-up timing with Social Security', view['line']['text'])
        self.assertNotIn('penalty of', json.dumps(view))

    def test_09c_disability_is_not_forced_into_the_turning_65_calculation(self):
        self.put('situation.age65', {'month': 11, 'year': 2026, 'first_day': False})
        self.put('coverage.current', ['none'])
        self.fact('RC04', choice='neither')
        self.fact('RC06', choice='disability')
        view = self.seen()
        self.assertIn('not_age_based', view['record']['unsupported'])
        self.assertEqual(view['dates'], [])
        self.assertIn('not_age_based', view['route']['statement_ids'])

    # 10. A changed Part B date ----------------------------------------------------
    def test_10_a_corrected_part_b_date_recomputes_only_what_depends_on_it(self):
        self.person()
        self.say('Part B starts December 1.')
        rows = {row['label']: row for row in self.seen()['dates']}
        self.assertEqual((rows['Part B start']['value'], rows['Part B start']['basis']), ('December 1, 2026', 'reported'))
        self.assertEqual(rows['Medigap window']['value'], 'December 2026 through May 2027')
        part_a = copy.deepcopy(self.seen()['record']['parts']['A'])
        coverage, birthday = self.flow.value(self.g, 'coverage.current'), self.flow.value(self.g, 'situation.age65')
        self.say('Actually, Part B starts January 1.')
        rows = {row['label']: row for row in self.seen()['dates']}
        self.assertEqual(rows['Part B start']['value'], 'January 1, 2027')
        self.assertEqual((rows['Medigap window']['value'], rows['Medigap window']['basis']),
                         ('January 2027 through June 2027', 'reported'))
        self.assertEqual(self.seen()['record']['parts']['A'], part_a)
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), coverage)
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), birthday)

    # 11. More information, denial, conflicting dates --------------------------------
    def test_11_problems_stay_visible_with_no_success_badge(self):
        self.person()
        self.say('I applied on November 5.')
        out = self.say('They need more information.')
        self.assertEqual(out['enrollment']['line']['text'], 'Part A: Social Security asked for more · Part B: Social Security '
                         'asked for more. Next: answer Social Security’s request.')
        self.assertEqual(out['enrollment']['dashboard']['paths']['original']['steps'][0]['state'], 'open')
        denied = self.say('Social Security denied my application.')
        self.assertEqual(denied['enrollment']['line']['text'], 'Part A: denied (you told me) · Part B: denied (you told me). '
                         'Next: ask Social Security about the denial at 1-800-772-1213.')
        self.assertNotIn('active', [part['state'] for part in denied['enrollment']['record']['parts'].values()])

    def test_11b_an_active_report_with_a_future_start_is_a_conflict(self):
        self.put('situation.age65', {'month': 11, 'year': 2026, 'first_day': False})
        self.put('coverage.current', ['cobra'])
        self.fact('RC04', choice='a_only')
        self.put('enrollment.partB', {'status': 'active', 'date': '2027-03-01', 'date_kind': 'start'})
        view = self.seen()
        self.assertIn('Part B: start date to confirm', view['line']['text'])
        self.assertEqual(view['line']['next']['id'], 'confirm_start_date')
        self.assertNotEqual(view['dashboard']['paths']['original']['steps'][0]['state'], 'done')

    # 12. Asks for 2027 coverage -----------------------------------------------------
    def test_12_a_2027_request_keeps_its_year_and_gets_no_2026_prices(self):
        self.person()
        self.fact('RC03', year=2027)
        profile = part_d_profile.profile(self.g, self.r)
        self.assertNotEqual(profile['status'], 'ready')       # never 2026 plans shown as 2027
        self.assertEqual(self.flow.report(self.r, 'RC03').get('year'), 2027)
        view = self.seen()
        self.assertNotIn('$', json.dumps(view['line']) + json.dumps(view['dashboard']) + json.dumps(view['dates']))
        self.assertEqual(view['line']['text'], PP16_LINE)       # Parts A and B guidance does not depend on the plan year

    # 13. Unsupported Medigap ZIP: no steering ------------------------------------------
    def test_13_missing_medigap_prices_never_steer_toward_medicare_advantage(self):
        self.put('subject.role', 'self')
        self.put('comparison.scope.zip', '34120')               # outside the priced ZIPs
        self.put('needs.costPreference', 'predictable')
        self.put('coverage.current', ['none'])
        self.put('situation.age65', {'month': 11, 'year': 2026, 'first_day': False})
        self.fact('RC04', choice='neither')
        card = ux_flow.two_paths(self.flow, self.owner, self.g, self.r)
        self.assertEqual([path['id'] for path in card['paths']], ['original_medigap', 'medicare_advantage'])
        self.assertEqual(card['lean']['path'], 'original_medigap')         # the person's own preference, unchanged
        self.assertEqual([choice['label'] for choice in card['choices']],
                         ['Parts A and B only', 'Keep my current coverage', 'Wait for now'])
        self.assertEqual(card['paths'][0]['name'], 'Original Medicare')
        self.assertEqual(self.seen()['line']['text'], PP16_LINE)             # the next step survives missing prices

    # 14. A helper, and a reload ---------------------------------------------------------
    def test_14_helper_reports_are_about_the_beneficiary_and_a_reload_rebuilds_the_view(self):
        self.person(role='someone')
        self.say('I applied last week.')                     # the helper's own application is not hers
        self.assertIsNone(self.flow.value(self.g, 'enrollment.partB'))
        out = self.say('She applied last week.')
        self.assertEqual(self.flow.value(self.g, 'enrollment.partB')['status'], 'applied')
        # A reload or a saved-progress return has only the reports. The view is rebuilt from them.
        g, r = self.flow.validate(copy.deepcopy(self.g), copy.deepcopy(self.r))
        self.assertEqual(enrollment_flow.view(self.flow, g, r), out['enrollment'])
        self.assertEqual(self.flow.response(g, r)['enrollment']['line'], out['enrollment']['line'])

    def test_14b_someone_asking_for_themselves_is_not_given_another_persons_report(self):
        self.person()
        self.say('She applied last week.')
        self.assertIsNone(self.flow.value(self.g, 'enrollment.partB'))


class Capture(Journey):
    """Build items 3 and 4: finishes and status updates from the conversation."""

    def test_the_four_example_updates_change_the_status_line(self):
        self.person()
        applied = self.say('I applied')
        self.assertEqual(applied['enrollment']['line']['text'], 'Part A: applied, waiting to hear · Part B: applied, waiting to '
                         'hear. Next: wait for Social Security’s decision letter.')
        self.assertEqual(self.flow.value(self.g, 'enrollment.partA'), {'status': 'applied', 'date': None, 'date_kind': 'application'})
        self.assertEqual(self.g['fields']['enrollment.partA']['source'], 'user_text')
        have = self.say('I have Part A now')
        self.assertIn('Part A: active · Part B: applied, waiting to hear.', have['enrollment']['line']['text'])
        more = self.say('they need more information')
        self.assertIn('Part B: Social Security asked for more', more['enrollment']['line']['text'])
        self.assertIn('Part A: active', more['enrollment']['line']['text'])       # the request is about what is pending
        starts = self.say('Part B starts December 1')
        self.assertEqual(self.flow.value(self.g, 'enrollment.partB'), {'status': 'approved', 'date': '2026-12-01', 'date_kind': 'start'})
        self.assertIn('Part B: starts December 1, 2026 (you told me)', starts['enrollment']['line']['text'])
        self.assert_dates_labelled(starts['enrollment']['line']['text'])

    def test_saying_you_applied_also_answers_which_parts_you_have(self):
        # Owner's test conversation, November 13, 2026: after "I just called and finished my
        # application" Daylight still asked "Which Medicare parts do you have now?".
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        text = 'I turn 65 on November 8 2026'
        self.say(text, situation_proposals=[self.situation('age65', text, month=11, year=2026)])
        self.assertFalse(self.flow.report(self.r, 'RC04'))
        out = self.say('Okay I just called and finished my application with Social Security. What now?')
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'pending')
        self.assertTrue(out['enrollment']['line']['text'].startswith('Part A: applied, waiting to hear · Part B: applied, waiting to hear.'),
                        out['enrollment']['line']['text'])
        self.assertNotEqual(((out.get('assessment') or {}).get('nextQuestion') or {}).get('id'), 'RC04')
        later = self.pick('RC09', choice='my_job')        # the question he was asked next; RC04 never follows it
        self.assertNotEqual(((later.get('assessment') or {}).get('nextQuestion') or {}).get('id'), 'RC04')

    def test_a_stated_answer_about_parts_is_never_replaced_by_a_report(self):
        self.person(parts='a_only')
        self.say('I applied for Part B yesterday.')
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')
        self.assertIsNone(enrollment_flow.parts_answer(self.flow, self.g, self.r, 'I applied for Part B yesterday.', []))
        self.assertIsNone(enrollment_flow.parts_answer(self.flow, self.g, self.r, 'Did you say I applied?', []))

    def test_replies_and_the_model_name_the_tab_the_person_can_see(self):
        said = 'The Medicare Supplement (Medigap) tab on the Plans page now lists premiums for your details.'
        self.assertEqual(enrollment_flow.tab_names(said), 'The Plans page now lists premiums for your details.')   # no tab or step by name (November 13, 2026)
        self.assertEqual(enrollment_flow.tab_names('Open the Medicare Advantage tab.'), 'Open the Medicare Advantage tab.')
        pages = enrollment_flow.plans_pages(self.flow.plans_pages(self.g, self.r))
        self.assertEqual(pages['medigap']['tab'], 'the Plans page')
        self.assertEqual(pages['part_d']['tab'], 'the Plans page')
        self.assertEqual(self.flow.plans_pages(self.g, self.r)['medigap']['tab'], 'Medicare Supplement (Medigap)')   # the shared page is untouched

    def test_coverage_that_ended_is_not_a_decision_to_keep_it(self):
        # Live run of profile PP03, November 13, 2026: step 3 read "Coverage you already have".
        said = 'About 450 employees, regular employee plan, ended October 31. I have the letter saying my drug coverage counted. No Part B yet, no HSA, no COBRA.'
        self.assertEqual(enrollment_flow.choices_from_text(said)['components'], {})
        self.assertEqual(enrollment_flow.choices_from_text('My drug coverage from work ended in October.')['components'], {})
        self.assertEqual(enrollment_flow.choices_from_text('I already have drug coverage through the VA.')['components'], {'part_d': 'keep_existing'})
        self.assertEqual(enrollment_flow.choices_from_text('I have a Medigap policy already.')['components'], {'medigap': 'keep_existing'})
        self.assertEqual(enrollment_flow.choices_from_text('I am keeping my drug plan.')['components'], {'part_d': 'keep_existing'})

    def test_questions_plans_and_other_products_are_not_reports(self):
        self.person()
        for words in ('How do I sign up?', 'I need to sign up soon.', "I haven't applied yet.", 'I applied for a job last week.',
                      'I signed up for a Medicare Advantage plan.', 'If I sign up now Part B starts December 1.',
                      'When does Part B start?'):
            self.say(words)
            self.assertIsNone(self.flow.value(self.g, 'enrollment.partA'), words)
            self.assertIsNone(self.flow.value(self.g, 'enrollment.partB'), words)

    def test_updates_work_on_a_saved_progress_return(self):
        self.person()
        self.say('I applied on November 5.')
        # What saved progress holds: the validated reports. A new visit starts from them.
        g, r = self.flow.validate(copy.deepcopy(self.g), copy.deepcopy(self.r))
        self.assertEqual(g['fields']['enrollment.partB']['value'],
                         {'status': 'applied', 'date': '2026-11-05', 'date_kind': 'application'})
        before = enrollment_flow.view(self.flow, g, r)['line']['text']
        self.assertIn('applied, waiting to hear', before)
        self.assertNotIn('November 5', before)        # an application date is never shown as a start or a deadline
        enrollment_flow.capture(self.flow, g, r, 'Part B starts December 1 and Part A started November 1.')
        after = enrollment_flow.view(self.flow, g, r)['line']['text']
        self.assertEqual(after, 'Part A: active since November 1, 2026 (you told me) · Part B: starts December 1, 2026 '
                                '(you told me). Next: check that your Medicare card or letter shows the start date of December 1, 2026.')

    def test_parts_a_and_b_only_is_a_recorded_finish_with_its_own_summary(self):
        self.person()
        out = self.say('I want Parts A and B only.')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_only')
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'medigap': 'not_needed', 'part_d': 'not_needed'})
        summary = self.cards(out, 'finish_summary')[0]
        self.assertEqual(summary['title'], 'Your plan: Parts A and B only')
        rows = {row['label']: row['value'] for row in summary['rows']}
        self.assertEqual(rows['Your share of medical costs'], 'No Medigap policy')
        self.assertEqual(rows['Prescriptions'], 'No Part D plan')
        self.assertTrue(rows['Next'].startswith('Sign up through Social Security by February 28, 2027'))
        self.assertEqual(summary['statement_ids'], ['no_limit', 'part_d_penalty'])      # accepted wording only
        self.assertIn('Your plan: Parts A and B only.', out['enrollment']['line']['text'])
        self.assertFalse(self.cards(self.say('ok'), 'finish_summary'))                # once
        # The record marks the finish complete once Parts A and B are applied for.
        applied = self.say('I applied.')
        self.assertEqual(applied['enrollment']['record']['finish'], 'ab_only')
        self.assertEqual(len(self.cards(applied, 'finish_summary')), 1)                # updated summary
        self.assertEqual(self.seen()['before']['applies'], False)

    def test_keep_current_and_wait_finish_the_same_way(self):
        self.person()
        keep = self.say('I want to keep my current coverage.')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'keep_current')
        self.assertEqual(self.cards(keep, 'finish_summary')[0]['title'], 'Your plan: keep your current coverage')
        self.assertEqual(keep['enrollment']['record']['finish'], 'keep_current')
        self.assertIn('Your plan: keep your current coverage.', keep['enrollment']['line']['text'])
        wait = self.say('I’ll wait for now.')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'wait')
        self.assertEqual(self.cards(wait, 'finish_summary')[0]['title'], 'Your plan: wait for now')
        text = wait['enrollment']['line']['text']
        self.assertIn('Your sign-up window runs through February 28, 2027 (from your birthday month).', text)
        self.assert_dates_labelled(text)

    def test_original_medigap_never_means_must_buy_medigap(self):
        self.person()
        self.say('I’ll go with Original Medicare.')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_medigap')
        self.assertIsNone(self.flow.value(self.g, 'intent.components'))                 # no invented Medigap choice
        self.say('I don’t need a Medigap policy.')
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'medigap': 'not_needed'})
        self.say('I’ll keep my drug coverage from the VA.')
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'medigap': 'not_needed', 'part_d': 'keep_existing'})
        self.assertEqual(self.seen()['line']['plan'], 'original_plus')

    def test_the_model_is_told_states_and_never_a_date(self):
        self.person()
        self.say('Part B starts December 1.')
        self.say('ok')
        told = self.composed_context()['conversation_state']['enrollment']
        self.assertEqual(told['parts'], {'A': 'needed', 'B': 'approved_future'})
        self.assertFalse(ISO.search(json.dumps(told)) or LONG_DATE.search(json.dumps(told)))
        self.assertTrue(any('Never ask for a Social Security number' in rule for rule in told['rules']))


class Decisions(Journey):
    """Build item 5: tapped decisions. No model call; a tab never records one."""

    def test_a_decision_is_recorded_without_a_model_call(self):
        self.person()
        calls = len(self.calls)
        out = self.decide(component='medigap', value='not_needed')
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'medigap': 'not_needed'})
        self.assertEqual(self.g['fields']['intent.components']['source'], 'user_choice')
        self.assertEqual(out['enrollment']['dashboard']['paths']['original']['steps'][1]['state'], 'not_needed')
        out = self.decide(component='part_d', value='decide_later')
        self.assertEqual(out['enrollment']['dashboard']['paths']['original']['steps'][2]['text'], 'Decide later')
        self.assertIsNone(out['enrollment']['line']['plan'])             # decide later is not a finish
        out = self.decide(path='original_only')
        self.assertEqual(self.flow.value(self.g, 'intent.components'), {'medigap': 'not_needed', 'part_d': 'not_needed'})
        self.assertEqual(out['enrollment']['line']['plan'], 'ab_only')
        out = self.decide(component='medigap', value='chosen')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_medigap')   # no longer "only"
        self.assertEqual(self.say('ok')['enrollment']['dashboard']['paths']['original']['steps'][1]['state'], 'chosen')

    def test_only_listed_decisions_are_accepted(self):
        self.person()
        for bad in ({'component': 'medigap', 'value': 'buy'}, {'component': 'dental', 'value': 'chosen'},
                    {'path': 'best'}, {'path': 'wait', 'value': 'chosen'}, {'component': 'medigap', 'value': 'chosen', 'plan': 'G'}):
            with self.assertRaises(ProfileError, msg=str(bad)):
                self.decide(**bad)
        self.assertIsNone(self.flow.value(self.g, 'intent.components'))

    def test_every_view_keeps_estimates_and_reports_apart(self):
        self.person()
        for words in ('ok', 'I applied on November 5.', 'Part B starts December 1.', 'I have Part A now.'):
            view = self.say(words)['enrollment']
            self.assert_dates_labelled(view['line']['text'])
            for row in view['dates']:
                self.assertIn(row['basis'], ('estimated', 'reported'))
                self.assertTrue(row['note'])


class AfterTheFirstLiveLook(Journey):
    """The design approved November 13, 2026: ask about the call, show both paths
    before narrowing, and give the person their own lines for the call. Every tap
    is the person's answer and needs no model call."""

    def working(self):
        """The owner's test person: coverage through his own current job, 65 this season."""
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        text = 'I turn 65 on November 8 2026'
        return self.say(text, situation_proposals=[self.situation('age65', text, month=11, year=2026)])

    def test_the_card_asks_where_the_person_is_with_social_security(self):
        view = self.working()['enrollment']
        self.assertEqual(view['call']['question'], 'Where are you with Social Security?')
        self.assertEqual([choice['label'] for choice in view['call']['choices']],
                         ['I plan to call', 'I already called', 'Not what I need right now'])
        calls = len(self.calls)
        planned = self.decide(contact='planned')['enrollment']['call']
        self.assertEqual((planned['stage'], planned['choices'][0]['label']), ('planned', 'I already called'))
        self.assertIn('call guide is open', planned['line'])
        called = self.decide(contact='called')['enrollment']['call']
        self.assertEqual(called['question'], 'What happened on the call?')
        self.assertEqual([choice['label'] for choice in called['choices']],
                         ['I applied', 'They gave me start dates', 'They need more from me', 'I only asked questions'])
        asked = self.decide(report='asked')['enrollment']
        self.assertIn('Tell me anything they said about dates', asked['call']['line'])
        self.assertEqual(asked['line']['parts'][0]['state'], 'unknown')          # nothing about the parts changed
        self.assertEqual(len(self.calls), calls)                                 # no model call for any tap
        self.assertEqual(self.g['fields']['enrollment.contact']['source'], 'user_choice')

    def test_i_applied_is_recorded_from_the_tap_and_answers_which_parts(self):
        self.working()
        self.decide(contact='called')
        out = self.decide(report='applied')
        view = out['enrollment']
        self.assertTrue(view['line']['text'].startswith('Part A: applied, waiting to hear · Part B: applied, waiting to hear.'))
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'pending')
        self.assertEqual(view['call']['stage'], 'applied')
        self.assertIn('keep comparing plans', view['call']['line'])
        self.assertEqual(len(view['call']['after']), 4)
        self.assertEqual([choice['label'] for choice in view['call']['choices']], ['They gave me start dates', 'They need more from me'])
        if view['record']['version'] != 'enrollment-journey-v1':
            # Record v2 (Codex): a report outranks the held situation.
            self.assertIn('wait for Social Security’s decision letter', view['line']['text'])
            self.assertEqual(view['record']['route'], 'none_needed')
        self.assertNotIn('approved', json.dumps(view['line']))                   # never said to be approved or in effect

    def test_start_dates_are_the_persons_and_say_so(self):
        self.working()
        out = self.decide(starts={'A': '2026-11-01', 'B': '2026-12-01'})
        line = out['enrollment']['line']['text']
        self.assertIn('Part B: starts December 1, 2026 (you told me)', line)
        self.assert_dates_labelled(line)
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')
        self.assertEqual(out['enrollment']['call']['stage'], 'dates')
        for bad in ({'starts': {'B': 'next month'}}, {'starts': {}}, {'starts': {'C': '2026-12-01'}}, {'starts': {'B': '1900-01-01'}},
                    {'contact': 'emailed'}, {'report': 'approved'}, {'start_with': 'best'}, {'contact': 'called', 'report': 'applied'}):
            with self.assertRaises(ProfileError, msg=str(bad)):
                self.decide(**bad)

    def test_not_now_folds_the_card_and_is_not_raised_again(self):
        self.working()
        self.assertEqual(self.decide(contact='not_now')['enrollment']['call'], {'stage': 'not_now'})
        self.assertFalse(self.cards(self.say('ok'), 'signup_route'))

    def test_both_paths_are_shown_before_narrowing_and_a_tap_is_a_lean_not_a_choice(self):
        self.working()
        self.say('I hear Medicare Advantage might be a good option for me.')
        self.assertEqual(self.flow.value(self.g, 'intent.pathAsked'), 'medicare_advantage')
        card = enrollment_flow.trade_off_card(self.flow, self.g, 'predictable')
        self.assertEqual([column['title'] for column in card['columns']], ['Original Medicare with Medigap', 'Medicare Advantage'])
        self.assertEqual(card['question'], 'Both paths are on the card. Start with Medigap prices, and keep Medicare Advantage open to compare?')
        self.assertEqual(card['note'], 'You asked about Medicare Advantage first, so it stays open.')
        self.assertEqual([choice['label'] for choice in card['choices']], ['Start with Medigap', 'Start with Medicare Advantage', 'Show me both'])
        accepted = enrollment_flow.content()['statements']
        for identifier in card['statement_ids']:
            self.assertEqual(accepted[identifier]['state'], 'accepted', identifier)      # no new Medicare claim
        self.assertTrue(all(len(column['lines']) == 4 for column in card['columns']))    # each side is stated; neither is shortchanged
        self.assertNotIn('better', card['text'].casefold())
        self.assertNotIn('recommend', card['text'].casefold())
        calls = len(self.calls)
        self.decide(start_with='medicare_advantage')
        lean = ux_flow.path(self.flow, 'owner', self.g, self.r)
        self.assertEqual((lean['state'], lean['path']), ('leaning', 'medicare_advantage'))
        self.assertIsNone(self.flow.value(self.g, 'intent.coveragePath'))                # nothing is chosen
        self.decide(start_with='both')
        self.assertEqual(ux_flow.path(self.flow, 'owner', self.g, self.r)['state'], 'undecided')
        self.assertEqual(len(self.calls), calls)
        mirror = enrollment_flow.trade_off_card(self.flow, self.g, 'lower_monthly')
        self.assertEqual(mirror['choices'][0]['label'], 'Start with Medicare Advantage')
        self.assertEqual(mirror['note'], '')

    def test_for_your_call_uses_only_what_the_person_reported(self):
        self.assertIsNone(self.seen()['notes'])                                  # nothing reported, nothing shown
        self.working()
        self.pick('RC09', choice='my_job')
        notes = self.seen()['notes']
        self.assertEqual(notes['title'], 'For your call')
        self.assertEqual(notes['say'], ['“I turned 65 in November 2026.”', '“I have health coverage through my current job.”'])
        self.assertEqual(notes['ask'], ['“When should I sign up for Part B so it starts when my job coverage ends?”',
                                        '“Do I need my employer to fill in form CMS-L564?”'])
        self.assertEqual(len(notes['know']), 2)
        self.assertNotIn('Social Security number', json.dumps(notes))
        # With the record's reported end of job coverage (v2), the person's own date is added, as theirs.
        record = {**self.seen()['record'], 'coverage_end': {'date': '2026-12-31', 'precision': 'month', 'basis': 'reported', 'source': 'S_RETIREMENT'}}
        said = enrollment_flow.call_notes(self.flow, self.g, self.r, record)['say'][1]
        self.assertEqual(said, '“I have health coverage through my current job. I plan to retire at the end of December 2026.”')
        self.decide(report='applied')
        after = self.seen()['notes']
        self.assertEqual(after['ask'], [])                                       # no application date was given, so none is invented

    def test_retiring_at_the_end_of_the_year_is_kept_as_the_month_it_means(self):
        # Owner's test: "retiring at EOY" was said twice and nothing usable was kept.
        self.working()
        self.put('situation.retirement', {'status': 'retiring', 'when': 'at EOY'})
        self.assertTrue(enrollment_flow.note_retirement(self.flow, self.g, 'I am retiring at EOY.', TODAY))
        self.assertEqual(self.flow.value(self.g, 'situation.retirement'), {'status': 'retiring', 'when': 'December %d' % TODAY.year})
        end = self.seen()['record'].get('coverage_end')
        if self.seen()['record']['version'] != 'enrollment-journey-v1':
            self.assertEqual((end['date'], end['precision'], end['basis'], end['source']),
                             ('%d-12-31' % TODAY.year, 'month', 'reported', 'S_RETIREMENT'))
            self.assertIn('I plan to retire at the end of December %d.' % TODAY.year, self.seen()['notes']['say'][1])
        # A month the person gave is theirs and is never replaced; someone already retired is left alone.
        self.put('situation.retirement', {'status': 'retiring', 'when': 'March 2027'})
        self.assertFalse(enrollment_flow.note_retirement(self.flow, self.g, 'I am retiring at the end of the year.', TODAY))
        self.put('situation.retirement', {'status': 'retired', 'when': ''})
        self.assertFalse(enrollment_flow.note_retirement(self.flow, self.g, 'I retired at the end of the year.', TODAY))

    def test_the_two_path_card_says_what_is_left_in_general_until_medigap_comes_up(self):
        self.working()
        self.assertTrue(ux_flow.two_paths(self.flow, 'owner', self.g, self.r)['paths'][0]['general_left'])
        self.assertRegex(self.say('ok')['whatsLeft']['text'], r'^\d details? left to see plans and prices$')
        self.say('What about Medigap?')
        self.assertFalse(ux_flow.two_paths(self.flow, 'owner', self.g, self.r)['paths'][0]['general_left'])


class NotReleased(Journey):
    """The participant interface (:8893/:8894) is unchanged until the owner releases this."""
    enable = False

    def test_nothing_shows_or_records_where_the_journey_is_not_enabled(self):
        out = self.person()
        self.assertNotIn('enrollment', out)
        said = self.say('I applied. I want Parts A and B only.')
        self.assertNotIn('enrollment', said)
        self.assertFalse(self.cards(said, 'signup_route') or self.cards(said, 'finish_summary'))
        self.assertNotIn('enrollment.partA', self.g['fields'])
        self.assertNotIn('intent.components', self.g['fields'])
        with self.assertRaises(ProfileError):
            self.decide(component='medigap', value='not_needed')
        card = ux_flow.two_paths(self.flow, self.owner, self.g, self.r)
        self.assertNotIn('choices', card)
        self.assertEqual(card['paths'][0]['name'], 'Original Medicare + Medigap + Part D')


class Content(unittest.TestCase):
    """Every sentence a person can see has a source and a sign-off state."""

    def test_statements_and_guides_are_sourced_and_ask_for_no_identifier(self):
        content = enrollment_flow.content()
        self.assertEqual(content['review_state'], 'awaiting_owner_sign_off')
        self.assertRegex(content['last_checked'], r'^2026-\d{2}-\d{2}$')
        items = [(key, value) for key, value in content['statements'].items()]
        items += [(key, value) for key, value in content['after'].items()]
        for guide in content['guides']:
            self.assertIn(guide['official'], content['sources'])
            self.assertTrue(guide['ready'] and guide['steps'] and guide['after'])
            for section in ('lead', 'ready', 'steps', 'write_down'):
                items += [(item['id'], item) for item in guide.get(section, [])]
            for key in guide['after']:
                self.assertIn(key, content['after'])
        self.assertEqual({guide['id'] for guide in content['guides']}, {'online_ab', 'add_part_b', 'phone'})
        for key, item in items:
            if item.get('kind') != 'tip':
                self.assertTrue(item['sources'], key)
            for source in item['sources']:
                self.assertTrue(content['sources'][source]['url'].startswith('https://'), key)
            # Daylight never asks for an identifier; guides say to give it to Social Security only.
            self.assertNotRegex(item['text'], r'(?i)\b(?:enter|type|tell me|give me|share)\b[^.]*\b(?:social security number|medicare number|password)\b[^.]*\bhere\b(?<!never here)', key)
        for key, item in content['statements'].items():
            self.assertIn(item['state'], ('new', 'accepted'), key)
            if item['state'] == 'accepted':
                self.assertTrue(item['origin'], key)


if __name__ == '__main__':
    unittest.main()
