#!/usr/bin/env python3
"""Run the public advisor suite with fictional inputs and loopback HTTP only.

The accepted-reference replay module requires the separately governed source
archive. It is listed explicitly, never replaced by invented acceptance data.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

PRIVATE_TESTS = {
    "test_published_reference": "Requires exact accepted r4 evidence, original verifier and external review receipt from the private research archive.",
    "test_unified_demo": "Requires the private Collier pilot database (not in Git). Run it locally after the README quick start.",
    "test_comparison_http": "Its experiment check reads the CMS MPF benefit workbook under docs/data/, which is not in Git.",
}
KNOWN_FAILURES = "alternatives/advisor-first/tests/known-failures.json"


def test_name(test) -> str:
    """Stable id: module.Class.method, or 'setUpClass (module.Class)'."""
    test = getattr(test, "test_case", test)  # subTest failures
    if isinstance(test, unittest.TestCase):
        return test.id()
    return str(getattr(test, "description", test))


def worker(root: Path) -> int:
    def network_guard(event, args):
        if event == "socket.getaddrinfo":
            if args[0] not in {"localhost", "127.0.0.1", "::1", None}:
                raise PermissionError("PUBLIC_TEST_EXTERNAL_NETWORK_DENIED")
        elif event in {"socket.connect", "socket.bind"}:
            address = args[1]
            if not isinstance(address, tuple) or address[0] not in {"localhost", "127.0.0.1", "::1"}:
                raise PermissionError("PUBLIC_TEST_EXTERNAL_NETWORK_DENIED")
    sys.addaudithook(network_guard)
    tests = root / "alternatives/advisor-first/tests"
    sys.path.insert(0, str(tests))
    sys.path.insert(0, str(tests.parent))
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    modules = []
    for path in sorted(tests.glob("test_*.py")):
        if path.stem in PRIVATE_TESTS:
            continue
        modules.append(path.stem)
        suite.addTests(loader.loadTestsFromName(path.stem))
    if not modules or loader.errors:
        # Loader failures remain in the suite so unittest renders their details.
        if not modules:
            raise ValueError("PUBLIC_TEST_SUITE_MISSING")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # Known failures still run and are reported on every run. Only failures
    # outside the reviewed list fail the check; the list is not acceptance.
    known = json.loads((root / KNOWN_FAILURES).read_text())["tests"]
    failed = {test_name(test) for test, _ in result.failures + result.errors}
    unexpected = sorted(failed - set(known))
    summary = {"schema": "daylight-advisor-checks/v2",
        "passed": not unexpected and bool(result.testsRun),
        "unexpected_failures": unexpected,
        "known_failures_still_failing": sorted(failed & set(known)),
        "known_failures_now_passing": sorted(set(known) - failed),
        "python_tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped_cases": len(result.skipped),
        "public_test_modules": len(modules), "private_modules_not_run": PRIVATE_TESTS,
        "external_python_network": "denied", "provider_credentials_inherited": False,
        "source_acceptance_changed": False}
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.worker:
        return worker(root)
    # Do not inherit a real API key, database DSN, service token or model config.
    environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TMPDIR", "TEMP", "TMP") if key in os.environ}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    completed = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
                               cwd=root, env=environment)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
