# MPF-first comparison workflow and bounded experiment

November 4, 2026 · D91 revision 2 · 2026 Collier local pilot.

**Current direction:** use published structured facts, preserve readable benefit terms, and investigate only details that can change the requested comparison. Start with premium arithmetic, straightforward office visits and one bounded hospital stay. This replaces r1's eight-hour experiment and its broad catalog work as the immediate delivery sequence. The earlier 30–180-hour allowances remain historical, unmeasured planning ranges; they are not an MVP prerequisite or the budget for this experiment.

This task acquires the MPF source and records this plan. **The calculation experiment described below has not yet run.** Its next execution has a **30-minute elapsed-time hard stop**, including implementation, checks and the final artifact. Stop earlier when the deliverable is complete. Do not roll into another research session or expand the plan set automatically.

## What has already been pulled in

The official [CMS CY 2026 MPF Benefit Summary](https://www.cms.gov/data-research/statistics-trends-reports/medicare-advantage/part-d-contract-and-enrollment-data/mpf-benefit-summary-report/cy-2026-mpf-benefit-summary) is retained locally with source hashes and exact workbook/row locators. See [the acquisition record](../../data/mpf-benefit-summary-2026-11-04-r1/README.md).

- Download: 21,846,471 bytes, approximately 20.8 MiB compressed.
- Main workbook: 458,554 populated data rows. Exact year/contract/plan/segment matching retains **6,021 rows across all 72 frozen Collier MA offering identities**.
- Optional-benefit workbook: 3,667 national data rows; **15 rows across five of those offerings**. Missing optional rows do not establish that an offering has no optional benefits.
- The main workbook supplies service descriptions, readable cost sharing, network labels and limit/authorization/referral fields. It **does not supply the base plan premium**. Use a separate exact premium source already retained, or one targeted carrier-summary lookup.
- The optional workbook's premium is an optional package premium, paid once per package. Never substitute it for a base premium or add it once per service row.
- The main workbook filename includes `12232025`. Today's download does not establish that later amendments are included. Source currency and material discrepancies must be checked before consumer release.

This is source acquisition and structural matching, not completed benefit interpretation or release acceptance. No live PostgreSQL table, consumer result, chat behavior or existing evidence is changed.

## The proposed operating workflow

1. **Start from the existing profile.** Reuse the 41 conditional meanings, resolved reports, beneficiary/item identity and revisions. Gather only missing facts needed for the requested finding. Explain a relevant concept in the current conversation; do not add a fixed questionnaire.
2. **Use the shared catalog and published summary first.** Scope by exact year, county and offering. Display supported published facts and complete readable cost descriptions. Do not require every description to become an executable formula.
3. **Calculate a small supported subset.** Use the three methods below only when their exact inputs and material conditions are established. Published terms, scenario components and a personal total remain distinct.
4. **Investigate exceptions on demand.** For an ambiguous field, inspect the exact retained Summary of Benefits, then the relevant EOC section if needed. Preserve qualifiers and known disputes. A parser or model proposes a reading; applicable source/method review governs its use.
5. **Reuse checked facts by exact source version and offering scope.** Cache extraction/interpretation with source location, date, version and conditions. A changed source invalidates affected results; each person's applicability is evaluated separately. An unknown cannot become zero or poor fit.
6. **Explain the comparison and remaining checks.** Teach why a premium is different from service costs, how the stated hospital schedule works and what the scenarios omit. Recommendations follow only when their separate material evidence, candidate-selection and purpose requirements are satisfied.

General coverage-path education, current coverage, keep/defer and alternatives remain part of the product. Provider/drug checks, annual drug pricing and complex rights/transition determinations retain their existing separate requirements. They are not silently certified by these three cost examples.

## The experiment: exactly two plans, one profile, three methods

Use **H1036-217-000** and **H5652-002-000**, both for 2026, because both already have retained hospital/office adapter work and exact MPF matches. This is an engineering validation set, not a personalized shortlist or the entire market. Do not replace a difficult plan with an easier one during the experiment.

Use one fictional profile in the existing profile contract: Collier/2026, requesting comparison of those exact plans. The scenario specifies in-network covered services, four ordinary PCP office visits and one three-day acute inpatient admission. These quantities are explicitly hypothetical, not inferred future utilization or additional mandatory profile questions. Reference the existing report adapter and separate scenario inputs; no real guest data or saved transcript is needed.

| Calculation | Exact result to produce | Conditions and omissions |
| --- | --- | --- |
| Plan premium | Monthly base-plan premium × 12 months, with the monthly input also visible | A hypothetical full 2026 year at the stated rate, not twelve months from today. Exclude federal premiums, optional riders, subsidies/adjustments and medical/drug spending unless separately supported and explicitly included. No double counting medical/drug premium components. |
| Office visits | Four in-network ordinary PCP visits × applicable per-visit copay | Only the stated visit copayment component. State deductible applicability. Exclude procedures, lab work and other separately billed services. A range or percentage without its necessary basis cannot become an exact dollar result. |
| Hospital stay | Sum the applicable daily bands for one three-day in-network acute inpatient admission | Show each day/band and the charging unit. Establish relevant deductible/limit conditions; distinguish a daily schedule from a per-stay charge. Exclude professional fees and unrelated services. Do not claim authorization or actual coverage is approved. No readmission/benefit-period simulation. |

An unsupported required condition yields a named held result. Hypothetical service approval may define the scenario, but does not resolve unknown charging rules. The output must never use a range endpoint as the true charge, assume deductible application, or turn a percentage into dollars without an allowed-amount basis.

**One correction check:** change the hospital stay from three to four days and recompute only its hospital component. The other scenario outputs and source bindings must remain unchanged. Use the retained specialist copay range and out-of-network percentage as negative checks: the simple exact-dollar method must decline them when qualifiers/basis are unresolved.

## What we will have when it succeeds

One small local deliverable package, with **a comparison you can read** and **the same structured result the app can later consume**:

1. **`COMPARISON.md`:** two named real plans in columns; monthly premium and the three scenario results; the arithmetic, assumptions and exclusions; short plain-language teaching; source/workbook/row or carrier-page references; explicit unresolved items.
2. **`comparison.json`:** the same findings with exact plan IDs, fictional-profile/scenario bindings, typed amounts/units, source hashes, conditions and held/research status. This is an integration artifact, not a production release token.
3. **A small rerunnable calculation runner and fictional input:** changing the stay length produces the corrected result without re-reading every plan or hand-editing the output. Reuse existing adapters and Decimal mechanics; no new general-purpose framework.
4. **`RESULT.md`:** what worked, any failed criterion, elapsed time, sources actually inspected and the smallest specific next integration task.

Success requires **a supported numeric example of each of the three methods**, a source or explicit hold for all six plan/scenario cells, the correction check, and rejection of ambiguous range/percentage arithmetic. If one plan's scenario is legitimately held, the table shows it; at least one actual plan must demonstrate each method. Missing material facts do not disappear into generic disclaimers.

The experiment proves whether the source-first approach can produce a useful, reproducible cost-component comparison. **It does not deliver a live chat feature, a personal annual-cost prediction or a released recommendation.** On success, the next small integration is connecting the structured result to the existing service/view under exact-purpose review, without redesigning the chat or expanding the data scope first.

## Time and work limits

The source intake above is completed preparation. The following clock starts when the calculation experiment is launched:

| Elapsed budget | Work |
| --- | --- |
| First 5 minutes | Bind the two offering IDs, exact premium source, relevant MPF rows and fictional scenario to existing adapters |
| Next 15 minutes | Implement/reuse the three narrow methods and resolve only their necessary source conditions |
| Next 5 minutes | Run the correction and negative checks; compare the arithmetic with the exact source inputs |
| Final 5 minutes | Save the readable comparison, JSON, runnable input and result/remaining-work note |

Maximum source inspection: **two targeted sections per plan** in already-retained carrier documents, in addition to the MPF rows and exact premium reference. Prefer existing valid review receipts. No renewed HPMS search, broad source crawl, repeated stopped-source access, optional-dental investigation, all-72 reconciliation, cloud work, new UI, paid model evaluation or production activation belongs in this experiment.

If the time or source-work cap is reached, save the current artifacts and mark the experiment **incomplete**, listing the exact unresolved field/condition and affected result. A report of blockers alone does not count as a successful comparison. Do not automatically extend the cap, give a substitute all-catalog estimate, or claim that this short experiment promises an entire MVP in 30 minutes.

## Preservation and acceptance

The [r1 scope contract](../recommendation-scope-2026-11-04-r1/PLAN.md) remains the authority for educational depth, conditional question meanings, independent candidate selection and material-evidence gates, except where this r2 explicitly replaces the immediate workflow, calculation priorities and experiment budget. Its broader catalog stages are later expansion work.

Preserve the 392,570 r9 obligations, 4,675 original first-plan obligations, accepted 535-entry r4 reference, 16 named missing items, source stops and all sealed work. Their research status is unchanged. A missing unrelated archival clause no longer blocks every product claim, while a material unresolved condition still blocks the dependent calculation or recommendation. D64 commercial independence and D73's separate report/evidence gates remain mandatory.

The current packet performs acquisition and planning only. Research outputs of the future experiment require their applicable independent interpretation/method review and exact-purpose acceptance before consumer use. Do not expose the raw downloaded workbook HTML or its SQL sheet as executable application content. Retain current permissions, saving/budget controls, :8890/:8891/:8893 guest stores and all protected runtime code.
