"""Meaningful source omissions, direction errors and boundary regressions."""
import copy
from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l11_r2_validate as validator
import l11_validate as baseline


class L11R2Tests(unittest.TestCase):
    def mutation(self,filename,change):
        original=validator.load
        def modified(path):
            row=original(path)
            if Path(path)==validator.BUILD/filename:
                row=copy.deepcopy(row);change(row)
            return row
        with patch.object(validator,'load',side_effect=modified):
            return validator.validate()['errors']

    def test_63_and_64_day_boundary_and_unknown(self):
        self.assertTrue(validator.continuity_boundary(63,synthetic=True))
        self.assertFalse(validator.continuity_boundary(64,synthetic=True))
        self.assertIsNone(validator.continuity_boundary(None,synthetic=True))
        with self.assertRaises(ValueError):validator.continuity_boundary(-1,synthetic=True)

    def test_credit_source_parent_cannot_be_lost(self):
        errors=self.mutation('creditable-category-comparisons.json',lambda rows:rows[-1].update(current_parent_text='All supplemental coverage qualifies'))
        self.assertTrue(any('parent fidelity' in e for e in errors))

    def test_enrollment_paragraph_cannot_become_automatic_GI(self):
        errors=self.mutation('sep-crosswalk.json',lambda rows:rows[18].update(classification='CMS_expressly_listed_conditional_route'))
        self.assertTrue(any('Enrollment/historical scope 19' in e for e in errors))

    def test_unresolved_omission_cannot_become_no_right(self):
        errors=self.mutation('sep-crosswalk.json',lambda rows:rows[10].update(absence_from_exhibit_is_no_right_finding=True))
        self.assertTrue(any('negative inference guard 11' in e for e in errors))

    def test_exhibit_row_cannot_disappear(self):
        errors=self.mutation('exhibit-24-crosswalk.json',lambda rows:rows.pop())
        self.assertTrue(any('18-row inventory' in e for e in errors))
        self.assertTrue(any('printed-section census' in e for e in errors))

    def test_exceptional_AB_entry_mismatch_cannot_silently_close(self):
        errors=self.mutation('sep-crosswalk.json',lambda rows:rows[25].update(review_question_ids=[]))
        self.assertTrue(any('hold disappeared or broadened 26' in e for e in errors))

    def test_personal_and_release_guards(self):
        with self.assertRaisesRegex(ValueError,'Personal applicability'):
            validator.continuity_boundary(63)
        errors=self.mutation('summary.json',lambda x:x.update(consumer_release_enabled=True))
        self.assertIn('Reference release guard',errors)

    def test_notice_coverage_end_clock_difference(self):
        clocks={x['id']:x for x in validator.load(validator.PARENT/'clocks.json')}
        # Early notice versus later coverage end produces two different windows.
        a=baseline.synthetic_window(clocks['C04'],{'notice':'2026-10-01','coverage_end':'2026-12-31'},synthetic=True)
        b=baseline.synthetic_window(clocks['C05'],{'notice':'2026-10-01','coverage_end':'2026-12-31'},synthetic=True)
        self.assertEqual(a,(date(2026,10,1),date(2026,12,3)))
        self.assertEqual(b,(date(2026,12,31),date(2027,3,4)))
        # Late notice produces the same end anchor under these two formulas.
        facts={'notice':'2027-01-15','coverage_end':'2026-12-31'}
        self.assertEqual(baseline.synthetic_window(clocks['C04'],facts,synthetic=True),
                         baseline.synthetic_window(clocks['C05'],facts,synthetic=True))

    def test_two_month_boundary_is_not_invented(self):
        clock=next(x for x in validator.load(validator.PARENT/'clocks.json') if x['id']=='C03')
        for day in ['2026-01-15','2026-01-31','2026-02-28']:
            self.assertEqual(baseline.synthetic_window(clock,{'event':day},synthetic=True),(None,None))


if __name__=='__main__':unittest.main()
