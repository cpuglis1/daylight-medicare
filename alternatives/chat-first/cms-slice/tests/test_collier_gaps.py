"""Consequential source, pagination, restricted-plan and star-state checks for C04/C05."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
from demo_tools import DemoTools
from naples_catalog import NaplesCatalog
import star_ratings
from chat import Chat, ResponsesClient, ModelUnavailable
from live_conversation import LiveConversation


class CollierGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = DemoTools(research_mode=True)
        cls.catalog = NaplesCatalog(cls.tools)

    def test_all_contract_ratings_have_independent_cell_checks_and_plan_sources(self):
        checks = cms.load_json(star_ratings.REPORTS / "independent-check.json")["checks"]
        self.assertEqual(len(checks), 72)
        self.assertEqual(len({c["contract"] for c in checks}), 24)
        self.assertTrue(all(c["status"] == "agrees" for c in checks))
        plans = self.catalog.list()["plans"]
        self.assertEqual(len(plans), 70)
        for plan in plans:
            stars = plan["star_rating"]
            self.assertEqual(stars["rating_year"], "2027")
            self.assertEqual(stars["published_on"], "2026-10-08")
            self.assertIn("sha256", stars["evidence"])
            self.assertEqual(stars["rating_type"], "part_d_summary" if plan["category"] == "PDP" else "part_c_summary" if plan["category"] == "MA" else "overall")
        for pid in self.tools.by_id:
            self.assertTrue(any(f["id"] == "stars-" + pid for f in self.tools.plan_details(pid)["facts"]))

    def test_unrated_and_inapplicable_never_become_zero(self):
        plan = next(p for p in self.catalog.list()["plans"] if p["id"].startswith("H9917-"))
        self.assertEqual(plan["star_rating"]["state"], "not_enough_data")
        self.assertIsNone(plan["star_rating"]["value"])
        self.assertEqual(plan["star_rating"]["reason"], "Not enough data available")
        value = self.tools.star_ratings["contracts"]["S5904"]["ratings"]["overall"]
        self.assertEqual(value["state"], "not_applicable")
        self.assertIsNone(value["value"])
        for token in ("", "0", "6", "3.2", "NaN", "suppressed for unknown reason"):
            with self.assertRaises(cms.SourceError):
                star_ratings.rating(token)

    def test_pagination_exhausts_exact_70_without_gaps_duplicates_or_scope_exclusions(self):
        ids, offset, sizes = [], 0, []
        while offset is not None:
            page = self.tools.drug_evidence("1551300", offset=offset)
            ids.extend(r["plan_id"] for r in page["results"])
            sizes.append(len(page["results"]))
            self.assertEqual(page["pagination"]["total"], 70)
            self.assertEqual(page["full_option_ids"], sorted(self.tools.by_id))
            offset = page["pagination"]["next_offset"]
        self.assertEqual(sizes, [20, 20, 20, 10])
        self.assertEqual(ids, sorted(self.tools.by_id))
        final = self.tools.drug_evidence("1551300", offset=69, limit=1)
        self.assertIsNone(final["pagination"]["next_offset"])

    def test_restricted_and_regional_records_have_capability_access_without_eligibility_claim(self):
        ids = [r["id"] for r in self.tools.snapshot["exclusions"] if self.tools.joins[r["id"]]["selected_plan"]]
        self.assertEqual(len(ids), 30)
        for pid in ids:
            result = self.tools.drug_evidence("1551300", [pid])
            self.assertEqual(result["results"][0]["plan_id"], pid)
            self.assertIn(result["results"][0]["status"], {"listed_with_source_conditions", "missing_basic_evidence_not_noncoverage"})
            if self.tools.by_id[pid]["category"] == "SNP":
                self.assertIn("eligibility remains unconfirmed", result["facts"][0]["text"])

    def test_ma_only_is_not_applicable_even_when_outside_historical_scope(self):
        ids = [p for p, r in self.tools.by_id.items() if r["category"] == "MA"]
        results = self.tools.drug_evidence("1551300", ids, "1609197854")["results"]
        self.assertEqual(len(results), 9)
        self.assertTrue(all(r["status"] == "not_applicable_non_part_d" and not r["products"] for r in results))

    def test_paging_and_medicine_batch_boundaries_reject_invalid_requests(self):
        for kwargs in ({"offset": -1}, {"offset": 70}, {"offset": True}, {"limit": 0}, {"limit": 21}, {"limit": 1.0}, {"plan_ids": []}, {"plan_ids": ["H5434-002-000-2027"] * 2}, {"plan_ids": ["H0000-000-000-2027"]}):
            with self.assertRaises(cms.SourceError):
                self.tools.drug_evidence("1551300", **kwargs)
        result = self.tools.drug_list_evidence(["1551300", "861007"], offset=40, limit=7)
        self.assertEqual(len(result["results"]), 7)
        self.assertEqual(len(result["facts"]), 14)
        self.assertEqual(result["pagination"]["next_offset"], 47)
        self.assertTrue(all(len(r["medicines"]) == 2 for r in result["results"]))

    def model_client(self, outputs):
        values = iter(outputs)
        return ResponsesClient(key="synthetic-test-key", model="synthetic-test-model", transport=lambda payload: next(values))

    def tool_page(self, offset):
        return {"output": [{"type": "function_call", "name": "drug_evidence", "call_id": "page-" + str(offset),
                            "arguments": json.dumps({"rxcui": "1551300", "plan_ids": None, "pharmacy_npi": None, "offset": offset, "limit": 20})}]}

    def final(self, value):
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}]}

    def test_evidence_adapter_rejects_partial_pages_and_preserves_all_after_exhaustion(self):
        final = self.final({"fact_ids": [], "clarification": "none"})
        chat = Chat(self.tools, self.model_client([self.tool_page(0), final]))
        with self.assertRaisesRegex(ModelUnavailable, "pagination is incomplete"):
            chat.answer("Check RxCUI 1551300 across all plans", use_model=True)
        chat = Chat(self.tools, self.model_client([self.tool_page(i) for i in (0, 20, 40, 60)] + [final]))
        result = chat.answer("Check RxCUI 1551300 across all plans", use_model=True)
        self.assertEqual(len(result["facts"]), 70)
        self.assertTrue(result["model_request_completed"])

    def test_live_adapter_rejects_partial_plan_comparison(self):
        value = {"reply": "The captured formulary lists this medicine.", "question": "", "quick_replies": [],
                 "fact_ids": ["rx-H0710-010-000-2027-1551300"], "state_update": {}}
        client = self.model_client([self.tool_page(0), self.final(value)])
        result = LiveConversation(Chat(self.tools, client)).answer(message="Check RxCUI 1551300 across all plans")
        self.assertTrue(result["fallback"])
        self.assertEqual(result["facts"], [])
        client = self.model_client([self.tool_page(i) for i in (0, 20, 40, 60)] + [self.final(value)])
        result = LiveConversation(Chat(self.tools, client)).answer(message="Check RxCUI 1551300 across all plans")
        self.assertFalse(result["fallback"])
        self.assertTrue(result["model_request_completed"])


if __name__ == "__main__":
    unittest.main()
