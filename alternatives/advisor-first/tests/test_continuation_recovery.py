"""D177 fictional recovery journeys; no live model or language-quality claims."""
import unittest
import test_quiet_recovery as fixture
import conversation_planner as planner
from chat import ModelUnavailable


class ContinuationRecovery(fixture.QuietRecovery):
    # Reuse helpers without duplicating the inherited test suite.
    for name in dir(fixture.QuietRecovery):
        if name.startswith('test_'):
            locals()[name] = None

    def partial(self, task='costs'):
        text='How can we work out the details that matter to my decision?'
        p=self.interpreted(text,task=task)
        p['discussion']['question_quote']=text
        out=self.message(text,extraction=p,compose=self.draft('', 'first',
            reply_blocks=['We can work through the details that affect your decision.',
                          'Your premium is $99999.']))
        return text,out

    def test_partial_prose_has_no_internal_status_notice(self):
        text,out=self.partial()
        self.assertNotIn('notice',out)
        self.assertEqual(out['reply'],'We can work through the details that affect your decision.')
        self.assertEqual(out['generated']['answer_state'],'partial')
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_question_recovery_uses_existing_catalog_explanation(self):
        self.ask('Help me organize my enrollment.',task='timing',checks=['job_loss'],target='T05',
            updates=[self.update('RC01',{'choice':'self'},'me')])
        self.compositions.append(self.draft('Your premium is $99999.','RC09'))
        out=self.turn({'type':'choice','id':'T05','fields':{'choice':'employer'}})
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC09')
        self.assertEqual(out['reply'],self.flow.content['RC09']['why'].removeprefix('Why we ask: '))
        self.assertNotIn('notice',out)
        self.assertEqual(out['metrics']['llmCalls'],1)

    def test_open_request_survives_detour_and_validated_answer_resolves_it(self):
        text,out=self.partial()
        pending=planner.state(self.flow,self.owner)['open_requests']
        self.assertEqual(pending[0]['request'],text)
        identifier=pending[0]['id']
        self.reply('Let me think about something else first.',mode='discuss',task='')
        self.assertEqual(self.extracted_context()['open_requests'][0]['id'],identifier)
        self.assertEqual(self.composed_context()['open_requests'][0]['id'],identifier)
        self.assertTrue(planner.state(self.flow,self.owner)['open_requests'])
        self.reply('Please connect this to my earlier concern.',task='costs',
                   addressed_requests=[identifier])
        self.assertEqual(planner.state(self.flow,self.owner)['open_requests'],[])

    def test_rejected_reply_cannot_clear_pending_request(self):
        text,out=self.partial()
        identifier=planner.state(self.flow,self.owner)['open_requests'][0]['id']
        self.message('Continue.',extraction=self.interpreted('Continue.',task='costs'),
            compose=self.draft('', 'first',reply_blocks=['We can use the details you share.',
                'Your premium is $99999.'],addressed_requests=[identifier]))
        self.assertEqual(planner.state(self.flow,self.owner)['open_requests'][0]['id'],identifier)

    def test_no_silent_clear_after_history_rolls_or_unknown_receipt(self):
        text,out=self.partial()
        identifier=planner.state(self.flow,self.owner)['open_requests'][0]['id']
        for _ in range(7):
            self.reply('Let me keep exploring first.',mode='discuss',task='',addressed_requests=['not-offered'])
        self.assertEqual(self.composed_context()['open_requests'][0]['id'],identifier)
        self.assertEqual(planner.state(self.flow,self.owner)['open_requests'][0]['id'],identifier)
        self.assertNotIn('open_requests',self.g)
        self.assertNotIn('open_requests',self.r)

    def test_receipts_are_visit_scoped_bounded_and_exclude_blocked_prose(self):
        for index in range(5):
            text=f'Please explain concern {index} before we continue.'
            p=self.interpreted(text,mode='discuss',task='')
            p['discussion']['question_quote']=text
            self.message(text,extraction=p,compose=self.draft('',reply_blocks=[
                'We can use the details you share.', 'Your premium is $99999.']))
        pending=planner.state(self.flow,self.owner)['open_requests']
        self.assertEqual(len(pending),4)
        self.assertNotIn('99999',str(pending))
        old_chain=self.flow.current_chain[self.owner]
        self.flow.current_chain[self.owner]='a-separate-fictional-visit'
        self.assertFalse(planner.state(self.flow,self.owner)['open_requests'])
        self.flow.current_chain[self.owner]=old_chain


class WorkerClaimScope(fixture.CoverageSafeguards):
    for name in dir(fixture.CoverageSafeguards):
        if name.startswith('test_'):
            locals()[name] = None

    def test_worker_questions_and_conditionals_do_not_assert_a_relationship(self):
        replies=[
            'We can check whether the insurance comes through your spouse’s current job.',
            'If coverage comes through your wife’s employer, we can look at the relevant details.',
            'The next detail is whether the insurance comes through your husband’s job.',
            'Does the insurance come through your spouse’s work?',
            'We need to know if coverage comes through your spouse’s employer.',
            'We should establish whether coverage is through your wife’s workplace.',
            'Can you tell me if this comes through your husband’s employer?',
            'The question is whether you use your spouse’s current work coverage.',
            'If it comes through your husband’s current employer, that detail matters.',
            'We can clarify whether the policy is connected to your wife’s employment.',
            'Whether your spouse’s work provides it is still unclear.',
            'We can ask whether your husband’s workplace provides the insurance.',
            'Is this through your wife’s current job?',
            'We can learn if the insurance is connected to your spouse’s workplace.',
            'If the insurance is through your spouse’s job, we can use that detail.',
        ]
        for reply in replies:
            with self.subTest(reply=reply):
                self.h.answer=self.h.composition(reply=reply)
                self.assertEqual(self.h.compose()['reply'],reply)

    def test_unrelated_uncertainty_cannot_hide_an_asserted_relationship(self):
        for reply in ['We can check whether you prefer this, but coverage comes through your spouse’s job.',
                      'If you want help, your insurance is through your husband’s employer.',
                      'Your insurance is through your wife’s employer; whether you keep it is open.']:
            self.h.answer=self.h.composition(reply=reply)
            with self.subTest(reply=reply),self.assertRaises(ModelUnavailable):
                self.h.compose()


if __name__=='__main__': unittest.main()
