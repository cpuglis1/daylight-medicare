"""Real sealed catalog + synthetic profiles/receipts; no live model or private DB."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from test_comparison_chat import CurrentChatHarness
from test_plans_workspace import REPORTS, accepted_fixture, allow, publication_fixture, PlansHttpTests
from plans_adapters import (catalog_metrics, prepare_checks, decimal_amount, metric_payload,
                            VerificationFindings, METRICS, CHECKS)
from plans_authority import PlansAuthority
from plans_catalog import PlansCatalog
from plans_context import rehydrate, context_evidence
from plans_publication import PlansPublication
from plans_ranking import method_payload
from plans_service import PlansService


class PreparedProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h=CurrentChatHarness()
        for identifier,fields in REPORTS:h.choice(identifier,**fields)
        review=h.turn({'type':'review_plans'},aiConsent=False)['review']
        token=h.turn({'type':'confirm_plan_review','token':review['token']},aiConsent=False)['plansHandoff']['token']
        cls.handoff=h.flow.resolve_plans_handoff(h.owner,token)
        cls.h=h

    def setUp(self):
        self.service=PlansService(self.h.flow,local_review=True)
        self.view,_=self.service.projection()
        self.plans=self.view['plans'];self.profile=copy.deepcopy(self.handoff['profile'])
        self.metrics=catalog_metrics(self.service.catalog.typed(),self.plans)

    def change(self,path,**changes):
        next(f for f in self.profile['facts'] if f['ref']['path']==path).update(changes)

    def test_actual_profile_adapters_do_not_require_absent_items(self):
        rows=prepare_checks(self.profile,self.plans)
        normal=rows['2026:H1032:198:000'];snp=rows['2026:H0710:010:000']
        for key in ['providers','medicines','travel','restrictions']:self.assertEqual(normal[key]['state'],'not_required',key)
        self.assertEqual(snp['restrictions']['state'],'needs_check')
        self.assertEqual(normal['eligibility']['input_state'],'reported_not_verified')
        self.assertEqual(normal['stated_priorities']['reason_codes'],['PRIORITY_EXCEEDS_PREMIUM_AND_MEDICAL_LIMIT'])
        self.assertEqual(normal['budget']['state'],'not_required')
        self.change('guide.fields.needs.providersStatus',report_state='unknown')
        self.change('guide.fields.needs.medicinesStatus',usable_for_bound_subject=False)
        normal=prepare_checks(self.profile,self.plans)['2026:H1032:198:000']
        self.assertEqual(normal['providers']['state'],'needs_check');self.assertEqual(normal['medicines']['state'],'needs_check')

    def test_conflicting_entity_does_not_vanish_behind_old_none(self):
        self.change('guide.fields.needs.providers',value=['A retained office'],report_state='conflicting')
        self.assertEqual(prepare_checks(self.profile,self.plans)['2026:H1032:198:000']['providers']['state'],'needs_check')

    def test_actual_typed_metrics_and_precise_held_values(self):
        self.assertEqual({key:sum(row[key]['state']=='available' for row in self.metrics.values()) for key in METRICS},
                         dict(zip(METRICS,[69,70])))
        for identifier in ['2026:H1032:241:000','2026:H1032:243:000','2026:H1889:026:000']:
            self.assertIsNone(self.metrics[identifier][METRICS[0]]['amount'])
        # Deliberately corrupt a display string: the source-native number stays $0.
        plans=copy.deepcopy(self.plans);plans[1]['fields']['plan_premium']['value']='$999999'
        self.assertEqual(catalog_metrics(self.service.catalog.typed(),plans)[plans[1]['id']][METRICS[0]]['amount'],'0.00')
        for amount in ['NaN','Infinity','-1',3.14]:
            self.assertIsNone(decimal_amount({'type':'decimal','amount':amount,'currency':'USD','unit':'month'},'month'))

    def test_reference_ordering_survives_recommendation_hold_and_keeps_all_plans(self):
        view=self.service.confirm_priorities(self.h.owner,self.handoff['token'],list(METRICS),True)
        ref=view['reference_comparison']
        self.assertEqual(len(ref['ordered_ids']),68);self.assertEqual(len(ref['unranked_ids']),4)
        self.assertEqual(len(view['plans']),72);self.assertEqual(view['recommendation']['top_three'],[])
        self.assertFalse(ref['personal_recommendation']);self.assertEqual(len(ref['tie_groups'][0]),4)
        self.assertEqual(view['metric_coverage'],dict(zip(METRICS,[69,70])))

    def test_context_can_explain_reference_but_never_held_amount(self):
        view=self.service.workspace(self.h.owner,self.handoff['token'])
        request={'version':'plans-context-v1','reviewToken':self.handoff['token'],'viewDigest':view['view_digest'],
                 'visibleIds':[],'comparedIds':[],'selectedId':'2026:H1032:198:000','field':'plan_premium','mode':'all'}
        context=rehydrate(self.service,self.h.owner,request,self.handoff)
        evidence=context_evidence(context)
        self.assertTrue(any('$0' in row['text'] for row in evidence))
        self.assertTrue(all(row['review_state']=='reference' for row in evidence))
        self.assertEqual(context['recommendation']['top_three'],[])
        request.update(selectedId='2026:H1032:241:000')
        context=rehydrate(self.service,self.h.owner,request,self.handoff)
        self.assertFalse(any(row['id'].endswith(':plan_premium') for row in context_evidence(context)))

    def test_compared_plans_carry_displayed_fields_and_listing_type_only(self):
        view=self.service.workspace(self.h.owner,self.handoff['token'])
        compared=['2026:H1032:198:000','2026:H1032:241:000']
        other=next(p['id'] for p in view['plans'] if p['id'] not in compared)
        request={'version':'plans-context-v1','reviewToken':self.handoff['token'],'viewDigest':view['view_digest'],
                 'visibleIds':[other],'comparedIds':compared,'selectedId':None,'field':None,'mode':'compare'}
        context=rehydrate(self.service,self.h.owner,request,self.handoff)
        by_id={p['id']:p for p in context['plans']}
        listed={p['id']:p for p in view['plans']}
        for identifier in compared:
            self.assertEqual(set(by_id[identifier]['fields']),set(listed[identifier]['fields']))
            self.assertEqual(by_id[identifier]['type'],listed[identifier]['type'])
        self.assertEqual(by_id[other]['fields'],{});self.assertIsNone(by_id[other]['type'])
        evidence=context_evidence(context)
        self.assertEqual({row['id'] for row in evidence if row['kind']=='published_plan_listing'},{f'plan-type:{i}' for i in compared})
        self.assertTrue(all(row['review_state']=='reference' for row in evidence))
        self.assertFalse(any(row['offering_id']==other for row in evidence))
        held={(i,k) for i in compared for k,c in by_id[i]['fields'].items() if c['value'] is None}
        self.assertFalse(any(row['id']==by_id[i]['fields'][k]['evidence_ref'] for i,k in held for row in evidence))

    def test_complete_adapter_pipeline_with_fictional_verification_then_revocation(self):
        # Real catalog + explicitly fictional receipts exercise every production
        # adapter. No acceptance is installed into the actual app registry.
        with tempfile.TemporaryDirectory() as folder:
            authority=accepted_fixture(); rows=[]
            now=datetime.now(timezone.utc)
            for plan in self.plans:
                for key,metric in self.metrics[plan['id']].items():
                    if metric['state']=='available':allow(authority,'ranking_metric',metric_payload(plan['id'],key,metric))
                for key in CHECKS:
                    fact={'state':'meets','verification_kind':'personal_plan_check',
                          'scope':{'year':2026,'county_fips':'12021'},'evidence_refs':['fixture:no-real-acceptance'],
                          'checked_at':(now-timedelta(hours=1)).isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat()}
                    if key=='restrictions' and any(m['state']=='held' for m in self.metrics[plan['id']].values()):
                        fact['state']='known_conflict'
                    row={'input_digest':self.handoff['inputDigest'],'offering_id':plan['id'],'check':key,'finding':fact}
                    rows.append(row);allow(authority,'personal_check',row)
            allow(authority,'recommendation_method',method_payload(self.plans))
            ap=Path(folder)/'authority.json';fp=Path(folder)/'findings.json'
            ap.write_text(json.dumps(authority));fp.write_text(json.dumps({'schema':'plans-verification-findings/1','findings':rows}))
            self.service.authority=PlansAuthority(ap);self.service.findings=VerificationFindings(fp)
            view=self.service.confirm_priorities(self.h.owner,self.handoff['token'],list(METRICS),True)
            self.assertEqual(view['recommendation']['state'],'supported')
            self.assertEqual(len(view['recommendation']['top_three']),3)
            self.assertEqual(len(view['recommendation']['tie_groups'][0]),4)
            # Changing the profile prevents all previous verification from matching.
            self.assertEqual(self.service.findings.read('changed',self.service.authority.read()),{})
            previous=view['decision_evidence_digest']
            ap.write_text('{"status":"revoked"}')
            view=self.service.workspace(self.h.owner,self.handoff['token'])
            self.assertEqual(view['recommendation']['top_three'],[])
            self.assertEqual(view['coverage']['usable_reference_fields'],568)
            self.assertNotEqual(view['decision_evidence_digest'],previous)


class PublicationTests(unittest.TestCase):
    def test_all_actual_dispositions_independent_of_recommendation_gate(self):
        service=PlansService(None,local_review=True);view,_=service.projection()
        self.assertEqual(view['coverage']['usable_reference_fields'],568)
        self.assertEqual(view['coverage']['not_applicable_fields'],11)
        self.assertEqual(view['coverage']['material_held_fields'],141)
        self.assertEqual(view['coverage']['usable_examples'],200)
        self.assertFalse(view['publication']['consumer_approved'])
        catalog=PlansCatalog().read()
        held=0
        for p,source in zip(view['plans'],catalog['plans']):
            for key,cell in p['fields'].items():
                if source['display_candidate']['benefits'][key]['state']=='held':
                    held+=1;self.assertIsNone(cell['value']);self.assertNotIn('PUBLICATION_REVIEW_REQUIRED',cell['reason_codes'])
            for key,cell in p['examples'].items():
                if source['display_candidate']['cost_examples'][key]['state']=='held':
                    held+=1;self.assertIsNone(cell['amount'])
        self.assertEqual(held,229)
        self.assertEqual(PlansService(None).projection()[0]['coverage']['usable_reference_fields'],0)

    def test_publication_does_not_depend_on_recommendation_runtime_or_method(self):
        with tempfile.TemporaryDirectory() as folder:
            a=accepted_fixture();p=PlansCatalog().read()['plans'][0]['display_candidate']
            allow(a,'published_display',{'offering_id':p['offering_id'],'field':'plan_premium','cell':p['benefits']['plan_premium']})
            pub=publication_fixture(a);pub['consumer']['method']='irrelevant';pub['consumer']['runtime_sha256']='irrelevant'
            path=Path(folder)/'pub.json';path.write_text(json.dumps(pub))
            service=PlansService(None,publication=PlansPublication(path))
            self.assertEqual(service.projection()[0]['coverage']['published_fields'],1)
            pub['revoked']=True;path.write_text(json.dumps(pub))
            self.assertEqual(service.projection()[0]['coverage']['published_fields'],0)

    def test_findings_reject_identity_lookup_expiry_scope_and_unaccepted_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checks.json';a=accepted_fixture();now=datetime.now(timezone.utc)
            fact={'state':'meets','verification_kind':'identity_lookup','scope':{'year':2026,'county_fips':'12021'},
                  'evidence_refs':['fixture:identity'],'checked_at':(now-timedelta(days=1)).isoformat(),
                  'expires_at':(now+timedelta(days=1)).isoformat()}
            row={'input_digest':'fixture:profile','offering_id':'fictional:1','check':'providers','finding':fact}
            def result():
                path.write_text(json.dumps({'schema':'plans-verification-findings/1','findings':[row]}))
                return VerificationFindings(path).read('fixture:profile',a)
            allow(a,'personal_check',row);self.assertEqual(result(),{})
            fact['verification_kind']='personal_plan_check';self.assertEqual(result(),{})
            allow(a,'personal_check',row);self.assertEqual(len(result()),1)
            fact['expires_at']='2020-01-01T00:00:00+00:00';allow(a,'personal_check',row);self.assertEqual(result(),{})
            fact['expires_at']=(now+timedelta(days=1)).isoformat();fact['scope']['year']=2027
            allow(a,'personal_check',row);self.assertEqual(result(),{})


class ConnectedHttpTests(PlansHttpTests):
    def setUp(self):
        super().setUp();self.server.plans.local_review=True

    def test_actual_http_profile_metrics_and_details(self):
        _,view=self.request('/api/plans/priorities',{'token':self.receipt,'order':list(METRICS),'confirmed':True})
        self.assertEqual(view['coverage']['usable_reference_fields'],568)
        self.assertEqual(len(view['reference_comparison']['ordered_ids']),68)
        _,detail=self.request('/api/plans/detail',{'offeringId':'2026:H1036:217:000'})
        self.assertEqual(detail['plan']['fields']['plan_premium']['value'],'$0')
        self.assertEqual(detail['metrics'][METRICS[0]]['amount'],'0.00')
        self.assertEqual(self.server.adaptive.agent.calls,0)


if __name__=='__main__':unittest.main()
