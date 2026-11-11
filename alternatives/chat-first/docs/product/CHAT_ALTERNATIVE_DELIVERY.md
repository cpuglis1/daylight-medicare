# Daylight chat-first alternative · local delivery

**October 25 source-location update:** [Canonical source, sync and rollback](../../README.md). The delivery and UI evidence below remain dated October 23; only source organization changed.

23 October 2026. Bounded alternative for comparing two UIs; no migration or replacement. Addresses the owner’s ALT73 alternative direction while preserving D64 independence, the ten D66 baseline semantics, D68 contextual teaching, existing D72 input preparation and all plan-validation gates.

## Local URLs and source isolation

- Current app: http://127.0.0.1:8890/
- Chat alternative: http://127.0.0.1:8891/
- Canonical editable source (D75 relocation, October 25): `/Users/cep4u/daylight/alternatives/chat-first`
- Retained noncanonical fallback: `/Users/cep4u/Documents/Codex/2026-10-23/task/daylight-chat-alternative`
- Running source-only runtime: `/Users/cep4u/daylight-chat-alternative-runtime`
- Inventory, delivered before implementation: [CHAT_ALTERNATIVE_QUESTION_INVENTORY.md](CHAT_ALTERNATIVE_QUESTION_INVENTORY.md)

This is a separate source snapshot, not a checkout or branch switch. `ISOLATION_BASELINE.json` records the original Git HEAD, main branch and SHA-256 hashes for 509 current on-disk source files, including relevant uncommitted files. Original source hashes remained unchanged at delivery; original listener PID 72890 remained on port 8890. No commit, push, deployment to the public Internet, guest-data migration or source-tree reset occurred. Credentials and every original guest/budget database were excluded from the snapshot. Root DESIGN.md remains identical to the incumbent.

The accepted landing section is byte-for-byte identical, including branding, photo, tagline, copy and actions. Get started opens the alternative’s conversation. The original landing/app files were never edited. Footer privacy entry retains its original landing text and class.

## Implemented experience

The existing wide Ask Daylight transcript/composer styling, fonts, palette, sun asset and source-labeled sample cards are reused in the main workspace. After a brief welcome, one question and its reason appear at a time. Inline suggestions and free text are available throughout, with Something else, Not sure, Check later and See plans. Multi-selects keep every selection until Send selected. Month/year and county controls retain the original semantics. Lists preserve multiple doctors and medicines, including periods in names and semicolon-separated entries.

The ten baseline topics and existing conditional readiness rules share a scheduler and profile. One message can supply current and later topics. Confirmed reports are reused, partial entity details merge, and conflicting/ambiguous changes receive a conversational confirmation. Review information permits correction and return to the same conversation. Unknown/deferred entries do not automatically repeat. A genuinely missing question/context is an unavailable-progress error, never zero readiness. Explicit comparison/request scope cannot be suppressed by an earlier learning goal.

The top bar is **Your information**, measuring reported information against the applicable information scope. Additional needs may increase the denominator. Unknown/deferred and tentative reports remain separate; external source/coverage verification is explicitly missing. Baseline and RC completeness maps are retained with the optional guest record; baseline-derived duplicate RC facts are not counted twice. Completion offers the existing five source-labeled samples; See plans remains available with gaps and Back to your conversation works with or without gaps. Samples preserve exact source identity and unvalidated/unknown notices. No personal ranking or enrollment is unlocked.

## Storage, AI and voice

The live alternative cookie is `daylight_chat_alt_dev`; its database is `cms-slice/var/chat-alternative-profiles/guides.sqlite3` under the dedicated runtime, never the original profile directory. Same-origin/CSRF, guest ownership, version conflicts, expiry, explicit guide saving and separate sensitive-saving consent are reused. Chat, raw submitted text, unsent drafts and tentative values are not durably saved. In-tab return from plans preserves drafts/transcript. Reload resumes saved structured information, not raw chat; details omitted by sensitive-saving choice remain visibly missing and can be supplied again. Saving and AI transfer remain separate choices.

Both applications use exactly `/Users/cep4u/daylight/cms-slice/var/ai-budget/usage.sqlite3`, the existing aggregate $1 per UTC-day reservation/settlement ledger. Alternative runtime loads the existing configured model credentials from the original .env at startup without copying or displaying them. No automatic AI retries, new provider, subscription or credentials. Live interpretation extends the existing grounded conversation transport to all baseline and readiness definitions, with quoted reports and allowlisted output. **No paid live-provider behavior was exercised.** All extraction tests used synthetic transport; live availability/configuration was inspected only through the public status endpoint.

Firefox displays an explicit unavailable voice-input message and supports typing or the user’s OS dictation. In browsers exposing SpeechRecognition/webkitSpeechRecognition, Voice input first discloses that the browser/OS speech service may process audio, then requires user-initiated start and user-controlled microphone permission. Stop is explicit, transcripts remain editable, and there is no automatic submission or background recording. No microphone permission was accepted during this work. Actual browser microphone operation was not exercised.

## Focused evidence and limitations

- Node state scenario: three mixed turns, several later baseline answers from one message, all doctors/medicines preserved, distinct entity followups, no resolved-doctor repeat, unknown/defer, conflicting correction, changed travel scope/denominator, explicit comparison against earlier learning scope and no fabricated zero on content failure.
- Six synthetic Python model/HTTP checks passed: all ten baseline + 28 readiness definitions in one bounded request; literal list retention; rejection of untraceable names/date invention; save/resume of structured map; cookie ownership and profile conflict isolation; two servers sharing a temporary budget and uncertain reservations; held comparison endpoint; exact five sample records; protection against use of port 8890 or original profile storage.
- Lightweight synthetic DOM test passed: unchanged landing to Get started, three-turn progression, sample plans and back with unsent draft, review/edit, held multi-selection until Send selected, confirmation focus and Firefox fallback. **This is a semantic DOM fixture, not a rendered browser test.**
- Source hash check: original snapshot files unchanged, original DESIGN.md unchanged, landing section exact. Both public root URLs returned HTTP 200 after launcher completion. Public status showed equal $1 UTC-day budget state with zero requests/charges from this work and automatic retries disabled.
- Bounded independent code review found and then verified fixes for doctor-name punctuation, negative/no-medication replies, explanation questions being mistaken for lists, and focus/announcements on question/clarification/confirmation transitions. Findings closed at code level. One Impeccable detector pass flagged only incumbent Fraunces; the approved type system is intentionally preserved.

Browser access remained paused following the owner’s permission clarification. No workaround, browser automation, browser/profile/history/cookie access or macOS privacy permission change was used. **Rendered desktop/tablet/phone layout, actual assistive-technology speech and real microphone behavior remain unverified.** No screenshot gallery, production-readiness claim or owner-acceptance claim is made. The 29 source references remain research-only, not professionally approved policy. Identity/network/formulary/pricing, eligibility/rights, comprehensive market coverage, personal recommendation and enrollment remain independently held.

## Local service operations

Only `com.daylight.chat-alternative.8891` was registered with launchd in `gui/501`; it survives the launching command. macOS prevented launchd from reading scripts in Documents. The authorized source-only runtime was therefore installed in the dedicated unprotected sibling directory above; no protected-file permissions were expanded, no original records were copied, and no original service was restarted. The running plist is `runtime/com.daylight.chat-alternative.8891.plist` inside the runtime directory. Runtime logs contain startup/error messages only; the inherited server disables submitted-message/access logging.

To stop only the alternative: `launchctl bootout gui/501/com.daylight.chat-alternative.8891`. Keep its profile database if retaining saved alternative information. Re-register its runtime plist to start again. Do not reset or delete either app’s data or the shared ledger. The original port 8890 is independent and remains managed by its existing job.


## ALT73 simplification · October 23, 2026

Owner direction: “Simplicity is key.” Simplified port 8891 only into one centered 780px maximum conversation column, a slim information bar immediately above the transcript, inline wrapping answer chips inside the conversation scroll area, and one anchored composer. Removed the visible chat heading/card shell, repeated speaker labels/acknowledgments, long welcome, “A little context,” duplicate choices, separate options panel and unrelated footer controls from the chat view. Back/review/plans remain quiet actions; privacy and voice remain available. Reasons are brief and contextual, without a ten-question-count promise. Landing, original port, intake engine, conditional logic, profile persistence, information calculation, AI/budget boundaries and plan gates are unchanged.

Before-images of editable and deployed chat-app.js/chat.css, with SHA-256 hashes, are under `audit-evidence/chat-simplification-20261023T143125Z/`. Syntax and the focused synthetic DOM interaction passed, including first-screen simplicity, inline options, one composer, dictation fallback, multi-select confirmation, review and plans/back with draft. Original source hashes and exact landing section remained unchanged. Only the two presentation files were synchronized into the live alternative without restarting its service. Rendered desktop/tablet/phone checks remain paused by the owner; no browser access or paid AI calls occurred.


## ALT73 controls and conditional continuity · October 23, 2026

Owner requested simpler entry copy, initial step 1, Enter submission, Continue everywhere, no routine AI banner, and evidence of conditional followups. The alternative now uses “Type your answer below,” shorter doctor/medicine field labels, and one always-present Continue action for text, selected chips and details. Invalid/empty/IME/pending submissions disable the action. Enter submits; Shift+Enter retains newline behavior. IME composition, held keys and a second submission while the action is pending do not submit again. Selecting chips does not submit until Continue; an existing unsent message is preserved when the selected choice is continued. The routine AI disclosure/banner was removed from the chat; actual transfer consent, actionable service/budget errors and plan-data limits remain. No backend or spend-policy change.

The visible ordinal starts **Step 1** and counts actual displayed conversational questions, without a fixed total. The bar separately measures reported relevant information; a multi-field reply can advance the bar while avoiding redundant questions. The prior initial three reports were a real defect: empty provider/medicine/fill gap arrays were marked confirmed. Empty inactive entity checks are now not applicable and contribute no reported information. Individual completed entities advance completeness separately. Values remain reported, not verified coverage.

Conditional trace: baseline normalization → confirmed guide/readiness facts → explicit request scope → existing RC candidate evaluator/map → current question/context → same chat. Existing local extraction recognized fewer explicit request phrases than the live-model contract; it now connects explicit payer-order, job-ending/event, replacement, drug-gap/problem, continuity and SNP phrases to the existing request IDs. No new Medicare rules or blanket questions were added. Merely having employer coverage or a broad review goal does not assert a timing/payer-order request; user facts supplied earlier, fully specified medicine literals, and deliberate unknown/defer can legitimately skip followups. RC29 remains the system data guard and RC30 the held future application gate. Missing question content or an unresolved actionable queue cannot produce a false completion. Employer threshold context matches the displayed variant.

Focused semantic DOM traces (no browser or provider):

- Explicit employer/coverage-transition/timing/payer-order/job-ending case showed RC01 → RC04 → RC05 → RC06 → RC07 → RC08 → RC09 → RC10 → RC11 → RC12 → RC13 → RC14 in the SAME chat, then zero actionable gaps and sample plans.
- Doctor/medicine/travel with explicit drug-pricing request showed RC01 → RC18 → RC20 → RC21 for each of two doctors → RC22 for each of two medicines → RC23 for each of two fills, then zero gaps and plans.
- Existing mixed-message scenario still covers later-field extraction, no resolved-entity repeats, unknown/defer, correction, changing denominator and saved-profile projection. Entry/control DOM checks cover Step 1, zero phantom reports, visible disabled Continue, Enter/Shift+Enter/IME, duplicate-submit suppression, single primary composer, no routine banner, multi-select, draft preservation and plans return.

Exact synthetic displayed questions and context IDs are recorded in `runtime/conditional-employer.json` and `runtime/conditional-needs.json`. These checks establish the listed paths, not exhaustive validation of every RC/legal predicate or live model behavior. Source references remain research-only. Before-images for editable and deployed app/core/readiness-core/CSS and SHA-256 hashes: `audit-evidence/chat-controls-20261023T145307Z/`. Original source hashes and exact landing remained unchanged. Rendered/browser checks stay paused, no paid AI calls or microphone/browser permissions, no commits/push.

Conditional scope accessibility confirmation: both final semantic DOM traces start with no readiness request flags, enter the explicit scope utterance through the actual chat composer and Continue submit handler, assert the resulting request IDs, then answer the displayed conditional questions in that same conversation. No hidden request flag is manually set. Baseline fixture facts use the actual accepted baseline normalizer. The employer utterance is “Check my enrollment timing. I want to change coverage. Check payer order. My job will end and I am losing coverage.” The needs utterance is “Check the cost of my drugs.” These are reachable user inputs; a generic review goal alone does not assert those specific checks.


## ALT74 profile/readiness delivery · October 23, 2026

Implemented the recovered question map and empty schema/template in the existing guest aggregate with server-authoritative capability gates. See CUSTOMER_PROFILE_QUESTION_MAP.md and CUSTOMER_PROFILE_READINESS.md for enumeration, exact requirements, provenance/privacy, endpoint behavior and targeted evidence. All-idk produces missing-information guidance, not personalized recommendations or automatic plans. Explicit sample browsing remains available. Even full reported input remains held for external/source/domain validation. Only alternative 8891 was refreshed; original landing/8890, records, shared AI cap and no-retry protections were preserved. No paid AI calls or browser access.
