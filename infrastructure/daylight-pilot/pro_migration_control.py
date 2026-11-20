#!/usr/bin/env python3
"""Guarded, staged network migration. No subscription, certificate or ingress execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import build_pro_migration as build
from foundation_control import ACCOUNT, REGION, STACK, require, save


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def clients():
    import boto3
    s = boto3.Session(region_name=REGION)
    require(s.client("sts").get_caller_identity()["Account"] == ACCOUNT, "Wrong workload account")
    return {k: s.client(k) for k in ("cloudformation", "ec2", "ssm", "cloudfront")}


def template_body(c):
    value = c["cloudformation"].get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
    return json.loads(value) if isinstance(value, str) else value


def snapshot(c):
    stack = c["cloudformation"].describe_stacks(StackName=STACK)["Stacks"][0]
    require(stack["StackStatus"] in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}, "Stack is not stable")
    resources = {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in
                 c["cloudformation"].list_stack_resources(StackName=STACK)["StackResourceSummaries"]}
    host = c["ec2"].describe_instances(InstanceIds=[resources["Host"]])["Reservations"][0]["Instances"][0]
    require(host["State"]["Name"] == "running" and host["InstanceType"] == "t3.medium", "Unexpected host state/size")
    require(len(host["NetworkInterfaces"]) == 1, "Expected one network interface")
    sg = c["ec2"].describe_security_groups(GroupIds=[resources["HostSecurityGroup"]])["SecurityGroups"][0]
    credits = c["ec2"].describe_instance_credit_specifications(InstanceIds=[resources["Host"]])["InstanceCreditSpecifications"]
    require(credits[0]["CpuCredits"] == "standard", "Unexpected surplus CPU billing")
    require(not sg["IpPermissions"], "Ingress must still be closed")
    key = next(o["OutputValue"] for o in stack["Outputs"] if o["OutputKey"] == "DataKeyArn")
    volumes = c["ec2"].describe_volumes(VolumeIds=[b["Ebs"]["VolumeId"] for b in host["BlockDeviceMappings"]])["Volumes"]
    require(len(volumes) == 2 and sum(v["Size"] for v in volumes) == 50 and
            all(v["Encrypted"] and v["KmsKeyId"] == key for v in volumes), "Unexpected disks")
    address_id = resources["NatAddress"]
    addresses = c["ec2"].describe_addresses(**{
        "AllocationIds" if address_id.startswith("eipalloc-") else "PublicIps": [address_id]})["Addresses"]
    require(len(addresses) == 1, "Expected one retained public address")
    address = {k: addresses[0].get(k) for k in ("AllocationId", "PublicIp", "AssociationId", "NetworkInterfaceId")}
    route_table = c["ec2"].describe_route_tables(RouteTableIds=[resources["PrivateRouteTable"]])["RouteTables"][0]
    routes = [r for r in route_table["Routes"] if r.get("DestinationCidrBlock") == "0.0.0.0/0"]
    require(len(routes) == 1 and routes[0]["State"] == "active", "Unexpected application default route")
    expected_target = {"NatGatewayId": resources["NatGateway"]} if "NatGateway" in resources else {
        "GatewayId": resources["InternetGateway"]}
    require(all(routes[0].get(k) == v for k, v in expected_target.items()), "Default route drift")
    return {"stack_id": stack["StackId"], "resources": resources,
            "host_eni": host["NetworkInterfaces"][0]["NetworkInterfaceId"],
            "host_public_ip": host.get("PublicIpAddress"),
            "volume_ids": sorted(v["VolumeId"] for v in volumes),
            "address": address, "default_route": expected_target,
            "parameters": stack.get("Parameters", [])}


def validate_change_set(response, stage):
    require(response["Status"] == "CREATE_COMPLETE" and response["ExecutionStatus"] == "AVAILABLE",
            "Change set not ready")
    rows = [r["ResourceChange"] for r in response.get("Changes", [])]
    require(len(rows) == len(build.EXPECTED_CHANGES[stage]), "Unexpected change count")
    require({r["LogicalResourceId"]: r["Action"] for r in rows} == build.EXPECTED_CHANGES[stage],
            "Unexpected resource changes")
    require(all(r.get("Replacement") in (None, "False") for r in rows),
            "Replacement or conditional replacement refused")


def prepare(c, stage, directory):
    require(stage in build.STAGES[:2], "Ingress requires a separate verified origin release; not executable here")
    plan_path = directory / (stage + "-plan.json")
    require(not plan_path.exists(), "Plan already exists; inspect it instead of creating another")
    before = snapshot(c)
    previous = build.predecessor(stage)
    require(template_body(c) == previous, "Live template differs from the expected predecessor")
    require(before["host_public_ip"] is None, "Unexpected public host address before closed migration")
    if stage == "attach-address":
        # AWS may report a removed NAT for a while; only 'deleted' is acceptable.
        nat = c["ec2"].describe_nat_gateways(Filter=[{"Name": "vpc-id", "Values": [before["resources"]["Vpc"]]}])["NatGateways"]
        require(all(n["State"] == "deleted" for n in nat), "NAT deletion has not completed")
        require(not before["address"]["AssociationId"], "Existing address still associated")
    target = build.network(stage)
    body = json.dumps(target, indent=2) + "\n"
    c["cloudformation"].validate_template(TemplateBody=body)
    name = "pro-" + stage + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    response = c["cloudformation"].create_change_set(StackName=STACK, ChangeSetName=name,
        ChangeSetType="UPDATE", TemplateBody=body, Capabilities=["CAPABILITY_IAM"],
        Parameters=[{"ParameterKey": p["ParameterKey"], "UsePreviousValue": True} for p in before["parameters"]],
        Description="D193 reviewed closed network migration: " + stage)
    plan = {"account": ACCOUNT, "region": REGION, "stage": stage, "stack": STACK,
            "change_set": response["Id"], "before": before, "previous_sha256": digest(previous),
            "target_sha256": digest(target), "target": target,
            "expected_changes": build.EXPECTED_CHANGES[stage],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "note": "No public ingress; subscription/certificate/traffic activation excluded"}
    directory.mkdir(parents=True, exist_ok=True)
    save(plan_path, plan)
    print(json.dumps({"prepared": response["Id"], "plan_sha256": digest(plan), "stage": stage}))


def checked(c, path):
    plan = json.loads(path.read_text())
    require((plan["account"], plan["region"], plan["stack"]) == (ACCOUNT, REGION, STACK), "Plan identity mismatch")
    stage = plan["stage"]
    require(stage in build.STAGES[:2], "Ingress execution is unavailable")
    require(plan["target"] == build.network(stage) and
            plan["target_sha256"] == digest(build.network(stage)) and
            plan["previous_sha256"] == digest(build.predecessor(stage)), "Plan/template changed")
    response = c["cloudformation"].describe_change_set(ChangeSetName=plan["change_set"])
    require(response["StackId"] == plan["before"]["stack_id"], "Wrong stack in change set")
    return plan, response


def inspect(c, path):
    plan, response = checked(c, path)
    validate_change_set(response, plan["stage"])
    report = {"stage": plan["stage"], "plan_sha256": digest(plan),
              "status": response["Status"], "execution": response["ExecutionStatus"],
              "changes": [r["ResourceChange"] for r in response["Changes"]]}
    save(path.with_name(plan["stage"] + "-inspection.json"), report)
    print(json.dumps(report, indent=2))


def execute(c, path, reviewed_sha256):
    # There is no all-stages action and no automatic retry or next-stage apply.
    plan, response = checked(c, path)
    require(reviewed_sha256 == digest(plan), "Exact reviewed plan hash is required")
    validate_change_set(response, plan["stage"])
    require(template_body(c) == build.predecessor(plan["stage"]), "Live template drift")
    require(snapshot(c) == plan["before"], "Live resources changed since preparation")
    body = c["cloudformation"].get_template(ChangeSetName=plan["change_set"], TemplateStage="Original")["TemplateBody"]
    require((json.loads(body) if isinstance(body, str) else body) == plan["target"], "Cloud change-set template drift")
    observed = {p["ParameterKey"]: p["ParameterValue"] for p in response["Parameters"]}
    require(observed == {p["ParameterKey"]: p["ParameterValue"] for p in plan["before"]["parameters"]},
            "Change-set parameters drifted")
    c["cloudformation"].execute_change_set(
        ChangeSetName=plan["change_set"], DisableRollback=True)
    print("One stage started. Inspect stack completion before preparing the next stage.")


def verify(c, path):
    plan = json.loads(path.read_text())
    require(plan["account"] == ACCOUNT and plan["region"] == REGION and plan["stack"] == STACK, "Wrong plan identity")
    require(plan["stage"] in build.STAGES[:2] and plan["target"] == build.network(plan["stage"]), "Wrong target")
    require(template_body(c) == plan["target"], "Target template not deployed")
    after = snapshot(c)
    before = plan["before"]
    for logical, physical in before["resources"].items():
        if logical != "NatGateway":
            require(after["resources"].get(logical) == physical, "Resource replaced: " + logical)
    require(after["volume_ids"] == before["volume_ids"], "Disk identity changed")
    require(after["host_eni"] == before["host_eni"], "Network interface replaced")
    if plan["stage"] == "attach-address":
        require(after["address"]["AllocationId"] == before["address"]["AllocationId"] and
                after["host_public_ip"] == after["address"]["PublicIp"] and
                after["address"]["NetworkInterfaceId"] == after["host_eni"], "Address not on the expected host")
        info = c["ssm"].describe_instance_information(Filters=[{
            "Key": "InstanceIds", "Values": [after["resources"]["Host"]]}])["InstanceInformationList"]
        require(len(info) == 1 and info[0]["PingStatus"] == "Online", "SSM not online")
    else:
        require(after["host_public_ip"] is None, "Unexpected host address")
    receipt = {"stage": plan["stage"], "verified_at": datetime.now(timezone.utc).isoformat(),
               "after": after, "inbound_rules": 0, "disk_ids_preserved": True, "site_live": False}
    save(path.with_name(plan["stage"] + "-verification.json"), receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "inspect", "execute", "verify"))
    parser.add_argument("stage", choices=build.STAGES[:2])
    parser.add_argument("--directory", type=Path, default=Path("pro-migration-evidence"))
    parser.add_argument("--reviewed-sha256")
    args = parser.parse_args()
    c = clients()
    path = args.directory / (args.stage + "-plan.json")
    if args.action == "prepare":
        prepare(c, args.stage, args.directory)
    elif args.action == "execute":
        execute(c, path, args.reviewed_sha256)
    else:
        globals()[args.action](c, path)
