"""Provider selection and settlement across the existing two-stage controller."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import test_natural_flow as flow_support
from advisor_budget import AdvisorDailyBudget
from ai_budget import DailyBudget
from chat import ResponsesClient
from claude_client import ClaudeClient
from guest_profiles import ProfileError
from natural_agent import NaturalAgent, TurnReservation


class AdvisorModelTests(unittest.TestCase):
    def setUp(self):
        self.case = flow_support.NaturalFlowTests()
        self.case.setUp()
        self.flow = self.case.flow

    def test_selected_sol_uses_low_for_both_stages_and_replay_binds_selection(self):
        def transport(payload):
            return {**self.flow._agent.client.transport(payload), 'model': payload['model']}

        sol = ResponsesClient(key='fixture', model='gpt-6.1-sol', transport=transport)
        self.flow.model_agents[sol.model] = NaturalAgent.from_agent(self.flow.agent, client=sol)
        self.case.extractions.append(self.case.extraction())
        payload = self.case.payload({'type': 'message', 'message': 'I want to learn about Medicare.'},
                                    model=sol.model, aiProvider='OpenAI')
        result = self.case.take(payload)
        self.assertEqual(result['generated']['status'], 'complete')
        self.assertEqual([(p['model'], p['reasoning']['effort'], p['max_output_tokens'])
                          for p in self.case.calls], [(sol.model, 'low', 2400)] * 2)
        self.assertEqual(self.case.take(payload)['generated']['status'], 'complete')
        self.assertEqual(len(self.case.calls), 2)
        with self.assertRaises(ProfileError):
            self.case.take({**payload, 'aiProvider': 'Anthropic'})
        self.assertEqual(self.flow.agent.client.model, 'gpt-5.4')

    def test_claude_returns_normalized_metered_structured_reply(self):
        client = ClaudeClient('fixture')
        schema = {'type': 'object', 'required': ['reply'], 'additionalProperties': False,
                  'properties': {'reply': {'type': 'string', 'maxLength': 12}}}
        payload = {'instructions': 'Reply in JSON.', 'input': [{'role': 'user', 'content': 'Hello'}],
                   'max_output_tokens': 2400, 'text': {'format': {'schema': schema}}}
        usage = {'input_tokens': 100, 'cache_read_input_tokens': 5, 'output_tokens': 250}
        returned = {'usage': usage, 'model': client.model, 'stop_reason': 'end_turn',
                    'content': [{'type': 'thinking', 'thinking': 'internal'},
                                {'type': 'text', 'text': json.dumps({'reply': 'Hello.'})}]}
        with patch.object(client, 'request', side_effect=[{'input_tokens': 105}, returned]) as request:
            self.assertEqual(client.count(payload), 105)
            response = client.transport(payload)
        count_body, generate_body = (call.args[1] for call in request.call_args_list)
        self.assertEqual(count_body, {k: v for k, v in generate_body.items() if k != 'max_tokens'})
        self.assertNotIn('maxLength', generate_body['output_config']['format']['schema']['properties']['reply'])
        self.assertEqual(generate_body['output_config']['format']['schema']['properties']['reply']['description'],
                         'At most 12 characters.')
        self.assertEqual(response['usage']['input_tokens'], 105)
        self.assertEqual(response['usage']['output_tokens'], 250)
        self.assertEqual(response['output'][0]['content'][0]['text'], '{"reply": "Hello."}')

    def test_claude_keeps_valid_answer_when_optional_draft_is_out_of_bounds(self):
        client = ClaudeClient('fixture')
        schema = {'type': 'object', 'required': ['reply', 'evidence_refs', 'education_followups'],
                  'properties': {'reply': {'type': 'string'},
                                 'evidence_refs': {'type': 'array', 'items': {'enum': ['reviewed']}},
                                 'education_followups': {'type': 'array', 'maxItems': 2}}}
        payload = {'instructions': 'Return a small object.', 'input': [], 'max_output_tokens': 100,
                   'text': {'format': {'name': 'daylight_resolved_conversation', 'schema': schema}}}
        draft = {'reply': 'Here is the answer.', 'evidence_refs': ['reviewed'],
                 'education_followups': ['one', 'two', 'three']}
        for refs in (['reviewed'], ['unreviewed']):
            with self.subTest(refs=refs):
                returned = {'usage': {'input_tokens': 50, 'output_tokens': 25},
                            'model': client.model, 'stop_reason': 'end_turn', 'content': [
                                {'type': 'text', 'text': json.dumps({**draft, 'evidence_refs': refs})}]}
                with patch.object(client, 'request', return_value=returned):
                    response = client.transport(payload)
                self.assertEqual(response['usage']['total_tokens'], 75)
                if refs == ['reviewed']:
                    self.assertNotIn('structured_output_error', response)
                    result = json.loads(response['output'][0]['content'][0]['text'])
                    self.assertEqual(result['reply'], draft['reply'])
                    self.assertEqual(result['evidence_refs'], refs)
                    self.assertEqual(result['education_followups'], [])
                else:
                    self.assertEqual(response['structured_output_error'], 'schema_constraints')

    def test_reviewed_model_rates_and_unissued_hold_share_the_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = AdvisorDailyBudget.adopt(DailyBudget(Path(directory) / 'usage.db'),
                                              pricing_review_path=Path(__file__).resolve().parents[1] / 'pricing-review.json')
            for model, tier, expected in [('gpt-6.1-sol', 'default', 24_008_100),
                                          ('claude-opus-5-5', 'standard', 48_016_200)]:
                with TurnReservation(budget, model) as reservation:
                    stage = reservation.stage('compose')
                    stage.check_input(5)
                    stage.issued()
                    stage.settle({'model': model, 'status': 'completed', 'service_tier': tier,
                                  'usage': {'input_tokens': 5, 'output_tokens': 2400, 'total_tokens': 2405,
                                            'input_tokens_details': {'cached_tokens': 1}}})
                with budget.db() as db:
                    self.assertEqual(db.execute('SELECT measured,output_bound FROM ai_charges WHERE id=?',
                                                (stage.key,)).fetchone(), (expected, 2400))
            self.assertEqual(budget.summary()['reservedOrUncertainUsd'], 0)

    def test_sol_reserves_and_settles_billable_prompt_cache_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = AdvisorDailyBudget.adopt(DailyBudget(Path(directory) / 'usage.db'),
                pricing_review_path=Path(__file__).resolve().parents[1] / 'pricing-review.json')
            receipts = [
                (5407, 5, {'cached_tokens': 0, 'cache_write_tokens': 5404}, 13_566_000),
                (8000, 400, {'cached_tokens': 2000, 'cache_write_tokens': 5000,
                    'cache_write_tokens_details': {'ttl_30m_tokens': 5000, 'ttl_12h_tokens': 0}}, 18_700_000),
            ]
            for inputs, output, details, cost in receipts:
                with TurnReservation(budget, 'gpt-6.1-sol', stages=('extract',)) as reservation:
                    stage = reservation.stage('extract')
                    stage.check_input(inputs)
                    stage.issued()
                    stage.settle({'model': 'gpt-6.1-sol', 'status': 'completed', 'service_tier': 'default',
                        'usage': {'input_tokens': inputs, 'output_tokens': output,
                                  'total_tokens': inputs + output, 'input_tokens_details': details}})
                with budget.db() as db:
                    self.assertEqual(db.execute('SELECT reserved,measured,status FROM ai_charges WHERE id=?',
                        (stage.key,)).fetchone(), (inputs * 2500 + 24_000_000, cost, 'settled'))
                    self.assertIsNone(db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone())

    def test_maya_wording_is_saved_and_birthday_retains_only_the_exception(self):
        self.case.task('timing')
        self.case.choice('RC01', choice='self')
        self.case.choice('T05', choice='cobra')
        self.case.message('I want to understand Medicare timing.',
                          compose={'question_target': 'T04',
                                   'question': 'When would you like Medicare coverage to start?'})
        text = "As soon as I'm eligible. I need help understanding the timing"
        result = self.case.message(text, [self.case.update('T04', {'choice': 'soonest'}, text, scope='intended')],
            compose={'question_target': 'S_AGE65',
                     'question': 'What month and year will you turn 65, and does your birthday fall on the first of that month?'})
        self.assertEqual(self.flow.value(result['guide'], 'coverage.requestedStart'), 'soonest')
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'S_AGE65')
        start = len(self.case.calls)
        self.case.compositions.append(TimeoutError('synthetic connection interruption'))
        self.case.turn({'type': 'message', 'message': 'March 2027, not the first'})
        self.assertEqual(self.flow.value(self.case.g, 'situation.age65'),
                         {'month': 3, 'year': 2027, 'first_day': False})
        self.assertEqual([call['text']['format']['name'] for call in self.case.calls[start:]],
                         ['daylight_resolved_conversation'])

    def test_existing_medicare_review_recovers_to_a_comparison_question(self):
        self.case.task('review')
        self.case.choice('RC01', choice='someone')
        self.case.choice('T05', choice='original')
        result = self.case.message('Please continue with the coverage review.',
                                   compose=TimeoutError('synthetic connection interruption'))
        self.assertEqual(result['generated']['code'], 'transport_or_format')
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'T03')
        self.assertIn('connection ended', result['notice'])
