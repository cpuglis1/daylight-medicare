# Ongoing advisor execution contract

D86 · November 1, 2026 · :8893 only · **Implemented; final checks and local activation recorded separately**

The owner approved correcting the ongoing conversation after explanations ended without a useful continuation. The implemented direction prioritizes helping a person understand their coverage options: infer tentative topic familiarity to choose appropriate explanation depth, answer user-led educational questions, and normally continue with a consequential question toward that decision. This is not evidence of a validated recommendation capability. [Actual verification](../../audit-evidence/ongoing-advisor-20261101/README.md) records the current technical checks, fictional real-model attempts, costs, remaining limits and local-runtime status; earlier packets do not prove this revision.

## Mission and turn policy

Help this person understand Medicare and make progress toward their stated goal. Use their circumstances to decide what matters now. Explain a relevant concept when it helps them understand the next decision. When useful work remains, offer one clear next step. Preserve their place when answering a side question. Respect requests to pause or change direction.

The default direction is understanding suitable coverage options, with coverage paths and tradeoffs before individual policies. This is a product purpose, not an invented user report or pressure to enroll. Keep the person's explicit goal separate from the current topic. Learning may reveal a new concern or change stated priorities; resolve those reports and recompute the useful next question.

Answering, teaching and asking are parts of a useful turn, not mutually exclusive move choices. Prefer a concise answer or relevant explanation plus one consequential follow-up when useful work remains. If the person continues asking educational questions, follow that concern and preserve the practical return point. Resume naturally once it helps; do not insert a scripted nudge every few turns. Answer-only turns remain valid for a pause, a substantial explanation or no useful next action. Never fabricate a question or claim completion to keep the chat moving.

The approved 41 meanings remain conditional information requirements, with purposes, dependencies, skip cases and person/time/item scope. Supply useful candidates from that contract rather than mechanically asking the first empty field or running another questionnaire. Do not re-ask reported/deferred information. Explain why an unfamiliar requested detail matters; help the person answer it instead of requiring them to already know the decision the advisor should help resolve.

## Two model stages around validated state

| Stage | Input and responsibility | Output and service boundary |
| --- | --- | --- |
| 1. Interpret the message | Current message, permitted recent discourse, current question, relevant resolved state and all 41 approved meanings. Identify explicit reports, stated purpose and supported life circumstances. No consumer response or model-selected conversation mode. | Exact wire: `updates`, `requests`, `fact_ids`, `agenda`, `situation_proposals`, `goal_quote`. The bounded legacy `agenda` supports explicit concerns/reasons for compatibility; it is not routing authority. The service validates proposals independently, accepts clear reports and preserves uncertainty/corrections. |
| 2. Advise from resolved state | Service-built decision brief, validated reports/status/revisions and change receipts, useful conditional question candidates with purposes, reviewed teaching, actual capability/evidence limits and permitted current/recent dialogue. | Exact wire: `question_target`, `reply`, `question`, `report_refs`, `evidence_refs`, `agenda_update`. The service validates the target, scope, references and claimed actions before display. A null target permits an answer or educational detour; the prior practical return point remains in visit memory. |

The implementation keeps GPT-5.4 and two routine typed-message calls, with no third planner or automatic paid repair/retry. A deliberate finite-answer Send resolves its report deterministically and uses at most one composition call. The current reviewed policy uses `none` reasoning for both stages; the composition setting is configurable for a later bounded comparison. This correction changes the state/prompt/action contract rather than claiming that additional reasoning solves it. Settings and measured costs belong in actual evidence.

The decision brief separates product direction, explicit goal, current concern, pending approved question/return point, pause state, research-only status, explicitly reported familiarity and explained-topic metadata. Reports, reviewed evidence, uncertainties and candidate purposes accompany it. Topic calibration is an instruction applied to that context, not a new model-output field, stored education-level estimate or comprehension score. `agenda_update` can patch the bounded current concern and pause state in RAM. There is no continuation-reason field or private chain-of-thought record.

Fresh accepted reports reach the advisor even when its next-question lens would omit them; new job/insurance end dates carry the necessary prior worker relationship. Server-built `resolved_changes` distinguishes superseded and current values for an accurate correction contrast, without making the old value current report authority. RC28 cannot become generic correction bookkeeping outside its actual approved question. An uncertain coarse goal category cannot block an explicitly stated purpose, and research-only reports do not restart personal intake.

## Accurate capture and topic calibration

Use semantic interpretation for explicit circumstances, with deterministic scope/provenance validation. Variations such as “turning 65 years old in November” must not depend on matching one phrase. Preserve a known month with an unknown year. Birthday, intended coverage start, retirement, current insurance and actual enrollment remain distinct. Do not infer retiree insurance from retirement or an enrollment status from wanting to enroll. Rejected advisory hints must not discard independently valid reports.

Topic familiarity is a tentative discourse judgment used to select explanation depth. It is not formal education, intelligence, a verified fact or inferred mastery. Use explicit familiarity reports and the current question/context; do not infer from age, demographics or writing style. General T02 familiarity remains explicit-report-only. Exposure to a lesson does not establish comprehension or preference, and familiarity with one topic does not establish knowledge of another. Explicit requests for more/less detail override the tentative calibration.

## Versioned visit continuity and privacy

The implementation uses `natural-context-v3` for bounded cross-topic visit context. The existing inline disclosure/privacy explanation already describes the submitted message, recent conversation and relevant profile context; this revision changes the Send context version rather than claiming a disclosure-copy redesign. Deliberate Send supplies that scoped permission; typing, selection and navigation do not transfer anything. No confirmation modal is added. Existing v1/v2 permissions do not authorize the new history/working-brief scope. This latest owner direction supersedes the earlier same-task-only restriction only within v3.

Visit context remains owner/session-bound server memory, capped at six exchanges and 5,000 dialogue characters with a one-hour TTL. A topic change can retain the relevant return point and permitted recent conversation; resolved reports remain the authority for current personal assertions. Unrelated sensitive material and commercial metadata stay out. Outgoing payload/privacy contract checks are recorded in the evidence packet. No hosted conversation store is added.

Raw dialogue and the new decision agenda, return-point metadata and inferred topic calibration are not saved in guest profiles. Saving remains separate and opt-in, with the existing sensitive-field choice; saving permission never authorizes AI transfer. Preserve profile ownership, isolation, expiry, deletion and correction/invalidation behavior. No guest-store migration, transcript logging or silent raw-history expansion follows.

## Scope and acceptance

Preserve the accepted layout, CSS, HTML/assets, greeting and bounded word reveal, reduced-motion/accessibility, one composer, useful answer choices, drafts/history, quiet intake footer and optional final profile review. A copy/extraction duplication correction must preserve reveal and accessibility, and verify visible, accessible and copied text separately. No visual redesign or extra navigation follows from this work.

Keep :8890/:8891, their pinned source/runtime/stores and the shared ledger unchanged. The :8893 $5/UTC-day allowance, existing charges/holds, pricing/token validation and no automatic retry remain. No source acceptance, personalized finding, recommendation, enrollment, external contact or commercial influence is authorized by this conversational correction. Coordinate with separately authorized comparison work through resolved state and actual evidence authority; do not bypass its release gates.

| Verification | Technical evidence and limits |
| --- | --- |
| Exact reported failures | Controlled handoff tests cover timing education plus a consequential follow-up and the enrollment-goal/category regression. Fictional live checks exercised openings and follow-ups; see the exact attempts/failures and corrections in evidence. |
| Conversation continuity | Controlled tests cover educational detours, explicit pause/resume, cross-topic return points and research-only conversation without personal intake. These prove state/input/output contracts, not natural language quality in general. |
| Capture and calibration | Tests cover varied birthdays, partial dates, helper isolation, mixed valid/invalid proposals, explicit familiarity transmission, separate spouse-job/end-date reports and correction receipts. The prompt adapts explanation depth; representative consumer understanding remains unmeasured. |
| Privacy and storage | Contract tests cover old permission versus v3 payloads, owner isolation, context bounds/expiry and absence of saved raw history/new working state. Existing production privacy/legal review remains separate. |
| Behavior and cost | Retained interaction and finite-Send tests accompany the backend checks. Exact final suite results, charged live attempts, latency and runtime activation belong in the evidence packet, not inherited historical counts. |

The fictional live journey was exercised through diagnostic attempts and continuation of an accepted session for its final correction. It was not an uninterrupted six-turn run entirely on the final code revision. Technical success does not establish observed consumer comprehension, effort reduction or a recommendation release.

## Requirement and D73 review

| Requirement/review item | Application and remaining gap |
| --- | --- |
| D49 / consumer task | Implemented advisor explanation/progress around deterministic facts, scope and capabilities; controlled contracts and targeted live attempts are documented. Consumer usefulness remains to be observed. |
| D52 / consequential intake | Clear reports consolidate, consequential ambiguity gets targeted clarification, 41 meanings remain conditional. No blanket review or new questionnaire. |
| D53/D54 / permission and control | Saved reports stay separate from v3 visit dialogue/working brief; actual payload/storage contract checks are recorded without claiming production compliance approval. |
| D57/D86 / change control | Latest owner direction recorded in requirements/master/product/variant instructions; existing visual and interaction contract retained. |
| D64 / independence and challenge | Commercial metadata stays outside prompting, next-question choice, evidence retrieval and explanations. Report correction and evidence limits remain inspectable. |
| D73 / paths, two gates and actual capability | Fair coverage-path education before policies; reported-input sufficiency does not establish external verification. Recommendations and source releases retain their independent acceptance. |
| D73 / proof and stage | Technical contracts and targeted fictional model attempts are documented, with final totals/runtime status in the evidence packet. Consumer comprehension, effort reduction, savings and comparative superiority are not established by this contract or a test count. |

This document records the implemented contract and technical limits. Consult the evidence packet for final checks and actual local activation; implementation and test results are not consumer approval or source/recommendation acceptance.
