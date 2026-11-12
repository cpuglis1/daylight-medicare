"""Actual r13, disposable HTTP visits, deterministic fixtures; no paid calls."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import test_http as support
from test_comparison_chat import CurrentChatHarness
from comparison_evidence import canonical_sha256
from guest_profiles import ProfileError
from plans_authority import METHOD, PlansAuthority, permits, runtime_digest
from plans_publication import PlansPublication
from plans_adapters import metric_payload
from plans_catalog import PATH, SHA256, PlansCatalog
from plans_context import rehydrate
from plans_ranking import CHECKS, METRICS, recommend
from plans_service import PlansService

REPORTS = [('T01', {'choice': 'compare'}), ('RC01', {'choice': 'self'}), ('T03', {'zip': '34102'}),
    ('RC03', {'year': '2026'}), ('T05', {'choice': 'original,drug'}), ('RC04', {'choice': 'both'}),
    ('T06', {'choice': 'none'}), ('T07', {'choice': 'no'}), ('T08', {'choice': 'local'}),
    ('T09', {'choice': 'predictable'}), ('T10', {'choice': 'total_cost'})]


def allow(authority, purpose, payload):
    authority['outputs'][purpose + ':' + canonical_sha256(payload)] = True
    if purpose not in authority['source_use']['purposes']:
        authority['source_use']['purposes'].append(purpose)


def accepted_fixture():
    now = datetime.now(timezone.utc)
    review = {'name': 'Fictional reviewer', 'receipt': 'fixture:no-real-acceptance',
              'reviewed_at': (now-timedelta(days=1)).isoformat(), 'expires_at': (now+timedelta(days=1)).isoformat()}
    return {'schema': 'plans-workspace-acceptance/2', 'status': 'accepted',
        'release_id': 'fixture:release', 'catalog_sha256': SHA256, 'method': METHOD,
        'runtime_sha256': runtime_digest(), 'source_use': {**review, 'purposes': []},
        'independent_review': {**review, 'role': 'medicare_subject_matter_reviewer', 'independent_of_sales': True},
        'outputs': {}, 'cases': {}}


def publication_fixture(authority):
    return {'schema':'plans-publication/1','catalog_sha256':SHA256,'revoked':False,'withheld':[],
            'local_review':{'authorized':False},'consumer':copy.deepcopy(authority)}


class CatalogAndAuthorityTests(unittest.TestCase):
    def test_exact_72_all_amounts_held_and_restrictions_retained(self):
        service = PlansService(None)
        view, _ = service.projection()
        catalog = PlansCatalog().read()
        self.assertEqual([p['id'] for p in view['plans']], [p['display_candidate']['offering_id'] for p in catalog['plans']])
        self.assertEqual(view['coverage']['prepared_fields'], 720)
        self.assertEqual(view['coverage']['published_fields'], 0)
        self.assertEqual(view['coverage']['verified_availability'], 0)
        self.assertEqual(len(view['plans']), 72)
        self.assertTrue(all(c['value'] is None for p in view['plans'] for c in p['fields'].values()))
        self.assertTrue(all(c['amount'] is None for p in view['plans'] for c in p['examples'].values()))
        self.assertEqual(len([p for p in view['plans'] if ':H5652:' in p['id'] and p['retained_restrictions']]), 5)
        self.assertNotIn('profile', view)

    def test_catalog_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'catalog.json';path.write_bytes(PATH.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError, 'INTEGRITY'):
                PlansCatalog(path).read()

    def test_exact_field_only_then_revocation_and_expiry(self):
        catalog = PlansCatalog().read(); p=catalog['plans'][0]['display_candidate']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json'; a=accepted_fixture()
            payload={'offering_id': p['offering_id'], 'field':'plan_premium', 'cell':p['benefits']['plan_premium']}
            allow(a,'published_display',payload);path.write_text(json.dumps(a))
            path.write_text(json.dumps(publication_fixture(a)))
            source=PlansPublication(path);service=PlansService(None,publication=source)
            first,_=service.projection();self.assertEqual(first['coverage']['published_fields'],1)
            self.assertEqual(first['plans'][0]['fields']['plan_premium']['value'],'$4.80')
            self.assertIsNone(first['plans'][0]['examples']['premium_12_months']['amount'])
            for key in ['status','catalog_sha256']:
                changed=publication_fixture(a)
                if key=='status':changed['consumer']['status']='revoked'
                else:changed[key]='bad'
                path.write_text(json.dumps(changed))
                self.assertEqual(service.projection()[0]['coverage']['published_fields'],0)
            changed=publication_fixture(a);changed['consumer']['independent_review']['expires_at']='2020-01-01T00:00:00+00:00';path.write_text(json.dumps(changed))
            self.assertEqual(service.projection()[0]['coverage']['published_fields'],0)
            changed=publication_fixture(a);changed['commission_rate']=999;path.write_text(json.dumps(changed))
            self.assertEqual(service.projection()[0]['coverage']['published_fields'],0)

    def test_material_held_cell_cannot_be_released_by_receipt(self):
        p=PlansCatalog().read()['plans'][0]['display_candidate'];a=accepted_fixture()
        allow(a,'published_display',{'offering_id':p['offering_id'],'field':'primary_care_in_network','cell':p['benefits']['primary_care_in_network']})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json';path.write_text(json.dumps(publication_fixture(a)))
            cell=PlansService(None,publication=PlansPublication(path)).projection()[0]['plans'][0]['fields']['primary_care_in_network']
            self.assertEqual(cell['state'],'held');self.assertIsNone(cell['value'])


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.a=accepted_fixture();self.plans=[{'id':f'fictional:{i}'} for i in range(4)]
        self.order=list(METRICS);self.digest='fixture:profile';self.metrics={};self.checks={}
        for i,p in enumerate(self.plans):
            self.checks[p['id']]={key:{'state':'meets','reason_codes':[]} for key in CHECKS}
            self.metrics[p['id']]={key:{'state':'available','amount':amount} for key,amount in zip(METRICS,[str(i),str(10-i)])}
        self.admit()

    def admit(self):
        allow(self.a,'recommendation_method',{'method':METHOD,'metrics':list(METRICS),'checks':list(CHECKS),'offering_ids':[p['id'] for p in self.plans]})
        for p in self.plans:
            for key,fact in self.metrics[p['id']].items():
                allow(self.a,'ranking_metric',metric_payload(p['id'],key,fact))

    def result(self,**kwargs):
        return recommend(self.digest,self.order,self.plans,self.a,metrics=self.metrics,checks=self.checks,**kwargs)

    def test_priority_order_changes_three_with_no_economic_feature(self):
        self.assertEqual(self.result()['top_three'],['fictional:0','fictional:1','fictional:2'])
        self.order.reverse();self.assertEqual(self.result()['top_three'],['fictional:3','fictional:2','fictional:1'])

    def test_unknown_worse_fourth_does_not_block_but_possible_winner_does(self):
        self.checks['fictional:3']['eligibility']['state']='needs_check'
        self.assertEqual(self.result()['top_three'],['fictional:0','fictional:1','fictional:2'])
        self.metrics['fictional:3'][METRICS[0]]['amount']='0';self.admit()
        self.assertEqual(self.result()['top_three'],[])
        self.assertIn('MATERIAL_UNKNOWN_CONTENDER',self.result()['reason_codes'])
        self.assertEqual(len(self.result()['plans']),4)

    def test_known_conflicts_no_padding_and_ties(self):
        for identifier in ['fictional:2','fictional:3']:
            self.checks[identifier]['restrictions']['state']='known_conflict'
        self.assertEqual(len(self.result()['top_three']),2)
        self.metrics['fictional:1']=copy.deepcopy(self.metrics['fictional:0']);self.admit()
        self.assertEqual(self.result()['tie_groups'],[['fictional:0','fictional:1']])

    def test_missing_metric_scope_and_order_hold(self):
        self.assertEqual(self.result(scope_supported=False)['state'],'held')
        self.order=[];self.assertEqual(self.result()['state'],'held');self.order=list(METRICS)
        self.metrics['fictional:0'][METRICS[0]]['state']='held'
        self.assertEqual(self.result()['state'],'held')


class PlansHttpTests(unittest.TestCase):
    setUpClass=classmethod(support.HttpTests.setUpClass.__func__)
    tearDownClass=classmethod(support.HttpTests.tearDownClass.__func__)
    request=support.HttpTests.request
    turn=support.HttpTests.turn

    def setUp(self):
        support.HttpTests.setUp(self)
        for identifier,fields in REPORTS:self.turn({'type':'choice','id':identifier,'fields':fields})
        review=self.turn({'type':'review_plans'})['review']
        self.receipt=self.turn({'type':'confirm_plan_review','token':review['token']})['plansHandoff']['token']

    def test_current_profile_all_plans_priorities_and_lineage(self):
        code,status=self.request('/api/status')
        self.assertEqual(status['plans_workspace']['retained_identities'],72)
        self.assertFalse(status['consumer_ready'])
        code,result=self.request('/api/plans/workspace',{'token':self.receipt});self.assertEqual(code,200,result)
        self.assertTrue(result['recommendation']['scope_supported'])
        self.assertEqual(len(result['plans']),72);self.assertEqual(result['recommendation']['top_three'],[])
        code,ordered=self.request('/api/plans/priorities',{'token':self.receipt,'order':list(METRICS),'confirmed':True})
        self.assertEqual(code,200,ordered);self.assertEqual(ordered['recommendation']['priority_order'],list(METRICS))
        self.assertNotEqual(result['view_digest'],ordered['view_digest'])
        code,detail=self.request('/api/plans/detail',{'offeringId':result['plans'][0]['id']})
        self.assertEqual(code,200);self.assertIn('r5_source_refs',detail['lineage'])
        self.assertEqual(self.server.adaptive.agent.calls,0)

    def test_owner_csrf_source_payload_injection_and_correction(self):
        body={'token':self.receipt}
        self.assertEqual(self.request('/api/plans/workspace',body,csrf=False)[0],403)
        self.assertEqual(self.request('/api/plans/workspace',body,origin='https://example.com')[0],403)
        self.assertEqual(self.request('/api/plans/workspace?token=bad',body)[0],422)
        self.assertEqual(self.request('/api/plans/workspace',{**body,'profile':{}})[0],422)
        self.assertEqual(self.request('/api/plans/catalog',{'accepted':True})[0],422)
        self.turn({'type':'choice','id':'T10','fields':{'choice':'doctors'}})
        self.assertEqual(self.request('/api/plans/workspace',body)[0],409)
        self.cookie=None;_,self.session=self.request('/api/guest/session')
        self.assertEqual(self.request('/api/plans/workspace',body)[0],409)

    def test_2027_remains_2027_and_listing_stays_dated(self):
        self.turn({'type':'choice','id':'RC03','fields':{'year':'2027'}})
        review=self.turn({'type':'review_plans'})['review']
        token=self.turn({'type':'confirm_plan_review','token':review['token']})['plansHandoff']['token']
        code,result=self.request('/api/plans/workspace',{'token':token})
        self.assertEqual(code,200);self.assertEqual(result['profile_binding']['scope']['year'],2027)
        self.assertEqual(result['scope']['year'],2026);self.assertFalse(result['recommendation']['scope_supported'])


class PlansChatTests(unittest.TestCase):
    def setUp(self):
        self.h=CurrentChatHarness();self.h.flow.plans_service=PlansService(self.h.flow)
        transport=self.h.flow.agent.client.transport
        def scripted_transport(payload):
            response=transport(payload)
            if payload['text']['format']['name']=='daylight_resolved_conversation':
                value=json.loads(response['output'][0]['content'][0]['text'])
                if not value['question']:value['question']='Which part would you like to understand next?'
                response['output'][0]['content'][0]['text']=json.dumps(value)
            return response
        self.h.flow.agent.client.transport=scripted_transport
        for identifier,fields in REPORTS:self.h.choice(identifier,**fields)
        review=self.h.turn({'type':'review_plans'},aiConsent=False)['review']
        self.handoff=self.h.turn({'type':'confirm_plan_review','token':review['token']},aiConsent=False)['plansHandoff']
        self.view=self.h.flow.plans_service.workspace(self.h.owner,self.handoff['token'])
        self.context={'version':'plans-context-v1','reviewToken':self.handoff['token'],'viewDigest':self.view['view_digest'],
            'visibleIds':[self.view['plans'][0]['id']],'comparedIds':[],'selectedId':self.view['plans'][0]['id'],
            'field':'plan_premium','mode':'all'}

    def payload(self):
        return self.h.payload({'type':'message','message':'Explain the selected plan term.'},
                              plansContextPolicy='plans-context-v1',plansContext=copy.deepcopy(self.context))

    def test_current_view_sent_only_to_composer_no_held_prices_or_receipt(self):
        extraction=self.h.extraction();extraction['situation_proposals']=[];self.h.extractions.append(extraction)
        result=self.h.take(self.payload())
        self.assertNotEqual(result.get('generated',{}).get('status'),'unavailable',result.get('notice'))
        sent=self.h.composed_context()['plans_context']
        self.assertEqual(sent['selected_id'],self.context['selectedId'])
        self.assertIsNone(sent['plans'][0]['fields']['plan_premium']['value'])
        self.assertNotIn(self.handoff['token'],json.dumps(sent));self.assertNotIn('$4.80',json.dumps(sent))
        self.assertIn('plansContext',result)
        self.assertIsNone(self.h.flow._plans_context.get())

    def test_forged_amount_id_permission_scope_and_stale_view_rejected_before_model(self):
        payload=self.payload();before=len(self.h.calls)
        for change in [{'amount':'$0'},{'selectedId':'fictional:forged'},{'visibleIds':['bad']},{'viewDigest':'bad'}, {'field':'commission'}]:
            bad=copy.deepcopy(payload);bad['plansContext'].update(change)
            with self.assertRaises(ProfileError):self.h.take(bad)
        bad=copy.deepcopy(payload);bad['plansContextPolicy']='natural-context-v3'
        with self.assertRaises(ProfileError):self.h.take(bad)
        self.assertEqual(before,len(self.h.calls))

    def test_accepted_field_is_citable_without_promoting_personal_fit(self):
        p=PlansCatalog().read()['plans'][0]['display_candidate'];a=accepted_fixture()
        allow(a,'published_display',{'offering_id':p['offering_id'],'field':'plan_premium','cell':p['benefits']['plan_premium']})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json';path.write_text(json.dumps(publication_fixture(a)))
            self.h.flow.plans_service.publication=PlansPublication(path)
            view=self.h.flow.plans_service.workspace(self.h.owner,self.handoff['token'])
            self.context['viewDigest']=view['view_digest']
            ref=f"r13:{p['offering_id']}:plan_premium"
            transport=self.h.flow.agent.client.transport
            def composed(payload):
                response=transport(payload)
                if payload['text']['format']['name']=='daylight_resolved_conversation':
                    value=json.loads(response['output'][0]['content'][0]['text'])
                    value.update(reply='The published plan premium is $4.80. That is only one part of cost.',evidence_refs=[ref])
                    response['output'][0]['content'][0]['text']=json.dumps(value)
                return response
            self.h.flow.agent.client.transport=composed
            extraction=self.h.extraction();extraction['situation_proposals']=[];self.h.extractions.append(extraction)
            result=self.h.take(self.payload())
            self.assertNotEqual(result.get('generated',{}).get('status'),'unavailable',result.get('notice'))
            self.assertEqual(result['planEvidence'][0]['id'],ref)
            self.assertEqual(view['recommendation']['top_three'],[])
            path.write_text('{"status":"revoked"}')
            replay=self.h.flow.replay_response(self.h.owner,result)
            self.assertEqual(replay['reply'],'');self.assertEqual(replay['generated']['code'],'plans_context_stale')
            self.assertEqual(replay['planEvidence'],[])

    def test_priority_change_profile_edit_expiry_and_delete_revoke(self):
        self.h.flow.plans_service.confirm_priorities(self.h.owner,self.handoff['token'],list(METRICS),True)
        with self.assertRaises(ProfileError):self.h.take(self.payload())
        self.h.choice('T10',choice='doctors')
        with self.assertRaises(ProfileError):self.h.flow.plans_service.workspace(self.h.owner,self.handoff['token'])

    def test_browsing_context_requires_no_profile_handoff_and_cannot_recommend(self):
        view=self.h.flow.plans_service.workspace(self.h.owner)
        request={**self.context,'reviewToken':None,'viewDigest':view['view_digest']}
        context=rehydrate(self.h.flow.plans_service,self.h.owner,request,None)
        self.assertIsNone(context['input_digest']);self.assertEqual(context['recommendation']['top_three'],[])
        self.assertIn('CONFIRM_CURRENT_PROFILE',context['recommendation']['reason_codes'])

    def test_expired_handoff_rejected_before_any_model_work(self):
        self.h.flow.plan_reviews.handoffs[self.handoff['token']]['expires']=0
        before=len(self.h.calls)
        with self.assertRaises(ProfileError):self.h.take(self.payload())
        self.assertEqual(before,len(self.h.calls))
        self.h.flow.forget_owner(self.h.owner)
        self.assertFalse(self.h.flow.plans_service.preferences)
        with self.assertRaises(ProfileError):self.h.flow.plans_service.workspace(self.h.owner,self.handoff['token'])


if __name__=='__main__':unittest.main()
