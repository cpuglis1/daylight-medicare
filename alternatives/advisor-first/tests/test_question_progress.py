"""D176 profile/question lifecycle; explicit fictional meanings, no live calls."""
import unittest
import test_conversation_contract as contract
from timing_language import reported_end_date, end_date_supported, grounded_end_date
from guest_profiles import ProfileError
import conversation_planner
import question_progress
from adaptive_flow import metadata


class QuestionProgress(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads',
                 'extracted_context','composed_context','interpreted','ask','reply'):
        locals()[name] = getattr(contract.ConversationContract, name)
    update=staticmethod(contract.ConversationContract.update)
    extraction=staticmethod(contract.ConversationContract.extraction)
    def setUp(self):
        contract.ConversationContract.setUp(self)
        self.flow.agent.composition_recovery=True
        self.choice('RC01',choice='self')

    def work(self, text='Continue with the transition.', updates=(), target='RC11', **extra):
        return self.ask(text,task='timing',checks=['job_loss','payer_order'],
            updates=updates,target=target,**extra)

    def job(self):
        self.choice('T05',choice='employer'); self.choice('RC09',choice='my_job')

    def test_abbreviated_dates_are_captured_and_not_asked_again(self):
        self.job();self.work()
        text='My work finishes Apr 8, and my insurance finishes Apr. 30th.'
        out=self.work(text,[self.update('RC11',{'jobEnd':'Apr 8','coverageEnd':'April 30'},text)])
        self.assertEqual(self.flow.report(self.r,'RC11')['jobEnd'],'april 8')
        self.assertEqual(self.flow.report(self.r,'RC11')['coverageEnd'],'april 30')
        self.assertNotEqual(out['assessment']['nextQuestion']['id'],'RC11')
        self.assertNotIn('RC11',self.composed_context()['discussion_plan']['available_questions'])
        self.assertEqual(out['metrics']['llmCalls'],2)

    def test_unsupported_year_does_not_discard_the_reported_month_and_day(self):
        self.job();self.work()
        text='My job ends Sep 7 and insurance ends Sept. 30.'
        out=self.work(text,[self.update('RC11',{'jobEnd':'2028-09-07','coverageEnd':'2028-09-30'},text)])
        self.assertEqual(self.flow.report(self.r,'RC11')['jobEnd'],'september 7')
        self.assertEqual(self.flow.report(self.r,'RC11')['coverageEnd'],'september 30')
        self.assertNotIn('2028',str(self.flow.report(self.r,'RC11')))
        self.assertNotEqual(out['assessment']['nextQuestion']['id'],'RC11')

    def test_rejected_capture_cannot_force_same_question_forever(self):
        self.job();self.work()
        seen=[]
        for _ in range(4):
            out=self.work('That detail is complicated.',[],target='RC11')
            seen.append((out['assessment'].get('nextQuestion') or {}).get('id'))
        self.assertLessEqual(seen.count('RC11'),1) # first ask already delivered
        self.assertTrue(any(i.get('question_id')=='RC11' and i['state']=='parked'
            for i in out['questionProgress']))
        self.assertFalse(self.flow.report(self.r,'RC11'))

    def test_partial_answer_asks_only_missing_field(self):
        self.job();self.work()
        text='My last workday is Feb. 12.'
        out=self.work(text,[self.update('RC11',{'jobEnd':'February 12'},text)])
        self.assertEqual(self.flow.report(self.r,'RC11')['jobEnd'],'february 12')
        self.assertEqual([f['key'] for f in out['assessment']['nextQuestion']['fields']],['coverageEnd'])
        self.assertNotIn('job end',out['assessment']['nextQuestion']['question'].lower())

    def test_known_and_unknown_subfields_are_both_addressed(self):
        self.job();self.work()
        text='My job ends June 16. I do not know when my insurance ends.'
        out=self.work(text,[self.update('RC11',{'jobEnd':'June 16','coverageEnd':'unknown'},text)])
        self.assertEqual(self.flow.report(self.r,'RC11')['jobEnd'],'june 16')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'),'RC11')
        row=next(r for r in out['questionProgress'] if r['question_id']=='RC11')
        self.assertEqual(row['fields'],{'jobEnd':'reported','coverageEnd':'unknown'})
        self.assertEqual(row['state'],'addressed')

    def test_later_answer_and_correction_work_after_parking(self):
        self.job();self.work();self.work('Continue with what is available.')
        self.work('We can leave that open for now.')
        text='My job ends Oct. 11 and my insurance ends Oct. 31.'
        self.work(text,[self.update('RC11',{'jobEnd':'October 11','coverageEnd':'October 31'},text)])
        text='Correction: my insurance ends November 30, 2027.'
        out=self.work(text,[self.update('RC11',{'coverageEnd':'2027-11-30'},text,correction=True)])
        report=self.flow.report(self.r,'RC11')
        self.assertEqual(report['jobEnd'],'october 11')
        self.assertEqual(report['coverageEnd'],'2027-11-30')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'),'RC11')
        self.assertFalse(any(row['state']=='parked' and row['question_id']=='RC11' for row in out['questionProgress']))

    def test_question_eligibility_uses_profile_without_ask_history(self):
        self.job();self.choice('RC11',jobEnd='August 12',coverageEnd='August 31')
        candidate={'id':'RC11','question':self.flow.question('RC11',['jobEnd','coverageEnd'])}
        self.assertEqual(question_progress.filter_candidates(self.flow,self.owner,self.g,self.r,[candidate],{}),[])
        metadata(self.r)['editing']='RC11'
        self.assertEqual(len(question_progress.filter_candidates(self.flow,self.owner,self.g,self.r,[candidate],{})),1)

    def test_backend_progress_is_supplied_to_both_model_stages(self):
        self.job();self.work();self.work('Continue with the other details.')
        self.assertTrue(self.extracted_context()['question_progress'])
        self.assertTrue(self.composed_context()['question_progress'])

    def test_receipt_replay_does_not_spend_another_question_attempt(self):
        self.job()
        text='Continue with the transition.'
        payload=self.payload({'type':'message','message':text})
        self.extractions.append(self.interpreted(text,task='timing',checks=['job_loss']))
        first=self.take(payload)
        calls=len(self.calls)
        replay=self.take(payload)
        self.assertEqual(len(self.calls),calls)
        self.assertEqual(first['questionProgress'],replay['questionProgress'])
        self.assertEqual(next(r for r in replay['questionProgress'] if r['question_id']=='RC11')['shown'],1)

    def test_composer_cannot_ask_an_already_stored_meaning(self):
        self.choice('T09',choice='predictable')
        out=self.message('Continue the comparison.',extraction=self.interpreted('Continue the comparison.',task='compare'),
            compose={'reply':'We can continue with the next useful detail.',
                     'question_target':'T09','question':'How would you balance monthly costs and care costs?'})
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'),'T09')
        self.assertEqual(self.flow.value(self.g,'needs.costPreference'),'predictable')

    def test_different_entities_have_separate_field_progress(self):
        self.flow.fact(self.r,'RC22',{'items':[{'entity':'medicine-1','name':'Fictional tablet',
                                              'strength':'5 mg','form':'tablet'}]},'user_choice')
        q=self.flow.question('RC22',['name','strength','form'],'medicine-2')
        p=question_progress.project(self.flow,self.g,self.r,q)
        self.assertEqual(p['open_fields'],['name','strength','form'])
        q=self.flow.question('RC22',['name','strength','form'],'medicine-1')
        self.assertFalse(question_progress.project(self.flow,self.g,self.r,q)['open_fields'])

    def test_new_missing_field_gets_its_own_repeat_allowance(self):
        self.job();self.work();self.work('Continue.')
        text='My job ends July 12.'
        out=self.work(text,[self.update('RC11',{'jobEnd':'July 12'},text)])
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
        self.assertEqual([f['key'] for f in out['assessment']['nextQuestion']['fields']],['coverageEnd'])
        out=self.work('Continue with the available information.')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
        out=self.work('Continue with the available information.')
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'),'RC11')


class DateNotation(unittest.TestCase):
    def test_standard_month_notation_preserves_precision(self):
        cases=[('Jan 3rd','january 3'),('Jan. 3','january 3'),('FEB 9','february 9'),
            ('Mar. 15th','march 15'),('Apr 8','april 8'),('Apr. 30th','april 30'),
            ('May 19','may 19'),('Jun 4','june 4'),('Jul. 2nd','july 2'),
            ('Aug 6','august 6'),('Sep 7','september 7'),('Sept. 30','september 30'),
            ('Oct 21st','october 21'),('Nov. 18','november 18'),('Dec 31st','december 31')]
        for raw,expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(reported_end_date(raw),expected)
                self.assertTrue(end_date_supported(expected,'The reported date is '+raw+'.'))

    def test_precision_recovery_cannot_change_a_stated_year_or_day(self):
        for proposed,quote in [('2028-04-08','April 8, 2027'),('2028-04-08','Apr 9'),
                               ('2028-04','Apr 8 and Apr 30'),('2028-02-30','Feb 30')]:
            with self.subTest(proposed=proposed,quote=quote), self.assertRaises(ProfileError):
                grounded_end_date(proposed,quote)
        self.assertEqual(grounded_end_date('2027-04-08','Apr. 8, 2027'),'2027-04-08')
        self.assertTrue(end_date_supported('april 8','Apr 8, and another date.'))


if __name__=='__main__':unittest.main()
