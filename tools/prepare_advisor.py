#!/usr/bin/env python3
"""Materialize reviewed development dependencies without changing authority.

No network, model, database, credentials, guest records or source evidence is
accessed. The original profile contract and its exact source hash stay intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE = "infrastructure/daylight-data/config/integration-review-catalog.2026.json"
TARGET = "docs/data/integration-review-2026-10-29/review-catalog.json"
DIGEST = "1585b420d137456a3aa2c1dc83d76c4a6794a29fe2485aa1c8e74ac879b29ba9"
JOURNEY_SOURCE = "alternatives/advisor-first/tests/fixtures/conversation_journey_spec.json"
JOURNEY_TARGET = "audit-evidence/advisor-conversation-quality-20261102/journey-spec.json"
JOURNEY_DIGEST = "d7877739311401ad870cb6f7d6359348c8988c741fa52b922dbd3ee020c103b9"
EVALUATOR_SOURCE = "alternatives/advisor-first/tests/journey_evaluator.py"
EVALUATOR_TARGET = "audit-evidence/advisor-conversation-quality-20261102/evaluate_journey.py"
EVALUATOR_DIGEST = "937dd564ac475cfb8272b35b80fb7d92ad17bce78a60933d49ee5c14cd0c7faf"


def checked_path(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("METADATA_SYMLINK_REJECTED")
    return current


def materialize(root: Path, relative: str, raw: bytes, digest: str) -> dict:
    target = checked_path(root, relative)
    created = False
    if target.exists():
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("EXISTING_METADATA_DIFFERS_NOT_OVERWRITTEN")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target = checked_path(root, relative)
        # Exclusive creation preserves another process's file. A concurrent
        # identical preparation can simply be retried without replacing it.
        with target.open("xb") as stream:
            stream.write(raw)
        created = True
    return {"created": created, "path": relative, "sha256": digest}


def prepare(root: Path) -> dict:
    root = root.resolve(strict=True)
    raw = checked_path(root, SOURCE).read_bytes()
    journey = checked_path(root, JOURNEY_SOURCE).read_bytes()
    evaluator = checked_path(root, EVALUATOR_SOURCE).read_bytes()
    if (hashlib.sha256(raw).hexdigest() != DIGEST
            or hashlib.sha256(journey).hexdigest() != JOURNEY_DIGEST
            or hashlib.sha256(evaluator).hexdigest() != EVALUATOR_DIGEST):
        raise ValueError("REVIEWED_METADATA_DIGEST_MISMATCH")
    document = json.loads(raw)
    metadata = document["metadata"]
    if (metadata["catalog_kind"] != "review_metadata_and_integration_proposal"
            or metadata["consumer_release"] is not False
            or metadata["personal_recommendations_enabled"] is not False
            or json.loads(journey)["fictional"] is not True):
        raise ValueError("METADATA_AUTHORITY_MISMATCH")
    # Validate all destinations before creating any file.
    for relative, digest in [(TARGET, DIGEST), (JOURNEY_TARGET, JOURNEY_DIGEST),
                             (EVALUATOR_TARGET, EVALUATOR_DIGEST)]:
        target = checked_path(root, relative)
        if target.exists() and (not target.is_file()
                or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
            raise ValueError("EXISTING_METADATA_DIFFERS_NOT_OVERWRITTEN")
    files = [materialize(root, TARGET, raw, DIGEST),
             materialize(root, JOURNEY_TARGET, journey, JOURNEY_DIGEST),
             materialize(root, EVALUATOR_TARGET, evaluator, EVALUATOR_DIGEST)]
    return {"schema": "daylight-advisor-prepare/v1", "created": any(f["created"] for f in files),
            "files": files, "consumer_release": False,
            "source_acceptance_changed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = prepare(args.root)
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"passed": False, "error": "METADATA_PREPARATION_FAILED"}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
