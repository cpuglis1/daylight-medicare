#!/usr/bin/env python3
"""Generate the closed Daylight AWS foundation. Does not contact AWS."""
import json
from pathlib import Path


def ref(name):
    return {"Ref": name}


def att(name, field):
    return {"Fn::GetAtt": [name, field]}


def sub(value):
    return {"Fn::Sub": value}


def template():
    resources = {}

    def add(name, kind, properties, **options):
        resources[name] = {"Type": "AWS::" + kind, "Properties": properties, **options}

    def tags(name):
        return [{"Key": "Project", "Value": "Daylight"},
                {"Key": "Name", "Value": sub("${AWS::StackName}-" + name)}]

    add("Vpc", "EC2::VPC", {"CidrBlock": "10.42.0.0/16", "EnableDnsSupport": True,
                          "EnableDnsHostnames": True, "Tags": tags("vpc")})
    add("InternetGateway", "EC2::InternetGateway", {"Tags": tags("igw")})
    add("GatewayAttachment", "EC2::VPCGatewayAttachment",
        {"VpcId": ref("Vpc"), "InternetGatewayId": ref("InternetGateway")})
    for name, cidr in (("Public", "10.42.0.0/24"), ("Private", "10.42.1.0/24")):
        add(name + "Subnet", "EC2::Subnet", {
            "VpcId": ref("Vpc"), "CidrBlock": cidr, "AvailabilityZone": ref("AvailabilityZone"),
            "MapPublicIpOnLaunch": False, "Tags": tags(name.lower())})
        add(name + "RouteTable", "EC2::RouteTable", {"VpcId": ref("Vpc"), "Tags": tags(name.lower())})
        add(name + "RouteAssociation", "EC2::SubnetRouteTableAssociation",
            {"SubnetId": ref(name + "Subnet"), "RouteTableId": ref(name + "RouteTable")})
    add("PublicRoute", "EC2::Route", {"RouteTableId": ref("PublicRouteTable"),
        "DestinationCidrBlock": "0.0.0.0/0", "GatewayId": ref("InternetGateway")},
        DependsOn="GatewayAttachment")
    add("NatAddress", "EC2::EIP", {"Domain": "vpc", "Tags": tags("nat")},
        DependsOn="GatewayAttachment")
    add("NatGateway", "EC2::NatGateway", {"SubnetId": ref("PublicSubnet"),
        "AllocationId": att("NatAddress", "AllocationId"), "Tags": tags("nat")},
        DependsOn="PublicRoute")
    add("PrivateRoute", "EC2::Route", {"RouteTableId": ref("PrivateRouteTable"),
        "DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": ref("NatGateway")})
    add("HostSecurityGroup", "EC2::SecurityGroup", {
        "GroupDescription": "Closed Daylight origin; no inbound access in foundation stage",
        "VpcId": ref("Vpc"), "SecurityGroupIngress": [],
        "SecurityGroupEgress": [{"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                                "CidrIp": "0.0.0.0/0", "Description": "TLS provider and AWS service access"}],
        "Tags": tags("origin")})
    add("DataKey", "KMS::Key", {"Description": "Daylight pilot encrypted storage",
        "EnableKeyRotation": True, "PendingWindowInDays": 30,
        "KeyPolicy": {"Version": "2012-10-17", "Statement": [
            {"Sid": "AccountAdministration", "Effect": "Allow",
             "Principal": {"AWS": sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:root")},
             "Action": "kms:*", "Resource": "*"}]}, "Tags": tags("data")},
        DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    add("DataKeyAlias", "KMS::Alias", {"AliasName": sub("alias/${AWS::StackName}-data"),
                                     "TargetKeyId": ref("DataKey")})
    add("ProviderSecret", "SecretsManager::Secret", {
        "Name": sub("${AWS::StackName}/openai"),
        "Description": "Empty until dedicated project hard limit and provider controls are verified",
        "KmsKeyId": att("DataKey", "Arn"), "Tags": tags("provider")},
        DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    add("HostRole", "IAM::Role", {
        "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        "ManagedPolicyArns": [sub("arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore")],
        "Policies": [{"PolicyName": "ReadOwnProviderSecret", "PolicyDocument": {
            "Version": "2012-10-17", "Statement": [
                {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"],
                 "Resource": ref("ProviderSecret")},
                {"Effect": "Allow", "Action": ["kms:Decrypt"], "Resource": att("DataKey", "Arn"),
                 "Condition": {"StringEquals": {
                     "kms:ViaService": sub("secretsmanager.${AWS::Region}.amazonaws.com"),
                     "kms:EncryptionContext:SecretARN": ref("ProviderSecret")}}}]}}],
        "Tags": tags("host")})
    add("HostProfile", "IAM::InstanceProfile", {"Roles": [ref("HostRole")]})
    add("Host", "EC2::Instance", {
        "ImageId": ref("ImageId"), "InstanceType": "t3.medium",
        "AvailabilityZone": ref("AvailabilityZone"),
        "IamInstanceProfile": ref("HostProfile"),
        "CreditSpecification": {"CPUCredits": "standard"},
        "MetadataOptions": {"HttpTokens": "required", "HttpEndpoint": "enabled",
                            "HttpPutResponseHopLimit": 1, "InstanceMetadataTags": "disabled"},
        "NetworkInterfaces": [{"DeviceIndex": "0", "SubnetId": ref("PrivateSubnet"),
                               "AssociatePublicIpAddress": False,
                               "GroupSet": [ref("HostSecurityGroup")]}],
        "BlockDeviceMappings": [{"DeviceName": "/dev/xvda", "Ebs": {
            "VolumeSize": 20, "VolumeType": "gp3", "Encrypted": True,
            "KmsKeyId": att("DataKey", "Arn"), "DeleteOnTermination": True}}],
        "Tags": tags("host")},
        DependsOn="PrivateRoute")
    add("StateVolume", "EC2::Volume", {
        "AvailabilityZone": ref("AvailabilityZone"), "Size": 30, "VolumeType": "gp3",
        "Encrypted": True, "KmsKeyId": att("DataKey", "Arn"), "Tags": tags("state")},
        DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    add("StateAttachment", "EC2::VolumeAttachment", {
        "InstanceId": ref("Host"), "VolumeId": ref("StateVolume"), "Device": "/dev/sdf"})
    add("BackupBucket", "S3::Bucket", {
        "BucketEncryption": {"ServerSideEncryptionConfiguration": [{
            "ServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms",
                                               "KMSMasterKeyID": att("DataKey", "Arn")},
            "BucketKeyEnabled": True}]},
        "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "IgnorePublicAcls": True,
                                          "BlockPublicPolicy": True, "RestrictPublicBuckets": True},
        "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
        "VersioningConfiguration": {"Status": "Enabled"},
        "LifecycleConfiguration": {"Rules": [
            {"Id": "BackupExpiry", "Status": "Enabled", "ExpirationInDays": 29,
             "NoncurrentVersionExpiration": {"NoncurrentDays": 1},
             "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}},
            {"Id": "DeleteExpiredMarkers", "Status": "Enabled",
             "ExpiredObjectDeleteMarker": True}]},
        "Tags": tags("backups")}, DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    add("BackupPolicy", "S3::BucketPolicy", {"Bucket": ref("BackupBucket"), "PolicyDocument": {
        "Version": "2012-10-17", "Statement": [
            {"Sid": "TLSOnly", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
             "Resource": [att("BackupBucket", "Arn"), sub("${BackupBucket.Arn}/*")],
             "Condition": {"Bool": {"aws:SecureTransport": "false"}}},
            {"Sid": "DenyWrongEncryption", "Effect": "Deny", "Principal": "*",
             "Action": "s3:PutObject", "Resource": sub("${BackupBucket.Arn}/*"),
             "Condition": {"StringNotEqualsIfExists": {"s3:x-amz-server-side-encryption": "aws:kms"}}},
            {"Sid": "DenyWrongKey", "Effect": "Deny", "Principal": "*",
             "Action": "s3:PutObject", "Resource": sub("${BackupBucket.Arn}/*"),
             "Condition": {"StringNotEqualsIfExists": {
                 "s3:x-amz-server-side-encryption-aws-kms-key-id": att("DataKey", "Arn")}}}]}})
    return {"AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Daylight closed AWS foundation D101 D185-D187; no app or public ingress",
        "Parameters": {
            "AvailabilityZone": {"Type": "AWS::EC2::AvailabilityZone::Name"},
            "ImageId": {"Type": "AWS::EC2::Image::Id"}},
        "Resources": resources,
        "Outputs": {name: {"Value": value} for name, value in {
            "VpcId": ref("Vpc"), "HostId": ref("Host"), "HostPrivateIp": att("Host", "PrivateIp"),
            "HostSecurityGroupId": ref("HostSecurityGroup"), "StateVolumeId": ref("StateVolume"),
            "DataKeyArn": att("DataKey", "Arn"), "BackupBucketName": ref("BackupBucket"),
            "ProviderSecretArn": ref("ProviderSecret"), "NatGatewayId": ref("NatGateway"),
            "PrivateSubnetId": ref("PrivateSubnet")}.items()}}


if __name__ == "__main__":
    path = Path(__file__).with_name("foundation.json")
    path.write_text(json.dumps(template(), indent=2) + "\n")
    print(path)
