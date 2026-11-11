# Collier critical benefit review across all 72 plans

November 4, 2026 · D91, D64 and D73 · 2026 Collier Medicare Advantage research

The [versioned benefit addendum](critical-benefits.json) prepares **20 medical service records per plan across all 72 retained offerings**, plus Part B reduction and Part D deductible reviews. It binds the [r9 gap matrix](../recommendation-scope-2026-11-04-r9/GAP_MATRIX.md) and the exact r5 catalog. Each service includes the source terms, flags, exact PBP record, retained carrier page locators and the checks needed when the service matters to a person. The local research API returns the addendum with each exact-plan lookup as `critical_benefits`, with a separate byte hash. Its consumer purpose remains held.

## Benefit preparation and review

The new medical records distinguish emergency and urgent visits, outpatient hospital, observation, ambulatory surgery, diagnostic tests, labs, diagnostic and therapeutic radiology, X-rays, ground and air ambulance, skilled nursing, home health, occupational therapy, physical/speech therapy, DME, prosthetics, medical supplies and diabetes monitoring supplies. They retain available Plan Finder network rows and bind each record to its exact Medicare PBP service. Observation, ambulatory surgery, therapeutic radiology, air ambulance, home health and medical supplies use PBP and carrier context because the selected Plan Finder file has no separately named row for them.

| Result of the source screen | Plan and service records | Disposition |
| --- | ---: | --- |
| Plan Finder and PBP default charge shape and values agree | 720 | Use as research candidates with native conditions attached. Rate basis, coverage and carrier applicability have separate review requirements. |
| Charge shape or value differs | 76 | Preserve both values. All 76 occur on 10 dual-eligible plans. Review protected versus nominal cost sharing, setting and service basis. A flat zero and zero daily bands may also differ in shape while preserving different period information. |
| Source expression preserved for targeted review | 161 | Retain alternatives and unresolved charge structures. Keep scope, conditions and source amounts together. |
| Diabetes supplies subtype scope needs review | 51 | The Plan Finder label can be broader than PBP monitoring supplies. Verify exact item, channel and charge basis before treating those terms as equivalent. |
| PBP and carrier context | 432 | 405 have a typed default PBP expression. The other 27 retain the native components without selecting a single expression. All 432 retain carrier page locators. |
| **Total** | **1,440** | No personal amounts or new consumer approvals. |

The screen compares exact charge shapes, values and day bands where the retained sources permit a narrow comparison. It preserves ranges, multiple charge types and source flags. It does not compute cost from a range or apply a coinsurance percentage without the allowed charge. In-network comparison is separate from retained out-of-network and POS source observations. Carrier service locators can span several settings, so the presence of a page or matching number cannot settle a child service. The addendum carries 85 prior named carrier checks and 16 exact r4 reference entry IDs within their existing scope. It also carries **33 service records with existing source hold IDs**, including some whose new charge expressions align. Source-approval, clinical and eligibility rules continue to apply to those records.

## Premium and deductible gaps

| Field | Review outcome | Remaining check |
| --- | --- | --- |
| Part B reduction | PBP Section D explicitly reports no MA rebate for Part B on 42 plans. On 29, the PBP amount matches the earlier carrier candidate. For Aetna H5521-306-000, the newly reviewed EOC confirms the PBP **$120/month** amount. This supplies evidence for all 43 prior gaps. | Check the applicable publication and source permission before consumer use. For actual billing, confirm Part B payment and credit eligibility and timing. Keep the reduction separate from the plan premium. |
| Part D deductible | The no-subsidy initial-coverage 30-day schedule supplies flags for all five prior tier gaps. H0710-010-000, H1032-243-000 and R5826-074-000 flag tiers 1–5. H1889-026-000 and H2509-003-000 flag tiers 2–5. Of the other offerings, 46 match retained carrier tiers, 10 have a published zero deductible and 11 have no included Part D. | The five schedules are evidence for targeted carrier scope and amendment review. Verify exact drug/tier, exemptions, remaining deductible and applicable assistance for a fill. |
| Plan premium | Three existing discrepancies remain held. H1032-241-000, H1032-243-000 and H1889-026-000 each have a retained $4.80 gross Landscape figure and a $0 carrier summary figure. | Establish the exact gross versus subsidized basis and current revision before a combined figure. Check the person's assistance and billing separately. |
| Medical deductible and maximum | Three medical deductible and two medical maximum fields remain held at their existing basis. Existing scenario holds stay visible by exact offering. | Resolve applicable assistance and service/network scope, including selective deductibles. The unresolved fields continue to hold dependent scenarios. |

## Targeted carrier readings

- **Humana H1036-217-000 emergency and skilled nursing.** The emergency chart at PDF pages 52–53 separates the $150 domestic visit charge from worldwide terms and describes an admission waiver within 24 hours for the same condition. The SNF source schedule is $0/day for days 1–20 and $160/day for days 21–100 in both CMS sources. The carrier chart at PDF page 72 adds the benefit-period condition, including the 60-day reset. A stay estimate needs eligible days and the current benefit period.
- **Humana H1036-217-000 home health.** EOC PDF page 54 pairs the home health copay with physician certification and homebound status. It separately lists equipment terms, so the home health zero cannot price the equipment. The broader batch has 69 explicit zero PBP copayment observations. H5410-047-000, H5410-055-000 and H5410-060-000 have no single home health charge selected from the available components.
- **Wellcare H1032-198-000 urgent care.** EOC PDF pages 95–96 distinguish the $25 domestic urgent visit and its admission condition from the separate worldwide urgent charge. The $25 Plan Finder amount and PBP base expression align. The source contexts stay separate.
- **Wellcare H1032-241-000 emergency.** EOC PDF pages 64–65 describe a $0 Medicare-covered emergency cost share and a separate $115 worldwide emergency charge. The Plan Finder domestic row shows $0 while the PBP charge screen sees $115. The two sources cannot be flattened to a single visit amount. UHC H1889-026-000's chart at PDF pages 94–96 separately describes conditions on zero Medicare-covered cost sharing for QMB or full Medicaid and provider acceptance. The review retains unresolved basis for every affected service.
- **Freedom H5427-087-000 skilled nursing.** EOC PDF page 94 presents a $0 copay per stay. Plan Finder has a flat zero and PBP has a zero day band for days 1–100. The zero token agrees, but the period and covered days still matter.
- **Erickson H5652-002-000 observation.** The $375 observation source term has a distinct setting and is subject to the published selective $1,000 in-network annual deductible. The plan's observation chart is at PDF page 84, with deductible scope at pages 39–40. The candidate cannot supply a personal subtotal without a deductible balance and applicable exceptions. [Exact deductible source packet](../../data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/Liberty-no-Rx-deductible-conditions.json)
- **Aetna H5521-306-000 Part B reduction.** SB PDF page 3 and EOC PDF pages 6–7 agree with the exact PBP $120 amount. The EOC distinguishes monthly from quarterly credit timing. The source locator in the addendum binds page 7 and its text hash.

## Before these records support recommendations

**Source and method approval.** An independent reviewer still needs to approve the exact published fields, carrier and CMS scope, calculation methods, material differences, amendments, source permissions and intended use. Start with the 76 charge differences, then any material ambiguous service, deductible, limit or existing hold for the case. The full archive reconciliation remains a separate track. Keep the original 535-entry r4 reference, the two-plan pilot and the 392,570-obligation research inventory intact.

**Personal checks.** Confirm the intended year and date, residence/service area, enrollment window, current coverage and applicable SNP or assistance status. For an important service, bind the treatment or item, setting, exact provider/site/supplier, deductible balance, applicable limits and any required referral or authorization. For medicines, check exact product/tier/restrictions, outlet and channel, fill, assistance and phase. For travel or supplemental needs, check the actual destination and service or exact base benefit/rider, with frequency and allowance terms. The addendum carries supplemental source pointers and flags the conditional work. The expanded medical review covers the baseline service families. Exact travel and supplemental terms remain on demand, with unresolved material facts holding the affected conclusion.

**Decision and release.** Connect those verified findings to the confirmed profile and the relevant alternative coverage paths. Use an accepted decision method with neutral inclusion, reasons, correction invalidation and current source authority. Observe the complete consumer journey through a concrete next action. [Full gap matrix and product gates](../recommendation-scope-2026-11-04-r9/GAP_MATRIX.md) · [Release target](../recommendation-scope-2026-11-04-r6/CONSUMER_JOURNEY.md)

## Reproduction

From the repository root, run `python3 -B docs/product/recommendation-scope-2026-11-04-r10/build_benefits.py --check`. Input hashes and record locators are embedded in the addendum. Use the [existing local research request](../recommendation-scope-2026-11-04-r9/GAP_MATRIX.md#use-the-tool) with an exact `offering_id` to retrieve the updated research payload.

## Actual time and verification

| Checkpoint on November 4, ET | Clock time | Elapsed from start |
| --- | ---: | ---: |
| Work started | 4:41:04 p.m. | 0:00 |
| Exact medical service sources and representative layouts identified | 4:42:23 p.m. | 1:19 |
| All-plan medical charge screening and difference grouping complete | 4:46:06 p.m. | 5:02 |
| Premium and drug deductible pass, artifact pinning and isolated HTTP verification complete | 4:50:33 p.m. | 9:29 |
| Live HTTP, catalog/matrix replays and final scope checks verified | 4:52:03 p.m. | **10:59** |

The live local advisor returned all 72 original plan payloads, 1,352 original plan-to-source references and 1,440 new service records. The listing and all detail reads took **4.195 seconds** on loopback. The isolated check took 3.983 seconds. Twenty research HTTP regression tests passed. The replay preserved prior plan states, source holds and the original pilot amounts. Explicit tests refused ambiguous compound charges and discontinuous day bands. Both synthetic HTTP sessions were deleted after verification. Timings cover producer review and the internal research release.
