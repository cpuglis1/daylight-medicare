# Software boundaries and behavior contracts

Company name undecided · revised October 17, 2026 · [Architecture](ARCHITECTURE.md)

Operating boundary: self-directed conversational research, engine-owned ranking, licensed transaction. “AI research assistant” and “licensed agent” are different actors with different permissions.

Product priority: caregivers, then self-directed researchers, then Medigap shoppers. Positioning is auditable neutrality: rankings are reproducible, inspectable and compensation-independent. Partner integration is a distribution layer over the same research and licensed-purchase boundaries, not a separate commercial ranking policy.

These are proposed application boundaries, not a final OpenAPI document or a claim about any vendor's payload. Confirm source-specific schemas during data discovery. Start with a modular application and keep the number of deployable services small.

## 1. Modules and ownership

| Module | Owns | Does not own |
|---|---|---|
| Source intake | Download/receipt manifests, layout versions, source-shaped records, parsing outcomes | Customer data, recommendation ordering |
| Catalog query | Validated market/product/benefit read fields and source lookup | Invented availability, personalized underwriting approval |
| Customer context | Consent, subject/representative access, confirmed profile revisions and current coverage | Carrier acceptance, clinical truth inferred from chat |
| Eligibility | Supported dated rule assessments and missing evidence | Final insurance issuance or a jurisdiction's grant of authority |
| Verification/quotes | Approved supplier requests, receipts, freshness and unresolved tasks | Silent substitution of drugs/doctors; unsupported “verified” labels |
| Decision engine | Compatible structures/scenarios, ranking from user-stated criteria and verified data, full results/exclusions and stored ranking basis | Compensation optimization, hidden preferences or unrecorded weights/data versions |
| AI research assistant | Conversation, clarification, explanation of engine results and reviewable proposals | Reordering/adding/removing options, “you should buy” verdicts, purchase checklist approval or submission authority |
| Purchase handoff | Complete context packet, qualified agent routing, seasonal response target, queue/scheduled session, checklist and human work tracking | Counting an auto-acknowledgment as an agent response or bypassing review to clear a queue |
| Licensed fulfillment | Agent review/re-verification, approved applications, explicit consumer and agent authorizations, submission and reconciliation | Treating research selection or AI output as approval to enroll |
| Servicing | Actual policy record, administrative issues, notices and review tasks | Invented coverage determinations or automatic annual switching |
| Company operations | Source/authority approvals, quality, incidents, finance and complaints | Unlogged intervention or private revenue inputs to ranking |

A module may initially be a package with typed functions. An HTTP boundary is added for a real deployment, security or scaling need. Do not turn every row in this table into a network service.

## 2. Consumer operations

Proposed operations, implemented incrementally:

- Start an education session; ask an immediate question.
- Create/save a case after consent and identity requirements are met.
- Save and resume out-of-hours caregiver research, invite the parent or an authorized caregiver into a case, and preserve actor-level permissions/provenance through purchase.
- Propose and confirm profile changes against the current revision.
- Request a market comparison and track missing checks.
- Inspect/edit stated criteria and weights; access the full engine-ranked set and exclusions at all times.
- Read an option's costs, restrictions and source information.
- Save a comparison or make an explicit selection.
- Choose **Ready to purchase**; enter a licensed-agent queue/session or scheduled fallback with the full context carried forward.
- With the licensed agent, complete required review/re-verification, preview the application and explicitly authorize it; the agent submits or authorizes submission.
- Read authoritative application/policy status and open a service case.
- Grant/revoke representative access, integration access and communications permissions.

Transport details follow the first working slice. Read-only education and the first market query do not require the entire enrollment API to exist.

## 3. Shared comparison snapshot

The consumer interface and agent must receive the same decision basis. The proposed envelope is intentionally small; the first implementation should include only validated fields.

```json
{
  "snapshot_id": "opaque-reference",
  "case_revision": "confirmed-profile-revision",
  "target": {"benefit_year": 2027, "market_ref": "resolved-market"},
  "basis": {
    "source_release_refs": [],
    "rule_version": null,
    "calculation_version": null,
    "assessed_at": "timestamp"
  },
  "coverage_scope": {"supported_categories": [], "known_gaps": []},
  "ranking_basis": {
    "confirmed_criteria": [],
    "weights": {},
    "inputs_ref": "pinned-ranking-inputs",
    "engine_version": "version",
    "tie_breaking_rule": "declared-method"
  },
  "options": [],
  "engine_ordered_option_refs": [],
  "shortlist_view_refs": [],
  "exclusions": [],
  "open_checks": [],
  "research_status": "more_information_needed"
}
```

This is an internal design example, not actual CMS or vendor data. An empty `options` array cannot mean the real market contains no options; the scope/result status must explain whether data is missing, an input is unsupported or there are no candidates within the assessed scope.

An option eventually references its components, validated monetary values and scope, access/restriction results, sources, major tradeoff and remaining conditions. Do not add fields simply to fill a dashboard. A first real-data card may show only product identity, source geography, published premium components and a few validated benefits, with clear limits.

The snapshot is immutable once used for a saved decision. A changed profile or source creates a new basis; it must not retroactively rewrite a selection or authorization. The physical persistence strategy is decided when those workflows are implemented.

Test auditable neutrality by replaying the same ranking inputs/data versions and changing only compensation, acquisition channel or partner attribution: the ranking must remain identical. Partner context can suggest facts or criteria for confirmation, but cannot silently become a consumer preference or hide an option. Store commercial/analytics data outside decision inputs and model context.

Every ranking retains its inputs, weights and data versions, with explicit criteria, calculation/engine identity and deterministic tie-breaking. The backend owns order and membership; the AI response and browser cannot independently sort or select a different shortlist. Full results and exclusions remain accessible through the same snapshot, using pagination if needed. A shortlist is a view, not a filter. A confirmed criteria change triggers a new engine computation and a new snapshot.

## 4. Advisor tools

Build tools only when their underlying capability is real. Initial read-only tools can be:

| Tool concept | Input supplied by model | Backend-enforced behavior |
|---|---|---|
| Read current case | No subject supplied by model | Resolve authorized subject and confirmed facts from session |
| Read/search supported results | Question or page reference within the current confirmed case | Preserve engine order/membership; provide full results/exclusions, validated geography/year and source/product gaps; changes to scope/criteria require confirmation and recomputation |
| Inspect option | Current option reference | Reject references outside the current result scope |
| Read evidence | Evidence reference | Authorize and return the exact supporting source fragment/path |
| Explain an educational topic | Question/topic | Retrieve approved dated material; distinguish general education from a personalized result |
| Propose profile correction | Allowed field/value proposal | Return a reviewable proposal, never silently confirm it |
| Request purchase handoff | Selected option/current snapshot reference | Resolve full transcript/profile/snapshot server-side, validate case access and create a licensed-agent request; confer no submission authority |

Later research tools assess eligibility, obtain a quote, check medicines/provider access, simulate costs and create verification tasks. The AI may help prepare a handoff but cannot complete the licensed-agent checklist, sign as the agent or submit an application. Submission is a separate permissioned workflow requiring the eligible licensed agent's submission/authorization and explicit consumer authorization. Supplier re-verification tools may assist that agent but do not replace their review.

Every tool validates arguments and authenticated case scope; returns data as data rather than instructions; distinguishes unsupported, incomplete and failed results; includes source/version information where relevant; and applies time/cost bounds. The server supplies identities, consent and permissions. Model-supplied values cannot expand authority.

## 5. Advisor response contract

A response combines short consumer prose with structured references and proposals:

- The answer and, where useful, one next question.
- The comparison/evidence references supporting material claims.
- An educational/provisional research status consistent with backend checks; it is not licensed purchase approval.
- References in exactly the engine's order, with its membership and shortlist view unchanged.
- Any proposed profile correction or UI focus action.
- Any authorized workflow's actual task/status reference.

Strict JSON schemas and typed tools prevent certain structural failures. Programmatic membership, scope, freshness and readiness checks are also required. Semantic truth and suitability need domain evaluation; merely listing a real evidence ID does not prove it supports the sentence.

Explain fit using “based on what you told us, these fit best because…” and inspectable criterion-level reasons; never “you should buy.” Validate order and membership against the engine, including conversational lists. Changing inputs or criteria requires user confirmation and an engine recomputation; it is not an LLM editing operation.

Only validated completed facts are actionable. Streaming can show progress and educational explanation, but a partial recommendation or half-written application cannot become a user authorization.

## 6. Asynchronous work and external actions

Use a simple durable job record for the first resumable checks. Adopt a workflow platform when the actual retry/wait/callback/compensation needs justify it. Business records remain authoritative regardless of implementation.

Useful event concepts are source inspected/published, criteria/profile confirmed, ranking computed, comparison invalidated, quote expired, verification completed/conflicted, selection confirmed, handoff requested/queued/scheduled/assigned, first substantive agent response, checklist completed/blocked, consumer/agent authorization recorded, application submitted/status changed, coverage effective, human work recorded, service issue opened/resolved, and access revoked. Add events as the actual workflow requires; avoid building a universal event bus up front.

For side effects, require a stable operation ID, exact authorized payload, current capability, durable status, supplier receipt and reconciliation rules. Delivery may be repeated; the business effect must be deduplicated. A supplier timeout is `unknown` until reconciled, not automatically `failed and safe to repeat`.

## 7. Errors the product must distinguish

| Condition | Consumer meaning | System response |
|---|---|---|
| Unsupported market/product | We cannot assess this scope yet | Explain limitation; do not use another market's data |
| Missing required fact | A specific answer/verification is needed | Ask a focused question or create a task |
| Ambiguous doctor/drug | More than one identity is plausible | Present candidates for confirmation |
| Stale/conflicting evidence | Current access/cost is unresolved | Show the conflict and block conclusions that require it |
| Supplier unavailable | The external check has not completed | Preserve useful progress and retry within policy |
| Stale profile/snapshot | Inputs changed | Recalculate and obtain renewed authorization where material |
| Action not approved | The company cannot perform this activity here | Keep the tool unavailable; explain the supported next step |
| No qualified agent available / queue above seasonal target | Licensed review cannot start within the applicable expectation | Show status and offer a real scheduled slot; preserve context; do not bypass review |
| Purchase re-verification changes a fact | The selected option's basis changed | Explain change, recompute ranking if affected and obtain renewed selection/authorization |
| AI order/membership differs from engine | The explanation violated the ranking contract | Withhold/correct the invalid output from engine results; record the failure |
| Uncertain transmission | We do not yet know whether a carrier received it | Reconcile before retrying |

Do not collapse these into “no plans found,” “not eligible,” or a persuasive apology. Error meaning is part of the insurance service.

## 8. Operations and evaluation interface

The internal workbench should expose source inspection/mappings, discrepancies, current authority/scope, case version, typed tool receipts, model/prompt versions, ranking inputs/weights/data versions, order/membership checks and graded failures. A role-restricted licensed-agent view adds full context, authority/appointment checks, selected-option re-verification, checklist, exact authorizations, queue/session state and active human work tracking. Keep sensitive payloads behind case permissions. It is distinct from the consumer interface.

For model evaluation, allow a fixed advisor policy plus subordinate experiment instructions. Run prompt variants against the same frozen factual cases. Export inputs, factual outputs, tool errors, latency/usage and grades with enough version identity to reproduce the result. The archived demo offers exploratory UI ideas, but its fixture results and contract tests do not establish any production capability.

## 9. Purchase handoff contract

Ready to purchase opens a case-scoped licensed-agent session carrying the full transcript, confirmed profile and comparison snapshot, along with the selected option, ranking basis and unresolved checks. Construct that packet from authoritative application state; a model-written summary is an aid, not a substitute. Pin the request-time basis and surface later changes.

Assignment requires a licensed, appointed agent of record qualified for the state/product/carrier. Store the assigned actor and authority check, then record the applicable identity/consents, SOA (MA/PDP), pre-enrollment checklist, provider/drug re-verification, replacement/guaranteed-issue risks and explicit consumer authorization. The agent submits or authorizes the exact application through the approved channel. A model or general operations role cannot mark this licensed review complete.

First-response targets are configured by season, staffed hours and measured capacity; values and percentile are approved before pilot. Measure the first substantive licensed-agent response, not an automated message. Exceeding the target opens a scheduled fallback, preserves context and triggers expiry rechecks as needed. Record queue wait separately from human handling/follow-up/service minutes.

Human work records support the primary metric, human minutes per effective, retained policy, including unsuccessful cases and attributable service/exception work. Use declared cohorts and retention windows; do not hide labor or convert queue time into active work time.

Carrier-link consumer self-enrollment with our agency as agent of record is a future, default-disabled capability. Enable only per approved carrier/state scope after quality evidence and validated attribution/reconciliation; it is not a queue bypass. The licensed-review boundary remains until explicitly changed.

## 10. Caregiver, partner and measurement boundaries

The initial caregiver journey supports public education without a purchase-ready identity packet, a saved research case, permissioned sharing and a full-context licensed handoff. Researcher and beneficiary are distinct actors. Record who supplied and confirmed a fact; do not infer transaction authority from family relationship or possession of a share link. Make the parent/representative confirmation path clear. Out-of-hours research availability and staffed licensed-agent response expectations remain separate.

Start with direct caregiver content/search. Add financial-advisor software and publisher entry/return paths around the same engine once the direct journey is proven. Partner-supplied context is scoped, authenticated where applicable, and confirmed when material; never trust a URL parameter as authority over a person or policy. Preserve access controls when a case moves between embedded and direct views. Do not expose health details to a publisher, advisor platform, advertising pixel or general conversion tracker by default.

The distribution funnel measures research, saved/returned cases, comparison, handoff, submission, effective coverage and retention by segment/channel using permitted minimal analytics. Track outbound clicks separately from known enrollment outcomes and optionally ask why someone chose an external path. Do not invent downstream visibility or change plan ordering to reduce leakage.

Outcome evidence must distinguish research assistance from licensed enrollment. Suitability, complaints and retention use declared cohorts/windows/denominators, independent quality review where appropriate, privacy protections and reported limitations. Health-system and later patient-portal integrations follow actual outcome evidence and specific agreements. These contracts describe required behavior; they do not require a large partner or analytics database before the first real-data query.
