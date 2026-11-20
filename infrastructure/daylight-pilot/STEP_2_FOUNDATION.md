# Step 2: closed AWS foundation

November 18, 2026. D185–D187 implementation; D191 spending restriction now controls further work.

The `daylight-pilot-foundation` CloudFormation stack completed in workload account
`020055445580`, `us-east-1`. The read-only verifier passed after the SSM agent
finished registering. Charges have started. Provisioning is paused.

No Daylight application, database restore, API key, public ingress, CloudFront,
WAF, certificate or DNS change was deployed. This does not make
daylightmedicare.com a live Daylight application.

## Approved estimate and exposure

The live AWS Price List API was checked before the 24-resource CREATE change set
was executed. The quote assumes 730 hours/month, Linux on-demand pricing, and
no credits or free-tier offsets. KMS and Secrets Manager fixed rates were checked
against their official pricing pages.

| Component | Rate/basis | Monthly estimate |
| --- | --- | ---: |
| One t3.medium | $0.0416/hour × 730 | $30.37 |
| One NAT gateway | $0.045/hour × 730 | $32.85 |
| NAT public IPv4 | $0.005/hour × 730 | $3.65 |
| Encrypted gp3 disks | 20 + 30 GiB at $0.08/GiB-month | $4.00 |
| One KMS key | Monthly key fee | $1.00 |
| One empty secret slot | Monthly secret fee | $0.40 |
| **Baseline** | Rounded total | **$72.27** |
| Discussed allowance | Variable overhead / prospective edge services | $30.00 |
| **Presented hosting estimate** | Separate from AI usage | **$102.27** |

D191 approves only the presented configuration and estimate, superseding the
earlier $75–$150 range. No additional paid service, upgrade or cost expansion
may be made without first disclosing its price and obtaining explicit owner
approval. The allowance is not blanket permission to provision more services.

This is not an enforced AWS invoice ceiling. A 31-day month has 744 hours rather
than 730 (about $73.55 baseline). NAT data processing, internet transfer, S3
storage/requests, KMS/Secrets Manager API requests and applicable taxes remain
variable. An idle private server reduces exposure but does not cap the invoice.
The separate $20 cumulative AI allowance does not limit AWS charges; no model
calls or paid probes were made here. Budget alerts or automated account-wide
shutdown are not claimed as configured. Existing resources continue billing
while provisioning is paused; stopping EC2 alone would not stop NAT/storage charges.

## Verified configuration

- Host `i-0f641362addf26b76`, private address `10.42.1.63`, no public IP or SSH key.
- Security group `sg-0b9fdca69a1cb7c57`: zero inbound rules; outbound TCP 443 only.
- IMDSv2 required; T3 credits set to standard, preventing surplus-credit billing.
- Two encrypted EBS volumes use the application KMS key; state volume is retained
  and is not yet formatted/mounted.
- Private S3 backup bucket with public access blocked, versioning and KMS encryption.
- KMS rotation enabled; provider secret slot empty; SSM reports the host online.
- No autoscaling, additional host or paid database service in this foundation.

The host has outbound access through the NAT gateway. The backup bucket and key
exist, but no backup job or durable chat archive has been implemented. Retention
and backup deletion verification remain separate release work.

## Evidence and verification

CloudShell retains the executed template/controller, `foundation-plan.json`,
`foundation-status.json`, `foundation-verification.json` and
`verification-output.txt` under `/home/cloudshell-user/daylight-foundation`.
The plan records the returned AWS price SKUs, rates, AMI and exact template hash.
Change set:
`arn:aws:cloudformation:us-east-1:020055445580:changeSet/foundation-20261118T220554Z/5444e0a1-d66e-4cda-852b-8a1c78665b57`.

The live verifier initially stopped while the stack was creating, then while SSM
was registering; its final read-only run returned `verified: true` and
`application_installed: false`. No extra resources were added to resolve either wait.
The local [observation record](../../audit-evidence/aws-account-setup-20261118/foundation-observation.json)
transcribes the verified terminal output; it is not a downloaded AWS receipt.

Eight offline foundation tests passed, including refusal to execute a plan
estimated above $102.27. The local controller now enforces that narrowed estimate
guard. It is not a billing limiter. The already-executed CloudShell copy retains
its earlier $150 preflight threshold and must not be reused; it has no scheduled
or autonomous execution. A future authorized operation must use the current
reviewed source. No further AWS mutation was made after D191.

Public routing/TLS, runtime integration, Linux data restore, durable consented
history, reusable invitations, provider setup, shared budget binding, deployment
pipeline and release verification remain open. Costs must be disclosed before
any subsequent paid provisioning.
