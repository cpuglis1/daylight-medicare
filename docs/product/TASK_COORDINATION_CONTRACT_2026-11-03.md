# One task, connected checks and useful outcomes

November 3, 2026 · D89 with D64/D73/D86/D87/D88 · :8893 backend increment.

The owner supplied four connected research implications and requested adding them to the backend. They extend one existing product requirement: Daylight should reduce the research and coordination a person must manage while preserving understanding and control. The provider-service archive supplies examples to investigate; it does not establish brokerage/enrollment behavior, representative prevalence, consumer preference for Daylight or a validated benefit from AI.

## Relationship to existing work

| Owner implication | Existing foundation | Added connection |
| --- | --- | --- |
| Understand the task under the question | Explicit goal, scoped reports, current concern and conditional question candidates. | The agent selects which check connections are consequential now, without a second goal record or universal questionnaire. |
| Make verification understandable | Report provenance, identity/research boundaries and held comparison authority. | Separate input availability, external verification and action execution for each check. |
| Teach a blocking concept | Granular education record, grounded current clarification and D88 contextual guides. | Tie the clarification to selected work and retain the existing optional task return point. |
| Carry work to a useful result | Existing preparation review, authorization and operation receipt. | Preserve open check identifiers during the current visit; distinguish an explanation, an open check with a next step and a completed local preparation. |

D88 remains the shared knowledge/guide contract. D89 coordinates its use with existing tasks and evidence. No D88 catalog, lock, statement, numerical example or source acceptance changes in this increment. Earlier working source bytes are retained in the new execution packet's `before/` archive; earlier packets remain unchanged.

## Agent and software responsibilities

The existing composition stage gains a small `task_work` selection:

- Up to four `check_ids` consequential to the present task.
- Up to two `blocking_concepts`, accepted only when supported by an existing open clarification or the current validated clarification request.
- A `next_step` category: answer, clarify, teach, prepare, review or pause.

The eight available check types are exact coverage identity; clinician/office identity; exact-plan participation; service/benefit conditions; personal payment; enrollment timing; coverage choices; and practical help/coordination. These are internal connections, not eight consumer questions or new eligibility predicates. The model chooses from them using the person's existing goal and conversation. It cannot author verification status, completion, source acceptance, diagnoses, clinical judgments, caregiver authority, hard priorities or commercial preferences.

Previously selected open checks accumulate within the same task, bounded by the eight check types. A changed explicit goal or task switch drops the prior selection. The current catalog and distinctions provide one shared vocabulary instead of independent prompts for each research anecdote. Existing approved question candidates continue to govern personal intake; selecting a check does not create a new question or require gathering every possible dependency.

## Verification and honest completion

The module derives input state only from the already permission-minimized reports and known-state entries available to composition. It adds no hidden personal values. A field absent from that context is `not_in_current_context`, which must not be interpreted as missing from the profile or absent coverage. Unknown, deferred, derived and stale states remain explicit.

Reported inputs never establish any of these stronger findings:

- A coverage type or carrier name does not independently identify an exact plan.
- A clinician or office name does not establish an exact source identity or plan participation.
- An office accepting a carrier does not establish participation in a particular plan at that location and time.
- Participation does not establish coverage for a service, satisfied conditions or authorization.
- A published amount or subtotal does not establish personal payment or a binding quote.
- A family relationship does not establish permission, care availability or financial eligibility.

No production loader for accepted external task findings or action receipts is introduced. All outside check results in this increment remain `not_verified` and `not_started`; `supported_findings` and `completed_external_actions` stay empty. Finishing intake or choosing a check cannot promote them. Their exact source/method/permission/release work continues under the existing layer contracts.

Each open selected check carries a concrete next-step category and relevant distinction that the agent can explain in the person's context. Preparing questions for an office or official service is useful supported work; it does not mean that service was contacted. The existing authorized `run_preparation` operation produces `preparation_completed` only when its server-created receipt matches the current profile fingerprint. The receipt does not resolve the original outside task.

The composer retains its existing factual guards and gains a bounded literal guard against unsupported contact, referral, appointment, exact-identity and callback claims. This is a mechanical safeguard, not proof of semantic entailment for every possible paraphrase. Real-model language/meaning evaluation remains required.

## Teaching and continuity

When a supported concept blocks progress, the agent can explain it through the current situation, select the relevant D88 guide and keep the practical return point. The task result records `explanation_delivered_not_comprehension`. An introduced concept, viewed picture or chosen follow-up never establishes understanding.

ADLs and PPO in the supplied research illustrate this pattern. This increment does not add clinical rules or independently reviewed definitions for those particular terms. It uses the existing supported concept/evidence catalog; an unsupported definition still needs an appropriate source/content revision. No diagnosis or functional-eligibility inference follows from the archive examples.

The new state contains selected check/concept identifiers, a next-step enum and a server-only binding to the existing task/goal. It reuses the existing owner/visit isolation, one-hour TTL, visit cap, explicit deletion and v3 continuity permission. It stores no additional raw goal copy, provider/drug value, narrative transcript or external source row. It is not persisted in guest profiles and does not create cross-device recovery or household sharing.

Free local reading/review controls preserve an already permitted visit without granting AI transfer permission or renewing the visit's expiry. A failed turn preserves existing work memory while issuing no fresh result; historical replay suppresses stale task results. Current authenticated replay retains its original server-built result without another model call.

## Implementation and validation

`task_work.py` owns the finite vocabulary, selection validation, task binding, check-state derivation, teaching linkage, result contract and action-claim guard. `advisor_memory.py` keeps the bounded record under the existing visit lifecycle. `natural_agent.py` proposes selections in the existing structured response; `natural_flow.py` supplies scoped check context, commits successful selections and binds local receipts. `server.py` exposes a build marker; request diagnostics include numeric task-context size only.

The existing two typed-message stages, at most one finite-answer composition stage, 900 output tokens, 16,000 input tokens, 96,000 request bytes and $5/UTC-day aggregate policy remain. No paid evaluation, model retry, UI change, new contact integration, source acquisition or external message is part of this increment.

Controlled tests cover the four owner implications, input/verification distinctions, unknown/deferred states, task switches, teaching detours, active versus historical replay, malformed metadata, failed turns, existing preparation authorization, deletion and save boundaries. Tests use fictional data and injected transport; they do not establish live-model timing, consumer comprehension, lower effort, functioning outside integrations or consumer release acceptance.

## D73 change-review evidence

| Review concern | Evidence or remaining gap |
| --- | --- |
| Useful task and minimal intake | Agent-selected check connections reuse existing goals/reports; no new capture paths or questionnaire. Tests preserve pauses, unknowns and detours. |
| Coverage paths and tradeoffs | Existing D88 explanations and neutral comparison mechanics are unchanged. No new personal policy selection occurs. |
| Reported inputs versus external evidence | Separate states, empty accepted findings/actions and unchanged source/release holds. |
| Independence and correction | Finite check vocabulary accepts no commercial fields; current reports and goal bindings drive work. Corrections/replay do not create verified results. Full I01–I10 release evidence remains separate. |
| Permission and continuity | Existing v3 owner/visit/TTL/delete controls; identifiers only in current visit RAM; no new profile persistence or transfer scope. |
| Actual capability | Current preparation receipt can establish completed local preparation; outside tasks remain unexecuted. |
| Consumer proof | Observe consequential omissions, next-step accuracy, correction success, effort, understanding and actual task completion. No improvement is inferred from test counts. |

[Execution, checks and activation](../../audit-evidence/task-work-20261103/README.md).
