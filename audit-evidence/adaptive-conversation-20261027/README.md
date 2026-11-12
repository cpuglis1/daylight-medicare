# D79 :8891 implementation evidence · October 27, 2026

Owner authorization: implement the full adaptive conversation on :8891, allow browser testing, preserve :8890 and all existing data, and verify actual live AI before delivery. [Delivery, accounting, implementation and limits](../../alternatives/chat-first/docs/product/ADAPTIVE_CONVERSATION.md).

## Recorded checks

| Evidence | Meaning |
| --- | --- |
| [backend-tests.log](backend-tests.log), [test-summary.json](test-summary.json) | 122 passing targeted Python checks, including 39 new adaptive checks. One unavailable historical source-package test is explicitly excluded with its reason. |
| [verify_backend.py](verify_backend.py) | Reproducible targeted suite; temporary stores and synthetic models only. |
| [javascript-checks.log](javascript-checks.log) | Four retained compatibility scripts and syntax check of the new renderer. Compatibility scripts do not replace browser testing. |
| [live-verification.json](live-verification.json), [live-status.json](live-status.json) | Actual configured GPT-5.4 usage, measured bounds/cost and observed live-flow cases. Deterministic controls did not add a model call. No raw customer records or transcripts retained. |
| [store-preservation.json](store-preservation.json) | Every pre-existing guide/readiness row remains byte-equivalent under canonical row hashing; database inodes retained. New synthetic session rows are accounted for separately. |
| [source-preservation.json](source-preservation.json), [protected-8890.json](protected-8890.json) | Protected original UI/service and source hashes. Concurrent L08 research changes were observed and not edited by this task. |
| [field-accounting.json](field-accounting.json) | 41 original IDs and 78 original fields retained; 14 additive optional report paths; zero external gaps closed. |
| [runtime-check.json](runtime-check.json) | Final allowlisted alternative source/runtime comparison, with no source difference. |
| [detector.json](detector.json) | Static interface detector returned an empty findings array. |
| [source-after.json](source-after.json) | Final alternative source hashes and exact changed/added paths relative to the valid before-image. |

The passing Python suite covers adaptive, alternative, profile readiness, budget, guest guide and readiness-conversation modules. The unavailable historical test is `test_guest_guide.SourceAndProductionTests.test_sample_identities_match_actual_locally_captured_cms_rows`; it expects `data-sources/release.json` and its pinned read-model package, deliberately absent after relocation. No source fixture or domain acceptance was fabricated to make it pass.

## Browser evidence

- [Desktop live multi-fact result](captures/desktop-multifact-live.jpg): fresh real-provider transition preparation, preserving one explicit unknown.
- [Desktop education alongside current task](captures/desktop-live.jpg): source-linked explanation and the preserved date question.
- [Tablet](captures/tablet-live.jpg) and [phone](captures/phone-live.jpg): actual 768×1024 and 390×844 viewports, scrollable conversation, no horizontal overflow.
- Final fresh-visit result at [tablet](captures/tablet-multifact-live.jpg) and [phone](captures/phone-multifact-live.jpg) sizes confirms the same per-field unknown behavior in the delivered renderer.
- [Saved-report resume](captures/desktop-resume.jpg): isolated fixture with temporary synthetic data, not a paid response or a live customer save.

The initial phone-resume attempt was taken on the wrong active viewport and was renamed `desktop-resume-extra.jpg`; do not cite it as phone evidence. [capture-inventory.json](capture-inventory.json) records actual image dimensions. The correct phone evidence is `phone-live.jpg` / `phone-live-transition.jpg`.

Observed behaviors: side education preserves the active task; one natural message supplies several facts; known dates are reused; unknown insurance end remains distinct from a known job end; Check later produces explicit unresolved consequences without looping; sample browsing returns the same unsent draft; review identifies reports as unverified; separate saving omits sensitive details; resume does not recreate raw chat.

No P0/P1 issue remained in the scoped technical checks. Accessibility review covered labels, semantic controls, focus visibility/dialog behavior and readable responsive layouts, not WCAG certification or real assistive-technology testing. Physical mobile keyboard, long-conversation performance, screen-reader and older-adult usability checks remain open. Counts and elapsed time are instrumentation, not measured consumer benefit. Source/policy/recommendation gates remain held independently.

## Preservation and source rollback

The valid pre-change checkpoint for 81 scoped app/service/configuration files is [before/](before/) with [before-manifest.json](before-manifest.json). Root documentation before-images are also retained there. The earlier nested `alternatives/chat-first/audit-evidence/adaptive-conversation-20261027/` attempt has an `INCOMPLETE_CHECKPOINT.txt` and is not a rollback checkpoint.

Incremental source-only runtime backups: `20261027T205800117048Z`, `20261027T205951572579Z`, `20261027T210547337484Z`, `20261027T211918609445Z`, `20261027T212351735431Z`, `20261027T213009171205Z`, `20261027T213402735447Z`, `20261027T214144077786Z`. They are under `alternatives/chat-first/runtime/backups/` and are changeset before-images, not full snapshots. The documented sync checks the exact alternative launchd identity before restarting only :8891. No commit, push, public deployment, package install, original service restart, database restore or shared-budget reset occurred.

Rollback must preserve additive readiness readers/validators for any newly saved records. Restore selected source only after checking current edits; never restore databases, credentials, the ledger or an obsolete strict schema over additive records. Technical verification is not owner acceptance or independent insurance/source approval.
