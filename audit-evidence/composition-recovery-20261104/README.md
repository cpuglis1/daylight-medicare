# D86/D90 composition validation and recovery

Owner instruction: fix validation and recovery while keeping the curriculum, profile, evidence and factual safeguards intact. Do not restore canned explanations or add another case-specific dialogue rule. The owner retains conversational quality review; no live model conversations or paid probes were run.

## Result

Active on the existing local **:8893** advisor. A response is no longer discarded solely because its optional learning metadata is missing or malformed. An invalid composition can receive one same-model repair with the same resolved reports, sources, learner context and current question candidates. A whole independently validated answer can survive an invalid question without another call. If repair fails, an independently validated model-written question can keep the conversation open. Unsupported content remains withheld.

This is a generic recovery mechanism, with no new Medicare phrase, name, date or scenario exceptions. It does not establish that the owner's original rejected wording was correct: rejected drafts were not retained, so the exact triggering date/amount cannot be reconstructed. The existing lexical and source/report guards remain engineering safeguards, not proof of semantic accuracy for arbitrary model output.

## Mechanism and boundaries

- `composition_recovery.py` separates recoverable contract failures from provider failures, supplies bounded request-local repair feedback, and checks whole components. It never splices sentences: removing a qualification could change the meaning of advice.
- `natural_agent.py` validates optional metadata separately, preserves the required core contract for both providers, and applies the existing factual checks to repaired output. The core reply bound now matches the outgoing schema. A provider schema warning about optional metadata does not bypass application validation of required fields.
- A retained question must have the model's original wording, target an approved current meaning, respect required clarification, and pass both question and answer factual checks. An orphaned free-form follow-up is not retained. No new canned fallback explanation or automatic optional intake target was added. Existing approved intake controls remain.
- Completed invalid generation is settled before repair. The replacement is separately reserved, counted and funded under the unchanged **$5 UTC-day cap**. Validation repair and dropped-connection recovery share one recovery slot: at most **two submitted composition attempts**. Accepted extraction is not repeated. Uncertain transport receipts stay held. Billing failures do not trigger repair.
- Failed drafts exist only in request-local memory and may return to the same selected provider as explicitly untrusted correction input. They are not logged, cached as accepted replies, written to profiles or added to visit history. Diagnostics contain fixed failure categories only. Only validated responses enter exact-request replay.
- Rejected prose earns no teaching credit. Question-only recovery carries neutral education/task metadata. Existing curriculum delivery, learner observations, user reports, independent verification, task state and permissions remain separate.
- If neither component validates and the single repair fails or cannot be funded, the response remains withheld with the existing failure status. This is bounded recovery, not a promise of universal provider reliability.

The latest entries in `DAYLIGHT_REQUIREMENTS.md`, `docs/product/MASTER_DESIGN.md` and the scoped `AGENTS.md` record the owner's authorization. It supersedes the earlier network-only retry restriction only for this bounded completed-response repair. Protected variants, source acceptance and personal recommendation gates remain unchanged.

## Technical verification

**178 checks passed** in `final-tests.txt`: 17 new fault-injection/controller checks plus 161 existing agent, budget, connection-recovery and education-contract checks. Subtests exercise all three selectable models and literal, entity, personal-finding and malformed-output failures. They cover optional metadata quarantine, malformed JSON, rejected question premises, exhausted funding at both reservation and token-count stages, interrupted repair, the shared attempt limit, exact usage receipts, replay without another charge, and value-free logs.

A single injected controller transaction verifies that accepted beneficiary reports survive repair, curriculum/source/learner context reaches both attempts unchanged, rejected teaching receives no progress, and extraction runs only once. This is a state/validation test, not a conversational quality evaluation. Network access is forbidden in the new fault-injection tests; provider responses and ledger files are synthetic.

Earlier regression failures are retained in `regression-tests.txt`. Three connection-test assertions still assumed the removed fixed input reservation or exhausted the cap before initial submission; those expectations were corrected. Education tests were aligned with the earlier no-prewritten-visual direction and the new neutral handling of missing metadata. A valid empty update list is no longer mislabeled malformed. Final checks pass; no factual validator was weakened to satisfy them.

Compilation passed. `verification.json` confirms unchanged hashes for **all 38 web assets** and nine curriculum, learner-memory, profile-state, evidence and comparison files. The application UI was not edited. The retained shared-engine hash check passes on import. `changes.patch` and `before/` preserve this task's scoped changes without altering unrelated workspace work.

Re-run:

```sh
PYTHONPATH=alternatives/advisor-first/tests infrastructure/daylight-data/.venv/bin/python -m unittest test_composition_recovery test_natural_agent test_advisor_budget test_connection_recovery test_education_contract test_education_followups -v
```

## Activation and D73 review

The :8893 launch agent was restarted; PID **79889** listened on `127.0.0.1:8893` at **17:43:37 EST, November 4, 2026**. Free GET checks returned HTTP 200 for the page, JavaScript and usage endpoint. Served JavaScript matches the unchanged local UI. See `activation.json`. Existing charges/holds were preserved; activation reported $0.3894198 remaining under the existing daily cap. This task made **zero paid model calls**.

D73: useful self-service improves through checked continuation rather than a rejected whole turn; minimal intake remains model-selected from existing meanings; independent facts and unknowns retain their boundaries; continuity remains owner-bound and permissioned. No new curriculum, profile meaning, verification finding, commercial influence, recommendation authority, external action or public release was introduced. Consumer comprehension and conversational quality remain for owner review. The other local surfaces were not restarted or edited.
