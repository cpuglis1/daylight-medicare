"""Money units, source-basis conflicts and explicit unknown benefit states."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
from demo_tools import DemoTools
from naples_catalog import NaplesCatalog
from florida_medigap import normalize
from core_benefits import OUT


class PhaseOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = NaplesCatalog(DemoTools(research_mode=True))

    def test_two_premium_conflicts_show_all_four_bases_and_remain_unrankable(self):
        for pid in ["H1889-026-000-2027", "H5594-017-000-2027"]:
            record = self.catalog.record(pid)
            basis = record["premium_basis"]
            self.assertEqual([o["value"]["value_cents"] for o in basis["observations"]], [730, 730, 0, 0])
            self.assertEqual(basis["state"], "unresolved_source_basis")
            self.assertTrue(record["premium_source_conflict"])
            self.assertEqual(record["eligibility"], "restricted_unconfirmed")
            self.assertIn("basis unresolved", basis["observations"][-1]["label"])
            self.assertIn("PREMIUM", basis["observations"][-1]["value"]["evidence"]["column"])
            self.assertIn("$7.30/month", " ".join(record["notes"]))
            self.assertIn("$0.00/month", " ".join(record["notes"]))
            facts = self.catalog.facts(record)
            fact = next(f for f in facts if f["id"].endswith("monthly_premium"))
            self.assertTrue(any(e.get("artifact") == "monthly_prescription_plan_information" for e in fact["evidence"]))
        ordered = self.catalog.list(priorities=["monthly_premium"])["plans"]
        self.assertEqual({r["id"] for r in ordered[-2:]}, {"H1889-026-000-2027", "H5594-017-000-2027"})

    def test_complete_matrix_does_not_promote_coded_benefits_or_historical_observations(self):
        matrix = cms.load_json(OUT / "c19-core-benefit-matrix.json")
        self.assertEqual(matrix["plan_count"], 70)
        for row in matrix["plans"]:
            self.assertEqual(set(row["fields"]), {d["id"] for d in cms.load_json(OUT / "c19-field-dictionary.json")["definitions"]})
            self.assertIsNone(row["fields"]["inpatient"]["source_cell"]["value"])
            self.assertFalse(row["fields"]["inpatient"]["ranking_allowed"])
            if row["category"] == "PDP":
                self.assertEqual(row["fields"]["inpatient"]["verification_state"], "not_applicable_standalone_PDP")
            elif row["category"] == "SNP":
                self.assertEqual(row["eligibility_state"], "restricted_unconfirmed")
            for cell in row["fields"].values():
                self.assertNotEqual(cell.get("new_C17_observation"), True)

    def fixture(self):
        capture = {"id": "synthetic", "inputs": {"zipCode": "34102", "age": "65", "gender": "f", "smoker": "o", "effectiveDate": "01/01/2027"}, "url": "https://choices.floir.gov/example", "retrieved_at_utc": "2026-10-20T00:00:00+00:00", "sha256": "fixture"}
        row = {"ratE_ID": 1, "agE_CD": "65", "seX_CD": "n", "zipcodE_DS": "34102", "companY_NM": "Synthetic insurer", "plaN_CD": "G*", "ratE_AM": "1949.87"}
        return row, capture

    def test_medigap_annual_rate_not_monthly_quote_or_verified_effective_year(self):
        row, capture = self.fixture()
        result = normalize(row, capture, 0)
        self.assertEqual(result["annual_premium_cents"], 194987)
        self.assertEqual(result["unit"], "USD/year")
        self.assertEqual(result["rate_type"], "illustrative_public_comparison")
        self.assertEqual(result["letter"], "G")
        self.assertTrue(result["high_deductible"])
        self.assertIsNone(result["actual_rate_effective_date"])
        self.assertIsNone(result["naic"])
        self.assertEqual(result["guaranteed_issue_entitlement"], "not_determined")
        self.assertNotIn("monthly_premium_cents", result)

    def test_medigap_unknown_zero_and_filter_mismatches_are_distinct(self):
        row, capture = self.fixture()
        for amount in [None, "0.00"]:
            row["ratE_AM"] = amount
            result = normalize(row, capture, 0)
            self.assertEqual(result["annual_premium_cents"], None if amount is None else 0)
            self.assertEqual(result["amount_state"], "unavailable" if amount is None else "value")
        for amount in ["NaN", "-1.00", "1.001"]:
            row["ratE_AM"] = amount
            with self.assertRaises(cms.SourceError):
                normalize(row, capture, 0)
        row["ratE_AM"] = "100"
        for field, value in [("zipcodE_DS", "34145"), ("agE_CD", "75"), ("seX_CD", "m"), ("plaN_CD", "UNKNOWN")]:
            changed = {**row, field: value}
            with self.assertRaises(cms.SourceError):
                normalize(changed, capture, 0)


if __name__ == "__main__":
    unittest.main()
