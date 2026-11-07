#!/usr/bin/env python3
"""Audit explicit pinned inventories without installing or executing project code.

Only public package names/versions are queried. This is not an audit of an
installed production image, the archived prototype, or unlisted optional extras.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)")
HASH = re.compile(r"--hash=sha256:[a-f0-9]{64}")
TARGETS = {
    "research": "infrastructure/daylight-data/requirements.lock",
    "audit-tools": "tools/security/requirements.lock",
}


def pinned_inventory(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Missing or unsafe dependency inventory")
    pins = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip().removesuffix("\\").strip()
        if not line or HASH.fullmatch(line):
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ValueError("Inventory must contain exact package pins and SHA-256 hashes only")
        name, version = match.groups()
        name = re.sub(r"[-_.]+", "-", name.lower())
        if name in pins:
            raise ValueError("Duplicate dependency pin")
        pins[name] = version
    if not pins:
        raise ValueError("Empty dependency inventory")
    return pins


def audit(root, output):
    output.mkdir(parents=True, exist_ok=True)
    targets = dict(TARGETS)
    plan_types = "infrastructure/daylight-data/src/daylight_data/plan_types/runtime-requirements.lock"
    if (root / plan_types).exists():
        targets["plan-types"] = plan_types
    summary = {"schema": "daylight-dependency-audit/v1", "observed_at": datetime.now(timezone.utc).isoformat(),
               "scope": "explicit pinned inventories, not the production image or arbitrary optional extras",
               "project_packages_installed": False, "results": [], "passed": False}
    try:
        # Validate everything before any network lookup. No requirement URLs,
        # include directives, VCS references or install commands are accepted.
        inventories = {name: pinned_inventory(root / rel) for name, rel in targets.items()}
        expected_tools = pinned_inventory(root / "tools/security/requirements.txt")
        if any(inventories["audit-tools"].get(k) != v for k, v in expected_tools.items()):
            raise ValueError("Audit tooling input and lock disagree; refresh and review the lock")
        for name, rel in targets.items():
            row = {"name": name, "path": rel, "packages": len(inventories[name]),
                   "sha256": hashlib.sha256((root / rel).read_bytes()).hexdigest(), "exit_codes": {}}
            summary["results"].append(row)
            for format_name, suffix in (("json", "audit.json"), ("cyclonedx-json", "cdx.json")):
                report = output / f"{name}.{suffix}"
                report.unlink(missing_ok=True)  # Never mistake an older report for this run.
                result = subprocess.run([
                    sys.executable, "-m", "pip_audit", "--strict", "--disable-pip", "--no-deps",
                    "--progress-spinner", "off", "--timeout", "20", "-r", str(root / rel),
                    "--format", format_name, "--output", str(report),
                ], timeout=240, capture_output=True, text=True)
                row["exit_codes"][format_name] = result.returncode
                if result.returncode or not report.is_file():
                    # Full findings stay in package-only reports; never print
                    # arbitrary subprocess content to CI or conversation logs.
                    print(f"{name} {format_name}: failed; inspect the package report and service availability")
                else:
                    print(f"{name} {format_name}: {row['packages']} pinned packages checked")
        summary["passed"] = all(row["exit_codes"] == {"json": 0, "cyclonedx-json": 0}
                                and all((output / f"{row['name']}.{suffix}").is_file()
                                        for suffix in ("audit.json", "cdx.json"))
                                for row in summary["results"])
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        summary["error"] = str(error) if isinstance(error, ValueError) else type(error).__name__
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return audit(args.root.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
