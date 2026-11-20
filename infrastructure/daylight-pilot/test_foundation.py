"""Offline boundaries for the closed initial infrastructure."""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import build_foundation
import foundation_control


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.t = build_foundation.template()
        self.r = self.t["Resources"]

    def test_generated_template_is_current(self):
        self.assertEqual(self.t, json.loads(Path(__file__).with_name("foundation.json").read_text()))

    def test_host_has_no_public_ingress_or_ssh_key(self):
        p = self.r["Host"]["Properties"]
        self.assertNotIn("KeyName", p)
        self.assertFalse(p["NetworkInterfaces"][0]["AssociatePublicIpAddress"])
        self.assertEqual(p["NetworkInterfaces"][0]["SubnetId"], {"Ref": "PrivateSubnet"})
        self.assertEqual(self.r["HostSecurityGroup"]["Properties"]["SecurityGroupIngress"], [])
        self.assertEqual(p["MetadataOptions"]["HttpTokens"], "required")
        self.assertEqual(p["CreditSpecification"]["CPUCredits"], "standard")
        self.assertNotIn("UserData", p)

    def test_private_route_uses_nat_in_same_az(self):
        self.assertNotIn("GatewayId", self.r["PrivateRoute"]["Properties"])
        self.assertEqual(self.r["PrivateRoute"]["Properties"]["NatGatewayId"], {"Ref": "NatGateway"})
        for name in ("PrivateSubnet", "PublicSubnet", "Host", "StateVolume"):
            self.assertEqual(self.r[name]["Properties"]["AvailabilityZone"], {"Ref": "AvailabilityZone"})
        self.assertEqual(self.r["NatGateway"]["Properties"]["SubnetId"], {"Ref": "PublicSubnet"})

    def test_state_survives_stack_or_instance_replacement(self):
        for name in ("StateVolume", "DataKey", "BackupBucket", "ProviderSecret"):
            self.assertEqual(self.r[name]["DeletionPolicy"], "Retain")
            self.assertEqual(self.r[name]["UpdateReplacePolicy"], "Retain")
        self.assertTrue(self.r["StateVolume"]["Properties"]["Encrypted"])
        root = self.r["Host"]["Properties"]["BlockDeviceMappings"][0]["Ebs"]
        self.assertTrue(root["Encrypted"])
        self.assertEqual(root["KmsKeyId"], self.r["StateVolume"]["Properties"]["KmsKeyId"])

    def test_backup_bucket_is_private_and_key_bound(self):
        p = self.r["BackupBucket"]["Properties"]
        self.assertTrue(all(p["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(p["VersioningConfiguration"]["Status"], "Enabled")
        self.assertEqual(p["OwnershipControls"]["Rules"][0]["ObjectOwnership"], "BucketOwnerEnforced")
        statements = self.r["BackupPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        self.assertTrue(all(s["Effect"] == "Deny" for s in statements))
        self.assertEqual({s["Sid"] for s in statements}, {"TLSOnly", "DenyWrongEncryption", "DenyWrongKey"})

    def test_runtime_cannot_read_other_secrets_or_backups(self):
        p = self.r["HostRole"]["Properties"]
        actions = p["Policies"][0]["PolicyDocument"]["Statement"]
        self.assertEqual(actions[0]["Resource"], {"Ref": "ProviderSecret"})
        self.assertEqual(actions[0]["Action"], ["secretsmanager:GetSecretValue"])
        self.assertEqual(actions[1]["Action"], ["kms:Decrypt"])
        self.assertEqual(actions[1]["Condition"]["StringEquals"]["kms:EncryptionContext:SecretARN"],
                         {"Ref": "ProviderSecret"})
        self.assertEqual(len(p["Policies"]), 1)
        self.assertEqual(len(p["ManagedPolicyArns"]), 1)
        self.assertNotIn("SecretString", self.r["ProviderSecret"]["Properties"])
        self.assertNotIn("GenerateSecretString", self.r["ProviderSecret"]["Properties"])

    def test_ambiguous_or_missing_price_refuses(self):
        client = Mock()
        client.get_paginator.return_value.paginate.return_value = [{"PriceList": []}]
        with self.assertRaises(RuntimeError):
            foundation_control.hourly_price(client, "AmazonEC2", {})

    def test_apply_refuses_estimate_above_owner_approval(self):
        cloud = Mock()
        with patch.object(foundation_control, "checked_plan", return_value=(
                {"monthly_with_allowance_usd": "102.28"},
                {"Status": "CREATE_COMPLETE", "ExecutionStatus": "AVAILABLE"})):
            with self.assertRaisesRegex(RuntimeError, "Estimate exceeds approved scope"):
                foundation_control.apply({"cloudformation": cloud})
        cloud.execute_change_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
