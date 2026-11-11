# All 72 Collier offerings and the recommendation gap matrix

November 4, 2026 · D91, D64 and D73 · 2026 Collier Medicare Advantage research

The advisor's local research endpoint retrieves the exact 72-offering r5 catalog. The [per-offering matrix](offering-gaps.json) accounts for **72 × 14 = 1,008 offering and family pairs**. It records the existing field states, exact scenario holds, raw source row locators and conditional gaps. This is the product plan's denominator for this audit. Coverage depth and consumer acceptance are separate measures. [Full product data plan](../recommendation-scope-2026-11-04-r1/PLAN.md#5-the-product-data-package) · [Catalog and replay](../recommendation-scope-2026-11-04-r5/REPORT.md)

The catalog contains 506 candidate, 59 held and 11 inapplicable published field cells. It also has 200 numeric research scenarios and 88 held scenarios. Monthly plan premium is carried separately from the eight published fields. All 72 plans have internal lookup coverage. The catalog grants zero new consumer acceptances. Earlier L01 and L03 r4 published references keep their exact accepted purposes. The 392,570 historical source obligations remain the separate archival research denominator.

## What each family needs before it can support a decision

| Family | What exists | Remaining work and when it matters |
| --- | --- | --- |
| 1. Offering identity and scope | 72 exact 2026 contract, plan and segment IDs, classified as 32 MA-PD non-SNP, 11 MA-only and 29 SNP. L02 records extent and enrollment status separately. | Review date-specific enrollment status, exact service area, county/ZIP ambiguity and plan restrictions. Check SNP, residence or assistance qualifications only where relevant. Record accepted market scope, missing/unsupported options and a neutral selection basis. This is baseline for an availability or choice claim. |
| 2. Premiums and deductibles | 69 exact premium scenarios and three conflicts. Medical deductible has 69 candidates and three holds. Part D has 56 candidates, five holds and 11 inapplicable. Part B reduction has 29 candidates and 43 holds. Accepted federal reference available separately. | Review the three premium discrepancies, deductible tier/service exceptions, applicable amendments and distinct Part B credits. Join extra rider premium, federal premium and applicable assistance only when relevant. Keep bills and costs under actual enrollment conditional. Never offset plan premium by the Part B credit. |
| 3. Spending limits | 70 candidate and two held medical maximum fields, with network scope retained. Federal and drug references are separate. | Review combined and in-network buckets, excluded services and what costs count. Bind any applicable annual drug limit and phase separately. Confirm which limits affect a personal cost inference. Core financial exposure is a baseline check. |
| 4. Office and hospital | Each published PCP, specialist and inpatient field has 70 candidates and two holds. Four-visit PCP example is numeric for 47. Both inpatient lengths are numeric for 42. | Review differences among ordinary office, preventive and telehealth services, referral/authorization, deductible and charging/reset basis. Resolve only material plan-specific holds, including the known nominal-versus-protected variants. Keep admission versus day charging and separate bills explicit. |
| 5. Other core medical costs | Retained MPF rows for emergency, urgent, outpatient hospital, diagnostics/labs/imaging and ground ambulance for all 72. | Project the named services into common fields with network, service/setting, deductible and authorization qualifiers. Check outpatient surgery/facility versus professional charges and ground versus air where relevant. Review claims and conflict edges before serving supported terms. Screen for material exposure in baseline comparison. |
| 6. Extended care and equipment | All 72 have MPF SNF, rehabilitation and equipment/supply rows. Main SB/EOC documents cover all 72. Home health has no separately named MPF row in this extract. | Pull home health terms from applicable carrier or PBP evidence. Bind SNF day bands, stay/reset and admission conditions, rehab visits, equipment versus supplies and authorization. Screen core exposure and deepen for expected use. |
| 7. Provider access | L08 provider and hospital evidence and identity lookup exist. R7 ties the same clinician and office to two candidate offerings with a dated Wellcare listing and a separate Humana group signal. | Confirm clinician, site, intended date, exact plan/network and participation with permitted dated evidence. Confirm scheduling/new-patient access separately if material. Retain partial directory coverage and any conflicting answer. A provider must-have holds dependent choices while unresolved. |
| 8. Medicines | L05 formulary and criteria research. R7 checks two forms of the same medicine against two plans. The 11 MA-only records show no included Part D. | For a reported medicine, bind formulation/strength/route and product identity to the correct plan formulary version and check tier, PA, ST and quantity limit/unit. Use applicable criteria and source permissions. Known access stops and ambiguous units hold dependent conclusions. |
| 9. Pharmacy and drug costs | L06 schedules and averages, L07 dated outlet/channel networks and r7's exact outlet/quantity/month estimates. | Bind the exact outlet, channel, strength, fill quantity, days, phase, subsidy and intended period. Add a reviewed estimate method with an official exact-fill route for material gaps. Keep source averages, plan estimates and quotes distinct. Rerun after changed drug, pharmacy, date or subsidy. |
| 10. Care away from home | Plan types and selected network conditions in the catalog. L03/L08 retain source material. | Establish emergency/urgent versus routine care, any POS/travel terms, service areas and destinations. Resolve provider/network and out-of-area cost at the place and date relevant to the person. Teach the distinction when routine travel is material. |
| 11. Supplemental benefits | MPF main rows for dental, vision and hearing for all 72. Separate optional file has 15 rows across five offerings. L03 carrier and rider records remain available. | Separate base from optional packages and charge each premium once. Verify allowance, unit, time period, network and use conditions for material benefits. Retrieve specific frequency, codes or rider details when a stated need depends on them. An absent optional row leaves availability unestablished. |
| 12. Quality | L09 build-r4 joins all 72 to retained contract-level context. The matrix preserves its observation ID and source status. | Review exact rating year, contract/reporting grain, missing/suppressed states and allowed redisplay. Include relevant quality context with its limits. Quality data does not establish individual access or suitability. |
| 13. Current coverage and transitions | Existing profile and L11–L14 rules, plus the r7 hypothetical enrollment timing path. | Confirm the coverage baseline and intended effective date from existing reports. Apply reviewed rules to the actual history, rights, window, coordination, assistance and applicable coverage loss. Verify entitlement/enrollment separately when the action requires it. Keep or defer remains a valid outcome. |
| 14. Alternative paths and next help | L01 federal reference, L04 PDP inventory, L10/L11 Medigap source/rule evidence, existing teaching and L15 counseling references. | Compare relevant coverage paths first, with Original Medicare, separate PDP and optional Medigap, and the current baseline. Verify available alternatives, rights and quote scope if needed. For a material unresolved check, give a permitted source or named assisted route and return the scoped answer to the comparison. |

The medical and supplemental source pointers in the per-offering matrix refer to the retained MPF extract. Their presence establishes row availability. It leaves interpretation, amendments, source-use and release review open. The shared gaps in the table apply wherever the cited field is material. [MPF source scope](../../data/mpf-benefit-summary-2026-11-04-r1/README.md) · [L01–L15 evidence and known limits](../../reviews/2026-11-02-project-readiness/DATA_REVIEW.md) · [Exact r7 cases](../recommendation-scope-2026-11-04-r7/CASES.md)

## Remaining recommendation work across the families

1. Build the accepted projection by source family. Bind exact claims, conditions, methods, amendments and review decisions for the intended use. Preserve the named existing holds and original authority replay. Start with baseline market scope and medical exposure, then include extra details when material to the person.
2. Connect verified personal lookups to the confirmed profile. Reuse the 41 meanings and attach each check to the person, item, site or outlet, year, evidence date and report revision. Validate corrections, stale or revoked evidence, conflicts and wrong-year requests. Exercise one completed verification and one actionable hold, using the r7 cases as regressions.
3. Implement exact-purpose selection and release in the existing comparison service. Present relevant coverage paths, a neutral candidate universe, comparable costs and clear reasons. Bind supported outcomes to a decision record. Independently review recommendation logic, AI explanations and D64 I01–I10, including missing-data neutrality and commercial invariance. Hold conclusions when an unresolved difference could change the choice.
4. Prove a complete pilot journey through a concrete next action. Include source inspection, correction, supported return, desktop and mobile use, and actual host/privacy/operating checks. Scope any assisted verification to a consented workflow with a responsible operator and a returned result. [Release target](../recommendation-scope-2026-11-04-r6/CONSUMER_JOURNEY.md) · [Independence acceptance](../INDEPENDENCE_ACCEPTANCE.md)

## Use the tool

Transfer the existing r5 `catalog.json` as the versioned research data file. Its byte digest is pinned in [catalog_research.py](../../../alternatives/advisor-first/catalog_research.py). The research adapter resolves the selected offering's source records from the same artifact, including their archive locators. The underlying carrier PDFs and source workbooks retain their separate archive locations.

On the local advisor with `--local-research`, create a guest session with `GET /api/guest/session`, then send `POST /api/research/query` with that cookie, `X-Daylight-CSRF` and the local origin. Use this body to list all offerings. Add `offering_id` to retrieve a specific plan, such as `2026:H1036:217:000`. Clients can set `expected_catalog_sha256` from the list response to pin their subsequent lookup.

```json
{
  "operation": "catalog",
  "scope": {"year": 2026, "state": "FL", "county_fips": "12021", "category": "medicare_advantage"}
}
```

The exact-plan response includes published fields, scenarios, assumptions, holds and resolved source records. The route uses the existing loopback research and session guards. It requires no personal profile, emits no ranking and grants no consumer or model authority. D73 review for this increment concerns source-inspectable research and honest scope. Consumer comprehension, intake and correction behavior still require the end-to-end pilot.

Reproduce the matrix from the sealed source selections with `python3 -B docs/product/recommendation-scope-2026-11-04-r9/build_matrix.py --check` from the repository root.

## Verification and actual time

| Checkpoint on November 4, ET | Clock time | Elapsed from start |
| --- | ---: | ---: |
| Work started | 3:20:39 p.m. | 0:00 |
| Direct catalog reads and existing research HTTP suite verified | 3:23:28 p.m. | 2:49 |
| Gap matrix replay and isolated HTTP verification complete | 3:25:24 p.m. | 4:45 |
| Live catalog verified on the restarted local advisor | 3:25:48 p.m. | 5:09 |
| Final catalog and matrix replay, integrity and code checks complete | 3:26:19 p.m. | **5:40** |

The live smoke test compared all 72 response payloads and 1,352 plan-to-source references with the exact catalog. One listing and all 72 detail reads took **1.347 seconds** on loopback. The same isolated run took 1.366 seconds. The checks exercised missing session and CSRF, foreign origin, wrong year or county, unknown offering, version mismatch, altered catalog bytes and a request to override purpose. Twenty existing research HTTP tests passed. Both smoke sessions were deleted after verification. The r5 catalog replay preserved the prior pilot values and explicit holds. These timings cover this internal delivery and gap audit.
