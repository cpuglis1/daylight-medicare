# Data quality, the 15 layers and national scale

October 29, 2026 · America/New_York · Companion to [D73: Daylight's strategic thesis](../product/STRATEGIC_THESIS.md).

The owner requested saving the scalability response in a new, clear folder and emphasized its importance to the thesis. This guide preserves the response's layer grouping, sourcing recommendations and Florida/national distinction, then adds the assessment of competitive advantage and how to prove it. The owner's request establishes the importance of the question; it does not establish an achieved competitive advantage or approve a new implementation scope.

## The strategic assessment

**The data foundation can scale. Repeating today's manual, chat-by-chat collection process across every county would be too expensive.** The next step is turning reusable collection and validation methods into scheduled pipelines.

**Yes: getting beyond the five largely reusable national layers could become a meaningful competitive advantage.** The opportunity is to turn fragmented evidence into reliable, understandable, personally relevant decision support that can be maintained economically. This builds directly on the thesis's two connected objectives: easy self-discovery and data quality sufficient for the requested personal task.

Public data access is a widely available foundation. CMS publishes approved MA/Part D benefits across organizations, and MA organizations are required to provide public Provider Directory APIs. Access alone does not establish exclusive data, accurate joins, complete conditions or a useful consumer experience. [CMS benefits data](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/benefits-data), [CMS Provider Directory API guidance](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api).

We have not performed a feature-by-feature competitive audit. No claim is made that competitors lack these capabilities, that our data is unique, or that Daylight has already achieved superior accuracy, national coverage or lower operating costs.

## How the 15 layers scale

Much of the work already starts with national data. L07 processes national pharmacy-network files; L08's hospital import retains the national dataset; L02 has engineering checks for Collier, Lee and New York County. These are foundations for expansion, not accepted nationwide consumer coverage. See the dated evidence in [L02 execution status](../data/l02-ma-availability-2026-10-25/STATUS.md), [L07 collection](../data/l07-pharmacy-networks-2026-10-27/COLLECTION.md) and [L08 hospital reference](../data/l08-provider-networks-2026-10-27/hospital-reference-r7/REPORT.md).

The architecture groups into three sets:

- **Five are largely reusable nationally:** L01, L02, L04, L09, L13.
- **Five have national foundations plus substantial carrier-specific work:** L03, L05, L06, L07, L08.
- **Five need substantial state or local adaptation:** L10, L11, L12, L14, L15.

This is an architectural assessment, not an estimate that two-thirds of the work is finished. Even the first group requires freshness, scope and release checks. The difficult layers can consume most of the effort. State/local layers also reuse federal foundations; the grouping describes the dominant expansion work rather than a strict partition of every source.

| Layer | What scales | What expansion needs |
| --- | --- | --- |
| **L01 — Original Medicare costs** | One federal annual reference serves the country. | Automated annual collection, change detection and review. No commercial feed needed for published federal amounts. |
| **L02 — MA availability** | National CMS offering and service-area data. | Scheduled national imports, geographic filtering and restriction checks. |
| **L03 — MA benefits** | National PBP data and reusable carrier document processing. | Automated document acquisition and complete benefit/condition comparisons. Interpretation remains difficult. |
| **L04 — PDP availability** | National CMS data organized by PDP region. | Regional views and recurring availability/status reconciliation. |
| **L05 — Drug coverage** | National formulary tables; shared formularies can serve many plans. | Recurring CMS imports, drug identity updates and carrier PA/ST policy collection. |
| **L06 — Drug costs** | Public cost-sharing schedules and published average prices. | Pharmacy-specific personal prices need a separately validated pricing source. That feature can remain deferred. |
| **L07 — Pharmacy networks** | National CMS network files and national pharmacy identities. | Scheduled imports, identity/address reconciliation and current-status exceptions. |
| **L08 — Doctors/hospitals** | National federal provider references; carrier connectors can cover multiple markets. | Carrier directory APIs/downloads, exact plan-network-location mapping and freshness checks. |
| **L09 — Star ratings** | National CMS annual tables. | Annual ingestion and exact contract/year joins. |
| **L10 — Medigap products/rates** | Common product/rate schema and reusable insurer logic. | State/carrier filings and effective dates. A rate/quote API becomes attractive as coverage expands. |
| **L11 — Medigap buying rights** | Federal baseline. | Reviewed state-specific rules and effective-dated changes. Primarily a rules-maintenance problem. |
| **L12 — Help paying costs** | Federal Extra Help foundation. | State MSP/Medicaid rules, thresholds and exceptions. An API alone cannot establish eligibility. |
| **L13 — Enrollment/penalties** | Federal rules and annual constants largely carry nationwide. | Dated event notices, rule changes and individual evidence for personal determinations. |
| **L14 — Other coverage paths** | National program/plan directories provide a starting inventory. | State/local service areas and program-specific restrictions, especially PACE. |
| **L15 — Local counseling** | Shared directory structure and national entry points. | State/local contact collection and periodic operational verification. |

CMS's structured drug files contain formulary, cost-sharing and pharmacy-network information; the pricing table reports average unit costs. That supports national ingestion while preserving the weaker grain of an average rather than a named-store personal price. [2026 CMS drug-data methodology](https://data.cms.gov/sites/default/files/2025-10/cf6b8476-ca42-48c6-9fc4-281b08c6ea87/Methodology-SPUF-2026.pdf).

## Where files, APIs and supplier feeds fit

A scheduled national CSV or ZIP download is already a scalable feed. Most layers do not require continuous streaming. Choose the delivery method around the publisher's actual update cadence, evidence grain, completeness and permitted use.

The priority connections are:

1. **Provider directories, L08.** Start with public carrier APIs and official downloads. Inspect whether each endpoint supplies the exact plan/network relationships, locations and dates needed. An API's existence does not establish complete, accurate participation data. CMS's 30-day update requirement is measured from the payer receiving information or an update; it is not proof that every entry was independently reverified within 30 days. [CMS directory API guidance](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api).
2. **Provider/pharmacy identities, L07–L08.** Use national bulk imports plus updates instead of thousands of individual searches. NPPES supplies free monthly files and weekly increments. Identity evidence still needs separate network evidence. [CMS NPPES dissemination](https://www.cms.gov/medicare/regulations-guidance/administrative-simplification/data-dissemination).
3. **Medigap rates and quotes, L10.** Public filings remain useful for bootstrapping and verification. A supplier API may become more economical than maintaining every state/carrier rate model ourselves. Actual coverage, sample payloads, freshness, consumer-display/audit rights and price must be evaluated before choosing a supplier. A supported rate is still distinct from personal eligibility or an underwritten quote.
4. **Personal pharmacy pricing, L06, if added.** This remains a separate sourcing and feature decision. Geographic expansion alone does not require that promise. Existing public averages and cost-sharing schedules retain their published scope.

An aggregator can help if it demonstrates adequate coverage and reduces total maintenance work. Purchasing a feed does not establish its completeness, solve every identity/condition question or make its contents exclusive. Some public carrier/document connectors will remain useful for corroboration and gaps.

A current API response cannot establish a historical 2026 network. Benefit year, source edition, effective dates and observation time must remain separate as the platform adds future years.

## Florida versus nationwide expansion

**Across Florida**, reuse Florida legal and assistance models, existing carrier connectors and national datasets. Additional work includes new offerings, networks, rate/geographic variants and local programs. Collier findings do not automatically establish another county's completeness or applicability.

**Across the country**, state rules and Medigap variation add substantial work. Additional carriers mean additional document formats and directory implementations. A state-specific rule adapter should reuse the federal baseline and represent actual differences, effective dates and unresolved interpretation.

The operating unit should be a unique source edition, exact offering, formulary or network. Process it once and attach its evidenced service areas. Reuse requires matching identity, period and complete conditions; a similar name, equal amount or shared carrier is insufficient.

Today we have reusable source methods, engineering checks and scoped research packages. We do not yet have a fully operating national refresh and acceptance service.

## What could make this a competitive advantage

The five largely national layers provide essential foundations. Extending the other ten creates more opportunities to answer consequential questions that a plan list or a general explanation leaves unresolved. The strongest opportunity is in the relationships between layers.

| Capability | Why it could matter to the person | Work that must be demonstrated |
| --- | --- | --- |
| **Exact benefit meaning — L03** | Understand the costs and conditions that matter for a service. | Preserve schedules, network variants, limitations, exceptions and source conflicts in complete comparisons. |
| **Drug coverage and access — L05–L07** | Understand the exact drug's coverage conditions and relevant pharmacy options. | Join product identity, formulary version, PA/ST/QL conditions, pharmacy identity/network and supported cost basis. Keep clinical approval and unknown personal prices explicit. |
| **Provider access — L08** | Investigate whether an intended clinician at an intended location participates in an exact plan/network. | Bind provider, location, network, offering and period. Directory evidence and current/new-patient confirmation remain distinct. |
| **Coverage flexibility — L10–L13** | Understand options and potential consequences before changing coverage. | Connect product/rate evidence, applicable buying rights, assistance and enrollment/coordination rules without inferring personal rights from incomplete facts. |
| **Complete paths and useful help — L14–L15** | See relevant alternatives and a usable official help route. | Include relevant local programs and uncompensated options with service-area/eligibility limits and operational contact evidence. |

The potential defensible assets are:

- A consistent model of exact identities, complete conditions, dates and relationships across sources.
- Reproducible source-to-claim lineage, reviewed corrections and known failure cases.
- Reusable collection and comparison workflows that make expansion and updates progressively cheaper.
- An honest, capability-specific account of missing information rather than silent exclusions.
- Independent, inspectable decision preparation that remains useful when the best outcome is keeping coverage, deferring or choosing an uncompensated option.
- A consumer experience that turns this evidence into understandable choices with minimal consequential intake and useful correction paths.

Some derived work may be distinctive subject to source permissions; public source bytes remain available to others. Durable advantage depends on maintaining quality, learning from errors and delivering better task outcomes at sustainable cost. It cannot be inferred from the size of a database or the number of layer folders.

## Quality means more than collecting all 15 layers

For every supported capability, quality includes the correct candidate universe; exact plan/person/location/product identity; complete material conditions; applicable year and effective dates; current-enough evidence under a reviewed policy; truthful unknowns; reproducible comparisons; and the required independent review and release acceptance.

Customer-reported completeness and external verification are separate. A completed intake cannot fill a provider-network gap or establish drug approval, assistance eligibility, a Medigap right or an exact personal price. The agent should ask only for missing facts that can advance the supported task, preserving the thesis's easy self-discovery objective.

**Full L03 remains unfinished.** The [r9 semantic inventory](../data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/README.md) freezes finite evidence/comparison obligations for the exact 72 Collier offerings; it does not establish verified benefit facts. The accepted r4 subset and all sealed revisions stay intact. The complete whole-offering pilot, structured comparisons, independent review and exact new-release acceptance remain required. Scale is not an MVP exemption or permission to reduce that denominator.

Every layer's actual current scope and acceptance must come from its own dated package and release records. This architectural grouping is not a certification that any group is complete.

## What would prove the advantage

Use the [D73 cohort evidence definitions](../product/STRATEGIC_THESIS.md#evidence-definitions-for-the-first-cohort). Establish an actual baseline before setting or claiming improvement. Evaluate against the target person's independent research process and available self-service alternatives; good-agent quality remains a useful benchmark. Any competitor comparison needs a separate current capability audit on matched tasks and evidence dates.

| Measure | Evidence to collect |
| --- | --- |
| **Material completeness** | Required checks for the supported task, checks with accepted evidence, named unresolved checks and missing candidate offerings. Define the denominator explicitly. |
| **Accuracy and conditions** | Independently adjudicated material claims, errors by severity, lost qualifications, incorrect joins and reviewed corrections. Extraction/test totals alone do not measure accuracy. |
| **Freshness and change handling** | Time from source publication/discovery to validated update, missed changes and stale claims withheld under the applicable policy. |
| **Consumer usefulness** | Ability to understand coverage-path tradeoffs, inspect a reason, correct a fact and complete supported research without a mandatory sales call. |
| **Human effort and economics** | Staff minutes and total maintenance/support cost per task, source update, new carrier and new state, including unsuccessful cases and rework. Measure actual reuse rather than assuming it. |
| **Repeatability** | The same scoped collection, validation and review workflow succeeds in another Florida county and another state while keeping exclusions and gaps visible. |
| **Trust and independence** | Reproducible decisions and correction history; economics counterfactuals; appropriate keep/defer/no-commission outcomes. |

The hypothesis becomes stronger when expanding to another county/state adds less maintenance effort, supported decisions become more complete and accurate, consumers understand them better, and staff effort falls without weakening review or independence. Those results are not established today.

## Recommended operating priorities

1. **Prove the difficult comparisons in Collier.** Prioritize L03, L08 and L10 because semantic benefit comparison, exact network mapping and effective-dated Medigap evidence are likely to determine expansion effort. Preserve existing full-scope review obligations.
2. **Build shared connectors and identities.** Parameterize year/geography; collect national sources once; reuse carrier/formulary/network work only where complete identity and period match.
3. **Make refresh and completeness routine.** Use scheduled discovery, immutable raw evidence, schema checks, changed-record comparisons, explicit gaps, isolated candidate builds and exact release/rollback records.
4. **Handle exceptions deliberately.** Automate repeatable source comparisons while preserving required independent/qualified review. A reviewed resolution can become a reusable test case; a similar case does not automatically inherit its acceptance.
5. **Demonstrate expansion across the supported capability.** Existing L02 checks in Lee and New York County are a start. Cross-layer proof must include the harder evidence and actual operating effort.
6. **Buy data selectively.** Evaluate whether a supplier closes a real capability gap or materially reduces total cost. Personal pharmacy pricing remains deferred unless separately authorized and supported.

These are strategic recommendations, not a new implementation authorization, supplier commitment or rollout schedule. D64 independence, source permissions/stops, privacy, full L03 obligations and exact capability/release gates continue to apply. Commercial economics cannot enter inclusion, filtering, ranking or explanations, and a costly or missing source cannot silently remove an option.
