"""Test the inventory's identity guard with an offline fake CLI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("aws-inventory.sh")


class InventoryTests(unittest.TestCase):
    def run_inventory(self, actual="020055445580", expected="020055445580", profile="-", failure=""):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fake = directory / "aws"
            fake.write_text("""#!/usr/bin/env python3
import json, os, sys
with open(os.environ['INVENTORY_CALLS'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if 'get-caller-identity' in sys.argv:
    print(os.environ['INVENTORY_ACCOUNT'])
elif os.environ.get('INVENTORY_FAILURE') in sys.argv:
    sys.exit(1)
else:
    print('[]')
""")
            fake.chmod(0o700)
            calls_path = directory / "calls"
            result = subprocess.run(["sh", str(SCRIPT), profile, expected],
                                    capture_output=True, text=True, env={
                                        **os.environ, "PATH": temp + ":" + os.environ["PATH"],
                                        "INVENTORY_ACCOUNT": actual,
                                        "INVENTORY_CALLS": str(calls_path),
                                        "INVENTORY_FAILURE": failure,
                                    })
            calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
            return result, calls

    def test_cloudshell_uses_existing_identity_and_only_reads(self):
        result, calls = self.run_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(len(calls), 10)
        services = {"sts", "route53", "cloudfront", "acm", "ec2", "cloudformation",
                    "secretsmanager", "ssm", "wafv2", "budgets"}
        for call in calls:
            self.assertNotIn("--profile", call)
            service_position = next(i for i, arg in enumerate(call) if arg in services)
            self.assertTrue(call[service_position + 1].startswith(("describe-", "list-", "get-caller-identity")))
            self.assertNotIn("get-secret-value", call)

    def test_named_profile_is_retained(self):
        result, calls = self.run_inventory(profile="daylight-pilot")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(all(call[call.index("--profile") + 1] == "daylight-pilot" for call in calls))

    def test_wrong_account_stops_before_inventory(self):
        result, calls = self.run_inventory(actual="111111111111")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_management_account_is_never_workload(self):
        result, calls = self.run_inventory(actual="717010296718", expected="717010296718")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_partial_denial_returns_failure_but_finishes_other_reads(self):
        result, calls = self.run_inventory(failure="describe-instances")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("describe-budgets" in call for call in calls))


if __name__ == "__main__":
    unittest.main()
