"""Tests for the narrow reply check. Fictional people, plans, doctors and amounts only.

False rejections are the main risk, so there are more "a good reply passes"
cases than "a bad reply fails" cases, and one test runs every passing example
and reports the false-rejection count.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,E702,F401

from one_call_check import check_reply  # noqa: E402


def grounding(**changes):
    """One fictional visit: the person's messages, saved reports, tool outputs and fact texts."""
    base = {
        'person_text': [
            "hi i turn 65 next spring and i'm still working",
            "my heart doctor is dr. anneliese rookmere over at bay lantern cardiology",
            "i take eliquis every day and also atorvastatn 20 mg",
            "insurance is through my job at Pellworth Tools, it's a harbor crest plan",
            "about 20 employees i think",
            "my last day will be some time in June",
            "i pay about $510 for 60 tablets right now",
            "ok that makes sense",
            "what happens to my wife Odalys",
            "can we keep going",
            "odalys pays 45 a month for hers",
        ],
        'reports': [
            {'id': 'guide.situation.age65', 'value': {'year': 2027, 'month': 3}, 'status': 'reported'},
            {'id': 'guide.coverage.current', 'value': 'employer', 'status': 'reported'},
        ],
        'tool_outputs': [
            {'name': 'get_signup_dates', 'arguments': {}, 'output': {
                'ok': True,
                'signup_window': {'start': '2026-12-01', 'end': '2027-06-30',
                                  'basis': 'three months before your birthday month to three months after'},
                'part_b_start': '2027-03-01',
                'medigap_window_end': '2027-08',
                'job_window_end': '2027-02-28'}},
            {'name': 'get_plan_status', 'arguments': {}, 'output': {
                'ok': True, 'plans': [{'name': 'Corvane Shield Value PPO', 'monthly_cents': 4250}]}},
        ],
        'fact_texts': {
            'F-PREMIUM': 'The example Part B premium used in this test is $185.00 a month.',
            'F-SHARE': 'In this example the program pays 80 percent and the person pays twenty percent.',
            'F-FALL': 'The example fall period runs October 15 through December 7 each year.',
            'F-STEP': 'In this example you should sign up for Part B during the sign-up window.',
        },
        'open_ids': {'T05', 'T07'},
    }
    base.update(changes)
    return base


def reply(*blocks, question=None, pause=False):
    return {'reply_blocks': [block if isinstance(block, dict) else {'text': block, 'fact_ids': []} for block in blocks],
            'question': question, 'pause': pause,
            'concerns': {'why_now': None, 'worries': [], 'tried': []}}


HELPER = grounding(person_text=["i'm helping my mother sort this out, she turns 65 in march",
                                "she still works part time", "she sees a dr. vale"])
ALIAS = grounding(person_text=["my card says uhc on it"])
# The same visit after two checks ran: one entry as the runner returns it, one
# as the bare output the conversation keeps from an earlier turn.
CHECK_OUTPUTS = [
    {'name': 'check_doctor', 'arguments': {'name': 'Rookmere', 'place': ''}, 'output': {
        'ok': True, 'kind': 'doctor', 'name': 'Dr. Anneliese Rookmere', 'status': 'result', 'needs': None,
        'results': [{'kind': 'doctor', 'name': 'Anneliese Rookmere', 'plan': 'Corvane Shield Value PPO',
                     'state': 'in_network', 'text': 'Listed in this plan directory.'}]}},
    {'ok': True, 'kind': 'medicine', 'name': 'Eliquis', 'status': 'result', 'needs': None,
     'results': [{'kind': 'drug', 'name': 'Eliquis', 'text': 'On this plan list, tier 3.'}]},
]
CHECKED = grounding(tool_outputs=grounding()['tool_outputs'] + CHECK_OUTPUTS)
REPORTED = grounding(person_text=["my heart doctor is dr. rookmere and she takes medicare", "what about my wife Odalys"])

# (name, reply, grounding). Every one of these is a correct reply and must pass whole.
PASSING = [
    ('tool date in other words',
     reply('Your sign-up window opens December 1, 2026 and stays open through June 30, 2027.'), None),
    ('tool date as the end of a month',
     reply('The window tied to your job runs through the end of February 2027, so February 28 is the last day.'), None),
    ('first of the month from a year and month',
     reply('Your Medigap window lasts until the end of August 2027. Part B would start March 1.'), None),
    ('day-first and numeric date wording',
     reply('The job window closes on 28 February 2027 (2/28/2027).'), None),
    ('month and year saved as report fields',
     reply('Since you turn 65 in March 2027, the timing questions come first.'), None),
    ('month the person named',
     reply('You said your last day is in June, so coverage through work could end around June 30.'), None),
    ('date from a fact text',
     reply({'text': 'That fall period runs from October 15 to December 7.', 'fact_ids': ['F-FALL']}), None),
    ('doctor named six turns earlier, by surname',
     reply("Keeping Dr. Rookmere matters, so we will look at how each path treats doctors. "
           "I can note Dr. Rookmere's office at Bay Lantern Cardiology."), None),
    ('medicine typed in lower case',
     reply('You take Eliquis every day, so drug coverage is worth a careful look.'), None),
    ('medicine the person misspelled',
     reply('Your medicines, Eliquis and atorvastatin, both belong on the drug list.'), None),
    ('dollar amount from a fact text',
     reply({'text': 'The example Part B premium is $185 a month.', 'fact_ids': ['F-PREMIUM']}), None),
    ('amount the person typed',
     reply('You mentioned paying about $510 for 60 tablets.'), None),
    ('amount held as cents in a tool output',
     reply('The Corvane Shield Value PPO is listed at $42.50 a month.'), None),
    ('percentages from digits and from words',
     reply({'text': 'In that example the program pays 80% and you pay 20%.', 'fact_ids': ['F-SHARE']}), None),
    ('percent idiom',
     reply("I'm not 100% sure which rule applies yet, so one more detail would help."), None),
    ('helper conversation',
     reply('It sounds like your mom is still working, so her job coverage matters. Does your mom want to keep Dr. Vale?'),
     HELPER),
    ('next step in the process',
     reply('We could look at Original Medicare first, then at Medicare Advantage.'), None),
    ('first-person process suggestions',
     reply("I'd suggest we start with your doctors. I suggest calling Social Security to confirm the date, "
           "and I'd keep that letter handy."), None),
    ('declining to pick',
     reply("I can't recommend a specific plan, but I can lay out how each path works."), None),
    ('ages and small counts',
     reply("You're 65 in the spring, the company has about 20 employees, there are 8 months to go and 12 topics left."),
     None),
    ('plan letter names',
     reply('Plan G and Plan N are two Medigap plan letters. A Medigap Plan G works alongside Original Medicare.'), None),
    ('program terms and plan types',
     reply('A Special Enrollment Period can follow job coverage. A Health Maintenance Organization plan and a '
           'Medicare Advantage plan are both Part C, and Extra Help, COBRA and Medicaid are separate programs. '
           'The Social Security Administration handles sign-up on a Monday in January like any other day.'), None),
    ('insurer and employer the person named',
     reply('Your Harbor Crest plan through Pellworth Tools counts as job coverage.'), None),
    ('plan name from a tool output',
     reply('One listed plan is the Corvane Shield Value PPO.'), None),
    ('insurer abbreviation written out',
     reply('Your UnitedHealthcare plan is the one on your card.'), ALIAS),
    ('family member the person named',
     reply('Your wife Odalys would have her own Medicare, separate from yours.'), None),
    ('capitalised ordinary words and labels',
     reply('**Timing** - Good news: your window is open. Next up: Doctors. '
           'You can see the list on the Plans tab under "Compare Plans".'), None),
    ('mentioning a number Daylight never needs',
     reply("Please don't share your Medicare number here. Daylight never needs your Social Security number. "
           'When you call the plan, give your Medicare number to the agent.'), None),
    ('question with a null target',
     reply('That covers the timing.', question={'target': None, 'text': 'What would you like to look at next?'}),
     None),
    ('question worded freely',
     reply('Thanks, that helps.',
           question={'target': 'T05', 'text': "Roughly how big is the company, give or take - more than 20 people, "
                                              "or a smaller shop? A guess is completely fine."}), None),
    ('no question while paused',
     reply('Take your time. I will be here.', pause=True), None),
    ('long reply with known fact ids',
     reply({'text': 'Here is the longer version. ' + 'Each path handles doctors, medicines and costs differently. ' * 12,
            'fact_ids': ['F-PREMIUM', 'F-SHARE', 'F-FALL']}), None),
    # Near the boundary of each rule added after the independent review.
    ('fact amount written in words',
     reply({'text': 'In that example the Part B premium is one hundred eighty-five dollars a month.',
            'fact_ids': ['F-PREMIUM']}), None),
    ('fact percentages written in words',
     reply({'text': 'In that example you pay twenty percent and the program pays eighty percent.',
            'fact_ids': ['F-SHARE']}), None),
    ('price the person gave without a currency sign',
     reply('You said Odalys pays $45 a month for hers.'), None),
    ('vague amount',
     reply("A gap like that could cost a few hundred dollars a year; I can't put a number on it yet."), None),
    ('month placed by a position word',
     reply('By the end of February your job window closes, and your sign-up window opens in early December.'), None),
    ('quarter that holds a tool date',
     reply('Your Part B would start in Q1 2027.'), None),
    ('check results that are in the tool outputs',
     reply('Dr. Rookmere is in network for the Corvane Shield Value PPO, and Eliquis is on tier 3 there.'), CHECKED),
    ('result the person reported in their own words',
     reply('You said Dr. Rookmere takes Medicare, so Original Medicare keeps her available.'), REPORTED),
    ('named family member who is covered',
     reply('Odalys is covered under your plan through Pellworth Tools for now.'), None),
    ('offering a check without stating its result',
     reply("I can check whether Dr. Rookmere is in network once you pick a plan to look at. "
           "If Eliquis is on a plan's list, the plan sets its tier."), None),
    ('general teaching about coverage',
     reply('Hospital stays are covered under Part A, and a Part D plan covers your prescriptions from its own list. '
           'Most doctors accept Medicare.'), None),
    ('carrier the person named by its short name',
     reply('UnitedHealthcare is the insurer on your card, and UHC is the same company.'), ALIAS),
    ('insurer the person named, as the subject',
     reply('Harbor Crest offers the plan you have through work.'), None),
    ('telling the person to keep a number private',
     reply('Keep your Medicare number private. It is on your red, white and blue card, and Daylight never asks '
           'for the number on your card.'), None),
    ('suggesting where to look first',
     reply('We could look at Original Medicare first, since you put predictable costs first. '
           'My suggestion: Original Medicare first, then Medicare Advantage.'), None),
    ('saying the best plan depends',
     reply("Which plan is best for you depends on your doctors and medicines, and I can't say which is the "
           "right choice for you yet."), None),
    ('framing both paths by a condition',
     reply('Choose Original Medicare if you want any doctor who takes Medicare; choose Medicare Advantage if a '
           'network is fine with you.'), None),
    ('declining to enroll',
     reply("I can't enroll you in a plan; you would do that with the plan or with Medicare."), None),
    ('instruction that a fact text states',
     reply({'text': 'You should sign up for Part B during the sign-up window.', 'fact_ids': ['F-STEP']}), None),
    ('second-person process advice',
     reply("You should have your Medicare card handy when you call Social Security, and you're better off asking "
           "HR for the exact end date."), None),
    ('Medicare Advantage beside a grounded date',
     reply('Medicare Advantage needs both Part A and Part B, and your Part B would start March 1.'), None),
    ('question with grounded content',
     reply('Thanks, that helps.',
           question={'target': 'T07', 'text': 'Your window closes June 30, 2027. Would you rather keep your employer '
                                              'plan until then or switch to Medicare sooner?'}), None),
]


def check(value, ground=None):
    return check_reply(value, grounding=ground or grounding())


class GoodRepliesPass(unittest.TestCase):
    def passes(self, name):
        value, ground = next((item[1], item[2]) for item in PASSING if item[0] == name)
        result = check(value, ground)
        self.assertEqual(result['rejected'], [], name)
        self.assertIsNone(result['question_code'], name)
        self.assertTrue(result['ok'], name)
        self.assertEqual(result['blocks'], value['reply_blocks'])
        self.assertEqual(result['question'], value['question'])

    def test_date_from_tool_output_worded_differently(self):
        self.passes('tool date in other words')
        self.passes('tool date as the end of a month')
        self.passes('first of the month from a year and month')
        self.passes('day-first and numeric date wording')

    def test_dates_from_reports_person_and_facts(self):
        self.passes('month and year saved as report fields')
        self.passes('month the person named')
        self.passes('date from a fact text')

    def test_doctor_named_six_turns_earlier_by_surname(self):
        ground = grounding()
        self.assertIn('rookmere', ground['person_text'][1])
        self.assertGreaterEqual(len(ground['person_text']) - 2, 6)
        self.passes('doctor named six turns earlier, by surname')

    def test_medicine_typed_in_lower_case(self):
        self.passes('medicine typed in lower case')
        self.passes('medicine the person misspelled')

    def test_amounts_from_facts_person_and_tools(self):
        self.passes('dollar amount from a fact text')
        self.passes('amount the person typed')
        self.passes('amount held as cents in a tool output')
        self.passes('percentages from digits and from words')
        self.passes('percent idiom')

    def test_helper_conversation_says_your_mom(self):
        self.passes('helper conversation')

    def test_process_suggestion_is_not_a_personal_pick(self):
        self.passes('next step in the process')
        self.passes('first-person process suggestions')
        self.passes('declining to pick')

    def test_ages_and_small_counts(self):
        self.passes('ages and small counts')

    def test_plan_letters_and_program_terms(self):
        self.passes('plan letter names')
        self.passes('program terms and plan types')

    def test_names_from_person_and_tools(self):
        self.passes('insurer and employer the person named')
        self.passes('plan name from a tool output')
        self.passes('insurer abbreviation written out')
        self.passes('family member the person named')
        self.passes('capitalised ordinary words and labels')

    def test_mentioning_identifiers_without_asking(self):
        self.passes('mentioning a number Daylight never needs')

    def test_question_with_null_target(self):
        self.passes('question with a null target')
        self.passes('no question while paused')

    def test_question_worded_freely(self):
        self.passes('question worded freely')

    def test_length_is_not_judged(self):
        self.passes('long reply with known fact ids')

    def test_amounts_in_words_and_without_a_sign(self):
        self.passes('fact amount written in words')
        self.passes('fact percentages written in words')
        self.passes('price the person gave without a currency sign')
        self.passes('vague amount')

    def test_month_by_position_and_quarter(self):
        self.passes('month placed by a position word')
        self.passes('quarter that holds a tool date')

    def test_check_result_that_is_in_a_tool_output(self):
        self.passes('check results that are in the tool outputs')
        self.passes('result the person reported in their own words')
        self.passes('named family member who is covered')
        self.passes('offering a check without stating its result')
        self.passes('general teaching about coverage')

    def test_carrier_the_person_named(self):
        self.passes('carrier the person named by its short name')
        self.passes('insurer the person named, as the subject')

    def test_keeping_a_number_private(self):
        self.passes('telling the person to keep a number private')

    def test_second_person_wording_that_is_not_a_pick(self):
        self.passes('suggesting where to look first')
        self.passes('saying the best plan depends')
        self.passes('framing both paths by a condition')
        self.passes('declining to enroll')
        self.passes('second-person process advice')
        self.passes('instruction that a fact text states')

    def test_question_and_block_beside_the_held_claim(self):
        self.passes('Medicare Advantage beside a grounded date')
        self.passes('question with grounded content')

    def test_false_rejection_count_is_zero(self):
        failures = []
        for name, value, ground in PASSING:
            result = check(value, ground)
            if not result['ok']:
                failures.append((name, result['rejected'], result['question_code']))
        print('one_call_check false rejections: %d of %d passing examples' % (len(failures), len(PASSING)))
        self.assertEqual(failures, [])

    def test_reply_and_grounding_are_not_changed(self):
        value = reply('Your sign-up window opens December 1, 2026.', 'I recommend Plan G.',
                      question={'target': 'T05', 'text': 'How big is the company?'})
        ground = grounding()
        before = copy.deepcopy((value, ground))
        check(value, ground)
        self.assertEqual((value, ground), before)


class BadRepliesFail(unittest.TestCase):
    def rejected(self, text, code, ground=None, fact_ids=()):
        result = check(reply({'text': text, 'fact_ids': list(fact_ids)}), ground)
        self.assertEqual(result['rejected'], [{'index': 0, 'code': code}], text)
        self.assertEqual(result['blocks'], [])
        self.assertFalse(result['ok'])

    def test_invented_dollar_amount(self):
        self.rejected('The Part B premium is $202.90 a month.', 'ungrounded_amount')
        self.rejected('The drug deductible is $2,100 this year.', 'ungrounded_amount')

    def test_invented_percentage(self):
        self.rejected('The late penalty is 10 percent for each year.', 'ungrounded_amount')
        # A day of the month in a fact text does not ground a percentage.
        self.rejected('You would pay 15% of the cost.', 'ungrounded_amount')

    def test_invented_date(self):
        self.rejected('Your window closes April 15, 2027.', 'ungrounded_date')
        self.rejected('Coverage begins on the 1st of July.', 'ungrounded_date')
        self.rejected('Your Medigap window ends August 15, 2027.', 'ungrounded_date')

    def test_right_day_wrong_year(self):
        self.rejected('Your sign-up window closes June 30, 2028.', 'ungrounded_date')

    def test_invented_doctor(self):
        self.rejected('Dr. Vandermolen is in that network.', 'ungrounded_name')
        self.rejected('Dr. Tobias Rookmere is in that network.', 'ungrounded_name')

    def test_invented_plan_or_insurer(self):
        self.rejected('One listed plan is the Corvane Shield Premier HMO.', 'ungrounded_name')
        self.rejected('A plan from Quillfeather could work in your area.', 'ungrounded_name')

    def test_invented_medicine(self):
        self.rejected('Since you take Eliquis and Zorvatrel, the drug list matters.', 'ungrounded_name')

    def test_personal_pick(self):
        self.rejected("I'd go with Plan G.", 'personal_pick')
        self.rejected('I recommend you enroll in Part B now.', 'personal_pick')
        self.rejected("If I were you, I'd keep your employer plan.", 'personal_pick')
        self.rejected('My recommendation is Medicare Advantage.', 'personal_pick')

    def test_asking_for_the_medicare_number(self):
        self.rejected('What is your Medicare number?', 'identifier_request')
        self.rejected('Could you share your Social Security number so I can look that up?', 'identifier_request')
        self.rejected('To verify, tell me your member ID number.', 'identifier_request')

    def test_unknown_fact_id(self):
        self.rejected('The example Part B premium is $185 a month.', 'unknown_fact_id', fact_ids=['F-PREMIUM', 'F-NOPE'])

    def test_question_asking_for_an_identifier_is_dropped(self):
        value = reply('That covers the timing.', question={'target': None, 'text': "What's your mom's Medicare number?"})
        result = check(value, HELPER)
        self.assertIsNone(result['question'])
        self.assertEqual(result['question_code'], 'identifier_request')
        self.assertEqual(result['blocks'], value['reply_blocks'])
        self.assertFalse(result['ok'])

    def test_question_target_that_is_not_open_is_dropped(self):
        value = reply('That covers the timing.', question={'target': 'T99', 'text': 'How big is the company?'})
        result = check(value)
        self.assertIsNone(result['question'])
        self.assertEqual(result['question_code'], 'target_not_open')
        self.assertEqual(result['rejected'], [])
        self.assertFalse(result['ok'])

    def test_rejected_block_is_removed_whole_and_order_is_kept(self):
        first = {'text': 'Your sign-up window opens December 1, 2026.', 'fact_ids': []}
        bad_amount = {'text': 'That is good news. The premium is $999 a month.', 'fact_ids': []}
        third = {'text': 'Keeping Dr. Rookmere matters here.', 'fact_ids': ['F-FALL']}
        pick = {'text': "I'd go with Plan G.", 'fact_ids': []}
        question = {'target': 'T07', 'text': 'Which matters more to you right now?'}
        result = check(reply(first, bad_amount, third, pick, question=question))
        self.assertEqual(result['blocks'], [first, third])
        self.assertEqual(result['rejected'], [{'index': 1, 'code': 'ungrounded_amount'},
                                              {'index': 3, 'code': 'personal_pick'}])
        self.assertEqual(result['question'], question)
        self.assertIsNone(result['question_code'])
        self.assertFalse(result['ok'])

    def test_model_written_tool_argument_is_not_grounding(self):
        ground = grounding(tool_outputs=[{'name': 'check_doctor', 'arguments': {'name': 'Vandermolen', 'place': ''},
                                          'output': {'ok': False, 'error': 'check_unavailable'}}])
        self.rejected('Dr. Vandermolen is in that network.', 'ungrounded_name', ground)

    def test_malformed_block_is_rejected_without_raising(self):
        result = check({'reply_blocks': [{'text': 7, 'fact_ids': []}, 'loose text'], 'question': None})
        self.assertEqual([item['code'] for item in result['rejected']], ['malformed_block', 'malformed_block'])
        self.assertFalse(result['ok'])


def block_code(text, ground=None):
    result = check(reply(text), ground)
    return result['rejected'][0]['code'] if result['rejected'] else None


def question_code(text, ground=None, target=None):
    result = check(reply('Thanks.', question={'target': target, 'text': text}), ground)
    return result['question_code']


class ReviewFindings(unittest.TestCase):
    """One test per finding of the independent review, in both directions."""

    def codes(self, cases, ground=None):
        for text, code in cases:
            self.assertEqual(block_code(text, ground), code, text)

    # 1. The question gets every check a block gets.
    def test_question_with_invented_content_is_dropped(self):
        value = reply('Thanks.', question={'target': None, 'text': (
            'Shall I enroll you in Humana Gold Plus HMO for $0 a month before July 31, 2027? '
            'You should pick it; it is the best plan for you.')})
        result = check(value)
        self.assertIsNone(result['question'])
        self.assertIn(result['question_code'], ('personal_pick', 'ungrounded_amount', 'ungrounded_date', 'ungrounded_name'))
        self.assertEqual(result['blocks'], value['reply_blocks'])
        self.assertFalse(result['ok'])

    def test_question_reports_the_same_codes_as_a_block(self):
        for text, code in [
                ('Is your premium $999 a month?', 'ungrounded_amount'),
                ('Does April 15, 2027 work as your deadline?', 'ungrounded_date'),
                ('Do you want to keep Dr. Vandermolen?', 'ungrounded_name'),
                ('Dr. Rookmere is in network. Shall we move on?', 'ungrounded_check_claim'),
                ('I think you should pick Plan G. Shall I note that?', 'personal_pick'),
                ('Should I go ahead and enroll you in Plan G?', 'personal_pick'),
                ('Your Medicare Advantage window lasts two months after Part B starts. Does that help?', 'held_claim'),
                ('Could you read me the number on your Medicare card?', 'identifier_request')]:
            self.assertEqual(question_code(text), code, text)
            self.assertEqual(question_code(text, target='T05'), code, text)

    # 2. Advice in the second person.
    SECOND_PERSON = [
        'You should enroll in Medicare Advantage.',
        'The best plan for you is Medicare Advantage.',
        'You should go with Original Medicare and a Medigap policy.',
        'Plan G is the right choice for you.',
        "You're better off with a Medigap plan.",
        'Based on what you told me, Medigap Plan G is your best option.',
        'Go with Plan N.',
        'Honestly, Plan G is the one to get.',
        'Your best match is WellCare Value Script.',
        'Many people in your county pick Humana Gold Plus.',
    ]

    def test_second_person_advice_is_a_personal_pick(self):
        for text in self.SECOND_PERSON:
            self.assertEqual(block_code(text), 'personal_pick', text)
            self.assertEqual(question_code(text), 'personal_pick', text)

    def test_offer_to_enroll_is_a_personal_pick(self):
        self.codes([('Shall I enroll you in Plan G?', 'personal_pick'),
                    ('Want me to sign you up for the Corvane Shield Value PPO?', 'personal_pick')])

    def test_part_b_instruction_needs_the_same_instruction_in_the_grounding(self):
        text = 'You should sign up for Part B right away.'
        self.assertEqual(block_code(text), 'personal_pick')
        facts = dict(grounding()['fact_texts'], **{'F-NOW': 'In this example you should sign up for Part B right away.'})
        self.assertIsNone(block_code(text, grounding(fact_texts=facts)))

    # 3. Amounts without a sign, and money grounded only by money.
    def test_amounts_in_words_and_currency_codes(self):
        self.codes([('The deductible is USD 257 this year.', 'ungrounded_amount'),
                    ('The deductible is two hundred fifty-seven dollars.', 'ungrounded_amount'),
                    ("You'd pay about 240 bucks a month.", 'ungrounded_amount'),
                    ('Your penalty would be ten percent for each year you waited.', 'ungrounded_amount')])

    def test_count_does_not_ground_a_percentage(self):
        # "about 20 employees" is in the visit; no fact text here holds 20 as a percentage.
        facts = {key: text for key, text in grounding()['fact_texts'].items() if key != 'F-SHARE'}
        self.assertEqual(block_code('Coinsurance is 20 percent after that.', grounding(fact_texts=facts)),
                         'ungrounded_amount')

    def test_age_count_and_zip_do_not_ground_money(self):
        ground = grounding(
            person_text=["i turn 65 next spring", "about 20 employees i think", "i work 35 hours a week"],
            reports=[{'id': 'T03', 'label': 'ZIP', 'state': 'answered', 'value': {'zip': '34102', 'county': 'Collier'}},
                     {'id': 'guide.situation.age65', 'value': {'year': 2027, 'month': 3}, 'status': 'reported'}])
        self.codes([('That would be $65 a month.', 'ungrounded_amount'),
                    ('Your premium is $35 a month.', 'ungrounded_amount'),
                    ('The fee is $20.', 'ungrounded_amount'),
                    ('It costs $34,102 a year.', 'ungrounded_amount'),
                    ('That comes to $2,027.', 'ungrounded_amount'),
                    ('The example premium is $185 a month.', None)], ground)

    # 4. Dates by position.
    def test_month_by_position_and_quarter_need_grounding(self):
        self.codes([('Your window closes at the end of July.', 'ungrounded_date'),
                    ('Your coverage begins the first of April.', 'ungrounded_date'),
                    ('You have until mid-September to enroll.', 'ungrounded_date'),
                    ('Your coverage starts in Q3 2028.', 'ungrounded_date'),
                    ('Your coverage starts in the second quarter of 2029.', 'ungrounded_date')])

    # 5. Names and check results.
    def test_doctor_cue_in_any_case_and_spelled_out(self):
        self.codes([('I see doctor Whitfield is covered.', 'ungrounded_name'),
                    ('DR. WHITFIELD IS IN NETWORK.', 'ungrounded_name'),
                    ('dr. whitfield is in network.', 'ungrounded_name')])
        # The person's own doctor passes the name check in every spelling.
        for text in ('Keeping doctor Rookmere matters to you.', 'KEEPING DR. ROOKMERE MATTERS TO YOU.',
                     'keeping dr. rookmere matters to you.'):
            self.assertIsNone(block_code(text), text)

    def test_insurer_names(self):
        self.codes([('Cigna offers a plan in Collier County.', 'ungrounded_name'),
                    ('You could look at UnitedHealthcare or Kaiser.', 'ungrounded_name'),
                    ('you could look at united healthcare.', 'ungrounded_name'),
                    ('BCBS is another one.', 'ungrounded_name'),
                    ("Quillfeather's network is narrow.", 'ungrounded_name')])

    CHECK_CLAIMS = [
        'HUMANA GOLD PLUS covers your doctor.',
        'humana gold plus covers your doctor.',
        'Your medicine lisinopril is on tier 1.',
        'Lisinopril is covered on every plan.',
        'ELIQUIS is covered with a low copay.',
        'eliquis is covered with a low copay.',
        'Dr. Rookmere is in network.',
        'Dr. Rookmere accepts Medicare.',
        'Your doctor is in network for that plan.',
        'Your medicines are covered.',
        'That plan covers your medicines.',
    ]

    def test_check_result_claim_needs_a_check_result(self):
        for text in self.CHECK_CLAIMS:
            self.assertEqual(block_code(text), 'ungrounded_check_claim', text)

    def test_check_result_claim_passes_with_the_check_result(self):
        self.codes([('Dr. Rookmere is in network.', None),
                    ('Your doctor is in network for that plan.', None),
                    ('Eliquis is covered on that plan.', None),
                    ('Eliquis is on tier 3.', None),
                    # A result for one medicine does not support a claim about another.
                    ('atorvastatin is covered.', 'ungrounded_check_claim')], CHECKED)

    def test_reported_result_supports_only_the_same_kind_of_result(self):
        # The person said she takes Medicare; nobody said she is in a plan's network.
        self.assertEqual(block_code('Dr. Rookmere is in network.', REPORTED), 'ungrounded_check_claim')

    def test_failed_or_empty_check_supports_nothing(self):
        outputs = [{'name': 'check_doctor', 'arguments': {'name': 'Rookmere', 'place': ''},
                    'output': {'ok': False, 'error': 'check_unavailable'}},
                   {'ok': True, 'kind': 'doctor', 'name': 'Dr. Anneliese Rookmere', 'status': 'needs_detail',
                    'results': [], 'needs': {'kind': 'plan'}}]
        self.assertEqual(block_code('Dr. Rookmere is in network.', grounding(tool_outputs=outputs)),
                         'ungrounded_check_claim')

    # 6. Indirect identifier requests.
    def test_indirect_identifier_requests(self):
        self.codes([(text, 'identifier_request') for text in (
            'Could you read me the number on your red, white and blue card?',
            'What are the digits on your Medicare card?',
            "To look that up I'll need the eleven characters on your Medicare card.",
            'What is your date of birth and your Medicare ID?',
            "Share your MBI when you're ready.",
            'Go ahead and tell me your Social.')])

    # 7. The held claim.
    def test_held_claim_is_rejected_on_every_surface(self):
        self.codes([('Since you added Part B after Part A, your Medicare Advantage window lasts two months '
                     'after Part B starts.', 'held_claim')])


# The reviewer's own case list and visit, kept whole as a regression test. The
# fact texts are fixture wording for these cases, not a source of Medicare facts.
REVIEW_GROUNDING = {
    'person_text': ["I turn 65 in March 2027. My doctor is Dr. Alvarez at Bayside Clinic and I take metformin 500 mg. "
                    "I have Aetna through my job.", "my wife pays 45 dollars for hers"],
    'reports': {'coverage_is_for': 'self', 'states': {}, 'saved': [
        {'id': 'T03', 'label': 'ZIP', 'state': 'answered', 'value': {'zip': '34102', 'county': 'Collier'}}]},
    'tool_outputs': [{'name': 'get_signup_dates', 'arguments': {}, 'output': {
        'ok': True, 'today': '2026-11-21',
        'signup_window': {'start': '2026-12-01', 'end': '2027-06-30', 'phase': 'before',
                          'basis': 'Estimated by code from the reported 65th-birthday month.'},
        'part_b_start': {'date': '2027-03-01', 'basis': 'x'},
        'medigap_window': {'start': '2027-03-01', 'end': '2027-08-31'}}}],
    'fact_texts': {
        'X-PARTB': 'Most people pay $202.90 a month for Part B in 2026; people with higher incomes pay more.',
        'X-INSULIN': 'A Medicare drug plan charges no more than $35 for a one-month supply of each insulin it covers.',
        'X-GENERAL': 'The General Enrollment Period runs from January 1 to March 31 each year.',
        'X-FALL': 'Medicare Open Enrollment runs from October 15 to December 7 each year.',
        'X-MEDIGAP': 'The federal Medigap Open Enrollment Period lasts six months.',
        'X-JOB': 'If the employer has 20 or more employees, that job coverage pays first; a Special Enrollment '
                 'Period covers the 8 months that follow.',
        'X-PENALTY': 'The penalty is about 1% of the national base premium for each month without coverage.',
        'X-BOTH': 'Medicare Advantage requires both Part A and Part B.',
    },
    'open_ids': {'T05', 'T06'},
}
REVIEW_BAD = [
    ('Your Part B premium will be $185 a month.', 'ungrounded_amount'),
    ('That plan costs 185 dollars each month.', 'ungrounded_amount'),
    ('The plan has a $0 premium and a $3,400 out-of-pocket limit.', 'ungrounded_amount'),
    ('The deductible is USD 257 this year.', 'ungrounded_amount'),
    ('The deductible is two hundred fifty-seven dollars.', 'ungrounded_amount'),
    ("You'd pay about 240 bucks a month.", 'ungrounded_amount'),
    ('Coinsurance is 20 percent after that.', 'ungrounded_amount'),
    ('Your penalty would be ten percent for each year you waited.', 'ungrounded_amount'),
    ('Your Part B starts on April 1, 2027.', 'ungrounded_date'),
    ('Your window closes 7/31/2027.', 'ungrounded_date'),
    ('Your window closes on the 31st of July.', 'ungrounded_date'),
    ('Your window closes at the end of July.', 'ungrounded_date'),
    ('Your coverage begins the first of April.', 'ungrounded_date'),
    ('Sign up by 2027-07-31 to avoid a gap.', 'ungrounded_date'),
    ('You have until mid-September to enroll.', 'ungrounded_date'),
    ('Your window closes July 31st, 2027.', 'ungrounded_date'),
    ('Your coverage would start 1 April 2027.', 'ungrounded_date'),
    ('Dr. Patel is in the network for that plan.', 'ungrounded_name'),
    ('Your doctor, Dr Susan Whitfield, accepts Medicare.', 'ungrounded_name'),
    ('I see doctor Whitfield is covered.', 'ungrounded_name'),
    ('DR. WHITFIELD IS IN NETWORK.', 'ungrounded_name'),
    ('dr. whitfield is in network.', 'ungrounded_name'),
    ('The Humana Gold Plus plan covers your doctor.', 'ungrounded_name'),
    ('HUMANA GOLD PLUS covers your doctor.', 'ungrounded_check_claim'),
    ('humana gold plus covers your doctor.', 'ungrounded_check_claim'),
    ('Many people in your county pick Humana Gold Plus.', 'personal_pick'),
    ('Your best match is WellCare Value Script.', 'personal_pick'),
    ('Cigna offers a plan in Collier County.', 'ungrounded_name'),
    ('You could look at UnitedHealthcare or Kaiser.', 'ungrounded_name'),
    ('Your medicine lisinopril is on tier 1.', 'ungrounded_check_claim'),
    ('Lisinopril is covered on every plan.', 'ungrounded_check_claim'),
    ('ELIQUIS is covered with a low copay.', 'ungrounded_check_claim'),
    ('eliquis is covered with a low copay.', 'ungrounded_check_claim'),
    ('Since you take Eliquis, drug coverage matters.', 'ungrounded_name'),
    ('You should enroll in Medicare Advantage.', 'personal_pick'),
    ('The best plan for you is Medicare Advantage.', 'personal_pick'),
    ('You should go with Original Medicare and a Medigap policy.', 'personal_pick'),
    ('Plan G is the right choice for you.', 'personal_pick'),
    ("You're better off with a Medigap plan.", 'personal_pick'),
    ('Based on what you told me, Medigap Plan G is your best option.', 'personal_pick'),
    ("If I were in your shoes, I'd pick the Advantage plan.", 'personal_pick'),
    ('My recommendation is Plan G.', 'personal_pick'),
    ('I recommend Plan G.', 'personal_pick'),
    ('Go with Plan N.', 'personal_pick'),
    ('Honestly, Plan G is the one to get.', 'personal_pick'),
    ('You should sign up for Part B right away.', 'personal_pick'),
    ('Could you read me the number on your red, white and blue card?', 'identifier_request'),
    ('What are the digits on your Medicare card?', 'identifier_request'),
    ("To look that up I'll need the eleven characters on your Medicare card.", 'identifier_request'),
    ('Please type your SSN so I can check.', 'identifier_request'),
    ("What's your Social Security number?", 'identifier_request'),
    ('Can you tell me the last four of your social?', 'identifier_request'),
    ('What is your date of birth and your Medicare ID?', 'identifier_request'),
    ("Share your MBI when you're ready.", 'identifier_request'),
    ('Go ahead and tell me your Social.', 'identifier_request'),
    ("I'll need your member ID from the Aetna card.", 'identifier_request'),
    ('Your Part B penalty is 10% for every 12 months.', 'ungrounded_amount'),
    ('Your Medicare Advantage window lasts two months after Part B starts.', 'held_claim'),
]
# Replies on the reviewer's "should be rejected" list that still pass, and why.
# The check matches values; it does not bind a value to what it measures.
REVIEW_STILL_PASSES = [
    # $35 is money in a fact text (about insulin). With no such fact it is rejected:
    # see test_age_count_and_zip_do_not_ground_money.
    'Your premium is $35 a month.',
    # December 7 is in a fact text.
    'The deadline is Dec. 7.',
    'Open enrollment ends December 7.',
    # The sign-up window in the tool output ends in June 2027, which is in that quarter.
    'Your coverage starts in Q2 2027.',
    # Durations are not checked, and this one is in a fact text.
    'You have 8 months after the job ends to sign up.',
]
REVIEW_GOOD = [
    'Your sign-up window opens December 1, 2026 and closes June 30, 2027.',
    'Your window runs from Dec 1, 2026 through the end of June 2027.',
    'If you sign up before March, Part B would start March 1, 2027.',
    'Part B would begin on 3/1/2027.',
    'Part B would begin on the 1st of March 2027.',
    'Your Medigap window would run from March 1 to August 31, 2027.',
    'You mentioned Dr. Alvarez at Bayside Clinic; I can check on that.',
    'You said you take metformin 500 mg.',
    'You told me you have Aetna through your job.',
    "You said your wife pays $45 for hers; I can't confirm that amount.",
    'You said you turn 65 in March 2027.',
    'Most people pay $202.90 a month for Part B in 2026.',
    'A Medicare drug plan charges no more than $35 for a one-month supply of each insulin it covers.',
    'The General Enrollment Period runs January 1 through March 31 each year.',
    'The General Enrollment Period runs from Jan. 1 to Mar. 31 every year.',
    'Medicare Advantage requires both Part A and Part B.',
    "I can't choose for you, but I can lay out how Original Medicare and Medicare Advantage differ.",
    "You don't need to share your Medicare number with me; keep it private.",
    'Social Security may ask for your Social Security number when you apply; I never need it.',
    "I'd suggest we look at your doctors next.",
    'You may 1) call Social Security or 2) apply online.',
    "I'm 100% sure that's worth checking.",
    "You're in Collier County, ZIP 34102.",
    'The Medigap Open Enrollment Period lasts six months.',
    'You should have your Medicare card handy when you call Social Security.',
    'Today is November 21, 2026.',
    'Aetna is the insurer you mentioned for your job plan.',
    'Your sign-up window opens in December.',
    "Your wife's plan and your own Aetna plan are separate.",
    'I recommend calling Social Security to confirm the date.',
    'A good next step would be to sign up for Part B through Social Security.',
    "Mr. Alvarez's office can confirm whether they take Medicare.",
]
REVIEW_QUESTIONS = [
    ({'target': None, 'text': 'Would you like to enroll in Humana Gold Plus for $0 a month before July 31, 2027?'},
     'ungrounded_amount'),
    ({'target': None, 'text': 'I think you should pick Plan G. Shall I note that?'}, 'personal_pick'),
    ({'target': 'T05', 'text': 'Should I go ahead and enroll you in Plan G?'}, 'personal_pick'),
    ({'target': 'RC99', 'text': 'What coverage do you have now?'}, 'target_not_open'),
    ({'target': None, 'text': 'Could you read me the number on your Medicare card?'}, 'identifier_request'),
    ({'target': 'T05', 'text': 'What coverage do you have now?'}, None),
]


class ReviewerCases(unittest.TestCase):
    def test_bad_replies_are_rejected(self):
        self.assertEqual(len(REVIEW_BAD) + len(REVIEW_STILL_PASSES), 63)
        for text, code in REVIEW_BAD:
            self.assertEqual(block_code(text, REVIEW_GROUNDING), code, text)

    def test_replies_that_still_pass_are_the_documented_ones(self):
        for text in REVIEW_STILL_PASSES:
            self.assertIsNone(block_code(text, REVIEW_GROUNDING), text)

    def test_good_replies_pass(self):
        failures = [(text, block_code(text, REVIEW_GROUNDING)) for text in REVIEW_GOOD
                    if block_code(text, REVIEW_GROUNDING)]
        print('one_call_check false rejections: %d of %d reviewer good replies' % (len(failures), len(REVIEW_GOOD)))
        self.assertEqual(failures, [])

    def test_questions(self):
        for question, code in REVIEW_QUESTIONS:
            result = check(reply('Thanks.', question=question), REVIEW_GROUNDING)
            self.assertEqual(result['question_code'], code, question['text'])
            self.assertEqual(result['question'], None if code else question)
            self.assertEqual(result['blocks'], [{'text': 'Thanks.', 'fact_ids': []}])


if __name__ == '__main__':
    unittest.main()
