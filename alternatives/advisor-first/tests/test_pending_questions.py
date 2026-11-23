"""D188: pending questions, passes, single-field targets and offers (:8895).

Real controller, scripted model outputs, fictional reports, no network. The
journey replays visit 12b0f11de2 (November 18, 2026) with the interpreter
proposals its log shows, plus the new pending_disposition code. These check
code behavior; they do not grade a live model's language or its choice of code.
"""
import json
import pathlib
import unittest
from datetime import date

import test_conversation_records as base
import conversation_records as records
import conversation_planner as planner
import question_progress

FIXTURE = json.loads((pathlib.Path(__file__).parent / 'fixtures/pending_question_20261118.json').read_text())
T1, T2, T3, TAP, T5 = [item['text'] for item in FIXTURE['original_inputs']]
NO_QUESTION = dict(reply='Drug coverage is separate from Parts A and B.', question_target=None, question='')
PART = {'subject': 'beneficiary', 'quote': 'I have A & B', 'status': 'active', 'month': None, 'year': None,
        'product': '', 'name': '', 'carrier': '', 'letter': ''}


class PendingBase(unittest.TestCase):
    """The D183 journey helpers, without inheriting its tests."""
    pending = True
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads', 'extracted_context',
                 'composed_context', 'interpreted', 'ask_recommended', 'capture', 'available', 'opening',
                 'ends_on_a_lead'):
        locals()[name] = getattr(base.RecordsJourney, name)
    update = staticmethod(base.RecordsJourney.update)
    extraction = staticmethod(base.RecordsJourney.extraction)

    def setUp(self):
        base.RecordsJourney.setUp(self)
        if self.pending:
            records.enable_pending(self.flow)
        records.TODAY = date(2026, 11, 18)

    def read(self, text, *, disposition=None, reason='goal', **kw):
        p = base.RecordsJourney.read(self, text, **kw)
        p['next_target']['reason'] = reason
        if disposition is not None and self.pending:        # not part of the contract with the switch off
            p['pending_disposition'] = disposition
        return p

    def say(self, text, compose=None, **kw):
        return self.message(text, extraction=self.read(text, **kw), compose=compose or self.ask_recommended())

    def ledger(self):
        return planner.state(self.flow, self.owner)['question_progress']

    def receipt(self, identifier):
        return next((r for k, r in self.ledger().items() if k.split('|')[0] == identifier), None)

    def trace(self, out):
        return out['metrics']['records']

    def asked(self, out):
        return (out['assessment'].get('nextQuestion') or {}).get('id')

    def offers(self, out):
        return [c for c in out.get('cards') or [] if c.get('kind') == 'next_step_offer']

    def first(self, parts=None):
        """Input 1, then input 2 (or "neither" for the variant without Parts A and B)."""
        ups = [self.update('RC01', {'choice': 'self'}, 'I am 65'), self.update('MG_AGE', {'choice': '65'}, 'I am 65'),
               self.update('T05', {'choice': 'employer'}, 'get off my employer plan'),
               self.update('T01', {'choice': 'compare'}, 'transition to Medicare'),
               self.update('RC09', {'choice': 'my_job'}, 'my employer plan')]
        retire = {'kind': 'retirement', 'subject': 'beneficiary', 'scope': 'intended', 'quote': 'retiring soon',
                  'uncertain': False, 'correction': False, 'month': None, 'year': None, 'first_day': None,
                  'first_day_quote': '', 'status': 'retiring', 'when': 'soon'}
        one = self.say(T1, updates=ups, targets=['RC04', 'RC11'], situation=[retire], disposition='none')
        if parts == 'neither':
            text = "I don't have Part A or Part B yet."
            two = self.say(text, updates=[self.update('RC04', {'choice': 'neither'}, text)], targets=['RC11'],
                           disposition='answered')
        else:
            two = self.say(T2, updates=[self.update('RC04', {'choice': 'both'}, 'I have A & B')], targets=['RC11'],
                           disposition='answered',
                           coverage_reports=[{**PART, 'kind': 'part_a'}, {**PART, 'kind': 'part_b'}])
        return one, two


class PendingJourney(PendingBase):
    def test_fixture_visit_fixed_flow(self):
        self.assertEqual(FIXTURE['today'], '2026-11-18')
        one, two = self.first()
        self.assertEqual(self.asked(one), 'RC04')
        # Turn 2: one field of RC11 (the insurance end) is delivered and marked pending.
        q = two['assessment']['nextQuestion']
        self.assertEqual((q['id'], [f['key'] for f in q['fields']]), ('RC11', ['coverageEnd']))
        self.assertEqual(self.trace(two)['pending_field'], 'RC11.coverageEnd')
        self.assertFalse(self.trace(two)['returned'])
        self.assertEqual(self.trace(two)['pending_disposition'], 'answered')    # RC04, asked in turn 1
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC11', self.ledger()), 'pending')
        # Turn 3: a detour. The composer, as in the log, writes no question.
        three = self.say(T3, updates=[self.update('RC04', {'choice': 'both'}, 'the A and B i have')], targets=[],
                         mode='discuss', task='', disposition='detour', compose=NO_QUESTION,
                         coverage_reports=[{**PART, 'kind': 'part_a', 'quote': 'the A and B i have'},
                                           {**PART, 'kind': 'part_b', 'quote': 'the A and B i have'}])
        plan = self.composed_context()['discussion_plan']
        self.assertEqual(plan['available_questions'], ['RC11'])
        self.assertEqual(plan['next_question'], 'RC11')
        self.assertEqual({k: plan['pending_question'][k] for k in ('id', 'fields', 'returning', 'delivered')},
                         {'id': 'RC11', 'fields': ['coverageEnd'], 'returning': True, 'delivered': 1})
        q = three['assessment']['nextQuestion']
        self.assertEqual((q['id'], [f['key'] for f in q['fields']]), ('RC11', ['coverageEnd']))
        self.assertEqual(self.offers(three), [])
        t = self.trace(three)
        self.assertEqual((t['pending_disposition'], t['passes'], t['deliveries'], t['returned'], t['offer_button']),
                         ('detour', 0, 2, True, False))
        # The date, given plainly, fills that field in the same turn.
        four = self.say(T5, updates=[self.update('RC11', {'coverageEnd': '2026-11-30'}, T5)], targets=[],
                        disposition='answered')
        self.assertEqual(self.capture(four).get('RC11'), 'accepted')
        self.assertEqual(self.flow.report(self.r, 'RC11').get('coverageEnd'), '2026-11-30')
        t = self.trace(four)
        self.assertFalse(t['confirmations_queued'])
        self.assertEqual(t['pending_disposition'], 'answered')
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertFalse([row for row in four['questionProgress'] if row['state'] == 'parked'])
        # The job end is not asked on its own: no readiness view needs it.
        self.assertNotEqual(self.asked(four), 'RC11')
        self.assertNotIn('RC11', self.composed_context()['discussion_plan']['available_questions'])
        self.assertNotIn('RC11', [i for o in records.readiness(self.flow, self.owner, self.g, self.r,
                                  planner.state(self.flow, self.owner))['outcomes'].values() for i in o.get('needs') or []])
        # No field asked as new twice; no offer repeated.
        outs = [one, two, three, four]
        new = [self.trace(o)['delivered_target'] for o in outs if not self.trace(o)['returned']]
        new = [i for i in new if i]
        self.assertEqual(len(new), len(set(new)), new)
        self.assertLessEqual(sum(len(self.offers(o)) for o in outs), 1)
        # As logged the person has Parts A and B, so the existing window code gives no card.
        self.assertEqual(self.trace(four)['timing_card_ready'], FIXTURE['expected']['timing_card_ready']['as_logged'])
        for o in outs:      # codes only, never words
            self.assertNotIn('Nov 30', json.dumps(self.trace(o)))

    def test_timing_card_is_ready_from_the_one_date_when_parts_are_not_in_place(self):
        one, two = self.first(parts='neither')
        self.assertEqual([f['key'] for f in two['assessment']['nextQuestion']['fields']], ['coverageEnd'])
        out = self.say(T5, updates=[self.update('RC11', {'coverageEnd': '2026-11-30'}, T5)], targets=['RC10'],
                       disposition='answered')
        self.assertTrue(self.trace(out)['timing_card_ready'])
        card = next(c for c in out.get('cards') or [] if c.get('kind') == 'enrollment_timing')
        values = {row['label']: row['value'] for row in card['rows']}
        for label, value in FIXTURE['expected']['timing_card_variant'].items():
            self.assertEqual(values[label], value)
        self.assertNotEqual(self.asked(out), 'RC11')          # the job end is not needed for the window

    def test_both_dates_in_one_message_are_still_captured(self):
        """job_coverage_20261117 with the pending switch on."""
        asked = [self.asked(self.opening())]
        text = "I don't have Part A or Part B yet."
        asked.append(self.asked(self.say(text, updates=[self.update('RC04', {'choice': 'neither'}, text)],
                                         targets=['RC10'], disposition='answered')))
        self.compositions.append(self.ask_recommended(target='RC11'))
        out = self.turn({'type': 'choice', 'id': 'RC10', 'fields': {'choice': 'yes'}})
        asked.append(self.asked(out))
        self.assertEqual([f['key'] for f in out['assessment']['nextQuestion']['fields']], ['coverageEnd'])
        ups = [self.update('RC11', {'jobEnd': '2026-11-21', 'coverageEnd': '2026-11-30'}, base.DATES)]
        out = self.say(base.DATES, updates=ups, targets=['RC12'], disposition='answered')
        asked.append(self.asked(out))
        self.assertEqual(asked, ['RC04', 'RC10', 'RC11', 'RC12'])
        report = self.flow.report(self.r, 'RC11')
        self.assertEqual((report['jobEnd'], report['coverageEnd']), ('2026-11-21', '2026-11-30'))


class PendingRules(PendingBase):
    def test_two_passes_park(self):
        one, _ = self.first()[0], None
        self.assertEqual(self.receipt('RC11')['pending']['id'], 'RC11')
        out = self.say('Let’s skip that one.', targets=['T03'], disposition='passed')
        self.assertNotEqual(self.asked(out), 'RC11')                  # not re-asked in the reply that passed it
        self.assertEqual(self.receipt('RC11').get('passes'), 1)
        self.assertEqual(self.trace(out)['pending_disposition'], 'passed')
        self.assertEqual(self.asked(out), 'T03')
        out = self.say('34102', updates=[self.update('T03', {'zip': '34102'}, '34102')], targets=['RC11'],
                       disposition='answered')
        self.assertEqual(self.asked(out), 'RC11')                     # open again: one pass does not park
        self.assertEqual(self.receipt('RC11')['shown'], 2)
        out = self.say('I would rather not say.', targets=['T03'], disposition='passed')
        self.assertEqual(self.receipt('RC11').get('passes'), 2)
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC11', self.ledger()), 'parked')
        out = self.say('Go on.', targets=['RC11'], disposition='none')
        self.assertNotEqual(self.asked(out), 'RC11')
        self.assertTrue(any(row['question_id'] == 'RC11' and row['state'] == 'parked' for row in out['questionProgress']))

    def test_three_detours_do_not_park_and_four_deliveries_do(self):
        self.first()
        for n in (2, 3, 4):
            out = self.say('And what does Part B cover again?', targets=[], mode='discuss', task='',
                           disposition='detour', compose=NO_QUESTION)
            self.assertEqual(self.asked(out), 'RC11', n)
            self.assertEqual((self.trace(out)['deliveries'], self.trace(out)['passes']), (n, 0))
        self.assertEqual(records.DELIVERY_CAP, 4)
        out = self.say('One more thing about Part A.', targets=[], mode='discuss', task='', disposition='detour',
                       compose=NO_QUESTION)
        self.assertNotEqual(self.asked(out), 'RC11')
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC11', self.ledger()), 'parked')

    def test_a_tentative_answer_is_not_a_pass_and_a_queued_confirmation_is_never_parked(self):
        self.first()
        text = 'I think Nov 30 2026'
        out = self.say(text, updates=[self.update('RC11', {'coverageEnd': '2026-11-30'}, text, uncertain=True)],
                       targets=[], disposition='passed')
        self.assertEqual(self.capture(out).get('RC11'), 'needs_clarification')
        self.assertTrue(self.trace(out)['confirmations_queued'])
        self.assertFalse(self.receipt('RC11').get('passes'))
        self.assertEqual(self.trace(out)['pending_disposition'], 'answered')   # a queued confirmation, by structure
        # Even with the pass count forced up, a field with a confirmation waiting is not parked.
        self.receipt('RC11')['passes'] = 5
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC11', self.ledger()), 'conflicting')
        q = self.flow.question('RC11', ['coverageEnd'])
        question_progress.filter_candidates(self.flow, self.owner, self.g, self.r, [{'id': 'RC11', 'question': q}], self.ledger())
        self.assertFalse(self.receipt('RC11').get('parked'))

    def test_person_raised_releases_the_pending_question_without_a_pass(self):
        self.first()
        text = 'Actually I want to keep my doctors.'
        out = self.say(text, updates=[self.update('T10', {'choice': 'doctors'}, 'I want to keep my doctors')],
                       targets=['T06'], reason='person_raised', disposition='detour')
        self.assertEqual(self.asked(out), 'T06')
        self.assertFalse(self.receipt('RC11').get('passes'))
        self.assertFalse(self.receipt('RC11').get('pending'))
        self.assertEqual(self.trace(out)['pending_disposition'], 'released')
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC11', self.ledger()), 'open')

    def test_answered_without_a_capture_is_treated_as_a_detour(self):
        self.first()
        out = self.say('Sure.', targets=['T03'], disposition='answered')
        self.assertEqual(self.asked(out), 'RC11')
        t = self.trace(out)
        self.assertEqual((t['pending_disposition'], t['passes'], t['returned']), ('detour', 0, True))

    def test_does_not_know_is_set_aside_for_the_visit_without_a_pass(self):
        self.first()
        out = self.say('No idea, honestly.', targets=[], disposition='does_not_know')
        self.assertNotEqual(self.asked(out), 'RC11')
        self.assertFalse(self.receipt('RC11').get('passes'))
        self.assertIn('RC11', planner.state(self.flow, self.owner)['deferred'])

    def test_narrowing_covers_every_multi_field_meaning(self):
        rows = {row['id']: row for row in records.multi_field_inventory()}
        self.assertEqual(rows['RC11']['narrowed'], ['coverageEnd', 'jobEnd'])     # insurance end, then job end
        narrowed = sorted(i for i, row in rows.items() if row['narrowed'] and row['asked_by_records'])
        self.assertEqual(narrowed, ['RC11'])
        for identifier in ('T04', 'T06', 'T07', 'RC05', 'RC08', 'RC12', 'RC16', 'RC20', 'RC25', 'S_AGE65', 'S_RETIREMENT'):
            self.assertIn(identifier, rows)
            self.assertFalse(rows[identifier]['narrowed'], identifier)         # a status with its detail stays whole
        # Derived from field kinds, not from a list of question IDs.
        self.assertNotIn('RC11', json.dumps(records.VALUE_KIND))
        self.first()
        for identifier in records.target_ids():
            q = records._question(self.flow, self.g, self.r, identifier)
            kinds = [records.VALUE_KIND.get(f['key'], f['key']) for f in (q or {}).get('fields', [])]
            self.assertEqual(len(kinds), len(set(kinds)), identifier)

    def test_interpreter_contract_is_one_enum(self):
        self.assertEqual(records.DISPOSITIONS, ('answered', 'detour', 'passed', 'does_not_know', 'none'))
        for good in records.DISPOSITIONS:
            self.assertEqual(records.validate_pending_disposition(good), good)
        for bad in (None, 'Answered', 'skip', 3, ['passed']):
            self.assertEqual(records.validate_pending_disposition(bad), 'none')
        self.first()
        context = self.extracted_context()
        self.assertEqual(context['profile_record']['pending']['id'], 'RC04')
        schema = next(c for c in reversed(self.calls) if c['text']['format']['name'] == 'daylight_guide_commands')
        self.assertEqual(schema['text']['format']['schema']['properties']['pending_disposition']['enum'],
                         list(records.DISPOSITIONS))
        import conversation_prompts
        self.assertLess(len(conversation_prompts.INTERPRETATION_PENDING), 8500)


class Offers(PendingBase):
    def test_an_accepted_offer_is_not_offered_again_and_sets_the_task(self):
        self.first()
        four = self.say(T5, updates=[self.update('RC11', {'coverageEnd': '2026-11-30'}, T5)], targets=[],
                        disposition='answered')
        state = planner.state(self.flow, self.owner)
        shown = records.next_offer(state, 'self')
        self.assertIsNotNone(shown)
        records.record_offer(state, shown['task'], shown['card'])
        say = shown['card']['actions'][0]['say']
        out = self.say(say, targets=[], mode='discuss', task='', disposition='none')
        t = self.trace(out)
        self.assertEqual(t['offers']['accepted'], [shown['task']])
        self.assertEqual(state['active_task'], shown['task'])
        self.assertIsNotNone(out['assessment'].get('nextQuestion'))            # goes to an open field, not another offer
        again = records.next_offer(state, 'self')
        self.assertNotEqual((again or {}).get('task'), shown['task'])

    def test_an_offer_shown_twice_and_not_taken_is_not_shown_a_third_time(self):
        state = {'suggested_task': 'providers', 'active_task': ''}
        tasks = []
        for _ in range(3):
            offer = records.next_offer(state, 'self')
            records.record_offer(state, offer['task'], offer['card'])
            tasks.append(offer['task'])
        self.assertEqual(tasks[:2], ['providers', 'providers'])
        self.assertNotEqual(tasks[2], 'providers')
        self.assertEqual(state['records_offers']['providers']['shown'], 2)

    def test_typed_words_are_not_a_tap(self):
        state = {'suggested_task': 'timing', 'active_task': ''}
        offer = records.next_offer(state, 'self')
        records.record_offer(state, offer['task'], offer['card'])
        self.assertIsNone(records.accept_offer(state, 'yes please work out my timing'))
        self.assertEqual(records.accept_offer(state, offer['card']['actions'][0]['say']), 'timing')
        self.assertTrue(state['records_offers']['timing']['accepted'])
        self.assertIsNone(records.accept_offer(state, offer['card']['actions'][0]['say']))   # taken once


class SwitchOff(PendingBase):
    pending = False

    def test_switch_off_restores_current_behavior(self):
        """The visit as logged: two-date question, the detour drops it, an offer button appears."""
        self.assertFalse(records.pending_on(self.flow))
        one, two = self.first()
        q = two['assessment']['nextQuestion']
        self.assertEqual((q['id'], q.get('fields')), ('RC11', []))
        self.assertEqual(q['question'], 'When do the job and its insurance end?')
        three = self.say(T3, targets=[], mode='discuss', task='', disposition='detour', compose=NO_QUESTION)
        self.assertNotEqual(self.asked(three), 'RC11')
        self.assertNotIn('pending_question', self.composed_context()['discussion_plan'])
        self.assertNotIn('pending_field', self.trace(three))
        self.assertNotIn('pending', self.extracted_context()['profile_record'])
        schema = next(c for c in reversed(self.calls) if c['text']['format']['name'] == 'daylight_guide_commands')
        self.assertNotIn('pending_disposition', schema['text']['format']['schema']['properties'])
        self.assertFalse(any('pending' in r or 'passes' in r for r in self.ledger().values()))

    def test_environment_switch(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'DAYLIGHT_PENDING': '0'}):
            self.assertFalse(records.pending_switch_on())
        with patch.dict(os.environ, {'DAYLIGHT_PENDING': '1'}):
            self.assertTrue(records.pending_switch_on())


class RecordsWithPending(base.RecordsJourney):
    """Every D183 journey test again, with the pending switch on (same pinned day)."""

    # With a question pending, a new subject wins only when the interpreter marks
    # it person_raised (spec, item 1). These D183 scripts raise doctors while
    # another question is waiting, so the stub says so here. Whether the live
    # interpreter does is for a live run to show.
    RAISED = ('sure, I want to keep my doctors', 'I want to keep my doctors and my medicines covered.')

    def setUp(self):
        base.RecordsJourney.setUp(self)
        records.enable_pending(self.flow)

    def read(self, text, **kw):
        p = base.RecordsJourney.read(self, text, **kw)
        if text in self.RAISED:
            p['next_target']['reason'] = 'person_raised'
        return p


if __name__ == '__main__':
    unittest.main()
