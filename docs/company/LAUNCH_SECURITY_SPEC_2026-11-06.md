# Daylight launch security and abuse-prevention spec

**November 18, D185.** The initial hosted demo uses $2 per redeemed invitation and $20 cumulative across online messaging. These limits supersede D99/D141 figures wherever they occur below for this deployment. Use one authoritative spend ledger across every enabled paid path. [Current release plan](../../infrastructure/daylight-pilot/DOMAIN_LAUNCH.md).


Owner direction · November 6, 2026 · Read with the [AI-native brokerage plan](AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md), [CURRENT_STATE](../project/CURRENT_STATE.md) and the [AI-native database readiness review](../reviews/ai-native-database-readiness-2026-11-06/README.md) (actions A05, A07 and A10). D141 authorizes local security implementation and AWS launch preparation. This specification records the controls and the deployed evidence still required. The legal sections describe the issues to resolve with counsel; they are not legal advice.

## 1. Owner direction and design constraints

1. **Login-free consumer tool.** D140–D141 keep the demo and later public advisor usable without an account. Same-browser progress uses a guest cookie. Enrollment and any future cross-device recovery need their own identity and permission design.
2. **One pilot allowance.** D99 and D141 set one $100 cumulative model budget across the invite-only pilot. Track each participant's usage. Re-evaluate the allowance and public controls after observing the pilot.
3. **AWS edge.** D141 selects CloudFront and AWS WAF. The backend validates invitations, sessions, permissions and spending on every applicable request.
4. **Bounded LLM authority.** Server code validates the model's proposed facts and actions against approved tools, evidence and permissions.
5. **Useful progress survives interruptions.** Free recovery reads restore trusted current visit state. An AI pause leaves the supported guide and published reference capabilities available under their existing source and access gates.

## 2. Threat model

| # | Threat | What it costs Daylight | Primary controls |
|---|---|---|---|
| T1 | Scripted chat flooding to run up model spend | Model bill, degraded service for real users | Edge bot gate, signed session tokens, pacing, global ceilings (§3) |
| T2 | Using Daylight as a free general-purpose chatbot | Model bill, reputational risk from off-topic output | Software scope check, service-area gate, per-message limits (§3.8) |
| T3 | Abuse of paid actions: SMS pumping, paid rate APIs, enrollment-platform calls | Direct per-message and per-call charges | Email-first verification, SMS protections, caching, checkout-only rails (§3.9) |
| T4 | Prompt injection, from user text, extracted plan documents, and later partner or MCP callers | Wrong or manipulated recommendations, data exposure, unauthorized actions | Two-stage controller, typed tools with software authorization, output treated as untrusted (§6.6) |
| T5 | One session or account reading another's data (IDOR) | Health-data breach, notification duties | Object-level authorization, row-level security, two-beneficiary tests (§6.2) |
| T6 | Health data leaking through logs, traces, analytics or vendors | Breach, FTC and state exposure | Content-free traces, no third-party trackers, vendor register with BAAs (§5) |
| T7 | Account takeover after checkout verification | Access to a beneficiary's profile and enrollment | Short-lived single-use magic links, step-up for enrollment, session binding (§6.1) |
| T8 | Enrollment fraud: someone enrolling another person, or changing their plan | Harm to the beneficiary, carrier and CMS consequences | Identity confirmation at checkout, licensed review (Option B), enrollment as a separate permission (§6.1) |
| T9 | Impersonation of Daylight in scams aimed at seniors | Harm to users, brand damage | Email authentication, published "what we never ask" policy, monitoring (§6.8) |
| T10 | Commission or acquisition data leaking into model context | Loss of independence, a compliance failure | Existing structural boundary (`dl_fulfillment`), serialized-request canaries (A07) |
| T11 | Infrastructure attacks: DDoS, leaked credentials, compromised dependencies | Outage, breach | Edge protection, secret management, MFA, supply-chain controls (§6) |
| T12 | Insider or reviewer over-access | Unnecessary exposure of health data | Least privilege, queue-scoped reviewer access, access audit log (§6.3) |

## 3. Abuse and cost controls without early verification

### 3.1 Edge gate

Use CloudFront with AWS WAF in the approved AWS workload account. Prefer a VPC origin so the backend has private network access through CloudFront. Bind the host, TLS certificate, security groups and outbound model route when the actual host is selected. Evaluate egress and hosting costs against the owner's hosting budget at that point.

The prepared [edge policy template](../../infrastructure/daylight-pilot/edge-policies.json) provides WAF request pacing, managed rule groups, disabled request sampling and a zero-TTL cache policy. The distribution must attach the web ACL and apply the zero-TTL policy to every authenticated or personalized response, including errors and Set-Cookie responses. Forward the exact guest cookies, Origin and CSRF headers. Verify direct-origin rejection and two-browser isolation on the deployed distribution. CloudFront can cache a private response when a policy has a positive minimum TTL, even if the origin sends no-store. [AWS cache policy](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-key-understand-cache-policy.html).

The template's per-IP request rates are provisional engineering values. Check legitimate shared-network use with fictional traffic before activation. Any challenge or paid Bot Control feature needs an accessible path and its actual privacy and cost settings reviewed at launch. AWS WAF evaluates rate rules periodically, so the application maintains its own immediate paid-call controls. [AWS rate rules](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-wafv2-webacl-ratebasedstatement.html).

### 3.2 Session token and refresh

Use an opaque guest cookie with Secure, HttpOnly and SameSite attributes on the deployed HTTPS origin. Validate its expiry and server-side ownership for every private read and write. Keep authorization cookies out of browser-readable storage and URLs.

D141's local refresh recovery stores only request references, saving-choice booleans, a page identifier and an expiry in sessionStorage. The server reads its existing visit journal using the authenticated owner. It returns the current trusted response, rechecks action/evidence authority and grants no AI permission. The journal remains in process memory with its existing one-hour expiry and capacity bounds. Restart, expiry, deletion and eviction can end recovery. Longer-lived saved reports retain their explicit save and sensitive-save choices. The invite-only pilot still disables durable saved profiles.

Same-tab refresh reopens accepted reports and the latest reply. Earlier displayed chat and unsent drafts remain outside browser persistence. A draft or active send triggers the browser's leave-page warning where supported. A later tab restore presents a Resume choice. Browser possession establishes access to a guest visit, so the shared-device notice remains necessary.

### 3.3 Pilot allowance and public re-evaluation

One $100 cumulative pilot model allowance covers all participants, stages, providers, retries and unresolved charges. Reserve conservative cost before a paid call, settle verified usage and retain ambiguous charges until reconciled. Restart, midnight, renewed cookies and replacement invitations retain the same cumulative ledger. Per-participant usage is reporting. Public dollar limits will be decided after the pilot.

### 3.4 Request pacing

Apply the existing three-second minimum gap, ten AI-capable turns per minute and one in-flight turn per participant. Bind pacing to the validated invitation so renewing a browser session does not reset it. Apply the gate to deliberate choice answers that request AI composition as well as free-text messages. Read-only resume/recovery calls use separate bounded server slots and never submit a model request.

At the HTTP boundary validate Host, Origin, Sec-Fetch-Site, method and route. Bound request bodies before reading them, reject ambiguous framing and use read timeouts. Review total connection and worker limits on the actual hosted service.

### 3.5 Public abuse controls

Before public access, exercise managed bot controls, session creation limits, request pacing and a global model-spend ceiling together. Measure challenges and denials for ordinary users, including shared networks and assistive tools. Choose the public controls from observed traffic and attack rehearsal. Device fingerprinting, proof-of-work, fixed trust scores and an extra LLM classifier are optional designs that require evidence and a privacy review before adoption.

### 3.6 Content-free measurement

Use the approved numeric usage fields for cost, token counts, retries, outcomes and latency. Keep detailed numeric usage for 90 days and non-identifying cohort totals for 12 months under D101. Infrastructure request logs and sampling need their own retention and redaction settings. An allowlisted event name, route category, status and timestamp are sufficient for the current pilot access log.

### 3.7 Global ceiling and kill switches

D99 and D141 approve one $100 cumulative pilot model ceiling. The existing isolated ledger enforces conservative reservations across concurrent participants. Every production model route must bind to this ledger before participant admission. OpenAI project spend alerts do not stop requests, so the application ledger enforces this cap. Verify any additional account cutoff and retain AWS billing alerts for infrastructure costs. [OpenAI project budgets](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform).

The guest-chat and all-chat switches pause paid composition. The paid-features switch controls any later approved paid integration. Supported deterministic capabilities retain their normal access and evidence gates. Stop admitting paid work when ledger integrity fails, accounting is unresolved beyond an approved reservation, or a required route/vendor setting is missing. A provider's calendar budget does not replace the cumulative pilot ledger.

### 3.8 Scope and cost efficiency

Keep the advisor within its reviewed Medicare capabilities. Apply service-area and coverage-year limits to the capabilities they actually constrain, while allowing useful general education before consequential intake. Evaluate a rule-based scope screen before adding a paid classifier. Any classifier, summarizer or fallback must use the approved provider route and count against the same budget.

Reuse deterministic answers, approved data tools and existing context compaction. Prompt caching requires model-specific billing and retention review. Compare cheaper models on fictional accuracy and completion checks before routing real traffic. Keep the existing reviewed request/output limits and bounded recovery attempts. Refresh, browsing, saving and supported structured operations stay free of model calls unless the person deliberately requests AI. Recover a completed reply after disconnect without generating it again.

### 3.9 Paid actions

- **SMS pumping** is the classic way to run up a bill: bots trigger verification texts to premium-rate numbers and Daylight pays for each one.
  - Prefer email magic links. Offer SMS only at checkout.
  - Require a passed bot check and a valid session token before any text is sent.
  - Use Twilio Verify with its fraud protection on, US numbers only, and limits per number, per session and per network.
  - Kill switch 3 can turn SMS off on its own.
- **Medigap rate API and other paid data.** These are needed before checkout for the coverage-path decision, so they cannot wait for verification. Instead:
  - call them only once the profile has the minimum facts the quote needs;
  - cache results by exact supported quote profile, source revision and effective date, so most calls are cache hits;
  - charge each uncached call against the session allowance;
  - limit calls per session.
- **Enrollment-platform calls and any outbound action** (sending, enrolling, contacting a plan or person) happen only after checkout verification and with the separate enrollment or action permission. No guest session triggers them.

## 4. Pilot measurement and public re-evaluation

Collect actual model cost for completed and incomplete visits within the single $100 allowance. Report participant count, supported completions, median and maximum cost, retry cost, cache usage and all model spend divided by supported completions. Retain held charges in the budget and show them separately in cost reports.

Use fictional stress checks for burst handling, concurrent budget admission and cookie renewal. The original two-cohort/50-completion target can guide later measurement, but a small pilot cannot establish a reliable p99 or a guaranteed challenge false-positive rate. Review the evidence with the owner before selecting public limits, adding paid bot features or changing model routing. Re-evaluate after material model, prompt or usage changes.

## 5. Health data, HIPAA and model data sharing

### 5.1 The core problem: which rules apply changes along the journey

Daylight will hold medication lists, doctors, conditions and Medicare details. Which law governs that information is not the same at every step, and some of it is unsettled for an AI-delivered brokerage. **The recommended position is to protect all health information to the HIPAA standard from the first message, whatever law strictly applies.** That avoids re-architecting at checkout and keeps every privacy statement Daylight makes true.

| Stage | What Daylight holds | Rules likely in play | Open question for counsel |
|---|---|---|---|
| Anonymous exploring and saved profile (before checkout) | Medications, doctors, ZIP, age, current coverage, typed by the person | **FTC Act §5**: privacy promises must be true, and unfair data practices are prohibited. **FTC Health Breach Notification Rule**: its 2024 amendments cover most health apps outside HIPAA, and a profile that draws from the person's input plus drug and provider data could qualify as a personal health record. **Florida 69O-128**: as a licensee, Daylight needs authorization before disclosing nonpublic personal health information outside insurance functions, and needs a written information security program (69O-128.032). **Florida Information Protection Act** (§501.171) for breaches. **CMS TPMO rules** on data sharing and recording. HIPAA probably does not apply yet, because no carrier relationship exists for this person. | Q1, Q2, Q3 |
| Checkout and enrollment | The above, plus Medicare number, date of birth, address, application data | Everything above, plus **HIPAA as a business associate** of the carrier, typically through the agent agreement: Security Rule, breach notification to the carrier, minimum necessary. Carrier contracts may add shorter notice deadlines. | Q1, Q6 |
| Service after enrollment | Plan correspondence, formulary problems, bills | Business-associate obligations for data received from plans; Florida rules | Q1 |
| Advocacy (appeals, contacting plans and pharmacies) | Claims and appeal records | Representative authority (CMS appointment of representative); HIPAA authorization for plans to release information to Daylight | Plan Q7 |
| Family sharing | Shared context, deadlines, tasks | Beneficiary-controlled permission grants; Florida 69O-128.018 authorization elements when health information is disclosed to family; HIPAA personal-representative rules where they apply | Q3 |
| Partner and AI-callable service | Cases handed in by other companies | Data-sharing agreements; a partner that is itself a TPMO triggers CMS one-to-one consent | Q5 |

### 5.2 Model and vendor data sharing: problems to expect

1. **A BAA covers only the services it names.** Every vendor that touches health information needs its own agreement, and each one covers only listed services. Expect gaps in features that store or transform content: caching, logging, analytics, edge compute. Keep a **vendor register** listing each vendor, what data it sees, its contract (BAA, data processing terms, zero retention), the covered services and the region. Candidates to review: the cloud provider, the model provider, the edge and bot service, email (some transactional email providers do not sign BAAs; if not, emails carry no health information, only a sign-in link), SMS, error tracking, the support desk, the agency management system and the enrollment platform.
2. **Zero data retention must be contracted and checked per feature.** It is not the default on most model APIs, and some features may sit outside it. Confirm in writing that inputs are not retained beyond processing, are not used for training, and stay in US regions. Confirm how prompt caching and any provider abuse monitoring are handled under the agreement.
3. **Model fallback can cause a breach.** The plan keeps Daylight model-agnostic. A failover to a provider without the same contract terms is an unauthorized disclosure. **The provider interface enforces an allowlist of covered providers and regions and fails closed.** No developer or config change can route production traffic to an uncovered endpoint.
4. **Every model sees content, including the small ones.** The scope classifier, the summarizer, any moderation call and any extraction model fall under the same rules as the main model.
5. **Conversation history (D186).** The owner requests durable hosted-pilot transcripts. Implement participant disclosure/consent and an encrypted archive with scoped reviewer access, access audit, expiry and deletion. Capture submitted messages and delivered content with release attribution. Exclude secrets and redact prohibited identifiers before persistence. Keep routine diagnostic logs content-free. This is authorized implementation work, with hosted verification pending. [Design](../../infrastructure/daylight-pilot/DOMAIN_LAUNCH.md).
6. **Evaluation data.** No production content enters evaluation suites. If de-identified data is ever used, it must meet the HIPAA de-identification standard. Medicare data is hard to de-identify: ZIP codes, birth dates, ages over 89 and rare drug combinations can identify someone.
7. **No third-party tracking on any page where health information is entered or shown.** That means no ad pixels, session-replay tools or third-party analytics. A federal court vacated part of HHS's tracking-technology guidance in 2024, but the FTC has brought enforcement actions over health data sent to advertising platforms. Use first-party, self-hosted analytics with no content.
8. **Commission data never enters model context.** This is an existing structural rule, not new. A07's serialized-request canaries test that it holds.
9. **The retention conflict.** CMS requires TPMOs to record calls with beneficiaries and to keep sales and enrollment call records for ten years. Whether that applies to chat is open (plan Q4). The design keeps raw chat visit-only by default, plus a separate, sealed compliance archive for the checkout and enrollment conversation if counsel says it must be kept: encrypted, access-logged, with no model or analytics access and a defined retention period. Guest chats that never reach checkout stay ephemeral unless counsel says otherwise.
10. **Deletion requests versus legal retention.** A person can ask Daylight to delete their profile. Records Daylight must keep (enrollment, the compliance archive, licensed review) are kept for the required period and excluded from all other use. Everything else is deleted. The privacy notice must say which is which.
11. **Sharing with other TPMOs needs one-to-one consent.** Under 42 CFR 422.2274(g) and 423.2274(g), a TPMO may share personal beneficiary data with another TPMO only with prior express written consent, given separately for each recipient. A federal court upheld that requirement in August 2025. An enrollment-platform vendor, an FMO or a partner agency may each be a TPMO. Build consent capture per named recipient, default off, recorded with time and the disclosure shown.
12. **Florida authorization forms.** Disclosure of health information outside insurance functions (to family members, to a partner handing a case back) needs an authorization with the elements in 69O-128.018: whose information, what types, to whom and why, signature and date. It is revocable, and Daylight keeps a copy. This maps onto the plan's separate permissions for sharing, handoff and enrollment.
13. **Privacy notice.** Florida 69O-128 requires privacy notices to customers of licensees. Daylight needs a notice that accurately describes the AI processing, the vendors, retention and the person's choices, written in plain language for the target user.

### 5.3 Data minimization in the conversation

- Do not ask for a Medicare number, Social Security number, full date of birth or payment details before checkout. Age or birth month and year are enough for most decisions.
- Detect and redact these if a person types them early (patterns for Medicare numbers, SSNs and card numbers), **before the model call and before any log**. Tell the person they don't need it yet.
- Ask for medications and doctors only when a check needs them, and say why.

### 5.4 Breach notification matrix (to confirm with counsel)

| Regime | Applies when | Who is notified | Deadline |
|---|---|---|---|
| HIPAA, as a business associate | Data received for or on behalf of a carrier | The carrier (which notifies individuals) | Without unreasonable delay and within 60 days; carrier contracts are often shorter |
| FTC Health Breach Notification Rule | If the pre-checkout profile is a personal health record | Individuals, the FTC, sometimes media | Without unreasonable delay and within 60 days |
| Florida Information Protection Act | Name plus medical or health-insurance information of Florida residents | Individuals; the Florida Department of Legal Affairs if 500 or more Floridians | Within 30 days for individuals |
| Carrier and vendor contracts | As written | As written | Often 24 to 72 hours |

## 6. Application and platform security requirements

### 6.1 Identity at checkout and enrollment

- Passwordless sign-in at checkout: an email magic link (single use, expires in about 15 minutes, bound to the browser that asked for it) or a passkey. A phone code is an alternative.
- The guest session and its profile attach to the new account only with the person's explicit "save" choice.
- **Step-up before enrollment**: confirm the beneficiary's identity against their Medicare details, and send confirmation to the contact on file. Watch for one account enrolling several different beneficiaries.
- Enrollment is its own permission (existing rule). Licensed review under Option B is also a fraud check.
- Sessions after sign-in: short idle timeout, sign-out everywhere, and notification on new device sign-in.

### 6.2 Authorization and data isolation

- Object-level authorization on every profile, case, decision and document lookup, enforced in the service and in the database (Postgres row-level security). Broad app roles alone are not enough (A05).
- Opaque, unguessable identifiers.
- The A05 tests: two fictional beneficiaries cannot read each other's records; a revoked family or action grant stops access at once.
- Guest stores and protected variants are untouched (existing rule).

### 6.3 Internal access

- SSO with phishing-resistant MFA (hardware keys or passkeys) for the cloud console, GitHub, the model provider and every vendor console.
- Least privilege by role. Licensed reviewers see only cases in their queue, not search across all customers.
- An immutable audit log of every access to customer records: who, what, when, why. Review it monthly.
- Remove access on the day someone leaves.

### 6.4 Encryption and secrets

- TLS 1.2 or later everywhere, with HSTS. Encryption at rest with managed keys. Field-level encryption for Medicare numbers and dates of birth.
- Secrets in a managed secret store, never in the repository. Pre-commit secret scanning (the repository already has git hooks to extend). Model API keys live only on the server, with separate keys and spend limits per environment. Rotate them on a schedule and immediately on suspected exposure.

### 6.5 Web application

- A strict Content Security Policy; no third-party scripts on health pages.
- Secure, HTTP-only, SameSite cookies; CSRF protection on state-changing requests.
- Model output rendered as text, never as HTML.
- SSRF protection on any server-side URL fetch.
- File uploads (if people later upload plan letters or card photos): type and size checks, malware scanning, a separate storage bucket and short-lived download links.
- Signed webhooks with idempotency and replay protection for enrollment-platform callbacks (A10).

### 6.6 AI-specific controls (OWASP Top 10 for LLM applications)

| Risk | Daylight control |
|---|---|
| Prompt injection, direct and through documents | The two-stage controller: the model proposes, software validates. Extracted plan-document text is data, never instructions. Tool authorization is decided by software, not by the model. |
| Sensitive information disclosure | Redaction before model calls (§5.3); per-session context only; no cross-user memory in the model. |
| Excessive agency | No outbound action without a software gate plus the person's specific permission. |
| Improper output handling | Model output is untrusted input to Daylight's own systems: validated against typed tool schemas and rendered as text. |
| System prompt leakage | No secrets, keys or commercial terms in prompts. Assume the prompt is public. |
| Misinformation | Grounding against the evidence store, abstention when evidence is missing, visible holds (existing). |
| Unbounded consumption | Section 3. |
| Supply chain and model provenance | Pinned model versions per release; evaluation receipts bound to exact versions (A07). |

### 6.7 Infrastructure and supply chain

- Dependency pinning, automated update PRs and vulnerability scanning; a software bill of materials per release.
- Branch protection with required review on the main branch; CI cannot reach production secrets.
- Separate dev, test and production accounts. Development uses fictional data only (existing rule).
- Backups with point-in-time recovery and a tested restore. Set recovery targets before launch. The pending HIPAA Security Rule update proposes a 72-hour restoration standard, which is a sensible target now.
- A capacity plan for the Annual Enrollment Period surge, and a status page.

### 6.8 Protecting users from impersonation

Medicare scams aimed at seniors are common, and a trusted AI brokerage will be impersonated.

- SPF, DKIM and DMARC (enforced) on every sending domain.
- A short, prominent "What Daylight will never do" statement, for example: Daylight will never call you to ask for your Medicare number, never ask for payment to compare plans, and never pressure you to switch.
- Monitor for look-alike domains and fake listings.

## 7. Security operations

- **One security program that satisfies both regimes.** Florida requires a written information security program (69O-128.032), and HIPAA requires a risk analysis for business associates. Build a single document set: risk analysis, policies, the vendor register, an asset inventory, access reviews, workforce training and an incident response plan.
- **A named security official** (HIPAA requires one). At launch this is likely the owner.
- **Incident response**: a runbook with the notification matrix (§5.4), a contact list for counsel and carriers, and one tabletop exercise before launch.
- **A pen test before public launch**, covering the OWASP web and LLM top 10s, including cost-exhaustion and cross-session tests.
- **Monitoring and alerts**: hourly spend against baseline; one session or network using an unusual share of the pool; session length outliers; failed-authorization spikes; SMS volume; scope-check rejection rate; new-session rate per network; error rates. Review the most expensive sessions weekly (§4).
- **Cyber liability insurance**, alongside the agency's E&O coverage.
- **Build toward the pending HIPAA Security Rule update now.** The proposed rule includes mandatory MFA, encryption, asset inventories and restoration standards. The final rule's target date on the federal regulatory agenda has moved to July 2027, and building to the proposal now avoids rework.

## 8. Launch gates

| Control | Gate 1: before pilot traffic | Gate 2: before checkout and enrollment | Gate 3: later |
|---|---|---|---|
| AWS edge controls and verified guest sessions | ✓ under accepted pilot scope | | |
| Global ceilings, provider spend limits, billing alerts, kill switches | ✓ | | |
| Cumulative pilot cap, pacing and supported capability bounds | ✓ | | |
| Approved numeric cost and outcome measurement | ✓ | | |
| Redaction before model calls and logs | ✓ | | |
| BAAs or equivalent terms with every vendor touching health data; provider allowlist | ✓ | | |
| No third-party trackers; content-free traces | ✓ | | |
| Privacy notice and terms that accurately describe AI processing | ✓ | | |
| Written security program, risk analysis, incident runbook, named security official | ✓ | | |
| Internal MFA, least privilege, audit log | ✓ | | |
| Public budget and calibrated abuse controls | | ✓ before public access | |
| Checkout identity, step-up before enrollment, SMS protections | | ✓ | |
| Object-level authorization and the A05 two-beneficiary tests | ✓ (saved profiles) | ✓ | |
| Compliance archive and retention rules (per counsel) | | ✓ | |
| One-to-one consent capture for any TPMO data sharing | | ✓ | |
| Signed enrollment webhooks (A10) | | ✓ | |
| Pen test and LLM red-team | | ✓ before public launch | |
| Florida authorization forms for family sharing and partner hand-back | | | ✓ |
| Partner API: per-key quotas, signed requests, scoped delegation | | | ✓ |
| Finer abuse scoring, device signals | | | ✓ |
| SOC 2 tooling | | | ✓ when partners ask |

<a id="81-proposed-invite-only-gate-1-amendment--november-7-2026"></a>

### 8.1 Invite-only Gate 1 amendment · accepted November 8, 2026

**Scope and deferrals accepted under D101 (SA-27).** The applicable Gate 1
requirements remain release conditions. D99 fixes the $100 total pilot model
budget and per-participant usage tracking. D100 authorizes the private GitHub
manual review exception. D101 approves numeric usage retention and the AWS
`us-east-1` and OpenAI GPT API target for fictional deployment verification.
The [decision packet](../reviews/pilot-security-stage1-2026-11-07/DECISIONS.md)
contains the proposed numbers and approval choices.

**Approved scope.** At most 20 individually invited adults in the existing
Collier County first-time-enrollee pilot, through December 23, 2026. Founder-only
administration; guest visits only, with saved profiles disabled. No public
registration, discoverable open-chat endpoint,
checkout/enrollment, SMS, family/partner access, or paid third-party actions.
Each participant gets an expiring, revocable invitation; a newly shared invite
requires founder authorization and counts toward the same 20-person limit.
An invite is not identity verification. No current source, method, personal
recommendation or consumer-purpose hold is released by this amendment. Only
separately accepted capabilities can be used with participants.

**Keep before the first participant.** Signed invitation/session enforcement
on every protected request; basic request/body/concurrency limits; scope and
service-area checks; the single D99 $100 pilot ceiling and durable accounting;
provider limits, alerts and tested kill switches; redaction, approved vendor
contracts/regions and fail-closed provider routing; content-free diagnostics;
accurate privacy/consent/terms; security program, risk analysis, incident runbook
and named official; phishing-resistant staff authentication, least privilege
and access logging; web hardening and TLS. Any later expansion to saved profiles
requires a scope decision, service/database authorization and deployed A05
revocation/isolation evidence.
Code checks and recorded founder review remain required. Disabled features must
be rejected at the server, not merely hidden in the interface.

**The accepted changes to the broader launch scope are these:**

| Requirement | Invite-only pilot treatment | Due before / reason |
| --- | --- | --- |
| AWS managed edge automation controls (§3.1–3.2) | Defer these managed automation controls. Keep short-lived server sessions, invitation validation before any model call, request limits, origin access restrictions and spending limits. | Before the first public cohort or any open registration, whichever is earlier. Small founder-issued access permits a bounded trial; an invitation alone is not bot protection. A leaked/reused link or uncontrolled session creation pauses admissions until contained. |
| Public abuse-control calibration (§3.5–3.6, §4) | Retain request pacing, the cumulative cost limit and content-free denial counters. D141 makes the choice of additional signals evidence-dependent. | Before public access. Twenty participants are insufficient to calibrate these signals without false confidence; no automated behavioral penalties during this pilot. |
| Two cohorts/50 completed decisions and p90/p99-derived allowance (§4) | Treat up to 20 participants as a provisional observation cohort; report all-session cost, median, observed maximum, incomplete-session cost and sample size. No claimed p99 or <1% false-positive proof. | Use pilot and fictional stress evidence to choose public controls before public access. Retain the two-cohort/50-completion target as a measurement objective and report tail uncertainty. D141 leaves public dollar limits for owner re-evaluation. |
| GitHub server enforcement and independent approval count (§6.7, SA-02) | **D100 approved for the invite-only pilot.** Private GitHub Free with PR-only work, recorded founder review and passing checks on the exact final commit. The procedure prohibits direct main pushes and force-pushes. Approve a tested revision separately for deployment. A repository writer can bypass manual enforcement. | Require server-enforced PR and check rules and a second qualified reviewer before public access. Reassess sooner if write access or automated deployment expands. |

Pen testing and AI red-team assessment remain due before the first public cohort
**or** checkout/enrollment, whichever comes first. Checkout identity, separate
action permissions, required retention and enrollment callback protections
remain Gate 2 requirements; family/partner features remain disabled until their
own controls and permissions are accepted. SOC 2 tooling retains its existing
later gate. No vendor/privacy/source control is deferred here.

Pilot admission requires owner review of the exact deployed controls and the
remaining applicable launch gates. Expanding the population, date, supported
actions, vendors or public exposure requires another recorded scope decision.
Passing tests, issuing invitations or producing this document is not acceptance.

Owner decision: **accepted under D101 on November 8, 2026**. Deployment review
and admission are separate from this scope decision.

## 9. Questions for counsel

These add to section 7 of the brokerage plan.

1. **When does HIPAA apply?** Is the agency a business associate from carrier appointment, only for enrollment data, or never for information a person gives Daylight before choosing a plan? Do carrier agent agreements impose BAA terms on everything the agency holds?
2. **Does the FTC Health Breach Notification Rule apply** to the pre-checkout profile, given that it combines the person's own input with drug and provider data?
3. **Florida 69O-128.** Does processing by the model provider, the cloud and other vendors count as an insurance function performed on Daylight's behalf, so no authorization is needed? Which flows need a 69O-128.018 authorization: family sharing, partner hand-back, advocacy? What must the privacy notice say?
4. **Recording and retention for chat** (extends plan Q4). Is a chat a "call" for CMS recording purposes? What must be kept from guest chats that never reach enrollment, and for how long?
5. **Which recipients are TPMOs** requiring one-to-one prior express written consent: the enrollment-platform vendor, an FMO, the agency management system, partners?
6. **Carrier contract terms**: breach-notice deadlines, security requirements, audit rights and any restrictions on AI or offshore processing.
7. **Identity confirmation at enrollment**: what carriers accept, and how the agent of record attests under Option B.

## 10. Owner decisions needed

| # | Decision | Options | Blocks |
|---|---|---|---|
| D1 | Cloud provider and region | D101 selects AWS us-east-1 | Actual account, vendor scope and deployment verification |
| D2 | Edge and bot service for health-data paths | D141 selects AWS CloudFront and AWS WAF. Bot Control tier and challenge configuration are selected at launch | Deployed edge verification |
| D3 | Pilot budget ceiling | D99 approved one $100 cumulative whole-pilot model limit; per-participant usage reporting; no monetary sublimits or calendar reset | Gate 1 implementation/verification remains |
| D4 | Pilot safety cap before shadow data | D99 uses the shared $100 ceiling without a personal/session dollar cap; retain request bounds and in-flight reservations. Later public/checkout policy remains separate | Gate 1 implementation/verification remains |
| D5 | Extend the trace contract with numeric usage fields | D101 approves detailed numeric usage for 90 days and non-identifying cohort totals for 12 months | Host retention verification |
| D6 | Record Option B as a numbered decision | Existing open item | Gate 2 |

## Sources

- [FTC Health Breach Notification Rule, final rule (Federal Register, May 30, 2024)](https://www.federalregister.gov/documents/2024/05/30/2024-10855/health-breach-notification-rule)
- [FTC: Health Breach Notification Rule overview](https://www.ftc.gov/node/78112)
- [Fla. Admin. Code R. 69O-128.017: when authorization is required for disclosure of health information](https://www.law.cornell.edu/regulations/florida/Fla-Admin-Code-Ann-R-69O-128-017)
- [Fla. Admin. Code R. 69O-128.018: authorizations](https://www.law.cornell.edu/regulations/florida/Fla-Admin-Code-Ann-R-69O-128-018)
- [Fla. Admin. Code R. 69O-128.032: information security program](https://regulations.justia.com/states/florida/69/69o/chapter-69o-128/section-69o-128-032)
- [Florida Statutes §501.171 (Florida Information Protection Act)](https://www.flsenate.gov/Laws/Statutes/2021/501.171)
- [Americans for Beneficiary Choice v. HHS, N.D. Tex., memorandum opinion of August 18, 2025](https://www.mintz.com/sites/default/files/media/documents/2026-01-06/CMS-ruling-N.D.-Tex.pdf)
- [Even with the FCC one-to-one rule gone, the CMS one-to-one rule stands (TCPAWorld, 2025)](https://tcpaworld.com/2025/03/11/even-with-fcc-11-gone-the-cms-11-rule-is-still-standing/)
- [CMS TPMO call-recording FAQ summary (JD Supra)](https://jdsupra.com/legalnews/cms-publishes-frequently-asked-6247221)
- [Fierce Healthcare: HIPAA Security Rule overhaul pushed to July 2027](https://www.fiercehealthcare.com/health-tech/feds-push-back-hipaa-security-rule-overhaul-july-2027)
- [Holland & Knight: AHA v. Becerra and the OCR tracking-technology bulletin](https://www.hklaw.com/en/insights/publications/2024/06/american-hospital-assn-v-becerra-are-tracking-tools-ok-again)
- [Is Cloudflare HIPAA compliant? BAA and covered services (Accountable)](https://www.accountablehq.com/post/is-cloudflare-hipaa-compliant-baa-covered-services-and-best-practices)
- [Cloudflare Turnstile plans](https://developers.cloudflare.com/turnstile/plans/)
- [Brokers as business associates (AssuredPartners, February 2025)](https://www.assuredpartners.com/-/media/Files/Corporate/EB-Compliance-Documents/2-19-Employees/Column-1/HIPAA/Brokers-as-Business-Associates.pdf)
- [Claude API and data retention](https://platform.claude.com/docs/build-with-claude/api-and-data-retention)
