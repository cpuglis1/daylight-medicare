"""Fictional explicit choices over the actual profile and identity mechanics."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity_resolution import DrugIdentityChoices, HELD_PURPOSES, IdentityResolutionError, NAMESPACE
from test_comparison_methods import profile, fact, NAME, STRENGTH, SCOPE


OWNER = 'fictional-owner-00000001'
OTHER = 'fictional-owner-00000002'
ITEM = 'medicine-1'


def candidate(identifier='fixture:product-1', cui='1000048', **changes):
    return {'candidate_id': identifier, 'namespace': NAMESPACE,
        'identity': {'rxcui':cui, 'drug_name':'Fictional retained product',
                     'dose_form':'Fictional tablet', 'ingredient_strength_description':'Fictional 5 mg'},
        'identity_grain':'drug_product_concept','identity_detail_state':'source_details_present',
        'automatic_profile_binding':False,'requires_identity_confirmation':True,
        'coverage_inferred':False,'output_authority':'held',
        'states':{'source_use_state':'existing_source_policy_applies'},
        'snapshot_source_use_state':'not_newly_reviewed',
        'lineage':{'raw_sha256':'a'*64,'source_table':'drug_identities','source_row_ordinal':1},
        'source_history':{'dated':'fictional'},'conditions':{'fictional':'preserved'},**changes}


class Dictionary:
    def __init__(self):
        self.calls=[];self.rows=[candidate()];self.snapshot='fixture:source-snapshot'
        self.failure=False;self.on_read=None;self.access=[]

    def lookup_rxcuis(self,rxcuis,*,year,expected_snapshot_id=None):
        self.calls.append((copy.deepcopy(rxcuis),year,expected_snapshot_id))
        if self.failure:raise RuntimeError('PRIVATE_SOURCE_EXCEPTION_CANARY')
        if expected_snapshot_id not in {None,self.snapshot}:raise ValueError('snapshot')
        if self.on_read:self.on_read()
        return {'contract_id':'l05-exact-rxcui-research-r1','operator_only':True,
            'automatic_profile_binding':False,'consumer_release':False,'clinical_substitution':False,
            'binding':{'snapshot_id':self.snapshot,'manifest_sha256':'b'*64},
            'authority':{purpose:{'state':'held'} for purpose in HELD_PURPOSES},
            'candidates':[copy.deepcopy(row) for row in self.rows if row['identity']['rxcui'] in rxcuis],
            'matches':[], 'source_access_states':copy.deepcopy(self.access),
            'source_access_registration':{'state':'registered' if self.access else 'unregistered','absence_is_permission':False}}


class IdentityResolutionTests(unittest.TestCase):
    def setUp(self):
        self.case=profile();self.repository=Dictionary();self.now=100
        self.service=DrugIdentityChoices(self.repository,clock=lambda:self.now,ttl_seconds=60)

    def offer(self,**changes):
        return self.service.offer(OWNER,self.case,item_id=ITEM,rxcuis=['1000048'],scope=SCOPE,**changes)

    def select(self,offer,**changes):
        args={'choice_token':offer['choice_token'],'candidate_id':'fixture:product-1','confirmed':True,**changes}
        return self.service.confirm(OWNER,self.case,**args)

    def test_offer_neither_selects_nor_edits_reports_or_transfers_them_to_source(self):
        before=copy.deepcopy(self.case);offer=self.offer()
        self.assertEqual(self.case,before)
        self.assertTrue(offer['explicit_choice_required']);self.assertEqual(offer['personal_output_state'],'held')
        self.assertEqual(self.repository.calls,[(['1000048'],2026,None)])
        self.assertEqual(offer['candidates'][0]['conditions'],{'fictional':'preserved'})
        self.assertEqual(offer['source_access_registration']['state'],'unregistered')

    def test_explicit_choice_binds_only_exact_item_source_with_no_coverage_or_policy_authority(self):
        out=self.select(self.offer())
        self.assertEqual(out['choice_state'],'explicitly_selected_source_identity')
        self.assertEqual(out['binding']['item_id'],ITEM)
        self.assertEqual(out['assessment']['identity_state'],'bound')
        self.assertFalse(out['coverage_verified']);self.assertFalse(out['clinical_equivalence_inferred'])
        self.assertEqual(out['personal_output_state'],'held');self.assertFalse(out['profile_reports_changed'])
        self.assertEqual(out['reported_details_consistency'],'requires_separate_reconciliation')
        self.assertEqual(self.repository.calls[-1],(['1000048'],2026,'fixture:source-snapshot'))

    def test_no_silent_choice_for_single_candidate_and_confirmation_is_exact_boolean(self):
        offer=self.offer()
        for value in [False,None,'yes',1]:
            with self.subTest(value=value),self.assertRaisesRegex(IdentityResolutionError,'EXPLICIT_IDENTITY_CHOICE_REQUIRED'):
                self.select(offer,confirmed=value)
        self.assertEqual(len(self.repository.calls),1)

    def test_foreign_owner_unknown_candidate_and_malformed_token_are_rejected_before_source_read(self):
        offer=self.offer()
        with self.assertRaisesRegex(IdentityResolutionError,'EXPIRED_OR_FOREIGN'):
            self.service.confirm(OTHER,self.case,choice_token=offer['choice_token'],candidate_id='fixture:product-1',confirmed=True)
        for args in [{'candidate_id':'not-offered'},{'choice_token':{}},{'candidate_id':[]}]:
            with self.assertRaises(IdentityResolutionError):self.select(offer,**args)
        self.assertEqual(len(self.repository.calls),1)

    def test_changed_item_value_or_revision_subject_or_time_invalidates_choice(self):
        for field,change in [('value','10 mg'),('report_revision',3),('subject_id','other'),('scope','historical')]:
            with self.subTest(field=field):
                self.case=profile();offer=self.offer();row=fact(self.case,STRENGTH,ITEM)
                if field=='value':row['value']=change
                else:row['ref'][field]=change
                with self.assertRaises(IdentityResolutionError):self.select(offer)

    def test_unrelated_item_and_parent_bookkeeping_do_not_reconfirm_unchanged_report(self):
        offer=self.offer();fact(self.case,STRENGTH,'medicine-2')['value']='20 mg'
        for row in self.case['facts']:
            if row['ref']['record_revision'] is not None:row['ref']['record_revision']+=1
        self.assertEqual(self.select(offer)['assessment']['identity_state'],'bound')

    def test_parent_rollback_is_held_even_when_item_values_are_unchanged(self):
        offer=self.offer()
        for row in self.case['facts']:
            if row['ref']['record_revision'] is not None:row['ref']['record_revision']-=1
        with self.assertRaisesRegex(IdentityResolutionError,'REPORT_BINDING_STALE'):self.select(offer)

    def test_partial_unknown_explicit_none_and_learner_reports_do_not_supply_positive_product_details(self):
        for change in [{'report_state':'unknown'},{'report_state':'explicit_none'},
                       {'capture_subject':'learner'},{'usable_for_bound_subject':False}]:
            with self.subTest(change=change):
                self.case=profile();fact(self.case,STRENGTH,ITEM).update(change)
                with self.assertRaisesRegex(IdentityResolutionError,'REPORT_DETAILS_REQUIRED'):self.offer()
        self.assertEqual(self.repository.calls,[])

    def test_scope_year_or_geography_change_cannot_reuse_item_choice(self):
        offer=self.offer();self.case['requested_scope']={**SCOPE,'year':2027}
        with self.assertRaises(IdentityResolutionError):self.select(offer)

    def test_source_revision_stop_disappearance_or_candidate_change_invalidates_confirmation(self):
        for mode in ['snapshot','stop','missing','raw']:
            with self.subTest(mode=mode):
                self.setUp();offer=self.offer()
                if mode=='snapshot':self.repository.snapshot='fixture:new-snapshot'
                elif mode=='stop':self.repository.failure=True
                elif mode=='missing':self.repository.rows=[]
                else:self.repository.rows[0]['lineage']['raw_sha256']='c'*64
                with self.assertRaises(IdentityResolutionError) as raised:self.select(offer)
                self.assertNotIn('PRIVATE_SOURCE_EXCEPTION_CANARY',str(raised.exception))

    def test_profile_change_during_source_replay_is_rechecked(self):
        offer=self.offer()
        self.repository.on_read=lambda:fact(self.case,STRENGTH,ITEM).update(value='changed during query')
        with self.assertRaisesRegex(IdentityResolutionError,'REPORT_CHANGED'):self.select(offer)

    def test_preexisting_source_stop_or_held_access_cannot_supply_a_new_choice(self):
        for state in ['stopped','held','source_STOP','unknown']:
            with self.subTest(state=state):
                self.repository.access=[{'source_id':'L05','state':state}]
                with self.assertRaisesRegex(IdentityResolutionError,'DICTIONARY_SOURCE_REQUIRED'):self.offer()
        self.repository.access=[]
        for where in ['observation','snapshot']:
            with self.subTest(where=where):
                self.repository.rows=[candidate()]
                if where=='observation':self.repository.rows[0]['states']['source_use_state']='source_STOP'
                else:self.repository.rows[0]['snapshot_source_use_state']='source_STOP'
                with self.assertRaisesRegex(IdentityResolutionError,'DICTIONARY_CANDIDATE_REQUIRED'):self.offer()

    def test_expiry_during_source_replay_is_rechecked_before_binding(self):
        offer=self.offer()
        self.repository.on_read=lambda:setattr(self,'now',161)
        with self.assertRaisesRegex(IdentityResolutionError,'EXPIRED_OR_FOREIGN'):self.select(offer)
        self.repository.on_read=None;self.now=101
        with self.assertRaisesRegex(IdentityResolutionError,'EXPIRED_OR_FOREIGN'):self.select(offer)

    def test_pack_and_partial_source_identity_are_inspectable_but_cannot_bind_product(self):
        for change in [{'identity_grain':'pack_concept'},{'identity_detail_state':'partial'}]:
            with self.subTest(change=change):
                self.setUp();self.repository.rows[0].update(change);offer=self.offer()
                with self.assertRaisesRegex(IdentityResolutionError,'DETAILS_OR_GRAIN_UNRESOLVED'):self.select(offer)

    def test_second_choice_cannot_overwrite_first_and_replay_of_same_choice_is_stable(self):
        self.repository.rows.append(candidate('fixture:product-2'))
        offer=self.offer();first=self.select(offer)
        self.assertEqual(first,self.select(offer))
        with self.assertRaisesRegex(IdentityResolutionError,'EXACT_OFFERED'):self.select(offer,candidate_id='fixture:product-2')

    def test_expiry_capacity_and_forgetting_owner_are_bounded_without_persistence(self):
        service=DrugIdentityChoices(self.repository,clock=lambda:self.now,ttl_seconds=60,max_offers=1)
        offer=service.offer(OWNER,self.case,item_id=ITEM,rxcuis=['1000048'],scope=SCOPE)
        with self.assertRaisesRegex(IdentityResolutionError,'CAPACITY'):service.offer(OWNER,self.case,item_id=ITEM,rxcuis=['1000048'],scope=SCOPE)
        service.forget_owner(OWNER)
        with self.assertRaisesRegex(IdentityResolutionError,'EXPIRED_OR_FOREIGN'):service.confirm(OWNER,self.case,choice_token=offer['choice_token'],candidate_id='fixture:product-1',confirmed=True)
        offer=self.offer();self.now+=61
        with self.assertRaisesRegex(IdentityResolutionError,'EXPIRED_OR_FOREIGN'):self.select(offer)

    def test_malformed_source_or_consumer_permission_cannot_be_used_as_identity_authority(self):
        valid=self.repository.lookup_rxcuis(['1000048'],year=2026)
        for mutate in [lambda out:out.update(authority=None),
                       lambda out:out.update(consumer_release=True),
                       lambda out:out['authority']['recommendation'].update(state='permitted'),
                       lambda out:out['candidates'].append(copy.deepcopy(out['candidates'][0])),
                       lambda out:out.update(candidates=[None])]:
            with self.subTest(mutate=mutate):
                broken=copy.deepcopy(valid);mutate(broken)
                with patch.object(self.repository,'lookup_rxcuis',return_value=broken):
                    with self.assertRaises(IdentityResolutionError):self.offer()


if __name__=='__main__':unittest.main()
