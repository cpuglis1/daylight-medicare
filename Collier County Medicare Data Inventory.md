# Collier County Medicare Data Inventory

Oct 20, 2026 · @Chris

Daylight already holds all 70 2027 Medicare Advantage and standalone drug plans for Collier County. To cover every option a Naples resident has, it still needs Medigap, personal drug pricing, doctor networks, star ratings, Original Medicare costs and the help-program rules.

## How to read this

Each row below is one kind of data a resident needs to compare options. Status reflects the Daylight audit workbook dated 2026-10-19 (release naples-7a0b8eff1577df6e41eb).

- **Have**: captured for 2027 and in the active Naples app.
- **Partial**: captured, but incomplete, unverified or not wired into the app.
- **Missing**: nothing captured yet.

## The two paths

&#91;embedded content: Medicare choices in Collier · 2 paths, help programs under both\]

Medigap and a standalone drug plan sit on top of Parts A and B. An Advantage plan replaces how A and B are delivered, but the person still pays the Part B premium.

## Inventory

Three of the fifteen data layers are fully in hand, all of them CMS plan files. The rest are partial or missing, and Medigap is missing entirely.

| Layer | What a resident needs | Best source | Updates | Status | Daylight today and next step |
| --- | --- | --- | --- | --- | --- |
| Original Medicare (Parts A and B) | 2027 premiums, deductibles, coinsurance, income-based surcharges (IRMAA) | CMS annual cost announcement; SSA for IRMAA | Yearly, usually Oct to Nov | Missing | Only an explainer page captured. Load 2027 amounts once CMS publishes them. |
| Medicare Advantage plan list | Every Advantage plan sold in Collier, including special-needs plans, with premiums and out-of-pocket limits | [CMS landscape file](https://www.cms.gov/newsroom/press-releases/medicare-advantage-medicare-prescription-drug-programs-expected-remain-stable-2027) | Yearly, late Sept, corrections into Oct | Have | 59 plans: 32 regular, 27 special-needs. Only 38 are in the comparison experiment. Reconcile the count against Medicare.gov Plan Finder for Naples ZIP codes. |
| Advantage benefit detail | Copays, dental, vision, hearing, extras, referral rules | CMS Plan Benefit Package (PBP) files | Yearly, early Oct, occasional re-releases | Have | 190,096 field values across all 70 plans. Only 38 plans spot-checked against Medicare.gov. |
| Standalone drug plans (Part D) | Every drug plan sold in Florida, with premium and deductible | CMS landscape and PBP files | Yearly, late Sept | Have | 11 plans captured. |
| Drug formularies | Which drugs each plan covers, at what tier, with what restrictions | CMS Part D formulary files | Monthly | Partial | 61 drug-bearing plans, 24 formularies. Two premium conflicts open (DQ-003, DQ-004). |
| Drug prices | A person's estimated yearly drug cost in each plan | CMS Part D pricing files | Quarterly | Missing | No 2027 price source (DQ-007), and a release-date ambiguity (DQ-008). Find the 2027 pricing release. |
| Pharmacy networks | Which pharmacies are preferred or in network | CMS Part D pharmacy network files | Monthly | Partial | Captured for 61 plans, only 31 in the app (DQ-010). Package the other 30. |
| Doctor and hospital networks | Whether a person's doctors and hospital are in each Advantage plan | Each insurer's public [provider directory API](https://www.cms.gov/priorities/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api) | At least every 30 days ([CMS-4208](https://1up.health/blog/is-your-provider-directory-endpoint-ready-for-medicare-plan-finder-cms-4208-f2/)) | Missing | Participation unresolved for all 70 plans (DQ-009). Pull directories for the 9 parent companies. |
| Star ratings | CMS quality score per plan | [CMS 2027 Star Ratings](https://www.cms.gov/newsroom/fact-sheets/2027-medicare-advantage-part-d-star-ratings), released Oct 8, 2026 | Yearly, October | Missing | Star columns blank in the landscape file (DQ-002). Load the separate 2027 star data. |
| Medigap plans and prices | Every insurer selling each letter plan (A to N, high-deductible F and G, SELECT) with Collier prices by age, sex and tobacco use | Florida OIR [CHOICES](https://floir.gov/consumers/choices-rate-comparison-search) (illustrative); insurer rate filings; a commercial rate feed | Rates change whenever insurers file, often yearly | Missing | No quotes captured (DQ-011). CHOICES and a CSG Actuarial sample are saved as reference only. Pick a supplier. |
| Medigap buying rules | Open enrollment window, guaranteed-issue rights, Plan C and F eligibility, under-65 access | Medicare.gov Medigap guide; Florida insurance law | Yearly | Partial | Medicare.gov Medigap page captured. Turn the rules into eligibility logic. |
| Help programs | Extra Help, Medicare Savings Programs, Florida Medicaid income and asset limits | SSA; Florida Department of Children and Families | Yearly, early in the year | Missing | Nothing captured. |
| Enrollment periods and penalties | Sign-up windows, late penalties for Part B and Part D | Medicare.gov | Yearly | Partial | Medicare.gov parts and drug-rules pages captured. Turn them into date logic. |
| Other plan types | PACE, Medicare Cost plans, Medical Savings Accounts | CMS PACE directory; landscape file | Yearly | Missing | None seen in Collier data. Confirm whether any exist locally. |
| Local counseling | Free unbiased help from Florida SHINE | Florida Department of Elder Affairs | As needed | Missing | Nothing captured. Add as a referral. |

## Biggest gaps, in order

Medigap comes first because without it, Daylight cannot show half of the basic decision every new enrollee makes.

1. **Medigap prices and rules.** Without them, the Original Medicare path cannot be compared with Advantage at all. This also needs a supplier decision, the slowest step.
2. **Personal drug costs.** Drug spending is often what separates one plan from another. Formularies are in hand, but prices for 2027 are not.
3. **Doctor and hospital networks.** "Is my doctor covered?" is the deciding question for most Advantage shoppers. All 70 plans are unresolved.
4. **Star ratings.** The 2027 data has been public since Oct 8, so this is the quickest gap to close.
5. **Original Medicare costs and help programs.** These are small, yearly tables, but every total-cost estimate depends on them.
6. **The 32 plans outside the comparison experiment.** They are captured, but residents can't compare them yet. Most are special-needs plans, which matter to people on Medicaid, with chronic conditions or in nursing homes.

## Out of scope

These affect what a resident should do but aren't plans anyone can shop for, so Daylight should flag them rather than list them.

- **Employer and union retiree plans.** These are offered only to a group's members and aren't on the public market.
- **VA health care and TRICARE for Life.** These change whether a person needs Part D or Medigap at all.
- **Pre-standardized Medigap policies.** Older policies that people still hold but that can't be bought new.

## Sources

- [CMS: 2027 Medicare Advantage and Part D press release](https://www.cms.gov/newsroom/press-releases/medicare-advantage-medicare-prescription-drug-programs-expected-remain-stable-2027)
- [CMS: 2027 Star Ratings fact sheet](https://www.cms.gov/newsroom/fact-sheets/2027-medicare-advantage-part-d-star-ratings)
- [CMS: Provider Directory API FAQ](https://www.cms.gov/priorities/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api)
- [1upHealth: CMS-4208-F2 and Medicare Plan Finder](https://1up.health/blog/is-your-provider-directory-endpoint-ready-for-medicare-plan-finder-cms-4208-f2/)
- [Florida OIR: CHOICES rate comparison](https://floir.gov/consumers/choices-rate-comparison-search)
- Daylight data quality audit workbook, 2026-10-19 (issue IDs DQ-001 to DQ-014)
