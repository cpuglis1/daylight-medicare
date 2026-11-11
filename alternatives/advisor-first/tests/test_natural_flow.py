"""D86 natural-flow integration contracts; scripted Responses transport, no paid calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Registers the retained engine imports without starting a server.
from advisor_flow import fingerprint
from chat import ModelUnavailable, ResponsesClient
from guest_profiles import ProfileError
from natural_flow import CONTEXT_POLICY, NaturalConversation
from situation import observations


class NaturalFlowTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.extractions = []
        self.compositions = []
        # Older state/provenance fixtures supplied answer-only prose. Keep
        # those fixtures valid under the active-turn contract without treating
        # this scripted question as evidence of real conversational quality.
        # Negative response-contract tests explicitly disable this convenience.
        self.supply_fixture_followup = True

        def transport(payload):
            self.calls.append(copy.deepcopy(payload))
            name = payload['text']['format']['name']
            if name == 'daylight_guide_commands':
                self.assertTrue(self.extractions, 'Unexpected extraction call')
                value = self.extractions.pop(0)
                if isinstance(value, dict) and 'mode' in value:
                    # Retain concise historical scenario fixtures, but put only
                    # the new interpretation contract on the simulated wire.
                    sent = json.loads(payload['input'][0]['content'])
                    text = sent['submitted_text']
                    context = sent['confirmed_context']
                    role = next((item['value'] for item in context.get('reports', [])
                                 if item['id'] == 'guide.subject.role'), None)
                    situations = []
                    for kind, reported in observations(text, role).items():
                        situations.append({'kind': kind, 'subject': 'beneficiary',
                            'scope': 'current', 'quote': text, 'uncertain': False,
                            'correction': False, 'month': reported.get('month'),
                            'year': reported.get('year'), 'status': reported.get('status', ''),
                            'when': reported.get('when', '')})
                    updates = copy.deepcopy(value.get('updates', []))
                    if value['mode'] == 'defer' and context.get('activeQuestion'):
                        updates.append(self.update(context['activeQuestion']['id'],
                                                   {'choice': 'deferred'}, text))
                    goal = value.get('practical_request', {}).get('quote', '') or value.get('task_quote', '')
                    value = {'updates': updates, 'requests': value.get('requests', []),
                             'fact_ids': value.get('fact_ids', []),
                             'agenda': value.get('agenda', {'concerns': [], 'priorityReason': {}}),
                             'situation_proposals': value.get('situation_proposals', situations),
                             'goal_quote': value.get('goal_quote', goal)}
                if isinstance(value, dict):
                    value.setdefault('education_request', {'kind': 'none', 'concept_ids': [], 'quote': ''})
            elif name == 'daylight_resolved_conversation':
                sent = json.loads(payload['input'][0]['content'])
                self.assertIn('question_candidates', sent)
                self.assertNotIn('eligible_moves', sent)
                value = self.compositions.pop(0) if self.compositions else {}
                if callable(value):
                    value = value(sent)
                if not isinstance(value, Exception):
                    move = next(iter(sent['question_candidates']), {})
                    question = move.get('question') or {}
                    value = copy.deepcopy(value)
                    legacy_move = value.pop('move_id', None)
                    target = value.get('question_target', move.get('id'))
                    if legacy_move is not None:
                        target = None if legacy_move in {'answer', 'invite', 'revise'} else legacy_move.split(':')[-1]
                    elif value.get('question') == '' and 'question_target' not in value:
                        target = None
                    value = {'question_target': target,
                             'reply': 'We can work through the next useful detail together.',
                             'question': question.get('question', '') if target is not None else '',
                             'report_refs': [], 'evidence_refs': [],
                             'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                             'agenda_update': {'current_concern': '', 'pause': False}, **value}
                    if (self.supply_fixture_followup and sent['resolved_context'].get('require_followup')
                            and not value['question'] and not value['agenda_update']['pause']):
                        value['question'] = 'What would be most helpful to explore next?'
            else:
                self.fail('Unexpected model schema: ' + name)
            if isinstance(value, Exception):
                raise value
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70,
                              'total_tokens': 370, 'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}

        self.flow = NaturalConversation(None, None,
            json.loads((HERE/'web/guide-contract.json').read_text()),
            json.loads((HERE/'web/teaching-facts.json').read_text()),
            json.loads((HERE/'web/readiness-content.json').read_text()),
            ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport),
            True, None, fixture=False)
        self.g, self.r = self.flow.initial()
        self.owner = uuid.uuid4().hex
        self.continuation = None

    @staticmethod
    def update(id, fields, quote, **extra):
        return {'id': id, 'entity': 'profile',
                'fields': [{'key': key, 'value': value} for key, value in fields.items()],
                'quote': quote, 'scope': 'current', 'subject': 'beneficiary',
                'uncertain': False, 'correction': False, **extra}

    @staticmethod
    def extraction(updates=(), **extra):
        return {'mode': 'report', 'task': '', 'task_quote': '', 'requests': [],
                'updates': list(updates), 'fact_ids': [], 'reflection': '',
                'confirmation': '', 'move_id': 'ask', 'reason_id': 'context', **extra}

    def payload(self, action, **extra):
        payload = {'guide': copy.deepcopy(self.g), 'record': copy.deepcopy(self.r),
                   'action': action, 'requestId': str(uuid.uuid4()), 'aiConsent': True,
                   'contextPolicy': CONTEXT_POLICY, **extra}
        if self.continuation is not None:
            payload['continuation'] = self.continuation
        return payload

    def take(self, payload):
        out = self.flow.turn(self.owner, payload)
        self.g, self.r = out['guide'], out['record']
        self.continuation = out['continuation']
        return out

    def turn(self, action, **extra):
        return self.take(self.payload(action, **extra))

    def message(self, text, updates=(), *, compose=None, extraction=None, **extra):
        self.extractions.append(extraction or self.extraction(updates))
        if compose is not None:
            self.compositions.append(compose)
        return self.turn({'type': 'message', 'message': text}, **extra)

    def choice(self, id, **fields):
        return self.turn({'type': 'choice', 'id': id, 'fields': fields}, aiConsent=False, contextPolicy=None)

    def task(self, task):
        return self.turn({'type': 'task', 'task': task, 'preparing': True})

    def stage_payloads(self, name):
        return [json.loads(call['input'][0]['content']) for call in self.calls
                if call['text']['format']['name'] == name]

    def extracted_context(self, index=-1):
        return self.stage_payloads('daylight_guide_commands')[index]['confirmed_context']

    def composed_context(self, index=-1):
        return self.stage_payloads('daylight_resolved_conversation')[index]['resolved_context']

    def test_exact_retirement_example_commits_without_review_and_generates_followup(self):
        text = "I've been retired for a few years, and am turning 65 in November."
        reply = 'We can take this step by step so you feel ready for what comes next.'
        question = 'What health insurance do you have now?'
        # Current coverage remains an allowed consequential follow-up even
        # when comparison guidance ranks ZIP first; choose its meaning explicitly.
        out = self.message(text, compose={'question_target': 'T05', 'reply': reply, 'question': question})
        self.assertNotIn('review', out)
        self.assertEqual(out['pendingUpdates'], [])
        self.assertEqual(out['reply'], reply)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(out['assessment']['nextQuestion']['question'], question)
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T05'})
        self.assertEqual(self.flow.value(self.g, 'situation.retirement'),
                         {'status': 'retired', 'when': 'for a few years'})
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        for field in ('coverage.current', 'coverage.requestedStartMonth'):
            self.assertNotIn(field, self.g['fields'])
        self.assertNotIn('RC04', self.r['facts'])
        for field in ('situation.retirement', 'situation.age65', 'subject.role'):
            self.assertEqual(self.g['fields'][field]['confirmation'], 'reported_by_user')
            provenance = self.r['natural']['provenance']['guide.' + field]
            self.assertEqual(provenance['method'], 'direct_report')
            self.assertEqual(provenance['status'], 'user_reported')
        self.assertEqual([call['text']['format']['name'] for call in self.calls],
                         ['daylight_guide_commands', 'daylight_resolved_conversation'])
        self.assertTrue(all(call['store'] is False and call['tools'] == [] for call in self.calls))

    def test_unsupported_retiree_guess_is_absent_from_composition(self):
        text = "I've been retired for a few years, and am turning 65 in November."
        self.message(text, [self.update('T05', {'choice': 'retiree'}, text),
                            self.update('RC09', {'choice': 'retiree'}, text)])
        self.assertNotIn('coverage.current', self.g['fields'])
        self.assertNotIn('RC09', self.r['facts'])
        reports = self.composed_context()['reports']
        self.assertFalse(any(item['id'] in {'guide.coverage.current', 'readiness.RC09.profile.choice'}
                             for item in reports))
        self.assertIn('guide.situation.age65', {item['id'] for item in reports})

    def test_multiturn_context_preserves_orientation_and_separate_dates(self):
        # This scenario tests the timing context lens, not the comparison
        # lens that intentionally minimizes unrelated older birthday reports.
        self.turn({'type': 'task', 'task': 'timing', 'preparing': True},
                  aiConsent=False, contextPolicy=None)
        first = "I've been retired for a few years, and am turning 65 in November."
        self.message(first, compose={'question_target': 'T02'})
        self.message('I am just getting started.')
        context = self.extracted_context()
        self.assertEqual(context['activeQuestion']['id'], 'T02')
        table = context['question_table']
        self.assertEqual(table['columns'], ['id', 'question', 'options', 'fields', 'purpose',
                                            'dependency', 'requiredWhen', 'cannotInfer'])
        self.assertEqual(len(table['rows']), 41)
        rows = {row[0]: dict(zip(table['columns'], row)) for row in table['rows']}
        self.assertEqual(set(rows), {item['id'] for item in self.flow.agent.definitions})
        for definition in self.flow.agent.definitions:
            self.assertEqual({key: rows[definition['id']][key] for key in definition}, definition)
        self.assertIn('guide.situation.age65', {item['id'] for item in context['reports']})
        self.assertNotIn('RC04', self.r['facts'])
        text = "My current health insurance is through my wife's current job."
        self.message(text, [self.update('T05', {'choice': 'employer'}, text),
                            self.update('RC09', {'choice': 'spouse_job'}, text)])
        text = 'Her job ends in March 2027, and that health insurance ends in April 2027.'
        self.message(text, [self.update('RC11', {'jobEnd': 'March 2027', 'coverageEnd': 'April 2027'}, text)])
        self.assertEqual(self.flow.report(self.r, 'RC11')['jobEnd'], '2027-03')
        self.assertEqual(self.flow.report(self.r, 'RC11')['coverageEnd'], '2027-04')
        self.assertNotIn('coverage.requestedStartMonth', self.g['fields'])
        final = {item['id']: item['value'] for item in self.composed_context()['reports']}
        self.assertEqual(final['guide.situation.age65'], {'month': 11, 'year': None})
        self.assertEqual(final['readiness.RC09.profile.choice'], 'spouse_job')
        self.assertEqual(final['readiness.RC11.profile.jobEnd'], '2027-03')
        self.assertEqual(final['readiness.RC11.profile.coverageEnd'], '2027-04')
        self.assertNotIn(first, json.dumps(self.r['natural']))

    def test_tentative_fact_is_held_while_clear_birthday_commits(self):
        text = 'I think my current health insurance is through my current job. I turn 65 in November.'
        out = self.message(text, [self.update('T05', {'choice': 'employer'}, text, uncertain=True)])
        self.assertNotIn('coverage.current', self.g['fields'])
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
        self.assertNotIn('review', out)
        self.assertEqual(out['generated']['move'], 'T05')
        self.assertTrue(self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates'][0]['required'])
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        context = self.composed_context()
        self.assertEqual(context['uncertainties'], [{'id': 'T05', 'status': 'needs_clarification'}])
        self.assertFalse(any(item['id'] == 'guide.coverage.current' for item in context['reports']))

    def test_brief_spouse_reply_uses_active_question_without_inventing_new_scope(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.choice('T04', choice='month', month='April 2027')
        self.choice('T05', choice='employer')
        self.assertEqual(self.flow.assess(self.g, self.r)['nextQuestion']['id'], 'RC09')
        text = 'Through my wife.'
        out = self.message(text, [self.update('RC09', {'choice': 'spouse_job'}, text)])
        self.assertEqual(self.extracted_context()['activeQuestion']['id'], 'RC09')
        self.assertEqual(self.flow.report(self.r, 'RC09').get('choice'), 'spouse_job')
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertNotIn('review', out)
        self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'RC09')

    def test_mixed_educational_question_keeps_clear_report_and_reviewed_evidence(self):
        text = 'This is for me. What is Medicare?'
        out = self.message(text, [self.update('RC01', {'choice': 'self'}, 'This is for me.')],
            extraction=self.extraction([self.update('RC01', {'choice': 'self'}, 'This is for me.')],
                                       mode='answer', fact_ids=['basics']),
            compose={'reply': 'Medicare is federal health insurance.',
                     'evidence_refs': ['basics'],
                     'education': {'purpose': 'teach', 'updates': [
                         {'concept_id': 'medicare_basics', 'depth': 'introduced',
                          'reason': 'new', 'evidence_refs': ['basics']}], 'visual': 'none'}})
        self.assertNotIn('review', out)
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        self.assertEqual(out['facts'], [])
        self.assertIn('basics', out['advisor']['teachingFactIds'])
        self.assertIn('basics', {fact['id'] for fact in self.composed_context()['evidence']})
        self.assertEqual(out['generated']['status'], 'complete')

    def test_explicit_defer_moves_on_without_inventing_an_answer(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.assertEqual(self.flow.assess(self.g, self.r)['nextQuestion']['id'], 'T04')
        out = self.message("I don't know yet; let's leave that for later.",
                           extraction=self.extraction(mode='defer'))
        self.assertIsNone(self.flow.value(self.g, 'coverage.requestedStartMonth'))
        self.assertNotEqual(out['assessment']['nextQuestion']['id'], 'T04')
        self.assertIn('T04', {item['id'] for item in out['assessment']['unresolvedReportedInputs']})
        self.assertNotIn('review', out)

    def test_exact_typed_unknown_moves_past_active_question_without_model_or_transfer(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.assertEqual(self.flow.assess(self.g, self.r)['nextQuestion']['id'], 'T04')
        with patch.object(self.flow.agent, 'reserve_turn', side_effect=AssertionError('Unknown must not reserve a model turn')):
            out = self.turn({'type': 'message', 'message': 'I don’t know'}, aiConsent=False)
        self.assertIsNone(self.flow.value(self.g, 'coverage.requestedStartMonth'))
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T04')
        self.assertIn('T04', {item['id'] for item in out['assessment']['unresolvedReportedInputs']})
        self.assertEqual(out['metrics']['llmCalls'], 0)
        self.assertEqual(self.calls, [])
        self.assertNotIn('review', out)

    def test_exact_typed_unknown_clears_tentative_birthday_without_repeating_it(self):
        self.message('I think I turn 65 in November.')
        self.assertEqual(self.flow.pending_for(self.owner)['update']['id'], 'S_AGE65')
        calls_before = len(self.calls)
        with patch.object(self.flow.agent, 'reserve_turn', side_effect=AssertionError('Unknown must not reserve a model turn')):
            out = self.turn({'type': 'message', 'message': 'I don’t know'}, aiConsent=False)
        self.assertNotIn('situation.age65', self.g['fields'])
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'S_AGE65')
        refreshed = self.turn({'type': 'refresh'})
        self.assertNotEqual((refreshed['assessment']['nextQuestion'] or {}).get('id'), 'S_AGE65')
        self.assertEqual(len(self.calls), calls_before)
        self.assertEqual(out['metrics']['llmCalls'], 0)

    def test_exact_typed_check_later_defers_familiarity_without_model_or_repeat(self):
        first = self.message('I turn 65 in November.', compose={'question_target': 'T02'})
        self.assertEqual(first['assessment']['nextQuestion']['id'], 'T02')
        calls_before = len(self.calls)
        with patch.object(self.flow.agent, 'reserve_turn', side_effect=AssertionError('Defer must not reserve a model turn')):
            out = self.turn({'type': 'message', 'message': 'check later'}, aiConsent=False)
        self.assertEqual(self.r['conversation']['baselineDispositions']['T02'], 'deferred')
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T02')
        refreshed = self.turn({'type': 'refresh'})
        self.assertNotEqual((refreshed['assessment']['nextQuestion'] or {}).get('id'), 'T02')
        self.assertEqual(len(self.calls), calls_before)
        self.assertEqual(out['metrics']['llmCalls'], 0)
        self.assertNotIn('review', out)

    def test_conflicting_report_preserves_prior_value_and_excludes_candidate(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        text = 'My current health insurance is retiree coverage through my former employer.'
        out = self.message(text, [self.update('T05', {'choice': 'retiree'}, text)])
        self.assertEqual(self.g['fields']['coverage.current']['value'], ['employer'])
        self.assertEqual(self.g['fields']['coverage.current']['status'], 'stale')
        self.assertIsNone(self.flow.value(self.g, 'coverage.current'))
        self.assertEqual(out['generated']['move'], 'T05')
        context = self.composed_context()
        self.assertFalse(any(item['id'] == 'guide.coverage.current' for item in context['reports']))
        self.assertTrue(any(item['id'] == 'guide.coverage.current' and item['status'] in {'stale', 'conflicting'}
                            for item in context['known']))
        self.assertNotIn('retiree', json.dumps(context['reports']))

    def test_pending_insurance_conflict_resolves_from_clear_reply_without_correction_word(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        text = 'My current health insurance is retiree coverage through my former employer.'
        self.message(text, [self.update('T05', {'choice': 'retiree'}, text)])
        self.assertIsNotNone(self.flow.pending_for(self.owner))
        self.assertIsNone(self.flow.value(self.g, 'coverage.current'))
        out = self.message(text, [self.update('T05', {'choice': 'retiree'}, text)])
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['retiree'])
        self.assertEqual(self.g['fields']['coverage.current']['status'], 'reported')
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertNotIn('review', out)
        self.assertEqual(self.composed_context()['uncertainties'], [])
        current = next(item for item in self.composed_context()['reports']
                       if item['id'] == 'guide.coverage.current')
        self.assertEqual(current['value'], ['retiree'])

    def test_pending_ambiguity_does_not_leak_to_another_visit_with_matching_versions(self):
        tentative = 'I think my current health insurance is through my current job.'
        self.message(tentative, [self.update('T05', {'choice': 'employer'}, tentative, uncertain=True)])
        visit_a = copy.deepcopy((self.g, self.r, self.continuation))
        self.assertIsNotNone(self.flow.pending_for(self.owner))
        self.g, self.r = self.flow.initial()
        self.continuation = None
        self.turn({'type': 'read_concept', 'id': 'basics'})
        self.turn({'type': 'read_concept', 'id': 'parts'})
        self.assertEqual([self.g['stateVersion'], self.r['stateVersion']],
                         [visit_a[0]['stateVersion'], visit_a[1]['stateVersion']])
        out = self.message('What is Medicare?', extraction=self.extraction(mode='answer', fact_ids=['basics']))
        self.assertNotEqual(out['generated']['move'], 'clarify')
        self.assertNotEqual((self.extracted_context().get('activeQuestion') or {}).get('id'), 'T05')
        self.assertEqual(self.composed_context()['uncertainties'], [])
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.g, self.r, self.continuation = visit_a
        clear = 'My current health insurance is through my current job.'
        self.message(clear, [self.update('T05', {'choice': 'employer'}, clear)])
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_two_visits_retain_their_own_pending_clarification(self):
        self.message('I think I turn 65 in November.')
        visit_a = copy.deepcopy((self.g, self.r, self.continuation))
        self.g, self.r = self.flow.initial()
        self.continuation = None
        self.message('I think I am retired.')
        self.g, self.r, self.continuation = visit_a
        self.message('December')
        self.assertEqual(self.extracted_context()['activeQuestion']['id'], 'S_AGE65')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 12, 'year': None})
        self.assertNotIn('situation.retirement', self.g['fields'])

    def test_tentative_life_report_does_not_become_an_accepted_birthday(self):
        text = 'I think I turn 65 in November.'
        self.message(text, [self.update('RC06', {'choice': 'age65'}, text, uncertain=True)])
        self.assertNotIn('situation.age65', self.g['fields'])
        self.assertNotIn('RC06', self.r['facts'])
        self.assertFalse(any(item['id'] == 'guide.situation.age65'
                             for item in self.composed_context()['reports']))

    def test_conflicting_birthday_stays_open_until_explicit_correction(self):
        self.message('I turn 65 in November.')
        before = copy.deepcopy(self.g['fields']['situation.age65'])
        self.message('I turn 65 in December.')
        self.assertEqual(self.g['fields']['situation.age65']['value'], {'month': 11, 'year': None})
        self.assertEqual(self.g['fields']['situation.age65']['status'], 'stale')
        self.assertIsNone(self.flow.value(self.g, 'situation.age65'))
        context = self.composed_context()
        self.assertFalse(any(item['id'] == 'guide.situation.age65' for item in context['reports']))
        self.assertTrue(any(item['id'] == 'guide.situation.age65' and item['status'] in {'stale', 'conflicting'}
                            for item in context['known']))
        self.message('Correction: I turn 65 in December.')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 12, 'year': None})
        provenance = self.r['natural']['provenance']['guide.situation.age65']
        self.assertEqual(provenance['supersedesRevision'], before['revision'])
        self.assertEqual(self.g['fields']['situation.age65']['confirmation'], 'reported_by_user')

    def test_targeted_birthday_clarification_accepts_month_only_reply(self):
        self.message('I turn 65 in November.')
        conflict = self.message('I turn 65 in December.')
        self.assertEqual(conflict['assessment']['nextQuestion']['id'], 'S_AGE65')
        out = self.message('December')
        self.assertEqual(self.extracted_context()['activeQuestion']['id'], 'S_AGE65')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 12, 'year': None})
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertNotIn('review', out)
        self.assertEqual(self.composed_context()['uncertainties'], [])

    def test_helper_and_two_medicine_strengths_preserve_person_and_item_scope(self):
        self.task('drug_coverage')
        text = ('This is for my mother. I have health insurance through my current job. '
                'She takes Example Med 5 mg tablet and Example Med 10 mg tablet.')
        out = self.message(text, [
            self.update('RC01', {'choice': 'someone'}, 'This is for my mother.'),
            self.update('T05', {'choice': 'employer'}, 'I have health insurance through my current job.', subject='learner'),
            self.update('T07', {'text': 'Example Med'}, 'She takes Example Med 5 mg tablet and Example Med 10 mg tablet.'),
            self.update('RC22', {'name': 'Example Med', 'strength': '5 mg', 'form': 'tablet'}, 'She takes Example Med 5 mg tablet', entity='new'),
            self.update('RC22', {'name': 'Example Med', 'strength': '10 mg', 'form': 'tablet'}, 'Example Med 10 mg tablet.', entity='new'),
        ])
        self.assertNotIn('review', out)
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'someone')
        self.assertNotIn('coverage.current', self.g['fields'])
        items = self.flow.report(self.r, 'RC22')['items']
        self.assertEqual({item['strength'] for item in items}, {'5 mg', '10 mg'})
        self.assertEqual(len({item['entity'] for item in items}), 2)
        context = self.composed_context()
        self.assertTrue(all(item['provenance'].get('subject') == 'beneficiary'
                            for item in context['reports'] if item['id'].startswith('readiness.RC22.')))
        for item in items:
            self.assertIn('readiness.RC22.' + item['entity'] + '.strength',
                          {report['id'] for report in context['reports']})

    def seed_item_reports(self, identifier):
        self.task('providers' if identifier == 'RC21' else 'drug_pricing')
        self.choice('RC01', choice='self')
        if identifier == 'RC21':
            for number, city in ((1, 'Naples'), (2, 'Tampa')):
                self.turn({'type': 'choice', 'id': 'RC21', 'entity': 'doctor-' + str(number),
                           'fields': {'practice': 'Example Clinic ' + str(number), 'city': city}})
        else:
            for number, strength in ((1, '5 mg'), (2, '10 mg')):
                self.turn({'type': 'choice', 'id': 'RC22', 'entity': 'medicine-' + str(number),
                           'fields': {'name': 'Example Med', 'strength': strength, 'form': 'tablet'}})
                if identifier == 'RC23':
                    self.turn({'type': 'choice', 'id': 'RC23', 'entity': 'medicine-' + str(number),
                               'fields': {'quantity': str(number * 30) + ' tablets', 'daysSupply': '30'}})
        return copy.deepcopy(self.r['facts'][identifier]['value']['items'])

    def check_targeted_aggregate_resolution(self, identifier, entity, fields, text):
        before = self.seed_item_reports(identifier)
        update = self.update(identifier, fields, text, entity=entity)
        self.message(text, [update])
        self.assertTrue(self.r['facts'][identifier]['stale'])
        self.message(text, [update])
        items = self.r['facts'][identifier]['value']['items']
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1], before[1])
        self.assertTrue(all(next(item for item in items if item['entity'] == entity)[key] == value
                            for key, value in fields.items()))
        self.assertFalse(self.r['facts'][identifier]['stale'])
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_provider_clarification_preserves_other_provider_reports(self):
        self.check_targeted_aggregate_resolution('RC21', 'doctor-1', {'city': 'Miami'},
                                                  'The first clinic is in Miami.')

    def test_medicine_clarification_preserves_other_medicine_reports(self):
        self.check_targeted_aggregate_resolution('RC22', 'medicine-1', {'strength': '20 mg'},
                                                  'The first medicine is 20 mg.')

    def test_fill_clarification_preserves_other_medicine_fill_reports(self):
        self.check_targeted_aggregate_resolution('RC23', 'medicine-1', {'quantity': '90 tablets'},
                                                  'The first medicine quantity is 90 tablets.')

    def test_other_medicine_edit_preserves_pending_target_and_aggregate_hold(self):
        self.seed_item_reports('RC22')
        text = 'The first medicine is 20 mg.'
        first = self.update('RC22', {'strength': '20 mg'}, text, entity='medicine-1')
        self.message(text, [first])
        other = 'Correction: the second medicine is 30 mg.'
        self.message(other, [self.update('RC22', {'strength': '30 mg'}, other,
                                         entity='medicine-2', correction=True)])
        pending = self.flow.pending_for(self.owner)
        self.assertIsNotNone(pending)
        self.assertEqual(pending['update']['entity'], 'medicine-1')
        self.assertTrue(self.r['facts']['RC22']['stale'])
        items = self.r['facts']['RC22']['value']['items']
        self.assertEqual({item['entity']: item['strength'] for item in items},
                         {'medicine-1': '5 mg', 'medicine-2': '30 mg'})
        self.assertFalse(any(item['id'].startswith('readiness.RC22.')
                             for item in self.composed_context()['reports']))
        self.message(text, [first])
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertEqual({item['entity']: item['strength'] for item in self.flow.report(self.r, 'RC22')['items']},
                         {'medicine-1': '20 mg', 'medicine-2': '30 mg'})

    def queue_two_medicine_conflicts(self):
        self.seed_item_reports('RC22')
        first = 'The first medicine is 20 mg.'
        second = 'The second medicine is 30 mg.'
        self.message(first + ' ' + second, [
            self.update('RC22', {'strength': '20 mg'}, first, entity='medicine-1'),
            self.update('RC22', {'strength': '30 mg'}, second, entity='medicine-2')])
        pending = self.flow.pending_for(self.owner)
        self.assertEqual(pending['update']['entity'], 'medicine-1')
        self.assertEqual(pending['remaining'][0]['entity'], 'medicine-2')
        return first

    def test_multiple_item_conflicts_keep_hold_until_message_and_structured_resolution(self):
        first = self.queue_two_medicine_conflicts()
        self.message(first, [self.update('RC22', {'strength': '20 mg'}, first, entity='medicine-1')])
        self.assertTrue(self.r['facts']['RC22']['stale'])
        self.assertEqual(self.flow.pending_for(self.owner)['update']['entity'], 'medicine-2')
        self.assertFalse(any(item['id'].startswith('readiness.RC22.')
                             for item in self.composed_context()['reports']))
        calls_before = len(self.calls)
        self.turn({'type': 'choice', 'id': 'RC22', 'entity': 'medicine-2', 'fields': {'strength': '30 mg'}}, aiConsent=False, contextPolicy=None)
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertFalse(self.r['facts']['RC22']['stale'])
        self.assertEqual({item['entity']: item['strength'] for item in self.flow.report(self.r, 'RC22')['items']},
                         {'medicine-1': '20 mg', 'medicine-2': '30 mg'})
        self.assertEqual(len(self.calls), calls_before)

    def test_unknown_and_defer_advance_item_queue_without_losing_sibling_reports(self):
        self.queue_two_medicine_conflicts()
        calls_before = len(self.calls)
        out = self.turn({'type': 'message', 'message': 'I don’t know'}, aiConsent=False)
        self.assertEqual(out['assessment']['nextQuestion']['entity'], 'medicine-2')
        self.assertTrue(self.r['facts']['RC22']['stale'])
        self.assertEqual(self.flow.pending_for(self.owner)['update']['entity'], 'medicine-2')
        self.turn({'type': 'message', 'message': 'check later'}, aiConsent=False)
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertFalse(self.r['facts']['RC22']['stale'])
        items = self.r['facts']['RC22']['value']['items']
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item['name'] == 'Example Med' and item['form'] == 'tablet' for item in items))
        self.assertTrue(all('strength' not in item for item in items))
        self.assertEqual(len(self.calls), calls_before)

    def test_other_field_on_same_item_does_not_resolve_pending_strength(self):
        self.seed_item_reports('RC22')
        first = 'The first medicine is 20 mg.'
        self.message(first, [self.update('RC22', {'strength': '20 mg'}, first, entity='medicine-1')])
        other = 'Correction: the first medicine form is capsule.'
        self.message(other, [self.update('RC22', {'form': 'capsule'}, other, entity='medicine-1', correction=True)])
        self.assertEqual(self.flow.pending_for(self.owner)['update']['fields'], {'strength': '20 mg'})
        self.assertTrue(self.r['facts']['RC22']['stale'])
        items = self.r['facts']['RC22']['value']['items']
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['strength'], '5 mg')
        self.assertEqual(items[0]['form'], 'capsule')

    def test_explicit_correction_supersedes_report_and_invalidates_named_action(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        before = copy.deepcopy(self.g['fields']['coverage.current'])
        review = self.turn({'type': 'review_preparation'})
        text = 'Correction: my current health insurance is retiree coverage through my former employer.'
        self.message(text, [self.update('T05', {'choice': 'retiree'}, text, correction=True)])
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['retiree'])
        provenance = self.r['natural']['provenance']['guide.coverage.current']
        self.assertEqual(provenance['supersedesRevision'], before['revision'])
        self.assertEqual(self.g['fields']['coverage.current']['confirmation'], 'reported_by_user')
        with self.assertRaises(ProfileError):
            self.turn({'type': 'run_preparation', 'token': review['review']['token']})

    def test_correctly_signed_old_snapshot_cannot_execute_preparation_after_edit(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        review = self.turn({'type': 'review_preparation'})
        stale_action = self.payload({'type': 'run_preparation', 'token': review['review']['token']})
        self.choice('T02', choice='comfortable')
        with self.assertRaises(ProfileError) as rejected:
            self.flow.turn(self.owner, stale_action)
        self.assertEqual(rejected.exception.code, 409)
        self.assertNotIn((self.owner, stale_action['requestId']), self.flow.turn_journal)
        self.assertEqual(self.calls, [])

    def test_resuming_old_snapshot_cannot_revive_stale_preparation_authorization(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        review = self.turn({'type': 'review_preparation'})
        old_guide, old_record = copy.deepcopy((self.g, self.r))
        self.choice('T02', choice='comfortable')
        resumed = self.flow.turn(self.owner, {
            'guide': old_guide, 'record': old_record, 'action': {'type': 'refresh'},
            'requestId': str(uuid.uuid4()), 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner, {
                'guide': resumed['guide'], 'record': resumed['record'],
                'continuation': resumed['continuation'],
                'action': {'type': 'run_preparation', 'token': review['review']['token']},
                'requestId': str(uuid.uuid4()), 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
        self.assertEqual(self.calls, [])

    def test_lost_response_replay_returns_identical_state_without_extra_calls(self):
        text = "I've been retired for a few years, and am turning 65 in November."
        self.extractions.append(self.extraction())
        payload = self.payload({'type': 'message', 'message': text})
        first = self.flow.turn(self.owner, copy.deepcopy(payload))
        replay = self.flow.turn(self.owner, copy.deepcopy(payload))
        self.assertEqual(replay, first)
        self.assertEqual(len(self.calls), 2)
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner, {**payload, 'action': {'type': 'message', 'message': 'A different message'}})
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn(text, json.dumps(list(self.flow.turn_journal.values())))

    def test_composition_failure_preserves_capture_and_replay_never_reextracts(self):
        text = 'My current health insurance is through my current job.'
        self.extractions.append(self.extraction([self.update('T05', {'choice': 'employer'}, text)]))
        self.compositions.append(TimeoutError('fictional response interrupted'))
        payload = self.payload({'type': 'message', 'message': text})
        first = self.flow.turn(self.owner, copy.deepcopy(payload))
        self.assertEqual(first['guide']['fields']['coverage.current']['value'], ['employer'])
        self.assertEqual(first['guide']['fields']['coverage.current']['confirmation'], 'reported_by_user')
        self.assertEqual(first['generated']['status'], 'unavailable')
        self.assertIsNone(first['assessment']['nextQuestion'])
        self.assertNotIn('review', first)
        self.assertEqual(self.flow.turn(self.owner, copy.deepcopy(payload)), first)
        self.assertEqual(len(self.calls), 2)

    def test_partial_journal_recovers_resolved_update_after_composition_profile_error(self):
        text = 'My current health insurance is through my current job.'
        self.extractions.append(self.extraction([self.update('T05', {'choice': 'employer'}, text)]))
        payload = self.payload({'type': 'message', 'message': text})
        with patch.object(self.flow, 'compose_response', side_effect=ProfileError('fictional composition preflight failure')):
            with self.assertRaises(ProfileError):
                self.flow.turn(self.owner, copy.deepcopy(payload))
        recovered = self.take(copy.deepcopy(payload))
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(self.g['fields']['coverage.current']['confirmation'], 'reported_by_user')
        self.assertIsNone(recovered['assessment']['nextQuestion'])
        self.assertNotIn('review', recovered)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.flow.turn_journal[(self.owner, payload['requestId'])]['stage'], 'resolved')
        self.turn({'type': 'refresh'})
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(len(self.calls), 1)

    def test_unavailable_generated_move_recovers_without_losing_resolved_report(self):
        text = 'My current health insurance is through my current job.'
        out = self.message(text, [self.update('T05', {'choice': 'employer'}, text)],
                           compose={'move_id': 'fabricated-enrollment-action'})
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('preparation', out)
        self.assertNotIn('review', out)
        self.assertEqual(len(self.calls), 2)

    def test_extraction_failure_preserves_reports_and_never_calls_composer(self):
        self.task('timing')
        before = fingerprint(self.g, self.r)
        self.extractions.append(TimeoutError('fictional extraction interrupted'))
        with self.assertRaises(ModelUnavailable):
            self.turn({'type': 'message', 'message': 'My current health insurance is through my job.'})
        self.assertEqual(fingerprint(self.g, self.r), before)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.stage_payloads('daylight_resolved_conversation'), [])

    def test_forged_continuation_rejected_before_any_model_request(self):
        self.turn({'type': 'start'})
        payload = self.payload({'type': 'message', 'message': 'What is Medicare?'})
        payload['continuation'] = '0' * 64
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner, payload)
        self.assertEqual(self.calls, [])

    def test_continuation_is_owner_bound(self):
        self.turn({'type': 'start'})
        payload = self.payload({'type': 'refresh'})
        with self.assertRaises(ProfileError):
            self.flow.turn('another-fictional-owner', payload)
        self.assertEqual(self.calls, [])

    def test_ai_transfer_declined_starts_no_model_request(self):
        before = fingerprint(self.g, self.r)
        with self.assertRaises(ProfileError):
            self.turn({'type': 'message', 'message': 'I turn 65 in November.'}, aiConsent=False)
        self.assertEqual(fingerprint(self.g, self.r), before)
        self.assertEqual(self.calls, [])

    def test_future_intended_parts_a_and_b_are_not_actual_enrollment(self):
        text = 'I will have Parts A and B in November 2027.'
        out = self.message(text, [self.update('RC04', {'choice': 'both'}, text, scope='intended')])
        self.assertNotIn('RC04', self.r['facts'])
        self.assertFalse(any(item['id'].startswith('readiness.RC04.')
                             for item in self.composed_context()['reports']))
        self.assertNotIn('review', out)

    def test_orientation_application_progress_is_not_enrollment_or_familiarity(self):
        self.message('I turn 65 in November.', compose={'question_target': 'T02'})
        text = "I haven't applied for Medicare yet; I am just getting started."
        out = self.message(text, [self.update('RC04', {'choice': 'neither'}, text),
                                  self.update('RC04', {'choice': 'pending'}, text),
                                  self.update('T02', {'choice': 'new'}, text)])
        self.assertEqual(self.extracted_context()['activeQuestion']['id'], 'T02')
        self.assertNotIn('RC04', self.r['facts'])
        self.assertNotIn('knowledge.general', self.g['fields'])
        self.assertNotIn('review', out)
        self.assertFalse(any(item['id'].startswith('readiness.RC04.')
                             for item in self.composed_context()['reports']))

    def test_stale_signed_continuation_cannot_replay_old_state_as_new_turn(self):
        self.turn({'type': 'start'})
        stale = self.payload({'type': 'refresh'})
        self.task('timing')
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner, stale)
        self.assertEqual(self.calls, [])

    def test_missing_continuation_cannot_submit_changed_visit_reports(self):
        self.message('I turn 65 in November.')
        payload = self.payload({'type': 'message', 'message': 'What is Medicare?'})
        payload.pop('continuation')
        before = fingerprint(self.g, self.r)
        calls_before = len(self.calls)
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner, payload)
        self.assertEqual(fingerprint(self.g, self.r), before)
        self.assertEqual(len(self.calls), calls_before)

    def test_context_permission_version_controls_actual_outgoing_prior_values(self):
        self.task('timing')
        self.choice('RC01', choice='self')
        self.choice('T04', choice='month', month='April 2027')
        self.choice('T05', choice='employer')
        self.choice('RC09', choice='my_job')
        self.choice('RC11', jobEnd='March 2027', coverageEnd='May 2027')
        self.choice('T06', text='Private Clinic Canary')
        for permission in (None, 'natural-context-v0', CONTEXT_POLICY):
            with self.subTest(permission=permission):
                self.message('Please help with the next detail.', contextPolicy=permission)
                for context in (self.extracted_context(), self.composed_context()):
                    sent = json.dumps(context)
                    self.assertNotIn('Private Clinic Canary', sent)
                    for value in ('2027-04', '2027-03', '2027-05'):
                        if permission == CONTEXT_POLICY:
                            self.assertIn(value, sent)
                        else:
                            self.assertNotIn(value, sent)
                    if permission != CONTEXT_POLICY:
                        self.assertTrue(all(set(item) == {'id', 'status'} for item in context['known']))

    def test_old_context_scope_hides_private_values_echoed_in_question_labels(self):
        self.task('drug_pricing')
        self.choice('RC01', choice='self')
        self.choice('RC03', year='2033')
        self.turn({'type': 'choice', 'id': 'RC22', 'entity': 'medicine-1',
                   'fields': {'name': 'PrivateCanaryMedicine', 'strength': '13 mg', 'form': 'capsule'}})
        self.turn({'type': 'choice', 'id': 'RC23', 'entity': 'medicine-1',
                   'fields': {'quantity': '73'}})
        question = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual(question['id'], 'RC23')
        self.assertIn('PrivateCanaryMedicine', question['question'])
        self.assertIn('73', json.dumps(question['fields']))
        self.message('Please help with the next fill detail.', contextPolicy=None)
        for call in self.calls[-2:]:
            with self.subTest(stage=call['text']['format']['name'], task='drug_pricing'):
                sent = json.dumps(call)
                for private in ('PrivateCanaryMedicine', '13 mg', '73', '2033'):
                    self.assertNotIn(private, sent)
        self.task('timing')
        question = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual(question['id'], 'T04')
        self.assertEqual(self.flow.report(self.r, 'RC03')['year'], '2033')
        self.message('Please help with the next timing detail.', contextPolicy=None)
        for call in self.calls[-2:]:
            with self.subTest(stage=call['text']['format']['name'], task='timing'):
                sent = json.dumps(call)
                for private in ('PrivateCanaryMedicine', '13 mg', '73', '2033'):
                    self.assertNotIn(private, sent)
                self.assertNotIn('knownYear', sent)

    def test_current_structured_form_applies_without_acceptance_or_model_call(self):
        self.task('compare')
        question = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual(question['id'], 'RC01')
        out = self.turn({'type': 'stage', 'id': 'RC01', 'entity': 'profile', 'fields': {'choice': 'self'}}, aiConsent=False, contextPolicy=None)
        self.assertNotIn('review', out)
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        self.assertEqual(self.g['fields']['subject.role']['confirmation'], 'reported_by_user')
        self.assertEqual(self.r['natural']['provenance']['guide.subject.role']['method'], 'structured')
        self.assertEqual(self.calls, [])


class ClarificationLoopTests(unittest.TestCase):
    """Nov 9 fixes: a pending clarification must be satisfiable in the person's own words."""
    setUp = NaturalFlowTests.setUp
    update = staticmethod(NaturalFlowTests.update)
    extraction = staticmethod(NaturalFlowTests.extraction)
    payload = NaturalFlowTests.payload
    take = NaturalFlowTests.take
    turn = NaturalFlowTests.turn
    message = NaturalFlowTests.message
    stage_payloads = NaturalFlowTests.stage_payloads

    @staticmethod
    def situation(kind, text, **value):
        return {'kind': kind, 'subject': 'beneficiary', 'scope': 'current', 'quote': text,
                'uncertain': False, 'correction': False, 'month': value.get('month'),
                'year': value.get('year'), 'status': value.get('status', ''), 'when': value.get('when', '')}

    def test_retired_and_not_working_is_one_consistent_report(self):
        text = 'Retired, and not working anywhere.'
        self.message(text, extraction=self.extraction(
            situation_proposals=[self.situation('retirement', text, status='retired')]))
        self.assertEqual(self.flow.value(self.g, 'situation.retirement'), {'status': 'retired', 'when': ''})
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_mixed_retirement_clauses_still_clarify(self):
        text = 'Retired, but still working part time.'
        self.message(text, extraction=self.extraction(
            situation_proposals=[self.situation('retirement', text, status='retired')]))
        self.assertNotIn('situation.retirement', self.g['fields'])
        self.assertEqual(self.flow.pending_for(self.owner)['update']['id'], 'S_RETIREMENT')

    def test_phrase_answer_to_the_retirement_question_is_accepted(self):
        self.message('I think I am retired.')
        self.assertEqual(self.flow.pending_for(self.owner)['update']['id'], 'S_RETIREMENT')
        # The extractor returns nothing usable; the person's phrase still answers.
        self.message('Yes, retired from civilian work and not working', extraction=self.extraction(situation_proposals=[]))
        self.assertEqual(self.flow.value(self.g, 'situation.retirement'), {'status': 'retired', 'when': ''})
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_bare_yes_confirms_the_tentative_life_report_daylight_asked_about(self):
        out = self.message('I think I am retired.')
        self.assertEqual(self.flow.pending_for(self.owner)['update']['id'], 'S_RETIREMENT')
        self.assertTrue(out['assessment']['nextQuestion']['clarification']['confirmable'])
        self.message('Yes.', extraction=self.extraction(situation_proposals=[]))
        self.assertEqual(self.flow.value(self.g, 'situation.retirement'), {'status': 'retired', 'when': ''})
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_just_those_two_confirms_the_pending_medicine_list(self):
        text = 'I take levothyroxine and atorvastatin, I think that is everything.'
        out = self.message(text, [self.update('T07', {'text': 'levothyroxine and atorvastatin'}, text, uncertain=True)])
        pending = self.flow.pending_for(self.owner)
        self.assertEqual(pending['update']['id'], 'T07')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T07')
        self.assertTrue(out['assessment']['nextQuestion']['clarification']['confirmable'])
        self.message('Just those two.')
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'levothyroxine and atorvastatin')
        self.assertEqual(self.g['fields']['needs.medications']['status'], 'reported')

    def test_a_plain_no_does_not_confirm_a_pending_report(self):
        text = 'I take levothyroxine and atorvastatin, I think that is everything.'
        self.message(text, [self.update('T07', {'text': 'levothyroxine and atorvastatin'}, text, uncertain=True)])
        self.message('No.')
        self.assertIsNotNone(self.flow.pending_for(self.owner))
        self.assertNotEqual(self.g['fields'].get('needs.medications', {}).get('status'), 'reported')

    def test_an_affirmative_with_a_new_report_lets_the_report_win(self):
        text = 'I take levothyroxine and atorvastatin, I think that is everything.'
        self.message(text, [self.update('T07', {'text': 'levothyroxine and atorvastatin'}, text, uncertain=True)])
        reply = 'Yes, those are all of them: levothyroxine, atorvastatin and metformin.'
        self.message(reply, [self.update('T07', {'text': 'levothyroxine, atorvastatin and metformin'}, reply, correction=True)])
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'levothyroxine, atorvastatin and metformin')


class PartAOnlyTests(unittest.TestCase):
    """Nov 9: "Part A only" is a report of the parts held (RC04), told in the person's words."""
    setUp = NaturalFlowTests.setUp
    update = staticmethod(NaturalFlowTests.update)
    extraction = staticmethod(NaturalFlowTests.extraction)
    payload = NaturalFlowTests.payload
    take = NaturalFlowTests.take
    turn = NaturalFlowTests.turn
    message = NaturalFlowTests.message

    def test_part_a_only_in_own_words_records_the_parts_held(self):
        self.message('This is for me.', [self.update('RC01', {'choice': 'self'}, 'This is for me.')])
        self.message('I have Medicare Part A only, not Part B yet.')
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')

    def test_never_signed_up_for_part_b_records_a_only(self):
        self.message('This is for me.', [self.update('RC01', {'choice': 'self'}, 'This is for me.')])
        self.message('I turned 65 last year and never signed up for Part B. Embarrassing, I know.',
                     extraction=self.extraction(situation_proposals=[]))
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')

    def test_a_relatives_parts_are_left_to_the_extractor(self):
        self.message('This is for me.', [self.update('RC01', {'choice': 'self'}, 'This is for me.')])
        self.message('My husband has Part A only.')
        self.assertFalse(self.flow.report(self.r, 'RC04'))

    def test_part_a_only_also_answers_the_coverage_question_as_original_medicare(self):
        found = self.flow.direct_choices('I have Medicare Part A only, not Part B yet.', self.flow.question('T05'), [])
        self.assertEqual([item['fields']['choice'] for item in found], ['original'])
        found = self.flow.direct_choices('Regular Medicare.', self.flow.question('T05'), [])
        self.assertEqual([item['fields']['choice'] for item in found], ['original'])


class PlansPageEntryTests(unittest.TestCase):
    """Nov 9, 2026 (owner): Plans-page entries are the person's reports, saved
    quietly, never chat turns; the next chat reply acknowledges them once and
    asks whether there are others. Several medicines may be added."""
    setUp = NaturalFlowTests.setUp
    update = staticmethod(NaturalFlowTests.update)
    extraction = staticmethod(NaturalFlowTests.extraction)
    payload = NaturalFlowTests.payload
    take = NaturalFlowTests.take
    turn = NaturalFlowTests.turn
    message = NaturalFlowTests.message
    stage_payloads = NaturalFlowTests.stage_payloads
    composed_context = NaturalFlowTests.composed_context

    def plans(self, id, **fields):
        return self.turn({'type': 'choice', 'id': id, 'fields': fields, 'source': 'plans_filter'},
                         aiConsent=False, contextPolicy=None)

    def start(self):
        self.message('This is for me.', [self.update('RC01', {'choice': 'self'}, 'This is for me.')])

    def test_two_medicines_added_on_the_plans_page_both_stay_and_make_no_model_call(self):
        self.start()
        calls = len(self.calls)
        self.plans('T07', text='Eliquis')
        self.plans('T07', text='metformin 500 mg')
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'Eliquis; metformin 500 mg')
        self.assertEqual(self.r['natural']['provenance']['guide.needs.medications']['method'], 'plans_filter')

    def test_several_at_once_and_a_restated_list_do_not_duplicate(self):
        self.start()
        self.plans('T07', text='Eliquis; metformin')
        self.plans('T07', text='metformin; lisinopril 10 mg')
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'Eliquis; metformin; lisinopril 10 mg')

    def test_a_doctor_with_a_comma_is_one_doctor(self):
        self.start()
        self.plans('T06', text='Dr. Maria Lopez, Naples')
        self.plans('T06', text='Naples Heart and Vascular')
        self.assertEqual(self.flow.value(self.g, 'needs.providers'), 'Dr. Maria Lopez, Naples; Naples Heart and Vascular')

    def test_next_chat_reply_acknowledges_once_and_asks_for_others(self):
        self.start()
        self.plans('T07', text='Eliquis')
        self.plans('T07', text='metformin')
        out = self.message('Do any of these plans have a $0 premium?', compose={'reply': 'Several plans on screen list a $0 monthly premium.'})
        sent = self.composed_context()
        self.assertEqual(sent['plans_page_additions']['medicines_added'], ['Eliquis', 'metformin'])
        self.assertIn('take them as given', sent['plans_page_additions']['how_to_use'])
        self.assertTrue(out['reply'].startswith('I see you added Eliquis and metformin on the Plans page'))
        self.assertIn('Several plans on screen', out['reply'])
        candidates = self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertEqual(candidates[0]['id'], 'T07')
        self.assertIn('Besides Eliquis and metformin', candidates[0]['question']['question'])
        out = self.message('What is a deductible?', compose={'reply': 'A deductible is what you pay before the plan starts to pay.'})
        self.assertNotIn('plans_page_additions', self.composed_context())
        self.assertNotIn('Plans page', out['reply'])

    def test_a_reply_that_already_names_the_entries_is_left_as_written(self):
        self.start()
        self.plans('T07', text='Eliquis')
        reply = 'I see you added Eliquis on the Plans page. Coverage for it differs by plan.'
        out = self.message('Which plans cover it?', compose={'reply': reply})
        self.assertEqual(out['reply'].split('\n\n')[0], reply)

    def test_remove_control_reports_only_the_net_removal(self):
        self.start()
        self.plans('T07', text='Eliquis; metformin')
        self.message('Thanks.', compose={'reply': 'Noted.'})
        self.plans('T07', choice='no')
        self.plans('T07', text='metformin')
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'metformin')
        self.message('Okay.', compose={'reply': 'Okay.'})
        additions = self.composed_context()['plans_page_additions']
        self.assertEqual(additions['removed'], ['Eliquis'])
        self.assertEqual(additions['medicines_added'], [])

    def test_also_take_adds_even_when_marked_a_correction(self):
        self.start()
        self.plans('T07', text='Eliquis, metformin')
        more = 'Oh, and I also take atorvastatin.'
        self.message(more, [self.update('T07', {'text': 'atorvastatin'}, 'I also take atorvastatin', correction=True)], compose={'reply': 'Noted.'})
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'Eliquis; metformin; atorvastatin')

    def test_model_acknowledgement_still_gets_any_others_when_another_question_wins(self):
        self.start()
        self.plans('T07', text='Eliquis')
        out = self.message('Is there a deadline?', compose={'reply': 'I see you added Eliquis on the Plans page. The timing depends on your coverage.', 'question_target': None, 'question': ''})
        self.assertIn('Tell me if there are any other medicines to include.', out['reply'])

    def test_a_medicine_named_in_chat_adds_to_the_list(self):
        self.start()
        text = 'I take Eliquis and metformin.'
        self.message(text, [self.update('T07', {'text': 'Eliquis and metformin'}, text)])
        more = 'I also take lisinopril.'
        self.message(more, [self.update('T07', {'text': 'lisinopril'}, more)])
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertEqual(self.flow.value(self.g, 'needs.medications'), 'Eliquis; metformin; lisinopril')


class RetestNov9FlowTests(unittest.TestCase):
    """R1, R3, R5 from the Nov 9 live retest."""
    setUp = NaturalFlowTests.setUp
    update = staticmethod(NaturalFlowTests.update)
    extraction = staticmethod(NaturalFlowTests.extraction)
    payload = NaturalFlowTests.payload
    take = NaturalFlowTests.take
    turn = NaturalFlowTests.turn
    message = NaturalFlowTests.message
    stage_payloads = NaturalFlowTests.stage_payloads
    composed_context = NaturalFlowTests.composed_context

    def start(self):
        self.message('This is for me.', [self.update('RC01', {'choice': 'self'}, 'This is for me.')])

    def test_just_part_a_answers_the_coverage_question_once_parts_are_known(self):
        self.start()
        self.message('I have Medicare Part A only, not Part B yet.')
        self.assertEqual(self.flow.report(self.r, 'RC04').get('choice'), 'a_only')
        current = self.flow.question('T05')
        self.assertIsNotNone(self.flow.part_a_coverage_answer('Yes, still just Part A.', current, [], self.r))
        self.assertIsNone(self.flow.part_a_coverage_answer('Just Part A and COBRA.', current, [], self.r))
        self.assertIsNone(self.flow.part_a_coverage_answer('Is just Part A enough?', current, [], self.r))

    def test_ended_job_coverage_keeps_the_accepted_window_statement_until_r2(self):
        self.start()
        if 'partb_sep_coverage_ended' in self.flow.facts:
            self.skipTest('r2 accepted; the dedicated statement is used')
        selected = [{'rule_id': 'partb_sep_coverage_ended', 'fact_id': 'partb_sep_coverage_ended', 'status': 'met',
                     'applies_because': ['RC11: coverage ended October 2026'], 'confirm_with': [], 'how_to_use': 'State the window.'}]
        with patch('natural_flow.applicable_rules', return_value=selected):
            self.message('What deadline am I about to miss?', compose={'reply': 'There is an 8-month window.'})
        rules = {rule['rule_id']: rule for rule in self.composed_context().get('applicable_rules', [])}
        self.assertEqual(rules['partb_sep_coverage_ended']['fact_id'], 'working_coverage_sep')
        self.assertTrue(rules['partb_sep_coverage_ended']['statement'])

    def test_the_floor_never_repeats_and_never_stands_in_for_an_answer(self):
        self.start()
        first = self.message('Is my buddy right about the VA penalty?', compose=ModelUnavailable('x'))
        second = self.message('So is he right?', compose=ModelUnavailable('x'))
        self.assertIn('I don’t have a checked answer to that question here yet', first['reply'])
        self.assertNotEqual(first['reply'].split('\n\n')[0], 'The sign-up window and coverage start are different; current insurance helps identify the relevant timing questions.')


if __name__ == '__main__':
    unittest.main()
