"""Published-reference boundaries and independent-audit fault injection.

Review receipts below are synthetic temporary fixtures, never actual approval.
"""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import l04_build as build
import l04_reference as reference
import l04_validate as audit

PACKAGE = reference.PACKAGE
NOW = datetime(2026,10,25,22,tzinfo=timezone.utc)


class PublishedPDPTests(unittest.TestCase):
    def test_signed_component_and_exact_precision(self):
        self.assertEqual(build.money('($21.50)'),-2150)
        self.assertEqual(build.money('$0.00 '),0)
        self.assertEqual(build.money('$1,234.56'),123456)
        for raw in ('NaN','Infinity','$1.001','($2.00','2e2'):
            with self.subTest(raw=raw),self.assertRaises(build.BuildError):build.money(raw)

    def test_unknown_and_not_applicable_are_not_zero(self):
        field = next(f for f in build.read(build.BASE/'field-map.json')['fields'] if f['key']=='annual_deductible')
        for raw,state,value in [('', 'missing',None),('Not Applicable','not_applicable',None),('Not Available','unavailable',None),('$0.00','published',0)]:
            with self.subTest(raw=raw):
                result = build.fact(raw,field)
                self.assertEqual((result['state'],result['value']),(state,value))
                self.assertEqual(result['value_encoding'],'integer_cents')

    def test_no_unreviewed_flag_coercion(self):
        field = next(f for f in build.read(build.BASE/'field-map.json')['fields'] if f['key']=='national_pdp')
        with self.assertRaises(build.BuildError):build.fact('Maybe',field)

    def test_build_is_immutable(self):
        with self.assertRaises(build.BuildError):build.build(PACKAGE)

    def test_wrong_source_year_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'acquisition-r1').mkdir()
            source = build.read(build.L02/'acquisition-r1/source-manifest.json')
            source['sources']['landscape']['benefit_year'] = '2027'
            (root/'acquisition-r1/source-manifest.json').write_text(json.dumps(source))
            with patch.object(build,'L02',root),self.assertRaisesRegex(build.BuildError,'Wrong-year'):
                build.build(root/'out')
            self.assertFalse((root/'out').exists())

    def test_real_source_audit_completed(self):
        result = reference.read(PACKAGE.parent/(PACKAGE.name+'-validation.json'))
        self.assertEqual(result['failed'],0)
        self.assertTrue(result['source_fidelity_passed'])
        self.assertEqual(result['primary_field_observations_checked'],310)
        self.assertEqual(result['published_fl_sets'],{'landscape':10,'pbp':10,'monthly':10})

    def test_all_florida_counties_use_same_regional_reference(self):
        expected = reference.project({'year':2026,'state':'FL'},PACKAGE)
        with closing(sqlite3.connect(PACKAGE/'inventory.sqlite3')) as db:
            counties = [r[0] for r in db.execute('SELECT fips FROM counties')]
        self.assertEqual(len(counties),67)
        for fips in counties:
            with self.subTest(fips=fips):
                self.assertEqual(reference.project({'year':2026,'county_fips':fips},PACKAGE),expected)

    def test_wrong_scope_and_personal_or_commercial_inputs_refused(self):
        requests = [
            {'year':2027,'state':'FL'},{'year':True,'state':'FL'},{'year':'2026','state':'FL'},
            {'year':2026,'state':'NY'},{'year':2026,'pdp_region':'09'},
            {'year':2026,'county_fips':'36061'},{'year':2026,'county_fips':'34102'},
            {'year':2026,'county_fips':'00000'},{'year':2026},
            {'year':2026,'state':'FL','income':25000},{'year':2026,'state':'FL','commission':5},
            {'year':2026,'state':'FL','research':True},{'year':2026,'state':'FL','medications':[]},
            {'year':2026,'state':'FL','ids':['unknown']},
        ]
        for request in requests:
            with self.subTest(request=request),self.assertRaises(reference.ReferenceError):
                reference.project(request,PACKAGE)

    def test_missing_review_holds_accepted_lookup_but_research_is_inspectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp)/'no-review.json'
            with self.assertRaises(reference.ReferenceHeld):
                reference.lookup({'year':2026,'county_fips':'12021'},package=PACKAGE,registry=registry,now=NOW)
            result = reference.lookup({'year':2026,'county_fips':'12021'},package=PACKAGE,registry=registry,research=True,now=NOW)
            self.assertEqual(result['records'],reference.read(PACKAGE/'records.json'))
            self.assertEqual(result['mode'],'research_pending_review')
            self.assertEqual(result['personal_applicability'],'not_assessed')
            self.assertFalse(result['recommendations_available'])
            self.assertFalse(result['enrollment_available'])

    def fixture_review(self):
        manifest = reference.read(PACKAGE/'manifest.json')
        return {'schema':'l04-published-review/1','decision':'accepted','revoked':False,
                'package_id':manifest['package_id'],'manifest_sha256':reference.digest(PACKAGE/'manifest.json'),
                'validation_sha256':reference.digest(PACKAGE.parent/(PACKAGE.name+'-validation.json')),
                'accepted_ids':sorted(r['offering_id'] for r in reference.read(PACKAGE/'records.json')),
                'accepted_field_map_sha256':manifest['files_sha256']['field-map.json'],
                'accepted_gaps_sha256':manifest['files_sha256']['gaps.json'],
                'reviewer':{'name':'SYNTHETIC TEST FIXTURE','role':'Synthetic test only','qualified_for_scope':True,'independent_of_sales':True},
                'receipt':'SYNTHETIC: never actual data acceptance','reviewed_at_utc':'2026-10-25T21:00:00+00:00','review_after_utc':'2026-11-23T00:00:00+00:00'}

    def test_review_binds_exact_population_fields_gaps_and_validation(self):
        original = self.fixture_review()
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp)/'synthetic.json'
            registry.write_text(json.dumps(original))
            reference.require_review(PACKAGE,registry,NOW)
            for field,value in [('revoked',True),('accepted_ids',original['accepted_ids'][:-1]),('accepted_field_map_sha256','bad'),('accepted_gaps_sha256','bad'),('validation_sha256','bad'),('decision','pending'),('review_after_utc','2026-10-24T00:00:00+00:00')]:
                changed = deepcopy(original);changed[field] = value;registry.write_text(json.dumps(changed))
                with self.subTest(field=field),self.assertRaises(reference.ReferenceHeld):reference.require_review(PACKAGE,registry,NOW)
            changed = deepcopy(original);changed['reviewer']['qualified_for_scope'] = False;registry.write_text(json.dumps(changed))
            with self.assertRaises(reference.ReferenceHeld):reference.require_review(PACKAGE,registry,NOW)

    def test_stale_or_revoked_reference_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp)/'synthetic.json';review = self.fixture_review();registry.write_text(json.dumps(review))
            with self.assertRaises(reference.ReferenceHeld):
                reference.require_review(PACKAGE,registry,datetime(2026,11,25,tzinfo=timezone.utc))
            review['revoked'] = True;registry.write_text(json.dumps(review))
            with self.assertRaises(reference.ReferenceHeld):reference.require_review(PACKAGE,registry,NOW)

    def test_unknown_ids_and_duplicate_ids_rejected(self):
        identity = reference.read(PACKAGE/'records.json')[0]['offering_id']
        for ids in ([],[identity,identity],['unknown']):
            with self.subTest(ids=ids),self.assertRaises(reference.ReferenceError):
                reference.project({'year':2026,'state':'FL','ids':ids},PACKAGE)

    def test_actual_negative_component_and_standard_vs_lis_basis_preserved(self):
        records = {r['offering_id']:r['fields'] for r in reference.project({'year':2026,'state':'FL'},PACKAGE)}
        wellcare = records['2026:S4802:146:000']
        self.assertEqual([wellcare[k]['value'] for k in ('basic_premium','supplemental_premium','total_premium')],[-2150,2150,0])
        humana = records['2026:S5884:190:000']
        self.assertEqual(humana['total_premium']['value'],2590)
        self.assertEqual(humana['low_income_beneficiary_premium']['value'],2110)
        self.assertEqual(reference.read(PACKAGE/'coverage.json')['material_source_differences'],[])

    def copy_package(self,root):
        target = root/'mutated'
        shutil.copytree(PACKAGE,target)
        shutil.copyfile(PACKAGE.parent/(PACKAGE.name+'-validation.json'),root/'mutated-validation.json')
        return target

    def rehash_database(self,target):
        manifest = reference.read(target/'manifest.json')
        manifest['files_sha256']['inventory.sqlite3'] = reference.digest(target/'inventory.sqlite3')
        (target/'manifest.json').write_text(json.dumps(manifest))

    def test_changed_amount_detected_even_after_database_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self.copy_package(Path(tmp))
            with closing(sqlite3.connect(target/'inventory.sqlite3')) as db, db:
                ordinal,raw = db.execute("SELECT ordinal,fields_json FROM catalog WHERE region='11' AND state='FL' LIMIT 1").fetchone()
                fields = json.loads(raw);fields['total_premium']['value'] += 1
                db.execute('UPDATE catalog SET fields_json=? WHERE ordinal=?',(json.dumps(fields),ordinal))
            self.rehash_database(target)
            result = audit.validate(target)
            self.assertFalse(result['source_fidelity_passed'])
            self.assertTrue(any(f['check']=='modeled_field_semantics' for f in result['failure_examples']))
            with self.assertRaises(reference.ReferenceHeld):reference.verify(target)

    def test_missing_plan_detected_without_shrinking_expected_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self.copy_package(Path(tmp))
            with closing(sqlite3.connect(target/'inventory.sqlite3')) as db, db:
                db.execute("DELETE FROM catalog WHERE ordinal=(SELECT ordinal FROM catalog WHERE region='11' AND state='FL' LIMIT 1)")
            self.rehash_database(target)
            result = audit.validate(target)
            self.assertFalse(result['source_fidelity_passed'])
            self.assertEqual(result['published_fl_sets']['landscape'],10)
            self.assertTrue(any(f['check']=='pdp_row_present' for f in result['failure_examples']))


if __name__ == '__main__':unittest.main()
