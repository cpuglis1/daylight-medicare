# Work package 1: real CMS query and evidence report

Implementation and inspection: October 17, 2026. This delivers a working engineering slice and review evidence. It does **not** close domain validation, source-rights or consumer-publication gates.

## Query and source scope

Question: **Which records occur in the pinned 2027 landscape for New York County, NY, including its statewide PDP records, and what published premium/deductible/MOOP values and matching PBP identity evidence do they contain?**

The experiment includes ordinary `MA`/`MA-PD` categories with `HMO`, `HMO-POS` or `PPO` types, plus `PDP`. It retains every other matching landscape row as an exclusion with reasons. This deliberately excludes SNP and other specialized types from the included view; it does not conclude that an individual is ineligible for them. No commission, partner, carrier-contract or acquisition filter exists. Source-identity ordering is not a ranking.

New York County is an inspected test market, not a company launch decision. A second Stafford County, VA query exercises the actual missing-PBP case. The next user-requested extension is [Naples / Collier County, FL](NAPLES_DATA.md), with all matching landscape rows and complete PBP payloads preserved. Only these three explicitly mapped counties are supported.

The current [CMS landscape page](https://www.cms.gov/medicare/coverage/prescription-drug-coverage) and [2027 PBP page](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/benefits-data/pbp-benefits-2027-json) linked the original source URLs when checked. Fresh CMS downloads matched the original bundle hashes. The county reference comes from the [Census 2025 Gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip). The [release registry](../cms-slice/data-sources/release.json) pins exact bytes, members, hashes and source pages. The landscape README says data last updated September 22, 2026, with a September 30 note revision. The original PBP publication/download timestamps were not supplied; nested update timestamps do not fill that gap.

## Verified observations

The machine-readable [quality report](../cms-slice/reports/work-package-1/quality.json) records the complete results.

| Observation | Result | Interpretation limit |
|---|---:|---|
| Landscape rows / columns | 130,307 / 53 | One pinned release |
| Distinct year/contract/plan/segment identities | 5,884 | Not a national count of purchasable coverage options |
| Distinct year/contract/plan identities | 5,412 | Dropping segment loses distinctions |
| Distinct source geographic offering tuples | 130,307; zero duplicates | Observed grain, not a permanent source invariant |
| `All Counties` rows | 476, all PDP | Scope is statewide within the exact source state |
| Literal landscape segment `0` rows | 117,748 | Retain raw text; three-digit padding is join-only |
| PBP members / fully parsed payloads | 7,969 / 7,969 | Extends the earlier five-sample inspection |
| PBP uncompressed bytes | 1,775,307,420 | Stream members; no full extraction required |
| PBP payload/filename identity mismatches | 0 | All four identity fields checked, one PBP entry per member |
| Landscape identities matched to PBP | 5,883 / 5,884 | One missing source identity remains unresolved |
| PBP-only identities | 2,086 | Population differences explained below |
| Matched plan-name conflicts | 0 | String agreement does not validate nested benefits |
| Negative Part D basic-premium rows | 46,713 | Valid parenthesized source components; not rejected or clipped to zero |
| Empty C/D/overall star ratings | 130,307 in each column | Blank is not zero stars; no rating displayed as verified |
| Part D component arithmetic | 111,971 agree; 18,336 not comparable | Basic + supplemental = total when applicable |
| Consolidated premium arithmetic | 111,386 agree; 18,921 not comparable | C + D total when all components apply |
| Rejected selected currency values / arithmetic conflicts | 0 / 0 | Does not verify personalized premiums or costs |
| Plan-segments with varying selected premium tuples by geography | 0 | Single-release observation only; no premature normalization invariant |

## Join discrepancies investigated

**All 2,086 PBP-only identities fit documented landscape exclusions.** The complete [PBP-only ledger](../cms-slice/reports/work-package-1/pbp-only.jsonl) preserves the observed evidence for each:

- **1,672 employer-only:** every record has PBP `isEmployerOnlyPlan = "Yes"` and a plan ID at least 800. Examples include `E3014-801-000-2027` and `H0028-801-000-2027`.
- **414 National PACE:** every remaining record has `planTypeLabel = "National PACE"`. Example: `H0016-001-000-2027`.
- **0 unexplained PBP-only identities.** None is added to the consumer candidate set merely because a PBP file exists.

This classification uses the actual characteristics plus the included landscape README's population exclusions. Numeric plan-ID comparison is used only for this documented employer exclusion check; the stored plan ID remains the original three-character string. PBP plan-type labels alone are insufficient: employer plans also have ordinary HMO/PPO labels.

**The missing landscape identity is `H3931-143-000-2027`, Aetna Medicare Elite Extra (HMO).** It appears in **16 Virginia county rows**, all retained in the [missing-PBP ledger](../cms-slice/reports/work-package-1/landscape-without-pbp.jsonl). There are 19 other members for contract `H3931`, but none for plan `143` under any segment/year in this archive. All 7,969 directory names and payload identities were checked. Padding, leading-zero loss, payload/filename disagreement and an alternate segment within this archive do not explain the absence.

The later [October Part D follow-up](../cms-slice/reports/source-diligence/missing-pbp-followup.json) adds independent evidence: the exact contract-plan-segment appears unsuppressed in 16 PUF rows, whose SSA-locator state/county labels match all 16 affected landscape rows exactly. Name/segment/geography do not explain the PBP gap. This additional source does not supply the missing PBP or establish publisher-level cause, marketability or complete benefits. Run `python3 scripts/check_missing_pbp.py` from `cms-slice/` to reproduce the dated probe without changing WP1's original reports.

The publisher-level cause is unconfirmed. Do not call it a withdrawal, infer nonmarketability, copy another plan's benefits or silently discard it. The Stafford query keeps it in scope with `pbp.join_status = "missing"` and an explicit open check. Request CMS/source clarification and compare a subsequent dated release before closing this question.

All PBP plan statuses are the literal `Submitted`. This inspection does not establish what that workflow value guarantees. No status is interpreted as approved, verified or enrollable.

## Geography and query results

The [explicit aliases](../cms-slice/data-sources/markets.json) are checked against actual Census records:

| FIPS | Census record ordinal / name | Exact CMS state / county label | Included / excluded / total |
|---|---|---|---:|
| `36061` | 1,862 / New York County | NY / New York | 35 / 35 / 70 |
| `51179` | 2,909 / Stafford County | VA / Stafford | 35 / 26 / 61 |
| `12021` | 334 / Collier County | FL / Collier | 38 / 32 / 70 |

New York's included records are 21 MA-PD, five MA and nine statewide PDP. Its 35 excluded rows are SNP. Stafford's included records are 19 MA-PD, seven MA and nine statewide PDP; one of the included MA-PD records lacks PBP evidence. Exclusion reasons and original records remain inspectable in each output.

The Census file is pipe-delimited, not assumed to be tab-delimited. Aliases are explicit and narrow: no national suffix removal, fuzzy county matching, ZIP inference or conflation of New York City with New York County. `All Counties` stays a source scope, with exact-state matching and a PDP guard. It is never persisted as if CMS supplied a separate county-level PDP row.

## Mapping and lineage

The [field mapping](../cms-slice/data-sources/field-mapping.json) gives source columns/JSON pointers, units, documented meaning and limits. Promoted monetary fields are landscape Part C premium; Part D basic, supplemental and total premiums; consolidated C+D premium; annual Part D deductible; and in-network medical MOOP. PBP contributes verified identity and raw characteristics/status evidence. Undocumented nested benefit codes are not decoded.

For example, `H0423-004-000-2027` appears at landscape **CSV record ordinal 78,536**. Its raw annual Part D deductible is `"$700.00 "`, parsed as **70,000 cents**, and raw medical MOOP is `"$9,850.00 "`, parsed as **985,000 cents**. The matching PBP member is `H0423-004-000-2027.json`; its plan name is read from `/pbp/0/planCharacteristics/planName`. Neither value establishes this person's medicine coverage, full annual costs or a recommendation.

Each fact carries archive SHA-256, exact ZIP member, member SHA-256, and CSV record ordinal plus column or JSON pointer. Header counts as record 1; CSV ordinals are not physical lines. Each included/excluded record also keeps all 53 original landscape values. PBP raw content remains recoverable from the immutable archive. Release/configuration/script hashes and all output hashes are pinned in [run-manifest.json](../cms-slice/reports/work-package-1/run-manifest.json).

Money uses integer cents after exact decimal parsing. Every raw cell distinguishes value (including zero), empty, `Not Applicable`, `Not Available`, JSON null, absent path and rejected encoding. Only documented Part D basic components accept parenthesized negatives. A missing or inapplicable consolidated premium never becomes zero or a guessed replacement. Published plan premiums do not include every Medicare premium, penalty, income adjustment or personal cost.

PBP `moopLimits` contains ranges in sampled payloads; these are not substituted for plan-specific medical limits. `cmsApprovedContArea` remains an explicitly opaque raw code. `lastUpdatedAt` remains source text; no undocumented timezone/meaning conversion is made.

## Acceptance evidence and open questions

Run commands are in the [action reference](../ACTION_REFERENCE.md). The expanded 21-test suite covers actual archive counts/populations, all New York and Naples membership and raw-record replay, source paths, complete raw export including exclusions, the Stafford gap, exact money/null semantics, malformed identities/layouts/payloads, tampered source bytes, unsupported year/geography and repeatability. See the [validation record](../cms-slice/VALIDATION.md). Structural negative fixtures are test-only corruption inputs, not insurance catalog fixtures.

| Gate | State |
|---|---|
| Real input → scoped query → explicit gaps/exclusions | Implemented and tested |
| Full PBP payload identity audit and population explanation | Verified; the single missing identity's root cause remains open |
| Selected landscape field units/meaning against included README | Mapped; independent domain sign-off still required |
| Exact source/config/code/output replay basis | Implemented; hash verification and deterministic query replay tested |
| Independent authoritative market/benefit value cross-check | Not completed; no Medicare Plan Finder/carrier comparison claimed |
| Current source terms/display/transformation/retention rights | Not signed off; public availability alone does not settle downstream uses |
| Consumer launch authority, eligibility, quotes, networks, transaction and outcomes | Outside this slice; not implemented or asserted |

Before promoting this to a consumer read model: resolve or explicitly accept the bounded missing-source handling; obtain source status/benefit documentation and qualified field review; independently check representative carrier/Medicare facts; approve source-use scope; and review the [minimal persistence proposal](PERSISTENCE_PROPOSAL.md). A failed source hash or layout check requires fresh inspection, not a permissive parser change.
