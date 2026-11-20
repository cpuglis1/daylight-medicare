# Step 1: enable the workload region and inventory AWS

November 18, 2026. Implements the already-approved account-specific exception
under D101 and D185–D187. This is an execution procedure, not evidence of a
deployed website.

## Current result

Completed November 18 at 4:51 p.m. Eastern: the tested script was uploaded to
management CloudShell, prepared the full backup, and applied the approved
exception to policy p-nh0ejrgr. AWS readback passed. The policy's canonical
SHA-256 is 48cb2f8b7941737a8105140fecd6166f897839357b6d776c9857b34dd1bf8a76.
The full before/after policy and apply receipt remain in management CloudShell
at /home/cloudshell-user/daylight-region-20261118.

The inventory script was uploaded to workload-account CloudShell in Ohio and
explicitly queried us-east-1. It completed with exit code 0, including the
previously denied EC2 and Secrets Manager reads. The downloaded original
[inventory](../../audit-evidence/aws-account-setup-20261118/workload-inventory.txt)
and [execution record](../../audit-evidence/aws-account-setup-20261118/execution.json)
are retained locally. No credentials or secret values were copied.

The workload has one default VPC, six default subnets and an internet gateway.
The queried region has no running/stopped EC2 instances, ACM certificates,
NAT gateways, CloudFormation stacks, secrets or SSM-managed hosts. No CloudFront
distributions, CloudFront-scope WAF ACLs, matching Route 53 zone or workload-owned
budgets were returned. This is the queried resource scope, not an all-region or
all-service absence claim.

No hosting resource or DNS record was created. The initial attempt was paused
because browser windows changed and CloudShell expired; the resumed run above
supersedes that blocker. Local CLI authentication remains unconfigured.

## Management account

The following commands record the completed procedure and recovery route.
Use the existing management-account console, account 717010296718. Transfer
[region_exception.py](region_exception.py) through CloudShell's file upload.
Do not put credentials, a provider key or application data in the upload.

Run from the directory containing the uploaded script:

    python3 region_exception.py prepare "$HOME/daylight-region-20261118"

The preparation directory now exists; do not repeat prepare against it.
For a new preparation, the directory must not already exist. Review the printed diff: only
UsEast1Partitional.Condition.StringNotEquals.aws:PrincipalAccount is added,
with value 020055445580. All other conditions, statements and attachments stay
unchanged. The script checks the management account, organization, root
attachment and exact policy identity. It retains the full original policy,
before/after JSON and hashes in a private directory.

Apply the owner-approved change:

    python3 region_exception.py apply "$HOME/daylight-region-20261118"

Apply refuses changed metadata, attachments, prepared files or live content.
It reconstructs the permitted edit and verifies AWS's readback before recording
success. Repeating apply after a successful update makes no additional write.
Organizations UpdatePolicy does not offer an ETag precondition: do not run
another policy editor concurrently. The immediate read and drift check reduce,
but cannot eliminate, a concurrent administrator race.

If readback fails or a response is lost, inspect the current AWS policy and
backup before proceeding. Do not interpret the absence of a receipt as proof
that AWS did not change.

To restore the exact prior policy when appropriate:

    python3 region_exception.py rollback "$HOME/daylight-region-20261118"

Rollback refuses to overwrite subsequent policy changes. Keep this backup and
the apply receipt in the management CloudShell; retain a private operational
copy before retiring that environment. This exception changes a regional deny
for workload-account principals; it does not grant IAM permissions or prove
that all other organization restrictions permit deployment.

## Workload account

Use Blank Slate account 020055445580, not the management account. Upload
[aws-inventory.sh](aws-inventory.sh), then run:

    sh aws-inventory.sh - 020055445580

The dash uses the current CloudShell identity without a named CLI profile.
It refuses a mismatched account and always refuses the management account as
a workload. It lists DNS zones, distributions, certificates, instances, VPCs,
subnets, NAT/internet gateways, stacks, secret metadata, SSM hosts, WAF ACLs
and workload-owned budgets. It does not read secret values. A denied section
sets a nonzero final exit status while remaining reads continue.

Record successful EC2 and Secrets Manager reads as proof that the previously
observed regional denial is cleared. Record existing resource IDs before
preparing a priced infrastructure change set. Billing controls may belong to
the management account and require separate inspection. BAA coverage,
authoritative DNS, provider settings and hosting charges are not established
by this inventory.

## Verification completed locally

    python3 -B -m unittest discover -s infrastructure/daylight-pilot -p 'test_*.py' -v
    sh -n infrastructure/daylight-pilot/aws-inventory.sh

18 tests passed; shell syntax passed. Tests use fictional policies and a fake
AWS CLI, with no network, provider calls or AWS mutations. They cover identity,
attachments, drift, prepared-file tampering, private backups, one-condition
change scope, idempotency, failed readback, exact rollback, preservation of
later edits, CloudShell/profile modes and partial inventory denial.

The first test run found a Python Path.open argument error; it was corrected
before the passing run. These tests verify the controls offline. The successful
live AWS policy readback and inventory are recorded separately above; hosted
application security and participant acceptance remain open.

## Subsequent steps

1. Price and prepare the private host, encrypted storage, edge controls and TLS.
2. Bind the latest :8895 features, shared $20 ledger, reusable invitations,
   consented history storage and GPT-6.1 Sol low reasoning to the hosted runtime.
3. Restore and verify the display database, then exercise fictional traffic.
4. Set up automatic test deployment, explicit pilot promotion and rollback.
5. Bind Namecheap DNS and admit reviewers only after the applicable release checks.

References:
[Organizations UpdatePolicy](https://docs.aws.amazon.com/organizations/latest/APIReference/API_UpdatePolicy.html)
and [AWS global condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html).
