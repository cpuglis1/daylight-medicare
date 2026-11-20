#!/usr/bin/env python3
"""Validate the plan-path profiles offline; never calls the advisor or a model.

Run from the repo root with the existing environment:
  infrastructure/daylight-data/.venv/bin/python \
    docs/evaluations/plan-paths-2026-11-12/validate.py

Requires jsonschema with Draft 2020-12 support. An optional positional argument
selects another profiles file; the adjacent schema remains the contract.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
AS_OF = "2026-11-12"
EXPECTED_IDS = [f"PP{number:02}" for number in range(1, 17)]
PATHS = {"medicare_advantage", "original_medicare_medigap_part_d", "part_d_only", "keep_current_or_wait", "undecided"}
TEACH_BACK_PREFIX = "Unprompted, as the very last message"
IDENTIFIER = re.compile(
    r"\b(?:[0-9][A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{4}|[0-9]{3}-[0-9]{2}-[0-9]{4})\b"
)
EXPECTED_IDENTIFIERS = {"PP06": ["0EG4-TE5-MK72"]}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def read_json(path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def validate(data, schema):
    Draft202012Validator.check_schema(schema)
    errors = [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(data)
    ]
    if errors:
        return errors, {}

    def require(condition, message):
        if not condition:
            errors.append(message)

    require([item["id"] for item in data] == EXPECTED_IDS, "IDs must be ordered PP01–PP16.")
    as_of = date.fromisoformat(AS_OF)
    short_openings, long_openings, identifiers, details = [], [], {}, []
    paths = Counter()
    check_counts = Counter()
    misconceptions = 0
    for item in data:
        pid = item["id"]
        truth = item["ground_truth"]
        outcome = item["expected_outcome"]
        script = item["response_script"]
        teach_back = item["understanding"]["teach_back"]

        words = len(item["opening_message"].split())
        if words < 15:
            short_openings.append(pid)
        if words > 80:
            long_openings.append(pid)

        require(truth["as_of_date"] == AS_OF, f"{pid}: as_of_date must be {AS_OF}.")
        require(truth["plan_year"] == 2026, f"{pid}: plan_year must be 2026 (pilot data).")
        for field in ("household_and_work", "current_coverage", "finances", "sex_category", "tobacco"):
            require(isinstance(truth.get(field), str) and truth[field].strip(), f"{pid}: missing {field}.")
        for field in ("medicines", "doctors"):
            values = truth.get(field)
            require(isinstance(values, list) and values and all(isinstance(v, str) and v.strip() for v in values),
                    f"{pid}: missing or malformed {field}.")

        try:
            born = date.fromisoformat(truth["date_of_birth"])
            age = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
            require(item["person"]["age"] == age, f"{pid}: age disagrees with date of birth.")
            medicare = truth["medicare"]
            require(isinstance(medicare, dict), f"{pid}: medicare must be an object.")
            for field in ("part_a_start_date", "part_b_start_date"):
                require(field in medicare, f"{pid}: missing medicare.{field}.")
            for field, value in medicare.items():
                if field.endswith("_date") and value is not None:
                    effective = date.fromisoformat(value)
                    require(born <= effective <= as_of + timedelta(days=60),
                            f"{pid}: {field} is outside the allowed range (birth to two months after as_of).")
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{pid}: invalid birth or Medicare dates: {error}")

        pushes = sum(entry["if_asked_about"].startswith("Unprompted,") for entry in script)
        require(script[-1]["if_asked_about"].startswith(TEACH_BACK_PREFIX),
                f"{pid}: the last scripted message must be the teach-back.")
        require(script[-1]["reply"] == teach_back["message"],
                f"{pid}: understanding.teach_back.message must equal the last scripted reply.")
        misconceptions += bool(teach_back["contains_misconception"])

        require(outcome["coverage_path"] in PATHS, f"{pid}: unknown coverage_path.")
        paths[outcome["coverage_path"]] += 1
        tabs = outcome["tabs"]
        if tabs["medigap"]["expected"] in ("unlocks", "optional"):
            require(64 <= item["person"]["age"] <= 74, f"{pid}: Medigap tab expected but age is outside pilot pricing.")
        require(any(tab["expected"] in ("unlocks", "shows_message") for tab in tabs.values())
                or outcome["coverage_path"] in {"keep_current_or_wait", "undecided"},
                f"{pid}: a plan path needs at least one tab that unlocks or shows a message.")

        sentences = [part for part in re.split(r"(?<=[.!?])\s+", item["grading_notes"].strip()) if part]
        require(len(sentences) <= 2, f"{pid}: grading_notes exceeds two sentences.")

        typed = "\n".join([item["opening_message"]] + [entry["reply"] for entry in script])
        found = sorted(set(IDENTIFIER.findall(typed)))
        if found:
            identifiers[pid] = found
            require(all(value in truth.get("synthetic_identifier", "") for value in found),
                    f"{pid}: identifier probe lacks its fictional ground-truth explanation.")

        checks = item["checks"]
        real_doctors = fictional_doctors = meds_with_rxcui = 0
        has_pharmacy = False
        if checks:
            for doc in checks["doctors"]:
                if doc["real"]:
                    real_doctors += 1
                    require(doc["identity"]["npi"] is not None and doc["sites_on_file"],
                            f"{pid}: real doctor {doc['identity']['name']} needs an NPI and at least one site on file.")
                else:
                    fictional_doctors += 1
                    require(doc["identity"]["npi"] is None, f"{pid}: a fictional doctor must not carry an NPI.")
            if checks["pharmacy"]:
                has_pharmacy = True
            meds_with_rxcui = sum(m["product"]["rxcui"] is not None for m in checks["medicines"])
            require(checks["doctors"] or checks["pharmacy"] or checks["medicines"], f"{pid}: checks is empty; use null instead.")
        for tab_name in ("medicare_advantage", "medigap", "part_d", "coverage_path"):
            require(item["expected_sorting"][tab_name].strip(), f"{pid}: expected_sorting.{tab_name} is empty.")
        check_counts["real_doctor_profiles"] += real_doctors > 0
        check_counts["negative_control_profiles"] += fictional_doctors > 0
        check_counts["pharmacy_profiles"] += has_pharmacy
        check_counts["medicine_profiles"] += meds_with_rxcui > 0
        check_counts["profiles_with_any_real_check"] += (real_doctors > 0 or has_pharmacy or meds_with_rxcui > 0)
        details.append({
            "id": pid,
            "coverage_path": outcome["coverage_path"],
            "tabs": {name: tab["expected"] for name, tab in tabs.items()},
            "typist": item["person"]["relationship_to_typist"],
            "opening_words": words,
            "scripted_messages": len(script),
            "unprompted_messages": pushes,
            "teach_back_misconception": teach_back["contains_misconception"],
            "real_doctors": real_doctors,
            "negative_control_doctors": fictional_doctors,
            "pharmacy": has_pharmacy,
            "medicines_with_rxcui": meds_with_rxcui,
        })

    require(set(paths) == PATHS, "Every coverage path must appear at least once.")
    require(len(short_openings) >= 2, "At least two openings must have fewer than 15 words.")
    require(len(long_openings) >= 1, "At least one opening must have more than 80 words.")
    require(check_counts["profiles_with_any_real_check"] >= 8, "At least eight profiles must run real-data checks.")
    require(check_counts["real_doctor_profiles"] >= 5, "At least five profiles must check a real doctor.")
    require(check_counts["medicine_profiles"] >= 6, "At least six profiles must check medicines with RxCUIs.")
    require(check_counts["pharmacy_profiles"] >= 5, "At least five profiles must check a real pharmacy.")
    require(check_counts["negative_control_profiles"] >= 2, "At least two fictional doctors must serve as negative controls.")
    require(1 <= misconceptions <= 15, "Teach-backs must mix misconceptions with correct summaries.")
    require(identifiers == EXPECTED_IDENTIFIERS, "Only PP06 types its designated invalid identifier probe.")
    require(any(item["person"]["relationship_to_typist"] != "self" for item in data),
            "At least one profile must be typed by a helper.")
    return errors, {
        "profiles": len(data),
        "coverage_paths": dict(sorted(paths.items())),
        "distinct_zips": sorted({item["person"]["zip"] for item in data}),
        "ages": sorted(item["person"]["age"] for item in data),
        "short_openings": short_openings,
        "long_openings": long_openings,
        "teach_backs_with_misconception": misconceptions,
        "checks": dict(check_counts),
        "identifier_probe_profiles": sorted(identifiers),
        "per_profile": details,
    }


def main():
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "profiles.json"
    try:
        data = read_json(path)
        schema_path = HERE / "profiles.schema.json"
        schema = read_json(schema_path)
        errors, measurements = validate(data, schema)
        report = {
            "status": "passed" if not errors else "failed",
            "data_file": path.name,
            "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
            "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "jsonschema_version": version("jsonschema"),
            "errors": errors,
            "measurements": measurements,
            "scope": "Offline structure and corpus checks only. No advisor conversations, model calls or paid probes.",
        }
    except (OSError, ValueError) as error:
        report = {"status": "failed", "errors": [str(error)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
