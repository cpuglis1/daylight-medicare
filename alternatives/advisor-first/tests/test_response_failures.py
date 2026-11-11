"""Regression of the retained fictional failed reply and preflight HTTP gates."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import test_natural_agent as fixtures
import test_provider_http as http_fixtures
import test_natural_flow as flow_fixtures
from chat import ModelUnavailable
from natural_flow import CONTEXT_POLICY
from provider_tokens import TokenCountUnavailable
from natural_agent import (COMPOSITION_TEXT_BOUND, COMPOSITION_REPLY_BOUND,
    COMPOSITION_QUESTION_BOUND, COMPOSE_INSTRUCTIONS)


class QuestionRecoveryTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.NaturalAgentTests()
        fixture.setUp()
        self.agent=fixture.agent
        self.fixture=json.loads((HERE/'tests/fixtures/response-failure-20261103.json').read_text())
        self.value=self.fixture['raw_proposal']
        self.context=self.fixture['context']
        self.moves=self.fixture['candidates']

    def test_exact_failed_live_proposal_is_grounded_by_the_persons_own_words(self):
        # November 3 live failure: the question named "Collier County", which the
        # person had just typed. Own-words grounding (Nov 9) makes a name the
        # person stated echoable, so the question is kept and nothing is replaced.
        core={key:value for key,value in self.value.items() if key not in {'education','education_followups','task_work'}}
        self.agent._validate_composition_core(core,self.context,self.moves)
        before=copy.deepcopy(self.value)
        out=self.agent.validate_composition(self.value,self.context,self.moves)
        self.assertEqual(out['reply'],self.value['reply'])
        self.assertEqual(out['question'],self.value['question'])
        self.assertNotIn('validation_recovery',out)
        self.assertEqual(self.value,before)

    def test_a_county_the_person_never_named_still_fails_the_question_and_recovers_it(self):
        value=copy.deepcopy(self.value)
        value['question']=value['question'].replace('Collier County','Lee County')
        core={key:item for key,item in value.items() if key not in {'education','education_followups','task_work'}}
        with self.assertRaisesRegex(ModelUnavailable,'named entity'):
            self.agent._validate_composition_core(core,self.context,self.moves)
        out=self.agent.validate_composition(value,self.context,self.moves)
        self.assertEqual(out['reply'],value['reply'])
        self.assertEqual(out['question'],self.moves[0]['question']['question'])
        self.assertEqual(out['validation_recovery']['reason'],'ungrounded_entity')

    def test_bad_answer_still_fails_after_question_recovery(self):
        value={**self.value,'reply':'Dr Fabricated Name participates in your exact plan.'}
        with self.assertRaises(ModelUnavailable):
            self.agent.validate_composition(value,self.context,self.moves)

    def test_absent_or_invalid_target_never_infers_an_answer(self):
        out=self.agent.validate_composition({**self.value,'question_target':None},self.context,self.moves)
        self.assertIsNone(out['question_target'])
        self.assertNotIn('validation_recovery',out)
        with self.assertRaises(ModelUnavailable):
            self.agent.validate_composition({**self.value,'question_target':'NOT-APPROVED'},self.context,self.moves)

    def test_invalid_source_never_becomes_a_valid_answer(self):
        with self.assertRaises(ModelUnavailable):
            self.agent.validate_composition({**self.value,'evidence_refs':['unreviewed']},self.context,self.moves)

    def test_exact_live_public_term_with_quantifier_is_not_an_invented_name(self):
        packet=HERE.parents[1]/'audit-evidence/live-sample-conversations-20261103/20261103T104504-0500-cc5c1f'
        capture=json.loads((packet/'provider_and_costs-turn-3-composition.json').read_text())
        out=self.agent.validate_composition(capture['raw_proposal'],capture['resolved_context'],capture['candidates'])
        self.assertIn('Most Advantage plans',out['reply'])
        self.assertEqual(out['reply'],capture['raw_proposal']['reply'])
        for name in ('Most Blue Cross','Many Fabricated Insurance'):
            with self.subTest(name=name),self.assertRaises(ModelUnavailable):
                self.agent.validate_composition({**self.value,'reply':name+' is your coverage.'},self.context,self.moves)


class PreflightHttpTests(unittest.TestCase):
    def setUp(self):
        self.http=http_fixtures.ProviderHttpTests()
        self.http.setUp()
        self.addCleanup(self.http.doCleanups)

    def send(self):
        h=self.http
        payload={'guide':copy.deepcopy(h.state['guide']),'record':copy.deepcopy(h.state['record']),
            'requestId':str(uuid.uuid4()),'action':{'type':'message','message':'I need help for myself.'},
            'aiConsent':True,'contextPolicy':CONTEXT_POLICY}
        if h.state.get('continuation'):
            payload['continuation']=h.state['continuation']
        return h.request('/api/conversation/turn',payload)

    def fail_count(self,*_):
        raise TokenCountUnavailable({'phase':'preflight','exception':'ProviderTransportError',
                                     'curl_exit_code':35,'transport_category':'tls'})

    def test_extraction_preflight_does_not_issue_or_charge_generation(self):
        h=self.http
        h.service.adaptive.agent.count_tokens=self.fail_count
        status,out=self.send()
        self.assertEqual(status,503,out)
        self.assertIn('connection check',out['error'])
        self.assertNotIn('daily',out['error'])
        self.assertEqual(h.calls,[])
        with h.service.budget.db() as db:
            rows=db.execute("SELECT status,charged FROM ai_charges WHERE id NOT LIKE 'approved-smoke-%'").fetchall()
        self.assertEqual(rows,[('cancelled',0)]*2)

    def test_composition_preflight_retains_reports_counts_only_actual_stage_and_never_retries(self):
        h=self.http
        calls=[]
        def count(client,payload):
            calls.append(payload['text']['format']['name'])
            return 1000 if len(calls)==1 else self.fail_count()
        h.service.adaptive.agent.count_tokens=count
        text='I need help for myself.'
        h.extractions.append({'updates':[h.update('RC01',{'choice':'self'},text)],
            'requests':[],'fact_ids':[],'agenda':{'concerns':[],'priorityReason':{}},
            'situation_proposals':[],'goal_quote':''})
        status,out=self.send()
        self.assertEqual(status,200,out)
        self.assertEqual(out['generated']['code'],'input_token_verification')
        self.assertEqual(out['generated']['preflight']['transport_category'],'tls')
        self.assertIn('connection check',out['notice'])
        self.assertEqual(out['guide']['fields']['subject.role']['value'],'self')
        self.assertEqual(out['metrics']['llmCalls'],1)
        self.assertEqual(len(h.calls),1)
        self.assertEqual(len(calls),2)
        with h.service.budget.db() as db:
            rows=db.execute("SELECT status,charged FROM ai_charges WHERE id NOT LIKE 'approved-smoke-%'").fetchall()
        self.assertEqual([row[0] for row in rows],['settled','cancelled'])
        self.assertEqual(rows[1][1],0)


class GenerationContractTests(unittest.TestCase):
    def test_provider_field_bounds_fit_the_existing_combined_validator(self):
        fixture=fixtures.NaturalAgentTests()
        fixture.setUp()
        fixture.answer=fixture.composition()
        fixture.compose()
        properties=fixture.calls[-1]['text']['format']['schema']['properties']
        self.assertEqual(properties['reply']['maxLength'],COMPOSITION_REPLY_BOUND)
        self.assertEqual(properties['question']['maxLength'],COMPOSITION_QUESTION_BOUND)
        self.assertLessEqual(properties['reply']['maxLength']+properties['question']['maxLength']+1,
                             COMPOSITION_TEXT_BOUND)
        self.assertIn(str(COMPOSITION_REPLY_BOUND),COMPOSE_INSTRUCTIONS)

    def test_the_retained_oversize_summary_still_fails_the_original_guard(self):
        path=HERE.parents[1]/'audit-evidence/live-sample-conversations-20261103/20261103T102514-0500-cbe9ae/caregiver_and_coverage-turn-6-composition.json'
        value=json.loads(path.read_text())
        fixture=fixtures.NaturalAgentTests()
        fixture.setUp()
        with self.assertRaisesRegex(ModelUnavailable,'text allowance'):
            fixture.agent.validate_composition(value['raw_proposal'],value['resolved_context'],[])


class LocationDependencyTests(unittest.TestCase):
    def test_exact_four_extractions_allow_a_grounded_zip_acknowledgment(self):
        packet=HERE.parents[1]/'audit-evidence/live-sample-conversations-20261103/20261103T103012-0500-a7b59b'
        result=json.loads((packet/'result.json').read_text())
        fixture=flow_fixtures.NaturalFlowTests()
        fixture.setUp()
        fixture.turn({'type':'start'})
        for row in result['cases'][0]['turns']:
            number=row['turn']
            interpreted=json.loads((packet/f'provider_and_costs-turn-{number}-interpretation.json').read_text())
            composed=json.loads((packet/f'provider_and_costs-turn-{number}-composition.json').read_text())
            proposal=composed['raw_proposal'] if number < 4 else {
                'question_target':None,'question':'',
                'reply':'The office correction is here, and the home ZIP is 34102.',
                'report_refs':['guide.comparison.scope.zip','readiness.RC21.doctor-1.city']}
            out=fixture.message(row['user'],extraction=interpreted['raw_proposal'],compose=proposal)
            self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
            pending=fixture.flow.pending_for(fixture.owner)
            if pending:
                self.assertNotIn('T03',[u['id'] for u in [pending['update'],*pending.get('remaining',[])]])
        self.assertEqual(out['guide']['fields']['comparison.scope.zip']['value'],'34102')
        reports={r['id']:r for r in fixture.composed_context()['reports']}
        self.assertEqual(reports['guide.comparison.scope.zip']['value'],'34102')
        self.assertEqual(reports['readiness.RC21.doctor-1.city']['value'],'Bonita Springs')
        self.assertEqual(out['reply'].split('\n\n')[0],proposal['reply'])
        self.assertEqual(out['guide']['fields']['needs.priorities']['value'],['doctors','total_cost'])

    def test_exact_reported_doctor_name_survives_office_detail_and_city_correction(self):
        packet=HERE.parents[1]/'audit-evidence/live-sample-conversations-20261103/20261103T103820-0500-6d597a'
        result=json.loads((packet/'result.json').read_text())
        fixture=flow_fixtures.NaturalFlowTests()
        fixture.setUp()
        fixture.turn({'type':'start'})
        for row in result['cases'][0]['turns']:
            number=row['turn']
            interpreted=json.loads((packet/f'provider_and_costs-turn-{number}-interpretation.json').read_text())
            composed=json.loads((packet/f'provider_and_costs-turn-{number}-composition.json').read_text())
            proposal=copy.deepcopy(composed['raw_proposal']) if number == 1 else {
                'question_target':None,'question':'',
                'reply':'The reported doctor is Dr. Maya Reed at Cypress Heart Clinic in Naples.',
                'report_refs':['guide.needs.providers','readiness.RC21.doctor-1.practice',
                               'readiness.RC21.doctor-1.city']}
            out=fixture.message(row['user'],extraction=interpreted['raw_proposal'],compose=proposal)
            self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        text=fixture.g['fields']['needs.providers']['value']
        self.assertIn('Dr. Maya Reed',text)
        self.assertIn('Cypress Heart Clinic',text)
        correction='Actually, the office is in Bonita Springs, not Naples.'
        fixture.message(correction,[fixture.update('RC21',{'city':'Bonita Springs'},correction,
            entity='doctor-1',correction=True)],compose={'question_target':None,'question':''})
        text=fixture.g['fields']['needs.providers']['value']
        self.assertIn('Dr. Maya Reed',text)
        self.assertIn('Bonita Springs',text)
        self.assertNotIn('Naples',text)
