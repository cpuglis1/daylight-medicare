"""D173 controller contracts. Explicit scripted meanings, no keyword interpreter.

These verify that the real controller follows semantic outputs and preserves
capture/education. They do not grade a live model's conversational judgment.
"""
import unittest
import copy
import test_conversation_planner as harness
import conversation_planner as planner
import conversation_tasks as tasks
from chat import ModelUnavailable


class SemanticGuidance(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context','composed_context'):
        locals()[name] = getattr(harness.ConversationPlannerTests, name)
    def setUp(self):
        harness.ConversationPlannerTests.setUp(self)
        self.script_legacy_discussion = False
    update = staticmethod(harness.ConversationPlannerTests.update)
    extraction = staticmethod(harness.ConversationPlannerTests.extraction)

    def interpreted(self, text, *, mode='work', task='', checks=(), focus='', updates=(), **extra):
        p = planner.empty_proposal()
        p.update(purpose='problem' if mode == 'work' else 'understand', focus=focus, quote=text,
                 guidance=dict(mode=mode,task=task,checks=list(checks),quote=text,finish=''))
        return self.extraction(updates, discussion=p, **extra)

    def ask(self, text, *, mode='work', task='', checks=(), focus='', updates=(), target=None, **extra):
        def compose(sent):
            choices=sent['question_candidates']
            move=next((c for c in choices if c['id']==target),None) if target else next(iter(choices),None)
            return dict(reply='We can work through what matters for your next decision.',
                question_target=move['id'] if move else None,
                question=move['question']['question'] if move else 'Would working through that be useful now?')
        return self.message(text, extraction=self.interpreted(text,mode=mode,task=task,checks=checks,focus=focus,updates=updates,**extra),compose=compose)

    def test_different_tasks_use_same_semantic_contract_without_trigger_words(self):
        cases=[('compare','Can we put these possibilities alongside one another?','T10'),
               ('review','What I have no longer feels right.','T05'),
               ('timing','I need the handoff to line up.','T05'),
               ('providers','Being able to stay with my specialist is everything.','T06'),
               ('drug_coverage','I need to know whether my prescriptions are included.','T07'),
               ('drug_pricing','What might I spend at the counter?','T07'),
               ('medigap','Show me the monthly figures for that supplement.','MG_AGE'),
               ('advantage','Let me inspect the private alternatives.','T03'),
               ('costs','I cannot handle unpredictable bills.','T09')]
        self.choice('RC01',choice='self')
        for task,text,target in cases:
            with self.subTest(task=task):
                out=self.ask(text,task=task,target=target)
                self.assertEqual(out['conversationPlanner']['active_task'],task)
                self.assertEqual(out['assessment']['nextQuestion']['id'],target)
                self.assertEqual(out['coveragePath']['state'],'undecided')
                self.assertEqual(out['generated']['status'],'complete',out.get('generated'))

    def test_model_selects_consequential_question_not_first_topic_slot(self):
        self.choice('RC01',choice='self')
        out=self.ask('Let us weigh the alternatives.',task='compare',target='T10')
        moves=self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertNotEqual(moves[0]['id'],'T10')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T10')

    def test_same_acceptance_can_continue_any_offered_task(self):
        for task in ('timing','providers','costs'):
            self.ask('I am having trouble deciding what to do next.',mode='suggest',task=task)
            offer=self.composed_context()['discussion_plan']
            self.assertFalse(offer['require_structured'])
            self.assertEqual(offer['suggested_task'],task)
            out=self.ask('That sounds useful; go ahead.',task=task)
            self.assertEqual(out['conversationPlanner']['active_task'],task)
            self.assertIsNotNone(out['assessment']['nextQuestion'])

    def test_quoted_keywords_do_not_override_discussion_or_refusal(self):
        self.choice('RC01',choice='self')
        for text in ('A friend said settle on timing. What does that mean?',
                     'Show me plans is what the button says; I am only asking what it does.',
                     'I am not ready to give personal details.'):
            out=self.ask(text,mode='discuss')
            self.assertIsNone(out['assessment']['nextQuestion'])
            self.assertEqual(out['conversationPlanner']['active_task'],'')
            self.assertEqual(out['conversationPlanner']['investigations'],[])

    def test_missing_interpretation_does_not_start_task_from_words(self):
        out=self.message('Settle on timing!',extraction=self.extraction())
        self.assertEqual(out['conversationPlanner']['active_task'],'')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_detour_captures_all_reports_and_resumes_missing_details(self):
        self.choice('RC01',choice='self')
        self.ask('Help me coordinate the change.',task='timing',checks=['payer_order','job_loss'])
        text='My insurance is from my current job. I have Part A only, no Part B. What is a premium?'
        out=self.ask(text,mode='detour',updates=[self.update('T05',{'choice':'employer'},text),
            self.update('RC09',{'choice':'my_job'},text),self.update('RC04',{'choice':'a_only'},text)])
        self.assertIn('employer',self.flow.value(self.g,'coverage.current'))
        self.assertEqual(self.flow.report(self.r,'RC09')['choice'],'my_job')
        self.assertEqual(self.flow.report(self.r,'RC04')['choice'],'a_only')
        self.assertEqual(out['conversationPlanner']['active_task'],'timing')
        self.assertIsNone(out['assessment']['nextQuestion'])
        out=self.ask('Okay, back to what we were doing.',checks=['payer_order','job_loss'],target='RC11')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
        ids=self.composed_context()['discussion_plan']['available_questions']
        self.assertFalse(set(ids)&{'T05','RC04','RC09'})

    def test_unknown_and_correction_keep_existing_profile_semantics(self):
        self.choice('RC01',choice='self')
        self.ask('Let us look at my needs.',task='compare',target='T10')
        self.turn({'type':'unknown','id':'T10'},aiConsent=False)
        out=self.ask('Continue with what we can.',task='compare')
        self.assertNotIn('T10',self.composed_context()['discussion_plan']['available_questions'])
        self.choice('T05',choice='employer')
        text='Correction: I am on COBRA, not my current job insurance.'
        self.ask(text,task='timing',updates=[self.update('T05',{'choice':'cobra'},text,correction=True)],checks=['payer_order'])
        self.assertEqual(self.flow.value(self.g,'coverage.current'),['cobra'])

    def test_capability_context_and_existing_education_ledger_are_supplied(self):
        self.ask('Can you explain the differences?',mode='discuss',focus='coverage_paths')
        context=self.extracted_context()
        self.assertEqual({t['id'] for t in context['discussion_capabilities']['tasks']},set(tasks.TASKS))
        context=self.composed_context()
        self.assertIn('education_context',context)
        self.assertIn('learner_context',context)
        self.assertIn('known',context)
        self.assertIn('reports',context)

    def test_failure_keeps_available_question_without_rephrase(self):
        self.choice('RC01',choice='self')
        text='I want to look into my prescriptions.'
        out=self.message(text,extraction=self.interpreted(text,task='drug_coverage'),compose=ModelUnavailable('Declared offline failure'))
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T07')
        self.assertNotIn('rephrase',str(out['assessment']['nextQuestion']))

    def test_education_receipts_do_not_repeat_or_imply_understanding(self):
        from advisor_memory import CONTEXT_POLICY
        def teach(text, reason='new', revisit=False):
            return self.message(text, extraction=self.interpreted(text,mode='discuss',
                fact_ids=['basics'], education_request=dict(kind='revisit' if revisit else 'explain',
                    concept_ids=['medicare_basics'],quote=text)),
                compose=dict(reply='Medicare is federal health insurance.',evidence_refs=['basics'],
                    education=dict(purpose='teach',visual='none',updates=[dict(concept_id='medicare_basics',
                        depth='introduced',reason=reason,evidence_refs=['basics'])])))
        def receipt():
            return self.flow.memory.education(self.owner,self.flow.current_chain[self.owner],CONTEXT_POLICY)['concepts']['medicare_basics']
        self.choice('RC01',choice='self')
        out=teach('What is Medicare?')
        self.assertEqual(out['generated']['status'],'complete')
        self.assertEqual(receipt()['deliveries'],1)
        teach('Tell me something else.')
        self.assertEqual(receipt()['deliveries'],1)
        teach('Explain Medicare again please.',reason='requested_revisit',revisit=True)
        self.assertEqual(receipt()['deliveries'],2)
        self.assertNotIn('understood',receipt())

    def test_comparison_goal_uses_existing_profile_and_readiness(self):
        out=self.ask('Let us weigh the alternatives.',task='compare')
        self.assertEqual(self.flow.value(self.g,'intent.goal'),'compare')
        self.assertTrue(out['planReadiness']['active'])
        self.assertEqual({c['id'] for c in out['planReadiness']['criteria']},
            {'goal','person','location','year','coverage','enrollment','doctors','medicines','travel','costs','priorities'})

    def test_task_contract_limits_unrelated_product_work(self):
        self.choice('RC01',choice='self')
        text='Show me those private plans.'
        extraction=self.interpreted(text,task='advantage')
        extraction['discussion'].update(investigate=['advantage','medigap'],request_quote=text)
        out=self.message(text,extraction=extraction)
        self.assertEqual(out['conversationPlanner']['investigations'],['advantage'])

    def test_structured_answer_resumes_checks_after_detour(self):
        self.choice('RC01',choice='self')
        self.ask('I want to look into my prescriptions.',task='drug_coverage')
        self.ask('What is a formulary?',mode='detour')
        self.choice('T07',text='Fictional medicine')
        self.assertTrue(planner.checks_relevant(self.flow,self.owner,self.g))

    def test_pause_is_semantic_and_preserves_reports(self):
        self.choice('RC01',choice='self');self.choice('T05',choice='employer')
        out=self.ask('Let me take a breath and leave this here.',mode='pause')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertEqual(self.flow.value(self.g,'coverage.current'),['employer'])

    def test_conflicting_parts_keep_required_clarification(self):
        self.choice('RC01',choice='self')
        text='I have Parts A and B. I do not have Part B.'
        out=self.ask(text,mode='discuss')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'CP_PARTS')
        sent=self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertTrue(sent['question_candidates'][0]['required'])

    def test_candidate_preview_never_mutates_reports(self):
        self.choice('RC01',choice='self');self.choice('T05',choice='employer')
        before=copy.deepcopy((self.g,self.r))
        for task in tasks.TASKS:tasks.candidates(self.flow,self.g,self.r,task,['payer_order'])
        self.assertEqual((self.g,self.r),before)


if __name__=='__main__':unittest.main()
