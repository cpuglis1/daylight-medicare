# Data acceptance standard — October 20, 2026

Owner requirement: **“non-validated data is unacceptable.”** Captured records, a completed engineering task, passing software tests and an immutable release do not constitute acceptance of every consumer fact. The current candidate remains an owner-testing research artifact; qualified domain sign-off is pending.

## Acceptance applies to individual fields and claims

Before a value can appear in consumer chat, cards, comparisons, ordering, totals or exports, its acceptance record must identify:

1. Exact plan/contract/segment or insurer/product/form identity, benefit/effective year, geography and applicable population.
2. An authoritative source, saved bytes/hash, retrieval date, document page/table/row or structured pointer, and original wording/value.
3. Correct interpretation: monetary units and periods, gross/subsidy/beneficiary basis, network/site/service conditions, exceptions and eligibility qualifications.
4. An independent extraction/reconciliation check appropriate to the claim. A second format from the same CMS publication checks extraction; it is not a second independent source. Use independent authoritative corroboration for money, availability and participation where required by the workstream.
5. Resolution of material discrepancies. Equal numbers do not establish equal definitions; a source-only or conflicting value is not accepted merely because a warning accompanies it.
6. Reviewer, review date, scope, evidence and refresh deadline, tied to the exact source/transformation and release. Source changes, expiry or a relevant parser change invalidate acceptance until reviewed.

An official nonnumeric state, such as CMS “Not enough data available,” can be accepted as that source's stated result. Missing data is never zero or proof of noncoverage/ineligibility. An unsupported answer may say that verification is unavailable without exposing an unverified number or benefit claim. A missing required R1 fact blocks release; an optional unsupported feature remains disabled.

## Current gaps found in the October 20 audit

- The 70-plan/24-field matrix contains 831 cells marked not independently reviewed, 530 source-only cells, 96 historical selected-field corroborations, 54 historical card summaries with unreviewed conditions, four premium-conflict cells and 165 standalone-PDP nonapplicable cells. These are scope classifications, not 1,680 accepted facts.
- Carrier corroboration covers selected fields for 16 plans across three parent organizations. It does not validate every benefit for those plans or the other 54 records.
- The initial audit found that the catalog could display and sort source-only monetary values. **C37 now enforces admission before consumer data access**, with per-field and exact-output receipts plus complete required-release review. The current candidate has no accepted claims and remains closed to consumer use; explicit offline research retains the raw values.
- C21 completed the prior plan's display-both alternative. Both premium sources remain unresolved; consumer use now requires resolution or suppression, while raw evidence stays available for research.
- All 3,876 CHOICES amounts are illustrative annual comparisons. Requested January 1, 2027 is not an established effective date. Actual effective dates/forms, 33 insurer NAIC mappings, household-discount assumptions and independent rate replays remain missing.
- A provider-directory plan/network reference does not validate a specific doctor/hospital at a specific location for a 2027 plan. Clinical participation remains unverified.
- Medicare.gov bootstrap returned HTTP 403. The collector remains stopped. No protected-source retry, alternate-browser workaround or bypass is authorized by a demand for validation.

Evidence: [matrix](../cms-slice/reports/collier-gap-20261020/c16-c23/c19-core-benefit-matrix.json), [partial rate dataset](../cms-slice/reports/collier-gap-20261020/c16-c23/c23-florida-medigap.json), [source stop](../cms-slice/reports/collier-gap-20261020/c16-c23/c16-browser-preflight-9/run.json), and the selected release's manifest (`domain_signoff: pending`). The original captures remain historical research evidence. Implementation and new checks are documented in `VALIDATED_DATA_OPERATIONS.md` and the validation review packet; no qualified domain acceptance is claimed.

## Work needed to accept R1 data

| Data | Required validation |
| --- | --- |
| Market/availability | Reconcile all 70 CMS identities against current 2027 availability for the four Collier ZIP inputs, in both directions. Explain every difference and restricted offering. C17/C18 need documented source-access resolution; do not infer absence from the incomplete historical scenario. |
| Benefits and money | Collect exact 2027 Summary of Benefits/EOC documents for all 70 records. Validate each displayed field's amount, units, conditions and plan/year applicability; reconcile CMS and independent observations. Review Regional PPO semantics and resolve the two premium-basis disputes. Carrier-document work can proceed while Medicare.gov access remains blocked. |
| Drugs/pharmacies | Validate exact drug/form/strength identifiers, formulary joins, tier/restriction meaning, quantity units and pharmacy-plan mapping. Coverage evidence is separate from a price. Pricing needs an authorized adequate 2027 source and reproducible synthetic cases before any applicable held calculator can be approved. |
| Medigap | Obtain responsive OIR records for case 26-045612, join insurer/NAIC/form/variant/rating area/effective dates, reconcile CHOICES with filing tables or insurer evidence, and reproduce rates and assumptions from an independent source per insurer. Resolve household discounts, fees and under-65/GI scope; preserve illustrative status unless a real quote supports a different label. |
| Provider participation | Verify exact clinician/facility identity, service location, medical network and 2027 plan mapping against current insurer and hospital/provider evidence. Validate adapter joins and cases; keep unsupported participation answers unavailable. |
| Rules/programs | Verify authoritative passages and effective periods, then have a Medicare reviewer approve interpretation and boundary cases. Published program/service-area evidence does not determine an individual's eligibility. |
| Product/release | C37 blocks unaccepted fields throughout the app. C33–C36 test the final candidate, regenerate its audit, bind its immutable release and obtain named domain-review acceptance. Technical tests support this review; they do not substitute for it. |

External dependencies are responsive OIR records, an authorized route for the blocked CMS observations, and a named Medicare subject-matter reviewer. No paid purchase, new outreach, personal-data collection or reopening of a hold is authorized by recording this standard. C01's owner-testing deferral remains unchanged.

C37 is implemented and the local app now shows a validation-pending page. Fourteen additional plans have selected financial checks, four Optimum plans have carrier-side observations across the four ZIPs, and every packaged pharmacy network has an exact-plan join replay. These are partial technical checks, not consumer acceptance. Continue exact SB/EOC field audits across all 70 plans and independent participation/drug checks; complete source-access, OIR and named-reviewer dependencies. Evidence: `../cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md`.
