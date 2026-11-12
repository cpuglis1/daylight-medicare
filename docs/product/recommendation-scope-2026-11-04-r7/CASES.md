# Two timed 2026 Collier decision cases

November 4, 2026 · D91 r7 · Offline research with fictional profiles

**Result.** Case A supports comparing the coverage paths and two candidate plans. Case B holds the recommendation and makes the exact doctor check the next action. Both cases reached a next step. Neither includes a personal enrollment decision or proof of an accepted consumer journey.

The [r4 pilot](../recommendation-scope-2026-11-04-r4/PILOT.md) supplies two real 2026 Collier MA-PD HMOs, Humana Gold Plus H1036-217-000 and Wellcare Giveback H1032-198-000. They are an engineering pair within a wider market. Both fictional cases report Collier residence, ZIP 34102, first-time Parts A and B effective November 1, age 65 in November, current Original Medicare, no other coverage or assistance, and a requested December 1 start. Ordinary age-based eligibility and other program prerequisites are assumed for the timing test. The request date is November 4. The cases share the named doctor and the same pharmacy. In A the person is open to another doctor and wants to limit medical spending. In B the person says keeping this doctor at this office is essential and corrects the medicine to extended release.

## Eligibility and date check

The retained ZIP reference maps 34102 to Collier, and the exact pair is present in 2026 Medicare Plan Finder for that ZIP. The existing L13 timing method puts the fictional initial MA election window at August 1, 2026 through February 28, 2027. A valid initial election received November 4 under the stated facts would take effect December 1, 2026. The annual election route would start January 1, 2027, so a comparison for that route requires 2027 evidence. The calculated window depends on the reported dates, actual eligibility and a valid election. No individual Medicare record or carrier application was checked. [Election periods](https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-422/subpart-B/section-422.62) · [Effective dates](https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-422/subpart-B/section-422.68) · [Retained enrollment method](../../data/l13-enrollment-2026-10-28/README.md)

## Doctor and site check

NCH confirms Mark Josephson, MD at Concierge Medicine South, 311 9th Street North, Suite 306, Naples. The dated September 23, 2026 Wellcare directory lists that exact site for the plan. NCH Medical Group’s public list also names Wellcare Medicare Advantage through year-end and lists Humana Medicare Advantage PPO only. NCH’s separate hospital contract list is broader. The Humana pilot plan is an HMO, and its partial October 11 directory has no exact listing for this doctor. That leaves an adverse group signal and an unresolved exact Humana result. The Wellcare listing provides a stronger December lead, with individual access and concierge terms still open. NCH describes limited concierge enrollment. The individual NCH profile returned HTTP 403, and the check used the public clinic page instead. [NCH exact office](https://nchmd.org/services/concierge-medicine/concierge-physicians/) · [NCH Medical Group payer list](https://nchmd.org/patients-and-visitors/contracted-insurance-plans/) · [NCH concierge program](https://nchmd.org/services/concierge-medicine/) · [Wellcare directory evidence](../../data/l08-provider-networks-2026-10-27/wellcare-r5/REPORT.md)

NCH separately announces that Wellcare Medicare Advantage goes out of network there on January 1, 2027. A December listing is useful for a December question and cannot establish continuity into January. [NCH network change notice](https://nchmd.org/maupdate/)

## Medicine and pharmacy check

I ran both product selections in anonymous 2026 Medicare Plan Finder with no subsidy, 30 tablets every month and only Publix Pharmacy #1434 at 1981 Tamiami Trl N, Naples, selected. Plan Finder returned the December drug estimate for each combination below. The tiers and limit flags were cross-checked against the exact retained formulary and pharmacy rows. The immediate-release Humana tier and absence of a limit come from the retained row. Where a limit applies, its numeric amount and days are visible, and the physical unit remains unbound. The dollar amounts are Plan Finder estimates for the fictional December fill and outlet. [Humana Plan Finder detail](https://www.medicare.gov/plan-compare/?year=2026#/plan-details/2026-H1036-217-0?plan_type=PLAN_TYPE_MAPD&fips=12021&zip=34102&lang=en&year=2026&page=1#drug-coverage) · [Wellcare Plan Finder detail](https://www.medicare.gov/plan-compare/?year=2026#/plan-details/2026-H1032-198-0?plan_type=PLAN_TYPE_MAPD&fips=12021&zip=34102&lang=en&year=2026&page=1#drug-coverage) · [Captured guest inputs and observations](public-observations.json)

| 500 mg metformin product | Humana · standard retail | Wellcare · preferred retail |
| --- | --- | --- |
| A. Immediate-release tablet, RxCUI 861007 | **$0 estimated for December**, tier 1, quantity-limit flag off | **$0 estimated for December**, tier 6, limit 150 per 30 days |
| B. 24-hour extended-release tablet, RxCUI 860975 | **$0 estimated for December**, tier 1, limit 120 per 30 days | **$0 estimated for December**, tier 6, limit 120 per 30 days |

The correction changed the RxCUI, NDC and restriction evidence. The pharmacy network class and estimated price stayed the same in this scenario. The fixture rejected the prior identity receipt after the form’s report revision changed. The official plan and outlet lookup ran again for the corrected product. [Structured case results](case-results.json)

## How the checks change the next step

| | Case A · Flexible about PCP | Case B · Exact doctor required |
| --- | --- | --- |
| What the comparison can say | The tested medicine does not separate the two December estimates. Humana has a $3,800 in-network medical maximum and a $540 three-day hospital copay component in the bounded example, versus $7,200 and $1,200 for Wellcare. Wellcare publishes a $77 monthly Part B reduction versus Humana’s maximum $3. Actual Part B billing remains separate. Both list $0 plan premium and $0 for the four ordinary covered in-network PCP visits in the example. | The same medical tradeoffs and rerun ER estimate remain visible. Neither plan has verified access to the required doctor and office. Wellcare’s exact listing makes it the first December verification lead. Humana’s HMO faces the NCH Medical Group PPO-only signal. The published cost differences cannot settle a must-have. |
| Next action | Confirm the initial-election basis and effective date with the intended plan or Medicare. Compare the current Original Medicare path, including separate drug and supplemental options where relevant, with the December MA candidates. If MA is still under consideration, identify an acceptable in-network PCP and check the January coverage path separately. | **Hold the recommendation.** Ask the office and plan whether the exact plan covers Dr. Josephson at Suite 306 on December 1, whether the person can be seen, and what concierge terms apply. Verify Wellcare first for December because it has an exact listing. For ongoing access, compare year-matched 2027 options separately in light of NCH’s termination notice. The next action is recorded for the pilot participant or a permissioned verifier. |

The doctor hold is separate from the advisor’s existing consumer authority hold. The existing must-have evaluator was run with an otherwise identical fictional finding, first as a hypothetical verified positive and then as unresolved. The positive put one candidate in **known meets**. The unresolved version put both candidates in **unresolved**, with no known conflict, hidden candidate or automatic order. A corrected report revision invalidated the prior office and drug receipts. The preview rejected a conflicting 2027 request. A separate advisor engine check confirmed that real recommendation authority is still held. The next-action contrast is demonstrated by the offline case runner. [Replay output](case-results.json)

## Replay and time

From the repository root, run:

```sh
python3 -B docs/product/recommendation-scope-2026-11-04-r7/run_cases.py
```

Replay reads the sealed plan, formulary, pharmacy and directory sources plus the dated manual public observations. It tests the two cases, the isolated must-have control, correction invalidation and wrong-year behavior. It performs no network calls and does not update the evidence. For a fresh price, rerun the anonymous Plan Finder lookup using the recorded inputs.

The timed pass ran **12:07:26–12:16:25 ET**, or **8 minutes 59 seconds**, through exact replay and link verification. That includes public rule and provider review, the anonymous Plan Finder lookups, comparison, test execution and reporting. The measured machine-only replay took **2.12 seconds**. The 45 targeted advisor tests, 20 enrollment reference tests, 53 enrollment fixtures and original two-plan replay passed. No founder-assisted response time was measured.

Work was confined to public-source checks, read-only research, and the offline packet. Daylight UI, runtime, guest data and source acceptance were outside this run.
