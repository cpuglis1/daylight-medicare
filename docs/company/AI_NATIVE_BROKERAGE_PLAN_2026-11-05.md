# Daylight AI-native brokerage plan

Owner direction · November 5, 2026 · Updated plan following the expanded-vision review. Read with [PRINCIPLES](../../PRINCIPLES.md), the [strategic thesis](../product/STRATEGIC_THESIS.md) and the [capability ledger](../project/CAPABILITIES.md). This is strategy and sequencing. It records no new numbered requirement and approves no implementation or release by itself. The human-involvement level (section 3) stays an open decision until the owner records it.

## 1. Thesis

Daylight is an AI-native Medicare brokerage. It takes responsibility for the customer's whole coverage problem: being found, understanding Medicare, getting a recommendation, enrolling, then using and maintaining the coverage over time.

**The moat is not offering AI. It is how much of the work the company is willing to let AI do, together with a seamless experience.** The owner has reviewed competing tools hands-on. In the owner's assessment, they stop short of true recommendations and almost all route the customer to a human agent to close the sale. Online brokerages show that the digital-brokerage model works; chat AI added on top performs unevenly from one competitor to the next. None of them takes on the work of explaining and comparing plans for the people who most need that help.

Complete white space is not required. The goal is a better product. The four parts of the expanded vision are:

1. **The complete brokerage.** Education, self-discovery, a profile, a recommendation, the application, confirmation that coverage is in effect, and service.
2. **A continuing representative for coverage problems.** Formulary and authorization issues, bills, network changes, the annual Notice of Change review, and appeals with proper authorization.
3. **A family service.** The beneficiary controls access; authorized family members share context, deadlines and tasks.
4. **A Medicare service other AIs call.** Assistants and partners (employers, financial advisers, retiree organizations) hand cases to Daylight, which carries them through.

The principles still bind all four. Commissions stay downstream of the decision; keeping current coverage, deferring, and choosing a plan that pays no commission all remain valid outcomes. Advocacy is credible only if the economics hold up across that neutral mix of outcomes.

## 2. Critical path

Each step ends with evidence, not with a document.

| # | Step | Exit evidence | Status, Nov 5 |
|---|---|---|---|
| 1 | **Legal and operating route** | Written counsel opinion covering: the agency license and its designated licensed producer; carrier appointments and the agent number (NPN) on each enrollment; whether a software-delivered needs assessment satisfies the CMS pre-enrollment checklist; Florida treatment of recommendations; recording and retention of chat-based sales and enrollment. Open items stay blocked. | Florida law gives no guidance. CMS was contacted and has not replied. Lawyer conversation pending. |
| 2 | **First real recommendation, 72 Collier plans** | A reviewed decision method on the r13 catalog: first the coverage-path decision, then cost, doctor and drug checks with visible holds; the end-of-gathering confirmation; reproducible reasons; independence tests I01–I10; independent review of the exact outputs; a small observed user cohort. | Catalog, cost examples, plan review and the Plans handoff exist. Recommendation authority is blocked. |
| 3 | **Enrollment route** | A chosen route (enrollment-platform vendor or carrier online enrollment) with sandbox receipts and status tracking: submitted, accepted, effective. Enrollment authorization is a separate permission. | Not started. Architecture step 15 is specified. |
| 4 | **One proven acquisition channel** | A single channel with arrivals, completed decisions, effort and cost measured across repeated cohorts. | Not started (CAP-14). |

Advocacy, family coordination and the AI-callable service follow, reusing the same profile, evidence and permission infrastructure.

**Compliance becomes part of the product.** The self-discovery conversation should be designed to cover every item on the CMS pre-enrollment checklist (CY2026 agent/broker guidelines; 42 CFR 422.2274(c)(12) and 423.2274(c)(12)):

- plan type, and whether the person's doctors, pharmacy and hospitals are in network;
- formulary coverage;
- other needed benefits;
- premiums, including Part B;
- cost sharing;
- out-of-network rules;
- coverage outside the U.S.;
- the effect on current coverage, including Medigap;
- plan-year changes and the Evidence of Coverage;
- how to file complaints;
- special-needs plan requirements;
- the right to cancel.

Each enrollment should carry a receipt showing which items were covered and when. Whether software coverage meets the "agents and brokers discuss" standard is question 3 in section 7.

## 3. Human involvement: open decision

The target is zero routine human involvement in the consumer journey. Licensed accountability still exists: an agency, its designated responsible producer, an agent of record on each enrollment, and supervision. The level to launch with is undecided. The options below are listed for the counsel conversation, not chosen:

| Option | Shape | Tradeoff |
|---|---|---|
| A. Zero touch | AI completes the recommendation; the person self-enrolls through the agency's platform; a licensed agent of record is attached; humans handle exceptions only. | Strongest moat; depends most on the legal answer. |
| B. Async licensed review | AI completes everything; a licensed agent reviews and signs off on the recommendation record before or after submission, without contacting the customer. | Light staff cost; a defensible starting position; measurable step toward A. |
| C. Opt-in human | Same as A or B, plus an offered (never required) licensed conversation. | Builds trust with hesitant users; must not become a sales-call gate. |

Measure staff minutes per completed case under whichever option launches, so the move toward A rests on evidence.

## 4. Hands-on competitive test

The owner challenged Claude to test the tools personally and see whether the vision already exists.

- **Tools:** Chapter, Healthpilot, CoverRight, Well Advised, MedicareShopper.ai, Pops, eHealth, a strong local broker, and the Medicare.gov Plan Finder as a baseline.
- **Personas:** three synthetic first-time cases, using fictional details only. For example: retiring in March with a spouse keeping employer coverage; specialists and two medications; a Medigap open-enrollment window.
- **Rubric:**
  - Can you start without an appointment or contact details?
  - Does it uncover circumstances you didn't mention?
  - Does it compare coverage paths before policies?
  - Does it give a true recommendation with reasons?
  - What does it disclose about market scope and exclusions?
  - Does it check doctors and drugs?
  - Can you complete enrollment without a human?
  - Is there any service after enrollment?
  - What does it cost you in time?
- **Output:** a dated scorecard with screenshots. No real applications, real personal information or callback requests are submitted.

## 5. Stack for scale

**Principle: buy the rails, build the brain.** Daylight's advantage lives in the profile, conversation, decision engine, evidence and compliance record. Quoting, enrollment transport, Medigap rates and book-of-business operations are commodities that others already run at scale.

### Data: replace hand-reviewed facts with automated pipelines

- **Backbone from national public files.** These cover every county at once:
  - CMS MA/PDP Landscape and Plan Benefit Package files;
  - the Medicare Plan Finder benefit summary (already acquired);
  - Part D formulary, pharmacy network and pricing files;
  - Star Ratings;
  - NPPES and the Doctors & Clinicians file;
  - NLM RxNorm for drug normalization.
- **Provider networks.** MA plans must publish provider directories through a public FHIR API (CMS Interoperability and Patient Access rule). That is the scalable route to network checks; directory accuracy problems mean results should be presented as "listed in network" with a confirmation step.
- **Plan documents (SB/EOC).** Use AI extraction with structured output only for fields the backbone lacks or for consequential exceptions. Cross-check automatically against the Plan Benefit Package data. Humans review methods and sampled disagreements, not each fact. This carries the November 4 MPF-first direction to national scale.
- **Medigap rates.** There is no complete public rate source. Use a commercial rate API, such as CSG Actuarial, alongside state filings.
- **Pipeline tools.** Orchestrate ingestion with Dagster, which tracks lineage and versions per data asset and fits Daylight's provenance model. Prefect is an alternative. Keep raw source files immutable and versioned in object storage. Transform with dbt, using its tests as the data-quality gate; each release is a versioned snapshot with rollback.
- **Database.** Keep PostgreSQL. Move to a managed instance (AWS RDS/Aurora or Google Cloud SQL) under a BAA.

### Decision engine

- Keep calculations deterministic and in Python (the existing comparison engine and methods). The AI never does arithmetic or decides eligibility.
- Version rules as code. Each recommendation stores its inputs, evidence versions, method version, candidates, exclusions and reasons, which makes replay and independence counterfactuals routine.

### Agent layer

- Keep the existing two-stage controller: the model proposes an interpretation, software validates it, then the reply is composed.
- Expose verified capabilities (plan lookup, doctor and drug checks, cost scenarios, the checklist status) as typed tools.
- Stay model-agnostic, and route model calls through a provider covered by a BAA with zero data retention (cloud-hosted models via Bedrock, Vertex or Azure, or direct enterprise agreements).
- Later, publish the same tools as an MCP server and partner API for direction 4.

### Evaluation and observability

- Build an evaluation harness that runs on every prompt, model or data change. Use promptfoo, Braintrust or a custom harness. Suites:
  - persona journeys;
  - checklist-coverage scoring;
  - factual grounding against the evidence store;
  - commission-swap counterfactuals;
  - abstention when evidence is missing.
- Trace with OpenTelemetry and self-hosted Langfuse so personal health information stays inside Daylight's boundary.

### Enrollment and quoting rails

- Evaluate enrollment and quoting platforms: SunFire, ConnectureDRX/Convey and CSG. The criteria:
  - carrier coverage for Florida in 2026–27;
  - API access, as opposed to embedded white-label screens;
  - status callbacks;
  - support for the agent of record;
  - pricing.
- Carrier online enrollment is the fallback. Do not automate arbitrary enrollment web pages with an unrestricted agent.

### Operations

- A case and exception system: Front or Zendesk, or a purpose-built queue on Postgres.
- An agency management system for commissions, appointments and book-of-business reconciliation (Medicare-specific options exist, such as AgencyBloc).
- Passwordless identity (Auth0, Clerk or Cognito) when Daylight moves beyond guest profiles.
- Twilio for SMS and voice, and Postmark for email, once outreach is authorized.
- Compliance automation (Vanta or Drata) when partners require SOC 2.

### Hosting

Choose one cloud with a signed BAA. AWS is the common default for this mix (RDS, S3, Bedrock); GCP is equivalent. Hosting, region and budget are still undecided (see [CLOUD_HANDOFF](../project/CLOUD_HANDOFF.md)).

### Process

The repository's governance layer (stacked dated directives in AGENTS.md, per-revision owner sign-off) slows AI-assisted development. Consolidate the current state into one short living document and move dated history out of the agent entry point.

## 6. What does not change

- Independence and comprehensive-scope obligations: D64, I01–I10.
- Coverage path before policy.
- Unknown evidence stays unknown, never counted against an option.
- Separate permissions for AI transfer, saving, family sharing, human handoff and enrollment.
- The protected variants and their stores.
- The 2026 Collier controlled pilot comes first.

## 7. Questions for counsel

1. Under Option A, what are the agency's and designated responsible producer's obligations when software makes the recommendation and the customer self-enrolls? What supervision is required?
2. Does Florida treat a software-generated plan recommendation from a licensed agency as solicitation or negotiation requiring a licensed individual's involvement per transaction?
3. Can a recorded, software-delivered needs assessment satisfy the 422.2274(c)(12) and 423.2274(c)(12) "agents and brokers discuss" requirement? What receipt would carriers and CMS accept?
4. Recording and retention: CMS requires recording of sales and enrollment calls. How does that apply to chat? What must be retained, and for how long? How does that reconcile with Daylight's minimal-retention default for raw conversation?
5. Disclosures for a third-party marketing organization, the agency's scope of representation, and what enrollment-platform and carrier contracts require.
6. For Medigap: underwriting questions, guaranteed-issue rights, and whether carrier applications permit fully digital submission without agent attestation.
7. For advocacy: the authority needed for appeals (the CMS representative appointment) and for contacting plans or pharmacies on the customer's behalf.

## Sources

- [CMS CY2026 Agent/Broker Training & Testing Guidelines](https://www.cms.gov/files/document/cy2026agentbrokertrainingtestingguidelinespdf.pdf)
- [Fierce Healthcare: Humana investment in Healthpilot](https://www.fiercehealthcare.com/payers/humana-makes-investment-ai-powered-medicare-enrollment-platform-healthpilot)
- [Original October 15 competitive landscape](../../medicare-project-2026-10-17-v1.2/medicare-ai-landscape.md)
