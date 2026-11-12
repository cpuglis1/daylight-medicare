"""Reference-only data, integrity, scope and genuine-acceptance boundaries."""
import copy
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l01_reference as ref
import l01_reference_build as builder

NOW=datetime(2026,10,25,20,0,tzinfo=timezone.utc)


class PublishedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package=Path(self.tmp.name)/'package'
        shutil.copytree(ref.PACKAGE,self.package)
        self.registry=Path(self.tmp.name)/'synthetic-review.json'
        self.review=ref.read(self.package/'review-template.json')
        self.review.update(decision='accepted',conditions_and_units_reviewed=True,
            reviewed_at_utc='2026-10-25T19:00:00+00:00',review_after_utc='2026-11-20T00:00:00+00:00',
            receipt='SYNTHETIC TEST ONLY; no human approval')
        self.review['reviewer']={'name':'Synthetic fixture','role':'test fixture',
            'qualified_for_scope':True,'independent_of_sales':True}
        for value in self.review['conflict_decisions'].values():
            value.update(decision='accept_proposed_reference_disposition',reason='Synthetic disposable acceptance test')
        self.save_review()

    def save_review(self):
        self.registry.write_text(json.dumps(self.review))

    def lookup(self,request=None,**kwargs):
        return ref.lookup(request or {'year':2026},package=self.package,registry=self.registry,now=NOW,**kwargs)

    def test_all_reference_records_and_exact_sources(self):
        data=self.lookup(research=True)
        self.assertEqual(len(data['records']),78)
        observations={x['id']:x for x in data['observations']}
        for row in data['records']:
            self.assertTrue(row['observation_ids'])
            for oid in row['observation_ids']:
                self.assertTrue(observations[oid]['locator'])
                self.assertTrue(observations[oid]['snapshot_sha256'])
        self.assertFalse(data['personal_applicability_determined'])
        self.assertEqual(len(data['source_conflicts']),3)

    def test_zero_cost_and_exhaustion_have_different_meanings(self):
        rows={x['id']:x for x in self.lookup(research=True)['records']}
        self.assertEqual(rows['hospital_1_60']['value'],0)
        self.assertIn('separate inpatient deductible',rows['hospital_1_60']['conditions'])
        self.assertEqual(rows['snf_1_20']['day_range'],{'first':1,'last':20})
        self.assertEqual(rows['snf_21_100']['day_range'],{'first':21,'last':100})
        self.assertIsNone(rows['snf_after_100']['value'])
        self.assertEqual(rows['snf_after_100']['kind'],'coverage_boundary')
        self.assertEqual(rows['a_deductible']['period'],'benefit_period')
        self.assertEqual(rows['b_deductible']['period'],'calendar_year')
        self.assertEqual(rows['a_deductible']['unit'],'USD cents')

    def test_hospice_and_limited_benefit_qualifications(self):
        rows={x['id']:x for x in self.lookup(research=True)['records']}
        cap=rows['hospice_respite_rate']['reference_cap']
        self.assertEqual(cap['current_year_amount_only_if_period_started_in'],2026)
        self.assertIn('period began',cap['basis'])
        self.assertEqual(rows['hospice_drug_cap']['value']['maximum_cents'],500)
        self.assertEqual(rows['immuno_premium']['coverage_context'],'immuno_b')
        self.assertNotEqual(rows['immuno_premium']['value'],rows['b_premium']['value'])

    def test_no_personal_or_commercial_inputs_or_operations(self):
        for field,value in [('magi_cents',15000000),('state','FL'),('operation','personal_total'),
                ('days',30),('commission',500),('approved_charge_cents',10000),('research',True)]:
            with self.subTest(field=field),self.assertRaises(ref.ReferenceError):
                self.lookup({'year':2026,field:value})
        for request in ({'year':2026,'ids':[]},{'year':2026,'ids':['b_premium','b_premium']},
                        {'year':2026,'ids':['unknown']},{'year':2026,'ids':'b_premium'}):
            with self.assertRaises(ref.ReferenceError):self.lookup(request)

    def test_wrong_or_untyped_year_is_unavailable(self):
        for year in (2025,2027,'2026',True,None):
            with self.subTest(year=year),self.assertRaises(ref.ReferenceHeld):
                self.lookup({'year':year},research=True)

    def test_pending_registry_holds_reference_amounts(self):
        pending=self.registry.with_name('pending.json')
        pending.write_text(json.dumps(ref.read(self.package/'review-template.json')))
        with self.assertRaises(ref.ReferenceHeld):
            ref.lookup({'year':2026},package=self.package,registry=pending,now=NOW)
        state=ref.status(package=self.package,registry=pending,now=NOW)
        self.assertTrue(state['engineering_complete'])
        self.assertFalse(state['consumer_reference_available'])

    def test_synthetic_exact_review_only_enables_published_lookup(self):
        result=self.lookup({'year':2026,'ids':['b_premium']})
        self.assertEqual(result['mode'],'accepted_published_reference')
        self.assertEqual(result['records'][0]['value'],20290)
        self.assertFalse(result['personal_total_available'])
        self.assertFalse(result['recommendations_available'])
        self.assertIn('CMS-MM14279',[s['id'] for s in result['sources']])
        self.assertIn('NOTE-COMPONENTS',[s['id'] for s in result['qualifications']])

    def test_partial_or_unqualified_review_is_held(self):
        changes=[('accepted_ids',[]),('conditions_and_units_reviewed',False),('receipt','')]
        for key,value in changes:
            previous=copy.deepcopy(self.review)
            self.review[key]=value;self.save_review()
            with self.assertRaises(ref.ReferenceHeld):self.lookup()
            self.review=previous;self.save_review()
        for key in ('qualified_for_scope','independent_of_sales'):
            self.review['reviewer'][key]=None;self.save_review()
            with self.assertRaises(ref.ReferenceHeld):self.lookup()
            self.review['reviewer'][key]=True;self.save_review()

    def test_revocation_and_review_expiry_take_effect_on_next_read(self):
        self.lookup()
        self.review['revoked']=True;self.save_review()
        with self.assertRaises(ref.ReferenceHeld):self.lookup()
        self.review['revoked']=False
        self.review['review_after_utc']='2026-10-25T20:00:00+00:00';self.save_review()
        with self.assertRaises(ref.ReferenceHeld):self.lookup()

    def test_expired_sources_block_research_as_well_as_consumer(self):
        with self.assertRaises(ref.ReferenceHeld):
            ref.lookup({'year':2026},package=self.package,research=True,
                       now=datetime(2026,11,24,tzinfo=timezone.utc))

    def test_changed_payload_fails_before_returning_amounts(self):
        path=self.package/'costs.json';rows=ref.read(path)
        rows[0]['value']=1;path.write_text(json.dumps(rows))
        with self.assertRaises(ref.ReferenceHeld):self.lookup(research=True)

    def test_changed_manifest_wrong_scope_and_conflict_decisions_are_held(self):
        self.review['manifest_sha256']='0'*64;self.save_review()
        with self.assertRaises(ref.ReferenceHeld):self.lookup()
        self.review['manifest_sha256']=ref.digest(self.package/'manifest.json')
        self.review['conflict_decisions']['L01-G04']['decision']='pending';self.save_review()
        with self.assertRaises(ref.ReferenceHeld):self.lookup()

    def test_source_or_code_binding_change_is_held(self):
        m=ref.read(self.package/'manifest.json')
        for key in ('evidence_sha256','code_sha256'):
            current=copy.deepcopy(m)
            first=next(iter(current[key]));current[key][first]='0'*64
            (self.package/'manifest.json').write_text(json.dumps(current))
            with self.assertRaises(ref.ReferenceHeld):self.lookup(research=True)

    def test_reviewed_revision_cannot_be_rebuilt(self):
        with patch.object(builder,'OUT',self.package),patch.object(builder,'REGISTRY',self.registry):
            with self.assertRaisesRegex(ValueError,'frozen'):
                builder.build(self.package)

    def test_complete_reference_checks_and_all_boundary_cases(self):
        report=ref.read(self.package/'checks.json')
        self.assertEqual(report['failed'],0)
        self.assertEqual(len(report['income_boundary_cases']),108)
        self.assertTrue(all(x['passed'] for x in report['income_boundary_cases']))
        bands=ref.read(self.package/'bands.json')
        self.assertEqual(Counter(b['coverage_context'] for b in bands),{'full_b':15,'immuno_b':15,'part_d':15})
        self.assertTrue(all(b['tax_return_basis']['normal_year']==2024 for b in bands))
        self.assertTrue(all(b['published_total_cents'] is None for b in bands if b['coverage_context']=='part_d'))


if __name__=='__main__':
    unittest.main()
