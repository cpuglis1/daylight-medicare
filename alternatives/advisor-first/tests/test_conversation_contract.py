"""D174 offline wire/controller checks. All model meanings are explicitly scripted.

No phrase interpreter or automatic follow-up filler; these are not model-quality evals.
"""
import copy
import json
import unittest
import test_semantic_guidance as semantic
from advisor_memory import CONTEXT_POLICY
import conversation_prompts
import conversation_tasks


class ConversationContract(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context', 'interpreted', 'ask'):
        locals()[name] = getattr(semantic.SemanticGuidance, name)
    update = staticmethod(semantic.SemanticGuidance.update)
    extraction = staticmethod(semantic.SemanticGuidance.extraction)

    def setUp(self):
        semantic.SemanticGuidance.setUp(self)
        self.supply_fixture_followup = False

    def reply(self, text, *, mode='work', task='compare', checks=(), target=None, question='', **kwargs):
        return self.message(text, extraction=self.interpreted(text, mode=mode, task=task, checks=checks),
            compose=dict(reply='We can work through the details that matter for this decision.',
                question_target=target, question=question, **kwargs))

    def test_offer_survives_even_with_authorized_questions_across_all_tasks(self):
        self.choice('RC01', choice='self')
        offer='Would you like to work through the relevant details together, or explore the idea further first?'
        for task in conversation_tasks.TASKS:
            with self.subTest(task=task):
                out=self.reply('Help me with this part of the decision.',task=task,question=offer,
                    conversation_assessment=dict(goal_progress='open',next_move='next_step'))
                self.assertEqual(out['generated']['status'],'complete')
                self.assertIsNone(out['assessment']['nextQuestion'])
                self.assertTrue(out['reply'].endswith(offer))
                self.assertFalse(out['metrics']['questionSelection']['changed'])
                self.assertEqual(out['metrics']['llmCalls'],2)

    def test_direct_work_and_missing_followup_recover_existing_controls(self):
        self.choice('RC01',choice='self')
        for task in conversation_tasks.TASKS:
            with self.subTest(task=task):
                # Independent task contract; prior unanswered tasks must not
                # consume this case's question allowance.
                self.doCleanups(); self.setUp(); self.choice('RC01',choice='self')
                out=self.reply('Please help me work through this now.',task=task)
                q=out['assessment']['nextQuestion']
                self.assertIsNotNone(q)
                self.assertIn(q['id'],self.composed_context()['discussion_plan']['available_questions'])
                self.assertNotIn('understand next',out['reply']+q['question'])
                self.assertTrue(out['metrics']['questionSelection']['changed'])
                self.assertEqual(out['metrics']['llmCalls'],2)

    def test_detour_can_answer_then_select_a_common_preparation_question(self):
        self.choice('RC01',choice='self')
        self.choice('T05',choice='employer')
        self.ask('Help me prepare for the transition.',task='timing',checks=['payer_order'],target='RC04')
        out=self.reply('What does this coverage label mean?',mode='detour',task='',target='RC04',
            question='Which Medicare parts are in effect now?')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC04')
        self.assertEqual(out['coveragePath']['state'],'undecided')
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_detour_can_answer_without_forced_intake_or_generic_closer(self):
        self.choice('RC01',choice='self')
        self.ask('Help me review the options.',task='compare',target='T10')
        out=self.reply('I need this idea explained first.',mode='detour',task='')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['reply'],'We can work through the details that matter for this decision.')
        self.assertTrue(self.composed_context()['discussion_plan']['available_questions'])
        self.assertEqual(out['conversationPlanner']['active_task'],'compare')

    def test_education_alone_does_not_start_intake_or_invent_a_question(self):
        out=self.reply('Explain this idea to me.',mode='discuss',task='')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('?',out['reply'])
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_null_target_does_not_smuggle_personal_intake(self):
        out=self.reply('Help with my medicines.',task='drug_coverage',question='Which medicines do you take?')
        self.assertIsNotNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['metrics']['questionSelection']['changed'])
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_proposed_nonfirst_question_keeps_its_controls(self):
        self.choice('RC01',choice='self')
        out=self.reply('Help me weigh the choices.',target='T10',question='What matters most to you?')
        q=out['assessment']['nextQuestion']
        self.assertEqual(q['id'],'T10')
        self.assertTrue(q['choices'])
        self.assertNotEqual(self.composed_context()['discussion_plan']['available_questions'][0],'T10')

    def test_term_correction_can_advance_without_recording_a_product_choice(self):
        self.choice('RC01',choice='self')
        self.choice('T05',choice='employer')
        text='I want the public parts plus C. How do I get started?'
        out=self.message(text,extraction=self.interpreted(text,task='timing',focus='enrollment',checks=['payer_order'],
            fact_ids=[]),compose=dict(
                reply='Original Medicare is Parts A and B. Medicare Advantage is an alternative way to receive those benefits. We can start with the enrollment details while the coverage choice stays open.',
                question_target='RC04',question='Which Medicare parts are in effect now?',evidence_refs=['routesintro']))
        self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC04')
        self.assertEqual(out['coveragePath']['state'],'undecided')
        self.assertIsNone(self.flow.value(self.g,'intent.components'))

    def test_prompt_contract_is_single_and_keeps_full_question_inventory(self):
        self.reply('Please help me compare the options.')
        extract,compose=self.calls[-2:]
        self.assertEqual(extract['instructions'],conversation_prompts.INTERPRETATION)
        self.assertEqual(compose['instructions'],conversation_prompts.COMPOSITION)
        self.assertNotIn('discussion_instructions',self.extracted_context())
        self.assertNotIn('rules',self.composed_context()['conversation_state'])
        self.assertEqual(len(self.extracted_context()['question_table']['rows']),41)
        self.assertLess(len(extract['instructions']),8500)
        self.assertLess(len(compose['instructions']),8500)

    def teach_paths(self, visual):
        text='How do the main coverage structures differ?'
        p=self.interpreted(text,mode='discuss',task='',focus='coverage_paths')
        p['discussion']['question_quote']=text
        return self.message(text,extraction=p,compose=dict(
            reply='Here are the main coverage structures to compare.',question_target=None,question='',
            education=dict(purpose='teach',updates=[],visual=visual)))

    def test_card_is_optional_and_records_delivery_when_selected(self):
        out=self.teach_paths('none')
        self.assertFalse(out.get('cards'))
        out=self.teach_paths('discussion_paths')
        self.assertEqual([c['kind'] for c in out['cards']],['discussion_paths'])
        receipt=self.flow.memory.education(self.owner,self.flow.current_chain[self.owner],CONTEXT_POLICY)
        self.assertEqual(receipt['concepts']['coverage_paths']['deliveries'],1)
        self.assertNotIn('understood',receipt['concepts']['coverage_paths'])
        self.assertFalse(self.teach_paths('discussion_paths').get('cards'))

    def test_arbitrary_card_name_cannot_render(self):
        self.assertFalse(self.teach_paths('invented_plan_recommendation').get('cards'))

    def test_suggestion_does_not_start_intake_until_accepted(self):
        self.reply('I am still trying to understand this.',mode='suggest',task='costs',
            question='Would working through the cost tradeoffs help?')
        self.assertFalse(self.composed_context()['discussion_plan']['available_questions'])
        out=self.reply('Yes, that would help.',task='')
        self.assertEqual(out['conversationPlanner']['active_task'],'costs')
        self.assertIsNotNone(out['assessment']['nextQuestion'])

    def test_local_retention_avoids_an_extra_paid_repair(self):
        self.flow.agent.composition_recovery=True
        out=self.reply('Explain this general idea.',mode='discuss',task='',
            question='Your premium is $99999. What else?',evidence_refs=[])
        self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        self.assertNotIn('99999',out['reply'])
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_factual_rejection_cannot_spend_the_repair_slot(self):
        self.flow.agent.composition_recovery=True
        text='Explain this general idea.'
        out=self.message(text,extraction=self.interpreted(text,mode='discuss'),
            compose=dict(reply='Your premium is $99999.',question_target=None,question=''))
        self.assertEqual(out['generated']['status'],'unavailable')
        self.assertEqual(out['metrics']['llmCalls'],2)
        self.assertNotIn('99999',out['reply'])

    def test_structure_repair_has_one_slot_and_identical_resolved_context(self):
        self.flow.agent.composition_recovery=True
        self.compositions.append(dict(reply='Long fictional draft. '*100,question_target=None,question=''))
        out=self.reply('Help me compare the choices.')
        self.assertEqual(out['generated']['status'],'complete')
        self.assertEqual(out['metrics']['llmCalls'],3) # one extraction, two composition attempts
        drafts=self.stage_payloads('daylight_resolved_conversation')
        self.assertEqual(len(drafts),2)
        self.assertEqual(drafts[0]['resolved_context'],drafts[1]['resolved_context'])
        self.assertEqual(drafts[1]['validation_feedback']['failure'],'text_bound')

    def test_metrics_contain_counts_and_codes_not_text(self):
        out=self.reply('Please help me compare my choices.')
        rows=out['metrics']['modelStages']
        self.assertEqual([r['stage'] for r in rows],['extract','compose'])
        for row,payload in zip(rows,self.calls[-2:]):
            self.assertEqual(row['instructions_bytes'],len(payload['instructions'].encode()))
            self.assertEqual(row['request_bytes'],len(json.dumps(payload).encode()))
            self.assertNotIn('instructions',row)
            self.assertNotIn('Please help',json.dumps(row))
            self.assertIsNone(row['first_text_ms']) # scripted transport is not a live timing sample


if __name__=='__main__':unittest.main()
