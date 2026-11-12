"""Failure-path tests for public collection controls; no external requests."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import medicare_collector as m


URL = "https://www.medicare.gov/plan-compare/"


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.seconds = 100.0
        self.calls = []
        self.policy = {"robots": {"allow": ["/core/*.js$"], "disallow": ["/core/", "/app-static-content/", "/user/login/"]}}
        self.config = {"reviewed_get_urls": [URL], "response_sha256": {}}

    async def sleep(self, seconds):
        self.seconds += seconds

    def guard(self):
        return m.Guard(self.config, self.policy, "synthetic-tests", self.root,
                       clock=lambda: self.seconds, sleeper=self.sleep,
                       now=lambda: datetime(2026, 10, 20, 4, tzinfo=timezone.utc))

    async def transport(self):
        self.calls.append(self.seconds)
        return 200, {"Content-Type": "text/html"}, b"<main>synthetic page</main>"

    async def test_identical_query_cached_and_hash_tamper_never_refetched(self):
        g = self.guard()
        first = await g.fetch(URL, "GET", self.transport)
        self.assertEqual(await g.fetch(URL + "#/search-results", "GET", self.transport), first)
        self.assertEqual(len(self.calls), 1)
        (g.root / "raw" / first[0]["sha256"]).write_bytes(b"changed")
        with self.assertRaises(m.Halt):
            await g.fetch(URL, "GET", self.transport)
        self.assertEqual(len(self.calls), 1)

    async def test_concurrent_requests_share_five_second_spacing(self):
        self.config["reviewed_get_urls"].append(URL + "static/a.js")
        g = self.guard()
        await asyncio.gather(g.fetch(URL, "GET", self.transport), g.fetch(URL + "static/a.js", "GET", self.transport))
        self.assertEqual(self.calls, [100, 105])
        # A new guard/process preserves the last request timestamp on disk.
        g = self.guard()
        self.config["reviewed_get_urls"].append(URL + "static/b.js")
        await g.fetch(URL + "static/b.js", "GET", self.transport)
        self.assertEqual(self.calls[-1], 110)

    async def test_stop_responses_and_challenges_persist_before_next_request(self):
        for status, body in [(403, b"forbidden"), (429, b"limited"), (200, b"<title>Verify you are human</title>")]:
            with self.subTest(status=status):
                g = self.guard()
                async def denied():
                    self.calls.append(self.seconds)
                    return status, {"content-type": "text/html"}, body
                with self.assertRaises(m.Halt):
                    await g.fetch(URL, "GET", denied)
                before = len(self.calls)
                with self.assertRaises(m.Halt):
                    await self.guard().fetch(URL, "GET", self.transport)
                self.assertEqual(len(self.calls), before)
                self.assertTrue(list((g.root / "receipts").glob("*.json")))
                (self.root / "STOP").unlink()  # Isolated fixture reset, never production reset.

    async def test_kill_switch_interrupts_wait_and_blocks_cached_requests(self):
        g = self.guard()
        await g.fetch(URL, "GET", self.transport)
        m.dump(self.root / "STOP", {"reason": "synthetic operator stop"})
        with self.assertRaises(m.Halt):
            await g.fetch(URL, "GET", self.transport)
        self.assertEqual(len(self.calls), 1)
        (self.root / "STOP").unlink()
        self.config["reviewed_get_urls"].append(URL + "static/a.js")
        async def stop_during_wait(seconds):
            m.dump(self.root / "STOP", {"reason": "synthetic stop while waiting"})
        g.sleep = stop_during_wait
        with self.assertRaises(m.Halt):
            await g.fetch(URL + "static/a.js", "GET", self.transport)
        self.assertEqual(len(self.calls), 1)

    async def test_unknown_denied_foreign_encoded_and_post_requests_fail_before_network(self):
        for url, method in [("https://example.com/", "GET"), (URL + "unknown", "GET"),
                            ("https://www.medicare.gov/app-static-content/a.js", "GET"),
                            ("https://www.medicare.gov/%75ser/login/", "GET"), (URL, "POST")]:
            with self.subTest(url=url, method=method):
                with self.assertRaises(m.Halt):
                    await self.guard().fetch(url, method, self.transport)
                self.assertEqual(self.calls, [])
                (self.root / "STOP").unlink()

    async def test_redirect_and_changed_app_shape_stop_without_following(self):
        g = self.guard()
        async def redirect():
            return 302, {"location": "https://example.com/"}, b""
        with self.assertRaises(m.Halt):
            await g.fetch(URL, "GET", redirect)
        self.assertNotIn(URL, g.cache)
        (self.root / "STOP").unlink()
        self.config["response_sha256"][URL] = "0" * 64
        with self.assertRaises(m.Halt):
            await self.guard().fetch(URL, "GET", self.transport)

    async def test_request_cap_and_transport_failure_do_not_retry(self):
        g = self.guard(); g.count = 2000
        with self.assertRaises(m.Halt):
            await g.fetch(URL, "GET", self.transport)
        self.assertEqual(self.calls, [])
        (self.root / "STOP").unlink()
        async def broken():
            self.calls.append(self.seconds)
            raise TimeoutError("synthetic failure")
        with self.assertRaises(m.Halt):
            await self.guard().fetch(URL, "GET", broken)
        self.assertEqual(len(self.calls), 1)

    async def test_reviewed_security_post_does_not_admit_other_payloads_or_log_body(self):
        self.config["reviewed_public_security_post_urls"] = [URL]
        g = self.guard()
        body = b'{"sensor_data":"synthetic-browser-only"}'
        await g.fetch(URL, "POST", self.transport, body)
        await g.fetch(URL, "POST", self.transport, body)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("synthetic-browser-only", (g.root / "events.jsonl").read_text())
        with self.assertRaises(m.Halt):
            await g.fetch(URL, "POST", self.transport, b'{"resident":"not-allowed"}')
        self.assertEqual(len(self.calls), 1)

    def test_exclusive_run_lock(self):
        with m.exclusive(self.root):
            with self.assertRaises(m.Halt):
                with m.exclusive(self.root):
                    self.fail("Second run must not acquire the shared pacing lock")

    def test_robots_exception_is_specific_and_does_not_clear_other_denials(self):
        self.assertFalse(m.robots_denies("https://www.medicare.gov/core/a.js", self.policy))
        self.assertTrue(m.robots_denies("https://www.medicare.gov/core/a.js.map", self.policy))
        self.assertTrue(m.robots_denies("https://www.medicare.gov/app-static-content/a.js", self.policy))


if __name__ == "__main__":
    unittest.main()
