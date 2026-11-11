# Daylight launch security and abuse-prevention spec

Owner direction · November 6, 2026 · Read with the [AI-native brokerage plan](AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md), [CURRENT_STATE](../project/CURRENT_STATE.md) and the [AI-native database readiness review](../reviews/ai-native-database-readiness-2026-11-06/README.md) (actions A05, A07 and A10). This is a specification and launch gate list. It records no new numbered requirement and approves no implementation or release by itself. The legal sections describe the issues to resolve with counsel; they are not legal advice.

## 1. Owner direction and design constraints

1. **No identity required until checkout.** People abandon the tool when asked to verify or give personal details, so verification moves to enrollment, where identity is needed anyway. Before that, the only identity step is optional and framed as a benefit ("email me a link to pick up where I left off").
2. **Honest users can use as much as they need.** There is a per-individual cap, but it is generous and set from pilot evidence (section 4), so honest users should not hit it.
3. **The front door is a bot gate.** An edge firewall with bot management, plus an invisible challenge at session start.
4. **The AI is hard to misuse as a free general chatbot.** Scope is enforced by software, not by the prompt.
5. **The worst case is bounded globally.** However many fake sessions arrive, total spend cannot exceed set ceilings.

Two design consequences follow:

- **Defend against automation, accept bounded manual abuse.** Someone manually opening new windows and typing is limited by typing speed and patience. Scripts run up the bill. Every control below is aimed at traffic that does not behave like a person, and asks nothing of a person who does.
- **Degrade, never wall.** No answer is cut off mid-response. At any limit the person keeps the deterministic tools (plan lookup, drug and doctor checks, cost comparisons); only open-ended chat pauses.

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

- Put all traffic behind an edge firewall with bot management and rate-limiting rules per IP address and per network (ASN), plus a managed challenge for bursts. **Which edge depends on the health-data contract question in §10, decision D2.** The two workable shapes:
  - **Cloudflare Enterprise with a signed BAA** covering the proxy, WAF and bot services; or
  - **The cloud provider's own edge under its BAA** (for AWS: CloudFront, AWS WAF and its Bot Control rules), with **Cloudflare Turnstile used on its own as the challenge widget**. Turnstile runs in the browser and returns a token; it never sees chat content, so it does not need to sit on the health-data path.
- Allow only the methods and paths the app uses. Block or challenge requests with no browser fingerprint on chat endpoints.

### 3.2 Session token

- At session start the browser passes an invisible Turnstile challenge. The server validates the Turnstile token with Cloudflare's server-side verification (tokens are single-use and short-lived) and issues **Daylight's own signed session token**: short expiry, rotated on use, bound to a server-side session record.
- Every chat and tool request must carry a valid session token. Requests without one get no model call.
- The token is kept in a secure, HTTP-only cookie, with the session ID mirrored in local storage, so an honest user who returns on the same browser keeps their progress and their allowance.
- A new window or private window creates a new session. That is acceptable: each new session must pass the bot check again, starts at the default allowance, and counts against the global pool.

### 3.3 Per-session allowance

- Each session has a budget, metered in model cost (tokens converted to dollars) and stored server-side (Redis or Postgres), never trusted from the client.
- **Launch value: a high safety cap only.** Before the pilot, estimate the cost of one completed decision from the existing 14-scenario persona runner, then set the safety cap at roughly 20× that estimate. The enforced, evidence-based cap replaces it after shadow mode (§4).
- A saved profile (after the optional email link) carries its allowance across devices. This is the honest user's way past the per-session limit without verifying identity.

### 3.4 Pacing tuned to human speed

Starting values, to be confirmed in the pilot:

| Control | Starting value | Why an honest user won't notice |
|---|---|---|
| Minimum gap between messages | 3 seconds | Reading an answer about Part D takes far longer |
| Messages per minute per session | 10 | Typing speed of the target user is well below this |
| Requests in flight per session | 1 | A person waits for the answer before sending the next |
| New sessions per network per 10 minutes | Starting value set in shadow mode; network class adjusts it | Households and senior centers share an IP address, so this is a signal, not a hard block |

### 3.5 Invisible friction that increases quietly

The friction ladder runs in log-only mode during shadow mode (§4), then is enforced.

| Level | Trigger (any of) | Action | What the honest user sees |
|---|---|---|---|
| 0 | Normal behavior | None | Nothing |
| 1 | Session unusually long or fast; datacenter or VPN network | Re-run the invisible Turnstile challenge | Nothing, or a one-second check |
| 2 | Level 1 plus repeated or near-identical messages, or inhuman timing | Proof-of-work challenge in the browser; slightly slower responses | A brief pause |
| 3 | Persistent automation signals, or allowance nearly spent | Shorter answers; open chat limited | Answers still come, more concise |
| 4 | Allowance spent, or clear automation | Tool-only mode (§1, "Degrade, never wall") | Tools keep working; chat pauses with a save offer |
| 5 | Confirmed abuse (scripted, high off-topic share, attack patterns) | End the session; temporary network-level challenge | Only abusers reach this |

### 3.6 Behavior signals instead of identity

Each session carries a trust score from signals like these. The score lowers the allowance and raises the friction level; it never asks the user for anything.

- message timing (too regular, too fast, no reading pauses);
- repeated identical or templated messages;
- share of off-topic messages (§3.8);
- prompt-injection or jailbreak patterns;
- many new sessions from one network in a short window;
- network class: datacenter, known VPN, Tor. **iCloud Private Relay and residential VPNs are common among ordinary iPhone users and lower the score only slightly. They are never blocked.**
- no progress toward a decision (no ZIP, no coverage facts) after many turns.

### 3.7 Global ceilings and kill switches

This is the backstop that makes generosity safe. It is the one control a VPN cannot beat.

- **Separate budget pools**: anonymous sessions per hour and per day; saved-profile sessions; checkout and enrollment. When the anonymous pool runs out, new anonymous sessions start in tool-only mode with a save offer. Sessions already partway through a decision, saved profiles and checkout are unaffected.
- **Provider-side limits**: monthly spend limits on every model-provider account, with separate API keys per environment.
- **Cloud billing budgets** with alerts at 50%, 80% and 100%.
- **Three kill switches** (feature flags, changeable in under a minute without a deploy):
  1. anonymous chat → tool-only;
  2. all chat off, deterministic tools still on;
  3. any single paid feature off (SMS, Medigap rate API).
- Pool sizes are an owner budget decision (§10, decision D3).

### 3.8 Scope enforcement

- **A scope check runs before the main model call**: rules first, then a small, cheap classifier for what rules cannot decide. Off-topic messages get a fixed redirect that costs no main-model call. Several off-topic messages in a row move the session up the friction ladder and then end it.
- **Service-area gate**: a ZIP outside the pilot area (Collier County) gets a deterministic message and a waitlist, not open-ended chat.
- **Per-message limits**: input capped at about 2,000 characters; maximum output tokens; maximum tool calls per turn; maximum turns per session (the session cap, not a conversation wall: past it, the person is offered a saved summary and a fresh start).
- **Keep long conversations cheap**: summarize older turns instead of resending the whole history; cache the system prompt and catalog context; stop generation when the user disconnects.
- **The deterministic engine does the heavy lifting.** Plan lookup, cost scenarios and drug checks are Python and nearly free. The model interprets and writes; it never does arithmetic or decides eligibility (existing rule). This is the largest cost control in the design.

### 3.9 Paid actions

- **SMS pumping** is the classic way to run up a bill: bots trigger verification texts to premium-rate numbers and Daylight pays for each one.
  - Prefer email magic links. Offer SMS only at checkout.
  - Require a passed bot check and a valid session token before any text is sent.
  - Use Twilio Verify with its fraud protection on, US numbers only, and limits per number, per session and per network.
  - Kill switch 3 can turn SMS off on its own.
- **Medigap rate API and other paid data.** These are needed before checkout for the coverage-path decision, so they cannot wait for verification. Instead:
  - call them only once the profile has the minimum facts the quote needs;
  - cache results by ZIP, age band, sex and tobacco status for the rate period, so most calls are cache hits;
  - charge each uncached call against the session allowance;
  - limit calls per session.
- **Enrollment-platform calls and any outbound action** (sending, enrolling, contacting a plan or person) happen only after checkout verification and with the separate enrollment or action permission. No guest session triggers them.

## 4. Shadow-mode measurement plan for the cap

The goal is to set the per-individual cap from the distribution of honest, completed journeys, not from a guess.

**What is enforced during shadow mode:** only the safety cap (§3.3), the pacing limits (§3.4), the global ceilings and kill switches (§3.7), the scope check and the service-area gate. The friction ladder and trust score run in log-only mode: they record what they would have done.

**What is recorded per session.** Metadata only, never message content. This fits the no-transcript rule.

| Field | Example |
|---|---|
| Opaque session reference | hash |
| Turns; input and output tokens; model cost | 23 turns; $0.41 |
| Tool calls by type; paid API calls; cache hits | 6 plan lookups, 1 Medigap quote (cached) |
| Wall-clock duration; active duration | 41 min; 18 min |
| Outcome | decision reached / saved / abandoned / handed to a person / ended for abuse |
| Network class; trust score; highest friction level that would have applied | residential; 0.92; level 1 |

The current trace contract limits metadata to three short fields and carries no content. These usage fields are numeric measures, not content, but the contract needs a recorded extension to carry them (§10, decision D5).

**How the cap is set:**

1. Run at least two pilot cohorts with at least 50 completed decisions in total (the owner may adjust this to the pilot's size).
2. Compute the cost distribution for sessions that reached a decision. Look at the median, the 90th percentile and the 99th percentile.
3. Set the enforced per-session cap at about 3× the 99th percentile of completed decisions. Set the saved-profile cap higher.
4. Check the log-only friction ladder for false positives: the share of honest, completed sessions that would have been challenged at level 2 or above. Target: under 1%. Retune any signal that fires on honest users.
5. Review the 20 most expensive sessions each week. Each one is either abuse (tune the controls) or a person stuck in a loop (a product fix, not a security issue).
6. Re-tune before each Annual Enrollment Period (October 15 to December 7), when traffic and honest session length both rise, and after any model or prompt change that moves cost per turn.

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
5. **Debugging pressure.** Engineers will want transcripts to fix problems. The current rule stands: no raw transcript persistence. Use the fictional persona runner to reproduce issues. If real-conversation review is ever needed, it requires an explicit, per-conversation share from the user, kept in a sealed store with an expiry.
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
| Edge gate, Turnstile, signed session tokens | ✓ | | |
| Global ceilings, provider spend limits, billing alerts, kill switches | ✓ | | |
| Safety cap, pacing, scope check, service-area gate, per-message limits | ✓ | | |
| Shadow-mode metering and log-only friction ladder | ✓ | | |
| Redaction before model calls and logs | ✓ | | |
| BAAs or equivalent terms with every vendor touching health data; provider allowlist | ✓ | | |
| No third-party trackers; content-free traces | ✓ | | |
| Privacy notice and terms that accurately describe AI processing | ✓ | | |
| Written security program, risk analysis, incident runbook, named security official | ✓ | | |
| Internal MFA, least privilege, audit log | ✓ | | |
| Enforced cap and friction ladder, set from shadow-mode data | | ✓ | |
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
| D1 | Cloud provider and region | AWS or Google Cloud (existing open decision) | BAAs, the edge choice, deployment |
| D2 | Edge and bot service for health-data paths | Cloudflare Enterprise with a BAA; or the cloud provider's own edge under its BAA, with Turnstile standalone | Gate 1 |
| D3 | Budget ceilings | Anonymous pool per hour and per day; total monthly model budget | Gate 1 |
| D4 | Safety cap multiple before shadow data | About 20× the persona-runner estimate of one completed decision, or another value | Gate 1 |
| D5 | Extend the trace contract with numeric usage fields | Record as an amendment to the content-free trace rule | Shadow mode |
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
