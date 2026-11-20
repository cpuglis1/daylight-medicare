# CloudFront Pro feasibility review

November 18, 2026 · D192 research only. Addresses D141, D185–D187 and D191.
No subscription, AWS configuration, DNS, application code or paid test changed.

**Recommendation:** develop the $15/month Pro alternative for the small demo,
subject to the account and security checks below. It appears compatible from
documentation and source inspection. It is not yet an AWS-validated deployment.
The existing private foundation remains running and billing as recorded in
[Step 2](STEP_2_FOUNDATION.md). Nothing in this review approves a migration.

## Proposed design and cost

Use one Pro distribution for `daylightmedicare.com` and
`test.daylightmedicare.com`. Forward the viewer Host to an HTTPS reverse proxy
on the existing-size EC2 host, which selects two isolated loopback app services.
Keep separate guests, invitations and data namespaces, with the one shared $20
model ledger. Neither hostname may select the other service through arbitrary
forwarded headers. This shares edge configuration and host availability; it is
not complete infrastructure isolation.

Pro has no VPC-origin support. Replace the app subnet's NAT route with an
internet-gateway route and assign one public IPv4 to the host. Its security
group accepts only HTTPS from CloudFront's origin-facing prefix list. Require
a separate high-entropy CloudFront origin header at the reverse proxy, before
any application access. The prefix list alone trusts other customers'
CloudFront distributions too. Reject unknown Host values, absent/wrong origin
tokens, direct IP access and private/admin paths. Keep SSH closed and use SSM.
This has less network isolation than a private VPC origin and requires explicit
approval and deployed negative checks. It must never become an unrestricted
public application server.

[AWS prefix-list controls](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/LocationsOfEdgeServers.html)
and [origin-header controls](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-origin-custom-headers.html)
support that design. The prefix list has weight 55: one IPv4 HTTPS rule fits
the usual 60-rule inbound quota; do not add unrestricted HTTP/SSH alongside it.

| Item | Monthly basis, 730 hours |
| --- | ---: |
| CloudFront Pro, one distribution | $15.00 |
| Existing-size t3.medium, standard credits | $30.37 |
| One public IPv4, now attached to host | $3.65 |
| Existing 50 GiB encrypted gp3 storage | $4.00 |
| Existing key and provider secret slot | $1.40 |
| **Baseline after migration** | **$54.42** |

Calculation reuses the account's November 18 price check: $72.268 current
baseline minus $32.85 NAT hourly cost plus $15 Pro = $54.418. It does not count
the earlier $30 allowance as another bill. Public IPv4 remains necessary, so
its $3.65 is not a saving. A 744-hour month gives approximately $55.07.
Any temporary resource overlap during migration must be priced separately;
no overlap or replacement is authorized here.

There is also origin HTTPS: propose one exportable ACM certificate for
`origin.daylightmedicare.com`, **$7 on issuance and each renewal**, not per
month. Current certificates last 198 days and renew 45 days before expiry;
the renewed certificate must be installed on the host. Viewer TLS uses a
non-exportable ACM certificate for the public hostnames. Do not purchase a
wildcard or create duplicate certificates automatically. Alternatives such as
a free ACME certificate would require separately verified renewal tooling.
[ACM pricing](https://aws.amazon.com/certificate-manager/pricing/) ·
[export and renewal requirements](https://docs.aws.amazon.com/acm/latest/userguide/acm-exportable-certificates.html).

The baseline excludes tax, model usage, metered backend operations, existing
domain renewal and optional add-ons. It is not a guaranteed invoice maximum.

## Pro scope and exceptions

[AWS's FAQ](https://aws.amazon.com/cloudfront/faqs/) prices Pro at $15 and
includes delivery and core protection. The published allowance is 10 million
requests and 50 TB monthly. Covered traffic has no overage charges; sustained
excess can reduce delivery performance. The plan is per distribution, not per
server. Adding a second Pro distribution would add another $15.

[Plan constraints](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html):
Pro excludes VPC origins and custom cache/origin-request/response-header
policies. Managed policies remain the candidate. It has 10 cache behaviors
and 25 WAF rules. AWS staging distributions are unsupported; our test app
would be a normal hostname/service. Log ingestion coverage excludes storage
and querying. Lambda@Edge, some logging destinations and CAPTCHA JavaScript
API use can add fees. Route 53 non-alias query excess can move DNS to
usage-based billing. Disabling a distribution does not cancel its fee;
cancellation takes effect at cycle end and then changes to pay-as-you-go.
Account eligibility and exact configuration acceptance are unverified.

Keep Namecheap DNS if its authoritative service is BasicDNS/FreeDNS/PremiumDNS:
it supports apex ALIAS records. Use an apex ALIAS and test CNAME to CloudFront,
plus DNS validation records and a separate origin A record. Preserve mail
records. This avoids adding Route 53 for this proposal; actual nameservers and
existing records still need inspection. [Namecheap ALIAS documentation](https://www.namecheap.com/support/knowledgebase/article.aspx/10128/2237/how-to-create-an-alias-record/).

## Application compatibility

The current `edge-policies.json` creates custom policies, so it cannot be reused
unchanged. Proposed replacements:

| Existing requirement | Proposed Pro-compatible configuration |
| --- | --- |
| Private HTML, chat, invitation and profile responses never cached | Managed `CachingDisabled`, ID `4135ea2d-6df8-44a3-9df3-4b5a84be39ad`; zero TTLs, origin `no-store`, supported error-cache TTLs zero |
| Cookies, Host, Origin and CSRF reach app | Managed `AllViewer`, ID `216adef6-5c7f-47e4-b989-5492eafa07d3`; proxy removes untrusted forwarding headers and passes only required values downstream |
| CSP and other security headers | Set at the origin; no custom CloudFront response-header policy needed |
| Pilot and test isolation | Forward Host; explicit proxy mapping to distinct services and host-only cookies; reject unknown names |
| Origin confidentiality | HTTPS-only to a trusted certificate matching origin hostname; reject plaintext |

[Managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html)
and [managed origin request policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html)
document these mechanisms. `CachingOptimized` is unsuitable here because its
positive minimum TTL can override `no-store`. The broader `AllViewer` policy
is a reason to sanitize at the reverse proxy, not a reason to relax app checks.
[Origin TLS validation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https-cloudfront-to-custom-origin.html).

Source inspection found the existing hosted handler checks exact Host/Origin,
uses invitation and guest cookies, validates CSRF and denies unknown routes.
Those protections are compatible in principle with this mapping. They do not
prove end-to-end CloudFront behavior. Long model turns still need a bounded
timeout/recovery design: the current provider wait can exceed CloudFront's
default 30-second origin response timeout. A larger timeout alone is not proof
of reliable delivery; use fictional slow-provider tests, without paid probes.

CloudFront is HIPAA eligible excluding Embedded POP delivery. Pricing tier
does not prove account BAA coverage or participant readiness. The existing
AWS/OpenAI vendor checks, consent, archive implementation and release gates
remain necessary before real participant data.
[AWS compliance documentation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/compliance.html).

## Remaining cost risks and required work

Removing NAT removes its hourly and per-byte fees. It does not cap direct
internet egress from the host. Pro also does not cap S3/KMS/Secrets Manager
operations, application logs, OpenAI, or resources created by an administrator.

Before a public demo, prepare and verify:

1. An outbound byte allowance and restricted destinations, with persistence
   across restarts and service pause on exhaustion. Do not claim a hard network
   cap until tested; privileged host compromise can defeat host-only controls.
2. Bounded local logs and scheduled, size/count-limited backups. No raw
   request logging, private content in URLs, per-request object creation or
   automatic growth of disks. S3 lifecycle alone is not a size limit.
3. A routine deployment role confined to the existing host/release destination.
   It must not create/resize machines, enable autoscaling, purchase subscriptions
   or change its own permissions. Broader administrator access remains separate.
4. Every paid model path bound to the persistent $20 cumulative/$2 invitation
   ledger. Neither a leaked provider key nor cloud costs are bounded by a
   ledger the request bypasses; verify provider-side controls separately.
5. Explicit cancellation instructions: disable traffic first, handle paid-plan
   cancellation timing, and ensure an active distribution cannot silently keep
   serving after switching to pay-as-you-go. Never auto-upgrade a plan.

## Next implementation boundary

First prepare the exact offline configuration and migration change set for
review, including retained disk/key/bucket preservation, the origin certificate,
renewal process, migration cost and rollback. Check account eligibility with
read-only access. A subscription, public-origin change or new certificate
requires owner approval under D191. If Pro rejects the managed-policy or TLS
configuration, stop and report it; do not upgrade to Business automatically.

After approval, verify direct-origin denial, another-distribution denial,
two-browser cache isolation, cross-host cookie/CSRF isolation, slow replies,
budget exhaustion, state preservation and backup limits using fictional data.

This review read project/Brain context, the existing foundation and edge
templates, and hosted route code, and checked official AWS/Namecheap sources.
It did not access the AWS console, run conversation tests, change infrastructure,
or verify actual Pro configuration acceptance. Only documentation and arithmetic
were checked locally. Brain notes still describe older deployment status; the
repository's execution records hold the current account state.
