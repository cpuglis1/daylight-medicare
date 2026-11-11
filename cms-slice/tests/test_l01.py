"""Meaningful L01 boundaries, evidence integrity and separate acceptance controls.

Synthetic reviews exist ONLY in disposable test directories. They do not approve
the checked-in research package or the legacy consumer release.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from l01 import L01, Acceptance, L01Error, L01Held, PACKAGE, digest, load, value_cell, verify
from l01_acquire import dump,require_research_revision
from l01_http import attach
from l01_validate import AS_OF, report
from l01_maintenance import compare
from consumer_acceptance import ConsumerAcceptance, AcceptanceRequired


def synthetic_registry(package):
    receipt = {'decision': 'accepted', 'revoked': False,
               'reviewer': {'name': 'SYNTHETIC TEST ONLY', 'role': 'medicare_subject_matter_reviewer', 'independent_of_sales': True},
               'receipt': 'synthetic-not-a-real-human-acceptance', 'reviewed_at_utc': '2026-10-25T17:00:00+00:00', 'review_after_utc': '2026-11-01T00:00:00+00:00'}
    requirements = load(package / 'requirements.json')
    return {'schema': 'l01-acceptance/1', 'package_id': 'L01-US-2026-r1',
            'manifest_sha256': hashlib.sha256((package / 'manifest.json').read_bytes()).hexdigest(),
            'package_review': copy.deepcopy(receipt),
            'capabilities': {id: {**copy.deepcopy(receipt), 'binding_sha256': digest(binding), 'output_schema': 'l01-result/1'} for id, binding in requirements['capabilities'].items()},
            'claims': {record['id']: {**copy.deepcopy(receipt), 'claim_sha256': digest(record), 'conditions_reviewed': True} for record in load(package / 'facts.json') + load(package / 'bands.json') + load(package / 'rules.json')},
            'conflicts': {record['id']: {**copy.deepcopy(receipt), 'conflict_sha256': digest(record), 'canonical_disposition': 'SYNTHETIC proposed canonical for control test only'} for record in load(package / 'conflicts.json')}}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.service = L01(now=lambda: AS_OF)
        self.base = {'operation': 'premiums', 'year': 2026, 'month': 10, 'state': 'FL', 'county_fips': '12021', 'covered_months': ['2026-10'], 'coverage_context': 'full_b'}

    def test_all_source_expected_cases_and_table_partitions(self):
        coverage, result = report(write=False)
        self.assertTrue(result['all_case_checks_passed'], [c for c in result['case_results'] if not c['passed']])
        self.assertEqual(108, coverage['rule_and_case_coverage']['income_boundary_cases'])
        self.assertEqual(45, coverage['annual_table_reconciliation']['expanded_bands'])
        # No gaps or overlaps at any boundary, including negative reported MAGI.
        bands = load(PACKAGE / 'bands.json')
        for context in ['full_b', 'immuno_b', 'part_d']:
            for filing in ['individual', 'joint', 'separate_together']:
                rows = [b for b in bands if b['coverage_context'] == context and b['filing_status'] == filing]
                self.assertIsNone(rows[0]['lower_cents'])
                self.assertIsNone(rows[-1]['upper_cents'])
                for a, b in zip(rows, rows[1:]):
                    self.assertEqual(a['upper_cents'], b['lower_cents'])
                    self.assertNotEqual(a['upper_inclusive'], b['lower_inclusive'])

    def test_county_reuse_another_state_and_unsupported_territory(self):
        original = self.service.research(self.base)
        for state, county in [('FL', '12086'), ('CA', '06037'), ('NY', '36061')]:
            changed = self.service.research(dict(self.base, state=state, county_fips=county))
            self.assertEqual(original, changed)
        self.assertEqual('unavailable', self.service.research(dict(self.base, state='PR'))['state'])

    def test_unknown_and_wrong_year_never_default_to_zero_or_current_year(self):
        for year in [2025, 2027, None, '2026', True]:
            r = self.service.research(dict(self.base, year=year))
            self.assertEqual('unavailable', r['state'])
            self.assertEqual([], r['components'])
        for field in ['month', 'coverage_context', 'covered_months']:
            request = dict(self.base);request.pop(field)
            self.assertEqual('unknown', self.service.research(request)['state'])
        for bad in [['2026-10', '2026-10'], ['2027-01'], ['2026-01']]:
            with self.assertRaises(L01Error):self.service.research(dict(self.base, covered_months=bad))

    def test_minimal_intake_and_irmaa_exception_routes(self):
        request = {'operation': 'irmaa', 'year': 2026, 'month': 10, 'state': 'FL', 'covered_months': ['2026-10'], 'coverage_context': 'full_b', 'filing_status': 'individual', 'magi_cents': 10900000, 'tax_year': 2024, 'return_basis': 'normal_2024', 'changed_income': False, 'amended_return': False}
        for key in ['filing_status', 'magi_cents', 'tax_year', 'return_basis', 'changed_income', 'amended_return']:
            q = dict(request);q.pop(key)
            self.assertEqual('unknown', self.service.research(q)['state'])
        self.assertEqual('value', self.service.research(dict(request, tax_year=2023, return_basis='2023_because_2024_unavailable'))['state'])
        self.assertEqual('unknown', self.service.research(dict(request, tax_year=2023))['state'])
        for flag in ['changed_income', 'amended_return']:
            self.assertEqual('unavailable', self.service.research(dict(request, **{flag: True}))['state'])
        self.assertEqual('unavailable', self.service.research(dict(request, filing_status='married_separate', lived_together=False))['state'])
        self.assertEqual('unknown', self.service.research(dict(request, filing_status='separate_together', lived_together=False))['state'])
        d = self.service.research(dict(request, coverage_context='part_d', magi_cents=13700001))
        self.assertEqual(3750, d['components'][0]['value_cents'])
        for key in ['plan_premium_cents', 'd_adjustment_cents', 'a_category']:
            with self.assertRaises(L01Error):self.service.research(dict(request, **{key: 0}))

    def test_calendar_dates_cross_year_and_repeat_periods(self):
        q = {'operation': 'hospital_stay', 'year': 2026, 'month': 1, 'state': 'FL', 'first_day': 1, 'days': 1, 'benefit_period_id': 'synthetic', 'benefit_period_start': '2026-01-31', 'service_start_date': '2026-01-31', 'deductible_satisfied': True, 'reserve_remaining': 60, 'use_reserve': True, 'coverage_confirmed': True}
        for day in [29, 30, 31]:
            for month in [1, 3, 5, 7, 8, 10, 12]:
                r = self.service.research(dict(q, month=month, benefit_period_start=f'2026-{month:02d}-{day:02d}', service_start_date=f'2026-{month:02d}-{day:02d}'))
                self.assertEqual('value', r['state'])
        self.assertEqual('unavailable', self.service.research(dict(q, month=12, days=2, benefit_period_start='2026-12-31', service_start_date='2026-12-31'))['state'])
        with self.assertRaises(L01Error):self.service.research(dict(q, benefit_period_start='2026-02-01'))
        for days, ended in [(59,False),(60,True),(61,True)]:
            r = self.service.research({'operation':'benefit_reset','year':2026,'month':10,'state':'FL','days_out':days,'inpatient_definition_confirmed':True})
            self.assertEqual(ended,r['benefit_period_ended'])
        q.update(month=1, service_start_date='2026-01-01', benefit_period_start='2026-01-01', deductible_satisfied=False)
        # Engineering arithmetic can be inspected after an explicitly synthetic
        # resolution; the real registry remains pending.
        r = self.service.research(q, resolved_conflicts={'L01-G09'})
        self.assertEqual(173600, sum(c['value_cents'] for c in r['components']))
        second = self.service.research(dict(q, month=10, service_start_date='2026-10-01', benefit_period_id='second', benefit_period_start='2026-10-01'), resolved_conflicts={'L01-G09'})
        self.assertEqual(347200, sum(c['value_cents'] for c in r['components'] + second['components']))

    def test_zero_unknown_other_states_roundtrip_without_coercion(self):
        for state in ['unknown', 'unavailable', 'conflicting', 'expired', 'not_applicable', 'no_fixed_annual_cap']:
            value = value_cell(state, reason='synthetic state envelope, no factual claim')
            self.assertEqual(value, json.loads(json.dumps(value)))
            self.assertIsNone(value['value_cents'])
            with self.assertRaises(L01Error):value_cell(state, 0)
        self.assertEqual(0, value_cell('value',0)['value_cents'])

    def test_range_only_scenarios_and_public_band_browsing_need_no_exact_income(self):
        q={'operation':'irmaa','year':2026,'month':10,'state':'FL','covered_months':['2026-10'],'coverage_context':'full_b','filing_status':'individual','tax_year':2024,'return_basis':'normal_2024','changed_income':False,'amended_return':False,
           'magi_range_cents':{'lower_cents':10900000,'upper_cents':13700000,'lower_inclusive':False,'upper_inclusive':True}}
        self.assertEqual(28410,self.service.research(q)['components'][0]['value_cents'])
        broad=copy.deepcopy(q);broad['magi_range_cents']['lower_inclusive']=True
        self.assertEqual('unknown',self.service.research(broad)['state'])
        with self.assertRaises(L01Error):self.service.research(dict(q,magi_cents=11000000))
        view=self.service.research({'operation':'published_cost_lookup','year':2026,'month':10,'state':'FL','band_ids':['L01-IRMAA-part_d-individual-1']})
        self.assertEqual(1450,view['bands'][0]['adjustment_cents'])

    def test_commercial_inputs_rejected_and_replay_deterministic(self):
        for key in ['commission', 'carrier_contract', 'revenue_score', 'source_override', 'research_mode', 'acceptance', 'assistance_payment_cents']:
            with self.assertRaises(L01Error):self.service.research(dict(self.base, **{key:'CANARY'}))
        self.assertEqual(self.service.research(self.base), self.service.research(self.base))
        self.assertFalse(self.service.research(self.base)['reported_inputs_are_verified'])
        self.assertFalse(Acceptance().status()['consumer_ready'])


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.package = Path(self.temp.name) / 'copy'
        shutil.copytree(PACKAGE, self.package)
        self.registry = Path(self.temp.name) / 'synthetic-review.json'
        self.data = synthetic_registry(self.package)
        dump(self.registry, self.data)
        self.gate = Acceptance(self.package, self.registry, now=lambda: AS_OF)
        self.service = L01(self.package, self.gate, now=lambda: AS_OF)
        self.request = {'operation':'premiums','year':2026,'month':10,'state':'FL','covered_months':['2026-10'],'coverage_context':'full_b'}

    def tearDown(self):self.temp.cleanup()

    def test_relocated_copy_binds_actual_read_payload_and_raw_bytes(self):
        self.assertEqual('accepted_component', self.service.evaluate(self.request)['mode'])
        for filename in ['facts.json','bands.json','requirements.json','sources.json','dependencies.json']:
            p = self.package / filename; original = p.read_bytes();p.write_bytes(original + b' ')
            with self.assertRaises(L01Held):self.service.evaluate(self.request)
            p.write_bytes(original)
        p = next((self.package/'raw').iterdir());original=p.read_bytes();p.write_bytes(original+b'!')
        with self.assertRaises(L01Held):self.service.evaluate(self.request)
        p.write_bytes(original)
        p = self.package/'facts.json';p.unlink()
        with self.assertRaises(L01Held):self.service.evaluate(self.request)

    def test_revocation_expiry_scope_output_and_rule_failures(self):
        self.service.evaluate(self.request)
        mutations = [lambda r:r['package_review'].update(revoked=True), lambda r:r['claims']['b_premium'].update(decision='pending'),
                     lambda r:r['claims']['premium_months'].update(conditions_reviewed=False), lambda r:r['capabilities']['premiums'].update(binding_sha256='bad'),
                     lambda r:r['claims']['b_premium']['reviewer'].update(name=''),lambda r:r['claims'].pop('b_premium'),
                     lambda r:r['package_review'].update(review_after_utc='2026-10-24T00:00:00+00:00')]
        for mutation in mutations:
            d=copy.deepcopy(self.data);mutation(d);dump(self.registry,d)
            with self.assertRaises(L01Held):self.service.evaluate(self.request)
        dump(self.registry,self.data)
        self.assertEqual(20290,self.service.evaluate(self.request)['components'][0]['value_cents'])
        expired = L01(self.package, self.gate, now=lambda:datetime(2026,12,1,tzinfo=timezone.utc))
        with self.assertRaises(L01Held) as context:expired.research(self.request)
        self.assertEqual('expired',context.exception.state)
        # An L01 review cannot make the existing plan release accepted.
        with self.assertRaises(AcceptanceRequired):ConsumerAcceptance(registry=self.registry).require_release()

    def test_reviewed_or_revoked_revision_cannot_be_rebuilt_or_refreshed(self):
        with self.assertRaisesRegex(ValueError,'frozen'):require_research_revision(self.package,self.registry)
        self.data['package_review']['decision']='revoked'
        self.data['package_review']['revoked']=True
        dump(self.registry,self.data)
        with self.assertRaisesRegex(ValueError,'frozen'):require_research_revision(self.package,self.registry)
        self.data['package_review'].update(decision='pending',receipt='',reviewed_at_utc=None)
        self.data['claims']={};dump(self.registry,self.data)
        require_research_revision(self.package,self.registry)

    def test_unaccepted_conflict_stays_withheld_under_partial_acceptance(self):
        q = dict(self.request,operation='irmaa',coverage_context='full_b',filing_status='married_separate',lived_together=True,magi_cents=39100000,tax_year=2024,return_basis='normal_2024',changed_income=False,amended_return=False)
        self.data['conflicts']={};dump(self.registry,self.data)
        with self.assertRaises(L01Held):self.service.evaluate(q)
        dump(self.registry,synthetic_registry(self.package))
        self.assertEqual(68990,self.service.evaluate(q)['components'][0]['value_cents'])
        self.assertEqual('proposed_pending_independent_review',load(PACKAGE/'conflicts.json')[0]['status'])

    def test_wrong_year_source_evidence_and_rollover_diff(self):
        m=load(self.package/'manifest.json');m.update(year=2027,package_id='L01-US-2027-r1');dump(self.package/'manifest.json',m)
        with self.assertRaises(L01Held):self.service.research(dict(self.request,year=2027))
        for name in ['facts.json','bands.json']:
            records=load(self.package/name)
            for record in records:record.update(version='2027-r1',effective_from='2027-01-01',effective_until='2028-01-01')
            self.rebind_disposable_payload(name,records)
        with self.assertRaisesRegex(L01Held,'Raw evidence content year'):
            self.service.research(dict(self.request,year=2027))
        altered=load(self.package/'facts.json');altered[0]['value']+=1;dump(self.package/'facts.json',altered)
        delta=compare(PACKAGE,self.package)
        self.assertTrue(any(c['id']=='a_premium_full' for c in delta['changes']))
        self.assertFalse(delta['acceptance_carried_forward'])

    def rebind_disposable_payload(self,name,value):
        dump(self.package/name,value)
        m=load(self.package/'manifest.json')
        m['files_sha256'][m['package_path']+'/'+name]=hashlib.sha256((self.package/name).read_bytes()).hexdigest()
        dump(self.package/'manifest.json',m)

    def test_removed_fields_and_sources_worsen_fixed_denominators(self):
        baseline,_=report(self.package,write=False)
        facts=load(self.package/'facts.json');facts[0].pop('value')
        self.rebind_disposable_payload('facts.json',facts)
        removed,_=report(self.package,write=False)
        self.assertEqual(baseline['field_coverage']['required_broad_obligations'],removed['field_coverage']['required_broad_obligations'])
        self.assertLess(removed['field_coverage']['structurally_represented_obligations'],baseline['field_coverage']['structurally_represented_obligations'])
        sources=[s for s in load(self.package/'sources.json') if s['id']!='CMS-ANNUAL']
        self.rebind_disposable_payload('sources.json',sources)
        removed,_=report(self.package,write=False)
        self.assertEqual(baseline['source_coverage']['required'],removed['source_coverage']['required'])
        self.assertLess(removed['source_coverage']['acquired'],baseline['source_coverage']['acquired'])
        self.assertLess(removed['field_coverage']['structurally_represented_obligations'],baseline['field_coverage']['structurally_represented_obligations'])
        with self.assertRaises(L01Held):self.service.evaluate(self.request)

    def test_bound_rate_drives_calculation_and_changes_invalidate_acceptance(self):
        facts=load(self.package/'facts.json')
        next(f for f in facts if f['id']=='b_coinsurance')['value']={'numerator':7,'denominator':100}
        self.rebind_disposable_payload('facts.json',facts)
        q={'operation':'ordinary_b','year':2026,'month':10,'state':'FL','approved_charge_cents':10000,'deductible_remaining_cents':0,'ordinary_rule_confirmed':True}
        self.assertEqual(700,self.service.research(q)['components'][0]['value_cents'])
        with self.assertRaises(L01Held):self.service.evaluate(q)

    def test_malformed_requirements_fail_closed(self):
        for value in [[],{},None,{'capabilities':None}]:
            dump(self.package/'requirements.json',value)
            with self.assertRaises(L01Held):self.service.evaluate(self.request)

    def test_http_acceptance_and_pending_behavior_without_private_storage(self):
        from ten_server import build
        server=attach(build(0,fixture=True,database=Path(self.temp.name)/'fixture.sqlite3'))
        server.l01_service=self.service # Closure is replaced by attaching to a fresh base handler below.
        # Unwrap the production default wrapper, then attach the disposable service.
        server.RequestHandlerClass=server.RequestHandlerClass.__bases__[0]
        del server.l01_service
        attach(server,self.service)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            def request(payload,origin=None):
                headers={'Content-Type':'application/json','Origin':origin or url}
                return urlopen(Request(url+'/api/l01/evaluate',data=json.dumps(payload).encode(),headers=headers),timeout=10)
            with request(self.request) as response:self.assertEqual(20290,json.load(response)['components'][0]['value_cents'])
            range_request={'operation':'irmaa','year':2026,'month':10,'state':'FL','covered_months':['2026-10'],'coverage_context':'full_b','filing_status':'individual','tax_year':2024,'return_basis':'normal_2024','changed_income':False,'amended_return':False,'magi_range_cents':{'lower_cents':10900000,'upper_cents':13700000,'lower_inclusive':False,'upper_inclusive':True}}
            with request(range_request) as response:self.assertEqual(28410,json.load(response)['components'][0]['value_cents'])
            self.data['package_review']['revoked']=True;dump(self.registry,self.data)
            with self.assertRaises(HTTPError) as error:request(self.request)
            self.assertEqual(503,error.exception.code);self.assertNotIn('20290',error.exception.read().decode());error.exception.close()
            with self.assertRaises(HTTPError) as error:request(self.request,'http://untrusted.example')
            self.assertEqual(403,error.exception.code);error.exception.close()
            with self.assertRaises(HTTPError) as error:request(dict(self.request,research_mode=True))
            self.assertEqual(422,error.exception.code);error.exception.close()
            with urlopen(url+'/api/l01/status') as response:self.assertFalse(json.load(response)['consumer_ready'])
        finally:server.shutdown();server.server_close();worker.join()


if __name__ == '__main__':unittest.main()
