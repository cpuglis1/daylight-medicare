"""The background record pass: advisor-first's extraction stage, run after the reply.

Offline: scripted transport, temporary budget ledger, sockets forbidden,
fictional people. The worker runs at once here (an injected executor) except
in the one test that uses the default thread. A scripted extraction stands in
for the model; nothing here shows what a live model would find.
"""
import copy
import json
import logging
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

from natural_flow import CONTEXT_POLICY

import _one_call_support as support
from _one_call_support import Script, Visit, extraction, extraction_update, message, reply, save, update
import one_call_reconcile
from one_call_reconcile import Reconciler, tool_updates

CANARY = 'ZEBRAFINCH'


class Conversion(unittest.TestCase):
    def test_every_kind_of_proposal_becomes_a_save_tool_update(self):
        result = extraction(
            [extraction_update('T03', {'zip': '34102'}, 'I live in 34102'),
             {**extraction_update('RC21', {'name': 'Dr. Vale'}, 'Dr. Vale'), 'entity': 'doctor-1', 'direct_choice': True}],
            situation_proposals=[
                {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'current', 'quote': 'I turn 65 in March 2027',
                 'uncertain': False, 'correction': False, 'month': 3, 'year': 2027, 'first_day': True,
                 'first_day_quote': '', 'status': '', 'when': '', 'relative_month': 'none'},
                {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'current', 'quote': 'next month', 'uncertain': False,
                 'correction': False, 'month': None, 'year': None, 'first_day': None, 'status': '', 'when': '',
                 'relative_month': 'next_month'},
                {'kind': 'retirement', 'subject': 'beneficiary', 'scope': 'intended', 'quote': 'retiring in June',
                 'uncertain': True, 'correction': False, 'month': None, 'year': None, 'status': 'retiring', 'when': 'in June'}],
            coverage_reports=[
                {'kind': 'birth', 'subject': 'beneficiary', 'quote': 'born in March 1962', 'status': '', 'month': 3,
                 'year': 1962, 'product': '', 'name': '', 'carrier': '', 'letter': ''},
                {'kind': 'part_a', 'subject': 'beneficiary', 'quote': 'I have Part A', 'status': 'active', 'month': None,
                 'year': None, 'product': '', 'name': '', 'carrier': '', 'letter': ''},
                {'kind': 'held_plan', 'subject': 'beneficiary', 'quote': 'my Plan G', 'status': '', 'month': None,
                 'year': None, 'product': 'medigap', 'name': '', 'carrier': '', 'letter': 'G'}])
        updates = tool_updates(result)
        shape = {'id', 'entity', 'fields', 'quote', 'subject', 'scope', 'uncertain', 'correction'}
        self.assertTrue(all(set(item) == shape for item in updates))
        fields = [(item['id'], item['entity'], {pair['key']: pair['value'] for pair in item['fields']}) for item in updates]
        self.assertEqual(fields, [
            ('T03', None, {'zip': '34102'}),
            ('RC21', 'doctor-1', {'name': 'Dr. Vale'}),
            ('S_AGE65', None, {'month': '3', 'year': '2027', 'firstOfMonth': 'yes'}),
            ('S_AGE65', None, {'relativeMonth': 'next_month'}),
            ('S_RETIREMENT', None, {'status': 'retiring', 'when': 'in June'}),
            ('S_AGE65', None, {'birthMonth': '3', 'birthYear': '1962'}),
            ('COV_PART_A', None, {'status': 'active'}),
            ('COV_PLAN', None, {'product': 'medigap', 'letter': 'G'})])
        self.assertTrue(updates[4]['uncertain'])
        self.assertEqual(tool_updates(None), [])
        self.assertEqual(tool_updates({'updates': [{'id': 'T03'}, 'nonsense']}), [])

    def test_the_switch_defaults_on_and_zero_turns_it_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(one_call_reconcile.SWITCH, None)
            self.assertTrue(one_call_reconcile.switch_on())
            self.assertTrue(Reconciler(None).enabled)
            os.environ[one_call_reconcile.SWITCH] = '0'
            self.assertFalse(one_call_reconcile.switch_on())
            self.assertFalse(Reconciler(None).enabled)
            self.assertTrue(Reconciler(None, enabled=True).enabled)


@unittest.skipUnless(support.READY, support.NOT_READY)
class ReconcileCase(unittest.TestCase):
    reconcile = True

    def setUp(self):
        support.offline(self)
        support.pin_today(self)
        self.script = Script()
        self.flow = support.make_flow(self.script, reconcile=self.reconcile)
        self.budget = support.temporary_ledger(self, self.flow.agent)
        self.visit = Visit(self, self.flow, self.script)
        self.visit.start()

    def stats(self):
        return dict(self.flow.reconciler.stats)


class Supplies(ReconcileCase):
    TEXT = 'This coverage is for me, and my ZIP code is 34102.'

    def forgetful_turn(self):
        """The scripted main call saves who it is for and forgets the ZIP; the record pass finds the ZIP."""
        self.script.extractions.append(extraction([
            extraction_update('RC01', {'choice': 'self'}, 'This coverage is for me'),
            extraction_update('T03', {'zip': '34102'}, 'my ZIP code is 34102')]))
        return self.visit.say(self.TEXT, [save(update('RC01', {'choice': 'self'}, 'This coverage is for me'))],
                              [message(reply('Thank you.', question='What would you like help with?', target='T01'))])

    def test_a_fact_the_main_call_missed_is_applied_at_the_start_of_the_next_turn(self):
        visit = self.visit
        out = self.forgetful_turn()
        self.assertEqual(out['metrics']['oneCall']['reconciled'], 0)
        # Nothing changed between turns: the browser's state has no ZIP yet.
        self.assertIsNone(visit.value('comparison.scope.zip'))
        self.assertEqual(visit.value('subject.role'), 'self')
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 1)
        self.assertEqual(self.stats(), {'scheduled': 1, 'proposals': 2, 'already_known': 1, 'held': 1, 'completed': 1})
        # The pass used advisor-first's own extraction request against the post-turn state.
        sent = json.loads(self.script.extraction_sent[0]['input'][0]['content'])
        self.assertEqual(sent['submitted_text'], self.TEXT)
        self.assertEqual(self.script.extraction_sent[0]['text']['format']['name'], 'daylight_guide_commands')
        self.assertIn('RC01', sent['confirmed_context']['profile_record']['reported'])
        self.assertEqual(sent['confirmed_context']['recent_exchanges'], [])

        out = visit.say('What should I look at first?', [message(reply('Here is a good first step.'))])
        self.assertEqual(visit.value('comparison.scope.zip'), '34102')
        self.assertEqual(out['metrics']['oneCall']['reconciled'], 1)
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 0)
        turn = self.script.inputs()[-1]
        # The main call saw the fact as saved, and was told which field code filled in. Ids only.
        self.assertIn('T03', {row['id'] for row in turn['profile']['saved']})
        self.assertIn('T03', turn['pending_note'])
        self.assertNotIn('34102', turn['pending_note'])
        self.assertNotIn('T03', {item['id'] for item in turn['open_items']})
        self.assertEqual(self.stats()['applied'], 1)

    def test_the_pass_has_its_own_budget_reservation(self):
        self.forgetful_turn()
        # Two settled rows for the turn's two requests and one for the record pass. None left uncertain.
        self.assertEqual(support.charge_rows(self.budget), ['settled', 'settled', 'settled'])

    def test_a_held_fact_is_not_applied_once_its_field_is_no_longer_open(self):
        visit = self.visit
        self.forgetful_turn()
        visit.tap({'type': 'choice', 'id': 'T03', 'fields': {'zip': '34105'}})
        self.assertEqual(visit.value('comparison.scope.zip'), '34105')
        out = visit.say('What next?', [message(reply('Here is what is next.'))])
        self.assertEqual(visit.value('comparison.scope.zip'), '34105')     # the person's own later answer stands
        self.assertEqual(out['metrics']['oneCall']['reconciled'], 0)
        self.assertEqual(self.stats()['not_open'], 1)
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 0)
        self.assertIsNone(self.script.inputs()[-1]['pending_note'])

    def test_held_facts_survive_a_turn_that_fails_before_it_is_delivered(self):
        visit = self.visit
        self.forgetful_turn()
        self.flow.agent.enabled = False                                    # the next turn is refused outright
        with self.assertRaises(Exception):
            self.flow.turn(visit.owner, visit.payload({'type': 'message', 'message': 'Hello?'}))
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 1)
        self.flow.agent.enabled = True
        visit.say('Hello again.', [message(reply('Hello.'))])
        self.assertEqual(visit.value('comparison.scope.zip'), '34102')

    def test_what_the_gates_refuse_is_not_held(self):
        self.script.extractions.append(extraction([
            extraction_update('T03', {'zip': '34102'}, 'a quote that is not in the message'),
            extraction_update('T05', {'choice': 'employer'}, 'work', uncertain=True)]))
        self.visit.say('I get my insurance through work, I think.', [message(reply('Thank you.'))])
        self.assertEqual(self.flow.reconciler.held(self.visit.owner, self.visit.chain), 0)
        stats = self.stats()
        self.assertEqual(stats.get('held', 0), 0)
        # advisor-first's own extraction validator drops the unsupported quote; the save tool's
        # gate turns the tentative report into a confirmation, which this pass does not hold.
        self.assertEqual(stats['proposals'], 1)
        self.assertEqual(stats.get('needs_confirmation', 0) + stats.get('rejected', 0), 1)

    def test_it_never_guesses_who_the_coverage_is_for(self):
        # The extraction stage proposes nothing about the person; nothing is saved about them.
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'ZIP is 34102')]))
        self.visit.say('I am helping my mother. Her ZIP is 34102.', [message(reply('Glad to help.'))])
        self.visit.say('Where do we start?', [message(reply('Here.'))])
        self.assertIsNone(self.visit.value('subject.role'))


class ClearedVisits(ReconcileCase):
    """A pass belongs to the permission it was queued under (the reviewer's race)."""

    def queue_a_pass(self):
        visit = self.visit
        visit.say("It's for me.", [save(update('RC01', {'choice': 'self'}, "It's for me"))], [message(reply('Thank you.'))])
        queued = []
        self.flow.reconciler.executor = queued.append                     # the worker has not run yet
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'my ZIP is 34102')]))
        visit.say('my ZIP is 34102', [message(reply('Thank you.'))])      # the main call forgot to save it
        self.assertEqual(len(queued), 1)
        return queued, len(self.script.extraction_sent)

    def test_a_queued_pass_sends_nothing_and_holds_nothing_after_a_policy_clear(self):
        visit = self.visit
        queued, sent = self.queue_a_pass()
        with self.assertRaises(Exception):
            self.flow.turn(visit.owner, visit.payload({'type': 'message', 'message': 'hello'}, policy='natural-context-v2'))
        queued.pop()()                                                     # the queued worker now runs
        self.assertEqual(len(self.script.extraction_sent), sent)          # the message was not sent
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 0)
        self.assertEqual(self.stats()['withdrawn'], 1)
        self.flow.reconciler.executor = lambda work: work()
        out = visit.say('thanks', [message(reply('You are welcome.'))])
        self.assertEqual(out['metrics']['oneCall']['reconciled'], 0)
        self.assertIsNone(visit.value('comparison.scope.zip'))

    def test_a_queued_pass_sends_nothing_after_the_owner_is_forgotten(self):
        visit = self.visit
        queued, sent = self.queue_a_pass()
        chain = visit.chain
        self.flow.forget_owner(visit.owner)
        queued.pop()()
        self.assertEqual(len(self.script.extraction_sent), sent)
        self.assertEqual(self.flow.reconciler.held(visit.owner, chain), 0)

    def test_a_pass_in_flight_when_the_visit_is_cleared_keeps_nothing(self):
        visit = self.visit
        visit.say("It's for me.", [save(update('RC01', {'choice': 'self'}, "It's for me"))], [message(reply('Thank you.'))])
        reconciler = self.flow.reconciler
        original = reconciler._classify

        def classify(job, proposals):
            reconciler.discard(visit.owner, visit.chain)                  # cleared while the request was out
            return original(job, proposals)
        reconciler._classify = classify
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'my ZIP is 34102')]))
        visit.say('my ZIP is 34102', [message(reply('Thank you.'))])
        self.assertEqual(reconciler.held(visit.owner, visit.chain), 0)
        self.assertEqual(self.stats()['withdrawn'], 1)

    def test_forgetting_old_clearings_never_revives_a_pass(self):
        reconciler = Reconciler(None, enabled=True)
        stamp = reconciler._stamp()
        self.assertTrue(reconciler._current('owner', 'chain', stamp))
        reconciler.discard('owner', 'chain')
        self.assertFalse(reconciler._current('owner', 'chain', stamp))
        with patch.object(one_call_reconcile, 'MAX_CLEARED', 2):
            for number in range(4):
                reconciler.discard('other-%d' % number)
        self.assertFalse(reconciler._current('owner', 'chain', stamp))    # its clearing was evicted; it stays withdrawn
        self.assertTrue(reconciler._current('owner', 'chain', reconciler._stamp()))

    def test_a_newer_typed_answer_replaces_a_held_one(self):
        visit = self.visit
        visit.say("It's for me.", [save(update('RC01', {'choice': 'self'}, "It's for me"))], [message(reply('Thank you.'))])
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'my ZIP is 34102')]))
        visit.say('my ZIP is 34102', [message(reply('Thank you.'))])
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 1)
        visit.say('sorry, wrong: my ZIP is 33901', [save(update('T03', {'zip': '33901'}, 'my ZIP is 33901'))],
                  [message(reply('Thank you, I have the new one.'))])
        self.assertEqual(visit.value('comparison.scope.zip'), '33901')


class SameGatesAsTheExtractor(ReconcileCase):
    def test_the_save_tool_refuses_what_advisor_firsts_extractor_drops(self):
        # The reviewer's comparison: each unsupported value through advisor-first's extraction
        # stage and through the save tool, on the same message and state.
        from natural_state import legacy_projection
        from one_call_tools import ToolRunner
        visit, flow = self.visit, self.flow
        text = 'Hi, I am looking for some help understanding my options.'
        visit.say(text, [save(update('RC01', {'choice': 'self'}, 'I'))], [message(reply('Glad to help.'))])
        cases = [('T03', {'zip': '34102'}, 'I am'), ('T06', {'choice': 'list', 'text': 'Dr. Raj Patel'}, 'some help'),
                 ('RC11', {'jobEnd': '2027-03'}, 'I am'), ('MG_AGE', {'choice': '70'}, 'I am'),
                 ('T05', {'choice': 'medicaid'}, 'my options'), ('RC04', {'choice': 'both'}, 'I am')]
        dropped = []
        for identifier, fields, quote in cases:
            self.script.extractions.append(extraction([extraction_update(identifier, fields, quote)]))
            guide, record = copy.deepcopy(visit.guide), copy.deepcopy(visit.record)
            job = {'owner': visit.owner, 'chain': visit.chain, 'message': text, 'guide': guide, 'record': record,
                   'extraction_guide': legacy_projection(guide, record)[0], 'agent': flow.agent, 'today': support.TODAY,
                   'context': one_call_reconcile.extraction_context(flow, visit.owner, visit.chain, guide, record, None, text),
                   'request_id': 'rc-test-' + identifier}
            kept = bool((flow.reconciler._extract(job) or {}).get('updates'))
            runner = ToolRunner(flow, visit.owner, visit.guide, visit.record, text, today=support.TODAY)
            status = runner.run('save_profile_fields', {'updates': [update(identifier, fields, quote)]})['outcomes'][0]['status']
            if not kept:
                dropped.append(identifier)
                self.assertEqual(status, 'rejected', identifier)
            if status == 'accepted':
                self.assertTrue(kept, identifier)                         # nothing is saved that the extractor would drop
        self.assertEqual(dropped, ['T06', 'RC11', 'MG_AGE'])


class Failures(ReconcileCase):
    def test_a_failed_pass_never_reaches_the_turn_and_holds_nothing(self):
        for failure in (ConnectionError('fictional outage'), 'not json at all'):
            self.script.extractions.append(failure)
            out = self.visit.say('This is for me.', [message(reply('Thank you.'))])
            self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(self.flow.reconciler.held(self.visit.owner, self.visit.chain), 0)
        self.assertEqual(self.stats()['scheduled'], 2)
        self.assertEqual(self.stats().get('completed', 0), 0)
        self.assertEqual(self.stats().get('unavailable', 0) + self.stats().get('failed', 0), 2)
        self.assertEqual(self.flow.reconciler._running, set())

    def test_an_executor_that_refuses_work_is_counted_not_raised(self):
        def refuse(work):
            raise RuntimeError('fictional refusal')
        self.flow.reconciler.executor = refuse
        out = self.visit.say('Hello.', [message(reply('Hello.'))])
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(self.stats(), {'scheduled': 1, 'failed': 1})
        self.assertEqual(self.flow.reconciler._running, set())

    def test_logs_carry_counts_and_categories_only(self):
        text = 'My friend %s says my ZIP code is 34102.' % CANARY
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'my ZIP code is 34102')]))
        self.script.extractions.append(ConnectionError(CANARY))
        with self.assertLogs(level='DEBUG') as captured:
            logging.getLogger('one_call_reconcile').info('Daylight one-call test marker')
            self.visit.say(text, [message(reply('Thank you.'))])
            self.visit.say('And then %s.' % CANARY, [message(reply('Yes.'))])
        logged = '\n'.join(captured.output)
        for forbidden in (CANARY, '34102', 'ZIP code'):
            self.assertNotIn(forbidden, logged)
        self.assertIn('Daylight one-call reconcile completed held=1', logged)

    def test_the_default_executor_is_a_worker_thread(self):
        seen = []
        done = threading.Event()
        self.flow.reconciler.executor = one_call_reconcile._thread
        original = self.flow.reconciler._work

        def work(job):
            seen.append(threading.current_thread().name)
            try:
                original(job)
            finally:
                done.set()
        self.flow.reconciler._work = work
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'ZIP 34102')]))
        self.visit.say('This is for me, ZIP 34102.', [save(update('RC01', {'choice': 'self'}, 'This is for me'))],
                       [message(reply('Thank you.'))])
        self.assertTrue(done.wait(30))
        self.assertEqual(seen, ['daylight-one-call-reconcile'])
        self.assertNotEqual(seen[0], threading.current_thread().name)
        self.assertEqual(self.flow.reconciler.held(self.visit.owner, self.visit.chain), 1)


class SwitchedOff(ReconcileCase):
    reconcile = False

    def test_switched_off_it_makes_no_request_and_supplies_nothing(self):
        visit = self.visit
        self.script.extractions.append(extraction([extraction_update('T03', {'zip': '34102'}, 'my ZIP code is 34102')]))
        visit.say('This is for me, and my ZIP code is 34102.',
                  [save(update('RC01', {'choice': 'self'}, 'This is for me'))], [message(reply('Thank you.'))])
        self.assertEqual(self.script.extraction_sent, [])
        self.assertEqual(self.stats(), {'switched_off': 1})
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 0)
        out = visit.say('What next?', [message(reply('Here.'))])
        self.assertIsNone(visit.value('comparison.scope.zip'))
        self.assertEqual(out['metrics']['oneCall']['reconciled'], 0)
        self.assertEqual(support.charge_rows(self.budget), ['cancelled', 'settled', 'settled', 'settled'])

    def test_the_environment_switch_turns_it_off(self):
        self.flow.reconciler.enabled = None                                # follow the environment
        with patch.dict(os.environ, {one_call_reconcile.SWITCH: '0'}):
            self.visit.say('Hello.', [message(reply('Hello.'))])
        self.assertEqual(self.script.extraction_sent, [])
        with patch.dict(os.environ, {one_call_reconcile.SWITCH: '1'}):
            self.visit.say('Hello again.', [message(reply('Hello.'))])
        self.assertEqual(len(self.script.extraction_sent), 1)

    def test_held_facts_are_not_applied_while_switched_off(self):
        visit = self.visit
        visit.say('This is for me.', [save(update('RC01', {'choice': 'self'}, 'This is for me'))], [message(reply('Thank you.'))])
        held = update('T03', {'zip': '34102'}, 'ZIP 34102')
        self.flow.reconciler._held[(visit.owner, visit.chain)] = {
            'items': [{'update': held, 'message': 'My ZIP 34102.'}], 'expires': 1e18}
        visit.say('What next?', [message(reply('Here.'))])
        self.assertIsNone(visit.value('comparison.scope.zip'))


if __name__ == '__main__':
    unittest.main()
