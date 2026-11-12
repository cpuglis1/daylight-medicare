"""Fictional safeguards for the offline CSG candidate importer."""
import tempfile
import unittest
from pathlib import Path
from import_csg_medigap import HEADERS, build, money_cents, normalize, parse_scenario


class ImportSafeguards(unittest.TestCase):
    def test_missing_money_is_not_zero(self):
        self.assertIsNone(money_cents(None))
        self.assertIsNone(money_cents("n/a"))
        self.assertEqual(money_cents("0"), 0)
        self.assertEqual(money_cents("123.45"), 12345)

    def test_precision_and_invalid_money_fail(self):
        for value in ("1.001", "-1", "NaN", "Infinity", "unknown"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money_cents(value)

    def test_export_float_tail_is_distinct_from_billing_rounding(self):
        self.assertEqual(money_cents("78.43000000000001"), 7843)
        self.assertEqual(money_cents("84.59999999999999"), 8460)
        with self.assertRaises(ValueError):
            money_cents("78.431")

    def test_year_and_private_client_labels_fail(self):
        for label in ("Real Person - 65 - Female - Non-Tobacco - ZIP: 34102 - November 10, 2026",
                      "Client Name or Quote Label - 65 - Female - Non-Tobacco - ZIP: 34102 - November 10, 2027"):
            with self.assertRaises(ValueError):
                parse_scenario(label)

    def record(self, **overrides):
        raw = dict.fromkeys(HEADERS)
        raw.update({"Company": "Fictional Assurance", "County": "COLLIER", "NAIC": "00001",
                    "Monthly Rate": "100.01", "Annual Rate": "1199.00",
                    "Effective Date": "January 01, 2026", **overrides})
        return normalize(raw, {"fictional": True}, "G", "fictional-source", "Plan G Rates", 11)

    def test_independent_amounts_and_unknown_eligibility(self):
        record = self.record()
        self.assertEqual(record["monthly_cents"], 10001)
        self.assertEqual(record["annual_cents"], 119900)
        self.assertIsNone(record["select_observed"])
        self.assertIsNone(record["policy_form"])
        self.assertFalse(record["personal_quote"])
        self.assertEqual(record["consumer_release"], "held")
        self.assertIsNone(self.record(**{"Annual Rate": "n/a"})["annual_cents"])

    def test_bad_county_naic_and_select_fail(self):
        for override in ({"County": "LEE"}, {"County": "NOTCOLLIER"}, {"County": "LEE;"},
                         {"County": "COLLIER;COLLIER"}, {"County": None},
                         {"NAIC": ""}, {"NAIC": "1234"}, {"Med Select": "maybe"}):
            with self.assertRaises(ValueError):
                self.record(**override)

    def test_source_can_list_multiple_counties_including_collier(self):
        record = self.record(**{"County": "LEE;COLLIER"})
        self.assertEqual(record['county_fips'], '12021')
        self.assertEqual(record['source_county_names'], ['LEE', 'COLLIER'])
        self.assertEqual(record['raw']['County'], 'LEE;COLLIER')
        self.assertFalse(record['personal_quote'])

    def test_source_rows_are_not_deduplicated_by_company(self):
        first = self.record()
        second = normalize(first["raw"], first["scenario"], "G", "fictional-source", "Plan G Rates", 12)
        self.assertNotEqual(first["id"], second["id"])

    def test_existing_candidate_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            sentinel = candidate / "original"
            sentinel.write_text("sealed")
            with self.assertRaises(ValueError):
                build(directory, candidate)
            self.assertEqual(sentinel.read_text(), "sealed")


if __name__ == "__main__":
    unittest.main()
