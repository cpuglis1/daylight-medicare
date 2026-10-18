"""A real positive step-therapy sample from a second exact carrier formulary."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from validate_devoted_drugs import build


class DevotedRestrictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.result=build(out=Path(cls.temp.name)/"sample.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_positive_step_marker_is_exact_and_replayed(self):
        r=self.result
        self.assertEqual(r["plan_id"],"H9884-016-000-2027")
        self.assertEqual(r["positive_step_therapy_products"],2)
        self.assertEqual(r["check_status_counts"],{"agrees":13})
        self.assertEqual(r["source_replay"]["rows"],3)
        for c in r["cases"][:2]:
            self.assertEqual(c["cms_row"]["raw"]["STEP_THERAPY_YN"],"Y")
            self.assertEqual(c["cms_row"]["raw"]["QUANTITY_LIMIT_AMOUNT"]," ")
            self.assertIsNone(c["personal_approval"])

    def test_generic_listing_never_confirms_the_absent_brand(self):
        absent=self.result["absent_brand_case"]
        self.assertFalse(absent["basic_formulary_match"])
        self.assertIsNone(absent["personal_coverage"])
        self.assertIn("absence_not_noncoverage",absent["status"])
