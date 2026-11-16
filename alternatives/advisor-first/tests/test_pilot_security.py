"""Fictional pilot abuse probes, with loopback HTTP and no provider calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest

import server
from ai_budget import BudgetError, NANO
from guest_profiles import ProfileError
from natural_agent import TurnReservation
from pilot_access import PilotAccess, PilotTurnPacing, participant
from pilot_budget import PilotBudget
from test_advisor_budget import completed


class PilotSecurityTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'pilot'
        self.now = int(time.time())
        self.access = PilotAccess.initialize(self.root, ends_at=self.now + 7200)
        self.budget = PilotBudget.open(self.access, initialize=True)
        self.reviewed = datetime.fromisoformat(self.budget.rates['verified_at']).timestamp()
        self.budget.clock = lambda: self.reviewed

    def invite(self):
        return self.access.issue(expires_at=self.now + 1800)

    def joined(self):
        key, token = self.invite()
        self.access.redeem(token)
        return key

    def enable_chat(self):
        self.access.set_flag('guest_chat', True)
        self.access.set_flag('all_chat', True)

    def test_hosted_display_uses_the_shared_ui_and_admits_only_display_routes(self):
        from unittest.mock import Mock

        origin = 'https://daylight.example'
        app = server.build(0, fixture=True, pilot_state=self.root, pilot_origin=origin,
                           medigap_repository=Mock(), part_d_repository=Mock(),
                           pilot_display_binding={'snapshot_id': 'fictional'})
        thread = Thread(target=app.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(app.server_close)
        self.addCleanup(app.shutdown)

        def request(path, data=None, **headers):
            connection = http.client.HTTPConnection('127.0.0.1', app.server_port)
            try:
                connection.request('POST' if data is not None else 'GET', path,
                    json.dumps(data) if data is not None else None,
                    {'Host': 'daylight.example', 'Origin': origin, 'Content-Type': 'application/json', **headers})
                response = connection.getresponse()
                return response.status, response.read(), response.headers
            finally:
                connection.close()

        self.assertEqual(request('/')[0], 401)
        _, invitation = self.invite()
        status, _, headers = request('/pilot/redeem', {'invitation': invitation})
        self.assertEqual(status, 200)
        invite_cookie = headers['Set-Cookie'].split(';')[0]
        status, body, headers = request('/api/guest/session', Cookie=invite_cookie)
        self.assertEqual(status, 200)
        cookies = invite_cookie + '; ' + headers['Set-Cookie'].split(';')[0]
        csrf = json.loads(body)['csrf']
        self.assertIn(b'/plans-workspace.js', request('/', Cookie=cookies)[1])
        self.assertEqual(request('/api/plans/catalog', {}, Cookie=cookies,
                                 **{'X-Daylight-CSRF': csrf})[0], 200)
        self.assertEqual(request('/api/recommendation', {}, Cookie=cookies,
                                 **{'X-Daylight-CSRF': csrf})[0], 404)
        self.assertEqual(request('/api/plans/catalog', {}, Cookie=cookies)[0], 403)
        self.assertEqual(request('/api/plans/catalog', {}, Cookie=cookies, Host='127.0.0.1')[0], 403)

    def test_signed_expiring_single_use_and_revocation(self):
        key, invite = self.invite()
        with self.assertRaises(ProfileError):
            self.access.redeem(invite[:-1] + ('0' if invite[-1] != '0' else '1'))
        session, _ = self.access.redeem(invite)
        self.assertEqual(self.access.authenticate(session), (key, None))
        with self.assertRaises(ProfileError):
            self.access.redeem(invite)
        self.access.revoke(key)
        with self.assertRaises(ProfileError):
            self.access.authenticate(session)
        _, second = self.invite()
        self.access.clock = lambda: self.now + 1801
        with self.assertRaises(ProfileError):
            self.access.redeem(second)

    def test_concurrent_redeem_allows_only_one_browser(self):
        _, invite = self.invite()

        def redeem(_):
            try:
                self.access.redeem(invite)
                return True
            except ProfileError:
                return False

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(redeem, range(2))), 1)

    def test_message_pacing_releases_inflight_slot_and_enforces_rolling_window(self):
        now = 0
        pacing = PilotTurnPacing(clock=lambda: now)
        with pacing.admit('fictional-one'):
            now = 3
            with self.assertRaisesRegex(ProfileError, 'current reply'), pacing.admit('fictional-one'):
                self.fail('Another request was admitted while a reply was in flight')
            with pacing.admit('fictional-two'):
                pass
        for now in range(3, 30, 3):
            with pacing.admit('fictional-one'):
                pass
        now = 30
        with self.assertRaises(ProfileError), pacing.admit('fictional-one'):
            self.fail('The rolling window admitted an eleventh message')
        now = 60
        with pacing.admit('fictional-one'):
            pass
        now = 62
        with self.assertRaises(ProfileError), pacing.admit('fictional-one'):
            self.fail('The gap between messages was too short')

    def test_whole_pilot_cap_concurrent_across_users_providers_and_days(self):
        self.enable_chat()
        first, second = self.joined(), self.joined()
        context = participant.set(first)
        try:
            key = self.budget.reserve(1000, 900, 'gpt-5.4')
            self.budget.settle_model(key, completed(), 'gpt-5.4')
            provider_total = self.budget.participant_usage()[0][2]
            self.assertGreater(provider_total, 0)
            self.assertEqual(self.budget.reconcile(provider_total)['status'], 'matched')
            discrepancy = self.budget.reconcile(provider_total + 1)
            self.assertEqual((discrepancy['status'], discrepancy['difference_nano_usd']), ('difference', 1))
            with self.budget.db() as db:
                # Fictional historic cost, leaving enough room for one attempt.
                db.execute('UPDATE ai_charges SET charged=?,measured=? WHERE id=?',
                           (100 * NANO - 64_000_000, 100 * NANO - 64_000_000, key))
            self.reviewed += 86400
        finally:
            participant.reset(context)

        def reserve(owner):
            binding = participant.set(owner)
            try:
                return self.budget.reserve(1000, 2400, 'claude-opus-5-5')
            except BudgetError:
                return None
            finally:
                participant.reset(binding)

        with ThreadPoolExecutor(2) as pool:
            keys = list(pool.map(reserve, (first, second)))
        self.assertEqual(sum(key is not None for key in keys), 1)
        with self.budget.db() as db:
            total, _, held, count = self.budget._total(db)
        self.assertLessEqual(total, 100 * NANO)
        self.assertGreater(held, 0)
        self.assertEqual(self.budget.reconcile(total - held)['status'], 'unresolved_charges')
        self.assertEqual(count, 2)
        self.assertEqual(sum(row[2] + row[3] for row in self.budget.participant_usage()), total)
        self.assertIsNone(self.budget.session_costs()['all_spend_per_completed_nano_usd'])
        self.access.bind_guest(first, 'fictional-guest')
        self.access.mark_completed(first)
        report = self.budget.session_costs()
        self.assertEqual(report['completed'], 1)
        self.assertEqual(report['max_completed_nano_usd'], 100 * NANO - 64_000_000)
        self.assertEqual(report['held_nano_usd'], held)

    def test_reservation_rechecked_when_switch_flips(self):
        self.enable_chat()
        binding = participant.set(self.joined())
        try:
            with TurnReservation(self.budget, 'gpt-5.4', ('compose',)) as turn:
                stage = turn.stage('compose')
                stage.check_input(1000)
                self.access.set_flag('all_chat', False)
                with self.assertRaisesRegex(BudgetError, 'paused'):
                    stage.issued()
            self.assertEqual(self.budget.participant_usage(), [])
        finally:
            participant.reset(binding)

    def test_http_gate_headers_csrf_browser_binding_and_revocation(self):
        origin = 'https://pilot.example.test'
        service = server.build(0, fixture=True, pilot_state=self.root, pilot_origin=origin)
        thread = Thread(target=service.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(service.server_close)
        self.addCleanup(service.shutdown)
        def request(method, path, *, cookie='', data=None, csrf=None, site=None, host='pilot.example.test'):
            headers = {'Cookie': cookie, 'Host': host}
            if method == 'POST':
                headers.update({'Origin': site or origin, 'Content-Type': 'application/json'})
            if csrf:
                headers['X-Daylight-CSRF'] = csrf
            connection = http.client.HTTPConnection('127.0.0.1', service.server_port, timeout=4)
            try:
                connection.request(method, path, json.dumps(data) if data is not None else None, headers)
                reply = connection.getresponse()
                body = reply.read()
                return reply.status, dict(reply.getheaders()), body
            finally:
                connection.close()

        self.assertEqual(request('GET', '/')[0], 401)
        self.assertEqual(request('GET', '/api/guest/session')[0], 401)
        self.assertEqual(request('GET', '/pilot/join', host='wrong.example.test')[0], 403)
        with self.assertLogs('daylight.pilot.access', level='INFO') as captured:
            self.assertEqual(request('GET', '/pilot/join?private=fictional-secret')[0], 422)
        self.assertEqual(json.loads(captured.records[0].getMessage())['route'], 'other')
        self.assertNotIn('fictional-secret', captured.records[0].getMessage())
        code, headers, body = request('GET', '/pilot/join')
        self.assertEqual(code, 200)
        self.assertEqual(headers['Strict-Transport-Security'], 'max-age=31536000')
        self.assertIn(b'Continue', body)
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])

        def join():
            owner, invite = self.invite()
            body = {'invitation': invite}
            self.assertEqual(request('POST', '/pilot/redeem', data=body, site='https://invalid.test')[0], 403)
            with self.assertLogs('daylight.pilot.access', level='INFO') as captured:
                code, headers, _ = request('POST', '/pilot/redeem', data=body)
            self.assertEqual(code, 200)
            record = json.loads(captured.records[0].getMessage())
            self.assertEqual(set(record), {'event', 'route', 'status', 'time'})
            self.assertEqual((record['route'], record['status']), ('/pilot/redeem', 200))
            self.assertNotIn(invite, captured.records[0].getMessage())
            self.assertIn('Secure; HttpOnly; SameSite=Strict', headers['Set-Cookie'])
            session = headers['Set-Cookie'].split(';')[0]
            code, headers, body = request('GET', '/api/guest/session', cookie=session)
            self.assertEqual(code, 200)
            self.assertIn('Secure', headers['Set-Cookie'])
            return owner, session, headers['Set-Cookie'].split(';')[0], json.loads(body)['csrf']

        owner, pilot, guest, csrf = join()
        _, _, other_guest, _ = join()
        both = f'{pilot}; {guest}'
        self.assertEqual(request('GET', '/api/conversation/initial', cookie=both)[0], 200)
        self.assertEqual(request('GET', '/api/conversation/initial', cookie=f'{pilot}; {other_guest}')[0], 401)
        self.assertEqual(request('POST', '/api/conversation/save', cookie=both, data={})[0], 404)
        message = {'action': {'type': 'message', 'message': 'fictional question'}}
        self.assertEqual(request('POST', '/api/conversation/turn', cookie=both, data=message)[0], 403)
        self.assertEqual(request('POST', '/api/conversation/turn', cookie=both, data=message, csrf=csrf)[0], 503)
        choice = {'action': {'type': 'choice', 'id': 'T02', 'fields': {'choice': 'comfortable'}}, 'aiConsent': True}
        self.assertEqual(request('POST', '/api/conversation/turn', cookie=both, data=choice, csrf=csrf)[0], 503)
        self.enable_chat()
        self.assertNotEqual(request('POST', '/api/conversation/turn', cookie=both, data=message, csrf=csrf)[0], 429)
        self.assertEqual(request('POST', '/api/conversation/turn', cookie=both, data=choice, csrf=csrf)[0], 429)
        code, headers, body = request('GET', '/api/guest/session', cookie=pilot)
        self.assertEqual(code, 200)
        renewed = f"{pilot}; {headers['Set-Cookie'].split(';')[0]}"
        self.assertNotEqual(renewed, both)
        csrf = json.loads(body)['csrf']
        self.assertEqual(request('POST', '/api/conversation/turn', cookie=renewed, data=message, csrf=csrf)[0], 429)
        self.access.revoke(owner)
        self.assertEqual(request('GET', '/api/conversation/initial', cookie=renewed)[0], 401)
