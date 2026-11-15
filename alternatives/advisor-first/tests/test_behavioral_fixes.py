"""D170 held-out mechanics. Local scripted transport; network forbidden."""
import unittest
from test_conversation_planner import ConversationPlannerTests as Harness
from test_recommendation_engine import run
import enrollment_flow


class BehavioralFixes(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context','composed_context'):
        locals()[name] = getattr(Harness, name)
    setUp = Harness.setUp
    update = staticmethod(Harness.update)
    extraction = staticmethod(Harness.extraction)

    def test_explicit_parts_override_wrong_model_and_previous_inference(self):
        self.choice('RC01',choice='self'); self.choice('T05',choice='advantage')
        self.message('I have Parts A and B.')
        for text, states in [('I have neither A nor B.', ['needed','needed']),
                             ('To correct that: I have Part A only, no Part B.', ['active','needed']),
                             ('I do not have Part A or Part B.', ['needed','needed'])]:
            out=self.message(text,[self.update('RC04',{'choice':'both'},text)])
            self.assertEqual([v['state'] for v in out['enrollment']['record']['parts'].values()], states)
            self.assertNotIn('Part B: active',out['enrollment']['line']['status'])
            self.assertNotEqual(out['enrollment']['record']['route'],'none_needed')

    def test_month_is_not_reported_day(self):
        self.choice('RC01',choice='self')
        out=self.message('My Parts A and B start December 2026.')
        self.assertIn('December 2026',out['enrollment']['line']['status'])
        self.assertNotIn('December 1,',out['enrollment']['line']['status'])

    def test_sign_up_request_does_not_create_active_parts(self):
        self.choice('RC01',choice='self')
        self.message('I have neither Part A nor Part B.')
        text='Tell me the next steps to get A and B started.'
        out=self.message(text,extraction=self.extraction(discussion=Harness.proposal(text,purpose='problem',focus='enrollment')))
        self.assertEqual([v['state'] for v in out['enrollment']['record']['parts'].values()], ['needed','needed'])
        self.assertEqual(out['conversationPlanner']['plans_view'],'ab')

    def test_negative_b_alone_does_not_assert_a(self):
        self.choice('RC01',choice='self')
        out=self.message('I do not have Part B.')
        self.assertEqual([v['state'] for v in out['enrollment']['record']['parts'].values()], ['unknown','needed'])

    def test_conflicting_parts_require_clarification_and_correction_resolves(self):
        self.choice('RC01',choice='self')
        out=self.message('I have Parts A and B. I do not have Part B.')
        self.assertEqual(out['enrollment']['record']['parts']['B']['state'],'unknown')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'CP_PARTS')
        out=self.message('Actually, I have Part A only, no Part B.')
        self.assertEqual(out['enrollment']['record']['parts']['B']['state'],'needed')

    def test_finish_failure_has_summary_and_no_default_intake(self):
        from chat import ModelUnavailable
        self.choice('RC01',choice='self')
        out=self.message('Please summarize what remains open.', compose=ModelUnavailable('Declared offline failure'))
        self.assertEqual(out['generated']['status'],'unavailable')
        self.assertEqual(out['cards'][0]['kind'],'finish_summary')
        self.assertNotIn('What would you like to understand next?',out['reply'])

    def test_task_and_standard_g_filter_survive_side_question(self):
        self.message('Please show standard Plan G premiums in 34103.')
        text='Does that price guarantee acceptance?'
        out=self.message(text,extraction=self.extraction(discussion=Harness.proposal(text,
            focus='medigap',question_quote=text)))
        self.assertEqual(out['conversationPlanner']['plans_view'],'supplement')
        self.assertEqual(out['conversationPlanner']['medigap_variant'],'G')
        self.assertEqual(out['coveragePath']['state'],'undecided')

    def test_advantage_review_survives_doctor_evidence_question(self):
        self.message('I want to review my Advantage plan.')
        out=self.message('What did you check about my doctor?')
        self.assertEqual(out['conversationPlanner']['plans_view'],'advantage')

    def test_keep_g_does_not_divert_drug_task(self):
        out=self.message("I'm keeping my Plan G. My drug plan costs too much. Can you compare it using my pharmacy?")
        self.assertEqual(out['conversationPlanner']['plans_view'],'part-d')
        self.assertEqual(out['enrollment']['record']['components']['medigap'],'keep_existing')
        text='Lowest total cost using my pharmacy. I have Parts A and B, my Plan G and a separate drug plan.'
        p=Harness.proposal(text,purpose='investigate',focus='part_d',request_quote=text,investigate=['part_d','medicines'])
        out=self.message(text,extraction=self.extraction([self.update('T05',{'choice':'drug'},text)],discussion=p))
        self.assertEqual(out['conversationPlanner']['plans_view'],'part-d')

    def test_finish_is_recorded_and_does_not_restart_intake(self):
        self.message('I just want to understand my choices. I am not ready to give personal details.')
        out=self.message('That is enough for today. I am undecided. Please give me a short recap.')
        self.assertEqual(out['conversationPlanner']['outcome']['kind'],'education_complete')
        self.assertEqual(out['cards'][0]['kind'],'finish_summary')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['coveragePath']['state'],'undecided')

    def test_wait_with_followup_question_is_explicit(self):
        out=self.message("I'm going to wait before choosing additional coverage. What do I still need to check?")
        self.assertEqual(out['coveragePath']['path'],'wait')
        self.assertEqual(out['conversationPlanner']['outcome']['kind'],'wait')

    def test_unknown_criteria_never_get_positive_fit_label(self):
        result=run(doctors='list',priorities=['doctors','total_cost'])['advantage']
        self.assertEqual(result['recommended_ids'],[])
        self.assertNotEqual(result['groups'][0]['label'],'Matches your priorities')

    def test_partial_doctor_evidence_remains_open_in_finish(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from journey_completion import summary
        flow = SimpleNamespace(value=lambda g, field: None, report=lambda r, field: {})
        state = {'finish_requested':'summary', 'task_investigate':['doctors'],
                 'decision':{'stance':'undecided'}}
        out = {'conversationCheck':{'results':[{'kind':'doctor_matrix', 'name':'Dr. Example',
                'plans':{'one':{'state':'listed','membership':'in_network'},
                         'two':{'state':'unknown'}}}]}}
        with patch('enrollment_flow.journey', return_value={'components':{'medigap':None}}):
            outcome, card = summary(flow, 'fictional', {}, {}, state, out)
        self.assertFalse(outcome['goal_complete'])
        self.assertIn('1 remain unknown',outcome['work'][0])
        self.assertIn('exact office',outcome['next_action'])
        self.assertEqual(card['finish'],'source_blocked')

    def test_detail_preserves_unresolved_medicine_and_binds_named_item(self):
        self.choice('RC01',choice='self')
        self.choice('T07',text='insulin glargine and apixaban 5 mg tablets')
        self.flow.apply(self.g,self.r,{'id':'RC22','entity':'new',
            'fields':{'name':'apixaban','strength':'5 mg','form':'tablet'}})
        self.assertIn('insulin glargine',self.flow.value(self.g,'needs.medications'))
        items=self.r['facts']['RC22']['value']['items']
        self.assertEqual(items[0]['entity'],'medicine-2')
        self.flow.apply(self.g,self.r,{'id':'RC22','entity':'medicine-2','correction':True,
            'fields':{'name':'rivaroxaban','strength':'10 mg','form':'tablet'}})
        names=self.flow.value(self.g,'needs.medications')
        self.assertIn('insulin glargine',names)
        self.assertIn('rivaroxaban',names)
        self.assertNotIn('apixaban',names)


if __name__ == '__main__': unittest.main()
