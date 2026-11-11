# Collier County Medicare data: gap closure plan

Prepared October 19, 2026. Planning baseline: the supplied [data inventory](../Collier%20County%20Medicare%20Data%20Inventory.md), the October 19 audit workbook, active release `naples-7a0b8eff1577df6e41eb`, and the current application code. All tasks below are proposed work; this document does not mark data gaps closed. Day 1 means the first working day of execution.

The objective is to let a Collier resident compare the two main coverage paths with traceable, current evidence: Original Medicare with optional Medigap and Part D, and Medicare Advantage. Conditional options such as SNPs and PACE must remain visible with their actual eligibility requirements. Every displayed cost, benefit, participation result and rule needs an identifiable source and an explicit verification state.

Start Medigap, drug-price and provider-source access immediately because access and source adequacy determine the schedule. In the same first week, close the smaller engineering gaps: stars, pharmacy packaging, legacy tool restrictions, source freshness and the market reconciliation. Then integrate each new layer only after its evidence can pass independent checks.

## Correct the baseline before measuring progress

| Inventory statement | Verified position and planning consequence |
| --- | --- |
| Only 38 plans can be compared | The current catalog and selected-plan comparison expose all **70 captured records**. The older evidence tools still restrict some deeper lookups to the original 38. Finish evidence coverage and remove those specific restrictions; do not rebuild catalog browsing. |
| 59 Advantage plans and 11 PDPs | Confirmed in the active snapshot: **23 non-SNP MA-PD + 9 MA-only + 27 SNP + 11 PDP = 70**. The SNPs are 15 dual-eligible, 9 chronic-condition and 3 institutional. Counts describe this captured release, pending live-market reconciliation. |
| Doctor participation unresolved for all 70 | Clinical network sourcing applies to the **59 Advantage records**, currently **18 contracts across eight parent companies**. The 11 standalone PDPs require pharmacy networks. Original Medicare acceptance and any Medigap SELECT networks need separate treatment. Parent-company membership alone cannot establish participation. |
| Package the other 30 pharmacy networks | Correct, but incomplete as a task. The workspace has 61 plan networks; the active bundle has 31. `demo_release.py` packages only original in-scope records, and `DemoTools.drug_evidence()` rejects excluded plans and caps requests at 38. Packaging, tool eligibility, indexing and tests must change together. |
| 190,096 PBP rows imply complete benefit detail | These are flattened field values across the 70 plans, including blanks and technical fields. Raw capture is complete for that snapshot; consumer benefit interpretation and independent validation are partial. Measure reviewed consumer fields, not raw row volume. |
| Stars missing | They are absent locally, but CMS lists a separate **2027 Star Ratings Data Tables** release dated October 8, 2026. Import that release. Ratings are reported at contract level, so use a reviewed contract/year join, preserving unrated states. [CMS downloads](https://www.cms.gov/medicare/health-drug-plans/part-c-d-performance-data), [technical notes](https://www.cms.gov/files/document/2027-tech-notes-2026-09-30.pdf). |
| Other local options unknown | AHCA's **July 2026** report lists **Hope PACE as operational in Collier**. This is evidence of an omitted local program, not proof that every resident qualifies or that the service area is unchanged for 2027. Verify the current service area and add an eligibility/referral path. [AHCA report, PDF page 5](https://ahca.myflorida.com/file/medicaid/JULY%202026%20Monthly%20PACE%20Report.pdf#page=5). |
| Find the quarterly file to obtain personal drug prices | The inspected monthly 2027 archive has no pricing table; the inspected quarterly archive is for 2026. A future 2027 public file must be checked for actual pricing grain and adequacy. A plan-level average unit cost does not establish an exact store-specific fill quote. Source discovery and personal-price capability are separate gates. [Existing source inspection](WORK_PACKAGE_3.md). |

Preserve the supplied inventory as the original assessment. Issue a revised status report from the new evidence rather than editing historical counts into a claim that the work was already complete.

## Sequence, staffing and decision points

Proposed roles: **data engineering** owns capture, joins, quality checks and audit exports; **application engineering** owns query tools, calculations and UI; a **Medicare data analyst/domain reviewer** owns field meaning, rule cases and independent review; the **product/supplier owner** owns coverage targets, access and commercial decisions. These are responsibilities to assign, not claims that anyone is staffed.

Planning assumption: two engineers, roughly half-time analyst support and scheduled domain review. Target a first reviewed Collier release in **6–10 weeks**, subject to actual source access and feasibility. One engineer will need a longer schedule. This is a planning range, not a commitment: revise it after the first three working days, and again after real supplier payloads arrive. Publisher release dates and supplier responses are external dependencies.

| Window | Main work | Required result |
| --- | --- | --- |
| Days 1–3 | G0 baseline; G4 Medigap access assessment; G5 drug-price feasibility; G6 provider endpoint discovery | A reconciled starting ledger, source/access findings, named owners and actual blockers. No waiting for a vendor before inspecting the public sources. |
| Days 4–10 | G1 catalog/evidence scope; G2 stars; G7 PACE/SHINE; begin G3 dated rules and annual tables | A candidate release with stars or explained unrated states, all 61 pharmacy networks usable, and corrected availability/eligibility language. |
| Weeks 2–4 | Complete core benefits; implement available annual/rule tables; inspect actual Medigap and pricing payloads; build first provider adapters | Reviewable source-shaped datasets and independent test receipts. Each inaccessible feed has a dated alternative or an explicit capability limit. |
| Weeks 4–8 | Quote and drug-cost calculations where supported; broaden provider coverage; integrate both coverage paths | Reproducible comparisons with exact inputs, dates, assumptions and unsupported factors shown. Partial results remain visibly partial. |
| Weeks 6–10 | G8 end-to-end review, audit workbook refresh, release verification and rollback rehearsal | A signed review of the exact candidate release and a coverage report stating which capabilities passed. Unmet capabilities remain open. |

Do not serialize the three difficult source workstreams behind Medigap. Start all three on Day 1. Do not spend several weeks waiting for public quarterly pricing before testing an authorized current-year commercial source.

## G0 — Establish the coverage ledger and release contract

**Owner:** data engineering. **Start:** Day 1. **Initial effort:** 2–3 engineering days. **Dependencies:** none.

1. Record the active release, source hashes, parser versions and audit extraction time. Reproduce the 70 catalog, 61 drug-bearing, 59 medical and 31 packaged-network counts. Keep the original 38/32 scope distinction as historical validation metadata.
2. Create one coverage ledger keyed by benefit year, county, exact contract/plan/segment and evidence layer. Medigap products/quotes, rules, formularies and provider participation need their own native keys; do not force them into a CMS PBP identifier.
3. Track **captured**, **normalized**, **available in app** and **independently reviewed** separately. Add source applicability, freshness, conflicts, owner, next action and closure evidence. A blank/unknown/unrated value is not zero, not ineligibility and not a failed parser by default.
4. Extend the existing immutable file/manifest approach. Keep raw artifacts and receipts plus narrow normalized read models. A database migration is not a prerequisite; introduce an index or SQLite read cache only if measured lookup performance requires it. Do not turn all 190,096 PBP values into a new relational model.
5. Refresh CMS catalog discovery in a candidate workspace, retaining the old receipt. Distinguish source publication, retrieval, effective period and review deadline. Rebuilding identical bytes does not renew a review. Address the overdue catalog review, DQ-014.
6. Put the audit export generator under a maintained, versioned command and make it consume the same release/coverage ledger as the app. New sources must appear in the next workbook with their raw values and lineage.

**Done when:** every baseline count replays, every open issue has an owner and next action, every displayed field traces to a source, and the same candidate release produces the app and audit counts. No consumer-facing data changes are required to close this foundation task.

## G1 — Reconcile all local offerings and finish core benefit evidence

**Owner:** data engineering + analyst; application engineering for tool scope. **Start:** first week. **Dependencies:** G0 identity and state conventions.

**Market coverage.** Compare the exact 2027 CMS identities and service areas with current Medicare.gov Plan Finder results for a documented set of Collier ZIP/county selections covering Naples, North Naples, Marco Island and Immokalee. Where a ZIP crosses counties, require the Collier selection; a ZIP name alone is insufficient. Save query inputs, timestamps and observed IDs. Compare both directions: missing local rows and captured rows absent from the independent result. Explain restricted, withdrawn, sanctioned, statewide PDP and regional offerings instead of silently deleting discrepancies. Use public observations or authorized access; do not assume a private Plan Finder API exists.

**Existing scope restrictions.** Replace original comparison-scope checks with evidence-capability checks in the deeper tools. A plan may be browsable and still lack a reviewed benefit or price. Extend the drug tools to all 61 matched Part D records, retain the nine explicit non-Part-D states, and keep SNP eligibility separate from whether its public evidence can be read. Review Regional PPO service-area and spending-limit semantics for the five additional non-SNP records.

**Consumer benefit matrix.** Define the initial field dictionary before decoding more PBP fields. Include premiums and Part B reductions; medical and drug deductibles; in/out-of-network and combined spending limits where applicable; primary/specialist, inpatient, emergency and skilled-nursing costs; referrals and prior authorization; dental, vision and hearing limits; travel/out-of-area conditions; and benefit eligibility restrictions. Preserve visit/day/benefit-period units, conditions and source paths. Use 2027 SB/EOC documents to interpret and corroborate the fields; one PDF can apply to several plans only with explicit identity and service-area evidence.

**Independent review.** Extend critical monetary/availability checks to all 70 records, with applicability-specific denominators. The existing Medicare.gov checks cover selected fields on 38 plans; carrier checks cover selected amounts on 16. Neither validates every field. Validate all newly displayed core fields or show an unresolved state; use a stratified deeper document review across carriers, plan types and benefits to investigate interpretation risks. An uncertain benefit cannot drive a preference score.

**Done when:** the live-market set has zero unexplained differences; all 70 records have an applicability/verification result for every exposed core field; all 32 formerly excluded records have a reviewed evidence-capability state; and restricted eligibility is displayed without declaring a person eligible. Any unresolved critical amount remains excluded from cost ordering and is retained in the discrepancy ledger.

**Evidence:** market reconciliation, field dictionary, normalized core-benefit matrix, plan-to-document map and cell-level validation report. Closes DQ-005/DQ-006 only for the fields actually reviewed, not full-policy accuracy.

## G2 — Import 2027 star ratings

**Owner:** data engineering. **Start:** first week. **Initial effort:** 1–2 engineering days. **Dependencies:** G0; independent of supplier access.

Capture the CMS data ZIP and technical notes with hashes. Inspect its actual schema and join ratings to the **24 captured contracts**, then project the appropriate overall/Part C/Part D values into local plans. Preserve rating year, publication/revision date, contract identity and CMS's unrated/suppressed reasons. Do not confuse 2027 ratings with recalculated 2026 ratings used for 2027 quality-bonus payments. The existing landscape blanks stay intact as raw evidence. [CMS release page](https://www.cms.gov/medicare/health-drug-plans/part-c-d-performance-data).

**Done when:** all 70 records have either an applicable sourced rating or the publisher's explained nonnumeric state, joins are unique at the inspected grain, and every distinct local contract result is independently checked. UI, source facts and workbook agree; missing ratings never become zero stars. Closes DQ-002's missing-source gap even if CMS legitimately does not rate a contract.

## G3 — Add Original Medicare costs, assistance and enrollment rules

**Owner:** analyst/domain reviewer + application engineering. **Start:** first week; complete in stages as publications become available. **Dependencies:** G0; used by G4 and G5 calculations.

**Annual cost tables.** Build effective-dated records for premium-free/premium-paid Part A, Part A benefit-period costs, Part B premiums/deductible/coinsurance, Part B and Part D IRMAA, and the relevant Part D annual parameters. Capture source year, effective dates, tax-year/filing-status basis and exceptions. Official 2027 A/B amounts have not been established by this planning pass: discover the actual CMS/SSA publication and import only published figures. Prepare the adapter and leave unavailable 2027 inputs explicitly pending. Trustees projections and 2026 amounts cannot fill a 2027 total. [Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs).

**Assistance.** Capture SSA Extra Help rules and Florida DCF's actual financial standards and policy text for QMB, SLMB, QI, QDWI and the relevant Medicaid groups. Store program-specific household definitions, income/resource treatment, exclusions, deemed eligibility and effective dates. New-year standards may become effective at different times. Use the effective rule for the requested date rather than inventing one annual January snapshot. Implement a preliminary eligibility screen with an application/referral route, not a government determination. [SSA](https://www.ssa.gov/medicare/part-d-extra-help), [DCF manual and Appendix A-9.1](https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual/).

**Enrollment and compatibility.** Implement independently sourced date rules for initial/general/annual/MA open enrollment and the specific special enrollment periods the product supports, plus Part B/Part D penalties. Medigap open enrollment and guaranteed-issue rights are separate rules from MA switching windows. Preserve unknown dates and exceptions; give a sourced next step when a case exceeds the supported rule set. Include compatibility checks so PDP, MA, Medigap and PACE are not summed into an impossible package. [Medicare joining rules](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan).

**Done when:** every supported rule has a source passage, effective period, required inputs and reviewer; boundary cases at, below and above income/date thresholds pass independent expected results; unknown inputs remain unresolved; and the UI distinguishes a preliminary screen from an award or enrollment guarantee. Test disability, retirement/employer coverage, moves, assistance changes and year transitions. Do not call this gap closed while required 2027 amounts remain unpublished or unverified.

## G4 — Add Medigap products, rates and buying rules

**Owner:** product/supplier owner for access; data engineering + analyst for evidence; application engineering for quotes. **Start:** Day 1. **Dependencies:** G0; G3 rules/cost inputs before combined totals.

**Recommended sourcing route.** Evaluate the already-inspected **CSG Actuarial feed/API first**, with direct carrier/OIR filings as independent checks and coverage-gap sources. Its public site advertises rate, product and underwriting data; current Collier coverage, consumer display rights, access, price and payload adequacy remain unconfirmed. Obtain an actual sample before choosing it. Assess an alternative supplier if it fails. [CSG offerings](https://www.csgactuarial.com/quoting/).

Use Florida OIR CHOICES and filings to establish the carrier/product universe and validate selected rates. CHOICES explicitly labels its rates illustrative, so preserve that label and keep it distinct from an applicant quote. OIR authorization to operate also does not establish that a carrier is selling every letter plan locally. [OIR CHOICES](https://floir.gov/consumers/choices-rate-comparison-search), [filing search](https://irfssearch.floir.gov/).

**Access decision by the end of Week 1.** The supplier owner needs actual coverage lists and success/error/conditional examples; required inputs; current/future effective dates; rate basis and fees; refresh commitments; consumer display, storage, transformation and audit rights; total commercial cost; and access requirements. No supplier pricing or delivery SLA has been established here. Prefer the feed that proves the needed coverage, rather than one that merely has the largest advertised carrier count.

**Data contract.** Keep carrier legal identity/NAIC, product/form and letter, high-deductible/SELECT variant, service/rating area, sale status, rate effective date and source validity. Preserve applicant/rating age basis, sex/tobacco and other source-required inputs, household discounts and conditions, rating method, underwriting/guaranteed-issue assumptions, fees and quote ID. Distinguish base rate, illustrative scenario, conditional quote, carrier quote, unavailable product and manual-quote requirement. Never present a conditional premium as guaranteed acceptance.

**Rules.** Capture standardized benefit definitions, C/F eligibility, Medigap open enrollment and guaranteed-issue situations, under-65 Florida access, SELECT conditions and pre-existing-condition treatment where relevant. Use current federal guidance and Florida statute/policy for the requested effective date; do not infer rules from a rate response. [Medicare buying guidance](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy), [Florida §627.6741](https://www.flsenate.gov/Laws/Statutes/2026/627.6741), [Florida consumer guidance](https://www.myfloridacfo.com/division/consumers/understanding-insurance/medicare-supplement-insurance-overview).

**Validation and done criteria.** Build a stratified synthetic test grid for ages 65/70/75/80, sex/tobacco variants where applicable, household-discount eligibility, under-65, open-enrollment/guaranteed-issue/underwritten cases and future effective dates. Reconcile every known locally sold carrier/product against the feed. Independently reproduce at least one available product/rate result per carrier and each supported variant; test failures, expiration and conditional responses. Record missing carriers and manual-quote paths explicitly. Complete Medigap price coverage requires every offered in-scope product to have a valid supported rate/quote route; a partial supplier feed is a milestone, not closure of DQ-011.

**Fallback if access is delayed:** ship sourced standardized benefits, Florida buying rules, clearly labeled illustrative rates where usable and a dated manual-quote route. Keep applicant-price comparisons unavailable for uncovered products. This improves the Original Medicare path but does not close the personalized pricing gap.

## G5 — Finish prescription evidence and personal drug costs

**Owner:** data/application engineering + analyst; supplier owner for external price access. **Start:** Day 1 feasibility; first-week packaging. **Dependencies:** G0/G1 for broad tool scope; G3 for assisted annual-cost cases.

**First unblock existing evidence.** Package and hash all **61** captured plan pharmacy files, plus shared formulary/cost tables. Update `demo_release.py`, the tool/API schemas and `DemoTools.drug_evidence()` so previously excluded SNP/regional records can return evidence. Bound request size deliberately and test pagination/batches instead of simply changing every occurrence of 38 to 70. Verify extracted-bundle queries offline for all 61; the nine MA-only records remain not applicable. Measure startup/memory/lookup latency with the larger package before adding an index. Closes DQ-010 after both packaging and query access pass.

**Resolve existing semantics.** Keep DQ-003/DQ-004 open for `H1889-026-000-2027` and `H5594-017-000-2027`: PUF premium $0.00 versus landscape Part D total $7.30. Retain gross/LIS-adjusted bases separately until authoritative evidence explains the difference. Resolve the quantity-unit issue using actual layout/carrier evidence before converting quantities. For DQ-008, distinguish filename, catalog period, publication and retrieval dates; an October 31 member token cannot establish future freshness. The monthly source may remain usable with a disclosed ambiguity, but do not mark the issue resolved without evidence.

**Price-source decision within three working days.** Run current CMS distribution discovery, inspect the actual benefit year, methodology and join keys, and assess whether the source supports the requested estimate. In parallel assess an authorized 2027 commercial/carrier quote source. Require exact product, quantity/unit, days supply, plan/segment, pharmacy/channel, pricing date, deductible/phase behavior and assistance support. A source limited to averages may support an explicitly labeled model, but cannot be relabeled a store quote. Medicare.gov is an independent comparison reference where accessible; do not assume a reusable API or republishing entitlement. [Monthly CMS source](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information), [quarterly CMS source](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/quarterly-prescription-drug-plan-formulary-pharmacy-network-and-pricing-information).

**Calculation.** Start with confirmed exact medicine/form/strength, quantity, fill schedule and store or mail order. Preserve NDC/RxCUI mapping/version, tier/restrictions, preferred status, dispensing fees, coverage phase and annual accumulators. Include year-correct deductible/cap, special insulin/vaccine rules and Extra Help only when the source and reviewed rules support them. Separate plan premium, estimated covered-drug out-of-pocket costs and noncovered purchases; explain start-month assumptions. Do not annualize a single copay or count Medicare Prescription Payment Plan timing as a reduction in annual cost.

**Validation and done criteria.** Require a join/applicability result for all 61 drug plans and independent cases spanning every captured formulary and distinct supported cost-rule family. Include generic/brand/specialty drugs, insulin/vaccines, 30/90-day supplies, retail/mail, preferred/nonpreferred/out-of-network states, deductible crossings, annual caps, assistance, partial years and missing/restricted drugs. Replay at least 30 complete synthetic scenarios against a dated independent estimate or reviewed expected calculation, including uncovered cases. Explain every material discrepancy; define rounding/tolerance from source semantics before accepting results. Coverage restrictions or unresolved quantities cannot silently become a priced fill. DQ-007 closes only for the plan/product/pharmacy scenarios the validated source actually supports.

**Fallback:** show dated coverage/restriction/pharmacy evidence and a Medicare.gov comparison route. Retain personal annual costs as unavailable when no adequate 2027 source exists; do not import 2026 prices as substitutes.

## G6 — Establish doctor and hospital participation evidence

**Owner:** data engineering + analyst; supplier owner for missing access. **Start:** Day 1 discovery. **Dependencies:** exact plan/network identity from G0/G1.

1. Map all **59 Advantage records / 18 contracts / eight parent organizations** to their actual issuer, plan network and 2027 directory. Start with public payer Provider Directory APIs and official directory pages; use authorized carrier/commercial data where the public result cannot identify the required plan/network/year. Treat the eight parent groups as discovery buckets, not eight guaranteed uniform API implementations.
2. Inspect real API capability statements, schema and pagination, then capture representative resources and network links before designing adapters. NPPES resolves identity/location; it does not establish participation. Retain provider NPI, practice location, organization/facility, specialty, source network and exact plan/year mapping, effective/termination dates, source retrieval and reported update dates.
3. Resolve a clinician at the requested practice site and hospital separately. A hospital agreement does not prove the anesthesiologist or physician participates. Keep accepting-new-patient and referral/prior-authorization conditions distinct from network membership. For Original Medicare, add a separate Medicare participation/assignment evidence route; a SELECT product's network is also separate.
4. Return listed/not listed in inspected directory, confirmed participation, conflicting, stale and unknown states with dated evidence. Absence in an incomplete search is not confirmed out of network. A directory entry alone must retain its date and confirmation limits. Define how current carrier/provider confirmation can be recorded when a decision depends on it.
5. Prioritize locally important hospitals and practices using actual user demand, then widen to the source's complete applicable network. Validate at least 30 exact provider/location/plan cases spanning all eight groups, including positive, negative, stale, conflicting, multi-location and hospital/clinician mismatch cases. Lack of verified negative evidence must remain unresolved.

CMS's FAQ describes updates within 30 days **of receiving directory information or a change**. This is not proof that each entry is reverified every 30 days, nor that each endpoint exposes the exact 2027 plan mapping needed here. Source adequacy must be demonstrated. [CMS Provider Directory API FAQ](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api).

**Done when:** every local Advantage record has a verified network-source mapping or an explicit unresolved-source exception; all tested participation assertions have replayable evidence; and a selected person's doctor is scored as a match only for an exact supported plan/location/effective period. Complete sourcing of all 59 is required to call the network-source gap closed. A successful one-carrier pilot or 30-case sample is progress, not blanket validation of all directory rows. Track source coverage separately from independently confirmed provider matches. Addresses DQ-009.

## G7 — Add PACE, other local option checks and counseling

**Owner:** analyst + application engineering. **Start:** first week. **Initial effort:** 1–3 working days for the first evidence/referral slice. **Dependencies:** G0; G3 for supported eligibility rules.

**PACE.** Start from the AHCA July 2026 Hope PACE record, then verify current CMS/state/operator identity, service-area ZIPs, effective date, eligibility conditions, enrollment assessment, costs and contact/referral route. A program can serve part of a county. Capture the actual 2027 position where published; do not infer every Collier address is served. Represent PACE as a conditional integrated coverage path, not an add-on premium to MA/PDP. [AHCA reports](https://ahca.myflorida.com/medicaid/recent-medicaid-presentations-and-reports.html).

**Cost plans/MSAs and other types.** Query the authoritative current landscape/service-area/program directories specifically for Collier and retain a dated positive or negative search receipt. If none are found, say which sources/year were searched; do not equate exclusion from the initial parser's taxonomy with local absence.

**SHINE.** Capture the official Collier counseling directory, phone/contact route, appointment information and last checked date. Make the referral visible for unresolved rules, assistance and coverage questions. [Official Collier SHINE directory](https://www.floridashine.org/Counseling-Sites/Collier.aspx).

**Coordination flags.** Add concise sourced routing for employer/union retiree coverage, VA/TRICARE for Life and existing older Medigap policies. These remain outside the public shopping catalog but must be recognized before suggesting a coverage change.

**Done when:** PACE has a current documented status and address-specific service-area route, each other plan type has a reproducible local search result, and SHINE contact information is usable. A referral does not certify eligibility or replace the missing program evidence.

## G8 — Integrate, independently review and maintain the release

**Owner:** application/data engineering; domain reviewer signs the stated review scope. **Dependencies:** whichever preceding capabilities are included in the candidate release.

Build deterministic comparisons from the reviewed layers. Keep Original Medicare alone, Original Medicare + Medigap + PDP, and compatible Advantage configurations distinguishable. Separate recurring premiums, income adjustments, assistance, drug estimates and medical utilization assumptions. A medical out-of-pocket maximum is not expected annual spending, and Original Medicare does not inherit an MA spending cap. Costs for uncovered services remain separate. A total requires every mandatory component for the requested year and scenario; otherwise show components and the missing inputs.

Keep the user's ordered priorities explicit. Score only factors supported for that exact result; display unscored factors and the full result set. Supplier/carrier commercial relationships and commissions must not change ordering. When only some plans have prices, do not label their ordering as the cheapest options across all local plans.

Use synthetic/public cases for development and audit exports. The current app writes visible conversations to local text files: adding medicine, income or quote questions does not make those inputs ephemeral. Resolve what is requested, logged and retained before real-user testing; keep personal quote inputs out of public source bundles and the audit workbook.

### Release evidence and acceptance

| Gate | Acceptance evidence |
| --- | --- |
| Inventory | Exact identity reconciliation for the entire claimed local market; explained additions, withdrawals and restricted options; Medigap/program coverage stated separately from CMS plan counts. |
| Source integrity | Hash/size/layout/identity checks, preserved raw states, unique joins at source grain, completeness deltas reviewed, no silent cross-year substitution. |
| Consumer facts | Every displayed field has source/date/conditions; independent reviewed checks for exposed core facts; critical unresolved conflicts cannot influence costs or matching. |
| Calculations/rules | Deterministic replay with explicit scenario inputs, source versions and expected outputs; date/year/subsidy/quantity/phase boundary cases; incomplete scenarios visibly incomplete. |
| Provider and pharmacy | Correct plan/network/location mapping, full query pagination, dated states, no participation assertion derived solely from NPI or carrier brand. |
| App behavior | Browse/compare the full captured set; all 61 drug plans usable; restricted eligibility remains conditional; unsupported factors remain unscored; same facts in chat, cards and export. |
| Portability | Build and verify a new immutable candidate; replay selected cases from the extracted bundle without workspace caches; preserve the prior release and rehearse rollback. |
| Review | Named reviewer, date, exact release hash, fields/cases covered, unresolved issues and consumer limitations. Engineering checks alone do not close DQ-012. |

Run appropriate existing suites (`test_cms_slice`, `test_prescription`, `test_naples_mvp`, `test_demo_release`, and conversation tests when tool outputs change), plus independent source/calculation replays for new capabilities. Add tests for real interpretation and join failure modes, rather than tests that merely reproduce the parser. Rebuild review receipts against the changed basis; never extend old approval by changing a timestamp.

### Refresh and operations

These are proposed monitoring targets, not claims about publisher update guarantees. Assign an operator and refine them from observed source behavior.

| Layer | Discovery/refresh target | On change or failure |
| --- | --- | --- |
| Landscape, PBP, stars and carrier documents | Daily discovery during fall enrollment and known correction windows; weekly outside them unless the source requires more | Stage changed bytes, profile count/schema/value deltas, review affected facts and issue a new immutable release. Keep prior evidence. |
| Formulary/pharmacy | Check publication availability weekly; ingest each applicable monthly release and material corrections | Reconcile all 61 identities and changing formularies/networks; report additions/removals and stale coverage. |
| Drug prices and Medigap rates | Follow actual feed SLA, quote validity and effective dates; discover each relevant quarterly public release | Expired/unsupported quotes leave cost ordering; pending future rates cannot replace currently effective rates. |
| Provider directories | Target daily change detection where supported; recapture at least weekly for the first pilot and recheck decision-critical queries | Display retrieval and reported update dates; retain unknown source age. Apply a reviewed freshness policy without claiming a universal 30-day verification guarantee. |
| Costs, IRMAA, assistance and enrollment rules | Weekly publication checks around annual changes; monitor authoritative rule changes and special enrollment notices | Version by effective date; regression-test boundary cases; schedule announced future changes. |
| PACE and SHINE | Monthly review and recheck before time-sensitive referral | Update dated service/contact facts, preserving the historical capture. |

On failed refresh, keep the last verified bytes with an explicit age/status. Remove stale facts from calculations or matching when their reviewed validity policy requires it. Alert on unexpected identity losses, join failures, schema changes, growing missingness and new monetary conflicts. Use an isolated candidate build so discovery cannot overwrite the active release.

## Coverage of all 15 inventory layers

| Inventory layer | Work package | Closure evidence |
| --- | --- | --- |
| Original Medicare A/B | G3, G8 | Published effective-year tables and independently checked cost scenarios. |
| Advantage plan list | G1 | Bidirectional county/year identity reconciliation and service-area receipts. |
| Advantage benefit detail | G1 | Reviewed core field dictionary/matrix and exact plan-document evidence; remaining raw fields remain raw. |
| Standalone Part D list | G1 | All current statewide PDP identities reconciled and applicable fields checked. |
| Formularies | G1, G5 | All drug plans queryable, exact versions/restrictions, unresolved semantics handled. |
| Drug prices | G5, G3, G8 | Adequate 2027 source, reproducible personal scenarios and explicit coverage limits. |
| Pharmacy networks | G5 | All 61 captured plan networks in the bundle and usable through tools/API. |
| Doctor/hospital networks | G6 | Plan/network mappings and dated exact-provider evidence; source and match coverage measured separately. |
| Stars | G2 | Appropriate contract/year ratings or documented unrated states for all records. |
| Medigap plans/prices | G4 | Reconciled local product universe and valid rate/quote routes with recorded conditions. |
| Medigap buying rules | G3, G4 | Current federal/Florida rules, eligibility inputs and reviewed boundary cases. |
| Help programs | G3 | Effective-dated SSA/DCF program rules, preliminary screens and application routes. |
| Enrollment/penalties | G3 | Supported date rules, exceptions, compatibility and independent expected outcomes. |
| Other plan types | G7 | Current PACE evidence plus dated searches for Cost/MSA/other offerings. |
| Local counseling | G7 | Verified official Collier SHINE referral and review date. |

## Disposition of the existing audit issues

The baseline workbook remains historical. The next export should retain these IDs and add closure receipts, rather than deleting resolved rows.

| Audit issue | Action and closure condition |
| --- | --- |
| DQ-001: national landscape-only PBP | Keep the Virginia identity `H3931-143-000-2027` open in the national ledger; inspect corrected CMS releases and retain the existing 16-row Part D corroboration. It does not block Naples capture, but cannot disappear from national completeness reporting. |
| DQ-002: stars | G2 source import and contract-level reconciliation; unrated reasons remain valid states. |
| DQ-003 / DQ-004: premium conflicts | G5 source-basis clarification for the two exact SNPs; keep both observations until reviewed. |
| DQ-005: Medicare.gov sampling | G1 expands checks to all local plans for declared core fields; record validation scope per cell. |
| DQ-006: carrier sampling | G1 expands exact plan/document corroboration; do not label all PBP fields independently verified. |
| DQ-007: drug prices | G5 source adequacy and independently replayed supported scenarios. |
| DQ-008: prescription dates | G5 authoritative date interpretation or corrected source; retain explicit ambiguity until then. |
| DQ-009: clinical participation | G6 separate 59 medical-plan mappings from 11 PDP nonapplicability; exact matches require their own evidence. |
| DQ-010: packaged networks | G5 all 61 networks plus runtime access and extracted-bundle verification. |
| DQ-011: Medigap | G4 real source payloads, product coverage reconciliation and validated rate/quote routes. |
| DQ-012: qualified review | G8 documented review of the exact release and supported consumer claims. |
| DQ-013: national field variation | G0/G1 retain offering-grain variation and explicit representative-field rules; first-offering values cannot silently represent differing county observations. Track the 148 affected identities and regression-check local projections. |
| DQ-014: catalog review overdue | G0 new discovery receipt, actual change assessment and a review deadline tied to inspected evidence. |

## First execution queue

1. Reproduce the baseline counts and create the capability ledger, preserving DQ-001–014.
2. Inspect the published 2027 stars artifact and prepare the contract/year mapping.
3. Expand pharmacy packaging and remove the original-scope prescription gates together; verify all 61 from an extracted candidate bundle.
4. Start the bidirectional Plan Finder/Collier identity reconciliation and core benefit dictionary.
5. Run the 2027 drug-price feasibility assessment; record public/commercial source adequacy and access findings by Day 3.
6. Prepare Medigap supplier evaluation using actual sample requirements and the OIR product-universe comparison; make an evidence-based source decision in Week 1 if payloads/access are available.
7. Discover and test directory/network mappings for each of the eight Advantage parent groups; record missing plan/year links before building a general adapter.
8. Capture current Hope PACE service-area/eligibility information and the official SHINE referral.
9. Prepare effective-dated annual cost, assistance and enrollment schemas with independent rule cases; import only actually published values.
10. Build the first candidate release and regenerate the audit workbook with separate capture, app-availability, review and freshness measures.

The weekly review should report coverage fractions at the right grain: reconciled offerings / expected offerings; reviewed core cells / applicable core cells; drug plans queryable / 61; mapped medical plans / 59; supported Medigap products / independently identified products; and passing scenarios / independently reviewed scenarios. Update denominators when the source market changes. No combined percentage should hide a missing coverage path or a critical unresolved price/network dependency.
