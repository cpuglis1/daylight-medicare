"""OneCallConversation driven through flow.turn with a scripted model.

Offline: scripted transport, temporary budget ledger, sockets forbidden,
fictional people. These tests check the conversation's software behaviour:
what is sent to the model, what is saved, what is shown and what is recorded.
They do not show how a live model behaves; no test here makes a live call.
"""
import copy
import json
import logging
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat import ModelUnavailable
from guest_profiles import ProfileError
from natural_flow import CONTEXT_POLICY, NaturalConversation
import conversation_planner
import conversation_records

import _one_call_support as support
from _one_call_support import Script, Visit, call, message, reply, save, update
import one_call_flow
from one_call_flow import OneCallConversation, VisitStore

CANARY = 'ZEBRAFINCH'
SEPARATE_VISIT = 'Open a separate visit'


@unittest.skipUnless(support.READY, support.NOT_READY)
class FlowCase(unittest.TestCase):
    reconcile = False

    def setUp(self):
        support.offline(self)
        support.pin_today(self)
        self.script = Script()
        self.flow = support.make_flow(self.script, reconcile=self.reconcile)
        self.budget = support.temporary_ledger(self, self.flow.agent)
        self.visit = Visit(self, self.flow, self.script)
        self.visit.start()

    def one(self, out):
        return out['metrics']['oneCall']

    def asked(self, out):
        return (out['assessment'].get('nextQuestion') or {}).get('id')

    def typed_question(self, out):
        """The model-worded question when it was delivered as plain text with no answer buttons."""
        move = out.get('conversationNext') or {}
        return move.get('question') if move.get('kind') == 'clarification' else None

    def catalog(self, identifier):
        return conversation_records._question(self.flow, self.visit.guide, self.visit.record, identifier)

    def be_self(self):
        return self.visit.say('This coverage is for me.', [save(update('RC01', {'choice': 'self'}, 'This coverage is for me'))],
                              [message(reply('Thank you, I have noted that.'))])


class HelperVisit(FlowCase):
    def test_who_the_coverage_is_for_is_saved_only_by_the_tool_and_a_correction_is_confirmed(self):
        visit = self.visit
        first = 'Hello, I am helping my mother with her Medicare. I am not sure where to start.'
        out = visit.say(first, [message(reply('I can help you and your mother with that.',
                                              question='What brought you and your mother here today?'))])
        # The message names a mother and says "I", and nothing about the person is saved from its words.
        self.assertIsNone(visit.value('subject.role'))
        self.assertEqual(visit.report('RC01'), {})
        self.assertEqual(self.one(out)['saved'], 0)
        # Who it is for is not saved yet, so the question is plain text with no answer buttons.
        self.assertIsNone(out['assessment'].get('nextQuestion'))
        self.assertEqual(self.typed_question(out), 'What brought you and your mother here today?')

        second = 'Yes, the coverage is for my mother. Her ZIP code is 34102.'
        out = visit.say(second,
                        [save(update('RC01', {'choice': 'someone'}, 'the coverage is for my mother'),
                              update('T03', {'zip': '34102'}, 'Her ZIP code is 34102'))],
                        [message(reply('Thank you. I have noted that this is for your mother.',
                                       question='What would you like help with for her?'))])
        self.assertEqual(visit.value('subject.role'), 'someone')
        self.assertEqual(visit.value('comparison.scope.zip'), '34102')
        # For a helper the catalog wording ("you") would be about the wrong person: plain text again.
        self.assertIsNone(out['assessment'].get('nextQuestion'))
        self.assertEqual(self.typed_question(out), 'What would you like help with for her?')

        third = 'Sorry, I said that wrong. The coverage is actually for me, not my mother.'
        out = visit.say(third,
                        [save(update('RC01', {'choice': 'self'}, 'The coverage is actually for me', correction=True))],
                        [message(reply('Thanks for telling me.', question='What would you like help with?', target='T01'))])
        outcome = json.loads(self.script.sent[-1]['input'][-1]['output'])['outcomes'][0]
        self.assertEqual(outcome, {'index': 0, 'id': 'RC01', 'status': 'needs_confirmation', 'reason': 'subject_change'})
        # Not applied on the model's say-so. Code asks, in its own words, with its own two buttons.
        self.assertEqual(visit.value('subject.role'), 'someone')
        question = out['assessment']['nextQuestion']
        self.assertEqual(question['id'], 'RC01')
        self.assertEqual(question['question'], 'I want to be sure before I save this. Who this is for: Me. Is that right?')
        self.assertEqual(question['clarification'], {'confirmable': True, 'confirmLabel': 'Yes, that’s right'})
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'RC01'})
        self.assertEqual((self.one(out)['staged'], self.one(out)['questionDelivery'], self.one(out)['saved']), (1, 'confirmation', 0))
        self.assertNotIn('What would you like help with?', json.dumps(out))

        # The interface's "Yes, that's right" button sends these words; the change is applied by code.
        out = visit.say('Yes, that’s right.', [message(reply('Thank you. This is your own coverage now.'))])
        self.assertEqual(visit.value('subject.role'), 'self')
        self.assertEqual(visit.report('RC01')['choice'], 'self')
        self.assertEqual(visit.value('comparison.scope.zip'), '34102')     # the earlier report stays attached
        self.assertIn({'choice': 'someone'}, [entry.get('previous') for entry in visit.record['history'] if entry['triggerId'] == 'RC01'])
        self.assertEqual(self.one(out)['confirmed'], 1)
        sent = self.script.inputs()[-1]
        self.assertIn('RC01', sent['pending_note'])
        self.assertEqual(sent['profile']['coverage_is_for'], 'self')
        self.assertEqual(sent['transcript'][-1], {'role': 'person', 'text': 'Yes, that’s right.'})
        self.assertIsNone(self.flow.pending_for(visit.owner))
        for item in visit.outs:
            self.assertNotIn(SEPARATE_VISIT, json.dumps(item))
        for payload in self.script.sent:
            self.assertNotIn(SEPARATE_VISIT, json.dumps(payload['input']))

    def test_a_change_of_person_is_never_applied_without_the_persons_confirmation(self):
        # The reviewer's case: "ok thanks" with a correction flag flipped the person.
        visit = self.visit
        visit.say("It's for me. My ZIP is 34102 and I have Medicaid.",
                  [save(update('RC01', {'choice': 'self'}, "It's for me"), update('T03', {'zip': '34102'}, 'My ZIP is 34102'),
                        update('T05', {'choice': 'medicaid'}, 'I have Medicaid'))], [message(reply('Thank you.'))])
        history = len(visit.record['history'])
        for choice in ('someone', 'research'):
            out = visit.say('ok thanks', [save(update('RC01', {'choice': choice}, 'ok', correction=True))],
                            [message(reply('You are welcome.'))])
            self.assertEqual(visit.value('subject.role'), 'self')
            self.assertEqual(len(visit.record['history']), history)
            self.assertEqual(self.one(out)['saved'], 0)
            self.assertTrue(out['assessment']['nextQuestion']['clarification']['confirmable'])
            # Anything but a yes to that confirmation withdraws it; the next "ok thanks" is not a yes to a new one.
        out = visit.say('No, it is still for me.', [message(reply('Understood, nothing has changed.'))])
        self.assertEqual(visit.value('subject.role'), 'self')
        self.assertEqual(self.one(out)['confirmed'], 0)
        self.assertIsNone(self.flow.pending_for(visit.owner))
        # A yes with no confirmation on screen confirms nothing.
        out = visit.say('Yes, that’s right.', [message(reply('Good.'))])
        self.assertEqual((visit.value('subject.role'), self.one(out)['confirmed']), ('self', 0))

    def test_a_contradicting_report_is_confirmed_with_one_tap_and_survives_a_failed_turn(self):
        visit = self.visit
        self.be_self()
        visit.say('I have COBRA.', [save(update('T05', {'choice': 'cobra'}, 'I have COBRA'))], [message(reply('Thank you.'))])
        out = visit.say('I have Medicaid.', [save(update('T05', {'choice': 'medicaid'}, 'I have Medicaid'))],
                        [message(reply('Thank you.'))])
        self.assertEqual(visit.value('coverage.current'), ['cobra'])
        question = out['assessment']['nextQuestion']
        self.assertEqual((question['id'], question['clarification']['confirmable']), ('T05', True))
        self.assertIn('Medicaid', question['question'])
        self.assertTrue(question['question'].startswith('I want to be sure before I save this. '))
        # A turn that is refused before delivery leaves the confirmation waiting.
        self.flow.agent.enabled = False
        with self.assertRaises(Exception):
            self.flow.turn(visit.owner, visit.payload({'type': 'message', 'message': 'Yes, that’s right.'}))
        self.flow.agent.enabled = True
        self.assertIsNotNone(self.flow.pending_for(visit.owner))
        out = visit.say('Yes, that’s right.', [message(reply('Thank you, that is saved.'))])
        self.assertEqual(visit.value('coverage.current'), ['medicaid'])
        self.assertEqual(self.one(out)['confirmed'], 1)

    def test_a_first_time_value_is_never_met_with_a_code_built_confirmation(self):
        self.visit.given_profile_permission()
        # Line 20 of the owner's first live visit: the goal was put back to the person to confirm.
        visit = self.visit
        self.be_self()
        said = 'I want to find coverage that works for me in my situation, but I want to feel good about my decision'
        out = visit.say(said, [save(update('T01', {'choice': 'compare', 'text': said}, said, scope='unknown'))],
                        [message(reply('We will look for coverage that fits you.',
                                       question='Which Medicare parts do you have now?', target='RC04'))])
        self.assertEqual(visit.value('intent.goal'), 'compare')
        self.assertEqual((self.one(out)['saved'], self.one(out)['staged']), (1, 0))
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
        self.assertNotIn('I want to be sure before I save this', json.dumps(out))
        # A doubtful first-time report is not saved, and the model's own question is what follows.
        out = visit.say('I think I prefer predictable costs.',
                        [save(update('T09', {'choice': 'predictable'}, 'I think I prefer predictable costs'))],
                        [message(reply('That is worth settling.', question='Is a steadier monthly cost what you want?'))])
        self.assertEqual((self.one(out)['saved'], self.one(out)['staged'], self.one(out)['questionDelivery']),
                         (0, 0, 'free_text'))
        self.assertIsNone(self.flow.pending_for(visit.owner))

    def test_a_first_person_sentence_about_turning_65_does_not_set_who_it_is_for(self):
        # advisor-first's typed-message step records "self" from words like "I turn" once a
        # birthday report is accepted. Here a birthday is saved and the person stays unknown.
        text = 'I turn 65 in March 2027 and my mom keeps asking about her plan.'
        out = self.visit.say(text,
                             [save(update('S_AGE65', {'month': '3', 'year': '2027'}, 'I turn 65 in March 2027'))],
                             [message(reply('Thank you for telling me.', question='Who is this coverage for?', target='RC01'))])
        self.assertEqual(self.one(out)['saved'], 1)
        self.assertEqual(self.visit.value('situation.age65'), {'month': 3, 'year': 2027})
        self.assertIsNone(self.visit.value('subject.role'))
        self.assertEqual(self.visit.report('RC01'), {})


class OneToolRound(FlowCase):
    def test_two_fields_from_one_message_take_one_round_and_leave_the_open_items(self):
        visit = self.visit
        text = 'This is for me, and I live in ZIP code 34102.'
        out = visit.say(text,
                        [save(update('RC01', {'choice': 'self'}, 'This is for me'),
                              update('T03', {'zip': '34102'}, 'I live in ZIP code 34102'))],
                        [message(reply('Thank you, I have both of those.',
                                       question='What would you like help with today?', target='T01'))])
        self.assertEqual(len(self.script.sent), 2)                       # exactly two requests
        self.assertEqual((self.one(out)['requests'], self.one(out)['toolCalls'], self.one(out)['saved']), (2, 1, 2))
        self.assertEqual(out['metrics']['llmCalls'], 2)
        self.assertEqual(self.script.sent[0]['tool_choice'], 'auto')
        self.assertEqual(self.script.sent[1]['tool_choice'], 'none')
        self.assertEqual((visit.value('subject.role'), visit.value('comparison.scope.zip')), ('self', '34102'))
        self.assertEqual(support.charge_rows(self.budget), ['settled', 'settled'])
        before = {item['id'] for item in self.script.inputs()[0]['open_items']}
        self.assertIn('RC01', before)

        visit.say('I would like to understand my options.', [message(reply('Glad to.', question='Which Medicare parts do you have now?', target='RC04'))])
        sent = self.script.inputs()[-1]
        after = {item['id'] for item in sent['open_items']}
        self.assertFalse({'RC01', 'T03'} & after, after)
        self.assertIn('RC04', after)
        saved = {row['id']: row for row in sent['profile']['saved']}
        self.assertEqual(sent['profile']['coverage_is_for'], 'self')
        self.assertEqual(saved['T03']['state'], 'reported')
        self.assertIn('RC01', sent['profile']['states']['reported'])

    def test_a_turn_without_tools_makes_one_request_and_leaves_no_uncertain_rows(self):
        out = self.visit.say('What is Medicare, in a sentence?', [message(reply('Here is a plain answer.'))])
        self.assertEqual(len(self.script.sent), 1)
        self.assertEqual((self.one(out)['requests'], self.one(out)['toolCalls'], self.one(out)['fallback']), (1, 0, False))
        self.assertEqual(out['metrics']['llmCalls'], 1)
        self.assertEqual(out['generated']['status'], 'complete')
        # The first stage settled; the unused second stage was released, not left held.
        self.assertEqual(support.charge_rows(self.budget), ['cancelled', 'settled'])
        self.assertEqual(self.one(out), {**self.one(out), 'rejected': 0, 'rejectedCodes': [], 'retry': False,
                                         'reconciled': 0, 'failure': None})

    def test_typed_sentences_advisor_first_answers_without_the_model_go_to_the_model_here(self):
        visit = self.visit
        visit.say('Hello there.', [message(reply('Hello.', question='What would you like help with?'))])
        for text in ("I don't know.", 'Check later.', 'Me.', '34102'):
            requests = len(self.script.sent)
            out = visit.say(text, [message(reply('Thanks for telling me.', question='What would you like help with?'))])
            self.assertEqual(len(self.script.sent), requests + 1, text)
            self.assertEqual(self.script.inputs()[-1]['transcript'][-1], {'role': 'person', 'text': text})
            self.assertEqual(out['reply'], 'Thanks for telling me.\n\nWhat would you like help with?')
        self.assertIsNone(visit.value('subject.role'))                    # "Me." matched a chip label and saved nothing


class WholeVisit(FlowCase):
    def test_turn_eight_carries_the_first_message_verbatim_and_fixed_instructions(self):
        visit = self.visit
        first = 'Good morning. My neighbour %s told me to ask about Medicare before spring.' % CANARY
        visit.say(first, [message(reply('Good morning. I am glad you came by.', question='What would you like help with?'))])
        for number in range(2, 9):
            visit.say('This is my message number %d of the visit.' % number,
                      [message(reply('Reply number %d.' % number, question='What would you like help with?'))])
        self.assertEqual(len(self.script.sent), 8)
        eighth = self.script.inputs()[7]
        people = [item['text'] for item in eighth['transcript'] if item['role'] == 'person']
        self.assertEqual(people[0], first)
        self.assertEqual(len(people), 8)
        self.assertEqual(len(eighth['transcript']), 15)                  # seven exchanges and the new message
        self.assertEqual(eighth['transcript'][1]['text'], 'Good morning. I am glad you came by.\n\nWhat would you like help with?')
        self.assertEqual(eighth['transcript'][-1], {'role': 'person', 'text': 'This is my message number 8 of the visit.'})
        instructions = {payload['instructions'].encode() for payload in self.script.sent}
        self.assertEqual(len(instructions), 1)                           # byte-identical on every turn
        tools = {json.dumps(payload['tools'], sort_keys=True) for payload in self.script.sent}
        self.assertEqual(len(tools), 1)
        self.assertEqual(list(eighth), ['today', 'profile', 'open_items', 'readiness', 'education', 'concerns',
                                        'stage', 'pending_note', 'transcript'])
        self.assertEqual(eighth['today'], support.TODAY.isoformat())

    def test_a_button_answer_between_two_typed_turns_reaches_the_next_model_input(self):
        visit = self.visit
        visit.say('Hello, I would like some help.', [message(reply('Of course.', question='Who is this coverage for?', target='RC01'))])
        out = visit.tap({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertEqual(len(self.script.sent), 1)                       # the button made no model call
        self.assertEqual(visit.value('subject.role'), 'self')
        shown = (out['assessment'].get('nextQuestion') or {}).get('question')
        visit.say('What happens next?', [message(reply('Here is what happens next.'))])
        transcript = self.script.inputs()[-1]['transcript']
        button = transcript[2]
        # The model's wording was plain text; the button's own question is the catalog's.
        self.assertEqual(button, {'role': 'person', 'text': 'Answered on screen. Question: %s Answer: Me'
                                                            % self.flow.question('RC01')['question'].strip()})
        if shown:
            # The question the button's response put on screen is there too.
            self.assertEqual(transcript[3], {'role': 'daylight', 'text': shown})
        self.assertEqual(transcript[-1]['text'], 'What happens next?')
        self.assertEqual(self.script.inputs()[-1]['profile']['coverage_is_for'], 'self')

    def test_a_question_delivered_four_times_is_parked_by_advisor_firsts_own_cap(self):
        self.visit.given_profile_permission()
        self.be_self()
        outs = [self.visit.say('Message %d.' % number,
                               [message(reply('Reply %d.' % number, question='Which parts do you have?', target='RC04'))])
                for number in range(5)]
        self.assertEqual([self.asked(out) for out in outs], ['RC04'] * 4 + [None])
        self.assertEqual(outs[4]['reply'], 'Reply 4.')                   # the reply stays; only the repeat question goes
        self.assertEqual([row['state'] for row in outs[4]['questionProgress'] if row['question_id'] == 'RC04'], ['parked'])

    def test_a_free_control_never_creates_a_transcript_and_a_new_visit_starts_empty(self):
        visit = self.visit
        visit.tap({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertFalse(self.flow.one_call_visits.exists(visit.owner, visit.chain))
        visit.say('Hello.', [message(reply('Hello.'))])
        chain = visit.chain
        self.assertEqual(self.flow.one_call_visits.turns(visit.owner, chain), 2)
        self.flow.forget_owner(visit.owner)
        self.assertEqual(self.flow.one_call_visits.turns(visit.owner, chain), 0)

    def test_a_replayed_request_is_not_added_twice(self):
        visit = self.visit
        payload = visit.payload({'type': 'message', 'message': 'Hello, just once.'})
        self.script.add([message(reply('Hello.'))])
        first = self.flow.turn(visit.owner, copy.deepcopy(payload))
        again = self.flow.turn(visit.owner, copy.deepcopy(payload))
        self.assertEqual(first['reply'], again['reply'])
        self.assertEqual(len(self.script.sent), 1)
        self.assertEqual(self.flow.one_call_visits.turns(visit.owner, visit.chain), 2)


class ContextPolicy(FlowCase):
    def test_a_request_without_the_current_policy_clears_the_transcript_and_is_refused(self):
        visit = self.visit
        visit.say('Please remember %s for me.' % CANARY, [message(reply('I will keep that in mind.'))])
        self.assertEqual(len(visit.transcript()), 2)
        self.flow.reconciler._held[(visit.owner, visit.chain)] = {'items': [{'update': {}, 'message': ''}], 'expires': 1e18}
        for policy in ('natural-context-v2', None):
            with self.assertRaises(ProfileError) as refused:
                self.flow.turn(visit.owner, visit.payload({'type': 'message', 'message': 'And now?'}, policy=policy))
            self.assertEqual(refused.exception.code, 428)
            self.assertEqual(str(refused.exception), one_call_flow.POLICY_MESSAGE)
            self.assertFalse(self.flow.one_call_visits.exists(visit.owner, visit.chain))
        self.assertEqual(self.flow.reconciler.held(visit.owner, visit.chain), 0)
        self.assertEqual(len(self.script.sent), 1)                       # nothing was sent for the refused turns
        # The next permitted turn starts from an empty transcript.
        visit.say('Hello again.', [message(reply('Hello again.'))])
        people = [item['text'] for item in self.script.inputs()[-1]['transcript']]
        self.assertEqual(people, ['Hello again.'])
        self.assertNotIn(CANARY, json.dumps(self.script.sent[-1]['input']))

    def test_without_ai_permission_nothing_is_sent(self):
        with self.assertRaises(ProfileError) as refused:
            self.flow.turn(self.visit.owner, self.visit.payload({'type': 'message', 'message': 'Hello.'}, consent=False))
        self.assertEqual(refused.exception.code, 428)
        self.assertEqual(self.script.sent, [])

    def test_identifiers_are_refused_before_anything_is_sent(self):
        with self.assertRaises(ProfileError):
            self.flow.turn(self.visit.owner, self.visit.payload(
                {'type': 'message', 'message': 'My Social Security number is 123-45-6789.'}))
        self.assertEqual(self.script.sent, [])

    def test_visit_store_follows_the_visit_memory_rule(self):
        clock = [0.0]
        store = VisitStore(clock=lambda: clock[0], ttl=10, limit=2)
        entry = [{'role': 'person', 'text': 'one'}]
        self.assertFalse(store.add('owner', 'a', None, entries=entry))            # a free control cannot create one
        self.assertTrue(store.add('owner', 'a', CONTEXT_POLICY, entries=entry))
        self.assertTrue(store.add('owner', 'a', None, entries=entry))              # and may add to a permitted one
        self.assertEqual(store.turns('owner', 'a'), 2)
        self.assertEqual(store.read('owner', 'a', 'natural-context-v2')['transcript'], [])
        self.assertFalse(store.exists('owner', 'a'))                               # that read deleted it
        for chain in ('a', 'b', 'c'):
            store.add('owner', chain, CONTEXT_POLICY, entries=entry)
        self.assertEqual([store.exists('owner', chain) for chain in ('a', 'b', 'c')], [False, True, True])   # visit cap
        clock[0] = 11
        self.assertFalse(store.exists('owner', 'c'))                               # time-to-live
        small = VisitStore(max_bytes=5)
        self.assertTrue(small.add('owner', 'a', CONTEXT_POLICY, entries=[{'role': 'person', 'text': 'abc'}]))
        self.assertFalse(small.add('owner', 'a', CONTEXT_POLICY, entries=[{'role': 'person', 'text': 'defg'}]))
        self.assertEqual(small.read('owner', 'a', CONTEXT_POLICY)['transcript'], [{'role': 'person', 'text': 'abc'}])


class CheckedReply(FlowCase):
    def floor(self, out):
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['advisor']['reason'], 'recovery')
        self.assertTrue(self.one(out)['fallback'])
        self.assertTrue(out['reply'].strip())

    def test_an_invented_amount_is_never_shown_and_the_fallback_is(self):
        self.visit.given_profile_permission()
        visit = self.visit
        visit.say('This is for me.', [save(update('RC01', {'choice': 'self'}, 'This is for me'))],
                  [message(reply('Thank you.', question='What would you like help with?', target='T01'))])
        invented = 'Your plan will cost $4,321 every month.'
        out = visit.say('How much will a plan cost me?',
                        [message(reply(invented, question='What is your ZIP code?', target='T03'))],
                        [message(reply('It will be $4,321 a month.'))])
        self.floor(out)
        self.assertNotIn('4,321', json.dumps(out))
        self.assertEqual(self.one(out)['rejectedCodes'], ['ungrounded_amount', 'ungrounded_amount'])
        self.assertEqual((self.one(out)['rejected'], self.one(out)['retry'], self.one(out)['requests']), (2, True, 2))
        self.assertEqual(out['generated']['code'], 'reply_rejected')
        # The next open question, in advisor-first's own catalog wording, with nothing the model wrote.
        question = out['assessment']['nextQuestion']
        expected = conversation_records._question(self.flow, visit.guide, visit.record, question['id'])
        self.assertEqual(question['question'], expected['question'])
        self.assertNotEqual(question['question'], 'What is your ZIP code?')
        # The retry reused the unused second stage, with tools off and codes only in its note.
        retry = self.script.sent[-1]
        self.assertEqual(retry['tool_choice'], 'none')
        note = json.loads(retry['input'][0]['content'])['pending_note']
        self.assertIn('ungrounded_amount', note)
        self.assertNotIn('4,321', note)
        self.assertEqual(support.charge_rows(self.budget), ['settled'] * 4)
        # What the visit remembers is what was shown.
        self.assertNotIn('4,321', json.dumps(visit.transcript()))
        self.assertEqual(visit.transcript()[-2]['text'], 'How much will a plan cost me?')

    def test_the_retry_replaces_a_rejected_draft_when_it_passes(self):
        out = self.visit.say('What does it cost?',
                             [message(reply('It costs $4,321.'))],
                             [message(reply('I do not have a price to give you yet.'))])
        self.assertEqual(out['reply'], 'I do not have a price to give you yet.')
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual((self.one(out)['fallback'], self.one(out)['retry'], self.one(out)['rejected'], self.one(out)['requests']),
                         (False, True, 1, 2))

    def test_blocks_that_pass_are_kept_when_another_is_rejected_after_a_tool_round(self):
        # The one retry after the tool round is lost, so the surviving block of the first draft is the reply.
        out = self.visit.say('This is for me. What will I pay?',
                             [save(update('RC01', {'choice': 'self'}, 'This is for me'))],
                             [message(reply('I have noted that this is for you.', 'You will pay $4,321.'))],
                             ConnectionError('fictional outage'))
        self.assertEqual(out['reply'], 'I have noted that this is for you.')
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual((self.one(out)['fallback'], self.one(out)['retry'], self.one(out)['rejectedCodes']),
                         (False, True, ['ungrounded_amount']))
        self.assertEqual(self.visit.value('subject.role'), 'self')

    def test_an_amount_the_person_typed_earlier_in_the_visit_grounds_a_later_reply(self):
        visit = self.visit
        visit.say('My premium went up to $187 this year.', [message(reply('That is a real jump.'))])
        visit.say('I also have a question about doctors.', [message(reply('Go ahead.'))])
        out = visit.say('So what did I say I pay?', [message(reply('You told me your premium went up to $187.'))])
        self.assertEqual(out['reply'], 'You told me your premium went up to $187.')
        self.assertFalse(self.one(out)['fallback'])

    def test_a_question_with_no_catalog_target_is_a_clarification(self):
        out = self.visit.say('I am not sure what I need.',
                             [message(reply('That is a fine place to start.', question='Would it help to begin with the basics?'))])
        self.assertEqual(out['conversationNext'], {'kind': 'clarification', 'question': 'Would it help to begin with the basics?'})
        self.assertTrue(out['reply'].endswith('Would it help to begin with the basics?'))
        self.assertIsNone(out['assessment'].get('nextQuestion'))

    def test_a_target_that_is_not_open_is_dropped_and_delivery_still_ends_validly(self):
        visit = self.visit
        visit.say('This is for me.', [save(update('RC01', {'choice': 'self'}, 'This is for me'))],
                  [message(reply('Thank you.', question='Who is this coverage for?', target='RC01'))])
        out = visit.outs[-1]
        self.assertEqual(self.one(out)['questionCode'], 'target_not_open')
        self.assertNotEqual(self.asked(out), 'RC01')
        self.assertEqual(out['reply'].split('\n\n')[0], 'Thank you.')

    def test_pause_ends_the_turn_without_a_question(self):
        out = self.visit.say('I need to stop for today.', [message(reply('Of course. Come back any time.', pause=True))])
        self.assertEqual(out['conversationNext'], {'kind': 'finish'})
        self.assertIsNone(out['assessment'].get('nextQuestion'))
        self.assertTrue(out['assessment']['intakePaused'])
        # The next message is an ordinary turn again.
        out = self.visit.say('I am back.', [message(reply('Welcome back.', question='Who is this coverage for?', target='RC01'))])
        self.assertEqual(self.typed_question(out), one_call_flow.DISCOVERY_QUESTION)

    def test_cited_facts_reach_the_education_record_and_the_next_input(self):
        fact = next(iter(sorted(self.flow.progress_fact_ids)))
        text = self.flow.facts[fact]['text']
        out = self.visit.say('Can you explain that?', [message(reply({'text': text, 'fact_ids': [fact]}))])
        self.assertEqual(out['reply'], text.strip())
        self.assertEqual(self.one(out)['factIds'], [fact])
        self.assertEqual(out['advisor']['teachingFactIds'], [fact])
        self.visit.say('Thank you.', [message(reply('You are welcome.'))])
        self.assertIn(fact, self.script.inputs()[-1]['education']['delivered_facts'])

    def test_a_checked_rule_with_a_digit_in_its_id_survives_the_next_turn(self):
        fact = 'glp1_prior_authorization'
        block = {'text': self.flow.facts[fact]['text'], 'fact_ids': [fact]}
        out = self.visit.say('This is for me. What about prior authorization for a GLP-1?',
            [save(update('RC01', {'choice': 'self'}, 'This is for me'))], [message(reply(block))])
        self.assertFalse(self.one(out)['fallback'])
        self.assertEqual(out['advisor']['teachingFactIds'], [fact])
        self.assertEqual(out['advisor']['sources'], self.flow._sources([fact]))
        self.assertEqual(out['record']['conversation']['lastFactIds'], [])
        self.visit.say('Can we keep talking?', [message(reply('Of course.', question='What else would help?'))])
        self.assertIn(fact, self.script.inputs()[-1]['education']['delivered_facts'])

    def test_an_unknown_fact_id_rejects_its_block(self):
        out = self.visit.say('Tell me something.',
                             [message(reply({'text': 'Here is a point.', 'fact_ids': ['not_a_library_fact']}))],
                             [message(reply('Here is what I can say.'))])
        self.assertEqual(self.one(out)['rejectedCodes'], ['unknown_fact_id'])
        self.assertEqual(out['reply'], 'Here is what I can say.')

    def test_concerns_are_kept_for_the_visit_and_sent_back(self):
        visit = self.visit
        visit.say('My husband just retired and I am worried about drug costs.',
                  [message(reply('That is a common worry.', concerns={'why_now': 'husband just retired',
                                                                       'worries': ['drug costs'], 'tried': []}))])
        visit.say('We called the plan already.',
                  [message(reply('Good to know.', concerns={'why_now': None, 'worries': ['losing her doctor'],
                                                            'tried': ['called the plan']}))])
        visit.say('What now?', [message(reply('Here is a next step.'))])
        self.assertEqual(self.script.inputs()[-1]['concerns'],
                         {'why_now': 'husband just retired', 'worries': ['drug costs', 'losing her doctor'],
                          'tried': ['called the plan']})
        self.assertEqual(self.script.inputs()[0]['concerns'], {'why_now': None, 'worries': [], 'tried': []})


class QuestionAndButtons(FlowCase):
    """Answer buttons appear only under wording that code owns."""
    UNRELATED = 'Do you agree that I should sign you up for the Humana Gold Plus plan at $0 today?'

    def no_model_wording_above_buttons(self, out, wording):
        question = out['assessment'].get('nextQuestion')
        if question:
            self.assertNotEqual(question['question'], wording)
            self.assertNotIn(wording, json.dumps(question))

    def test_self_and_a_target_with_choices_gets_the_catalog_wording_and_its_buttons(self):
        self.visit.given_profile_permission()
        self.be_self()
        wording = 'Tell me, do you already have any part of Medicare?'
        out = self.visit.say('What next?', [message(reply('Here is the next step.', question=wording, target='RC04'))])
        expected = self.catalog('RC04')
        question = out['assessment']['nextQuestion']
        self.assertEqual((question['id'], question['question'], question['choices']),
                         ('RC04', expected['question'], expected['choices']))
        self.assertTrue(question['choices'])
        self.assertEqual(out['conversationNext'], {'kind': 'profile_question', 'target': 'RC04'})
        self.assertEqual(self.one(out)['questionDelivery'], 'catalog')
        self.assertNotIn(wording, json.dumps(out))                        # the model's wording is not shown at all
        self.assertEqual(out['reply'], 'Here is the next step.')
        # What the visit remembers is the question that was on screen.
        self.assertEqual(self.visit.transcript()[-1]['text'], 'Here is the next step.\n\n' + expected['question'])

    def test_unrelated_wording_on_an_open_target_never_sits_above_its_buttons(self):
        self.visit.given_profile_permission()
        # The reviewer's case, for a person who is not yet known and for one who is.
        out = self.visit.say('What is Medicare?', [message(reply('Happy to help.', question=self.UNRELATED, target='RC01'))],
                             [message(reply('Happy to help.'))])
        self.no_model_wording_above_buttons(out, self.UNRELATED)
        self.assertIsNone(out['assessment'].get('nextQuestion'))
        self.be_self()
        target = next(item['id'] for item in self.script.inputs()[-1]['open_items'] if self.catalog(item['id']).get('choices'))
        out = self.visit.say('And then?', [message(reply('Happy to help.', question=self.UNRELATED, target=target))],
                             [message(reply('Happy to help.'))])
        self.no_model_wording_above_buttons(out, self.UNRELATED)
        self.assertNotIn(self.UNRELATED, json.dumps(out))

    def test_a_helper_gets_the_models_wording_as_plain_text(self):
        self.visit.given_profile_permission()
        self.visit.say('This is for my mother.', [save(update('RC01', {'choice': 'someone'}, 'This is for my mother'))],
                       [message(reply('Thank you.'))])
        wording = 'Which parts of Medicare does your mother have now?'
        out = self.visit.say('What next?', [message(reply('Here is the next step.', question=wording, target='RC04'))])
        self.assertIsNone(out['assessment'].get('nextQuestion'))
        self.assertEqual(self.typed_question(out), wording)
        self.assertTrue(out['reply'].endswith(wording))
        self.assertEqual(self.one(out)['questionDelivery'], 'free_text')

    def test_a_target_with_no_choices_and_a_null_target_are_plain_text(self):
        self.visit.given_profile_permission()
        self.be_self()
        self.assertFalse(self.catalog('T03').get('choices'))
        for target, wording in (('T03', 'What is the ZIP code where you live?'), (None, 'Would the basics help first?')):
            out = self.visit.say('What next?', [message(reply('Here is the next step.', question=wording, target=target))])
            self.assertIsNone(out['assessment'].get('nextQuestion'))
            self.assertEqual(self.typed_question(out), wording)
            self.assertEqual(self.one(out)['questionDelivery'], 'free_text')

    def test_a_typed_answer_to_a_plain_text_question_is_saved_through_the_validated_tool(self):
        self.visit.given_profile_permission()
        self.be_self()
        self.visit.say('What next?', [message(reply('Next.', question='What is the ZIP code where you live?', target='T03'))])
        out = self.visit.say('It is 34102.', [save(update('T03', {'zip': '34102'}, 'It is 34102'))], [message(reply('Thank you.'))])
        self.assertEqual((self.visit.value('comparison.scope.zip'), self.one(out)['saved']), ('34102', 1))


class ToolOutputs(FlowCase):
    INVENTED = 'The Zentara Gold Plus plan costs $47 a month starting April 9, 2027.'

    def test_a_rejected_save_cannot_plant_grounding_for_an_invented_claim(self):
        # The reviewer's case: the invention rode in on a rejected update's entity.
        visit = self.visit
        bad = update('T05', {'choice': 'zzz'}, 'nothing', entity='Zentara $47 April 9 2027')
        out = visit.say('What is Medicare?', [save(bad)], [message(reply(self.INVENTED))], [message(reply(self.INVENTED))])
        outputs = self.flow.one_call_visits.read(visit.owner, visit.chain, CONTEXT_POLICY)['tool_outputs']
        self.assertEqual(outputs[-1]['outcomes'], [{'index': 0, 'id': 'T05', 'status': 'rejected', 'reason': 'invalid_choice'}])
        for echoed in ('Zentara', '47', 'April', 'zzz', 'nothing'):
            self.assertNotIn(echoed, json.dumps(outputs))
        self.assertNotIn('Zentara', json.dumps(out))
        self.assertTrue(self.one(out)['fallback'])
        self.assertIn(self.one(out)['rejectedCodes'][0], ('ungrounded_amount', 'ungrounded_date', 'ungrounded_name'))
        out = visit.say('ok thanks', [message(reply('As I said, Zentara is $47 from April 9, 2027.'))],
                        [message(reply('As I said, Zentara is $47.'))])
        self.assertNotIn('Zentara', json.dumps(out))
        self.assertTrue(self.one(out)['fallback'])

    def test_values_the_person_never_stated_are_not_saved_by_the_turn(self):
        # The reviewer's case at the level of a whole turn.
        visit = self.visit
        out = visit.say('Hi, I am looking for some help understanding my options.',
                        [save(update('RC01', {'choice': 'self'}, 'I'), update('T03', {'zip': '34102'}, 'I am'),
                              update('T06', {'choice': 'list', 'text': 'Dr. Raj Patel'}, 'some help'),
                              update('RC11', {'jobEnd': '2027-03'}, 'I am'), update('MG_AGE', {'choice': '70'}, 'I am'))],
                        [message(reply('Glad to help.'))])
        outcomes = json.loads(self.script.sent[-1]['input'][-1]['output'])['outcomes']
        self.assertEqual([item['status'] for item in outcomes][1:], ['rejected'] * 4)
        for path in ('comparison.scope.zip', 'needs.providers', 'medigap.age'):
            self.assertIsNone(visit.value(path), path)
        self.assertEqual(visit.report('RC11'), {})
        self.assertNotIn('Patel', json.dumps([visit.guide, visit.record]))
        self.assertLessEqual(self.one(out)['saved'], 1)

    def test_a_card_made_of_unaccepted_enrollment_statements_is_not_shown(self):
        import enrollment_flow
        import one_call_tools
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(one_call_tools.STATEMENTS_SWITCH, None)
            out = self.visit.say('How do I sign up?', [call('c1', 'show_card', {'kind': 'signup_route'})],
                                 [message(reply('Here is how sign-up works.'))])
        self.assertEqual(json.loads(self.script.sent[-1]['input'][-1]['output']),
                         {'ok': False, 'error': 'card_needs_owner_acceptance'})
        self.assertFalse([card for card in out.get('cards') or [] if card.get('kind') == 'signup_route'])
        new = [item['text'] for item in enrollment_flow.content()['statements'].values() if item['state'] != 'accepted']
        self.assertTrue(new)
        for text in new:
            self.assertNotIn(text, json.dumps(out.get('cards') or []))

    def test_the_library_holds_no_enrollment_content_statement(self):
        import enrollment_flow
        fixed = self.flow._fixed(support.TODAY)
        self.assertEqual(set(fixed['fact_texts']), set(self.flow.facts))
        content = enrollment_flow.content()
        for identifier, item in content['statements'].items():
            if identifier not in self.flow.facts:
                self.assertNotIn(' '.join(item['text'].split()), fixed['instructions'], identifier)

    def test_the_held_medicare_advantage_window_claim_is_withheld_on_every_surface(self):
        text = 'Since you added Part B after Part A, your Medicare Advantage window lasts two months after Part B starts.'
        for surface in (None, 'unified-8895'):
            script = Script()
            flow = support.make_flow(script)
            flow.pilot_knowledge.surface = surface
            visit = Visit(self, flow, script)
            visit.start()
            out = visit.say('I already have Part A and I am adding Part B late. When can I join a Medicare Advantage plan?',
                            [message(reply(text))], [message(reply(text))])
            self.assertNotIn('two months', out['reply'], surface)
            self.assertEqual(set(out['metrics']['oneCall']['rejectedCodes']), {'held_claim'}, surface)
            self.assertTrue(out['metrics']['oneCall']['fallback'])

    def test_a_reply_check_that_cannot_run_ends_in_the_fallback(self):
        with patch.object(one_call_flow, 'check_reply', side_effect=RuntimeError('fictional fault')):
            out = self.visit.say('Hello.', [message(reply('An unchecked reply.'))])
        self.assertNotIn('An unchecked reply.', json.dumps(out))
        self.assertEqual(out['generated']['code'], 'reply_check_unavailable')
        self.assertTrue(self.one(out)['fallback'])


class ModelFailure(FlowCase):
    def test_a_transport_failure_ends_in_the_reviewed_fallback_not_an_exception(self):
        out = self.visit.say('Hello, are you there?', ConnectionError('fictional outage'))
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(out['generated']['code'], 'transport_or_format')
        self.assertEqual(out['advisor']['reason'], 'recovery')
        self.assertTrue(out['reply'].strip())
        self.assertEqual((self.one(out)['fallback'], self.one(out)['failure'], self.one(out)['requests']),
                         (True, 'transport_or_format', 1))
        self.assertIsNone(self.asked(out))
        self.assertEqual(self.typed_question(out), one_call_flow.DISCOVERY_QUESTION)
        # An issued request that never settled stays held; the unused stage is released.
        self.assertEqual(support.charge_rows(self.budget), ['cancelled', 'uncertain'])
        # The person's words are still part of the visit for the next turn.
        self.visit.say('Trying again.', [message(reply('I am here now.'))])
        self.assertEqual(self.script.inputs()[-1]['transcript'][0], {'role': 'person', 'text': 'Hello, are you there?'})

    def test_saves_survive_a_failure_after_the_tool_round(self):
        out = self.visit.say('This is for me.',
                             [save(update('RC01', {'choice': 'self'}, 'This is for me'))], ConnectionError('fictional outage'),
                             ConnectionError('fictional outage'))                 # and its one retry
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(self.visit.value('subject.role'), 'self')
        self.assertEqual((self.one(out)['saved'], self.one(out)['fallback']), (1, True))

    def test_an_oversize_request_fails_the_turn_and_the_transcript_is_not_trimmed(self):
        visit = self.visit
        visit.say('The first thing I want to say is %s.' % CANARY, [message(reply('Thank you.'))])
        self.flow.one_call_request_bytes = 2000                           # far below the fixed instructions
        out = self.flow.turn(visit.owner, visit.payload({'type': 'message', 'message': 'And a second thing.'}))
        self.assertEqual(out['generated'], {**out['generated'], 'status': 'unavailable', 'code': 'input_bound'})
        self.assertEqual((self.one(out)['requests'], self.one(out)['fallback'], self.one(out)['failure']), (0, True, 'input_bound'))
        self.assertEqual(len(self.script.sent), 1)                       # nothing was sent for the oversize turn
        self.assertTrue(conversation_planner.valid_delivered_next(out))
        self.assertEqual([item['text'] for item in visit.transcript() if item['role'] == 'person'],
                         ['The first thing I want to say is %s.' % CANARY, 'And a second thing.'])
        self.assertEqual(support.charge_rows(self.budget), ['cancelled', 'cancelled', 'cancelled', 'settled'])

    def test_a_model_that_is_not_served_in_the_tool_format_is_refused(self):
        self.flow.agent.client.model = 'claude-opus-5-5'
        with self.assertRaises(ProfileError) as refused:
            self.flow.turn(self.visit.owner, self.visit.payload({'type': 'message', 'message': 'Hello.'}))
        self.assertEqual(refused.exception.code, 503)
        self.assertEqual(self.script.sent, [])

    def test_no_budget_and_no_reply_raise_as_advisor_first_does(self):
        self.flow.agent.enabled = False
        with self.assertRaises(ModelUnavailable):
            self.flow.turn(self.visit.owner, self.visit.payload({'type': 'message', 'message': 'Hello.'}))


class Logs(FlowCase):
    def test_logs_carry_no_message_reply_or_value(self):
        secret_reply = 'The %s reply mentions $9,876.' % CANARY
        with self.assertLogs(level='DEBUG') as captured:
            logging.getLogger('one_call_flow').info('Daylight one-call test marker')
            self.visit.say('My friend %s lives in 34102 and this is for me.' % CANARY,
                           [save(update('RC01', {'choice': 'self'}, 'this is for me'),
                                 update('T03', {'zip': '34102'}, 'lives in 34102'),
                                 update('T05', {'choice': 'no-such-choice'}, CANARY))],
                           [message(reply(secret_reply))], [message(reply(secret_reply))])
            self.visit.say('And again %s.' % CANARY, ConnectionError('fictional outage'))
        text = '\n'.join(captured.output)
        for forbidden in (CANARY, '34102', '9,876', 'this is for me'):
            self.assertNotIn(forbidden, text)
        self.assertIn('Daylight one-call reply unavailable code=transport_or_format', text)


class Structure(unittest.TestCase):
    def test_one_call_and_its_local_coverage_choice_preserve_shared_turn_dispatch(self):
        own = {name for name, value in vars(OneCallConversation).items() if callable(value) or isinstance(value, (property, classmethod, staticmethod))}
        inherited = {name for name in own if hasattr(NaturalConversation, name)}
        self.assertEqual(inherited, {'__init__', '_turn', 'message', 'direct_disposition', 'direct_local_answer',
                                     'replay_response', 'forget_owner', 'question', '_apply'})
        for name in ('turn', '_selected_turn', 'validate', 'bind', 'compose_choice', 'recover', 'save', 'response'):
            self.assertIs(getattr(OneCallConversation, name), getattr(NaturalConversation, name))

    def test_the_request_bound_is_the_variants_own(self):
        self.assertEqual(one_call_flow.ONE_CALL_REQUEST_BYTES, 400_000)

    @unittest.skipUnless(support.READY, support.NOT_READY)
    def test_synthetic_fixture_mode_calls_no_model_and_says_so(self):
        support.offline(self)
        script = Script()
        flow = support.make_flow(script)
        flow.fixture = True
        visit = Visit(self, flow, script)
        visit.start()
        out = visit.send({'type': 'message', 'message': 'Hello, this is for me.'})
        self.assertEqual(script.sent, [])
        self.assertEqual(out['generated']['code'], 'synthetic_fixture')
        self.assertEqual(out['notice'], one_call_flow.SYNTHETIC_NOTICE)
        self.assertTrue(out['metrics']['synthetic'])
        self.assertIsNone(flow.value(out['guide'], 'subject.role'))


if __name__ == '__main__':
    unittest.main()
