"""Consequential corruption and capability-boundary tests for L09."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l09_build
import l09_reference
import l09_validate

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l09-star-ratings-2026-10-28'


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class L09BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selection=BASE/'CURRENT_REFERENCE.json'
        cls.package=(ROOT/json.loads(selection.read_text())['package']) if selection.exists() else BASE/'build-r4'

    @contextmanager
    def changed(self):
        with tempfile.TemporaryDirectory(prefix='daylight-l09-test-') as tmp:
            dest=Path(tmp)/self.package.name
            shutil.copytree(self.package,dest)
            yield dest

    def reseal(self,package):
        m=json.loads((package/'manifest.json').read_text())
        for rel in m['files_sha256']:m['files_sha256'][rel]=digest(package/rel)
        write(package/'manifest.json',m)
        (package/'SEALED').write_text(digest(package/'manifest.json')+'\n')

    def corrupt_observation(self,change):
        with self.changed() as p:
            rows=json.loads((p/'observations.json').read_text());r=next(r for r in rows if r['kind']=='measure_data' and r['unit']=='percent')
            change(r);write(p/'observations.json',rows)
            con=sqlite3.connect(p/'inventory.sqlite3')
            con.execute('UPDATE observations SET state=?,value_decimal=?,unit=?,payload=? WHERE id=?',
                (r['state'],r['value_decimal'],r['unit'],json.dumps(r,sort_keys=True),r['id']))
            con.commit();con.close();self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Source-derived observation'):
                l09_validate.validate(p)

    def test_complete_population_and_correct_primary_type(self):
        rows=json.loads((self.package/'offerings.json').read_text())
        self.assertEqual(len(rows),82)
        self.assertEqual(len({r['contract'] for r in rows}),24)
        self.assertEqual(sum(r['rating_type']=='overall' for r in rows),61)
        self.assertEqual(sum(r['rating_type']=='part_c_summary' for r in rows),11)
        self.assertEqual(sum(r['rating_type']=='part_d_summary' for r in rows),10)
        self.assertTrue(any(r['contract']=='H5652' for r in rows))
        self.assertFalse(any(r['contract']=='H9917' for r in rows))

    def test_source_validation_passes_entire_model(self):
        result=l09_validate.validate(self.package)
        self.assertTrue(result['passed']);self.assertEqual(result['source_cells_checked'],2448)

    def test_percentage_rescaling_is_detected_after_consistent_rehash(self):
        self.corrupt_observation(lambda r:r.update(value_decimal='0.51'))

    def test_wrong_measurement_period_is_detected(self):
        self.corrupt_observation(lambda r:r.update(measurement_period_raw='01/01/2026 – 12/31/2026'))

    def test_changed_unit_is_detected(self):
        self.corrupt_observation(lambda r:r.update(unit='stars'))

    def test_wrong_contract_is_detected(self):
        self.corrupt_observation(lambda r:r.update(contract='H9917'))

    def test_missing_state_cannot_be_replaced_by_zero(self):
        with self.changed() as p:
            rows=json.loads((p/'observations.json').read_text());r=next(r for r in rows if r['state']=='not_required')
            r.update(state='rated',value_decimal='0',unit='stars');write(p/'observations.json',rows);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Source-derived observation'):l09_validate.validate(p)

    def test_swapped_summary_type_is_detected(self):
        with self.changed() as p:
            rows=json.loads((p/'offerings.json').read_text());r=next(r for r in rows if r['product']=='MA-only')
            r['rating_type']='overall';r['primary_observation_id']='2026:'+r['contract']+':summary:overall'
            write(p/'offerings.json',rows);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Offering identity/type'):l09_validate.validate(p)

    def test_dropped_offering_cannot_shrink_denominator(self):
        with self.changed() as p:
            rows=json.loads((p/'offerings.json').read_text());rows.pop();write(p/'offerings.json',rows)
            coverage=json.loads((p/'coverage.json').read_text());coverage['offerings']=81;write(p/'coverage.json',coverage);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Offering identity/type'):l09_validate.validate(p)

    def test_truncated_technical_definition_is_detected(self):
        with self.changed() as p:
            rows=json.loads((p/'measure-definitions.json').read_text());segment=rows[0]['segments'][0]
            segment['text']=segment['text'][:80];segment['sha256']=hashlib.sha256(segment['text'].encode()).hexdigest()
            write(p/'measure-definitions.json',rows);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Definition page/section'):l09_validate.validate(p)

    def test_context_deletion_is_detected(self):
        with self.changed() as p:
            rows=json.loads((p/'context-tables.json').read_text());rows[0]['rows'].pop();write(p/'context-tables.json',rows);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'Context table'):l09_validate.validate(p)

    def test_unknown_source_message_and_invalid_stars_are_rejected(self):
        for raw in ['NEW CMS TOKEN','0','5.5','NaN','Infinity','4%']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):l09_build.scalar(raw,'measure_stars')
        for raw,state in [('','blank'),('No data available','no_data'),('Plan too small to be measured','too_small')]:
            value=l09_build.scalar(raw,'measure_stars');self.assertEqual(value['state'],state);self.assertIsNone(value['value_decimal'])

    def test_consumer_lookup_remains_held(self):
        with self.assertRaises(l09_reference.ReferenceHeld):l09_reference.lookup({'year':2026},self.package)
        with self.assertRaises(l09_reference.ReferenceHeld):l09_reference.lookup({'year':2026},self.package,research='true')

    def test_research_lookup_and_bounded_pagination(self):
        out=l09_reference.lookup({'year':2026,'offering_ids':['2026:H5652:001:000'],'kinds':['measure_stars'],'limit':10},self.package,research=True)
        self.assertEqual(out['total_observations'],45);self.assertEqual(len(out['observations']),10)
        self.assertEqual(out['next_offset'],10);self.assertFalse(out['consumer_release_enabled'])

    def test_wrong_year_segment_geography_and_commercial_inputs_fail(self):
        cases=[{'year':2027},{'year':True},{'year':2026,'county_fips':'12071'},
            {'year':2026,'commission':100},{'year':2026,'drug':'example'},
            {'year':2026,'offering_ids':['2026:H1045:048:000']},
            {'year':2026,'contract_ids':['H9917']},{'year':2026,'limit':251},
            {'year':2026,'offering_ids':None},{'year':2026,'contract_ids':[]},
            {'year':2026,'offset':-1},{'year':2026,'kinds':['personal_fit']}]
        for request in cases:
            with self.subTest(request=request),self.assertRaises(ValueError):l09_reference.lookup(request,self.package,research=True)

    def test_mutation_invalidates_exact_validation_receipt(self):
        with self.changed() as p:
            shutil.copy2(self.package.parent/(self.package.name+'-validation.json'),p.parent/(p.name+'-validation.json'))
            rows=json.loads((p/'observations.json').read_text());rows[0]['raw']='3' if rows[0]['raw']!='3' else '4';write(p/'observations.json',rows);self.reseal(p)
            with self.assertRaises(l09_reference.ReferenceHeld):l09_reference.lookup({'year':2026},p,research=True)

    def test_immutable_build_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'new immutable'):l09_build.build(BASE/'acquisition-r1',self.package)


if __name__=='__main__':unittest.main()
