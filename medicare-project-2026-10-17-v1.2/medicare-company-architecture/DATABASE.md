# Data foundation: inspect first, model second

Company name undecided · revised October 17, 2026 · source inspection performed October 16, 2026 · companion to [ARCHITECTURE.md](ARCHITECTURE.md)

## Decision

Do not design a giant insurance database from imagined vendor responses. First inspect real inputs, establish their grain and meaning, and prove the queries needed by the product. Preserve original source data, promote only validated fields, and add structure when a concrete decision requires it.

This document records a first inspection of **actual public CMS artifacts** and a plan for the remaining discovery. It does not prescribe final DDL, a complete ontology, dozens of normalized tables, a partition strategy or a vector database. There are no production migrations to apply yet.

## 1. What was actually inspected

The following artifacts were downloaded from links on CMS's official [landscape page](https://www.cms.gov/medicare/coverage/prescription-drug-coverage) and [2027 PBP page](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/benefits-data/pbp-benefits-2027-json). This is one release of each source, not a longitudinal study or a national completeness certification.

| Artifact | Inspection performed | Observed result |
|---|---|---|
| `cy2027-landscape-202609-1.zip` | Read included README and CSV header; scan all CSV records for counts, candidate keys, values and missingness | 11,964,394 compressed bytes; CSV contains 130,307 data rows and 53 columns |
| `pbp-benefits-json-2027-zip.zip-0` | Enumerate entire ZIP directory; parse five selected JSON payloads; compare filenames with candidate landscape identities | 73,428,262 compressed bytes; 7,969 JSON members; 1,775,307,420 total uncompressed bytes |

Read the reproducible structural evidence: [landscape profile](evidence/landscape-profile.json), [PBP profile](evidence/pbp-profile.json), [source manifest](evidence/source-manifest.json). Original downloads remain in the working research directory; large government files are not bundled into this review package.

### Landscape observations

- 130,307 distinct candidate geographic keys using year, contract, plan, segment, state and county; no duplicate of that candidate tuple in this particular file.
- 5,884 distinct `(Contract Year, Contract ID, Plan ID, Segment ID)` combinations; 5,412 without segment. These are measured source-key counts, not an audited count of products a consumer can buy.
- 476 rows use `All Counties`. A county column therefore cannot be treated as a clean county-FIPS foreign key without geographic interpretation and a reference crosswalk.
- The segment value is literal text `0` in 117,748 rows. Plan IDs include leading zeros. Preserve raw identifier values; do not let an import silently coerce all identifiers into numbers.
- Currency is formatted text, including dollar signs, commas, whitespace and parenthesized negative amounts. The latter occurs in the Part D basic-premium component; a blanket “reject all negative currency” rule would reject real source values.
- Empty strings and `Not Applicable` both occur. Neither should silently become zero, false or the same universal null meaning.
- No variation in the selected premium tuple was observed within a year/contract/plan/segment key in this release. This supports a candidate factorization for further testing; it does not prove a permanent invariant across future releases or other feeds.

Selected actual columns include `Contract Year`, `Contract ID`, `Plan ID`, `Segment ID`, `Contract Plan Segment ID`, `State Territory Abbreviation`, `County Name`, `Contract Category Type`, `Plan Type`, `Sanctioned Plan`, `Part D Coverage Indicator`, `Part C Premium`, `Part D Total Premium`, `Monthly Consolidated Premium (Part C + D)`, `In-Network Maximum Out-of-Pocket (MOOP) Amount`, and ratings. The complete 53-column header and observed missingness are in the evidence JSON.

The included README describes exclusions such as employer-sponsored plans, Part B-only plans and National PACE. It warns about leading zeros and records release changes. Store and read source documentation alongside the data; the filename alone is not a specification.

### PBP observations

The filenames have an observed contract-plan-segment-year shape, such as `H0104-012-000-2027.json`. The sampled payloads expose `contractYear`, `section`, and a `pbp` array. Inside the sampled array are `contractId`, `planId`, `segmentId`, `status`, `lastUpdatedAt` and nested sections. `segmentId` was numeric zero in the inspected payloads, while the corresponding filename uses `000` and the landscape uses `0`.

The samples were an employer PDP, a PACE product, a D-SNP, an ordinary PPO and an ordinary HMO. The ordinary HMO/PPO samples include sections such as `planCharacteristics`, `benefitOfferings`, `planLevelCostSharing`, `priorAuthorizationAndReferral`, `costShareGroups`, `rx` and `benefitDetails`. Much smaller samples contain fewer sections. Do not assume all payloads have one flat record shape.

The sampled plan-level status is `Submitted`. That is an observed source workflow value, not a conclusion that the plan is currently marketable, available to this customer, verified or enrollable. Its meaning needs documentation and reconciliation with the appropriate availability source.

A **candidate filename join**, after padding the landscape segment for comparison, matched 5,883 of 5,884 landscape identities. There was one landscape identity without a corresponding PBP filename and 2,086 PBP filenames outside the landscape set. This is a useful discrepancy list, not evidence that 2,086 plans should be added to a consumer result. Different source populations, statuses and product categories need to be explained first. Only five payloads have been parsed; a full payload-identity and benefit-semantic audit has not been done.

### Immediate design implications

1. We need a source-aware join and scope reconciliation before declaring a canonical plan count.
2. Raw identifiers and source values must survive normalization.
3. Preserve nested PBP content initially. Extract only the fields required by a real query, with a source path and tested interpretation.
4. County matching, premium meaning and status meaning require validation, not guessed casts or labels.
5. Neither artifact supplies the entire business: Medigap quotes, precise provider participation, actual pharmacy-specific customer costs and carrier transaction rights remain separate dependencies.

## 2. What has not been inspected

| Source family | What we need to see before designing its storage/adapter |
|---|---|
| Monthly formulary/pharmacy files and quarterly pricing | Current files, layouts, use agreement, complete row grain, plan/formulary joins, pharmacy identity, restrictions, price scope and dated updates |
| Medigap rate/underwriting source | Actual quote request/response, rate identifier, product/form identity, age/rating inputs, discount representation, geography, underwriting conditions, dates, errors and quote TTL |
| Provider/network supplier | Exact provider/location/plan response, network identity, participation status meanings, freshness, conflicts, new-patient availability and confirmation receipts |
| Shopping/enrollment supplier | Sandbox schemas, availability versus enrollment lists, required forms/fields, approved signatures, submission IDs, status callbacks, duplicate/timeout behavior and carrier limitations |
| Carrier documents | Representative EOC, Summary of Benefits, ANOC, certificate, underwriting guide and rate filing; extraction rights and exact authoritative scope |
| Customer history | Actual authorized API scopes/payloads, consent and revocation flow, lag, completeness and identifiers; no real personal data needed for initial schema exploration |

Public CMS dataset descriptions identify several formulary/pharmacy tables, but a description is not a substitute for profiling the selected release. [CMS dataset](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information). Vendor marketing and API landing pages similarly establish candidate capabilities rather than a data contract.

## 3. Ask product questions before choosing tables

The first schema should support a handful of validated queries, then grow with evidence.

| Product question | Inputs required | What must be proven |
|---|---|---|
| Which supported health/drug options appear in a specific market and year? | Actual landscape, geography mapping, product/status meanings | Exact location match, category handling, no unexamined source omissions |
| What are this option's published premiums and selected benefit conditions? | Landscape plus a matching PBP payload and interpretation docs | Identity match, correct component/scope, source path, missing/not-applicable handling |
| How does the current option differ from two alternatives? | Validated normalized fields plus existing coverage | Comparable structures and costs; missing data displayed rather than fabricated |
| Is a specific medicine covered and under what restrictions? | Confirmed drug identity plus actual formulary/restriction data | Correct drug/plan/year, pharmacy and authorization limitations |
| Is this exact doctor at this address available under this exact plan? | Actual identity and participation responses | Location and plan precision, current evidence and conflict policy |
| What Medigap rate can this person obtain? | Actual rate/quote source and supported profile inputs | Quote versus reference rate, underwriting conditions, discounts, expiration |
| Can the licensed agent submit or authorize and confirm coverage? | Actual carrier/channel contracts, payloads/status interfaces, licensed/appointed agent and required review | User authorization, agent authority/checklist/re-verification, approved fields, receipts, reconciliation and effective coverage |

The first two queries can begin with public source data. The later queries must not be declared solved merely because the plan catalog loads successfully.

## 4. Smallest useful data experiment

**Slice:** one stated year and one test geography, ordinary supported plan categories, a small set of benefits needed for comparison, and one reconciled landscape/PBP join. Choose the test geography from the data; this does not select a legal launch state.

1. Keep the downloaded artifacts, checksums, publication/retrieval details and README/layouts.
2. Profile the relevant records with simple scripts or a local analytical query tool. No production database is required to discover grain and joins.
3. Explain the unmatched landscape identity and a representative sample of PBP-only identities before deciding scope rules.
4. Create a small source-to-output mapping for identities, geography, premium components, plan category and a few benefit fields. Record field path, raw example, unit/encoding, null meaning and supporting documentation.
5. Query the actual market and compare results with the source records and another authoritative view where permitted. Verify edge cases rather than only a successful example.
6. Introduce the smallest persistent read model that serves the proven queries. PostgreSQL is a reasonable candidate, not a reason to normalize every unexamined PBP field.
7. Repeat the method for medicines, then provider access and Medigap quotes once representative inputs and terms are available.

**Exit artifact:** a short mapping, a tested market query, discrepancy explanations, a few validated read fields, source lineage, and an explicit missing-capabilities list. Only then approve the first production migrations.

## 5. A provisional storage approach

These are responsibilities, not a required table count:

- **Source artifacts and manifest:** immutable original files or permitted receipts, checksum, source/date/layout, access terms and inspection/import outcome.
- **Source-shaped staging:** preserve actual CSV columns and nested JSON before irreversible transformations. Allow a layout to evolve without losing the raw basis for reprocessing.
- **Small validated read model:** identities, location eligibility and selected comparison fields whose meanings have been established. Keep a path back to each source record.
- **Private application records:** customer permissions, confirmed profile revision, saved comparison basis and workflow status, introduced when those workflows are implemented. Their design follows actual requirements and a privacy assessment, not the source-feed schema.

Under the revised operating model, each ranking must retain the user-stated criteria, inputs, weights and data/engine versions needed to reproduce it, including full results/exclusions and the shortlist view. At purchase, preserve the full-context handoff, assigned licensed/appointed agent, checklist/re-verification, exact approvals and queue/work timestamps. Measure attributable human minutes through the declared retention window. These are behavioral record requirements; inspect the real carrier/agent workflow and build only the persistence needed by an implemented capability.

The caregiver-first strategy adds an actor/subject distinction, permissioned sharing and attribution of who supplied/confirmed a fact. Auditable neutrality requires ranking replay independent of compensation or partner/channel attribution. Later distribution/outcome measurement must separate a permitted outbound click from a confirmed enrollment and use declared cohorts/retention windows. Keep commercial/analytics data outside ranking inputs, and add only the storage needed by implemented, consented workflows; do not predesign a large partner/analytics schema.

Use relational columns for validated fields used in filters, joins and calculations. Keeping unmodeled source detail in JSON or raw files is acceptable. Avoid both extremes: duplicating the entire PBP into speculative normalized tables, or putting everything into a single opaque blob and asking the LLM to interpret benefits on every turn.

Do not add sharding, a graph database, a separate search cluster, a warehouse, pervasive embeddings or complex historical machinery just because they might be useful at national scale. Add an index for an observed query; partition only after measured size/access/update patterns justify it. Public/private access isolation is a security requirement, but its initial physical implementation remains a deployment decision.

## 6. Data rules to preserve from the start

Some principles are warranted before choosing physical tables:

| Rule | Reason |
|---|---|
| Preserve raw values and source-qualified identifiers | Real files already demonstrate different encodings and leading zeros |
| Separate zero, missing, not applicable and unverified | These have different decision meanings |
| Retain year, source release and relevant effective/observation dates | A current download can contain older or future-effective information |
| Keep provenance for every displayed/calculated fact | Reprocessing and explaining errors require the actual input |
| Separate reference rate, personalized quote, cost estimate and final accepted premium | Different sources and assurances |
| Distinguish discovered, interpretable, quotable, verifiable and enrollable | A catalog row is not an ability to complete the job |
| Represent uncertainty explicitly | A missing network answer cannot become “in network” |
| Keep compensation out of comparison inputs | Prevent commercial incentives from silently shaping advice |
| Make imports repeatable and reject unexplained schema/value drift | Avoid quietly changing outcomes when a supplier changes a layout |

A practical first version can meet these rules with simple source files, manifests, a small staging/import process and a limited read model. The final schema should express what the inspected inputs and validated product queries actually need.

## 7. Supplier sample and rights checklist

Before committing an adapter or database shape, request representative successful, incomplete, error and changed responses. Include multiple states, years, product categories and atypical cases appropriate to the source. Ask for:

1. Current schema/layout, identifier semantics, required/optional fields and compatibility policy.
2. Actual market/carrier/product counts and omissions; not only a nationwide marketing claim.
3. Source cadence, observed/effective dates, historical access, correction and deletion behavior.
4. Null/status definitions, quote validity, confidence/verification scope and conflict handling.
5. Pagination, bulk export, incremental updates, rate limits, latency and outage behavior.
6. Rights to store, display, transform, audit, retain and process data with an LLM in self-directed consumer research and to share/re-verify it in the licensed-agent purchase workflow.
7. Pricing, minimum commitments, exit/export rights, permitted subvendors and applicable data-security terms.

For later embedded software partners, verify data display/processing rights in the actual embedded context and permissioned case transfer; direct-use rights alone are not assumed to cover every distributor. Patient-portal/health-system access is a later, separately approved source/integration decision after outcome evidence.

Until those answers exist, the architecture names the dependency and its required behavior. It must not invent a vendor field, claim broad completeness, or encode an assumed quote/underwriting/transaction contract into a final schema.

## 8. Data review checkpoint

Approve physical schema only when the first source packet includes: artifact/layout versions; observed grain and distributions; candidate identity/joins and discrepancies; proven example queries; source-to-output mapping; use rights; and an explanation of what remains unknown.

The correct first build is a thin path from real inputs to a trustworthy query. Expand the database with each newly proven capability.
