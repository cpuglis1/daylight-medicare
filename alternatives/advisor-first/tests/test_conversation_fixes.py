"""D190: five conversation fixes from visit a912962310 (:8895, November 18, 2026).

Real controller, scripted model outputs, fictional reports, no network. These
check code behavior; they do not grade a live model's language.
"""
import unittest
from datetime import date

import test_pending_questions as pending
import conversation_planner as planner
import conversation_records as records
import medigap_profile
import plans_fixes

TURNING = "I'm turning 65 next month and already have Medicare parts A and B."
AGAIN = "I told you i'm turning 65 next month"
FALLBACK = 'I don’t have a reliable answer to that yet.'
REJECTED = dict(reply='You should choose the first plan.', question_target=None, question='')


def age65(quote, relative=None):
    proposal = {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'intended', 'quote': quote, 'uncertain': False,
                'correction': False, 'month': None, 'year': None, 'first_day': None, 'first_day_quote': '',
                'status': '', 'when': ''}
    if relative:
        proposal['relative_month'] = relative
    return proposal


class Base(pending.PendingBase):
    fixes = True

    def setUp(self):
        pending.PendingBase.setUp(self)
        plans_fixes.enable(self.flow)
        if self.fixes:
            records.enable_fixes(self.flow)

    def start(self, relative='next_month'):
        ups = [self.update('RC01', {'choice': 'self'}, "I'm turning 65"),
               self.update('RC04', {'choice': 'both'}, 'already have Medicare parts A and B')]
        return self.say(TURNING, updates=ups, targets=[], disposition='none',
                        situation=[age65("I'm turning 65 next month", relative if self.fixes else None)])

    def missing(self):
        return medigap_profile.for_flow(self.flow, self.g, self.r)['missing']


class RelativeMonth(Base):
    def test_turning_65_next_month_is_saved_and_the_age_is_not_asked(self):
        out = self.start()
        self.assertEqual(self.capture(out).get('S_AGE65'), 'accepted', out['metrics'].get('capture'))
        self.assertEqual({k: self.flow.value(self.g, 'situation.age65')[k] for k in ('month', 'year')},
                         {'month': 12, 'year': 2026})                   # today is pinned to 2026-11-18
        self.assertNotIn('MG_AGE', self.missing())
        self.assertTrue(records.age_view(self.flow, self.g)['turns_65'], '2026-12')

    def test_repeating_it_answers_the_pending_age_question(self):
        ups = [self.update('RC01', {'choice': 'self'}, 'I already have'),
               self.update('RC04', {'choice': 'both'}, 'I already have Medicare parts A and B')]
        self.say('I already have Medicare parts A and B.', updates=ups, targets=['MG_AGE'], disposition='none')
        ledger = planner.state(self.flow, self.owner)['question_progress']
        question = medigap_profile.question('MG_AGE', 'self')
        ledger['MG_AGE|profile|choice'] = {'question': question, 'shown': 1,
                                           'pending': {'id': 'MG_AGE', 'fields': [], 'revision': [0, 0], 'returned': False}}
        for receipt in ledger.values():
            if receipt.get('pending', {}).get('id') != 'MG_AGE':
                receipt.pop('pending', None)
        out = self.say(AGAIN, targets=[], disposition='answered', situation=[age65("i'm turning 65 next month", 'next_month')])
        self.assertEqual(self.capture(out).get('S_AGE65'), 'accepted')
        self.assertEqual(out['metrics']['records']['pending_disposition'], 'answered')
        self.assertNotEqual(self.asked(out), 'MG_AGE')

    def test_month_arithmetic(self):
        base = age65('I turn 65 next month')
        resolve = lambda rel, today: records.resolve_relative_month({**base, 'relative_month': rel}, today)
        self.assertEqual([resolve('next_month', date(2026, 12, 10))[k] for k in ('month', 'year')], [1, 2027])
        self.assertEqual([resolve('this_month', date(2026, 11, 18))[k] for k in ('month', 'year')], [11, 2026])
        self.assertEqual([resolve('last_month', date(2027, 1, 5))[k] for k in ('month', 'year')], [12, 2026])
        self.assertIsNone(resolve('none', date(2026, 11, 18))['month'])
        named = records.resolve_relative_month({**base, 'month': 3, 'relative_month': 'next_month'}, date(2026, 11, 18))
        self.assertEqual(named['month'], 3)                              # a named month is never overridden
        retire = records.resolve_relative_month({**base, 'kind': 'retirement', 'relative_month': 'next_month'}, date(2026, 11, 18))
        self.assertIsNone(retire['month'])
        self.assertNotIn('relative_month', resolve('next_month', date(2026, 11, 18)))

    def test_interpreter_contract_adds_one_code(self):
        self.start()
        call = next(c for c in reversed(self.calls) if c['text']['format']['name'] == 'daylight_guide_commands')
        item = call['text']['format']['schema']['properties']['situation_proposals']['items']
        self.assertEqual(item['properties']['relative_month']['enum'], list(records.RELATIVE_MONTHS))


class SavedAnswers(Base):
    def turn_with_rejected_reply(self):
        self.start()
        text = 'Local only, but yes i just checked its creditable'
        ups = [self.update('T08', {'choice': 'local'}, 'Local only')]
        return self.say(text, updates=ups, targets=[], disposition='answered', compose=REJECTED)

    def test_a_rejected_reply_acknowledges_what_was_saved_and_keeps_a_lead(self):
        out = self.turn_with_rejected_reply()
        self.assertEqual(self.capture(out).get('T08'), 'accepted')
        self.assertNotIn(FALLBACK, out['reply'])
        self.assertTrue(out['reply'].startswith(records.SAVED_PREFIX), out['reply'])
        self.assertIn('Local', out['reply'])
        self.assertNotIn('choose the first plan', out['reply'])
        self.assertTrue(self.ends_on_a_lead(out), (out['assessment'].get('nextQuestion'), out.get('cards')))

    def test_nothing_saved_keeps_the_stock_sentence(self):
        self.start()
        out = self.say('Which one is best?', targets=[], disposition='none', compose=REJECTED)
        self.assertFalse(out['reply'].startswith(records.SAVED_PREFIX))


class PreClose(Base):
    def test_answer_first_rule_travels_with_a_pre_close_detail(self):
        state = {'records_preclose': True}
        moves = [{'id': 'MG_AGE'}]
        self.assertEqual(records.pre_close_plan(self.flow, state, moves), {'id': 'MG_AGE', 'rule': records.ANSWER_FIRST_RULE})
        self.assertIsNone(records.pre_close_plan(self.flow, {'records_preclose': False}, moves))
        self.assertIsNone(records.pre_close_plan(self.flow, state, []))

    def test_the_planner_marks_the_pre_close_ask(self):
        import inspect
        source = inspect.getsource(planner.refine)
        self.assertIn("s['records_preclose'] = bool(timed)", source)
        self.assertIn('pre_close_plan', inspect.getsource(planner.prepare))


class SwitchOff(Base):
    fixes = False

    def test_switch_off_is_the_logged_behavior(self):
        self.assertFalse(records.fixes_on(self.flow))
        out = self.start()
        got = {i['target']: (i['status'], i['reason']) for i in out['metrics'].get('capture') or []}
        self.assertEqual(got.get('S_AGE65'), ('unsupported', 'invalid_situation_value'))
        self.assertIn('MG_AGE', self.missing())
        call = next(c for c in reversed(self.calls) if c['text']['format']['name'] == 'daylight_guide_commands')
        self.assertNotIn('relative_month', call['text']['format']['schema']['properties']['situation_proposals']['items']['properties'])
        text = 'Local only, but yes i just checked its creditable'
        out = self.say(text, updates=[self.update('T08', {'choice': 'local'}, 'Local only')], targets=[],
                       disposition='answered', compose=REJECTED)
        self.assertFalse(out['reply'].startswith(records.SAVED_PREFIX))     # the stock recovery text, as before
        self.assertNotIn('Local', out['reply'])
        self.assertNotIn('pre_close_detail', planner.state(self.flow, self.owner)['plan'])

    def test_environment_switch(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'DAYLIGHT_CONVERSATION_FIXES': '0'}):
            self.assertFalse(records.fixes_switch_on())


if __name__ == '__main__':
    unittest.main()
