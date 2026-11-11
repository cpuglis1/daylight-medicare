"""Consequential validation boundaries; no research admission double here."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
from consumer_acceptance import ConsumerAcceptance, AcceptanceRequired, WORKSTREAMS, digest
from chat import Chat, ResponsesClient
from demo import make_server
from demo_tools import DemoTools
from naples_catalog import NaplesCatalog
from conversation import Conversation
from live_conversation import LiveConversation


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "acceptance.json"
        self.now = datetime(2026, 10, 20, 17, tzinfo=timezone.utc)
        self.review = {"status": "accepted", "reviewer": {"name": "Synthetic Reviewer", "role": "medicare_subject_matter_reviewer"},
                       "reviewed_at_utc": "2026-10-20T16:00:00+00:00", "review_after_utc": "2026-10-20T23:00:00+00:00",
                       "review_receipt": "synthetic-test-receipt"}
        requirements = {"version": 1, "required_workstreams": sorted(WORKSTREAMS),
                        "claims": [{"id": "benefit:synthetic", "year": "2027", "field": "premium", "cents": 730}]}
        cms.write_json(self.root / "validation-requirements.json", requirements)
        cms.write_json(self.root / "manifest.json", {"fixture": "immutable-manifest"})
        self.manifest = {"release_id": "test-release", "files_sha256": {"validation-requirements.json": cms.file_hash(self.root / "validation-requirements.json")},
                         "source_receipt": {"data_review_after_utc": "2026-10-21T01:33:00+00:00"}}
        self.data = {**self.review, "version": 1, "release_id": "test-release", "manifest_sha256": cms.file_hash(self.root / "manifest.json"),
                     "claims": {"benefit:synthetic": {**copy.deepcopy(self.review), "claim_sha256": digest(requirements["claims"][0]),
                                "conditions_reviewed": True, "reconciliation_receipt": "synthetic-source-reconciliation"}}, "approved_outputs": {}}
        self.save()
        self.gate = ConsumerAcceptance(self.root, self.registry, now=lambda: self.now)
        self.verify = patch("demo_release.verify", return_value=self.manifest)
        self.verify.start()

    def tearDown(self):
        self.verify.stop()
        self.temp.cleanup()

    def save(self):
        cms.write_json(self.registry, self.data)

    def test_only_exact_current_named_review_is_admitted(self):
        self.gate.require_release()
        for key, value in [("release_id", "another-release"), ("manifest_sha256", "0"*64), ("status", "pending"),
                           ("review_after_utc", "2026-10-20T16:30:00+00:00"),
                           ("review_after_utc", "2026-10-30T23:00:00+00:00"),
                           ("reviewed_at_utc", "2026-10-21T16:00:00+00:00"),
                           ("review_after_utc", "2026-10-20T23:00:00"), ("review_receipt", "")]:
            with self.subTest(key=key, value=value):
                old = self.data[key]; self.data[key] = value; self.save()
                with self.assertRaises(AcceptanceRequired): self.gate.require_release()
                self.data[key] = old; self.save()
        self.data["reviewer"]["role"] = "engineering"
        self.save()
        with self.assertRaises(AcceptanceRequired): self.gate.require_release()

    def test_missing_changed_unreviewed_or_conflicting_field_blocks_release(self):
        original = copy.deepcopy(self.data)
        for mutation in (lambda c: c.pop("benefit:synthetic"),
                         lambda c: c["benefit:synthetic"].update(claim_sha256="bad"),
                         lambda c: c["benefit:synthetic"].update(conditions_reviewed=False),
                         lambda c: c["benefit:synthetic"].update(status="conflict"),
                         lambda c: c["benefit:synthetic"].update(reconciliation_receipt="")):
            self.data = copy.deepcopy(original); mutation(self.data["claims"]); self.save()
            with self.assertRaises(AcceptanceRequired): self.gate.require_release()

    def test_changed_runtime_or_data_never_inherits_review(self):
        with patch("demo_release.verify", side_effect=cms.SourceError("changed code")):
            with self.assertRaises(AcceptanceRequired): self.gate.require_release()
        (self.root / "manifest.json").write_text("changed bytes")
        with self.assertRaises(AcceptanceRequired): self.gate.require_release()

    def test_exact_facts_do_not_authorize_another_amount_or_structured_leak(self):
        fact = {"id": "synthetic-premium", "text": "Synthetic source amount $7.30 monthly with stated conditions.", "evidence": [{"sha256": "test"}]}
        self.data["approved_outputs"]["fact:" + digest(fact)] = self.review
        self.save()
        self.gate.require_output({"facts": [fact]})
        changed = copy.deepcopy(fact); changed["text"] = "Synthetic source amount $0 monthly."
        for payload in ({"facts": [changed]}, {"facts": [fact], "results": [{"price_cents": 0}]},
                        {"facts": [fact], "resources": {"unreviewed_rule": "eligible"}}):
            with self.assertRaises(AcceptanceRequired): self.gate.require_output(payload)

    def test_full_plan_review_does_not_replace_field_review(self):
        plan = {"id": "synthetic", "metrics": {"premium": {"state": "value", "value_cents": 730}}, "notes": ["Reviewed conditions"]}
        self.data["approved_outputs"]["plan:" + digest(plan)] = self.review
        self.save()
        with self.assertRaises(AcceptanceRequired): self.gate.require_output({"plans": [plan]})
        field = {"plan_id": plan["id"], "field": "premium", "cell": plan["metrics"]["premium"]}
        self.data["approved_outputs"]["field:" + digest(field)] = self.review
        self.save(); self.gate.require_output({"plans": [plan]})
        plan["notes"].append("Unreviewed exception")
        with self.assertRaises(AcceptanceRequired): self.gate.require_output({"plans": [plan]})

    def test_revocation_and_malformed_registry_are_immediate(self):
        self.gate.require_release()
        self.data["status"] = "revoked"; self.save()
        self.assertFalse(self.gate.status()["consumer_ready"])
        self.registry.write_text("{")
        self.assertFalse(self.gate.status()["consumer_ready"])


class PendingConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = DemoTools()

    def test_direct_tools_catalog_and_conversations_block_before_model_or_network(self):
        client = ResponsesClient(key="test", model="test", transport=lambda p: self.fail("Model called before acceptance"))
        chat = Chat(self.tools, client)
        calls = [lambda: self.tools.market_options(), lambda: self.tools.plan_details("H1889-026-000-2027"),
                 lambda: self.tools.medicine_candidates("Trulicity"), lambda: self.tools.local_resources(),
                 lambda: self.tools.drug_evidence("1551300"), lambda: self.tools.provider_evidence("NCH"),
                 lambda: NaplesCatalog(self.tools).list(priorities=["monthly_premium"]),
                 lambda: chat.answer("Show plans"), lambda: LiveConversation(chat).answer(message="Show plans"),
                 lambda: Conversation(chat).answer({}, message="Hello")]
        for call in calls:
            with self.assertRaises(AcceptanceRequired): call()

    def test_all_real_http_paths_and_static_guidance_are_closed_even_with_research_tools(self):
        # Internal raw-data opt-in must never disable admission at the HTTP boundary.
        with patch.object(self.tools, "research_mode", True), tempfile.TemporaryDirectory() as folder:
            chat = Chat(self.tools, ResponsesClient(key="test", model="test", transport=lambda p: self.fail("Model called")))
            server = make_server(chat, 0, transcript_dir=folder)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            def request(path, value=None):
                req = Request(base + path, data=json.dumps(value).encode() if value is not None else None,
                              headers={"Content-Type": "application/json"})
                try:
                    with urlopen(req) as r: return r.status, r.read().decode()
                except HTTPError as error:
                    with error: return error.code, error.read().decode()
            try:
                code, body = request("/api/status"); state = json.loads(body)
                self.assertFalse(state["consumer_ready"]); self.assertEqual(state["catalog_count"], 0)
                self.assertFalse(state["conversation_available"])
                code, page = request("/"); self.assertEqual(code, 200)
                self.assertIn("Data validation is in progress", page); self.assertNotIn("app.js", page)
                for path, payload in [("/api/chat", {"message": "What is the premium?"}),
                                      ("/api/conversation", {"message": "Show costs", "profile": {}}),
                                      ("/api/live-chat", {"message": "Show all plans"}),
                                      ("/api/catalog", {"priorities": ["monthly_premium"]})]:
                    code, body = request(path, payload)
                    self.assertEqual(code, 503, path); result = json.loads(body)
                    self.assertEqual(result["validation_status"], "pending")
                    self.assertNotIn("facts", result); self.assertNotIn("plans", result); self.assertNotIn("$", body)
                for path in ("/api/local-resources", "/app.js", "/styles.css", "/zip-counties.json"):
                    self.assertEqual(request(path)[0], 503)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
