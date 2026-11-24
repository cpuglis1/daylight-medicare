"""Validate the committed diagnostic calibration corpus offline.

The split is part of the corpus, so the validator never samples or rewrites
fixtures. Evidence must resolve to exact text in the owner-accepted rule file.
"""

from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


CASE_DIR = Path(__file__).resolve().parent / "cases"
ROOT = CASE_DIR.parents[2]
RULE_PATH = "alternatives/advisor-first/pilot-rules.json"
JUDGES = {
    "tool_use", "question_timing", "unsupported_inferences",
    "conversational_continuity", "medicare_factual_support", "required_coverage",
}
TEXT_FIELDS = {
    "id", "judge", "scenario_family", "split", "journey", "context",
    "user_prompt", "expected_behavior", "sample_reply", "reference_label",
    "reference_reason",
}


def require(condition, message):
    """Raise ValueError with a fixture location if an invariant fails.

    Args:
        condition: The invariant evaluated by the caller.
        message: A concise description including the failing location.
    """
    if not condition:
        raise ValueError(message)


def validate_records(items, fields, location):
    """Require a list of records with exactly the stated nonempty string fields.

    Args:
        items: The decoded JSON field.
        fields: The accepted names in each record.
        location: The fixture location for error messages.
    """
    require(isinstance(items, list), f"{location} must be a list")
    for record in items:
        require(isinstance(record, dict) and record.keys() == fields
                and all(isinstance(value, str) and value.strip() for value in record.values()),
                f"{location} contains an invalid record")


def validate_case(case, judge, location, accepted):
    """Check judge binding, schema, and exact source matches for one case.

    Args:
        case: The decoded case record.
        judge: The judge expected from the filename.
        location: The line location for error messages.
        accepted: Owner-accepted rule text keyed by case evidence reference.
    """
    require(isinstance(case, dict) and case.keys() == TEXT_FIELDS | {"evidence", "tool_trace"},
            f"{location} has unexpected or missing fields")
    for field in TEXT_FIELDS:
        require(isinstance(case[field], str) and case[field].strip(),
                f"{location} requires nonempty {field}")
    require(case["judge"] == judge, f"{location} targets a different judge")
    require(case["split"] in {"training", "heldout"}, f"{location} has an invalid split")
    require(case["journey"] in {"self_service", "caregiver"}, f"{location} has an invalid journey")
    require(case["reference_label"] in {"pass", "fail"}, f"{location} has an invalid label")
    validate_records(case["evidence"], {"source", "scope", "excerpt"}, f"{location} evidence")
    validate_records(case["tool_trace"], {"tool", "status", "detail"}, f"{location} tool trace")
    for evidence in case["evidence"]:
        require(accepted.get(evidence["source"]) == evidence["excerpt"],
                f"{location} evidence does not match an accepted rule")
    if judge == "medicare_factual_support" and case["reference_label"] == "pass":
        require(case["evidence"], f"{location} factual pass is missing accepted evidence")


def validate_corpus():
    """Check the six files, label balance, unique IDs, and split isolation.

    Returns:
        A count of validated cases and a count of self-service cases.
    """
    store = json.loads((ROOT / RULE_PATH).read_text(encoding="utf-8"))
    require(store["review_state"] == "owner_accepted_2026-11-08",
            "Expected owner-accepted pilot rules")
    accepted = {f"{RULE_PATH}#{fact['id']}": fact["text"] for fact in store["facts"]}
    files = sorted(CASE_DIR.glob("*.jsonl"))
    require({path.stem for path in files} == JUDGES, "Unexpected set of judge files")
    seen_ids = set()
    seen_inputs = set()
    self_service = 0
    for path in files:
        family_splits = defaultdict(set)
        family_sizes = Counter()
        splits = Counter()
        caregivers = Counter()
        labels = Counter()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            location = f"{path.name}:{line_no}"
            case = json.loads(line)
            validate_case(case, path.stem, location, accepted)
            identifier = case["id"]
            require(identifier not in seen_ids, f"{location} has a duplicate ID")
            seen_ids.add(identifier)
            inputs = (case["context"], case["user_prompt"])
            require(inputs not in seen_inputs, f"{location} repeats another case's inputs")
            seen_inputs.add(inputs)
            split = case["split"]
            splits[split] += 1
            caregivers[split] += case["journey"] == "caregiver"
            labels[split, case["reference_label"]] += 1
            family = case["scenario_family"]
            family_splits[family].add(split)
            family_sizes[family] += 1
            self_service += case["journey"] == "self_service"
        require(splits == {"training": 50, "heldout": 30}, f"{path.name} has incorrect split sizes")
        require(len(family_sizes) == 16 and set(family_sizes.values()) == {5},
                f"{path.name} has incorrect scenario-family sizes")
        require(all(len(value) == 1 for value in family_splits.values()),
                f"{path.name} leaks a scenario family across splits")
        require(sum(caregivers.values()) == 8 and min(caregivers.values()) > 0,
                f"{path.name} needs eight caregiver cases across both splits")
        require(len(labels) == 4, f"{path.name} needs both labels in each split")
    require(0.85 <= self_service / len(seen_ids) <= 0.95,
            "Expected roughly 90% self-service cases")
    return len(seen_ids), self_service


if __name__ == "__main__":
    try:
        total, self_service = validate_corpus()
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(str(error))
    print(f"Validated {total} fictional turns, including {self_service} self-service turns")
