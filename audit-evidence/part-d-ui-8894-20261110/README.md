# D134: Part D in the existing Plans workspace

Implemented and activated locally November 10, 2026, America/New_York.

The owner requested Part D in a very similar way to the completed Medigap
integration. The existing **Part D drug plans** tab on :8894 now displays the
ten retained 2026 Collier stand-alone PDP offerings through a read-only :8893
endpoint. It reuses the shared chat profile and existing MA card, detail-sheet
and three-plan comparison patterns. D134 addresses CAP-01, CAP-02 and CAP-06,
with D64 independence, D96 source boundaries, D108's explicit 2026 default,
D113 silent navigation and D131's conversation-first entry retained.

## Participant behavior

Missing person, home ZIP or county produces a **Talk to MidMorning** invitation.
That button opens the existing conversation and its missing question without
sending an AI message, inventing an answer or clearing the draft. Existing
buttons and free text capture answers; question reasons explain the scope.
Known reports are reused. Explicitly unknown/deferred reports remain open and
are not repeatedly demanded. Corrections use **Edit … in conversation**.

Once the profile has usable Collier scope, the tab loads published plans
automatically. A known coverage year takes precedence; 2026 defaults only when
no usable or explicitly held year exists. Conflicting/stale years do not
silently become 2026. A correction invalidates prior results, comparison and
open details; delayed responses from the old scope cannot restore them.
Unsupported counties or years show a specific message and no plans.

Medicine reports remain available in the shared profile and existing drug
conversation. They are not sent to the plan-source endpoint. Part D does not
ask for Medigap age, sex or tobacco categories, and Medigap's 75+ pilot limit
does not apply to Part D. All ten offerings are shown independent of commercial
relationships; searching and sorting affect display only.

## Source and release boundaries

The source is sealed D96 PostgreSQL build
`b6992365031d7e3bc3253651b21d924e9d160d7a2c6511e1cab96eb9d782c15c`:
the September 2026 CMS published PDP snapshot and retained restriction checks
through October 25, mapped from Collier county 12021 to PDP region 11.
All 31 published fields per offering and source locators are preserved. Zero,
negative components, missing values, and separate subsidy figures retain their
source meanings. No published subsidy amount is assigned to the participant.

D134 authorizes this bounded local display. The original research build,
review holds and genuine acceptance records remain unchanged; no fabricated
source/method receipt or source promotion was created. Existing source STOPs,
exact-build checks and source-review expiry still fail closed. The L04 review
is due November 24, 2026. Partial populations and unavailable sources show a
recoverable error rather than substituted plans.

This is published premium/deductible information, **not personal prescription
or pharmacy cost estimates**, eligibility, subsidy qualification, a binding
quote, live enrollment availability or a recommendation. L05/L06/L07 personal
cost methods remain held. The dated source and these limits appear in the UI.

`POST /api/plans/part-d` uses existing same-origin, guest-cookie and CSRF
checks. It accepts only ZIP, county and year, rejects URL query strings and
extra personal/economic fields, and uses read-only database access. Source
rows do not enter saved profiles, chat context or AI requests. There are no
new profile meanings, schema changes, permissions, source acquisition or paid
vendor/model calls. MA and Medigap behavior and protected variants remain intact.

## Verification actually run

| Check | Observed result |
| --- | --- |
| New source/profile/HTTP checks | 11 passed: scope-only queries, zero/negative values, wrong build/expiry/STOP/partial population, source-based restriction language, missing-only questions, existing medicines, unknown/stale/conflicting years, no Medigap age limit, HTTP authorization and recovery |
| Existing Medigap regressions | 20 passed across source, shared profile and HTTP checks |
| Existing HTTP/session and Plans filters | 12 HTTP tests and four filter tests passed |
| New and existing frontend behavior | 16 passed: seven Part D, seven Medigap and two handoff tests; covers automatic loading, no form, stale replies, corrections, details, three-plan comparison and retry |
| Broader natural conversation suite | 214 passed; one previously recorded failure remains, described below |
| Source parity | All ten IDs, all 310 fields and all source locators equal the retained source records |
| Activated :8894 endpoint | HTTP 200, D134 metadata, ten plans and all 310 database fields equal; served HTML/JS/CSS hashes equal local files |
| Responsive browser inspection | Desktop 1280×900, tablet 768×1024 and phone 390×844; no document-level horizontal overflow or browser warning/error entries |
| Correction and controls | Chat invitation, Me button, ZIP reason/capture, missing medicine question, automatic plans, details, comparison, draft preservation and unsupported-2027 correction observed |

There are **63 passing focused checks**. Commands from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest test_part_d_pilot -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest \
  test_medigap_pilot test_medigap_profile test_medigap_profile_http -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest test_http -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest test_plans_filters -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest test_natural_flow -q
node --test alternatives/advisor-first/tests/test_part_d_view.js \
  alternatives/advisor-first/tests/test_medigap_view.js \
  alternatives/advisor-first/tests/test_plans_handoff.js
PYTHONDONTWRITEBYTECODE=1 infrastructure/daylight-data/.venv/bin/python \
  audit-evidence/part-d-ui-8894-20261110/verify_live.py
```

Python 3.14.7, Node v20.16.0, PostgreSQL 18.6, macOS. Changed JavaScript also
passed `node --check`. [Source hashes](source-hashes.json) bind the final
implementation; [change.diff](change.diff) records the targeted patch against
the task baseline, preserving concurrent D133 naming work.

The broader failure is
`test_pending_ambiguity_does_not_leak_to_another_visit_with_matching_versions`:
its setup expects record revision 2 while the current original flow produces
revision 0. It was already reproduced against the pre-D130 implementation in
the [Medigap profile evidence](../medigap-chat-profile-20261110/README.md).
It remains outside this change and is not counted as passing.

Logs: [Part D](part-d-tests.log), [Medigap](medigap-regression.log),
[HTTP](http-regression.log), [filters](plans-filter-regression.log),
[frontend](frontend-tests.log), [conversation](natural-regression.log).
Read-only checks: [database](database-read.json), [parity](source-parity.json),
[activated endpoint](live-http-verification.json).

Browser checks used the actual UI over a disposable [fictional backend](preview.py),
including narrowly scripted fictional ZIP/year extraction. They verify the
interface and state transitions, not live model extraction or conversation
quality. No agent-run live conversation or paid probe occurred. The temporary
server and browser tabs were closed. Desktop, tablet and phone screenshots are
in [screenshots](screenshots/); all depicted plans and amounts are fictional.
Physical touch devices, assistive technology, user comprehension, production
load and owner acceptance were not tested. The final purpose-text visibility
extension was syntax-checked after browser inspection.

## Local activation and preservation

Only :8893 was restarted through its existing launch agent. The final process
started at 21:23:09 ET (PID 39225), using the same interpreter and arguments.
The :8894 proxy remained PID 91391. No active backend child was present before
restart. [Before](runtime-before.json) and [after](runtime-after.json) receipts
show identical original saved-profile rows, readiness/request tables,
AI-ledger schemas/counts/row hashes, provider request counts, and model/budget
settings. The HTTP checks created two empty guest sessions (including the
initial request with an incorrect CSRF header); both have version zero and no
saved guide. Hashing the original six guest rows confirms they are unchanged.
The corrected endpoint check sent zero conversation turns.

All 406 captured protected source hashes and protected-port states remain
unchanged, including pinned source, sealed plan-type reader and the existing
Medigap implementation. See [verification](verification.json). No hosted
deployment, commit or push occurred. Technical verification is complete for
this bounded display; independent source/method review, personal-cost methods,
consumer acceptance and owner assessment of live conversation quality remain open.
