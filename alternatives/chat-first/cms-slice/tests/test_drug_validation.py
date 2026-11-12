"""Independent carrier sample, exact product joins and consequential unit limits."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
import drug_validation as sample
import prescription as rx


class DrugSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.result = sample.build(out=root / "sample.json", manifest_path=root / "manifest.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_nine_exact_products_agree_only_on_reviewed_fields(self):
        self.assertEqual(self.result["product_cases"], 9)
        self.assertEqual(self.result["check_status_counts"], {"agrees": 45})
        self.assertEqual(self.result["source_replay"]["rows"], 9)
        cases = {c["rxcui"]: c for c in self.result["cases"]}
        self.assertNotEqual(cases["861007"]["row_name"], cases["860975"]["row_name"])
        self.assertEqual(cases["1364447"]["carrier"]["quantity"], "74")
        self.assertEqual(cases["1364441"]["carrier"]["quantity"], "60")

    def test_equal_and_different_quantities_both_keep_unknown_cms_units(self):
        quantities = [r["quantity_comparison"] for c in self.result["cases"] for r in c["cms_rows"]]
        self.assertEqual(sum(q["numeric_amounts_equal"] for q in quantities), 7)
        self.assertTrue(all(q["cms_unit"] is None for q in quantities))
        self.assertTrue(all(q["status"] == "unit_unresolved_no_conversion_or_quantity_acceptance" for q in quantities))
        lantus = next(c for c in self.result["cases"] if c["rxcui"] == "285018")["cms_rows"][0]["quantity_comparison"]
        self.assertEqual((lantus["carrier_amount"], lantus["carrier_unit"], lantus["cms_raw_amount"]), ("6", "vials", "60"))

    def test_replay_rejects_a_changed_actual_restriction(self):
        row = copy.deepcopy(self.result["cases"][0]["cms_rows"][0])
        row["raw"]["PRIOR_AUTHORIZATION_YN"] = "N"
        with self.assertRaisesRegex(cms.SourceError, "original national source"):
            sample.replay_rows(cms.load_json(rx.CONFIG), [row])

    def test_partial_name_cannot_validate_a_different_strength(self):
        page = self.result["cases"][1]["carrier"]["raw_line"]
        with self.assertRaises(cms.SourceError):
            sample.carrier_row(page, "ELIQUIS - apixaban tab 5 mg")


if __name__ == "__main__":
    unittest.main()
