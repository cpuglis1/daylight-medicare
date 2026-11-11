# Collier PDP/Medigap backend implementation

November 6, 2026 · D96; preserves D64/D73, D78, D84, D85 and D95.

**Implemented and loaded the private research backend. Consumer display remains
held, with zero genuine approval events.** No UI, advisor route, guest store,
protected variant or original research row was changed.

The additive `dl_plan_types` schema is installed in `daylight_research_2026_r2`.
Its selected research build is:

`b6992365031d7e3bc3253651b21d924e9d160d7a2c6511e1cab96eb9d782c15c`

This is a **2026 Collier source-research build**, not an approved for-sale market,
personal pricing engine or consumer release. A research selection does not alter
the original `dl_review.active_release` or application publication controls.

## What is done

| Plan item | Delivered behavior | State |
| --- | --- | --- |
| B01 | Exact selection of 52 source files and 13 parent manifest/audit bindings; immutable content-derived build; source/code/schema/Python/38-dependency pins; declared populations and explicit dates | Implemented for the retained scope |
| B02 | Added the omitted L10 base benefits, qualifications, monthly tables, discovery map, form leads, filing details and gap/anomaly records; imported existing illustrations and all r3/r4/r5 structured overlays | Loaded and verified |
| B03 | Typed research items and separate PDP/rate views; county-region-offering joins; exact Medigap schedule/cell links; source identity, area/form/conditions and unknowns retained | Implemented without inventing unresolved product/sale/area joins |
| B04 | Separate loader/reader/reviewer/publisher roles; immutable evidence and event records; completion/selection guards; original-receipt replay contract, trusted-reviewer requirements, source/method/output gates, expiry and revocation; permanent serving STOPs | Technical controls implemented; actual approval remains open |
| B05 | Authenticated bounded research API and CLI; exact build/runtime binding; read-only connections; principal/request/build-bound cursors; source/qualification/hold envelopes and verification receipts; consumer route always held | Implemented and verified in-process; no daemon or advisor integration activated |
| B06 | Existing product/filing/condition worklists imported; exact schedule links and source-rate safeguards operational | Required census, source and rating interpretation remain open; no personal rate engine claimed |
| B07 | Deterministic portable prepared streams; restart/checkpoint recovery; append-only research selection/rollback; bounded completed-build diff; source STOP invalidation; metrics, local workload checks and portable runtime archive | Local controls delivered; scheduler/cloud/actual-target deployment remain open |

Implementation and operator guidance:
[package runbook](../../../../infrastructure/daylight-data/src/daylight_data/plan_types/README.md),
[source selection](../../../../infrastructure/daylight-data/config/plan-types.2026.r1.json),
[API](../../../../infrastructure/daylight-data/src/daylight_data/plan_types/api.py),
[SQL schema](../../../../infrastructure/daylight-data/src/daylight_data/plan_types/schema.sql).
No legacy adapter, original migration SQL or current dependency lock was edited.

## Actual loaded populations

| Kind | Serving records |
| --- | ---: |
| PDP offerings / fields / Florida county relations / restriction observations | 10 / 310 / 67 / 10 |
| Medigap standardized variants / benefit cells / combined source conditions | 12 / 108 / 52 |
| Medigap discovery groups / source listings / historical-and-current insurer leads | 213 / 305 / 188 |
| Illustrative annual observations / published monthly table observations | 115,500 / 680 |
| Filed annual cells / exact schedules | 63,196 / 628 |
| Other research records / complete source-document envelopes | 95,908 / 11 |
| **Total** | **277,198** |

These are different grains, not additive counts of policies or current Collier
offers. All 10 PDP identities join through Collier `12021` to region `11`.
Filed Medigap cells retain **zero asserted county mappings**: unresolved area/form
applicability was not filled from the requested county. Historical/replaced grids,
future periods, group/SELECT context and exact native source strings remain present.

The filed cells include 22,052 replaced observations, 78 source-zero observations
and 43,364 observations with incomplete rate periods; categories can overlap.
The service withholds a supported rate for replaced, zero/unresolved,
unknown-period and out-of-period observations. It preserves the raw source amount
for research. Every result retains `personal_quote: false` and held authority.
Annual illustrations and monthly tables retain separate bases and limitations.

## Verification actually run

| Check | Actual result |
| --- | --- |
| New fictional unit/PostgreSQL/API suite | **17 passed** on PostgreSQL 18.6/Python 3.14.7. Covers signed/zero/unknown money, source/scope tamper, exact trusted review/expiry/revocation, county joins, date/rate holds, privileges, immutable completion, interrupted-source rollback/resume, cursor integrity, denied personal inputs, consumer denial and cross-build source STOP invalidation. [Log](backend-tests-final.log) |
| Existing PDP and Medigap filing-boundary regressions | **29 passed**: 15 L04 and 14 L10 filing tests. [Log](legacy-reference-tests.log) |
| Full loaded-value parity | **All 277,198 records across all 52 sources passed**, comparing every typed column, complete payload and condition to the exact prepared streams, in a read-only transaction. 25.63 seconds including API checks. [Receipt and per-source accounting](verification-final.json) |
| Real research API/gate checks | Authenticated Collier PDP: **200 / 10 records**; consumer: **503**; unauthenticated: **401**; personal input: **422**. In-process HTTP adapter, no model calls. [Receipt](verification-final.json) |
| Existing release/storage controls | Original compact source sets: **315**. Original acceptance bindings/releases/released offerings: **0/0/0**. New genuine review events: **0**. New serving item relation including indexes, retaining both loaded revisions: **1,437,081,600 bytes**. [Receipt](verification-final.json) |
| Small local read workload | Forty calls across PDP, benefits, discovery and an exact filed grid. Serial medians **18.3–26.8 ms**; four-worker medians **57.7–65.9 ms**. This is not a national or production-capacity benchmark. [Measurements](query-benchmark-final.json) |
| Portable runtime | A source-runtime archive was extracted to a fresh temporary directory; imports came from that directory and verified the selected build/38 dependency pins without the original repository path. Original-source independence also passes in the fictional suite. [Receipt](portable-runtime-final.json) |

The final real load completed in **26.34 seconds**, with 52 source-level atomic
checkpoints, followed by research-only selection and full parity verification.
Prepared source populations and the runtime archive remain private/ignored at
`infrastructure/daylight-data/.state/plan-types/`.

The first fictional integration run caught a shared mutable scope value; it was
fixed before any real schema/load. The earlier offline candidate is preserved at
`2026-candidate-r1`, with its exact code in `2026-candidate-r1-code`. Initially
loaded `2026-candidate-r2` adds execution/code-stability and exact completion/source
guards. Final `2026-candidate-r3` also propagates an exact-source STOP to later
builds reusing that source. R2 and its code remain retained; only r3 is selected.
The [source diff](source-diff-final.json) records no payload/population change.
No old candidate was overwritten.

The test client emits a Starlette/httpx deprecation warning; the checked behavior
passes. An offline wheel-build attempt could not import `setuptools.build_meta`
from the existing data virtualenv. The alternate portable source-runtime archive
and extracted-runtime check passed; no packages or frozen locks were changed.
A fresh dependency installation/wheel build and actual cloud-target validation
remain unproven. The broader original L10 PDF-extraction suite was not rerun;
that environment's previously reported `pdfplumber` gap remains separate from
this query runtime, which does not import PDF parsers.

Targeted whitespace checks pass. The workspace-wide `git diff --check` reports
unrelated trailing whitespace in protected `cms-slice/apps/chat/index.html:27`;
that existing/concurrent UI work was left unchanged.

## What remains open

1. **Actual approval.** Source-use, qualified R15/meaning/method review and exact
   output acceptance for PDP and Medigap capabilities. No genuine receipt or
   reviewer trust assignment was invented. The consumer endpoint remains 503
   even when fictional gate receipts are accepted in tests. A later reviewed
   consumer implementation must follow actual approval.
2. **Medigap data/rating completion.** Complete 2026 insurer/form/variant/current-sale
   and Collier applicability census; other-company source contents; Blue approved
   intervals and form editions; automatic-payment/discount/fee/modal-factor and
   rounding reconciliation, applicable amendments, group and SELECT conditions.
   All seventeen supplied filings are already retained and imported. The remaining
   work is not another request for those files. [Required source ledger](../../../data/l10-medigap-2026-10-28/targeted-filings-r5/gaps.json).
3. **Personal capabilities.** No personal Medigap quote/underwriting/buying-rights
   engine or PDP formulary/pharmacy/annual-cost calculation was enabled. These need
   their own accepted evidence/methods and permissioned customer-plane work.
4. **Operations and deployment.** Dedicated service login/secrets, persistent
   process supervision, advisor integration, scheduled acquisition and reviewed
   refresh operations are not activated. Cloud provider/region/budget, actual-target
   TLS/roles/dependency install/recovery and source-object relocation remain open.
   The new tables supplement the same research database; the compact archive,
   original recovery evidence and all source bytes remain retained.

D64/D73 review: inclusion/order uses only source scope and stable evidence IDs;
unknown or uncompensated options are not penalized. Coverage types remain distinct
and neither a PDP premium nor Medigap illustration becomes an Original Medicare
total. Requests accept no beneficiary facts; telemetry stores no private prompt,
transcript or profile. No AI call, outreach, paid probe, source-STOP retry, UI
change, source acceptance, customer migration or cloud resource was performed.
