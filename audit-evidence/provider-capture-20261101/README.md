# Provider-submission incident investigation

November 1, 2026 · :8893 only · **Reported production failure remains unreproduced**

The owner reported an HTTP failure after supplying a PCP name and Naples location at T06. The notice was “The service could not complete this request. Your guide is unchanged. Your input is preserved.” This is the shared HTTP handler's generic unexpected-exception response, rather than the normal budget, token-limit, model-unavailable or validation response. It does not identify the exception that caused it.

The two recent failed submissions had settled interpretation calls and cancelled unissued composition reservations. That narrows the suspected boundary, but anonymous ledger rows cannot conclusively associate those calls with one browser conversation. Existing operational logs did not capture the unexpected exception class/location; they cannot establish a cause retrospectively. A separate recorded `ungrounded_literal` composition warning is not proof of this HTTP failure's cause.

## Investigation and checks

- Adapter: 120 plausible T06/RC21 proposal combinations completed without uncaught exceptions. A permanent adapter regression covers both report orders and the supplied lowercase doctor-answer format.
- Controller: reconstructed self/COBRA/insurance-end/Naples/familiarity/previous-teaching states, prior provider states and mixed T06/RC21 proposals completed, including full JSON serialization. The permanent provider capture regressions check retained names/city, resolved context, advancing from T06 and held verification/recommendation status.
- HTTP: a five-message fictional journey passes through actual loopback HTTP, guest cookie, CSRF, continuation, token counting, budget settlement and JSON serialization. All AI responses are scripted; both profiles and the ledger are disposable. Ten stages settle only in that temporary ledger. See `tests/test_provider_http.py` in the advisor variant.
- Real model: one fictional near-identical PCP turn used the actual configured GPT-5.4 and shared budget with a disposable profile database. It captured the fictional provider and advanced to prescriptions. It used **two stages, $0.031905 accounted estimate, $0 outstanding holds**, with no automatic retry or saving. See [live result](live-result.json) and [the bounded script](verify_live.py). This success does not reproduce or resolve the owner's failure.

The final suite passed **385 tests**; results are in [tests.log](tests.log). These checks establish working tested paths, not the cause of the reported exception.

## Local diagnostic change

Added `controller_diagnostics.py` and a narrow unexpected-exception logging boundary in `natural_flow.py`. It logs only a fixed code, code-defined exception class and allowlisted source filenames/line numbers. It never logs exception messages, source snippets, locals, request bodies, profiles, generated prose or identifiers. Expected validation/model errors keep their existing handling. Unexpected exceptions still propagate to the same HTTP behavior; this is observability, not a guessed fix or a silent fallback. Canary tests verify that sensitive-looking exception content is absent.

No conversation prompt, UI asset, branching meaning, profile-saving rule, budget allowance or pinned engine was changed. **The diagnostic change has not been activated in the running :8893 process**, so that the owner's current visit is not reset during this investigation. No existing guest profiles were inspected, changed or migrated. A restart would reset the visit-only server memory; browser state and separately saved reports are distinct.

## Open next step

The owner correctly pointed out that the relevant exchanges had already been supplied: the COBRA-end question, followed by T06 and the exact PCP submission/error. Requesting them again was unnecessary. Continue from that supplied sequence; additional copied conversation is not a prerequisite for investigation. The missing diagnostic is the original unexpected exception's class/code location, which the old HTTP handler did not retain. If the existing sequence still does not reproduce the failure, inspect a subsequent value-free runtime trace rather than repeatedly asking for the same context. Do not claim the doctor-submission bug fixed from these passing tests, attribute it to a spending limit, or buy more provider calls without a concrete diagnostic purpose.

The earlier activation statement above describes the state at the initial investigation. A later, separately authorized D87 local-research runtime now exists; preserve that work and its configuration. This follow-up has not restarted or changed the running service.
