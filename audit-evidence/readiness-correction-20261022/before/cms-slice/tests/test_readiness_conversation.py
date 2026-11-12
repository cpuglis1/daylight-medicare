"""Synthetic test contract for D71; no paid requests."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from readiness_conversation import ReadinessConversation
from chat import ResponsesClient,ModelUnavailable
from guest_profiles import ProfileError
W=ROOT/'apps/ten-question';C=json.loads((W/'guide-contract.json').read_text());F=json.loads((W/'teaching-facts.json').read_text());D=json.loads((W/'readiness-content.json').read_text())
def guide():return {'schemaVersion':2,'stateVersion':0,'fields':{},'flow':{'node':'R00','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'T01','invalidations':[],'scroll':0},'topics':{},'preferences':{'saveGuide':False,'saveSensitive':False,'noticeVersion':'guest-notice-2026-10-21-v1'}}
def ctx(id='RC01',**kw):return {'triggerId':id,'recordRevision':1,'eligibleIds':[id],'protectedIds':[],'pendingProposalId':None,'questionVariant':'standard',**kw}
def reply(id='RC01',choice='self',quote='myself',certainty='explicit',**kw):return {'reflection':'Thanks. I’ll keep this focused on you.','intent':'answer','confirmation':'not_requested','clarifying_question':'','fact_ids':[],'reports':[{'triggerId':id,'choice':choice,'quote':quote,'certainty':certainty,'details':[]}],**kw}
class ConversationTests(unittest.TestCase):
 def setUp(self):self.a=ReadinessConversation(C,F,D)
 def validate(self,value,message,context=None):self.a.local.context={**(context or ctx()),'details':{t['id']:t for t in D['triggers']}};return self.a.validate_output(value,message,guide(),[],['R00'],'owner')
 def test_clear_reply_is_report_without_extra_acceptance_card(self):
  r=self.validate(reply(),'This is for myself.');self.assertEqual(r['reports'][0]['value'],{'choice':'self'});self.assertIsNone(r['pendingProposalId'])
 def test_ambiguous_reply_gets_natural_confirmation_and_affirmation_commits(self):
  r=self.validate(reply(certainty='ambiguous'),'Maybe myself.');self.assertFalse(r['reports']);self.assertTrue(r['pendingProposalId']);c=ctx(pendingProposalId=r['pendingProposalId']);confirmed=self.validate(reply(reports=[],reflection='Got it.',confirmation='yes'),'Yes',c);self.assertEqual(confirmed['reports'][0]['value']['choice'],'self');self.assertIsNone(confirmed['pendingProposalId'])
 def test_established_fact_cannot_be_overwritten_without_affirmation(self):
  r=self.validate(reply(),'myself',ctx(protectedIds=['RC01']));self.assertFalse(r['reports']);c=ctx(pendingProposalId=r['pendingProposalId']);no=self.validate(reply(reports=[],confirmation='no'),'No',c);self.assertFalse(no['reports'])
 def test_unknown_pending_confirmation_is_deferred_instead_of_repeated(self):
  r=self.validate(reply(certainty='ambiguous'),'myself');c=ctx(pendingProposalId=r['pendingProposalId']);out=self.validate(reply(reports=[],intent='unknown',confirmation='unclear'),'Not sure',c);self.assertIsNone(out['pendingProposalId']);self.assertEqual(out['intent'],'unknown')
 def test_wrong_owner_stale_confirmation_and_untraceable_values_are_rejected(self):
  r=self.validate(reply(certainty='ambiguous'),'myself');c=ctx(recordRevision=2,pendingProposalId=r['pendingProposalId'])
  with self.assertRaises(ProfileError):self.validate(reply(reports=[],confirmation='yes'),'yes',c)
  with self.assertRaises(ModelUnavailable):self.validate(reply(quote='spouse'),'myself')
 def test_unsupported_coverage_promises_and_sources_are_rejected(self):
  for changes in [{'reflection':'You are eligible now.'},{'fact_ids':['made-up']},{'reports':[{'triggerId':'UNSUPPORTED','choice':'self','quote':'myself','certainty':'explicit','details':[]}]}]:
   with self.assertRaises(ModelUnavailable):self.validate(reply(**changes),'myself')
 def test_mocked_real_orchestration_uses_natural_contract_and_stays_bounded(self):
  seen=[]
  def transport(payload):seen.append(payload);return {'output':[{'content':[{'type':'output_text','text':json.dumps(reply())}]}]}
  a=ReadinessConversation(C,F,D,client=ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),enabled=True,max_calls=1);g=guide();old=copy.deepcopy(g);out=a.converse('owner','This is for myself.',g,ctx(),'synthetic-conversation-001');self.assertEqual(g,old);self.assertEqual(out['reports'][0]['value']['choice'],'self');self.assertIn('conversational assistant',seen[0]['instructions']);self.assertLess(len(json.dumps(seen[0]).encode()),24000);self.assertEqual(a.calls,1)
 def test_employer_variant_is_scoped_to_current_question(self):
  seen=[]
  def transport(payload):seen.append(payload);return {'output':[{'content':[{'type':'output_text','text':json.dumps(reply(reports=[],reflection='Thanks.'))}]}]}
  a=ReadinessConversation(C,F,D,client=ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),enabled=True,max_calls=1);a.converse('owner','I do not know.',guide(),ctx('RC10',questionVariant='employer100'),'synthetic-conversation-002');self.assertIn('100 or more employees',seen[0]['input'][0]['content'])
if __name__=='__main__':unittest.main()
