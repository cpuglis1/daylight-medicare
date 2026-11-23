"""Regressions from the owner's first live visit on port 8897 (2026-11-22).

Offline: a scripted model, a temporary budget ledger, sockets forbidden and
fictional people. Each test fixes in place what code now does at a point where
that visit went wrong: getting to plans, the doctor and medicine picker, the
fallback after a doctor was typed, confirmations, the goal question, the turn
trace and the reasoning setting. They say nothing about a live model's wording.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

import conversation_planner
import journey_completion
import plan_review

import _one_call_support as support
from _one_call_support import Script, Visit, call, message, reply, save, update
import one_call_flow
import one_call_prompt
import one_call_tools
from sim import cost

VARIANT = Path(__file__).resolve().parents[1]
CLOSE_NOTE = '[Shown on screen: the step to review the saved information and see plans]'
# One message that reports everything advisor-first's plan checklist asks for, less the priorities.
ALMOST = ("It's for me. I'm in 34102 and I want to find coverage. I have Part A and Part B and no other insurance. "
          'I see Dr. Nera Vale. I take no prescriptions. I stay local and I want lower monthly payments.')
ALMOST_UPDATES = (
    update('RC01', {'choice': 'self'}, "It's for me"), update('T03', {'zip': '34102'}, "I'm in 34102"),
    update('T01', {'choice': 'compare'}, 'I want to find coverage'), update('RC04', {'choice': 'both'}, 'I have Part A and Part B'),
    update('T05', {'choice': 'none'}, 'no other insurance'), update('T06', {'text': 'Dr. Nera Vale'}, 'I see Dr. Nera Vale'),
    update('T07', {'choice': 'no'}, 'I take no prescriptions'), update('T08', {'choice': 'local'}, 'I stay local'),
    update('T09', {'choice': 'lower_monthly'}, 'I want lower monthly payments'))
LAST = 'Total cost matters most to me.'
LAST_UPDATE = update('T10', {'choice': 'total_cost'}, 'Total cost matters most')


@unittest.skipUnless(support.READY, support.NOT_READY)
class Case(unittest.TestCase):
    checks = False

    def setUp(self):
        support.offline(self)
        support.pin_today(self)
        self.script = Script()
        self.flow = support.make_flow(self.script)
        self.budget = support.temporary_ledger(self, self.flow.agent)
        if self.checks and not support.attach_fictional_checks(self.flow):
            self.skipTest('advisor-first offline check fixtures could not be loaded')
        self.visit = Visit(self, self.flow, self.script)
        self.visit.start()

    def one(self, out):
        return out['metrics']['oneCall']

    def close(self, out):
        return bool((out.get('comparisonClose') or {}).get('show'))

    def almost_ready(self):
        return self.visit.say(ALMOST, [save(*ALMOST_UPDATES)],
                              [message(reply('Thank you.', question='What matters most when we compare your options?',
                                             target='T10'))])

    def ready(self, *blocks, question=None):
        self.almost_ready()
        return self.visit.say(LAST, [save(LAST_UPDATE)], [message(reply(*(blocks or ('Thank you.',)), question=question))])

    def handed_over(self, out):
        """The turn ended on advisor-first's close, with its one button and nothing else to answer."""
        self.assertTrue(self.close(out))
        self.assertTrue(out['comparisonClose']['ready'])
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'plan_review'})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertIsNone((out.get('conversationCheck') or {}).get('question'))
        self.assertTrue(self.one(out)['plansHandoff'])


class PlansHandoff(Case):
    def test_offer_plans_on_a_ready_profile_ends_the_turn_on_advisor_firsts_review_step(self):
        self.ready()
        self.visit.say('Tell me about premiums.', [message(reply('Here is the general idea.', question='Shall we go on?'))])
        out = self.visit.say('Can I just see the plans?', [call('p1', 'offer_plans', {})],
                             [message(reply('Here is the step to review your details and see plans.',
                                            'A second block the lead-in does not need.',
                                            question='Would you like to look at your doctor first?'))])
        self.handed_over(out)
        self.assertEqual(out['reply'], 'Here is the step to review your details and see plans.')    # the first block only
        self.assertEqual((self.one(out)['questionDelivery'], self.one(out)['plansAsked']), ('plans_handoff', True))
        self.assertEqual(self.visit.transcript()[-1]['text'].split('\n\n')[-1], CLOSE_NOTE)
        # The one button leads through advisor-first's own review to the Plans page.
        review = self.visit.tap({'type': 'review_plans'})['review']
        self.assertEqual((review['kind'], review['label']), ('plan_profile', 'See plans'))
        handoff = self.visit.tap({'type': 'confirm_plan_review', 'token': review['token']})['plansHandoff']
        self.assertEqual((handoff['destination'], handoff['reportedInfoReviewed']), ('plans', True))

    def test_offer_plans_before_the_profile_is_ready_returns_only_what_is_missing(self):
        self.almost_ready()
        out = self.visit.say('Can I see plans now?', [call('p1', 'offer_plans', {})],
                             [message(reply('One detail comes first.', question='What matters most?', target='T10'))])
        result = json.loads(self.script.sent[-1]['input'][-1]['output'])
        self.assertEqual(result, {'ok': True, 'ready': False, 'missing': [{'id': 'T10', 'label': 'What matters most'}]})
        self.assertFalse(self.close(out))
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T10')
        self.assertEqual((self.one(out)['plansAsked'], self.one(out)['plansHandoff']), (True, False))
        # The request is remembered: once the detail is in, the step appears without another tool call.
        out = self.visit.say(LAST, [save(LAST_UPDATE)],
                             [message(reply('Thank you.', question='Is there anything else you want me to know?'))])
        self.handed_over(out)
        self.assertEqual(out['reply'], 'Thank you.')
        self.assertFalse(self.flow.one_call_visits.read(self.visit.owner, self.visit.chain, support.CONTEXT_POLICY)['plans_asked'])

    def test_offer_plans_with_no_goal_saved_names_the_goal(self):
        runner = one_call_tools.ToolRunner(self.flow, self.visit.owner, self.visit.guide, self.visit.record, 'Show me plans.',
                                           today=support.TODAY)
        out = runner.run('offer_plans', {})
        # Asking for plans is a request for coverage work: the goal is saved as finding coverage,
        # and what is still missing is named against that goal's checklist.
        self.assertEqual((out['ok'], out['ready']), (True, False))
        self.assertNotIn('T01', [item['id'] for item in out['missing']])
        self.assertEqual(out['missing'][0], {'id': 'RC01', 'label': 'Who the coverage is for'})
        self.assertEqual(self.flow.value(runner.guide, 'intent.goal'), 'compare')
        self.assertIn({'id': 'T01', 'entity': 'profile', 'fields': {'choice': 'compare'}}, runner.saved)
        self.assertEqual((runner.plans_requested, runner.plans_offered), (True, False))
        self.assertEqual(runner.run('offer_plans', {'now': True}), {'ok': False, 'error': 'bad_arguments'})

    def test_the_step_appears_when_the_profile_becomes_ready_even_if_the_model_asks_a_question(self):
        # The cause of the silent close: a question the model worded outranked the close in
        # advisor-first's delivery step, which then withdrew it, on every turn the model asked one.
        out = self.ready('We will use that.', 'A second block.',
                         question='Would you like to start by looking at whether your doctor participates?')
        self.handed_over(out)
        self.assertEqual(out['reply'], 'We will use that.\n\nA second block.')      # no tool call, so the whole reply stays
        self.assertNotIn('whether your doctor participates', json.dumps(out))
        self.assertEqual(self.script.sent[-1]['tool_choice'], 'none')
        self.assertFalse(any(item['name'] == 'offer_plans' for payload in self.script.sent
                             for item in payload['input'] if isinstance(item, dict) and item.get('type') == 'function_call'))
        # Shown once for these details; an ordinary turn afterwards is an ordinary turn.
        out = self.visit.say('What is a premium?', [message(reply('A general answer.', question='Shall we go on?'))])
        self.assertFalse(self.close(out))
        self.assertEqual(out['conversationNext']['kind'], 'clarification')

    def test_the_step_appears_on_the_fallback_too(self):
        self.almost_ready()
        out = self.visit.say(LAST, [save(LAST_UPDATE)], [message('not the reply format')], [message('still not the reply format')])
        self.assertTrue(self.one(out)['fallback'])
        self.handed_over(out)

    def test_a_detail_advisor_first_asks_before_the_close_is_asked_by_code_and_then_gives_way(self):
        self.visit.given_profile_permission()
        # Predictable costs and doctors first: advisor-first asks the Medigap price details before its close.
        said = ALMOST.replace('lower monthly payments', 'predictable costs') + ' My doctors matter most.'
        updates = [item for item in ALMOST_UPDATES if item['id'] != 'T09'] + [
            update('T09', {'choice': 'predictable'}, 'I want predictable costs'),
            update('T10', {'choice': 'doctors'}, 'My doctors matter most')]
        out = self.visit.say(said, [save(*updates)], [message(reply('Thank you.', question='Anything else?'))])
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertFalse(self.close(out))
        first = out['assessment']['nextQuestion']['id']
        self.assertIn(first, ('MG_AGE', 'MG_SEX', 'MG_TOBACCO'))
        self.assertEqual(self.one(out)['questionDelivery'], 'pre_close')
        self.assertNotIn('Anything else?', out['reply'])
        # Asking for plans sets those details aside for the visit: the Plans page asks for them.
        out = self.visit.say('Please just show me the plans.', [call('p1', 'offer_plans', {})],
                             [message(reply('Here is the step to see your plans.'))])
        self.handed_over(out)
        self.assertIn(first, conversation_planner.state(self.flow, self.visit.owner)['deferred'])

    def test_an_unanswered_detail_before_the_close_stops_being_asked(self):
        self.visit.given_profile_permission()
        said = ALMOST.replace('lower monthly payments', 'predictable costs') + ' My doctors matter most.'
        updates = [item for item in ALMOST_UPDATES if item['id'] != 'T09'] + [
            update('T09', {'choice': 'predictable'}, 'I want predictable costs'),
            update('T10', {'choice': 'doctors'}, 'My doctors matter most')]
        out = self.visit.say(said, [save(*updates)], [message(reply('Thank you.'))])
        turns = 0
        while not self.close(out) and turns < 16:
            turns += 1
            out = self.visit.say('What is a premium?', [message(reply('A general answer.'))])
        self.handed_over(out)

    def test_plan_status_gives_the_model_nothing_it_cannot_show(self):
        def engine(inputs, *, checks, expected_doctors, reported):
            tab = {'state': 'ready', 'recommended_ids': [], 'no_pick_reason': 'personal_checks_remain',
                   'message': 'Available options · personal checks remain',
                   'groups': [{'id': 'available', 'label': 'Available options · personal checks remain',
                               'ids': ['FICTIONAL-%d' % number for number in range(29)]}]}
            return {'method': 'fictional', 'evaluation_only': True, 'path': tab, 'advantage': tab, 'medigap': tab, 'part_d': tab}
        self.flow.one_call_recommendation = engine
        self.ready()
        self.visit.say('What is the result?', [call('s1', 'get_plan_status', {})], [message(reply('Here is where things stand.'))])
        sent = self.script.sent[-1]['input'][-1]['output']
        result = json.loads(sent)
        self.assertTrue(result['plan_review']['can_review'])
        self.assertEqual(result['recommendation']['advantage'],
                         {'state': 'ready', 'recommended_ids': [], 'no_pick_reason': 'personal_checks_remain'})
        for unshowable in ('Available options', '29', 'FICTIONAL', '"count"', '"label"', '"groups"', '"message"'):
            self.assertNotIn(unshowable, sent)

    def test_the_instructions_say_how_a_person_gets_to_plans_and_stay_byte_stable(self):
        core = (VARIANT / 'prompt/core.md').read_text()
        for sentence in ('Never describe, name or count the plans on a list.',
                         'Never ask the person to bring or share plan documents, benefit summaries or plan names.',
                         'call `offer_plans` in that turn', '`offer_plans` is how the person gets to their plans.',
                         'never ask what they want help with once they have told you'):
            self.assertIn(sentence, core)
        closing = (VARIANT / 'prompt/playbooks/closing-and-handoff.md').read_text()
        self.assertIn('call `offer_plans` and let code decide', closing)
        self.assertIn('never ask the person to bring plan documents or benefit summaries', closing)
        first = one_call_prompt.static_instructions(self.flow)
        self.ready()
        self.assertEqual(one_call_prompt.static_instructions(self.flow), first)
        self.assertEqual({payload['instructions'] for payload in self.script.sent}, {first})
        self.assertIn('offer_plans', [tool['name'] for tool in self.script.sent[0]['tools']])


class ChecksDoNotBlockPlans(Case):
    checks = True

    def test_readiness_never_reads_a_check_result(self):
        self.ready()
        runner = one_call_tools.ToolRunner(self.flow, self.visit.owner, self.visit.guide, self.visit.record, 'Hello.',
                                           today=support.TODAY)
        with_checks = runner.plans_readiness()
        self.flow.conversation_checks = None
        self.assertEqual(runner.plans_readiness(), with_checks)
        self.assertTrue(with_checks['canReview'])
        # advisor-first lists the open checks as holds to show; they are not among what is missing.
        self.assertIn('DOCTOR_CHECKS_OPEN', [hold['code'] for hold in with_checks['holds']])
        self.assertEqual(with_checks['missing'], [])
        self.assertEqual(with_checks, journey_completion.reviewed_status(self.flow, self.visit.owner, self.visit.guide,
                                                                         self.visit.record))
        self.assertTrue(plan_review.readiness(self.visit.guide, self.visit.record)['canReview'])

    def test_an_open_doctor_picker_does_not_hold_back_a_person_who_asked_for_plans(self):
        out = self.almost_ready()
        self.assertEqual(out['conversationCheck']['question']['kind'], 'doctor')        # the picker is open
        out = self.visit.say(LAST + ' Can I see the plans?', [save(LAST_UPDATE), call('p1', 'offer_plans', {})],
                             [message(reply('Here is the step to see your plans.'))])
        self.handed_over(out)
        review = self.visit.tap({'type': 'review_plans'})['review']
        self.assertIn('DOCTOR_CHECKS_OPEN', [hold['code'] for hold in review['readiness']['holds']])
        self.assertEqual(self.visit.tap({'type': 'confirm_plan_review', 'token': review['token']})['plansHandoff']['destination'],
                         'plans')


class DoctorAndMedicinePicker(Case):
    checks = True

    def start_visit(self):
        said = "It's for me. I'm in 34102 and I want to find coverage."
        return self.visit.say(said, [save(update('RC01', {'choice': 'self'}, "It's for me"),
                                          update('T03', {'zip': '34102'}, "I'm in 34102"),
                                          update('T01', {'choice': 'compare'}, 'I want to find coverage'))],
                              [message(reply('Thank you.', question='Are there doctors you want to keep?', target='T06'))])

    def test_the_picker_arrives_on_the_turn_the_doctor_is_typed(self):
        self.start_visit()
        said = 'Dr. Nera Vale, at her office in Naples'
        out = self.visit.say(said, [save(update('T06', {'text': 'Dr. Nera Vale'}, said))],
                             [message(reply('I have noted Dr. Nera Vale.', question='Now, shall we list your medicines?',
                                            target='T07'))])
        self.assertEqual(len(self.script.sent), 4)                  # the model never called check_doctor
        picker = out['conversationCheck']['question']
        self.assertEqual((picker['kind'], picker['item'], picker['question']), ('doctor', 'doctor-1', 'Which of these is Dr. Nera Vale?'))
        self.assertEqual(picker['choices'][0], {'value': 'Nera0', 'label': 'Dr. Nera Vale — 1 Test Lane, Naples, FL, 34103'})
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'check'})
        self.assertIsNone(out['assessment']['nextQuestion'])        # the picker replaced the model's question
        self.assertNotIn('shall we list your medicines', json.dumps(out))
        self.assertEqual(out['reply'], 'I have noted Dr. Nera Vale.')
        self.assertEqual(self.visit.value('needs.providers'), 'Dr. Nera Vale')
        self.assertEqual(self.visit.transcript()[-1]['text'], 'I have noted Dr. Nera Vale.\n\nWhich of these is Dr. Nera Vale?')
        # The pick itself is advisor-first's own button path.
        picked = self.visit.tap({'type': 'check_answer', 'token': picker['token'], 'value': 'Nera0'})
        self.assertNotEqual((picked['conversationCheck'].get('question') or {}).get('question'), picker['question'])

    def test_only_a_visible_invitation_can_authorize_intake_after_a_doctor_lookup(self):
        self.start_visit()
        out = self.visit.say('Can you look up Dr. Nera Vale?', [save(update('T06', {'text': 'Dr. Nera Vale'}, 'Dr. Nera Vale'))],
            [message(reply('I can look her up.', question='May I ask about your coverage?', detail_step='invite'))])
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'check'})
        self.assertNotIn('May I ask about your coverage?', out['reply'])
        self.assertEqual(self.flow.one_call_visits.read(self.visit.owner, self.visit.chain,
                         support.CONTEXT_POLICY)['detail_permission'], 'open')
        q = out['conversationCheck']['question']
        out = self.visit.tap({'type': 'check_answer', 'token': q['token'], 'value': 'Nera0'})
        self.assertTrue(out['conversationCheck']['results'])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['conversationNext'], {'kind': 'clarification', 'question': one_call_flow.DETAIL_INVITATION})
        self.assertIsNone(one_call_flow.ensure_state(out['record'])['dialogue']['lastTarget'])
        out = self.visit.say('Yes, go ahead.', [message(reply('Of course.', question='What coverage do you have?',
            target='T05', detail_step='agree'))])
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'T05'})

    def start_without_a_compare_goal(self, goal=None):
        said = "It's for me. I'm in 34102 and I don't know where to start."
        updates = [update('RC01', {'choice': 'self'}, "It's for me"), update('T03', {'zip': '34102'}, "I'm in 34102")]
        if goal:
            updates.append(update('T01', {'choice': goal}, "I don't know where to start"))
        return self.visit.say(said, [save(*updates)],
                              [message(reply('Thank you.', question='Are there doctors you want to keep?', target='T06'))])

    def test_the_picker_does_not_depend_on_the_saved_goal(self):
        # Owner's visit, November 22, 2026: the goal had been saved as something other than
        # "compare", which left advisor-first's planner outside working mode, and its picker
        # (and its close) stayed off for the whole visit.
        for goal in (None, 'learn'):
            with self.subTest(goal=goal):
                self.setUp()
                self.start_without_a_compare_goal(goal)
                said = 'Dr. Nera Vale, at her office in Naples'
                out = self.visit.say(said, [save(update('T06', {'text': 'Dr. Nera Vale'}, said))],
                                     [message(reply('I have noted Dr. Nera Vale.'))])
                picker = (out.get('conversationCheck') or {}).get('question')
                self.assertIsNotNone(picker)
                self.assertEqual(picker['kind'], 'doctor')
                self.assertTrue(picker['choices'])

    def test_the_picker_still_arrives_when_the_reply_is_rejected(self):
        # Owner's visit, November 22, 2026: the reply to the doctor's name was rejected by the
        # check and the fallback was shown with no picker.
        self.start_without_a_compare_goal()
        said = 'Dr. Nera Vale, at her office in Naples'
        out = self.visit.say(said, [save(update('T06', {'text': 'Dr. Nera Vale'}, said))],
                             [message(reply('Dr. Nera Vale is in network and a visit costs $4,321.'))],
                             [message(reply('Dr. Nera Vale is in network for every plan.'))])   # the retry fails too
        self.assertTrue(out['metrics']['oneCall']['fallback'])
        picker = (out.get('conversationCheck') or {}).get('question')
        self.assertIsNotNone(picker)
        self.assertEqual(picker['kind'], 'doctor')
        self.assertNotIn('{', out['reply'])
        self.assertNotIn("'items'", out['reply'])

    def test_the_picker_arrives_under_a_question_the_model_worded_itself(self):
        # advisor-first reads "no button question this turn" as a pause and holds its picker back.
        self.start_visit()
        said = 'I see Dr. Nera Vale.'
        out = self.visit.say(said, [save(update('T06', {'text': 'Dr. Nera Vale'}, said))],
                             [message(reply('I have noted Dr. Nera Vale.', question='What else should I know about your care?'))])
        self.assertEqual(out['conversationCheck']['question']['kind'], 'doctor')
        self.assertFalse(out['assessment']['intakePaused'])
        self.assertNotIn('What else should I know', out['reply'])

    def test_a_typed_medicine_gets_its_picker_in_the_same_turn(self):
        self.start_visit()
        said = 'I take metformin 500 mg tablets.'
        out = self.visit.say(said, [save(update('T06', {'choice': 'none'}, said), update('T07', {'text': 'metformin 500 mg'}, said))],
                             [message(reply('I have noted metformin.', question='Do you travel much?', target='T08'))])
        self.assertEqual(self.visit.value('needs.medications'), 'metformin 500 mg')
        picker = out['conversationCheck']['question']
        self.assertEqual(picker['kind'], 'drug')
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'check'})
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_a_name_typed_as_the_last_detail_gets_its_picker_before_the_close(self):
        said = ALMOST.replace(' I see Dr. Nera Vale.', '') + ' ' + LAST
        updates = [item for item in ALMOST_UPDATES if item['id'] != 'T06'] + [LAST_UPDATE]
        self.visit.say(said, [save(*updates)], [message(reply('Thank you.', question='Any doctors to keep?', target='T06'))])
        doctor = 'I see Dr. Nera Vale.'
        out = self.visit.say(doctor, [save(update('T06', {'text': 'Dr. Nera Vale'}, doctor))], [message(reply('Noted.'))])
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertEqual(out['conversationCheck']['question']['kind'], 'doctor')
        self.assertFalse(self.close(out))
        out = self.visit.say('What is a premium?', [message(reply('A general answer.', question='Shall we go on?'))])
        self.handed_over(out)


class DoctorTypedWithAnOffice(Case):
    SAID = 'Dr. Shannon Wise, at her office on Goodlette-Frank Road'

    def begin(self):
        self.visit.given_profile_permission()
        said = "It's for me and I want to find coverage. I'm in 34104."
        self.visit.say(said, [save(update('RC01', {'choice': 'self'}, "It's for me"),
                                   update('T01', {'choice': 'compare'}, 'I want to find coverage'),
                                   update('T03', {'zip': '34104'}, "I'm in 34104"))],
                       [message(reply('Thank you.', question='Are there doctors you want to keep?', target='T06'))])

    def test_a_reply_that_names_the_doctor_and_her_street_is_saved_and_shown(self):
        # Line 46 was not this path: the validators accept the name with or without the office,
        # and the reply check passes the name and the street the person typed.
        for fields in ({'text': 'Dr. Shannon Wise'}, {'choice': 'list', 'text': self.SAID}):
            with self.subTest(fields=fields):
                self.setUp()
                self.begin()
                out = self.visit.say(self.SAID, [save(update('T06', fields, self.SAID)),
                                                 call('d1', 'check_doctor', {'name': 'Dr. Shannon Wise', 'place': 'Goodlette-Frank Road'})],
                                     [message(reply('I have noted Dr. Shannon Wise at her office on Goodlette-Frank Road.',
                                                    'I could not check her participation just now.',
                                                    question='Which prescriptions should we include?', target='T07'))])
                self.assertEqual((self.one(out)['fallback'], self.one(out)['rejectedCodes'], self.one(out)['fallbackReason']),
                                 (False, [], None))
                self.assertIn('Dr. Shannon Wise at her office on Goodlette-Frank Road', out['reply'])
                self.assertEqual(self.visit.value('needs.providers'), fields['text'])
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'T07')

    def test_when_no_model_reply_can_be_shown_the_saved_doctor_is_still_acknowledged_by_name(self):
        # What line 46 showed: the save ran, the reply after the tool round was lost, and the
        # fallback said nothing about the doctor. Here the one retry after the tool round is lost too.
        for lost, code in (([message('not the reply format')], 'invalid_structure'),
                           (TimeoutError('fictional timeout'), 'transport_or_format'),
                           ([message(reply('Plan Zebra H1234 costs $17.50 a month for her.'))], 'reply_rejected')):
            with self.subTest(code=code):
                self.setUp()
                self.begin()
                out = self.visit.say(self.SAID, [save(update('T06', {'text': 'Dr. Shannon Wise'}, self.SAID))], lost, lost)
                self.assertTrue(self.one(out)['fallback'])
                self.assertEqual((self.one(out)['fallbackReason'], out['generated']['code']), (code, code))
                self.assertEqual(self.visit.value('needs.providers'), 'Dr. Shannon Wise')
                self.assertEqual(out['reply'], 'I’ve noted Dr. Shannon Wise.')
                self.assertNotIn('keep going with the next useful detail', out['reply'])
                # The turn still ends on the next open question, in its approved wording.
                self.assertNotIn(out['assessment']['nextQuestion']['id'], ('T06', 'RC21'))
                self.assertEqual(out['conversationNext']['kind'], 'profile_question')
                self.assertEqual((self.one(out)['retry'], self.one(out)['requests']), (True, 3))


class GoalFromTheOpeningMessage(Case):
    OPENING = ("Hi. I turn 65 on December 14 and my Medicare card came last month. I'm in 34104. I don't know the difference "
               "between the two things everyone keeps talking about, and I don't want to pick wrong. Where do I start?")

    def test_the_goal_question_is_never_delivered_once_the_goal_is_saved(self):
        out = self.visit.say(self.OPENING,
                             [save(update('T03', {'zip': '34104'}, "I'm in 34104"),
                                   update('T01', {'choice': 'compare', 'text': "I don't want to pick wrong"},
                                          "I don't want to pick wrong", scope='unknown'))],
                             [message(reply('Start with the difference between the two.',
                                            question='What would you like help with?', target='T01'))])
        self.assertEqual(self.visit.value('intent.goal'), 'compare')
        self.assertEqual(self.one(out)['staged'], 0)
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'), 'T01')
        self.assertNotIn('What would you like help with?', json.dumps(out))
        # From then on the goal is not among what the model may ask about.
        self.visit.say('Okay.', [message(reply('Good.'))])
        self.assertNotIn('T01', [item['id'] for item in self.script.inputs()[-1]['open_items']])

    def test_a_goal_in_words_that_fit_no_listed_goal_is_saved_as_the_persons_own_words(self):
        said = 'My neighbour said I should ask about something called a give back.'
        out = self.visit.say(said, [save(update('T01', {'text': said}, said))], [message(reply('Thank you for telling me.'))])
        self.assertEqual((self.one(out)['saved'], self.visit.value('intent.goal')), (1, 'unresolved'))
        self.assertNotIn('T01', [item['id'] for item in self.script.inputs()[-1].get('open_items', [])
                                 ] if len(self.script.inputs()) > 2 else [])


class TurnTraceAndCost(Case):
    CANARY = 'Quillfeather'

    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.trace = Path(folder.name) / 'nested' / 'trace.jsonl'
        self.flow.one_call_trace = str(self.trace)

    def lines(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def test_one_content_free_line_per_typed_turn_and_a_cost_per_visit(self):
        said = 'It is for me. I see Dr. %s on Heron Street.' % self.CANARY
        self.visit.say(said, [save(update('RC01', {'choice': 'self'}, 'It is for me'),
                                   update('T06', {'text': 'Dr. ' + self.CANARY}, 'I see Dr. %s on Heron Street' % self.CANARY))],
                       [message(reply('I have noted Dr. %s.' % self.CANARY, question='What would you like help with?',
                                      target='T01'))])
        self.visit.tap({'type': 'choice', 'id': 'T01', 'fields': {'choice': 'learn'}})     # a button turn writes nothing
        self.visit.say('What about %s?' % self.CANARY, [message('not the reply format')])
        first, second = self.lines()
        self.assertEqual(set(first), {'at', 'visit', 'turn', 'requests', 'tools', 'rejected_codes', 'fallback',
                                      'fallback_reason', 'retry', 'reconciled', 'plans_handoff', 'input_tokens',
                                      'cached_tokens', 'output_tokens', 'settled_nano_usd', 'usd', 'unresolved_attempts',
                                      'seconds', 'fallback_detail', 'can_review', 'missing_count', 'plans_requested',
                                      'close_due', 'handoff_reason'})
        self.assertEqual((first['turn'], first['requests'], first['tools'], first['fallback'], first['fallback_reason']),
                         (1, 2, ['save_profile_fields'], False, None))
        self.assertEqual((first['input_tokens'], first['cached_tokens'], first['output_tokens']), (600, 0, 140))
        self.assertEqual((second['turn'], second['fallback'], second['fallback_reason'], second['tools']),
                         (2, True, 'invalid_structure', []))
        self.assertEqual(first['visit'], second['visit'])
        self.assertRegex(first['visit'], r'^[0-9a-f]{12}$')
        self.assertNotIn(first['visit'], self.visit.owner)
        self.assertNotIn(self.visit.owner[:12], self.trace.read_text())
        # The dollars are the ledger's own settled amounts.
        with self.budget.db() as db:
            settled = sum(row[0] for row in db.execute("SELECT measured FROM ai_charges WHERE status = 'settled'"))
        self.assertGreater(settled, 0)
        self.assertEqual(first['settled_nano_usd'] + second['settled_nano_usd'], settled)
        self.assertEqual(first['usd'], round(first['settled_nano_usd'] / 1e9, 6))
        # No message, reply, value, name or tool argument.
        text = self.trace.read_text()
        for word in (self.CANARY, 'Heron', 'Dr.', 'noted', 'for me', 'RC01', 'T06'):
            self.assertNotIn(word, text)
        # The published metric carries the same fixed code.
        self.assertEqual(self.one(self.visit.outs[-1])['fallbackReason'], 'invalid_structure')
        self.assertIsNone(self.one(self.visit.outs[1])['fallbackReason'])
        # The summary: requests, tokens and dollars for the visit.
        rows, skipped = cost.read(self.trace)
        visits, overall = cost.summarise(rows)
        self.assertEqual((len(visits), skipped, overall['turns'], overall['fallbacks']), (1, 0, 2, 1))
        self.assertEqual((visits[0]['requests'], visits[0]['settled_nano_usd']), (first['requests'] + second['requests'], settled))
        self.assertEqual(visits[0]['fallback_reasons'], {'invalid_structure': 1})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(cost.main([str(self.trace)]), 0)
        self.assertIn(first['visit'], printed.getvalue())
        self.assertIn('%.4f' % visits[0]['usd'], printed.getvalue())
        self.assertIn('invalid_structure x1', printed.getvalue())
        self.assertNotIn(self.CANARY, printed.getvalue())

    def test_a_turn_that_ends_in_an_error_is_traced_and_a_missing_trace_is_reported(self):
        self.visit.say('It is for me.', [message(reply('Thank you.'))])
        self.script.add(RuntimeError('fictional ' + self.CANARY))
        with self.assertRaises(Exception):
            self.flow.turn(self.visit.owner, self.visit.payload({'type': 'message', 'message': 'And then?'}))
        last = self.lines()[-1]
        self.assertEqual((last['turn'], last['fallback'], last['fallback_reason']), (2, True, 'turn_failed'))
        self.assertNotIn(self.CANARY, self.trace.read_text())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(cost.main([str(self.trace.parent / 'absent.jsonl')]), 1)
        self.assertIn('No turn trace', printed.getvalue())

    def test_the_trace_is_off_unless_a_path_is_set_and_lives_inside_the_variant(self):
        self.flow.one_call_trace = None
        self.visit.say('It is for me.', [message(reply('Thank you.'))])
        self.assertFalse(self.trace.exists())
        self.assertEqual(one_call_flow.TRACE_FILE, VARIANT / 'var' / 'one-call-turn-trace.jsonl')
        self.assertEqual(cost.DEFAULT, one_call_flow.TRACE_FILE)
        self.assertIn('var/', (VARIANT / '.gitignore').read_text().split())


class ReasoningSetting(Case):
    def test_every_one_call_request_asks_for_low_reasoning_whatever_the_base_agent_holds(self):
        self.assertEqual(one_call_flow.ONE_CALL_REASONING_EFFORT, 'low')
        self.flow.agent.reasoning_effort = 'medium'
        self.visit.say('It is for me.', [save(update('RC01', {'choice': 'self'}, 'It is for me'))], [message(reply('Thank you.'))])
        self.visit.say('And then?', [message(reply('Plan Zebra H1234 costs $17.50 a month.'))],
                       [message(reply('Here is what comes next.'))])
        self.assertTrue(self.one(self.visit.outs[-1])['retry'])
        self.assertEqual(len(self.script.sent), 4)                       # first request, tool round, first try, retry
        self.assertEqual([payload['reasoning'] for payload in self.script.sent], [{'effort': 'low'}] * 4)


class StartScript(unittest.TestCase):
    PATH = VARIANT / 'Start Daylight One-Call 8897.command'

    def test_the_script_mirrors_the_demo_launcher_and_turns_the_checks_on(self):
        text = self.PATH.read_text()
        self.assertTrue(self.PATH.stat().st_mode & stat.S_IXUSR and self.PATH.stat().st_mode & stat.S_IXOTH)
        self.assertEqual(stat.S_IMODE(self.PATH.stat().st_mode), 0o755)
        for line in ('cd "$(dirname "$0")/../.." || exit 1',
                     'foundation="$PWD/infrastructure/daylight-data/.state"',
                     'local_pg="host=$foundation/socket port=55485 user=$(id -un)"',
                     'export DAYLIGHT_FOUNDATION_SOURCE_DSN="$local_pg dbname=daylight_research_2026_r2"',
                     'export DAYLIGHT_FOUNDATION_PACKAGE_DSN="$local_pg dbname=daylight_pilot_foundation_2026_r1"',
                     'export DAYLIGHT_DEFAULT_MODEL=gpt-6.1-sol',
                     'export DAYLIGHT_TOKEN_PREFLIGHT="${DAYLIGHT_TOKEN_PREFLIGHT:-local_bound}"',
                     'exec infrastructure/daylight-data/.venv/bin/python alternatives/one-call/one_call_server.py \\',
                     '  --doctor-foundation "$foundation/pilot-foundation-2026-r1/binding.json" --conversation-checks'):
            self.assertIn(line, text.splitlines())
        self.assertNotIn('--doctor-chat', text)
        self.assertEqual(subprocess.run(['sh', '-n', str(self.PATH)], capture_output=True).returncode, 0)

    def test_the_server_takes_the_options_the_script_passes(self):
        import one_call_server
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            one_call_server.main(['--doctor-chat'])
        with contextlib.redirect_stderr(io.StringIO()) as said, self.assertRaises(SystemExit):
            # Without the two DSNs the launcher exports, the server refuses to start half-wired.
            saved = {key: os.environ.pop(key, None) for key in ('DAYLIGHT_FOUNDATION_PACKAGE_DSN', 'DAYLIGHT_FOUNDATION_SOURCE_DSN')}
            try:
                one_call_server.main(['--doctor-foundation', 'binding.json', '--conversation-checks'])
            finally:
                os.environ.update({key: value for key, value in saved.items() if value is not None})
        self.assertIn('foundation DSNs', said.getvalue())



class GettingToKnowThePerson(Case):
    invitation = 'Would it be okay to go through a few coverage details together?'

    def intro(self):
        words = "It's for me. I'm in 34104 and worried about costs. I got my card and two sales calls."
        return self.visit.say(words, [save(
            update('RC01', {'choice': 'self'}, "It's for me"),
            update('T03', {'zip': '34104'}, "I'm in 34104"))],
            [message(reply('Those calls left you wondering what coverage would cost.',
                           question=self.invitation, detail_step='invite',
                           concerns={'why_now': 'card arrived', 'worries': ['costs'], 'tried': ['sales calls']}))])

    def test_invite_then_agreement_unlocks_only_missing_details(self):
        out = self.intro()
        self.assertEqual(out['conversationNext'], {'kind': 'clarification', 'question': self.invitation})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(self.visit.value('comparison.scope.zip'), '34104')
        before = len(self.script.sent)
        out = self.visit.say('Sure, go ahead and ask.', [message(reply('That helps.',
            question='What coverage do you have now?', target='T05', detail_step='agree'))])
        self.assertEqual(self.script.inputs()[-1]['stage']['detail_permission'], 'invited')
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'T05'})
        self.assertEqual(len(self.script.sent), before + 1)
        self.assertEqual(self.flow.one_call_visits.read(self.visit.owner, self.visit.chain,
                         support.CONTEXT_POLICY)['detail_permission'], 'granted')

    def test_asking_for_more_about_the_two_routes_delivers_every_checked_point(self):
        import plans_fixes
        plans_fixes.enable(self.flow)  # Use :8897's public error handling and record validation.
        self.intro()
        facts = ['original', 'advantage', 'drugs', 'medigap']
        blocks = [{'text': self.flow.facts[fact]['text'], 'fact_ids': [fact]} for fact in facts]
        follow_up = 'Which difference would you like to explore a little more?'
        out = self.visit.say('First, can I learn more about the two main routes?',
            [message(reply(*blocks, question=follow_up, detail_step='later'))])
        self.assertEqual(out['conversationNext'], {'kind': 'clarification', 'question': follow_up})
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertFalse(self.one(out)['fallback'])
        for block in blocks:
            self.assertIn(block['text'], out['reply'])
        self.assertEqual(out['advisor']['teachingFactIds'], facts)
        self.assertEqual(out['record']['conversation']['lastFactIds'], facts[:3])
        self.assertEqual(out['advisor']['sources'], self.flow._sources(facts))
        self.assertTrue(set(facts).issubset(out['record']['conversation']['journey']['learningSeen']))
        self.assertTrue(set(facts).issubset(out['record']['natural']['dialogue']['explainedTopics']))
        self.visit.say('The drug coverage part.', [message(reply('We can focus on that.',
            question='What have you heard about drug coverage?'))])
        self.assertEqual(self.script.inputs()[-1]['stage']['detail_permission'], 'declined')
        self.assertTrue(set(facts).issubset(self.script.inputs()[-1]['education']['delivered_facts']))

    def test_a_decline_or_a_yes_to_something_else_stays_conversational(self):
        self.intro()
        words = 'What would you like to understand about the two routes?'
        out = self.visit.say('Not yet. Could we just talk about the difference?', [
            message(reply('We can talk that through.', question=words, detail_step='later'))])
        self.assertEqual(out['conversationNext']['question'], words)
        out = self.visit.say('Yes, that is what worries me.', [message(reply('Thank you.',
            question='What coverage do you have now?', target='T05', detail_step='agree'))])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('What coverage do you have now?', out['reply'])
        self.assertEqual(self.script.inputs()[-1]['stage']['detail_permission'], 'declined')

    def test_completed_discovery_and_elapsed_turns_do_not_start_intake(self):
        self.intro()
        for _ in range(5):
            out = self.visit.say('Can we talk a little more?', [message(reply('Of course.',
                question='What else would help you weigh the options?'))])
            self.assertEqual(out['conversationNext']['kind'], 'clarification')
            self.assertIsNone(out['assessment']['nextQuestion'])
        stage = self.script.inputs()[-1]['stage']
        self.assertEqual(stage, {'now': 'direction_understood', 'still_to_learn': [], 'detail_permission': 'open'})
        out = self.visit.say('I am still thinking.', [message(reply('Take your time.',
            question='What coverage do you have now?', target='T05'))])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('What coverage do you have now?', out['reply'])

    def test_requested_work_can_ask_for_its_prerequisite_and_permission_can_be_withdrawn(self):
        self.intro()
        out = self.visit.say('I only want to check my doctor. What do you need?', [message(reply(
            'I can look up the doctor you have in mind.', question='Which doctor should we look up?',
            target='T06', detail_step='requested_work'))])
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'T06'})
        out = self.visit.say('Actually, could you explain the two options first?', [message(reply(
            'We can take that first.', question='What insurance do you have?', target='T05'))])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('What insurance do you have?', out['reply'])
        self.intro()
        self.visit.say('Yes, go ahead.', [message(reply('All right.', question='What coverage do you have?',
            target='T05', detail_step='agree'))])
        out = self.visit.say('I would rather talk about the basics again.', [message(reply(
            'Of course.', question='What is on your mind?', detail_step='later'))])
        self.assertEqual(out['conversationNext']['question'], 'What is on your mind?')
        out = self.visit.say('I am still thinking about the basics.', [message(reply(
            'Take your time.', question='What coverage do you have?', target='T05'))])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(self.script.inputs()[-1]['stage']['detail_permission'], 'declined')

    def test_failed_opening_preserves_a_conversational_next_question(self):
        out = self.visit.say('I have a few general questions.', TimeoutError('offline fixture'))
        self.assertTrue(self.one(out)['fallback'])
        self.assertEqual(out['conversationNext']['kind'], 'clarification')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_prompt_shares_the_same_opening_and_discovery_rules_on_every_turn(self):
        self.intro()
        self.visit.say('What do you mean?', [message(reply('Let us talk that through.',
                       question='What part feels unclear?'))])
        a, b = self.script.sent[0]['instructions'], self.script.sent[-1]['instructions']
        self.assertEqual(a, b)
        self.assertLess(a.index('## Make the opening a conversation'), a.index('## The rules that always apply'))
        self.assertIn('first three moves of CLOSER', a)
        self.assertIn('End there and wait for their answer.', a)
        self.assertIn('Keep the acronym', a)


if __name__ == '__main__':
    unittest.main()
