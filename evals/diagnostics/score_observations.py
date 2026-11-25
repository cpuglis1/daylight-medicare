"""Score observed Daylight turns against their exact fictional case definitions.

The subscription judge sees the recorded action and output, including the visible
follow-up question. Authored sample replies and mock tool results stay private
to calibration. A missing trace, version mismatch or failed judge leaves a case
unscored. The report records validation coverage across all six suites.
"""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/evaluation"))
from calibrate_turns import SUITES, grade, subscription_available


def load_cases():
    """Index the original UTF-8 case bytes so a changed case cannot score an earlier trial."""
    cases = {}
    for suite in SUITES:
        for line in (ROOT / "evals/diagnostics/cases" / (suite + ".jsonl")).read_bytes().splitlines():
            case = json.loads(line)
            cases[case["id"]] = (case, hashlib.sha256(line).hexdigest())
    return cases


def score_trial(row, case, version, grader=grade):
    """Grade one observed trial; return an unscored result if required evidence is unavailable."""
    trace = row.get("trace")
    if (row.get("rawLineHash") != version or row.get("status") != "observed"
            or not isinstance(trace, dict) or trace.get("message") != case["user_prompt"]
            or not isinstance(row.get("reply"), str) or not isinstance(trace.get("toolCalls"), list)):
        return {"verdict": "unscored", "reason": "Missing or mismatched live observation"}
    target = {key: case[key] for key in ("context", "user_prompt", "expected_behavior", "evidence")}
    target["sample_reply"] = json.dumps({"reply": row["reply"], "serverFollowupCandidate": row.get("nextQuestion"),
                                         "advisorSources": trace.get("advisorSources"), "factsSaved": trace.get("factsSaved"),
                                         "profileChecks": trace.get("profileChecks"),
                                         "caseStateCheck": trace.get("caseStateCheck")}, ensure_ascii=False)
    # A reference excerpt defines correctness. Only observed runtime evidence establishes
    # that Daylight actually obtained support when answering the visitor.
    first_inputs = [c.get("request", {}).get("input") for c in trace.get("modelCalls", [])
                    if c.get("kind") == "compose"]
    supplied = []
    for request_inputs in first_inputs:
        for entry in request_inputs if isinstance(request_inputs, list) else []:
            if not isinstance(entry, dict):
                continue
            content = entry.get("content")
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except ValueError:
                continue
            if isinstance(payload, dict) and payload.get("sources_supplied_by_code"):
                supplied.append(payload["sources_supplied_by_code"])
            if isinstance(payload, dict):
                resolved = payload.get("resolved_context", {})
                if isinstance(resolved, dict) and resolved.get("evidence"):
                    supplied.append(resolved["evidence"])
    target["tool_trace"] = {"observedToolCalls": trace["toolCalls"], "codeSuppliedSources": supplied}
    if case.get("judge") == "medicare_factual_support":
        target["expected_behavior"] += (" The reference excerpts describe the correct rule. Verify grounding "
                                        "from actual tool responses or code-supplied source text for this turn.")
    verdict = grader(target)
    return {key: verdict[key] for key in ("verdict", "reason", "model", "confidence")}


def main():
    """Score a private run artifact and publish a new report without replacing past scores."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    if not subscription_available():
        parser.error("Use the configured subscription judge without API-key overrides")
    auth = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=15)
    try:
        status = json.loads(auth.stdout)
    except ValueError:
        status = {}
    if not status.get("loggedIn") or not status.get("subscriptionType"):
        parser.error("Sign in to the local Claude subscription before running the judges")
    folder = ROOT / "alternatives/advisor-first/var/eval-diagnostics"
    path = args.artifact.absolute()
    if (path.parent.resolve() != folder.resolve() or not re.fullmatch(r"live-observation-[a-f0-9-]{36}\.json", path.name)):
        parser.error("Supply an artifact from the private diagnostic runner directory")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 160_000_000:
            parser.error("Runner artifacts must be private bounded regular files owned by the operator")
        raw = file.read(160_000_001)
    run = json.loads(raw)
    if path.name != "live-observation-" + run.get("runId", "") + ".json":
        parser.error("Run identity does not match its artifact")
    if run.get("kind") != "live_turn_observations":
        parser.error("Supply a Daylight live observation artifact")
    cases = load_cases()
    scores = []
    for row in run["trials"]:
        case, version = cases[row["caseId"]]
        scores.append({"caseId": case["id"], "suite": case["judge"], "split": case["split"],
                       "trial": row["trial"], **score_trial(row, case, version)})
    report = {"kind": "live_turn_scores", "runId": run["runId"], "identity": run["identity"],
              "sourceHash": hashlib.sha256(raw).hexdigest(), "scores": scores}
    with tempfile.NamedTemporaryFile("w", dir=args.artifact.parent, suffix=".partial", delete=False) as out:
        json.dump(report, out, allow_nan=False)
    path = Path(out.name).with_suffix(".scores.json")
    os.replace(out.name, path)
    print(path)
    return int(any(score["verdict"] not in ("pass", "fail") for score in scores))


if __name__ == "__main__":
    raise SystemExit(main())
