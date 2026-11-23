"""D200: owner demo review, November 19, 2026. Fictional, offline, no provider calls.

1. "Slow down… why do you need that?" keeps the visit open with choices.
2. A real stop's summary names the Social Security step, not "reopen this conversation".
3. A shared-invitation visitor may start a fresh visit five times.
"""
import json
from pathlib import Path
import tempfile
import time
import unittest

import server  # noqa: F401  (sets the engine import path)
import conversation_planner as planner
import journey_completion
from pilot_access import PilotAccess, RESTART_LIMIT, ProfileError
import test_semantic_guidance as sg
import test_hosted_history as base
from test_hosted_history import MemoryHistory, request

SLOW = 'Slow down, we are going too fast, why do you need that information?'


class PaceIsNotAPause(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context', 'interpreted', 'ask'):
        locals()[name] = getattr(sg.SemanticGuidance, name)
    setUp = sg.SemanticGuidance.setUp
    update = staticmethod(sg.SemanticGuidance.update)
    extraction = staticmethod(sg.SemanticGuidance.extraction)

    def start(self):
        self.choice('RC01', choice='self'); self.choice('T05', choice='employer')

    def test_slow_down_keeps_the_visit_open_with_choices(self):
        self.start()
        out = self.ask(SLOW, mode='pause')          # the interpreter's reading in the owner's demo
        self.assertFalse(out['assessment'].get('intakePaused'))
        self.assertNotIn('guided_summary', [c['kind'] for c in out.get('cards', [])])
        self.assertNotIn('finish_summary', [c['kind'] for c in out.get('cards', [])])
        pace = [c for c in out.get('cards', []) if c.get('pace')]
        self.assertEqual(len(pace), 1)
        labels = [a['label'] for a in pace[0]['actions']]
        self.assertEqual(labels, [label for label, _ in planner.PACE_CHOICES])
        self.assertIn('Stop for today', labels)
        self.assertEqual(planner.state(self.flow, self.owner)['guidance']['mode'], 'detour')
        sent = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertIn('pace_request', json.dumps(sent))

    def test_a_why_question_offers_choices_even_when_read_as_a_detour(self):
        self.start()
        out = self.ask('Why are you asking about that?', mode='detour')
        self.assertTrue(any(c.get('pace') for c in out.get('cards', [])))

    def test_a_real_stop_still_pauses(self):
        self.start()
        for words in ('Let me take a breath and leave this here.', "Slow down. Let's stop for today."):
            out = self.ask(words, mode='pause')
            self.assertTrue(out['assessment']['intakePaused'], words)
            self.assertFalse(any(c.get('pace') for c in out.get('cards', [])), words)

    def test_skip_tap_sets_the_question_aside_for_this_visit(self):
        self.start()
        current = {'id': 'T08', 'entity': 'profile'}
        s = planner.state(self.flow, self.owner)
        planner.observe(self.flow, self.owner, self.g, self.r, planner.PACE_CHOICES[0][1],
                        {'discussion': planner.empty_proposal()}, current)
        self.assertIn('T08', s['deferred'])
        planner.observe(self.flow, self.owner, self.g, self.r, planner.PACE_CHOICES[0][1],
                        {'discussion': planner.empty_proposal()}, {'id': 'RC01'})
        self.assertNotIn('RC01', s['deferred'])        # who the coverage is for is never set aside

    def test_stop_summary_names_the_social_security_step(self):
        self.flow.guided_close = True
        self.start()
        out = self.ask('Let me take a breath and leave this here.', mode='pause')
        summary = next(c for c in out['cards'] if c['kind'] in ('guided_summary', 'finish_summary'))
        text = json.dumps(summary)
        self.assertIn('Social Security', text)
        self.assertNotIn('Reopen this conversation', text)


class FreshStarts(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.now = int(time.time())
        self.access = PilotAccess.initialize(Path(folder.name) / 'state', ends_at=self.now + 86400)
        self.access.migrate_hosted()

    def visit(self, max_visits=20):
        _, token = self.access.issue_shared(expires_at=self.now + 3600, max_visits=max_visits)
        session, _ = self.access.redeem(token)
        return self.access.authenticate(session)[0]

    def test_five_fresh_starts_then_none(self):
        key = self.visit()
        self.assertEqual(self.access.restarts_left(key), RESTART_LIMIT)
        for expected in range(RESTART_LIMIT - 1, -1, -1):
            old = key
            session, age, left = self.access.restart(key)
            self.assertGreater(age, 0)
            key = self.access.authenticate(session)[0]
            self.assertNotEqual(key, old)
            self.assertEqual(left, expected)
            with self.assertRaises(ProfileError):
                self.access.visit_policy(old)            # the old visit is closed
        with self.assertRaises(ProfileError) as raised:
            self.access.restart(key)
        self.assertEqual(raised.exception.code, 409)

    def test_fresh_starts_do_not_use_the_links_visits_and_keep_consent(self):
        _, token = self.access.issue_shared(expires_at=self.now + 3600, max_visits=2)
        session, _ = self.access.redeem(token, consent_version='hosted-demo-history-2026-11-18-v1')
        key = self.access.authenticate(session)[0]
        for _ in range(RESTART_LIMIT):
            session, _, left = self.access.restart(key)
            key = self.access.authenticate(session)[0]
        self.assertEqual(left, 0)
        link, consent, _ = self.access.visit_policy(key)
        self.assertIsNotNone(link)
        self.assertEqual(consent, 'hosted-demo-history-2026-11-18-v1')
        second, _ = self.access.redeem(token)        # the link's second visit is still available
        self.assertTrue(self.access.authenticate(second))
        with self.assertRaises(ProfileError):
            self.access.redeem(token)                 # and then its two visits are used

    def test_a_revoked_link_offers_no_fresh_start(self):
        link_id, token = self.access.issue_shared(expires_at=self.now + 3600)
        session, _ = self.access.redeem(token)
        key = self.access.authenticate(session)[0]
        self.access.revoke_shared(link_id)
        with self.assertRaises(ProfileError):
            self.access.restart(key)

    def test_a_personal_invitation_has_no_fresh_starts(self):
        _, token = self.access.issue(expires_at=self.now + 3600)
        session, _ = self.access.redeem(token)
        self.assertEqual(self.access.restarts_left(self.access.authenticate(session)[0]), 0)


class FreshStartRoute(unittest.TestCase):
    setUp, app, join = base.HostedTests.setUp, base.HostedTests.app, base.HostedTests.join

    def test_shared_visitor_starts_fresh_and_the_old_visit_closes(self):
        app = self.app(MemoryHistory())
        _, token = self.access.issue_shared(expires_at=self.end, max_visits=20)
        cookies, csrf = self.join(app, token=token)
        code, body, _ = request(app, '/api/pilot/restart', cookies=cookies)
        self.assertEqual((code, json.loads(body)), (200, {'left': RESTART_LIMIT, 'limit': RESTART_LIMIT}))
        self.assertEqual(request(app, '/api/pilot/restart', {}, cookies, csrf)[0], 422)   # confirmation required
        code, body, headers = request(app, '/api/pilot/restart', {'confirm': True}, cookies, csrf)
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)['left'], RESTART_LIMIT - 1)
        fresh = headers['Set-Cookie'].split(';')[0]
        guest = cookies.split('; ')[1]
        self.assertEqual(request(app, '/api/status', cookies=cookies)[0], 401)          # old visit closed
        code, _, headers = request(app, '/api/guest/session', cookies=fresh + '; ' + guest)
        self.assertEqual(code, 200)

    def test_personal_invitation_cannot_start_fresh(self):
        app = self.app(MemoryHistory())
        cookies, csrf = self.join(app)
        self.assertEqual(json.loads(request(app, '/api/pilot/restart', cookies=cookies)[1])['left'], 0)
        self.assertEqual(request(app, '/api/pilot/restart', {'confirm': True}, cookies, csrf)[0], 409)


if __name__ == '__main__':
    unittest.main()
