"""Offline tests for decision records and the commercial-context guard."""
import pytest

from daylight_operations.checklist import CHECKLIST_ITEMS
from daylight_operations.records import (CommercialContextError, build_decision_record, canonical_sha256,
                                         commercial_keys, substantive_result)

# Same cases as tests/sql/001_operations_test.sql, so the Python and SQL rules agree.
GUARD_CASES = [
    ({"commission": 1}, True),
    ({"a": [{"b": {"Carrier_Contract": True}}]}, True),
    ({"initial_commission_cents": 694}, True),
    ({"referral_required": True}, False),
    ({"note": "commission"}, False),
    ([1, "x", None], False),
    ("scalar", False),
]


@pytest.mark.parametrize("document,flagged", GUARD_CASES)
def test_guard_matches_the_database_rule(document, flagged):
    assert bool(commercial_keys(document)) is flagged


def base(**overrides):
    values = dict(purpose="published_term_comparison", state="available",
                  inputs={"priority_order": ["monthly_premium"], "zip": "34102"},
                  evidence_versions={"catalog": "r13"}, method_version="plans-method-v1",
                  policy_version="policy-v1", candidate_ids=["H1036-217-000", "H1032-198-000"],
                  ordered_ids=["H1032-198-000", "H1036-217-000"], reason_codes=["PUBLISHED_TERMS_ONLY"])
    values.update(overrides)
    return build_decision_record(**values)


def test_record_hashes_inputs_canonically():
    record = base()
    assert record["inputs_sha256"] == canonical_sha256({"zip": "34102", "priority_order": ["monthly_premium"]})


def test_commercial_inputs_are_refused_with_their_path():
    with pytest.raises(CommercialContextError, match=r"inputs\.plans\[0\]\.payout"):
        base(inputs={"plans": [{"id": "H1", "payout": 694}]})


def test_commercial_holds_are_refused():
    with pytest.raises(CommercialContextError):
        base(holds=[{"reason": "x", "carrier_appointment": "pending"}])


def test_ordered_ids_must_be_candidates():
    with pytest.raises(ValueError):
        base(ordered_ids=["H9999-999-999"])


def test_unknown_purpose_or_state_is_refused():
    with pytest.raises(ValueError):
        base(purpose="highest_commission")
    with pytest.raises(ValueError):
        base(state="sold")


def test_checklist_receipt_names_every_item():
    record = base(checklist_coverage={"formulary_coverage": {"covered": True, "turn": 4}})
    assert list(record["checklist_coverage"]) == list(CHECKLIST_ITEMS)
    assert record["checklist_coverage"]["formulary_coverage"]["covered"] is True
    assert record["checklist_coverage"]["right_to_cancel"] == {"covered": False}
    with pytest.raises(ValueError):
        base(checklist_coverage={"best_commission": {"covered": True}})


def test_substantive_result_excludes_identity_and_time():
    first, second = base(), base()
    assert first["decision_id"] != second["decision_id"]
    assert substantive_result(first) == substantive_result(second)
