# Pilot notice: "this is a pilot, for 2026 sample data only"

November 7, 2026 · DQ-01 (pilot scope) · surface :8893 `alternatives/advisor-first/`

## Owner direction

"For DQ-1 just for the pilot, make it so that the model knows to say: this is a
pilot, for 2026 sample data only."

Not yet recorded as a numbered decision. Another agent added D100 to
`DAYLIGHT_REQUIREMENTS.md`, `CURRENT_STATE.md` and `DIRECTIVE_HISTORY.md` at
22:29 UTC while this change was in progress, so those files were left alone to
avoid a numbering collision. Proposed entry for the owner to record:

> Pilot scope notice. In the invite-only pilot, Daylight replies state that this
> is a pilot using 2026 sample data only: in the first reply of each visit, next
> to any plan, price, benefit, network, drug or comparison detail, and, when asked
> about 2027, enrolling, switching or buying, that the pilot shows no 2027 plans or
> prices, cannot enroll anyone, and that Medicare.gov or 1-800-MEDICARE can help.
> Applies only to the pilot server. The DQ-01 manifest gate remains separate work.

## What changed

| File | Change |
| --- | --- |
| `natural_agent.py` | `PILOT_SCOPE_NOTICE`, `PILOT_SCOPE_INSTRUCTIONS` and `PILOT_FIRST_REPLY_INSTRUCTION`, appended to the composer instructions only when `pilot_scope` is set. First-reply request repeats until a returned reply mentions "pilot" (per visit owner; soft, never a rejection). The approved notice text is added to literal-claim grounding in pilot mode only. |
| `server.py` | The `--pilot-state` branch sets `pilot_scope = True` on the base agent and any per-model agents. |
| `tests/test_pilot_scope.py` | New: 7 offline tests. |

Exact diff: [after/changes.diff](after/changes.diff). Before copies and hashes:
[before/](before/). After hashes: [after/SHA256SUMS](after/SHA256SUMS).

## Checks actually run

Offline, network-forbidden, in the desktop Linux VM (Python 3.10.12; the Mac's
own Python was not used). Run from `alternatives/advisor-first/tests`.

| Suite | Before | After |
| --- | --- | --- |
| test_natural_agent | 96 OK | 96 OK |
| test_education_contract | 30 OK | 30 OK |
| test_conversation_claims | 37 OK | 37 OK |
| test_http | 12 OK | 12 OK |
| test_response_failures | 11 run, 2 errors | same 2 errors |
| test_pilot_scope (new) | — | 7 OK |

The two `test_response_failures` errors are environmental and pre-existing:
Python 3.10 `datetime.fromisoformat` cannot parse the `Z` suffix in
`pricing-review.json`. Re-run on the Mac's Python 3.11+ to confirm.

No live model conversation was run. The owner assesses conversation quality.

## Limits and open items

- The pilot server still requires `--fixture`, so model calls are off in the
  current rehearsal. The notice takes effect when the pilot runs live models.
- The instruction steers the model; it is not a hard guarantee on every reply.
  A fixed on-screen pilot label would be the deterministic backstop.
- In pilot mode only, the literals 2026, 2027, 1 and 800 are grounded by the
  notice. Dollar amounts and other dates are still checked (tested).
- Another agent was editing `pilot_access.py` (22:31 UTC) and had edited
  `server.py`, `pilot_budget.py` and `pilot_admin.py` (22:28 UTC) during this
  change. This patch was applied on top of the 22:28 `server.py`. Confirm the
  other agent's next write keeps the `pilot_scope` lines.
- The full DQ-01 exit evidence (build reads only the approved P0 manifest; wrong
  year, unaccepted data and unapproved personal requests fail closed) is not
  implemented by this change.
