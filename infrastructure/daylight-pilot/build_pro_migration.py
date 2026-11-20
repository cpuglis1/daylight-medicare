#!/usr/bin/env python3
"""Build D193 migration candidates locally. Never contacts AWS."""
import copy
import json
from pathlib import Path

from build_foundation import template as foundation, ref, att, sub

STAGES = ("remove-nat", "attach-address", "cloudfront-ingress")
EXPECTED_CHANGES = {
    "remove-nat": {"NatGateway": "Remove", "PrivateRoute": "Modify"},
    "attach-address": {"OriginAddressAssociation": "Add"},
    "cloudfront-ingress": {"HostSecurityGroup": "Modify"},
}


def network(stage):
    if stage not in STAGES:
        raise ValueError("Unknown migration stage")
    t = copy.deepcopy(foundation())
    r = t["Resources"]
    # Keep logical IDs and all storage/IAM/host properties unchanged.
    # The old PrivateSubnet becomes publicly routed, but is NOT recreated.
    del r["NatGateway"]
    r["PrivateRoute"]["Properties"].pop("NatGatewayId")
    r["PrivateRoute"]["Properties"]["GatewayId"] = ref("InternetGateway")
    r["PrivateRoute"]["DependsOn"] = "GatewayAttachment"
    del t["Outputs"]["NatGatewayId"]
    t["Outputs"]["OriginPublicIp"] = {"Value": ref("NatAddress")}
    if stage != "remove-nat":
        # Deliberately a separate update: NAT deletion must finish before
        # CloudFormation tries to associate its existing EIP with the host.
        r["OriginAddressAssociation"] = {
            "Type": "AWS::EC2::EIPAssociation",
            "Properties": {"AllocationId": att("NatAddress", "AllocationId"),
                           "InstanceId": ref("Host")}}
    if stage == "cloudfront-ingress":
        t["Parameters"]["CloudFrontPrefixListId"] = {
            "Type": "String", "AllowedPattern": "pl-[0-9a-f]+"}
        r["HostSecurityGroup"]["Properties"]["SecurityGroupIngress"] = [{
            "IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
            "SourcePrefixListId": ref("CloudFrontPrefixListId"),
            "Description": "CloudFront origin servers; proxy must also authenticate this distribution"}]
    t["Description"] = "Daylight D193 Pro migration: " + stage
    return t


def predecessor(stage):
    index = STAGES.index(stage)
    return foundation() if index == 0 else network(STAGES[index - 1])


def edge():
    """Closed edge only. Subscription creation does not activate paid pricing."""
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "D193 closed CloudFront Pro candidate; no automatic activation or traffic",
        "Parameters": {
            "ViewerCertificateArn": {"Type": "String", "AllowedPattern":
                "arn:aws:acm:us-east-1:020055445580:certificate/[0-9a-f-]+"},
            "OriginToken": {"Type": "String", "NoEcho": True,
                            "MinLength": 64, "MaxLength": 64,
                            "AllowedPattern": "[0-9a-f]{64}"}},
        "Resources": {
            "ClosedWebAcl": {
                "Type": "AWS::WAFv2::WebACL",
                "Properties": {
                    "Scope": "CLOUDFRONT", "DefaultAction": {"Block": {}},
                    "Description": "All requests blocked until separately reviewed pilot admission",
                    "VisibilityConfig": {"SampledRequestsEnabled": False,
                                         "CloudWatchMetricsEnabled": False,
                                         "MetricName": "daylight-pro-closed"},
                    "Rules": []}},
            "Distribution": {
                "Type": "AWS::CloudFront::Distribution",
                "Properties": {"DistributionConfig": {
                    "Enabled": False,
                    "Comment": "Daylight Pro pending activation and privacy verification",
                    "Aliases": ["daylightmedicare.com", "test.daylightmedicare.com"],
                    "HttpVersion": "http2", "IPV6Enabled": True,
                    "PriceClass": "PriceClass_All",
                    "WebACLId": att("ClosedWebAcl", "Arn"),
                    "Origins": [{"Id": "daylight-origin", "DomainName": "origin.daylightmedicare.com",
                        "OriginCustomHeaders": [{"HeaderName": "X-Daylight-Origin-Token",
                                                  "HeaderValue": ref("OriginToken")}],
                        "ConnectionAttempts": 1, "ConnectionTimeout": 10,
                        "CustomOriginConfig": {"HTTPSPort": 443, "OriginProtocolPolicy": "https-only",
                            "OriginSSLProtocols": ["TLSv1.2"], "OriginReadTimeout": 60,
                            "OriginKeepaliveTimeout": 5}}],
                    "DefaultCacheBehavior": {
                        "TargetOriginId": "daylight-origin", "ViewerProtocolPolicy": "https-only",
                        "AllowedMethods": ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
                        "CachedMethods": ["GET", "HEAD"],
                        "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                        "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",
                        "Compress": False},
                    "CustomErrorResponses": [{"ErrorCode": code, "ErrorCachingMinTTL": 0}
                        for code in (400, 403, 404, 405, 414, 416, 500, 501, 502, 503, 504)],
                    "ViewerCertificate": {"AcmCertificateArn": ref("ViewerCertificateArn"),
                        "SslSupportMethod": "sni-only", "MinimumProtocolVersion": "TLSv1.2_2021"}}}},
            "ProSubscription": {
                "Type": "AWS::PricingPlanManager::Subscription",
                "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain",
                "Properties": {"PlanFamily": "CloudFront", "PlanTier": "PRO", "UsageLevel": "DEFAULT",
                    "ResourceArns": [sub("arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}"),
                                     att("ClosedWebAcl", "Arn")]}}},
        "Outputs": {"DistributionId": {"Value": ref("Distribution")},
                    "DistributionDomain": {"Value": att("Distribution", "DomainName")},
                    "SubscriptionArn": {"Value": ref("ProSubscription")},
                    "SubscriptionStatus": {"Value": att("ProSubscription", "Status")}}}


if __name__ == "__main__":
    directory = Path(__file__).parent / "pro-candidates"
    directory.mkdir(exist_ok=True)
    for name, value in [(stage, network(stage)) for stage in STAGES] + [("closed-edge", edge())]:
        path = directory / (name + ".json")
        path.write_text(json.dumps(value, indent=2) + "\n")
        print(path.name)
