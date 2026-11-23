"""one_call_tools: schemas, the field catalog and the runner over the real advisor-first flow.

Offline: the scripted transport fails the test if a model is called and sockets
are forbidden. Every person, doctor, insurer and date here is fictional. These
tests check software behavior; they say nothing about a live model's reading.
"""
import copy
from datetime import date
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths

from chat import ResponsesClient
from guest_profiles import ProfileError
from natural_flow import NaturalConversation
import conversation_planner
import conversation_records
import enrollment_flow
import one_call_tools as tools

TODAY = date(2026, 11, 21)
ADVISOR = _paths.ADVISOR


def _contract_available():
    """advisor-first's plan views read a sealed profile contract whose sources may be absent in a checkout."""
    try:
        import comparison_profile
        comparison_profile._load_contract()
        return True
    except Exception:
        return False


CONTRACT = _contract_available()
NEEDS_CONTRACT = 'advisor-first profile contract sources are not present in this checkout'


def make_flow():
    def transport(payload):
        raise AssertionError('one_call_tools must never call a model')
    flow = NaturalConversation(None, None,
        json.loads((ADVISOR / 'web/guide-contract.json').read_text()),
        json.loads((ADVISOR / 'web/teaching-facts.json').read_text()),
        json.loads((ADVISOR / 'web/readiness-content.json').read_text()),
        ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport),
        True, None, fixture=False)
    # The :8895 configuration the variant builds on: Parts A and B fields, planner and records.
    enrollment_flow.enable(flow)
    conversation_planner.enable(flow)
    conversation_records.enable(flow)
    conversation_records.enable_pending(flow)
    conversation_records.enable_fixes(flow)
    return flow


def update(identifier, fields, quote, **extra):
    return {'id': identifier, 'entity': None,
            'fields': [{'key': key, 'value': value} for key, value in fields.items()],
            'quote': quote, 'subject': 'beneficiary', 'scope': 'current',
            'uncertain': False, 'correction': False, **extra}


class Base(unittest.TestCase):
    def setUp(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('network access is forbidden in these tests')
        for target in ('socket.create_connection', 'socket.getaddrinfo', 'socket.socket.connect'):
            guard = patch(target, forbidden); guard.start(); self.addCleanup(guard.stop)
        self.flow = make_flow()
        self.owner = uuid.uuid4().hex
        self.guide, self.record = self.flow.initial()

    def runner(self, message, guide=None, record=None):
        return tools.ToolRunner(self.flow, self.owner, guide if guide is not None else self.guide,
                                record if record is not None else self.record, message, today=TODAY)

    def save(self, message, *updates, keep=True):
        runner = self.runner(message)
        out = runner.run('save_profile_fields', {'updates': list(updates)})
        if keep:
            self.guide, self.record = runner.guide, runner.record
        return runner, out

    def statuses(self, out):
        return [(item['id'], item['status'], item['reason']) for item in out['outcomes']]


class SchemaAndCatalog(Base):
    def walk(self, schema, seen):
        if isinstance(schema, dict):
            if schema.get('type') == 'object':
                seen.append(schema)
            for value in schema.values():
                self.walk(value, seen)
        elif isinstance(schema, list):
            for value in schema:
                self.walk(value, seen)

    def test_tools_are_strict_function_tools(self):
        self.assertEqual([tool['name'] for tool in tools.TOOLS],
                         ['save_profile_fields', 'get_signup_dates', 'check_doctor', 'check_medicine',
                          'get_plan_status', 'offer_plans', 'show_card'])
        for tool in tools.TOOLS:
            self.assertEqual(set(tool), {'type', 'name', 'description', 'parameters', 'strict'})
            self.assertEqual(tool['type'], 'function')
            self.assertIs(tool['strict'], True)
            objects = []
            self.walk(tool['parameters'], objects)
            self.assertTrue(objects)
            for item in objects:
                self.assertIs(item['additionalProperties'], False)
                self.assertEqual(item['required'], list(item['properties']))
        json.dumps(tools.TOOLS)
        self.assertLess(len(json.dumps(tools.TOOLS)), 6000)
        place = tools.TOOLS[2]['parameters']['properties']['place']
        self.assertEqual(place['type'], ['string', 'null'])

    def test_field_catalog_is_stable_and_matches_the_tool(self):
        catalog = tools.field_catalog(self.flow)
        self.assertEqual(json.dumps(catalog), json.dumps(tools.field_catalog(make_flow())))
        ids = [row['id'] for row in catalog]
        enum = tools.TOOLS[0]['parameters']['properties']['updates']['items']['properties']['id']['enum']
        self.assertEqual(ids, enum)
        self.assertEqual(len(ids), len(set(ids)))
        for row in catalog:
            self.assertEqual(list(row), ['id', 'label', 'purpose', 'choices', 'fields'])
            self.assertTrue(row['label'] and row['purpose'] and row['fields'])
        by_id = {row['id']: row for row in catalog}
        for expected in ('T01', 'T05', 'RC01', 'RC11', 'S_AGE65', 'S_RETIREMENT', 'MG_AGE'):
            self.assertIn(expected, by_id)
        self.assertNotIn('RC28', by_id)
        self.assertIn(['cobra', 'COBRA'], by_id['T05']['choices'])
        self.assertEqual([field['key'] for field in by_id['RC11']['fields']], ['choice', 'jobEnd', 'coverageEnd'])
        self.assertTrue(next(f for f in by_id['T05']['fields'] if f['key'] == 'choice').get('multi'))


class Saving(Base):
    def test_birthday_calendar_resolution_requires_an_upcoming_dated_report(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        for quote, fields, expected_year in (
            ('I turn 65 on January 4', {'month': '1'}, 2027),
            ('I turn 65 on December 14', {'month': '12', 'year': '2026'}, 2026),
            ('I turned 65 in December', {'month': '12'}, None),
            ('My 65th birthday is in December', {'month': '12'}, None)):
            with self.subTest(quote=quote):
                runner, saved = self.save(quote, update('S_AGE65', fields, quote), keep=False)
                self.assertEqual(self.statuses(saved)[0][1], 'accepted')
                self.assertEqual(self.flow.value(runner.guide, 'situation.age65')['year'], expected_year)
        quote = 'I turn 65 on December 14'
        _, saved = self.save(quote, update('S_AGE65', {'month': '12', 'year': '2030'}, quote), keep=False)
        self.assertEqual(self.statuses(saved)[0][1], 'rejected')

    def test_effective_days_stay_with_their_part_and_survive_month_only_restatement(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        a, b = 'Part A starts December 1, 2026', 'Part B starts December 15, 2026'
        fields = {'status': 'approved', 'year': '2026', 'month': '12'}
        _, result = self.save(a + ' and ' + b,
                              update('COV_PART_A', fields, a), update('COV_PART_B', fields, b))
        self.assertEqual([row['status'] for row in result['outcomes']], ['accepted', 'accepted'])
        again = 'Part B starts in December 2026'
        self.save(again, update('COV_PART_B', fields, again))
        for part, day in [('A', '01'), ('B', '15')]:
            report = self.flow.value(self.guide, 'enrollment.part' + part)
            self.assertEqual((report['precision'], report['date']), ('day', '2026-12-' + day))

    def test_saves_a_simple_field_on_working_copies(self):
        message = 'This is for me, and I am on COBRA right now.'
        runner, out = self.save(message, update('RC01', {'choice': 'self'}, 'This is for me'),
                                update('T05', {'choice': 'cobra'}, 'I am on COBRA right now'), keep=False)
        self.assertTrue(out['ok'])
        self.assertEqual(self.statuses(out), [('RC01', 'accepted', 'explicit_report'), ('T05', 'accepted', 'explicit_report')])
        self.assertEqual(self.flow.value(runner.guide, 'coverage.current'), ['cobra'])
        self.assertEqual(self.flow.value(runner.guide, 'subject.role'), 'self')
        # The caller's guide and record are untouched; the runner holds the working copies.
        self.assertEqual(self.guide['fields'], {})
        self.assertEqual(self.record['facts'], {})
        self.assertEqual(runner.saved, [{'id': 'RC01', 'entity': 'profile', 'fields': {'choice': 'self'}},
                                        {'id': 'T05', 'entity': 'profile', 'fields': {'choice': 'cobra'}}])
        self.assertEqual([call['name'] for call in runner.results], ['save_profile_fields'])
        self.assertEqual(runner.results[0]['output'], out)
        self.assertNotIn('T05', out['open'])
        self.assertIn('T03', out['open'])
        self.flow.validate(runner.guide, runner.record)
        json.dumps(runner.results)

    def test_a_field_hidden_among_several_in_one_call(self):
        message = ('My name is not important. It is for me, I live in 34102, my job gives me insurance, '
                   'I take fictionol every day and I see Dr. Nera Vale. Low monthly payments would be nice.')
        runner, out = self.save(message,
            update('T03', {'zip': '34102'}, 'I live in 34102'),
            update('T05', {'choice': 'employer'}, 'my job gives me insurance'),
            update('RC09', {'choice': 'my_job'}, 'my job gives me insurance'),
            update('T07', {'text': 'fictionol'}, 'I take fictionol every day'),
            update('T06', {'text': 'Dr. Nera Vale'}, 'I see Dr. Nera Vale'),
            update('T09', {'choice': 'lower_monthly'}, 'Low monthly payments would be nice'),
            update('RC01', {'choice': 'self'}, 'It is for me'))
        self.assertEqual([status for _, status, _ in self.statuses(out)], ['accepted'] * 7)
        self.assertEqual([item['id'] for item in out['outcomes']], ['T03', 'T05', 'RC09', 'T07', 'T06', 'T09', 'RC01'])
        value = lambda key: self.flow.value(runner.guide, key)
        self.assertEqual(value('comparison.scope.zip'), '34102')
        self.assertEqual(value('needs.medications'), 'fictionol')
        self.assertEqual(value('needs.providers'), 'Dr. Nera Vale')
        self.assertEqual(value('needs.costPreference'), 'lower_monthly')
        self.assertEqual(self.flow.report(runner.record, 'RC09')['choice'], 'my_job')
        self.assertEqual(len(runner.saved), 7)

    def test_an_already_known_value(self):
        self.save('It is for me and I have COBRA.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        before = self.flow.capture_values(self.guide, self.record)
        runner, out = self.save('As I said, I have COBRA.', update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        self.assertEqual(self.statuses(out), [('T05', 'already_known', 'explicit_report')])
        self.assertEqual(runner.saved, [])
        # Reported values and their states are unchanged (advisor-first's own comparison, which ignores revision counters).
        self.assertEqual(self.flow.capture_values(runner.guide, runner.record), before)

    def test_a_change_without_a_correction_changes_nothing(self):
        self.save('It is for me and I have COBRA.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        runner, out = self.save('It is retiree coverage.', update('T05', {'choice': 'retiree'}, 'It is retiree coverage'))
        self.assertEqual(self.statuses(out), [('T05', 'needs_confirmation', 'conflicting_report')])
        self.assertEqual(self.flow.value(runner.guide, 'coverage.current'), ['cobra'])
        self.assertEqual(runner.saved, [])

    def test_a_correction_of_an_existing_value_is_accepted(self):
        self.save('It is for me and I have COBRA.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        earlier = self.guide['fields']['coverage.current']['revision']
        runner, out = self.save('Sorry, it is retiree coverage, not COBRA.',
                                update('T05', {'choice': 'retiree'}, 'it is retiree coverage, not COBRA', correction=True))
        self.assertEqual(self.statuses(out), [('T05', 'accepted', 'explicit_report')])
        self.assertEqual(self.flow.value(runner.guide, 'coverage.current'), ['retiree'])
        provenance = runner.record['natural']['provenance']['guide.coverage.current']
        self.assertEqual(provenance['supersedesRevision'], earlier)
        self.assertEqual(provenance['method'], 'direct_report')

    def test_a_change_of_who_the_coverage_is_for_waits_for_the_persons_confirmation(self):
        self.save('It is for me. I live in 34102, I have COBRA and I take fictionol.',
                  update('RC01', {'choice': 'self'}, 'It is for me'), update('T03', {'zip': '34102'}, 'I live in 34102'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'), update('T07', {'text': 'fictionol'}, 'I take fictionol'))
        correction = update('RC01', {'choice': 'someone'}, 'this is all for my mother, not me', correction=True)
        # advisor-first alone refuses this change once personal reports exist.
        with self.assertRaises(ProfileError):
            self.flow.capture(copy.deepcopy(self.guide), copy.deepcopy(self.record),
                              {**correction, 'entity': 'profile', 'fields': {'choice': 'someone'}})
        earlier_fact = self.record['facts']['RC01']['revision']
        earlier_role = self.guide['fields']['subject.role']['revision']
        reports = {key: copy.deepcopy(item['value']) for key, item in self.guide['fields'].items() if key != 'subject.role'}
        # The model's update never applies it, with or without the correction flag, whatever the message says.
        for message, item in (('Sorry, this is all for my mother, not me.', correction),
                              ('ok thanks', update('RC01', {'choice': 'someone'}, 'ok', correction=True)),
                              ('ok thanks', update('RC01', {'choice': 'someone'}, 'ok')),
                              ('ok thanks', update('RC01', {'choice': 'research'}, 'ok', correction=True))):
            runner, out = self.save(message, item, keep=False)
            self.assertEqual(self.statuses(out), [('RC01', 'needs_confirmation', 'subject_change')], message)
            self.assertEqual(self.flow.value(runner.guide, 'subject.role'), 'self')
            self.assertEqual(runner.saved, [])
            self.assertEqual(len(runner.confirmations), 1)
        runner, out = self.save('Sorry, this is all for my mother, not me.', correction, keep=False)
        staged = runner.confirmations[0]
        self.assertEqual((staged['id'], staged['fields'], staged['correction']), ('RC01', {'choice': 'someone'}, True))
        # The person confirms through the code-built control; advisor-first's own helper builds the update.
        confirmed = {'id': 'RC01', 'fields': {'choice': 'someone'}, 'entity': 'profile', 'quote': 'Yes, that’s right.',
                     'subject': 'beneficiary', 'scope': 'current', 'uncertain': False, 'correction': True}
        runner = self.runner('Yes, that’s right.')
        self.assertTrue(runner.confirm(confirmed))
        self.assertEqual(self.flow.value(runner.guide, 'subject.role'), 'someone')
        self.assertEqual(self.flow.report(runner.record, 'RC01')['choice'], 'someone')
        # Every earlier report is still attached and current.
        self.assertEqual({key: item['value'] for key, item in runner.guide['fields'].items() if key != 'subject.role'}, reports)
        self.assertTrue(all(item['status'] != 'stale' for item in runner.guide['fields'].values()))
        self.assertFalse(any(fact.get('stale') for fact in runner.record['facts'].values()))
        # The earlier value is kept in revision history and provenance, as other corrections keep it.
        self.assertIn({'choice': 'self'}, [entry.get('previous') for entry in runner.record['history'] if entry['triggerId'] == 'RC01'])
        provenance = runner.record['natural']['provenance']
        self.assertEqual(provenance['readiness.RC01']['supersedesRevision'], earlier_fact)
        self.assertEqual(provenance['guide.subject.role']['supersedesRevision'], earlier_role)
        self.assertEqual(provenance['readiness.RC01']['method'], 'explicit_confirmation')
        self.flow.validate(runner.guide, runner.record)
        self.assertEqual(runner.saved, [{'id': 'RC01', 'entity': 'profile', 'fields': {'choice': 'someone'}}])

    def test_who_it_is_for_can_still_change_before_any_personal_report_exists(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        # advisor-first itself allows this change while nothing personal is attached to the person.
        runner, out = self.save('Sorry, it is for my mother.', update('RC01', {'choice': 'someone'}, 'it is for my mother', correction=True))
        self.assertEqual(self.statuses(out), [('RC01', 'accepted', 'explicit_report')])
        runner, out = self.save('What about my mother?', update('RC01', {'choice': 'someone'}, 'my mother'), keep=False)
        self.assertEqual(self.statuses(out), [('RC01', 'already_known', 'explicit_report')])

    def test_a_different_person_without_a_correction_is_not_accepted(self):
        self.save('It is for me and I have COBRA.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        runner, out = self.save('What about my mother?', update('RC01', {'choice': 'someone'}, 'my mother'))
        self.assertEqual(self.statuses(out), [('RC01', 'needs_confirmation', 'subject_change')])
        self.assertEqual(self.flow.value(runner.guide, 'subject.role'), 'self')

    def test_advisor_firsts_extraction_validators_run_before_anything_is_saved(self):
        # The reviewer's case: a message that states none of these values.
        message = 'Hi, I am looking for some help understanding my options.'
        self.save(message, update('RC01', {'choice': 'self'}, 'I'))
        for item in (update('T03', {'zip': '34102'}, 'I am'),
                     update('T06', {'choice': 'list', 'text': 'Dr. Raj Patel'}, 'some help'),
                     update('RC11', {'jobEnd': '2027-03'}, 'I am'),
                     update('MG_AGE', {'choice': '70'}, 'I am'),
                     update('S_AGE65', {'month': '3', 'year': '2027'}, 'I am'),
                     update('S_AGE65', {'birthMonth': '3', 'birthYear': '1962'}, 'I am'),
                     update('S_AGE65', {'relativeMonth': 'next_month'}, 'I am'),
                     update('S_RETIREMENT', {'status': 'retired'}, 'I am'),
                     update('COV_PLAN', {'product': 'advantage', 'name': 'Humana Gold Plus', 'carrier': 'Humana'}, 'my options')):
            runner, out = self.save(message, item, keep=False)
            self.assertEqual(self.statuses(out)[0][1], 'rejected', item['id'])
            self.assertEqual(runner.saved, [])
            self.assertEqual(runner.confirmations, [])
            self.assertEqual(self.flow.capture_values(runner.guide, runner.record),
                             self.flow.capture_values(self.guide, self.record))
        # The same values, when the person does state them, are saved.
        said = 'My ZIP is 34102, I see Dr. Raj Patel and I am 70.'
        runner, out = self.save(said, update('T03', {'zip': '34102'}, 'My ZIP is 34102'),
                                update('T06', {'choice': 'list', 'text': 'Dr. Raj Patel'}, 'I see Dr. Raj Patel'),
                                update('MG_AGE', {'choice': '70'}, 'I am 70'))
        self.assertEqual([status for _, status, _ in self.statuses(out)], ['accepted'] * 3)

    def test_code_asks_for_confirmation_only_when_a_report_contradicts_a_saved_one(self):
        self.save('It is for me and I have COBRA.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T05', {'choice': 'cobra'}, 'I have COBRA'))
        # A doubtful first-time value is not saved and is not queued for a code-built confirmation.
        runner, out = self.save('I think I prefer predictable costs.',
                                update('T09', {'choice': 'predictable'}, 'I think I prefer predictable costs'))
        self.assertEqual(self.statuses(out), [('T09', 'needs_confirmation', 'tentative')])
        self.assertEqual(runner.confirmations, [])
        self.assertIsNone(self.flow.value(runner.guide, 'needs.costPreference'))
        runner, out = self.save('I might turn 65 in March 2027.',
                                update('S_AGE65', {'month': '3', 'year': '2027'}, 'I might turn 65 in March 2027', uncertain=True))
        self.assertEqual(self.statuses(out), [('S_AGE65', 'needs_confirmation', 'tentative')])
        self.assertEqual(runner.confirmations, [])
        # A report that contradicts a saved value is held in advisor-first's pending shape.
        runner, out = self.save('I have Medicaid.', update('T05', {'choice': 'medicaid'}, 'I have Medicaid'))
        self.assertEqual(self.statuses(out), [('T05', 'needs_confirmation', 'conflicting_report')])
        self.assertEqual(runner.confirmations, [{'id': 'T05', 'entity': 'profile', 'fields': {'choice': 'medicaid'},
                                                 'quote': 'I have Medicaid', 'subject': 'beneficiary',
                                                 'scope': 'current', 'uncertain': False, 'correction': True}])
        self.assertEqual(self.flow.value(runner.guide, 'coverage.current'), ['cobra'])
        self.save('I turn 65 in March 2027.', update('S_AGE65', {'month': '3', 'year': '2027'}, 'I turn 65 in March 2027'))
        runner, out = self.save('I turn 65 in June 2027.',
                                update('S_AGE65', {'month': '6', 'year': '2027'}, 'I turn 65 in June 2027'))
        self.assertEqual(self.statuses(out), [('S_AGE65', 'needs_confirmation', 'conflicting_report')])
        self.assertEqual(runner.confirmations, [{'id': 'S_AGE65', 'fields': {}, 'entity': 'profile',
                                                 'proposed': {'month': 6, 'year': 2027}}])
        self.assertTrue(runner.confirm_situation('age65', {'month': 6, 'year': 2027}))
        self.assertEqual(self.flow.value(runner.guide, 'situation.age65'), {'month': 6, 'year': 2027})

    def test_a_goal_in_the_persons_own_words_is_saved_without_a_confirmation(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        said = 'I want to find coverage that works for me, but I want to feel good about my decision'
        # However the model flagged it: no time scope, unsure of the category, or words with no category.
        for extra, fields in (({'scope': 'unknown'}, {'choice': 'compare', 'text': said}),
                              ({'uncertain': True}, {'choice': 'compare'}),
                              ({'scope': 'intended', 'subject': 'learner'}, {'choice': 'compare', 'text': said}),
                              ({}, {'text': said})):
            runner, out = self.save(said, update('T01', fields, said, **extra), keep=False)
            self.assertEqual(self.statuses(out), [('T01', 'accepted', 'explicit_report')], extra)
            self.assertEqual(runner.confirmations, [])
            self.assertEqual(self.flow.value(runner.guide, 'intent.goal'), fields.get('choice', 'unresolved'))
        # Words the person did not type are still refused by advisor-first's validators.
        runner, out = self.save(said, update('T01', {'choice': 'compare', 'text': 'the cheapest plan'}, said), keep=False)
        self.assertEqual(self.statuses(out), [('T01', 'rejected', 'unsupported_report')])

    def test_a_restated_goal_or_a_request_for_coverage_work_replaces_the_goal_without_a_question(self):
        self.save('It is for me. I want to understand Medicare.', update('RC01', {'choice': 'self'}, 'It is for me'),
                  update('T01', {'choice': 'learn', 'text': 'I want to understand Medicare'}, 'I want to understand Medicare'))
        runner, out = self.save('Can I see the plans now?', update('T01', {'choice': 'compare'}, 'Can I see the plans now?'))
        self.assertEqual((self.statuses(out)[0][1], runner.confirmations), ('accepted', []))
        self.assertEqual(self.flow.value(runner.guide, 'intent.goal'), 'compare')
        runner, out = self.save('I want to find a plan that keeps my doctor.',
                                update('T01', {'choice': 'compare', 'text': 'find a plan that keeps my doctor'},
                                       'I want to find a plan that keeps my doctor'))
        self.assertEqual((self.statuses(out)[0][1], runner.confirmations), ('accepted', []))
        # Moving away from coverage work contradicts the saved goal, so the person confirms it.
        runner, out = self.save('I just want to understand Medicare.',
                                update('T01', {'choice': 'learn'}, 'I just want to understand Medicare'))
        self.assertEqual(self.statuses(out), [('T01', 'needs_confirmation', 'conflicting_report')])
        self.assertEqual([item['id'] for item in runner.confirmations], ['T01'])
        self.assertEqual(self.flow.value(runner.guide, 'intent.goal'), 'compare')

    def test_the_quote_must_be_in_the_message_and_doubt_is_not_saved(self):
        runner, out = self.save('It is for me. I think I might have COBRA.',
            update('RC01', {'choice': 'self'}, 'It is for me'),
            update('T05', {'choice': 'cobra'}, 'I definitely have COBRA'),
            update('T09', {'choice': 'predictable'}, 'I think I might have COBRA', uncertain=True),
            update('T08', {'choice': 'local'}, 'It is for me', subject='unclear'))
        self.assertEqual(self.statuses(out), [('RC01', 'accepted', 'explicit_report'),
                                              ('T05', 'rejected', 'missing_supporting_span'),
                                              ('T09', 'needs_confirmation', 'tentative'),
                                              ('T08', 'needs_confirmation', 'unclear_scope')])
        self.assertEqual(sorted(runner.guide['fields']), ['subject.role'])

    def test_values_outside_the_catalog_and_identifiers_are_rejected(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        runner, out = self.save('I have purple coverage. My number is 123-45-6789. My zip is 34102.',
            update('T05', {'choice': 'purple'}, 'I have purple coverage'),
            update('T03', {'zip': '123-45-6789'}, 'My number is 123-45-6789'),
            update('T03', {'colour': 'blue'}, 'My zip is 34102'),
            update('RC28', {'choice': 'neither'}, 'My zip is 34102'),
            update('T01', {'choice': 'learn'}, 'My zip is 34102', entity='spouse'))
        self.assertEqual(self.statuses(out), [('T05', 'rejected', 'invalid_choice'),
                                              ('T03', 'rejected', 'identifier_not_accepted'),
                                              ('T03', 'rejected', 'invalid_fields'),
                                              (None, 'rejected', 'unsupported_question'),
                                              ('T01', 'rejected', 'unsupported_entity')])
        # An outcome names its update by position and a catalog id. Nothing the model wrote comes back.
        self.assertEqual([item['index'] for item in out['outcomes']], [0, 1, 2, 3, 4])
        self.assertTrue(all(set(item) == {'index', 'id', 'status', 'reason'} for item in out['outcomes']))
        for echoed in ('spouse', 'purple', 'blue', 'RC28', '123-45-6789'):
            self.assertNotIn(echoed, json.dumps(out))
        self.assertEqual(sorted(runner.guide['fields']), ['subject.role'])
        self.assertNotIn('123-45-6789', json.dumps([runner.guide, runner.record]))

    def test_birth_month_work_status_and_medicare_parts(self):
        message = ('It is for me. I was born in March 1962 and I retired last year. '
                   'I have Part A since June 2026 and I applied for Part B.')
        runner, out = self.save(message,
            update('RC01', {'choice': 'self'}, 'It is for me'),
            update('S_AGE65', {'birthMonth': '3', 'birthYear': '1962'}, 'I was born in March 1962'),
            update('S_RETIREMENT', {'status': 'retired', 'when': 'last year'}, 'I retired last year'),
            update('COV_PART_A', {'status': 'active', 'month': '6', 'year': '2026'}, 'I have Part A since June 2026'),
            update('COV_PART_B', {'status': 'applied'}, 'I applied for Part B'))
        self.assertEqual([status for _, status, _ in self.statuses(out)], ['accepted'] * 5)
        value = lambda key: self.flow.value(runner.guide, key)
        self.assertEqual(value('coverage.birth'), '1962-03')
        self.assertEqual(value('situation.age65'), {'month': 3, 'year': 2027})
        self.assertEqual(value('situation.retirement'), {'status': 'retired', 'when': 'last year'})
        self.assertEqual(value('enrollment.partA')['date'], '2026-06-01')
        self.assertEqual(value('enrollment.partB')['status'], 'applied')
        self.assertNotIn('S_AGE65', out['open'])
        # A month the quote does not state is not saved; a different birth month needs the person's correction.
        _, out = self.save('I was born in April.', update('S_AGE65', {'birthMonth': '5', 'birthYear': '1962'}, 'I was born in April'))
        self.assertEqual(self.statuses(out), [('S_AGE65', 'rejected', 'ungrounded_report')])
        _, out = self.save('I was born in April 1962.', update('S_AGE65', {'birthMonth': '4', 'birthYear': '1962'}, 'I was born in April 1962'))
        self.assertEqual(self.statuses(out), [('S_AGE65', 'needs_confirmation', 'conflicting_report')])
        first = update('S_AGE65', {'firstOfMonth': 'yes'}, 'My birthday is on the first of the month')
        # advisor-first's situation validator takes this detail only as an answer to the birthday question.
        _, out = self.save('My birthday is on the first of the month.', first, keep=False)
        self.assertEqual(self.statuses(out), [('S_AGE65', 'rejected', 'unsupported_situation')])
        runner = tools.ToolRunner(self.flow, self.owner, self.guide, self.record, 'My birthday is on the first of the month.',
                                  today=TODAY, asked=self.flow.question('S_AGE65'))
        out = runner.run('save_profile_fields', {'updates': [first]})
        self.assertEqual(self.statuses(out)[0][1], 'accepted')
        self.assertEqual(self.flow.value(runner.guide, 'situation.age65'), {'month': 3, 'year': 2027, 'first_day': True})

    def test_several_priorities_in_one_message_are_one_answer(self):
        self.save('It is for me.', update('RC01', {'choice': 'self'}, 'It is for me'))
        runner, out = self.save('My doctors and my prescriptions matter most.',
                                update('T10', {'choice': 'doctors'}, 'My doctors'),
                                update('T10', {'choice': 'drugs'}, 'my prescriptions matter most'))
        self.assertEqual([status for _, status, _ in self.statuses(out)], ['accepted', 'accepted'])
        self.assertEqual(self.flow.value(runner.guide, 'needs.priorities'), ['doctors', 'drugs'])
        self.assertEqual(len(runner.saved), 1)

    def test_a_bad_tool_name_never_raises(self):
        runner = self.runner('Hello.')
        for name in ('delete_everything', '', None, 7):
            self.assertEqual(runner.run(name, {}), {'ok': False, 'error': 'unknown_tool'})
        self.assertEqual(len(runner.results), 4)
        self.assertEqual(runner.results[0], {'name': 'delete_everything', 'arguments': {}, 'output': {'ok': False, 'error': 'unknown_tool'}})
        json.dumps(runner.results)

    def test_bad_arguments_never_raise_and_save_nothing(self):
        runner = self.runner('It is for me.')
        good = update('RC01', {'choice': 'self'}, 'It is for me')
        bad_calls = [
            ('save_profile_fields', None), ('save_profile_fields', 'not json'), ('save_profile_fields', []),
            ('save_profile_fields', {}), ('save_profile_fields', {'updates': 'RC01'}),
            ('save_profile_fields', {'updates': [good], 'extra': 1}),
            ('save_profile_fields', {'updates': [good, {'id': 'T05'}]}),
            ('save_profile_fields', {'updates': [{**good, 'correction': 'yes'}]}),
            ('save_profile_fields', {'updates': [{**good, 'fields': [{'key': 'choice', 'value': 3}]}]}),
            ('save_profile_fields', {'updates': [{**good, 'fields': []}]}),
            ('save_profile_fields', {'updates': [good] * 25}),
            ('get_signup_dates', {'when': 'now'}), ('get_plan_status', {'x': 1}),
            ('check_doctor', {'name': 'Dr. Nera Vale'}), ('check_medicine', {}),
            ('show_card', {}), ('show_card', {'kind': 5}),
        ]
        for name, arguments in bad_calls:
            self.assertEqual(runner.run(name, arguments), {'ok': False, 'error': 'bad_arguments'}, (name, arguments))
        self.assertEqual(len(runner.results), len(bad_calls))
        self.assertEqual(runner.guide['fields'], {})
        self.assertEqual(runner.saved, [])
        json.dumps(runner.results)
        # A JSON string of a valid call is accepted as its object.
        self.assertTrue(runner.run('save_profile_fields', json.dumps({'updates': [good]}))['ok'])

    def test_an_internal_failure_is_a_fixed_code_and_logs_no_content(self):
        runner = self.runner('CANARY-MESSAGE for me.')
        with patch.object(tools.enrollment_journey, 'status', side_effect=RuntimeError('CANARY-ERROR-TEXT')), \
                self.assertLogs(tools.LOGGER, level='WARNING') as logs:
            self.assertEqual(runner.run('get_signup_dates', {}), {'ok': False, 'error': 'tool_failed'})
        text = '\n'.join(logs.output)
        self.assertIn('tool=get_signup_dates error=RuntimeError', text)
        self.assertNotIn('CANARY', text)


class Dates(Base):
    def reported(self):
        message = 'It is for me. I was born in March 1962. I am on COBRA. I do not have Part A or Part B.'
        return self.save(message, update('RC01', {'choice': 'self'}, 'It is for me'),
                         update('S_AGE65', {'birthMonth': '3', 'birthYear': '1962'}, 'I was born in March 1962'),
                         update('T05', {'choice': 'cobra'}, 'I am on COBRA'),
                         update('RC04', {'choice': 'neither'}, 'I do not have Part A or Part B'))[0]

    def test_dates_for_a_reported_birthday_month(self):
        runner = self.reported()
        out = runner.run('get_signup_dates', {})
        self.assertTrue(out['ok'])
        self.assertEqual(out['today'], '2026-11-21')
        # The same dates advisor-first's own timing code gives for this report.
        import ux_pass
        timing = ux_pass.enrollment_timing({'month': 3, 'year': 2027}, TODAY, 'neither')
        self.assertEqual(out['signup_window']['start'], timing['iep']['start'].isoformat())
        self.assertEqual(out['signup_window']['end'], timing['iep']['end'].isoformat())
        self.assertEqual(out['signup_window']['phase'], 'before')
        self.assertEqual(out['part_a_start']['date'], timing['part_a_start'].isoformat())
        self.assertEqual(out['part_b_start']['date'], timing['part_b_start'].isoformat())
        # The Medigap window is the row advisor-first's own coordinated-dates builder makes.
        row = next(item for item in enrollment_flow.coordinated_dates(
            enrollment_flow.journey(self.flow, runner.guide, runner.record, TODAY), timing, {'month': 3, 'year': 2027})
            if item['label'] == 'Medigap window')
        self.assertEqual(out['medigap_window'], {'months': row['value'],
                                                 'start': timing['medigap_window']['start'].isoformat(),
                                                 'end': timing['medigap_window']['end'].isoformat(),
                                                 'basis': out['medigap_window']['basis']})
        for key in ('signup_window', 'part_a_start', 'part_b_start', 'medigap_window', 'next_step'):
            self.assertIn('reported 65th-birthday month', out[key]['basis'])
        for value in (out['signup_window']['start'], out['signup_window']['end'], out['part_a_start']['date'],
                      out['part_b_start']['date'], out['medigap_window']['start'], out['next_step']['by']):
            self.assertEqual(date.fromisoformat(value).isoformat(), value)
        self.assertIsNone(out['job_coverage_window'])
        self.assertEqual(out['parts'], {'A': 'needed', 'B': 'needed'})
        self.assertIs(out['first_of_month_reported'], False)
        self.assertEqual(out['needs'], [])
        json.dumps(out)
        self.assertEqual(runner.results[-1], {'name': 'get_signup_dates', 'arguments': {}, 'output': out})

    def test_a_reported_start_is_marked_reported(self):
        self.reported()
        runner, _ = self.save('I got Part A, it started June 2026.',
                              update('COV_PART_A', {'status': 'active', 'month': '6', 'year': '2026'}, 'it started June 2026'))
        out = runner.run('get_signup_dates', {})
        self.assertEqual(out['part_a_start'], {'date': '2026-06-01', 'basis': 'Reported by the person.'})

    def test_no_dates_before_a_birthday_is_reported(self):
        out = self.runner('Hello.').run('get_signup_dates', {})
        self.assertTrue(out['ok'])
        for key in ('signup_window', 'part_a_start', 'part_b_start', 'medigap_window', 'job_coverage_window', 'coverage_end'):
            self.assertIsNone(out[key])
        self.assertEqual(out['needs'], ['S_AGE65', 'RC04'])

    def test_the_job_coverage_window_comes_from_the_reported_end_dates(self):
        message = ('It is for me. I was born in May 1958. My insurance is from my own job. '
                   'The job ends December 15 2026 and the insurance ends December 31 2026. I have neither part of Medicare.')
        runner, out = self.save(message, update('RC01', {'choice': 'self'}, 'It is for me'),
            update('S_AGE65', {'birthMonth': '5', 'birthYear': '1958'}, 'I was born in May 1958'),
            update('T05', {'choice': 'employer'}, 'My insurance is from my own job'),
            update('RC09', {'choice': 'my_job'}, 'My insurance is from my own job'),
            update('RC11', {'jobEnd': 'December 15 2026', 'coverageEnd': 'December 31 2026'},
                   'The job ends December 15 2026 and the insurance ends December 31 2026'),
            update('RC04', {'choice': 'neither'}, 'I have neither part of Medicare'))
        self.assertEqual([status for _, status, _ in self.statuses(out)], ['accepted'] * 6)
        dates = runner.run('get_signup_dates', {})
        expected = conversation_records.work_window(self.flow, runner.guide, runner.record, TODAY)
        window = dates['job_coverage_window']
        self.assertEqual(window['first_end'], '2026-12-15')
        self.assertEqual([window['part_b_window']['start_month'], window['part_b_window']['end_month']], expected['part_b_window'])
        self.assertEqual(window['plan_window_end_month'], expected['plan_window_end'])
        self.assertIn('reported job and coverage end dates', window['basis'])
        self.assertEqual(dates['coverage_end'], {'date': '2026-12-31', 'precision': 'day', 'basis': 'Reported by the person.'})
        self.assertIsNone(dates['signup_window'])
        card = runner.run('show_card', {'kind': 'enrollment_timing'})
        self.assertTrue(card['ok'])
        self.assertEqual(runner.cards[0]['records'], conversation_records.VERSION)


class StandInChecks:
    """Has the public shape of advisor-first's ConversationChecks.reconcile result. Fictional."""
    drugs = None

    def __init__(self, error=None):
        self.doctors = object()
        self.error = error
        self.calls = 0

    def reconcile(self, owner, guide, record):
        self.calls += 1
        if self.error:
            raise self.error
        return {'question': {'kind': 'doctor', 'field': 'doctor_plan', 'item': 'doctor-1', 'token': 'fictional',
                             'question': 'Which coverage would you like me to check for this doctor?', 'why': '',
                             'choices': [{'value': 'a', 'label': 'CANDIDATE-LABEL'}]},
                'results': [], 'canBack': False, 'participant_release': False}


class Checks(Base):
    def test_checks_are_unavailable_when_none_is_configured(self):
        runner = self.runner('Hello.')
        self.assertEqual(runner.run('check_doctor', {'name': 'Dr. Nera Vale', 'place': 'Naples'}),
                         {'ok': False, 'error': 'check_unavailable'})
        self.assertEqual(runner.run('check_doctor', {'name': 'Dr. Nera Vale', 'place': None}),
                         {'ok': False, 'error': 'check_unavailable'})
        self.assertEqual(runner.run('check_medicine', {'name': 'fictionol'}), {'ok': False, 'error': 'check_unavailable'})
        self.assertEqual([call['name'] for call in runner.results], ['check_doctor', 'check_doctor', 'check_medicine'])

    def test_medicine_check_is_unavailable_without_a_drug_service(self):
        self.flow.conversation_checks = StandInChecks()
        self.assertEqual(self.runner('Hello.').run('check_medicine', {'name': 'fictionol'}),
                         {'ok': False, 'error': 'check_unavailable'})

    def test_a_failing_check_is_a_fixed_code(self):
        runner, _ = self.save('It is for me. I see Dr. Nera Vale.', update('RC01', {'choice': 'self'}, 'It is for me'),
                              update('T06', {'text': 'Dr. Nera Vale'}, 'I see Dr. Nera Vale'))
        self.flow.conversation_checks = StandInChecks(error=RuntimeError('CANARY-SOURCE-ROW'))
        with self.assertLogs(tools.LOGGER, level='WARNING') as logs:
            self.assertEqual(runner.run('check_doctor', {'name': 'Nera Vale', 'place': None}),
                             {'ok': False, 'error': 'check_failed'})
        self.assertNotIn('CANARY', '\n'.join(logs.output))

    @unittest.skipUnless(CONTRACT, NEEDS_CONTRACT)
    def test_the_check_wrapper_reports_what_is_still_needed(self):
        runner, _ = self.save('It is for me. I see Dr. Nera Vale.', update('RC01', {'choice': 'self'}, 'It is for me'),
                              update('T06', {'text': 'Dr. Nera Vale'}, 'I see Dr. Nera Vale'))
        self.flow.conversation_checks = StandInChecks()
        out = runner.run('check_doctor', {'name': 'Nera Vale', 'place': None})
        self.assertTrue(out['ok'])
        self.assertEqual((out['status'], out['needs']['field'], out['needs']['choices_shown_in_interface']),
                         ('needs_detail', 'doctor_plan', 1))
        self.assertNotIn('CANDIDATE-LABEL', json.dumps(out))
        self.assertEqual(runner.run('check_doctor', {'name': 'Dr. Absent Example', 'place': None}),
                         {'ok': False, 'error': 'doctor_not_saved'})


class PlanStatus(Base):
    def find(self, value, key):
        if isinstance(value, dict):
            return key in value or any(self.find(item, key) for item in value.values())
        if isinstance(value, list):
            return any(self.find(item, key) for item in value)
        return False

    def test_status_without_an_engine_reports_no_order(self):
        runner, _ = self.save('It is for me and I live in 34102.', update('RC01', {'choice': 'self'}, 'It is for me'),
                              update('T03', {'zip': '34102'}, 'I live in 34102'))
        out = runner.run('get_plan_status', {})
        self.assertTrue(out['ok'])
        self.assertEqual((out['recommendation']['available'], out['recommendation']['reason']), (False, 'engine_not_configured'))
        self.assertFalse(self.find(out, 'recommended_ids'))
        self.assertIn('plan_review', out)
        self.assertIsInstance(out['unavailable'], list)
        if CONTRACT:
            self.assertEqual(out['unavailable'], [])
            self.assertIn('needs', out['outcomes']['plan_comparison'])
            self.assertIn('status', out['plans_pages']['medigap'])
        json.dumps(out)
        self.assertLess(len(json.dumps(out)), 4000)

    def test_the_engine_is_not_called_when_its_inputs_cannot_be_built(self):
        called = []
        setattr(self.flow, tools.RECOMMENDATION_HOOK, lambda inputs, **extra: called.append(inputs))
        import recommendation_engine
        with patch.object(recommendation_engine, 'inputs', side_effect=RuntimeError('fictional')):
            out = self.runner('Hello.').run('get_plan_status', {})
        self.assertEqual(called, [])
        self.assertEqual((out['recommendation']['available'], out['recommendation']['reason']), (False, 'inputs_unavailable'))

    @unittest.skipUnless(CONTRACT, NEEDS_CONTRACT)
    def test_an_engine_result_is_passed_through_and_never_made_here(self):
        seen = {}

        def engine(inputs, *, checks, expected_doctors, reported):
            seen.update(inputs=inputs, reported=reported)
            tab = {'state': 'ready', 'recommended_ids': ['FICTIONAL-1'], 'no_pick_reason': None,
                   'groups': [{'id': 'priority', 'label': 'Fictional group', 'ids': ['FICTIONAL-1', 'FICTIONAL-2']}],
                   'plans': {'FICTIONAL-1': {'checks': []}}}
            return {'method': 'fictional-method', 'evaluation_only': True, 'path': tab, 'advantage': tab,
                    'medigap': {'state': 'unavailable', 'message': 'Fictional hold.', 'groups': [], 'recommended_ids': []},
                    'part_d': tab}
        setattr(self.flow, tools.RECOMMENDATION_HOOK, engine)
        out = self.runner('Hello.').run('get_plan_status', {})
        import recommendation_engine
        self.assertEqual(seen['inputs']['version'], recommendation_engine.INPUTS_VERSION)
        self.assertTrue(out['recommendation']['available'])
        # The engine's result only: no group label, no number of plans, no display message.
        self.assertEqual(out['recommendation']['advantage'],
                         {'state': 'ready', 'recommended_ids': ['FICTIONAL-1'], 'no_pick_reason': None})
        self.assertEqual(out['recommendation']['medigap'],
                         {'state': 'unavailable', 'recommended_ids': [], 'no_pick_reason': None})
        text = json.dumps(out)
        for shown_only_on_the_plans_page in ('Fictional group', 'Fictional hold', '"count"', '"label"', '"groups"',
                                             '"message"'):
            self.assertNotIn(shown_only_on_the_plans_page, text)


class Cards(Base):
    def test_show_card_builds_a_supported_kind_once(self):
        runner = Dates.reported(self)
        out = runner.run('show_card', {'kind': 'enrollment_timing'})
        self.assertTrue(out['ok'])
        self.assertEqual((out['kind'], out['already_shown']), ('enrollment_timing', False))
        self.assertEqual(len(runner.cards), 1)
        card = runner.cards[0]
        self.assertEqual(card['kind'], 'enrollment_timing')
        # The card is advisor-first's own, built from the same reports.
        import ux_pass
        expected = ux_pass.timing_card(ux_pass.enrollment_timing({'month': 3, 'year': 2027}, TODAY, 'neither'), {'cobra'}, [])
        self.assertEqual(card['rows'], expected['rows'])
        self.assertEqual(out['dates'], expected['dates'])
        self.assertEqual(out['rows'][0], {'label': expected['rows'][0]['label'], 'value': expected['rows'][0]['value']})
        again = runner.run('show_card', {'kind': 'enrollment_timing'})
        self.assertTrue(again['already_shown'])
        self.assertEqual(len(runner.cards), 1)
        medigap = runner.run('show_card', {'kind': 'medigap_window'})
        self.assertTrue(medigap['ok'])
        self.assertEqual([item['kind'] for item in runner.cards], ['enrollment_timing', 'medigap_window'])
        json.dumps(runner.cards)
        json.dumps(runner.results)

    def test_cards_made_of_enrollment_statements_are_off_until_the_owner_accepts_them_here(self):
        runner = Dates.reported(self)
        self.assertEqual(tools.STATEMENT_CARD_KINDS,
                         {'two_paths', 'signup_route', 'trade_off', 'discussion_paths', 'finish_summary'})
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop(tools.STATEMENTS_SWITCH, None)
            for kind in sorted(tools.STATEMENT_CARD_KINDS):
                self.assertEqual(runner.run('show_card', {'kind': kind}),
                                 {'ok': False, 'error': 'card_needs_owner_acceptance'}, kind)
            self.assertEqual(runner.cards, [])
            # The kinds left on never read a sentence from enrollment-content.json.
            def unaccepted(*args, **kwargs):
                raise AssertionError('an enrollment statement was read')
            with patch.object(enrollment_flow, 'statement', unaccepted), patch.object(enrollment_flow, 'content', unaccepted):
                for kind in sorted(set(tools.CARD_KINDS) - tools.STATEMENT_CARD_KINDS):
                    runner.run('show_card', {'kind': kind})
            self.assertNotIn('tool_failed', json.dumps(runner.results))
            self.assertTrue({'enrollment_timing', 'medigap_window'} <= {card['kind'] for card in runner.cards})
        with patch.dict('os.environ', {tools.STATEMENTS_SWITCH: '1'}):
            route = runner.run('show_card', {'kind': 'signup_route'})
            self.assertTrue(route['ok'])
            self.assertEqual(runner.cards[-1]['route'], 'sign_up_a_and_b')

    def test_unknown_and_unbuildable_cards_return_fixed_codes(self):
        runner = self.runner('Hello.')
        self.assertEqual(runner.run('show_card', {'kind': 'surprise'}), {'ok': False, 'error': 'unknown_card_kind'})
        self.assertEqual(runner.run('show_card', {'kind': 'plans_ready'}), {'ok': False, 'error': 'unknown_card_kind'})
        for kind in ('enrollment_timing', 'medigap_window', 'trial_right', 'coverage_now'):
            self.assertEqual(runner.run('show_card', {'kind': kind}), {'ok': False, 'error': 'card_not_available'}, kind)
        with patch.dict('os.environ', {tools.STATEMENTS_SWITCH: '1'}):
            for kind in ('finish_summary', 'trade_off'):
                self.assertEqual(runner.run('show_card', {'kind': kind}), {'ok': False, 'error': 'card_not_available'}, kind)
        self.assertEqual(runner.cards, [])
        self.assertEqual(len(runner.results), 8)

    @unittest.skipUnless(CONTRACT, NEEDS_CONTRACT)
    def test_two_paths_card(self):
        runner = Dates.reported(self)
        with patch.dict('os.environ', {tools.STATEMENTS_SWITCH: '1'}):
            self.assertTrue(runner.run('show_card', {'kind': 'two_paths'})['ok'])
        self.assertEqual(runner.cards[-1]['kind'], 'two_paths')


if __name__ == '__main__':
    unittest.main()
