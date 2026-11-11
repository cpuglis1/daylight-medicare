"""Year, disclosure, identity and source-integrity boundaries for L10 research."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l10_gap_build as build
import l10_gap_public as public
import l10_gap_validate as audit
import l10_gap_sources as sources
from l10_filings_reference import FilingArchive


class L10GapTests(unittest.TestCase):
    def cycle(self,*titles):return build.cycle_evidence([{'title':t,'type':'Actuarial Memorandum'} for t in titles])

    def test_revision_date_cannot_relabel_2027_memo_as_2026(self):
        r=self.cycle('2027 Select Act Memo 8-24-2026')
        self.assertEqual(r['state'],'2027_cycle_title_hold')
        self.assertIsNone(r['actual_premium_effective_period'])

    def test_administrative_date_is_not_rate_cycle(self):
        self.assertEqual(self.cycle('GBD Third Party Authorization 1 26 2026')['state'],'period_unestablished_from_metadata')

    def test_projection_assumption_is_not_effective_year(self):
        self.assertEqual(self.cycle('Exhibit 2026 trend projection')['state'],'period_unestablished_from_metadata')

    def test_month_coded_memo_remains_candidate(self):
        r=self.cycle('ActMem - FL - all - 202604')
        self.assertEqual(r['state'],'2026_cycle_title_candidate')
        self.assertIsNone(r['actual_premium_effective_period'])

    def test_mixed_cycles_require_review(self):
        self.assertEqual(self.cycle('2026 Actuarial Memo','2027 Actuarial Memo')['state'],'mixed_cycle_titles_require_review')

    def test_sample_company_evidence_preserves_unknown_sale(self):
        rows=audit.read(audit.WORK/'build-r1/company-evidence-matrix.json')
        sample=[r for r in rows if r['in_CHOICES_samples']]
        self.assertEqual(len(sample),34)
        self.assertTrue(all(r['exact_name_case_ids'] and r['current_sale']=='unknown' and r['same_naic_alias_is_not_accepted_equivalence'] for r in sample))

    def test_proposal_does_not_inherit_monthly_units(self):
        rows=audit.read(audit.WORK/'build-r1/group-rate-observations.json')
        proposal=[r for r in rows if r['group']=='FSRBC_Cigna_proposal']
        self.assertEqual(len(proposal),30)
        self.assertTrue(all(r['unit']=='not_explicitly_labeled_in_proposal' and r['filed_rate_approval_period'] is None for r in proposal))

    def test_similar_group_rates_do_not_merge_groups(self):
        comparisons=audit.read(audit.WORK/'build-r1/group-comparisons.json')
        self.assertEqual(sum(not c['same_amount'] for c in comparisons),1)
        self.assertTrue(all(c['groups_merged'] is False for c in comparisons))

    def test_questionnaire_does_not_invent_discount_percentage(self):
        claims=audit.read(audit.WORK/'build-r1/published-discount-questionnaire.json')
        self.assertTrue(all(c['discount_percent'] is None and c['acceptance']=='pending' for c in claims))

    def test_source_audit_rejects_secret_document_as_public(self):
        with tempfile.TemporaryDirectory() as directory:
            copied=Path(directory)/'data';shutil.copytree(audit.WORK/'build-r1',copied)
            path=copied/'document-registry.json';rows=audit.read(path)
            next(r for r in rows if r['trade_secret'])['public_request_candidate']=True
            path.write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):audit.validate(copied)

    def test_source_audit_rejects_year_inferred_from_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            copied=Path(directory)/'data';shutil.copytree(audit.WORK/'build-r1',copied)
            path=copied/'filing-records.json';rows=audit.read(path);rows[0]['actual_rate_period']='2026'
            path.write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):audit.validate(copied)

    def test_sealed_revision_rejects_builder_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'SEALED').touch()
            with self.assertRaises(ValueError):build.build(directory)
            with self.assertRaises(ValueError):public.build(directory)

    def test_parent_research_archive_still_verifies(self):
        archive=FilingArchive();archive.verify()

    def test_sealed_acquisition_cannot_rewrite_source_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'build-r1').mkdir();(path/'build-r1/SEALED').touch()
            with patch.object(sources,'WORK',path),self.assertRaises(ValueError):sources.acquire()


if __name__=='__main__':unittest.main()
