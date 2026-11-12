# D86 natural advisor conversation — October 30, 2026

The owner authorized implementing the [natural conversation plan](../../docs/product/NATURAL_ADVISOR_FLOW_PLAN_2026-10-30.md), with conversational language and **no layout redesign**. Target: [local :8893](http://127.0.0.1:8893/). This record distinguishes implemented behavior, controlled verification and the remaining live-provider blocker.

## Implemented

- Clear reports resolve individually into the profile before the model composes a response. Routine typed and structured reports bypass the former interpretation acceptance card. A bad proposal does not discard unrelated supported facts.
- A second bounded model request writes a connected acknowledgment and one useful question from the resolved profile, relevant reviewed teaching and service-owned eligible moves. The ordinary response is generated, not a scripted paraphrase of the retirement example. Optional orientation is conversation state, not another required profile field.
- The full 41-question wording, choices, purposes, dependencies and inference limits remain in the extractor context, compacted into one table. Original 78 paths, adaptive branches and source gaps remain. Two earlier circumstance fields preserve retirement and a stated birthday month/year without inventing insurance, enrollment or a year.
- Uncertainty receives a targeted question. Corrections invalidate affected inputs; unknown/defer controls remain useful without a paid model call. Optional profile inspection remains available. A named preparation action still needs its separate revision-bound authorization.
- New capture provenance says reported by the person; it does not pretend that accepting a generated summary occurred. A transient compatibility projection feeds the retained engine. Saving guide/readiness state is atomic and retains sensitive-save policy.
- Relevant prior private context requires the new `natural-context-v1` AI permission. Previous consent alone cannot expand context. No raw transcript is persisted or sent as history. Saving, AI transfer and external sharing remain separate.
- Continuations bind owner, visit chain and exact state. Request replay reuses the resolved response, including after a composition failure; it cannot silently repeat extraction or duplicate an operation. Named actions cannot be revived by refreshing an old snapshot.

Local implementation: `natural_flow.py`, `natural_agent.py`, `natural_state.py`, narrow adapters in `narrative_agent.py`, `situation.py` and `server.py`, and functional wiring/copy in `web/advisor.js`. Styles, HTML, teaching data, brand assets and the pinned shared engine are unchanged. The existing one-Send interaction and review utility remain.

## Verification

The final [test log](tests.log) records **174 passing tests** in 6.439 seconds, including temporary HTTP/storage tests. JavaScript syntax passes `node --check`. Tests cover multi-fact capture, unsupported inferences, current/historical/helper scope, actual versus intended enrollment/dates, partial acceptance, conflicts/corrections, independent medicine/provider items, queued targeted clarifications, direct unknown/defer, context redaction, honest provenance, atomic save/resume, stale states, owner/visit binding, duplicate requests/actions, failure preservation, bounded spend and no automatic retry.

Browser inspection used an explicitly labeled **synthetic fixture** with fictional input on :8892, separate temporary storage and no API calls. At desktop 1280×800, tablet 768×1024 and phone 390×844, the retirement report advanced to the conversational question without an acceptance card. Each viewport had one Send and no document-width overflow. Screenshots: [desktop](desktop-fixture.png), [tablet](tablet-fixture.png), [phone](phone-fixture.png). These demonstrate rendering and wiring, not live model quality. Physical keyboards and assistive-technology execution remain untested.

[Preservation comparison](preservation-after.json) checks all 77 enumerated pinned engine/static files against the pre-change hashes. Existing customer database rows and database inodes were retained; no customer migration, fixture save into the live profile store or original-variant restart occurred. Shared-budget additions are accounted separately, with no cap reset or deletion of prior/uncertain charges.

Only `gui/501/com.daylight.advisor-first.8893` was restarted. The active [configuration](runtime-config.json) identifies `D86-natural-v1`, with `mockAI: false`; health status returned successfully. A fresh browser tab on :8893 verified the opening, unselected shortcuts and one Send without making a model request. [Active service screenshot](active-8893.png). Opening that tab added one normal unsaved guest row (2 → 3); all existing guest rows are unchanged, and requests/readiness/saved-operation tables remain empty. The [build manifest](build-manifest.json) records final implementation/document/test hashes.

## Live checks and actual blocker

Bounded fictional real-model checks exposed and led to fixes for unsupported application-to-enrollment and process-to-familiarity inferences, omitted explicit spouse-job insurance, month-name grounding and excessive repeated question context. Early failing outputs remain in [first-live-semantic-failures](first-live-semantic-failures/). Some intermediate replies completed; they do not establish broad language accuracy or an end-to-end pass of the final build.

**Final real-model verification is blocked by API credits.** The latest provider streaming event explicitly returned `insufficient_quota` / `credit_balance_exhausted`: [fictional provider event](fictional-provider-event.json), [HTTP error](live-error.json). This is separate from the local $1/UTC-day limit. No additional paid checks were attempted after identifying that code. The app now gives an accurate fixed provider-credit error rather than a generic model failure; private provider error prose is not retained by production diagnostics.

The shared ledger still uses GPT-5.4, extraction low / composition none, 8,000 input and 900 total output tokens per stage, two-stage reservation, measured settlement and conservative holds for issued requests without final usage. Unissued stages are cancelled. No automatic model retry, credit purchase, account change or budget increase was added. [Final local status](runtime-status.json) records measured estimates and held reservations separately; these are not an invoice. A complete final three-turn live run and final generated-tone evaluation must be repeated once the API account has credits.

Final UTC-day accounting is $0.387757 measured estimates plus $0.1675 held, leaving $0.444743 under the local cap. This task's append-only ledger delta is $0.2164585 measured plus $0.1675 held across 26 stage rows (16 settled, 5 cancelled, 5 uncertain). Local headroom does not establish provider credit availability.

## Strategic review and limits

Requirements addressed: D49, D52/D53/D54/D56 as revised by D86, D64 independence, D71 conversation continuity, D73, D75 variant isolation and D79 adaptive dependencies. D86 supersedes blanket interpretation acceptance only within this local flow.

The D73 checklist is supported by lower routine confirmation burden, useful conditional intake, preserved teaching and coverage-path distinctions, inspectable reported inputs and separate permissioned continuity. Technical tests do not prove consumer comprehension, reduced completion time or superiority over forms. Grounding/reference and language guards are finite rules, not a guarantee of factual or semantic perfection. Long-context capacity beyond the tested bounded cases remains a gap; oversize requests fail closed.

Source/eligibility/provider/drug/price/recommendation gates remain independent of profile completeness. No new evidence is accepted, no plan ranking or personal recommendation is unlocked, and the five 2027 sample records remain labeled samples. Commercial metadata does not enter the conversation or decision logic. This local delivery changes no sealed L01/L03 evidence or release obligations.
