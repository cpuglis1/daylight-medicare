"""Regressions from the owner's third live visit on port 8897 (2026-11-22).

Offline: a scripted model, a temporary budget ledger, sockets forbidden and a
fictional person. Each test walks the owner's visit in its own order, with no
state the visit did not have: an opening message with a ZIP code and worries,
the goal tapped, the coverage answers typed, "Dr. Shannon Wise, at her office
on Goodlette-Frank Road.", a medicine, the priorities tapped, and then the
request to compare. Taps are sent with AI permission, as the live interface
sends them. The tests say nothing about a live model's wording.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat import ResponsesClient
import conversation_planner
import journey_completion
import plan_review

import _one_call_support as support
from _one_call_support import Script, Visit, call, message, reply, save, update
import one_call_check
import one_call_flow
import one_call_server
import one_call_tools

VARIANT = Path(__file__).resolve().parents[1]
OFFICE = {'street': '730 Goodlette-Frank Rd, Ste 200', 'city': 'Naples', 'state': 'FL', 'postal': '34102'}
SHOWN = 'Wise, Shannon MD — 730 Goodlette-Frank Rd, Ste 200, Naples, FL, 34102'
PLANS = 72

OPENING = ("Hi. I turn 65 in December and I keep getting mail about Medicare. I'm in 34104 and I'm worried about "
           'picking the wrong thing.')
COVERAGE = 'My card says Part A and Part B both start December 1, 2026. I have no other insurance.'
DOCTOR = 'Dr. Shannon Wise, at her office on Goodlette-Frank Road.'
MEDICINE = 'I take lisinopril.'
COMPARE = 'Yes, let’s do that: compare my options.'       # the words advisor-first's offer button sends
DETAILS = 'I stay local and I want lower monthly payments.'
OPEN_ON_COSTS = 'I stay local. I have no preference on costs yet.'


def fictional_checks(flow, *, two_offices=False):
    """advisor-first's check controller over fictional services shaped like the owner's visit:
    one distinct directory entry and four whose name and office read the same, 72 Medicare
    Advantage offerings, and three medicine products with one label."""
    loaded = support.check_services()
    if loaded is None:
        return False
    Doctors, Drugs, ConversationChecks = loaded

    class Directory(Doctors):
        def search(self, name, **kwargs):
            def entry(number, office):
                return dict(candidate_id='W%d' % number, label='Wise, Shannon MD', kind='clinician', site_count=1,
                            source_npis=['W%d' % number], office_previews=[dict(office)])
            other = dict(OFFICE, street='11 Other St')
            if two_offices:
                if not kwargs.get('location'):
                    return {'candidates': [], 'next_offset': None}
                return {'candidates': [dict(entry(1, OFFICE), site_count=2, office_previews=[OFFICE, other])],
                        'next_offset': None}
            return {'candidates': [entry(0, other)] + [entry(number, OFFICE) for number in range(1, 5)], 'next_offset': None}

        def sites(self, candidate_id, **kwargs):
            if two_offices:
                return {'sites': [{'site_id': 'goodlette', 'address': OFFICE},
                                  {'site_id': 'other', 'address': dict(OFFICE, street='11 Other St')}], 'next_offset': None}
            return super().sites(candidate_id, **kwargs)

        def address(self, identifier):
            return dict(OFFICE)

    class Products(Drugs):
        def products(self, refs, **query):
            one = super().products(refs, **query)[0]
            same = [dict(one, name='Lisinopril 10 mg tablet', rxcui=str(314076 + number), strength_description='10 mg')
                    for number in range(3)]
            return same + [dict(one, name='Lisinopril 20 mg tablet', rxcui='197884', strength_description='20 mg')]

    offerings = [{'offering_id': '2026:H9999:%03d:000' % number, 'name': 'Fictional Plan %d' % number}
                 for number in range(PLANS)]
    flow.conversation_checks = ConversationChecks(flow, Directory(offerings), Products(), lambda: [])
    return True


@unittest.skipUnless(support.READY, support.NOT_READY)
class OwnerVisit(unittest.TestCase):
    checks = False

    def setUp(self):
        support.offline(self)
        support.pin_today(self)
        self.script = Script()
        self.flow = support.make_flow(self.script)
        self.budget = support.temporary_ledger(self, self.flow.agent)
        if self.checks and not fictional_checks(self.flow):
            self.skipTest('advisor-first offline check fixtures could not be loaded')
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.trace = Path(folder.name) / 'trace.jsonl'
        self.flow.one_call_trace = str(self.trace)
        self.visit = Visit(self, self.flow, self.script)
        self.visit.start()

    # -- the visit, step by step ---------------------------------------------------

    def opening(self):
        # This historical fixture follows the profile questions through to Plans.
        self.visit.given_profile_permission()
        return self.visit.say(OPENING, [save(update('T03', {'zip': '34104'}, "I'm in 34104"),
                                             update('RC01', {'choice': 'self'}, 'I turn 65 in December'))],
                              [message(reply('That is a lot of mail to sort through.',
                                             question='What would you like help with?', target='T01'))])

    def goal(self):
        return self.visit.tap({'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}}, consent=True)

    def coverage(self):
        both = 'Part A and Part B both start December 1, 2026'
        return self.visit.say(COVERAGE, [save(update('COV_PART_A', {'status': 'approved', 'month': '12', 'year': '2026'}, both),
                                              update('COV_PART_B', {'status': 'approved', 'month': '12', 'year': '2026'}, both),
                                              update('T05', {'choice': 'none'}, 'I have no other insurance'))],
                              [message(reply('Thank you.', question='Are there doctors you want to keep?', target='T06'))])

    def doctor(self, *steps):
        said = DOCTOR.rstrip('.')
        steps = steps or ([message(reply('I have noted Dr. Shannon Wise.', question='Do you take any prescriptions?',
                                         target='T07'))],)
        return self.visit.say(DOCTOR, [save(update('T06', {'text': 'Dr. Shannon Wise'}, said),
                                            update('RC21', {'practice': 'Dr. Shannon Wise', 'city': 'Goodlette-Frank Road'},
                                                   said, entity='new'))], *steps)

    def medicine(self):
        return self.visit.say(MEDICINE, [save(update('T07', {'text': 'lisinopril'}, 'I take lisinopril'))],
                              [message(reply('I have noted lisinopril.', question='What matters most to you?', target='T10'))])

    def pick(self, out, index=0):
        question = out['conversationCheck']['question']
        return self.visit.tap({'type': 'check_answer', 'token': question['token'],
                               'value': question['choices'][index]['value']}, consent=True)

    def priorities(self):
        return self.visit.tap({'type': 'choice', 'id': 'T10', 'fields': {'choice': 'doctors,total_cost'}}, consent=True)

    def up_to_priorities(self, *, details=False):
        self.opening()
        self.goal()
        self.coverage()
        out = self.doctor()
        if self.checks:
            self.pick(out, 1)
        out = self.medicine()
        if self.checks:
            self.pick(out, 0)
        if details == 'open_on_costs':
            self.visit.say(OPEN_ON_COSTS, [save(update('T08', {'choice': 'local'}, 'I stay local'),
                                                update('T09', {'choice': 'no_preference'}, 'I have no preference on costs yet'))],
                           [message(reply('Thank you.', question='What matters most to you?', target='T10'))])
        elif details:
            self.visit.say(DETAILS, [save(update('T08', {'choice': 'local'}, 'I stay local'),
                                          update('T09', {'choice': 'lower_monthly'}, 'I want lower monthly payments'))],
                           [message(reply('Thank you.', question='What matters most to you?', target='T10'))])
        return self.priorities()

    def compare(self, *steps):
        """The request to compare, as the model handled it in the owner's visit: a save and offer_plans."""
        steps = steps or ([save(update('T01', {'choice': 'compare', 'text': 'compare my options'}, 'compare my options')),
                           call('p1', 'offer_plans', {})],
                          TimeoutError('fictional: the reply after the tool round never arrived'),
                          TimeoutError('fictional: nor did the one retry'))
        return self.visit.say(COMPARE, *steps)

    # -- readings ------------------------------------------------------------------

    def one(self, out):
        return out['metrics']['oneCall']

    def close(self, out):
        return bool((out.get('comparisonClose') or {}).get('show'))

    def asked(self, out):
        return (out['assessment'].get('nextQuestion') or {}).get('id')

    def last_trace(self):
        return json.loads(self.trace.read_text().splitlines()[-1])

    def labels(self, out):
        return [choice['label'] for choice in out['conversationCheck']['question']['choices']]


class PickerShowsEachChoiceOnce(OwnerVisit):
    checks = True

    def test_directory_entries_that_read_the_same_are_one_choice(self):
        self.opening(); self.goal(); self.coverage()
        out = self.doctor()
        picker = out['conversationCheck']['question']
        self.assertEqual((picker['kind'], picker['field']), ('doctor', 'doctor'))      # the turn the name was typed
        self.assertEqual(self.labels(out), ['Wise, Shannon MD — 11 Other St, Naples, FL, 34102', SHOWN,
                                            'None of these: search by practice name', 'Look outside this area'])
        self.assertEqual([choice['value'] for choice in picker['choices'][:2]], ['W0', 'W1'])      # the first is kept
        # The kept choice answers through advisor-first's own check_answer path.
        picked = self.pick(out, 1)
        result = picked['conversationCheck']['results'][0]
        self.assertEqual((result['key'], result['name']), ('doctor:doctor-1', 'Wise, Shannon MD'))
        self.assertEqual(result['office_parts']['line'], OFFICE['street'])

    def test_medicine_products_that_read_the_same_are_one_choice(self):
        self.opening(); self.goal(); self.coverage()
        self.pick(self.doctor(), 1)
        out = self.medicine()
        picker = out['conversationCheck']['question']
        self.assertEqual(picker['kind'], 'drug')
        self.assertEqual(self.labels(out), ['Lisinopril 10 mg tablet', 'Lisinopril 20 mg tablet'])
        self.assertEqual(picker['choices'][0]['value'], '314076')
        picked = self.pick(out, 0)
        self.assertIsNone(picked['conversationCheck']['question'])

    def test_the_picker_still_arrives_on_a_turn_that_ends_in_the_fallback(self):
        self.opening(); self.goal(); self.coverage()
        out = self.doctor(TimeoutError('fictional: no reply'), TimeoutError('fictional: no reply'))
        self.assertTrue(self.one(out)['fallback'])
        self.assertEqual(len(self.labels(out)), 4)
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'check'})


class ChatShowsTheMatchNotEveryPlan(OwnerVisit):
    checks = True

    def test_marketplace_visit_through_office_medicine_travel_and_cost(self):
        self.assertTrue(fictional_checks(self.flow, two_offices=True))
        say = self.visit.say
        say(OPENING, [save(update('T03', {'zip': '34104'}, "I'm in 34104"),
                           update('RC01', {'choice': 'self'}, 'I turn 65 in December'))],
            [message(reply('We can start with the two routes.', question='May I ask a few details?', detail_step='invite'))])
        say('First, can I learn more about the two routes?', [message(reply('We can talk about those first.',
            question='What would help you understand the options?', detail_step='later'))])
        say('Maybe use an example.', [message(reply('We can walk through an example.',
            question='Would it help to go through your details together?', detail_step='invite'))])
        goal = 'Yes, I want to compare the plans that fit me.'
        say(goal, [save(update('T01', {'choice':'compare', 'text':goal}, goal))],
            [message(reply('Let’s look at your card.', question='Which Medicare parts do you have?', target='RC04',
                           detail_step='agree'))])
        both = 'Part A and Part B both start December 1, 2026'
        asked = say('My card says '+both+'.', [save(*[
            update('COV_PART_'+part, {'status':'approved','month':'12','year':'2026'}, both) for part in ('A','B')])],
            [message(reply('Thank you.', question='What health insurance do you have now?', target='T05'))])
        self.assertEqual(self.asked(asked), 'T05')
        self.assertIn('marketplace', dict(asked['assessment']['nextQuestion']['choices']))
        self.assertIn('marketplace', self.script.sent[-1]['instructions'])
        quote = 'I have a marketplace plan until Medicare starts'
        recorded = say('I retired two years ago. '+quote+'. No job insurance.', [save(
            update('T05', {'choice':'marketplace'}, quote),
            update('S_RETIREMENT', {'status':'retired','when':'two years ago'}, 'I retired two years ago'))],
            [message(reply('Thank you.', question='Which doctors would you like to keep?', target='T06'))])
        self.assertEqual(self.visit.value('coverage.current'), ['marketplace'])
        self.assertEqual(self.visit.value('situation.retirement')['status'], 'retired')
        coverage_row = next(row for row in self.flow.rows(self.visit.guide,self.visit.record) if row['id'] == 'T05')
        self.assertEqual(coverage_row['value'], 'Marketplace / individual health plan')
        self.assertNotIn('T05', [row['id'] for row in self.flow._open_items(self.visit.owner, self.visit.guide, self.visit.record)[1]])
        self.assertEqual(self.asked(recorded), 'T06')
        out = say(DOCTOR, [save(update('T06', {'text':'Dr. Shannon Wise'}, DOCTOR))],
            [message(reply('I can check that office.', question='Which prescriptions should we include?', target='T07'))])
        self.assertEqual(out['conversationCheck']['question']['field'], 'doctor_location')
        out = say('Naples Florida', [message(reply('Thank you.'))])
        self.assertEqual(out['conversationCheck']['question']['field'], 'office')
        office = self.pick(out)
        key = 'doctor:doctor-1'
        stamp = office['conversationCheck']['chatResultStamps'][key]
        self.assertEqual(office['conversationCheck']['results'][0]['office_parts']['line'], OFFICE['street'])
        product = say('Lisinopril', [save(update('T07', {'text':'lisinopril'}, 'Lisinopril'))],
            [message(reply('Thank you.', question='Will you need routine care away from home?', target='T08'))])
        medicine = self.pick(product)
        self.assertIn('formulary', medicine['conversationCheck']['chatResultStamps'])
        last = medicine
        for id, choice in [('T08','local'), ('T09','lower_monthly')]:
            self.assertEqual(self.asked(last), id)
            last = self.visit.tap({'type':'choice','id':id,'fields':{'choice':choice}}, consent=True)
        self.assertEqual(self.visit.value('coverage.current'), ['marketplace'])
        self.assertEqual(self.asked(last), 'T10')
        self.assertEqual(sum(out['conversationNext'].get('target') == 'T05' for out in self.visit.outs), 1)
        later = self.visit.outs[self.visit.outs.index(office)+1:]
        self.assertTrue(all(out['conversationCheck']['chatResultStamps'][key] == stamp for out in later))

    def test_marketplace_picker_and_current_coverage_correction(self):
        self.opening()
        self.goal()
        self.visit.tap({'type':'choice','id':'T05','fields':{'choice':'marketplace'}}, consent=True)
        self.assertEqual(self.visit.value('coverage.current'), ['marketplace'])
        words = 'Correction. I have Medicaid now.'
        self.visit.say(words, [save(update('T05', {'choice':'medicaid'}, words, correction=True))],
                       [message(reply('Thank you.'))])
        self.assertEqual(self.visit.value('coverage.current'), ['medicaid'])
        self.assertNotIn('marketplace', dict(one_call_flow.Q['T05']['choices']))

    def test_after_the_doctor_is_picked_the_chat_confirms_the_match_without_a_row_per_plan(self):
        self.opening(); self.goal(); self.coverage()
        picked = self.pick(self.doctor(), 1)
        shown = picked['conversationCheck']['results']
        self.assertEqual(len(shown), 1)
        result = shown[0]
        # The doctor and office picked, the date checked and advisor-first's own Medicare lines.
        self.assertEqual((result['kind'], result['key'], result['name']), ('doctor', 'doctor:doctor-1', 'Wise, Shannon MD'))
        self.assertEqual(result['office_parts']['line'], OFFICE['street'])
        self.assertRegex(result['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(result['plan'], 'Original Medicare')
        self.assertTrue(result['details'])
        self.assertTrue(all('Medicare' in line for line in result['details']))
        self.assertNotIn('plans', result)
        self.assertNotIn('Fictional Plan', json.dumps(picked))
        # The per-plan rows are intact for the Plans page and the sorting engine.
        full = self.flow.conversation_checks.reconcile(self.visit.owner, self.visit.guide, self.visit.record)['results'][0]
        self.assertEqual((full['kind'], len(full['plans'])), ('doctor_matrix', PLANS))
        self.assertEqual(full['details'], result['details'])

    def test_after_the_medicine_is_picked_the_chat_names_the_product_without_a_row_per_plan(self):
        self.opening(); self.goal(); self.coverage()
        self.pick(self.doctor(), 1)
        picked = self.pick(self.medicine(), 0)
        by_key = {result['key']: result for result in picked['conversationCheck']['results']}
        self.assertEqual(set(by_key), {'doctor:doctor-1', 'formulary'})
        medicine = by_key['formulary']
        self.assertNotIn('plans', medicine)
        self.assertEqual(medicine['kind'], 'note')
        self.assertEqual(len(medicine['details']), 1)                   # the product matched, and nothing per plan
        self.assertTrue(medicine['products'])
        self.assertNotIn('Tier', json.dumps(picked['conversationCheck']))
        full = {result['key']: result for result in self.flow.conversation_checks.reconcile(
            self.visit.owner, self.visit.guide, self.visit.record)['results']}
        self.assertEqual(full['formulary']['kind'], 'formulary')
        self.assertGreater(len(full['formulary']['plans']), 1)
        self.assertEqual(full['formulary']['products'], medicine['products'])
        # Every later response of the visit keeps the short form, typed turns included.
        out = self.visit.say('Thank you.', [message(reply('You are welcome.'))])
        self.assertEqual({result['kind'] for result in out['conversationCheck']['results']}, {'doctor', 'note'})

    def test_the_close_still_counts_the_doctor_and_medicine_as_checked(self):
        # advisor-first's close reads the full results; only what is sent to the screen is shortened.
        self.opening(); self.goal(); self.coverage()
        self.pick(self.doctor(), 1)
        self.pick(self.medicine(), 0)
        self.visit.say(DETAILS, [save(update('T08', {'choice': 'local'}, 'I stay local'),
                                      update('T09', {'choice': 'lower_monthly'}, 'I want lower monthly payments'))],
                       [message(reply('Thank you.', question='What matters most to you?', target='T10'))])
        import plans_fixes
        plans_fixes.enable(self.flow)               # as the server turns it on
        out = self.priorities()
        self.assertTrue(self.close(out))
        learned = {row['label']: row['value'] for row in out['comparisonClose']['learned']}
        self.assertIn('Checked', learned)
        self.assertNotIn('To check', learned)
        # Its lines that point to full results "above" are not shown, because the chat no longer has them.
        self.assertEqual(out['comparisonClose']['findings'], [])
        self.assertEqual({result['kind'] for result in out['conversationCheck']['results']}, {'doctor', 'note'})


@unittest.skipUnless(support.READY, support.NOT_READY)
class ChecksRouteShowsTheSameShortForm(unittest.TestCase):
    """The interface replaces what the chat shows with this route's answer every few seconds."""

    def test_the_checks_route_answers_with_what_the_turn_showed(self):
        import test_one_call_server as server_tests
        server_tests.loopback_only(self)
        support.pin_today(self)
        loaded = support.check_services()
        if loaded is None:
            self.skipTest('advisor-first offline check fixtures could not be loaded')
        script = Script()
        Doctors, Drugs, _ = loaded
        service = one_call_server.build_one_call(
            0, fixture=True, client=ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=script),
            medigap_repository=server_tests.FictionalStore(), part_d_repository=server_tests.FictionalStore(),
            conversation_checks=True, doctor_service=Doctors([]), prescription_service=Drugs(), reconcile=False)
        self.addCleanup(one_call_server.close, service)
        flow = service.adaptive
        self.assertTrue(fictional_checks(flow))         # the same controller, over the visit's fictional directory
        support.temporary_ledger(self, flow.agent)
        helper = server_tests.ServerCase('run')
        helper.addCleanup = self.addCleanup
        port = helper.serve(service)
        auth, state = helper.session(port)
        _, out = helper.turn(port, auth, state, {'type': 'start'}, consent=False, policy=None)

        def say(text, *steps):
            script.add(*steps)
            status, result = helper.turn(port, auth, say.state, {'type': 'message', 'message': text}, consent=True,
                                         policy=support.CONTEXT_POLICY)
            self.assertEqual(status, 200, result)
            say.state = result
            return result
        say.state = out
        say(OPENING, [save(update('T03', {'zip': '34104'}, "I'm in 34104"), update('RC01', {'choice': 'self'}, 'I turn 65 in December'))],
            [message(reply('Thank you.'))])
        said = DOCTOR.rstrip('.')
        out = say(DOCTOR, [save(update('T06', {'text': 'Dr. Shannon Wise'}, said),
                                update('RC21', {'practice': 'Dr. Shannon Wise', 'city': 'Goodlette-Frank Road'}, said, entity='new'))],
                  [message(reply('I have noted Dr. Shannon Wise.'))])
        picker = out['conversationCheck']['question']
        self.assertEqual(len(picker['choices']), 4)
        status, _, raw = helper.request(port, 'POST', '/api/conversation/checks', {'continuation': out['continuation']}, auth)
        self.assertEqual(status, 200)
        self.assertEqual([choice['label'] for choice in json.loads(raw)['question']['choices']],
                         [choice['label'] for choice in picker['choices']])
        status, out = helper.turn(port, auth, out, {'type': 'check_answer', 'token': picker['token'], 'value': 'W1'},
                                  consent=False, policy=None)
        self.assertEqual(status, 200, out)
        status, _, raw = helper.request(port, 'POST', '/api/conversation/checks', {'continuation': out['continuation']}, auth)
        self.assertEqual(status, 200)
        view = json.loads(raw)
        self.assertEqual(view['results'], out['conversationCheck']['results'])
        self.assertEqual(view['results'][0]['kind'], 'doctor')
        self.assertNotIn('Fictional Plan', raw.decode())


class PartsTypedInWordsCountTowardPlans(OwnerVisit):
    def test_parts_a_and_b_saved_from_the_persons_words_satisfy_plan_readiness(self):
        # The cause of the missing close. advisor-first derives "which parts do you have" (RC04) from
        # the two part reports and never asks it again, but the derived answer carried no record of
        # who it was about, and plan readiness does not count such an answer. A visit in which the
        # person described the card in words could never reach the close.
        self.opening(); self.goal()
        self.coverage()
        self.assertEqual(self.visit.report('RC04').get('choice'), 'both')
        status = plan_review.readiness(self.visit.guide, self.visit.record)
        self.assertNotIn('enrollment', [item['id'] for item in status['missing']])
        self.assertNotIn('RC04', [move['id'] for move in conversation_planner.refine(
            self.flow, self.visit.owner, self.visit.guide, self.visit.record, [])])

    def test_the_owners_visit_reaches_the_close_when_the_priorities_are_tapped(self):
        out = self.up_to_priorities(details=True)
        self.assertTrue(out['planReadiness']['canReview'], [item['id'] for item in out['planReadiness']['missing']])
        self.assertTrue(self.close(out))
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'plan_review'})


class TheEndingIsBuiltByCode(OwnerVisit):
    def handed_over(self, out):
        self.assertTrue(self.close(out))
        brief = out['comparisonClose']
        self.assertTrue(brief['ready'])                                  # the one button is drawn when this is true
        self.assertTrue(brief['learned'])                                # what matters to them, from their own reports
        self.assertTrue(brief['rows'])                                   # their answers, to review
        self.assertTrue(brief['steps'])
        self.assertEqual(out['conversationNext'], {'kind': 'action', 'action': 'plan_review'})
        self.assertIsNone(out['assessment']['nextQuestion'])
        return brief

    def test_a_request_to_compare_ends_on_the_close_even_when_the_reply_never_arrives(self):
        # Doctors first and no wish for the lowest monthly payment: advisor-first's direction line applies.
        out = self.up_to_priorities(details='open_on_costs')
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertFalse(self.close(out))               # advisor-first asks a Medigap price detail first
        out = self.compare()
        self.assertTrue(self.one(out)['fallback'])
        brief = self.handed_over(out)
        self.assertEqual(brief['direction'], 'Original Medicare with Medigap is worth looking at first, since you put keeping '
                                             'your doctors first. Then look at Medicare Advantage the same way.')
        self.assertEqual(out['reply'], one_call_flow.PLANS_READY_LINE)
        self.assertNotIn('notice', out)
        self.assertNotIn('I’ve noted', out['reply'])
        review = self.visit.tap({'type': 'review_plans'})['review']
        self.assertEqual(self.visit.tap({'type': 'confirm_plan_review', 'token': review['token']})['plansHandoff']['destination'],
                         'plans')

    def test_the_offer_button_alone_is_a_request_for_plans(self):
        # The button sends words this server issued, so code knows the request without the model.
        self.up_to_priorities()
        out = self.visit.say('What is a premium?', [message(reply('A general answer.'))])
        offer = [card for card in out.get('cards') or [] if card.get('kind') == 'next_step_offer']
        self.assertEqual([action['say'] for card in offer for action in card['actions']], [COMPARE])
        out = self.compare(TimeoutError('fictional: no reply at all'))          # no tool call was ever made
        self.assertEqual((self.one(out)['requests'], self.one(out)['toolCalls'], self.one(out)['plans']['requested']),
                         (1, 0, True))
        self.assertEqual(out['reply'], one_call_flow.PLANS_NOT_READY_LINE)
        self.assertEqual(self.asked(out), 'T08')
        out = self.visit.say(DETAILS, [save(update('T08', {'choice': 'local'}, 'I stay local'),
                                            update('T09', {'choice': 'lower_monthly'}, 'I want lower monthly payments'))],
                             [message(reply('Thank you.', question='Anything else?'))])
        self.handed_over(out)
        self.assertEqual(out['reply'], 'Thank you.')
        # The same words typed when no such button was on screen are an ordinary message.
        out = self.visit.say(COMPARE, [message(reply('We can keep going.', question='What else is on your mind?'))])
        self.assertFalse(self.one(out)['plans']['requested'])

    def test_a_request_before_the_details_are_in_ends_on_the_first_missing_detail(self):
        # The visit as listed: no answer yet about care away from home or about costs.
        out = self.up_to_priorities()
        self.assertEqual([item['id'] for item in out['planReadiness']['missing']], ['travel', 'costs'])
        out = self.compare()
        self.assertTrue(self.one(out)['fallback'])
        self.assertFalse(self.close(out))
        self.assertEqual(out['reply'], one_call_flow.PLANS_NOT_READY_LINE)
        self.assertNotIn('notice', out)
        self.assertEqual(self.asked(out), 'T08')
        self.assertEqual(out['assessment']['nextQuestion']['question'], self.flow.question('T08')['question'])
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'T08'})
        self.assertEqual(json.loads(self.script.sent[-1]['input'][-1]['output'])['missing'],
                         [{'id': 'T08', 'label': 'Routine care away from home'},
                          {'id': 'T09', 'label': 'Monthly payments and care costs'}])
        # The request stays owed: each turn ends on the next missing detail, whatever the model asks,
        # and the close appears as soon as the last one is in.
        out = self.visit.say('I stay local.', [save(update('T08', {'choice': 'local'}, 'I stay local'))],
                             [message(reply('Thank you.', question='Is there anything else on your mind?'))])
        self.assertFalse(self.close(out))
        self.assertEqual(self.asked(out), 'T09')
        self.assertNotIn('anything else on your mind', json.dumps(out))
        out = self.visit.say('Lower monthly payments, please.',
                             [save(update('T09', {'choice': 'lower_monthly'}, 'Lower monthly payments'))],
                             TimeoutError('fictional: no reply'), TimeoutError('fictional: no retry either'))
        self.handed_over(out)

    def test_a_request_for_plans_saves_the_goal_of_finding_coverage(self):
        # Without a goal of finding or reviewing coverage advisor-first has no checklist at all.
        self.opening()
        self.visit.tap({'type': 'choice', 'id': 'T01', 'fields': {'choice': 'learn'}}, consent=True)
        out = self.visit.say('Can I just see the plans?', [call('p1', 'offer_plans', {})],
                             TimeoutError('fictional: no reply'), TimeoutError('fictional: no retry either'))
        self.assertEqual(self.visit.value('intent.goal'), 'compare')
        self.assertTrue(out['planReadiness']['active'])
        self.assertEqual(out['reply'], one_call_flow.PLANS_NOT_READY_LINE)
        self.assertEqual(self.asked(out), out['planReadiness']['missing'][0]['question_id'])

    def test_the_close_does_not_depend_on_the_enrollment_statements_switch(self):
        self.assertFalse(one_call_tools.statement_cards_on())
        self.up_to_priorities(details='open_on_costs')
        brief = self.handed_over(self.compare())
        self.assertTrue(brief['direction'])
        self.assertTrue(brief['learned'] and brief['steps'] and brief['rows'])
        self.assertEqual([card.get('kind') for card in self.visit.outs[-1].get('cards') or []], [])

    def test_the_trace_says_why_the_close_was_or_was_not_shown(self):
        self.up_to_priorities()
        self.compare()
        line = self.last_trace()
        self.assertEqual((line['can_review'], line['missing_count'], line['plans_requested'], line['close_due'],
                          line['handoff_reason']), (False, 2, True, False, 'not_ready'))
        self.visit.say('I stay local and I want lower monthly payments.',
                       [save(update('T08', {'choice': 'local'}, 'I stay local'),
                             update('T09', {'choice': 'lower_monthly'}, 'I want lower monthly payments'))],
                       [message(reply('Thank you.'))])
        line = self.last_trace()
        self.assertEqual((line['can_review'], line['missing_count'], line['plans_requested'], line['close_due'],
                          line['handoff_reason']), (True, 0, True, True, 'close_shown'))
        self.visit.say('What is a premium?', [message(reply('A general answer.'))])
        line = self.last_trace()
        self.assertEqual((line['can_review'], line['plans_requested'], line['close_due'], line['handoff_reason']),
                         (True, False, False, 'already_shown'))
        for value in (OPENING, 'Wise', 'lisinopril', '34104'):
            self.assertNotIn(value, self.trace.read_text())
        self.assertEqual(self.one(self.visit.outs[-1])['plans'],
                         {'canReview': True, 'missingCount': 0, 'requested': False, 'closeDue': False, 'reason': 'already_shown'})


class OneRetryAfterAToolRound(OwnerVisit):
    REJECTED = [message(reply('Plan Zebra H1234 costs $17.50 a month for her.'))]

    def test_a_rejected_reply_after_a_save_gets_one_more_request(self):
        self.opening(); self.goal(); self.coverage()
        before = len(self.script.sent)
        out = self.doctor(self.REJECTED, [message(reply('I have noted Dr. Shannon Wise.'))])
        sent = self.script.sent[before:]
        self.assertEqual(len(sent), 3)                                   # the save, the reply, one retry
        self.assertEqual((self.one(out)['requests'], out['metrics']['llmCalls'], self.one(out)['retry'],
                          self.one(out)['fallback']), (3, 3, True, False))
        self.assertEqual(out['reply'], 'I have noted Dr. Shannon Wise.')
        self.assertEqual(self.visit.value('needs.providers'), 'Dr. Shannon Wise')
        retry = sent[2]
        self.assertEqual(retry['tool_choice'], 'none')
        kinds = [item.get('type', 'message') for item in retry['input']]
        self.assertEqual(kinds.count('function_call'), 1)
        self.assertEqual(kinds.count('function_call_output'), 1)        # the tool results are already in the input
        note = json.loads(retry['input'][0]['content'])['pending_note']
        self.assertIn('ungrounded', note)                                # codes only
        self.assertNotIn('Zebra', json.dumps(retry['input']))
        self.assertEqual(support.charge_rows(self.budget).count('uncertain'), 0)
        self.assertEqual(set(support.charge_rows(self.budget)), {'settled'})
        self.assertEqual(self.last_trace()['requests'], 3)

    def test_a_reply_lost_after_a_save_gets_one_more_request(self):
        self.opening(); self.goal(); self.coverage()
        before = len(self.script.sent)
        out = self.doctor([message('not the reply format')], [message(reply('I have noted Dr. Shannon Wise.'))])
        self.assertEqual(len(self.script.sent) - before, 3)
        self.assertEqual((self.one(out)['requests'], self.one(out)['retry'], self.one(out)['fallback']), (3, True, False))
        self.assertEqual(out['reply'], 'I have noted Dr. Shannon Wise.')
        self.assertEqual(self.script.sent[-1]['tool_choice'], 'none')

    def test_there_is_never_a_fourth_request(self):
        self.opening(); self.goal(); self.coverage()
        before = len(self.script.sent)
        out = self.doctor(self.REJECTED, self.REJECTED)
        self.assertEqual(len(self.script.sent) - before, 3)
        self.assertEqual((self.one(out)['requests'], self.one(out)['fallback'], self.one(out)['fallbackReason']),
                         (3, True, 'reply_rejected'))
        self.assertEqual(self.visit.value('needs.providers'), 'Dr. Shannon Wise')
        self.assertEqual(support.charge_rows(self.budget).count('uncertain'), 0)
        # A turn with no tool round keeps its one retry on the turn's own second stage: two requests.
        before = len(self.script.sent)
        out = self.visit.say('What is a premium?', self.REJECTED, self.REJECTED)
        self.assertEqual((len(self.script.sent) - before, self.one(out)['requests']), (2, 2))


class OneRejectedPointCostsOnePoint(unittest.TestCase):
    def test_the_instructions_ask_for_one_point_per_block_with_the_acknowledgement_first(self):
        core = (VARIANT / 'prompt/core.md').read_text()
        self.assertIn('Put each distinct point in its own block', core)
        self.assertIn('keep it in a short first block of its own', core)


class FallbackRepeatsOnlyWhatWasTyped(OwnerVisit):
    def test_a_saved_value_the_person_did_not_type_is_not_said_back(self):
        self.opening(); self.goal(); self.coverage()
        out = self.visit.say('The first one sounds right to me.',
                             [save(update('T09', {'choice': 'lower_monthly'}, 'The first one sounds right'))],
                             TimeoutError('fictional: no reply'), TimeoutError('fictional: no reply'))
        self.assertEqual(self.visit.value('needs.costPreference'), 'lower_monthly')
        self.assertTrue(self.one(out)['fallback'])
        self.assertNotIn('I’ve noted', out['reply'])
        self.assertNotIn('Lower monthly payments', out['reply'])
        self.assertTrue(out['reply'].strip())                            # advisor-first's reviewed statement instead

    def test_a_tapped_goal_label_is_not_echoed_when_the_compare_request_fails(self):
        self.up_to_priorities()
        out = self.compare()
        self.assertNotIn('Find coverage', out['reply'])

    def test_a_name_the_person_typed_is_still_said_back(self):
        self.opening(); self.goal(); self.coverage()
        out = self.doctor(TimeoutError('fictional: no reply'), TimeoutError('fictional: no reply'))
        self.assertEqual(out['reply'], 'I’ve noted Dr. Shannon Wise.')


# -- the reply check: acknowledging a doctor or a medicine is not claiming a check result ----------

DOCTOR_GROUND = {'person_text': [OPENING, COVERAGE, DOCTOR],
                 'reports': {'coverage_is_for': 'self', 'saved': [
                     {'id': 'T06', 'label': 'Doctors and hospitals', 'state': 'reported', 'value': 'Dr. Shannon Wise'}],
                     'states': {}},
                 'tool_outputs': [{'name': 'save_profile_fields', 'arguments': None, 'output': {
                     'ok': True, 'outcomes': [{'index': 0, 'id': 'T06', 'status': 'accepted', 'reason': 'explicit_report'}],
                     'open': ['T07', 'T08', 'T09', 'T10']}}],
                 'fact_texts': {}, 'open_ids': {'T07', 'T08', 'T09', 'T10'}}
MEDICINE_GROUND = {**DOCTOR_GROUND, 'person_text': [OPENING, COVERAGE, DOCTOR, MEDICINE],
                   'reports': {'coverage_is_for': 'self', 'saved': [
                       {'id': 'T06', 'label': 'Doctors and hospitals', 'state': 'reported', 'value': 'Dr. Shannon Wise'},
                       {'id': 'T07', 'label': 'Medicines', 'state': 'reported', 'value': 'lisinopril'}], 'states': {}}}

# Ordinary things to say when a doctor or a medicine has just been named. None states a result.
ACKNOWLEDGING_A_DOCTOR = (
    "I've noted Dr. Shannon Wise at her office on Goodlette-Frank Road.",
    "Thank you. I've saved Dr. Shannon Wise as a doctor you want to keep.",
    "Dr. Wise is on your list now. Whether she participates in any particular plan still has to be checked.",
    "Keeping Dr. Wise will be part of the comparison.",
    "Got it: Dr. Shannon Wise on Goodlette-Frank Road. Her participation in any plan hasn't been checked yet.",
    "I've added Dr. Wise. A plan's network decides whether a doctor is covered, so we'll look at that for each option.",
    "With Original Medicare, you can see any doctor who accepts Medicare. With a Medicare Advantage plan, the plan's network matters.",
    "Dr. Wise matters to you, so we'll check whether each plan includes her before you rely on it.",
    "I have Dr. Shannon Wise down. I haven't confirmed whether she is in any plan's network.",
    "Thanks. I can't tell you yet whether Dr. Wise is in network for any plan; that still needs checking.",
    "Dr. Wise is saved. Whether a plan covers visits to her depends on that plan's network.",
    "Dr. Wise is on record. I couldn't check her participation just now, so that stays open.",
    "Medicare Advantage plans have networks, so Dr. Wise would need to be in the plan's network.",
    "I've noted Dr. Wise. That way we can confirm she is covered by the plan you choose.",
    # These nine were rejected as claims of a check result before the rule was tightened.
    "We'll make sure Dr. Wise is covered under whatever you choose.",
    "We'll focus on plans that include Dr. Wise.",
    "Since keeping Dr. Wise is important, we'll make sure your doctor is covered before you pick anything.",
    "Dr. Wise is noted. You'll want a plan that covers your doctor.",
    "I've saved Dr. Wise. The goal is to find coverage where your doctor is in network.",
    "Dr. Wise is saved. A plan only works for you if Dr. Wise is covered.",
)
ACKNOWLEDGING_A_MEDICINE = (
    "I've noted lisinopril.",
    "Lisinopril is on your list. Whether a plan covers it, and at what cost, still has to be checked.",
    "I've added lisinopril. Each drug plan has its own list of covered medicines, so coverage can differ by plan.",
    "I have lisinopril down. Whether it's covered depends on each plan's drug list.",
    "I've saved lisinopril. If lisinopril is covered by a plan, the plan's tier decides your copay.",
    "Lisinopril is saved so we can check that your prescription is covered.",
    "Lisinopril is noted. A plan works for you only if lisinopril is covered.",
    "I've noted lisinopril. To make sure your prescription is covered, I'll need the strength.",
)
FIRST_REJECTED = {'doctor': 14, 'medicine': 5}       # where the formerly rejected examples start in each list
# Statements of a result nobody checked. Each must still be withheld.
CLAIMING_A_RESULT = (
    ('doctor', "Dr. Wise is in network."),
    ('doctor', "Good news: Dr. Wise is covered."),
    ('doctor', "I checked, and Dr. Wise is covered by most plans."),
    ('doctor', "I can confirm that Dr. Wise is in network."),
    ('doctor', "A quick check shows Dr. Wise is in network for most plans."),
    ('doctor', "Since Dr. Wise is in network, you can keep seeing her."),
    ('doctor', "I found plans that include Dr. Wise."),
    ('doctor', "Dr. Wise accepts Medicare."),
    ('doctor', "Your doctor is covered."),
    ('doctor', "We made sure Dr. Wise is covered."),
    ('medicine', "Lisinopril is covered."),
    ('medicine', "Lisinopril is on tier 1."),
    ('medicine', "Your prescription is covered by every plan."),
    ('medicine', "I checked that your prescription is covered."),
)


class AcknowledgingIsNotClaiming(unittest.TestCase):
    def rejected(self, text, ground):
        result = one_call_check.check_reply(reply(text), grounding=ground)
        return [item['code'] for item in result['rejected']]

    def test_ordinary_acknowledgements_of_a_named_doctor_pass(self):
        self.assertGreaterEqual(len(ACKNOWLEDGING_A_DOCTOR) + len(ACKNOWLEDGING_A_MEDICINE), 20)
        for text in ACKNOWLEDGING_A_DOCTOR:
            with self.subTest(text=text):
                self.assertEqual(self.rejected(text, DOCTOR_GROUND), [])

    def test_ordinary_acknowledgements_of_a_named_medicine_pass(self):
        for text in ACKNOWLEDGING_A_MEDICINE:
            with self.subTest(text=text):
                self.assertEqual(self.rejected(text, MEDICINE_GROUND), [])

    def test_a_stated_result_nobody_checked_is_still_withheld(self):
        for kind, text in CLAIMING_A_RESULT:
            with self.subTest(text=text):
                self.assertEqual(self.rejected(text, DOCTOR_GROUND if kind == 'doctor' else MEDICINE_GROUND),
                                 [one_call_check.UNGROUNDED_CHECK_CLAIM])


if __name__ == '__main__':
    unittest.main()
