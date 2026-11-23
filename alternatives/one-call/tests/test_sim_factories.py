"""The two bake-off flow factories, each driven for two scripted turns by the harness.

Offline: an injected scripted client, a scripted person, sockets forbidden.
The live branch of the factories (no client given) is not exercised here or
anywhere: it needs a model key, the budget ledger and the display database.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat import ResponsesClient
from natural_flow import NaturalConversation
import conversation_planner
import conversation_records

from sim import graders, run as sim_run
from sim.person import ScriptedPerson, normalise

import _one_call_support as support
from _one_call_support import completed, extraction, extraction_update, message, reply, save, update
import one_call_prompt
import sim_factories
from one_call_flow import OneCallConversation

OPENING = 'This is for me. I live in 34102.'


def profile():
    return normalise({
        'id': 'FACTORY1', 'opening': OPENING, 'opening_states': ['who', 'zip'], 'typist': 'self', 'relation': '',
        'facts': {
            'who': {'kind': 'choice', 'value': 'self', 'say': "It's for me."},
            'zip': {'kind': 'number', 'value': '34102', 'say': 'ZIP 34102.'},
            'age': {'kind': 'number', 'value': '66', 'say': '66 years old.'},
            # The question both loops ask next here; a real answer keeps turn two a typed, model-read turn.
            'parts': {'kind': 'choice', 'value': 'neither', 'say': 'I have neither Part A nor Part B yet.'},
        }})


def person(item, seed=0):
    return ScriptedPerson(item, seed=seed)


def client(transport):
    return ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=transport)


@unittest.skipUnless(support.READY, support.NOT_READY)
class Factories(unittest.TestCase):
    def setUp(self):
        support.pin_today(self)

    def switches(self, flow):
        return {'planner': conversation_planner.enabled(flow), 'records': conversation_records.enabled(flow),
                'pending': conversation_records.pending_on(flow), 'fixes': conversation_records.fixes_on(flow),
                'enrollment': bool(getattr(flow, 'd161', False)), 'guided_close': bool(getattr(flow, 'guided_close', False)),
                'composed_opening': bool(getattr(flow, 'composed_opening', False)),
                'plans_fixes': bool(getattr(flow, 'plans_fixes', False)),
                'turn_progress': getattr(flow, 'turn_progress', None) is not None,
                'checks': getattr(flow, 'conversation_checks', None) is not None,
                'pilot_surface': flow.pilot_knowledge.surface,
                'reasoning': flow.agent.reasoning_effort, 'recovery': getattr(flow.agent, 'composition_recovery', False)}

    def test_both_factories_set_the_same_switches(self):
        two = sim_factories.make_two_call_flow(client(lambda payload: None))
        one = sim_factories.make_one_call_flow(client(lambda payload: None))
        self.assertIs(type(two), NaturalConversation)
        self.assertIs(type(one), OneCallConversation)
        self.assertEqual(self.switches(two), self.switches(one))
        self.assertTrue(all(self.switches(one)[name] for name in ('planner', 'records', 'pending', 'fixes', 'enrollment',
                                                                 'guided_close', 'composed_opening', 'plans_fixes')))
        # Neither claims a pilot-knowledge surface unless the caller names one.
        self.assertIsNone(self.switches(one)['pilot_surface'])
        named = sim_factories.make_two_call_flow(client(lambda payload: None), pilot_knowledge_surface='unified-8895')
        self.assertEqual(named.pilot_knowledge.surface, 'unified-8895')
        with self.assertRaises(ValueError):
            sim_factories.make_two_call_flow(client(lambda payload: None), reconcile=False)

    def test_two_call_flow_runs_two_scripted_turns_through_the_harness(self):
        stages = []

        def transport(payload):
            name = payload['text']['format']['name']
            sent = json.loads(payload['input'][0]['content'])
            stages.append(name)
            if name == 'daylight_guide_commands':
                first = stages.count(name) == 1
                value = extraction([extraction_update('RC01', {'choice': 'self'}, 'This is for me'),
                                    extraction_update('T03', {'zip': '34102'}, 'I live in 34102')] if first else [])
            else:
                candidates = sent.get('question_candidates', [])
                target = candidates[0]['id'] if candidates else None
                question = (candidates[0].get('question') or {}) if candidates else {}
                value = {'question_target': target, 'reply': 'We can work through the next useful detail together.',
                         'question': question.get('question', '') if target else '', 'report_refs': [], 'evidence_refs': [],
                         'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                         'agenda_update': {'current_concern': '', 'pause': False}}
            return completed([message(value)])

        with sim_run.offline_network():
            result = sim_run.run(lambda: sim_factories.make_two_call_flow(client(transport)), person, [profile()], max_turns=2)
        run = result['runs'][0]
        self.assertIsNone(run['start_error'])
        self.assertEqual([turn['error'] for turn in run['turns']], [None, None])
        self.assertEqual([turn['model_requests'] for turn in run['turns']], [2, 2])
        self.assertEqual(stages, ['daylight_guide_commands', 'daylight_resolved_conversation'] * 2)
        self.assertEqual([turn['generated'] for turn in run['turns']], ['complete', 'complete'])
        self.assertEqual(run['final']['values']['comparison.scope.zip'], '34102')
        self.assertEqual(run['final']['states']['RC01'], 'reported')

    def test_one_call_flow_runs_two_scripted_turns_through_the_harness(self):
        stages = []

        def transport(payload):
            name = payload['text']['format']['name']
            stages.append(name)
            if name == 'daylight_guide_commands':                         # the background record pass
                return completed([message(extraction())])
            self.assertEqual(name, one_call_prompt.REPLY_SCHEMA_NAME)
            sent = json.loads(payload['input'][0]['content'])
            after_tools = len(payload['input']) > 1
            first_turn = sum(1 for item in sent['transcript'] if item['role'] == 'person') == 1
            if first_turn and not after_tools:
                return completed([save(update('RC01', {'choice': 'self'}, 'This is for me'),
                                       update('T03', {'zip': '34102'}, 'I live in 34102'))])
            target = sent['open_items'][0]['id'] if sent['open_items'] and not after_tools else None
            if after_tools:
                target = 'T01'
            return completed([message(reply('Thank you, I have that.', question='Could you tell me a little more?',
                                            target=target))])

        with sim_run.offline_network():
            result = sim_run.run(lambda: sim_factories.make_one_call_flow(client(transport)), person, [profile()], max_turns=2)
        run = result['runs'][0]
        self.assertIsNone(run['start_error'])
        self.assertEqual([turn['error'] for turn in run['turns']], [None, None])
        # The harness reads the request and rejection counts from the names the response publishes.
        self.assertEqual([turn['model_requests'] for turn in run['turns']], [2, 1])
        self.assertEqual([turn['rejected'] for turn in run['turns']], [0, 0])
        self.assertEqual([turn['generated'] for turn in run['turns']], ['complete', 'complete'])
        one_call = one_call_prompt.REPLY_SCHEMA_NAME
        self.assertEqual(stages, [one_call, one_call, 'daylight_guide_commands', one_call, 'daylight_guide_commands'])
        self.assertFalse((run['turns'][0].get('question') or {}).get('id'))
        self.assertEqual(run['final']['values']['comparison.scope.zip'], '34102')
        self.assertEqual(run['final']['states']['RC01'], 'reported')
        # The first turn's tool outputs are published for the graders' grounding.
        self.assertTrue(any('toolOutputs' in part for part in run['turns'][0]['grounding']))
        accuracy = graders.grade(run, profile())['profile_accuracy']
        self.assertEqual((accuracy['correct'], accuracy['wrong']), (2, []))

    def test_one_call_metrics_carry_the_names_the_harness_reads(self):
        script = support.Script()
        flow = sim_factories.make_one_call_flow(client(script), reconcile=False)
        support.offline(self)
        visit = support.Visit(self, flow, script)
        visit.start()
        out = visit.say('Hello.', [message(reply('Hello.'))])
        one = out['metrics']['oneCall']
        self.assertEqual({name: type(one[name]) for name in ('requests', 'toolCalls', 'rejected', 'rejectedCodes',
                                                             'fallback', 'retry', 'reconciled')},
                         {'requests': int, 'toolCalls': int, 'rejected': int, 'rejectedCodes': list,
                          'fallback': bool, 'retry': bool, 'reconciled': int})
        self.assertEqual(out['metrics']['llmCalls'], one['requests'])
        self.assertEqual(sim_run.model_requests(out), 1)
        self.assertEqual(sim_run.rejected_replies(out), 0)
        self.assertEqual(one['toolOutputs'], [])


if __name__ == '__main__':
    unittest.main()
