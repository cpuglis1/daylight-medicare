---
type: review-request
status: draft
updated: 2026-11-11
owner: Chris Puglisi
author: Codex
reviewer: Claude
review_status: pending
source_requirement: D141
---

# AWS migration plan for Claude review

Chris asked Codex to place the full AWS migration plan in the new Daylight Brain for Claude to review. The proposal below is ready for review; it is not approved infrastructure spending or permission to deploy. Claude's review has not run.

## Review request

Review the full proposal below against the current Brain and the repository. Give Chris a concise recommendation, then evidence-backed findings separated into blockers before the invite pilot, work before public access, and optional improvements. For each finding, name the relevant section or source, explain the consequence, and recommend a concrete change. Distinguish implementation facts from assumptions and proposed controls.

Review only. Do not deploy resources, change app behavior, run paid API probes, relax source gates or create duplicate tasks. The planning sheet remains the task tracker. Any later source edits belong in the canonical repository document and should retain their review evidence.

## Current Brain context to apply

- Read [[AGENTS]], [[Decisions]], [[08 Infrastructure and accounts]], [[07 Privacy and security]], [[05 Pilot and validation]] and the relevant entries in [[Open questions]]. Use current owner direction and engineering requirements in their respective scopes.
- **Dates and format:** the Brain records AWS deployment starting November 12, sessions November 17 to December 4, and go/no-go December 5 or 6. Participants use a hosted link on their own devices with Chris present on a video call, using their own real situations and hypothetical 2026 data. The proposal's reference to the older December 23 authorization boundary is not the current session schedule. Align the release plan with C4/C5 and the current readiness gates.
- **Operating model:** Option A is the current owner decision under D143: Chris approves deterministic methods in advance; no mandatory per-case human review. The deterministic engine recommends and the AI explains. Counsel's answer remains pending. Do not interpret the proposal's inventory of review/operations tables as adoption of the superseded Option B model.
- **Transcript retention:** C9 is already open. The engineering implementation remains visit-only, while later pilot materials describe consented sealed transcripts/recordings. Flag this as a release-policy dependency; do not treat this handoff as its resolution or permission to persist chats. Existing pilot guidance says to keep transcript saving off if the sealed store is not ready.
- **Provider route:** C8 is already open regarding the production route and fallback wording. OpenAI is the pilot direction; the proposed fail-closed allowlist does not authorize a fallback provider. Reconcile exact account, model, endpoint and retention settings before release.
- **Money:** retain the single $100 cumulative pilot model allowance. The proposal's roughly $100–300/month hosting envelope is an estimate for review, not a purchase approval. Validate whether a smaller secure pilot topology meets the actual workload and schedule.
- **Related planning-sheet work:** IN-07/IN-11 (hosted deployment), SA-26 (invitations), SA-06 (spending and stop control), HP-07/HP-09 (redaction and logs), HP-08 (sealed transcript dependency), HP-12/HP-13 (notice and consent), PX-02 (2026 research labeling). Use these existing task IDs rather than reproducing the task tracker here.

## Review focus

1. Whether the proposed pilot architecture is the smallest practical secure design, and which dependencies actually block the first session.
2. The unified :8894 hosted UI/API entry point, explicit route permissions, private origin and Linux/data-binding portability.
3. Every paid model stage using the durable cumulative ledger, including retries, uncertain charges, restart and rollback.
4. Data/source rights, exact-build verification, current plan-year limits, guest isolation, consent and retention boundaries.
5. CloudFront cache and timeout behavior, recovery without duplicate calls, health checks that never generate paid replies, and useful alerts.
6. Hosting assumptions and current AWS pricing, especially NAT, database, edge-plan and backup costs.
7. Cutover, rollback, restore evidence, operational ownership and the separation between a research pilot and the public tool.

## Source and status

Canonical proposal: `infrastructure/daylight-pilot/MIGRATION_ANALYSIS.md` in `/Users/cep4u/daylight`. This note contains the complete proposal captured for review. The engineering runbook is `infrastructure/daylight-pilot/README.md`; technical truth remains `docs/project/CURRENT_STATE.md`.

The proposal predates the latest Brain context above. Preserve that distinction when reviewing. Its original engineering content is included below, with heading levels and local source links adapted for this vault. Local file links refer to Chris's Mac; the full proposal is included so it can also be reviewed from Drive. Claude Code should verify implementation claims against the repository. Published AWS/OpenAI source links remain in place.

Source SHA-256: 13491b54593fd71141c10f51b654c2921924a2e8097d9c76a481554d31481c51

## Daylight AWS migration analysis

November 11, 2026. Architecture and execution proposal under D141, based on the current local source and official service documentation. This expands the [launch runbook](file:///Users/cep4u/daylight/infrastructure/daylight-pilot/README.md); it does not authorize purchases, publish the site, change retention or release held recommendations. Recheck service capabilities, prices and source years before the 2027 public launch.

### 1. Recommendation and boundaries

Migrate Daylight in stages: assemble a reproducible application, prove a fictional AWS deployment, migrate and verify the permitted evidence, connect the approved model route and cumulative ledger, then admit the bounded invitation cohort. Use the pilot to choose the public capacity and spending policy.

Keep four boundaries explicit:

1. **Consumer application:** the website, anonymous guest sessions, conversation controller and approved plan displays.
2. **Evidence system:** acquired source files, research PostgreSQL, derivations, release permissions and bounded serving views.
3. **Customer operations:** invitations, permissions, spending, approved saved reports and later decisions/reviews/cases.
4. **Administration and fulfillment:** infrastructure access and any future enrollment or commercial systems. Commercial terms never enter the advisor's selection, ranking, tools or model context.

The preferred AWS direction is CloudFront and WAF in front of a private application origin, PostgreSQL for evidence, S3 for private artifacts/backups, and tightly scoped server-to-provider model calls. Start with **one application process** because visit state, request recovery and some pacing currently live in memory. Horizontal scaling requires a separate state/concurrency migration.

The **$100 is one cumulative pilot model allowance**, with participant attribution and no new daily, hourly or per-person monetary sublimits. The previously reported $20/month AWS budget is an infrastructure alert, not a demonstrated price for this complete architecture. Before provisioning, approve a line-item hosting estimate.

The existing D101 cohort is at most 20 individually invited adults in the approved Collier scope, through December 23, 2026. A later pilot date or broader cohort needs an explicit scope update; the proposed 2027 public launch does not automatically extend that invitation permission. Paid third-party data calls, SMS, enrollment and family/partner access remain disabled in this cohort.

### 2. Current component inventory

| Component | Current implementation | AWS disposition and gap |
| --- | --- | --- |
| Consumer website | Static HTML/CSS/JS in [web-8894](file:///Users/cep4u/daylight/alternatives/advisor-first/web-8894); local Python proxy at :8894 | Package the exact current assets. Initially serve through the authenticated origin; optionally move genuinely public/versioned assets to a private S3 origin with CloudFront access. |
| Advisor API | [server.py](file:///Users/cep4u/daylight/alternatives/advisor-first/server.py), :8893, wraps a hash-pinned engine from the protected chat-first variant | Build a production entry point with a canonical HTTPS origin, bounded request handling, correct frontend and explicit cloud dependencies. Preserve the engine lock. |
| Conversation controller | Natural state, teaching/task memory, interpretation/composition, reviewed rules, factual guards and source gates | Retain these behaviors. Move configuration and dependencies without substituting a generic unrestricted agent. |
| Refresh recovery | Cookie-bound server memory journal plus a minimal tab reference; latest reply/reports, one-hour expiry and capacity bound | Works only while that process retains the visit. Define deployment draining and any later approved persistence separately. |
| Existing optional saved profiles | Variant SQLite store, separate saving and sensitive-saving choices | Do not upload existing local guest stores. Invite-only pilot currently disables durable profile saving. |
| Pilot invitations | [pilot_access.py](file:///Users/cep4u/daylight/alternatives/advisor-first/pilot_access.py), expiry, one-time redemption, revocation and restricted routes | Retain server enforcement; reconcile the allowlist with the actual selected UI and plan APIs. |
| Model spending | [pilot_budget.py](file:///Users/cep4u/daylight/alternatives/advisor-first/pilot_budget.py), transactional reservations, uncertain holds, reconciliation and switches | Keep persistent independent state. Connect every live model stage to this ledger before admission; current hosted pilot is still fixture-only. |
| Provider routing | [model-routes.json](file:///Users/cep4u/daylight/alternatives/advisor-first/model-routes.json), transport allowlist and reviewed pricing | Pilot route names GPT-6.1 Sol, but project/endpoints remain unset. Verify account, model, regional processing and data terms; no automatic provider fallback. |
| MA display | Plans services, catalogs, publication configuration and reviewed-profile receipts | Package exact catalog and authority files together; port only permitted display routes. Missing evidence and recommendation holds remain. |
| Medigap display | D129 exact-profile adapter over a private CSG-derived build | Replace local socket/OS-user wiring with restricted cloud access and a new verified target binding. Preserve ZIP 34101–34108, ages 65–74 and the November 10, 2026 source-date limits until a newer release is reviewed. |
| Part D display | D134 adapter over ten retained 2026 Collier PDP offerings | Port exact build and county/year checks. Published premiums are not personalized drug costs or enrollment confirmation. |
| Identity/comparison research | Private provider/drug candidate and evidence tools | Keep internal routes private. Selecting an identity does not establish network participation, coverage or recommendation authority. |
| Research database | PostgreSQL 18.6; last recorded compact size 29.37 GB; 17.77 million source/context rows and 17.82 million projections | Restore into a new cloud target; prove logical parity and roles. Size is historical measured evidence, not a new inventory of every later import. |
| Evidence archive | Content-addressed files plus source/code/build receipts | Private S3 with verified byte hashes, source rights, retention and read scopes. Archive size must be measured separately from database size. |
| Private data API | FastAPI/uvicorn package, service authentication and bounded read-only queries | Optional private service seam; it does not replace all current direct adapters automatically. Consumer endpoint currently fails closed. |
| Operations database | Separate PostgreSQL schema/package for traces, decisions, review, cases, enrollment and fulfillment | Not connected to the advisor. Wire only needed capabilities after their workflow/retention guards are complete. |
| Acquisition and refresh | Import/build/verify tools; discovery-only release watcher; routine connectors off | Keep outside web requests. Add scheduling only for explicitly permitted sources and reviewed workflows. |
| Delivery and admin | Local launchd/scripts; CI and dependency workflows; partial pilot systemd/Caddy files | Create a clean release artifact, AWS identity, deployment procedure, monitoring, recovery and exact-release acceptance. |

The [research runbook](file:///Users/cep4u/daylight/infrastructure/daylight-data/runbooks/PERSISTENT_LOCAL.md), [operations README](file:///Users/cep4u/daylight/infrastructure/daylight-operations/README.md) and [database readiness review](file:///Users/cep4u/daylight/docs/reviews/ai-native-database-readiness-2026-11-06/README.md) explain the boundaries behind this inventory.

#### Concrete migration blockers found

1. The pilot factory rejects live mode and real repositories; the existing service runs `--fixture`. Its localhost-only egress policy intentionally cannot reach OpenAI.
2. That service serves the reference `web/` frontend. It does not yet deploy the :8894 surface as a unified hosted application.
3. The pilot API allowlist lacks the current `/api/plans/*` display/handoff routes. Adding every local endpoint would expose research capabilities; each selected route needs a specific permission decision and tests.
4. The :8894 proxy accepts loopback HTTP hosts by design. Putting it unchanged behind a public hostname will fail its checks. A production ingress must preserve equivalent protections for the canonical HTTPS origin.
5. Plan adapters construct a Mac Unix-socket connection and use the OS username. Other serving guards bind the cluster identifier, database OID, local marker and archived execution receipts.
6. The fixture service specifies Python 3.11, while the data package requires 3.12+ and some retained builds bind Python 3.14.7 and exact dependency/code hashes. Linux packaging needs explicit compatibility proof.
7. Research serving and operations are not automatically a complete production API. The earlier readiness review found incomplete recommendation prerequisites, enrollment ordering and callback idempotency; these functions remain unavailable until fixed.
8. The archive S3 adapter uses SSE-S3 explicitly and a single-PUT size bound of 5 GiB. It cannot yet satisfy an SSE-KMS-only bucket policy unchanged or upload a larger artifact through that code path.
9. The operations trace table is append-only. The approved 90-day numeric retention needs a separate audited retention mechanism; a scheduled DELETE under the app role will not solve it.
10. The inspected core application, infrastructure and workflow paths are untracked in this checkout's current Git index. This does not establish what another remote checkout contains. A deployable, reviewed clean snapshot must be produced and proven independently of the working Mac.

### 3. Target architecture and hosting choices

~~~mermaid
flowchart TD
    Browser[Browser with guest cookie] --> Edge[CloudFront and WAF]
    Edge --> Static[Optional private S3 public assets]
    Edge --> Origin[Private VPC application origin]
    Origin --> App[One bounded advisor process]
    App --> Guest[Persistent invitations and spending ledger]
    App --> Serving[Restricted evidence adapters]
    Serving --> Research[Research PostgreSQL]
    App --> Provider[Approved OpenAI endpoint]
    App --> Ops[Content-free operations metrics]
    Worker[Separate acquisition and build worker] --> Archive[Private S3 evidence archive]
    Worker --> Stage[New research revision]
    Stage --> Review[Validation and applicable review]
    Review --> Research
    Admin[Founder through temporary AWS role] --> Control[SSM and deployment controls]
    Control --> Origin
~~~

Arrows show permitted communication, not permission to release data. OpenAI is an external processor; hosting Daylight on AWS does not move the existing OpenAI API calls into AWS or authorize a switch to Bedrock.

#### Recommended initial topology

Use a dedicated AWS workload account in us-east-1. Keep the management account for governance/billing. Provision the network structure for separate application and database access, even if the pilot initially uses few resources.

For the invite pilot, compare:

| Option | Advantages | Tradeoffs and conditions |
| --- | --- | --- |
| **Private EC2 application origin, evidence PostgreSQL on a separately protected host or RDS** | Closest to current application; private ingress; easy to keep one process and a persistent ledger volume | Explicit outbound route for model calls; host maintenance; single-process availability; certificate lifecycle if TLS terminates on EC2. Preferred family if the estimate is acceptable. |
| **Private ALB plus EC2/ECS application and RDS** | Managed TLS at the load balancer; clearer path to health-based routing and future multi-instance operation | Higher fixed cost and more components. Adding replicas is still unsafe until application state is shared. Better later operating target or an initial choice with an approved budget. |
| **Restricted public EC2 origin behind CloudFront** | Can avoid NAT/ALB fixed charges for a tiny pilot | A different risk tradeoff requiring deliberate selection: HTTPS only, CloudFront source restrictions plus a secret origin header, reject direct/default-host requests, no public SSH/database. Do not silently substitute this for the preferred private origin. |

CloudFront supports EC2 and load balancers in private subnets as VPC origins. Use its service-managed security group as the source restriction where appropriate. The VPC has specific gateway/address prerequisites; follow the actual deployed service requirements. [AWS VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html).

For a public-origin alternative, CloudFront IP ranges alone are insufficient to distinguish your distribution from another customer's. The secret-header check must be enforced at ingress, withheld from browsers/logs and rotated. [AWS origin restrictions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html).

**Do not start with Kubernetes.** It adds operational work without addressing the current state, authorization or data-binding gaps. Lambda/API Gateway would require redesigning the synchronous HTTP controller, filesystem dependencies and visit memory. ECS is reasonable once there is a portable application image, but ephemeral container storage cannot hold the only invitation or cost ledger.

For the smallest pilot, retaining the tested SQLite invitation/cost stores on encrypted EBS attached to one application host is reasonable. Keep them outside the immutable application release and back them up consistently. Do not put SQLite on a shared network filesystem to simulate a multiwriter database. Before multiple application hosts, migrate those contracts to a tested transactional shared store.

### 4. Website, DNS, TLS and edge behavior

Use one canonical browser origin, for example `https://app.<owned-domain>`, with relative `/api/` URLs. This keeps cookie and CSRF behavior understandable. Choose the actual domain only after ownership and brand/release clearance. Protect the registrar and DNS administrators with strong authentication and recovery controls.

Configure DNS to CloudFront, provision the CloudFront certificate in the required region, and separately configure origin TLS/certificate renewal. A private origin cannot depend on an ordinary public HTTP certificate challenge reaching it. Prefer managed TLS on the selected load balancer or a tested DNS-based certificate renewal flow with narrowly scoped DNS rights.

Initially serve the small authenticated application and API through one origin with caching disabled. Later, move versioned public assets to S3 if that provides a useful reduction in origin traffic. S3 must remain private, with CloudFront Origin Access Control restricted to the intended distribution; use a regular bucket origin rather than a public website endpoint. [AWS S3 origin access](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).

| Traffic | Required behavior |
| --- | --- |
| Versioned CSS, JS, fonts and public images | May be cached once artifact hashes and immutable URLs are established. Never include secrets or source archives. |
| HTML/configuration | Match the deployed API version. Initially no-store; do not freeze stale API contracts in a long-lived cache. |
| Guest/session/invite/API responses | Zero cache TTL, no-store, correct cookies and CSRF/origin forwarding, zero error-cache TTL. |
| Private data, reports or exports | Authenticated per request; no shared edge cache or public object link. |
| Unknown API paths | Explicit rejection, not an HTML single-page-app fallback. |
| Administrative/research endpoints | No public route; require the separate internal identity/network boundary. |

A positive CloudFront minimum TTL can override private/no-store origin headers. The existing zero-TTL policy is a useful preparation artifact, but only the actual distribution behavior proves private responses cannot be replayed across guests. [AWS cache policy behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-key-understand-cache-policy.html).

Retain CSP, MIME sniffing protection, frame restrictions, referrer policy and permissions policy. Configure HSTS after HTTPS and hostname behavior are verified. Avoid ad pixels, session replay and third-party scripts on pages handling personal information.

WAF should cover the distribution with managed common/bad-input protections, allowed methods and separately scoped invitation/API rate controls. The existing 60 redemption and 1,200 API requests per IP per five minutes are provisional settings, not a capacity promise. Test shared household/network traffic and accessibility. The configured body inspection can cover less than the application's allowed 80,000-byte body, so server schema/size/permission checks remain essential. Request sampling/logging stays disabled until a reviewed content-minimal configuration is verified.

### 5. API ingress, calls and timeouts

The API is the enforcement boundary. WAF does not determine whether an invitation is valid, a profile belongs to this guest, a source is approved or a model call fits the budget.

#### Hosted route contract

| Route family | Access and behavior |
| --- | --- |
| `/pilot/join`, `/pilot/redeem` | Minimal join assets; expiry and one-time redemption; no invite secrets in access logs; redemption pacing before expensive work. |
| `/api/guest/session` | Establish or refresh a bounded guest session only within pilot admission rules. Secure, HttpOnly cookie; CSRF token delivered through the controlled same-origin flow. |
| `/api/conversation/initial` | Fresh state, no model call and no automatic exposure of another visit. |
| `/api/conversation/turn` | Validate method, origin, size, CSRF, session, current state, action permission and request identity before execution. Apply budget admission to every paid stage. |
| `/api/conversation/recover`, `/resume` | Free, owner-bound recovery; no resubmission or new AI permission; bounded concurrency and polling. |
| `/api/plans/catalog`, `/workspace`, `/detail`, `/priorities`, `/handoff` | Explicitly decide which capabilities the pilot admits. Preserve receipts, year/location scope, field holds and source authority. |
| `/api/plans/medigap`, `/part-d` | Bounded POST bodies; permitted source build and exact-profile/year checks; no personal facts in URLs or shared cache keys. |
| Profile save/delete routes | Follow the chosen cohort's retention rules. Existing invite-only scope disables durable profile saving; later enabling it requires the complete consent/deletion contract. |
| Identity, comparison and internal evidence routes | Release individually by purpose, never wholesale because they exist locally. Research/private paths stay inaccessible to public guests. |
| Health and admin | Separate minimal health from detailed diagnostics; spending, source internals and account configuration belong behind operator access. |

Support only necessary methods. Reject duplicate or ambiguous framing, unsupported content types, oversize bodies, malformed JSON, surplus fields and wrong-origin requests. Treat forwarded IP/protocol/host headers as untrusted unless inserted by the configured trusted proxy chain.

The present advisor is a standard-library HTTP handler/server, not an ASGI application. It cannot simply be started under Uvicorn or multiplied with Gunicorn workers. Choose and verify a bounded production serving strategy: either a deliberately hardened single-process pilot handler behind the production ingress, or a reviewed ASGI adapter around the existing controller. Prove connection/thread limits, graceful draining, exceptions and timeouts without changing source or permission semantics. The separate private data API is already FastAPI and has its own serving contract.

#### What an actual model request does

The browser sends a deliberate action to Daylight. Daylight authenticates the guest and validates state. Deterministic capture/tool operations run without an LLM where supported. A paid stage reserves a conservative amount, calls only the permitted provider endpoint, validates the result, settles known usage or holds uncertainty, and returns the trusted response. The request ID supports recovery without repeating completed work.

The browser never receives an OpenAI key, a research service token, a database credential or permission to call an arbitrary tool URL. The model never receives infrastructure secrets or broad SQL/shell access.

#### Long replies and lost connections

The current model transport supports bounded waits up to 120 seconds per configured transport call, and a turn can contain multiple stages and a limited recovery attempt. CloudFront's default origin response timeout is 30 seconds. A locally successful turn can therefore fail at the edge unless the full chain is designed and tested. [AWS origin timeouts](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html).

Measure and align browser, edge, ingress, application and provider deadlines with fictional slow-provider fixtures. No proxy or SDK may silently retry a paid POST. Prefer an accepted request ID with authenticated status/result polling if the supported turn duration cannot reliably fit the connection limits. That requires a reviewed API/worker implementation; the existing free recovery endpoint is not a durable job queue.

After a disconnect, retain the original reservation and request identity. If the provider may have processed a call, treat it as uncertain until reconciled. An HTTP timeout does not mean the provider charged nothing. Polling should back off, stop on completion/expiry, pause when unnecessary and never renew paid allowance.

### 6. Guests, persistence and deployment continuity

There are four different kinds of state, and they need different handling:

| State | Current boundary | Migration rule |
| --- | --- | --- |
| Tab reference/page/preferences | Minimal sessionStorage record; no profile or transcript | Keep non-authorizing. A new production domain starts with new cookies and tab storage; localhost visits do not migrate automatically. |
| Active conversation/recovery | Process memory, expiry/capacity bound | One process initially; drain before deploy. Restart survival is not promised. Do not back up RAM transcripts or core dumps. |
| Explicit saved reports | Separate optional consent locally; disabled in current invite pilot | No automatic migration of existing guest stores. If later enabled, use scoped durable storage, expiry, deletion and sensitive-save choices. |
| Invitations, revocations, budget and numeric audit | Durable security/financial control state | Preserve across code deploys. Never reset or replace with a fresh ledger to recover a service. |

Cookies prove possession of this browser's access, not the person's identity. Keep shared-device notices, an explicit separate-visit route, expiry/revocation and an appropriate finish/delete path. Cross-device recovery, household sharing and enrollment identity remain separate features.

For the pilot, maintain one writer/process and bounded request workers. Pause new paid admissions before deployment, wait for active work or record its unresolved reservation, then replace code. Tell users accurately when a visit cannot be restored.

For public operation, decide whether accepted reports must survive host replacement. If yes, implement the approved structured-state persistence before claiming that behavior. Multi-instance transient state could use a shared memory store with explicit TTL and persistence disabled, but that is still a privacy/architecture change needing validation; adding Redis does not by itself preserve authorization, signing-key rotation, request ownership or exactly-once execution.

### 7. Research data and evidence migration

The consumer site does not need to expose the entire research database. It needs the exact permitted data for each released capability, plus enough provenance and authority information to verify it.

#### Inventory and classify first

Produce a manifest separating public-source evidence, licensed CSG evidence, derived serving data, source/code receipts, local guest state, operational records, logs and secrets. Record byte counts, content hashes, year/geography, source permissions, dependency builds and retention. The known 29.37 GB database size excludes the independent archive, backups and later additions.

Do not upload the working repository wholesale. Exclude .env files, private keys, local guest stores, raw conversation logs, personal notes, protected variant stores and irrelevant private archives. The production artifact needs selected code/assets; the evidence transfer needs a separate manifest and authorization.

#### Database destination

Prefer RDS PostgreSQL for the durable production direction, with private networking, encryption, TLS verification, backups and separate reader/migration principals. A small pilot may instead use carefully managed PostgreSQL on EC2 if the owner accepts the maintenance/recovery tradeoff.

RDS currently lists PostgreSQL 18.6 support. Verify availability, instance class, extensions, collations and parameter compatibility in the actual region/account; matching the major version alone is insufficient. Mac-to-Linux migration can affect locale/collation and ordering. [AWS PostgreSQL release history](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/doc-history.html).

Use a logical export/import into a new target for this controlled migration. Do not copy a Mac PostgreSQL data directory to an RDS instance or run old import/resume commands against the compact retained read views. Native PostgreSQL migration is a documented option for whole-database PostgreSQL-to-PostgreSQL transfers; RDS privilege differences require explicit role/ownership mapping. [AWS PostgreSQL import guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Procedural.Importing.html).

#### Migration sequence

1. Select a consistent source snapshot and the exact application/data release. Record any write freeze or ingestion checkpoint.
2. Export schema/data and separately inventory roles, extensions, functions, triggers, grants and external artifacts. Record checksums. Transfer encrypted through the approved operator path.
3. Restore into a new, initially unreachable target. Keep the original database and sealed revisions untouched.
4. Reconcile counts and canonical logical hashes, not just database byte size. Verify original/staged column hashes, source relationships, plan identities and representative bounded queries.
5. Recreate restricted runtime roles. Test denied writes, denied cross-schema access, source STOPs, unknown/held fields and unsupported year/profile cases.
6. Create a **new cloud binding** that identifies the target and its verified inputs. Preserve original local identity receipts; do not erase physical-target checks to make a new host pass.
7. Port each adapter to explicit secret-backed connection configuration and bounded pools. Use TLS certificate/hostname verification and statement/connection timeouts.
8. Run the consumer fixtures against the restored target using the real app role and canonical cloud runtime.
9. Restore again from the cloud backup into a separate target and repeat material checks before retiring any dependency.

A full research restore is the least ambiguous parity target. A smaller serving export can reduce hosting cost, but it must be a new reviewed derivation with complete scope/provenance and all necessary join dependencies. Do not silently discard an uncompensated plan or label a reduced export comprehensive.

#### S3 archive and source updates

Use distinct private buckets/prefixes and roles for evidence, customer backups, release artifacts and audit logs. Block public access. Enforce TLS, chosen encryption and ownership settings. Verify downloaded bytes against the original hash; multipart ETags are not a substitute for the evidence hash.

The existing S3 archive class must be adapted if choosing an SSE-KMS-only policy or multipart artifacts. It currently requests SSE-S3 explicitly and rejects objects above its single-PUT bound. Add encryption/multipart behavior with exact round-trip checks instead of assuming a bucket default changes the request.

Use versioning and, where appropriate, immutability for sealed evidence. Set retention deliberately; applying indefinite object lock to personal backups would conflict with future deletion promises. APFS clone savings on the Mac do not automatically carry over to S3/EBS byte accounting.

Separate discovery, acquisition, transformation, validation, review and publication. The current release watcher discovers candidate links only and routine network connectors are disabled. A future scheduled worker may record a new candidate; it must not overwrite a sealed build or publish unreviewed 2027 information.

### 8. LLM security, authority and the cumulative budget

Keep the current reviewed model choice during infrastructure migration. The inspected configuration names GPT-6.1 Sol for the pilot; development alternatives do not become production fallbacks. Model changes belong in their own evaluation and route/pricing review.

#### Provider controls

Use a dedicated pilot project and scoped server key, delivered from the approved AWS secret store to the application role. Keep development, test and production usage separate. Verify the exact model, Responses and token-counting endpoints, processing region, applicable agreements and effective account settings.

API training use, application-state storage, abuse-monitoring retention and regional processing are different controls. `store:false` alone does not establish zero retention. Check the applicable endpoint/model behavior and the provisioned project settings rather than inferring them from the AWS region. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

The router must fail closed if the endpoint, project, model, pricing review or permission is missing. Preserve the transport's verified TLS, no redirects, constrained request schema and refusal of provider-hosted tools/state features that have not been approved. Do not silently switch to Anthropic, another region or a hosted agent service on outage.

#### Admission and accounting

For every stage that can incur a charge:

1. Check invitation/session validity, current request ownership, appropriate AI permission and the applicable kill switch.
2. Determine the conservative reservation from the actual model's reviewed pricing and bounded work, including allowed retry/repair paths and relevant cache-write charges.
3. In one transaction, admit only if settled spend plus outstanding reservations plus the new reservation remains within $100.
4. Reserve before the outbound call; record stage/attempt identity so an identical request cannot execute twice.
5. Settle using actual provider usage when known. Keep the conservative hold when an interruption leaves billing uncertain.
6. Reconcile against the dedicated provider project's matching date window. Missing accounting or integrity failure blocks new paid work.

The ledger, invitations, revocations and operation identities survive application replacement. Never reseed the pilot from development history and never restore an older ledger into active service without accounting reconciliation. A backup may omit spending that happened after it was taken; keep paid work off until the missing period is conservatively covered.

The best-effort operations trace wrapper is useful telemetry but cannot be the spending control: it deliberately lets a turn continue after a trace-write failure. The admission ledger must fail closed independently.

Keep both guest-chat and all-chat switches operable through the private operator path. At the cap, supported deterministic browsing and already-completed recovery can continue subject to normal permissions. A stolen provider key can bypass application accounting, so scoped secrets, key rotation/revocation, provider limits and usage alerts remain necessary defense layers.

#### Model and tool attacks

| Risk | Required application control |
| --- | --- |
| A message/document says to ignore instructions | Treat external content as data. Software decides permissions and source authority; prompts are not the security boundary. |
| Cross-guest leakage | Bind every profile, result, receipt, cache and request ID to the current guest/subject; test foreign and stale IDs. |
| Model requests an unapproved action | Fixed tool registry and strict schemas; allowlisted arguments, row/output limits and current-purpose receipts. No arbitrary SQL, shell, browser or URL tool. |
| Source content tries to exfiltrate information | No automatic URL following from model output; block metadata/private-network destinations and recheck redirects on permitted fetches. |
| Fabricated plan facts or recommendation | Keep source/method/release gates and structured validation; an LLM cannot declare its own evidence accepted. |
| Output injects code into the website | Render model text safely; do not interpret it as HTML, executable Markdown or script. Validate any allowed links. |
| Resource exhaustion | Bound body sizes, concurrency, tool result rows, output tokens, transport deadlines and retries; apply actual model-cost reservations. |
| Paid action or outreach | Separate explicit authorization for the exact action/content/recipient. No enrollment, SMS, email or partner callback is enabled merely by migrating. |

Commercial metadata stays outside the research/decision context and model inputs. Cloud IAM roles and database grants should preserve that separation, not depend solely on a prompt instruction.

#### Cost reduction in priority order

1. Keep refresh/recovery, navigation, supported structured operations and local source lookup free of model generation.
2. Preserve idempotency and reuse the completed response after a lost connection. Avoid duplicated extraction/composition and uncontrolled fallback loops.
3. Send the minimum current facts and source-backed context. Keep existing context compaction and output limits; measure whether a change increases repairs or abandoned visits.
4. Stabilize shared prompt material and evaluate caching on the selected model. Current caching requires a matching prefix and eligible cache boundaries; measure writes, reads and retention implications rather than assuming a repeated instruction block is automatically cheap. [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
5. Use deterministic tool results and versioned evidence caches with the exact source/profile/date key. Never share personalized generated answers across guests.
6. Evaluate a cheaper model or narrower stage only after fictional accuracy, repair cost and completion checks. A lower token price can produce a higher cost per successful task.
7. Use offline batch processing only for appropriately approved research work; it is not the live conversation path and must preserve source/retention gates.

Track settled cost, unresolved holds, uncached/cache-write/cache-read usage where applicable, output usage, stage, attempt, latency and outcome. Report total model spend divided by supported completions, including abandoned visits in the numerator. A 20-person pilot cannot establish a reliable p99 cost or broad security false-positive rate.

### 9. AWS account, network and operational security

Consumer login-free access does not mean administrator access is anonymous. Founder, deployment, app, data-worker, backup and reviewer identities need distinct permissions.

| Identity | Needed access | Explicit exclusion |
| --- | --- | --- |
| Founder/admin | Temporary AWS role, approved deployment and incident controls | Routine root use and credentials pasted into chat or source |
| Deployment role | Exact release resources/artifacts and required service updates | Unrestricted account administration or routine access to customer contents |
| Application role | Its secret, approved data reads, necessary operational writes | Source acceptance changes, raw archive-wide access, commercial records, role-policy changes |
| Data acquisition/build worker | Permitted source access and new staging revisions | Publishing its own output or reading customer visits |
| Migration role | Time-bounded schema/data import and grant setup | Continued use by the running app |
| Backup/retention operator | Named backup and expiry operations with audit evidence | Arbitrary live profile changes or spending resets |
| Future reviewer/fulfillment | Exact separately authorized workflow | Commercial access influencing consumer decisions |

Require strong MFA/passkeys and recovery for AWS, GitHub, domain and provider administration. Verify the actual workload account, region controls, agreement scope and budget coverage. Use short-lived roles for administration and workload roles for applications; do not put static AWS access keys into the image.

Private database security groups admit only named application/data roles' network paths. Do not expose PostgreSQL, internal evidence APIs, metrics ports or operator CLIs to the internet. Keep runtime processes non-root, root filesystems/read-only mounts where possible, bounded resources and minimal installed tools. Require IMDSv2 on EC2, limit metadata access and prevent URL-fetch features from reaching it.

Use SSM for host administration instead of an open SSH port. SSM still needs its agent, IAM permissions and outbound connectivity or relevant private endpoints; private networking is not operational until these paths are tested. [AWS Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html).

A NAT gateway enables outbound connectivity; it does not enforce a hostname allowlist. Security groups also do not directly express an OpenAI domain allowlist. Preserve the application's exact route validation and, if the risk/cost warrants it, add a controlled egress proxy or firewall. Separate runtime model access from broader source-acquisition access.

Encrypt databases, EBS volumes, backups and appropriate S3 objects. Separate key permissions from ordinary data access. Plan key rotation and recovery before changing or deleting a key; a correct backup is useless without its decrypt capability.

Use CloudTrail for account/control-plane audit, content-free application events and selected threat/configuration monitoring. Scope paid monitoring products and data events deliberately. Control-plane auditing does not require recording health-related request bodies.

Verify applicable agreements and the eligibility/configuration of every service handling covered data, including edge, logs and backups. An eligible AWS service is not proof that the entire application meets its obligations. Apply Daylight's existing privacy/legal launch gates to the exact pilot use; counsel resolves legal applicability and operating permissions. [AWS eligible services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/).

### 10. API pings, health checks and monitoring

Distinguish availability checks, a real user request, data-refresh polling and provider billing reconciliation. They have different permissions and costs.

| Check | Proposed cadence | What it proves | Must not do |
| --- | --- | --- | --- |
| Local process liveness | Every 30–60 seconds | Process/event loop answers a minimal request | Query personal records or invoke an LLM |
| Internal readiness | Every 30–60 seconds, bounded | Required data connection, release binding and ledger are usable | Reveal credentials, source rows or detailed diagnostics publicly |
| External HTTPS availability | Every 1–5 minutes from a small number of locations | DNS/TLS/edge/ingress and coarse service availability | Create ongoing participant sessions or send paid messages |
| Browser synthetic smoke | On deployment and a reviewed periodic schedule | Assets load, join boundary works, deterministic fictional flow remains usable | Use real people or silently spend the pilot allowance |
| In-flight result polling | Only while a user has outstanding work, bounded/backoff | The submitted request's state/result | Resubmit the model request |
| Provider health | Observe real request outcomes and approved status information | Errors/latency for the selected route | Generate a completion every minute just to test connectivity |
| Cost reconciliation | Regularly during the pilot and after uncertainty/restore | Provider totals and ledger agree for the same window | Clear unresolved holds because an invoice is rounded or delayed |
| Source freshness | Per source's approved update schedule | Selected evidence's age and a possible new candidate | Automatically publish a newly discovered source |
| Backup/retention job | Proposed daily checks plus periodic restores | Recent backup, successful expiry and usable recovery | Treat job exit code alone as restored-service proof |

Cadences are engineering proposals to tune against cost and observed behavior. Add dedicated minimal liveness/readiness routes if necessary; the present `/api/status` includes more operational information than a public health endpoint should expose. The private data API already distinguishes a minimal `/health` from authenticated `/ready`.

Monitor request rate, 4xx/5xx categories, queue/concurrency pressure, latency, rejected invitations, authorization failures, recovery failures, worker crashes, disk/memory, database connections, backup age, certificate expiry, source freshness, ledger holds and remaining model allowance.

Use actionable alerts: repeated external failures, authorization/cache isolation failure, ledger integrity error, unresolved billing, excessive denials, missing backup and source STOP/freshness failures. Define the recipient and response. An alarm that nobody receives is not an operating control.

Default logs to allowlisted event names, route categories, status, duration, stage/model and numeric usage. Exclude prompts/replies, cookies, CSRF values, invite tokens, personal URL parameters and medication/provider details. Bound metric cardinality; do not use raw participant IDs or free text as metric dimensions. Treat pseudonymous references as protected operational data.

The approved policy is 90 days for detailed numeric usage and 12 months for non-identifying cohort totals. Implement and verify expiry in the actual database/log stores. Resolve append-only table behavior through a reviewed retention-role/partition design. Infrastructure log retention requires its own explicit configuration.

### 11. Backups, recovery and incidents

Back up each kind of data according to its authority and recovery need:

- **Evidence:** exact source bytes, derivation code, manifests, source permissions, release selection and STOP records. Preserve a verified prior release.
- **Pilot control state:** invitations, revocations, settled costs, reservations, reconciliation and switches. Use a consistent database backup, not a live SQLite file copy that ignores its journal/WAL.
- **Permitted customer records:** only what the selected consent policy authorizes; encrypted backups with an explicit expiry/deletion approach.
- **Deployment:** exact application artifact, dependency locks, configuration versions, infrastructure definition and key/secret references. Do not embed secret values in a release manifest.

Set recovery objectives before launch. A reasonable discussion starting point is a four-hour service recovery target and a 15-minute maximum loss window for permitted operational/customer writes, subject to actual architecture and backup capability. These are proposed objectives, not measured promises. Evidence should reproduce the selected accepted revision exactly. Model spend after a backup cannot simply be lost: restore into paid-off mode and reconcile it before continuing.

Restore to a new environment, prove integrity and permissions, reapply deletion/revocation records as needed, then enable traffic deliberately. Test expired sessions and signing-key rotation as part of recovery. Restoring an old application version must not undo a source STOP, reopen a revoked invitation or restore spent allowance.

Maintain a short incident playbook for compromised credentials, unauthorized access, suspected private-response caching, provider outage, source withdrawal, unexpected spending and failed restore. It should identify who pauses admissions/model calls, who rotates credentials, how evidence is preserved without copying private chats, and how applicable notification obligations are assessed.

Planned deployments use a drain/maintenance procedure for the single-process pilot. Code rollback points to a compatible previous application/data release while retaining the current security and spending state. Database changes need forward/backward compatibility or an explicit maintenance migration; blindly reverting a schema against newer writes is not a rollback plan.

### 12. Packaging, CI and deployment

Create an allowlisted Linux release bundle or OCI image. Include the exact frontend, advisor modules, pinned engine dependencies, selected policy/rule/authority files and required data adapters. Keep protected services/stores on the Mac unchanged. Do not rely on an untracked local path happening to exist.

Pin the Python/dependency/runtime and curl/CA environment. Test the selected CPU architecture; ARM pricing savings are only useful if native libraries and data bindings work. Package secrets separately through runtime configuration. Retain the original sealed code artifacts when a new platform build needs a new authority binding.

The existing repository and dependency workflows are a starting point. Add cloud-package construction, route-matrix tests, Linux compatibility, privacy fixtures, ledger concurrency/restart tests and infrastructure policy checks to the exact release pipeline. Preserve hashes and test evidence after short-lived CI artifacts expire.

Deploy a reviewed immutable artifact, not a mutable working directory or latest-tag image. Give the workflow temporary AWS credentials through a narrowly scoped OIDC trust if selected; restrict the repository and intended branch/environment identity, and keep ordinary pull-request jobs away from production secrets. [AWS GitHub OIDC trust guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).

Keep the approved private-GitHub-Free manual review exception limited to the pilot. Before public access, establish the required enforced checks/review and independent reviewer. A passing local test count is not release approval.

Use infrastructure as code for network, origin, WAF/cache behavior, roles, secret references, stores, logs and alarms. The current `edge-policies.json` creates policies only; it is not a complete VPC, application, database, distribution or deployment stack. Generate and review the actual change set and price estimate before applying it.

### 13. Cost analysis

#### Three separate cost categories

1. **Pilot model calls:** one $100 cumulative allowance enforced by the application ledger. Per-person usage is measured, not a new entitlement or sublimit.
2. **Hosting and operations:** recurring AWS compute, database, disk, backup, networking, edge, keys/secrets, logs and monitoring.
3. **Other integrations/business costs:** licensed data, future messages/enrollment services, domain registration, CI, legal/security review and staff time. Do not imply these fit inside the model cap.

If all 20 invitees participate, $100 corresponds arithmetically to $5 average model spend per person. Actual use may be uneven; this is not a per-person limit or forecast. Measure completed and abandoned visits before changing the allowance.

#### Verified pricing facts that affect the design

AWS currently lists CloudFront flat-rate Free, Pro, Business and Premium at $0, $15, $200 and $1,000 per distribution/month. Its comparison places private VPC origins and custom caching rules in Business/Premium. Therefore do not choose a free/Pro plan assuming it supports this design's private-origin and custom-cache requirements. Compare pay-as-you-go against the actual required features. These are current published prices, not a 2027 guarantee. [CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/).

At the published example rate of $0.045 per hour, one NAT gateway/AZ is about **$32.85 per 730-hour month before data processing and other charges**. Private outbound access can therefore exceed the existing $20 hosting alert by itself. Add public-address, traffic and endpoint charges where applicable. [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

At the published US-East example rate of $0.0225 per hour, an ALB's base charge is about **$16.43 per 730-hour month**, before capacity/traffic charges. [AWS load-balancer pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

Standard WAF examples charge $5 per ACL/month plus $1 per rule/rule-group attachment and request charges. The prepared five-rule layout suggests roughly a $10/month basic fixed component before request volume, capacity/body-inspection increments and optional bot/challenge products. Validate the exact rule accounting and plan before purchase. [AWS WAF pricing](https://aws.amazon.com/waf/pricing/).

#### Planning envelope

These are deliberately broad **engineering allowances**, not AWS quotes or approved spending. Assumptions: one region, low pilot traffic, one application instance, a modest single-AZ evidence database, one outbound path, limited logs and selected archives.

| Component | Illustrative monthly allowance | Main uncertainty |
| --- | --- | --- |
| App compute | $15–50 | RAM/CPU needed by the real package and concurrency |
| Evidence database and working storage | $30–120 | RDS class versus self-managed host, dataset/working-set size and I/O |
| Ledger disk and backup storage | $5–20 | Backup frequency, retention and selected data volume |
| Private outbound networking | $35–55 | NAT/address/processing and necessary endpoints |
| Pay-as-you-go edge/WAF/DNS | $10–25 | Requests, exact rules and transfer |
| Secrets/keys/logs/monitoring | $5–25 | Selected services, event volume and retention |
| Optional ALB | Add $17–30 | Capacity and routing needs |

This points to an order-of-magnitude **$100–300/month private pilot hosting envelope**, with a priced configuration still required. Full archives, separate database instances, multiple AZs, independent staging, security products, support, tax and higher traffic can move it above that. A leaner restricted public-origin/self-managed-database pilot may cost less, but trades away managed operations/private ingress; benchmark and price it separately.

Do not assume credits/free tiers, S3 storage credits or the physical database size make the full service fit under $20. Avoid a NAT gateway per AZ, always-on staging, verbose request logs and paid Bot Control tiers by default. Keep durable security/backup requirements when reducing infrastructure.

AWS Budgets can alert on actual/forecast costs, but billing/notification delay means charges may exceed the threshold before action. The $20 alert is not an account-wide hard stop. [AWS Budgets behavior](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

### 14. Execution sequence and acceptance evidence

| Phase | Work | Evidence needed to leave the phase |
| --- | --- | --- |
| 1. Release and scope inventory | Freeze selected app/data versions; enumerate routes, permissions, dependencies, source rights and excluded files; choose pilot persistence limits | Reviewed manifest and route matrix; clean checkout/package reproduces the selected behavior |
| 2. Local cloud-readiness work | Unified hosted :8894 entry point, live-pilot ledger seam, production origin handling, explicit DB configuration, portable bindings, bounded HTTP execution | Fictional/offline tests prove isolation, state recovery, model routing and budget invariants on the target runtime |
| 3. Account and architecture | Verify workload identity, region, agreements, domain and administrative access; select topology and cost estimate | Non-secret account/configuration evidence, reviewed infrastructure change set and approved spend |
| 4. AWS fictional rehearsal | Deploy network, edge, certificate, origin, secrets references, logs/alarms and isolated stores with model calls disconnected | HTTPS route/cache/origin tests, resource permissions, alerts and successful fictional journey |
| 5. Evidence migration | Restore selected data and archives into new targets; prove hashes/roles/bindings and source limits | Full migration receipts, app-role reads, STOP/denial tests and off-machine restore |
| 6. Live route preparation | Bind the actual covered project/endpoints and model pricing; connect all paid stages to persistent $100 control state | Fail-closed configuration tests, fictional exhaustion/concurrency/retry tests and operator switch/reconciliation drills |
| 7. Pilot release review | Inspect exact app/data/infra revision, consent/copy, legal/source gates and support readiness | Founder accepts the specific release before invitations are issued; any real-model quality testing follows the existing owner-controlled rule |
| 8. Small invite rollout | Admit a small initial group within the approved cohort; observe usage, failures, supported completion and participant feedback | Daily operational/cost review, incident response capability and evidence for further invitations |
| 9. Public-readiness work | 2027 evidence release, revised guest/bot controls and budget, shared state/scaling if needed, independent security review | Explicit public release decision with new scope/cost limits and verified capacity/recovery |

Phases 1–2 can proceed locally. Phases 3–7 require the actual account, chosen deployment and some founder/provider evidence. Data/cloud migration and public recommendation acceptance are separate workstreams; moving a database cannot satisfy a source or recommendation review.

#### Deployment acceptance matrix

| Scenario | Required observation |
| --- | --- |
| Direct origin, wrong Host and forged proxy headers | Rejected before private application access |
| Guest B requests guest A's result/profile/receipt | No content or authority leakage |
| Expired/redeemed/revoked invite and new-cookie attempts | Pilot admission remains enforced; no allowance reset |
| Cached successful/error/Set-Cookie response | No guest receives another guest's data, even across edge locations |
| Refresh during pending/completed work | Free recovery or accurate expiry; no duplicate model charge |
| Network/provider timeout, retry and process crash | Bounded attempts, retained uncertainty and no overspend |
| Concurrent requests near $100 | Transactions refuse work exceeding settled-plus-reserved allowance |
| Restored older database or code rollback | Paid-off until reconciliation; current revocations/STOPs preserved |
| Missing/stale/mismatched source revision | Affected capability fails closed with useful user-visible limits |
| Wrong year, unsupported Medigap age/ZIP, incomplete drug/provider evidence | No invented facts or widened eligibility/recommendation claims |
| Privacy canaries in requests, errors and logs | No private values enter unapproved logs, URLs, metrics or caches |
| Oversize/ambiguous request, burst and slow connection | Bounded resources, rejection and useful retry behavior |
| Backup restored on a new host | Verified bytes/data/roles, functioning app and measured recovery time |
| Operator receives an alert and stops paid work | Actual delivery and control effect, without disabling free authorized recovery |
| Desktop/tablet/phone on public HTTPS | Complete fictional flow, readable errors and accessible invitation/challenge behavior |

### 15. What changes before the 2027 public launch

Revisit source years, plan identities, benefit grids, restrictions, rates and freshness. The current 2026 schema/API assumptions, ten PDP offerings and dated Medigap prices do not become current by changing a heading or calendar setting. Preserve the old evidence and create reviewed 2027 releases.

Replace invitation issuance with a deliberately designed anonymous session-admission policy only when approved. Combine edge automation controls, application concurrency/pacing, tool limits and the newly approved global spending policy. Clearing cookies must not grant unlimited paid access. Keep legitimate shared-network users and assistive technology in the evaluation.

Before increasing replicas, externalize the required session/request/permission state, use a shared transactional spending ledger and test race/crash behavior. Add managed queue/worker components only where the asynchronous contract needs them. Choose multi-AZ recovery according to the service objectives and approved costs.

Future enrollment, partner/MCP access, family sharing and outbound contact require their own authenticated principals, scoped permissions and exact-action receipts. Enrollment callbacks need signed/replay-resistant verification, idempotent event handling and valid state transitions; the current operations prototype does not yet supply all of that. Do not expose it simply because a webhook URL is reachable.

Complete enforced repository review, independent security review, operational ownership and the applicable privacy/source/recommendation release gates. Public availability and permission to provide personalized recommendations remain distinct.

### 16. Immediate engineering backlog and review status

The next useful implementation package is:

1. A cloud-runtime specification and one hosted entry point serving the current :8894 application.
2. An explicit admitted-route matrix, with negative tests for every excluded research/admin capability.
3. A live-provider adapter bound to the tested cumulative pilot ledger, preserving reservations across restarts.
4. Secret-backed database configuration and new target bindings for MA, Medigap, PDP and any admitted identity reads.
5. A reproducible Linux artifact with exact code/data/authority manifests.
6. A full infrastructure proposal and line-item estimate, including egress and certificate renewal.
7. A fictional deployment/restore/incident acceptance packet.

The owner inputs needed before deployment are the workload account/temporary role, selected hostname, acceptable recurring hosting estimate, verified provider project/settings and final cohort/release approval. No consumer login is required by this plan.

This analysis inspected source/configuration/runbooks and current official documentation. It made documentation changes only: no service restart, AWS login/resource creation, data transfer, live conversation test or paid probe. Earlier local test results remain in the [D141 evidence packet](file:///Users/cep4u/daylight/audit-evidence/guest-resume-security-20261111/README.md); they were not rerun for this analysis. Exact AWS quotas, costs, permissions and deployed behavior remain to be established in the chosen account.

