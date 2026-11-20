"""Offline rejection and preservation tests; never contact AWS or an AI provider."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import build_foundation
import build_pro_migration as build
import pro_migration_control as control


def response(stage):
    return {"Status": "CREATE_COMPLETE", "ExecutionStatus": "AVAILABLE", "Changes": [
        {"ResourceChange": {"LogicalResourceId": key, "Action": action,
                            **({"Replacement": "False"} if action == "Modify" else {})}}
        for key, action in build.EXPECTED_CHANGES[stage].items()]}


class MigrationTests(unittest.TestCase):
    def test_all_stages_preserve_host_disks_key_and_permissions(self):
        original = build_foundation.template()["Resources"]
        protected = set(original) - {"NatGateway", "PrivateRoute", "HostSecurityGroup"}
        for stage in build.STAGES:
            target = build.network(stage)["Resources"]
            for name in protected:
                self.assertEqual(target[name], original[name], (stage, name))
            self.assertNotIn("NatGateway", target)
            self.assertEqual(target["PrivateRoute"]["Properties"]["GatewayId"], {"Ref": "InternetGateway"})

    def test_nat_must_be_deleted_in_an_earlier_update_than_ip_association(self):
        first = build.network("remove-nat")["Resources"]
        second = build.network("attach-address")["Resources"]
        self.assertNotIn("OriginAddressAssociation", first)
        self.assertEqual(second["OriginAddressAssociation"]["Properties"], {
            "AllocationId": {"Fn::GetAtt": ["NatAddress", "AllocationId"]}, "InstanceId": {"Ref": "Host"}})
        self.assertEqual(sum(r["Type"] == "AWS::EC2::EIP" for r in second.values()), 1)

    def test_first_two_stages_have_no_ingress(self):
        for stage in build.STAGES[:2]:
            self.assertEqual(build.network(stage)["Resources"]["HostSecurityGroup"]["Properties"]["SecurityGroupIngress"], [])

    def test_final_candidate_only_accepts_cloudfront_https(self):
        rules = build.network("cloudfront-ingress")["Resources"]["HostSecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual(len(rules), 1)
        self.assertEqual((rules[0]["FromPort"], rules[0]["ToPort"], rules[0]["IpProtocol"]), (443, 443, "tcp"))
        self.assertNotIn("CidrIp", rules[0])
        self.assertEqual(rules[0]["SourcePrefixListId"], {"Ref": "CloudFrontPrefixListId"})

    def test_edge_closed_and_pro_only(self):
        resources = build.edge()["Resources"]
        self.assertFalse(resources["Distribution"]["Properties"]["DistributionConfig"]["Enabled"])
        self.assertEqual(resources["ClosedWebAcl"]["Properties"]["DefaultAction"], {"Block": {}})
        self.assertEqual(resources["ClosedWebAcl"]["Properties"]["Rules"], [])
        self.assertEqual(resources["ProSubscription"]["Properties"]["PlanTier"], "PRO")
        self.assertEqual(resources["ProSubscription"]["DeletionPolicy"], "Retain")

    def test_private_responses_use_managed_zero_cache_and_forward_session(self):
        config = build.edge()["Resources"]["Distribution"]["Properties"]["DistributionConfig"]
        behavior = config["DefaultCacheBehavior"]
        self.assertEqual(behavior["CachePolicyId"], "4135ea2d-6df8-44a3-9df3-4b5a84be39ad")
        self.assertEqual(behavior["OriginRequestPolicyId"], "216adef6-5c7f-47e4-b989-5492eafa07d3")
        self.assertEqual(behavior["ViewerProtocolPolicy"], "https-only")
        self.assertTrue(all(r["ErrorCachingMinTTL"] == 0 for r in config["CustomErrorResponses"]))
        self.assertNotIn("Logging", config)
        self.assertTrue(build.edge()["Parameters"]["OriginToken"]["NoEcho"])

    def test_rejects_disk_replacement_even_if_other_changes_are_correct(self):
        value = response("remove-nat")
        value["Changes"].append({"ResourceChange": {
            "LogicalResourceId": "StateVolume", "Action": "Modify", "Replacement": "True"}})
        with self.assertRaises(RuntimeError):
            control.validate_change_set(value, "remove-nat")

    def test_rejects_new_paid_resources(self):
        value = response("attach-address")
        value["Changes"].append({"ResourceChange": {"LogicalResourceId": "ExtraHost", "Action": "Add"}})
        with self.assertRaises(RuntimeError):
            control.validate_change_set(value, "attach-address")

    def test_rejects_conditional_replacement_and_unavailable_changes(self):
        for replacement in ("True", "Conditional"):
            value = response("remove-nat")
            value["Changes"][1]["ResourceChange"]["Replacement"] = replacement
            with self.assertRaises(RuntimeError):
                control.validate_change_set(value, "remove-nat")
        value = response("remove-nat")
        value["ExecutionStatus"] = "EXECUTE_COMPLETE"
        with self.assertRaises(RuntimeError):
            control.validate_change_set(value, "remove-nat")

    def test_only_exact_known_changes_pass(self):
        for stage in build.STAGES:
            control.validate_change_set(response(stage), stage)

    def test_refuses_ingress_preparation_before_any_api_call(self):
        c = {"cloudformation": Mock()}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Ingress"):
                control.prepare(c, "cloudfront-ingress", Path(directory))
        self.assertEqual(c["cloudformation"].mock_calls, [])

    def test_execute_requires_exact_review_hash_before_mutation(self):
        c = {"cloudformation": Mock()}
        plan = {"stage": "remove-nat"}
        with patch.object(control, "checked", return_value=(plan, response("remove-nat"))):
            with self.assertRaisesRegex(RuntimeError, "reviewed plan hash"):
                control.execute(c, Path("unused"), "wrong")
        c["cloudformation"].execute_change_set.assert_not_called()

    def test_checked_refuses_tampered_template(self):
        target = build.network("remove-nat")
        plan = {"account": control.ACCOUNT, "region": control.REGION, "stack": control.STACK,
                "stage": "remove-nat", "target": target, "target_sha256": control.digest(target),
                "previous_sha256": control.digest(build.predecessor("remove-nat"))}
        plan["target"]["Resources"]["Host"]["Properties"]["InstanceType"] = "m7i.48xlarge"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(RuntimeError, "changed"):
                control.checked({}, path)

    def test_execution_rejects_live_resource_drift(self):
        plan = {"stage": "remove-nat", "before": {"resources": {"Host": "original"}}}
        c = {"cloudformation": Mock()}
        with patch.object(control, "checked", return_value=(plan, response("remove-nat"))), \
                patch.object(control, "template_body", return_value=build.predecessor("remove-nat")), \
                patch.object(control, "snapshot", return_value={"resources": {"Host": "different"}}):
            with self.assertRaisesRegex(RuntimeError, "resources changed"):
                control.execute(c, Path("unused"), control.digest(plan))
        c["cloudformation"].execute_change_set.assert_not_called()

    def test_generated_candidates_match_sources(self):
        directory = Path(__file__).parent / "pro-candidates"
        for stage in build.STAGES:
            self.assertEqual(json.loads((directory / (stage + ".json")).read_text()), build.network(stage))
        self.assertEqual(json.loads((directory / "closed-edge.json").read_text()), build.edge())

    def test_reviewed_execution_starts_only_one_stage_without_automatic_rollback(self):
        plan = {"stage": "remove-nat", "before": {"parameters": []},
                "target": build.network("remove-nat"), "change_set": "reviewed-change"}
        value = response("remove-nat")
        value["Parameters"] = []
        cloud = Mock()
        cloud.get_template.return_value = {"TemplateBody": plan["target"]}
        with patch.object(control, "checked", return_value=(plan, value)), \
                patch.object(control, "template_body", return_value=build.predecessor("remove-nat")), \
                patch.object(control, "snapshot", return_value=plan["before"]):
            control.execute({"cloudformation": cloud}, Path("unused"), control.digest(plan))
        cloud.execute_change_set.assert_called_once_with(
            ChangeSetName="reviewed-change", DisableRollback=True)
        cloud.create_change_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
