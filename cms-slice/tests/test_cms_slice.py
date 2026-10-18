"""Structural negatives and independent checks on the actual pinned public archives."""

import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/cms_slice.py"
SPEC = importlib.util.spec_from_file_location("cms_slice", SCRIPT)
cms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cms)


class ParsingTests(unittest.TestCase):
    def test_money_precision_whitespace_and_negative_component(self):
        self.assertEqual(cms.money("$1,234.56 ")["value_cents"], 123456)
        self.assertEqual(cms.money("($15.20)", allow_negative=True)["value_cents"], -1520)
        self.assertEqual(cms.money("($15.20)")["state"], "rejected")
        self.assertEqual(cms.money("$0.00 ")["state"], "value")
        self.assertEqual(cms.money("$0.00 ")["value_cents"], 0)

    def test_null_states_never_become_zero_or_false(self):
        cases = [("", "empty"), ("  ", "empty"), ("Not Applicable", "not_applicable"),
                 ("Not Available", "not_available"), (None, "json_null"), (cms.ABSENT, "absent")]
        for raw, state in cases:
            with self.subTest(state=state):
                result = cms.money(raw)
                self.assertEqual(result["state"], state)
                self.assertIsNone(result["value_cents"])
                if raw is not cms.ABSENT:
                    self.assertEqual(result["raw"], raw)
                else:
                    self.assertNotIn("raw", result)

    def test_unknown_money_encodings_are_rejected(self):
        for raw in ("$1,23.00", "$12.345", "-$1.00", "12.00", "$1e3", "free", "$2.00 extra", 12):
            with self.subTest(raw=raw):
                result = cms.money(raw)
                self.assertEqual(result["state"], "rejected")
                self.assertIsNone(result["value_cents"])

    def test_identifier_types_and_year_are_preserved(self):
        key = cms.identity("2027", "H0104", "012", "0")
        self.assertEqual(key, cms.identity("2027", "H0104", "012", 0))
        self.assertEqual(cms.member_for(key), "H0104-012-000-2027.json")
        self.assertNotEqual(key, cms.identity("2026", "H0104", "012", 0))
        for plan in (12, "12", "0012"):
            with self.assertRaises(cms.SourceError):
                cms.identity("2027", "H0104", plan, 0)
        for segment in (True, None, "0000"):
            with self.assertRaises(cms.SourceError):
                cms.identity("2027", "H0104", "012", segment)

    def test_pointer_distinguishes_absence_from_json_null(self):
        doc = {"pbp": [{"a": None, "b": "Not Available"}]}
        self.assertIsNone(cms.pointer(doc, "/pbp/0/a"))
        self.assertIs(cms.pointer(doc, "/pbp/0/missing"), cms.ABSENT)
        self.assertEqual(cms.pointer(doc, "/pbp/0/b"), "Not Available")

    def test_geography_never_expands_another_state(self):
        market = {"state": "NY", "landscape_county": "New York"}
        row = {"State Territory Abbreviation": "NJ", "County Name": "All Counties", "Contract Category Type": "PDP", "Plan Type": "PDP"}
        self.assertFalse(cms.in_market(row, market))
        row["State Territory Abbreviation"] = "NY"
        self.assertTrue(cms.in_market(row, market))
        row["Contract Category Type"] = "MA"
        with self.assertRaises(cms.SourceError):
            cms.in_market(row, market)


class DriftTests(unittest.TestCase):
    def test_tampered_archive_is_not_accepted(self):
        sources = cms.Sources()
        with tempfile.TemporaryDirectory() as temporary:
            sources.root = Path(temporary)
            path = sources.path("pbp")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"not the pinned source")
            with self.assertRaisesRegex(cms.SourceError, "Checksum/size mismatch"):
                sources.verify_artifact("pbp")

    def test_changed_header_is_not_silently_mapped(self):
        sources = cms.Sources()
        with tempfile.TemporaryDirectory() as temporary:
            sources.root = Path(temporary)
            path = sources.path("landscape")
            path.parent.mkdir(parents=True)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(sources.manifest["artifacts"]["landscape"]["member"], "Contract ID,New Column\nH0104,unknown\n")
            with self.assertRaisesRegex(cms.SourceError, "layout changed"):
                list(sources.landscape())

    def test_payload_identity_and_cardinality_are_checked(self):
        sources = cms.Sources()
        doc = {"contractYear": "2027", "section": "MA&RX", "pbp": [
            {"contractId": "H0104", "planId": "013", "segmentId": 0, "planCharacteristics": {}}]}
        for payload, message in ((doc, "disagreement"), ({**doc, "pbp": []}, "cardinality")):
            with self.subTest(message=message), io.BytesIO() as buffer:
                with zipfile.ZipFile(buffer, "w") as archive:
                    archive.writestr("H0104-012-000-2027.json", json.dumps(payload))
                buffer.seek(0)
                with zipfile.ZipFile(buffer) as archive, self.assertRaisesRegex(cms.SourceError, message):
                    sources.pbp_record(archive, "H0104-012-000-2027.json")


class RealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = cms.Sources()
        # Intentionally fail with instructions if public inputs are missing; never substitute fixtures.
        cls.sources.verify()
        cls.quality, cls.extras, cls.missing, _ = cms.inspect(cls.sources)
        cls.ny = cms.query(cls.sources, "2027", "36061")
        cls.stafford = cms.query(cls.sources, "2027", "51179")
        cls.naples = cms.query(cls.sources, "2027", "12021")

    def test_full_archive_counts_and_population_reconciliation(self):
        q = self.quality
        self.assertEqual(q["landscape"]["rows"], 130307)
        self.assertEqual(q["landscape"]["columns"], 53)
        self.assertEqual(q["landscape"]["plan_segment_keys"], 5884)
        self.assertEqual(q["landscape"]["contract_plan_keys"], 5412)
        self.assertEqual(q["landscape"]["offering_keys"], 130307)
        self.assertEqual(q["landscape"]["all_counties_rows"], 476)
        self.assertEqual(q["pbp"]["payloads_parsed"], 7969)
        self.assertEqual(q["pbp"]["uncompressed_bytes"], 1775307420)
        self.assertEqual(q["pbp"]["payload_filename_identity_errors"], 0)
        self.assertEqual(q["join"]["matched_plan_segments"], 5883)
        self.assertEqual(q["join"]["pbp_only_population"], {
            "documented_employer_exclusion": 1672, "documented_national_pace_exclusion": 414})
        self.assertEqual(q["join"]["plan_name_conflicts"], [])
        self.assertEqual(q["rejected_values_or_arithmetic_conflicts"], [])

    def test_negative_currency_and_missing_ratings_are_real_source_values(self):
        q = self.quality["landscape"]
        self.assertEqual(q["negative_amount_counts"], {"Part D Basic Premium": 46713})
        for field in ("Part C Summary Star Rating", "Part D Summary Star Rating", "Overall Star Rating"):
            self.assertEqual(q["empty_counts"][field], 130307)
        self.assertEqual(q["multiple_premium_tuples_per_plan_segment"], 0)

    def test_independent_market_membership_and_record_replay(self):
        # Separate direct CSV scan, with literal observed scope, checks the whole market, not just a first card.
        spec = self.sources.manifest["artifacts"]["landscape"]
        with self.sources.archive("landscape") as archive:
            rows = list(csv.DictReader(io.TextIOWrapper(archive.open(spec["member"]), encoding="utf-8-sig", newline="")))
        expected = {i: row for i, row in enumerate(rows, 2)
                    if row["State Territory Abbreviation"] == "NY" and row["County Name"] in ("New York", "All Counties")}
        actual = self.ny["options"] + self.ny["exclusions"]
        self.assertEqual(len(expected), 70)
        self.assertEqual(self.ny["counts"], {"source_market_rows": 70, "included": 35, "excluded": 35, "missing_pbp_included": 0})
        self.assertEqual({r["landscape_evidence"]["record_ordinal"] for r in actual}, set(expected))
        for result in actual:
            self.assertEqual(result["landscape_raw"], expected[result["landscape_evidence"]["record_ordinal"]])
        self.assertEqual(sum(r["source_geography"]["scope"] == "statewide_pdp" for r in self.ny["options"]), 9)
        self.assertTrue(all(r["landscape_raw"]["Contract Category Type"] == "SNP" for r in self.ny["exclusions"]))

    def test_all_displayed_cells_replay_to_exact_sources(self):
        with self.sources.archive("pbp") as archive:
            for result in self.ny["options"]:
                for fact in result["facts"].values():
                    loc = fact["evidence"]
                    self.assertEqual(fact["raw"], result["landscape_raw"][loc["column"]])
                    self.assertEqual(loc["archive_sha256"], self.sources.manifest["artifacts"]["landscape"]["sha256"])
                ploc = result["pbp"]["evidence"]
                raw = archive.read(ploc["member"])
                self.assertEqual(cms.sha256(raw), ploc["member_sha256"])
                doc = json.loads(raw)
                for fact in result["pbp"]["source_facts"].values():
                    self.assertEqual(fact.get("raw", cms.ABSENT), cms.pointer(doc, fact["evidence"]["json_pointer"]))
                self.assertIsInstance(result["pbp"]["raw_identity"]["segmentId"], int)
                if result["facts"]["category"]["value"] == "PDP":
                    self.assertEqual(result["facts"]["consolidated_premium"]["state"], "not_applicable")
                    self.assertIsNone(result["facts"]["consolidated_premium"]["value_cents"])

    def test_missing_pbp_is_visible_in_stafford(self):
        self.assertEqual({r["expected_member"] for r in self.missing}, {"H3931-143-000-2027.json"})
        self.assertEqual(len(self.missing), 16)
        investigation = self.quality["join"]["missing_identity_investigation"][0]
        self.assertEqual(len(investigation["related_contract_members"]), 19)
        self.assertEqual(investigation["same_contract_plan_other_segment_or_year"], [])
        target = [r for r in self.stafford["options"] if r["identity"]["contract"] == "H3931" and r["identity"]["plan"] == "143"]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["pbp"]["join_status"], "missing")
        self.assertTrue(any("cause unresolved" in s for s in target[0]["open_checks"]))

    def test_no_substitution_for_unresolved_location_or_year(self):
        for year, fips in (("2026", "36061"), ("2027", "36047"), ("2027", "10001")):
            with self.subTest(year=year, county=fips), self.assertRaises(cms.SourceError):
                cms.query(self.sources, year, fips)

    def test_query_is_repeatable_without_network(self):
        self.assertEqual(cms.query(self.sources, "2027", "36061"), self.ny)

    def test_naples_mapping_is_collier_county_not_a_zip(self):
        market = self.naples["market"]
        self.assertEqual((market["county_fips"], market["state"], market["census_name"], market["landscape_county"]),
                         ("12021", "FL", "Collier County", "Collier"))
        self.assertEqual(market["evidence"]["record_ordinal"], 334)
        self.assertEqual(market["census_raw"]["GEOID"], "12021")
        self.assertEqual(market["requested_place"], "City of Naples, FL")
        with self.assertRaises(cms.SourceError):
            cms.query(self.sources, "2027", "34102")

    def test_independent_naples_membership_includes_every_source_row(self):
        spec = self.sources.manifest["artifacts"]["landscape"]
        with self.sources.archive("landscape") as archive:
            reader = csv.DictReader(io.TextIOWrapper(archive.open(spec["member"]), encoding="utf-8-sig", newline=""))
            expected = {i: row for i, row in enumerate(reader, 2)
                        if row["State Territory Abbreviation"] == "FL" and row["County Name"] in ("Collier", "All Counties")}
        actual = self.naples["options"] + self.naples["exclusions"]
        self.assertEqual(self.naples["counts"], {"source_market_rows": 70, "included": 38, "excluded": 32, "missing_pbp_included": 0})
        self.assertEqual({r["landscape_evidence"]["record_ordinal"] for r in actual}, set(expected))
        for record in actual:
            self.assertEqual(record["landscape_raw"], expected[record["landscape_evidence"]["record_ordinal"]])
            self.assertEqual(record["pbp"]["join_status"], "payload_identity_verified")
            self.assertEqual(record["pbp"]["source_facts"]["plan_name"]["raw"], record["landscape_raw"]["Plan Name"])
        self.assertEqual(sum(r["source_geography"]["scope"] == "statewide_pdp" for r in actual), 11)
        self.assertEqual(sum(r["landscape_raw"]["Contract Category Type"] == "SNP" for r in self.naples["exclusions"]), 27)
        self.assertEqual(sum(r["landscape_raw"]["Plan Type"] == "Regional PPO" for r in self.naples["exclusions"]), 5)

    def test_naples_export_preserves_full_payloads_and_raw_csv_strings(self):
        records = self.naples["options"] + self.naples["exclusions"]
        records.sort(key=lambda r: r["landscape_evidence"]["record_ordinal"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "naples.zip"
            profile = cms.export_market(self.sources, self.naples, path)
            self.assertEqual(profile["pbp_payload_count"], 70)
            self.assertEqual(profile["pbp_uncompressed_bytes"], 16313662)
            self.assertEqual(profile["missing_pbp"], [])
            self.assertEqual(profile["plan_name_conflicts"], [])
            self.assertEqual(profile["category_counts"], {"PDP": 11, "MA-PD": 23, "MA": 9, "SNP": 27})
            with zipfile.ZipFile(path) as exported, self.sources.archive("pbp") as original:
                self.assertEqual(sum(name.startswith("pbp/") for name in exported.namelist()), 70)
                for record in records:
                    member = record["pbp"]["evidence"]["member"]
                    self.assertEqual(exported.read("pbp/" + member), original.read(member))
                rows = list(csv.DictReader(io.StringIO(exported.read("landscape.csv").decode("utf-8"), newline="")))
                self.assertEqual(rows, [r["landscape_raw"] for r in records])
                manifest = json.loads(exported.read("manifest.json"))
                for name, digest in manifest["files_sha256"].items():
                    self.assertEqual(cms.sha256(exported.read(name)), digest)
                # Exact payload preservation includes unmodeled benefits and original JSON nulls.
                member = records[0]["pbp"]["evidence"]["member"]
                doc = json.loads(exported.read("pbp/" + member))
                self.assertIn("pbp", doc)
                self.assertIsInstance(doc["pbp"][0]["segmentId"], int)

    def test_market_export_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / "a.zip", Path(temporary) / "b.zip"
            cms.export_market(self.sources, self.naples, a)
            cms.export_market(self.sources, self.naples, b)
            self.assertEqual(cms.file_hash(a), cms.file_hash(b))

    def test_export_records_missing_payload_instead_of_substituting(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stafford.zip"
            profile = cms.export_market(self.sources, self.stafford, path)
            self.assertEqual(profile["pbp_payload_count"], 60)
            self.assertEqual([r["expected_member"] for r in profile["missing_pbp"]], ["H3931-143-000-2027.json"])
            with zipfile.ZipFile(path) as exported:
                self.assertNotIn("pbp/H3931-143-000-2027.json", exported.namelist())


if __name__ == "__main__":
    unittest.main()
