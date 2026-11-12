"""Checklist-coverage scoring (evaluation suite: checklist coverage)."""
from daylight_operations.checklist import CHECKLIST_ITEMS, coverage_score
from daylight_operations.records import build_decision_record


def test_twelve_distinct_items():
    assert len(CHECKLIST_ITEMS) == 12 == len(set(CHECKLIST_ITEMS))


def test_empty_receipt_covers_nothing():
    score = coverage_score({})
    assert (score["covered"], score["complete"]) == (0, False)
    assert score["missing"] == list(CHECKLIST_ITEMS)


def test_only_explicit_true_counts():
    receipt = {"formulary_coverage": {"covered": True}, "cost_sharing": {"covered": "yes"},
               "right_to_cancel": {"covered": False}}
    score = coverage_score(receipt)
    assert score["covered"] == 1 and "cost_sharing" in score["missing"]


def test_complete_receipt_from_a_decision_record():
    record = build_decision_record(
        purpose="personal_recommendation", state="held", inputs={}, evidence_versions={},
        method_version="m", policy_version="p", candidate_ids=[],
        checklist_coverage={item: {"covered": True} for item in CHECKLIST_ITEMS})
    assert coverage_score(record["checklist_coverage"])["complete"] is True


def test_unknown_items_block_completion():
    receipt = {item: {"covered": True} for item in CHECKLIST_ITEMS} | {"made_up": {"covered": True}}
    score = coverage_score(receipt)
    assert score["unknown_items"] == ["made_up"] and score["complete"] is False
