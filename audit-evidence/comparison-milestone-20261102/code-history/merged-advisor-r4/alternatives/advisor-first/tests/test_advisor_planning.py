"""Bounded advisor work beyond a missing-field queue; no paid calls."""
import copy
import unittest
import test_natural_flow as support
from guest_profiles import ProfileError
from natural_flow import CONTEXT_POLICY


class AdvisorPlanningTests(unittest.TestCase):
    setUp=support.NaturalFlowTests.setUp
    payload=support.NaturalFlowTests.payload
    take=support.NaturalFlowTests.take
    turn=support.NaturalFlowTests.turn
    message=support.NaturalFlowTests.message
    choice=support.NaturalFlowTests.choice
    task=support.NaturalFlowTests.task
    stage_payloads=support.NaturalFlowTests.stage_payloads
    extracted_context=support.NaturalFlowTests.extracted_context
    composed_context=support.NaturalFlowTests.composed_context
    update=staticmethod(support.NaturalFlowTests.update)
    extraction=staticmethod(support.NaturalFlowTests.extraction)

    @staticmethod
    def agenda(concerns=(),reason=None):
        return {'concerns':list(concerns),'priorityReason':reason or {
            'topic':'','reason':'','quote':'','subject':'beneficiary','scope':'current'}}

    @staticmethod
    def teaching(concept, evidence, visual='none'):
        return {'purpose':'teach','updates':[{'concept_id':concept,
            'depth':'introduced','reason':'new','evidence_refs':[evidence]}],
            'visual':visual}

    def test_novice_can_receive_one_reviewed_concept_with_the_useful_question(self):
        text='I turn 65 in November and I know very little about Medicare.'
        def compose(sent):
            move=next(item for item in sent['question_candidates'] if item['id']=='T05')
            return {'question_target':move['id'],'reply':'Medicare is federal health insurance.',
                'question':move['question']['question'],'evidence_refs':['basics'],
                'education':self.teaching('medicare_basics','basics')}
        out=self.message(text,[self.update('T02',{'choice':'new'},'I know very little about Medicare.')],compose=compose)
        self.assertEqual(out['advisor']['kind'],'teach')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertEqual(out['facts'],[])
        self.assertEqual(out['advisor']['teachingFactIds'],['basics'])
        self.assertTrue(out['advisor']['sources'][0]['url'].startswith('https://www.medicare.gov/'))
        self.assertEqual(self.r['conversation']['journey']['learningSeen'],['basics'])
        self.assertNotIn('needs.priorities',self.g['fields'])

    def test_explicit_concern_can_choose_teaching_without_another_intake_field(self):
        self.task('timing');self.choice('RC01',choice='self')
        text='I am worried about keeping my doctors.'
        concern={'topic':'doctors','subject':'beneficiary','scope':'current','status':'open','quote':text}
        def compose(sent):
            return {'question_target':None,'reply':'Doctor participation needs a separate check for each plan and office.',
                'question':'','evidence_refs':['checks'],
                'education':self.teaching('provider_checks','checks')}
        out=self.message(text,extraction=self.extraction(agenda=self.agenda([concern])),compose=compose)
        self.assertEqual(out['advisor']['kind'],'teach')
        self.assertEqual(out['advisor']['topic'],'doctors')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertEqual(self.flow.assess(self.g,self.r)['nextQuestion']['id'],'T04')
        self.assertNotIn('needs.priorities',self.g['fields'])
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])

    def test_optional_education_prompts_keep_the_practical_question_and_call_count(self):
        prompts=['How does prescription coverage work with each path?']
        def compose(sent):
            move=next(item for item in sent['question_candidates'] if item['id']=='T05')
            return {'question_target':move['id'],
                'reply':'Original Medicare and Medicare Advantage have different rules and costs.',
                'question':move['question']['question'], 'evidence_refs':['routesintro'],
                'education_followups':prompts,
                'education':self.teaching('coverage_paths','routesintro','routes')}
        before=len(self.calls)
        out=self.message('I turn 65 in November and want to understand my options.', compose=compose)
        self.assertEqual(out['advisor']['educationFollowups'],prompts)
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertEqual(len(self.calls)-before,2)
        self.assertFalse(out['assessment']['intakePaused'])
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertEqual(self.flow.memory.brief(self.owner,
            self.flow.current_chain[self.owner],CONTEXT_POLICY)['pending_question'],'T05')

    def test_explicit_concern_followup_uses_approved_meaning_and_retains_original_dependency(self):
        self.task('timing');self.choice('RC01',choice='self')
        text='I am worried about keeping my doctors.'
        concern={'topic':'doctors','subject':'beneficiary','scope':'current','status':'open','quote':text}
        def compose(sent):
            move=next(item for item in sent['question_candidates'] if item['id']=='T06')
            return {'question_target':move['id'],'reply':'','question':move['question']['question']}
        out=self.message(text,extraction=self.extraction(agenda=self.agenda([concern])),compose=compose)
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T06')
        self.message('No doctors to include.',[self.update('T06',{'choice':'none'},'No doctors to include.')])
        self.assertEqual(self.extracted_context()['activeQuestion']['id'],'T06')
        self.assertEqual(self.flow.value(self.g,'needs.providersStatus'),'none')
        self.assertEqual(self.flow.assess(self.g,self.r)['nextQuestion']['id'],'T04')

    def test_priority_revision_can_be_its_own_turn_with_stated_reason(self):
        self.task('timing');self.choice('RC01',choice='self');self.choice('T10',choice='total_cost')
        text='Keeping my doctors matters more now because switching doctors was difficult.'
        update=self.update('T10',{'choice':'doctors'},text,correction=True)
        reason={'topic':'doctors','reason':'switching doctors was difficult','quote':text,
                'subject':'beneficiary','scope':'current'}
        def compose(sent):
            return {'question_target':None,'reply':'We can put doctor access first in the checks we prepare.',
                'question':'','report_refs':['guide.needs.priorities']}
        out=self.message(text,extraction=self.extraction([update],agenda=self.agenda(reason=reason)),compose=compose)
        self.assertEqual(out['advisor']['kind'],'answer')
        self.assertIsNone(out['assessment']['nextQuestion'])
        stored=self.r['natural']['agenda']['priorityReasons'][0]
        self.assertEqual(stored['priorityRevision'],self.g['fields']['needs.priorities']['revision'])
        self.assertEqual(stored['reason'],reason['reason'])
        self.assertEqual(self.composed_context()['agenda']['priorityReasons'][0]['reason'],reason['reason'])
        self.assertFalse(out['assessment']['externalVerificationReady'])

    def test_malformed_agenda_enum_is_a_profile_error(self):
        g,r=self.flow.initial()
        r['natural']['agenda']={'version':1,'concerns':[{'topic':[], 'subject':'beneficiary',
            'scope':'current','status':'open','revision':0}],'priorityReasons':[],'lastMove':None}
        with self.assertRaises(ProfileError):self.flow.validate(g,r)

    def test_finite_insurance_answer_has_its_question_and_resolved_report_reference(self):
        self.task('timing');self.choice('RC01',choice='self')
        before=len(self.calls)
        out=self.turn({'type':'choice','id':'T05','fields':{'choice':'none'}},
                      aiConsent=True,contextPolicy=CONTEXT_POLICY)
        self.assertEqual([call['text']['format']['name'] for call in self.calls[before:]],
                         ['daylight_resolved_conversation'])
        submitted=self.composed_context()['submitted_answer']
        self.assertEqual(submitted['question_id'],'T05')
        self.assertEqual(submitted['question'],self.flow.question('T05')['question'])
        self.assertEqual(submitted['fields'],{'choice':'none'})
        self.assertEqual(submitted['report_refs'],['guide.coverage.current'])
        report=next(x for x in self.composed_context()['reports'] if x['id']==submitted['report_refs'][0])
        self.assertEqual(report['value'],['none'])
        self.assertEqual(out['generated']['status'],'complete')


if __name__=='__main__':unittest.main()
