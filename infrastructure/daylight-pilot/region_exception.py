#!/usr/bin/env python3
"""Prepare/apply the owner-approved Virginia SCP exception; no credentials saved.

Run from authenticated management-account CloudShell (no --profile required).
Prepare is read-only in AWS. Apply and rollback require the saved preparation.
"""
import argparse
import copy
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess

MANAGEMENT = "717010296718"
WORKLOAD = "020055445580"
ORGANIZATION = "o-krtzzvaahd"
ROOT = "r-53ag"
POLICY = "p-nh0ejrgr"
NAME = "AdvancedModeRegionRestrictionSecurityControlPolicy"
SID = "UsEast1Partitional"
CONDITION = {"StringEquals": {"aws:RequestedRegion": "us-east-1"}}


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def desired_policy(before):
    after = copy.deepcopy(before)
    statements = [s for s in after["Statement"] if s.get("Sid") == SID]
    require(len(statements) == 1, "Expected exactly one Virginia statement.")
    statement = statements[0]
    require(statement.get("Effect") == "Deny" and "NotAction" in statement,
            "Virginia statement no longer matches the reviewed deny.")
    require(statement.get("Condition") == CONDITION,
            "Virginia conditions changed or exception already exists; inspect live policy.")
    statement["Condition"]["StringNotEquals"] = {"aws:PrincipalAccount": WORKLOAD}
    return after


class AWS:
    def __init__(self, profile=None):
        self.prefix = ["aws", "--region", "us-east-1", "--no-cli-pager", "--output", "json"]
        if profile:
            self.prefix += ["--profile", profile]

    def __call__(self, *args):
        result = subprocess.run(self.prefix + list(args), check=True, capture_output=True,
                                text=True, timeout=90)
        return json.loads(result.stdout)


def inspect(aws):
    require(aws("sts", "get-caller-identity")["Account"] == MANAGEMENT,
            "Wrong account: this operation requires the verified management account.")
    org = aws("organizations", "describe-organization")["Organization"]
    require(org["Id"] == ORGANIZATION, "Organization changed.")
    targets = aws("organizations", "list-targets-for-policy", "--policy-id", POLICY)["Targets"]
    require([(t["TargetId"], t["Type"]) for t in targets] == [(ROOT, "ROOT")],
            "Policy attachments differ from the reviewed organization-root attachment.")
    policy = aws("organizations", "describe-policy", "--policy-id", POLICY)["Policy"]
    summary = policy["PolicySummary"]
    require(summary["Id"] == POLICY and summary["Name"] == NAME
            and summary["Type"] == "SERVICE_CONTROL_POLICY" and not summary["AwsManaged"],
            "Policy identity/type differs from the reviewed customer policy.")
    return policy


def private_write(path, value):
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def prepare(aws, directory):
    policy = inspect(aws)
    before = json.loads(policy["Content"])
    after = desired_policy(before)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    private_write(directory / "policy-backup.json", policy)
    private_write(directory / "before.json", before)
    private_write(directory / "after.json", after)
    private_write(directory / "manifest.json", {
        "policy": POLICY, "management": MANAGEMENT, "workload": WORKLOAD,
        "organization": ORGANIZATION, "root": ROOT,
        "prepared_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "before_sha256": digest(before), "after_sha256": digest(after),
        "summary_sha256": digest(policy["PolicySummary"]),
    })
    diff = "".join(difflib.unified_diff(
        json.dumps(before, indent=2).splitlines(True),
        json.dumps(after, indent=2).splitlines(True), fromfile="before", tofile="after"))
    print(diff)
    print(f"Prepared only. Private backup: {directory.resolve()}")


def apply(aws, directory, rollback=False):
    manifest = json.loads((directory / "manifest.json").read_text())
    before = json.loads((directory / "before.json").read_text())
    after = json.loads((directory / "after.json").read_text())
    require(all(manifest.get(k) == v for k, v in {
        "policy": POLICY, "management": MANAGEMENT, "workload": WORKLOAD,
        "organization": ORGANIZATION, "root": ROOT}.items()), "Preparation identity mismatch.")
    require(digest(before) == manifest["before_sha256"]
            and digest(after) == manifest["after_sha256"], "Prepared files changed.")
    require(desired_policy(before) == after, "Prepared change exceeds the approved exception.")
    expected, desired = (after, before) if rollback else (before, after)
    live = inspect(aws)
    require(digest(live["PolicySummary"]) == manifest["summary_sha256"],
            "Policy metadata changed after preparation.")
    content = json.loads(live["Content"])
    if content == desired:
        print("Already in the requested state; no write performed.")
        return
    require(content == expected, "Live policy changed after preparation; no write performed.")
    # Organizations has no ETag/conditional UpdatePolicy. Re-read immediately before
    # this single write; do not run concurrently with another policy administrator.
    aws("organizations", "update-policy", "--policy-id", POLICY, "--content", encoded(desired))
    observed = inspect(aws)
    require(json.loads(observed["Content"]) == desired
            and digest(observed["PolicySummary"]) == manifest["summary_sha256"],
            "Post-write verification failed; inspect AWS and the backup before retrying.")
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    private_write(directory / f"{'rollback' if rollback else 'apply'}-{timestamp}.json", {
        "policy": POLICY, "workload": WORKLOAD, "verified_at": timestamp,
        "sha256": digest(desired), "rollback": rollback,
    })
    print(f"Verified {'rollback' if rollback else 'exception'}: {POLICY}, workload {WORKLOAD}.")
    print("Resource access still needs verification from the workload account.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "apply", "rollback"))
    parser.add_argument("directory", type=Path, help="New preparation directory, or existing one to apply/rollback")
    parser.add_argument("--profile", help="Omit in management-account CloudShell")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(AWS(args.profile), args.directory)
        else:
            apply(AWS(args.profile), args.directory, rollback=args.action == "rollback")
    except (Refused, OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Stopped: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
