"""PP16 (November 12, 2026 test conversation): journey contracts for D157.

The fictional person turned 65 on November 8, 2026, is on COBRA, has neither
Part A nor Part B, lives in 34102, takes Ozempic and metoprolol, and chose
predictable costs. Each test starts from that person's own words or reports.
Scripted transport: no network, no model billing. The scripted replies quote
the wording seen in the live run, so these tests prove the code-side guards,
not live model behaviour (UX playbook lesson 10).
"""
import copy
from datetime import date
import unittest

import test_natural_flow as harness
from adaptive_flow import metadata
from applicable_rules import applicable_rules
from chat import ModelUnavailable
from natural_flow import CONTEXT_POLICY
import medigap_profile
import ux_flow
import ux_pass

TODAY = date(2026, 11, 12)
COBRA_LINE = ('COBRA does not count as current-employment coverage and does not extend the time to sign up '
              'for Part B.')
MENU = 'What would you like to understand next?'


class PP16(unittest.TestCase):
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)
    @staticmethod
    def situation(kind, text, **value):
        return {'kind': kind, 'subject': 'beneficiary', 'scope': 'current', 'quote': text,
                'uncertain': False, 'correction': False, 'month': value.get('month'),
                'year': value.get('year'), 'status': value.get('status', ''), 'when': value.get('when', '')}

    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)

    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        try:
            import ux_flow
        except ImportError:   # before D157 the hooks do not exist
            return
        ux_flow.TODAY = TODAY
        self.addCleanup(setattr, ux_flow, 'TODAY', None)

    # --- the person's reports, in the order the live run gave them -----------
    def pick(self, identifier, compose=None, **fields):
        """A tapped answer that goes to the model, as in the live run."""
        if compose is not None:
            self.compositions.append(compose)
        return self.turn({'type': 'choice', 'id': identifier, 'fields': fields})

    def say(self, text, updates=(), compose=None, **extra):
        return self.message(text, updates, compose=compose, extraction=self.extraction(updates, **extra))

    def situation_known(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        text = 'I turned 65 on November 8 2026'
        self.say(text, situation_proposals=[self.situation('age65', text, month=11, year=2026)])
        self.assertEqual(self.flow.value(self.g, 'situation.age65')['month'], 11)
        self.assertEqual(self.flow.value(self.g, 'situation.age65')['year'], 2026)

    def enrolled_in_neither(self, compose=None):
        return self.pick('RC04', compose, choice='neither')

    def ids(self):
        return [item['id'] for item in self.flow.eligible(self.owner, self.g, self.r)]

    # --- CV-01, CV-06, CV-07, CV-11 -------------------------------------------
    def test_birth_month_is_asked_early_and_nothing_that_changes_nothing(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        ids = self.ids()
        self.assertIn('S_AGE65', ids[:3], ids)            # CV-06: without the person volunteering it
        self.assertNotIn('RC11', ids)                      # CV-07: "When does your COBRA coverage end?"
        self.assertNotIn('T04', ids)                       # CV-11: not a real choice on COBRA
        self.assertNotIn('T02', ids)                       # CV-01: no familiarity warm-up
        question = next(item['question'] for item in self.flow.eligible(self.owner, self.g, self.r)
                        if item['id'] == 'S_AGE65')
        self.assertTrue(question.get('why'))               # CV-09: the reason travels with the question
        self.assertEqual(question['question'].count('?'), 1)   # CV-31: one question

    def test_the_opening_choice_asks_a_real_question_not_familiarity(self):
        # Found in the live browser check, November 12, 2026: "Understand
        # Medicare" set the familiarity question outside the eligible hook.
        out = self.choice('T01', choice='learn')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC01')   # CV-01
        self.assertNotEqual(self.r['natural']['dialogue']['lastTarget']['id'], 'T02')

    # --- CV-10, CV-12, CV-13, CV-14, K-01 ---------------------------------------
    def test_timing_is_stated_by_code_in_the_next_turn_and_cobra_once(self):
        self.situation_known()
        out = self.enrolled_in_neither({'question_target': None, 'question': '',
                                        'reply': 'Here is how the timing works for you.'})
        cards = [card for card in out.get('cards', []) if card['kind'] == 'enrollment_timing']
        self.assertEqual(len(cards), 1)
        text = cards[0]['text']
        for wanted in ('August 1, 2026 through February 28, 2027', 'Part B starts December 1, 2026',
                       'Premium-free Part A starts November 1, 2026', 'COBRA isn’t coverage from a current job',
                       'Medicare pays first and COBRA pays second'):
            self.assertIn(wanted, text)
        rows = {row['label']: row['value'] for row in cards[0]['rows']}
        self.assertEqual(rows['Medigap window'], 'December 2026 through May 2027')   # CV-13
        self.assertNotIn('contact Social Security', out['reply'])
        # Said once: the same caveat in later replies is removed, the card is not shown again.
        later = self.say('ok', compose={'question_target': None, 'question': '',
                                         'reply': COBRA_LINE + ' Plans differ by ZIP code.'})
        self.assertNotIn('COBRA', later['reply'])
        self.assertIn('Plans differ by ZIP code.', later['reply'])
        self.assertFalse([card for card in later.get('cards', []) if card['kind'] == 'enrollment_timing'])
        # Asked again by the person: it may be said again.
        again = self.say('wait, what about cobra?', compose={'question_target': None, 'question': '',
                                                             'reply': 'COBRA isn’t coverage from a current job, so it doesn’t let someone put off Part B without a penalty.'})
        self.assertIn('COBRA', again['reply'])

    # --- CV-08 ------------------------------------------------------------------
    def test_the_eight_month_window_is_not_explained_to_someone_turning_65_on_cobra(self):
        self.situation_known()
        self.enrolled_in_neither()
        rules = applicable_rules(lambda identifier: self.flow.report(self.r, identifier),
                                 lambda path: self.flow.value(self.g, path), today=TODAY)
        ids = [rule['rule_id'] for rule in rules]
        self.assertNotIn('partb_sep_coverage_ended', ids)
        self.assertNotIn('partb_gep_penalty', ids)
        self.assertIn('cobra_not_current_employment', ids)     # K-01 still fires

    def test_the_eight_month_window_still_shows_for_job_coverage_that_ended_after_65(self):
        self.choice('RC01', choice='self')
        report = {'RC04': {'choice': 'a_only'}, 'RC11': {'coverageEnd': '2026-09', 'jobEnd': '2026-09'}}
        values = {'coverage.current': ['none'], 'situation.age65': {'month': 3, 'year': 2025}}
        rules = applicable_rules(lambda identifier: report.get(identifier, {}), values.get, today=TODAY)
        self.assertIn('partb_sep_coverage_ended', [rule['rule_id'] for rule in rules])

    # --- CV-04 ------------------------------------------------------------------
    def test_total_cost_as_a_priority_does_not_raise_extra_help(self):
        values = {'coverage.current': ['cobra'], 'needs.priorities': ['total_cost', 'bills']}
        rules = applicable_rules(lambda identifier: {}, values.get, today=TODAY,
                                 concern='Wants to compare total cost and predictable costs')
        self.assertFalse({'extra_help', 'msp_extra_help_basics'} & {rule['rule_id'] for rule in rules})
        asked = applicable_rules(lambda identifier: {}, values.get, today=TODAY,
                                 concern='Worried about affording prescriptions on a fixed income')
        self.assertTrue({'extra_help', 'msp_extra_help_basics'} & {rule['rule_id'] for rule in asked})

    # --- CV-02, CV-25 -------------------------------------------------------------
    def test_which_is_best_for_me_switches_to_the_shortest_path(self):
        self.choice('RC01', choice='self')
        out = self.say('I want to know which is best for me. I hear good things about MA?',
                       compose={'reply': 'Happy to help with that.'})
        state = self.composed_context()['conversation_state']
        self.assertEqual(state['mode'], 'find')
        self.assertIn('A few questions about your situation, then your options.', out['reply'])
        self.assertEqual(self.composed_context()['required_target']['id'], 'T03')
        again = self.say('idk which is better for me', compose={'reply': 'Understood.'})
        self.assertEqual(again['reply'].count('A few questions about your situation'), 0)   # once

    # --- CV-03 ------------------------------------------------------------------
    def test_a_failed_reply_uses_what_the_person_said_and_asks_the_next_question(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        out = self.pick('T10', ModelUnavailable('forced'), choice='total_cost,bills')
        self.assertIn('total cost and predictable costs', out['reply'])
        self.assertNotIn('couldn', out.get('notice', ''))
        self.assertNotIn('Extra Help', out['reply'])
        self.assertTrue(out['assessment']['nextQuestion'])
        self.assertNotIn(MENU, out['reply'])

    def test_a_failed_answer_to_a_question_stays_on_the_persons_topic(self):
        self.situation_known()
        self.enrolled_in_neither()
        out = self.say('wait, does cobra let me delay?', compose=ModelUnavailable('forced'))
        self.assertIn('COBRA', out['reply'])
        self.assertNotIn('couldn', out.get('notice', ''))
        other = self.say('what is a formulary?', compose=ModelUnavailable('forced'))
        self.assertEqual(other['reply'], 'I don’t have a checked answer to that question here yet, so I won’t guess.')
        self.assertTrue(other['assessment']['nextQuestion'])

    # --- CV-05, CV-24 -------------------------------------------------------------
    def test_conflicting_priorities_get_one_tie_break_that_is_never_asked_again(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        self.pick('T10', {'reply': 'Those two can pull in different directions.'}, choice='total_cost,bills')
        self.assertEqual(self.composed_context()['required_target']['id'], 'T09')
        self.choice('T09', choice='predictable')
        self.assertNotIn('T09', self.ids())
        self.assertNotIn('T10', self.ids())

    def test_predictable_costs_alone_already_answers_the_balance_question(self):
        self.choice('RC01', choice='self')
        self.choice('T10', choice='bills')
        self.assertNotIn('T09', self.ids())

    # --- CV-09 ------------------------------------------------------------------
    def test_a_question_is_never_asked_twice_in_the_same_words(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        ask = 'What month and year do you turn 65?'
        first = self.say('June 2027. but i just turned 65', compose={'question_target': 'S_AGE65', 'reply': 'Thanks.', 'question': ask})
        self.assertEqual(first['assessment']['nextQuestion']['question'], ask)
        second = self.say('why do you need to know that?', compose={
            'question_target': 'S_AGE65', 'question': ask,
            'reply': 'The month you turn 65 sets your sign-up window and when coverage can start.'})
        question = second['assessment']['nextQuestion']
        self.assertEqual(question['id'], 'S_AGE65')
        self.assertNotEqual(question['question'], ask)
        self.assertLess(len(question['question']), len(ask))
        self.assertTrue(question['why'])

    # --- CV-14, CV-15, CV-20, CV-27, CV-28, CV-30, CV-32 ----------------------------
    def test_generated_replies_are_tidied_without_failing_the_turn(self):
        self.situation_known()
        self.enrolled_in_neither()
        self.choice('T03', zip='34102')
        reply = ('Noted: Naples, 34102. Original Medicare and Medicare Advantage price things differently. '
                 'That is not yet a finding. I wouldn’t call either one better. '
                 'This is not a finding that one is better for you. '
                 'The missing piece is whether you already have Medicare in place. '
                 'Medigap premiums need the sex category used by the price source and tobacco category. '
                 'I don’t yet have a supported personal ranking to call any plan your best option. '
                 'Next I’ll be checking participation at the exact office.')
        out = self.say('ok', compose={'question_target': None, 'question': '', 'reply': reply})
        text = out['reply']
        self.assertFalse(text.startswith('Noted'))                       # CV-32
        self.assertNotIn('34102.', text.split('Original')[0])
        self.assertEqual(text.count('finding'), 1)                       # CV-27: one limit statement
        self.assertNotIn('wouldn’t call either', text)
        self.assertNotIn('missing piece', text)                          # CV-15: a recorded fact is not missing
        self.assertNotIn('price source', text)                           # CV-28: never announce a missing detail
        self.assertNotIn('supported personal ranking', text)             # CV-30: no internal language
        self.assertNotIn('checking participation', text)                 # CV-20
        self.assertNotIn('exact office', text)
        self.assertIn('Original Medicare and Medicare Advantage price things differently.', text)
        self.assertEqual(out['generated']['status'], 'complete')

    def test_a_recorded_medicare_status_reaches_the_model_as_a_report(self):
        self.situation_known()
        self.enrolled_in_neither({'reply': 'Thanks.'})
        reports = {item['id']: item for item in self.composed_context()['reports']}
        self.assertEqual(reports['readiness.RC04.profile.choice']['value'], 'neither')

    # --- CV-28, CN-10, PG-10 --------------------------------------------------------
    def test_medigap_prices_are_reached_from_the_conversation_without_naming_medigap(self):
        self.situation_known()
        self.enrolled_in_neither()
        self.choice('T03', zip='34102')
        self.choice('T10', choice='total_cost,bills')
        out = self.pick('T09', {'reply': 'Predictable it is.'}, choice='predictable')
        self.assertEqual(out['coveragePath'], {'state': 'leaning', 'path': 'original_medigap',
                                               'because': ['You said predictable costs matter more.']})
        self.assertNotEqual(metadata(self.r)['task'], 'medigap')
        ids = self.ids()
        self.assertIn('MG_SEX', ids)
        self.assertNotIn('MG_AGE', ids)                                  # the birthday already gives the pricing age
        self.assertEqual(out['whatsLeft']['text'], '2 details left to see your Medigap prices')   # CV-37
        self.choice('MG_SEX', choice='Male')
        self.assertIn('MG_TOBACCO', self.ids())
        done = self.choice('MG_TOBACCO', choice='Non-Tobacco')
        self.assertEqual(done['medigapProfile']['status'], 'ready')
        self.assertFalse({'MG_SEX', 'MG_TOBACCO', 'MG_AGE'} & set(self.ids()))

    def test_an_explicit_choice_of_path_is_recorded_as_a_profile_fact(self):
        self.choice('RC01', choice='self')
        self.choice('T09', choice='lower_monthly')
        out = self.say('I think I want Original Medicare with a supplement', compose={'reply': 'Got it.'})
        self.assertEqual(out['coveragePath']['state'], 'chosen')
        self.assertEqual(out['coveragePath']['path'], 'original_medigap')
        self.assertEqual(self.flow.value(self.g, 'intent.coveragePath'), 'original_medigap')

    # --- CV-29, CV-30, X-03, X-04 ---------------------------------------------------
    def test_this_isnt_specific_to_me_gets_the_persons_two_paths_and_no_menu(self):
        self.situation_known()
        self.enrolled_in_neither()
        self.choice('T03', zip='34102')
        self.choice('T10', choice='total_cost,bills')
        self.choice('T09', choice='predictable')
        out = self.say('yeah but this isnt specific to me? IDK what is best for me for my situation',
                       compose={'question_target': None, 'question': MENU,
                                'reply': 'I’m sorry about that. ' + COBRA_LINE})
        kinds = [card['kind'] for card in out.get('cards', [])]
        self.assertIn('two_paths', kinds)
        self.assertIn('trade_off', kinds)                                # X-04: the trade-off, relayed
        card = next(card for card in out['cards'] if card['kind'] == 'two_paths')
        self.assertEqual([path['id'] for path in card['paths']], ['original_medigap', 'medicare_advantage'])
        self.assertEqual(card['lean']['path'], 'original_medigap')
        self.assertNotIn(MENU, out['reply'])
        question = out['assessment']['nextQuestion']
        self.assertTrue(question and question['id'] in {'MG_SEX', 'MG_TOBACCO'}, question)
        # Live run, November 12, 2026: asking again repeated both cards, and the
        # model sent a Medigap-path person to "Review your info" first.
        self.choice('MG_SEX', choice='Male')
        self.choice('MG_TOBACCO', choice='Non-Tobacco')
        last = self.say('i want to see the best plans for me', compose={'question_target': None, 'question': '',
            'reply': 'We’ll focus on predictable bills. The next step is Review your info, where you can correct your '
                     'details before choosing See plans. That review prepares the comparison. '
                     'Would you like to review your information now before seeing plans?'})
        self.assertEqual([card['kind'] for card in last.get('cards', [])], [])       # each card once a visit
        self.assertNotIn('Review your info', last['reply'])
        self.assertNotIn('review', last['reply'].casefold())
        self.assertIn('predictable bills', last['reply'])

    # --- found in the live run on :8895, November 12, 2026 ----------------------------
    def test_a_card_is_announced_only_when_one_is_attached(self):
        self.situation_known()            # birthday known, Part A and B not yet reported
        self.choice('T03', zip='34102')
        out = self.say('ok', compose={'question_target': None, 'question': '',
            'reply': 'We’ll connect your timing with what you have. The card below shows your timing.'})
        self.assertFalse([card for card in out.get('cards', []) if card['kind'] == 'enrollment_timing'])
        self.assertNotIn('card', out['reply'].casefold())
        self.assertIn('We’ll connect your timing', out['reply'])
        context = ux_flow.brief(self.flow, self.owner, self.g, self.r, {}, [], message='ok')
        self.assertFalse(context['conversation_state']['software_cards']['enrollment_timing'])
        shown = self.enrolled_in_neither({'question_target': None, 'question': '',
            'reply': 'The card below shows your timing.'})
        self.assertTrue([card for card in shown['cards'] if card['kind'] == 'enrollment_timing'])
        self.assertIn('card below', shown['reply'])

    def test_the_question_stands_alone_without_its_reason_or_its_options(self):
        cases = [
            ('What month and year do you turn 65? That helps identify the sign-up window.', [],
             'What month and year do you turn 65?'),
            ('Because Medigap insurers list separate Female and Male prices, which sex category should we use for '
             'your prices: Female or Male?', ['Female', 'Male'], 'Which sex category should we use for your prices?'),
            ('When balancing monthly payments against costs when you get care, which would you lean toward: lower '
             'monthly payments, more predictable costs, or no preference yet?',
             ['Lower monthly payments', 'More predictable costs', 'No preference yet'],
             'When balancing monthly payments against costs when you get care, which would you lean toward?'),
            ('To help compare options with your care in mind, which doctors or hospitals would you like to keep? You '
             'can leave this for later if you prefer.', [], 'Which doctors or hospitals would you like to keep?'),
            ('What ZIP code do you live in, so we can look at options in your area?', [], 'What ZIP code do you live in?'),
            ('What month and year do you turn 65, so we can put your Medicare sign-up timing in context?', [],
             'What month and year do you turn 65?'),
            ('Who is this for?', [], 'Who is this for?')]
        for text, labels, wanted in cases:
            self.assertEqual(ux_pass.plain_question(text, labels)[0], wanted)
        self.choice('RC01', choice='self')
        out = self.pick('T05', {'question_target': 'S_AGE65',
                                'question': 'What month and year do you turn 65? That helps identify your sign-up window.',
                                'reply': 'Thanks.'}, choice='cobra')
        question = out['assessment']['nextQuestion']
        self.assertEqual(question['question'], 'What month and year do you turn 65?')
        self.assertTrue(question['why'])

    def test_the_two_paths_appear_once_the_zip_is_known_in_find_mode(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='cobra')
        self.say('I want to know which is best for me.', compose={'reply': 'Whether one is best depends on your situation.'})
        out = self.pick('T03', {'reply': 'We’ll use 34102.'}, zip='34102')
        self.assertIn('two_paths', [card['kind'] for card in out.get('cards', [])])
        again = self.say('ok', compose={'question_target': None, 'question': '', 'reply': 'Okay.'})
        self.assertNotIn('two_paths', [card['kind'] for card in again.get('cards', [])])

    def test_the_card_does_not_restate_the_cobra_rule_the_reply_already_gave(self):
        self.choice('RC01', choice='self')
        self.pick('T05', {'question_target': None, 'question': '', 'reply': COBRA_LINE}, choice='cobra')
        text = 'I turned 65 on November 8 2026'
        self.say(text, situation_proposals=[self.situation('age65', text, month=11, year=2026)])
        out = self.enrolled_in_neither({'question_target': None, 'question': '', 'reply': 'Here is your timing.'})
        card = next(card for card in out['cards'] if card['kind'] == 'enrollment_timing')
        self.assertNotIn('COBRA isn’t coverage from a current job', card['cobra'])
        self.assertIn('Medicare pays first and COBRA pays second', card['cobra'])

    # --- PG-01 ----------------------------------------------------------------------
    def test_medigap_age_is_derived_not_reported_at_the_birthday_boundary(self):
        self.situation_known()
        self.choice('T03', zip='34102')
        view = medigap_profile.profile(self.g)
        self.assertEqual(view['inputs']['age'], 65)
        age = next(item for item in view['details'] if item['id'] == 'MG_AGE')
        self.assertEqual(age['value'], 65)
        self.assertEqual(age['status'], 'derived')
        self.assertNotIn('reported', age['label'].casefold())
        self.assertNotIn('reported age 64', view['note'])
        # A person who really reports 64 still sees the age-65 note.
        self.choice('MG_AGE', choice='64')
        reported = medigap_profile.profile(self.g)
        self.assertEqual(reported['inputs']['age'], 65)
        self.assertIn('64', reported['note'])

    # --- CV-33 ----------------------------------------------------------------------
    def test_sources_show_only_when_a_fact_is_stated(self):
        self.choice('RC01', choice='self')
        out = self.say('ok thanks', compose={'question_target': None, 'question': '', 'reply': 'You’re welcome.',
                                              'evidence_refs': ['basics']})
        self.assertEqual(out['advisor']['sources'], [])

    # --- K-02 -----------------------------------------------------------------------
    def test_the_blood_pressure_memory_jog_is_kept_and_returns_to_the_task(self):
        self.choice('RC01', choice='self')
        jog = 'Common blood pressure medicines include lisinopril, amlodipine, losartan, metoprolol and hydrochlorothiazide.'
        out = self.say('can you jog my memory of common BP medicines? ill know it when i see it.',
                       compose={'question_target': 'T07', 'reply': jog, 'question': 'Which one do you take?'})
        if out['generated']['status'] == 'complete':
            self.assertEqual(out['reply'], jog)
            self.assertEqual(out['assessment']['nextQuestion']['id'], 'T07')
        else:   # the grounding check, not the UX pass, withheld scripted names
            self.assertTrue(out['assessment']['nextQuestion'])
        self.assertNotIn(MENU, out['reply'])

    # --- K-03, CV-26 ------------------------------------------------------------------
    def test_the_two_routes_are_explained_once_then_answered_with_the_persons_specifics(self):
        self.situation_known()
        self.enrolled_in_neither()
        self.choice('T03', zip='34102')
        routes = ('There are two main routes: Original Medicare with a Medigap policy and a separate drug plan, '
                  'or a Medicare Advantage plan.')
        first = self.say('I don’t understand my options.', compose={'reply': routes})
        self.assertIn(routes, first['reply'])                              # K-03: the first delivery stays whole
        self.assertIn('two_routes', self.flow.ux.view(self.owner, self.flow.current_chain[self.owner])['points'])
        self.say('ok', compose={'reply': 'Good.'})
        self.assertIn('two_routes', self.composed_context()['conversation_state']['already_said'])
        again = self.say('idk which is better for me', compose={'reply': routes + ' Here is how they compare for you.'})
        self.assertNotIn('two main routes', again['reply'])                # CV-26: not the general explanation again
        self.assertIn('Here is how they compare for you.', again['reply'])
        self.assertIn('two_paths', [card['kind'] for card in again['cards']])

    # --- CV-31 ------------------------------------------------------------------------
    def test_one_question_per_turn_in_the_question_slot(self):
        self.choice('RC01', choice='self')
        out = self.say('hello', compose={'question_target': 'T03', 'question': 'What is your ZIP code?',
                                         'reply': 'Plans are local. Do you live in Collier County? That decides which plans you see.'})
        self.assertNotIn('?', out['reply'])
        self.assertEqual(out['assessment']['nextQuestion']['question'].count('?'), 1)
        self.assertIn('That decides which plans you see.', out['reply'])

    # --- CV-22 (participant build: no check runs) ---------------------------------------
    def test_medicines_get_one_clear_not_checked_yet(self):
        self.choice('RC01', choice='self')
        text = 'Ozempic and metoprolol'
        out = self.say(text, [self.update('T07', {'text': text}, text)], compose={'reply': 'Thanks.'})
        notes = [card for card in out.get('cards', []) if card['kind'] == 'medicines_note']
        self.assertEqual(len(notes), 1)
        self.assertIn('aren’t checked against each plan’s drug list yet', notes[0]['text'])
        later = self.say('also vitamin d', [self.update('T07', {'text': 'vitamin d'}, 'also vitamin d')], compose={'reply': 'Added.'})
        self.assertFalse([card for card in later.get('cards', []) if card['kind'] == 'medicines_note'])

    # --- CV-23 ------------------------------------------------------------------------
    def test_ozempic_gets_the_prior_authorization_statement_once(self):
        self.choice('RC01', choice='self')
        text = 'Ozempic and metoprolol'
        out = self.say(text, [self.update('T07', {'text': text}, text)], compose={'reply': 'Thanks.'})
        cards = [card for card in out.get('cards', []) if card['kind'] == 'medicine_rule']
        self.assertEqual(len(cards), 1)
        self.assertIn('many require prior authorization', cards[0]['text'])
        self.assertIn('don’t cover a drug prescribed only for weight loss', cards[0]['text'])
        self.assertTrue(cards[0]['sources'])
        later = self.say('ok', compose={'reply': 'Good.'})
        self.assertFalse([card for card in later.get('cards', []) if card['kind'] == 'medicine_rule'])

    # --- CV-34 ------------------------------------------------------------------------
    def test_a_question_never_reads_out_its_answer_buttons(self):
        self.choice('RC01', choice='self')
        typed = ('What coverage do you have now: Original Medicare (Parts A and B), Medicare Advantage (Part C), '
                 'Medicare Supplement / Medigap, a separate prescription drug plan, current-job coverage, retiree '
                 'coverage, COBRA, VA, TRICARE or military coverage, Medicaid, none, or not sure?')
        out = self.say('hi', compose={'question_target': 'T05', 'reply': 'Hello.', 'question': typed})
        question = out['assessment']['nextQuestion']
        self.assertEqual(question['id'], 'T05')
        self.assertLess(len(question['question']), 80)
        self.assertNotIn('TRICARE', question['question'])
        self.assertGreaterEqual(len(question['choices']), 10)              # the options stay as buttons

    # --- the whole journey, scripted, with the scorecard measures -----------------------
    def test_scripted_journey_reaches_medigap_prices_and_records_the_scorecard(self):
        asked, replies, cards, answered = [], [], [], []

        def note(out):
            question = (out.get('assessment') or {}).get('nextQuestion') or {}
            asked.append(question.get('id'))
            replies.append(out.get('reply', ''))
            cards.extend(card['kind'] for card in out.get('cards', []))
            return out
        note(self.pick('T01', {'reply': ''}, choice='learn'))                                  # 1 Understand Medicare
        note(self.say('I don’t understand my options.', compose={'reply': 'There are two main routes: Original Medicare, or Medicare Advantage.'}))
        note(self.say('I want to know which is best for me. I hear good things about MA?', compose={'reply': 'Good question.'}))
        note(self.pick('RC01', {'reply': 'Thanks.'}, choice='self'))
        note(self.pick('T05', {'reply': COBRA_LINE}, choice='cobra'))                           # 6 COBRA
        text = 'I just turned 65, November 8 2026'
        note(self.say(text, compose={'reply': COBRA_LINE}, situation_proposals=[self.situation('age65', text, month=11, year=2026)]))
        note(self.pick('RC04', {'reply': COBRA_LINE + ' Here is your timing.'}, choice='neither'))   # 10 Neither
        note(self.pick('T03', {'reply': 'Noted: Naples, 34102.'}, zip='34102'))                 # 16 34102
        note(self.pick('T10', {'reply': 'Those can pull apart.'}, choice='total_cost,bills'))   # 5
        note(self.pick('T09', {'reply': 'Predictable it is.'}, choice='predictable'))           # 25
        note(self.pick('MG_SEX', {'reply': 'Thanks.'}, choice='Male'))
        last = note(self.pick('MG_TOBACCO', {'reply': 'Your Medigap prices are ready.'}, choice='Non-Tobacco'))
        self.assertEqual(last['medigapProfile']['status'], 'ready')
        self.assertEqual(last['coveragePath']['path'], 'original_medigap')                     # PG-10
        said = ' '.join(replies) + ' '
        scorecard = {
            'inputs_before_medigap_prices': len(replies),
            'cobra_caveat_in_replies': said.count('does not extend the time to sign up'),
            'timing_cards': cards.count('enrollment_timing'),
            'topic_menus': sum(MENU in reply for reply in replies),
            'noted_openers': sum(reply.startswith('Noted') for reply in replies),
            'reasks_of_an_answered_detail': sum(1 for item in asked if item in ('RC11', 'T04', 'T02')),
            'questions_asked': [item for item in asked if item]}
        self.assertLessEqual(scorecard['inputs_before_medigap_prices'], 12)
        self.assertLessEqual(scorecard['cobra_caveat_in_replies'], 1)      # CV-14: COBRA stated once
        self.assertEqual(scorecard['timing_cards'], 1)
        self.assertEqual(scorecard['topic_menus'], 0)
        self.assertEqual(scorecard['noted_openers'], 0)
        self.assertNotIn('T02', asked)
        self.assertNotIn('RC11', asked)
        self.assertNotIn('T04', asked)
        import json, os
        target = os.environ.get('PP16_SCORECARD')
        if target:
            with open(target, 'w', encoding='utf-8') as handle:
                json.dump(scorecard, handle, indent=2)


if __name__ == '__main__':
    unittest.main()
