"""D129: fictional HTTP inputs, no model calls, no source/guest writes."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_http as support
from medigap_pilot import BUILD, DATE, prices

PROFILE = dict(zipcode='34101', age=65, gender='Female', tobacco='Non-Tobacco', effective_date=DATE)


class FictionalRepository:
    def __init__(self):
        self.calls = []

    def query(self, **body):
        self.calls.append(copy.deepcopy(body))
        scenario = dict(zip=body['zipcode'], age=body['age'], gender=body['gender'],
                        tobacco=body['tobacco'], requested_effective_date=body['effective_date'])
        rows = []
        for i, rating in enumerate(('Standard', 'Household')):
            rows.append(dict(id=str(i), company_name_raw='Fictional Company', variant='G', naic='12345',
                rating_class_raw=rating, rating_type_raw='Issue Age', select_observed=None,
                monthly_cents=12345+i, annual_cents=None, monthly_with_discounts_cents=11728,
                annual_with_discounts_cents=140000, scenario=scenario, source_sha256='a'*64,
                raw={'HH Discount':'5%', 'Policy Fee':'$20 fixed', 'AM Best Rating':'Stable', 'AM Best Outlook':'A-'},
                policy_fee_timing='not_determined', discount_eligibility='not_determined',
                source_effective_date='2026-07-01', effective_end=None, policy_form=None, policy_edition=None,
                source_locator=f'Plan G Rates!A{11+i}:Q{11+i}'))
        return dict(build_id=BUILD, personal_quote=False, status='matched_source_observations',
                    source_sha256='a'*64, records=rows, holds=['PERSONAL_ELIGIBILITY_NOT_DETERMINED'],
                    field_issues=[{'record_id':'0'}])


class MedigapHttpTests(unittest.TestCase):
    request = support.HttpTests.request

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repository = FictionalRepository()
        cls.server = support.build(0, fixture=True, database=Path(cls.tmp.name)/'profiles.sqlite3',
                                   medigap_repository=cls.repository)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def setUp(self):
        self.cookie = None
        code, self.session = self.request('/api/guest/session')
        self.assertEqual(code, 200)
        self.repository.calls.clear()

    def test_exact_prices_preserve_classes_and_independent_unknown_amounts(self):
        before = self.request('/api/guest/session')[1]
        code, value = self.request('/api/plans/medigap', PROFILE)
        self.assertEqual(code, 200)
        self.assertEqual(value['status'], 'matched_source_prices')
        self.assertEqual(self.repository.calls, [PROFILE])
        self.assertEqual(len(value['plans']), 2)
        self.assertEqual(value['plans'][0]['monthly_cents'], 12345)
        self.assertIsNone(value['plans'][0]['annual_cents'])
        self.assertEqual(value['plans'][0]['annual_with_discounts_cents'], 140000)
        self.assertTrue(value['plans'][0]['rating_labels_need_review'])
        self.assertFalse(value['personal_quote'])
        self.assertEqual(value['eligibility'], 'not_determined')
        self.assertEqual(self.request('/api/guest/session')[1], before)

    def test_pilot_boundaries_and_date_never_query_another_profile(self):
        for change, status in [({'age':75},'unsupported_pilot_age'), ({'age':64},'unsupported_pilot_age'),
                               ({'zipcode':'34109'},'unsupported_pilot_zip'),
                               ({'effective_date':'2027-01-01'},'unsupported_price_date')]:
            code, value = self.request('/api/plans/medigap', {**PROFILE, **change})
            self.assertEqual(code, 200)
            self.assertEqual(value['status'], status)
            self.assertEqual(value['plans'], [])
        self.assertEqual(self.repository.calls, [])
        code, value = self.request('/api/plans/medigap', {**PROFILE, 'age':74, 'zipcode':'34108', 'gender':'Male', 'tobacco':'Tobacco User'})
        self.assertEqual(code, 200)
        self.assertEqual(value['profile']['age'], 74)

    def test_explicit_inputs_no_defaults_or_client_authority(self):
        for body in ({k:v for k,v in PROFILE.items() if k!='gender'}, {**PROFILE,'age':True},
                     {**PROFILE,'age':'65'}, {**PROFILE,'gender':'unknown'},
                     {**PROFILE,'commission':100}, {**PROFILE,'consumer_release':'accepted'},
                     {**PROFILE,'zipcode':'3410'}, {**PROFILE,'effective_date':None}):
            self.assertEqual(self.request('/api/plans/medigap',body)[0],422)
        self.assertEqual(self.repository.calls, [])

    def test_existing_origin_csrf_cookie_and_no_url_profile_boundary(self):
        self.assertEqual(self.request('/api/plans/medigap',PROFILE,csrf=False)[0],403)
        self.assertEqual(self.request('/api/plans/medigap',PROFILE,origin='https://untrusted.example')[0],403)
        self.assertEqual(self.request('/api/plans/medigap?age=65',PROFILE)[0],422)
        self.cookie = None
        self.assertIn(self.request('/api/plans/medigap',PROFILE)[0],(401,403))
        self.assertEqual(self.repository.calls, [])

    def test_source_stop_or_database_failure_fails_without_data_or_details(self):
        with patch.object(self.repository,'query',side_effect=RuntimeError('SOURCE_STOP secret fictional-input')):
            code, value = self.request('/api/plans/medigap',PROFILE)
        self.assertEqual(code,503)
        self.assertNotIn('secret',str(value))
        self.assertNotIn('plans',value)

    def test_wrong_build_or_wrong_profile_is_never_displayed(self):
        original = self.repository.query(**PROFILE)
        for tamper in ('build','age'):
            changed = copy.deepcopy(original)
            if tamper == 'build': changed['build_id'] = 'b'*64
            else: changed['records'][0]['scenario']['age'] = 66
            with patch.object(self.repository,'query',return_value=changed):
                self.assertEqual(self.request('/api/plans/medigap',PROFILE)[0],503)

    def test_no_repository_and_ordinary_ma_catalog(self):
        with self.assertRaises(RuntimeError): prices(None,PROFILE)
        code, value = self.request('/api/plans/catalog',{})
        self.assertEqual(code,200)
        self.assertEqual(len(value['plans']),72)
        self.assertNotIn('display_authorization',value)


if __name__ == '__main__': unittest.main()
