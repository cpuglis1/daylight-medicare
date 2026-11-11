"""Circumstance subjects stay local to the actual report, without paid calls."""
import unittest

import test_natural_flow as fixtures
from natural_state import classify_situation
from situation import observations


class SituationScopeTests(unittest.TestCase):
    def test_self_circumstances_survive_a_separate_spouse_job_insurance_clause(self):
        message=("I've been retired for a few years and turn 65 in November. "
                 "My health insurance is through my wife's current job.")
        expected={'retirement':{'status':'retired','when':'for a few years'},
                  'age65':{'month':11,'year':None}}
        self.assertEqual(observations(message),expected)
        self.assertEqual(observations(message,role='self'),expected)
        for kind,value in expected.items():
            self.assertEqual(classify_situation(message,kind,value)['decision'],'accept')

    def test_spouse_insurance_mention_in_same_sentence_does_not_steal_the_birthday(self):
        for message in (
                "I'm retired and turn 65 in November, and my insurance is through my wife's job.",
                "My insurance is through my wife's job, and I turn 65 in November.",
                "I have insurance through my husband's job and turn 65 in November."):
            with self.subTest(message=message):
                self.assertEqual(observations(message).get('age65'),{'month':11,'year':None})

    def test_multiple_observed_people_are_not_collapsed_without_a_beneficiary_scope(self):
        for message in (
                'I am retired and my mother turns 65 in November.',
                'I turn 65 in November. My mother is retired.',
                'My mother is retired. My father turns 65 in November.'):
            with self.subTest(message=message):self.assertEqual(observations(message),{})

    def test_existing_beneficiary_role_does_not_import_another_person(self):
        message='I turn 65 in November. My mother is retired.'
        self.assertEqual(observations(message,role='self'),{'age65':{'month':11,'year':None}})
        self.assertEqual(observations(message,role='someone'),{'retirement':{'status':'retired','when':''}})
        self.assertEqual(observations('I turn 65 in November.',role='someone'),{})
        self.assertEqual(observations('My mother turns 65 in November.',role='self'),{})

    def test_explicit_helper_target_keeps_only_the_beneficiary_observation(self):
        self.assertEqual(observations('This is for my mom. I am retired.'),{})
        message='This is for my mother. I am retired. My mother turns 65 in November.'
        self.assertEqual(observations(message),{'age65':{'month':11,'year':None}})

    def test_coordinated_predicates_inherit_only_their_stated_subject(self):
        self.assertEqual(observations('My mother is retired and turns 65 in November.'),
                         {'retirement':{'status':'retired','when':''},'age65':{'month':11,'year':None}})
        self.assertEqual(observations("My wife's 65th birthday is in November."),
                         {'age65':{'month':11,'year':None}})
        self.assertEqual(observations('My 65th birthday is in November.'),
                         {'age65':{'month':11,'year':None}})

    def test_missing_subject_does_not_invent_one_but_single_subject_fragment_survives(self):
        self.assertEqual(observations('Turning 65 in November.'),{})
        self.assertEqual(observations("My wife has insurance. Turning 65 in November."),{})
        self.assertEqual(observations('I am retired. Turning 65 in November.'),
                         {'retirement':{'status':'retired','when':''},'age65':{'month':11,'year':None}})
        self.assertEqual(observations('I am retired. My wife has insurance. Turning 65 in November.'),
                         {'retirement':{'status':'retired','when':''}})
        self.assertEqual(observations('I am retired. She turns 65 in November.'),
                         {'retirement':{'status':'retired','when':''}})

    def test_existing_tentative_hypothetical_and_conflicting_guards_remain(self):
        self.assertEqual(observations('If I turn 65 in November, what happens?'),{})
        message="I think I'm retired. My insurance is through my wife's job."
        value=observations(message)['retirement']
        self.assertEqual(classify_situation(message,'retirement',value)['reason'],'tentative')
        message='I am retired. I am working.'
        value=observations(message)['retirement']
        self.assertEqual(classify_situation(message,'retirement',value)['reason'],'multiple_situation_clauses')

    def test_actual_flow_keeps_circumstances_alongside_spouse_job_reports(self):
        case=fixtures.NaturalFlowTests()
        case.setUp()
        message=("I've been retired for a few years and turn 65 in November. "
                 "My health insurance is through my wife's current job.")
        coverage="My health insurance is through my wife's current job."
        out=case.message(message,[
            case.update('RC01',{'choice':'self'},"I've been retired for a few years"),
            case.update('T05',{'choice':'employer'},coverage),
            case.update('RC09',{'choice':'spouse_job'},coverage)])
        self.assertEqual(case.flow.value(case.g,'situation.retirement'),{'status':'retired','when':'for a few years'})
        self.assertEqual(case.flow.value(case.g,'situation.age65'),{'month':11,'year':None})
        self.assertEqual(case.flow.value(case.g,'coverage.current'),['employer'])
        self.assertEqual(case.flow.report(case.r,'RC09')['choice'],'spouse_job')
        selected=out['assessment']['nextQuestion']['id']
        candidates=case.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertIn(selected,{item['id'] for item in candidates})
        self.assertNotEqual(selected,'T05')  # Current coverage was already reported.
        self.assertNotIn('coverage.requestedStartMonth',case.g['fields'])


if __name__=='__main__':unittest.main()
