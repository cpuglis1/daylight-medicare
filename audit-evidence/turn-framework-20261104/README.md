# Coherent turn framework — November 4, 2026

Owner scope: implement contextual capture, truthful acknowledgments, a shared working assessment of learning and decision preparation, and flexible continuation. Offline checks only. No UI, latency, caching, model selection, pricing, or source-release changes. D86/D73 govern this increment; D64 independence, the 41 conditional meanings, privacy and exact source/method/purpose gates remain.

## What changed

- The interpreter receives the actual server-owned displayed question, target, entity, subject relationship and field meanings. The controller obtains these from the owner/chain/revision-bound presentation, not client text or the scheduler's next candidate. Educational turns with no personal target cannot lend a hidden intake meaning to the following answer.
- The existing semantic circumstance proposal can now use that question as meaning support. Month/year must still occur in the answer at the supplied precision. The existing first-of-month boolean has its own exact answer-support span; unanswered remains null. There is no extra birthday phrase branch. Existing direct structured parsing remains, but it no longer manufactures an “I turn 65” user sentence to pass classification.
- `contextual_capture.py` supplies contextual classification alongside the frozen `natural_state.py`. It preserves hypothetical/question/uncertainty/conflict handling and never calculates eligibility or enrollment dates. The original capture module remains byte-identical to the source pinned by the r2 comparison experiment.
- Composition receives request-local capture outcomes: accepted, already known, needs clarification, conflicting, or unsupported. Accepted/reaffirmed situation reports are included among resolved reports even after the next-question context changes. The outcome record carries IDs/status/reasons, not another copy of raw quotes or rejected values.
- `working_assessment` joins references to the existing reported goal, current concern, learner observations, delivered curriculum, report states, unresolved items and capability holds. It is a view over existing permissioned state, not another saved profile or a new questionnaire. Report-presence markers survive history pruning; absent history or an absent field does not prove the user never answered.
- The shared composition policy asks the model to distinguish answering the latest question from reaching a useful stopping point in the broader goal. It chooses explanation, clarification, consequential intake, a supported next step, or an ending. Educational questions can have a null personal target. There is no mandatory follow-up or case-specific response script.
- Optional `conversation_assessment` supplies tentative progress/next-move enums in the existing composition call. It cannot authorize an action, clear a hold, establish comprehension, or certify recommendation readiness. Malformed metadata is discarded without dropping otherwise valid prose.
- Value-free continuation metadata distinguishes a chosen answer-only turn, a question, validation-altered continuation and a withheld composition. It remains in the existing owner/visit/TTL-scoped RAM brief and response diagnostics, never saved reports. A failed turn or removed question does not masquerade as successful task completion. The existing explicit pause override remains authoritative.

## Preserved boundaries

The original curriculum, learner-state contract, source/evidence files, profile persistence format, protected variants, byte-for-byte UI assets and provider/budget/transport configuration are unchanged. No new paid stage, retry allowance or live evaluation was added. Existing recovery still validates whole components and retains evidence gates. No literal-name/date/amount guard was removed. Interpretation is still a semantic model proposal; exact provenance/type/scope checks do not prove perfect semantic entailment.

New support quotes are request-local. Existing deliberate Send permissions and separate optional sensitive saving remain. No raw transcript retention was expanded. Commercial economics remain absent from guidance. Unknown must-haves and failed external checks remain material holds regardless of the model's proposed conversational stopping point.

## Offline verification

`tests/test_turn_contract.py` exercises the reported compound answer and unrelated question meanings, the actual displayed question, unsupported month/year/boolean claims, uncertainty and conflicts, corrections, wrong-person/hypothetical claims, accepted facts surviving history pruning, reaffirmation outside the previous topic, educational continuation and intentional endings, removed follow-ups, malformed optional metadata, explicit pause, failed composition, owner/chain/TTL isolation and unresolved provider verification.

The broader suite runs through `run_offline.py`: real curl provider transports and non-loopback socket connections are forbidden; HTTP checks use temporary local fixture servers and injected model responses. The initial sandbox cannot bind local ports, so the local HTTP checks are separately run with that sandbox restriction lifted. This does not permit live AI calls.

The original r2 experiment's `run.py --check` passes after retaining its frozen capture source, including all six cells and the hospital-only three-to-four-day correction. `before-hashes.json` records 48 protected assets/configuration/source files. Final verification and activation are recorded below when complete.

## Limits

Scripted transports verify state handling and authority, not model-selected phrasing or whether a person finds the conversation natural. No real-model conversations were run, and no quality improvement is asserted from test counts. Owner review remains the evidence for naturalness and useful pacing. The model can still misunderstand a supported phrase or choose an unhelpful continuation; this change supplies coherent state and makes validation-altered endings distinguishable rather than promising their elimination.

The broad repository suite contains pre-existing checks for removed prepared lessons, visual blocks and the state changes those used to produce. `baseline_failures.py` and `baseline_http.py` replay those failures against the exact pre-edit backend snapshots, without resetting working files. These are reported separately rather than restoring canned output or changing the UI to satisfy obsolete expectations.

## Final result and local activation

- **347 focused offline checks passed** on the final code, including the new contextual/continuation cases, existing learner/curriculum checks, profile/persona coverage, factual safeguards, composition recovery, and provider/budget accounting. No live model generation was used.
- The broad offline run executed **1,003 tests**: 985 passed; 13 failures and 5 errors reproduce against the pre-edit backend. The exact lists and baseline comparison are in `final-full-result.json`, `baseline-result.json` and `baseline-http-result.json`. They concern superseded prepared-lesson/visual behavior, its former state transitions/replay assumptions, and an unchanged frontend Send test. This is not a claim that the entire historical suite is green. The last field-literal uncertainty adjustment was covered by the final focused run, including all twelve months.
- The original r2 source replay and three-to-four-day calculator check pass. `natural_state.py` is byte-identical to the snapshot and the experiment's pinned capture source.
- All **48 protected files** retain their before hashes: UI assets, curriculum/learner/evidence content, server, model/price/budget policy, provider clients, counting and transport.
- Only the existing **:8893** LaunchAgent was restarted. `activation.json` records its PID/time and the two free local health responses. No model calls, guest-store migration, UI edits, source acceptance, or released personal recommendations were performed.

Owner-facing result: contextual capture and response continuity are implemented and locally active. Naturalness, learner benefit and the model's actual choice of next move remain for owner review; scripted conversation text and test counts do not establish those outcomes.
