# 2026 Collier cost example review

**Offline candidate for the exact 72 retained plans. Consumer approval is pending.**

[See all 72 plans and their cost examples](COST_EXAMPLES.md) · [Inspect the combined catalog and evidence references](display-candidate.json)

This revision adds the four existing r5 fictional examples to the r12 catalog. It preserves every plan identity, restriction, published value and held field in r12. Each example requires both a supported r5 calculation and available r12 input fields. No r5 amount or disposition changed. [r5 scenario methods and source review](../recommendation-scope-2026-11-04-r5/REPORT.md) · [r12 published field decisions](../recommendation-scope-2026-11-04-r12/REVIEW.md)

| Example | Numeric candidates | Held |
| --- | ---: | ---: |
| 12 months of plan premiums | 69 | 3 |
| Four ordinary covered in-network primary care office visits | 47 | 25 |
| One covered in-network acute admission, three counted days | 42 | 30 |
| Same admission, four counted days | 42 | 30 |
| **Total** | **200** | **88** |

41 plans have numbers for all four examples. Three plans have all four examples held and stay visible in the catalog. The examples are separate cost components for a fictional case, with no combined annual spending figure. The premium uses 12 months of the plan’s monthly charge, including plan Part D once where applicable, with Part B and any reduction separate. The office example uses four ordinary covered visits. The admission assumes required referral and authorization, sufficient room under the in-network medical limit, and no assistance adjustment. The admission starts at day one and excludes discharge day, transfers, readmissions, later bands and separately billed professional services.

## What stays held

- The annual premium examples for H1032-241-000, H1032-243-000 and H1889-026-000 have no amount. The retained sources disagree on premium basis.
- The primary care and hospital examples for all 20 D-SNPs remain held because the nominal or Medicaid-protected cost basis is unresolved. Other holds cover condition-specific variants, unclear visit terms, uncorroborated hospital charging units, or unresolved deductible and limit conditions. Each held example contains its exact reason codes and a reference to the review evidence.
- Both Erickson H5652-002-000 hospital examples remain held. Its selective $1,000 deductible applies to inpatient care, and the remaining deductible and charges that could meet it are unspecified. The ordinary primary care example remains available under its stated scope.
- For the supported hospital examples, 39 plans charge by day and three charge once per admission. For example, Humana H1036-217-000 changes from $540 to $720 when the fourth covered day is added. UHC H0710-010-000 stays at $2,200 across both variants because its selected charge is per admission.

## Approval before consumer display

1. **Published facts and source use.** Accept the exact dated 2026 Collier listing, restrictions and r12 benefit projection for the proposed consumer purpose. Record permission for the selected CMS Landscape, Plan Finder benefit summary, PBP and retained carrier-derived evidence as applicable. Confirm effective versions, material amendments and refresh/expiry policy. The r11 and r12 source-use decisions are still pending, and prior acceptance for other purposes does not transfer. [r11 listing approvals](../recommendation-scope-2026-11-04-r11/REVIEW.md#decisions-required-before-daylight-can-display-it) · [r12 benefit approvals](../recommendation-scope-2026-11-04-r12/REVIEW.md#acceptance-before-display)
2. **Independent approval of the examples.** A qualified Medicare reviewer independent of sales approves the exact examples, assumptions, math and limitations. Focus the review on the 12-month premium basis and Part B separation, ordinary office visit scope, hospital day counting and single admission charges, and deductible, spending limit and assistance rules. Sign the exact projection and methods, including the decision to display unresolved cells as held. A held amount needs its own resolution and approval if it is later proposed for display.
3. **Daylight approval and serving review.** The accountable owner approves the exact consumer education purpose. When integration is authorized, verify that the serving path is bound to the approved scope, shows the assumptions and hold states, and blocks stale or unapproved amounts. The proposed purpose covers fictional examples and published facts. Personal eligibility, doctor/site participation, drug coverage or prices and plan fit remain separate checks.

The catalog keeps exact offering-ID order and the original fictional case. It uses no consumer records, commercial inputs or plan ranking. The structured packet pins the earlier method and evidence versions. Candidate SHA-256 is `ba625a2968a53a46dc72dddf52a4e74064b56b0b14e55c9e8768d2b580fa3609`.

Replay the examples from the repository root with `python3 -B docs/product/recommendation-scope-2026-11-04-r13/build_examples.py --check`.

Offline preparation and verification took **2 minutes 37 seconds**, from 4:26:36 to 4:29:13 p.m. ET on November 4, 2026. The r5, r12 and r13 replays passed. The final check confirmed all 720 published field dispositions and 288 example dispositions, recalculated all 200 numeric examples, resolved the scenario source references, and verified that a held input suppresses the dependent amount. The elapsed time covers the offline packet and these checks. The approvals above are pending.
