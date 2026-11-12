"""Adversarial contract examples; synthetic review IDs never approve evidence.

Expected outcomes are specified here, independently of comparison code. These
are not an offering-wide pilot or an independent review of carrier extraction.
"""
import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from l03_comparison_contract import (
    CONDITION_FAMILIES, compare, fingerprint, check_inventory_transition,
)
from l03_inventory import build, carrier_blocks, cms_json_group


def observation(side="cms"):
    conditions = {family:{"state":"documented_inapplicable",
        "assertion":"Synthetic test: explicitly inapplicable",
        "obligation_ids":["TEST-"+family],"evidence_ids":[side+"-TEST"],
        "interpretation_review_id":"SYNTHETIC-REVIEW"} for family in CONDITION_FAMILIES}
    evidence = {"source_sha256":"a"*64,"side":side,
                "interpretation_review_id":"SYNTHETIC-REVIEW"}
    if side == "cms":
        evidence.update(member="H5652-002-000-2026.json",pointer="/synthetic/cost")
    else:
        evidence.update(pdf_page=3,passage_sha256="b"*64,location={"line_start":1,"line_end":5},
                        headers=["Synthetic hospital row, in network"],footnotes=[])
    return {
        "identity":{"year":2026,"contract":"H5652","plan":"002","segment":"000",
                    "geography":"12021","geographic_variant":"published_Collier"},
        "service":{"category":"1a","subtype":"acute_inpatient"},
        "context":{"network":"in_network","setting":"inpatient_hospital",
                   "population":"published_standard","assistance_basis":"nominal"},
        "cost":{"kind":"copayment","amount":"375.00","range_basis":"exact_schedule"},
        "unit":{"currency_or_percentage":"USD","denominator":"day","period":"stay"},
        "boundaries":{"day_bands":[{"begin":1,"end":7,"amount":"375","unit":"USD/day"},
                                    {"begin":8,"end":90,"amount":"0","unit":"USD/day"}],
                      "quantity":"documented_inapplicable","frequency":"per_stay","reset":"per_stay"},
        "conditions":conditions,"exceptions":[],
        "variant":{"kind":"base","identifier":"base","enrollment_basis":"base_plan_enrollment",
                   "effective_period":"synthetic_2026_period"},
        "shared_budgets":[],"evidence":[evidence],
    }


class StructuredComparison(unittest.TestCase):
    def setUp(self):
        self.cms=observation();self.carrier=observation("carrier")

    def result(self):
        return compare(self.cms,self.carrier)["outcome"]

    def test_exact_decimal_agreement(self):
        self.carrier["cost"]["amount"]="375"
        self.assertEqual(self.result(),"exact_agreement")

    def test_reject_wrong_plan_segment_year(self):
        for key,value in [("year",2027),("plan","001"),("segment","001")]:
            with self.subTest(key=key):
                self.carrier=observation("carrier");self.carrier["identity"][key]=value
                self.assertEqual(self.result(),"conflict")

    def test_reject_wrong_service(self):
        self.carrier["service"]["subtype"]="psychiatric_inpatient"
        self.assertEqual(self.result(),"conflict")

    def test_reject_swapped_network(self):
        self.carrier["context"]["network"]="out_of_network"
        self.assertEqual(self.result(),"conflict")

    def test_reject_day_vs_stay(self):
        self.carrier["unit"]["denominator"]="stay"
        self.assertEqual(self.result(),"conflict")

    def test_reject_quarter_vs_year(self):
        self.cms["unit"]["period"]="quarter";self.carrier["unit"]["period"]="year"
        self.assertEqual(self.result(),"conflict")

    def test_reject_missing_footnote_check(self):
        del self.carrier["evidence"][0]["footnotes"]
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_reject_dropped_exception(self):
        self.cms["exceptions"]=["FQHC Medicare-covered services exempt"]
        self.assertEqual(self.result(),"conflict")

    def test_reject_dropped_later_hospital_band(self):
        self.carrier["boundaries"]["day_bands"].pop()
        self.assertEqual(self.result(),"conflict")

    def test_reject_overlapping_or_inverted_bands(self):
        for begin,end in [(3,2),(6,90)]:
            self.carrier=observation("carrier")
            self.carrier["boundaries"]["day_bands"][1].update(begin=begin,end=end)
            self.assertEqual(self.result(),"insufficient_evidence")

    def test_optional_rider_cannot_be_base(self):
        self.carrier["variant"]["kind"]="optional_rider"
        self.carrier["variant"]["identifier"]="Platinum_Dental"
        self.assertEqual(self.result(),"conflict")

    def test_expected_inventory_identity_binds_both_sources(self):
        expected=copy.deepcopy(self.cms["identity"]);expected["plan"]="001"
        self.assertEqual(compare(self.cms,self.carrier,expected_identity=expected)["outcome"],"conflict")

    def test_effective_period_is_material(self):
        self.carrier["variant"]["effective_period"]="synthetic_later_amendment"
        self.assertEqual(self.result(),"conflict")

    def test_reject_double_counted_shared_budget(self):
        self.carrier["shared_budgets"]=[{"id":"wallet"},{"id":"wallet"}]
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_reject_range_maximum_as_universal(self):
        self.cms["cost"]["range_basis"]="range_maximum"
        self.assertEqual(self.result(),"conflict")

    def test_missing_value_is_not_zero(self):
        self.cms["cost"]["amount"]=None;self.carrier["cost"]["amount"]="0"
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_two_unknowns_cannot_agree(self):
        self.cms["unit"]["period"]="unknown";self.carrier["unit"]["period"]="unknown"
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_incomplete_conditions_cannot_pass(self):
        del self.carrier["conditions"]["deductible"]
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_pending_condition_cannot_pass(self):
        self.carrier["conditions"]["deductible"]["state"]="unknown"
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_conditions_compare_meaning_not_source_ids(self):
        self.carrier["conditions"]["deductible"]["evidence_ids"]=["DIFFERENT-SOURCE-ID"]
        self.assertEqual(self.result(),"exact_agreement")

    def test_nominal_and_assistance_charges_stay_separate(self):
        self.carrier["context"]["assistance_basis"]="QMB_protected"
        self.carrier["cost"]["amount"]="0"
        self.assertEqual(self.result(),"different_basis")

    def test_carrier_native_is_not_cms_agreement(self):
        result=compare(None,self.carrier)
        self.assertEqual(result["outcome"],"supported_carrier_statement")
        self.assertFalse(result["accepted_for_reference"])

    def test_nonfinite_decimal_rejected(self):
        self.carrier["cost"]["amount"]="NaN"
        self.assertEqual(self.result(),"insufficient_evidence")

    def test_arbitrary_mapping_id_cannot_fix_conflict(self):
        self.carrier["service"]["subtype"]="other"
        self.assertEqual(compare(self.cms,self.carrier,mapping="made-up")["outcome"],"conflict")

    def test_mapping_is_bound_to_full_pair_and_receipt(self):
        self.carrier["service"]["subtype"]="reviewed_service_alias"
        approved={"review_decision":"accepted_mapping","cms_sha256":fingerprint(self.cms),
                  "carrier_sha256":fingerprint(self.carrier),"reviewer":"TEST-REVIEWER",
                  "evidence":["TEST-SOURCE"],"review_receipt_sha256":"c"*64}
        self.assertEqual(compare(self.cms,self.carrier,mapping="TEST",mapping_registry={"TEST":approved})["outcome"],
                         "agreement_through_reviewed_mapping")
        self.carrier["cost"]["amount"]="999"
        self.assertEqual(compare(self.cms,self.carrier,mapping="TEST",mapping_registry={"TEST":approved})["outcome"],"conflict")

    def test_identity_mismatch_not_waived_by_mapping(self):
        self.carrier["identity"]["year"]=2027
        approved={"review_decision":"accepted_mapping","cms_sha256":fingerprint(self.cms),
                  "carrier_sha256":fingerprint(self.carrier),"reviewer":"TEST",
                  "evidence":["TEST"],"review_receipt_sha256":"c"*64}
        self.assertEqual(compare(self.cms,self.carrier,mapping="TEST",mapping_registry={"TEST":approved})["outcome"],"conflict")

    def test_inapplicability_requires_explicit_control(self):
        self.carrier["inapplicability"]={"explicit_source_control":False,"review_id":"TEST"}
        self.assertEqual(self.result(),"insufficient_evidence")
        self.carrier["inapplicability"]["explicit_source_control"]=True
        self.assertEqual(self.result(),"documented_inapplicability")


class InventoryBoundaries(unittest.TestCase):
    def setUp(self):
        self.before=[{"id":"claim-1","kind":"required_unknown","required":True,
                      "offering_id":"TEST","parent_id":None,"source_ids":["SOURCE-1"]}]

    def test_cannot_silently_drop_failed_claim(self):
        with self.assertRaises(ValueError):check_inventory_transition(self.before,[])

    def test_cannot_remove_source_reference(self):
        after=copy.deepcopy(self.before);after[0]["source_ids"]=[]
        with self.assertRaises(ValueError):check_inventory_transition(self.before,after)

    def test_cannot_relabel_required_as_extra(self):
        after=copy.deepcopy(self.before);after[0]["required"]=False
        with self.assertRaises(ValueError):check_inventory_transition(self.before,after)

    def test_child_discovery_keeps_root(self):
        after=self.before+[dict(self.before[0],id="child",parent_id="claim-1")]
        self.assertEqual(check_inventory_transition(self.before,after)["added_roots"],1)

    def test_reviewed_change_requires_exact_before_after(self):
        after=[]
        receipt={"review_receipt_sha256":"c"*64,"before_sha256":fingerprint(self.before),
                 "after_sha256":fingerprint(after),"affected_ids":["claim-1"]}
        self.assertEqual(check_inventory_transition(self.before,after,receipt)["reviewed_changes"],["claim-1"])
        receipt["before_sha256"]="invalid"
        with self.assertRaises(ValueError):check_inventory_transition(self.before,after,receipt)

    def test_lossless_carrier_block_boundaries(self):
        lines=["header","","service $25","condition","","continued exception"]
        self.assertEqual(list(carrier_blocks(lines,{3:["claim"],4:["claim"]})),
                         [(1,1,()),(3,4,("claim",)),(6,6,())])

    def test_json_group_preserves_array_item_and_schedule(self):
        self.assertEqual(cms_json_group("/pbp/0/benefitDetails/benefitDetailsInfo/8/benefitDetails/Tier/amount"),
                         "/pbp/0/benefitDetails/benefitDetailsInfo/8")

    def test_builder_refuses_compressed_existing_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            (root/"inventory.sqlite3.gz").write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError,"immutable"):
                build(root)


if __name__ == "__main__":unittest.main()
