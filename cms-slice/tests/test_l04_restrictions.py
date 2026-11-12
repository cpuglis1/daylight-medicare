"""Meaningful completeness/corruption checks for the dated L04 supplement."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cms-slice/scripts"))
from l04_restriction_validate import validate

PACKAGE = ROOT / "docs/data/l04-pdp-availability-2026-10-25/restriction-check-r3"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rehash(package):
    manifest = read(package / "manifest.json")
    manifest["files"] = {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in manifest["files"]}
    write(package / "manifest.json", manifest)


class RestrictionAuditTests(unittest.TestCase):
    def clone(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        dest = Path(temp.name) / "supplement"
        shutil.copytree(PACKAGE, dest)
        return dest

    def test_real_all_ten_plans_and_all_notices(self):
        result = validate(PACKAGE)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["offering_count"], 10)
        self.assertEqual(result["plan_date_checks"], 20)
        self.assertEqual(result["indexed_notices_checked"], 89)
        self.assertEqual(result["independent_pdf_extractions"], 88)
        self.assertEqual(result["target_matching_fine_notices"], 4)
        self.assertEqual(result["target_matching_nonmonetary_notices"], 0)

    def test_deleted_plan_is_caught_even_if_rehashed_and_count_lowered(self):
        package = self.clone()
        rows = read(package / "records.json")
        removed = rows.pop()["offering_id"]
        write(package / "records.json", rows)
        coverage = read(package / "coverage.json")
        coverage["offering_count"] = 9
        coverage["plan_date_checks"] = 18
        write(package / "coverage.json", coverage)
        lines = (package / "plan-status.csv").read_text().splitlines(True)
        (package / "plan-status.csv").write_text("".join(s for s in lines if not s.startswith(removed + ",")))
        rehash(package)
        result = validate(package)
        self.assertFalse(result["passed"])
        self.assertIn("all_ten_exact_plan_ids_checked", {f["check"] for f in result["failures"]})

    def test_deleted_notice_does_not_shrink_source_population(self):
        package = self.clone()
        rows = read(package / "notice-ledger.json")
        rows.pop()
        write(package / "notice-ledger.json", rows)
        coverage = read(package / "coverage.json")
        coverage["indexed_notices_checked"] = 88
        write(package / "coverage.json", coverage)
        rehash(package)
        result = validate(package)
        self.assertFalse(result["passed"])
        self.assertIn("every_index_notice_dispositioned_without_omissions", {f["check"] for f in result["failures"]})

    def test_fine_cannot_be_turned_into_plan_restriction(self):
        package = self.clone()
        rows = read(package / "notice-ledger.json")
        target = next(r for r in rows if r["target_contract_matches"])
        target["action_kind"] = "enrollment_suspension"
        target["target_availability_restriction"] = True
        write(package / "notice-ledger.json", rows)
        rehash(package)
        result = validate(package)
        self.assertFalse(result["passed"])
        names = {f["check"] for f in result["failures"]}
        self.assertIn("action_classification_matches_source", names)
        self.assertIn("notice_disposition_accurate", names)

    def test_wrong_reference_date_and_false_live_confirmation_rejected(self):
        package = self.clone()
        rows = read(package / "records.json")
        rows[0]["checks"][0]["as_of"] = "2027-09-02"
        rows[0]["live_enrollment_confirmed"] = True
        write(package / "records.json", rows)
        rehash(package)
        result = validate(package)
        self.assertFalse(result["passed"])
        names = {f["check"] for f in result["failures"]}
        self.assertIn("both_reference_dates_reconciled", names)
        self.assertIn("fine_and_live_availability_kept_distinct", names)


if __name__ == "__main__":
    unittest.main()
