"""Source integrity, conditional eligibility, referrals and coverage coordination."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
import local_programs
from chat import Chat, ResponsesClient
from research_http import make_research_test_server as make_server
from demo_tools import DemoTools
from live_conversation import LiveConversation
from naples_catalog import NaplesCatalog
from reply_validation import validate_reply


class LocalProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = DemoTools(research_mode=True)
        cls.chat = Chat(cls.tools, ResponsesClient(key="", model=""))

    def test_pace_is_conditional_and_separate_from_catalog(self):
        data = self.tools.local_resources()
        pace = data["resources"]["pace"]
        self.assertEqual(pace["cms_identity"]["Contract Number"], "H5934")
        self.assertEqual(pace["coverage_path"], "separate_conditional_program")
        self.assertEqual(pace["eligibility_status"], "not_determined")
        self.assertIsNone(pace["service_area"]["zip_codes"])
        self.assertEqual(pace["service_area"]["address_confirmation_phone"], "239-985-6400")
        self.assertEqual(len(NaplesCatalog(self.tools).list()["plans"]), 70)
        response = self.chat.answer("I am 54 and live in 34102. Do I qualify for Hope PACE?")
        self.assertIn("55 or older", response["text"])
        self.assertIn("must assess", response["text"])
        self.assertIn("costs depend on coverage", response["text"])
        self.assertIn("disenrollment", response["text"])
        self.assertNotIn("you qualify", response["text"].lower())

    def test_shine_has_appointment_routes_restriction_and_check_date(self):
        data = self.tools.local_resources()
        shine = data["resources"]["shine"]
        self.assertTrue(data["checked_at_utc"])
        self.assertEqual(shine["phone"], "1-800-963-5337")
        self.assertEqual(shine["sites"][0]["phone"], "239-262-8388")
        self.assertEqual(shine["sites"][1]["restriction"], "Members only")
        self.assertIn("not presented as the appointment", shine["liaison"]["role"])
        result = LiveConversation(self.chat).answer(message="SHINE appointments")
        self.assertEqual(result["conversation_mode"], "source_only")
        self.assertIn("Dates vary", result["text"])
        for fact in result["facts"]:
            for source in fact["evidence"]:
                self.assertTrue(source["sha256"])
                self.assertTrue(source["retrieved_at_utc"])

    def test_other_types_search_is_replayable_and_bounded(self):
        data = local_programs.load()["other_plan_types"]
        self.assertEqual(data["records_searched"], 70)
        self.assertEqual(data["cost_plan_ids"], [])
        self.assertEqual(data["msa_plan_ids"], [])
        self.assertEqual(data["catalog_sha256"], cms.file_hash(cms.ROOT / "reports/work-package-2/catalog.json"))
        self.assertIn("C18", data["conclusion"])

    def test_all_coordination_types_are_review_flags(self):
        flags = local_programs.context(["I have employer retiree coverage, VA healthcare, TRICARE For Life and my old Medigap policy."])
        self.assertEqual({f["key"] for f in flags}, set(local_programs.PATTERNS))
        self.assertTrue(all(f["eligibility_determined"] is False for f in flags))
        self.assertEqual(local_programs.context(["What is TRICARE?"])[0]["status"], "discussed_coverage_unconfirmed")
        self.assertEqual(local_programs.context(["I have a VA loan in Virginia"]), [])
        self.assertEqual(local_programs.context(["I am a veteran"]), [])

    def test_latest_explicit_negatives_clear_only_relevant_flags(self):
        flags = local_programs.context(["I have VA healthcare and TRICARE", "I don't have VA healthcare, I have TRICARE"])
        self.assertEqual([f["key"] for f in flags], ["tricare"])
        self.assertEqual(local_programs.context(["My old Medigap policy", "I no longer have Medigap"]), [])
        self.assertEqual(local_programs.context(["I am not on TRICARE"]), [])
        response = LiveConversation(self.chat).answer(message="I don't have TRICARE", history=[{"role":"user","content":"I have TRICARE"}])
        self.assertEqual(response["coordination_flags"], [])
        self.assertEqual(self.tools.coordination([response['state_update']['current_coverage']])['coordination_flags'], [])
        response = LiveConversation(self.chat).answer(message="I no longer have TRICARE", state={"current_coverage":"I have TRICARE and VA healthcare"})
        self.assertEqual([f['key'] for f in self.tools.coordination([response['state_update']['current_coverage']])['coordination_flags']], ['va'])

    def test_older_policy_year_is_not_rejected_as_catalog_year(self):
        result = self.chat.answer("My Medigap policy is from 2001. Should I switch?")
        self.assertIn("coordination-medigap", [f["id"] for f in result["facts"]])
        self.assertIn("cannot be recovered", result["text"])
        self.assertFalse(result["personal_recommendation"])

    def test_unresolved_provider_and_price_questions_offer_shine(self):
        for message in ["Does my doctor take Humana?", "What is my annual drug cost?"]:
            result = self.chat.answer(message)
            self.assertEqual(result["referral_facts"][0]["id"], "shine-referral")

    def test_model_cannot_omit_contextual_coordination_review(self):
        payloads = []
        value = {"reply":"We can look through the published information.","question":"","fact_ids":[],"quick_replies":[],"state_update":{}}
        def transport(payload):
            payloads.append(payload)
            return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(value)}]}]}
        chat = Chat(self.tools, ResponsesClient(key="synthetic-test", model="test", transport=transport))
        result = LiveConversation(chat).answer(message="Explain the next step", state={"current_coverage":"I have VA healthcare and TRICARE For Life"})
        self.assertEqual([f["key"] for f in result["coordination_flags"]], ["va", "tricare"])
        self.assertEqual([f["id"] for f in result["coordination_facts"]], ["coordination-va", "coordination-tricare", "shine-referral"])
        reviewed = json.loads(payloads[0]["input"][0]["content"])["reviewed_facts"]
        self.assertIn("coordination-va", [f["id"] for f in reviewed])
        self.assertIn("does not automatically", self.tools.education("coordination_va")["facts"][0]["text"])

    def test_eligibility_assertions_rejected_even_with_rule_citation(self):
        facts = {f["id"]:f for f in self.tools.education("pace")["facts"]}
        for text in ["You qualify for PACE.", "Your mom is eligible for PACE.", "You are ineligible for PACE."]:
            with self.assertRaisesRegex(ValueError, "eligibility"):
                validate_reply({"reply":text,"question":"","fact_ids":["pace-eligibility"]}, facts)

    def test_resource_output_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in ("manifest.json", "sources.json", "resources.json", "source-review.json"):
                shutil.copy2(local_programs.REPORTS / name, target / name)
            (target / "resources.json").write_text("{}")
            with patch.object(local_programs, "REPORTS", target), self.assertRaisesRegex(cms.SourceError, "output changed"):
                local_programs.load()

    def test_http_resources_and_catalog_flags_work_without_model(self):
        with tempfile.TemporaryDirectory() as folder:
            server = make_server(self.chat, 0, transcript_dir=folder)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/local-resources") as response:
                    self.assertEqual(json.load(response)["resources"]["pace"]["eligibility_status"], "not_determined")
                payload = {"message":"Show all plans", "state":{"current_coverage":"I have union retiree coverage and TRICARE"}}
                request = Request(base + "/api/live-chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
                with urlopen(request) as response:
                    result = json.load(response)
                self.assertEqual([f["key"] for f in result["coordination_flags"]], ["employer_union", "tricare"])
                self.assertEqual([p["id"] for p in result["catalogs"][0]["plans"]], [p["id"] for p in NaplesCatalog(self.tools).list()["plans"]])
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
