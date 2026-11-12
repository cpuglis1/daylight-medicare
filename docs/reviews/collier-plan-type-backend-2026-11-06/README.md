# Collier PDP and Medigap: backend exposure review

Implementation is now recorded separately in the
[D96 execution report](implementation-r1/README.md). The assessment below preserves
the pre-implementation findings and proposed sequence.

November 6, 2026 · D64/D73, D78, D84, D85 and D95 · Review and implementation
sequence; no data promotion, service change or consumer release.

**Both plan types already have data in PostgreSQL. The work is to complete the
selected imports, build plan-type serving models and enforce exact release
authority.** “There is no Medigap pricing data” is too broad: published annual
illustrations, monthly carrier tables and filed annual grids exist. A complete
Collier inventory, supported personal rate calculation and binding quote do not.

This review uses the established **2026** Collier scope. Preparing 2027 requires
new source, geography, method and release bindings; the existing records cannot
be relabeled. Backend preparation can proceed while reviews remain pending.
Storing research and authorizing a consumer output are separate steps.

## Verified current position

[Read-only database evidence](evidence/database.json) records all SQL and results
from one repeatable-read transaction on `daylight_research_2026_r2`, PostgreSQL
18.6. The inspection did not import, update or delete database records.

| Area | Verified evidence | Practical meaning |
| --- | --- | --- |
| Stand-alone PDP, L04 | 10 Florida offerings, 310 field observations; live Collier `12021` → PDP region `11` → all 10 IDs, zero unmatched | The published regional reference is already in the DB. It is a dated September baseline with a separately retained October 25 restriction check, not current enrollment confirmation. |
| L04 transport | Eight selected source sets, 265,248 raw rows and 265,558 observations | Includes national source/accounting/context rows; these totals are not counts of Collier plans. |
| Medigap, L10 | 115,500 illustrative annual observations; 63,196 filed annual cells and 628 schedules from the r3/r5 source grids | Pricing evidence is present. Filed cells span regions, years, policy blocks and approved/replaced versions. They are not 63,196 current Collier prices. |
| L10 transport | 42 selected source sets, 274,574 raw rows/observations | Includes metadata, discovery and conditions alongside monetary evidence. |
| Release authority | Zero acceptance bindings, release manifests, active releases and released offerings | No consumer release has been established in the database. All inspected L04/L10 observations remain `research_only` and `not_newly_reviewed`. |

The latest source accounts are the [L04 published-reference packet](../../data/l04-pdp-availability-2026-10-25/README.md)
and [L10 r5 completion/status](../../data/l10-medigap-2026-10-28/STATUS.md).
The older L10 closeout predates receipt of the final eleven filing packets;
**all seventeen supplied packets are already ingested**. Do not request them again.

## Backend gaps found

1. **The L10 importer skips useful base-package sidecars.**
   [The current adapter](../../../infrastructure/daylight-data/src/daylight_data/adapters/l10.py)
   reads the base SQLite database and three later JSON overlay directories.
   The base SQLite database contains only `illustrations`, `listings`, `insurers`
   and `filing_metadata`. It does not contain the base package's standardized
   benefits or monthly carrier tables. Those exact JSON paths have no selected
   L10 source sets in the live database. The missing source-row imports include:

   | Retained base file | Extent to account for |
   | --- | --- |
   | `standardized-benefits.json` | 12 variants, 108 benefit cells, 11 qualifications |
   | `carrier-table-observations.json` | 680 published monthly observations |
   | `product-discovery-map.json` | 213 source-observed discovery groups |
   | `product-form-leads.json` / `filing-details.json` | 811 form leads / 387 filing detail records |
   | `required-coverage-ledger.json` / `source-anomalies.json` | Per-listing gaps, source omissions and four carrier-only SELECT discovery leads |

   [File hashes and shapes](evidence/base-sidecars.json) identify these inputs.
   This is a projection/import gap, not a claim that their source bytes were lost
   or that equivalent facts cannot appear in another retained document.

2. **A direct county filter cannot serve these records correctly.**
   PDP offering/field rows have no material county: geography is a separate
   county-to-region relation. Every inspected L10 illustration/filed rate row
   also has a null material county and benefit year. Its native source context
   remains in `fields`/related schedules. An API filter `county_fips='12021'`
   therefore misses those observations. Conversely, accepting null year as
   matching 2026 does not prove a Medigap rate applies during 2026. Add explicit,
   evidence-backed joins; do not backfill the immutable research rows.

3. **The existing application research repository covers MA only.**
   [ResearchPlanRepository](../../../infrastructure/daylight-data/src/daylight_data/serving/repository.py)
   binds the 72-offering MA catalog and L02/L03/L09 inspection. It explicitly
   identifies PDP and Medigap as requiring separate query/identity scopes.
   Medigap insurer/form/edition/variant identities cannot be represented as a
   CMS contract/plan/segment ID.

4. **The generic API is preflight infrastructure.**
   [The API](../../../infrastructure/daylight-data/src/daylight_data/api/app.py)
   requires a permitted source state for internal research and always returns
   503 for `/v1/offerings/query`. Authentication supplies no source-use authority.
   [The released-offering view](../../../infrastructure/daylight-data/migrations/004_release_boundaries.sql)
   is deliberately empty. Setting an acceptance flag or removing `WHERE false`
   would not implement source/method/output verification.

5. **Raw monetary observations need their existing safeguards carried into serving.**
   The filed grids contain 22,052 replaced cells, 78 source-zero cells and 43,364
   cells with incomplete sourced rate periods; these categories can overlap.
   The existing [targeted research reader](../../../cms-slice/scripts/l10_targeted_reference.py)
   holds replaced, zero, unresolved-period and out-of-period amounts. The generic
   projection retains source context but does not implement that decision.
   Preserve schedule linkage, source labels and unknown current-sale state.

## Implementation order and concrete completion criteria

All names below describe proposed new contracts, not implemented endpoints or
tables. Use additive versioned serving structures beside the retained research
snapshot. The [persistent-local runbook](../../../infrastructure/daylight-data/runbooks/PERSISTENT_LOCAL.md)
prohibits rerunning the legacy importer/migrations against its compact read views.

| Order | Backend work | Completion evidence |
| --- | --- | --- |
| **B01: bind scope and inputs** | Create an immutable Collier plan-type serving manifest naming 2026, county `12021`, PDP region `11`, selected L04 build-r4/restriction-r3 and L10 r2/r3/r4/r5 parents. Bind exact source/adapter/schema/dependency hashes, observed/effective dates and source rights/STOPs. Keep “published reference”, “personal comparison” and “quote” as distinct capabilities. | Exact source closure resolves; no implicit latest file, wrong-year reuse or inherited acceptance. Scope report separates known plans, unresolved leads, fields prepared and purposes accepted. |
| **B02: complete missing imports** | Add source-preserving readers for the listed base sidecars in a new adapter/build revision. Reuse existing archive, ordinals, control accounting and restart/checkpoint machinery. Reconcile SQLite and JSON duplicates explicitly rather than treating every copy as a distinct product. | All declared sidecars/children/qualifications accounted for; source-to-projection checksums and before/after totals; original sources, seals and compact snapshot unchanged. Failed/partial runs cannot select a new serving release. |
| **B03: add typed serving models** | PDP: offering identity, field terms, county-region mapping, published restriction observations. Medigap: discovery lead distinct from confirmed product; insurer/NAIC, exact form/edition, letter/high-deductible variant, standard/SELECT and individual/group; dated availability assertions; rate schedule/cell, rating class, age/sex/tobacco/area, policy-issue cohort, fees/discounts/modal factors and conditions. Carry exact source references and uncertainty. | Collier PDP resolves to the same 10 unique IDs without duplicating plans per county. All relevant Medigap terms join through exact source identities; unknown joins remain explicit. Annual illustrations, annual filed cells and monthly tables retain distinct bases. Native precision/negative amounts/nulls survive. |
| **B04: implement authority and release selection** | Extend the existing `dl_review` foundation with verified source-use, qualified semantic/method review and exact-purpose output bindings. Import/replay actual authority from the existing reference controls; do not manufacture acceptance. Bind the restriction supplement separately. Restrict reviewer/publisher privileges, audit decisions/revocations and atomically select an immutable manifest. | Published output works only for a genuinely accepted exact capability in a fixture. Wrong source/hash/field/scope/year/purpose, missing review, expiry, revocation, STOP and stale method all hold. Consumer reader cannot reach research-only evidence through another route. |
| **B05: expose bounded backend tools** | Add separate PDP list/detail, Medigap standardized-benefit/discovery and published-rate-observation capabilities. A rate-observation request specifies exact identity/source date; a future personal rate engine is separate. Use server-side authentication, read-only roles, parameterized SQL, limits/timeouts, release-bound cursors and a verified connection factory. Return release/evidence IDs, scope, dates, qualifications, holds and completeness. | End-to-end research and fixture-approved queries work through the service. Missing county mappings return an explicit unsupported/unknown state, not an apparently complete empty market. Source observations cannot be labeled personal quotes. No browser token or arbitrary model-written SQL. |
| **B06: reconcile Medigap evidence for supported prices** | Complete exact insurer/form/edition/area/sale-state joins and the Collier product census; preserve leads that remain unsupported. Resolve Blue approved intervals/form equivalence and automatic-payment conditions; Humana/GPM modal precision, applicable discounts/fees/rounding/amendments; group and SELECT qualifications. Expand the existing source worklist for other companies. Use qualified R15 review for genuine interpretation. | A released published table has exact identity/date/basis and disclosed limits. A personal estimate additionally reproduces the applicable filed rating method and all consequential inputs/conditions. Missing evidence holds the conclusion. Full-market claims require a separately proven denominator. |
| **B07: maintain and deploy** | Version source refresh/diffs, reviewed release/rollback and affected-result invalidation. Preserve STOPs and keep routine acquisition disabled until authorized. Package the API independently of PDF acquisition/build tooling. Add query/hold/freshness metrics and non-sensitive receipts. Benchmark real tool queries and index only justified joins. Use D95 portable release bindings; verify roles/TLS/restore on the selected cloud target at cutover. | Changed evidence builds a new candidate without replacing the last good release; revoked/stale outputs stop. Clean fixture installation and bounded workload pass. Cloud account/region/budget decision remains separate; local implementation does not depend on it. |

B01–B03 and a research-only B05 can proceed while actual acceptance is pending.
B04 is necessary before consumer display. B06 contains remaining evidence and
rating work; it must not be described as a reviewer merely signing off completed
pricing. B07 starts with local packaging/observability and finishes target checks
when hosting is selected. These tasks reuse D95 A01–A04/A08/A11 instead of creating
another database or replacing the compact archive.

## Release capabilities in useful increments

| Capability | Required before enabling | What remains held |
| --- | --- | --- |
| Internal source research | Exact source binding and permitted research use; authenticated bounded tool; preserved holds | Consumer use, personal suitability, quote and enrollment |
| Published PDP reference for Collier | B01–B05, genuine narrow L04 source-use/field/population acceptance, explicit snapshot dates and separately reviewed restriction evidence if used | Live availability, a person's subsidy/drug cost and recommendation |
| Standardized Medigap benefits / source-observed discovery | Import the exact sidecars; scoped R15/source-use/output acceptance; unresolved sale/form/SELECT/group states explicit | Complete for-sale market and personal prices |
| Published Medigap rate observation | Exact rate/schedule/area/form/date/basis acceptance; replaced/zero/period safeguards; label as published amount or illustration as appropriate | Personal eligibility, underwriting, binding quote and unverified billing derivations |
| Personalized PDP costs/comparison | Separate accepted L05 formulary/PA/ST/QL, L06 cost methods, L07 pharmacy evidence and applicable rights/subsidy dependencies, plus confirmed necessary user facts | Unsupported checks and live enrollment claims |
| Personal Medigap estimate/quote | B06, exact accepted rating method and date, consequential personal inputs, L11 buying-rights/underwriting/SELECT dependencies where applicable; authorized quote rail if a binding quote is claimed | Any unsupported price, eligibility or fulfillment claim |

The existing [L10 r5 gap register](../../data/l10-medigap-2026-10-28/targeted-filings-r5/gaps.json)
still governs incomplete census/other-company evidence and rating interpretation.
The 29 other sampled companies and wider source queue are not resolved by the
seventeen supplied packets. A partial accepted reference must disclose its scope;
it cannot silently exclude unknown or uncompensated options. Commercial terms
stay outside inclusion, filtering, pricing evidence and comparison tools.

Personal output integration also needs the permissioned customer/decision plane
identified in [D95](../ai-native-database-readiness-2026-11-06/README.md).
Beneficiary facts and quote requests do not belong in this public-evidence DB.
No UI redesign is a prerequisite for these backend deliverables.

## Verification actually performed

- Live database read-only inspection: six bounded SELECTs, recorded with SQL,
  exact source hashes, counts and timings in [database.json](evidence/database.json).
  A preliminary read also confirmed source-set paths and zero release records.
  The sandbox initially denied the Unix socket; the read-only retry was approved.
- Local base-sidecar shape/hash and SQLite-table inspection: confirmed the
  omitted import inputs recorded in [base-sidecars.json](evidence/base-sidecars.json).
- Existing L04 suite: **15 tests passed** in 14.072 seconds.
  Command: `infrastructure/daylight-data/.venv/bin/python -m unittest discover -s cms-slice/tests -p test_l04_reference.py -v`.
- Existing L10 suite attempt: **14 filing-boundary tests passed; three test modules
  failed to import because this virtualenv lacks `pdfplumber`** (`test_l10_gaps`,
  `test_l10_reference`, `test_l10_targeted`). Command:
  `infrastructure/daylight-data/.venv/bin/python -m unittest discover -s cms-slice/tests -p 'test_l10*.py' -v`.
  This is incomplete validation, not a passing L10 suite. No dependency installation
  or change to a frozen parser/runtime was made for this review.
- The first inspection helper was named `inspect.py`, shadowing Python's standard
  module and failing before DB access. Renamed to
  [inspect_plan_data.py](evidence/inspect_plan_data.py); its six-query run passed.

No full source re-extraction, full database verifier, load test, cloud deployment,
paid/live model probe, consumer acceptance or personal quoting was performed.
Only this new review/evidence directory was authored. Source data, running services,
protected variants, guest stores, the 41 meanings and existing authority remain
unchanged. No new owner decision is inferred from this review request.
