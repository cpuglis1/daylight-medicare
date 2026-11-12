# Adaptive conversation delivery · D79

**Current revision: October 28 r3 (UI2).** The [UI2 evidence and 41-question matrix](../../../../audit-evidence/ui2-review-20261028/README.md) supersede r2's fixed-bottom Send and inline-field presentation. Earlier delivery descriptions remain history; their pricing-expiry statements are superseded by r2's reviewed November 4 expiry.

Implemented October 27, 2026 in the canonical :8891 alternative. Chris authorized the full hybrid flow, browser testing, and actual live AI verification. This implements D79 with the D49–D57 conversation/continuity requirements, D64 independence, D73 change review, D75 isolation and ALT73/ALT74 compatibility. The root :8890 application and the retained Documents fallback were not deployment targets.

## Result

The server now selects missing information for the person's current task. The ten baseline questions are no longer a universal queue. Learning needs no personal intake; published-plan lookup asks for relevant scope; transition, doctor, prescription and Medigap preparation ask only consequential missing details. A source hold stops unsupported conclusions and unnecessary collection. There is no global “ready” state unlocked by answering questions.

Buttons, explicit structured answers, exact short replies and unknown/defer use deterministic code. A natural message makes at most one AI request after consent. It can provide several facts, answer part of a grouped question, ask an educational side question or explicitly correct earlier reports. The controller reuses those reports, preserves the active task during side questions and identifies each remaining unknown separately. Clear submitted text advances directly; consequential ambiguity has an explicit interpretation check. Structured controls have one Continue action; chat uses Send.

The optional explanation preference changes teaching depth. The current task, Back, report review, explicit sample browsing and privacy controls remain accessible. Nothing is preselected. Date controls accept an actual known date or month/year without inventing a day. Prescription pricing preparation keeps quantity units, days supply, exact pharmacy wording and fill channel separate. A typed pharmacy or doctor is a report, not a directory match.

## Contract and accounting

[adaptive-flow.json](../../cms-slice/config/profile/adaptive-flow.json) snapshots the reviewed question/field maps, dependencies, unknown/stale treatment and named gaps. The historical [question map](CUSTOMER_PROFILE_QUESTION_MAP.md) and [readiness record](CUSTOMER_PROFILE_READINESS.md) remain available.

| Obligation | Before | After |
| --- | ---: | ---: |
| Reviewed question IDs | 41 (38 primary, 3 child) | 41 |
| Existing field paths | 78 | 78 |
| Optional report paths for G01–G14 | 0 | 14 additive paths |
| Named representation/evidence gaps | 14 | 14 retained |
| External gaps closed by this work | 0 | 0 |

The additive paths retain partial volunteered reports; they do not make all 14 gaps complete or accepted. The reviewed broader U.S. travel choice is additive. RC06/08/12/16/20 have an internal partial-report choice so supplying one detail cannot silently assert a missing yes/no or basis. Existing historical values remain readable. Shared child fields are reused within their actual parent; RC14 is suppressed from routine intake, RC19 does not collect a diagnosis without supported plan-specific requirements, and internal checks do not become consumer questions merely because they have inventory IDs.

## Implementation boundaries

- [adaptive_flow.py](../../cms-slice/scripts/adaptive_flow.py) owns task dependencies, report normalization, per-item identity, revision invalidation, scoped unknowns, pending confirmation and request deduplication. The browser renders its assessment rather than authorizing a capability.
- [adaptive_agent.py](../../cms-slice/scripts/adaptive_agent.py) uses the existing Responses transport with a strict schema, no tools and `store:false`. Report proposals need quotations from the latest message plus person/time scope. The model selects reviewed teaching blocks; arbitrary model prose cannot become an insurance finding. The existing 8,000-input/900-output token limits, shared $1/UTC-day ledger and no automatic retries remain in force.
- [adaptive-app.js](../../cms-slice/apps/chat-alternative/adaptive-app.js) renders the single conversation, explicit choices, optional detail controls, review and privacy. An unsent draft survives sample browsing and request failure. A structured Continue cannot silently ignore a nonempty chat draft.
- New `/api/conversation/initial`, `/turn` and `/save` routes retain cookie ownership, CSRF/Origin checks, input/concurrency limits and existing storage. Old endpoints and saved shapes remain supported. Loading old reports is in-memory compatibility, not a migration.

Saving remains opt-in and separate from AI transfer. One SQLite transaction saves the guide and readiness reports with both expected versions checked. Sensitive dates, optional wording and item details are omitted unless separately enabled. Chat messages, original quotations, audio and unsent drafts are not persisted as a transcript. Previous provider/prescription/pharmacy/date values and raw history are not automatically appended to the model context. Resume warns about shared devices and does not overwrite the current visit on failure. A conflict preserves the visit and saved copy for explicit resolution.

## Verification

[The evidence packet](../../../../audit-evidence/adaptive-conversation-20261027/README.md) contains tests, source/database fingerprints, live usage and desktop/tablet/phone captures.

- 122 targeted Python checks passed, including 39 new adaptive tests for contract accounting, routing, multi-fact reuse, scoped unknowns/corrections, entity-specific changes, privacy omissions, atomic saves, idempotency and HTTP boundaries. Synthetic transport tests use temporary databases and make no paid calls.
- Four retained JavaScript compatibility scripts passed. These check retained compatibility code; the new renderer was exercised in the browser and syntax-checked separately.
- One historical source-identity test is explicitly excluded because the pinned source/read-model package is absent from the relocated alternative (`data-sources/release.json`). Its initial failure is a known source-package limitation, not a passing or skipped domain acceptance check.
- Actual GPT-5.4 responses were verified in the running :8891 service after explicit AI consent. A final fresh-visit multi-fact message retained current-job coverage, no current Medicare, intended January 2027 coverage and a December 2026 job end, while leaving only the insurance end unknown. It did not ask the supplied facts again. A separate live Medicare Advantage explanation preserved the active transition task. Deterministic Check later and sample/review actions added no AI request.
- Desktop 1280×800, tablet 768×1024 and phone 390×844 had no horizontal overflow. Controls, dialogs, source links, draft retention, partial unknowns and isolated save/resume were inspected. The static design detector reported no findings in the new interface files.
- Read-only fingerprints confirm every pre-existing row in both guest databases is unchanged and both database inodes are retained. Original UI/service fingerprints are unchanged. Four concurrent L08 research-script changes were observed and left alone. Both local services respond; the deployable alternative source matches its runtime.

These are technical verification results, not owner acceptance, an independent insurance review or a consumer study. Conversation measurements are per-visit counts/time including pauses; no claim of faster consumer completion is established. Physical mobile keyboard, screen reader, sustained long-conversation performance and older-adult usability testing remain unperformed. The existing pricing review expires at 2026-10-28 00:00 UTC; the AI guard will stop new paid requests after expiry until pricing is properly reviewed. This work does not extend that guard.

## D73 review and remaining holds

| Review concern | Evidence / remaining boundary |
| --- | --- |
| Useful self-service and comprehension | Reviewed teaching, optional depth, explicit reports and missing details; consumer comprehension study remains open. |
| Consequential minimal intake | Task dependencies, reuse and per-field unknown suppression; education does not require intake. |
| Coverage path before policies | Goal and coverage context precede relevant preparation. Samples remain explicitly unvalidated. |
| Inspectable independent decisions | Server assessment, report review, source links and external holds; no commercial economics in agent/routing/capability logic. |
| Permissioned continuity | Separate AI/save choices, privacy omissions, atomic versioned persistence and resume warning. |

Personal recommendations, eligibility determinations, exact enrollment deadlines, payer order, provider participation, personal drug costs, Medigap rights, ranking and enrollment remain held where their independent source/rule/acceptance gates are unmet. This implementation does not activate the research datasets or infer acceptance from an owner request to implement the conversation.

## Operations and rollback

Continue using [the source-only sync workflow](../../README.md#run-and-update-the-existing-service). The runtime remains `/Users/cep4u/daylight-chat-alternative-runtime`; no launch configuration, credentials, guest database or shared ledger is copied. The final UI-label sync has before-image `runtime/backups/20261027T214144077786Z`; earlier incremental before-images and the scoped pre-change source checkpoint are listed in the evidence packet.

A rollback is a reviewed source change followed by an identity-checked restart of only :8891. Do not restore guest databases or the shared ledger. Preserve additive readiness validation/persistence support for any reports saved after this release when reverting the renderer or routing; restoring an older strict validator wholesale is not a safe data-compatible rollback. Compare later edits before restoring any source before-image.

## October 28 r2 · Approved live UI review

The owner approved all 25 extracted review actions. The contextual journey now connects learning, personal preparation and explicitly labeled sample browsing without repeatedly presenting the seven-task hub. Completed lessons are remembered; current-job/COBRA context, separate desired/job/insurance dates and unchanged unknowns are reused. Research-only learning stays public. Navigation progress is independent of insurance verification.

One fixed Send submits choices, fields or text; submitted selections appear on the right. Compact dates such as `1226` display their normalized month/year before Send. The persistent conversation shell preserves drafts and fields, including text typed while a request is pending and an in-progress field during a preference edit. Sources expand inline, navigation sits below the composer, conversational type is consistent, and validated new assistant text has a bounded reveal disabled by reduced-motion CSS. The landing retains the approved identity and photo with aligned edges, one centered Get started and a one-screen responsive layout.

All 41 original question records, 78 field records, 14 optional paths and 14 gaps remain unchanged in the contract; no external gap is closed. Added journey metadata records only seen teaching and explicit sample visibility. The original :8890 app/service and all pre-existing rows are preserved. One concurrent original-tree L09 research-script change is explicitly recorded and left alone.

The [evidence packet](../../../../audit-evidence/ui-review-20261028/README.md) contains 139 passing targeted Python checks, 17 new review checks, four retained JavaScript compatibility checks, the explicit unavailable historical source check, responsive browser captures and three settled real GPT-5.4 generations. Deterministic selections added no AI calls. Live testing found and resolved stale composer text; the retest verified clearing while a newly typed pending draft survives. Isolated save/resume and preference edits preserve the required privacy/missing-detail behavior.

The alternative-only pricing review was renewed using unchanged official GPT-5.4 rates and the existing 8,000-input/900-output bounds. It expires **November 4, 2026 at 00:00 UTC**. The shared $1/UTC-day cap, consent, no transcript persistence and no automatic retries remain. The :8890 pricing configuration was not changed.

The latest source-only runtime before-image is `runtime/backups/20261028T154923710864Z`; all six incremental manifests are listed in the packet. The runtime comparison has 137 matching source files. The 2026/2027 sample mismatch remains expressly deferred, and all source/personal-recommendation gates remain held. Browser instrumentation extended the outer document scroll area during dialog checks; the app's own BODY layout fits the tested viewports, and no instrumentation workaround was added. Physical keyboard, assistive-technology execution and consumer comprehension remain untested. This is technical delivery, not owner acceptance.

## October 28 r3 · UI2 and five-persona gate audit

Chris approved all five UI2 actions: contextual Send, one composer for every typed answer, provider submission repair, a real 41-entry gating audit and five synthetic personas with branch variants. One Send now moves below selected choices and back to the composer when typing; it remains visible within the reading pane on phones. Inline text/select fields are removed. Exact, obvious provider-name answers can be recorded without AI; mixed facts/questions retain natural interpretation.

The audit fixed multiple assistance-program selection, employer-threshold staleness when qualification basis changes, and stale interpretation IDs after confirm/reject. The original 41 question records, 78 field records, 14 optional report paths and 14 gaps remain unchanged. [The generated matrix](../../../../audit-evidence/ui2-review-20261028/COVERAGE_MATRIX.md) records 24 asked/exercised entries, 13 volunteered/reused entries, one integrity guard and three parent aliases. This is route/report coverage, not complete accepted insurance gating or all 78-field/model-input coverage.

[Delivery evidence](../../../../audit-evidence/ui2-review-20261028/README.md) records 151 passing targeted checks, nine HTTP variants, five browser journeys, responsive captures and one settled real AI generation. The live provider reply advanced without manual clearing or a model call; a prescription plus Part D side question used AI and advanced naturally to travel. Both services respond, all 236 captured original source files and all pre-existing guest/charge rows are unchanged. Only :8891 source was deployed; the latest before-image is `runtime/backups/20261028T193924078461Z`.

Remaining gaps are explicit: RC08/RC16 preparation still uses task-level triggers rather than accepted source rules for exact necessary precision/history; RC19/21/24 candidate/method-dependent branches lack accepted connected sources; broad natural-language/multiple-item completeness and physical keyboard/assistive-technology/consumer checks are not established. The fourteen semantic/evidence gaps, all independent personal/source/recommendation gates and deferred sample-year mismatch remain. This technical delivery does not constitute owner or domain acceptance.
