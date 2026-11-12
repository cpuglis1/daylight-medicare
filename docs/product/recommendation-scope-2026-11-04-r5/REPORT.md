# 2026 Collier offline catalog comparison

The offline comparison covers all 72 retained 2026 Collier County Medicare Advantage offerings. Each exact offering has the pilot’s published fields, personal-check statuses and fictional scenarios. The readable comparison keeps published terms beside held calculations and lists the reasons by offering. The structured bundle preserves source versions, row and page locators, qualifications and exact holds. [Readable comparison](COMPARISON.md) · [Structured catalog](catalog.json).

## Coverage and results

| Scenario | Numeric candidates | Held |
| --- | ---: | ---: |
| Twelve months of published plan premiums | 69 | 3 |
| Four ordinary covered in-network PCP visits | 47 | 25 |
| One covered acute in-network stay, three counted days | 42 | 30 |
| Same admission, four counted days | 42 | 30 |

There are 200 numeric candidates and 88 holds across 288 scenario cells. All scenario amounts are supported for **41 offerings** under the stated fictional assumptions. The 72 exact identities include 32 MA-PD, 11 MA-only and 29 special needs offerings. The source catalog’s geography, eligibility and plan restrictions remain separate from the scenario math. Offering ID determines the comparison order.

The 42 hospital candidates include 39 daily charges and three per-admission charges. The daily cases add one day’s charge when the stay changes from three to four days. The per-admission cases retain a single charge at both lengths. The pilot’s amounts and holds replay exactly, including Erickson Liberty no Rx’s unspecified inpatient deductible balance. Both lengths assume a single covered acute facility admission starting on day one, any required referral and authorization, sufficient room under the medical limit, and no assistance adjustment. Discharge day, separately billed professional services, transfers and readmissions sit outside the calculation.

## Treatment of unresolved terms

- **Premiums.** All 72 offerings match one exact September 2026 Collier Landscape record. Three annual calculations remain held where the retained gross and carrier premium amounts differ. The underlying figures remain inspectable. The scenario uses the plan premium only, with the Part D component counted once where applicable.
- **Medical deductibles.** Eleven nonzero deductibles have exact carrier statements for the selected scope. Seven exclude all in-network services and four exclude ordinary in-network PCP office visits while leaving inpatient applicability held. Three additional medical deductible rows retain their conditional published terms and held status.
- **Office and hospital charges.** The builder checks the MPF charging unit and amount against a retained carrier or scoped reference observation. The two documented nominal-versus-protected conflicts stay held for PCP, specialist and hospital. Twenty dual-eligible offerings keep their PCP and hospital examples held while the fictional case lacks the required cost-sharing basis. An unmatched amount, unclear charging unit, service-specific deductible or missing rate becomes a named hold.
- **Part B reductions and Part D deductibles.** Exact carrier reduction statements support 29 published candidates. The other 43 retain an unresolved reduction status. The reduction never offsets the plan premium scenario. Part D deductible status is published candidate for 56 offerings, held for five, and inapplicable for the 11 MA-only offerings. Carrier tier statements are used only when the amount and scope match the retained Landscape basis. Drug-specific exceptions and costs remain separate.
- **Personal checks.** Eligibility and enrollment, doctor and site participation, medicine coverage and cost, actual Part B billing and stated must-haves remain unchecked for every offering.

The packet uses exact local copies of CMS Landscape and MPF, retained carrier document evidence, and the existing bounded L03 source observations. The 535-entry accepted L03 r4 reference keeps its original purpose and its 153 held claim groups. Derived values in this catalog remain producer candidates. Independent review of the exact terms and methods, amendment and variant checks, and purpose-specific acceptance are required before consumer use. [Input versions](sources.json) · [Pilot](../recommendation-scope-2026-11-04-r4/PILOT.md).

## Replay

From the repository root, run:

```sh
python3 -B docs/product/recommendation-scope-2026-11-04-r5/build_catalog.py --check
```

The replay verifies the 72 exact identities, source hashes and references, the prior pilot’s amounts and holds, arithmetic, the three-to-four-day correction, refusal of range or percentage arithmetic, and held consumer authority. It compares both catalog outputs byte for byte. The scope is retained 2026 Collier Medicare Advantage. D64 and D73 boundaries carry forward. The work uses the existing fictional profile binding and 41 conditional meanings, with no new data collection or commercial input.

## Actual elapsed time

The pass ran from **11:17:58 to 11:33:37 ET on November 4, 2026**, or **15 minutes 39 seconds** through handoff verification. Source bindings were recorded at 11:21:30. The first full catalog passed its build checks at 11:27:47. Targeted deductible and charging-unit checks and hold presentation were completed at 11:32:13. The final byte-for-byte replay took **7.75 seconds**.

The clock includes source inspection, batch implementation, targeted exception checks, documentation and replay. Independent review, amendment clearance, consumer acceptance and UI work sit outside the measured scope.
