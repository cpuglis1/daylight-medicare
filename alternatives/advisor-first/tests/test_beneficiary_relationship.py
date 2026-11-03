"""Visit relationship scope is separate from helper insurance attributes.

Replays the observed interpreter shape through the production validators and
controller, using only injected in-process responses and temporary test state.
"""
import copy
import unittest
import uuid

import test_natural_agent as agent_support
import test_natural_flow as flow_support
from natural_state import classify_update


class RelationshipAdapterTests(unittest.TestCase):
    setUp = agent_support.NaturalAgentTests.setUp
    update = agent_support.NaturalAgentTests.update
    extraction = agent_support.NaturalAgentTests.extraction
    empty_agenda = agent_support.NaturalAgentTests.empty_agenda

    def interpret(self, message, updates):
        self.answer = self.extraction(updates)
        before = copy.deepcopy(self.answer)
        with self.agent.reserve_turn() as reservation:
            result = self.agent.extract('fictional',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(self.answer,before,'Normalization must not mutate the proposed wire report.')
        return result

    def test_observed_helper_relationship_metadata_is_normalized_only_for_rc01(self):
        message = ('I am helping my mother. I have insurance through my current job, '
                   'but she has no health insurance.')
        role = self.update('RC01',{'choice':'someone'},'I am helping my mother',subject='learner')
        helper = self.update('T05',{'choice':'employer'},
            'I have insurance through my current job',subject='learner')
        beneficiary = self.update('T05',{'choice':'none'},'she has no health insurance')
        result = self.interpret(message,[role,helper,beneficiary])
        self.assertEqual(result['updates'],[{**role,'subject':'beneficiary'},beneficiary])
        self.assertEqual([item['id'] for item in result['rejected_updates']],['T05'])

    def test_relationship_normalization_preserves_quote_choice_entity_and_scope_guards(self):
        message = 'I am helping my mother.'
        valid = self.update('RC01',{'choice':'someone'},'I am helping my mother',subject='learner')
        invalid = [{**valid,'quote':'I am helping my father'},
            {**valid,'entity':'doctor-1'},
            {**valid,'fields':[{'key':'choice','value':'invented_role'}]},
            {**valid,'scope':'invented_scope'}]
        for proposal in invalid:
            with self.subTest(proposal=proposal):
                result = self.interpret(message,[proposal])
                self.assertEqual(result['updates'],[])
                self.assertEqual([item['id'] for item in result['rejected_updates']],['RC01'])

    def test_unclear_relationship_subject_remains_uncertain(self):
        message = 'This may be for someone else.'
        proposal = self.update('RC01',{'choice':'someone'},message,subject='unclear')
        result = self.interpret(message,[proposal])
        self.assertEqual(result['updates'][0]['subject'],'unclear')
        self.assertIs(result['updates'][0]['uncertain'],True)
        self.assertEqual(classify_update(result['updates'][0],message)['decision'],'clarify')

    def test_unknown_time_scope_is_not_rewritten_to_current(self):
        message = 'I am helping my mother.'
        proposal = self.update('RC01',{'choice':'someone'},message,subject='learner',scope='unknown')
        result = self.interpret(message,[proposal])
        self.assertEqual(result['updates'][0]['scope'],'unknown')
        self.assertEqual(classify_update(result['updates'][0],message)['decision'],'clarify')

    def test_existing_different_beneficiary_relationship_still_requires_resolution(self):
        message = 'I am helping my mother.'
        proposal = self.update('RC01',{'choice':'someone'},message,subject='learner')
        result = self.interpret(message,[proposal])
        resolution = classify_update(result['updates'][0],message,
            existing={'value':{'choice':'self'}})
        self.assertEqual(resolution['decision'],'clarify')

    def test_familiarity_still_belongs_to_the_learner(self):
        message = 'I do not understand Medicare.'
        proposal = self.update('T02',{'choice':'new'},message,subject='learner')
        self.assertEqual(self.interpret(message,[proposal])['updates'],[proposal])


class RelationshipControllerTests(unittest.TestCase):
    setUp = flow_support.NaturalFlowTests.setUp
    update = staticmethod(flow_support.NaturalFlowTests.update)
    payload = flow_support.NaturalFlowTests.payload
    take = flow_support.NaturalFlowTests.take
    turn = flow_support.NaturalFlowTests.turn
    message = flow_support.NaturalFlowTests.message
    extraction = staticmethod(flow_support.NaturalFlowTests.extraction)
    composed_context = flow_support.NaturalFlowTests.composed_context
    stage_payloads = flow_support.NaturalFlowTests.stage_payloads

    def test_observed_caregiver_opening_captures_relationship_without_helper_insurance(self):
        message = ('I am helping my mother, who turns 65 in November. '
            'I have insurance through my current job, but she has no health insurance. '
            'She wants to understand her Medicare options.')
        birthday = {'kind':'age65','subject':'beneficiary','scope':'intended',
            'quote':'my mother, who turns 65 in November','uncertain':False,'correction':False,
            'month':11,'year':None,'status':'','when':''}
        result = self.message(message,extraction={
            'updates':[
                self.update('RC01',{'choice':'someone'},'I am helping my mother',subject='learner'),
                self.update('T05',{'choice':'employer'},
                    'I have insurance through my current job',subject='learner'),
                self.update('T05',{'choice':'none'},'she has no health insurance')],
            'requests':[],'fact_ids':[],'agenda':{'concerns':[],'priorityReason':{}},
            'situation_proposals':[birthday],'goal_quote':'She wants to understand her Medicare options.',
            'education_request':{'kind':'none','concept_ids':[],'quote':''}})
        self.assertEqual(result['generated']['status'],'complete')
        self.assertEqual(self.flow.value(self.g,'subject.role'),'someone')
        self.assertEqual(self.flow.value(self.g,'coverage.current'),['none'])
        self.assertEqual(self.flow.value(self.g,'situation.age65'),{'month':11,'year':None})
        self.assertNotEqual((result['assessment'].get('nextQuestion') or {}).get('id'),'RC01')
        candidates = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertNotIn('RC01',[item['id'] for item in candidates['question_candidates']])
        self.assertEqual(len(self.calls),2)

    def test_hypothetical_helper_relationship_is_not_captured(self):
        text = 'If I were helping my mother, what would I need?'
        result = self.message(text,updates=[self.update('RC01',{'choice':'someone'},
            'If I were helping my mother',subject='learner')])
        self.assertEqual(result['generated']['status'],'complete')
        self.assertIsNone(self.flow.value(self.g,'subject.role'))
        self.assertNotIn('RC01',self.r['facts'])
        self.assertEqual((result['assessment'].get('nextQuestion') or {}).get('id'),'RC01')


if __name__ == '__main__':
    unittest.main()
