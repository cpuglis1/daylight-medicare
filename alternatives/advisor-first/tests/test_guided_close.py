"""D180 real controller, fictional reports, explicit model outputs, no network."""
import copy
import unittest
import test_quiet_recovery as fixture
import journey_completion as close
import conversation_planner as planner
from guest_profiles import ProfileError
from plans_context import rehydrate, NAVIGATION
from plans_service import PlansService


class GuidedClose(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads',
                 'extracted_context','composed_context','interpreted','ask','draft'):
        locals()[name]=getattr(fixture.QuietRecovery,name)
    update=staticmethod(fixture.QuietRecovery.update)
    extraction=staticmethod(fixture.QuietRecovery.extraction)

    def setUp(self):
        fixture.QuietRecovery.setUp(self)
        self.flow.guided_close=True

    def fill(self,omit=()):
        self.flow.guided_close=False  # Pre-existing profile, before the first guided turn.
        for identifier,fields in [('RC01',{'choice':'self'}),('T01',{'choice':'compare'}),
            ('T03',{'zip':'34102'}),('T05',{'choice':'employer'}),('RC04',{'choice':'neither'}),
            ('T06',{'choice':'none'}),('T07',{'choice':'no'}),('T08',{'choice':'local'}),
            ('T09',{'choice':'predictable'}),('T10',{'choice':'doctors'}),
            # D181: a close that points to Medigap asks its price details first.
            ('MG_AGE',{'choice':'66'}),('MG_SEX',{'choice':'Female'}),('MG_TOBACCO',{'choice':'Non-Tobacco'})]:
            if identifier not in omit:self.choice(identifier,**fields)
        self.flow.guided_close=True

    def work(self,text='Please help me compare these options.'):
        return self.message(text,extraction=self.interpreted(text,task='compare'),
            compose=self.draft('We can use your priorities to focus the comparison.'))

    def test_automatic_close_review_handoff_without_extra_calls_or_choice(self):
        self.fill()
        out=self.work()
        self.assertEqual(out['metrics']['llmCalls'],2)
        self.assertTrue(out['comparisonClose']['show'])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['profileProgress']['addressed'],11)
        self.assertEqual(out['profileProgress']['total'],11)
        self.assertIsNone(out['comparisonClose']['recommendation'])
        # D181: doctors + predictable costs with Medigap prices ready opens Medigap first.
        self.assertEqual(out['comparisonClose']['destination'],'supplement')
        self.assertIsNotNone(self.composed_context()['closing_brief'])
        self.assertEqual(out['coveragePath']['state'],'undecided')
        before=len(self.calls)
        review=self.turn({'type':'review_plans'},aiConsent=False)['review']
        handoff=self.turn({'type':'confirm_plan_review','token':review['token']},aiConsent=False)['plansHandoff']
        self.assertEqual(len(self.calls),before)
        self.assertFalse(handoff['personalRecommendationAllowed'])
        self.assertEqual(len(handoff['profile']['questions']),41)
        self.assertFalse(self.work('What should we compare first?')['comparisonClose']['show'])

    def test_unknown_counts_as_addressed_and_stays_open_in_close(self):
        self.fill(omit={'T09'})
        before=close.progress(self.flow,self.g,self.r)
        self.turn({'type':'edit','id':'T09'},aiConsent=False)
        self.turn({'type':'unknown','id':'T09'},aiConsent=False)
        self.turn({'type':'resume'},aiConsent=False)
        out=self.work()
        self.assertEqual(before['addressed'],10)
        self.assertEqual(out['profileProgress']['addressed'],11)
        self.assertIn('Monthly payments and care costs',out['comparisonClose']['open'])

    def test_learning_and_timing_do_not_impose_comparison_progress(self):
        for task in ('','timing'):
            out=self.message('Help me understand the next step.',
                extraction=self.interpreted('Help me understand the next step.',mode='discuss',task=task),
                compose=self.draft('We can go through the details together.'))
            self.assertFalse(out['profileProgress']['active'])
            self.assertNotIn('comparisonClose',out)

    def test_correction_invalidates_review_and_updates_closing(self):
        self.fill();out=self.work();revision=out['comparisonClose']['revision']
        review=self.turn({'type':'review_plans'},aiConsent=False)['review']
        self.turn({'type':'edit','id':'T09'},aiConsent=False)
        out=self.turn({'type':'choice','id':'T09','fields':{'choice':'lower_monthly'}},aiConsent=False)
        self.assertNotEqual(out['comparisonClose']['revision'],revision)
        self.assertTrue(out['comparisonClose']['show'])
        with self.assertRaises(ProfileError):self.turn({'type':'confirm_plan_review','token':review['token']},aiConsent=False)

    def test_checks_fold_only_unchanged_results_and_reopen_changed_evidence(self):
        self.fill();out=self.work();s=planner.state(self.flow,self.owner)
        out['conversationCheck']={'results':[{'key':'doctor:a','kind':'doctor_matrix','name':'Fictional Doctor','plans':{}}]}
        close.attach(self.flow,self.owner,out,s)
        self.assertEqual(out['conversationCheck']['compactResults'],[])
        close.attach(self.flow,self.owner,out,s)
        self.assertEqual(out['conversationCheck']['compactResults'],['doctor:a'])
        out['conversationCheck']['results'][0]['plans']={'test':{'state':'unknown'}}
        close.attach(self.flow,self.owner,out,s)
        self.assertEqual(out['conversationCheck']['compactResults'],[])

    def test_requested_pause_has_summary_and_preserves_missing_work(self):
        self.choice('RC01',choice='self')
        self.choice('T01',choice='compare')
        text='Let us stop here for now.'
        out=self.message(text,extraction=self.interpreted(text,mode='pause',task='compare'),
            compose=self.draft('We can continue when you are ready.'))
        cards=[c for c in out['cards'] if c['kind']=='guided_summary']
        self.assertEqual(len(cards),1)
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(cards[0]['open'])
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_navigation_is_validated_send_context_not_preference(self):
        service=PlansService(self.flow);view=service.workspace(self.owner)
        request=dict(version='plans-context-v1',reviewToken=None,viewDigest=view['view_digest'],
                     visibleIds=[],comparedIds=[],selectedId=None,field=None,mode='all')
        before=copy.deepcopy(self.g)
        for nav in NAVIGATION:
            context=rehydrate(service,self.owner,{**request,'navigation':nav},None)
            self.assertEqual(context['navigation']['view'],nav)
            self.assertTrue(context['navigation']['attention_is_not_preference'])
            self.assertFalse(context['plans'])
        self.assertEqual(self.g,before)
        for nav in ('invented',{'step':'<script>'}):
            with self.assertRaises(ProfileError):rehydrate(service,self.owner,{**request,'navigation':nav},None)
        with self.assertRaises(ProfileError):rehydrate(service,self.owner,
            {**request,'navigation':'supplement','selectedId':view['plans'][0]['id']},None)

    def test_review_receipt_survives_detour_but_not_a_report_correction(self):
        self.fill();self.work()
        review=self.turn({'type':'review_plans'},aiConsent=False)['review']
        receipt=self.turn({'type':'confirm_plan_review','token':review['token']},aiConsent=False)['plansHandoff']
        text='Explain the page I am looking at.'
        self.message(text,extraction=self.interpreted(text,mode='detour'),
                     compose=self.draft('We can work through this step.'))
        resolved=self.flow.resolve_plans_handoff(self.owner,receipt['token'])
        self.assertEqual(resolved['inputDigest'],receipt['inputDigest'])
        self.assertFalse(resolved['personalRecommendationAllowed'])
        self.turn({'type':'edit','id':'T09'},aiConsent=False)
        self.choice('T09',choice='lower_monthly')
        with self.assertRaises(ProfileError):self.flow.resolve_plans_handoff(self.owner,receipt['token'])

    def checks_fixture(self,multiple=False):
        from behavioral_offline_server import Doctors,Drugs
        from conversation_checks import ConversationChecks
        from daylight_data.serving.binding import ResearchServingError
        class Directory(Doctors):
            stopped=False
            def sites(self,**query):
                result=super().sites(**query)
                if multiple:
                    # Same address text is not proof that two source office IDs are one.
                    result['sites'].append({**copy.deepcopy(result['sites'][0]),'site_id':'second-office'})
                return result
            def network_matrix(self,*args):
                if self.stopped:raise ResearchServingError('PILOT_SOURCE_STOP')
                return super().network_matrix(*args)
        self.choice('RC01',choice='self');self.choice('T03',zip='34102')
        self.directory=Directory([])
        self.checks=ConversationChecks(self.flow,self.directory,Drugs(),lambda:[])
        return self.checks

    def check_answer(self,value):
        q=self.checks.visits[self.owner]['question']
        self.checks.answer(self.owner,self.g,self.r,q['token'],value)
        return self.checks.reconcile(self.owner,self.g,self.r)

    def test_distinct_office_ids_need_choice_and_confirmed_identity_survives_outage(self):
        self.checks_fixture(multiple=True);self.choice('T06',text='Dr. Nera Vale in Naples')
        first=self.checks.reconcile(self.owner,self.g,self.r)
        second=self.check_answer(first['question']['choices'][0]['value'])
        self.assertEqual(second['question']['field'],'office')
        ids=[c['value'] for c in second['question']['choices'] if not c['value'].startswith('__')]
        self.assertEqual(len(set(ids)),2)
        selected=self.check_answer('second-office')
        self.assertEqual(selected['results'][0]['kind'],'doctor_matrix')
        self.choice('T09',choice='predictable')
        self.assertIsNone(self.checks.reconcile(self.owner,self.g,self.r)['question'])
        self.directory.stopped=True
        held=self.checks.reconcile(self.owner,self.g,self.r)
        self.assertFalse(held['results']);self.assertEqual(held['question']['field'],'doctor_retry')
        self.directory.stopped=False
        recovered=self.checks.reconcile(self.owner,self.g,self.r)
        self.assertIsNone(recovered['question'])
        detail=next(iter(self.checks.visits[self.owner]['doctors'].values()))
        self.assertEqual(detail['office']['site_id'],'second-office')

    def test_exact_medicine_is_retained_and_explicit_edit_reopens_only_that_check(self):
        self.checks_fixture();self.choice('T07',text='metformin')
        first=self.checks.reconcile(self.owner,self.g,self.r)
        self.assertEqual(first['question']['field'],'formulary_product')
        selected=self.check_answer(first['question']['choices'][0]['value'])
        self.assertTrue(any(r['kind']=='formulary' for r in selected['results']))
        self.choice('T09',choice='predictable')
        again=self.checks.reconcile(self.owner,self.g,self.r)
        self.assertNotEqual((again.get('question') or {}).get('field'),'formulary_product')
        self.checks.edit(self.owner,self.g,self.r,'formulary','products')
        edited=self.checks.reconcile(self.owner,self.g,self.r)
        self.assertEqual(edited['question']['field'],'formulary_product')
        self.assertFalse(any(r['kind']=='formulary' for r in edited['results']))


if __name__=='__main__':unittest.main()
