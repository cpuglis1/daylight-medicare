# 2026 Collier plan listing review

**Prepared for independent review. Consumer publication is held.**

[Read all 72 proposed rows](CATALOG.md) · [Inspect row-by-row evidence](display-candidate.json) · [Replay the source checks](build_inventory.py)

The proposed scope is individual Medicare Advantage offerings published for Collier County, Florida (FIPS 12021), in the September 2, 2026 CMS Landscape. Each row displays the exact offering ID (year, contract, plan and segment), CMS plan name and type, and the restriction labels supported by the sources below. The display is ordered by exact offering ID. [CMS Landscape release index](https://www.cms.gov/medicare/coverage/prescription-drug-coverage)

> **2026 Collier County Medicare Advantage plans**  
> These plans appear in the September 2, 2026 CMS Landscape. Check current availability, enrollment status and whether you qualify before relying on a listing.

## Preparation and evidence

| Review item | Result |
| --- | --- |
| Scope and identity | 72 exact offering IDs across 19 contracts. All 72 IDs, names and plan types match the existing r5 catalog and exact Collier Landscape rows. All 72 names and IDs also match exact 2026 CMS PBP records. |
| Special Needs Plan restrictions | 20 Dual Eligible SNPs, eight Chronic Condition SNPs and one facility-based Institutional SNP. The proposed chronic condition labels use the categories published for each exact offering. D-SNP integration and cost-sharing fields are retained as review evidence. Exact individual Medicaid, medical and institutional qualification remains unverified. |
| Erickson residence | Five exact 2026 carrier Evidence of Coverage documents state the residence requirement and identify Collier in the service-area text. The packet pins each document and page. H5652-004 carries both chronic condition and residence labels. |
| Geography discrepancy | All five Erickson PBP geographic labels omit Florida. The proposed county listing relies on the exact Landscape county rows, with carrier wording supporting the residence restriction. Preserve the disagreement for review. Neither observation establishes availability at an address or access to an Erickson community. |
| Other held evidence | Eleven Landscape/PBP differences in Part D indicator wording are retained without a separate drug-coverage claim. The 115 contract-level county observations cannot add plans or segments. The expected full-market denominator is unknown and current address-level availability has been verified for zero plans. |

The snapshot excludes stand-alone drug plans and other coverage outside individual Medicare Advantage. The source README documents omissions including employer offerings with plan IDs of 800 or more, Part B-only plans, PACE and Medicare-Medicaid demonstration plans. The restriction column is limited to the published SNP categories, facility-based classification and exact Erickson residence wording identified in this review. [Frozen L02 county packet](../../data/l02-ma-availability-2026-10-25/build-r5/12021/review-packet.md) · [Carrier evidence matrix](../../data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/plan-document-matrix.json) · [Existing r5 catalog](../recommendation-scope-2026-11-04-r5/REPORT.md)

The five carrier evidence locations are PDF page 7 for H5652-002-000 and PDF page 9 for H5652-001-000, H5652-004-000, H5652-006-000 and H5652-008-000. Look for the special eligibility requirements and Section 2.2 on service area. The packet binds each PDF and its extracted text to the exact plan.

## Decisions required before Daylight can display it

| Gate | Required decision |
| --- | --- |
| G01 · Scope and denominator (R06) | Confirm the 72 rows and the disclosed population and coverage year as a dated CMS snapshot. The verified count of published observations is separate from an accepted count of all options in the market. |
| G02 · Source use (R07) | Record permission for this exact CMS-derived display and the five carrier-derived residence paraphrases. The CMS site policy is evidence for the review. Carrier bytes were retained for research and need their own use decision. Existing Plan Finder, UHC and Wellcare access restrictions still apply. |
| G03 · Correctness and freshness (R06/R08) | Review the restriction wording, the five Erickson geography discrepancies, the source date and the qualification/status limits. Record the accepted display dates, expiry, refresh triggers and affected-row dispositions for later changes. |
| G04 · Independent acceptance | A named qualified Medicare/domain reviewer independent of sales signs off on the exact evidence, date, field projection, purpose and applicable gates. The accountable Daylight owner records the approved consumer use. Record decisions against the candidate SHA-256 and the exact source/build bindings. |
| G05 · Serving acceptance | After separate authorization for integration, review the exact Daylight serving path and approve the binding between code, data and claim. Exercise year, scope, expiry and absent or revoked approval handling. Only the four approved fields per row are candidates for serving. The review evidence is internal. |

[L02 release gate definitions](../../data/l02-ma-availability-2026-10-25/PLAN.md#review-packet-and-release-gates) · [Current acceptance registry](../../data/l02-ma-availability-2026-10-25/acceptance-receipts.json) · [CMS site reuse policy](https://www.cms.gov/about-cms/web-policies-important-links/about-website/link-to-us)

The candidate is pending and carries no release ID. The existing L02 service returned 72 records for research and held the consumer inventory query because the exact receipt is absent. If the approved snapshot purpose requires a different population binding from the current service, review that binding before serving. Recommendations, personal checks, benefit details and cost scenarios have their own release scopes.

Candidate SHA-256: `7a5f572334d0c47a019e2ce397cf26e16f3ecd7a8114fd28604e501eaabda382`

Run `python3 -B docs/product/recommendation-scope-2026-11-04-r11/build_inventory.py --check` from the repository root to reproduce the proposed rows and source bindings.

## Timing and verification

Preparation and verification took **6 minutes 49 seconds** on November 4, 2026, from 4:01:56 to 4:08:45 p.m. ET. That time covers the offline packet and data checks. Independent review, source-use approval and serving review are pending.

The replay reproduced both candidate artifacts byte for byte. The direct service check confirmed 72 research rows and the expected consumer hold. Of the 26 existing L02 tests, 25 passed and the loopback HTTP test could not bind a local socket in the sandbox.
