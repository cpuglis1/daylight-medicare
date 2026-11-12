# Advisor session recovery

November 4, 2026 · D86/D90/D73 · advisor-first :8893

The owner reported a normal second message ending with “Your conversation changed. Keep this message and resume the latest state.” The continuation guard rejected the request before model execution, while the browser retained the draft without obtaining usable current state. A process restart reproduces the same error; historical logs do not prove which mismatch triggered the reported visit.

The owner authorized repair and permits discarding earlier chat during reconnection. The implementation retains reported details and drafts when possible and never treats a session failure as a reason to weaken factual checks or silently retry a paid action.

## Behavior

- A lost response is checked against the existing owner-bound request journal. A completed current reply is returned without another interpretation or composition call.
- If that request is still processing, the browser checks for its receipt at most twenty times, 1.5 seconds apart. These checks never start a model call. If work remains in progress, a subsequent deliberate Send retains the same request key.
- A newer trusted snapshot in the same conversation replaces stale browser state. A lost server session reconnects validated reported details using the existing free refresh operation. Obsolete choices and action tokens are discarded, and the draft stays available for a new deliberate Send against the visible question. Earlier displayed chat can be cleared.
- A newer draft is never overwritten by an older failed message; the existing Restore draft control retains the older message separately.
- Expired guest authority reconnects through the existing session refresh with saving paused. Cached state cannot re-enable withdrawn saving permissions.
- Unavailable or rejected generation remains outside assistant history. Provider/content failures, named-action conflicts and recommendation holds do not become session-retry authority.

## Implementation

`natural_flow.py` owns free receipt/state recovery and reuses its existing source/understanding/task-work checks on replay. `session_recovery.py` adds the authenticated same-origin/CSRF-protected recovery route and structured recovery categories for the relevant turn conflicts. The pinned shared server is unchanged. `web/advisor.js` handles automatic receipt checking, state reconnection, draft restoration and usable continuation in the existing interface.

No model prompt, model selection, generation-stage policy, budget limit, saved-profile schema, transcript retention, source release or recommendation authority changes. Recovery does not save reports, execute a preparation token or transmit another message to a provider. The earlier independently funded provider-stage connection retry remains separate.

## Verification

- Eleven focused controller cases cover restart, completed receipt replay, stale snapshots, later corrections, lost recovery receipts, active work, request-key mismatch, privacy withdrawal, named actions, owner revocation and invalid profiles.
- Four real HTTP cases use temporary databases and fixture responses, including replacing the actual server instance while retaining its guest database. They cover resumed Send, completed-versus-stale results, origin/CSRF/query guards and foreign-session isolation.
- Thirty-four production-JavaScript Send tests cover ordinary Send and recovery, including polling completion, bounded checks, newer drafts, exact request reuse, expired guest reconnection and unavailable-generation history.
- Browser check: an open fictional visit survived an actual temporary-server stop/start. The next Send reconnected and restored the full draft; a subsequent deliberate Send succeeded. Desktop and phone continuation were inspected, and the preserved tablet layout was inspected at 768 pixels without horizontal overflow. [Reconnected draft](reconnected-draft.jpg) and [continued phone view](continued-phone.jpg) are fixture evidence, not real-model conversation-quality evidence.
- The configured app Python environment passed **940 tests in 147.949 seconds**, including the production-JavaScript checks. The focused Send suite passed **34 tests**. The first invocation used system Python and encountered three missing-`jsonschema` dependency errors; its log is retained separately.
- Local :8893 was restarted as PID 19408, returned HTTP 200, served the exact tested JavaScript, and rejected unauthenticated recovery with HTTP 401. The [completion receipt](completion.json) records those observations and 11.58 minutes from the implementation checkpoint, excluding the earlier investigation/design reads. Reload an already-open page once to load the new browser code. No public deployment was made.

All new evaluations use synthetic data and no paid provider calls. Existing real customer stores and the shared budget ledger are not reset or migrated. The source manifest pins the implementation and test files; `before/` preserves their predecessors and requirement records.

## Limits and release scope

This fixes a recoverable session dead end; it cannot guarantee uninterrupted network/provider availability or establish human comprehension. A changed question still requires a deliberate Send, rather than guessing how an earlier answer should be interpreted. Recovery retains the existing finite in-memory journal and visit expiry; it adds no durable transcript. If the service cannot be reached, the draft stays local and the notice gives a usable retry action.

D73 review: useful continuation improves, intake/curriculum meanings remain unchanged, reported inputs remain distinct from verified findings, commercial independence and source/method/purpose holds remain, and privacy choices remain owner-controlled. No plan integration, visual redesign, public deployment or protected-variant change is included.
