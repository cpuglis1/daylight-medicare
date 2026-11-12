"""Fictional current profiles; injected source dependencies; no real guests/AI."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity_journey import (IdentityJourney, IdentityJourneyError, IdentityPurposeContract,
                              IDENTITY_SCOPE, POLICY_PATH, HELD_PURPOSES)
from test_identity_resolution import Dictionary, candidate
from test_comparison_methods import profile, fact, STRENGTH

ROOT = Path(__file__).resolve().parents[3]
OWNER, OTHER = 'fictional-identity-owner-0001', 'fictional-identity-owner-0002'


def case():
    value = profile(); value['requested_scope'] = copy.deepcopy(IDENTITY_SCOPE)
    return value


class Discovery(Dictionary):
    def search(self, name_text, **kwargs):
        self.calls.append(('literal', name_text, copy.deepcopy(kwargs)))
        out = super().lookup_rxcuis(['1000048'], year=2026,
            expected_snapshot_id=kwargs.get('expected_snapshot_id'))
        out.update(contract_id='l05-literal-drug-candidates-research-r1',
                   page={'has_more': False, 'next_after_ordinal': None}, partial={'is_partial': False})
        return out


def envelope(contract):
    return {'contract_id': contract, 'operator_only': True, 'automatic_profile_binding': False,
        'consumer_release': False, 'binding': {'snapshot_id': 'fixture:provider-snapshot', 'accepted_release_id': None},
        'source_access_states': [], 'source_access_registration': {'state': 'unregistered', 'absence_is_permission': False},
        'authority': {key: {'state': 'held'} for key in HELD_PURPOSES}}


class Providers:
    def __init__(self):
        self.calls=[];self.on_read=None
        self.value=envelope('l08-exact-provider-site-research-r2')
        self.value.update(identity_state='site_identity_candidate',page={},partial={'is_partial':False},
            site_candidates=[{'candidate_id':'fixture:provider-site','namespace':'retained_L08_composite_directory_site',
                'entity_ref':'fixture:actor','role_ref':'fixture:role','location_ref':'fixture:location',
                'source_name':[{'text':'Synthetic retained practice'}],
                'source_location':{'name':'Synthetic retained site','address':{'city':'Synthetic city'}},
                'actor_resolution_state':'explicit_source_actor_entity','source_identity_conflict_refs':[],
                'automatic_profile_binding':False,'output_authority':'held','relation_basis':'explicit_role_provider_key_and_location_reference'}],
            entity_candidates=[],role_observations=[],location_observations=[],sources=[{'source_native_fields':{'id':'fixture:source'},
                'output_authority':'held','states':{'source_use_state':'existing_source_policy_applies'},
                'snapshot_source_use_state':'not_newly_reviewed'}],
            source_observation_locators=[])
        for group,ref in [('entity_candidates','fixture:actor'),('role_observations','fixture:role'),('location_observations','fixture:location')]:
            self.value[group].append({'record_ref':ref,'output_authority':'held',
                'states':{'source_use_state':'existing_source_policy_applies'},'snapshot_source_use_state':'not_newly_reviewed',
                'source_native_fields':{'observation_id':ref}})
            self.value['source_observation_locators'].append({'observation_id':ref,'raw_parent_verified':True,
                'projected_locator_values_verified':True,'primary_record_refs':[ref],
                'pointer':'/fixture/resource','source_id':'fixture:source'})

    def lookup(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.on_read:self.on_read()
        if kwargs.get('expected_snapshot_id') not in {None,self.value['binding']['snapshot_id']}:
            raise ValueError('PRIVATE_SOURCE_CANARY')
        return copy.deepcopy(self.value)


class ProviderDiscovery:
    def __init__(self):self.calls=[]
    def search(self,name,**kwargs):
        self.calls.append((name,copy.deepcopy(kwargs)))
        out=envelope('l08-literal-provider-candidates-research-r1')
        out.update(candidates=[{'candidate_id':'fixture:provider-entity','entity_key':'fixture:actor',
            'kind':'provider_entity','label':'Synthetic retained practice','selector':{'entity_key':'fixture:actor'},
            'output_authority':'held','states':{'source_use_state':'existing_source_policy_applies'},
            'snapshot_source_use_state':'not_newly_reviewed'}],
            requested={'literal_tokens':['Synthetic','office'],'leading_title_omitted_for_discovery_only':[]},
            page={'has_more':False,'next_after_ordinal':None},partial={'city':'unresolved'})
        return out


class IdentityJourneyTests(unittest.TestCase):
    def setUp(self):
        self.profile=case();self.now=100;self.discovery=Discovery();self.exact=Dictionary()
        self.providers=Providers();self.provider_discovery=ProviderDiscovery()
        self.purpose=IdentityPurposeContract.load(ROOT,internal_research=True)
        self.service=IdentityJourney(self.discovery,self.exact,self.providers,
            provider_discovery=self.provider_discovery,purpose=self.purpose,clock=lambda:self.now,ttl_seconds=60)

    def drug(self):return self.service.drug_search(OWNER,self.profile,item_id='medicine-1')
    def provider(self):return self.service.provider_search(OWNER,self.profile,item_id='doctor-1',selector={'npi':'1000000001'})
    def confirm(self,out,**changes):
        return self.service.confirm(OWNER,self.profile,choice_token=out['choice_token'],
            candidate_id=out['candidates'][0]['candidate_id'],confirmed=True,**changes)

    def test_default_consumer_gate_has_no_source_calls_or_source_labels(self):
        service=IdentityJourney(self.discovery,self.exact,self.providers)
        out=service.drug_search(OWNER,self.profile,item_id='medicine-1')
        self.assertEqual(out['state'],'held');self.assertEqual(out['candidates'],[])
        self.assertEqual(self.discovery.calls,[]);self.assertEqual(self.exact.calls,[])
        self.assertEqual(service.capability()['audience'],'consumer')
        self.assertFalse(out['consumer_release']);self.assertFalse(out['ai_context_changed'])

    def test_source_policy_change_holds_without_auto_accepting_new_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/POLICY_PATH;path.parent.mkdir(parents=True)
            path.write_bytes((ROOT/POLICY_PATH).read_bytes())
            purpose=IdentityPurposeContract.load(temporary,internal_research=True)
            service=IdentityJourney(self.discovery,self.exact,self.providers,purpose=purpose)
            path.write_bytes(path.read_bytes()+b' ')
            self.assertEqual(service.drug_search(OWNER,self.profile,item_id='medicine-1')['state'],'held')
            self.assertEqual(self.discovery.calls,[])

    def test_drug_discovery_composes_frozen_exact_choice_without_backfill(self):
        before=copy.deepcopy(self.profile);out=self.drug()
        self.assertTrue(out['candidates'][0]['selectable'])
        chosen=self.confirm(out)
        self.assertEqual(chosen['state'],'explicitly_selected_source_identity')
        self.assertEqual(chosen['binding']['item_id'],'medicine-1')
        self.assertEqual(chosen['assessment']['identity_state'],'bound')
        self.assertEqual(self.profile,before)
        self.assertFalse(chosen['coverage_verified']);self.assertFalse(chosen['clinical_equivalence_inferred'])
        self.assertEqual(chosen['personal_output_state'],'held')
        self.assertNotIn('raw_source_payload',str(out));self.assertNotIn('conditions',str(out))
        literal_call=next(call for call in self.discovery.calls if call[0]=='literal')
        self.assertIsNone(literal_call[2]['strength_text']);self.assertIsNone(literal_call[2]['form_text'])
        self.assertEqual(out['discovery_basis'],'literal_name_only')

    def test_unknown_strength_allows_discovery_but_not_silent_product_selection(self):
        fact(self.profile,STRENGTH,'medicine-1')['report_state']='unknown'
        out=self.drug();self.assertFalse(out['candidates'][0]['selectable'])
        self.assertEqual(self.exact.calls,[])
        with self.assertRaises(IdentityJourneyError):self.confirm(out)

    def test_provider_name_discovery_requires_explicit_entity_then_site(self):
        first=self.service.provider_search(OWNER,self.profile,item_id='doctor-1')
        self.assertEqual(first['candidates'][0]['kind'],'provider_entity')
        self.assertEqual(self.providers.calls,[])
        sites=self.service.provider_search(OWNER,self.profile,item_id='doctor-1',
            selector=first['candidates'][0]['selector'],choice_token=first['choice_token'])
        chosen=self.confirm(sites)
        self.assertEqual(chosen['binding']['kind'],'provider_site')
        self.assertEqual(chosen['binding']['item_id'],'doctor-1')
        self.assertEqual(chosen['assessment']['identity_state'],'bound')
        self.assertFalse(chosen['coverage_verified'])

    def test_provider_entity_or_npi_does_not_automatically_choose_a_site(self):
        out=self.provider();self.assertTrue(out['explicit_choice_required'])
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)
        with self.assertRaises(IdentityJourneyError):
            self.service.provider_search(OWNER,self.profile,item_id='doctor-1',selector={'entity_key':'not-offered'})
        with self.assertRaises(IdentityJourneyError):
            self.service.confirm(OWNER,self.profile,choice_token=out['choice_token'],
                                 candidate_id=out['candidates'][0]['candidate_id'],confirmed=1)

    def test_missing_actor_location_only_conflict_or_native_lineage_cannot_bind_provider(self):
        for mode in ('actor','location','conflict','locator'):
            with self.subTest(mode=mode):
                self.setUp();site=self.providers.value['site_candidates'][0]
                if mode=='actor':site['actor_resolution_state']='role_identity_actor_reference_not_separately_resolved'
                elif mode=='location':site['actor_resolution_state']='location_entity_only'
                elif mode=='conflict':site['source_identity_conflict_refs']=['fixture:conflict']
                else:self.providers.value['source_observation_locators'][0]['raw_parent_verified']=False
                out=self.provider();self.assertFalse(out['candidates'][0]['selectable'])
                with self.assertRaises(IdentityJourneyError):self.confirm(out)

    def test_owner_item_report_subject_scope_and_rollback_guards(self):
        out=self.drug()
        with self.assertRaises(IdentityJourneyError):
            self.service.confirm(OTHER,self.profile,choice_token=out['choice_token'],candidate_id='fixture:product-1',confirmed=True)
        for mode in ('value','revision','subject','time','rollback'):
            with self.subTest(mode=mode):
                self.setUp();out=self.drug();row=fact(self.profile,STRENGTH,'medicine-1')
                if mode=='value':row['value']='changed'
                elif mode=='revision':row['ref']['report_revision']+=1
                elif mode=='subject':row['ref']['subject_id']='learner'
                elif mode=='time':row['ref']['scope']='historical'
                else:row['ref']['record_revision']-=1
                with self.assertRaises(IdentityJourneyError):self.confirm(out)

    def test_unrelated_item_and_parent_bookkeeping_leave_exact_item_choice_usable(self):
        out=self.drug();fact(self.profile,STRENGTH,'medicine-2')['value']='other corrected value'
        for row in self.profile['facts']:
            if row['ref']['record_revision'] is not None:row['ref']['record_revision']+=1
        self.assertEqual(self.confirm(out)['state'],'explicitly_selected_source_identity')

    def test_source_stop_revision_and_candidate_change_clear_selected_preparation(self):
        for mode in ('stop','revision','candidate','source_row'):
            with self.subTest(mode=mode):
                self.setUp();self.confirm(self.provider())
                if mode=='stop':self.providers.value['source_access_states']=[{'state':'source_STOP'}]
                elif mode=='revision':self.providers.value['binding']['snapshot_id']='fixture:new'
                elif mode=='source_row':self.providers.value['sources'][0]['states']['source_use_state']='source_STOP'
                else:self.providers.value['site_candidates'][0]['source_location']['name']='changed'
                out=self.service.view(OWNER,self.profile,item_id='doctor-1')
                doctor=next(row for row in out['items'] if row['item_id']=='doctor-1')
                self.assertEqual(doctor['state'],'stale_identity_needs_fresh_lookup')
                self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)

    def test_current_report_correction_clears_selection_without_source_query_or_profile_mutation(self):
        self.confirm(self.drug());count=len(self.exact.calls)
        fact(self.profile,STRENGTH,'medicine-1')['value']='changed report'
        before=copy.deepcopy(self.profile)
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)
        self.assertEqual(len(self.exact.calls),count);self.assertEqual(self.profile,before)

    def test_report_change_and_expiry_during_provider_query_do_not_resurrect_selection(self):
        out=self.provider()
        self.providers.on_read=lambda:fact(self.profile,'readiness.facts.RC21.value.items[].city','doctor-1').update(value='changed')
        with self.assertRaises(IdentityJourneyError):self.confirm(out)
        self.setUp();out=self.provider();self.providers.on_read=lambda:setattr(self,'now',161)
        with self.assertRaises(IdentityJourneyError):self.confirm(out)
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)

    def test_preparation_references_only_current_selections_and_never_source_or_coverage_authority(self):
        self.confirm(self.provider());self.confirm(self.drug())
        out=self.service.preparation(OWNER,self.profile)
        self.assertEqual(out['selected_count'],2);self.assertEqual(out['coverage_findings'],[])
        self.assertTrue(all(row['source_state']=='requires_live_recheck' for row in out['bindings']))
        self.assertEqual(out['personal_output_state'],'held');self.assertFalse(out['saved'])
        self.service.forget_owner(OWNER,item_id='medicine-1')
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],1)

    def test_many_reversible_drug_searches_do_not_exhaust_frozen_choice_service(self):
        for _ in range(20):self.confirm(self.drug())
        self.assertLessEqual(len(self.service._offers),3)

    def test_forget_during_pending_lookup_cannot_recreate_ram_offer(self):
        self.providers.on_read=lambda:self.service.forget_owner(OWNER)
        with self.assertRaises(IdentityJourneyError):self.provider()
        self.assertEqual(self.service._offers,{})
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)

    def test_partial_drug_source_stop_never_becomes_display_candidates(self):
        fact(self.profile,STRENGTH,'medicine-1')['report_state']='unknown'
        self.discovery.rows[0]['states']['source_use_state']='source_STOP'
        with self.assertRaises(IdentityJourneyError):self.drug()

    def test_provider_discovery_or_site_source_stop_cannot_expose_labels_or_offers(self):
        original=self.provider_discovery.search
        def stopped(*args,**kwargs):
            out=original(*args,**kwargs)
            out['candidates'][0]['states']['source_use_state']='source_STOP'
            return out
        self.provider_discovery.search=stopped
        with self.assertRaises(IdentityJourneyError):
            self.service.provider_search(OWNER,self.profile,item_id='doctor-1')
        self.assertEqual(self.service._offers,{})
        self.providers.value['sources'][0]['snapshot_source_use_state']='source_STOP'
        with self.assertRaises(IdentityJourneyError):self.provider()
        self.assertEqual(self.service._offers,{})

    def test_browsing_again_does_not_erase_previously_selected_current_identity(self):
        self.confirm(self.drug());self.drug()
        self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],1)

    def test_preparation_does_not_reuse_rolled_back_parent_changed_subject_role_or_removed_item(self):
        for mode in ('rollback','role','removed'):
            with self.subTest(mode=mode):
                self.setUp();self.confirm(self.drug())
                if mode=='rollback':fact(self.profile,STRENGTH,'medicine-1')['ref']['record_revision']-=1
                elif mode=='role':self.profile['profile_binding']['subject_role']='someone'
                else:self.profile['facts']=[row for row in self.profile['facts'] if row['ref'].get('item_id')!='medicine-1']
                self.assertEqual(self.service.preparation(OWNER,self.profile)['selected_count'],0)

    def test_view_only_reports_current_positive_customer_values_and_never_old_source_labels(self):
        fact(self.profile,STRENGTH,'medicine-1')['capture_subject']='learner'
        out=self.service.view(OWNER,self.profile)
        medicine=next(row for row in out['items'] if row['item_id']=='medicine-1')
        self.assertEqual(medicine['reported']['name'],'Synthetic same name')
        self.assertNotIn('strength',medicine['reported'])
        self.assertNotIn('Fictional retained product',str(out))


if __name__=='__main__':unittest.main()
