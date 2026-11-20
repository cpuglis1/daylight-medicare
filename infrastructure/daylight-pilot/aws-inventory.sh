#!/bin/sh
# Read-only inventory for the Daylight workload. Use a separate billing role
# to verify the linked-account budget if it belongs to the management account.
# In workload CloudShell: sh aws-inventory.sh - 020055445580
set -eu
export AWS_PAGER=""
profile=${1:-daylight-pilot}
expected_account=${2:?Pass the expected 12-digit workload account as argument 2}
case "$expected_account" in
    *[!0-9]*|'') echo "Expected a numeric workload account ID." >&2; exit 2 ;;
esac
[ "${#expected_account}" -eq 12 ] || exit 2
inspect() {
    if [ "$profile" = "-" ]; then
        aws --region us-east-1 --no-cli-pager "$@"
    else
        aws --profile "$profile" --region us-east-1 --no-cli-pager "$@"
    fi
}
account=$(inspect sts get-caller-identity --query Account --output text)
[ "$account" = "$expected_account" ] || { echo "Workload account mismatch. Stopping." >&2; exit 1; }
[ "$account" != "717010296718" ] || { echo "Do not provision workloads in management." >&2; exit 1; }
status=0
report() {
    title=$1
    shift
    echo "$title"
    if ! inspect "$@" --output json; then
        echo "Unable to verify $title with this role." >&2
        status=1
    fi
}
report "Matching DNS zones in this account" route53 list-hosted-zones-by-name \
    --dns-name daylightmedicare.com --query "HostedZones[?Name=='daylightmedicare.com.'].{Id:Id,Private:Config.PrivateZone}"
report "CloudFront aliases in this account" cloudfront list-distributions \
    --query 'DistributionList.Items[].{Id:Id,Domain:DomainName,Aliases:Aliases.Items,Status:Status}'
report "ACM certificates in us-east-1" acm list-certificates \
    --query 'CertificateSummaryList[].{Arn:CertificateArn,Domain:DomainName,Status:Status}'
report "Running or stopped EC2 instances in us-east-1" ec2 describe-instances \
    --filters Name=instance-state-name,Values=running,stopped \
    --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,Vpc:VpcId,Subnet:SubnetId,PublicIP:PublicIpAddress}'
report "VPCs" ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Cidr:CidrBlock,Default:IsDefault}'
report "Subnets" ec2 describe-subnets \
    --query 'Subnets[].{Id:SubnetId,Vpc:VpcId,Cidr:CidrBlock,Zone:AvailabilityZone,PublicIP:MapPublicIpOnLaunch}'
report "NAT gateways" ec2 describe-nat-gateways \
    --query 'NatGateways[].{Id:NatGatewayId,Vpc:VpcId,Subnet:SubnetId,State:State}'
report "Internet gateways" ec2 describe-internet-gateways \
    --query 'InternetGateways[].{Id:InternetGatewayId,Attachments:Attachments}'
report "Deployment stacks" cloudformation describe-stacks \
    --query 'Stacks[].{Id:StackId,Name:StackName,Status:StackStatus}'
report "Secrets metadata only" secretsmanager list-secrets \
    --query 'SecretList[].{Arn:ARN,Name:Name,KmsKey:KmsKeyId,RotationEnabled:RotationEnabled}'
report "SSM-managed hosts" ssm describe-instance-information \
    --query 'InstanceInformationList[].{Id:InstanceId,Status:PingStatus,OS:PlatformName,Version:PlatformVersion}'
report "WAF CloudFront ACLs" wafv2 list-web-acls --scope CLOUDFRONT \
    --query 'WebACLs[].{Name:Name,Id:Id,Arn:ARN}'
report "Workload-owned billing alerts and filters" budgets describe-budgets \
    --account-id "$account" --query 'Budgets[].{Name:BudgetName,Period:TimeUnit,Limit:BudgetLimit,Filters:CostFilters,FilterExpression:FilterExpression}'
exit "$status"
