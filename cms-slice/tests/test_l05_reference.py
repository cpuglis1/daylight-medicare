"""Population, fault-injection and boundary checks for the L05 reference."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cms-slice/scripts'))
from l05_reference import project,verify
from l05_validate import validate
from l05_acquire import request

PACKAGE=ROOT/'docs/data/l05-drug-coverage-2026-10-25/build-r3'


class PublishedDrugReference(unittest.TestCase):
    def test_audit_covers_population_and_every_native_field(self):
        audit=json.loads(PACKAGE.with_name(PACKAGE.name+'-validation.json').read_text())
        self.assertTrue(audit['passed'])
        self.assertEqual(audit['failed'],0)
        self.assertEqual(audit['target_plans_checked'],71)
        self.assertEqual(audit['formulary_ids_checked'],26)
        self.assertEqual(audit['scoped_rows_checked'],{'basic':87075,'excluded':309,'indication':0})
        self.assertEqual(sum(audit['modeled_source_fields_checked'].values()),1047990)
        self.assertEqual(audit['drug_identity_records_checked'],4547)
        for profile in audit['source_quality'].values():self.assertTrue(all(v==0 for v in profile.values()))
        verify(PACKAGE)

    def test_exact_lookup_for_every_target_and_all_restriction_fields(self):
        plans=json.loads((PACKAGE/'plans.json').read_text())
        with closing(sqlite3.connect(PACKAGE/'inventory.sqlite3')) as db:
            self.assertEqual(dict(db.execute('SELECT table_name,count(*) FROM drug_rows GROUP BY table_name')),{'basic':87075,'excluded':309})
            self.assertEqual(dict(db.execute('SELECT offering_id,formulary_id FROM plans')),{p['offering_id']:p['formulary_id'] for p in plans})
            for p in plans:
                code,ndc,raw=db.execute('SELECT rxcui,ndc,raw_json FROM drug_rows WHERE table_name="basic" AND formulary_id=? ORDER BY ordinal LIMIT 1',(p['formulary_id'],)).fetchone()
                result=project(PACKAGE,{'year':2026,'offering_id':p['offering_id'],'rxcui':code,'ndc':ndc})
                self.assertEqual(result['plan'],p)
                got=next(r for r in result['matches'] if r['table']=='basic')
                self.assertEqual({k:v['raw'] for k,v in got['fields'].items()},json.loads(raw))
                self.assertFalse(result['personal_price_available'])
                self.assertFalse(result['recommendations_available'])
                self.assertEqual(got['drug_identity']['rxcui'],code)

    def test_supplemental_encoding_grain_and_proxy_ndc_are_preserved(self):
        with closing(sqlite3.connect(PACKAGE/'inventory.sqlite3')) as db:
            row=db.execute('SELECT contract_id,plan_id,rxcui,modeled_json FROM drug_rows WHERE table_name="excluded" AND json_extract(raw_json,\'$.QUANTITY_LIMIT_YN\')="1" LIMIT 1').fetchone()
            contract,number,code,fields=row
            ident=db.execute('SELECT offering_id FROM plans WHERE offering_id LIKE ? LIMIT 1',('2026:'+contract+':'+number+':%',)).fetchone()[0]
            result=project(PACKAGE,{'year':2026,'offering_id':ident,'rxcui':code})
            got=next(r for r in result['matches'] if r['table']=='excluded')
            self.assertEqual(got['fields'],json.loads(fields))
            self.assertIs(got['fields']['QUANTITY_LIMIT_YN']['value'],True)
            self.assertEqual(got['fields']['QUANTITY_LIMIT_YN']['raw'],'1')
            self.assertIn('no segment asserted',got['source_grain'])
            ident,ndc=db.execute('SELECT p.offering_id,d.ndc FROM plans p JOIN drug_rows d ON p.formulary_id=d.formulary_id WHERE d.ndc LIKE "0%" LIMIT 1').fetchone()
            result=project(PACKAGE,{'year':2026,'offering_id':ident,'ndc':ndc})
            self.assertTrue(result['matches'])
            self.assertEqual(result['supplemental_ndc_check'],'not_possible_without_RxCUI')
            self.assertTrue(all(r['fields']['NDC']['value']==ndc for r in result['matches']))

    def test_absence_is_not_a_coverage_denial(self):
        result=project(PACKAGE,{'year':2026,'offering_id':'2026:S5921:383:000','rxcui':'99999999999999'})
        self.assertEqual(result['list_state'],'not_listed_in_published_snapshot')
        self.assertEqual(result['total_matching_source_rows'],0)
        self.assertEqual(result['personal_clinical_approval'],'not_assessed')

    def test_wrong_year_segment_and_personal_commercial_requests_fail(self):
        good={'year':2026,'offering_id':'2026:S5921:383:000','rxcui':'1551300'}
        bad=[{**good,'year':2027},{**good,'offering_id':'2026:S5921:383:001'},
             {**good,'commission':100},{**good,'diagnosis':'example'},
             {**good,'ndc':2133380},{**good,'rxcui':'1551300 OR 1=1'},
             {**good,'limit':True},{**good,'limit':101},{**good,'offset':-1}]
        for r in bad:
            with self.subTest(request=r),self.assertRaises(ValueError):project(PACKAGE,r)

    def test_inherited_stops_fail_before_network_access(self):
        with tempfile.TemporaryDirectory() as name:
            for url in ['https://www.uhc.com/example','https://wellcare.com/example','https://www.medicare.gov/example','http://www.cms.gov/example']:
                with self.subTest(url=url),self.assertRaises(ValueError):request(url,Path(name))

    def test_independent_audit_detects_rehashed_data_loss_and_changes(self):
        with tempfile.TemporaryDirectory() as name:
            clone=Path(name)/'faults';shutil.copytree(PACKAGE,clone)
            # Rehash deliberate damage: this tests source comparison, not merely hashes.
            plans=json.loads((clone/'plans.json').read_text());lost=plans.pop()['offering_id']
            (clone/'plans.json').write_text(json.dumps(plans))
            identities=json.loads((clone/'identities.json').read_text());identities[0]['name']='wrong strength and formulation'
            (clone/'identities.json').write_text(json.dumps(identities))
            fieldmap=json.loads((clone/'field-map.json').read_text());fieldmap['excluded']['QUANTITY_LIMIT_YN']['flag_encoding']='Y/N'
            (clone/'field-map.json').write_text(json.dumps(fieldmap))
            with closing(sqlite3.connect(clone/'inventory.sqlite3')) as db, db:
                db.execute('DELETE FROM plans WHERE offering_id=?',(lost,))
                db.execute('DELETE FROM drug_rows WHERE table_name="basic" AND ordinal=(SELECT max(ordinal) FROM drug_rows WHERE table_name="basic")')
                ordinal,modeled=db.execute('SELECT ordinal,modeled_json FROM drug_rows WHERE table_name="excluded" LIMIT 1').fetchone()
                modeled=json.loads(modeled);modeled.pop('TIER');modeled['QUANTITY_LIMIT_YN']['value']=not modeled['QUANTITY_LIMIT_YN']['value']
                db.execute('UPDATE drug_rows SET modeled_json=? WHERE table_name="excluded" AND ordinal=?',(json.dumps(modeled),ordinal))
                db.execute('UPDATE drug_identities SET payload=? WHERE rxcui=?',(json.dumps(identities[0]),identities[0]['rxcui']))
            manifest=json.loads((clone/'manifest.json').read_text());manifest['year']=2027
            manifest['files']={n:hashlib.sha256((clone/n).read_bytes()).hexdigest() for n in manifest['files']}
            (clone/'manifest.json').write_text(json.dumps(manifest))
            result=validate(clone)
            kinds={r['check'] for r in result['failure_examples']}
            self.assertFalse(result['passed'])
            self.assertTrue({'package_year_and_schema','all_71_plan_records_present','every_scoped_source_row_present','no_modeled_field_omission','every_modeled_source_field','field_map_semantics','every_identity_field_against_source'}<=kinds,kinds)
            with self.assertRaises(ValueError):verify(clone)

    def test_condition_evidence_retains_text_without_claiming_snapshot_criteria(self):
        base=PACKAGE.parent;assessment=base/'condition-assessment-r1'
        audit=json.loads((base/'condition-assessment-r1-validation.json').read_text())
        self.assertTrue(audit['passed'])
        self.assertEqual(audit['condition_contexts_checked'],62193)
        self.assertEqual(audit['PDF_documents_checked'],16)
        self.assertEqual(audit['PDF_pages_checked'],3050)
        report=json.loads((assessment/'assessment.json').read_text())
        self.assertEqual(report['accepted_snapshot_criterion_bindings'],0)
        self.assertFalse(report['published_condition_reference_complete'])
        manifest=json.loads((assessment/'manifest.json').read_text())
        for name,digest in manifest['inputs'].items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((assessment/name).read_bytes()).hexdigest(),digest,name)


if __name__=='__main__':unittest.main()
