# Current :8893 synthetic profile coverage

November 2, 2026 · D49/D54/D55/D57/D79/D86 · offline controller regression evidence

The ten retained personas and four branch variants are ported to the current :8893 natural conversation controller. Sixteen additional field/state scenarios close missing positive and boundary checks. The **30 scenarios pass 2,164 executed assertions with zero paid model calls**. The runner uses the actual interpretation → validation/capture → composition contracts through an injected in-process transport, with `fixture=False`. It blocks DNS and socket connection paths. It neither starts the app nor reads or writes real guest profiles or the shared usage ledger.

## What is covered

| Inventory | Paths | Executed assertion | Captured reports | Derived values | Remaining capture gaps |
| --- | ---: | ---: | ---: | ---: | --- |
| Original contract | 78 | 78 | 71 | 5 | Two legacy guide fields have no current writer |
| Additional optional detail paths | 14 | 14 | 0 | 1 | Thirteen held paths reject direct actions and remain absent |
| Current report extensions | 4 | 4 | 3 | 1 | No positive-capture gap in this bounded corpus |

The five derived original paths include the normalized county, location evidence and three item-identity links. The current extensions are retirement, age-65 circumstances, named assistance programs and the subject-role mirror. G13 is a compatibility mirror of the reported military program, not a separately verified answer.

All 41 approved meanings retain exact canonical field traceability, including the three documented child aliases. This does not mean every meaning was asked as a displayed question or that every answer combination was exercised. Question rows distinguish field evidence from actual next-question assertions. Unknown, deferred, rejected, stale, absent and reused values do not count as newly captured known reports. Item identities and derived mirrors do not become independent user reports.

## Inspect the results

- [Field and question matrix](coverage-matrix.md), [CSV](coverage-matrix.csv) and [complete JSON witnesses](coverage-matrix.json)
- [Independently authored expected final profiles](expected-profiles.json)
- [Observed final profiles](observed-profiles.json)
- [Executed steps, assertions and transport counts](executed-results.json)
- [Machine-readable summary](summary.json)
- [Retained persona fixtures](../../alternatives/advisor-first/tests/fixtures/persona_journeys.json) and [16 field/state fixtures](../../alternatives/advisor-first/tests/fixtures/field_scenarios.json)

Final expectations are authored separately from controller observations. Exact active guide paths, report IDs, personal report fields, item lists and retained-persona disposition sets catch invented or omitted data. Deliberately changing an expected value fails the suite; no test regenerates its own expected profile. Coverage witnesses bind the executed assertion's exact path, state, mode, expected value and observed value. Negative accounting tests reject relabeled, orphaned, failed and stale-value witnesses.

The new scenarios cover permanent residence, optional goal/priorities, eligibility age range, reported drug gaps, brand/fill details, field-specific unknown/defer, date conflict/correction, dependency invalidation, helper/beneficiary separation, same-name medicines, sibling preservation, explicit no-item reports, held/legacy input rejection, current Medicare ambiguity, report-versus-derived scope, retirement/birthday precision and family-coverage consequences. Scripted compositions also exercise pauses, education detours, consequential follow-ups and composition failure recovery.

## Controller defects found and corrected

Only `alternatives/advisor-first/natural_flow.py` and `natural_state.py` changed in production code. There are no UI, prompt, model, budget, database-schema or source-data changes.

1. **Concurrent assistance programs:** clear current reports of Medicaid and Extra Help no longer contradict each other merely because RC18 retains a scalar latest choice alongside its additive program set. None/decline, uncertainty, unsupported choices and person/time-scope guards remain separate.
2. **Named item clarification:** explicitly identifying a retained medicine/provider resolves the earlier profile-scoped ambiguous edit. A valid capture clears both its named pending target and ambiguous alias when appropriate; unrelated fields and other items remain pending. No first-name match is chosen automatically.
3. **Disputed beneficiary mirror:** a pending conflict about who receives coverage now holds the role mirror as well as RC01. Neither model context nor the comparison binding treats the disputed role as usable.
4. **Beneficiary ownership:** retained personal facts cannot be reassigned by first making RC01 stale, by keeping facts only in readiness, or by resuming a privacy-pruned profile whose role survives only as a guide mirror. Existing information stays with its original person; a separate visit is required for another person.

The independent persona expectations were kept while these defects were fixed. Targeted regressions cover supported program combinations, named versus ambiguous targets, sibling and pending-queue preservation, model/comparison role exclusion, readiness-only ownership and privacy-pruned ownership.

## Reproduce without paid calls

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 alternatives/advisor-first/scripts/profile_coverage.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s alternatives/advisor-first/tests -v
```

Only the explicit report command writes audit artifacts. Normal tests do not rewrite fixtures or evidence. The full suite uses temporary loopback HTTP fixtures and may require local socket permission; its model transports are synthetic.

## Remaining limits

- `guide.fields.needs.medicationDetails` and `guide.fields.needs.pharmacies` remain retained legacy fields without current writers. Medicine identity and fill/pharmacy reports use RC22/RC23. Their absence is tested and not presented as successful capture.
- Thirteen additional detail paths remain held/unwritten in this controller; their absence and rejected direct actions are tested. These are still semantic/source-binding gaps, not completed capabilities. RC23 `supply` supports a voluntary typed report but is not a routine question; quantity and days supply remain separate.
- Every field exposes untested states in the JSON/CSV. This corpus does not exhaust every option, multi-select combination, time scope, entity count or correction sequence.
- A pre-existing inherited guard still rejects changing the beneficiary after both goal and familiarity have been recorded, even when no personal coverage facts exist. The bounded reproduction is T01 compare → T02 new → RC01 someone → RC01 self. This is an over-restrictive safe rejection, recorded separately from the personal-data ownership defects fixed here.
- Scripted model outputs test software handling of a proposed interpretation. They do not establish live-model extraction, item-binding accuracy, natural language quality, comprehension, retention or latency. No paid evaluation is claimed.
- Source evidence, external verification, independent recommendation and exact consumer-release gates remain held. A complete synthetic profile does not establish eligibility, participation, coverage, rights, cost or fit.

## Final verification and local activation

The [final complete suite](tests-final.log) passes **608 tests in 115.142 seconds**, including the existing frontend interaction, privacy, HTTP, comparison and identity checks. An earlier 606-test snapshot passed before the final saved-profile and overlapping-pending-target regressions were added; it is retained separately as `tests-initial.log`. The final [coverage replay](coverage-run.log) also passes all 30 scenarios and 2,164 assertions against the final controller code.

[Protected-file verification](protected-check.json) checks 67 paths against the captured baseline: only the two intentional local controller files differ. All 58 shared-engine pins match. CSS, composition prompts and the local budget policy are unchanged.

The existing `gui/501/com.daylight.advisor-first.8893` job was restarted after the final checks. The first sandboxed restart was denied by operating-system permissions; the authorized elevated restart succeeded. [Read-only activation checks](activation.json) show the page, JavaScript and CSS return HTTP 200 and match the workspace; the status reports the configured GPT-5.4 agent available, automatic retries disabled and consumer readiness still held. These requests make no model call and do not open a browser or create a guest session. No real guest-store action, ledger reset, protected-variant restart or configuration change was performed. Restarting clears temporary in-memory chat/visit state; saved profiles remain intact. Use a fresh visit for the corrected flow.
