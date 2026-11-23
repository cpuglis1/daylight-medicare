"""On-demand Medicare source lookup for the composer (D155 Q5, Nov 21, 2026).

Covers the lookup harness: the composer calls lookup_medicare_sources through
a strict function tool instead of receiving teaching sources preloaded, and
code keeps the checks.
(1) a function_call round returns the reviewed source and the model answers
on the next call; the first prompt carries the catalog but no teaching source;
(2) lookups are bounded (LOOKUP_ROUNDS per attempt, LOOKUP_LIMIT per turn),
never counted as repairs, and a model that keeps calling the tool ends in the
source fallback quoting what it looked up, never an unsourced answer;
(3) a repair reuses the sources looked up earlier without a new lookup, and a
replay of the repaired turn returns the cached answer (no 409);
(4) the fallback prefers a looked-up source over the keyword retrieval;
(5) lookup arguments are untrusted: unknown ids and long queries are bounded;
(6) the Claude route and fixture transports keep the keyword retrieval, and
the natural flow stops preloading teaching sources only when tools are on;
(7) review fixes: one lookup per round even when a route returns several
calls, an oversized round is refused before it is funded, a retained question
may cite a looked-up source, an empty store offers no tool, and a looked-up
source the reply cites gets its citation in the flow.
No live models; all data is fictional.
"""
import copy
import json
import unittest
from unittest.mock import patch

import test_composition_recovery as recovery
import test_natural_flow as flow_harness
from claude_client import ClaudeClient
from natural_agent import (FACT_REPAIR_LIMIT, LOOKUP_LIMIT, LOOKUP_QUERY_BOUND, LOOKUP_RESULTS,
                           LOOKUP_ROUNDS, LOOKUP_TOOL)

INVENTED = 'An example amount is $777777.'


def lookup_call(call_id='c1', source_ids=('partb',), query='What is Part B?'):
    """Return a scripted model response item asking for a lookup."""
    return {'type': 'function_call', 'call_id': call_id, 'name': LOOKUP_TOOL,
            'arguments': json.dumps({'query': query, 'source_ids': list(source_ids)})}


class SourceLookupTests(recovery.CompositionRecoveryTests):
    """Reuses the fault-injection harness with function tools turned on."""

    def setUp(self):
        """Ask a fictional Part B question on a route that supports function tools."""
        super().setUp()
        self.agent.client.supports_function_tools = True
        self.context.update(current_message='What is Part B?', evidence=[], message_evidence_ids=[])

    def transport(self, payload):
        """Return a scripted response; a dict with 'type' function_call becomes a tool call."""
        item = self.responses[0] if self.responses else None
        # {'output_items': [...]} scripts a whole output list (several calls, reasoning).
        if isinstance(item, dict) and (item.get('type') == 'function_call' or 'output_items' in item):
            self.calls.append(copy.deepcopy(payload))
            self.responses.pop(0)
            return {'status': 'completed', 'model': self.agent.client.model, 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 20, 'total_tokens': 320,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': copy.deepcopy(item.get('output_items') or [item])}
        return super().transport(payload)

    def content(self, call):
        """Decode the first input item of a recorded request."""
        return json.loads(call['input'][0]['content'])

    def test_lookup_round_returns_the_source_and_the_model_answers(self):
        """One lookup, then the answer: two calls, one counted lookup, one primary attempt."""
        self.responses = [lookup_call(), self.draft(evidence_refs=['partb'])]
        answer = self.compose()
        self.assertEqual(answer['reply'], self.draft()['reply'])
        self.assertEqual(len(self.calls), 2)
        first, second = self.calls
        self.assertEqual([tool['name'] for tool in first['tools']], [LOOKUP_TOOL])
        self.assertEqual((first['tool_choice'], first['parallel_tool_calls']), ('auto', False))
        # No teaching source is preloaded; the model sees only the catalog.
        self.assertEqual(self.content(first)['resolved_context']['evidence'], [])
        self.assertIn('partb', [row['id'] for row in self.content(first)['source_catalog']])
        self.assertNotIn('message_evidence_ids', self.content(first)['resolved_context'])
        returned = [item for item in second['input'] if item.get('type') == 'function_call_output']
        self.assertEqual(len(returned), 1)
        sources = json.loads(returned[0]['output'])['sources']
        self.assertEqual(sources[0]['id'], 'partb')
        self.assertEqual(sources[0]['summary'], self.agent.facts['partb']['summary'])
        self.assertIn('partb', [item['id'] for item in self.content(second)['resolved_context']['evidence']])
        stage = self.reservation.stage('compose')
        self.assertEqual((stage.lookups, stage.primary_attempts), (1, 1))

    def test_last_round_disables_the_tool(self):
        """After LOOKUP_ROUNDS lookups in one attempt the next call sets tool_choice none."""
        self.responses = [lookup_call('c1'), lookup_call('c2', ('basics',)), self.draft()]
        self.compose()
        self.assertEqual(len(self.calls), 1 + LOOKUP_ROUNDS)
        self.assertEqual([call['tool_choice'] for call in self.calls], ['auto', 'auto', 'none'])

    def test_a_model_that_keeps_calling_ends_in_the_quoted_source_within_the_limits(self):
        """Lookups never exceed LOOKUP_LIMIT, repairs stay at FACT_REPAIR_LIMIT, and code quotes partb.

        Attempt 1: two lookups, then a call on the final round (rejected).
        Repair 1: the third lookup, then a final-round call (rejected).
        Repairs 2 and 3: lookups spent, tool_choice none, still a call (rejected).
        """
        self.responses = [lookup_call(f'c{index}') for index in range(7)]
        answer = self.compose()
        self.assertEqual(len(self.calls), 7)
        stage = self.reservation.stage('compose')
        self.assertEqual(stage.lookups, LOOKUP_LIMIT)
        self.assertEqual(stage.primary_attempts, 1 + FACT_REPAIR_LIMIT)
        self.assertEqual(answer['source_fallback'], {'kind': 'quoted', 'reason': 'missing_evidence',
                                                     'evidence_ids': ['partb']})
        self.assertIn(self.agent.facts['partb']['summary'], answer['reply'])
        self.assertEqual([call['tool_choice'] for call in self.calls[-2:]], ['none', 'none'])
        # Every repair after the lookups were spent still sees the looked-up source.
        for call in self.calls[-2:]:
            self.assertIn('partb', [item['id'] for item in self.content(call)['resolved_context']['evidence']])
        self.assertTrue(all(row[0] == 'settled' for row in self.rows()))

    def test_repair_reuses_the_looked_up_source_and_a_replay_hits_the_cache(self):
        """An unsourced draft is repaired with partb reseeded; the same request again costs nothing."""
        self.context['message_evidence_ids'] = ['basics']
        self.responses = [lookup_call(), self.draft(reply=INVENTED), self.draft()]
        answer = self.compose()
        self.assertEqual(len(self.calls), 3)
        repair = self.content(self.calls[2])
        self.assertIn('partb', [item['id'] for item in repair['resolved_context']['evidence']])
        self.assertIn('lookup_medicare_sources', repair['validation_feedback']['source_guidance'])
        replay = self.compose()
        self.assertEqual(replay, answer)
        self.assertEqual(len(self.calls), 3, 'A replay must not call the model again')

    def test_fallback_prefers_the_looked_up_source_over_keyword_retrieval(self):
        """With 'basics' from keyword retrieval and 'partb' looked up, the quote is partb."""
        self.context['message_evidence_ids'] = ['basics']
        self.responses = [lookup_call(), *[self.draft(reply=INVENTED) for _ in range(1 + FACT_REPAIR_LIMIT)]]
        answer = self.compose()
        self.assertEqual(answer['source_fallback']['evidence_ids'], ['partb'])

    def test_lookup_arguments_are_bounded_and_unknown_ids_ignored(self):
        """Model-written arguments cannot reach outside the reviewed store or past the bounds."""
        facts = self.agent.lookup_sources({'query': 'x' * (LOOKUP_QUERY_BOUND * 10),
                                           'source_ids': ['../secrets', 7, 'partb'] + sorted(self.agent.facts)})
        self.assertLessEqual(len(facts), LOOKUP_RESULTS)
        self.assertEqual(facts[0]['id'], 'partb')
        self.assertTrue(all(fact['id'] in self.agent.facts for fact in facts))
        self.assertEqual(self.agent.lookup_sources('not a dict'), [])
        spec = self.agent.lookup_spec()
        self.assertTrue(spec['strict'])
        self.assertFalse(spec['parameters']['additionalProperties'])
        self.assertEqual(spec['parameters']['properties']['source_ids']['items']['enum'], sorted(self.agent.facts))

    def test_only_the_first_of_several_calls_is_run_and_sent_back(self):
        """A route that ignores parallel_tool_calls: one lookup, one call and its output go back.

        A reasoning item without encrypted_content is dropped (it cannot be
        resent with store false); one with it is kept.
        """
        kept = {'type': 'reasoning', 'id': 'r1', 'encrypted_content': 'opaque', 'summary': []}
        dropped = {'type': 'reasoning', 'id': 'r2', 'summary': []}
        self.responses = [{'output_items': [kept, dropped, lookup_call('c1'), lookup_call('c2', ('basics',))]},
                          self.draft(evidence_refs=['partb'])]
        self.compose()
        sent = self.calls[1]['input'][1:]
        self.assertEqual([item.get('type') for item in sent], ['reasoning', 'function_call', 'function_call_output'])
        self.assertEqual(sent[0]['id'], 'r1')
        self.assertEqual({sent[1]['call_id'], sent[2]['call_id']}, {'c1'})
        self.assertEqual(self.reservation.stage('compose').lookups, 1)

    def test_an_oversized_lookup_round_is_refused_before_it_is_funded(self):
        """A round too large to send is never reserved: lookups stay 0 and the repair still runs."""
        self.agent.facts['partb'] = {**self.agent.facts['partb'], 'summary': 'Part B. ' * 6000}
        real = self.transport

        def tight(payload):
            # Allow the first request, then cap the size just above it.
            if not self.calls:
                self.agent.max_input_bytes = len(json.dumps(payload).encode()) + 4000
            return real(payload)
        self.agent.client.transport = tight
        self.responses = [lookup_call(), self.draft()]
        answer = self.compose()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(answer['reply'], self.draft()['reply'])
        stage = self.reservation.stage('compose')
        self.assertEqual((stage.lookups, stage.primary_attempts), (0, 2))
        self.assertTrue(all(row[0] == 'settled' for row in self.rows()))

    def test_retained_question_may_cite_the_looked_up_source(self):
        """Every reply fails, the model's own question cites partb: the fallback keeps that question."""
        own = self.draft(reply=INVENTED, evidence_refs=['partb'],
                         question='Which health insurance do you have today?')
        self.responses = [lookup_call(), *[copy.deepcopy(own) for _ in range(1 + FACT_REPAIR_LIMIT)]]
        answer = self.compose()
        self.assertEqual(answer['source_fallback']['kind'], 'quoted')
        self.assertEqual(answer['question'], own['question'])

    def test_the_round_that_spends_the_last_lookup_disables_the_tool(self):
        """Lookups reach LOOKUP_LIMIT on a repair's first round: its next call is tool_choice none."""
        self.responses = [lookup_call('c0'), lookup_call('c1', ('basics',)), self.draft(reply=INVENTED),
                          lookup_call('c2'), self.draft()]
        self.compose()
        self.assertEqual(self.reservation.stage('compose').lookups, LOOKUP_LIMIT)
        self.assertEqual([call['tool_choice'] for call in self.calls], ['auto', 'auto', 'none', 'auto', 'none'])

    def test_fallback_quotes_the_source_both_lookup_and_retrieval_found(self):
        """The model looks up basics then partb; retrieval found partb, so partb is quoted."""
        self.context['message_evidence_ids'] = ['partb']
        self.responses = [lookup_call(source_ids=('basics', 'partb')),
                          *[self.draft(reply=INVENTED) for _ in range(1 + FACT_REPAIR_LIMIT)]]
        answer = self.compose()
        self.assertEqual(answer['source_fallback']['evidence_ids'], ['partb'])

    def test_an_empty_store_offers_no_tool(self):
        """With no reviewed sources the route keeps the keyword path (a strict enum may not be empty)."""
        self.agent.facts = {}
        self.assertFalse(self.agent.source_lookup_enabled())


# Run only the tests above, not the inherited recovery suite a second time.
for _name in [name for name in dir(recovery.CompositionRecoveryTests) if name.startswith('test_')]:
    if _name not in SourceLookupTests.__dict__:
        setattr(SourceLookupTests, _name, None)


class RouteTests(unittest.TestCase):
    def test_claude_route_and_fixture_transports_keep_keyword_retrieval(self):
        """Claude declares no function tools; a scripted transport is not assumed to have them."""
        self.assertIs(ClaudeClient.supports_function_tools, False)
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent = case.flow.agent
        self.assertFalse(agent.source_lookup_enabled())
        agent.client.supports_function_tools = True
        self.assertTrue(agent.source_lookup_enabled())

    def test_flow_preloads_no_teaching_source_when_tools_are_on(self):
        """With tools on the composed context has no partb; message_evidence_ids still names it."""
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.flow.agent.client.supports_function_tools = True
        case.message('This is for me.', [case.update('RC01', {'choice': 'self'}, 'This is for me.')])
        case.message('What is Part B?')
        payload = case.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertNotIn('partb', [item['id'] for item in payload['resolved_context']['evidence']])
        self.assertIn('partb', [row['id'] for row in payload['source_catalog']])

    def test_a_looked_up_source_the_reply_cites_gets_its_citation(self):
        """Tools on, nothing preloaded, the reply cites partb: the advisor lists partb's source."""
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent = case.flow.agent
        agent.client.supports_function_tools = True
        case.message('This is for me.', [case.update('RC01', {'choice': 'self'}, 'This is for me.')])
        original = agent.compose

        def cites_partb(*args, **kwargs):
            composed = copy.deepcopy(original(*args, **kwargs))
            composed['evidence_refs'] = ['partb']
            return composed
        with patch.object(agent, 'compose', side_effect=cites_partb):
            out = case.message('What is Part B?')
        fact = agent.facts['partb']
        urls = [source['url'] for source in out['advisor']['sources']]
        expected = [fact['source']] if fact.get('source') else [item['url'] for item in fact.get('sources', [])]
        self.assertTrue(expected)
        self.assertEqual(urls[:len(expected)], expected)


if __name__ == '__main__':
    unittest.main()
