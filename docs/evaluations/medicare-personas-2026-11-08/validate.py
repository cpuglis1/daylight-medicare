#!/usr/bin/env python3
"""Validate the saved fictional corpus offline; never call the guidance tool.

Run from the project root using the existing environment:
  infrastructure/daylight-data/.venv/bin/python \
    docs/evaluations/medicare-personas-2026-11-08/validate.py

Requires jsonschema with Draft 2020-12 support. An optional positional argument
selects another corpus file; the adjacent schema remains the contract.
"""

import hashlib
import json
import re
import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
EXPECTED_IDS = [f"P{number:02}" for number in range(1, 21)]
IDENTIFIER = re.compile(
    r"\b(?:[0-9][A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{4}|"
    r"[0-9]{3}-[0-9]{2}-[0-9]{4})\b"
)
EXPECTED_IDENTIFIERS = {
    "P09": ["0EG4-TE5-MK72"],
    "P16": ["000-42-7816"],
}


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

    require([item["id"] for item in data] == EXPECTED_IDS, "IDs must be ordered P01–P20.")
    short_openings = []
    long_openings = []
    identifiers = {}
    details = []
    for item in data:
        pid = item["id"]
        truth = item["ground_truth"]
        words = len(item["opening_message"].split())
        if words < 15:
            short_openings.append(pid)
        if words > 80:
            long_openings.append(pid)
        pushes = sum(
            entry["if_asked_about"].startswith("Unprompted,")
            for entry in item["response_script"]
        )
        sentences = [
            part for part in re.split(r"(?<=[.!?])\s+", item["grading_notes"].strip())
            if part
        ]
        require(len(sentences) <= 2, f"{pid}: grading_notes exceeds two sentences.")
        require(truth.get("as_of_date") == "2026-11-08", f"{pid}: wrong evaluation date.")
        require(truth.get("plan_year") == 2026, f"{pid}: wrong plan year.")
        for field in ("household_and_work", "current_coverage", "finances"):
            require(isinstance(truth.get(field), str) and bool(truth[field].strip()),
                    f"{pid}: missing {field} facts.")
        for field in ("medicines", "doctors"):
            values = truth.get(field)
            require(isinstance(values, list) and bool(values)
                    and all(isinstance(value, str) and value.strip() for value in values),
                    f"{pid}: missing or malformed {field} facts.")
        try:
            born = date.fromisoformat(truth["date_of_birth"])
            as_of = date.fromisoformat(truth["as_of_date"])
            age = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
            require(item["person"]["age"] == age, f"{pid}: age disagrees with birth date.")
            medicare = truth["medicare"]
            require(isinstance(medicare, dict), f"{pid}: missing Medicare facts.")
            if isinstance(medicare, dict):
                for field in ("part_a_start_date", "part_b_start_date"):
                    require(field in medicare, f"{pid}: missing {field}.")
                for field, value in medicare.items():
                    if field.endswith("_date") and value is not None:
                        effective = date.fromisoformat(value)
                        require(born <= effective <= as_of,
                                f"{pid}: {field} is outside the historical date range.")
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{pid}: invalid birth or Medicare date facts: {error}")
        typed_text = "\n".join(
            [item["opening_message"]] + [entry["reply"] for entry in item["response_script"]]
        )
        found = sorted(set(IDENTIFIER.findall(typed_text)))
        if found:
            identifiers[pid] = found
            require(all(value in truth.get("synthetic_identifier", "") for value in found),
                    f"{pid}: identifier probe lacks its fictional ground-truth explanation.")
        details.append({
            "id": pid,
            "opening_words": words,
            "response_script_items": len(item["response_script"]),
            "unprompted_pushes": pushes,
            "must_cover_items": len(item["answer_key"]["must_cover"]),
            "must_not_claim_items": len(item["answer_key"]["must_not_claim"]),
            "grading_notes_sentences": len(sentences),
        })
    require(len(short_openings) >= 4, "At least four openings must have fewer than 15 words.")
    require(len(long_openings) >= 3, "At least three openings must have more than 80 words.")
    require(identifiers == EXPECTED_IDENTIFIERS,
            "Exactly P09 and P16 must type their designated invalid identifier probes.")
    return errors, {
        "personas": len(data),
        "distinct_allowed_zips": len({item["person"]["zip"] for item in data}),
        "short_openings": short_openings,
        "long_openings": long_openings,
        "identifier_probe_personas": sorted(identifiers),
        "per_persona": details,
    }


def main():
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "personas.json"
    try:
        data = read_json(path)
        schema_path = HERE / "personas.schema.json"
        schema = read_json(schema_path)
        errors, measurements = validate(data, schema)
        report = {
            "status": "passed" if not errors else "failed",
            "data_file": path.name,
            "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "schema_file": schema_path.name,
            "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
            "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "jsonschema_version": version("jsonschema"),
            "command": "infrastructure/daylight-data/.venv/bin/python docs/evaluations/medicare-personas-2026-11-08/validate.py",
            "errors": errors,
            "measurements": measurements,
            "scope": "Offline JSON Schema and corpus-constraint validation only; no tool conversations or paid probes were run.",
            "save_correction": "Removed the duplicate P01 answer_key.grading_notes property; the required top-level grading_notes and every other original parsed value were preserved and compared during extraction.",
            "remaining_review": [
                "Licensed reviewer assessment of the Medicare answer keys.",
                "Semantic review of biographies, script consistency, scenario and personality coverage, and fictional names; these are not established by JSON Schema.",
                "Evaluation of actual tool responses and owner acceptance remain separate."
            ],
        }
    except (OSError, ValueError) as error:
        report = {"status": "failed", "errors": [str(error)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
