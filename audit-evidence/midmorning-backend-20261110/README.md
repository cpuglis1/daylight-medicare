# D122: MidMorning backend identity and reviewed activation

Completed November 10, 2026. The owner authorized finishing the backend rebrand, preserving internal code names and saved data, and checking pending changes before restarting. This closes the backend deferral in D121. D112/D113 pending runtime work was reviewed before activation; D64 independence and existing source, review and acceptance gates remain in force.

## Implemented scope

- Composer and report-interpreter instructions identify the advisor as **MidMorning**.
- Authored backend status, recovery, budget, identifier, plan-reference and proxy-unavailable messages use MidMorning. Draft company-statement copy uses MidMorning but remains pending owner review and unloaded.
- The service adapts only four exact, fixed 429 busy-error strings from the pinned engine. It does not rewrite user text, reports, arbitrary replies or stored history. The pinned engine remains unchanged.
- `/ten-config.json` exposes the non-sensitive `advisorName: MidMorning` activation marker.
- Internal module names, schema names, cookies, headers, paths, launch labels and database structures retain their existing names. No data migration was performed.

The task-specific [change.diff](change.diff) compares edited files with the captured pre-task sources, rather than treating the workspace's substantial existing uncommitted work as this change. [before-manifest.json](before-manifest.json) records those source hashes and modification times.

## Pending-change review before restart

The original backend process started November 9 at 20:01:21 ET. Of the captured root runtime Python/JSON sources, only the pre-existing `natural_flow.py` modification was newer, at 20:05:49 ET. That file's SHA-256 remained `3e0afbd34fd83fc47ba643a5254162eed0014666b457ee0e5c7a548f8b4cb302` throughout this task.

Reviewed the current source and the existing November 9 fixes/retest records for Plans-page list union and one-time acknowledgement, earlier Plans-question memory, Part A-only interpretation, reviewed-statement fallback, non-repeating recovery, and the fail-closed pending-rule loader. Sixty relevant offline tests passed before edits and before any restart. See [pending-review.json](pending-review.json) and [pending-checks-before.log](pending-checks-before.log).

File times narrow the possible pending changes; they do not prove the exact previous in-memory revision. An exact snapshot of that earlier loaded revision was not available. The reviewed current sources, including the pending controller fixes, are now loaded.

## Verification actually run

All Python checks used the existing `infrastructure/daylight-data/.venv/bin/python` with bytecode writing disabled. Unit-test runners patched both `socket.socket.connect` and `socket.create_connection` to reject network connections. Model transports were scripted; no live advisor conversation or paid model probe was run.

| Check | Scope and result | Evidence |
| --- | --- | --- |
| Before-edit pending checks | 60 tests passed: four targeted natural-flow classes, applicable rules, own-words grounding, context fit and carrier aliases | [Log](pending-checks-before.log) |
| After-edit regression | 200 tests passed: all `test_natural_agent`; `ClarificationLoopTests`, `PartAOnlyTests`, `PlansPageEntryTests`, `RetestNov9FlowTests`; `test_applicable_rules`; `test_advisor_budget`; `test_session_recovery`; identifier `DetectorTests` | [Log](regression-after.log) |
| Offline personas | 14 scenarios, 1,244 assertions passed; zero paid model calls | [Results](persona-results.json) |
| Brand boundaries | Composer/interpreter identity, unchanged schema names, verbatim fictional user text, exact busy-error mapping, unchanged cookies, pinned engine verification and unloaded unaccepted rule drafts passed | [Script](verify_brand.py), [Results](brand-checks.json) |
| Plan authority | 10 tests passed across `CatalogAndAuthorityTests` and `PlansChatTests`, including held fields, revocation, expiry and context limits | [Log](plan-authority-checks.log) |
| Static checks | Changed Python sources parsed; targeted `git diff --check -- DAYLIGHT_REQUIREMENTS.md` passed | Task execution |

The persona command was:

```sh
PYTHONDONTWRITEBYTECODE=1 infrastructure/daylight-data/.venv/bin/python alternatives/advisor-first/tests/persona_runner.py --output audit-evidence/midmorning-backend-20261110/persona-results.json
```

The brand script used an isolated fixture database and local ephemeral listener. Its first run exposed an incorrect schema-name expectation in the verification harness; the expectation was corrected to the existing `daylight_guide_commands` name. No production schema was changed. The subsequent run passed.

## Activation and preservation

Immediately before restart, checked that the sources still matched the tested snapshot and that the backend had no child process. Restarted only the existing `com.daylight.advisor-first.8893` launch service and the existing :8894 proxy, using their existing interpreters and command arguments. No launch configuration was changed.

| Service | Prior PID | New PID | Start time, November 10 ET |
| --- | --- | --- | --- |
| Backend :8893 | 87146 | 91371 | 17:06:58 |
| UI proxy :8894 | 88460 | 91391 | 17:06:59 |

Both services responded successfully and reported `advisorName: MidMorning`; model policy and variant remained unchanged. See [activation.json](activation.json).

Read-only SQLite snapshots compare schema and sorted row hashes without recording profile contents. The saved-profile database and shared usage ledger had identical schema, row counts and row hashes before and after activation. Provider request counts also stayed unchanged. Eighty-six protected/reference frontend file hashes matched, and protected-port process state was unchanged. See [runtime-before.json](runtime-before.json), [runtime-after.json](runtime-after.json), [snapshot method](runtime_snapshot.py), and [activation-verification.json](activation-verification.json).

## Limits

This establishes the configured identity, tested backend behavior and successful activation. It is not an observed live-model self-introduction, owner acceptance, legal name clearance or plan-data acceptance. Existing saved conversations retain their original text. Unaccepted statement drafts remain inactive, and no source STOP or acceptance gate was relaxed. The :8893 reference frontend retains Daylight; the :8894 consumer frontend was rebranded under [D121](../midmorning-8894-20261110/README.md).
