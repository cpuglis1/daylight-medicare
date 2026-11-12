# Utility button audit · :8893 · November 2, 2026

Scope: source-code tracing of the actual `advisor.js`, comparison, identity and research clients into their controller/HTTP validators. No browser automation or paid AI request was used for this audit. Questionnaire answer gating is covered by the sibling question audit; this document covers every non-question control family, including dormant retained controls. Scripted model transports in controller tests establish deterministic setup and are not real-model observations.

## Defects found and fixed

1. **A pending save could replay withdrawn sensitive-saving permission.** `pendingSave` retained the earlier full snapshot. Unchecking sensitive saving changed the live preference, but the old Retry handler still called `completeSave()` on that earlier payload. The pending-save button now performs read-only saved-profile/readiness version reconciliation. Apply privacy choices first reconciles uncertainty, then creates a new operation from the current reports and current permission. Pausing saving sends no new write. A previously started request may already have succeeded; the UI does not claim otherwise. A failed check keeps uncertainty and never replays the earlier sensitive payload.
2. **Deleting saved information broke the next conversation action.** Deletion replaces the guest session, while the old signed continuation/review/identity tokens belonged to its previous owner. The UI now clears those tokens and pending-save/request snapshots, retains local composer/history/form drafts, and makes one free `refresh` under the new session with no prior continuation or AI permission. A failed reconnect keeps an explicit retry marker; subsequent actions reconnect before proceeding. An HTTP rejection preserves the current authority and information. A lost DELETE response instead remains explicitly uncertain: saving is paused, the possibly revoked authority is discarded, and recovery reads session/profile/readiness before a free refresh, without automatically deleting again. A later expired-owner HTTP 401 similarly requires a free rebind before the next deliberate action.
3. **Reading a concept, canceling preparation, or returning from samples could silently resume intake.** These utilities recomputed a canonical assessment, replacing a validated current question or changing a paused teaching turn into T04 while server visit memory still said paused. The controller now reads the current owner-bound journal head and retains its question, pause/open state, and narrative presentation across these non-progress actions. Client-supplied question/state presentation is never used as authority.
4. **Explanation preference relied on an off-current questionnaire answer.** The profile dropdown now uses a narrow `explanation_preference` settings action. The backend accepts only the exact type/value keys and `new`, `some`, or `comfortable`; it captures explicit structured T02 provenance, retains the current practical question/pause, and performs no composition or extraction call. This keeps settings distinct from stale questionnaire buttons.
5. **Resuming stored reports retained earlier failed-save/request tokens.** Successful explicit resume now drops the earlier pending-save/request/action bindings and old opening selection while preserving the unsent chat composer. Fresh saved versions come from the just-read reports; no earlier payload is retried.
6. **Lesson/navigation bookkeeping could erase pending item clarifications.** Learning/source navigation increments record revisions without changing the underlying reports. The exact pending clarification queue now rebinds to those new revisions, preserving both the current and remaining item targets instead of letting the next candidate check discard them as stale.

Deletion deliberately does **not** migrate the former owner's server RAM conversation, free-form goal, educational calibration, pending source choices or action authority into a new owner. A paused screen can remain locally paused during the immediate reconnect; this is presentation only and is never sent as reported input or backend authority. A subsequent deliberate conversation action uses the new server visit and retained reported profile. This is not a claim that the former visit's pause memory or raw dialogue persists after deletion.

## Control inventory and routing

| Actual control | Handler and effect | Backend gate / resulting state |
| --- | --- | --- |
| Get started | `#start.onclick` opens the existing visit and greeting. | Local only; no report, AI transfer, or saved-store change. |
| Understand Medicare | Opening shortcut selects `learn`; shared Send submits T01. | Selection is local; deliberate Send uses validated T01 choice and existing scoped AI permission for at most one composition. |
| Find coverage | Opening shortcut selects `compare`; shared Send submits T01. | Same deliberate-Send boundary; backend goal enum is authoritative. |
| Review my coverage | Opening shortcut selects `review`; shared Send submits T01. | Same deliberate-Send boundary; no coverage or recommendation is inferred. |
| Something else | Opening shortcut selects unresolved and focuses the composer. | No empty goal is submitted; the user supplies ordinary text. |
| Clear selection, opening | Clears the local unsent goal selection. | No API call or profile deletion. |
| Original Medicare / Medicare Advantage / Part A / Part B in an inline guide | `concept(id)` → `read_concept`. | Exact reviewed fact ID only. Free operation; no AI permission. Keeps the current validated question or pause. Reading does not assert understanding or a coverage preference. |
| What Medicare is / Parts A and B / The two coverage paths / Prescription coverage / How costs work, at summary | Same `concept(id)` route for the listed reviewed IDs. | Same fact allowlist, free operation, retained place and source qualifications. |
| More about this disclosure | Native details expansion. | Local only. At most two bounded contextual questions are rendered. |
| Each More about this suggested question | Fills the one composer; refuses to replace an existing typed draft. | No API call until deliberate Send; selection does not become education level, preference, or an answer. |
| Sources disclosure | Native details expansion. | Local only. Existing de-duplication and HTTPS filtering remain; opening a source is an explicit external link, not an AI call. |
| Go to next question / Go to latest message, downward arrow | `jumpDown()` scrolls/focuses within the reading pane. | Local only; no navigation/profile/AI mutation. |
| Restore draft | Restores a parked earlier message only if current composer is empty. | Local only; never sends or overwrites a newer typed draft. |
| Review your profile | `reviewInformation()` opens reported rows. | Local inspection, clearly not verified coverage. No AI call. |
| Explanation preference dropdown | `explanation_preference` with one bounded value. | Exact action keys/enum, honest `user_choice`/structured T02 capture; preserves an unrelated current question/pause and never calls AI, even if a request includes AI consent. If T02 itself is the actual pending question, the explicit setting resolves it and avoids asking it again. |
| Open checklist 1, 2, … | Opens the selected already-prepared local checklist version. | No API call. Stale report revisions remain visibly identified. Does not execute an outside action. |
| Prepare my next steps | `review_preparation`. | Free named-action review; binds token to owner, current chain, complete report fingerprint and 10-minute expiry. No output is prepared yet. |
| Prepare my next steps, shared Send in preparation review | `run_preparation` with current review token. | Exact token/kind/owner/current revision required. Creates editable local checklist only; no outside party contacted or coverage changed. Exact request replay returns the same receipt. |
| Back to my conversation, preparation review | `discard_review` with current token. | Same current owner/revision guard; token consumed, reports unchanged, previous question/pause retained. |
| Use these details / Make edits, retained review compatibility | Shared Send uses `accept_review`; Make edits uses `discard_review`. | Exact owner/current chain/revision/expiry. A preparation token cannot be accepted as a report interpretation. Routine natural reports continue to consolidate without this card. |
| Copy checklist | Clipboard write; if unavailable, selects editable checklist for manual copy. | Local only; no API, insurer contact, save, or model call. |
| Print | Prints the current editable checklist. | Local explicit action; no backend or AI transfer. |
| Return to my conversation, prepared checklist | Clears the local prepared view. | Local only; current report profile remains. |
| Browse sample plans | `next` / `samples`. | Sample display only. Five explicitly unvalidated 2027 Collier records; no personal recommendation or accepted market completeness. Retains practical question/pause. |
| Return to my conversation, above and below samples | `next` / `resume`. | Clears sample visibility without starting another questionnaire or resuming paused intake. |
| Published source, sample record | Opens the retained static sample's source link. | No matching, ranking, recommendation, or AI call. |
| Review comparison preparation | `/api/comparison/journey`. | Origin/session/CSRF, exact request keys, signed current owner/profile/chain/head, live journal and post-read recheck. Derived view only; no save/profile/AI mutation. All personal source/method/output purposes remain held. |
| Return to my conversation, comparison | Clears `comparisonViewOpen` locally. | Keeps current conversation, reports, composer and drafts; no model call. |
| Review medicine and doctor identities | `/api/identity/view`. | Same owner/current-head binding and recheck. Default consumer capability remains held; shows reported details, not released source candidates. |
| Find possible matches, internal identity view only | Drug or provider `/search` for current item ID. | Server-owned `IdentityJourney` capability and source-purpose policy; no caller-selected audience/purpose. Exact current item/profile/snapshot binding; not available in default consumer mode. |
| Check this person or practice's sites | Provider `/search` using source selector and opaque choice token. | Candidate/source owner binding; no automatic person/role/site collapse or provider/network assertion. |
| Select this source identity | `/api/identity/confirm`, current token/candidate ID, `confirmed:true`. | Explicit choice, current owner/report/scope/snapshot/TTL, trusted candidate grain and recheck. RAM-only identity association; never coverage, clinical equivalence, ranking or recommendation. |
| Show more possible matches | Matching kind-specific `/search` with after ordinal, snapshot and choice token. | Snapshot-bound pagination; old or changed sources cannot silently extend a selection. |
| Recheck selected source identity | `/api/identity/view` for item. | Current live report/source association rechecked; no stale identity authority. |
| Remove this identity selection | `/api/identity/forget`, then fresh view. | Removes visit-only source choice; does not delete or rewrite the reported medicine/doctor. |
| Return to comparison preparation, identity | Closes identity view and rechecks `/api/comparison/journey`. | Derived current comparison only; no AI call or profile overwrite. Failed recheck drops old source labels/tokens. |
| Retained source dates and qualifications / Source and limits | Native details expansion in internal identity view. | No API; retains dated, partial, source-native limits. Not a current practice or network verification. |
| Privacy & saving / Your guide & privacy | `privacy()` opens current choices and transfer/saving explanation. | Local only; opening never transfers to OpenAI or saves data. |
| Save my reported information / Also save sensitive details | Local checkboxes until Apply. | Saving and sensitive saving remain separate from AI transfer. Existing saved copies are not implicitly deleted by pausing. |
| Apply privacy choices | Reconciles any uncertain prior operation, then saves current reports only if chosen. | Atomic guide/readiness save with optimistic versions, operation ID and separate sensitive pruning. No forced write when saving is paused; no automatic model call. |
| Check the pending save | `reconcilePendingSave()`: GET profile + readiness only. | Read-only; cannot replay older sensitive consent or claim that an uncertain earlier operation failed. Preserves current reports and draft. |
| Delete this variant's saved information | Opens explicit confirmation. | No deletion yet; no effect on other variants. |
| Cancel, delete confirmation | Closes confirmation. | Local only; saved and current visit information stay intact. |
| Delete saved information, confirmation | Versioned `DELETE /api/guest/profile`, new guest session, free refresh. | Explicit `confirmed:true`, session/CSRF and expected version. Clears saved variant reports/session and old authority; retains local visit/draft. A failed optimistic delete preserves the previous state. |
| Resume saved information | Opens explicit device/privacy confirmation. | No reports loaded until deliberate Resume. |
| Keep this visit | Closes resume dialog. | Local only; existing history, draft and current state preserved. |
| Resume saved reports | Reads profile/readiness; free `refresh` creates new chain. | Explicit reopening of browser reports. Conversation and drafts are not represented as saved. Old action/pending-save/request tokens are cleared only on successful resume; current typed text remains. |
| Close, profile/privacy dialogs | Closes current dialog and restores opener focus. | Local only; no report, AI, or storage mutation. |
| Scope and service details | Native disclosure with limits and existing visit diagnostics. | Local only; does not change budget or release gates. |
| Back / Review information / Prepare next steps / Browse sample plans, old footer IDs | Retained handlers exist; all four are forced hidden in normal current UI. | They are not additional visible intake controls. Preparation/review handlers still use the same guards if reached internally. |
| Edit, compatibility rows; Return to my current task | Edit routes to supported question; resume clears explicit editing mode. Normal profile rows do not currently expose Edit buttons. | Current signed state and service question definitions remain authoritative; conversational correction stays available in the one composer. |

## Separate internal research page

`research.html` has no conversational model calls, personal profile inputs, release button or recommendation action.

| Control | Route / gate |
| --- | --- |
| Source offering checkboxes | Local selection, at most three in the client. Does not alter a consumer profile or preference. |
| Filter retained source records | Local literal name/ID filter over the complete returned retained catalog. Does not infer market absence. |
| Inspect selected source records | Exact `inspect` requests, source catalog order, same 2026 Collier scope and immutable expected snapshot. Source-only results, no fit score. |
| Load the next source records | Exact layer/entity cursor and expected snapshot; fixed bounded page size. Changed snapshot rejects rather than blending records. |
| Inspect accepted r4 reference | Exact offering/year; original acceptance verifier runs on each lookup. Renderer requires exact accepted subset metadata and held consumer purposes. Does not inherit acceptance into full L03. |
| Source-native data, complete retained fields, conditions, source/original row, exact identity/lineage and accepted entry disclosures | Local native details expansion only; retains original qualifications, lineage and held authority. |
| Return to advisor link | Ordinary local navigation. No source rows become consumer alternatives or model context. |

All research routes enforce allowed origin, authenticated guest session, CSRF on POST, bounded body shapes and concurrency. Server-owned repository/reference adapters determine accepted identities, exact scope and snapshots. SQL/source authority/personal purposes are not caller parameters. Identity source candidate controls remain disabled by default consumer capability; the separately explicit internal research launch flag is required.

## Deterministic verification

- `tests/test_utility_buttons.js`: 13 tests of actual production utility functions and click handlers with a fake transport, including permission withdrawal, read-only pending reconciliation, reduced current save payload, rejected/uncertain deletion, successful owner rotation, failed reconnect/retry, local paused presentation and successful resume.
- `tests/test_utility_buttons.py`: includes that Node suite in ordinary Python discovery.
- `tests/test_utility_button_gates.py`: 11 controller tests. They cover current/custom wording, paused concept navigation, preparation cancellation, sample return, named owner/revision/token/replay preparation, new owner/free refresh, exact preference settings, genuine pending T02 resolution, retained sibling-item queues and forged state rejection. Tested utility actions make zero model calls; scripted conversation setup uses local deterministic transports only.
- Existing ongoing advisor tests (18), comparison chat tests (10), and combined Send/reveal/utility Node checks passed during the utility implementation. The root audit's final test log controls the final aggregate count.

These checks establish code paths and deterministic behavior. They do not establish real-model conversational quality, beneficiary comprehension, production retention/vendor review, source release, recommendation accuracy or outside enrollment execution. Live :8893 activation is recorded separately by the root audit; this document does not claim runtime activation.
