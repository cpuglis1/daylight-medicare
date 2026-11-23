"""Offline tests for the simulated-person harness. Fictional people, no network, no model."""
import contextlib
import copy
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _paths  # noqa: E402,F401

from sim import graders, run as sim_run  # noqa: E402
from sim.person import (CLEARANCE_PREFIX, ModelPerson, ScriptedPerson, load_profiles, normalise,  # noqa: E402
                        persona_brief)

EVALUATIONS = _paths.REPO / 'docs/evaluations'
PLAN_PATHS = EVALUATIONS / 'plan-paths-2026-11-12/profiles.json'
PERSONAS = EVALUATIONS / 'medicare-personas-2026-11-08/personas.json'
JOURNEYS = EVALUATIONS / 'behavioral-journeys-2026-11-14/profiles.json'
CLEARED = CLEARANCE_PREFIX + ' fictional test of the gate, 10 calls'
TEACHING = 'The harbor ferry leaves from the north dock every morning at dawn.'


def fictional(identifier='SIM1', *, helper=False, opening='Hi, I need help choosing coverage.', states=None):
    """A small fictional profile in the harness's own shape."""
    return normalise({
        'id': identifier, 'opening': opening, **({} if states is None else {'opening_states': list(states)}),
        'typist': 'helper' if helper else 'self', 'relation': 'mother' if helper else '',
        'facts': {
            'who': {'kind': 'choice', 'value': 'someone' if helper else 'self',
                    'say': "It's for my mother." if helper else "It's for me."},
            'zip': {'kind': 'number', 'value': '34102', 'say': 'ZIP 34102.'},
            'age': {'kind': 'number', 'value': '66', 'say': '66 years old.'},
            'cost_preference': {'kind': 'choice', 'value': 'predictable', 'say': 'More predictable costs.'},
            'doctors': {'kind': 'names', 'value': ['avalindqvist'], 'say': 'Dr. Ava Lindqvist.'},
        },
        'answer_key': {'must_cover': ['SECRET-ANSWER-KEY-LINE']},
    })


class FakeFlow:
    """A deterministic stand-in for a conversation: fixed questions, one repeated, answers saved to state."""

    CONTEXT_POLICY = 'fake-context-policy'
    PATHS = {'RC01': 'subject.role', 'T03': 'comparison.scope.zip', 'MG_AGE': 'medigap.ageOn20261110',
             'T09': 'needs.costPreference', 'T06': 'needs.providers'}
    SCRIPT = [
        ('RC01', 'Who is this for?', [['self', 'Me'], ['someone', 'Someone I help']]),
        ('T03', 'What ZIP code do you live in?', []),
        ('MG_AGE', 'How old are you?', []),
        ('T03', 'What ZIP code do you live in?', []),                     # asked again after the answer
        ('T09', 'How would you prefer to balance monthly payments and costs when you get care?',
         [['lower_monthly', 'Lower monthly payments'], ['predictable', 'More predictable costs']]),
        ('T06', 'Are there doctors or hospitals you want to keep?', [['none', 'No doctors to include']]),
    ]

    def __init__(self, *, wrong=('MG_AGE',), drop=('T06',), teach_at=(1, 4), silent_at=(2,), fact_ids=True,
                 flaky=False, forbidden_at=None):
        self.wrong, self.drop, self.teach_at, self.silent_at = set(wrong), set(drop), set(teach_at), set(silent_at)
        self.fact_ids, self.flaky, self.forbidden_at = fact_ids, flaky, forbidden_at
        self.issued = {}
        self.payloads = []

    def initial(self):
        return {'fields': {}}, {'facts': {}, 'fake': {'step': 0, 'asked': None}}

    def _save(self, guide, record, identifier, message):
        if identifier is None or identifier in self.drop or "don't know" in message.lower():
            return
        choices = next(item[2] for item in self.SCRIPT if item[0] == identifier)
        if choices:
            value = next((key for key, label in choices if message.lower().startswith(label.lower())), None)
        elif identifier == 'T03':
            found = re.search(r'\b\d{5}\b', message)
            value = found.group(0) if found else None
            if self.flaky and 'Also:' in message:
                record['fake']['lost_zip'] = True                        # a long answer loses the ZIP for good
            if record['fake'].get('lost_zip'):
                value = None
        elif identifier == 'MG_AGE':
            found = re.search(r'\b(\d{2,3})\b', message)
            value = int(found.group(1)) + (1 if identifier in self.wrong else 0) if found else None
        else:
            value = message
        if value is None:
            return
        guide['fields'][self.PATHS[identifier]] = {'value': value, 'status': 'reported'}
        if identifier == 'RC01':
            record['facts']['RC01'] = {'value': {'choice': value}, 'stale': False}

    def turn(self, owner, payload):
        allowed = {'guide', 'record', 'action', 'requestId', 'aiConsent', 'contextPolicy', 'continuation'}
        if set(payload) - allowed or payload.get('contextPolicy') != self.CONTEXT_POLICY:
            raise ValueError('bad payload')
        if payload.get('continuation') != self.issued.get(owner):
            raise ValueError('stale continuation')
        self.payloads.append(payload)
        guide, record = copy.deepcopy(payload['guide']), copy.deepcopy(payload['record'])
        token = 'c%d' % len(self.payloads)
        self.issued[owner] = token
        out = {'guide': guide, 'record': record, 'continuation': token, 'reply': '',
               'assessment': {'nextQuestion': None}, 'planReadiness': {'canReview': False},
               'metrics': {'llmCalls': 0}, 'advisor': {'teachingFactIds': []}, 'facts': []}
        action = payload['action']
        if action['type'] != 'message':
            return out
        if payload.get('aiConsent') is not True:
            raise ValueError('typed messages need consent')
        state = record['fake']
        message = action['message']
        if state['step'] == 0:
            found = re.search(r'\b\d{5}\b', message)                     # an opening may already give the ZIP
            if found:
                guide['fields'][self.PATHS['T03']] = {'value': found.group(0), 'status': 'reported'}
        self._save(guide, record, state['asked'], message)
        step = state['step']
        out['metrics'] = {'llmCalls': 2}
        out['generated'] = {'status': 'complete'}
        if step < len(self.SCRIPT):
            identifier, text, choices = self.SCRIPT[step]
            out['assessment']['nextQuestion'] = {'id': identifier, 'question': text, 'why': '', 'choices': choices, 'fields': []}
            out['conversationNext'] = {'kind': 'profile_question', 'target': identifier}
            out['reply'] = '' if step in self.silent_at else 'Thanks, that helps.'
            if step in self.teach_at:
                out['reply'] = 'Thanks, that helps. ' + TEACHING
                if self.fact_ids:
                    out['advisor']['teachingFactIds'] = ['F-FERRY']
            if step == self.forbidden_at:
                out['reply'] = ("I'd recommend the Harbor Advantage plan for you. It costs $999 a month. "
                                'It starts on March 3, 2031. What is your Medicare number?')
            state['asked'] = identifier
        else:
            out['planReadiness'] = {'canReview': True}
            out['conversationNext'] = {'kind': 'action', 'action': 'plan_review'}
            out['cards'] = [{'kind': 'plans_ready', 'title': 'See plans', 'premium': '$25', 'starts': '2026-12-01'}]
            out['reply'] = 'Your plans are ready to review. The sample premium on the card is $25, starting December 1, 2026.'
            state['asked'] = None
        state['step'] = step + 1
        return out


def make_fake_flow():
    return FakeFlow()


def scripted(profile, seed=0):
    return ScriptedPerson(profile, seed=seed, style='terse')


class TickClock:
    """A clock whose turns take 0.5 s, except the third, which takes 2 s."""

    def __init__(self):
        self.now, self.calls = 0.0, 0

    def __call__(self):
        self.calls += 1
        if self.calls % 2 == 0:
            self.now += 2.0 if self.calls == 6 else 0.5
        return self.now


def patterns_only():
    return patch.object(graders, '_check_reply', lambda: None)


class LoadProfiles(unittest.TestCase):
    def test_all_three_real_sets_load_into_one_shape(self):
        for path, count, prefix in ((PLAN_PATHS, 16, 'PP'), (PERSONAS, 20, 'P'), (JOURNEYS, 12, 'BJ')):
            profiles = load_profiles(path)
            self.assertEqual(len(profiles), count)
            for profile in profiles:
                self.assertTrue(profile['id'].startswith(prefix))
                self.assertTrue(profile['opening'].strip())
                self.assertIn(profile['typist'], ('self', 'helper'))
                self.assertIn('who', profile['facts'])
                self.assertIn('max_messages', profile['stop'])
                for fact in profile['facts'].values():
                    self.assertTrue(fact['say'].strip())
                    self.assertIn(fact['kind'], ('choice', 'multi', 'subset', 'names', 'number', 'month_year'))

    def test_a_folder_path_loads_too(self):
        self.assertEqual(len(load_profiles(JOURNEYS.parent)), 12)

    def test_helpers_stop_rules_and_structured_facts(self):
        plan_paths = {p['id']: p for p in load_profiles(PLAN_PATHS)}
        self.assertEqual([i for i, p in plan_paths.items() if p['typist'] == 'helper'], ['PP05', 'PP15'])
        self.assertEqual(plan_paths['PP01']['stop']['max_messages'], 9)
        self.assertEqual(plan_paths['PP01']['facts']['zip']['value'], '34104')
        self.assertEqual(plan_paths['PP05']['facts']['who']['value'], 'someone')
        self.assertEqual(plan_paths['PP05']['facts']['tobacco']['value'], 'yes')
        self.assertEqual(plan_paths['PP08']['facts']['medicines']['value'], [])
        self.assertEqual(plan_paths['PP04']['facts']['coverage']['value'], ['original', 'drug'])
        self.assertEqual(sum(1 for entry in plan_paths['PP01']['script'] if entry['unprompted']), 3)
        personas = {p['id']: p for p in load_profiles(PERSONAS)}
        self.assertEqual(personas['P16']['typist'], 'helper')
        self.assertEqual(personas['P01']['facts']['parts']['value'], 'neither')
        journeys = {p['id']: p for p in load_profiles(JOURNEYS)}
        self.assertEqual(journeys['BJ06']['typist'], 'helper')
        self.assertEqual(journeys['BJ02']['facts']['zip']['value'], '34102')        # the corrected ZIP
        self.assertTrue(journeys['BJ09']['facts']['zip'].get('declined'))
        self.assertEqual(journeys['BJ01']['stop'], {'max_messages': 40, 'repeat_limit': 2, 'text': ''})
        self.assertTrue(journeys['BJ01']['skipped_beats'])                          # screen actions are not typed


class ScriptedPersonTests(unittest.TestCase):
    def question(self, identifier):
        return next({'id': i, 'question': t, 'choices': c, 'fields': []} for i, t, c in FakeFlow.SCRIPT if i == identifier)

    def test_answers_the_question_asked_not_the_next_script_line(self):
        person = ScriptedPerson(fictional(), style='terse')
        person.opening()
        self.assertEqual(person.answer('', self.question('T09')), 'More predictable costs')
        self.assertEqual(person.last, {'kind': 'answer', 'stated': ['cost_preference'], 'answered': 'T09'})
        self.assertEqual(person.answer('', self.question('RC01')), 'Me')
        self.assertEqual(person.answer('', self.question('T03')), 'ZIP 34102.')
        self.assertEqual(person.answer('', self.question('T06')), 'Dr. Ava Lindqvist.')

    def test_one_call_question_shape_and_choice_for_none(self):
        profile = fictional()
        profile['facts']['doctors'] = {'kind': 'names', 'value': [], 'say': 'No doctors I need to keep.'}
        person = ScriptedPerson(profile, style='terse')
        self.assertEqual(person.answer('', {'target': 'T03', 'text': 'Where do you live?'}), 'ZIP 34102.')
        self.assertEqual(person.answer('', self.question('T06')), 'No doctors to include')

    def test_unknown_fact_unclear_question_and_declined(self):
        profile = fictional()
        profile['facts']['age'] = {'kind': 'number', 'value': None, 'say': "I'd rather not say.", 'declined': True}
        person = ScriptedPerson(profile, style='terse')
        self.assertEqual(person.answer('', {'id': 'RC14', 'question': 'Are you adding money to an HSA?', 'choices': []}),
                         "I don't know.")
        self.assertEqual(person.last['kind'], 'unknown')
        self.assertEqual(person.answer('', {'id': 'T01', 'question': 'What would you like help with?',
                                            'choices': [['learn', 'Understand Medicare']]}),
                         'Hi, I need help choosing coverage.')
        self.assertEqual(person.last['stated'], ['goal'])
        self.assertIn('not sure what you', person.answer('', 'Shall we carry on with the next step then?'))
        self.assertEqual(person.last['kind'], 'unclear')
        self.assertEqual(person.answer('', self.question('MG_AGE')), "I'd rather not say.")
        self.assertEqual(person.answer('', 'What is your home zip code?'), 'ZIP 34102.')   # no id: falls back to words

    def test_styles_differ_and_repeat_exactly_for_a_seed(self):
        def transcript(seed):
            person = ScriptedPerson(fictional(), seed=seed)
            said = [person.opening()]
            for identifier in ('RC01', 'T03', 'MG_AGE', 'T09', 'T06'):
                said.append(person.answer('', self.question(identifier)))
            return person.style, said
        runs = [transcript(seed) for seed in (0, 1, 2)]
        self.assertEqual([style for style, _ in runs], ['terse', 'talkative', 'unsure'])
        self.assertEqual(runs, [transcript(seed) for seed in (0, 1, 2)])
        self.assertEqual(len({json.dumps(said) for _, said in runs}), 3)
        talkative = ScriptedPerson(fictional(), seed=1)
        text = talkative.answer('', self.question('T03'))
        self.assertIn('Also:', text)
        self.assertEqual(len(talkative.last['stated']), 2)                 # the ZIP and one volunteered fact
        unsure = ScriptedPerson(fictional(), style='unsure', seed=5)
        answers = [unsure.answer('', self.question('T03')) for _ in range(30)]
        self.assertIn("I don't know.", answers)
        self.assertIn('ZIP 34102.', answers)

    def test_real_profile_sends_its_own_questions_and_stops_at_its_limit(self):
        profile = next(p for p in load_profiles(PLAN_PATHS) if p['id'] == 'PP08')
        person = ScriptedPerson(profile, style='terse', max_messages=profile['stop']['max_messages'])
        said = [person.opening()]
        while True:
            text = person.answer('Okay.', {'id': 'T03', 'question': 'What ZIP code do you live in?', 'choices': []})
            if text is None:
                break
            said.append(text)
        self.assertEqual(len(said), 8)
        unprompted = [entry['reply'] for entry in profile['script'] if entry['unprompted']]
        self.assertEqual(said[-len(unprompted):], unprompted)              # the teach-back is last
        self.assertIn('ZIP 34105.', said)

    def test_stops_when_nothing_is_asked_twice(self):
        person = ScriptedPerson(fictional(), style='terse')
        person.opening()
        self.assertIn('still there', person.answer('', None))
        self.assertIsNone(person.answer('', None))


class RunAndGrade(unittest.TestCase):
    def one(self, profile=None, flow=None, person=scripted, **kwargs):
        profile = profile or fictional()
        flow = flow or FakeFlow()
        result = sim_run.run(lambda: flow, person, [profile], clock=TickClock(), **kwargs)
        return result['runs'][0], profile, flow

    def test_run_records_each_turn_and_round_trips_state(self):
        run, _, flow = self.one()
        self.assertEqual(run['end'], 'plans_handoff')
        self.assertEqual(len(run['turns']), 7)
        self.assertEqual(flow.payloads[0]['action'], {'type': 'start'})
        self.assertFalse(flow.payloads[0]['aiConsent'])
        self.assertTrue(all(p['aiConsent'] is True for p in flow.payloads[1:]))
        self.assertEqual([t['question']['id'] if t['question'] else None for t in run['turns']],
                         ['RC01', 'T03', 'MG_AGE', 'T03', 'T09', 'T06', None])
        self.assertEqual([t['person'] for t in run['turns']][1:4], ['Me', 'ZIP 34102.', '66 years old.'])
        last = run['turns'][-1]
        self.assertEqual(last['cards'], ['plans_ready'])
        self.assertEqual(last['generated'], 'complete')
        self.assertEqual(last['model_requests'], 2)
        self.assertTrue(last['can_review'])
        self.assertEqual(run['turns'][1]['fact_ids'], ['F-FERRY'])
        self.assertEqual(run['final']['values']['comparison.scope.zip'], '34102')
        self.assertEqual(run['final']['states']['T03'], 'reported')
        self.assertEqual(run['final']['guide']['fields']['subject.role']['value'], 'self')
        self.assertIn('T03', run['turns'][2]['reported'])

    def test_grades_match_the_known_answers(self):
        run, profile, _ = self.one()
        with patterns_only():
            grade = graders.grade(run, profile)
        accuracy = grade['profile_accuracy']
        self.assertEqual((accuracy['stated'], accuracy['graded'], accuracy['correct']), (5, 5, 3))
        self.assertEqual(accuracy['share'], 0.6)
        self.assertEqual(accuracy['wrong'], ['age'])                        # saved as 67
        self.assertEqual(accuracy['missed'], ['doctors'])                   # never saved
        self.assertEqual(grade['repeated_questions']['count'], 1)
        self.assertEqual(grade['repeated_questions']['after_answer'], [{'turn': 4, 'id': 'T03', 'answered_at': 3}])
        self.assertEqual(grade['repeated_teaching'], {
            'count': 1, 'basis': 'fact_ids', 'fact_ids': [{'fact_id': 'F-FERRY', 'turns': [2, 5]}],
            'sentences': grade['repeated_teaching']['sentences']})
        self.assertEqual(grade['turns_to_plans'], 7)
        self.assertEqual(grade['no_answer_turns'],
                         {'count': 1, 'turns': [3], 'nothing_at_all': [], 'after_i_dont_know': []})
        self.assertEqual(grade['finish'], {'reached': True, 'kind': 'plans_handoff'})
        self.assertEqual(grade['wrong_person'], {'applies': False, 'count': 0, 'turns': []})
        self.assertEqual(grade['seconds'], {'median': 0.5, 'max': 2.0})
        self.assertEqual(grade['model_requests'], 14)
        self.assertIsNone(grade['rejected_replies'])
        self.assertEqual(grade['forbidden']['personal_pick'] + grade['forbidden']['identifier_request']
                         + grade['forbidden']['ungrounded'], 0)             # the $25 and the date are on the card

    def test_repeated_teaching_falls_back_to_sentences(self):
        run, profile, _ = self.one(flow=FakeFlow(fact_ids=False))
        teaching = graders.repeated_teaching(run)
        self.assertEqual((teaching['count'], teaching['basis']), (1, 'sentences'))
        self.assertEqual(teaching['sentences'][0]['turns'], [2, 5])

    def test_question_asked_while_its_answer_is_already_saved(self):
        profile = fictional(opening='Hi, I live in 34102 and need help choosing coverage.')
        run, profile, _ = self.one(profile=profile)
        repeated = graders.repeated_questions(run)
        self.assertEqual(repeated['while_saved'], [{'turn': 2, 'id': 'T03'}])
        self.assertEqual(len(repeated['after_answer']), 1)
        self.assertEqual(repeated['count'], 2)
        self.assertIn('zip', run['turns'][0]['stated'])                     # the literal ZIP in the opening

    def test_helper_addressed_as_the_covered_person(self):
        run, profile, _ = self.one(profile=fictional(helper=True))
        self.assertEqual(run['turns'][1]['person'], 'Someone I help')
        grade = graders.grade(run, profile)
        self.assertEqual(grade['wrong_person'], {'applies': True, 'count': 1, 'turns': [3]})   # "How old are you?"
        self.assertIn('who', grade['profile_accuracy']['correct_fields'])

    def test_forbidden_content_patterns(self):
        run, profile, _ = self.one(flow=FakeFlow(forbidden_at=1, teach_at=()))
        with patterns_only():
            found = graders.forbidden(run)
        self.assertEqual(found['method'], 'patterns')
        self.assertEqual((found['personal_pick'], found['identifier_request'], found['ungrounded_amount'],
                          found['ungrounded_date']), (1, 1, 1, 1))
        self.assertEqual({item['turn'] for item in found['details']}, {2})

    def test_forbidden_content_uses_the_real_check_when_it_imports(self):
        if graders._check_reply() is None:
            self.skipTest('one_call_check is not importable here')
        run, profile, _ = self.one(flow=FakeFlow(forbidden_at=1, teach_at=()))
        found = graders.forbidden(run)
        self.assertEqual(found['method'], 'one_call_check')
        self.assertEqual((found['personal_pick'], found['identifier_request'], found['ungrounded_amount'],
                          found['ungrounded_date']), (1, 1, 1, 1))
        clean, _, _ = self.one()
        self.assertEqual(graders.forbidden(clean)['details'], [])

    def test_negated_and_grounded_wording_is_not_counted(self):
        text = ("I can't recommend a plan. Please don't share your Medicare number here. "
                'You said about $38,000 a year and that you turn 65 on December 14.')
        grounding = 'I make $38,000 and I turn 65 on December 14.'
        self.assertEqual(graders._pattern_findings(text, grounding), [])
        self.assertEqual(graders._pattern_findings('The premium is $41.50 from January 2027.', grounding),
                         ['ungrounded_amount', 'ungrounded_date'])

    def test_max_turns_person_stop_and_errors(self):
        run, profile, _ = self.one(max_turns=3)
        self.assertEqual((run['end'], len(run['turns'])), ('max_turns', 3))
        grade = graders.grade(run, profile)
        self.assertEqual(grade['finish'], {'reached': False, 'kind': 'max_turns'})
        self.assertIsNone(grade['turns_to_plans'])
        run, _, _ = self.one(person=lambda profile, seed=0: ScriptedPerson(profile, seed=seed, style='terse', max_messages=2))
        self.assertEqual((run['end'], len(run['turns'])), ('person_stopped', 2))

        class Broken(FakeFlow):
            def turn(self, owner, payload):
                if payload['action']['type'] == 'message':
                    raise RuntimeError('private words must not be recorded')
                return super().turn(owner, payload)
        run, profile, _ = self.one(flow=Broken())
        self.assertEqual(run['end'], 'error')
        self.assertEqual(run['turns'][0]['error'], {'type': 'RuntimeError', 'status': None})
        self.assertEqual(graders.grade(run, profile)['no_answer_turns']['count'], 2)

    def test_variance_across_seeds_is_reported(self):
        profile = fictional()

        def by_seed(profile, seed=0):
            return ScriptedPerson(profile, seed=seed, style=('terse', 'talkative')[seed])
        steady = sim_run.run(FakeFlow, scripted, [profile], runs=2)
        flaky = sim_run.run(lambda: FakeFlow(flaky=True), by_seed, [profile], runs=2)
        with patterns_only():
            steady_summary = graders.summary([graders.grade(one, profile) for one in steady['runs']])
            flaky_grades = [graders.grade(one, profile) for one in flaky['runs']]
            flaky_summary = graders.summary(flaky_grades)
        item = steady_summary['variance']['per_profile']['SIM1']
        self.assertEqual((item['runs'], item['distinct_saved_profiles'], item['consistent']), (2, 1, True))
        self.assertEqual(steady_summary['variance']['inconsistent_profiles'], [])
        self.assertEqual(steady_summary['profile_accuracy']['mean'], 0.6)
        self.assertEqual(steady_summary['turns_to_plans'], {'reached': 2, 'not_reached': 0, 'median': 7})
        self.assertEqual(steady_summary['finish'], {'recognised': 2, 'by_kind': {'plans_handoff': 2}})
        self.assertEqual(steady_summary['repeated_questions']['total'], 2)
        item = flaky_summary['variance']['per_profile']['SIM1']
        self.assertEqual(item['distinct_saved_profiles'], 2)
        self.assertIn('zip', item['differing_fields_same_statements'])     # said in both runs, saved in one
        self.assertFalse(item['consistent'])
        self.assertEqual(flaky_summary['variance']['inconsistent_profiles'], ['SIM1'])
        self.assertNotEqual(flaky_grades[0]['profile_accuracy']['share'], flaky_grades[1]['profile_accuracy']['share'])

    def test_a_fact_the_person_withheld_in_one_run_is_not_blamed_on_the_loop(self):
        profile = fictional()

        class Quiet(ScriptedPerson):
            def answer(self, reply_text, question):
                if self.seed == 1 and (question or {}).get('id') == 'T09':
                    return self._send("I don't know.", 'unknown', [], 'T09')
                return super().answer(reply_text, question)
        result = sim_run.run(FakeFlow, lambda profile, seed=0: Quiet(profile, seed=seed, style='terse'), [profile], runs=2)
        with patterns_only():
            summary = graders.summary([graders.grade(one, profile) for one in result['runs']])
        item = summary['variance']['per_profile']['SIM1']
        self.assertEqual(item['differing_fields_person_varied'], ['cost_preference'])
        self.assertEqual(item['differing_fields_same_statements'], [])
        self.assertTrue(item['consistent'])


class FakeClient:
    model = 'fictional-model'

    def __init__(self, replies):
        self.replies, self.payloads = list(replies), []

    def transport(self, payload):
        self.payloads.append(payload)
        value = self.replies.pop(0)
        text = value if isinstance(value, str) else json.dumps(value)
        return {'output': [{'content': [{'type': 'output_text', 'text': text}]}]}


class ModelPersonTests(unittest.TestCase):
    def test_refused_without_the_owners_clearance(self):
        client = FakeClient([])
        for clearance in (None, '', 'yes', 'cleared by an agent', CLEARANCE_PREFIX, CLEARANCE_PREFIX + ' ok'):
            with self.assertRaises(PermissionError) as refused:
                ModelPerson(fictional(), client, **({} if clearance is None else {'clearance': clearance}))
            self.assertIn("owner's clearance and a budget", str(refused.exception))
        self.assertEqual(client.payloads, [])

    def test_needs_an_injected_transport_and_a_call_limit(self):
        with self.assertRaises(ValueError):
            ModelPerson(fictional(), object(), clearance=CLEARED)
        with self.assertRaises(ValueError):
            ModelPerson(fictional(), FakeClient([]), clearance=CLEARED, max_calls=0)

    def test_prompt_and_call_path_through_a_fake_transport(self):
        profile = next(p for p in load_profiles(PLAN_PATHS) if p['id'] == 'PP01')
        client = FakeClient([{'message': 'I live in 34104.', 'stated': ['zip', 'not_a_fact'], 'stop': False},
                             {'message': '', 'stated': [], 'stop': True}])
        person = ModelPerson(profile, client, clearance=CLEARED)
        self.assertEqual(person.opening(), profile['opening'])
        self.assertEqual(client.payloads, [])                               # the opening costs no call
        text = person.answer('Glad to help.', {'id': 'T03', 'question': 'What ZIP code do you live in?', 'choices': []})
        self.assertEqual(text, 'I live in 34104.')
        self.assertEqual(person.last, {'kind': 'answer', 'stated': ['zip'], 'answered': 'T03'})
        payload = client.payloads[0]
        self.assertEqual((payload['model'], payload['store'], payload['tools']), ('fictional-model', False, []))
        self.assertEqual(payload['text']['format']['name'], 'daylight_sim_person')
        sent = json.loads(payload['input'][0]['content'])
        self.assertEqual(sent['advisor_question']['id'], 'T03')
        self.assertEqual(sent['persona']['facts']['zip'], 'ZIP 34104.')
        self.assertEqual(sent['transcript'][0], {'role': 'person', 'text': profile['opening']})
        whole = json.dumps(payload)
        for secret in (*profile['answer_key']['must_cover'], *profile['answer_key']['must_not_claim'], profile['answer_key']['trap']):
            self.assertNotIn(json.dumps(secret)[1:-1], whole)
        self.assertNotIn('answer_key', whole)
        self.assertIsNone(person.answer('Anything else?', None))            # the model chose to stop
        self.assertEqual(person.calls, 2)

    def test_brief_leaves_out_the_answer_key(self):
        self.assertNotIn('SECRET-ANSWER-KEY-LINE', json.dumps(persona_brief(fictional())))

    def test_call_limit_and_malformed_output(self):
        person = ModelPerson(fictional(), FakeClient(['not json']), clearance=CLEARED)
        person.opening()
        with self.assertRaises(RuntimeError) as failure:
            person.answer('Hello.', None)
        self.assertEqual(str(failure.exception), 'person_model_format')
        client = FakeClient([{'message': 'One.', 'stated': [], 'stop': False}])
        person = ModelPerson(fictional(), client, clearance=CLEARED, max_calls=1)
        self.assertEqual(person.answer('Hello.', None), 'One.')
        self.assertIsNone(person.answer('Hello again.', None))
        self.assertEqual(len(client.payloads), 1)


FACTORY_CALLS = []


def recording_factory():
    FACTORY_CALLS.append(1)
    return FakeFlow()


class CommandLine(unittest.TestCase):
    HERE = str(Path(__file__).resolve())

    def call(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sim_run.main(['--profiles', str(self.profiles), '--loop', 'two-call', '--out', str(self.out), *extra])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.profiles = Path(self.folder.name) / 'profiles.json'
        self.profiles.write_text(json.dumps([fictional('SIM1'), fictional('SIM2', helper=True)]))
        self.out = Path(self.folder.name) / 'out'
        del FACTORY_CALLS[:]

    def test_refuses_to_start_without_an_offline_model_or_a_cleared_live_run(self):
        code, out, err = self.call()
        self.assertEqual(code, 2)
        self.assertIn('Refusing to start', err)
        self.assertFalse(self.out.exists())

    def test_refuses_a_live_run_without_clearance(self):
        factory = self.HERE + ':recording_factory'
        for extra in (('--live',), ('--live', '--clearance', 'go ahead'), ('--live', '--max-calls', '500')):
            code, out, err = self.call('--flow-factory', factory, *extra)
            self.assertEqual(code, 2)
            self.assertIn("owner's clearance", err)
            self.assertNotIn('Estimated model calls', out)
        self.assertFalse(self.out.exists())

    def test_live_prints_the_estimate_first_and_still_needs_a_budget_and_a_flow(self):
        code, out, err = self.call('--live', '--clearance', CLEARED, '--runs', '3')
        self.assertEqual(code, 2)
        self.assertIn('Estimated model calls: about 144 at 12 turns a conversation, at most 720', out)
        self.assertIn('--max-calls', err)
        code, out, err = self.call('--live', '--clearance', CLEARED, '--max-calls', '50')
        self.assertEqual(code, 2)
        self.assertIn('--flow-factory', err)
        code, out, err = self.call('--live', '--clearance', CLEARED, '--max-calls', '50', '--scripted-model', 'x:y')
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())

    def test_live_options_without_live_are_refused(self):
        factory = self.HERE + ':recording_factory'
        for extra in (('--clearance', CLEARED), ('--max-calls', '10'), ('--person', 'model')):
            code, _, err = self.call('--flow-factory', factory, *extra)
            self.assertEqual(code, 2)
        self.assertEqual(FACTORY_CALLS, [])

    def test_offline_run_writes_a_file_per_run_and_a_summary(self):
        code, out, err = self.call('--flow-factory', self.HERE + ':make_fake_flow', '--runs', '2')
        self.assertEqual((code, err), (0, ''))
        self.assertNotIn('34102', out)                                      # progress lines carry no content
        names = sorted(path.name for path in self.out.iterdir())
        self.assertEqual(names, ['SIM1-run0.json', 'SIM1-run1.json', 'SIM2-run0.json', 'SIM2-run1.json',
                                 'summary.json', 'summary.md'])
        saved = json.loads((self.out / 'SIM2-run0.json').read_text())
        self.assertEqual((saved['loop'], saved['live'], saved['run']['typist']), ('two-call', False, 'helper'))
        self.assertIn('profile_accuracy', saved['grade'])
        table = (self.out / 'summary.md').read_text()
        self.assertIn('| SIM1 | 0 | terse |', table)
        self.assertIn('offline', table)
        summary = json.loads((self.out / 'summary.json').read_text())
        self.assertEqual((summary['summary']['runs'], summary['summary']['profiles']), (4, 2))
        self.assertIsNone(summary['clearance'])

    def test_offline_runs_block_the_network(self):
        import socket
        with sim_run.offline_network():
            with self.assertRaises(AssertionError):
                socket.create_connection(('192.0.2.1', 9))

    def test_call_limit_stops_a_cleared_run_before_it_overspends(self):
        counter = {'used': 0, 'limit': 7}
        result = sim_run.run(lambda: sim_run.LimitedFlow(FakeFlow(), counter, 3), scripted, [fictional()])
        run = result['runs'][0]
        self.assertEqual(run['end'], 'call_limit')
        self.assertEqual(len(run['turns']), 3)                               # 6 used; a fourth turn could reach 9
        self.assertEqual(counter['used'], 6)

    def test_estimate(self):
        estimate = sim_run.estimate_calls(16, 3, 'one-call', max_turns=40, model_person=True)
        self.assertEqual(estimate['conversations'], 48)
        self.assertEqual(estimate['calls_per_turn'], [3, 4])
        self.assertEqual((estimate['total_typical'], estimate['total_max']), (48 * 3 * 12, 48 * 4 * 40))


def advisor_ready():
    """The advisor's comparison contract needs local metadata that `tools/prepare_advisor.py` writes."""
    try:
        import comparison_profile
        comparison_profile._load_contract()
        return True
    except Exception:
        return False


class RealTwoCallFlow(unittest.TestCase):
    @unittest.skipUnless(advisor_ready(), 'advisor-first metadata is not prepared in this checkout (tools/prepare_advisor.py)')
    def test_two_typed_turns_through_the_real_conversation_with_a_scripted_model(self):
        stages = []

        def transport(payload):
            name = payload['text']['format']['name']
            sent = json.loads(payload['input'][0]['content'])
            stages.append(name)
            if name == 'daylight_guide_commands':
                first = stages.count(name) == 1
                updates = [{'id': identifier, 'entity': 'profile', 'subject': 'beneficiary', 'scope': 'current',
                            'uncertain': False, 'correction': False, 'quote': PROFILE['opening'],
                            'fields': [{'key': key, 'value': value}]}
                           for identifier, key, value in (('RC01', 'choice', 'self'), ('T03', 'zip', '34102'))] if first else []
                value = {'updates': updates, 'requests': [], 'fact_ids': [],
                         'agenda': {'concerns': [], 'priorityReason': {}}, 'situation_proposals': [], 'goal_quote': '',
                         'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''}}
            else:
                candidates = sent.get('question_candidates', [])
                target = candidates[0]['id'] if candidates else None
                question = (candidates[0].get('question') or {}) if candidates else {}
                value = {'question_target': target, 'reply': 'We can work through the next useful detail together.',
                         'question': question.get('question', '') if target else '', 'report_refs': [],
                         'evidence_refs': [], 'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                         'agenda_update': {'current_concern': '', 'pause': False}, 'education_followups': []}
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}

        PROFILE = fictional(opening='This is for me. I live in 34102.', states=('who', 'zip'))
        PROFILE['facts']['birth'] = {'kind': 'month_year', 'value': {'year': 1960, 'month': 2},
                                     'say': 'Born in February 1960.'}
        with sim_run.offline_network():
            result = sim_run.run(lambda: sim_run.scripted_flow('two-call', transport), scripted, [PROFILE], max_turns=2)
        run = result['runs'][0]
        self.assertIsNone(run['start_error'])
        self.assertEqual(len(run['turns']), 2)
        self.assertEqual([turn['error'] for turn in run['turns']], [None, None])
        self.assertEqual([turn['model_requests'] for turn in run['turns']], [2, 2])
        self.assertEqual(stages, ['daylight_guide_commands', 'daylight_resolved_conversation'] * 2)
        self.assertTrue(run['turns'][0]['question']['id'])
        self.assertEqual(run['turns'][0]['generated'], 'complete')
        self.assertEqual(run['final']['values']['comparison.scope.zip'], '34102')
        self.assertEqual(run['final']['states']['RC01'], 'reported')
        accuracy = graders.grade(run, PROFILE)['profile_accuracy']
        # The scripted model saved the two opening facts and ignored the birth month said in turn two.
        self.assertEqual(run['turns'][1]['person'], 'Born in February 1960.')
        self.assertEqual((accuracy['graded'], accuracy['correct'], accuracy['missed'], accuracy['wrong']), (3, 2, ['birth'], []))


if __name__ == '__main__':
    unittest.main()
