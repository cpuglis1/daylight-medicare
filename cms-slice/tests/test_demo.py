"""Real-source checks and consequential boundaries of the Naples demo."""

import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
import prescription as rx
from chat import Chat, ResponsesClient, ModelUnavailable
from demo import make_server
from demo_tools import DemoTools
from evidence_store import PublicSources
from identity_lookup import IdentityLookup
import carrier_quality
import chat as chat_module


class DemoEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = DemoTools()

    def test_ma_only_pharmacy_argument_remains_inapplicable(self):
        result = self.tools.rx.lookup("H5434-042-000-2027", rxcui="1551300", npi="1609197854")
        self.assertEqual(result["status"], "not_applicable_non_part_d")
        self.assertEqual(result["basic_formulary"], [])

    def test_cli_rejects_changed_alternate_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            shutil.copytree(rx.CACHE, cache)
            path = cache / "formulary.psv.gz"
            with gzip.open(path, "rt", encoding="ascii", newline="") as stream:
                lines = stream.readlines()
            columns = lines[0].rstrip("\r\n").split("|")
            index = {name: i for i, name in enumerate(columns)}
            changed = 0
            for i, line in enumerate(lines[1:], 1):
                cells = line.rstrip("\r\n").split("|")
                if cells[index["FORMULARY_ID"]] == "00027047" and cells[index["NDC"]] == "00002143380":
                    cells[index["PRIOR_AUTHORIZATION_YN"]] = "N"
                    lines[i] = "|".join(cells) + "\r\n"
                    changed += 1
            self.assertEqual(changed, 1)
            with gzip.open(path, "wt", encoding="ascii", newline="") as stream:
                stream.writelines(lines)
            output = io.StringIO()
            argv = ["prescription.py", "query", "--plan", "H5434-002-000-2027", "--ndc", "00002143380", "--cache", str(cache)]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                self.assertEqual(rx.main(), 2)
            self.assertIn("Captured prescription evidence changed", output.getvalue())

    def test_actual_generic_search_does_not_hide_the_plain_product_after_combinations(self):
        result = self.tools.medicine_candidates("metformin")
        self.assertGreater(result["candidate_count"], 80)
        self.assertEqual(len(result["candidates"]), result["candidate_count"])
        self.assertFalse(result["truncated"])
        self.assertIn("861007", [p["rxcui"] for p in result["candidates"]])
        self.assertIsNone(result["confirmed_rxcui"])
        self.assertIsNone(result["coverage"])

    def test_actual_brand_search_cannot_confirm_strength(self):
        result = self.tools.medicine_candidates("Trulicity")
        self.assertEqual(len(result["candidates"]), 4)
        self.assertIsNone(result["confirmed_rxcui"])

    def test_same_plan_name_requires_identity_selection(self):
        result = self.tools.plan_candidates("BlueMedicare Select")
        self.assertEqual([p["plan_id"] for p in result["candidates"]], ["H5434-002-000-2027", "H5434-045-000-2027"])
        self.assertIsNone(result["confirmed_plan_id"])
        response = Chat(self.tools).answer("Find BlueMedicare Select")
        self.assertEqual(len(response["choices"]["plans"]), 2)

    def test_explicit_plan_selection_is_used_for_a_followup(self):
        response = Chat(self.tools).answer("Check my medicine", selections={"rxcui": "1551300", "plan_id": "H5434-002-000-2027"})
        self.assertEqual(len(response["facts"]), 1)
        self.assertEqual(response["facts"][0]["plan_id"], "H5434-002-000-2027")

    def test_exact_provider_question_does_not_become_unrelated_plan_premiums(self):
        chat = Chat(self.tools)
        for message in ["Does my doctor take Humana?", "Is Dr Example in network for H5434-002-000-2027?", "Can I keep my physician with BlueMedicare Select?"]:
            response = chat.answer(message)
            self.assertEqual(response["facts"], [], message)
            self.assertIn("unresolved", response["text"])

    def test_future_years_do_not_receive_next_year_source_facts(self):
        for message in ["Show 2028 plans", "Explain H5434-002-000-2029", "Does NCH take Wellcare in 2030?"]:
            self.assertEqual(Chat(self.tools).answer(message)["facts"], [], message)
        self.assertTrue(Chat(self.tools).answer("Does the NCH 2027 change affect 2026 care?")["facts"])

    def test_answer_receipt_binds_actual_identity_evidence_within_the_same_catalog(self):
        chat = Chat(self.tools)
        a,b,c = [chat.answer(q) for q in ["Find Trulicity", "Find Eliquis", "Find Trulicity"]]
        self.assertEqual(a["snapshot_id"],b["snapshot_id"])
        self.assertNotEqual(a["evidence_sha256"],b["evidence_sha256"])
        self.assertEqual(a["evidence_sha256"],c["evidence_sha256"])
        self.assertIsNone(a["model_id"])

    def test_cms_drug_and_plan_facts_do_not_silently_renew_the_review_clock(self):
        review = {**self.tools.data_review, "review_after_utc": "2020-01-01T00:00:00+00:00"}
        with patch.object(self.tools, "data_review", review):
            for message in ["H5434-002-000-2027", "RxCUI 1551300 H5434-002-000-2027", "Show PDP plans"]:
                result = Chat(self.tools).answer(message)
                self.assertIn("review is overdue", result["text"])

    def test_explicit_all_plans_request_is_not_narrowed_by_old_selection(self):
        response = Chat(self.tools).answer("Compare this medicine across all plans", selections={"rxcui": "1551300", "plan_id": "H5434-002-000-2027"})
        self.assertEqual(len(response["facts"]), 38)

    def test_actual_pharmacy_search_does_not_confirm_network(self):
        result = self.tools.pharmacy_candidates("CVS")
        self.assertGreater(len(result["candidates"]), 1)
        self.assertIsNone(result["network_participation"])
        self.assertIsNone(result["confirmed_pharmacy_npi"])
        self.assertTrue(all(p["address"]["city"].casefold() == "naples" for p in result["candidates"]))

    def test_invalid_identity_search_does_not_expand_geography(self):
        with self.assertRaises(cms.SourceError):
            self.tools.identities.pharmacies("CVS", "Miami")
        with self.assertRaises(cms.SourceError):
            self.tools.identities.medicines("https://example.com/private")

    def test_compact_drug_evidence_replays_to_existing_query(self):
        pid = "H5434-002-000-2027"
        raw = rx.query(self.tools.rx.config, self.tools.rx.report, pid, rxcui="1551300", npi="1609197854")
        result = self.tools.drug_evidence("1551300", [pid], "1609197854")
        product = result["results"][0]["products"][0]
        self.assertEqual(product["ndc11"], raw["basic_formulary"][0]["raw"]["NDC"])
        self.assertEqual(product["prior_authorization"], "Y")
        self.assertEqual(product["raw_quantity"], "2")
        self.assertIsNone(product["quantity_unit"])
        self.assertNotIn("insulin_cost_rows", result)
        self.assertEqual(result["pricing"], "unavailable_for_2027")
        self.assertEqual(result["results"][0]["pharmacy"]["status"], "listed_in_pinned_network")

    def test_batch_keeps_all_requested_options_and_no_suitability_order(self):
        plans = ["S5904-001-000-2027", "H5434-042-000-2027", "H5434-002-000-2027"]
        result = self.tools.drug_evidence("1551300", plans)
        self.assertEqual([r["plan_id"] for r in result["results"]], sorted(plans))
        self.assertEqual(result["results"][1]["status"], "not_applicable_non_part_d")
        self.assertTrue(result["preserve_all_facts"])

    def test_nch_notice_has_effective_dates_and_no_exact_confirmation(self):
        result = self.tools.provider_evidence("NCH", "H1032-198-000-2027")
        self.assertIsNone(result["exact_plan_participation"])
        self.assertIsNone(result["accepting_new_patients"])
        self.assertTrue(any(f.get("effective_start") == "2027-01-01" for f in result["facts"]))
        self.assertTrue(any("hospital" in f["text"] and "medical group" in f["text"] for f in result["facts"]))

    def test_medicine_list_preserves_each_plan_product_and_inapplicable_state(self):
        plans = ["S5904-001-000-2027", "H5434-042-000-2027", "H5434-002-000-2027"]
        codes = ["1551300", "861007", "1364447"]
        result = self.tools.drug_list_evidence(codes, plans)
        self.assertEqual(result["full_option_ids"], sorted(plans))
        self.assertEqual(len(result["facts"]), 9)
        self.assertEqual([f["plan_id"] for f in result["facts"]], [pid for pid in sorted(plans) for _ in codes])
        for row in result["results"]:
            self.assertEqual([m["rxcui"] for m in row["medicines"]], sorted(codes, key=int))
            if row["plan_id"] == "H5434-042-000-2027":
                self.assertTrue(all(m["status"] == "not_applicable_non_part_d" for m in row["medicines"]))
        response = Chat(self.tools).answer("Check RxCUIs 1551300, 861007 and 1364447 in H5434-002-000-2027")
        self.assertEqual(len(response["facts"]), 3)
        self.assertEqual(response["tool_calls"], ["drug_list_evidence"])

    def test_medicine_list_rejects_duplicates_oversize_and_unconfirmed_names(self):
        for codes in [[], ["1551300", "1551300"], [str(n) for n in range(1, 17)], ["Trulicity"]]:
            with self.assertRaises(cms.SourceError):
                self.tools.drug_list_evidence(codes)

    def test_unknown_provider_is_unresolved_not_out_of_network(self):
        result = self.tools.provider_evidence("Unlisted Example Doctor")
        self.assertIsNone(result["exact_plan_participation"])
        self.assertEqual(result["facts"], [])

    def test_quality_matrix_does_not_spread_carrier_checks(self):
        quality = cms.load_json(cms.ROOT / "reports/demo-quality.json")
        self.assertEqual(len(quality["matrix"]), 38 * 3)
        self.assertGreaterEqual(quality["carrier_records_checked"], 16)
        self.assertGreaterEqual(quality["carrier_parent_organizations_checked"], 3)
        self.assertEqual(quality["field_status_counts"].get("conflict", 0), 0)
        self.assertTrue(any(x["corroboration"]["status"] == "not_independently_checked" for x in quality["matrix"]))
        self.assertTrue(all(x["qualified_domain_signoff"] == "pending" for x in quality["matrix"]))
        self.assertEqual(quality["medicare_gov_field_status_counts"], {"agrees": 96, "not_applicable_agrees": 18})

    def test_medical_summary_preserves_a_real_cost_range(self):
        result = self.tools.plan_details("H5521-272-000-2027")
        summaries = [f for f in result["facts"] if f["id"].endswith("official-office-summary")]
        self.assertEqual(len(summaries), 1)
        self.assertIn("$0-$72 copay", summaries[0]["text"])
        self.assertIn("conditions still need checking", summaries[0]["text"])

    def test_quality_report_tampering_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality.json"
            path.write_bytes(carrier_quality.OUT.read_bytes() + b" ")
            with self.assertRaisesRegex(cms.SourceError, "Quality evidence changed"):
                carrier_quality.verify(path=path)

    def test_frozen_source_review_window_is_rechecked_at_answer_time(self):
        fact = copy.deepcopy(self.tools.knowledge.facts["nch-2027-change"])
        fact["evidence"]["review_after_utc"] = "2000-01-01T00:00:00+00:00"
        result = Chat(self.tools)._render([fact])
        self.assertIn("review is overdue", result["text"])
        self.assertEqual(result["facts"][0]["evidence"][0]["freshness"], "review_overdue")

    def test_comparison_keeps_source_order_when_user_names_plans_in_reverse(self):
        result = Chat(self.tools).answer("Compare S5904-001-000-2027 and H5434-002-000-2027", use_model=True)
        ids = list(dict.fromkeys(f["plan_id"] for f in result["facts"] if f.get("plan_id")))
        self.assertEqual(ids, ["H5434-002-000-2027", "S5904-001-000-2027"])

    def test_answer_receipt_pins_the_loaded_code(self):
        expected = chat_module.CHAT_CODE_SHA256
        with patch.object(cms, "file_hash", return_value="a-later-file-version"):
            result = Chat(self.tools)._render([])
        self.assertEqual(result["answer_code_sha256"], expected)
        self.assertIn("answered_at_utc", result)

    def test_changed_source_snapshot_is_not_read(self):
        original = PublicSources()
        source, raw = original.read("medicare-parts")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cms.write_json(path / "registry.json", {"version": 1, "sources": {"medicare-parts": source}})
            (path / source["sha256"]).write_bytes(raw + b"changed")
            with self.assertRaises(cms.SourceError):
                PublicSources(path / "registry.json", path).read("medicare-parts")

    def test_local_selection_does_not_override_new_pharmacy_search(self):
        result = Chat(self.tools).answer("Find CVS in Naples", selections={"rxcui": "1551300"})
        self.assertTrue(result["choices"]["pharmacies"])
        self.assertEqual(result["choices"]["medicines"], [])

    def test_local_chat_keeps_unsupported_price_and_market_scope_unavailable(self):
        chat = Chat(self.tools)
        result = chat.answer("What is my cheapest plan and annual cost?")
        self.assertIn("unavailable", result["text"])
        self.assertFalse(result["personal_recommendation"])
        self.assertEqual(chat.answer("Show 2026 plans")["facts"], [])


class ModelBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = DemoEvidenceTests.tools if hasattr(DemoEvidenceTests, "tools") else DemoTools()

    def client(self, outputs, payloads=None):
        sequence = iter(outputs)
        def transport(payload):
            if payloads is not None:
                payloads.append(payload)
            return {"status": "completed", "output": next(sequence)}
        return ResponsesClient(key="test-not-a-live-key", model="controlled-test-model", transport=transport)

    def function(self, name, arguments):
        return [{"type": "function_call", "name": name, "arguments": json.dumps(arguments), "call_id": "test-call"}]

    def final(self, ids, clarification="none"):
        return [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"fact_ids": ids, "clarification": clarification})}]}]

    def test_responses_adapter_releases_only_real_fact_text_and_disables_storage(self):
        payloads = []
        client = self.client([self.function("education", {"topic": "prior_authorization"}), self.final(["education-pa"])], payloads)
        result = Chat(self.tools, client).answer("Explain prior authorization", use_model=True)
        self.assertEqual(result["facts"][0]["text"], self.tools.knowledge.facts["education-pa"]["text"])
        self.assertTrue(all(p["store"] is False for p in payloads))
        self.assertNotIn("test-not-a-live-key", json.dumps(payloads))

    def test_invented_fact_id_never_becomes_an_answer(self):
        client = self.client([self.final(["made-up-lowest-price"])])
        with self.assertRaises(ModelUnavailable):
            Chat(self.tools, client).answer("What would I pay?", use_model=True)

    def test_model_cannot_silently_confirm_medicine(self):
        client = self.client([self.function("drug_evidence", {"rxcui": "1551300", "plan_ids": None, "pharmacy_npi": None})])
        with self.assertRaisesRegex(ModelUnavailable, "unconfirmed medicine"):
            Chat(self.tools, client).answer("I take Trulicity", use_model=True)

    def test_model_cannot_pick_a_plan_not_named_by_the_user(self):
        client = self.client([self.function("plan_details", {"plan_id": "H5434-002-000-2027"})])
        with self.assertRaisesRegex(ModelUnavailable, "did not name"):
            Chat(self.tools, client).answer("What plan is best?", use_model=True)

    def test_model_cannot_remove_rows_from_a_market_listing(self):
        client = self.client([self.function("market_options", {"year": "2027", "county_fips": "12021", "category": "PDP"}), self.final(["plan-S5904-001-000-2027"])])
        result = Chat(self.tools, client).answer("Show PDP plans", use_model=True)
        self.assertEqual(len(result["facts"]), 12)
        self.assertEqual([f.get("plan_id") for f in result["facts"] if f.get("plan_id")], [r["id"] for r in self.tools.snapshot["options"] if r["category"] == "PDP"])

    def test_model_without_key_never_claims_a_live_answer(self):
        with self.assertRaises(ModelUnavailable):
            Chat(self.tools, ResponsesClient(key="", model="")).answer("Hello", use_model=True)

    def test_malformed_tool_arguments_are_rejected_with_a_model_error(self):
        for output in [self.function("drug_evidence", {"rxcui":"1551300","plan_ids":[{}],"pharmacy_npi":None}),
                       [{"type":"function_call","name":"education","arguments":123,"call_id":"bad"}]]:
            client=self.client([output])
            with self.assertRaises(ModelUnavailable):
                Chat(self.tools,client).answer("Check my medicine", selections={"rxcui":"1551300"}, use_model=True)

    def test_model_medicine_batch_cannot_add_a_product_or_drop_source_rows(self):
        args = {"rxcuis": ["1551300", "1364447"], "plan_ids": ["H5434-002-000-2027"], "pharmacy_npi": None}
        client = self.client([self.function("drug_list_evidence", args)])
        with self.assertRaisesRegex(ModelUnavailable, "unconfirmed"):
            Chat(self.tools, client).answer("Check RxCUI 1551300 in H5434-002-000-2027", use_model=True)
        client = self.client([self.function("drug_list_evidence", args), self.final([])])
        result = Chat(self.tools, client).answer("Check RxCUIs 1551300 and 1364447 in H5434-002-000-2027", use_model=True)
        self.assertEqual(len(result["facts"]), 2)

    def test_model_cannot_omit_dated_provider_limitations(self):
        # Select only a real favorable-looking fact; the effective-date and product limits must survive.
        real_id = "nch-setting"
        client = self.client([self.function("provider_evidence", {"name": "NCH", "plan_id": None}), self.final([real_id])])
        result = Chat(self.tools, client).answer("Does NCH accept my plan?", use_model=True)
        self.assertEqual(len(result["facts"]), 4)
        self.assertIn("January 1, 2027", result["text"])

    def test_model_cannot_invent_a_provider_search_or_silence_an_unresolved_check(self):
        client = self.client([self.function("provider_evidence", {"name": "NCH", "plan_id": None})])
        with self.assertRaisesRegex(ModelUnavailable, "did not name"):
            Chat(self.tools, client).answer("Does Dr Example accept my plan?", use_model=True)
        client = self.client([self.function("provider_evidence", {"name": "Dr Example", "plan_id": None}), self.final([])])
        result = Chat(self.tools, client).answer("Does Dr Example accept my plan?", use_model=True)
        self.assertIn("unresolved", result["text"])

    def test_model_cannot_omit_product_confirmation_prompt(self):
        client = self.client([self.function("medicine_candidates", {"name": "Trulicity"}), self.final([])])
        result = Chat(self.tools, client).answer("Find Trulicity", use_model=True)
        self.assertEqual(len(result["choices"]["medicines"]), 4)
        self.assertIn("Choose the exact medicine", result["text"])

    def test_model_cannot_reduce_plan_details_to_premium_only(self):
        pid = "H5434-002-000-2027"
        client = self.client([self.function("plan_details", {"plan_id": pid}), self.final([pid+"-consolidated_premium"])])
        result = Chat(self.tools, client).answer("Explain "+pid, use_model=True)
        self.assertEqual(len(result["facts"]), len(self.tools.plan_details(pid)["facts"]))


class DemoHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chat = Chat(DemoEvidenceTests.tools, ResponsesClient(key="", model=""))
        cls.server = make_server(cls.chat, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, path, data=None, headers=None):
        request = Request(self.url+path, data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urlopen(request) as response:
                return response.status, response.read()
        except HTTPError as error:
            with error:
                return error.code, error.read()

    def test_simple_chat_serves_real_provider_evidence(self):
        status, raw = self.request("/api/chat", {"message": "What changed at NCH for 2027?"})
        result = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertIn("January 1, 2027", result["text"])
        self.assertFalse(result["personal_recommendation"])

    def test_cross_origin_host_and_query_guards(self):
        self.assertEqual(self.request("/api/chat", {"message": "hello"}, {"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.request("/", headers={"Host": "untrusted.example"})[0], 403)
        self.assertEqual(self.request("/api/status?medicine=private")[0], 422)

    def test_arbitrary_actions_and_profile_writes_are_rejected(self):
        self.assertEqual(self.request("/api/chat", {"message": "hello", "role": "system"})[0], 422)
        self.assertEqual(self.request("/api/enroll", {"message": "hello"})[0], 404)
        self.assertEqual(self.request("/api/chat", {"message": "x"*17000})[0], 413)

    def test_missing_live_model_is_visible(self):
        self.assertEqual(self.request("/api/chat", {"message": "Explain prior authorization", "use_model": True})[0], 503)
        self.assertEqual(self.request("/api/chat", {"message": "Explain prior authorization", "use_model": "yes"})[0], 422)

    def test_only_fixed_assets_are_served(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)
        self.assertEqual(self.request("/../../data-sources/demo-sources.json")[0], 404)


if __name__ == "__main__":
    unittest.main()
