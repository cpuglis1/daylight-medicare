"""Real carrier sample and HTTP boundary checks for the local Naples read view."""

import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import cms_slice as cms
import validate_naples as validation
import research


class CarrierValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = cms.load_json(validation.CONFIG)
        cls.catalog = cms.load_json(cms.ROOT / "reports/work-package-1/market-12021-2027.json")
        cls.report = validation.validate(cls.config, cls.catalog)

    def test_actual_sample_agreements_are_narrow(self):
        self.assertEqual(self.report["counts"], {
            "sample_records": 5, "source_market_records": 70, "unsampled_records": 65,
            "carrier_document_pdfs_used": 4, "monetary_checks": 12, "monetary_agreements": 12,
            "monetary_conflicts": 0, "negative_candidates_rejected": 3})
        self.assertEqual(self.report["review"]["independent_domain_signoff"], "pending")
        self.assertTrue(all("Not printed" in row["segment_corroboration"] for row in self.report["samples"]))

    def test_same_name_wrong_plan_county_and_year_are_rejected(self):
        errors = [r["observed_errors"] for r in self.report["candidate_rejections"]]
        self.assertIn(["plan_identity_mismatch"], errors)
        self.assertIn(["plan_identity_mismatch", "geography_mismatch"], errors)
        self.assertIn(["benefit_year_mismatch"], errors)

    def test_real_2027_cover_with_2026_approval_footer_is_not_rejected(self):
        record = next(r for r in self.catalog["options"] if r["identity"]["contract"] == "H5434" and r["identity"]["plan"] == "042")
        pages = validation.pdf_pages(cms.ROOT / self.config["artifacts"]["patriot"]["path"])
        self.assertIn("2026_M", pages[0])
        self.assertEqual(validation.context_errors(pages, record, "2027"), [])

    def test_two_pdp_columns_are_not_interchangeable(self):
        record = next(r for r in self.catalog["options"] if r["identity"]["contract"] == "S5904" and r["identity"]["plan"] == "001")
        spec = self.config["artifacts"]["pdp"]
        pages = validation.pdf_pages(cms.ROOT / spec["path"])
        self.assertEqual(validation.observed_money(pages, record, spec)["part_d_total_premium"]["value_cents"], 16460)
        with self.assertRaisesRegex(cms.SourceError, "column identity/order"):
            validation.observed_money(pages, record, {**spec, "columns": list(reversed(spec["columns"]))})

    def test_changed_cms_amount_creates_a_conflict_without_rewriting_source(self):
        catalog = copy.deepcopy(self.catalog)
        row = next(r for r in catalog["options"] if r["identity"]["contract"] == "H5434" and r["identity"]["plan"] == "002")
        row["facts"]["consolidated_premium"]["value_cents"] += 1
        report = validation.validate(self.config, catalog)
        self.assertEqual(report["counts"]["monetary_conflicts"], 1)
        self.assertEqual(row["landscape_raw"]["Monthly Consolidated Premium (Part C + D)"], "$173.00 ")

    def test_missing_pdf_anchor_is_not_a_zero(self):
        with self.assertRaises(cms.SourceError):
            validation.pdf_amount("unrecognized benefit table", r"Monthly premium (\$[0-9.]+)")


class ReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = research.ReadModel()

    def test_all_members_and_source_order_are_preserved(self):
        data = self.model.catalog("2027", "12021")
        self.assertEqual((len(data["options"]), len(data["exclusions"])), (38, 32))
        refs = [r["id"] for r in data["options"] + data["exclusions"]]
        self.assertEqual(len(set(refs)), 70)
        self.assertTrue(all(r["pbp"]["join_status"] == "payload_identity_verified" for r in data["options"] + data["exclusions"]))

    def test_sample_checks_do_not_spread_to_unsampled_records_or_fields(self):
        data = self.model.catalog("2027", "12021")
        rows = data["options"] + data["exclusions"]
        self.assertEqual(sum(r["carrier_sample"]["sampled"] for r in rows), 5)
        self.assertEqual(sum(len(r["carrier_sample"]["checks"]) for r in rows), 12)
        self.assertTrue(all(not r["carrier_sample"]["checks"] for r in rows if not r["carrier_sample"]["sampled"]))

    def test_premium_source_selection_and_null_semantics(self):
        ma = self.model.option("H5434-042-000-2027")
        pdp = self.model.option("S5904-001-000-2027")
        self.assertEqual(ma["plan_premium"]["field"], "part_c_premium")
        self.assertEqual(ma["plan_premium"]["fact"]["value_cents"], 0)
        self.assertEqual(ma["facts"]["consolidated_premium"]["state"], "not_applicable")
        self.assertIsNone(ma["facts"]["annual_part_d_deductible"]["value_cents"])
        self.assertEqual(pdp["plan_premium"]["field"], "part_d_total_premium")
        self.assertIsNone(pdp["facts"]["in_network_medical_moop"]["value_cents"])

    def test_comparison_selection_does_not_reorder_source_results(self):
        refs = ["S5904-001-000-2027", "H5434-042-000-2027", "H5434-002-000-2027"]
        result = self.model.compare(refs)
        self.assertEqual([r["id"] for r in result["options"]], list(reversed(refs)))
        self.assertEqual(result, self.model.compare(list(reversed(refs))))

    def test_excluded_unknown_duplicate_and_oversized_selections_fail(self):
        excluded = self.model.catalog("2027", "12021")["exclusions"][0]["id"]
        for refs in ([excluded], ["H0000-001-000-2027"], ["H5434-002-000-2027"] * 2, [], [r["id"] for r in self.model.catalog("2027", "12021")["options"][:4]]):
            with self.subTest(refs=refs), self.assertRaises(cms.SourceError):
                self.model.compare(refs)

    def test_tampered_persistent_read_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            for name in ("read-manifest.json", "catalog.json", "validation.json"):
                shutil.copyfile(research.REPORTS / name, tmp / name)
            with (tmp / "catalog.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(cms.SourceError, "output changed"):
                research.ReadModel(tmp)


class ReadOnlyHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = research.make_server(research.ReadModel(), port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, method="GET", headers=None):
        request = Request(self.base + path, method=method, headers=headers or {})
        try:
            with urlopen(request) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            result = error.code, error.read(), error.headers
            error.close()
            return result

    def test_catalog_and_excluded_detail_are_accessible(self):
        status, raw, headers = self.request("/api/catalog?year=2027&county_fips=12021")
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(len(data["options"]) + len(data["exclusions"]), 70)
        ref = data["exclusions"][0]["id"]
        status, raw, _ = self.request("/api/options/" + ref)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(raw)["landscape_raw"]), 53)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_unsupported_scope_and_commercial_arguments_do_not_change_results(self):
        for query in ("year=2026&county_fips=12021", "year=2027&county_fips=12071", "year=2027&county_fips=34102",
                      "year=2027&county_fips=12021&partner=x", "year=2027&county_fips=12021&commission=999", "year=2027&year=2026&county_fips=12021"):
            with self.subTest(query=query):
                self.assertEqual(self.request("/api/catalog?" + query)[0], 422)

    def test_writes_are_unavailable(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/api/catalog", method=method)[0], 405)

    def test_files_outside_assets_are_not_served(self):
        for path in ("/../data-sources/release.json", "/%2e%2e/", "/.env", "/data-sources/raw/validation/patriot-2027-sb.pdf", "/api/submit"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_untrusted_host_is_rejected(self):
        self.assertEqual(self.request("/", headers={"Host": "untrusted.example"})[0], 403)

    def test_assets_and_comparison_endpoint(self):
        for path in ("/", "/styles.css", "/app.js"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 200)
        status, raw, _ = self.request("/api/compare?" + urlencode({"ids": "S5904-001-000-2027,H5434-042-000-2027"}))
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in json.loads(raw)["options"]], ["H5434-042-000-2027", "S5904-001-000-2027"])


if __name__ == "__main__":
    unittest.main()
