"""D146 through actual local HTTP, the signed visit, and the bound foundation."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest import TestCase
from unittest.mock import patch

import test_http as support
from demo_server import DEFAULT_BINDING, REPO, build_demo, start_prescription_rehearsal
from part_d_rehearsal import REHEARSAL_COOKIE
from part_d_visit_http import PATH
from daylight_data.serving.part_d_local import local_candidate
from daylight_data.serving.pilot_foundation import source_controls

PLAN = '2026:H1036:217:000'
PDP = '2026:S5884:105:000'
BEFORE = datetime(2026, 11, 12, tzinfo=timezone.utc)
EXPIRES = datetime(2026, 11, 24, tzinfo=timezone.utc)
OUTLET = '866193811ee83d46f8a2:1841534534'
SPEC = importlib.util.spec_from_file_location(
    'daylight_ui_8894', REPO / 'alternatives/advisor-first/ui-8894/serve.py')
UI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UI)


class PrescriptionProfileTests(TestCase):
    turn = support.HttpTests.turn
    setUp = support.HttpTests.setUp
    cookie_name = UI.PREVIEW_COOKIE

    @classmethod
    def setUpClass(cls):
        stack = cls.enterClassContext(ExitStack())
        cls.now = BEFORE
        cls.service = local_candidate(REPO, clock=lambda: cls.now)
        fixture = UI.start_d146_backend(stack, candidate=cls.service)
        cls.server = stack.enter_context(ThreadingHTTPServer(
            ('127.0.0.1', 0), UI.handler('http://127.0.0.1:8893', fixture)))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        stack.callback(cls.server.shutdown)

    def request(self, path, *args, **kwargs):
        return support.HttpTests.request(self, '/d146' + path, *args, **kwargs)

    def choice(self, identifier, *, entity=None, **fields):
        self.turn({'type': 'choice', 'id': identifier, 'fields': fields,
                   **({'entity': entity} if entity else {})})

    def start(self, *, shared_fill=True):
        self.turn({'type': 'task', 'task': 'drug_pricing', 'preparing': True})
        self.choice('RC01', choice='self')
        self.choice('T03', zip='34102')
        self.choice('RC03', year='2026')
        self.choice('T07', text='Metformin')
        self.choice('RC22', entity='medicine-1', name='Metformin', strength='500 mg', form='tablet')
        if shared_fill:
            self.choice('RC23', entity='medicine-1', quantity='30 tablets', daysSupply='30',
                        pharmacy='Publix', channel='retail')
            self.choice('RC18', choice='none')

    def check(self, action='read', revision=None, plan=PLAN, **details):
        payload = {'action': action, 'continuation': self.state['continuation'], 'offering_id': plan,
                   **({'revision': revision} if revision is not None else {}), **details}
        code, value = self.request(PATH, payload)
        self.assertEqual(code, 200, value)
        self.assertFalse(value.get('participant_release', False))
        return value

    def answer(self, current, field, value, plan=PLAN):
        self.assertEqual(current['question']['field'], field, current)
        return self.check('answer', current['revision'], plan, value=value)

    def ready(self, plan=PLAN, *, shared_fill=True):
        current = self.check(plan=plan)
        self.assertIn('861007', {row['value'] for row in current['question']['choices']})
        current = self.answer(current, 'rxcui', '861007', plan)
        if not shared_fill:
            current = self.answer(current, 'quantity', 30, plan)
            current = self.answer(current, 'unit', 'tablet', plan)
            current = self.answer(current, 'days_supply', 30, plan)
        current = self.answer(current, 'fills', [{'date': '2026-12-01', 'order': 1}], plan)
        current = self.answer(current, 'outlet_zip', '34102', plan)
        current = self.answer(current, 'pharmacy', OUTLET, plan)
        if not shared_fill:
            current = self.answer(current, 'channel', 'retail', plan)
        current = self.answer(current, 'period', '2026-12-01', plan)
        if not shared_fill:
            current = self.answer(current, 'assistance', 'none', plan)
        current = self.answer(current, 'prior_spending', 'confirmed_zero', plan)
        self.assertEqual(current['state'], 'ready', current)
        return current

    def test_existing_reports_are_reused_and_visit_has_no_durable_price(self):
        self.start()
        ready = self.ready()
        result = self.check('estimate', ready['revision'])
        self.assertEqual(result['state'], 'offline_average_candidate')
        self.assertEqual(result['period_kind'], 'remaining_year')
        self.assertEqual(result['drug_spending_cents'], 0)
        self.assertEqual(self.check('validate', result['revision'], receipt=result['receipt'])['state'], 'current')
        profile, stored = self.request('/api/guest/profile')
        self.assertEqual(profile, 200)
        self.assertNotIn('confirmed_zero', str(stored))
        self.assertNotIn(result['receipt'], str(stored))
        for key in ('ledger', 'sources', 'findings', 'report'):
            self.assertNotIn(key, result)

    def test_supplement_correction_rejects_previous_revision_and_receipt(self):
        self.start(shared_fill=False)
        ready = self.ready(PDP, shared_fill=False)
        prior = self.check('estimate', ready['revision'], PDP)
        self.assertEqual(prior['state'], 'offline_average_candidate', prior)
        edited = self.check('edit', prior['revision'], PDP, item='medicine-1', field='quantity')
        changed = self.answer(edited, 'quantity', 60, PDP)
        self.assertEqual(changed['state'], 'ready')
        self.assertEqual(self.check('validate', changed['revision'], PDP, receipt=prior['receipt'])['state'], 'held')
        stale = {'action': 'estimate', 'continuation': self.state['continuation'],
                 'offering_id': PDP, 'revision': prior['revision']}
        self.assertEqual(self.request(PATH, stale)[0], 409)
        after = self.check('estimate', changed['revision'], PDP)
        self.assertGreater(after['drug_spending_cents'], prior['drug_spending_cents'])

    def test_profile_correction_wrong_year_subject_and_foreign_guest(self):
        self.start()
        old = self.check('estimate', self.ready()['revision'])
        head = self.state['continuation']
        old_request = {'action': 'validate', 'continuation': head, 'offering_id': PLAN,
                       'revision': old['revision'], 'receipt': old['receipt']}
        self.choice('RC22', entity='medicine-1', form='extended release oral tablet')
        self.assertEqual(self.request(PATH, old_request)[0], 409)
        current = self.check()
        self.assertEqual(current['question']['field'], 'rxcui')
        ids = {row['value'] for row in current['question']['choices']}
        self.assertIn('860975', ids)
        self.assertNotIn('861007', ids)
        self.choice('RC03', year='2027')
        self.assertEqual(self.check()['hold'], 'scope_unsupported')
        _, self.state = self.request('/api/conversation/initial')
        self.turn({'type': 'start'})
        self.choice('RC01', choice='someone')
        self.assertEqual(self.request(PATH, old_request)[0], 409)
        self.assertNotEqual(self.check()['revision'], old['revision'])
        self.cookie = None
        _, self.session = self.request('/api/guest/session')
        self.assertEqual(self.request(PATH, old_request)[0], 409)

    def test_outlet_and_assistance_corrections_invalidate_the_estimate(self):
        self.start()
        old = self.check('estimate', self.ready()['revision'])
        self.choice('RC23', entity='medicine-1', pharmacy='Another location in Naples, FL 34102')
        current = self.check()
        if current['question']['field'] == 'rxcui':
            current = self.answer(current, 'rxcui', '861007')
        if current['question']['field'] == 'fills':
            current = self.answer(current, 'fills', [{'date': '2026-12-01', 'order': 1}])
        self.assertEqual(current['question']['field'], 'pharmacy')
        self.assertIn('Another location', current['question']['reported'])
        self.assertEqual(self.check('validate', current['revision'], receipt=old['receipt'])['state'], 'held')
        current = self.answer(current, 'pharmacy', OUTLET)
        self.assertEqual(current['state'], 'ready')
        self.choice('RC18', choice='extra_help')
        updated = self.check()
        self.assertEqual(updated['state'], 'ready')
        self.assertEqual(self.check('estimate', updated['revision'])['hold'],
                         'assistance_unresolved_or_unsupported')

    def test_expiry_and_stop_revoke_an_already_renderable_result(self):
        self.start()
        old = self.check('estimate', self.ready()['revision'])
        self.assertEqual(old['state'], 'offline_average_candidate')
        self.__class__.now = EXPIRES
        try:
            for action, extra in [('validate', {'receipt': old['receipt']}), ('estimate', {})]:
                held = self.check(action, old['revision'], **extra)
                self.assertEqual(held['hold'], 'PILOT_EVIDENCE_STALE')
                self.assertNotIn('drug_spending_cents', held)
        finally:
            self.__class__.now = BEFORE
        stopped = deepcopy(source_controls(self.service.foundation.source_dsn))
        stopped['source_access_states'].append({'source_id': 'fictional-source-stop', 'state': 'stopped'})
        with patch('daylight_data.serving.pilot_foundation.source_controls', return_value=stopped):
            for action, extra in [('validate', {'receipt': old['receipt']}), ('estimate', {})]:
                held = self.check(action, old['revision'], **extra)
                self.assertEqual(held['hold'], 'PILOT_SOURCE_WITHDRAWAL_OR_CONTROL_CHANGE')
                self.assertNotIn('drug_spending_cents', held)
        self.assertEqual(self.check('validate', old['revision'], receipt=old['receipt'])['hold'],
                         'result_changed')

    def test_correction_during_estimate_refuses_inflight_old_output(self):
        self.start()
        ready = self.ready()
        entering, resume = Event(), Event()
        estimate = self.service.estimate

        def paused(*args, **kwargs):
            result = estimate(*args, **kwargs)
            entering.set()
            if not resume.wait(8):
                raise AssertionError('test did not release request')
            return result

        body = {'action': 'estimate', 'continuation': self.state['continuation'],
                'offering_id': PLAN, 'revision': ready['revision']}
        with patch.object(self.service, 'estimate', side_effect=paused), ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.request, PATH, body)
            try:
                self.assertTrue(entering.wait(8))
                self.choice('RC03', year='2027')
            finally:
                resume.set()
            status, value = future.result()
        self.assertEqual(status, 409)
        self.assertNotIn('drug_spending_cents', value)

    def test_csrf_origin_and_client_report_are_rejected(self):
        self.start()
        payload = {'action': 'read', 'continuation': self.state['continuation'], 'offering_id': PLAN}
        self.assertEqual(self.request(PATH, payload, csrf=False)[0], 403)
        self.assertEqual(self.request(PATH, payload, origin='https://example.test')[0], 403)
        self.assertEqual(self.request(PATH, {**payload, 'report': {'medicines': []}})[0], 422)
        self.assertEqual(self.request(PATH, {**payload, 'purpose': 'participant'})[0], 422)
        self.assertTrue(self.cookie.startswith(self.cookie_name + '='))
        self.assertEqual(self.request('/api/prescription-preview/profile?purpose=participant', payload)[0], 404)


class UnifiedPrescriptionTests(PrescriptionProfileTests):
    cookie_name = REHEARSAL_COOKIE

    @classmethod
    def setUpClass(cls):
        stack = cls.enterClassContext(ExitStack())
        cls.now = BEFORE
        cls.service = local_candidate(REPO, clock=lambda: cls.now)
        port = start_prescription_rehearsal(stack, binding_path=DEFAULT_BINDING, candidate=cls.service)
        temp = stack.enter_context(TemporaryDirectory(prefix='daylight-d146-unified-tests-'))
        cls.server = stack.enter_context(build_demo(0, fixture=True,
            database=Path(temp) / 'ordinary.sqlite3', rehearsal_port=port))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        stack.callback(cls.server.shutdown)

    def test_only_the_fictional_chat_gets_the_prescription_task(self):
        def get(path, **headers):
            conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
            try:
                conn.request('GET', path, headers=headers)
                response = conn.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                conn.close()

        self.assertNotIn(b'prescription-profile-preview.js', get('/')[2])
        self.assertIn(b'src="prescription-profile-preview.js"', get('/d146/')[2])
        self.assertEqual(get('/d146/prescription-profile-preview.js')[0], 200)
        self.assertEqual(get('/d146')[1]['Location'], '/d146/')
        self.assertIn('Path=/d146/;', get('/d146/api/guest/session')[1]['Set-Cookie'])
        ordinary = get('/api/guest/session')[1]['Set-Cookie'].split(';')[0]
        self.assertEqual(get('/api/guest/profile', Cookie=self.cookie)[0], 401)
        self.assertEqual(get('/d146/api/guest/profile', Cookie=ordinary)[0], 401)
        self.assertEqual(get('/d146/api/ai/usage')[0], 404)
        self.assertEqual(get('/d146/api/status')[0], 200)
        self.assertIn(b'"fixture": true', get('/d146/api/status')[2])
        code, denied = support.HttpTests.request(self, PATH, {'action': 'read'})
        self.assertGreaterEqual(code, 400)
        self.assertNotIn('drug_spending_cents', denied)
