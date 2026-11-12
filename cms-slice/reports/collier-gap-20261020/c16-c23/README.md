# C16–C23 work and source gates — October 20, 2026

**Completed: C16 collector core, C19 dictionary/matrix and C21 display-both premium treatment.** C17/C18/C20/C22 remain blocked by an actual Medicare.gov HTTP 403. C23 has a substantial partial research dataset; the requested OIR records, underlying filing tables and independent insurer rate replays are still pending. This is not completion of the full eight-item batch or R1.

| Item | Result | Evidence |
| --- | --- | --- |
| C16 | Guarded headless browser transport, zero-network dry-run, persistent kill switch, identified requests, shared pacing/cap/cache, robots/path checks and receipts implemented. Task-specific current-source adapters are not admitted. | [Collector guide](../../../../docs/MEDICARE_COLLECTOR.md), [origin failure run](c16-browser-preflight-9/run.json), [active STOP](c16-active-stop.json), [guardrail verification](c16-guardrail-verification.json) |
| C17 | 70 IDs × four Collier ZIP inputs prepared (280 target cells). No new live plan facts captured. Historical observations retain their original date/scope. | [Coverage ledger](c17-coverage.json), [dry-run](c17-dry-run.json) |
| C18 | Current bidirectional market reconciliation not run. Historical 34102 diagnostic matches 43 observed non-SNP IDs; the other 27 are SNPs excluded by that old scenario, not evidence of market absence. Other ZIP/current comparisons remain unknown. | [Reconciliation state](c18-market-reconciliation.json) |
| C19 | 24-field dictionary and 1,680 explicitly classified cells for all 70 records. Coded benefits remain uninterpreted; no inferred zero, eligibility or benefit ranking. This does not close DQ-005/006. | [Dictionary](c19-field-dictionary.json), [matrix JSON](c19-core-benefit-matrix.json), [matrix overview](c19-matrix-overview.md) |
| C20 | Ten synthetic drug scenarios × 61 plans × retail/mail = 1,220 logical comparisons prepared. No price estimate captured or invented; exact products, quantity units and pharmacy identities still require confirmation. | [Coverage state](c20-drug-scenario-coverage.json), [dry-run](c20-dry-run.json) |
| C21 | Both affected plans expose the $7.30 published Part D total, $7.30 listed CMS-paid subsidy, $0 low-income beneficiary field and $0 monthly PUF PREMIUM, with separate labels and source links. PUF basis remains unresolved; conflict still blocks premium ordering. | [Display decision/records](c21-premium-basis-display.json) |
| C22 | Four ZIPs × 12 letter/high-deductible families prepared; SELECT variants must be enumerated from actual results. No new Medicare.gov insurer/product universe captured. | [Coverage state](c22-medigap-coverage.json), [dry-run](c22-dry-run.json) |
| C23 | 3,876 illustrative annual CHOICES rate rows, 34 insurers, 17 synthetic 34102 scenarios. IRFS verifies one insurer's NAIC and a related filing's metadata. OIR acknowledgment assigns case 26-045612; actual responsive records are pending. | [Dataset](c23-florida-medigap.json), [source index](choices-source-index.json), [IRFS review](c23-irfs-review.json), [OIR acknowledgment](c23-oir-acknowledgment.json) |

## Source stop and scope

The entry app identifies version 2.94.0. Preflight reviewed exact first-party static dependencies and ordinary anonymous security initialization, without constructing signatures, solving challenges, logging into an account or changing IPs. Local manifest stops were individually reviewed and retained. The early empty-shell capture was rejected by a documented readiness correction; it is not a successful observation.

At **2026-10-20 14:45:02 UTC**, `https://www.medicare.gov/api/v1/data/plan-compare/ldflags` returned HTTP 403. That response is preserved by hash. The final STOP has not been cleared, and no Medicare.gov request was sent after the denial. No alternate browser/transport/proxy retry, CAPTCHA solving, real beneficiary data or scenario query occurred. The final protected bootstrap failure is distinct from the earlier local path-review stops.

Live batches are restricted to 00:00–06:00 Eastern and need a current policy review. Dry-runs remain available with STOP active. Resumption needs a documented source-access resolution and review of current policies, paths and actual task schemas. The official C11 access inquiry still awaits a reply; C12 legal approval remains complete. C01 and all hold items remain as previously directed.

## Benefit and premium interpretation

The matrix retains selected historical Medicare.gov/carrier corroboration with its actual dates and scope. Every additional coded benefit has an explicit pending-document-review state and a PBP candidate-section pointer. A candidate section is navigation evidence, not a decoded benefit. Full 2027 SB/EOC interpretation, hospital/provider checks and domain sign-off remain open. No new current-source corroboration is fabricated.

C21 completes the plan's permitted **display both with their basis** alternative for H1889-026-000-2027 and H5594-017-000-2027. Equality between PUF PREMIUM and the low-income beneficiary amount does not prove a subsidy-adjusted PUF basis. Both SNPs retain restricted, unconfirmed eligibility. DQ-003/004 remain recorded as source discrepancies with display mitigation.

## Medigap dataset limits

The public CHOICES page labels its table **Annual Premiums** and its purpose as comparison shopping. Every normalized amount is `illustrative_public_comparison`, `USD/year`; no monthly quote or acceptance is calculated. The 01/01/2027 date is the **requested search filter**. Returned rows omit actual rate-effective dates, so no 2027 filed-rate applicability is asserted.

The grid covers ages 65, 70, 75 and 80, female/male, with/without tobacco, plus one public 0–64 female/non-smoker cohort case. Standard/SELECT and individual/group results are preserved separately, as are high-deductible variants, raw fee codes and GI indicators. The form has no household-discount or personal guaranteed-issue entitlement control. No such cases are invented. This is a narrow Collier research grid, not the held full stratified grid (H08).

IRFS filing **26-018953** is an approved 2026 rate filing for AMERICAN BENEFIT LIFE INSURANCE COMPANY, NAIC **66001**. Its metadata does not independently reproduce any CHOICES amount, establish a form-level join or confirm 2027 sale/effective dates. The other 33 insurers' NAIC mappings and all underlying rate-table joins remain open. The public IRFS document-request flow asks for email and a challenge; neither was submitted. No new messages, fees, purchases or contracts were authorized or sent.

OIR's acknowledgment, received October 20 at 14:34:46 UTC, assigns **26-045612** and says the records request is processing. The message supplies no rate dataset. It is recorded separately from the original C09 send receipt; no original evidence was rewritten. DQ-011 remains open, as do C22/C24 product reconciliation and second-source rate validation.

## Verification and rebuild

The final application suite passes **191 tests**. Separate collector and evidence checks cover failure paths, cache/kill/rate behavior, premium-source preservation and annual-rate units/unknowns. [Verification](verification.json), [immutable file manifest](manifest.json), [selected testing release](selection-receipt.json) and [isolated bundle replay](extracted-bundle-verification.json) record the final checks. The prior release and original earliest source-review deadline are retained; this is an owner-testing candidate, not R1 sign-off.

From the repository root:

```sh
python3 cms-slice/scripts/core_benefits.py
python3 cms-slice/reports/collier-gap-20261020/c16-c23/build_coverage.py
python3 cms-slice/reports/collier-gap-20261020/c16-c23/rebuild_choices_dataset.py
python3 cms-slice/reports/collier-gap-20261020/c16-c23/verify_evidence.py
```

The coverage builder preserves historical observations and unexecuted targets; its current source-stop status must be retained. The CHOICES capture script makes network requests and is not part of the offline rebuild. No collector run should be attempted while STOP remains active.
