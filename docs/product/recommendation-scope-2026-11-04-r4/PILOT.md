# 2026 Collier comparison pilot

This package prepares a two-plan educational comparison for independent review and later integration. The pilot pair is Humana Gold Plus H1036-217-000 and Wellcare Giveback H1032-198-000. Erickson Advantage Liberty no Rx H5652-002-000 remains a regression case for a residence restriction, a no-Part-D plan and an inpatient deductible hold.

## Plan selection and scope

Humana is the prior MA-PD HMO anchor. From the frozen 72-offering 2026 Collier catalog, take the lowest exact offering ID among non-SNP MA-PD HMOs with Part D from a different parent carrier. Eight offerings qualify. That rule selects Wellcare Giveback before reviewing its benefit amounts. The pair is an engineering selection without an implied order of fit. The [candidate bundle](pilot.json) records all eight eligible IDs.

## Published terms and fictional results

| 2026 Collier comparison | Humana Gold Plus | Wellcare Giveback |
| --- | --- | --- |
| Monthly plan premium and 12-month component | $0 × 12 = **$0** | $0 × 12 = **$0** |
| Published monthly Part B reduction | Up to $3 | $77 |
| Medical deductible | $0 | $0 |
| In-network annual medical out-of-pocket maximum | $3,800 | $7,200 |
| Four ordinary covered in-network PCP visits | $0 × 4 = **$0** | $0 × 4 = **$0** |
| Published in-network specialist office visit | $10. Check referral and authorization for the specific service. | $35. Referral and prior authorization may be required. |
| First inpatient band | $180 per covered day on days 1–5 | $400 per covered day on days 1–6 |
| One covered acute admission for three → four counted days | **$540 → $720** | **$1,200 → $1,600** |
| Published annual Part D deductible | $615 on tiers 4–5 | $615 on tiers 3–5 |

The hospital amounts cover one formal in-network acute admission, starting on day one and excluding discharge day. The case assumes any required referral and prior authorization, room under the applicable medical maximum, and no cost-sharing adjustment from assistance. Later bands, transfers, readmissions and separately billed professional services sit outside the calculation. Wellcare’s Evidence of Coverage describes additional days and lifetime reserve days separately. The carrier’s condition for days 91–95 excludes their cost sharing from the medical maximum. [Exact source rows and carrier pages](pilot.json).

Part B reductions apply separately from the plan premium. A member’s Part B bill and the timing of any credit require separate verification. The drug deductibles exempt covered insulin and most adult Part D vaccines. Doctor and site participation, individual medicine coverage and cost, eligibility and stated must-haves remain unchecked for both plans. [Field conditions and held checks](pilot.json).

## Evidence review

- **Humana.** The retained September 2026 CMS Landscape record 12549, MPF rows 45755–45756, 45762 and 45767–45768, and selected carrier pages support the scoped amounts and conditions. The accepted L03 r4 reference overlaps the gross monthly premium, in-network medical maximum and first inpatient band. That acceptance retains its existing published-reference scope. The earlier preview omitted the separately published Part B reduction of up to $3. [Source readings](source-readings.json).
- **Wellcare.** The retained September Landscape record 12541 and MPF rows 42075–42076, 42082 and 42087–42088 match the carrier amounts used here. The Summary of Benefits lists Giveback beside Wellcare Simple. The review checked the exact H1032-198-000 column, including the $77 Part B reduction, no medical deductible and the first inpatient band. The Evidence of Coverage distinguishes covered admission days, applicable referrals and authorizations, discharge day and longer-stay rules. [Source readings](source-readings.json).
- **Erickson regression.** The $0 plan premium and four-visit PCP component replay. Its $1,000 selective annual deductible applies to inpatient care and excludes ordinary PCP office visits. The $375 published daily rate for days 1–7 stays visible, while the three- and four-day copay subtotals both remain held because the remaining deductible and the charges relevant to meeting it are unspecified. The in-network specialist range and out-of-network hospital coinsurance still decline exact-dollar arithmetic. The carrier’s Collier and Erickson Retirement Community conditions are explicit. [Source readings](source-readings.json).

The cross-check was performed by the author of the earlier experiment and preview. Exact independent interpretation and method review, applicable amendment and variant checks, and purpose-specific acceptance are pending. The selected carrier passages establish the source snapshot and bounded reading. Enrollment, ranking, personal recommendations and 2027 use remain held.

## Handoff for later integration

- **Payload.** [pilot.json](pilot.json) contains the exact version, county and offering IDs, separate pilot and regression roles, typed amounts, conditions, held statuses and source hashes. The bundle is for server-side review. A later presentation should project consumer-safe labels and locators from the accepted fields.
- **Replay.** Run the command below from the repository root. It verifies source and method bindings, the original experiment, both stay lengths, stable source conditions and the held regression case.
- **Release gate.** Review the exact packet and bind any acceptance to its bytes, offering scope, fields and intended educational purpose. The current candidate’s accepted release ID is empty and consumer use is false. Surface selection remains a separate decision. A dedicated comparison page is an option for that decision.

```sh
python3 -B docs/product/recommendation-scope-2026-11-04-r4/build_pilot.py --check
```

D91 scope and the D64/D73 boundaries are preserved. The packet reuses the fictional adapter binding and all 41 conditional meanings, requires no additional intake, and has no commercial selection fields or real guest data. It prepares a comparison within one coverage path. Broader path choice and actual comprehension remain separate evidence. The r9 census, 4,675 first-plan obligations, 535-entry accepted r4 reference and 16 named gaps retain their existing status.

## Actual elapsed time

The timed pass ran from **11:04:47 to 11:13:02 ET on November 4, 2026**, or **8 minutes 15 seconds** through handoff verification. The plan rule and exact identities were recorded at 11:05:23. The core source-reading pass reached its checkpoint at 11:08:14, the first complete candidate replay passed at 11:11:54, and the final check passed at 11:13:02. The measured machine-only replay took **1.56 seconds**.

The elapsed time includes rechecking the original pair and onboarding one additional offering from existing local sources. It supplies one timing observation for the next review checkpoint. Independent reviewer time, amendment clearance, consumer acceptance and integration are outside this measurement.
