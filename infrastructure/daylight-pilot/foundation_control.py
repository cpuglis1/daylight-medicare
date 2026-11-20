#!/usr/bin/env python3
"""CloudShell operator: prepare, inspect, apply and verify the closed foundation."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ACCOUNT = "020055445580"
REGION = "us-east-1"
STACK = "daylight-pilot-foundation"
# D191: estimate guard only, not an AWS billing cap or permission for new services.
APPROVED_MONTHLY_ESTIMATE = Decimal("102.27")
PLAN = Path("foundation-plan.json")
TEMPLATE = Path("foundation.json")


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")
    path.chmod(0o600)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clients():
    import boto3
    session = boto3.Session(region_name=REGION)
    require(session.client("sts").get_caller_identity()["Account"] == ACCOUNT,
            "Wrong workload account; no changes made.")
    return {name: session.client(name) for name in
            ("cloudformation", "ec2", "ssm", "pricing", "kms", "s3", "secretsmanager")}


def hourly_price(client, service, fields, suffix=None):
    products = []
    paginator = client.get_paginator("get_products")
    for page in paginator.paginate(ServiceCode=service, Filters=[
        {"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in fields.items()]):
        products.extend(json.loads(row) for row in page["PriceList"])
    matches = []
    for product in products:
        attributes = product["product"]["attributes"]
        if suffix and not attributes.get("usagetype", "").endswith(suffix):
            continue
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            for dimension in term["priceDimensions"].values():
                if dimension.get("beginRange") == "0":
                    matches.append({"sku": product["product"]["sku"],
                                    "usd": dimension["pricePerUnit"]["USD"],
                                    "unit": dimension["unit"],
                                    "description": dimension["description"],
                                    "effective": term["effectiveDate"]})
    require(len(matches) == 1, f"Expected one price for {service}/{suffix or fields}; found {len(matches)}")
    return matches[0]


def prepare(c):
    require(not PLAN.exists(), "A plan already exists; inspect it before preparing another.")
    raw = TEMPLATE.read_bytes()
    template = json.loads(raw)
    # Only CREATE is supported. Never update or replace an existing deployment implicitly.
    try:
        c["cloudformation"].describe_stacks(StackName=STACK)
    except c["cloudformation"].exceptions.ClientError as exc:
        require("does not exist" in str(exc), str(exc))
    else:
        raise RuntimeError("Stack already exists; inspect its state rather than recreating it.")
    prices = {
        "compute": hourly_price(c["pricing"], "AmazonEC2", {
            "regionCode": REGION, "instanceType": "t3.medium", "operatingSystem": "Linux",
            "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"}),
        "nat": hourly_price(c["pricing"], "AmazonEC2", {"regionCode": REGION, "productFamily": "NAT Gateway", "operation": "NatGateway"}, "NatGateway-Hours"),
        "ebs": hourly_price(c["pricing"], "AmazonEC2", {"regionCode": REGION, "productFamily": "Storage", "volumeApiName": "gp3"}, "EBS:VolumeUsage.gp3"),
        "ipv4": hourly_price(c["pricing"], "AmazonVPC", {"regionCode": REGION}, "PublicIPv4:InUseAddress"),
    }
    # 730-hour month. KMS and secret rates reviewed on AWS official pricing pages.
    baseline = sum(Decimal(prices[k]["usd"]) * 730 for k in ("compute", "nat", "ipv4"))
    baseline += Decimal(prices["ebs"]["usd"]) * 50 + Decimal("1.40")
    allowance = baseline + 30  # Later WAF, edge requests, backup storage and low-volume overhead.
    require(allowance <= APPROVED_MONTHLY_ESTIMATE,
            f"Estimated monthly scope exceeds approved ${APPROVED_MONTHLY_ESTIMATE}: {allowance}")
    ami = c["ssm"].get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
    images = c["ec2"].describe_images(ImageIds=[ami], Owners=["amazon"])["Images"]
    require(len(images) == 1 and images[0]["State"] == "available"
            and images[0]["Architecture"] == "x86_64", "AMI is not the expected available Amazon image.")
    zones = c["ec2"].describe_availability_zones(Filters=[
        {"Name": "state", "Values": ["available"]}, {"Name": "zone-type", "Values": ["availability-zone"]}])["AvailabilityZones"]
    require(zones, "No available standard AZ.")
    zone = sorted(zones, key=lambda row: row["ZoneName"])[0]["ZoneName"]
    require(c["ec2"].describe_instance_type_offerings(LocationType="availability-zone", Filters=[
        {"Name": "instance-type", "Values": ["t3.medium"]}, {"Name": "location", "Values": [zone]}])["InstanceTypeOfferings"],
        "Selected AZ does not offer t3.medium.")
    c["cloudformation"].validate_template(TemplateBody=raw.decode())
    parameters = [{"ParameterKey": "ImageId", "ParameterValue": ami},
                  {"ParameterKey": "AvailabilityZone", "ParameterValue": zone}]
    name = "foundation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = c["cloudformation"].create_change_set(
        StackName=STACK, ChangeSetName=name, ChangeSetType="CREATE",
        TemplateBody=raw.decode(), Parameters=parameters, Capabilities=["CAPABILITY_IAM"],
        Description="Approved D101 D185-D187 closed private host and encrypted storage",
        Tags=[{"Key": "Project", "Value": "Daylight"}, {"Key": "Stage", "Value": "closed-foundation"}])
    save(PLAN, {"account": ACCOUNT, "region": REGION, "stack": STACK,
               "template_sha256": sha(raw), "change_set": result["Id"], "parameters": parameters,
               "image_name": images[0]["Name"], "prices": prices,
               "monthly_fixed_usd": str(baseline.quantize(Decimal(".01"))),
               "monthly_with_allowance_usd": str(allowance.quantize(Decimal(".01"))),
               "resource_types": {k: v["Type"] for k, v in template["Resources"].items()}})
    print(json.dumps({"prepared": result["Id"], "fixed_usd": str(baseline),
                      "with_allowance_usd": str(allowance), "ami": ami, "zone": zone}))


def checked_plan(c):
    plan = json.loads(PLAN.read_text())
    require(plan["account"] == ACCOUNT and plan["region"] == REGION and plan["stack"] == STACK,
            "Plan identity mismatch.")
    require(sha(TEMPLATE.read_bytes()) == plan["template_sha256"], "Template changed after preparation.")
    response = c["cloudformation"].describe_change_set(ChangeSetName=plan["change_set"])
    require(response["StackName"] == STACK, "Wrong change-set stack.")
    return plan, response


def inspect(c):
    plan, response = checked_plan(c)
    changes = [row["ResourceChange"] for row in response.get("Changes", [])]
    print(json.dumps({"status": response["Status"], "execution": response["ExecutionStatus"],
                      "reason": response.get("StatusReason"), "fixed_usd": plan["monthly_fixed_usd"],
                      "with_allowance_usd": plan["monthly_with_allowance_usd"],
                      "changes": [{k: row.get(k) for k in ("Action", "LogicalResourceId", "ResourceType", "Replacement")}
                                  for row in changes]}, indent=2))


def apply(c):
    plan, response = checked_plan(c)
    require(response["Status"] == "CREATE_COMPLETE" and response["ExecutionStatus"] == "AVAILABLE",
            "Change set is not available for execution.")
    require(Decimal(plan["monthly_with_allowance_usd"]) <= APPROVED_MONTHLY_ESTIMATE,
            "Estimate exceeds approved scope.")
    require({p["ParameterKey"]: p["ParameterValue"] for p in response["Parameters"]} ==
            {p["ParameterKey"]: p["ParameterValue"] for p in plan["parameters"]}, "Cloud parameters changed.")
    observed = c["cloudformation"].get_template(ChangeSetName=plan["change_set"], TemplateStage="Original")["TemplateBody"]
    if isinstance(observed, str):
        observed = json.loads(observed)
    local = json.loads(TEMPLATE.read_text())
    require(observed == local, "AWS change-set template differs from the reviewed template.")
    changes = [row["ResourceChange"] for row in response.get("Changes", [])]
    require(all(row["Action"] == "Add" for row in changes), "Unexpected replacement/removal/update.")
    require({row["LogicalResourceId"]: row["ResourceType"] for row in changes} ==
            {k: v["Type"] for k, v in local["Resources"].items()}, "Unexpected resource set.")
    c["cloudformation"].execute_change_set(ChangeSetName=plan["change_set"])
    print("Execution started. Run status; do not start another stack.")


def status(c):
    stack = c["cloudformation"].describe_stacks(StackName=STACK)["Stacks"][0]
    events = c["cloudformation"].describe_stack_events(StackName=STACK)["StackEvents"]
    print(json.dumps({"status": stack["StackStatus"],
                      "recent_events": [{"resource": e["LogicalResourceId"], "status": e["ResourceStatus"],
                                         "reason": e.get("ResourceStatusReason")}
                                        for e in events[:12]]}, indent=2))


def verify(c):
    stack = c["cloudformation"].describe_stacks(StackName=STACK)["Stacks"][0]
    require(stack["StackStatus"] == "CREATE_COMPLETE", "Stack has not completed successfully.")
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    instance = c["ec2"].describe_instances(InstanceIds=[outputs["HostId"]])["Reservations"][0]["Instances"][0]
    require(instance["State"]["Name"] == "running" and not instance.get("PublicIpAddress"),
            "Host not running privately.")
    require(instance["MetadataOptions"]["HttpTokens"] == "required", "IMDSv2 not required.")
    require(not instance.get("KeyName"), "Unexpected SSH key.")
    credits = c["ec2"].describe_instance_credit_specifications(InstanceIds=[outputs["HostId"]])["InstanceCreditSpecifications"]
    require(credits[0]["CpuCredits"] == "standard", "Unexpected surplus CPU billing.")
    group = c["ec2"].describe_security_groups(GroupIds=[outputs["HostSecurityGroupId"]])["SecurityGroups"][0]
    require(not group["IpPermissions"], "Unexpected inbound rule.")
    require(len(group["IpPermissionsEgress"]) == 1
            and group["IpPermissionsEgress"][0]["IpProtocol"] == "tcp"
            and group["IpPermissionsEgress"][0]["FromPort"] == 443
            and group["IpPermissionsEgress"][0]["ToPort"] == 443, "Unexpected outbound ports.")
    volumes = c["ec2"].describe_volumes(VolumeIds=[b["Ebs"]["VolumeId"] for b in instance["BlockDeviceMappings"]])["Volumes"]
    require(len(volumes) == 2 and all(v["Encrypted"] and v["KmsKeyId"] == outputs["DataKeyArn"] for v in volumes),
            "Expected two encrypted disks bound to the data key.")
    bucket = outputs["BackupBucketName"]
    require(all(c["s3"].get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values()),
            "S3 public access block incomplete.")
    require(c["s3"].get_bucket_versioning(Bucket=bucket)["Status"] == "Enabled", "Backup versioning missing.")
    encryption = c["s3"].get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"][0]["ApplyServerSideEncryptionByDefault"]
    require(encryption["SSEAlgorithm"] == "aws:kms" and encryption["KMSMasterKeyID"] == outputs["DataKeyArn"],
            "Backup key binding differs.")
    require(c["kms"].get_key_rotation_status(KeyId=outputs["DataKeyArn"])["KeyRotationEnabled"], "Key rotation missing.")
    secret = c["secretsmanager"].describe_secret(SecretId=outputs["ProviderSecretArn"])
    require(not secret.get("VersionIdsToStages"), "Expected an empty secret slot at foundation stage.")
    ssm = c["ssm"].describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [outputs["HostId"]]}])["InstanceInformationList"]
    require(len(ssm) == 1 and ssm[0]["PingStatus"] == "Online", "SSM host not online yet.")
    save(Path("foundation-verification.json"), {
        "verified_at": datetime.now(timezone.utc).isoformat(), "outputs": outputs,
        "private_host": True, "inbound_rules": 0, "encrypted_disks": len(volumes),
        "ssm_online": True, "secret_empty": True, "application_installed": False,
        "state_volume_formatted": False, "public_site_live": False})
    print(json.dumps({"verified": True, "outputs": outputs, "application_installed": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "inspect", "apply", "status", "verify"))
    args = parser.parse_args()
    globals()[args.action](clients())
