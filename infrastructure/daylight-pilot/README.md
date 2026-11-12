# Daylight AWS launch workstream

D141 · November 11, 2026. This is the continuation point for the secure backend
and site launch. AWS `us-east-1`, CloudFront and AWS WAF are selected. Start
with the existing invite-only pilot and one **$100 cumulative model budget**.
Re-evaluate public access and its budget after the pilot. Consumer use of the
advisor remains login-free.

The [full AWS migration analysis](MIGRATION_ANALYSIS.md) maps the current site,
APIs, research data, guest state, model calls, monitoring, costs and deployment
dependencies. It includes the proposed architecture, phased migration, rollback
and acceptance checks. Hosting choices and cost ranges there are proposals to
price and review before provisioning.

## Prepared locally

| Item | Implementation and verification |
| --- | --- |
| Guest access | Expiring, single-use invitations, server-side revocation, guest-cookie binding, CSRF and allowed routes in `pilot_access.py`. Durable saved profiles remain disabled in the invite-only pilot. |
| Refresh | :8894 stores a non-authorizing request reference and presentation metadata. The backend recovers accepted reports and the current reply from its existing memory journal. Polling an in-flight reply performs free reads. |
| Budget | `PilotBudget` reserves and settles all model stages within the single $100 ledger. Per-participant reporting, uncertain-charge holds, reconciliation and kill switches are implemented in the isolated rehearsal. |
| Pacing | The participant gate covers both free-text requests and choices that explicitly request AI composition. Free recovery has separate bounded slots. |
| UI proxy | Host and browser origin are checked before rewriting the origin for the loopback backend. Request framing, body size and read timeouts are checked at the proxy. |
| AWS policies | [edge-policies.json](edge-policies.json) prepares a CloudFront-scope WAF ACL, a cache policy with all TTLs zero and a guest origin request policy. Request sampling is disabled. CloudWatch receives counters. |
| Model routing | The existing `model-routes.json` fails closed for the pilot until the approved project, exact endpoints and processing-region settings are bound. |

The [D141 evidence packet](../../audit-evidence/guest-resume-security-20261111/README.md)
records actual local checks. The :8893/:8894 local services are activated, with
health and free-recovery checks. AWS deployment and acceptance remain open.
The current systemd service starts a fictional rehearsal.
The production model adapter still needs connection to the cumulative ledger
when the approved host and provider configuration are available.

## Browser recovery limits

Accepted details and the current reply can survive an ordinary same-tab
refresh while the server retains the visit. The current journal has a one-hour
expiry and a capacity bound. Restart, expiry, eviction or deleted access can
end recovery. Explicit saved reports have their existing separate retention.
Earlier displayed chat and unsent drafts are not durably saved. A draft,
pending request or unavailable browser storage invokes the browser's
leave-page warning where supported. A later restored tab offers Resume.

This design follows D54, D61, D86/D90 and D140–D141. Persistent transcript or
draft recovery across process loss would require a separately disclosed
retention design. Test ordinary refresh, pending response, server replacement,
two browsers, two tabs, blocked browser storage, deletion and expired access
again against the exact release before participant admission.

## AWS configuration at launch

1. Verify the workload account, role, region, agreement scope and hosting
   estimate. The owner's $20/month AWS budget is an alert budget. Account for
   compute, storage, backup, edge requests, logs and outbound connectivity.
2. Choose the host and private-origin route. Prefer a CloudFront VPC origin
   with inbound security-group access from the CloudFront service-managed
   group. Verify the public internet cannot reach the application origin.
   Price model-provider egress before selecting a private-subnet topology.
   [AWS VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html).
3. Review and validate `edge-policies.json` with CloudFormation in `us-east-1`.
   The provisional rate settings are 60 invitation redemptions and 1,200 API
   requests per IP per five minutes. They include legitimate shared-network
   traffic and free recovery reads. WAF rate limits are approximate; the
   application enforces the dollar budget. Exercise them before activation.
   [AWS rate-limit caveats](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html). Managed
   Bot Control and interactive challenges require a selected tier, accessible
   behavior and cost review. The common rule group's body-size rule is in
   Count mode because Daylight supports JSON state larger than its 8 KB
   threshold. The application still rejects bodies over 80,000 bytes. WAF's
   configured inspection size can cover only a prefix of the allowed body,
   so server-side schema, authorization and content checks remain necessary.
   [AWS managed rules](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html).
4. Attach the ACL to the actual CloudFront distribution. Set HTTPS-only
   access to the private routes. Use the prepared zero-TTL policy for the
   authenticated app, including API, invite and error responses. Forward
   Host, Origin, CSRF and the reviewed cookies. Confirm the guest cookie name
   when moving from the fictional runtime. Configure the matching certificate
   and canonical hostname. Set CloudFront error-caching minimum TTLs to zero.
   A positive minimum cache TTL can override origin no-store/private headers.
   [AWS cache policy behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-key-understand-cache-policy.html).
5. Keep CloudFront standard/real-time request logs and WAF request sampling
   disabled until the privacy-reviewed logging configuration is verified.
   Retain content-free application access events and security metrics. Bound
   log retention and cost. Confirm the actual logging destinations contain no
   invitation, cookie, CSRF value, private URL, message or health fact.
6. Configure the dedicated OpenAI project and exact permitted model endpoints
   from the verified account agreements and retention settings. Store its key
   in the approved AWS secret store. OpenAI project spend alerts do not stop
   requests; the application ledger must enforce the $100 ceiling. Verify any
   additional account cutoff without treating an alert as a hard cap.
   [OpenAI project budgets](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform).
   Bind every model stage and allowed model to the same cumulative ledger.
   Check the framework's historical budget seeding cannot populate the pilot
   ledger with development charges. Use a dedicated persistent volume and
   retain the ledger through deployment replacement.
7. Set worker and connection bounds, use managed service supervision, enable
   infrastructure auditing, verify least-privilege runtime/admin access, and
   perform an encrypted backup restore. Use one application process until
   visit state and request pacing have a shared multiworker implementation.
   Budget reservations already use a shared transactional ledger.
8. Run fictional probes through the public HTTPS hostname. Verify direct-origin
   rejection, two-guest isolation, private-response cache behavior, expired and
   revoked invitations, CSRF, burst controls, reload while a reply is pending,
   provider outage, budget exhaustion and kill switches. Reconcile usage for
   the exact dedicated provider project and date window. Verify the 90-day
   detailed numeric usage and 12-month aggregate retention jobs on the host.
9. Review the exact release, allowed source purposes, privacy notice, vendor
   settings and incident runbook with the founder before participant admission.
   Use an expiring cohort within the approved pilot scope. A publicly reachable
   hostname still enforces invitations on the server.

## Public access after the pilot

Review the [launch security spec](../../docs/company/LAUNCH_SECURITY_SPEC_2026-11-06.md)
against measured supported completions, abandoned visits, retry cost, peak
traffic and challenges to legitimate users. Select a public dollar ceiling,
session-creation controls and bot settings then. Independent security review,
enforced repository checks and the applicable privacy/source/release gates
remain due before public participant access. A public guest session receives
only specifically released tools and data. Enrollment, outbound contact,
family sharing and paid third-party actions retain their separate authority.

## Operator controls

Run the existing `alternatives/advisor-first/pilot_admin.py` against the exact
persistent cohort directory. Its `usage`, `session-costs` and `reconcile`
commands provide numeric evidence. `switch guest_chat off` and
`switch all_chat off` pause paid work. `revoke` ends a participant's access.
Store issued invitation fragments through the established private delivery
process. Include token-counting, interpretation, composition, recovery and any
future classifier in route and cost review.

For the next launch session, start with this file, CURRENT_STATE and the D141
evidence packet. Re-check the actual running revision, account and outstanding
items before provisioning or admitting participants.
