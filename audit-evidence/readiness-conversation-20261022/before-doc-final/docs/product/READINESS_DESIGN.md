# Readiness check before personalized matching

Research/design draft 0.1 · October 22, 2026 · **Not integrated into the live app. Not licensed validation, eligibility determination or an accepted recommendation release.**

This component follows the accepted ten-question summary. It gathers only consequential missing details, reuses confirmed facts, and states which checks can actually be supported. It is one prerequisite for stronger matching; verified plan data, integrations, expert rule review, independence evaluations and final enrollment confirmation remain independent prerequisites.

Read [PRINCIPLES](../../PRINCIPLES.md), [ten-question contract](TEN_QUESTION_CONTRACT.md), [trigger matrix](READINESS_TRIGGERS.md), [source notes](READINESS_SOURCES.md), [machine-readable research inventory](readiness-triggers.json), then [acceptance scenarios](READINESS_ACCEPTANCE.md). The isolated [wireframe](readiness-preview/index.html) demonstrates synthetic routes, not eligibility logic or live AI.

## 1. Where it goes

**Ten editable answers → explicit summary confirmation → readiness evaluation → zero or more targeted details → capability-by-capability readiness summary → supported options or a clear held boundary.** Plan-specific review before application is a later gate.

The default application still follows D66/D68: `T01…T10 → T11 → SAMPLE`. No live routes, guest schema, data or backend settings change in this task. Future integration introduces `T11 → R00 → R01 → R10* → R20 → supported options`, with an explicit direct route to labeled samples/education. Do not turn the readiness component into questions 11–40 or a quiz. The 30 registry entries include conditional exceptions, system guards and a post-selection gate; they are not a required intake list.

Four high-level phases remain **Your goal / Your situation / Your options / Your next step**. Readiness stays in Your next step. Ten questions complete remains truthful. No jumping phase count, percentage, dynamic denominator or resetting to question 1. Within follow-ups show “Readiness check” and the current topic; an optional list identifies complete/open/deferred checks. A simple “Detail 2” may count displayed details monotonically, without an invented total.

## 2. Exact main-flow wireframe and copy

| State | Primary content | Controls and deterministic transition |
|---|---|---|
| T11 proposed entry | Existing Review your answers, ten editable answer groups. Primary: **Check what we can compare**. One contextual introduction: **A few details can change which coverage fits. Let’s check what matters for you.** | Primary explicitly acknowledges the displayed report version and starts R00. Keep Edit and Ask. “See sample options” is a secondary bypass, clearly non-personalized. Do not silently mark every displayed fact independently verified. |
| R00 scope/data preflight | Requested categories/year/location and known source limitations. If current matching sources are held: **Personalized matching is waiting on verified plan data. You can review missing details or see labeled samples.** | Default ends at R20 with data-held capabilities. Optional **Prepare my details** explicitly requests limited future-readiness intake; **See samples** bypasses it. Do not gather sensitive facts for a capability that cannot run without explaining why. Education-only can finish here. |
| R01 evaluate | **Checking which details matter…** only during real deterministic evaluation; never a decorative delay. | Read confirmed reports + reviewed capability/rule/source receipts. Zero gaps → R20 immediately. Applicable gaps → finite queue. Failure → R20 with evaluator unavailable; retain all answers. No model decides applicability. |
| R10 detail | Short approved question, then exactly one **Why we ask: …** line. Registry copy is authoritative for this draft. No paragraphs of regulatory explanation in the primary exchange. | Structured options or labeled fields; **Continue** confirms and advances. **Not sure** is a valid answer; **Check later** explicitly defers. **Something else** opens bounded text where options do not fit. **Back**, **Ask Daylight · AI assistant** and **Finish for now** stay explicit. Selection never advances by itself. |
| R11 text proposal | **Here’s what I understood.** Show only proposed facts and unresolved parts. **Is that right?** is a confirmation, not an eligibility statement. | **Use these details** confirms the displayed patch atomically. **Edit**, **Keep as an unresolved note** or **Not sure** preserve ambiguity. One clarification attempt at most; unresolved afterward → disposition, next detail or R20. AI unavailable → fields remain usable and raw text stays local. |
| R12 help | Same contextual Ask overlay; question title/context, answer-first approved explanation, optional precise sources, composer. | Close/Return/Escape restores exact node, draft, focus and scroll without moving the queue or reflowing the underlying guide. Ask facts only enter the guide through an explicit confirmed structured proposal. |
| R20 readiness summary | **Here’s what we can check—and what still needs attention.** Show capability rows with **Your details**, **Source check** and **Next step** columns. No universal green “ready” badge. | **Continue to supported options** only enables supported scoped output; otherwise **See labeled samples**. **Review open details** is voluntary and never auto-reopens deferred items. **Edit your ten answers**, **Ask**, **Get help** and **Finish here** remain available. |
| R21 edit return | **Your change may affect these checks.** List only dependent capabilities and retain later answers. | Existing summary Edit/Save returns to R20. **Review affected checks** starts an explicit new pass. No automatic re-questioning, deletion or “start over.” |
| R30 options boundary | **These options are [scope/year/source basis].** Missing coverage universe, uncertain needs and held capabilities remain visible. | Current data state permits only existing labeled samples/education. The readiness UI cannot change `consumer-acceptance.json`, bypass reviews or invent ranking. |
| R40 final confirmation | Separate future plan-specific eligibility, dates, provider/drug restrictions, price assumptions, transition/cancellation and application authorization review. | RC30 is not an initial follow-up. A comparison result cannot enroll, cancel or promise issueability. |

The contextual intro appears once per entry, not on every question, and is not an additional homepage slogan. The sole brand line remains **Your coverage, plain as day**. Primary question and why line are short; detailed rationale, law, citations and notices live in optional help and this specification. No promise that a few answers guarantee the right plan.

## 3. What the ten answers do—and do not—establish

| Requested capability | Necessary baseline | Existing ten-question evidence | Missing/conditional distinction |
|---|---|---|---|
| General education / labeled samples | Goal and acknowledged limitations | Goal/familiarity already available | No eligibility or financial intake required. Zero follow-ups is valid. |
| Scoped published plan availability | Requested benefit year and usable reported home ZIP/county; accepted plan universe | Q3 location and some Q4 requested start context | Confirm only unresolved county/year/permanent-home ambiguity; county lookup is not independently verified residence. Current subset is 2027 Collier, not all-market. |
| Conditional health/drug candidate research | Actual reported A/B status and current arrangement, plus scope | “Already on Medicare” and Q5 categories do not explicitly establish A/B status/dates | RC04 is baseline when this capability is requested. Unknown means hold eligibility-dependent claims, not ineligible. |
| Enrollment timing / “can change now” | Relevant effective dates, age/basis or qualifying event/chronology, applicable reviewed rule | Q4 is desired timing, not actual coverage or election-period evidence | RC05/06/08/11 apply only to the timing path; never infer from familiarity, age alone or the annual enrollment calendar. |
| Medigap purchase/transition confidence | Applicable A/B, age/basis, residence, B start and event/prior-policy facts | Q5 Medigap report and Q9 preference are not issueability evidence | RC15–17 only if exploring an actual supplement/change path. Florida rights need separate review. No medical-underwriting questionnaire in this MVP check. |
| Provider fit | Exact doctor/facility and location; exact plan/year/network evidence | Q6 is free text; names alone are not identities or network checks | Clarify only ambiguous entries that matter. Missing directory data is a system hold, not another patient question. |
| Drug coverage and estimate | Exact drug identity, strength/form; quantity/days supply and pharmacy for prices; accepted formulary/restrictions/pricing | Q7 notes do not guarantee structured precision or current coverage | Identity is needed for drug coverage; supply/pharmacy are additional pricing prerequisites. No substitutions or fabricated dollar estimates. |
| Personal total cost/affordability | Explicit cost basis, accepted premiums/benefits/drug/rates and labeled usage/subsidy assumptions | Q9 preference and Q10 priorities do not establish affordability, subsidy, utilization or income adjustments | Budget disclosure optional. Unknown affordability is not a universal block on browsing. Missing plan data still holds personalized total/ranking. |

The current guest validator accepts a specific schema-v2 envelope and whitelisted fields; the live ten-question module writes only its question fields. Some legacy contract fields exist without a current route. Their presence in JSON is not proof the user supplied them or that the app supports this component. Current Ask explanations are not automatically a durable fact store. Reuse only actual user-confirmed structured facts available under consent; never silently mine or fabricate an old conversation.

## 4. Deterministic queue contract

### Applicability and ordering

Evaluate approved predicates against typed facts using `true / false / unknown`, not truthy strings. A candidate rule becomes active only with reviewed source applicability and requested capability. Missing required baseline facts can activate a baseline prompt; unknown parent facts make dependent conditional rules **blocked**, not false and not an invitation to guess. Not-applicable dependencies count as closed. Source/data guards (RC29) run first; integrity conflicts (RC28) precede any dependent use.

Static topological order: subject/scope/year/A-B → actual dates/basis/current arrangement → employment and loss chronology/enrollment events → creditable/retiree/HSA/Medigap/program coordination → requested provider/drug/travel/cost details. Within a level use approved priority, stable trigger ID, then stable entity ID. Higher commercial payout, likelihood of enrollment, model confidence or emotional persuasion never changes order. User-reported urgency may activate an approved continuity/referral rule, not an ad hoc model branch.

Each registry trigger must compile to an explicitly reviewed typed predicate and field-dependency set before implementation. Natural-language `trigger` descriptions in `readiness-triggers.json` are research contracts, **not executable eligibility policy**. No `eval`, model-written predicates or runtime source-page instructions. Example reviewed candidates:

```text
RC04 := request.includes(conditional_health_or_drug_research)
        AND missing_or_explicit_unknown(enrollment.partA.status OR partB.status)
        AND not_already_dispositioned(instance)
RC10 := active_current_group_report AND basis_known
        AND payer_order_requested AND employer_size_missing
        AND basis != ESRD
RC21(entity) := provider_fit_requested AND entity.requested
               AND identity_or_location_unresolved
RC29(capability) := NOT valid_named_review(rule_pack, code, sources, year, scope)
```

RC04 does not automatically reappear after an unknown answer; disposition suppression is part of the predicate. Employer-size variants use the appropriate age/disability source path; ESRD/multi-employer cases cannot use that shortcut. Federal/Florida purchase rights remain separate candidate assessments pending expert review.

### Finite identity and terminal states

A queue instance key is `(triggerId, subjectId, entityId-or-profile, ruleVersion, relevantFactFingerprint)`. Fingerprints contain canonical relevant values/provenance/version, never commercial metadata. There is one instance per key. Repeated mentions, Ask answers and equivalent extraction patches merge; multiple provider/drug entities remain distinct. Group missing details for one entity into one short relevant form; do not ask strength and form on separate mandatory pages.

States: `pending`, `blocked_dependency`, `shown`, `resolved_report`, `explicit_unknown`, `deferred`, `not_applicable`, `source_held`, `needs_human_review`, `not_asked_this_pass`. These are different. User confirmation is a report resolution, not independent verification. A negative result is not created from missing evidence.

**Proposed burden guard for review:** at most **six primary detail prompts per explicit pass**, with at most one interpretation/clarification attempt per instance. This is a product safety bound, not a Medicare rule. Remaining applicable instances stay `not_asked_this_pass` and their capabilities remain held/uncertain. “Finish for now” is always available. No automatic second batch; the user explicitly chooses additional checks. The limit does not imply a complete assessment in six answers.

A Continue/Not sure/Defer consumes the shown instance and advances to a not-yet-consumed eligible instance or R20. Blocked dependencies with unknown/deferred parents close the current pass as held, without re-asking the parent. Already resolved details reused from Ask can yield zero prompts. A technical failure goes to R20, not a loop. The finite pass counter strictly increases on each primary display; no data/LLM callback can lower it or reopen a consumed instance. Back revisits an existing frame, never appends another queue instance. Continue after Back replaces the same answer and returns forward; no duplicate topic menus.

### Edits, reruns and deferrals

- Back preserves unconfirmed input in this tab. Summary edit retains later answers and marks affected capabilities stale; it never silently erases medication/provider lists.
- Store explicit deferral/unknown disposition separately from the fact value and remember it for the current consented guide. Re-entering the component, model retries, source refresh or clock tick does not automatically ask again. “Review this detail” is the explicit reopening action.
- A changed dependency creates a review notice, not a spontaneous prompt. A new fingerprint is not permission to bypass a prior deferral. “Review affected checks” starts a named new pass; unchanged deferred items remain deferred.
- Newly stale rules/sources hold capabilities and show a source-update notice. Re-running data checks does not imply re-answering questions. Do not claim a source was refreshed when only its URL was opened.
- Required dates retain precision (`day/month/year`, `month/year`, range, unknown). If a possible date range crosses a material boundary, hold the calculation. Distinct clocks—A/B enrollment, MA/PDP elections, Medigap rights and creditable-drug gaps—never share one generic deadline field.

## 5. LLM / policy / live-evidence boundary

| Responsibility | Allowed | Prohibited |
|---|---|---|
| LLM | Explain approved source-linked text; propose whitelisted facts from volunteered text; select wording only from the approved current trigger; flag an ambiguity; summarize a user-controlled handoff | Choose eligibility, dates/deadlines, prices, rankings, source truth, question applicability or next route; infer a diagnosis/financial eligibility; invent a trigger or silently overwrite confirmed facts |
| Deterministic policy | Validate schemas; apply reviewed source-versioned predicates; deduplicate/dependency-order; calculate capability states with reason codes; invalidate dependencies | Relax source/consumer gates, interpret unapproved legal edge cases, equate unknown with false or confidence with verification |
| Live evidence adapters | Resolve provider/drug identity; inspect accepted plan/year/location networks, formularies, restrictions, prices/rates; return dated evidence/uncertainty | Treat NPI/RxNorm identity as coverage; send unnecessary health context; fabricate missing evidence; accept instructions embedded in source pages |
| Person / qualified reviewer | Confirm reports, decide priorities, review unresolved interpretation, perform necessary expert/official verification and final action approval | Be forced into a sales call simply to progress or see uncompensated options |

A free-text patch shows original volunteered detail and exact proposed field/value(s), unresolved fragments and affected check. “Use these details” is the single explicit confirmation/advance action; no redundant Continue after confirmation. A structured selection plus Continue is already explicit confirmation; no extra review dialog. The model cannot write an independent `verified` state. If a reported fact conflicts with another confirmed fact, RC28 asks for a resolution or leaves it open.

Budget exhausted, unavailable AI, offline model or timeout: no automatic paid retries, no financial cap bypass. Keep structured controls, local reviewed help and drafts; show **“AI help is unavailable. You can use the choices or check this later.”** Free text stays local/unresolved without a parser; no fake model reply. A late response is accepted only if `(profileVersion, runId, instanceKey, requestId)` still matches; otherwise discard the proposal without changing facts. Cancel never submits or frees uncertain budget prematurely. The existing aggregate $1/UTC-day cap remains an independent backend invariant; no new consumer spending banner.

## 6. Proposed state and persistence integration—not current functionality

Keep existing schema-v2 guides intact. Design a separate authorized readiness document/companion record linked to the same private guest session and immutable guide version; do not stuff new fields into the current whitelist or silently upgrade saved profiles.

```text
ReadinessRecord v1
  guideRef: {schemaVersion:2, serverVersion, stateVersion, subjectRef}
  request: {capabilities[], planCategories[], benefitYear, asOfDate, jurisdiction}
  facts: {canonicalField: FactEnvelope}
  run: {id, rulePackVersion, sourceReceiptRefs[], frames[], instances[], displayCount}
  dispositions: {instanceKey: state, reason, userReopenRequired, timestamp}
  capabilityResults: {capability: {inputState, evidenceState, resultState, reasons[], stale}}
FactEnvelope
  value | unknown | declined; precision; subject/time-period; reportSource;
  confirmation:{pending|confirmed_by_user, at, revision}; supersedes?;
  evidence:{not_checked|verified|conflicting|expired, controlledByServer, receiptRef?}
```

Map Q1/Q2 to intent/depth only; Q3 to reported scope plus location-reference provenance; Q4 to **requested** start only; Q5 to reported coverage categories; Q6/Q7 to unresolved name/detail notes until exact identities are confirmed; Q8/Q9/Q10 to needs/preferences, never verified eligibility. Newly confirmed canonical readiness facts refer back to existing values without rewriting them invisibly. The proposed field maps in the registry identify semantic fields; implementation must create explicit adapters and whitelist/schema tests.

Secure guest cookie/session authorization, CSRF/same-origin, versioned writes, isolation and conflict handling apply to the readiness record as to the existing guide. Shared-device notice, optional saving, separate sensitive-note saving, current approved retention, review/delete and lost-session recovery must remain truthful. No Medicare/SSN/member numbers, account passwords, bank balances, tax returns, full diagnosis inventories or document uploads in this component. Provider/drug details, birth context, financial limits, exception text and caregiver facts require sensitive-data classification and review; do not persist all chat. A new privacy/schema retention review is an implementation prerequisite, not permission granted by this document.

Reuse actual consented structured Ask facts. Existing unstored chat history cannot be reconstructed as a saved profile. Store only necessary confirmed fields/dispositions under applicable save permission; keep unconfirmed drafts local. Send only the current question and minimum relevant approved context to the configured model after consent. Logs should contain trigger/result/version/error metadata, not raw health text or full prompts. Server evidence receipts cannot be written by client/model. Source content, pasted notices and drug/provider strings are untrusted data, never tool instructions.

## 7. Readiness by capability and matching gate

Every capability has **input state** (`sufficient_reported`, `needs_facts`, `conflict`, `deferred`, `not_requested`) and **evidence state** (`reviewed_current`, `stale`, `missing`, `unsupported`, `review_pending`). A scoped check may run only when its required inputs, reviewed policy and evidence are adequate. Reported “sufficient” does not certify legal eligibility. Display the reason and next action independently.

Example R20 rows:

| Capability | Your details | Source check / permitted outcome |
|---|---|---|
| Plan availability for 2027 Collier | County/year reported | **Data review pending** → labeled subset only |
| Enrollment timing | Actual B date unknown | **Needs a detail** → no “you can enroll now” conclusion |
| Doctor access | Exact office reported | **Network not verified** → no keep-your-doctor promise |
| Prescription fit/cost | Medicine exact; pharmacy deferred | **Pricing unavailable** → no personal drug total |
| Medigap purchase confidence | State/basis/history incomplete | **Expert review needed** → no guaranteed-issue/underwriting assurance |
| Total cost/affordability | Preference reported; utilization unknown | **Estimate basis incomplete** → only explicitly labeled scenarios if supported |

No weighted “readiness score” can hide one critical missing dimension. No plan receives a lower fit score because its evidence is missing; mark that dimension unknown and disclose universe gaps. Strong matching requires evidence for the user's material priorities across compared candidates, consistent dimensions, explained uncertainty and accepted sources. Independent rules/data gates cannot be waived by a helpful conversation.

Commercial economics cannot influence questions, queue ordering, eligibility, inclusion, filtering, ranking, explanations, missing-data treatment or referral destination. Commission/contract/conversion data stays out of LLM context, feature allowlists and evaluation labels. Counterfactually changing those economics must not change the check. Fulfillment follows a user-chosen outcome, with conflict disclosure, never a forced sales gate.

## 8. Implementation increments and release criteria

1. **Review this draft:** owner checks burden/copy/location; Medicare and Florida-qualified experts approve actual legal predicates, edge cases, sources and date interpretation. Proposed six-detail cap and semantic field schema remain review points.
2. **Pure engine + fixtures:** typed predicates, stable instances, disposition suppression, explicit source/data guards, capability results and dependency invalidation. No guest migration, model or ranking. Test the scenarios in the acceptance appendix.
3. **Profile/consent adapters:** separate authorized record, explicit v2 mapping, sensitive-data minimization, concurrency/resume/delete. Test synthetic guests and rollback independently before connection to the default flow.
4. **UI integration behind a local feature boundary:** existing summary entry, one short question + one why, approved explanation/map/needs annotations, Ask exact return, manual fallback. Test desktop/tablet/phone/keyboard and no-loop journeys. Owner reviews before rollout; documentation alone is not rollout authorization.
5. **Actual source-backed capability adapters:** only named reviewed releases, explicit year/county/category coverage, complete uncertainty/reason records. Network/drug/rate services and comparison remain gated until accepted. Final plan/application checks are a separate increment.

Before-images of documentation entry points accompany this draft. Preview files are isolated under `docs/product/readiness-preview/` and make no API calls, save no guest data and call no model. Current app assets and live ports are preserved. Rollback for this design delivery is removing/reverting only its new pointers/files after preserving any concurrent edits; no database or application rollback is needed. Future integration requires its own protected code baseline and feature-off rollback, preserving both v2 and readiness records.

## 9. Isolated visual preview and evidence

[Review captured screens](readiness-preview/review.html) and [delivery evidence](READINESS_DELIVERY.md). This extension inherits the approved Daylight world; root DESIGN.md and .impeccable/design.json remain unchanged. The sun, paper/sage/olive palette, Fraunces/Atkinson typography and stable four phases are retained. Synthetic scenario controls, scripted proposals and source-held capability rows are development review aids, not new production features.

Prototype-only layout measurements are 68px workspace gap, 45/39/35px question headings, 720px stacking breakpoint and a 680px help dialog. They are local review choices, not new shared tokens; map them to the established system during any future authorized integration. Readiness remains in Your next step after the ten questions; the full core coverage picture supplies already-learned context. The contextual introduction explains this check and is not an additional brand tagline. A fresh documenter compared the artifact to the incumbent files and recommended preserving the existing design system.
