"""D199: hosted invited-demo wiring matches the :8895 features the owner approved.

Fictional and provider-free. Uses the same in-process harness as test_hosted_history.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import server  # noqa: F401  (sets the engine import path)
from hosted_history import VisitLocks, BLOCKS_SQL
from pilot_access import participant
import pilot_budget
import test_hosted_history as base
from test_hosted_history import MemoryHistory, request


class BlockHistory(MemoryHistory):
    """Adds the D199 per-block archive to the fault-injectable storage double."""
    def __init__(self):
        super().__init__(); self.blocks = {}; self.fail_blocks = False
    def check_blocks(self):
        return True
    def publish_blocks(self, visit, request, blocks):
        if self.fail_blocks:
            return False
        if self.rows.get((visit, request), {}).get('status') != 'accepted':
            return False
        self.blocks[visit, request] = list(blocks)
        return True


class HostedD199Tests(unittest.TestCase):
    setUp, visit, app, join, initial = (base.HostedTests.setUp, base.HostedTests.visit,
        base.HostedTests.app, base.HostedTests.join, base.HostedTests.initial)

    def test_status_sends_feature_switches_without_runtime_details(self):
        app = self.app(MemoryHistory()); cookies, _ = self.join(app)
        code, body, _ = request(app, '/api/status', cookies=cookies)
        self.assertEqual(code, 200)
        flags = json.loads(body)['local_demo']
        for key in ('plans_fixes', 'conversation_fixes', 'composed_opening', 'guided_close',
                    'enrollment_journey', 'turn_progress', 'discussion_planner'):
            self.assertTrue(flags[key], key)
        self.assertFalse(flags['block_release'])
        self.assertEqual(flags['surface'], 'hosted-demo')
        for private in ('plan_database', 'snapshot_id', 'runtime_build', 'python_sha256'):
            self.assertNotIn(private, body.decode())

    def test_gate_admits_plans_workspace_priorities_and_signup_guides(self):
        app = self.app(MemoryHistory()); cookies, csrf = self.join(app)
        code, body, _ = request(app, '/api/enrollment/content', cookies=cookies)
        self.assertEqual(code, 200, body)
        self.assertIn('version', json.loads(body))
        for path in ('/api/plans/workspace', '/api/plans/priorities'):
            code, body, _ = request(app, path, {}, cookies, csrf)
            self.assertNotEqual(code, 404, (path, body))
            self.assertNotIn(b'unavailable in the pilot', body)
        # Still gated: no invitation cookie, no access.
        self.assertEqual(request(app, '/api/enrollment/content')[0], 401)
        self.assertEqual(request(app, '/api/research/query', {}, cookies, csrf)[0], 404)

    def test_medicare_advantage_values_use_the_local_review_projection(self):
        app = self.app(MemoryHistory()); cookies, csrf = self.join(app)
        code, body, _ = request(app, '/api/plans/catalog', {}, cookies, csrf)
        self.assertEqual(code, 200, body)
        view = json.loads(body)
        self.assertEqual(view['publication']['state'], 'local_review')
        self.assertFalse(view['publication']['consumer_approved'])
        self.assertGreater(view['coverage']['usable_reference_fields'], 0)

    def test_facts_and_deadline_hold_apply_on_the_hosted_surface(self):
        app = self.app(MemoryHistory())
        knowledge = app.adaptive.pilot_knowledge
        self.assertEqual(knowledge.surface, 'hosted-demo')
        status = knowledge.status()
        self.assertTrue(status['enabled'])
        self.assertEqual(status['available_count'], 71)
        self.assertEqual(knowledge.response_limits()['held_claim_ids'], ['ma_initial_deadline_after_late_part_b'])

    def test_two_visits_chat_at_once_but_one_visit_never_overlaps(self):
        locks = VisitLocks(limit=2)
        self.assertTrue(locks.acquire('a' * 32)); self.assertTrue(locks.acquire('b' * 32))
        self.assertFalse(locks.acquire('a' * 32))
        self.assertFalse(locks.acquire('c' * 32))  # bounded
        locks.release('a' * 32); self.assertTrue(locks.acquire('c' * 32))
        self.assertFalse(locks.acquire(None))

    def test_second_visitor_is_not_told_daylight_is_busy(self):
        history = MemoryHistory(); app = self.app(history)
        first, csrf1 = self.join(app); second, csrf2 = self.join(app)
        started, release = threading.Event(), threading.Event()
        original = app.adaptive._selected_turn
        def slow(owner, payload):
            if payload['requestId'] == 'fictional-turn-001' and not started.is_set():
                started.set(); release.wait(10)
            return original(owner, payload)
        with patch.object(app.adaptive, '_selected_turn', side_effect=slow):
            with ThreadPoolExecutor(1) as pool:
                pending = pool.submit(request, app, '/api/conversation/turn', self.initial(app, first), first, csrf1)
                self.assertTrue(started.wait(10))
                payload = {**self.initial(app, second), 'requestId': 'fictional-turn-002'}
                code, body, _ = request(app, '/api/conversation/turn', payload, second, csrf2)
                release.set()
                self.assertEqual(code, 200, body)
                self.assertEqual(pending.result()[0], 200)

    def test_blocks_show_only_after_they_are_archived(self):
        with patch.dict(os.environ, {'DAYLIGHT_BLOCK_RELEASE': 'on'}):
            history = BlockHistory(); app = self.app(history)
            cookies, _ = self.join(app)
            code, body, _ = request(app, '/api/status', cookies=cookies)
            self.assertTrue(json.loads(body)['local_demo']['block_release'])
        progress = app.adaptive.turn_progress
        visit, key = 'f' * 32, ('fictional-owner', 'request-one')
        history.rows[visit, key[1]] = {'status': 'accepted', 'payload': {}}
        token = participant.set(visit)
        try:
            progress.begin(key)
            history.fail_blocks = True
            progress.publish(key, ['Not saved'])
            self.assertNotIn('blocks', progress.read(*key))
            history.fail_blocks = False
            progress.publish(key, ['Saved first block'])
            self.assertEqual(progress.read(*key)['blocks'], ['Saved first block'])
            self.assertEqual(history.blocks[visit, key[1]], ['Saved first block'])
        finally:
            participant.reset(token)

    def test_block_archive_migration_keeps_isolation_and_deletion(self):
        self.assertIn('FORCE ROW LEVEL SECURITY', BLOCKS_SQL)
        self.assertIn('ON DELETE CASCADE', BLOCKS_SQL)
        self.assertNotIn('DELETE ON', BLOCKS_SQL.upper().replace('ON DELETE', ''))

    def test_pricing_review_can_come_from_a_root_managed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pricing-review.json'
            path.write_text('{"verified_at":"2026-11-19T14:28:06Z","valid_until":"2026-11-26T14:27:06Z"}')
            with patch.dict(os.environ, {pilot_budget.PRICING_REVIEW_ENV: str(path)}):
                self.assertEqual(pilot_budget.pricing_review_path(), path)
            with patch.dict(os.environ, {pilot_budget.PRICING_REVIEW_ENV: 'relative.json'}):
                with self.assertRaises(ValueError):
                    pilot_budget.pricing_review_path()
            link = Path(directory) / 'link.json'; link.symlink_to(path)
            with patch.dict(os.environ, {pilot_budget.PRICING_REVIEW_ENV: str(link)}):
                with self.assertRaises(ValueError):
                    pilot_budget.pricing_review_path()


if __name__ == '__main__':
    unittest.main()


class HostedChecksTests(unittest.TestCase):
    setUp, visit, app, join, initial = (base.HostedTests.setUp, base.HostedTests.visit,
        base.HostedTests.app, base.HostedTests.join, base.HostedTests.initial)

    def checked_app(self):
        from unittest.mock import Mock
        import hosted_server
        def bind(service): service.server_name='localhost';service.server_port=19013
        import socketserver
        with patch('http.server.HTTPServer.server_bind',bind),patch.object(socketserver.TCPServer,'server_activate'):
            app=hosted_server.build_hosted(0,state=self.access.root,origin='https://daylight.example',
                ledger=self.budget.path,history=MemoryHistory(),binding={'snapshot_id':'a'*64},
                medigap=Mock(),pdp=Mock(),release='b'*64,synthetic=True,checks=(Mock(),Mock()))
        self.addCleanup(app.server_close)
        return app

    def test_checks_are_installed_announced_and_admitted(self):
        app = self.checked_app(); cookies, csrf = self.join(app)
        self.assertIsNotNone(app.adaptive.conversation_checks)
        flags = json.loads(request(app, '/api/status', cookies=cookies)[1])['local_demo']
        self.assertTrue(flags['conversation_checks']); self.assertTrue(flags['doctor_chat'])
        code, body, _ = request(app, '/', cookies=cookies)
        self.assertIn(b'/conversation-checks.js', body)
        code, body, _ = request(app, '/api/conversation/checks', {}, cookies, csrf)
        self.assertNotIn(b'unavailable in the pilot', body)
        self.assertEqual(code, 422, body)

    def test_without_checks_the_route_stays_closed(self):
        app = self.app(MemoryHistory()); cookies, csrf = self.join(app)
        self.assertEqual(request(app, '/api/conversation/checks', {}, cookies, csrf)[0], 404)
