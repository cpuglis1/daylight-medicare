# D137: Daylight restored

November 11, 2026, America/New_York. The owner requested: “Okay revert back to daylight, medicare plain as day.”

Restored **Daylight** across :8894 and the shared advisor's authored instructions, status/error text, privacy copy and Ask/Talk labels, including the newer Medigap and Part D tabs. Landing copy is again **Medicare, plain as day.** with **Understand your coverage options and prepare to enroll, at your pace.** The sun, photo, layout and functionality are retained.

Removed only the obsolete busy-error translation from the local response handler; retained that handler's newer Medigap/Part D initial-profile fields and its internal class name. Internal identifiers, schema names, assets, cookies, logs and saved records were not renamed. No source data, acceptance state or protected variant was changed. Unaccepted rule drafts remain inactive. Updated D137 and the current product/design records; earlier naming evidence remains historical.

## Scope and pending changes

[change.diff](change.diff) records this task's targeted changes against the captured [before manifest](before-manifest.json). It does not roll back the workspace to yesterday's snapshot.

Before restart, four existing backend files were newer than the running process: composition recovery, natural agent, natural flow and Medigap profile. Reviewed their current recovery/grounding/routing behavior and ran the relevant existing offline checks. A further plan-task-routing edit arrived in `natural_flow.py` while verification was underway. It was preserved, [recorded separately](preserved-concurrent-changes.diff), and the relevant checks were repeated against the updated source. No messages were sent to other chats and no other work was reset or discarded.

[Pending review](pending-review.json) records the process baseline and the limitation: file modification times do not prove the exact earlier in-memory revision. The final [tested source hashes](tested-source-hashes.json) stayed stable through the last checks and matched immediately before restart.

## Verification run

- **152 offline Python tests passed**: `test_natural_agent`, `test_composition_recovery`, `test_medigap_profile`, and the Plans catalog-authority/chat classes. Socket connections were patched to fail. [Log](python-checks.log).
- **36 focused Python checks passed on the final pending source**: `test_medigap_profile`, `test_composition_recovery`, and `test_natural_flow.RetestNov9FlowTests`, again with socket connections blocked. These overlap the first run and are not a distinct total. [Log](pending-final-checks.log).
- **12 existing HTTP tests passed** using temporary local fixture storage. [Log](http-checks.log).
- **16 existing frontend tests passed**: Part D, Medigap and Plans handoff. Only the two tests that locate the renamed Talk button needed their expected label restored. [Log](frontend-checks.log).
- [Brand-boundary verification](verify_brand.py) passed with two scripted requests and zero paid calls: composer/interpreter identity, verbatim fictional user text, unchanged schemas/cookies, four unchanged Daylight busy errors, pinned engine and inactive rule drafts. [Results](brand-checks.json).
- Parsed changed Python/JSON sources and checked targeted Markdown whitespace. A source sweep found no remaining MidMorning wording in active :8894 files, root advisor Python/JSON or the proxy.
- Inspected the live landing page at desktop 1440 × 900, tablet 820 × 1180 and phone 390 × 844. Verified restored title/home label/hero/support sentence, no phone horizontal overflow, and working enabled Get started/Plans controls after loading. Restored the default viewport. Captures: [desktop](desktop.jpg), [tablet](tablet.jpg), [phone](phone.jpg).

Commands used the existing Python environment with `PYTHONDONTWRITEBYTECODE=1`; unit-test suites were loaded through `unittest` with the network blocks above. Frontend command:

```sh
node --test alternatives/advisor-first/tests/test_part_d_view.js alternatives/advisor-first/tests/test_medigap_view.js alternatives/advisor-first/tests/test_plans_handoff.js
```

No live model conversation or paid probe was run. Tests establish the configured identity and technical boundaries, not observed live-model self-introduction or owner acceptance.

## Activation and data preservation

Restarted only the existing :8893 launch service and :8894 proxy after confirming no backend child was active and the source still matched the tested snapshot. Used the same interpreters, arguments and launch configuration. Backend PID 46690 became 12924 at 06:48:29 ET; proxy PID 91391 became 12927 at 06:48:30 ET. Both now report `advisorName: Daylight`. [Activation](activation.json).

[Verification](verification.json) confirms identical saved-profile and usage-ledger schemas, row counts and row hashes. All eight guest records remain unchanged. Provider request counts remain OpenAI 79 / Anthropic 5; costs are unchanged. Protected variant hashes and protected-port process states match. [Before](runtime-before.json), [after](runtime-after.json), [read-only snapshot method](runtime_snapshot.py).

Existing history containing MidMorning is not rewritten. Legal clearance, public rollout and all source/method/consumer gates retain their previous status. No commit, push or hosted deployment occurred.
