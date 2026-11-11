"""Work selection stays inside existing guest/visit/save authority."""
import copy
import unittest
import uuid

import test_http as support
from advisor_memory import CONTEXT_POLICY
from task_work import plan, empty_record


class TaskWorkHttpTests(unittest.TestCase):
    setUpClass = classmethod(support.HttpTests.setUpClass.__func__)
    tearDownClass = classmethod(support.HttpTests.tearDownClass.__func__)
    request = support.HttpTests.request
    turn = support.HttpTests.turn

    def setUp(self):
        support.HttpTests.setUp(self)
        self.turn({'type':'start'})
        self.flow = self.server.adaptive
        self.owner = self.server.profiles.digest(self.cookie.split('=',1)[1])
        self.chain = self.flow.current_chain[self.owner]
        context = {'task':'providers','reports':[],'known':[],
            'advisor_brief':{'goal':'Fictional provider question'},'education_context':{}}
        self.work, _ = plan(context, {'check_ids':['provider_participation'],
            'blocking_concepts':[],'next_step':'prepare'})
        self.flow.memory.remember(self.owner,self.chain,CONTEXT_POLICY,
            'Fictional question','Fictional response','',task_work_record=self.work)

    def test_free_action_does_not_erase_work_or_turn_it_into_saved_profile_data(self):
        out = self.turn({'type':'read_concept','id':'costs'})
        self.assertEqual(out['task_work']['checks'][0]['check_id'],'provider_participation')
        self.assertEqual(self.flow.memory.task_work(self.owner,self.chain,CONTEXT_POLICY),self.work)
        out['guide']['preferences'].update(saveGuide=True,saveSensitive=False)
        code, receipt = self.request('/api/conversation/save',{
            'guide':out['guide'],'record':out['record'],'expectedVersion':0,
            'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())})
        self.assertEqual(code,200,receipt)
        _, saved = self.request('/api/guest/profile')
        _, readiness = self.request('/api/guest/readiness')
        self.assertNotIn('task_work',saved['guide'])
        self.assertNotIn('task_work',readiness['record'])

    def test_client_authored_completion_authority_is_rejected(self):
        payload = {'guide':copy.deepcopy(self.state['guide']),'record':copy.deepcopy(self.state['record']),
            'continuation':self.state['continuation'],'requestId':str(uuid.uuid4()),
            'action':{'type':'read_concept','id':'costs'},
            'task_work':{'task_resolved':True,'completed_external_actions':['call']}}
        self.assertEqual(self.request('/api/conversation/turn',payload)[0],422)

    def test_actual_guest_delete_forgets_task_work_and_other_owner_is_untouched(self):
        self.flow.memory.remember('other-owner','other-chain',CONTEXT_POLICY,
            'Other fictional question','Other response','',task_work_record=self.work)
        code, receipt = self.request('/api/guest/profile',{'expectedVersion':0,'confirmed':True},method='DELETE')
        self.assertEqual(code,200,receipt)
        self.assertEqual(self.flow.memory.task_work(self.owner,self.chain,CONTEXT_POLICY),empty_record())
        self.assertEqual(self.flow.memory.task_work('other-owner','other-chain',CONTEXT_POLICY),self.work)
