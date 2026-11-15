"""Fictional inputs with separate synthetic and real-local-source test classes.

Full supported-cost journey supplements the six profile replays. Their missing
refill dates, quantities and source holds are not filled in with invented facts.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_profile_replay_20261114 import Replays
from conversation_checks import ConversationChecks
from daylight_data.serving.part_d_local import local_candidate
from daylight_data.serving.pilot_doctors import PilotDoctors
from daylight_data.serving.binding import ResearchServingError
import recommendation_engine as engine
from test_recommendation_engine import inputs, part_d

ROOT = Path(__file__).resolve().parents[3]


class ResearchJourney(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context','composed_context'):
        locals()[name] = getattr(Replays, name)
    update = staticmethod(Replays.update)
    extraction = staticmethod(Replays.extraction)
    proposal = staticmethod(Replays.proposal)
    setUp = Replays.setUp

    def attach_sources(self):
        self.service = local_candidate(ROOT)
        self.controller = ConversationChecks(self.flow, PilotDoctors(self.service.foundation), self.service, lambda: [])
        self.flow.conversation_checks = self.controller

    def answer(self, value):
        q = self.controller.visits[self.owner]['question']
        return self.turn({'type':'check_answer','token':q['token'],'value':value}, aiConsent=False)

    def test_cost_comparison_from_words_reaches_all_ten_plans_and_correction_withdraws(self):
        self.attach_sources()
        text = 'I want to compare drug plan costs. I have Original Medicare and a drug plan. I live in 34102.'
        out = self.message(text, [self.update('RC01', {'choice':'self'}, text),
            self.update('T05', {'choice':'original,drug'}, text), self.update('T03', {'zip':'34102'}, text)])
        text = 'I take Metformin.'
        self.message(text, [self.update('T07', {'text':'Metformin'}, text)])
        text = 'Metformin 500 mg tablets. I fill 30 tablets every 30 days at Publix in Naples, FL 34102, retail. I have no help with drug costs.'
        out = self.message(text, [
            self.update('RC22', {'name':'Metformin','strength':'500 mg','form':'tablet'}, text, entity='medicine-1'),
            self.update('RC23', {'quantity':'30 tablets','daysSupply':'30','pharmacy':'Publix in Naples, FL 34102','channel':'retail'}, text, entity='medicine-1'),
            self.update('RC18', {'choice':'none'}, text)])
        seen = []
        for _ in range(12):
            q = self.controller.visits[self.owner]['question']
            if not q: break
            seen.append(q['field'])
            answers = {'formulary_product':'861007', 'rxcui':'861007', 'fills':[{'date':'2026-12-01','order':1}],
                       'period':'2026-12-01', 'prior_spending':'confirmed_zero', 'outlet_zip':'34102', 'channel':'retail', 'assistance':'none'}
            if q['field']=='pharmacy':
                match = next((c for c in q['choices'] if c['value'].endswith(':1841534534')), None)
                self.assertIsNotNone(match, q)
                value = match['value']
            else:
                self.assertIn(q['field'], answers, q)
                value = answers[q['field']]
            out = self.answer(value)
        results = self.controller.reconcile(self.owner,self.g,self.r)['results']
        compared = next(r for r in results if r['kind']=='drug_comparison')
        self.assertEqual(len(compared['plans']),10)
        self.assertTrue(any(r['state']=='offline_average_candidate' for r in compared['plans'].values()))
        self.assertNotIn('drug_plan', seen)
        self.assertEqual(out['conversationPlanner']['plans_view'],'part-d')
        self.assertFalse(self.flow.value(self.g,'intent.coveragePath'))
        # The real sorting consumes the comparison, never a client's amount.
        ids = list(compared['plans'])
        ordered = engine.evaluate_part_d(inputs(medicines='yes'),part_d(*[(i,100,100) for i in ids]),drug_costs=compared['plans'])
        self.assertEqual(ordered['recommended_ids'],[])
        for identifier,row in compared['plans'].items():
            if row['state']!='offline_average_candidate': self.assertIsNone(ordered['plans'][identifier]['rank'])
        target=os.environ.get('PROFILE_REPLAY_OUTPUT')
        if target:
            Path(target,'supported-cost-journey.json').write_text(json.dumps({'scripted_language':True,'synthetic_evidence':isinstance(self.service,FictionalDrugService),'questions':seen,'result':compared,'sorting':ordered},indent=2)+'\n')
        self.turn({'type':'check_edit','key':'drug','field':'pharmacy'},aiConsent=False)
        self.assertFalse(any(r['kind']=='drug_comparison' for r in self.controller.reconcile(self.owner,self.g,self.r)['results']))
        with patch.object(self.service,'_scope',side_effect=ResearchServingError('PILOT_SOURCE_STOP')):
            self.assertFalse(self.controller.reconcile(self.owner,self.g,self.r)['results'])

    def test_PP13_ambiguous_doctor_is_not_silently_selected(self):
        self.attach_sources()
        text='I live in 34103. Check Dr. Albagdadi at the NCH heart institute.'
        out=self.message(text,[self.update('RC01',{'choice':'self'},text),self.update('T03',{'zip':'34103'},text),
                              self.update('T06',{'text':'Dr. Albagdadi at the NCH heart institute'},text)],
            extraction=self.extraction([self.update('RC01',{'choice':'self'},text),self.update('T03',{'zip':'34103'},text),
                self.update('T06',{'text':'Dr. Albagdadi at the NCH heart institute'},text)],
                discussion=self.proposal(text,purpose='investigate',focus='doctors',investigate=['doctors'],request_quote=text)))
        q=out['conversationCheck']['question']
        self.assertEqual(q['field'],'doctor')
        self.assertGreaterEqual(len([x for x in q['choices'] if not x['value'].startswith('__')]),2)
        self.assertFalse(out['conversationCheck']['results'])
        choice=next(x for x in q['choices'] if 'mazen' in x['label'].lower())
        out=self.answer(choice['value'])
        q=out['conversationCheck']['question']
        if q and q['field']=='office':
            site=next(x for x in q['choices'] if 'naples' in x['label'].lower())
            out=self.answer(site['value'])
        self.assertTrue(any(r['kind']=='doctor_matrix' for r in out['conversationCheck']['results']))


class CostOrdering(unittest.TestCase):
    def test_unknown_is_unranked_and_premium_is_not_total_cost(self):
        rows={'a':{'state':'offline_average_candidate','plan_premium_plus_drugs_cents':20000,'pharmacy':{'state':'preferred'}},
              'b':{'state':'offline_average_candidate','plan_premium_plus_drugs_cents':10000,'pharmacy':{'state':'standard'}},
              'c':{'state':'held','pharmacy':{'state':'unknown'}}}
        out=engine.evaluate_part_d(inputs(medicines='yes'),part_d(('a',0,0),('b',100,0),('c',0,0)),drug_costs=rows)
        self.assertEqual(out['plans']['b']['rank'],1)
        self.assertEqual(out['plans']['a']['rank'],2)
        self.assertIsNone(out['plans']['c']['rank'])
        self.assertEqual(out['plans']['c']['group'],'priority')
        self.assertEqual(out['recommended_ids'],[])


class FictionalDrugService:
    """Invented evidence exercises integration, not actual plan prices."""
    def _scope(self): pass
    def products(self, refs, **query):
        return [{'rxcui':'861007','name':'Metformin 500 mg tablet','type':'SCD','route':'oral',
                 'strength_description':'500 mg','form':'tablet'}]
    def outlets(self, refs, **query):
        return [{'npi':'1841534534','address_id':'fictional-store','zip':'34102','aliases':['Publix'],
                 'name':'Fictional Publix','address':{'street':'1 Fictional Street','city':'Naples','state':'FL','postal':'34102'}}]
    def formulary_matrix(self, medicines):
        return {f'2026:S9999:{i:03d}:000':{'name':f'Fictional plan {i}', 'medicines':[
            {**m,'state':'covered','evidence_date':'2026-11-14','tier':'1','prior_authorization':False,
             'step_therapy':False,'quantity_limit':False} for m in medicines]} for i in range(10)}
    def pharmacy(self, refs, plan, selection):
        return {'status':'preferred' if plan.endswith(':000:000') else 'standard'}, {}
    def estimate(self, report, revision):
        index=int(report['offering_id'].split(':')[2])
        if index==9: return {'state':'held','hold':'fictional_evidence_gap'}
        return {'state':'offline_average_candidate','receipt':json.dumps(report,sort_keys=True),'start':'2026-12-01',
                'end':'2026-12-31','drug_spending_cents':1000-index*10,'plan_premium_cents':index*5,
                'plan_premium_plus_drugs_cents':1000-index*5}
    def check_receipt(self, report, revision, receipt): return receipt==json.dumps(report,sort_keys=True)


class FictionalResearchJourney(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context','composed_context','answer'):
        locals()[name] = getattr(ResearchJourney, name)
    update = staticmethod(Replays.update)
    extraction = staticmethod(Replays.extraction)
    proposal = staticmethod(Replays.proposal)
    setUp = Replays.setUp
    test_complete_comparison = ResearchJourney.test_cost_comparison_from_words_reaches_all_ten_plans_and_correction_withdraws

    def attach_sources(self):
        self.service=FictionalDrugService()
        self.controller=ConversationChecks(self.flow,None,self.service,lambda:[])
        self.flow.conversation_checks=self.controller


if __name__=='__main__': unittest.main()
