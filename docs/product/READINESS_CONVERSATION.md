# D71: one optional readiness conversation

Current local implementation · October 22, 2026. This is the owner-approved interaction, technically verified below; it does not certify domain rules or personalized matching. Read [PRINCIPLES](../../PRINCIPLES.md), [master](MASTER_DESIGN.md), [ten-question contract](TEN_QUESTION_CONTRACT.md) and the dated [source inventory](READINESS_SOURCES.md).

## Current route and exact screen

`T01…T10 → T11 editable summary → R00 optional conversation → SAMPLE`.

If no consequential gaps remain, the summary's See plan options bypasses R00. All four stable phases and the accepted ten questions remain. Saved interim R10/R20 node names render the same R00 page; they do not add steps or discard previous answers.

The page title is **A few details to check**. Intro: **A few details can change which coverage fits. Let’s check what matters for you.** Two actions: **Chat with Daylight** and **See plans**. Chat expands inline with a labeled free-text composer and Send. It is not another answer-choice form, question counter, per-turn Continue sequence or mandatory review ceremony. See plans stays available before/during/after replies. Optional reported-details/source disclosures and Review your ten answers are secondary.

The live model receives the confirmed minimized profile, approved contextual question/source IDs and relevant typed report definitions. It reflects the reply naturally; clear new reports can be recorded without another acceptance card. Ambiguous interpretations and changes to established facts receive a conversational clarification; typed affirmation confirms, refusal preserves the old fact. A reply may supply several facts and remove redundant future questions. Reports remain inspectable with approved detail labels/values, reported/unverified status and corrections. The disclosure updates immediately and retains its expanded state.

Each approved follow-up is short with one specific why-we-ask line. Unknown, defer and refusal remain valid. Deduplication, dependencies, source IDs and allowed facts are deterministic. Deferred/unknown items are not automatically repeated. One unclear clarification retry then leaves the fact unresolved. An internal finite pass limit bounds burden without showing a required number of questions. No loop is used to unlock plans. AI unavailable, budget exhausted, cancellation or failure leaves browsing available; there is no fallback questionnaire.

## Safety and persistence boundaries

Real local orchestration uses the existing GPT-5.4 Responses service, shared persistent $1 per UTC-day reservation/settlement ledger and no automatic retries. Consent before processor transfer remains separate from saving. No new credentials or account was created. The model cannot navigate, decide eligibility, generate plan prices, add arbitrary fields, overwrite protected reports without confirmation or bypass data gates. Commercial metadata is excluded from question selection and recommendation context.

Additive readiness companion records use the existing guest cookie authorization, CSRF/same-origin checks, version/concurrency controls and retention/deletion policy. The ten-question schema and old saved fields are preserved; no destructive migration. Save guide is optional; saving extra sensitive reported values requires the existing explicit sensitive-note preference. Without it, values are stripped rather than described as server-saved. Raw chat and unsent drafts stay in the current tab, not the persistent record. In-tab return from samples restores the conversation and unsent draft. Refresh restores saved confirmed facts/dispositions, not the raw transcript; remaining topics reuse those facts. Privacy conflicts/errors remain explicit.

## Evidence and precise limits

| Check | Measured result |
|---|---|
| Backend full suite | 292 tests passed; includes 8 conversation-service tests, guest isolation/concurrency/privacy and budget tests. |
| Frontend full suite | 196 tests passed after the disclosure fix; includes two rendering regressions for live details, populated fields and expanded state. |
| Actual configured provider | One synthetic GPT-5.4 request succeeded, extracting recipient, A/B enrollment and age basis from one message. No extra confirmation card or redundant follow-up. **$0.00824 estimated from measured tokens**, no retries; no further paid test calls. |
| Actual route | Ten questions → editable summary → optional chat; See plans before chat works. Returning through summary with the three supplied facts bypassed the chat page to samples. |
| Synthetic browser fixture | Multi-turn ambiguity + typed yes, unknown/defer, saved refresh/resume, sample return with identical conversation and unsent draft; no readiness Continue buttons. Fixture explicitly identifies mocked replies. |
| Layout | Entry/chat desktop; chat tablet 768px; entry/chat phone 390px. Phone entry measured innerWidth/scrollWidth 390px, no horizontal overflow. Corrected entry capture is genuinely 390px. |
| Fresh finish review | Two material findings (stale detail disclosure and mislabeled phone evidence) fixed and bounded reviewer pass received. This is technical review, not owner acceptance. |

Screens: [desktop entry](../../audit-evidence/readiness-conversation-20261022/captures/entry-desktop.jpg), [phone entry](../../audit-evidence/readiness-conversation-20261022/captures/entry-phone.jpg), [desktop live chat](../../audit-evidence/readiness-conversation-20261022/captures/chat-desktop.jpg), [phone chat](../../audit-evidence/readiness-conversation-20261022/captures/chat-phone.jpg), [tablet chat](../../audit-evidence/readiness-conversation-20261022/captures/chat-tablet.jpg). [Backend log](../../audit-evidence/readiness-conversation-20261022/backend.log), [frontend log](../../audit-evidence/readiness-conversation-20261022/frontend.log).

One provider/drug detail prepares an input; it does not establish a complete resolved list. Eligibility, enrollment exceptions, Florida Medigap/underwriting interpretations, identity matching, network/formulary coverage, quotes, personalized total cost, rankings and comprehensive plan data remain independently unverified/held. Five labeled sample cards are not recommendations. The [researched trigger/source/acceptance package](READINESS_DESIGN.md) remains evidence, not reviewed licensed policy. Real mobile keyboards, screen-reader speech and older-adult comprehension were not verified by these checks.

## Files and rollback

Runtime: `apps/ten-question/readiness-ui.js`, `readiness-core.js`, `readiness-content.json`, `ten-app.js`, `ten.css`; backend `scripts/readiness_conversation.py`, `guide_agent.py`, `guide_server.py`, `readiness_profiles.py`, under `cms-slice/`. No approved hero/photo, source dataset, workbook or visual-system token was replaced. Root DESIGN.md and .impeccable/design.json are unchanged.

Before-images are in `audit-evidence/readiness-conversation-20261022/`, including incremental review fixes; earlier integration baseline is `audit-evidence/readiness-integration-20261022/`. For rollback, stop the local service, compare hashes/concurrent edits and restore only intended runtime before-images, then restart `python3 cms-slice/scripts/ten_server.py --port 8890`. **Keep additive readiness tables/records and all guest databases intact; never DROP or overwrite them to roll back UI.** No commit, push or public deployment was performed.
