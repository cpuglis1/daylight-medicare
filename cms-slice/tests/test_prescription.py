import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
import prescription as rx
import reference_evidence as ref
import research
import audit_prescription


class PrescriptionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = cms.load_json(rx.CONFIG)
        cls.report = cms.load_json(rx.REPORTS / "quality.json")

    def test_real_geography_and_absence_are_explained(self):
        self.assertEqual(self.report["geography"]["census_fips"], "12021")
        self.assertEqual(self.report["geography"]["puf_ssa"]["COUNTY_CODE"], "10100")
        self.assertEqual(len(self.report["joins"]), 70)
        self.assertEqual(sum(x["status"] == "matched" for x in self.report["joins"]), 61)
        absent = [x for x in self.report["joins"] if not x["selected_plan"]]
        self.assertEqual(len(absent), 9)
        self.assertTrue(all(x["status"] == "not_applicable_non_part_d" for x in absent))
        conflicts = [(row["id"], field) for row in self.report["joins"] for field, value in row["cross_source_amount_checks"].items() if value["status"] == "conflict"]
        self.assertEqual(conflicts, [("H1889-026-000-2027", "PREMIUM"), ("H5594-017-000-2027", "PREMIUM")])
        self.assertTrue(all(not row["comparison_scope"] for row in self.report["joins"] if any(x["status"] == "conflict" for x in row["cross_source_amount_checks"].values())))

    def test_exact_proxy_retains_restrictions_and_no_price(self):
        result = rx.query(self.config, self.report, "H5434-002-000-2027", ndc="00002143380")
        self.assertEqual(result["status"], "listed_with_source_conditions")
        self.assertEqual(len(result["basic_formulary"]), 1)
        row = result["basic_formulary"][0]["raw"]
        self.assertEqual(row["RXCUI"], "1551300")
        self.assertEqual((row["TIER_LEVEL_VALUE"], row["QUANTITY_LIMIT_AMOUNT"], row["QUANTITY_LIMIT_DAYS"], row["PRIOR_AUTHORIZATION_YN"]), ("3", "2", "28", "Y"))
        self.assertIsNone(result["pricing"]["annual_cost"])
        self.assertIsNone(result["pricing"]["pharmacy_drug_price"])
        self.assertEqual(result["basic_formulary"][0]["evidence"]["table"], "formulary")

    def test_real_code_can_be_missing_from_one_formulary(self):
        # Select an actual CMS proxy present in another captured formulary, absent from the first.
        rows = list(rx.captured_rows(rx.CACHE / "formulary.psv.gz"))
        form = next(x["selected_plan"]["raw"]["FORMULARY_ID"] for x in self.report["joins"] if x["id"] == "H5434-002-000-2027")
        present = {r["NDC"] for _, r in rows if r["FORMULARY_ID"] == form}
        absent = next(r["NDC"] for _, r in rows if r["NDC"] not in present)
        result = rx.query(self.config, self.report, "H5434-002-000-2027", ndc=absent)
        self.assertEqual(result["basic_formulary"], [])
        self.assertIn("not_a_noncoverage_conclusion", result["status"])

    def test_non_drug_plan_does_not_inherit_an_adjacent_formulary(self):
        result = rx.query(self.config, self.report, "H5434-042-000-2027", rxcui="1551300")
        self.assertEqual(result["status"], "not_applicable_non_part_d")
        self.assertEqual(result["basic_formulary"], [])

    def test_same_formulary_does_not_mean_same_plan_cost_sharing(self):
        a = rx.query(self.config, self.report, "H5434-002-000-2027", rxcui="1551300")
        b = rx.query(self.config, self.report, "S5904-001-000-2027", rxcui="1551300")
        self.assertEqual(a["basic_formulary"], b["basic_formulary"])
        self.assertTrue(a["beneficiary_cost_rows"] and b["beneficiary_cost_rows"])
        self.assertTrue(all(r["raw"]["CONTRACT_ID"] == "H5434" for r in a["beneficiary_cost_rows"]))
        self.assertTrue(all(r["raw"]["CONTRACT_ID"] == "S5904" for r in b["beneficiary_cost_rows"]))

    def test_real_cost_types_preserve_zero_and_units(self):
        examples = self.report["real_examples"]
        self.assertEqual(examples["cost_not_offered"]["interpretation"]["status"], "not_offered")
        self.assertIsNone(examples["cost_not_offered"]["interpretation"]["value"])
        self.assertEqual(examples["cost_copay"]["interpretation"]["unit"], "USD")
        self.assertEqual(examples["cost_coinsurance"]["interpretation"]["unit"], "fraction")
        self.assertEqual(rx.raw_state(" "), "blank_space")
        self.assertEqual(rx.raw_state(""), "empty")
        self.assertEqual(rx.raw_state("0"), "reported")
        self.assertEqual(rx.raw_state(None), "absent")

    def test_unknown_type_or_bad_amount_is_not_free_coverage(self):
        row = {"COST_TYPE_PREF": "9", "COST_AMT_PREF": "0"}
        self.assertEqual(rx.cost_share(row, "PREF")["status"], "unknown_type")
        for value in ("NaN", "-1", "1.5"):
            self.assertEqual(rx.cost_share({"COST_TYPE_PREF": "2", "COST_AMT_PREF": value}, "PREF")["status"], "rejected_amount")

    def test_exact_npi_join_and_pharmacy_lineage(self):
        result = rx.query(self.config, self.report, "H5434-002-000-2027", rxcui="1551300", npi="1609197854")
        self.assertEqual(result["pharmacy"]["status"], "listed_in_pinned_network")
        self.assertEqual(len(result["pharmacy"]["rows"]), 1)
        row = result["pharmacy"]["rows"][0]
        self.assertEqual(row["raw"]["PHARMACY_NUMBER"], "101609197854")
        self.assertEqual(row["evidence"]["table"], "pharmacy_4")
        self.assertGreater(row["evidence"]["source_row"], 1)

    def test_plan_year_identifier_shape_and_input_ambiguity_are_rejected(self):
        for kwargs in ({}, {"ndc": "00002143380", "rxcui": "1551300"}, {"ndc": "0002-1433-80"}, {"ndc": "2143380"}, {"rxcui": "Trulicity"}, {"rxcui": "1551300", "npi": "101609197854"}):
            with self.assertRaises(cms.SourceError):
                rx.query(self.config, self.report, "H5434-002-000-2027", **kwargs)
        for plan in ("H5434-002-000-2026", "H5434-002-0-2027", "H5434-047-000-2027"):
            with self.assertRaises(cms.SourceError):
                rx.query(self.config, self.report, plan, rxcui="1551300")

    def test_tampered_report_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "manifest.json").write_bytes((rx.REPORTS / "manifest.json").read_bytes())
            (path / "quality.json").write_text("{}\n")
            with self.assertRaisesRegex(cms.SourceError, "quality report changed"):
                rx.verify(self.config, out=path)

    def test_independent_replay_rejects_changed_raw_restriction(self):
        result = rx.query(self.config, self.report, "H5434-002-000-2027", ndc="00002143380")
        result["basic_formulary"][0]["raw"]["QUANTITY_LIMIT_AMOUNT"] = "999"
        with self.assertRaisesRegex(cms.SourceError, "Returned cells differ from formulary"):
            audit_prescription.audit(self.config, result)


class PublicReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = cms.load_json(ref.CONFIG)
        ref.verify_inputs(cls.config)
        cls.provider = cms.load_json(ref.ROOT / cls.config["artifacts"]["npi_individual_sample"]["path"])

    def test_actual_mailing_first_does_not_replace_practice_location(self):
        provider = self.provider["results"][1]
        self.assertEqual(provider["addresses"][0]["address_purpose"], "MAILING")
        found = ref.locations(provider)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["raw"]["address_purpose"], "LOCATION")
        self.assertEqual(found[0]["raw"]["city"], "NAPLES")
        shuffled = copy.deepcopy(provider)
        shuffled["addresses"].reverse()
        self.assertEqual([x["raw"] for x in found], [x["raw"] for x in ref.locations(shuffled)])

    def test_actual_brand_ambiguity_does_not_confirm_a_product_or_coverage(self):
        payload = cms.load_json(ref.ROOT / self.config["artifacts"]["rxnorm_brand_candidates"]["path"])
        result = ref.drug_candidates(payload)
        self.assertEqual(len(result["candidates"]), 4)
        self.assertEqual(result["status"], "requires_specific_product_confirmation")
        self.assertIsNone(result["confirmed_rxcui"])
        self.assertIsNone(result["coverage"])
        self.assertIsNone(result["price"])

    def test_no_vocabulary_result_is_not_noncoverage(self):
        result = ref.drug_candidates({"drugGroup": {"conceptGroup": [{"tty": "SBD"}]}})
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["coverage"])

    def test_public_evidence_does_not_create_quotes_or_network_claims(self):
        report = cms.load_json(ref.REPORTS / "observations.json")
        self.assertEqual(report["medigap"]["quote_receipts"], [])
        self.assertIsNone(report["medigap"]["accepted_premium"])
        self.assertTrue(all(r["network_participation"] is None and not r["license_verified"] for r in report["provider_identity"]["sample"]))
        self.assertEqual(report["carrier_sample"]["quantity_comparison_status"].split(";")[0], "unresolved_unit")


class PrescriptionHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rx_model = research.PrescriptionModel()
        cls.server = research.make_server(research.ReadModel(), 0, cls.rx_model)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        try:
            with urlopen(self.base + path) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            try:
                return error.code, json.load(error)
            finally:
                error.close()

    def test_context_keeps_only_actual_supported_plan_and_product_examples(self):
        status, context = self.get("/api/prescription/context")
        self.assertEqual(status, 200)
        self.assertEqual(len(context["plans"]), 31)
        self.assertEqual(len(context["medicine_example"]["candidates"]), 4)
        self.assertIsNone(context["medicine_example"]["confirmed_rxcui"])
        self.assertEqual(context["pharmacy_example"]["npi"], "1609197854")

    def test_actual_lookup_returns_source_lineage_without_a_personal_price(self):
        status, result = self.get("/api/prescription/lookup?plan_id=H5434-002-000-2027&rxcui=1551300&pharmacy_npi=1609197854")
        self.assertEqual(status, 200)
        self.assertEqual(result["pharmacy"]["status"], "listed_in_pinned_network")
        self.assertIsNone(result["pricing"]["annual_cost"])
        self.assertEqual(result["carrier_product_example"]["quantity_comparison_status"].split(";")[0], "unresolved_unit")
        self.assertIn(result["pharmacy"]["rows"][0]["evidence"]["table"], result["source_tables"])
        self.assertTrue(result["insulin_cost_rows"])

    def test_query_scope_and_commercial_arguments_fail(self):
        for path in ("/api/prescription/context?county_fips=36061", "/api/prescription/lookup?plan_id=H5434-002-000-2026&rxcui=1551300", "/api/prescription/lookup?plan_id=H5434-002-000-2027&rxcui=1551300&commission=500", "/api/prescription/lookup?plan_id=H5434-002-000-2027&rxcui=1551300&rxcui=1551306"):
            self.assertEqual(self.get(path)[0], 422)

    def test_changed_capture_is_rejected_after_startup(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            # The first required capture changes; the request fails before parsing or serving it.
            (path / "formulary.psv.gz").write_bytes(b"changed")
            with patch.object(rx, "CACHE", path):
                with self.assertRaisesRegex(cms.SourceError, "capture unavailable/changed"):
                    self.rx_model.lookup("H5434-002-000-2027", rxcui="1551300")


if __name__ == "__main__":
    unittest.main()
