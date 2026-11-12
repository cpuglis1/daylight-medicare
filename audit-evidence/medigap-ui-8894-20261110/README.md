# D129: Medigap prices in the existing Plans tab

Completed and activated locally November 10, 2026, America/New_York.

The owner requested immediate matched Medigap prices for ZIPs 34101–34108,
ages 65–74, using the existing MA interface and leaving the rest of the tool
alone. The :8894 **Medicare Supplement (Medigap)** tab now reads the verified
private PostgreSQL cache through `POST /api/plans/medigap` on :8893.

## What participants can do

Enter the coverage recipient's exact ZIP, age on November 10, source sex
category and tobacco category, then select **Show matched prices**. The
existing reported ZIP is reused when available; fresh age/sex/tobacco answers
are not preselected. Inputs remain in browser memory for this visit and do
not enter saved profiles, chat or model context.

The view uses the MA visual system: cards, source amounts, company search,
plan-letter filtering, display sorting, a detail sheet and comparison of up
to three listed rates. Every source rating class remains visible. The count
is labeled **listed rates**, not a count of distinct policies or eligibility.
Inputs collapse into **Edit pricing details** after a successful lookup;
changing an input removes the old results and comparison immediately.

Ages 75+ show **“Medigap pricing for ages 75+ is not supported in this pilot.”**
beside the age field. Under-65, unsupported ZIPs, different dates, unavailable
sources and changed/stopped builds never substitute another profile's prices.

The cache is explicitly for requested date **November 10, 2026**. Monthly and
annual amounts are independent source values; unknown amounts stay unknown.
Discount premiums remain conditional. Fee timing, eligibility, policy forms,
availability and qualification for a class/discount are not inferred. Anomalous
rating/outlook source labels are flagged in source details and never ranked.

## Boundaries

D129 is explicit owner authorization for this bounded local source-price
display. The existing D128 research build remains immutable, including its
historical review holds. This change creates no independent source/method
review receipt, binding quote, eligibility conclusion, recommendation or
hosted deployment. It adds no CSG acquisition, Data Feeds/API call, vendor
spending, source STOP exception or database permission/membership change.

The endpoint uses existing same-origin, guest-cookie and CSRF checks. It is
POST-only, rejects extra authority/economic fields and query strings, opens
read-only exact-build database access, and returns a generic recoverable
failure without source rows or internal error details. Prices and these lookup
inputs are excluded from the MA chat-context snapshot. The existing AI,
conversation, MA recommendation logic and Part D placeholder are unchanged.

## Verification actually run

| Check | Observed result |
| --- | --- |
| New route and existing MA regressions | 45 tests passed: `test_medigap_pilot`, `test_plans_workspace`, `test_plans_backend`, `test_plans_filters` |
| UI state and existing handoff | Seven Node tests passed: explicit inputs, exact money/nulls, stale asynchronous replies, age limits, error/retry, profile correction, three-rate comparison, existing handoff |
| Full real-source endpoint parity | All 320 fictional profiles, all 55,040 rate records, every displayed source value/condition compared successfully |
| Local HTTP timing | Median 15.57 ms, p95 17.03 ms, maximum 149.92 ms; serial isolated HTTP server with actual PostgreSQL reads, not a production capacity test |
| Live :8894 browser | 34101/65/Female/Non-Tobacco returned 178 rates, 34 Plan G rows; 34108/74/Male/Tobacco User returned 166 rates, 32 Plan G rows |
| UI failures and correction | 75+ and under-65 messages, cleared old prices, 34109 unsupported with no cards and focus on the message, empty company search, recovery to matched results |
| Controls and responsive rendering | Detail open/close, two-rate comparison, filtering, sorting, MA tab still shows 72 plans; no outer horizontal overflow at 1280×900, 768×1024 or 390×844 |
| Phone comparison | Internal horizontal scroll is labeled and keyboard-focusable; ArrowRight moved the table without widening the document |
| Browser errors | No error/warning entries in the final browser log check |

Evidence: [backend tests](backend-tests.log), [frontend tests](frontend-tests.log),
[all-profile result](profile-verification.json), [verification script](verify_profiles.py),
[browser and preservation receipt](verification.json).

Commands, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests \
  infrastructure/daylight-data/.venv/bin/python -m unittest \
  test_medigap_pilot test_plans_workspace test_plans_backend test_plans_filters -v
node --test alternatives/advisor-first/tests/test_medigap_view.js \
  alternatives/advisor-first/tests/test_plans_handoff.js
PYTHONDONTWRITEBYTECODE=1 infrastructure/daylight-data/.venv/bin/python \
  audit-evidence/medigap-ui-8894-20261110/verify_profiles.py
```

The first route-test attempt could not bind its temporary listener inside the
sandbox and ran zero tests. The permitted loopback run above passed. All new
test-server records were fictional and disposable; no live model conversation
or paid probe was run. The source parity script connects to the actual database
read-only and writes only aggregate/hash evidence.

Browser checks used the in-app browser with emulated viewport sizes. Physical
iOS/Android touch interaction, assistive-technology/user comprehension testing
and production concurrency were not tested. Screenshots contain licensed source
prices and remain private under
`infrastructure/daylight-data/.state/csg-medigap/2026-11-10-ui-r1/`.

## Activation and preservation

Only the existing :8893 backend was restarted, at **19:31:20 ET** on November
10 (PID 91371 → 17008). Its interpreter and launch arguments are unchanged.
The :8894 proxy remained PID 91391; it serves the changed static UI directly.
The tested backend hashes matched before restart, there was no active backend
child process, and the only existing root-runtime source changed since the
last recorded activation was this task's `server.py` connection.

[Before](runtime-before.json), [activation](runtime-activated.json) and
[after](runtime-after.json) snapshots record identical schemas, counts and row
hashes for the saved-profile database and model-usage ledger. Provider request
counts remained unchanged. All 392 captured protected source-file hashes and
protected-port process states remain unchanged. Existing MA service/HTTP files,
engine lock and launch configuration also match the task baseline.

The patch is retained in [change.diff](change.diff); [source hashes](source-hashes.json)
bind the final implementation. The backend CSG source build remains
`7be76407ca94d33223ec0144bac16f2e220fba0205496bdf05577a42ab32831f`.
Collection is still paused. No commit, push, migration or hosted deployment was
performed. Technical verification is distinct from independent domain review,
owner evaluation of the experience and participant-proven comprehension.
