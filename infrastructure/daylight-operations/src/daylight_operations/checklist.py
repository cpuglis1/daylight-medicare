"""The CMS pre-enrollment checklist items an enrollment receipt must account for.

Source: CMS CY2026 Agent/Broker Training and Testing Guidelines; 42 CFR
422.2274(c)(12) and 423.2274(c)(12), as summarized in the brokerage plan of
November 5, 2026. Whether software coverage satisfies the "agents and brokers
discuss" standard is an open counsel question; this list only names the items.
"""

CHECKLIST_ITEMS = (
    "plan_type_and_network_providers",   # plan type; doctors, pharmacy and hospitals in network
    "formulary_coverage",
    "other_needed_benefits",
    "premiums_including_part_b",
    "cost_sharing",
    "out_of_network_rules",
    "coverage_outside_us",
    "effect_on_current_coverage",        # including Medigap
    "plan_year_changes_and_eoc",
    "how_to_file_complaints",
    "special_needs_plan_requirements",
    "right_to_cancel",
)


def coverage_score(receipt: dict) -> dict:
    """Score a decision's checklist receipt. Missing or unknown items never count as covered."""
    unknown = sorted(set(receipt) - set(CHECKLIST_ITEMS))
    covered = [item for item in CHECKLIST_ITEMS
               if isinstance(receipt.get(item), dict) and receipt[item].get("covered") is True]
    return {"covered": len(covered), "total": len(CHECKLIST_ITEMS),
            "missing": [item for item in CHECKLIST_ITEMS if item not in covered],
            "unknown_items": unknown, "complete": len(covered) == len(CHECKLIST_ITEMS) and not unknown}
