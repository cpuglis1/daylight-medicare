"""Fictional exact-profile pricing safeguards; no network or participant data."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from query_csg_medigap import lookup, sha256


class ExactProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'raw').mkdir()
        self.candidate = root / 'candidate'
        self.candidate.mkdir()
        self.profile = dict(zipcode='34102', age=65, gender='Female', tobacco='Non-Tobacco',
                            effective_date='2026-11-10')
        sources, records = [], []
        for age, amounts in ((65, [10000, 12500]), (70, [17000])):
            source = root / 'raw' / f'fictional-{age}.xlsx'
            source.write_text(f'fictional source bytes {age}')
            scenario = {'zip':'34102','age':age,'gender':'Female','tobacco':'Non-Tobacco',
                        'requested_effective_date':'2026-11-10','fictional':True}
            sources.append({'filename':source.name,'sha256':sha256(source),'scenario':scenario})
            for i, amount in enumerate(amounts):
                records.append({'id':f'{age}-{i}','source_sha256':sha256(source),'variant':'G',
                                'naic':'00001','scenario':scenario,'monthly_cents':amount,
                                'annual_cents':None if i else 110001,
                                'rating_class_raw':f'Fictional class {i}',
                                'select_observed':True if i else None,
                                'personal_quote':False,'consumer_release':'held'})
        with closing(sqlite3.connect(self.candidate / 'research.sqlite3')) as db:
            db.execute('CREATE TABLE rate_observations(id,source_sha256,variant,naic,zip,age,gender,tobacco,requested_date,payload)')
            db.executemany('INSERT INTO rate_observations VALUES (?,?,?,?,?,?,?,?,?,?)', [
                (r['id'],r['source_sha256'],r['variant'],r['naic'],r['scenario']['zip'],r['scenario']['age'],
                 r['scenario']['gender'],r['scenario']['tobacco'],r['scenario']['requested_effective_date'],json.dumps(r)) for r in records])
            db.commit()
        (self.candidate / 'rates.jsonl').write_text('\n'.join(json.dumps(r) for r in records)+'\n')
        (self.candidate / 'benefit-observations.json').write_text('[]\n')
        manifest = {'schema':'csg-medigap-private-candidate/1','consumer_release':'held',
                    'holds':['FICTIONAL_REVIEW_PENDING'],'source_count':2,'sources':sources,
                    'files':{p.name:sha256(p) for p in self.candidate.iterdir()}}
        (self.candidate / 'manifest.json').write_text(json.dumps(manifest))

    def query(self, **changes):
        return lookup(self.candidate, **{**self.profile, **changes})

    def test_exact_age_prices_and_all_classes_remain_distinct(self):
        young, older = self.query(), self.query(age=70)
        self.assertEqual([r['monthly_cents'] for r in young['records']], [10000,12500])
        self.assertEqual([r['monthly_cents'] for r in older['records']], [17000])
        self.assertTrue(young['records'][1]['select_observed'])
        self.assertIsNone(young['records'][1]['annual_cents'])
        self.assertEqual(young['records'][0]['annual_cents'],110001)

    def test_no_nearby_profile_or_date_fallback(self):
        for change in ({'age':66},{'zipcode':'34103'},{'gender':'Male'},
                       {'tobacco':'Tobacco User'},{'effective_date':'2026-11-11'}):
            with self.subTest(change=change):
                result=self.query(**change)
                self.assertEqual(result['status'],'needs_source_export')
                self.assertEqual(result['records'],[])
                for key,value in change.items():
                    source_key={'zipcode':'zip','effective_date':'requested_effective_date'}.get(key,key)
                    self.assertEqual(result['source_export_request']['profile'][source_key],value)

    def test_missing_source_rows_do_not_mean_no_available_plans(self):
        self.assertEqual(self.query(variant='A')['status'],'no_rows_in_source_export')
        self.assertFalse(self.query(variant='A')['all_market_complete'])

    def test_under65_is_not_mapped_to_the_disabled_esrd_bucket(self):
        for age in (39,64):
            self.assertEqual(self.query(age=age)['status'],'unsupported_pilot_age')
            self.assertEqual(self.query(age=age)['records'],[])

    def test_pilot_upper_age_limit_is_not_insurance_ineligibility(self):
        self.assertEqual(self.query(age=74)['status'], 'needs_source_export')
        for age in (75,99,100,120):
            result=self.query(age=age)
            self.assertEqual(result['status'], 'unsupported_pilot_age')
            self.assertEqual(result['reason'], 'Medigap pricing for ages 75+ is not supported in this pilot.')
            self.assertEqual(result['insurance_eligibility'], 'not_determined')
            self.assertEqual(result['records'], [])
            self.assertIsNone(result['source_export_request'])

    def test_unknown_and_invalid_inputs_are_rejected(self):
        for change in ({'age':None},{'age':True},{'gender':None},{'tobacco':'unknown'},
                       {'zipcode':'3410'},{'effective_date':'2027-01-01'},
                       {'effective_date':'2026-02-30'},{'variant':'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.query(**change)

    def test_modified_source_or_candidate_fails_closed(self):
        source=self.candidate.parent/'raw/fictional-65.xlsx'
        source.write_text('changed')
        with self.assertRaisesRegex(ValueError,'source integrity'):
            self.query()

    def test_modified_database_fails_closed(self):
        with (self.candidate/'research.sqlite3').open('ab') as file:
            file.write(b'changed')
        with self.assertRaisesRegex(ValueError,'Candidate integrity'):
            self.query()

    def test_lookup_is_read_only_and_never_accepts_or_quotes(self):
        before={str(p):sha256(p) for p in self.candidate.parent.rglob('*') if p.is_file()}
        result=self.query()
        self.assertEqual(result['consumer_release'],'held')
        self.assertFalse(result['personal_quote'])
        self.assertEqual(result['eligibility'],'not_determined')
        self.assertEqual(before,{str(p):sha256(p) for p in self.candidate.parent.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
