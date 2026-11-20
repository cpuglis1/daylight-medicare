"""Offline security-boundary checks; never invokes AWS or a model."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import region_exception as region


class FakeAWS:
    def __init__(self):
        self.account = region.MANAGEMENT
        self.organization = region.ORGANIZATION
        self.targets = [{"TargetId": region.ROOT, "Type": "ROOT"}]
        self.document = {"Version": "2012-10-17", "Statement": [
            {"Sid": region.SID, "Effect": "Deny", "NotAction": ["iam:*", "sts:*"],
             "Resource": "*", "Condition": copy.deepcopy(region.CONDITION)},
            {"Sid": "UsWest2Partitional", "Effect": "Deny", "NotAction": ["iam:*"],
             "Resource": "*", "Condition": {"StringEquals": {"aws:RequestedRegion": "us-west-2"}}},
            {"Sid": "RegionFloor", "Effect": "Deny", "NotAction": ["iam:*"],
             "Resource": "*", "Condition": {"StringNotEquals": {
                 "aws:RequestedRegion": ["unspecified", "us-east-1", "us-east-2", "us-west-2"]}}},
        ]}
        self.summary = {"Id": region.POLICY, "Name": region.NAME,
                        "Type": "SERVICE_CONTROL_POLICY", "AwsManaged": False}
        self.writes = []
        self.fail_verification = False

    def __call__(self, service, operation, *args):
        if service == "sts":
            return {"Account": self.account}
        if operation == "describe-organization":
            return {"Organization": {"Id": self.organization}}
        if operation == "list-targets-for-policy":
            return {"Targets": copy.deepcopy(self.targets)}
        if operation == "describe-policy":
            return {"Policy": {"PolicySummary": copy.deepcopy(self.summary),
                               "Content": json.dumps(self.document)}}
        if operation == "update-policy":
            self.writes.append(args)
            if not self.fail_verification:
                self.document = json.loads(args[args.index("--content") + 1])
            return {}
        raise AssertionError((service, operation, args))


class RegionExceptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "preparation"
        self.aws = FakeAWS()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def prepare(self):
        region.prepare(self.aws, self.directory)

    def test_prepare_is_read_only_and_private(self):
        self.prepare()
        self.assertEqual(self.aws.writes, [])
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        for path in self.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        saved = json.loads((self.directory / "policy-backup.json").read_text())
        self.assertEqual(json.loads(saved["Content"]), self.aws.document)

    def test_only_account_condition_changes(self):
        original = copy.deepcopy(self.aws.document)
        after = region.desired_policy(original)
        self.assertEqual(original, self.aws.document)
        del after["Statement"][0]["Condition"]["StringNotEquals"]
        self.assertEqual(after, original)

    def test_apply_is_idempotent_and_rollback_exact(self):
        original = copy.deepcopy(self.aws.document)
        self.prepare()
        region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.document["Statement"][0]["Condition"]["StringNotEquals"],
                         {"aws:PrincipalAccount": region.WORKLOAD})
        region.apply(self.aws, self.directory)
        self.assertEqual(len(self.aws.writes), 1)
        region.apply(self.aws, self.directory, rollback=True)
        self.assertEqual(self.aws.document, original)
        self.assertEqual(len(list(self.directory.glob("apply-*.json"))), 1)
        self.assertEqual(len(list(self.directory.glob("rollback-*.json"))), 1)

    def test_wrong_management_account_refused(self):
        self.aws.account = region.WORKLOAD
        with self.assertRaises(region.Refused):
            self.prepare()
        self.assertFalse(self.directory.exists())
        self.assertEqual(self.aws.writes, [])

    def test_wrong_organization_refused(self):
        self.aws.organization = "o-unrelated"
        with self.assertRaises(region.Refused):
            self.prepare()

    def test_changed_attachment_refused(self):
        self.prepare()
        self.aws.targets.append({"TargetId": "ou-other", "Type": "ORGANIZATIONAL_UNIT"})
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.writes, [])

    def test_changed_policy_refused_without_write(self):
        self.prepare()
        self.aws.document["Statement"][1]["NotAction"].append("ec2:*")
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.writes, [])

    def test_changed_metadata_refused(self):
        self.prepare()
        self.aws.summary["Name"] = "Different"
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.writes, [])

    def test_tampered_preparation_refused(self):
        self.prepare()
        path = self.directory / "after.json"
        data = json.loads(path.read_text())
        data["Statement"][0]["Condition"]["StringNotEquals"]["aws:PrincipalAccount"] = "*"
        path.write_text(json.dumps(data))
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.writes, [])

    def test_expanded_change_with_recomputed_hash_refused(self):
        self.prepare()
        path = self.directory / "after.json"
        data = json.loads(path.read_text())
        data["Statement"].pop()
        path.write_text(json.dumps(data))
        manifest_path = self.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["after_sha256"] = region.digest(data)
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(self.aws.writes, [])

    def test_failed_readback_does_not_claim_success(self):
        self.prepare()
        self.aws.fail_verification = True
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory)
        self.assertEqual(len(self.aws.writes), 1)
        self.assertEqual(list(self.directory.glob("apply-*.json")), [])

    def test_rollback_refuses_to_overwrite_later_changes(self):
        self.prepare()
        region.apply(self.aws, self.directory)
        self.aws.document["Statement"][1]["NotAction"].append("ec2:*")
        with self.assertRaises(region.Refused):
            region.apply(self.aws, self.directory, rollback=True)
        self.assertEqual(len(self.aws.writes), 1)

    def test_changed_or_duplicate_statement_refused(self):
        for transform in (
            lambda doc: doc["Statement"].append(copy.deepcopy(doc["Statement"][0])),
            lambda doc: doc["Statement"][0].update(Effect="Allow"),
            lambda doc: doc["Statement"][0].update(Condition={}),
        ):
            data = copy.deepcopy(self.aws.document)
            transform(data)
            with self.assertRaises(region.Refused):
                region.desired_policy(data)


if __name__ == "__main__":
    unittest.main()
