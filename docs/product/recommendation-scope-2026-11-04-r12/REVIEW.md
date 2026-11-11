# 2026 Collier published costs and benefits review

**Offline display candidate. Independent review and consumer publication approval are pending.**

[Read the 72-plan cost and benefit tables](CATALOG.md) · [Inspect the per-plan evidence and holds](display-candidate.json) · [Read the plan names, types and restrictions](../recommendation-scope-2026-11-04-r11/CATALOG.md)

The proposal keeps all 72 exact individual Medicare Advantage offerings listed for Collier County in the September 2, 2026 CMS Landscape. It adds ten selected published cost and benefit fields, in exact offering-ID order. Scope and restrictions carry over from the r11 listing candidate. Actual enrollment, current availability, personal costs, plan recommendations and the separate fictional cost scenarios sit outside this purpose. [CMS Landscape index](https://www.cms.gov/medicare/coverage/prescription-drug-coverage) · [Medicare’s explanation of plan costs](https://www.medicare.gov/health-drug-plans/health-plans/costs)

## 720 plan and field cells

| Selected field | Display candidates | Held | Does not apply |
| --- | ---: | ---: | ---: |
| Monthly plan premium | 69 | 3 | 0 |
| Monthly Part B reduction | 72 | 0 | 0 |
| Annual medical deductible | 69 | 3 | 0 |
| Annual medical out-of-pocket limits | 70 | 2 | 0 |
| Annual Part D deductible | 56 | 5 | 11 |
| In-network primary care | 47 | 25 | 0 |
| In-network specialist | 47 | 25 | 0 |
| In-network inpatient hospital, first four covered days | 42 | 30 | 0 |
| Emergency visit | 48 | 24 | 0 |
| Urgent care visit | 48 | 24 | 0 |
| **Total** | **568** | **141** | **11** |

A held display cell has no value and retains one or more reason codes. The review evidence points to the original values and disagreements. Each of the 11 inapplicable cells reflects a plan without a Part D deductible in scope. An explicit published zero stays distinct from both dispositions.

## What was screened

- **Premiums and limits.** Use the published monthly premium from the checked r5 premium input, with Part D included once when applicable. Keep the premium and any Part B reduction separate. The Part B column incorporates r10's 42 explicit PBP no-reduction declarations and 30 corroborated reduction amounts. The limits preserve in-network, out-of-network and combined bases as published.
- **Deductibles.** Carry forward selective medical deductible scope. Show established Part D tiers and retain the five unresolved tier and exception scopes, even though r10 has candidate schedule flags for them. Retain the annual amount and schedule evidence for those cases only in the source review records.
- **Primary care and hospital.** Reuse the exact charge and charging-unit screens from r5. The output extracts rates from the checked inputs, without scenario subtotals. The 42 hospital entries include 39 daily charges over the first four covered days and three per-admission charges. Longer stays and separately billed charges have separate terms.
- **Specialist, emergency and urgent care.** Keep the specialist's published copay or range when it passes the retained named carrier amount screen and has no unresolved material variant. An amount falling inside a range does not establish when either endpoint applies. Emergency and urgent care require an exact selected MPF row, matching PBP charge shape and amounts, and no r10 material flag or historical hold. The display omits the generic source parenthetical about coverage and retains setting and waiver qualifications.

[r5 field and method record](../recommendation-scope-2026-11-04-r5/REPORT.md) · [r10 charge, rebate and deductible evidence](../recommendation-scope-2026-11-04-r10/REVIEW.md)

## Review the exceptions first

| Affected cells | Review or verification required |
| --- | --- |
| 3 premium holds | H1032-241-000, H1032-243-000 and H1889-026-000 have a $4.80 gross CMS observation and a $0 carrier observation. Resolve gross versus subsidized basis and applicable revision before displaying an amount. |
| 3 medical deductible and 2 limit holds | Deductibles are held for H1045-039-000, H1889-002-002 and R0759-003-000. Limits are held for H1889-026-000 and H2509-003-000. Check the service or network scope and applicable assistance basis. |
| 5 Part D deductible holds | H0710-010-000, H1032-243-000, H1889-026-000, H2509-003-000 and R5826-074-000. Confirm tier and exception scope with the applicable carrier evidence and amendments. Drug tier, supply, pharmacy, assistance and deductible balance remain personal checks. |
| 130 care holds | 100 care cells across 20 D-SNPs hold nominal versus Medicaid-protected terms. Another 20 cells across four offerings hold condition-specific variants. The other 10 cells hold unclear charge or deductible bases. The reason codes also retain 12 emergency/urgent MPF–PBP differences within the 130 holds. |
| Erickson H5652-002-000 | The published $1,000 deductible is selective and applies to inpatient care. The primary care rate carries the ordinary in-network office-visit scope. Inpatient remains held while the remaining deductible and applicable charge basis are unresolved. |

## Acceptance before display

1. **Scope and source use.** Close the r11 listing and restriction decisions. Record allowed consumer redisplay for the selected CMS Landscape, Plan Finder benefit-summary workbook, PBP and retained carrier-derived facts. Use the applicable source versions and permissions. Prior research acquisition, a carrier locator and prior L03 r4 acceptance each have a narrower scope. Existing source access stops still apply.
2. **Exact independent review.** A qualified reviewer independent of sales checks the family rules, displayed terms, source bases, material exceptions, applicable amendments and refresh/expiry limits. Review the held-field wording and the separation between published terms and what a person would pay. Record the reviewer, decision, date, expiry, exact scope and evidence against the candidate hash. The accountable Daylight owner approves the exact display use.
3. **Serving review when integration is authorized.** Bind the approved projection to the actual Daylight serving code. Verify that held fields expose no number, stale or unapproved data stays held, and the coverage year and per-field qualifications are visible. The review sources stay internal. The packet does not establish the acceptance for comparisons based on personal circumstances.

The next useful step for a user considering an offering is to confirm eligibility and current availability, then check the exact doctor, location and medicines with permitted current sources before acting. The D91 display serves browsing and source inspection. Exact-ID ordering, uniform field coverage and visible holds support D64 and D73. [Product display gate](../recommendation-scope-2026-11-04-r1/PLAN.md#3-evidence-depth-and-output-boundaries) · [r11 listing gates](../recommendation-scope-2026-11-04-r11/REVIEW.md#decisions-required-before-daylight-can-display-it)

## Reproduction

Candidate SHA-256 is `62ae73885700fb67d3f171d6807aaf6101f27801ab48246191cda34ab022e32f`.

From the repository root, run `python3 -B docs/product/recommendation-scope-2026-11-04-r12/build_display.py --check`. The candidate binds the exact r5, r10 and r11 inputs and produces the JSON and readable tables from the same projection.

## Actual time and verification

Offline preparation and verification took **5 minutes 45 seconds**, from 4:13:35 to 4:19:20 p.m. ET on November 4, 2026. This covers the field selection, checks, readable and structured packets, and review record. Independent review, source-use approval and serving review are pending.

The r5, r10, r11 and r12 replays passed. The final check resolved each r5 and r10 reference in the candidate and checked all 720 field dispositions, the removal of held amounts, the premium disputes, selective deductible, per-day versus per-admission rates, Part B reduction and Part D inapplicability examples.
