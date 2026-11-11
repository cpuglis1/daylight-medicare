"""Complete-cell grammar, raw-control conservation and real-source regressions."""
import copy
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import l03_benefit_normalization as norm
import l03_normalization_pipeline as run
import l03_review_pipeline as review

FIX = Path(__file__).parent / "fixtures/l03-normalization-r1"
PACKET = review.ROOT / "docs/data/l03-benefit-normalization-2026-11-03-r1"


def fixture_cases():
    return [row for _, row in review.json_rows(FIX / "native-cases.jsonl.gz")]


class CompletePriceGrammar(unittest.TestCase):
    def test_exact_decimals_do_not_round_or_use_float(self):
        self.assertEqual(norm.decimal_text("1,000.00"), "1000")
        self.assertEqual(norm.decimal_text("0.00"), "0")
        a, b = "1.00000000000000000000000000001", "1.00000000000000000000000000002"
        self.assertNotEqual(norm.decimal_text(a), norm.decimal_text(b))
        self.assertEqual(norm.decimal_text(10**400 + 1), str(10**400 + 1))
        for value in (True, False, None, "", "NaN", "Infinity", "-1", 0.1, "1,00", "1e4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                norm.decimal_text(value)

    def test_later_zero_band_and_open_phrase_are_preserved(self):
        result = norm.price_cell("$375 copay per day: days 1-7\n$0 copay per day: days 8 and beyond")
        self.assertEqual(result["form"], "day_schedule")
        self.assertEqual([b["amount"] for b in result["bands"]], ["375", "0"])
        self.assertEqual(result["bands"][1]["end_day"]["state"], "open_source_phrase")
        self.assertIsNone(result["covered_day_limit"])
        self.assertFalse(result["bands"][1]["end_day"]["coverage_entitlement_established"])

    def test_per_stay_and_percentage_base_are_separate(self):
        value = norm.price_cell("40% coinsurance per stay")
        self.assertEqual(value["denominator"], "stay")
        self.assertEqual(value["unit"], "percent")
        self.assertEqual(value["charge_base"], {"state": "unresolved"})
        self.assertEqual(norm.price_cell("$50 copay per visit")["denominator"], "visit")
        self.assertEqual(norm.price_cell("$50 copay")["denominator"], {"state": "unresolved"})

    def test_range_is_not_its_upper_endpoint(self):
        result = norm.price_cell("$0 - $65 copay")
        self.assertEqual(result["form"], "range")
        self.assertEqual((result["minimum"], result["maximum"]), ("0", "65"))
        self.assertNotIn("amount", result)

    def test_unsupported_qualifications_do_not_become_nearby_prices(self):
        for text in ("$0 copay for colonoscopy; $325 copay otherwise", "$65 copay except certain services",
                     "$0 copay - 40% coinsurance depending on service", "$50 copay, 1 per year",
                     "$65 copay $90 copay", "$180 copay per day for days 1-5 except transfers",
                     "No copay", "", "See Medicare rules"):
            with self.subTest(text=text):
                result = norm.price_cell(text)
                self.assertEqual(result["form"], "unresolved")
                self.assertEqual(result["raw_text"], text)

    def test_day_gaps_overlap_order_and_bad_limits_are_flagged(self):
        for text, issue in (
            ("$10 copay per day for days 1-5 $0 copay per day for days 7-90", "gap_in_day_bands"),
            ("$10 copay per day for days 1-5 $0 copay per day for days 5-90", "overlapping_or_unordered_day_bands"),
            ("$10 copay per day for days 9-5", "reversed_day_band")):
            self.assertIn(issue, norm.price_cell(text)["issues"])
        self.assertIn("percentage_over_100", norm.price_cell("150% coinsurance")["issues"])


class NativeControls(unittest.TestCase):
    def test_identity_bridge_is_limited_to_exact_numeric_segment(self):
        source = {"contractYear": 2026, "pbp": [{"contractId": "H5652", "planId": "002", "segmentId": 0}]}
        self.assertEqual(norm.bind_native_identity(source, "2026:H5652:002:000")["canonical_segment"], "000")
        for value in (False, 0.0, "0", -1, 1000):
            changed = copy.deepcopy(source)
            changed["pbp"][0]["segmentId"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                norm.bind_native_identity(changed, "2026:H5652:002:000")
        for offering in ("2027:H5652:002:000", "2026:H1036:002:000", "2026:H5652:001:000", "2026:H5652:002:001"):
            with self.subTest(offering=offering), self.assertRaises(ValueError):
                norm.bind_native_identity(source, offering)

    def test_no_cost_type_is_not_zero_total_cost(self):
        body = {"bdCopaymentAmountYesNoMinMax": "2", "bdCopaymentAmount": ""}
        result = norm.native_flat(body, "copayment")
        self.assertEqual(result["form"], "cost_type_not_selected_candidate")
        self.assertIsNone(result["amount"])
        self.assertEqual(result["raw_component"], body)

    def test_missing_control_does_not_select_populated_amount(self):
        body = {"bdCopaymentAmount": "65"}
        self.assertEqual(norm.native_flat(body, "copayment")["form"], "unresolved")
        body["bdCopaymentAmountYesNoMinMax"] = "9"
        self.assertEqual(norm.native_flat(body, "copayment")["form"], "unresolved")

    def test_inactive_populated_fields_are_not_dropped(self):
        body = {"bdCopaymentAmountYesNoMinMax": "2", "bdCopaymentAmount": "65"}
        result = norm.native_flat(body, "copayment")
        self.assertIn("populated_fields_under_no_cost_type_control", result["issues"])
        self.assertEqual(result["raw_component"]["bdCopaymentAmount"], "65")

    def test_range_qualification_and_invalid_values_are_preserved(self):
        body = {"bdCopaymentAmountYesNoMinMax": "3", "bdCopaymentMinAmount": "0.00", "bdCopaymentMaxAmount": "65.00"}
        result = norm.native_flat(body, "copayment")
        self.assertEqual(result["form"], "range")
        self.assertEqual((result["minimum"], result["maximum"]), ("0", "65"))
        body["bdCopaymentMaxAmount"] = ""
        result = norm.native_flat(body, "copayment")
        self.assertEqual(result["form"], "unresolved")
        self.assertEqual(result["raw_component"], body)

    def test_native_999_stays_finite_and_not_a_coverage_cap(self):
        body = {"bdDayInterval1BeginDay": "1", "bdDayInterval1EndDay": "999", "bdDayInterval1CopaymentAmount": "0"}
        result = norm.native_intervals(body, "CopaymentAmount")
        self.assertEqual(result["bands"][0]["end_day"], {"state": "finite", "value": 999})
        self.assertIsNone(result["covered_day_limit"])

    def test_incomplete_interval_is_not_silently_omitted(self):
        body = {"bdDayInterval1BeginDay": "1", "bdDayInterval1EndDay": "5", "bdDayInterval1CopaymentAmount": "180",
                "bdDayInterval2BeginDay": "6", "bdDayInterval2EndDay": "", "bdDayInterval2CopaymentAmount": "0"}
        result = norm.native_intervals(body, "CopaymentAmount")
        self.assertEqual(result["form"], "unresolved")
        self.assertTrue(result["issues"])
        self.assertEqual(result["raw_component"], body)

    def test_unexpected_populated_interval_type_is_held(self):
        body = {"bdDayInterval1CoinsurancePercentage": "20"}
        result = norm.native_intervals(body, "CopaymentAmount")
        self.assertEqual(result["form"], "unresolved")
        self.assertIn("unexpected_populated_interval_amount_type", result["issues"])
        self.assertEqual(result["raw_component"], body)

    def test_stay_reserve_scalar_and_schedule_remain_nonadditive(self):
        case = next(c for c in fixture_cases() if c["row"]["categoryCode"] == "1a")
        result = norm.native_hospital_component(case["row"]["benefitDetails"]["TierCopaymentComponent"], "copayment")
        self.assertFalse(result["alternatives_are_additive"])
        self.assertTrue(any(a.get("stay_or_reserve") == "reserve" for a in result["alternatives"]))
        self.assertTrue(any(a["form"] == "amount" for a in result["alternatives"]))
        self.assertEqual(result["selection"], {"state": "unresolved"})

    def test_complete_raw_conditions_and_network_components_retained(self):
        for case in fixture_cases():
            result = norm.normalize_native(case["offering_id"], case["row"], case["source"], case["plan_context"])
            self.assertEqual(result["raw_source"], case["row"])
            self.assertEqual(result["plan_context_raw"], case["plan_context"])
            self.assertEqual(set(result["conditions"]), set(norm.CONDITIONS))
            self.assertTrue(all(v["state"] == "unresolved" for v in result["conditions"].values()))
            self.assertFalse(result["calculation_ready"])
            self.assertEqual(result["originals_completed"], 0)
            if "CostShareABPOSComponent" in case["row"]["benefitDetails"]:
                self.assertIn("CostShareABPOSComponent", result["retained_uninterpreted_components"])

    def test_changed_native_payload_rejected(self):
        case = copy.deepcopy(fixture_cases()[0])
        case["row"]["categoryCode"] = "7a"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            norm.normalize_native(case["offering_id"], case["row"], case["source"], case["plan_context"])


class ActualCarrierAndNativeSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads((FIX / "source-expected.json").read_text())
        cls.profiles = json.loads((PACKET / "carrier-layout-profiles.json").read_text())
        cls.pages = [r for _, r in review.json_rows(FIX / "carrier-pages.jsonl.gz")]
        cls.carrier = []
        for profile in cls.profiles:
            page = next(r["record"] for r in cls.pages if r["offering_id"] == profile["offering_id"])
            cls.carrier.extend(norm.normalize_carrier(profile, page))

    def test_carrier_hospital_schedules_against_source_expectations(self):
        for offering, expected in self.expected["carrier"].items():
            row = next(r for r in self.carrier if r["offering_id"] == offering and r["family"] == "inpatient_hospital"
                       and r["context"]["network"]["value"] == "in_network")
            bands = row["cost_components"][0]["bands"]
            e = expected["hospital_in"]
            self.assertEqual([b["amount"] for b in bands], e["amounts"])
            self.assertEqual([b["begin_day"] for b in bands], e["begins"])
            self.assertEqual(bands[0]["end_day"]["value"], e["first_end"])
            self.assertEqual(bands[-1]["end_day"]["state"], e["terminal"])
            if "terminal_end" in e:
                self.assertEqual(bands[-1]["end_day"]["value"], e["terminal_end"])

    def test_network_and_setting_prices_are_separate(self):
        for row in self.carrier:
            offering, family = row["offering_id"], row["family"]
            if family == "inpatient_hospital":
                continue
            scope = row["context"]["network"]["value"] if offering.startswith("2026:H5652") else row["context"]["setting"]["value"]
            self.assertEqual(row["cost_components"][0]["amount"], self.expected["carrier"][offering][family][scope])
        self.assertEqual(len(self.carrier), 11)

    def test_out_of_network_percentage_keeps_per_stay_basis(self):
        row = next(r for r in self.carrier if r["family"] == "inpatient_hospital"
                   and r["context"]["network"]["value"] == "out_of_network")
        expected = self.expected["carrier"][row["offering_id"]]["hospital_out"]
        for key, value in expected.items():
            self.assertEqual(row["cost_components"][0][key], value)

    def test_native_source_expectations_and_specialist_range(self):
        for case in fixture_cases():
            row = norm.normalize_native(case["offering_id"], case["row"], case["source"], case["plan_context"])
            e = self.expected["native"][case["offering_id"]]
            copay = next(c for c in row["cost_components"] if c["kind"] == "copayment")
            if row["family"] == "inpatient_hospital":
                schedule = next(a for a in copay["alternatives"] if a.get("stay_or_reserve") == "stay" and a["bands"])
                self.assertEqual([b["amount"] for b in schedule["bands"]], e["hospital_amounts"])
                self.assertEqual([b["end_day"]["value"] for b in schedule["bands"]], e["hospital_ends"])
            else:
                for key, value in e[row["family"]].items():
                    self.assertEqual(copay[key], value)

    def test_duplicate_anchors_wrong_page_and_shifted_cells_fail_closed(self):
        profile = self.profiles[0]
        original = next(r["record"] for r in self.pages if r["offering_id"] == profile["offering_id"])
        for operation in ("wrong_page", "duplicate_header", "shifted_price"):
            page = copy.deepcopy(original)
            if operation == "wrong_page":
                page["pdf_page"] += 1
            elif operation == "duplicate_header":
                page["layout_text"] += "\n" + page["layout_text"].splitlines()[0]
            else:
                page["layout_text"] = page["layout_text"].replace("$375", "    $375", 1)
                # Force the whole first cell outside its source column.
                page["layout_text"] = page["layout_text"].replace("    $375", " " * 60 + "$375", 1)
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                norm.normalize_carrier(profile, page)

    def test_new_qualifier_becomes_unknown_not_a_headline_price(self):
        profile = self.profiles[1]
        page = copy.deepcopy(next(r["record"] for r in self.pages if r["offering_id"] == profile["offering_id"]))
        page["text"] = page["text"].replace("PCP's office: $0 copay", "PCP's office: $0 copay except certain services")
        rows = norm.normalize_carrier(profile, page)
        row = next(r for r in rows if r["family"] == "primary_care" and r["context"]["setting"]["value"] == "PCP's office")
        self.assertEqual(row["cost_components"][0]["form"], "unresolved")

    def test_price_cell_quote_and_exact_position_replay(self):
        for row in self.carrier:
            source = row["source"]
            page = next(r["record"] for r in self.pages if r["record"]["document_sha256"] == source["document_sha256"])
            lines = page[source["text_field"]].splitlines()
            quote = "\n".join(line[source["column_start"]:source["column_end"]]
                              for line in lines[source["line_start"]-1:source["line_end"]])
            self.assertEqual(quote, source["price_cell_quote"])
            self.assertEqual(norm.fingerprint(page), source["page_record_sha256"])

    def test_source_local_api_and_no_inherited_review_or_release(self):
        self.assertEqual(list(inspect.signature(norm.normalize_carrier).parameters), ["profile", "page"])
        for record in self.carrier:
            for key in ("accepted_for_reference", "consumer_usable", "calculation_ready"):
                self.assertFalse(record[key])
                changed = copy.deepcopy(record)
                changed[key] = True
                with self.assertRaises(ValueError):
                    norm.validate_record(changed)
        self.assertFalse(self.expected["independent_review_complete"])

    def test_empty_exclusions_and_asserted_conditions_cannot_be_inherited(self):
        for field, value in (("exceptions", []), ("shared_budgets", [])):
            record = copy.deepcopy(self.carrier[0])
            record[field] = value
            with self.assertRaises(ValueError):
                norm.validate_record(record)
        record = copy.deepcopy(self.carrier[0])
        record["conditions"]["authorization"]["state"] = "explicit_absence"
        with self.assertRaisesRegex(ValueError, "condition dispositions"):
            norm.validate_record(record)


class ActualNormalizationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="daylight-normalization-test-")
        cls.output = Path(cls.temp.name) / "run"
        cls.summary = run.build(PACKET / "config.json", cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_pipeline_conserves_scope_and_produces_separate_candidates(self):
        self.assertEqual(self.summary["normalization_candidates"], 17)
        self.assertEqual(self.summary["required_originals_preserved"], 10301)
        self.assertEqual(self.summary["global_required_originals"], 392570)
        self.assertEqual(self.summary["newly_accepted_entries"], 0)
        self.assertFalse(self.summary["calculation_ready"])
        self.assertGreater(self.summary["related_hospital_objects_retained"], 0)
        outcomes = json.loads((self.output / "family-diagnostics.json").read_text())
        self.assertEqual(len(outcomes), 6)
        self.assertTrue(all(r["outcome"] == "insufficient_evidence" for r in outcomes))

    def test_frozen_prior_pipeline_and_sources_are_unchanged(self):
        config = json.loads((PACKET / "config.json").read_text())
        review.check_bindings(review.ROOT, config["bindings"])
        parent = review.read_json(review.ROOT, config["parent_config"])
        review.check_bindings(review.ROOT, parent["bindings"])
        run.verify(self.output)

    def test_no_overwrite_and_output_tamper_detection(self):
        with self.assertRaisesRegex(ValueError, "new directory"):
            run.build(PACKET / "config.json", self.output)
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "copy"
            shutil.copytree(self.output, target)
            manifest = json.loads((target / "manifest.json").read_text())
            manifest["accepted_for_reference"] = True
            review.write_json(target / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "grant acceptance"):
                run.verify(target)
            manifest["accepted_for_reference"] = False
            review.write_json(target / "manifest.json", manifest)
            (target / "summary.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "packet changed"):
                run.verify(target)


if __name__ == "__main__":
    unittest.main()
