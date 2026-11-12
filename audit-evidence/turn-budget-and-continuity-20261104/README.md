# D86/D90 turn admission and continuity

Owner request: remove the early “complete turn could exceed the shared $5 daily AI limit” block, allowing the limit to be reached, and add a check against repeating information. Active on local :8893 as of November 4, 2026, 17:53:53 EST.

## Changes

The local advisor now admits a new turn whenever accounted usage is below $5. It records each stage's full counted input/output reservation, but does not reject the admitted turn because its forecast cost crosses $5. Its existing bounded recovery allowance can finish too. New turns stop once accounted usage reaches the threshold. **The last admitted turn can finish above $5; this is a start-of-turn threshold, not a hard maximum bill.**

`AdvisorDailyBudget` applies this policy only to :8893, including the single-request path and usage status. `TurnReservation` checks admission atomically; continued recovery must reference the existing settled/uncertain stage receipt with the same budget/model and remaining attempt allowance. No client field can request a budget exception. Exact counting, verified settlement, uncertain holds, cross-midnight accounting, pricing/clock checks, transport/output bounds and recovery limits remain. Unused reservations are released. Existing charges and holds are preserved; no allowance was increased or reset. Protected variants retain their previous policy.

The shared composition prompt now asks the model to compare its proposed response with `recent_exchanges` and `education_context.learning` before sending. It should add the newly useful information, implication or next step, instead of repeating explanations, cautions or acknowledgments in other words. Revisit remains appropriate for an explicit request, confusion, correction or changed guidance. A prior explanation still does not establish comprehension. This uses the existing context and model call; there is no new reviewer call, phrase filter, case script or automatic deletion of generated sentences.

The latest owner-requirement entries supersede the previous worst-case budget ceiling only for this advisor. The curriculum, profile, evidence, factual and recommendation safeguards remain intact.

## Verification and activation

**181 technical checks passed** (`checks-final.txt`). Temporary-ledger and injected-transport tests cover positive balance admission, the reached threshold, full exact receipts above the threshold, concurrent admission, completion/recovery for all three selectable models, and free exact-turn replay after crossing the threshold. Existing factual, recovery and education contract checks pass. Updated budget assertions reflect the new authorized policy; prior versions are retained in `before/`.

Compilation passed. Hash checks preserve all **38 web assets** plus nine curriculum, memory, profile-state, evidence and comparison files. No UI assets changed. The pinned shared engine still verifies on import.

Only the :8893 launch agent was restarted, with listener PID **84288**. Free GET checks for the page, JavaScript and usage endpoint returned HTTP 200. Served JavaScript matches the unchanged local file. At activation the existing ledger reported $4.9477362 accounted, $0.0522638 remaining and `canRequest: true`, with no early warning. See `activation.json`, `verification.json` and the scoped `changes.patch`.

**Zero paid model calls and no live conversation tests.** The repetition instruction is deployed for owner review; technical checks do not establish that every future response will avoid repetition.

D73 review: this removes premature test interruptions and gives the existing learner/decision framework a general continuity check. Consequential intake, source/report distinctions, permissions, independence and personal-purpose holds are unchanged. No new profile meaning, external capability, release acceptance or recommendation authority is added.

Re-run technical checks:

```sh
PYTHONPATH=alternatives/advisor-first/tests infrastructure/daylight-data/.venv/bin/python -m unittest test_advisor_budget test_composition_recovery test_connection_recovery test_natural_agent test_education_contract test_education_followups -v
```
