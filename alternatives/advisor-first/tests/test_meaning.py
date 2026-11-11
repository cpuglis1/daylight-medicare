"""Adversarial meaning checks: valid JSON must not create unsupported reports."""
import copy
import json
import unittest
import test_advisor as support
from situation import observations
from chat import ModelUnavailable
from guest_profiles import ProfileError

EXAMPLE="I've been retired for a few years, and am turning 65 in November."

class MeaningTests(unittest.TestCase):
    def setUp(self):
        self.case=support.AdvisorTests();self.case.setUp()

    def send(self,text,updates=(),task='timing',facts=()):
        self.case.scripted(text,list(updates),task=task)
        self.case.answer['fact_ids']=list(facts)
        return self.case.turn({'type':'message','message':text})

    def test_been_cannot_retrieve_a_plan_block(self):
        agent=self.case.flow.agent
        self.assertEqual(agent.retrieve(EXAMPLE,'R00'),[])
        self.assertEqual(agent.retrieve('What have you been doing?','R00'),[])
        self.assertEqual([x['id'] for x in agent.retrieve('What is Medicare Advantage?','R00')],['advantage'])

    def test_original_bad_inferences_are_filtered_and_real_details_preserved(self):
        update=self.case.update
        out=self.send(EXAMPLE,[update('RC01',{'choice':'self'},EXAMPLE),update('RC09',{'choice':'retiree'},EXAMPLE),update('T05',{'choice':'retiree'},EXAMPLE)])
        self.assertEqual(out['facts'],[])
        self.assertNotIn('Retiree coverage',json.dumps(out['review']))
        self.assertNotIn('work-to-Medicare',json.dumps(out['review']))
        self.assertEqual(out['guide']['fields'],{})
        self.case.accept(out)
        fields=self.case.g['fields']
        self.assertEqual(fields['situation.age65']['value'],{'month':11,'year':None})
        self.assertEqual(fields['situation.retirement']['value']['when'],'for a few years')
        self.assertNotIn('coverage.current',fields)
        self.assertNotIn('coverage.requestedStartMonth',fields)
        self.assertNotIn('RC09',self.case.r['facts'])
        self.assertEqual(self.case.flow.assess(self.case.g,self.case.r)['nextQuestion']['id'],'T05')
        self.assertNotIn('Job ends',json.dumps(self.case.flow.visual(self.case.g,self.case.r)))
        self.assertNotIn('Work insurance ends',json.dumps(self.case.flow.visual(self.case.g,self.case.r)))

    def test_irrelevant_unoffered_fact_is_rejected(self):
        with self.assertRaises(ModelUnavailable):self.send(EXAMPLE,facts=['checks'])

    def test_past_retirement_does_not_establish_a_timing_goal(self):
        text="I've been retired for several years."
        out=self.send(text)
        self.case.accept(out)
        self.assertEqual(self.case.r['conversation']['task'],'')
        self.assertNotIn('coverage.current',self.case.g['fields'])

    def test_birthday_is_not_a_desired_or_actual_coverage_start(self):
        text='I turn 65 in November 2026.'
        u=self.case.update
        out=self.send(text,[u('T04',{'choice':'month','month':'November 2026'},text),u('RC05',{'month':'November 2026'},text)])
        self.case.accept(out)
        self.assertNotIn('coverage.requestedStartMonth',self.case.g['fields'])
        self.assertNotIn('RC05',self.case.r['facts'])
        self.assertEqual(self.case.g['fields']['situation.age65']['value']['year'],2026)

    def test_explicit_retiree_insurance_remains_valid(self):
        text='My retiree insurance is through my former employer.'
        out=self.send(text,[self.case.update('T05',{'choice':'retiree'},text)])
        self.case.accept(out)
        self.assertEqual(self.case.g['fields']['coverage.current']['value'],['retiree'])
        self.assertEqual(self.case.r['facts']['RC09']['value']['choice'],'retiree')

    def test_no_medicare_does_not_mean_no_health_insurance(self):
        text='I do not have Medicare yet.'
        out=self.send(text,[self.case.update('T05',{'choice':'none'},text)],task='compare')
        self.assertNotIn('coverage.current',out['guide']['fields'])
        self.assertEqual(self.case.flow.agent.local.rejected,['T05'])

    def test_a_and_b_does_not_imply_original_delivery(self):
        text='I have Parts A and B through my Medicare Advantage plan.'
        u=self.case.update
        out=self.send(text,[u('T05',{'choice':'original,advantage'},text),u('RC04',{'choice':'both'},text)],task='review')
        self.case.accept(out)
        self.assertEqual(self.case.g['fields']['coverage.current']['value'],['advantage'])
        self.assertEqual(self.case.r['facts']['RC04']['value']['choice'],'both')

    def test_helper_and_hypothetical_observations_do_not_become_beneficiary_facts(self):
        self.assertEqual(observations('This is for my mom. I am retired.'),{})
        self.assertEqual(observations('If I turn 65 in November, what happens?'),{})
        self.assertEqual(observations('I turn 65 in November.',role='someone'),{})

    def test_genuine_situation_correction_invalidates_pending_preparation(self):
        self.case.accept(self.send(EXAMPLE))
        preparation=self.case.turn({'type':'review_preparation'})
        self.case.accept(self.send("I'm not retired; I am still working.",task=''))
        self.assertEqual(self.case.g['fields']['situation.retirement']['value']['status'],'working')
        with self.assertRaises(ProfileError):self.case.turn({'type':'run_preparation','token':preparation['review']['token']})

    def test_model_receives_all_question_meanings_and_no_prior_sensitive_values(self):
        self.case.ready_timing();self.case.choice('T06',text='Private Clinic Canary')
        self.send(EXAMPLE,task='')
        data=json.loads(self.case.calls[-1]['input'][0]['content'])
        context=data['confirmed_context']
        self.assertEqual(len(context['definitions']),41)
        self.assertEqual(len(context['question_catalog']),41)
        self.assertTrue(all(x['question'] for x in context['definitions']))
        self.assertIn('cannotInfer',context['question_catalog'][0])
        self.assertNotIn('Private Clinic Canary',json.dumps(context))
        self.assertNotIn('April 2027',json.dumps(context));self.assertNotIn('2027-04',json.dumps(context))

    def test_situation_schema_rejects_invented_month(self):
        g,r=self.case.flow.initial()
        self.case.flow.put(g,'situation.age65',{'month':13,'year':None},'user_choice')
        with self.assertRaises(ProfileError):self.case.flow.validate(g,r)

    def test_negated_retiree_insurance_is_not_positive_coverage(self):
        text='I do not have retiree insurance.'
        out=self.send(text,[self.case.update('T05',{'choice':'retiree'},text)],task='compare')
        self.assertNotIn('coverage.current',out['guide']['fields'])

    def test_insurance_question_is_not_an_insurance_report(self):
        text='What is retiree insurance?'
        out=self.send(text,[self.case.update('T05',{'choice':'retiree'},text)],task='learn')
        self.assertNotIn('coverage.current',out['guide']['fields'])

    def test_retired_ago_preserves_historical_status_not_an_end_date(self):
        self.assertEqual(observations('I retired three years ago.'),{'retirement':{'status':'retired','when':'three years ago'}})
        self.assertEqual(observations('I retired in 2020.'),{'retirement':{'status':'retired','when':'in 2020'}})

    def test_future_part_b_intention_cannot_be_mislabeled_as_current(self):
        text='I plan to start Part B in April 2027.'
        out=self.send(text,[self.case.update('RC05',{'month':'April 2027'},text)],task='')
        self.assertNotIn('RC05',out['record']['facts'])

    def test_needing_help_does_not_turn_a_birthday_into_desired_start(self):
        text='I turn 65 in November 2026 and need help understanding Medicare.'
        out=self.send(text,[self.case.update('T04',{'choice':'month','month':'November 2026'},text)])
        self.case.accept(out)
        self.assertNotIn('coverage.requestedStartMonth',self.case.g['fields'])

    def test_short_job_reply_reuses_the_active_insurance_question(self):
        self.case.task('timing');self.case.choice('RC01',choice='self');self.case.choice('T04',choice='month',month='April 2027')
        text='My current job.';u=self.case.update
        out=self.send(text,[u('T05',{'choice':'employer'},text),u('RC09',{'choice':'my_job'},text)],task='')
        self.case.accept(out)
        self.assertEqual(self.case.g['fields']['coverage.current']['value'],['employer'])
        self.assertEqual(self.case.r['facts']['RC09']['value']['choice'],'my_job')

