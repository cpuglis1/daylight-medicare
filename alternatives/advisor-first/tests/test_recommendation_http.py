"""D147: evaluation-only recommendation endpoint and conversation inputs. No network or model."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_natural_flow as harness
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from server import build
import recommendation_engine as engine
from test_recommendation_engine import GAP, PDP, inputs


class RecommendationHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='daylight-recommendation-tests-')
        cls.block = patch('urllib.request.urlopen', side_effect=AssertionError('External transport forbidden'))
        cls.block.start()
        cls.server = build(0, fixture=True, database=Path(cls.tmp.name) / 'fictional.sqlite3', local_demo=True,
                           research_catalog=CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.block.stop(); cls.tmp.cleanup()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        supplied = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        if body is not None:
            supplied['Content-Type'] = 'application/json'
        supplied.update(headers or {})
        conn.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, supplied)
        response = conn.getresponse(); raw = response.read(); conn.close()
        return response.status, json.loads(raw or b'{}'), dict(response.getheaders())

    def auth(self):
        code, session, headers = self.request('/api/guest/session')
        self.assertEqual(code, 200)
        return {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-Daylight-CSRF': session['csrf']}

    def test_status_flag_csrf_and_input_boundary(self):
        code, status, _ = self.request('/api/status')
        self.assertEqual(status['eval_recommendations']['method'], engine.METHOD)
        code, _, _ = self.request('/api/recommendation', {'inputs': inputs()})
        self.assertIn(code, {401, 403})
        auth = self.auth()
        code, value, _ = self.request('/api/recommendation', {'inputs': dict(inputs(), extra=1)}, auth)
        self.assertEqual(code, 422)
        code, value, _ = self.request('/api/recommendation?zip=34102', {'inputs': inputs()}, auth)
        self.assertEqual(code, 422)

    def test_scores_the_retained_ma_catalog_and_the_tab_data(self):
        auth = self.auth()
        with patch('recommendation_http.medigap_pilot.prices', return_value=copy.deepcopy(GAP)) as gap, \
                patch('recommendation_http.part_d_pilot.published_plans', return_value=copy.deepcopy(PDP)) as pdp:
            code, value, _ = self.request('/api/recommendation', {'inputs': inputs(
                doctors='list', priorities=['doctors', 'bills'], cost_preference='predictable')}, auth)
        self.assertEqual(code, 200, value)
        self.assertEqual(gap.call_args.args[1], {'zipcode': '34102', 'age': 66, 'gender': 'Female',
                                                 'tobacco': 'Non-Tobacco', 'effective_date': '2026-11-10'})
        self.assertEqual(pdp.call_args.args[1], {'zipcode': '34102', 'county_fips': '12021', 'year': 2026})
        ma = value['advantage']
        self.assertEqual(len(ma['plans']), 72)
        self.assertEqual(sum(len(g['ids']) for g in ma['groups']), 72)
        snp = [i for i, p in ma['plans'].items() if any(c['id'] == 'eligibility' for c in p['checks'])]
        self.assertTrue(snp and all(ma['plans'][i]['group'] == 'excluded' for i in snp))
        self.assertTrue(ma['recommended_ids'])          # medicines 'no' in these inputs
        self.assertEqual(value['path']['recommended_ids'], ['original'])
        self.assertTrue(value['evaluation_only'])

    def test_ordinary_build_has_no_recommendation(self):
        plain = build(0, fixture=True, database=Path(self.tmp.name) / 'plain.sqlite3')
        try:
            self.assertFalse(getattr(plain.adaptive, 'eval_recommendations', False))
        finally:
            plain.server_close()


class RecommendationInputsTests(unittest.TestCase):
    setUp = harness.NaturalFlowTests.setUp
    for name in ('payload', 'take', 'turn', 'choice'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)

    def test_inputs_come_from_reported_details_only(self):
        self.assertNotIn('recommendationInputs', self.choice('RC01', choice='self'))
        self.flow.eval_recommendations = True
        self.choice('T03', zip='34102'); self.choice('T08', choice='elsewhere_us')
        self.choice('T09', choice='predictable'); self.choice('T07', choice='no')
        self.choice('MG_AGE', choice='64'); self.choice('MG_SEX', choice='Female')
        out = self.choice('MG_TOBACCO', choice='Non-Tobacco')
        value = out['recommendationInputs']
        engine.validate_inputs(value)
        self.assertEqual((value['scope']['zipcode'], value['travel'], value['cost_preference'], value['medicines']),
                         ('34102', ['elsewhere_us'], 'predictable', 'no'))
        self.assertEqual((value['medigap']['age'], value['medigap']['reported_age'], value['medigap']['status']),
                         (65, 64, 'ready'))
        self.assertIsNone(value['doctors'])
        self.assertIsNone(value['medicaid'])


if __name__ == '__main__':
    unittest.main()
