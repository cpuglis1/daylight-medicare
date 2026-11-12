# Adaptive curriculum implementation on :8893

November 2, 2026 · D86 · technical implementation evidence

Daylight now keeps a granular education record alongside its reported profile. The model receives what was introduced, explored, left unclear and already illustrated. Sources, learning receipts and visual intent have separate contracts. Ordinary answer submission should advance the useful next question; explicit clarification, new depth and requested revisits remain available. The [implementation contract](../../docs/product/ADAPTIVE_CURRICULUM_2026-11-02.md) describes the architecture and its limits.

## What changed

- `education.py` provides a 17-concept map over existing reviewed material, bounded delivery receipts and pure validation/planning. Exposure is never called comprehension.
- `advisor_memory.py` stores learning under existing owner/chain/v3/expiry boundaries, outside saved profiles.
- `natural_agent.py` separates quoted education requests, citations, teaching updates and explicit visual intent. It removes exact trailing question duplication and safely recovers TLS/connection failures without retrying or refunding uncertain charges. Lossless JSON compaction, focused-source reuse and bounded whole-exchange packing keep the existing token allowance; the counted JSON is what both stages actually send. The small runner hook is in the variant-local `narrative_agent.py`, leaving the pinned shared copy unchanged.
- `natural_flow.py` commits only delivered explanations, permits scoped requests for repetition, prevents repeated introductory teaching after ordinary answers, and records explicit free lessons within existing authorized visits.
- `server.py` clears the deleted guest's learning/visit memory and continuation authority, protecting in-flight requests. No claim is made about deleting all inherited caches or provider records.
- `web/advisor.js` honors explicit validated visual intent. Citations alone cannot summon another figure. Legacy history without that property retains its rendering fallback.

The model, reasoning setting, paid stage count, budget policy, ledger, profile schema, source data and recommendation gates remain unchanged. The new state is visit-only server RAM, not durable curriculum saving. CSS, HTML, assets and incumbent UI interactions remain in place.

## Controlled verification

The [current persona replay](coverage-run.log) passes **30 scenarios and 2,164 assertions**, using independently authored expectations and no network/model calls. Its [complete field coverage output](profile-coverage/summary.json) retains the prior distinction between captured, derived, held and legacy fields; the curriculum does not expand that capability denominator.

The [final full suite](tests-final.log) passes **712 tests in 136.233 seconds**, including the renderer's 71 interaction checks. It exercises first introductions, ordinary finite advancement, explicit repeat requests, new depth, clarification, duplicate figures/questions, malformed metadata, failed processing, helper scope, replay, bounded memory and privacy. Token-packing tests verify the actual HTTP request bytes match the counted context and that source/profile/learning values remain intact. Injected transports test software behavior, not live-model reliability.

A [sandbox-constrained run](tests-sandbox-blocked.log) completed 632 tests with 15 loopback setup errors, all `PermissionError` from binding local HTTP fixtures; it is not reported as a passing full suite. The eight lifecycle tests were subsequently run with local socket permission and pass. Earlier failed fixtures/logs remain for traceability and are superseded only by named later checks.

## Browser checks

A disposable loopback preview used the real frontend/controller with a synthetic model transport, fictional inputs and temporary profile/budget databases. It displayed one coverage-path introduction and figure, then advanced a finite answer to the insurance question without another explanation or figure. This deliberately exercises the finite-answer branch; it is not a real-model role-extraction evaluation.

Rendered desktop 1280×800, tablet 768×1024 and phone 390×844 showed no horizontal document overflow. Existing reveal, Sources, inline figure, answer choices, composer, privacy control and phone down-arrow remain. Screenshots: [desktop](desktop.png), [tablet](tablet.png), [phone](phone.png). The preview tab was closed and browser viewport restored; only its disposable server was stopped.

A final [reproducible preview](preview.py) replayed the exact accepted fictional opening/finite-answer outputs from attempt 5 through the final controller and real frontend. The [final desktop screenshot](final-preview.png) shows advancement to the worker question with one retained path figure in history and no repeated introduction. It used no provider key or call, created only disposable stores, and its tab/server were closed after verification.

## Provider check and accounting

The initial [fictional attempt](attempt-1/live-results.json) completed interpretation but hit an SSL transport failure during composition. It did not complete a conversational turn. Interpretation captured the elliptical self-reference and month-only 65th birthday without inventing a year. This is one observation, not a reliability rate.

That attempt's receipt records **$0.02131 measured settled usage** plus a **$0.03350 uncertain hold**, **$0.05481 accounted total**. The hold was not released. No automatic retry occurred. The narrow recovery fix has controlled tests for extraction and composition failures and their charge/cache states.

Further diagnostic attempts are retained separately. [Attempt 2](attempt-2/live-results.json) exposed a conservative coverage guard treating sourced generic drug-coverage teaching as a personal insurance report. [Attempt 3](attempt-3/live-results.json) advanced two turns without repeating the introductory concepts, then hit the 8,000-token input cap on a requested revisit. [Attempt 4](attempt-4/live-results.json) measured the lossless compact input at 6,701 tokens, down from 7,084, and exposed a second generic grammatical variant of the coverage-guard rejection. The resulting fix distinguishes qualified generic category teaching from actual present personal coverage claims, retaining source requirements and positive/negative controls. Focus fallback also stopped adding multiple associated source records to already supported concepts. These attempts stopped at their first failures and are not claimed as successful journeys.

[Attempt 5](attempt-5/live-results.json), on the then-current production revision, completed the opening and finite answer: one path visual, no repeated introduction, then a relevant current-coverage timing explanation and worker question. A subsequent TLS failure occurred before the requested-revisit token count completed. Its unissued stages were canceled, with no new uncertain hold. A diagnostic continuation may replay these exact successful fictional captures locally, without a budget object, invented usage or provider request, then restore the real ledger/client for remaining turns. Such a result is explicitly labeled as continued evidence, not an uninterrupted six-turn live run.

[Attempt 6](attempt-6/live-results.json) used that free prefix replay and completed all remaining generated turns. The explicit recap delivered the path concept a second time, redisplayed its figure only on request, and preserved the pending worker question. Its caregiver check exposed a separate relationship-label boundary: interpretation correctly proposed `someone` from “I am helping my mother,” but labeled the relationship as learner metadata, which the retained personal-report guard rejected. The mother's uninsured status stayed separate from the helper's job coverage. This attempt completed generation but **failed the caregiver quality criterion**; completion is not presented as a quality pass.

The final narrow correction normalizes only RC01 visit-relationship metadata before the existing quote/choice/scope/entity validation. Helper insurance is still rejected as beneficiary coverage, and conflicts about an existing beneficiary still require clarification. Eight dedicated regressions cover the actual model shape and the retained boundaries.

The [final three-turn caregiver check](live-results.json) passes all four explicit criteria: correct beneficiary/insurance scope, no repeated identity question, preserved timing question across a Part B explanation, and December birthday correction without an invented year. All six stages completed, using **5,399–7,563 input tokens** while retaining the available history. No recommendation or source acceptance follows. The self/revisit observations preceded the final RC01-only correction; final deterministic regressions cover that unaffected contract. There has not been an uninterrupted six-turn live run entirely on the last revision.

[Total accounting for this implementation's attempts](live-accounting.json): **$0.4126365 measured settled usage**, **$0.03350 unresolved hold**, **$0.4461365 accounted total**. These are this check's receipt estimates, not an invoice or the cost of the owner's conversation. The final caregiver check used $0.112785. No provider credits were purchased, uncertain holds released, automatic retry added or budget limit changed.

The explicit [live harness](verify_live.py) caps a run at 14 reserved generation stages ($0.469 maximum), uses the existing model/key/shared ledger, fictional inputs and an isolated temporary profile database, and stops at the first failure. It never saves a profile. Additional execution and final activation status must be read from the final receipts below; the initial failed attempt does not establish end-to-end quality.

## Preservation and limits

[Protected-file checks](protected-check.json) verify all 70 captured paths unchanged, including all 58 shared-engine pins, CSS/HTML, model and budget settings. No :8890/:8891 change, real guest-store edit, ledger reset, source acceptance or recommendation release is included.

Learning receipts depend on model metadata and allowed evidence; they are not independent proof that every claimed concept was explained correctly. Arbitrary semantic repetition, user comprehension/retention, extraction reliability and sustained live conversation quality remain empirical questions. A restart, expired visit or new chain loses temporary learning history. Free lessons before a permitted v3 visit do not create or backfill that history.

## D73 thesis and interface review

| Requirement | Evidence and remaining gap |
| --- | --- |
| Useful self-service and comprehension | Repetition/revisit controller tests and fictional traces demonstrate continuity mechanics. Actual comprehension, retention and task-effort improvement remain unmeasured. |
| Consequential minimal intake | All 41 meanings and independent persona profiles remain; no question, lesson queue or curriculum completion gate is added. |
| Coverage path before policies | Existing contextual path teaching/figures remain available; citation reuse does not force their redisplay. No personal policy selection is released. |
| Inspectable independent decisions | Expandable Sources and existing report/evidence gates remain. No commercial inputs, ranking or recommendation authority are added. |
| Permissioned continuity | Existing v3 visit isolation, expiry, deletion and separate saving are tested. Durable learning progress and cross-visit recall are not implemented. |
| UI preservation | Accepted CSS/HTML/assets are unchanged; renderer tests and responsive screenshots check retained presentation. Technical verification is not owner acceptance of comprehension or design quality. |

## Local activation

The existing `gui/501/com.daylight.advisor-first.8893` job was restarted after the final checks; its running PID changed from 28585 to 45299. [Read-only activation receipts](activation.json) show HTTP 200 for the page, JavaScript, CSS and status. Served assets match the workspace. GPT-5.4 is available, automatic retries remain disabled and consumer/source gates remain held. No guest-session request, profile mutation or model call was made by these activation checks. Protected variants were not restarted.

Use a fresh visit on [127.0.0.1:8893](http://127.0.0.1:8893/) after refreshing. The restart clears temporary conversation/learning memory; saved profiles remain intact. The [implementation hashes](implementation-sha256.json), final test log and protected-file receipt bind the checked source.
