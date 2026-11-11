"""L15 published-directory fidelity and consequential referral boundaries."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import l15_reference as l15


class CounselingReferenceTests(unittest.TestCase):
    def setUp(self):
        self.data = l15.derive()

    def changed(self, change):
        change(self.data)
        with self.assertRaises(ValueError):
            l15.validate(self.data)

    def test_whole_source_and_field_comparison(self):
        result = l15.validate(self.data)
        self.assertEqual(result["native_site_cells_compared"], 12)
        self.assertEqual(result["form_labels_compared"], 13)

    def test_no_site_dropped(self):
        self.changed(lambda d: d["sites"].pop())

    def test_no_phone_substitution(self):
        self.changed(lambda d: d["sites"][0].update(phone="239-652-6900"))

    def test_members_only_survives(self):
        self.changed(lambda d: d["sites"][1].update(member_restriction="not_stated"))

    def test_unstated_does_not_mean_unrestricted(self):
        self.changed(lambda d: d["sites"][0].update(member_restriction="everyone_eligible"))

    def test_no_invented_hours(self):
        self.changed(lambda d: d["sites"][0].update(hours="9 to 5"))

    def test_no_booked_appointment(self):
        self.changed(lambda d: d["sites"][0].update(appointment_booked=True))

    def test_liaison_not_booking_route(self):
        self.changed(lambda d: d["liaison"].update(appointment_route=True))

    def test_no_submission_claim(self):
        self.changed(lambda d: d["online_request"].update(submission_executed=True))

    def test_no_personal_data_transfer(self):
        self.changed(lambda d: d["online_request"].update(personal_data_sent=True))

    def test_no_challenge_execution(self):
        self.changed(lambda d: d["online_request"].update(security_image_requested=True))

    def test_required_form_markers_preserved(self):
        self.changed(lambda d: d["online_request"]["fields"][0].update(marked_required=False))

    def test_form_choices_preserved(self):
        self.changed(lambda d: d["online_request"]["select_options"][0].pop())

    def test_no_fake_approval(self):
        self.changed(lambda d: d["status"].update(human_acceptance="approved"))

    def test_wrong_source_digest(self):
        self.changed(lambda d: d["statewide"]["phone"].update(source_sha256="0" * 64))

    def test_wrong_county(self):
        self.changed(lambda d: d.update(county_fips="12071"))

    def test_wrong_date(self):
        self.changed(lambda d: d.update(as_of_date="2027-10-29"))

    def test_no_consumer_release_without_receipt(self):
        with self.assertRaisesRegex(ValueError, "consumer release"):
            l15.load()

    def test_dated_geography_boundaries(self):
        for args in ({"county_fips": "12071"}, {"as_of": "2026-10-30"}, {"as_of": "2027-10-29"}):
            with self.assertRaisesRegex(ValueError, "dated Collier"):
                l15.load(research_mode=True, **args)

    def test_commercial_and_personal_context_rejected(self):
        for args in ({"commission": 9}, {"dob": "1961-01-01"}, {"member": True}):
            with self.assertRaises(TypeError):
                l15.load(research_mode=True, **args)

    def test_no_rebuild_over_existing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "owner-file").write_text("preserve")
            with self.assertRaisesRegex(ValueError, "new build revision"):
                l15.build(p)
            self.assertEqual((p / "owner-file").read_text(), "preserve")

    def test_replay_is_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "replay"
            l15.build(out)
            for name in ("directory.json", "validation.json"):
                self.assertEqual(l15.digest(out / name), l15.digest(l15.BUILD / name))

    def reader_fixture(self, change=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / l15.BASE.relative_to(l15.ROOT)
            acquisition = base / "acquisition-r2"
            shutil.copytree(l15.ACQUISITION, acquisition)
            (base / "build-r1").mkdir()
            shutil.copy2(l15.BUILD / "directory.json", base / "build-r1/directory.json")
            files = [p for p in base.rglob("*") if p.is_file()]
            l15.save(base / "manifest.json", {"files": {str(p.relative_to(root)): l15.digest(p) for p in files}})
            l15.save(base / "CURRENT_REFERENCE.json", {"manifest_sha256": l15.digest(base / "manifest.json"), "consumer_release": False})
            if change:
                change(base)
            with patch.object(l15, "ROOT", root), patch.object(l15, "ACQUISITION", acquisition):
                return l15.load(research_mode=True, base=base)

    def test_sealed_reader_round_trip(self):
        result = self.reader_fixture()
        self.assertEqual(result["site_count"], 2)
        self.assertFalse(result["status"]["consumer_release"])

    def test_directory_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            self.reader_fixture(lambda b: (b / "build-r1/directory.json").write_text("{}"))

    def test_raw_source_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            self.reader_fixture(lambda b: (b / "acquisition-r2/P26-S58.html").write_text("changed"))

    def test_manifest_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, "selector mismatch"):
            self.reader_fixture(lambda b: (b / "manifest.json").write_text('{"files": {}}'))

    def test_fake_consumer_selector_rejected(self):
        def change(base):
            p = base / "CURRENT_REFERENCE.json"
            d = json.loads(p.read_text())
            d["consumer_release"] = True
            l15.save(p, d)
        with self.assertRaisesRegex(ValueError, "selector mismatch"):
            self.reader_fixture(change)


if __name__ == "__main__":
    unittest.main()
