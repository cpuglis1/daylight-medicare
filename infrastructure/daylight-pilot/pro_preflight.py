#!/usr/bin/env python3
"""Read-only CloudShell preflight. No resource creation, subscription or secret reads."""
import json
from pathlib import Path
import subprocess

import build_pro_migration as build
import pro_migration_control as control
from foundation_control import save, require


def main():
    c = control.clients()
    before = control.snapshot(c)
    current = control.template_body(c)
    stages = {"foundation": build.predecessor("remove-nat"),
              **{stage: build.network(stage) for stage in build.STAGES}}
    matches = [name for name, value in stages.items() if value == current]
    require(len(matches) == 1, "Unknown live template; do not prepare an update")
    validations = []
    for name, value in [(stage, build.network(stage)) for stage in build.STAGES] + [("closed-edge", build.edge())]:
        c["cloudformation"].validate_template(TemplateBody=json.dumps(value))
        validations.append(name)
    cache = c["cloudfront"].get_cache_policy(Id="4135ea2d-6df8-44a3-9df3-4b5a84be39ad")["CachePolicy"]["CachePolicyConfig"]
    require(all(cache[k] == 0 for k in ("MinTTL", "DefaultTTL", "MaxTTL")), "Managed cache policy is not zero-TTL")
    origin = c["cloudfront"].get_origin_request_policy(Id="216adef6-5c7f-47e4-b989-5492eafa07d3")["OriginRequestPolicy"]["OriginRequestPolicyConfig"]
    require(origin["HeadersConfig"]["HeaderBehavior"] == "allViewer" and
            origin["CookiesConfig"]["CookieBehavior"] == "all" and
            origin["QueryStringsConfig"]["QueryStringBehavior"] == "all", "Managed forwarding policy differs")
    prefix = c["ec2"].describe_managed_prefix_lists(Filters=[{
        "Name": "prefix-list-name", "Values": ["com.amazonaws.global.cloudfront.origin-facing"]}])["PrefixLists"]
    require(len(prefix) == 1 and prefix[0]["OwnerId"] == "AWS", "Expected AWS-owned CloudFront prefix list")
    dns = {}
    for record_type, name in (("NS", "daylightmedicare.com"), ("A", "daylightmedicare.com"),
                              ("CNAME", "test.daylightmedicare.com"), ("A", "origin.daylightmedicare.com")):
        try:
            proc = subprocess.run(["dig", "+short", name, record_type], capture_output=True,
                                  text=True, timeout=10, check=True)
            dns[name + "/" + record_type] = proc.stdout.strip().splitlines()
        except (OSError, subprocess.SubprocessError):
            dns[name + "/" + record_type] = {"unverified": True}
    import boto3
    s = boto3.Session(region_name=control.REGION)
    supports_plan = "pricing-plan-manager" in s.get_available_services()
    report = {"account": control.ACCOUNT, "region": control.REGION,
        "live_stage": matches[0], "snapshot": before, "template_syntax_validated": validations,
        "managed_cache_zero_ttl": True, "managed_forwarding_all_viewer": True,
        "cloudfront_prefix_list_id": prefix[0]["PrefixListId"],
        "dns": dns, "pricingplanmanager_sdk": supports_plan,
        "pro_subscription_eligibility": "not established by syntax validation",
        "mutating_aws_calls": 0}
    if supports_plan:
        report["pricing_plan_operations"] = s.client("pricing-plan-manager").meta.service_model.operation_names
    save(Path("pro-preflight.json"), report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
