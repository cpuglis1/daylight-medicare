# Readiness integration plan and implementation record

October 22, 2026. Bounded consolidation of existing work, authorized for implementation. This is not a new question inventory, redesign, research pass or release of personalized recommendations. Read with [READINESS_TRIGGERS](READINESS_TRIGGERS.md), [READINESS_DESIGN](READINESS_DESIGN.md), [READINESS_CORRECTION](READINESS_CORRECTION.md), and the actual files below. Older inline-entry prose in those documents is superseded by the owner's current **existing wide Ask Daylight popup** direction.

## Existing architecture and concrete wiring

1. `cms-slice/apps/ten-question/ten-state.js` records the accepted ten questions as confirmed `guide.fields` envelopes. `ten-app.js` preserves these through Back/Edit/save/resume. Its summary's **A few details to check** calls `readiness.begin()`; **See plans** remains separate.
2. `readiness-ui.js` records an explicit `detailsRequested` scope, without changing the original goal or answers. `readiness-core.js` seeds only available confirmed reports, evaluates applicable input gaps, retains dispositions, and maintains `facts`, `entityDispositions`, `queue` and `completeness`. Requested checks and source limitations are separate from personal facts.
3. The client computes the actionable queue and remaining **detail instances** from that same state. Multiple doctors/medicines are separate instances; one reply can resolve several. `R.question()` supplies the first/next existing registry question, its specific why line and source IDs. There is no second questionnaire or per-turn Continue.
4. `ten-app.js::mountConversation/showConversation` uses the one existing `#ask-panel` dialog. Its readiness-only width, scroll region and anchored composer are in `ten.css`. `readiness-ui.js` binds the existing composer to the readiness handler and retains the transcript/draft in the tab. Back, summary editing, Escape, plans and return keep the same profile. Explicit entry/reopen never redirects to plans.
5. On Send, the existing consent flow supplies the current message and minimized guide/context to `POST /api/readiness/conversation`. `guide_server.py` applies cookie ownership, same-origin/CSRF, rate/concurrency limits and the existing aggregate budget policy. `readiness_conversation.py` scopes every message to all 28 existing input definitions, generic entity references and known-field presence, rather than only the current question. Private ten-question lists are not automatically attached.
6. `readiness_conversation.py` validates approved IDs/fields and quoted reports. Clear reports can merge directly; ambiguity, conflicting values and changes to established reports require a conversational confirmation. `readiness-ui.js::applyReports` applies current and later reports before recomputing the queue/map/count. Partial answers must merge with existing confirmed fields before completeness validation; missing fields remain missing.
7. Optional guide saving writes the additive companion record through `/api/guest/readiness` and `readiness_profiles.py`. It preserves ownership, CSRF, versions/conflicts, expiry and separate sensitive-saving choice. The backend stores the structured map as a derived snapshot; it is **not a second legal-policy engine**. Hydration recomputes it against the current confirmed guide. Raw chat/drafts and tentative interpretation values are not durably stored. Sensitive opt-out strips values/history and labels omitted facts `not_saved`.
8. See plans uses the existing sample-plan boundary. Source/eligibility/network/formulary/pricing/ranking and enrollment gates stay held. Reports never become verified coverage. RC29/RC30 are boundaries, not interview questions.

## Confirmed zero-queue defects and bounded correction

- `candidates()` returned `[]` unconditionally for `intent.goal === learn`, even after ten personal answers and an explicit readiness request. Preserve truly learning-only behavior; an explicit check with personal context or a requested comparison capability must evaluate the existing triggers. Persist the scope separately from the original goal.
- `pending()`/`begin()`/`sync()` excluded **every** disposition. That wrongly hid `needs_review`, `not_saved`, and legacy `resolved_report` instances whose actual fields were now missing. A new explicit check may review those gaps. Preserve genuine `explicit_unknown`/`deferred` choices and blocked dependencies; do not loop or equate them with complete facts.
- The derived count and navigation must use the same actionable set. Previously consumed IDs cannot hide newly actionable gaps while the count includes them.
- Missing/failed question content or saved context must display **count unavailable**, not a fabricated zero/completion. Do not save a blank replacement after a failed restore.
- Input preparation still has a few partial-field seams: partially known location, partial medicine reports, specific office information and qualification/budget subfields. Repair these using existing definitions; do not add questions or infer verified identities.

## RC01–RC30 implementation mapping and limits

All question copy/choices/source references remain in `apps/ten-question/readiness-content.json`; selection/gaps/merging are in `readiness-core.js`; all-field extraction is in `scripts/readiness_conversation.py`; persistence is in `scripts/readiness_profiles.py`.

| ID | Existing input connection / conditional use | Status and precise limit |
|---|---|---|
| RC01 | Confirmed subject role; otherwise ask who. | Wired. Ten-question route does not itself supply a role, so it can be a real first gap. |
| RC02 | Confirmed ZIP/county; residence-change request adds permanent-home ambiguity. | Partial seeding/merging implemented; asks only missing existing fields. No residence verification. |
| RC03 | Year from a valid requested month; otherwise comparison year. | Wired. Requested date never becomes an actual A/B start date. |
| RC04 | Explicit A/B reports, including the ten-question Original Medicare A/B label. | Wired for reported inputs only; Advantage alone does not assert actual enrollment. |
| RC05 | Actual Part B month for requested timing/Medigap path. | Part B input wired. A material Part A timing selector/calculation is not implemented; requires reviewed timing policy, not an invented rule. |
| RC06 | Basis only for an explicitly requested timing, payer-order or Medigap check. | Wired. No universal age/basis screen or eligibility decision. |
| RC07 | Current Original/Advantage arrangement, separate from future intent. | Wired. A/B plus Advantage is not inherently a conflict. |
| RC08 | Specific relevant event/date when timing/event context is requested. | Wired. No generic event screen for every review goal. |
| RC09 | Current work versus retiree/COBRA and whose work. | Wired on consequential work/timing/change paths. |
| RC10 | Employer threshold after current work, known basis and payer-order request. | Wired 20/100 question variants; no ESRD shortcut or payer determination. |
| RC11 | Separate missing job-end/coverage-end dates. | Wired; partial dates merge and unknowns remain unresolved. |
| RC12 | Written creditable-drug notice and relevant gap. | Wired across applicable coverage categories; missing-gap follow-up preserves a known notice. No penalty calculation. |
| RC13 | Family/retiree benefit impact when considering a change. | Wired as a reported administrator check, not verified preservation. |
| RC14 | HSA contributions on relevant current-work/Medicare-timing path. | Wired; no balance/account intake or tax determination. |
| RC15 | Requested Medigap rights/change-notice history. | Wired; reuses RC05 date, no duplicate Part B question or guarantee. |
| RC16 | Leaving Advantage: first plan, start and prior Medigap history. | Wired; history fields stay distinct, no trial-right determination. |
| RC17 | Replacing existing Medigap only on that requested path. | Wired; no cancellation/application action. |
| RC18 | Relevant cost-assistance reports; multiple programs can coexist. | Wired. Unknown is not ineligibility. |
| RC19 | Requested SNP type: reported program/qualification confirmation. | Definition/activation wired; actual qualification detail is required for a `details` report. No independent qualification verification. |
| RC20 | Routine travel location only when relevant and missing. | Wired. Reported travel is not a network/benefit guarantee. |
| RC21 | All listed doctors/hospitals and missing exact office/location fields. | Entity queue wired; raw names are retained without treating them as exact offices. External identity/network resolution held. |
| RC22 | All listed medicines; only missing name/strength/form/brand fields. | Partial-report validation and literal supplied-detail reuse implemented. No silent substitution or Rx identity/coverage claim. |
| RC23 | Quantity/days supply/exact pharmacy/channel only for personal pricing. | Wired per medicine; missing pricing adapters remain a system hold. |
| RC24 | Reported clinic/pharmacy setting/problem when consequential. | Basic setting report wired. Source-derived restrictions and per-drug benefit adjudication are unavailable. |
| RC25 | Optional amount and premium/total basis only for affordability request. | Activation and missing amount/basis subfields wired. Decline/no-limit closes the instance. No personalized total. |
| RC26 | Exact military/VA program when unclear. | Report preparation wired; detailed TRICARE/CHAMPVA source gaps remain held. |
| RC27 | Explicitly indicated continuity/refill/coverage interruption. | Wired recognition/preparation; no claimed outside intervention. |
| RC28 | Actual ambiguity/conflict in volunteered reports. | Implemented by protected-report/within-reply guards and specific conversational confirmation. Generic registry question is not automatically queued. |
| RC29 | Source/year/service/domain-review capability holds. | Active system guard/map and sample-plan limitations; no personal questions can replace missing data. |
| RC30 | Future plan-specific application/transition review. | Deliberately held and outside intake; enrollment/cancellation is not implemented. |

## User-facing semantics and state rules

- Preserve the existing reason: “A few extra details can change which coverage fits. Daylight will ask only about gaps in your answers. You can see plans anytime.”
- The live count is the number of currently actionable unresolved detail instances. “One reply may cover several; your answers may reveal another detail.” It is an estimate, not a promised fixed interview length or a readiness/eligibility score.
- True complete zero, learning-only scope, unknown/deferred closure, missing saved values and evaluator/content failure are different states and must have truthful wording. No fabricated questions to avoid zero.
- Explicit summary click/reopen always opens the popup. An implicit no-gap progression may browse plans; See plans remains separately available throughout.
- Reuse confirmed facts; evaluate all later fields on every submitted message. Preserve multiple entities/programs and contradiction history. One useful clarification maximum per current instance; unknown/defer closes it. Stale/missing saved data is reviewable on explicit request, not silently considered complete.
- Do not manufacture unsupported legal rules from the research package. Research sources are not domain approval. Keep external verification separate from user reports.

## Execution checklist and focused acceptance

| Task | Implementation action | Current state |
|---|---|---|
| T1 | Preserve explicit entry/popup and persist explicit readiness scope; fix learning-only leak. | Implemented and verified by actual UI/backend profiles below. |
| T2 | Unify actionable candidates, queue, map and count; preserve unknown/defer. | Implemented; focused stale/omitted/deferred assertions passed. |
| T3 | Close existing partial-field seams listed above without changing inventory. | Implemented: partial location/medicine merge, exact office gaps, qualification/budget completeness, later-only reply handling. |
| T4 | Make unavailable content/context explicit; block blank saves after restore failure. | Implemented; content outage displayed unavailable and disabled generation, without false zero/completion. |
| T5 | Two differing ten-answer profiles: personal learning route and comparison route both produce expected nonzero gaps; one complete saved-resume profile produces a real zero. Inspect actual displayed question and backend companion snapshot. | Verified: personal learning profile 1, comparison profile 11, complete saved resume 0; displayed count matched backend snapshot. |
| T6 | One utterance supplies current and later fields; partial follow-up merges; no repeats; unknown/defer remains closed. | Verified three real-handler synthetic replies: current+later reports, later partial medicines, count 11→8→7, no resolved drug re-ask or unrelated auto-defer. |
| T7 | Reload only the existing launchd service if backend schema/context changed; verify HTTP afterward. | Existing launchd job reloaded for additive scope schema; final HTTP check recorded below. |

No broad regression or screenshot campaign. Use temporary fixture databases and mocked transport/token receipts. Never transmit real guest data to a model. Record measured outcomes here after the focused checks; passing tests do not establish domain approval or older-adult comprehension.

## Rollback and unresolved gates

Before-images with hashes are in `audit-evidence/readiness-count-context-20261022/`; prior popup/entry before-images remain in their dated directories. Compare concurrent changes before restoring intended files. Retain every guest database and additive table/record. Keep optional new record fields readable; do not migrate, reset, delete, commit, push or publish to roll back a UI change.

External provider/drug identity, networks/formularies/pricing, coverage universe, authoritative Medicare/Florida/SNP/military timing/rights policy, recommendation validation and final enrollment remain concrete data/domain dependencies. This plan integrates reported-input preparation and its existing sample boundary; it does not label those held capabilities integrated.

## Measured focused outcomes

- Actual UI-to-backend fixture: ten-answer personal-learning profile produced **1** pending detail and RC01 first; a different comparison profile produced **11** detail instances and RC01 first. The stored companion count matched each display.
- One synthetic real-handler response recorded current RC01 plus later RC04. A complete saved resume remained **0** without re-asking RC01. No raw transcript was required to reconstruct confirmed reports.
- A three-report utterance and a later partial-medicine reply saved two medicine entities; comparison counts changed **11 → 8 → 7**, the resolved RC22 question left the queue, and the still-unanswered RC02 was not automatically marked unknown/deferred. All three actual HTTP extraction responses were 200 using mocked model/token receipts.
- A simulated question-content outage displayed **count unavailable**, no completion claim and a disabled Send action. Genuine unknown/defer states remained closed in focused core assertions; stale, not-saved and incomplete legacy resolved states remained actionable on explicit review.
- No browser errors in that bounded walk. No paid live provider call, new research, guest reset/deletion, commit/push or public deployment. These checks establish input wiring, not domain/data/insurance validation.

Final local verification: `http://127.0.0.1:8890/` returned HTTP 200 after the implementation commands exited; the current readiness scope/count code was served and launchd retained listener PID 72890 (parent PID 1). Six targeted integration regression tests passed.
