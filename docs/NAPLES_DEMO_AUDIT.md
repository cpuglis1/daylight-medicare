# Naples demo audit: implementation, data quality, and integrations

Reviewed October 17, 2026. Scope: this workspace against the original v1.2 build plan and the current plan of attack. UI design is excluded. Findings distinguish working code, documented intentions, independently observed issues, and recommended work.

## Assessment

**Codex built a credible, reproducible public-data foundation. It has not built the Medicare research assistant described in the plan.** The strongest work is source integrity, identity matching, preservation of uncertainty, and real-data testing. The main weakness is the distance between that engineering evidence and questions a Naples resident will actually ask: “Can I keep my doctor?”, “Does this cover my exact medicine?”, and “What would I pay?”

Keep the ingestion and evidence work. Narrow the next milestone to a source-grounded, facilitated Naples research chat. Full personalized ranking, Medigap quoting, saved caregiver accounts, and enrollment do not all have to precede that demonstration. They do have to precede claims or actions that depend on them.

The backend itself is reasonably small: seven Python scripts totaling 1,846 lines, plus 674 lines of tests. There is no microservice fleet or speculative database to remove. The simplification opportunity is primarily **scope, sequencing, repeated review paperwork, and the future product surface**, rather than rewriting the data foundation.

## What I actually verified

- Read the current [plan](../PLAN_OF_ATTACK.md), [execution ledger](EXECUTION_STATUS.md), work-package findings, source registries, all seven active scripts, and their tests. Compared them with the original [build plan](../medicare-project-2026-10-17-v1.2/medicare-company-architecture/BUILD_PLAN.md) and behavior contracts. The archived synthetic application is historical material, not the active implementation.
- Ran the active suite under Python **3.14.7**: **58 tests passed in 31.227 seconds**.
- Ran all four delivered verifiers: CMS slice, read model, prescription evidence, and reference evidence. All passed.
- Rechecked all **44 files** in the original bundle manifest: all sizes and hashes matched.
- Recomputed Naples composition from the delivered records, measured actual prescription-query latency, and reproduced two uncovered behavior defects using temporary files. Original source caches were unchanged.
- Consulted current primary sources for local hospital changes, provider-directory APIs, drug data limitations, Medicare educational material, and supplier offerings. No vendor account, agreement, outside message, or integration was created.

See the [verification receipt](../cms-slice/reports/audit-2026-10-17.json). Passing these checks establishes implementation consistency; it does not independently certify every benefit, current network relationship, or personal coverage outcome.

## Delivery against the plan

| Planned capability | What exists | Audit judgment |
|---|---|---|
| WP0–1: inspect real sources and query an actual market | National landscape/PBP inspection; three county queries; exact identity/geography joins; full Naples raw export; discrepancy reports | Strong execution. Engineering slice delivered; domain interpretation and release operations remain bounded. |
| WP2: minimal read model and comparison | File-backed catalog/API; 70 source records; 38 comparison records; 32 exclusions; five carrier records checked | Delivered for local review. Independent field checking is much narrower than market coverage. |
| WP3: prescription evidence | Actual 2027 formulary, restrictions, cost-sharing schedules, and pharmacy-network captures; exact-code lookup | Substantial partial completion. General medicine resolution, quantity interpretation, personal pricing, and broader domain cases remain unfinished. |
| WP4: Medigap quotes | Public source/vendor reconnaissance | No quote integration or quote receipts. |
| WP5: clinical provider verification | NPPES identity samples and one pharmacy identity/network example | No clinical provider-to-plan-to-location integration. Pharmacy work does not complete this package. |
| WP6: profiles, rules, calculations, ranking | Written contracts and dependencies | Not implemented. Source identity order is not a suitability ranking. |
| WP7: conversational research | Intended workflow and archived synthetic code | No active model adapter, conversational tool loop, or grounding evaluation. |
| WP8–10: licensed purchase, servicing, pilot | Plans, boundaries, and review protocol | No working carrier transaction, operational handoff, customer study, or policy outcome. |

The current execution ledger is generally candid about these limits. Its language about “completed slices” should not be read as completion of the larger prescription or consumer-release packages.

### Actual Naples coverage

| Population | Count | Meaning |
|---|---:|---|
| All matching landscape records | 70 | Source universe captured for this release and county, including statewide PDP offerings |
| Current comparison scope | 38 | **20 MA-PD, 7 MA-only, 11 PDP** |
| Excluded SNP records | 27 | Not supported by the comparison experiment; this is not a finding that a person is ineligible |
| Other excluded records | 5 | Non-SNP Regional PPOs excluded by the configured plan-type scope |
| All records matched to Part D data | 61 | Includes excluded records; the other nine are MA-only |
| Part D records within the 38-record scope | 31 | The relevant batch size for a medicine comparison in the current scope |
| Carrier-corroborated records | 5 | All from Florida Blue/GuideWell; twelve particular monetary facts checked |

The 38 supported records span **eight parent organizations**. The carrier check therefore does not establish cross-carrier correctness. Also, **38 is not the complete non-SNP MA/PDP market in the captured data**: another five Regional PPO records exist. Keep that limitation explicit or review and add those records before making a broader completeness claim. Do not add them merely by removing a filter; verify their geography and field interpretations first.

## What Codex did well

1. **Used actual data instead of extending the synthetic prototype.** The new implementation preserves the original bundle and does not use fictional plans to claim an integration works.
2. **Built unusually good traceability.** Exact archive hashes, member identities, source ordinals, raw cells, and field mappings let a reviewer replay an answer to its input. This is valuable infrastructure for a trustworthy chat product.
3. **Handled identities and geography carefully.** Contract/plan/segment/year remain distinct; leading zeros are preserved; statewide PDPs are handled separately; Collier FIPS `12021` is not confused with SSA county `10100`.
4. **Preserved meaningful uncertainty.** Zero, missing, inapplicable, unavailable, and rejected values remain different. A missing formulary row is not automatically noncoverage. An NPI is not presented as physician network participation.
5. **Found real source problems.** Encoding/layout differences, conflicting premium bases, quantity ambiguity, and date tokens were retained instead of silently repaired. Cost-sharing types and percentage units are handled explicitly.
6. **Tested consequential failures.** The suite covers wrong plan/year/county, swapped PDF columns, corrupted inputs, missing evidence, and post-startup capture changes. Those checks matter more than cosmetic tests.
7. **Avoided premature infrastructure and invented vendor access.** Files and a small Python adapter are appropriate at this scale. The absence of a quote, network, or enrollment adapter is honestly documented.

## Where improvement matters most

### 1. Rebalance effort toward answer coverage and independent correctness

Most validation proves that the program reproduces CMS bytes correctly. That is necessary but different from proving the interpretation is correct, complete, and current enough for a person’s question. The independent carrier work covers twelve amounts on five records from one organization; the independently inspected drug example is essentially one product across two related plans.

For the next release, make a **plan-by-field quality matrix**: plan identity, field, source/year, interpretation/units, independent comparison, conflict, reviewer, and disposition. Start with every fact the chat will actually answer. For a 38-record catalog, checking the published premium, drug deductible, medical limit, category, and geography across all supported records is a reasonable bounded task. Check benefit-specific conditions as well as headline amounts. Until completed, expose narrower supported answers or a clearly defined reviewed subset.

Do not count a second script reading the same source as independent domain corroboration. Use carrier documents or an independently inspected Medicare.gov result where appropriate, with exact plan/year/geography and recorded dates. Differences may reflect source timing; preserve both observations and adjudicate them.

### 2. Make the evidence local: doctors and hospitals are the largest Naples gap

NCH currently states that Cigna/HealthSpring and Wellcare Medicare Advantage participation will end **January 1, 2027**, while 2026 care is unaffected. This is a concrete question the demo must handle with effective dates, not generic carrier descriptions. [NCH change notice](https://nchmd.org/maupdate/).

NCH’s contracted-payer page also distinguishes the hospital from the medical group, warns that carrier contracts do not cover every product, and lists different Humana participation for those settings. A carrier-level “accepted” flag would lose these distinctions. [NCH contracted plans](https://nchmd.org/patients-and-visitors/contracted-insurance-plans/).

Build a small local evidence set first: NCH hospital locations and medical group separately, Physicians Regional, and the practices actually named by participants. Record **exact provider/facility, address, plan/network, relevant service or organization scope, effective period, source, checked date, and conflict state**. Hospital participation, individual clinician participation, and accepting new patients are separate facts. Include seasonal/out-of-area care questions as unknown unless supported.

A dated public notice can answer “What has NCH announced?” It does not by itself answer “Is my exact doctor in my exact plan?” Manual reviewed evidence is acceptable for a small demo; universal network automation is not a prerequisite for showing factual local research. Unsupported exact matches must remain unresolved.

### 3. Turn prescription capture into usable medicine and pharmacy lookup

The active endpoint accepts exact NDC11 or RxCUI. Its conversational reference context contains four saved Trulicity strength/form candidates and one pharmacy example. That is a useful proof, not general medicine search.

Needed next:

- Resolve a typed medicine name through an actual vocabulary source into strength, form, brand/generic, and packaging candidates. Require explicit product confirmation. NLM’s [getDrugs API](https://www.lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.getDrugs.html) is an existing starting point.
- Resolve a pharmacy name/location into the exact store and NPI. The saved Naples city query is not a complete, current Collier pharmacy directory.
- Capture quantity **with a unit** and days supply when the answer depends on them. Preserve source proxy NDC versus the actual dispensed product distinction.
- Batch a medicine list across supported plans, returning per-drug restrictions, unresolved identities, and absent evidence. Handle supplemental and indication-specific cases before making negative coverage conclusions.
- Independently check examples across carriers: plain generic, expensive brand, prior authorization, step therapy, quantity limit, insulin, ambiguous strength, and missing basic-formulary evidence.

The unresolved CMS quantity `2` versus carrier `4 pens` over 28 days should block a quantity conclusion for that example, not every medicine answer in the product.

### 4. Do not confuse cost-sharing schedules with prices

The captured 2027 data has no usable personal drug-pricing integration. It cannot answer “Which plan is cheapest for my medicines?” A copay/coinsurance schedule does not supply every input needed for a fill or annual estimate. CMS describes its quarterly pricing file as **plan-level average monthly unit costs**; even a correct-year version would not automatically establish an exact pharmacy quote. [CMS quarterly methodology](https://data.cms.gov/sites/default/files/2025-10/cf6b8476-ca42-48c6-9fc4-281b08c6ea87/Methodology-SPUF-2026.pdf).

For a factual demonstration, keep personal price and savings answers unavailable and help the user identify what needs checking. For a useful personal cost comparison, obtain a licensed, year-correct plan/drug/pharmacy pricing or estimation feed, inspect its assumptions, and validate receipts against independent examples. Include quantity/days, deductible applicability, benefit phases, start month, and subsidies where supported. Define what is excluded from the estimate.

Do not use a 2026 file as 2027 evidence. Do not imply a full medical-plus-drug annual cost from premiums, MOOP, and one medicine’s schedule. Comparing staying versus switching also needs an identified current plan and the relevant current/next-year evidence.

### 5. Use more of the captured benefits only when a real question needs them

All 70 Naples PBP payloads are retained, but the active PBP mapping exposes eight identity/status/characteristic fields. Medical cost-sharing sections are not yet a validated answer engine.

Select a small question set: primary care, specialist visits, hospital/outpatient care, referrals/prior authorization, out-of-network conditions, and relevant supplemental benefits. Validate only the fields and qualifications needed for those questions against the exact Summary of Benefits/Evidence of Coverage. Keep service setting, day limits, network scope, and exceptions attached. A dental allowance without its conditions is not a useful answer.

Ratings also need a reviewed rating year and scope before conversational use. Existing raw ratings are not independently certified by the twelve monetary checks. Do not decode opaque PBP values from their names or normalize the whole PBP schema merely because the JSON is available.

### 6. Add freshness and release operations, not just hashes

The current `fetch` commands recover **one pinned release**. They are not a mechanism to discover, review, and publish new releases. Existing verification has no time-based stale-data gate. A perfectly matching hash can still represent an outdated answer.

Add a small release process: discover candidate sources; preserve original bytes; compare plan membership, critical fields, restrictions, and layouts; review changes; publish an immutable release directory atomically; retain rollback. Track benefit year, publication/update date, retrieval time, effective period, and next review separately. Set review intervals by source and claim, with immediate review for known network changes. Check relevant sources before a demo session.

CMS explicitly warns that these public files may lag Medicare Plan Finder and that release timing is not guaranteed. The use agreement also prohibits misleading use. Record the applicable permissions and obligations for the actual demo rather than treating public access as either blanket permission or an automatic prohibition. [CMS agreement](https://data.cms.gov/sites/default/files/2023-10/4eeb19e1-525b-4a4e-9766-b33ff084fc5c/AGREEMENT-FOR-USE.pdf).

The raw/cache directory is ignored and includes roughly 4.4 GiB of data. Preserve permitted pinned artifacts in a durable artifact store or a verified offline demo bundle. Re-fetching an old mutable RxNorm/NPPES response is not a reliable backup strategy. The directory also lacks a dedicated Git repository: Git currently resolves to `/Users/cep4u`. Establish a project-scoped repository and avoid staging the home directory.

### 7. Two reproducible defects need focused fixes

**A. Alternate prescription caches are read without verifying those same bytes.** In [prescription.py](../cms-slice/scripts/prescription.py), lines 440–442, the query command runs `verify(config)` against the default cache, then reads `args.cache`. In a temporary copy, I changed one actual formulary row’s prior-authorization flag from `Y` to `N`. The CLI returned exit code **0** and the altered `N` while the default cache remained intact.

Fix the query path to verify the cache it will read and bind it to the correct release manifest. Add a regression case for an altered alternate cache. The HTTP wrapper has separate per-lookup hash checks; this finding does not demonstrate that the normal HTTP endpoint accepts the altered cache.

**B. A pharmacy argument turns a valid MA-only result into a misleading integrity error.** [research.py](../cms-slice/scripts/research.py), lines 167–175, requires a plan-specific pharmacy capture before the underlying query can return its non-Part-D state. `H5434-042-000-2027` returns `not_applicable_non_part_d` without a pharmacy; with NPI `1609197854`, it raises “Prescription capture unavailable/changed; rebuild and review.” That plan correctly has no Part D pharmacy capture.

Validate the plan and source applicability first, then verify only relevant captures. Add that case at the HTTP boundary. Neither issue is covered by the passing 58 tests. This audit records the defects; it does not change implementation code.

### 8. Adapt the evidence contract before connecting a model

The catalog file is **944,235 bytes**. A representative prescription response serializes to **21,334 bytes**, including repeated source-table descriptions. These are useful audit exports, but poor default model-tool payloads. The example query also returns insulin schedules for a non-insulin medicine, with a qualification that classification is unresolved; those schedules must not become applicable-price facts in a chat answer.

Return compact, typed facts, scope, uncertainty, and evidence IDs from normal tools; fetch detailed source material only when needed. Keep the full audit exports. Bind answer receipts to the relevant catalog, formulary, provider, education, and model/tool versions. The current read `snapshot_id` hashes the upstream catalog alone; it is not a complete future answer identity across those sources.

On this machine, a drug/plan/pharmacy lookup took **0.192–0.198 seconds**; the same public medicine across all 31 supported Part D plans took **5.91 seconds serially**, excluding model/network time. Single lookups are adequate for a facilitated demo. For medicine-list comparisons, load or index the small selected captures once and batch lookups before adding infrastructure. This is a local observation, not a production benchmark.

## Integration choices: what is actually needed

| Capability | Smallest useful demo approach | Needed for stronger personal comparisons | Current access/evidence |
|---|---|---|---|
| Plan catalog and selected benefits | Reuse existing CMS intake; broaden independent checking; add only reviewed answer fields | Update/diff/rollback process and wider benefit/rule validation | Working pinned CMS path |
| General Medicare education | Small reviewed collection from current Medicare.gov material, with year/topic/page references | Dated rules for any eligibility or switching conclusion | No active educational knowledge integration; start with [official publications](https://www.medicare.gov/publications) |
| Medicine identity | Actual name-to-product resolver and explicit confirmation | Robust multi-drug identity, quantity, and exception handling | Saved NLM examples; no general resolver endpoint |
| Pharmacy identity/network | Store search and exact NPI against existing dated plan-network rows | Current store/channel/preference confirmation and price linkage | One checked store; bulk published networks captured |
| Clinical provider/hospital access | Reviewed local notices/directories and exact manually supported cases; unresolved elsewhere | Exact provider/location/network/plan/year evidence plus conflicts and rechecking | No active clinical-network adapter |
| Personal drug costs | Leave unavailable in first factual demo | Contracted current-year pricing/estimation feed and validated calculations | No feed or personal estimate |
| Medigap | Explain structure using reviewed education; no premium or acceptance promise | Actual rate/quote inputs, discounts, effective date, underwriting/GI assumptions, and quote receipts | Vendor reconnaissance only |
| Current coverage | User identifies exact plan if relevant; ask rather than infer | Supported current-year baseline and verified coverage facts | No private profile or baseline integration |
| Chat/model | One server-side adapter calling bounded read tools | Grounding, numerical accuracy, conflict handling, and ranked-snapshot fidelity when ranking exists | Not implemented in active slice |
| Saved/private research | Session-only public examples can demonstrate the workflow | Minimal consented storage, authentication, subject access, retention/deletion, and caregiver grants if sharing is offered | Not implemented |
| Licensed handoff/enrollment | Explain or demonstrate a clearly identified manual process only if staffed | Actual appointed-agent workflow and approved submission/status channel | No operational integration |

### Provider-source discovery should precede buying a universal feed

CMS documents public provider-directory APIs for affected payers, including MA organizations; developer registration/API keys may still be required. Inspect actual endpoints for the carriers in scope before assuming all network evidence requires a paid intermediary. [CMS provider API FAQ](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api).

Also investigate the [CMS National Provider Directory developer service](https://directory.cms.gov/developers). During this audit, its `/fhir/metadata` returned HTTP 200, FHIR **4.0.1**, and resources including InsurancePlan, PractitionerRole, OrganizationAffiliation, and Location. Sample InsurancePlan and Location reads returned resources. The sampled InsurancePlan had no direct `identifier` field. **No exact 2027 Collier plan/network mapping or completeness was proven.** This is a concrete discovery task, not a claim that CMS has already solved the integration.

An adapter should be accepted only after demonstrating the exact identity bridge and real positive, negative, ambiguous, stale, and conflicting cases. No-result is not automatically out-of-network. Preserve conflicting payer/provider observations rather than flattening them into a single boolean.

### Start two supplier conversations, without designing against marketing copy

- **Drug pricing/shopping:** [ConnectureDRX](https://www.connecture.com/apis/) publicly describes Medicare shopping APIs, dosage-specific pricing, and cost estimates. Request a 2027 Florida sample with exact plan/drug/pharmacy inputs, estimate assumptions, coverage breadth, commercial restrictions, and permitted AI display/use.
- **Medigap, if included in the demo promise:** [CSG Actuarial](https://www.csgactuarial.com/quoting/) publicly offers rates, underwriting data, and API access. Request actual Florida samples, required rating/applicant inputs, discount treatment, effective dates, error/conditional responses, and what remains subject to carrier acceptance.

These are candidates for diligence, not selected vendors or assurances of startup access, cost, coverage, or delivery time. For either supplier, obtain an actual payload, rights to the intended consumer use, carrier/geography coverage, update cadence, sample discrepancies, and failure behavior before writing the adapter. A manual qualified review can support an early facilitated demonstration; it cannot be presented as a live automated integration.

Blue Button, EHR, claims ingestion, CRM, and carrier enrollment connections are not prerequisites for the first research demonstration. Add personal data import only when manual entry is a demonstrated barrier. [Blue Button](https://bluebutton.cms.gov/developers/) is a beneficiary claims-data API, not a substitute for a future-year shopping/pricing feed.

## The shortest path to getting this in Naples residents’ hands

Recommended initial promise: **“Ask questions about published 2027 Collier Medicare options, specific formulary evidence, and dated local provider notices; see sources and unresolved checks.”** Include direct retirees and caregivers. Confirm residence/county and intended coverage year; do not infer eligibility from a Naples mailing address or family relationship.

| Order | Work and owner | Evidence that closes the task |
|---|---|---|
| 1 | **Founder + insurance/domain reviewer:** write a one-page demo scope and answer inventory | Exact geography/year/categories, supported questions, exclusions, source-use/activity review, and a person accountable for corrections. No attempt to complete the whole company architecture. |
| 2 | **Engineering:** fix the two reproduced defects; preserve the existing source pipeline | Both regression cases pass; query reads the verified release; no source facts silently change. |
| 3 | **Data + domain reviewer:** build the plan/field quality matrix and local hospital evidence | Broader carrier checks; explicit decision on five Regional PPO exclusions; dated NCH evidence with hospital/group/product scope; unknowns isolated to affected claims. |
| 4 | **Engineering + data reviewer:** implement general medicine/store resolution and compact batched read tools | A person can name an arbitrary supported medicine/store, disambiguate it, and retrieve exact evidence; realistic restriction and missing-data cases independently checked. |
| 5 | **Domain reviewer + engineering:** add reviewed education and a thin chat adapter | Source-grounded answers for the declared inventory; citations, version/uncertainty propagation, clarification, and honest limits. No full ranking engine or saved-account system required for factual research. |
| 6 | **Engineering/operations:** package a reproducible demo release | Durable source artifacts; one-command start or small hosted service; version visible in receipts; stale-source/outage behavior; rollback; server-side model secret, basic abuse limits, and redacted logs if hosted. Do not expose the loopback review server directly as a public service. |
| 7 | **Founder + independent reviewer:** run facilitated sessions with roughly 8–12 local retirees/caregivers | Consented sessions, actual questions and source support, corrections, unresolved needs, and observed time to a useful answer. This is qualitative learning, not statistical accuracy certification. |

Supplier and public-provider-API discovery can run alongside steps 2–5. If participants need price-based choices, prioritize the real pricing integration next. If they primarily need doctor/hospital continuity, prioritize exact local network evidence. Make that decision from observed needs, not the original package numbering.

For personal prescriptions or saved conversations, add the necessary data controls before collection: minimum necessary facts, clear purpose, server-side secrets, restricted access, defined retention, and no health details in generic analytics or query URLs. A session-only demonstration with public examples avoids building account/sharing infrastructure before its value is tested. Caregiver sharing, when offered, needs actual subject-level authorization; it must not be approximated by a family-role checkbox.

### Demo acceptance checks

Use a small held-out question set reviewed by someone other than the implementer. Cover wrong year/county; the five unsupported Regional PPOs; SNP scope versus personal eligibility; zero versus unknown; correct premium basis; ambiguous medicine/quantity; prior authorization; absent basic-formulary evidence; pharmacy preference; the NCH 2026/2027 change; hospital versus doctor; stale/conflicting directories; and a source/model outage.

Every numerical and network answer must either have the required dated evidence or explicitly remain unresolved. No known consequential error should remain enabled. Check that the chat does not turn the twelve corroborated amounts into “all plans verified,” invent drug prices, apply insulin schedules to unrelated medicines, or present a PDP as interchangeable with a complete medical coverage package. Record refusals as well as answers so a system that refuses everything does not appear successful.

When ranking is later introduced, add the original plan’s deterministic criteria/order/membership and compensation-invariance checks. For the factual demo, source-order listings and explicit user-requested field comparisons are sufficient if described accurately.

## What should not block this limited demo

- The missing Virginia PBP payload: Naples has all 70 matching payloads. Keep the investigation, but move it off the Naples critical path.
- The two premium disagreements on excluded D-SNPs: retain them and do not use the disputed values for unsupported conclusions. They need resolution before expanding into those cases.
- Decoding `Submitted` and every nested PBP status: omit unsupported status claims instead of waiting for a complete code dictionary.
- A live Medigap quote feed, if the demo makes no personalized Medigap rate or cross-structure cost claim.
- A 2027 personal drug-price source, if personal price/savings/ranking is explicitly outside the demo. It becomes necessary as soon as those questions are promised.
- A national network database, accounts/caregiver sharing, an application workflow, finance/commission systems, CRM, advanced analytics, national geography, more UI, or rewriting Python into a larger stack.

The next investment should be **broader independent fact checks, local provider evidence, medicine resolution, and a small grounded chat integration**. Preserve the strong evidence foundation while replacing the full-company dependency chain with this bounded demonstration path.
