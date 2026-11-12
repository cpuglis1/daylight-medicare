# D101 pilot deployment and verification

November 8, 2026. AWS `us-east-1` and the OpenAI GPT API are the approved target.
The owner reports signed agreements and completed account security setup.
The approved scope is the guest-only Collier pilot through December 23, 2026,
with up to 20 participants and the existing D99 $100 cumulative model limit.
Keep detailed numeric usage for 90 days and non-identifying cohort totals for
12 months. Raw chat stays visit-only.

## AWS account handoff

The installed AWS CLI is 2.15.31. `aws configure list-profiles` returned no
profiles, and STS `get-caller-identity` returned `Unable to locate credentials`.
The owner sees AWS Settings Projects. That interface has a project connection
flow. Use **Create and manage cloud infrastructure → Use your AWS credentials
with AI coding tools** on the intended workload project. The project login
command, `aws login --profile daylight-pilot`, requires AWS CLI 2.32.0 or newer.
Select the existing workload project in the browser. `daylight-pilot` is a
local profile name. Of the listed projects, Blank Slate is the candidate for
the fictional rehearsal if the owner confirms it is the intended workload
account and permits the required resources in `us-east-1`. AWS provisions a
first project during new-experience sign-up, so Blank Slate may predate the
owner's management setup. The listed Identity Delegated Admin account suggests
advanced features are already active. Confirm that in AWS Organizations. Keep
the existing Daylight Management Account for billing and governance. Use a
member account for the workload and verify its region policy, budget scope and
agreement coverage before deployment. AWS documents a standard member account
created through Organizations as the option when account portability or control
of the root email matters.
[AWS project connection](https://docs.aws.amazon.com/accounts/latest/reference/connect-ai-coding-tool.html) · [AWS CLI login prerequisites](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
[AWS sign-up](https://docs.aws.amazon.com/accounts/latest/reference/sign-in-new.html) · [Project Regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html) · [Advanced features and member accounts](https://docs.aws.amazon.com/accounts/latest/reference/activate-advanced-features.html)

If the workload account and an assigned role are available via a standard
IAM Identity Center access portal, the existing CLI supports this alternative:

```sh
aws configure sso --profile daylight-pilot
aws sso login --profile daylight-pilot
aws sts get-caller-identity --profile daylight-pilot --region us-east-1
```

Use the access portal's Start URL and Identity Center region at the prompts.
Select the pilot account and assigned deployment role. The workload region
is `us-east-1` even if the Identity Center directory is in a different region.
The wizard creates a local profile linked to an existing AWS account and
role. The deployment needs the profile name and the existing host or planned
pilot hostname. Keep credentials and recovery material in their respective
stores.
[AWS CLI SSO guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)

## Hosting estimate and rehearsal wiring

The owner reports a **$20/month AWS alert budget** under D102. Verify that it
covers the workload account. Check an estimate for one small on-demand EC2 host,
an encrypted general purpose volume and a single public IPv4 address for HTTPS.
Allow room for logs and storage in the estimate. Validate architecture
compatibility and the quote before creating resources.
The estimate excludes the separate $100 model cap. Multiple hosts, a load
balancer, NAT, managed database, backup growth and significant traffic would
need a new estimate. AWS Budget notifications can arrive after charges accrue.
[EC2](https://aws.amazon.com/ec2/pricing/on-demand/) · [EBS](https://aws.amazon.com/ebs/pricing/) · [IPv4](https://aws.amazon.com/vpc/pricing/) · [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

The [systemd service](../../infrastructure/daylight-pilot/daylight-pilot.service)
and [Caddy configuration](../../infrastructure/daylight-pilot/Caddyfile) describe
one fictional rehearsal instance. Install the reviewed source snapshot at
`/opt/daylight-pilot`, Python 3.11 and Caddy with `request_body` support. Use a
dedicated `daylight-pilot` system user and group. Set `DAYLIGHT_PILOT_ORIGIN`
to the exact HTTPS origin in `/etc/daylight-pilot/origin.env` and set
`DAYLIGHT_PILOT_HOST` to the matching hostname in the Caddy service environment.
Initialize `/var/lib/daylight-pilot/cohort` as the service user using
`pilot_admin.py` and a rehearsal expiry. Keep the backend loopback-only and
allow HTTPS at the edge. Use SSM for administration. Review the release bundle
and confirm the instance profile, storage encryption, firewall, DNS and TLS
certificate before exposing the fixture origin. Use a different state directory
and signing key for the later participant deployment.
[Caddy HTTPS](https://caddyserver.com/docs/automatic-https) · [Request size limit](https://caddyserver.com/docs/caddyfile/directives/request_body)

Use `pilot_admin.py COHORT reconcile TOTAL_NANO_USD` to compare a finalized,
cumulative provider total from the isolated pilot project with the settled
ledger for the same window. Exit 2 means a difference or held charges require
review. The report leaves reservations and spend controls in force. A rounded
invoice is insufficient for an exact match. The fixture test uses synthetic
provider totals and leaves the paid API disconnected.

## Verification and remaining deployment work

| Check | Observed |
| --- | --- |
| HTTPS and origin | Local TLS 1.2 negotiated with hostname and certificate validation. HSTS returned. The HTTP regression rejected a wrong host and cross-origin redemption. |
| Access log | Eight local HTTPS events contained only an event type, fixed route or `other`, status and timestamp. Fictional invite, cookie, CSRF value, message and query text were absent. |
| Billing | A local HTTPS fixture session reconciled zero spend. Ledger tests used synthetic nonzero totals to exercise match, discrepancy and unsettled reservations. The operator CLI returned 0 for a match and 2 for a synthetic discrepancy. |
| Stop switches | Both chat switches independently returned 503 for a message while the sample route returned 200. The enrollment route returned 404. |
| Regression tests | 54 pilot security, pilot scope, response failure, advisor budget and provider budget tests passed on loopback with credentials and external sockets disabled. |
| AWS | No authenticated session available. Caddy, systemd, public certificate, CloudWatch delivery and AWS budget remain unverified on a host. |

Once AWS access is available, verify the intended account and inventory before
provisioning. Validate the edge configuration, capture certificate and fixed
field access log evidence, and repeat the stop switch and billing drills with
fictional traffic. Verify log and numeric usage retention in the actual stores.
Bind participant routing only to the covered OpenAI project after confirming
the model, Responses and token-counting paths, effective data controls, redaction
and the source and admission gates. Verify admin audit logging with the actual
runtime role. The founder reviews that exact deployment before invitations go to
participants. Actual cost per completed visit is measured in the pilot.
