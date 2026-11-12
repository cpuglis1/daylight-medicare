#!/usr/bin/env python3
"""Decide whether a pull request needs the full advisor test suite.

The suite takes about 13 minutes. It is skipped only when every changed file
is on a short list known not to affect it; anything else, including this
script and the workflow that calls it, runs the full suite.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

# Advisor code and tests read files under these roots, so Markdown there counts.
CODE_ROOTS = ("alternatives/", "infrastructure/", "cms-slice/", "tools/")
IRRELEVANT_FILES = {
    ".github/dependabot.yml",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/auto-merge.yml",
    ".github/workflows/dependency-security.yml",
}


def needed(paths: list[str]) -> bool:
    if not paths:
        return True  # an unknown or empty diff is never a reason to skip
    for path in paths:
        if path in IRRELEVANT_FILES:
            continue
        if path.endswith(".md") and not path.startswith(CODE_ROOTS):
            continue
        return True
    return False


def changed(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", "--no-renames", base, "HEAD"],
                         check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Base commit; omit to always run the suite.")
    args = parser.parse_args()
    paths = changed(args.base) if args.base else []
    result = needed(paths)
    print(f"advisor tests needed: {str(result).lower()} ({len(paths)} changed files)")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"needed={str(result).lower()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
