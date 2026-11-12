**Scope after D75 relocation:** [The main master design](../../../../docs/product/MASTER_DESIGN.md) owns shared governance, with [main strategy](../../../../docs/product/STRATEGIC_THESIS.md). The inherited original-flow sections below are preserved context; the ALT73/ALT74 decisions at the end govern this separate :8891 conversation. Do not apply original-only routing to replace it. [Canonical source and operations](../../README.md).

# Daylight master design and agent contract

**D71 current post-summary override · October 22, 2026:** [READINESS_CONVERSATION](READINESS_CONVERSATION.md) governs the installed local readiness interaction. Ten editable answers → summary → one optional inline free-text Chat with Daylight / See plans page, or direct samples if no consequential gaps. Trigger enumerations describe typed reported facts, not visible answer cards. No extra mandatory questionnaire, detail counter, Continue per turn or readiness review screen. D69 is historical research; its legal/source inventory remains useful but its wizard wireframes are superseded. Plan eligibility, quoting and personalized matching remain held.

Version 1.0 · October 21, 2026 · **Design specification only. No UI, storage, data promotion, outreach, deployment, commit or push is implemented or authorized by this document.**

## 1. Authority, reading order and change control

Read [PRINCIPLES.md](../../PRINCIPLES.md) first. D64 adds a binding invariant: confirmed user facts, priorities and plan evidence determine substantive outputs independently of commissions, contracts, referral economics and conversion/LTV. Commercial metadata stays outside eligibility, candidate inclusion, filtering, ranking, fit and AI explanations; optional fulfillment is downstream only. Scope/completeness and unresolved records remain explicit. [Independence acceptance](INDEPENDENCE_ACCEPTANCE.md) defines counterfactual tests, context/feature boundaries, reason records and governance required before recommendation release. This addition does not claim the engine is implemented or relax plan-data gates.

This is the single entry point for future product/design implementation. Read it with the binding [owner requirements](../../DAYLIGHT_REQUIREMENTS.md), then the [node inventory](BRANCHING_NODES.md), [wireframes](WIREFRAMES.md), [flow contract](flow-contract.json), and [acceptance/handoff](ACCEPTANCE_AND_HANDOFF.md). Appendices elaborate this contract; they cannot change its principles. The JSON enumerates nodes and transitions, not executable insurance policy. If a transition and prose disagree, stop that dependent implementation, name the conflict, and propose a targeted correction. Do not let a model choose which source wins.

Precedence: latest explicit owner decision → stable numbered requirements → this master and its versioned appendices → current code for implementation facts only → older proposals as content/evidence. Statutory/source-review and backend admission safeguards are never waived by a design preference. New owner decisions update the requirement register and decision table in the same documentation change. Preserve originals and unrelated uncommitted work.

### Confirmed owner decisions, not open questions

| ID | Decision | Consequence |
|---|---|---|
| D49 | AI agent first, for people comfortable using LLMs; Chapter is a business reference | The agent orchestrates the task, teaching, profile and explanation. A rigid wizard with a chat attachment does not satisfy the vision. It remains a legible guided experience with explicit actions, visual teaching and deterministic safety boundaries. |
| D50 | New / Know some / Comfortable plus free text; voluntary Explain / I know this | Goal never establishes expertise. Interpret free text for confirmation; no quiz, inferred mastery or mandatory repetition. |
| D51 | Same high-level progress phases across routes | Four stable phases below; personalized substeps never renumber the phases or masquerade as completed work. |
| D52 | Something else retains text, confirms interpretation, preserves unknowns | No new insurance rule or unconstrained route generated from prose. |
| D53 | Backend guest profiles without an account; same-browser resume | Replace the old session-only product policy in the planned architecture. Implement no storage merely because this document exists. Cross-device recovery is unresolved and not promised. |
| D54 | Purposeful data persistence and AI context controls | Saving a profile does not silently save all sensitive fields or all chat, and does not automatically authorize disclosure to an LLM or human. |
| D55 | Growing concept picture plus meaningful representative photography | One introduced concept/block at a time for beginners; preserve name/sun; professional warmth and people, not CSS-only changes. |
| D56 | Useful comparison, support and decision preparation; verified-source gates | Distinguish research preference, verified checks, licensed handoff and enrollment. Unsupported personal totals/provider fit/quotes remain explicit. |
| D57 | Master flow, branching wireframes and acceptance govern future changes | Styling-only requests cannot change route, copy meaning, facts, stored fields or evidence gates without a recorded decision. |

D64 additionally governs independence and completeness under [the principles](../../PRINCIPLES.md).

D49–D57 are confirmed design direction. Specific architecture defaults, exact proposed copy, measurements and implementation increments below are implementation proposals to validate, not claims of current functionality or medical/legal approval.

### Superseded-decisions map

| Source / section | Retain | Superseded by this contract |
|---|---|---|
| [PRODUCT](../../PRODUCT.md), Operating Context and Principles | Purpose, active app, useful visuals, person control, safeguards | “Not chat-led” cannot be used to prohibit the newly confirmed agent-first orchestration. Current session-state description is an implementation fact, not future storage policy. |
| [Requirements](../../DAYLIGHT_REQUIREMENTS.md), D01–D48 and settled interpretation | Content, deliberate Continue, Back, unknowns, diagram, contained help, scope | Older “do not reopen journey-first” text yields to D49; D42's tab preference becomes resumable presentation preference when saved under D53. |
| [Vision guide](../DAYLIGHT_VISION_REVIEW_AND_ACTION_GUIDE.md), §§2–9 | Four goals, who, browsing vs personal review, overlay, preparation, comparison dimensions | §3 “Do not add an expertise assessment” yields to voluntary D50. Draft-review status is historical; later requirements record approval. |
| [Learning flow](../DAYLIGHT_LEARNING_FLOW.md), Learning sequence | Relevant visual concepts, reasons, content independence | Beginner lesson before goal; a shown lesson meaning learned; compulsory old order; “no raster imagery needed” as a constraint on D55. |
| [65+ finish plan](../DAYLIGHT_65_PLUS_FINISH_PLAN.md), What to preserve / Confirmed build direction | Warm paper/sage/olive/type, question-answer clarity, visible follow-ups, real user validation | Whole-page help presentation and session-only future policy. Help is a pop-up over the reference picture. |
| [Journey plan](../archive/product-history/DAYLIGHT_JOURNEY_PLAN.md), §§2–8 | Contextual questions, vocabulary, payoff, route-aware content | Fixed stop order, mandatory supplement lesson, age-65 arithmetic, all-screen density and review-mode assumptions. |
| [Guide redesign](../archive/product-history/DAYLIGHT_GUIDE_REDESIGN.md), §§6–8 | Basics A–D; V0–V8 purposes, comparison/timeline/print content | Whole-picture-first, map after fixed eight-question intake, dock as universal help layout, reported A/B marked Done. |
| [Levels plan](../archive/product-history/DAYLIGHT_LEVELS_PLAN.md), §§4–7 | Useful technical/content constraints | Five unlocking levels, late map, animated sun, changing app shell, old chat-first implementation. Agent-first is not a restoration of these specific mechanics. |
| [Aesthetic plan](../archive/product-history/DAYLIGHT_AESTHETIC_PLAN.md), §§3–7 | Accessible typography, source/uncertainty clarity | Mascot/glasses, no photos, decorative paper tricks, unfolding/bloom animations. |
| [UI flow](../UI_FLOW.md), Implemented flow; [Milkman record](../MILKMAN_CHAT_IMPLEMENTATION.md) | Dated service and logging history | Intake→chat as the target UI, automatic final-answer navigation, old intake logging as the new profile policy. |
| [Original prototype design](../../medicare-project-2026-10-17-v1.2/archived-prototype/DESIGN.md), §§1–4 | Separate research/decision/transaction states and provenance ideas | Autonomous no-human transaction ambition, fictional catalog, old text-only UI. Never treat prototype as active application. |
| [Product workflow](../PRODUCT_WORKFLOW.md) | Keeping coverage, full-context qualified handoff ambition | Accounts/invitations/outreach/enrollment are future gated capabilities, not current promises. |
| [Implementation records](../../audit-evidence/VISION_IMPLEMENTATION_2026-10-21.md) | Actual implemented behavior and stated limitations | Tests, screenshots or “complete” headings do not override owner critique or prove usability. |

### D65 current presentation override · owner-approved implementation

The owner approved [the scoped simplification revision](UI_SIMPLIFICATION_REVISION.md) in full on October 21, 2026. This section and contract version `1.1.0-simplified` supersede conflicting presentation requirements below; old node IDs/content remain as compatibility/history, not mandatory screens. [Implementation evidence](UI_SIMPLIFICATION_COMPLETION.md) records technical results separately from owner approval.

- Header sun/Daylight Medicare → fixed four phases → actual question and short relevant teaching. No routine profile/status chips or duplicate assistant headings in the primary stack. **Your guide & privacy** is a labeled secondary utility; errors requiring action remain at the affected task.
- Pair conceptual context with real tasks. No mandatory glossary chain, expertise quiz or invented questions. Learning can finish without personal intake. Optional Explain more/source detail remains. Comfortable depth can hide the map, without claiming mastery.
- Group recipient + optional name; category + browsing/personal mode; ZIP + county reference/ambiguity + year; current coverage + review intent; job status + task; separate employment/coverage end dates. `presentation_groups` and `legacy_aliases` are authoritative; grouped writes are atomic, explicit Continue, no automatic advance.
- A05 is optional save/privacy action, not onboarding. Do not invent a visit/save answer merely to skip it. Consent, sensitive-note saving, receipts, conflicts, edit/delete and same-browser resume remain.
- Replace permanent inline text panel with sun SVG + **Ask Daylight · AI assistant** after Continue/Back. Something else enters answer mode in the same overlay. Interpretation is editable and proposed; **Confirm and continue** is one deliberate combined action with next-task preview. Help return never records inferred facts.
- Ask overlays the map without reflow; 600px desktop, phone 10px sides, available-height layout; compact AI identity/Return header, answer-first single reading area, composer and concise privacy link. Before first transfer, explain actual processor/context and ask permission. Focus trap, Escape, opener, exact draft/scroll/answer preservation remain.
- Only core Medicare/A/B/C/D/Medigap architecture becomes map pieces. Original is A+B with optional separate D and Medigap; C is alternative A+B, usually including D. Drug exceptions are optional detail. Costs, extras, switching and timing are contextual text/checks, not map blocks. Viewing/choosing a category never proves enrollment or fit.
- Unique published ZIP→county may be derived with exact source/period; it is not user-verified residency. Ambiguous county requires choice or explicit unknown. Preserve source and state distinctions.
- D65 removes visible consumer spend indicators only. D63's persistent aggregate $1/UTC-day cap, conservative reservation, fail-closed behavior and no automatic retries remain; `/api/status` retains developer diagnostics. Plan recommendation/validation gates remain held.

### D66 latest route override · ten essential questions

The owner rejected the repeatable Part D/topic cycle and authorized the protected replacement through local activation. [TEN_QUESTION_CONTRACT](TEN_QUESTION_CONTRACT.md) is authoritative for the new default's screen sequence. It supersedes D65 topic-menu routing and earlier dynamic route skipping: T01…T10, then editable summary, for every goal/familiarity. There are no definition-only pages or second questionnaire. AI adapts explanations and may fill a current unconfirmed draft after permission/confirmation; it cannot change navigation or confirmed answers. All other source, independence, privacy and budget requirements remain.

Runtime and tests use `apps/ten-question/guide-contract.json` plus the small `ten-state.js` finite policy. The old `flow-contract.json`/`apps/chat` remain intact for the preserved previous guide, not as competing default navigation. Legacy saved state is not silently translated. Separate protected guest storage/session and an explicit previous-guide link preserve recovery. [Verification, activation and rollback](TEN_QUESTION_EVIDENCE.md).

### D67 accepted direction and minor refinements · October 22, 2026

The owner accepted the ten-question direction. Preserve D66's sequence and revise only the requested controls: **Choose a start month** opens labeled Month and Year selectors with no silent new default; confirmed old values prefill exactly, ambiguous wording remains preserved until explicitly changed. No exact day or eligibility conclusion. The owner clarified that only the summary continuation, **See plan options**, belongs above the answer list. Question 10 keeps ordinary **Continue** below its priorities, consistent with the other question screens; remove its top Review your answers action. Keep one primary action and no competing duplicate. Plan options has the same sun-agent Ask overlay with sample/held-page context and preserved return state; remove its official Plan Finder promotional CTA while keeping necessary provenance/limitations.

Database-backed search remains future intent with **target field/dataset unresolved**. Do not infer a search scope or build tomorrow's data integration from this feedback. [D67 implementation evidence](TEN_QUESTION_REFINEMENTS.md).

### D68 guide clarity · October 22, 2026

At Q4's first A/B introduction, show **Two main ways to get Medicare coverage** with equally prominent Original Medicare and Medicare Advantage paths. Q5 introduces optional Medigap beside its first choice mention, belonging only with Original Medicare, alongside the separate Part D option; most Advantage plans include D. Q7/Q9 add drug/cost detail rather than delaying the first-use explanation. Q6/Q7 reveal Your doctors / Your medications as separate personal-needs annotations, updated from local drafts without promoting them to confirmed/saved facts. Continue-confirmed reports persist through later states/resume subject to existing sensitive-note saving choices. Unknown, None, add later and redacted/unavailable notes stay distinct. No automatic focus/scroll, extra questions or implied network/formulary verification. This supersedes older reveal timings. [Evidence](GUIDE_CLARITY_EVIDENCE.md).

### D69 readiness design · October 22, 2026

The owner requested the next proposed component between T11 confirmation and personalized matching: a finite, source-backed readiness check with zero or more consequential clarifications, explicit unknown/defer, reused confirmed Ask facts and capability-specific limitations. One brief contextual intro and exactly one short why line per follow-up; detailed law/sources stay in optional help. [Readiness contract](READINESS_DESIGN.md) and its triggers/sources/acceptance/wireframe define the researched proposal. **This task does not integrate it into the live app or approve legal predicates, new guest fields or plan matching.** D66/D68 remain the current implemented route. Expert rule review and accepted data/integrations remain independent.

## 2. Product promise, audience and success

Daylight is an AI-assisted Medicare research service. It helps people understand their situation, explore relevant evidence, articulate a preference and prepare the next action. Older adults, approaching-eligibility users and caregivers vary in Medicare knowledge, cognitive needs and device confidence. Being comfortable with an LLM does not establish Medicare expertise or remove accessibility needs.

The agent speaks plainly and warmly, addresses the covered person consistently, asks why/what matters, explains tradeoffs, and builds context with the user. It may respond to a multi-fact paragraph, revisit a topic, change a goal or recommend a useful next question. The user can always see the current task, the reason, what was recorded and the way forward. They are not required to reconstruct a transcript to understand their state.

Valid endings: learning summary; scoped published comparison; keep current coverage; undecided with checking tasks; transition preparation; qualified human handoff when operationally supported. Success requires the person to explain the comparison or next step, recognize uncertainty, correct a fact and recover from help. Fast completion or a confident statement alone is insufficient.

Scope: national education when reviewed; currently documented local catalog is published 2027 Collier County, Florida. Location resolution elsewhere does not imply available local records. No personal suitability/recommendation service, insurer Medigap quote, personal total-cost estimate, clinical-provider match, contact, cancellation or enrollment becomes available without its separate verified evidence, authority, integration and admission gates.

## 3. The experience: agent first with a durable visual task

### Stable common phases

Always show `1 Your goal → 2 Your situation → 3 Your options → 4 Your next step` in this order, with visible text and current state. Do not generate labels, renumber phases, hide them because a route is short, or add a percentage whose denominator changes. Below the track, show one truthful personalized task, such as “Your situation · Medicare enrollment” or “Your options · Compare published drug plans.” Education-only may label the situation/options phases “Optional for this visit”; do not mark them answered or failed.

A phase state is `current`, `visited`, `information_recorded`, `optional_for_goal`, `not_started`, or `needs_review`. These describe the guide, not competence, eligibility or a completed outside service. The track is navigation/status, not a set of competing answers. Back moves through actual navigation history, including personalized substeps and help return frames. Editing may move focus to an earlier phase; previously entered later work remains reviewable.

### Primary workspace composition

On desktop: stable header/track; left task surface with the actual question, short contextual teaching and large choices; right growing core Medicare picture. Continue is the only prominent page advance. Back and the compact sun-agent Ask launcher remain below the choices. Something else opens answer entry in the same overlay; sending only proposes reports. Explicit Confirm and continue applies reviewed reports and moves to the previewed task. Keep an optional full conversation history out of the task's primary reading order. The agent is the active conductor through context, questions and explanations, not merely the help button.

On tablet: retain the two areas if both meet readable widths; otherwise stack the compact current concept close to the question. On phone: phase summary, current task/why, compact concept, choices/free text, Continue/Back/Ask, then deeper reference. Stable concepts never consume the entire first screen and push the task out of reach. Breathing room takes precedence over forcing all content into one viewport.

From the first primary-composer use, show: “Your submitted text is sent for AI interpretation. Saving it for later is a separate choice. Do not enter ID numbers.” Explain actual processors/logging before enabling it. Sending text authorizes that request, not durable storage or automatic attachment of sensitive profile lists. A person declining AI transfer can use manual choices and reviewed explanations.

Free text may contain several answers, an explanation request, or a goal change. The agent distinguishes these intents, responds to the question, and proposes any data changes in X01. Confirming several facts may satisfy several nodes; the scheduler then proposes the first remaining eligible task. It explains skipped repeated questions (“You already told me…”), without displaying them as completed external checks. No automatic next-screen jump on extraction, answer selection or the model finishing a reply.

## 4. Profile and state architecture

### Ownership and value envelope

One anonymous guest identity can own one or more explicitly selected subject guides; do not silently mix a parent's answers into the user's own profile. MVP proposal: one active subject per guide, one active saved guide per browser; switching subject creates a separate guide or requires explicit replace/retain choice. Caregiver role is research context, not proof of permission for regulated disclosure or transaction.

All decision-relevant values use an envelope, not a bare boolean:

```json
{
  "field": "coverage.enrollment",
  "value": "ab",
  "status": "reported",
  "confirmation": "confirmed_by_user",
  "rawText": "I have A and B",
  "source": {"kind": "user_text", "nodeId": "C00", "actor": "guest", "eventId": "opaque-event"},
  "capturedAt": "ISO-8601 UTC",
  "confirmedAt": "ISO-8601 UTC",
  "evidenceRefs": [],
  "sensitivity": "personal",
  "saveScope": "guest_profile",
  "revision": 3
}
```

`status` = unanswered / reported / unknown / skipped / derived / source_supported / conflicting / stale. `confirmation` independently = not_required / proposed / confirmed_by_user / rejected. User confirmation establishes what the person reported, not independent truth. Source-supported requires evidence for the exact fact, subject/entity, location/year, scope and date. Never convert `unknown`, absent, not-applicable, zero or conflicting into each other.

### Aggregate schema

| Namespace | Required design fields / constraints |
|---|---|
| `profile` | opaque server ID; schemaVersion; stateVersion; created/updated/expiresAt; subjectId; policyVersion; no ID embedded in public links |
| `intent` | entryMode; goal enum learn/compare/review/job/unresolved; raw goal; comparisonMode browse/personal; desiredChange keep/replace/add/unknown; jobTask; requested comparison category; statedPreference with timestamp and snapshot |
| `subject` | self/someone/other; optional displayLabel; suppliedBy; authority remains unverified unless a future authorized process establishes it |
| `knowledge.general` | new/some/comfortable/unknown/skipped; raw description; confirmation; explicit teaching-depth preference, independent of intent |
| `knowledge.topics[id]` | seenAt; lastExplainedAt; selfReport familiar/wants_explanation/unknown; user “makes sense” acknowledgment optional; no automatic understood flag or inferred competence |
| `coverage` | enrollment ab/a/b_only/parts_unknown/no/unknown/other; socialBenefits; existing coverage components; actual/scheduled Part B month; birth month/year + first-day answer only when relevant; job/retiree/COBRA/military/Medicaid context, employer size, separate end dates, creditable-drug notice status |
| `needs` | medicine status; optional medications with raw/extracted/confirmed identity and unresolved strength/form; pharmacies; provider names/specialty/location; benefit needs; priorities and optional order; no source-match ⇒ personal coverage implication |
| `comparison` | requested scope; location source; target year/effective timing; category; query/filter/sort; accepted snapshot ID; exact candidates and savedAt; source/data versions; missing fields; rationale; explicit exclusions; stale reason |
| `checks` | check ID, reason, dependencies, status open/reported_done/source_confirmed/not_applicable; owner/user task; supporting receipt; no “done” from merely reading a lesson |
| `outcome` | nextTask; editable versioned drafts; research preference; summary; handoff request/payload/receipt states; no automatic outreach |
| `privacy` | persistence choice; notice/policy version; optional sensitive categories; chat-history choice; model-context disclosure/choice; retention config ID; scoped deletion requests |
| `flow` | currentNode; stable phase; navigation stack; eligible nodes; lesson queue; return frame; pending confirmed proposal; dependency invalidations; previous input drafts; current explanation/picture preference |
| `sync` | local dirty fields; acknowledged stateVersion; pending operation ID; status saving/saved/unsaved/conflict/offline; server receipt; save failure never mislabeled Saved |
| `history` | minimal typed semantic changes with before/after revisions, reason, timestamps and actor; content-bearing undo history inherits field sensitivity and deletion scope; no hidden chain-of-thought |
| `chat` | unsent draft; current exchange; chosen saved history summary; explicitly permitted context; raw transcript persistence off by default pending policy decision |
| `capabilities` | versioned education/catalog/quote/provider/pricing/rules/handoff/service availability and exact admission state; the model cannot modify it |

### Commands and persistence

Use a server-owned aggregate with typed command validation, optimistic concurrency (`expectedStateVersion`), idempotency keys for every mutation, server timestamps and auditable rule IDs. An operation either produces one acknowledged revision or a clear failure/conflict. Suggested command API names below are contracts, not a vendor/hosting choice. GET reads require the same guest authorization as writes; profile IDs are not authorization.

Do not store every keystroke remotely. Keep drafts locally in memory until explicit submission or an enabled, disclosed save action. After Continue or confirmed patch, persist eligible confirmed fields in one transaction; display Saving → Saved only after acknowledgment. Sensitive visit-only fields remain in memory and are excluded from durable snapshots, logs, undo payloads and cached AI summaries. Their absence on later resume is explained rather than inferred as no medicines/providers.

`ApplyConfirmedPatch` validates allowlisted field paths, enum/type/range, subject, revision and declared provenance; conflicts create X01/X03 review. `RecomputeGuide` returns rule IDs, eligible next tasks and affected summaries. Changes are not model-written database patches. `Undo` creates a new revision restoring permitted previous values; it cannot undo an external transmission or resurrect deleted content. Redaction/deletion must purge sensitive historical values as well as current state.

## 5. Agent, deterministic policy and flow scheduler

### Responsibility boundary

| Agent can propose | Deterministic service must decide |
|---|---|
| Interpret plain language, summarize, explain a reviewed concept, ask the next relevant eligible question, suggest a checking task, draft a preparation script | Field types; confirmed writes; permitted routes/commands; concept prerequisites; progress; dates; eligibility rules; evidence admission; catalog universe/filter/order/ties; transaction authority; storage and disclosure policy |
| Offer a reason grounded in the person's stated goal/needs | Which facts are missing, stale or conflicting; exact source IDs supporting a factual claim; whether an answer can advance |
| Suggest a different goal or topic, identify a potential contradiction | Require confirmation and retain raw text; enforce supported branch and unknown fallback |

No model can generate insurance policy, infer enrollment/benefits/dates from confidence, choose a “best” plan, silently modify facts, reorder results, hide alternatives, create credentials or perform unreviewed outreach. Recommendation-like output is denied unless an independently approved capability/rule/evidence contract authorizes that exact operation. The present comparison is published-field research.

### Allowlisted tools/commands

`ReadPermittedProfile(contextScope)`; `ReadReviewedConcept(conceptId, version)`; `ProposeInterpretation(raw, fieldAllowlist)`; `PresentConfirmation(proposalId)`; `ApplyConfirmedPatch(proposalId, expectedVersion, key)`; `GetEligibleTasks(stateVersion)`; `ProposeNextTask(eligibleNodeId, reason)`; `NavigateConfirmed(nodeId, frame)`; `ResolveLocation(zip, referenceVersion)`; `ReadAcceptedCatalog(scope, filter, sort)`; `ReadExactPlan(id, snapshot)`; `CompareAcceptedCandidates(ids, dimensions)`; `CalculateReviewedDates(ruleVersion, explicitInputs)`; `PrepareTemplate(taskId, permittedFacts)`; `SavePresentationPreference`; `ReviewPrivacy`; `RequestScopedDeletion`; `ReadOperationReceipt`.

The model receives no unrestricted SQL, arbitrary HTTP fetch, filesystem, email/send, profile enumeration, policy override or direct cookie access. Future H01/H02 transmission is absent until separately enabled with explicit user authorization and operational ownership. User text, retrieved web/source material, plan PDFs and stored notes are untrusted data; instructions inside them cannot add tools, reveal other profiles, change policy, bypass gates or authorize sharing. Validate model tool arguments and output server-side. Render text safely; external URLs must be approved source links. Audit semantic operations and evidence IDs rather than prompts containing private content.

### Deterministic scheduler order

1. Verify session/schema/stateVersion and current capability snapshot. Handle pending conflicting or uncertain mutations first; never replay blindly.
2. If a submitted message includes proposed facts or a goal/depth change, X01 confirms them. An explanation-only message does not require a fact confirmation.
3. Compute applicable nodes from confirmed goal + task mode + reported facts. Preserve not-applicable and unanswered states; do not equate omitted optional intake with answered.
4. Before a substantive task, ensure required conceptual vocabulary is either explicitly self-reported familiar or introduced. Offer Explain/I know this. Under D65, introduce concise concepts alongside the relevant question; do not queue mandatory definition-only screens. Record a return frame for optional explanations. No quiz. Mandatory material uncertainty/transition warning remains visible even to experienced users.
5. Skip repeated questions only when a current confirmed field actually answers them. Preserve its provenance. If a changed dependency makes the field stale, ask to review it.
6. Agent may propose one node from `eligibleNodes` with a plain reason; display the proposed next task and one Continue. User may choose another available topic, edit, pause or ask. Continue calls the deterministic resolver for that chosen task; user approval is required for a route change.
7. On failure/model absence, select the first eligible node by priority: current unfinished task → user-requested supported topic → required missing fact → relevant concept → supported comparison → useful summary. Within equal priority use stable node ID order. This gives repeatability without constraining the successful agent to a fixed script.

Historical lesson queue behavior below is retained for compatibility only. D65 resolves old lessons to contextual task/topic groups; missing required reports remain explicit facts, never a reason to force glossary screens. The agent cannot invent a bypass. All lesson answers resolve via `@after_lesson`: next queued concept → saved return node → default education next. This override is explicit in JSON. A local one-topic definition can instead open X10 without changing the route.

Personal-review entry sets `personalReview=true` explicitly. It returns through missing recipient only if necessary; it must not restart knowledge or broad goal questions already confirmed. Browsing never needs the entire coverage/needs profile. General education never needs location, birth timing or identifying details.

### G1: events inherited by every node

| Event | Required behavior |
|---|---|
| Answer selection | Change local input/selection state; show consequence if useful. No route advance. |
| Continue | Validate; confirm user-entered values; acknowledge eligible save or show unsaved failure; then resolve exactly one next task. Single valid form Enter uses this same path. |
| Free text / Something else | Preserve verbatim input. Agent proposes typed interpretation; X01 shows what will be recorded and asks confirmation. Unresolved details stay unknown; no new insurance rule. |
| Back | Pop actual navigation frame; restore choices/text/scroll; do not erase answers, change goal or reopen hidden guide. At root, show arrival without clearing work. |
| Edit | Open relevant node with return frame; compare revisions; confirm changes; invalidate dependent conclusions; return to review affected results. |
| Skip | Only declared optional fact; store skipped explicitly. “Unsure” is a reported unknown, not a skip. Required catalog context may be unknown, but local results then remain unavailable. |
| Explain / I know this | Explanation or explicit familiarity applies per topic. No competence inference; do not set enrollment facts. Keep essential tradeoff/uncertainty visible. |
| Help / Escape / Return | X10 over picture; no underlying reflow or route mutation. Restore exact node/input/candidates/draft/opener/scroll. |
| New goal | Confirm intent change; retain reusable subject/facts/notes/candidates; rebuild eligible tasks and mark obsolete derived outputs stale. |
| Service/model error | Preserve input and pending status; reviewed local explanations available; Retry + clear alternative; no fabricated answer or success. |
| Save conflict / uncertain outcome | X03; query operation receipt; compare revisions; avoid duplicate mutations. |
| Outside/unsupported/unknown scope | X04; preserve exact request; national education/official alternative; never substitute Collier or another year. |
| Start over | Distinguish new visit, new subject, clear local drafts, forget browser access and delete server profile. Explicit scope/confirmation for destructive operations. |

### Return, dependency and invalidation contract

A frame contains node ID, subview, phase, scroll anchor/offset, stable focus key, local draft, selected candidate IDs, filter/sort/page and guide visibility. If an opener disappears after an explicit edit, restore focus to the current task heading and announce why. A return token is generated by the service, allowlisted to inventory nodes and bound to subject/revision; never trust an arbitrary model-supplied destination.

| Changed input | Preserve | Invalidate / recheck |
|---|---|---|
| Goal or comparison mode | Subject, confirmed coverage, notes, priorities, candidates | Applicable-node plan, next-task suggestion, comparison rationale, preparation context; no automatic knowledge change |
| Knowledge or guide preference | Every personal fact and candidate | Teaching queue/presentation only; no catalog ordering or eligibility change |
| Subject | Previous guide in separate scope if retained explicitly | Never reuse prior person's facts/medicines/providers in the new subject; fresh proposed profile |
| ZIP/county/year/category | Personal facts/notes and old candidates for reference | Accepted query/snapshot/price assumptions/current comparison/preference context; mark candidates stale or out of scope |
| Enrollment/current coverage | Independent preferences and notes | Derived dates, required current-benefit questions, replacement warnings, current-policy baseline, scripts |
| Birth/first-day/Part B month/job dates | Original reported dates/history | All dependent windows and time-sensitive tasks; recompute with versioned reviewed rules, never substitute forecast for confirmed dates |
| Medicines/pharmacy/provider/benefit needs | Other entries and candidates | Relevant match/cost/check status; new name != verified identity; remove stale positive reassurance |
| Priority/order | All facts and candidate selection | Explicit supported sort/rationale; unscored priorities stay checking tasks |
| Data/source/capability release | User inputs and old snapshot with timestamp | Accepted result validity, source claims, supported service; renew through existing admission path |
| Draft's source facts | Edited draft as previous version | Flag “Details changed—review this draft”; regeneration creates new version, never overwrites edits silently |

## 6. Growing Medicare picture and teaching depth

The picture is a conceptual model, not proof of enrollment. Separate “What this piece means” from “Your reported coverage.” Labels may say Not answered / You reported / Confirmed by [source/date] / Needs checking; color alone never conveys state.

| Concept ID | Add exactly this item | Dependency / intended moment |
|---|---|---|
| medicare | One Medicare block | L00; nothing else visible on a fresh beginner picture |
| part_a | Hospital-care block | Medicare → L02 |
| part_b | Medical-care block | A → L03; no Part B start-date inference |
| original | Connect A+B as Original Medicare | A+B introduced → L04 |
| drugs | Prescription coverage block beside the foundation | Original → L05, relevant medicine/topic question |
| extras | Inline checking explanation only; no core-map block (D65) | Original → L06; not a verified plan-benefit block |
| premium | Inline explanation only; no core-map block (D65) | Original → L07 |
| care_cost | Inline example only; no core-map block (D65) | Premium → L08; example is clearly labeled |
| cost_limit | Inline scope caution only; no core-map block (D65) | Care cost → L09; restricted scope is visible |
| advantage | Alternative A/B arrangement block | Original → L10; never depict Medigap as an Advantage add-on |
| routes | Connect the two introduced arrangements | Advantage → L11; only already-introduced components expand |
| medigap | Optional Medigap block under Original | Original + care-cost context → L12 |
| switch_rights | Contextual caution only; no core-map block (D65) | Medigap → L13; no guaranteed ability to switch |
| enrollment_timeline | Contextual dates/checks; not part of core coverage map (D65) | Relevant user facts plus reviewed rule; general diagram when facts missing |

Default new/unknown: introduction and one block at a time. Know some: agent asks/uses per-topic familiarity and offers concise summary with Explain. Comfortable: concise reference initially hidden, explicit Show available; no concepts marked seen merely because of global familiarity. “Show full reference” is a separate explicit request after a concise explanation of what it contains; only changes presentation, never records understanding. Returning Back retains the introduced concept set, highlights the current concept, and does not suddenly reveal future pieces. Editing a reported fact updates its status annotation; it does not delete conceptual learning. Reset/new subject rules apply separately.

Show/Hide Medicare guide is always text-labeled and remembers the person's explicit preference. Save that preference only if guest persistence enabled. Hidden guide does not remove the task's reason, terms, warnings, source link or help. Named pieces open short local explanations with Back to picture; Ask more opens X10 and supplies the selected topic. Never stack a local explanation and a separate active chat overlay.

## 7. Visual system and component contracts

### Warm, professional art direction

Preserve the existing Daylight name, header sun/fav icon, warm paper, sage/olive accents and readable Atkinson Hyperlegible/Fraunces relationship. Avoid a duplicate hero logo, childish mascot, points, badges or decorative animation. Do not interpret this as permission to recreate the old all-chat levels design.

Meaningful photography is part of the planned visual work: one capable older adult using a laptop/tablet in an ordinary home; a caregiver/parent pair reviewing information together; an active older person in a transition/preparation context. Represent varied ages, skin tones, bodies, abilities and family relationships respectfully. Use natural light, warm believable materials, calm expressions and real activity. Avoid staged white coats, a doctor implying endorsement, frailty shorthand, “happy customer” captions, fabricated testimonials, stock handshake/call-center clichés or photo subjects implying they bought a particular plan.

Placement: a modest arrival image alongside/below the centered introduction on wide screens, cropped below actions on phones; a caregiver image only at a relevant introductory/support moment; optional meaningful next-step image. No photo above every question, behind text, inside plan rankings or beside a favored candidate. Do not reintroduce the removed landing diagram/three-step preview. This expands D38/D40 composition without displacing the main actions. Review image alternatives with the actual user flow in a later authorized implementation; no asset purchase or generation is done here. Local licensed assets, accessible alt text when informative, responsive crops/size limits and current CSP/release packaging are acceptance requirements.

### Components

| Component | Contract |
|---|---|
| StableProgress | Fixed phase IDs/labels/order across routes and widths; `aria-current=step`; status words; no moving denominator; meaningful optional labels |
| AgentTask | One short agent explanation, literal question, why, supported answer controls, optional free text and direct visible state summary; no giant transcript ahead of the task |
| AnswerChoice | Entire card tappable; native radio/checkbox semantics or equivalent tested behavior; text labels; selected/unselected/focus/error; no default or click-and-advance |
| ContinueBar | One primary Continue, lower-emphasis Back then Ask; predictable position near task; invalid stays with message; no overlapping sticky actions |
| InterpretationReview | Raw text and editable proposed fields/status; confirmed changes separated from unresolved notes; Confirm / Edit / Keep unknown / Return; model confidence never substitutes for confirmation |
| ProfileSummary | “What you have told Daylight”; optional collapsed detail after summary, explicit Edit/Remove; independent reported/source-backed/unknown states; masked sensitive list on resume |
| ConceptPicture | DOM text and semantic grouping, current concept emphasized, nonfuture pieces only, local definitions, persistent Show/Hide, print readable without color |
| SourceEvidence | Fact-level source name/date/scope; evidence drawer available; direct source links; no invented Reviewed seal; no blanket “verified” label |
| SaveStatus | Saving/Saved/Not saved/Conflict/Visit only with time/revision; clear review/delete entry; no silent durability assumption |
| Preparation | Editable task template, source facts and unknowns, Copy/Edit/Print, Prepared—not sent; data changes flag previous draft |
| Recovery | Clear failure scope, preserved input, one retry, useful local/official alternative, no raw JSON/stack trace |

Proposed metrics: body/answer text 18px minimum base, secondary text normally 16px+, relaxed line height around 1.5, prose about 55–70 characters; primary controls generally 48–56px tall; 16–24px component gaps and 24–40px section separation. These are Daylight design defaults, not claims of universal WCAG pixel requirements. At large text, use content reflow, not fixed card heights. Keep 320px CSS-width access and generous phone edge spacing. Exact tokens can be refined only after the flow is stable and measured on target devices.

### Ask Daylight pop-up

Desktop: dialog anchored over the reference/Medicare picture side, approximately 400–520px readable width if available, not a new column or a workspace resize. Underlying task remains visually recognizable and inert while modal. If reference hidden or insufficient room, center the same dialog with a short task reminder; do not unhide/reflow the picture. Tablet follows available width rather than a brittle device label. Phone: bottom sheet that can expand to available viewport for reading/keyboard; visible Return at top, composer reachable, one main reading region. Never constrain all help to a tiny tooltip.

On open store the return frame, contain focus, mark background inert and `aria-modal=true`. Focus the question/answer heading for suggested-topic reading; do not summon keyboard automatically. Textarea focus occurs when explicitly requested. Tab/Shift+Tab cycle; Escape/Return close; no click-outside-only close. Answer first, then useful supporting picture/source; two relevant visible follow-ups and explicit Send; history accessible by text label. Current question stays identifiable. Preserve unsent draft/current exchange/history and reading position on close/reopen. A model reply cannot scroll the underlying task, overwrite an answer or submit its form. Send and Continue are distinct events; composition/notes/Shift+Enter do not advance anything. Announce reply readiness without reading every token repeatedly.

## 8. Guest persistence, privacy and security

### Proposed baseline

Backend guest profiles, no account required, same-browser resume via a cryptographically random opaque session cookie. First storage choice describes server storage in plain language. Cookie is Secure, HttpOnly, SameSite appropriate to same-origin flows; use HTTPS in deployed environments, server-side expiry/revocation/rotation, CSRF protection and per-request object authorization. Secrets never appear in URLs, localStorage, analytics, model context, application logs, print or exported profile links. Profile/session IDs are separate; do not expose a shareable bearer recovery URL. Bound session lifetime and idle expiry through reviewed configuration. Vendor/hosting/database are deliberately unselected.

Same-browser access is device possession, not strong identity verification. Shared-device notice is mandatory. On resume show a masked high-level summary and Resume/Separate visit/Manage, not medicine/provider names immediately. Provide explicit Finish and remove browser access. Removing a cookie does not prove server deletion; if it leaves an unrecoverable guest profile, offer deletion first and explain the limit. Cross-device recovery, multi-person invitations and lost-cookie recovery need a separate secure design; do not promise them.

### Data choices and limits

| Category | Proposed behavior |
|---|---|
| Goal, knowledge, confirmed answers, non-sensitive presentation, candidates | Save after clear guest-save acknowledgment and command success; every value reviewable/editable/removable |
| Birth timing/job details | Minimum required month/year/context only; disclose purpose; avoid collecting full DOB, employer identity or unnecessary financial history |
| Medicines, providers, pharmacies, health-revealing free text | Optional granular save choice before durable write; default no remote sensitive save until affirmative selection; visit-only alternative |
| Raw goal/knowledge/Something else | Retain verbatim in the selected save scope for interpretation review; minimize irrelevant personal material and allow removal |
| Chat transcript | Unsaved by default in this design; offer explicit history choice only after retention/provider review. Existing local chat logging is current behavior to reconcile before launch, not authority to silently log the new guest experience |
| AI request context | Current question, user-submitted message, necessary confirmed facts and knowledge preferences only; preview/explain categories; sensitive lists only after explicit use-for-this-task approval. Saving and AI disclosure are different choices |
| Telemetry | Event IDs, node/rule/schema version, latency, error code, counts, capability/release IDs; no raw private prompts, names, medicine lists, session secrets or model reasoning |
| Deletion | Revoke access promptly, remove live profile plus content-bearing histories/summaries/caches, track receipt. Clearly disclose any reviewed backup/legal retention exception; do not promise instant removal from every vendor |

Do not display a retention duration until an owner-approved policy is configured. The notice must identify stored categories, purpose, expiry, deletion route, relevant processors and limits. Failure to resolve retention/processor/legal obligations blocks production persistence, not specification work. Encryption in transit/at rest, least privilege, tested cross-profile isolation, export/deletion access checks, backup handling, monitoring and breach ownership are required before production. No legal compliance or anonymity guarantee is made; “guest/no account” is more accurate than promising anonymous health data.

Offline proposal: reviewed local education and unsent drafts continue in memory; no service-worker caching of private responses or localStorage of sensitive profiles by default. Show Unsaved while disconnected; retry only from the acknowledged revision. On reload without network do not imply backend data is accessible. When live AI fails use reviewed explanations and deterministic eligible tasks; when catalog fails do not invent results.

## 9. Comparison dashboard and decision support

O07–O10 are the specified future dashboard behavior; the current app has parts of browsing/comparison, not proof of this finished dashboard. Maintain current scope, admission and unsupported-data boundaries.

Desktop dashboard: context line category/year/location + Edit; concise user priorities and baseline; main grid of identical plan cards; persistent candidate tray that does not cover content; Ask below the task actions. Use same order and labels in card/detail/compare. Phone: one readable card column; comparison is one dimension group at a time or labeled columns with accessible controlled scrolling—never a miniature three-column table. A clear “What differs?” walkthrough highlights supported field differences without ranking personal suitability.

| Consistent dimension | Display rule |
|---|---|
| Identity and scope | Plan/carrier/category/type; exact contract-plan-segment; year/geography; snapshot/source date |
| Monthly plan premium | Units/year known; zero displayed as $0; Part B and other components separate; unknown not zero |
| Medical spending limit | Covered-cost scope and network applicability; not a total annual cap for all costs; N/A distinct |
| Drug deductible / published drug facts | Same basis across columns; no personalized pharmacy total without supported calculation |
| Provider access | Source-backed exact entity/plan/year confirmation if available; otherwise explicit checking task; name matching not participation |
| Medicines/pharmacy | Separate identity match, formulary evidence, restrictions and personal pricing; unresolved strength/form or missing price visible |
| Extras | Conditions/limits only where reviewed; need selected != benefit match |
| Quality rating | Correct level/year/source; no fabricated plan-specific stars from a different reporting grain |
| Eligibility/switching | Restricted plans identified; unknown remains unknown; no enrollment-right inference from catalog inclusion |
| Current coverage | Baseline with reported policy facts and missing information; Keep available; no fake full-cost comparison |
| Evidence/unknowns | Missing/conflicting/stale entries and source links beside claims; every column has same row set |

Default order: source order unless a supported explicit user-controlled sort is chosen. Preserve all accessible results with visible filters, result count, Show more and Clear filters. Rationale states field and direction, missing/conflict placement, tie-break and unscored priorities. Proposal: valid values ascending → unknown/conflict not numerically ranked → deterministic source-order tie break; existing accepted engine behavior must be documented/migrated before changing it. Doctor/travel/benefit preferences do not silently filter plans or become unvalidated scores. Never style the first plan as recommended.

Two modes: same-role exact plans, or educational coverage-structure comparison. Do not place an MA-PD premium against a PDP-only premium and claim the latter is the price of Original Medicare. Bundle/total-cost mode remains unavailable until all necessary components, evidence and calculation assumptions are supported. Medigap education O11 is not an insurer quote. Personal preference is explicitly confirmed against a current snapshot and remaining checks; uncertainty can remain a useful ending.

Human handoff states: unavailable → preparation only; draft → reviewed → explicitly approved for exact recipient/content → requested → sent with receipt → acknowledged/scheduled → completed, with failed/cancelled/uncertain alternatives. Submission/acceptance/effective coverage are different future transaction states, never aliases for a research selection. Do not add live outbound tools or UI promises without separate authorization and qualified operational capability.

## 10. Accessibility, comprehension and evidence

Target WCAG 2.2 AA with a separately scoped assessment. COGA is supplemental cognitive-usability guidance, not a normative WCAG checklist or certification. The [acceptance appendix](ACCEPTANCE_AND_HANDOFF.md) maps both to observable checks, including real screen-reader speech, text enlargement/reflow, focus, touch, keyboards, accidental edit recovery and comprehension. A synthetic browser test, heuristic score or detector cannot substitute for those checks.

Preserve source-linked medical/legal content as reviewed content. Domain reviewer approval is required for exact insurance wording, calculations and source/version changes before consumer promotion. Claims shown here as proposed copy do not bypass that gate.

## 11. Delivery increments and non-drift rule

See the acceptance/handoff appendix for scoped implementation increments, dependencies and stopping rules. No implementation is authorized by this document. A future request should name the increment, requirement IDs, nodes/components and evidence expected. Implement behavior/state before styling; preserve the current frontend and accepted backend gates. Do not use a visual polish request to remove content or redesign the route.

Each change records: changed requirement/decision; nodes and field dependencies; wireframe/component revision; meaningful regression evidence; rendered device checks; unknown validation. Completion means the authorized slice meets its acceptance and limitations are stated—not that the whole service is ready.

## 12. Remaining owner/operational decisions

These do not block this design package, but dependent production capability must wait: actual retention/expiry/deletion/backup policy; model/provider data processing and raw-chat history policy; approved sensitive-data consent/notice language; guest recovery beyond the same browser; subject switching/multiple saved guides; data/source freshness and domain acceptance; supported provider/pricing/Medigap APIs and rights; qualified handoff operator/availability; localization and observed participant research. Do not substitute invented defaults for these operational approvals.

## 13. Sources and traceability

Local evidence: [PRODUCT](../../PRODUCT.md); [D01–D48](../../DAYLIGHT_REQUIREMENTS.md); [Vision guide](../DAYLIGHT_VISION_REVIEW_AND_ACTION_GUIDE.md) §§2–9; [65+ finish plan](../DAYLIGHT_65_PLUS_FINISH_PLAN.md), What to preserve / Priority findings / Release checks; [archived visual inventory](../archive/product-history/DAYLIGHT_GUIDE_REDESIGN.md) §§6–8; [archived journey](../archive/product-history/DAYLIGHT_JOURNEY_PLAN.md) §§2,5–9; [latest implementation](../../audit-evidence/VISION_IMPLEMENTATION_2026-10-21.md); [current architecture](../ARCHITECTURE.md); [current service limitations](../CURRENT_STATUS.md); [ZIP reference](../ZIP_COUNTY_REFERENCE.md). These describe intent or dated implementation, not newly verified readiness.

External references read October 21, 2026: [W3C COGA](https://www.w3.org/TR/coga-usable/) §§4.2–4.9,5; [WCAG 2.2](https://www.w3.org/TR/WCAG22/); [WAI-ARIA modal-dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/); [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html); [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html). Design/security decisions here are Daylight proposals using those references, not claims of endorsement or certified compliance.

Factual copy/rules must be reviewed against [Medicare coverage options](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options), [Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics), [enrollment timing](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-can-i-sign-up-for-medicare), and [working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65). Retrieval supports this design review, not exact-release consumer acceptance. SeniorSimple's planning sequence is a reference, not a suitability algorithm; do not encode a freedom-versus-premium binary as insurance advice.


## D72 · Approved bounded readiness correction · October 22, 2026

Owner approval: open A few details to check directly from the summary using the existing Ask Daylight panel inline, retaining the accepted guide and See plans bypass. Explain why and show a dynamically computed count of currently unresolved profile details: one reply may cover several and may reveal another. This explicitly supersedes D71’s prohibition on a count, without adding a second questionnaire or per-turn Continue. Check each message against all later conditional fields; maintain reported/tentative/unknown/deferred facts and external source holds separately. Preserve existing guest privacy/version/isolation, budget cap and held recommendation/data gates. RC research is not domain-approved. Runtime before-images: `audit-evidence/readiness-correction-20261022/before/`.

Current bounded implementation and limits: [D72 correction](READINESS_CORRECTION.md).


## ALT73 · Parallel chat-first comparison surface · October 23, 2026

Owner authorized an isolated alternative, preserving the original app on 8890. The accepted landing page, branding, photo and copy stay unchanged. Get started opens one continuous conversation containing the ten baseline semantics and applicable existing RC followups, inline suggestions plus free text, honest dictation fallback and information-based progress. Existing D64 independence, consent, shared $1 UTC-day budget, source-validation and sample-plan gates remain. This supersedes fixed-screen/D71 suggestion restrictions only for the alternative. No migration, commit, push or public deployment. See CHAT_ALTERNATIVE_QUESTION_INVENTORY.md and CHAT_ALTERNATIVE_DELIVERY.md.


### ALT73 presentation simplification · October 23, 2026

Owner asks for a much simpler alternative: one compact centered conversation column, inline answer chips near the current question, slim progress near the transcript, one composer, no repeated labels/welcome/extra teaching block or oversized heading. Preserve original landing and 8890, existing input/state/privacy/plan semantics and low-emphasis Back/review/plans. This applies only to 8891. See CHAT_ALTERNATIVE_DELIVERY.md for before-images and bounded checks.


### ALT73 input controls and adaptive followups · October 23, 2026

Owner direction for 8891 only: “Type your answer below”; visible conversational Step 1 separate from reported-information completeness; Enter submits, Shift+Enter adds newline, IME/pending/empty sends are guarded; one always-visible Continue action; remove routine AI warning copy while preserving actual consent/errors/budget and plan-data gates. Preserve and prove applicable RC followups within the same conversation, reuse supplied facts, keep unknown/defer, avoid false completion, and retain optional See plans. Exact bounded traces and before-images are in CHAT_ALTERNATIVE_DELIVERY.md. No changes to original 8890 or landing.


### ALT74 customer profile and server readiness gates · October 23, 2026

Owner authorized recovering the full question set, mapping it into the existing guest aggregate, and implementing capability-specific server gates. Ten answered/unknown steps cannot establish recommendation readiness. Required reported inputs, external verification and explicit sample browsing are separate. Unknown/deferred required fields remain missing; ordinary preferences are optional. Preserve relevant conditional followups, multiple entities, provenance and stale-on-change review without repetitive coercion. No government identifiers, credentials, new clinical intake, original-record migration or release of ranking/enrollment. See CUSTOMER_PROFILE_QUESTION_MAP.md, CUSTOMER_PROFILE_READINESS.md and the machine schema/template under cms-slice/config/profile/. This applies only to the isolated 8891 alternative; original 8890/landing and shared AI spend protection remain.


## D79 · Adaptive conversation implementation · October 27, 2026

Owner approved the full hybrid implementation plan and browser testing, with actual live AI verification required before delivery. The server selects only task-relevant missing details, reuses reports, distinguishes education/browsing/preparation from externally verified conclusions, and suppresses unchanged unknowns. Structured controls need no LLM; natural messages can supply several facts, side questions or explicit corrections. This supersedes ALT73 baseline-first sequencing and mandatory per-turn Continue for submitted chat on :8891 only. Preserve landing, :8890, both guest stores, all historical data, consent, commercial independence and the shared $1/UTC-day cap. All 41 reviewed IDs/78 existing paths remain accounted for; optional gap reports do not close G01–G14 external acceptance. Implementation evidence and limitations are recorded separately.

Technical delivery: [ADAPTIVE_CONVERSATION.md](ADAPTIVE_CONVERSATION.md). The running :8891 source is synchronized and actual GPT-5.4 chat was verified with synthetic inputs. Tests and browser checks do not constitute owner or independent source/policy acceptance; personal conclusions remain gated.

### D79 live UI review · October 28, 2026

Chris approved implementing the extracted 25-action review. Replace the repeated task hub with a guided learning-to-options conversation, reuse prior reports/unknowns, ask only missing precision, fix inert actions, and lead to explicit labeled samples. One deliberate Send control handles selected and typed answers; selections are logged, help/new replies remain visible, and unknowns sit with answer choices. Navigation moves below the composer; a centered navigation-progress bar, plain prompts, quieter sources and a wider responsive surface reduce header/section clutter. The landing keeps the identity, headline and photograph with aligned edges, concise self-discovery copy, one centered Get started action and a one-screen ordinary-viewport layout. Remove redundant notices and the previous-guide link; retain privacy access, consent and photo attribution. Bounded validated-text reveal respects reduced motion. The 2026/2027 sample mismatch remains deferred. :8890, existing stores, 41 original IDs/78 fields, source gates and the shared budget remain protected. See `audit-evidence/ui-review-20261028/` in the main repository for verification rather than inferring acceptance from implementation.

**October 28 technical delivery:** [D79 r2](ADAPTIVE_CONVERSATION.md#october-28-r2--approved-live-ui-review) implements the 25 actions with 139 passing targeted checks, live AI, responsive captures, exact field accounting and unchanged pre-existing guest rows. The original app/service source remains unchanged; one concurrent L09 research-script change is recorded separately. Alternative pricing review is renewed through November 4 at 00:00 UTC at unchanged rates/bounds/cap. Technical and human/source acceptance remain separate; browser instrumentation and unperformed assistive-technology/consumer checks are disclosed in the evidence packet.


**D79 UI2 authorization · October 28, 2026:** Chris approved implementing all five actions from the 14:39 EDT review on :8891: contextual Send below selections, one composer for every typed answer, the provider-submission stall fix, an audit of all 41 gating entries, and five synthetic personas with branch variants tested end to end. Preserve :8890 and existing records; present the 41-question coverage matrix and remaining gaps. Existing independent insurance/source gates, consent, commercial independence and shared $1/UTC-day cap remain. This supersedes the prior fixed-bottom Send placement only for :8891. Evidence: `audit-evidence/ui2-review-20261028/`.


**D79 UI2 technical delivery · October 28, 2026:** The :8891 revision implements contextual Send, composer-only typed answers and provider advancement. The five synthetic personas pass browser journeys; nine HTTP variants produce the [41-entry coverage matrix](../../../../audit-evidence/ui2-review-20261028/COVERAGE_MATRIX.md), with 151 targeted checks passing. The audit also fixes multi-program selection, changed employer-threshold staleness and stale interpretation confirmations. Original :8890 source, all pre-existing guest rows and all prior AI-charge rows are preserved. RC08/RC16 source-rule trigger precision, RC19/21/24 accepted-source branches, broad model/field coverage and human/assistive-technology checks remain explicit gaps; no source/personal recommendation gate is released. See the [delivery packet](../../../../audit-evidence/ui2-review-20261028/README.md); this is technical evidence, not owner/domain acceptance.
