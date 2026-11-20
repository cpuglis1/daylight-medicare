"""Regression tests from the 15-profile live run of November 13, 2026.

Every case is a fictional person's own words from the run logs in
``audit-evidence/enrollment-d161-20261112/profile-runs-20261113/``. Offline:
no network, no model billing. They prove the code-side rules, not how a live
model replies (UX playbook lesson 10).
"""
from datetime import date
import re
import unittest

import test_enrollment_flow as stories
import conversation_checks
import enrollment_flow
import identifier_guard
import natural_agent
import pilot_knowledge
import ux_flow
import ux_pass

TODAY = date(2026, 11, 13)
UNKNOWN = {'parts': {'A': {'state': 'unknown'}, 'B': {'state': 'unknown'}}}


def read(text, role='self'):
    return enrollment_flow.reports_from_text(text, UNKNOWN, TODAY, role)


class WhatPeopleAlreadyHave(unittest.TestCase):
    """Finding A: 2 of 15 of these were read before the fix."""
    ACTIVE = {
        'PP02': ("I'm 72, in 34105. A and B started June 1, 2019, and I joined this HMO then. I've never had Part G.", '2019-06-01'),
        'PP04': ("I've had Parts A and B since February 2025, plus a separate drug plan. I never bought a supplement.", '2025-02-01'),
        'PP05': ('A and B since July 2017, Plan F since then, and a separate drug plan. F is $318 a month now.', '2017-07-01'),
        'PP06': ('April 18, 1961. Naples, 34108. A, B, and this HMO all started April 1 this year.', '2026-04-01'),
        'PP07': ("Original Medicare since July, Plan G, and a separate drug plan I picked in June. I'm keeping the Plan G.", '2026-07-01'),
        'PP10': ("I'm 73, in 34102. Original Medicare, Plan G, and a separate prescription plan. A and B and both policies started in May 2018.", '2018-05-01'),
        'PP11': ('Parts A and B started September 1. No supplement or drug plan yet. I had a marketplace plan before.', '2026-09-01'),
        'PP14': ('Medicare and Wellcare Giveback both since August 2024. Never had a supplement.', '2024-08-01'),
    }
    SINCE = {
        'PP08': ('medicare a and b, plan n, and a drug plan since 2021. its $14 a month', '2021'),
        'PP12': ('Humana Gold Plus HMO since 2024. Original Medicare A and B before that, since 2020. No supplement.', '2020'),
        'PP15': ('Original Medicare since 2020, Plan G, and the AARP Rx Saver drug plan.', '2020'),
    }

    def test_both_parts_in_place_with_the_date_the_person_gave(self):
        for profile, (words, when) in self.ACTIVE.items():
            found = read(words)
            self.assertEqual({part: (found[part]['status'], found[part]['date']) for part in found},
                             {'A': ('active', when), 'B': ('active', when)}, profile)

    def test_a_year_alone_is_kept_as_the_person_said_it(self):
        for profile, (words, year) in self.SINCE.items():
            found = read(words)
            self.assertEqual({part: (found[part]['status'], found[part]['date'], found[part].get('since')) for part in found},
                             {'A': ('active', None, year), 'B': ('active', None, year)}, profile)
            self.assertEqual(enrollment_flow._part_text('active', {'date': None, 'basis': None}, found['A']),
                             'active since %s (you told me)' % year)

    def test_parts_still_to_start_and_one_part_only(self):
        self.assertEqual(read('My card says Part A and Part B both start December 1, 2026')['B'],
                         {'status': 'approved', 'date': '2026-12-01', 'date_kind': 'start'})
        self.assertEqual(read("A and B start January 1. I'm on a marketplace plan until then; no job insurance.")['A']['date'], '2027-01-01')
        only = read('I only ever signed up for Part A')
        self.assertEqual(list(only), ['A'])
        self.assertEqual(only['A']['status'], 'active')

    def test_sentences_that_say_nothing_about_the_parts(self):
        for words in ('I want Original Medicare since it covers any doctor.', 'I started looking at Original Medicare last week.',
                      'I have a question about Part B.', "I've never had Part G.", 'Medicare started sending me mail.',
                      "Should I get Part B since I'm still working?", 'Part B is $202.90 a month since January.',
                      'My wife has Parts A and B.', 'I heard Medicare started in 1965.', 'No A, no B.'):
            self.assertEqual(read(words), {}, words)
        # A negated part is left out, not guessed.
        self.assertEqual(list(read('I have had Part A since 2015 but never took Part B.')), ['A'])

    def test_the_plan_letter_a_person_holds(self):
        for words, letter in (('A and B since July 2017, Plan F since then, and a separate drug plan.', 'F'),
                              ('Original Medicare since 2020, Plan G, and the AARP Rx Saver drug plan.', 'G'),
                              ('medicare a and b, plan n, and a drug plan since 2021.', 'N'),
                              ("He's had Plan F since he turned 65.", 'F'), ("I'm paying $236 for Plan G plus a drug plan.", 'G')):
            self.assertEqual(enrollment_flow.held_from_text(words), {'medigap_letter': letter}, words)
        for words in ("My friend says Plan G is the one everyone gets. What's the difference with N?",
                      'What would Plan G cost me?', 'I want Plan G.', "I've never had Plan G."):
            self.assertEqual(enrollment_flow.held_from_text(words), {}, words)

    def test_where_someone_stands_is_not_a_decision(self):
        choices = enrollment_flow.choices_from_text
        self.assertEqual(choices('No supplement or drug plan yet.')['components'], {})                       # PP11
        self.assertEqual(choices('ok so i drop the drug plan now and pick one up later if i ever need pills')['components'], {})   # PP08
        self.assertEqual(choices("I'm keeping the Plan G.")['components'], {'medigap': 'keep_existing'})    # PP07
        self.assertEqual(choices("I don't need a drug plan.")['components'], {'part_d': 'not_needed'})
        self.assertEqual(choices("I'll decide on the drug plan later.")['components'], {'part_d': 'decide_later'})


class RecordedOnTheDashboard(stories.Journey):
    def test_trial_right_uses_the_reported_first_advantage_start(self):
        from unittest.mock import patch

        self.choice('RC01', choice='self')
        self.choice('T05', choice='advantage')
        with patch.object(enrollment_flow, '_today', return_value=TODAY):
            enrollment_flow.capture(self.flow, self.g, self.r,
                                    'I joined my first Medicare Advantage plan in April 2026.')
        trial = enrollment_flow.trial_right(self.flow, self.g, self.r, TODAY)
        self.assertEqual(trial['rows'][1]['value'], 'April 2027 (from your start month)')
        self.assertIn('still open', trial['rows'][2]['value'])
        with patch.object(enrollment_flow, '_today', return_value=TODAY):
            enrollment_flow.capture(self.flow, self.g, self.r,
                                    'I joined my first Medicare Advantage plan in April 2024.')
        trial = enrollment_flow.trial_right(self.flow, self.g, self.r, TODAY)
        self.assertEqual(trial['rows'][2]['value'], 'The first 12 months have passed.')

    def test_a_medicare_advantage_member_has_both_parts_and_is_told_why(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='advantage')
        out = self.say('I like my HMO otherwise.')                                    # PP12
        line = out['enrollment']['line']['text']
        self.assertIn('Part A: active (from your Medicare Advantage plan)', line)
        self.assertIn('Part B: active (from your Medicare Advantage plan)', line)
        self.assertNotIn('not confirmed', line)
        self.assertEqual(out['enrollment']['dashboard']['paths']['advantage']['steps'][1]['text'], 'You have a Medicare Advantage plan.')

    def test_parts_said_in_passing_set_the_status_line_and_answer_the_parts_question(self):
        self.choice('RC01', choice='self')
        out = self.say("I've had Parts A and B since February 2025, plus a separate drug plan.")           # PP04
        self.assertIn('Part A: active since February 1, 2025 (you told me)', out['enrollment']['line']['text'])
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'both')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'), 'RC04')

    def test_neither_part_in_five_words(self):
        self.choice('RC01', choice='self')
        self.say('No A, no B.')                                                         # PP09
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'neither')

    def test_what_a_person_has_is_shown_as_a_fact_with_keep_it_and_compare(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='original,medigap,drug')
        out = self.say('Original Medicare since 2020, Plan G, and the AARP Rx Saver drug plan.')            # PP15
        steps = out['enrollment']['dashboard']['paths']['original']['steps']
        self.assertEqual(steps[1]['text'], 'You have Plan G.')
        self.assertEqual(steps[2]['text'], 'You have a drug plan.')
        self.assertEqual([label for _, label in steps[1]['choices']], ['Keep it', 'Compare', 'Decide later'])
        self.assertEqual(out['enrollment']['record']['components'], {'medigap': 'unknown', 'part_d': 'unknown'})   # a fact, not a decision
        card = self.cards(out, 'coverage_now')
        self.assertEqual(len(card), 1)
        self.assertEqual(card[0]['title'], 'What you have now')
        self.assertEqual([row['value'] for row in card[0]['rows']],
                         ['active since 2020 (you told me)', 'active since 2020 (you told me)', 'You have Plan G.', 'You have a drug plan.'])
        self.assertFalse(self.cards(self.say('ok'), 'coverage_now'))                  # once


class OneQuestionNeverOwnsTheConversation(unittest.TestCase):
    def test_a_sentence_is_never_taken_as_the_doctors_town(self):
        place = conversation_checks.ConversationChecks.looks_like_place
        for words in ("Female, and I've never used tobacco.",                          # PP11: lost, no reply
                      "He doesn't want any hassle with doctors. He just thinks $318 is a lot.",   # PP05
                      'I visit my daughter in Chicago a few times a year.',           # PP11
                      "Keep Dr. Josephson. I like the Part B money back, but I'd give it up for him.",   # PP14
                      '70. cheapest is the priority', 'none', "It's on 9th Street"):
            self.assertFalse(place(words), words)
        for words in ('Naples', 'in Naples', '34102', 'Fort Myers, FL', 'Bay Lantern Cardiology', 'NCH',
                      'the NCH heart institute', 'Physicians Regional', 'Millennium Physician Group'):
            self.assertTrue(place(words), words)

    def test_only_the_name_is_searched(self):
        entry = conversation_checks.ConversationChecks.doctor_entry
        self.assertEqual(entry('Dr. Kelly Craig, my internist for years'), ('Dr. Kelly Craig', None, None))        # PP11
        self.assertEqual(entry('Dr. Mark Speake at NCH on 9th Street'), ('Dr. Mark Speake', None, 'NCH'))         # PP04
        self.assertEqual(entry('Mark Josephson at NCH'), ('Mark Josephson', None, 'NCH'))                         # PP14
        self.assertEqual(entry('Dr. Shannon Wise, at her office on Goodlette-Frank Road'), ('Dr. Shannon Wise', None, None))   # PP01
        self.assertEqual(entry('Dr. Albagdadi at the NCH heart institute'), ('Dr. Albagdadi', None, 'NCH heart institute'))   # PP13
        self.assertEqual(entry('Nella Ashden for primary care'), ('Nella Ashden', None, None))                    # PP06
        self.assertEqual(entry('Ashley Tunkle in Naples'), ('Ashley Tunkle', 'Naples', None))                     # PP16, unchanged
        self.assertEqual(entry('Dr. Maria Lopez, Naples'), ('Dr. Maria Lopez', 'Naples', None))
        self.assertEqual(entry('Naples Heart and Vascular'), ('Naples Heart and Vascular', None, None))
        self.assertEqual(conversation_checks.ConversationChecks.doctor_name('Ashley Tunkle in Naples'), ('Ashley Tunkle', 'Naples'))

    def test_not_found_is_not_unavailable(self):
        self.assertEqual(conversation_checks.NOT_FOUND_CODES,
                         {'DOCTOR_QUERY_EMPTY', 'DOCTOR_SEARCH_NEEDS_NAME_OR_DETAIL', 'INVALID_LITERAL_PROVIDER_REQUEST'})

    def test_a_second_ask_is_a_fixed_wording_and_never_a_fragment(self):
        short = ux_pass.shorter_question
        medicine = 'For each medicine, what quantity, days supply, exact pharmacy and retail or mail order should we use?'
        self.assertEqual(short('RC23', medicine), 'What are the refill details for these medicines?')
        doctors = 'Which doctors or hospitals would you want to keep, including your therapist?'
        self.assertEqual(short('T06', doctors), 'Any doctors or hospitals to keep?')
        self.assertEqual(short('RC99', doctors), doctors)                              # no fixed wording: unchanged, never a piece
        self.assertEqual(short('MG_AGE', 'How old is your father?', helper=True), 'How old is your father?')   # a helper is not "you"
        for wording in (short('RC23', medicine), short('T06', doctors)):
            self.assertNotIn('ready:', wording)
            self.assertNotIn('confirm:', wording)

    def test_two_shows_then_parked(self):
        ledger = ux_pass.VisitLedger()
        key = ux_flow.question_key({'id': 'RC23.medicine-1', 'entity': 'medicine-1'})
        self.assertEqual(key, 'RC23|medicine-1')
        self.assertEqual([ledger.shown_question('owner', 'chain', key) for _ in range(3)], [1, 2, 3])
        self.assertFalse(ledger.parked('owner', 'chain', key))
        ledger.park('owner', 'chain', key)
        self.assertTrue(ledger.parked('owner', 'chain', key))
        self.assertFalse(ledger.parked('owner', 'other-visit', key))


class TextIsCutByWholeSentences(unittest.TestCase):
    def test_titles_decimals_and_initials_do_not_end_a_sentence(self):
        said = ('We’ll keep Dr. Speake and Dr. Albagdadi at the center of the comparison. '
                'For your preference for predictable bills, Medigap is worth comparing.')
        self.assertEqual(len(ux_pass.sentences(said)), 2)                              # PP13: "Dr. Speake and Dr. For your..."
        self.assertEqual(ux_pass.sentences('Plan G costs $236.50 a month, e.g. in Naples. It is on U.S. 41.'),
                         ['Plan G costs $236.50 a month, e.g. in Naples. ', 'It is on U.S. 41.'])
        self.assertEqual(ux_pass.sentences('You have Part A. You still need Part B. Plan G is next.'),
                         ['You have Part A. ', 'You still need Part B. ', 'Plan G is next.'])
        self.assertEqual(len(ux_pass.sentences('Is that right? Yes! Good.')), 3)

    def test_replies_point_to_the_plans_page_not_to_a_tab_or_a_step(self):
        fix = enrollment_flow.tab_names
        self.assertEqual(fix('The Original Medicare (step 3, prescriptions) tab on the Plans page now lists 2026 stand-alone Part D plans.'),
                         'The Plans page now lists 2026 stand-alone Part D plans.')
        self.assertEqual(fix('The premiums already listed in the “Original Medicare (step 2, your share of medical costs)” tab are dated source prices.'),
                         'The premiums already listed on the Plans page are dated source prices.')
        self.assertEqual(fix('the Plans page now lists premiums for your details in the “Original Medicare (step 2, your share of medical costs)” tab.'),
                         'the Plans page now lists premiums for your details.')
        self.assertEqual(fix('Open the Medicare Advantage tab.'), 'Open the Medicare Advantage tab.')


class CardsFromTheStateOfTheConversation(unittest.TestCase):
    ASKS = ('Which way of doing Medicare lets me keep both?', 'What are my options?', 'What would a supplement cost me?',
            'Which plan is cheapest for her?', 'We just want the cheapest plan that works at Stoney\'s.',
            'Can you put the plans in order by what my four medicines would cost?', 'But show me whatever you have.',
            "need the cheapest 2027 drug plan. i don't take any pills", 'Should I leave this Advantage plan, yes or no?',
            'Would you actually recommend keeping the coverage I already have?', 'Just name the best Medicare plan',
            'Can you list the plans in order of lowest premium?', "How much is Plan G for my dad? He's 74, in 34108.")

    def test_thirteen_peoples_ways_of_asking_for_their_options(self):
        for words in self.ASKS:
            self.assertTrue(ux_pass.find_intent(words, wide=True), words)
        self.assertFalse(ux_pass.find_intent('Female, and I\'ve never used tobacco.', wide=True))
        self.assertFalse(ux_pass.find_intent('What are my options?'))                  # the shared build is unchanged until released
        self.assertTrue(ux_pass.find_intent("what's the best plan for me"))

    def test_both_paths_named_and_a_request_for_daylights_pick(self):
        self.assertTrue(ux_flow.BOTH_PATHS.search('That TV Advantage plan costs zero. I am paying $236 for Plan G.'))
        self.assertFalse(ux_flow.BOTH_PATHS.search('What would a supplement cost me?'))
        self.assertTrue(ux_flow.RECOMMEND_ASK.search('Would you actually recommend keeping the coverage I already have?'))
        self.assertTrue(ux_flow.RECOMMEND_ASK.search('Should I leave this Advantage plan, yes or no?'))
        self.assertFalse(ux_flow.RECOMMEND_ASK.search('Is there any limit on what I could end up paying?'))
        self.assertEqual(ux_flow.NO_PICK, 'I can’t make that choice for you here. This is how each path fits what you told me.')
        self.assertEqual(ux_flow.READY['medigap'][0], 'Your Medigap prices are ready.')
        self.assertEqual(ux_flow.READY['part_d'][0], 'Your drug plans are ready.')


class TheChatNeverRecommends(unittest.TestCase):
    def test_a_first_person_pick_is_rejected_and_a_caution_is_not(self):
        pick = natural_agent.FIRST_PERSON_PICK
        self.assertTrue(pick.search('Yes—as a practical next step, I’d keep your current coverage in place while comparing alternatives.'))   # PP10
        for words in ('I would switch to Plan N.', 'I recommend Plan G.', 'My recommendation is to stay.', 'If I were you, I would wait.'):
            self.assertTrue(pick.search(words), words)
        for words in ('No—he shouldn’t drop Plan F on that assumption.', 'Not necessarily. A zero-dollar premium doesn’t mean zero costs.',
                      'Before dropping existing coverage, confirm acceptance by a Medigap insurer.',
                      'I can’t make that choice for you here.', 'I’d like to check one detail.', 'I’ll keep that doctor on your list.'):
            self.assertFalse(pick.search(words), words)


class RulesTheChatCanState(unittest.TestCase):
    def test_peoples_own_phrasing_finds_the_approved_fact(self):
        knowledge = pilot_knowledge.PilotKnowledge(surface='unified-8895')
        if not knowledge.status(today=TODAY).get('available_count'):
            self.skipTest('the reviewed catalog is not available in this checkout')
        for words, fact in (('Is there any limit on what I could end up paying for drugs in a year?', 'pk_part_d_cap'),          # PP07
                            ("I work for a company with 240 employees and I'm staying two more years.", 'pk_payer_order'),        # PP09
                            ('I have about two months to get a drug plan, right?', 'pk_plan_coverage_loss_window'),               # PP03
                            ('ok so i drop the drug plan now and pick one up later if i ever need pills', 'pk_penalty_d'),        # PP08
                            ('Does losing my doctor mean they have to let me buy that G policy?', 'pk_medigap_underwriting')):    # PP02
            self.assertIn(fact, [item['id'] for item in knowledge.select(words, today=TODAY)], words)
        self.assertEqual(knowledge.select("Female, and I've never used tobacco.", today=TODAY), [])
        self.assertEqual(pilot_knowledge.PilotKnowledge(surface=None).select('Is there a limit on drug costs in a year?', today=TODAY), [])   # other surfaces unchanged

    def test_three_checked_rules_for_questions_that_had_no_words(self):
        found = lambda words: [item['id'] for item in enrollment_flow.extra_evidence(words)]
        self.assertEqual(found('I heard insulin is capped now. Is that true for my Lantus?'), ['ev_insulin_cap'])                  # PP12
        self.assertEqual(found("My friend says Plan G is the one everyone gets. What's the difference with N?"), ['ev_medigap_g_n'])   # PP04
        self.assertEqual(found("He's had Plan F since he turned 65. Can he even still have F?"), ['ev_medigap_c_f'])              # PP05
        self.assertEqual(found('How much is Plan G for my dad?'), [])
        for entry in enrollment_flow.extra_evidence('insulin, Plan F, Plan G or Plan N'):
            self.assertTrue(entry['sources'] and all(source['url'].startswith('https://www.medicare.gov/') for source in entry['sources']))
            self.assertNotRegex(entry['text'], r'(?i)\byou should\b|\bbest\b|\brecommend')

    def test_the_plan_letter_sentences_match_the_signed_lines_on_the_medigap_page(self):
        script = open(enrollment_flow.CONTENT.with_name('web-8894') / 'medigap-plans.js', encoding='utf-8').read()
        text = enrollment_flow.content()['evidence']['ev_medigap_g_n']['text']
        for letter in ('G', 'N'):
            line = re.search(r"\b%s:'([^']+)'" % letter, script).group(1)
            self.assertIn(line[1:], text)                                              # the signed line, after its first capital


class IdentifiersThatAlmostLookRight(unittest.TestCase):
    def test_near_misses_are_blocked_and_ordinary_numbers_are_not(self):
        find = identifier_guard.find_identifiers
        for words in ('My Medicare number is 0AB1-CD2-EF34 if you need to look me up.',   # the shape of PP06's fictional number
                      'my medicare # is 1EG4-TE5-MK7 thanks', 'medicare number: 1eg4te5mk7o', 'MBI 0EG4TE5MK73',
                      'my social is 123-45-678', 'Social Security number is 000-12-3456'):
            self.assertTrue(find(words), words)
        for words in ("I'm in 34102, plan H1036-286-000 looks good", "Medicare's number is 1-800-633-4227",
                      'My Medicare number is on my card, do you need it?', 'ZIP 34108-1234', '311 9th Street North, Suite 306',
                      'Plan G is $236.50 and Part B is $202.90', 'born April 18, 1961', 'Humana Gold Plus H1036-077 since 2024',
                      'A and B started June 1, 2019',
                      'Ends Dec 2026', 'ends dec 2026', 'Plan ends Mar 2027', 'Mine ends Jan 2027',   # D200: dates, not numbers
                      'Work ends Oct 2026', 'Job ends Sept 2026 and COBRA ends Mar 2027'):
            self.assertEqual(find(words), [], words)
        self.assertEqual(identifier_guard.find_transport_identifiers('plan H1036-286-000 and 0AB1-CD2-EF34'), [])   # the backstop is unchanged


class TraceAndHolds(stories.Journey):
    def test_the_turn_trace_holds_codes_and_counts_and_none_of_the_persons_words(self):
        import json, os, tempfile
        folder = tempfile.mkdtemp()
        self.flow.turn_trace = os.path.join(folder, 'turn-trace.jsonl')
        self.choice('RC01', choice='self')
        self.say('My cardiologist is Dr. Canaryname and I take Secretmedicine.')
        lines = [json.loads(line) for line in open(self.flow.turn_trace, encoding='utf-8')]
        self.assertTrue(lines and lines[-1]['action'] == 'message')
        self.assertEqual({'at', 'visit', 'action', 'ms', 'calls', 'question', 'cards', 'reply_chars'} - set(lines[-1]), set())
        text = open(self.flow.turn_trace, encoding='utf-8').read()
        self.assertNotIn('Canaryname', text)
        self.assertNotIn('Secretmedicine', text)
        self.assertNotIn(self.owner, text)

    def test_a_question_passed_twice_is_parked_and_the_next_one_is_asked(self):
        self.choice('RC01', choice='self')
        chain = self.flow.current_chain[self.owner]
        shown = []
        for _ in range(3):
            out = {'assessment': {'nextQuestion': self.flow.question('T08')}, 'guide': self.g, 'record': self.r}
            self.flow.park_passed_question(self.owner, chain, out)
            shown.append((out['assessment'].get('nextQuestion') or {}).get('id'))
        self.assertEqual(shown[:2], ['T08', 'T08'])                                     # asked, asked once more
        self.assertNotEqual(shown[2], 'T08')                                            # then parked (PP08: the travel question, three turns)
        self.assertTrue(self.flow.ux.parked(self.owner, chain, 'T08|profile'))
        self.assertNotIn('T08', [item['id'] for item in self.flow.eligible(self.owner, self.g, self.r)])
        for _ in range(4):                                                              # the ZIP code opens everything else: never parked
            out = {'assessment': {'nextQuestion': self.flow.question('T03')}, 'guide': self.g, 'record': self.r}
            self.flow.park_passed_question(self.owner, chain, out)
            self.assertEqual(out['assessment']['nextQuestion']['id'], 'T03')

    def test_being_in_a_plan_today_holds_the_suggested_path(self):
        import recommendation_engine
        held = recommendation_engine.evaluate_path({'scope': {'zipcode': '34105'}, 'current_coverage': ['advantage', 'drug']}, None, None, None)
        self.assertEqual(held['state'], 'held')                                         # PP02
        self.assertIn('does not suggest a path yet', json_text(held))

    def test_a_held_report_about_a_new_medicine_keeps_the_list_and_the_turn(self):
        # The cause of both 93-second failures (Terminal log, November 13, 2026: ValueError at
        # natural_state.set_target): a medicine for a new list entry, held for confirmation.
        self.choice('RC01', choice='self')
        self.choice('T05', choice='original,medigap,drug')
        said = 'Metformin ER 500, two a day. Atorvastatin 40. And the Breyna inhaler, two puffs twice a day.'
        listed = self.update('T07', {'text': 'Metformin ER 500; Atorvastatin 40; Breyna inhaler'}, said)
        for held in (dict(uncertain=True), dict(subject='unclear')):
            out = self.say(said, [listed, self.update('RC22', {'name': 'Breyna inhaler'}, 'the Breyna inhaler', entity='new', **held)])
            question = out['assessment'].get('nextQuestion') or {}
            self.assertEqual((question.get('id'), question.get('entity')), ('RC22', 'profile'))   # asked, not a failed turn
            self.assertTrue(out.get('reply'))

    def test_a_typed_message_never_ends_in_a_bare_server_error(self):
        import natural_flow
        from chat import ModelUnavailable
        def fail(*args):
            raise RuntimeError('boom')
        self.flow.message = fail
        with self.assertLogs('natural_flow', level='ERROR'):
            with self.assertRaises(ModelUnavailable) as caught:
                self.take(self.payload({'type': 'message', 'message': 'Metformin ER 500, two a day, and atorvastatin 40.'}))
        self.assertEqual(str(caught.exception), natural_flow.TURN_FAILED)               # PP07 and PP14 saw a 500 after 93 seconds
        self.assertTrue(natural_flow.TURN_TOO_LONG.endswith('Send again?'))


def json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False)


if __name__ == '__main__':
    unittest.main()
