# Minimal persistence proposal for review

This proposal follows the actual source queries and profiles. **No database, DDL or migrations have been created.** WP2 now uses the sufficient file-backed option: `catalog.json`, a scoped validation report and a read manifest pinning sources, configuration, code and outputs. The HTTP process verifies these files at startup and serves an immutable read snapshot.

## Keep the proven evidence

1. **Immutable source artifacts and receipts.** Address exact ZIP bytes by SHA-256; keep origin URL, byte count, member names, layout/README, source dates where known and actual retrieval receipts. Unknown original dates remain unknown. The current manifest and raw cache demonstrate this responsibility.
2. **Versioned release/query configuration.** Keep the references to artifact hashes, explicit county aliases, bounded category/type scope, field-mapping version and parser version. A release manifest can remain a versioned file; it need not be a new database table.
3. **One small geographic offering read model, if WP2 needs SQL/API lookup.** Derive only validated fields, preserve source geography and keep exact raw evidence locators. Full source-shaped CSV/PBP staging can remain files; no PBP-wide relational expansion is proposed.

## Candidate offering record

| Field group | Minimum demonstrated requirement |
|---|---|
| Release and identity | Release reference, year, raw contract ID, raw three-character plan ID, raw segment plus three-digit join segment |
| Source geography | Exact state, original county label, explicit scope (`county` or `statewide_pdp`); county FIPS only for a reviewed county mapping |
| Read fields | Plan name, category, plan type, raw Part D/sanction indicators; the seven monetary fields mapped in WP1 and their units |
| Cell states | Raw value plus value/empty/not-applicable/not-available/null/absent/rejected state; nullable integer cents for validated monetary values |
| Landscape lineage | Artifact hash, member/hash and CSV record ordinal; mapping supplies columns |
| PBP evidence | Member/hash, raw identity, join state (`payload_identity_verified` or `missing`), selected raw characteristics/status paths |
| Quality | Explicit missing/conflicting/rejected checks; absence of PBP evidence is not absence of the offering |

The observed candidate key is **release + year + contract + plan + join-segment + source-state + source-county-label**. Preserve and validate the raw segment before enforcing uniqueness on normalized values; a future `0`/`000` collision must be reviewed, not deduplicated silently. The current release has no geographic duplicates, but that fact does not approve a permanent vendor-wide key.

A statewide PDP record has scope `statewide_pdp` and no source county FIPS. That missing county foreign key is explained by scope, not a generic unknown. A query can project it into a requested county's results without manufacturing 62 New York source rows. Do not persist query-expanded copies as if supplied by CMS.

Use typed columns for the actual filters/joins and reviewed cents fields. Preserve the original row or a lossless content-addressed locator, with cell-state/raw metadata, rather than an EAV table for every source field. The existing output cell envelope is an evidence format, not a requirement to copy its repeated hashes into every SQL cell. Shared evidence references can remove duplication.

No separate canonical plan/segment table is required for this first county query. Premium tuples did not vary within plan-segment in this release, but one release does not justify making that a permanent cross-release invariant. Profile more releases before factorizing. Do not add partitions, search infrastructure, embeddings or an event bus without an observed query need.

## Deferred until a real dependency is proven

No customer/profile/consent/ranking, drug/provider/quote, application/policy, finance/partner or outcome schema is proposed here. Their behavioral obligations remain in the original architecture, including immutable ranking inputs/weights/data versions, full results/exclusions, compensation isolation and full-context licensed purchase. Their storage follows implemented workflows, real supplier payloads and privacy/operating review.

## Prescription evidence added after inspecting actual files

WP3 now preserves source-shaped, compressed pipe files in the ignored cache, with a versioned manifest and quality/discrepancy reports. Every captured row has its original table/part and source ordinal; raw cells and line endings are retained. The file-backed query is sufficient for the observed 79,793 formulary rows and per-plan network lookups. No SQL expansion or vendor-wide canonical schema is proposed.

| Observed source grain | Minimal persistence implication for review |
|---|---|
| Plan information repeats a contract-plan-segment across source counties | Keep the source SSA county/MA region/PDP region and ordinal. Join Collier through the inspected locator, not by equating SSA `10100` with FIPS `12021` |
| Basic formulary is shared through `FORMULARY_ID` | Keep release/year/formulary/version, raw proxy NDC11, RxCUI, tier/restrictions and lineage. The tested release+formulary+year+NDC candidate grain has no duplicates; retain version evidence rather than assuming that forever |
| Beneficiary schedule is plan-segment + coverage phase + tier + supply category | Keep exact typed cost-share kinds plus raw amount/minimum/maximum and deductible/specialty flags. Do not place plan-specific costs on a shared formulary |
| Supplemental excluded-drug and indication files omit segment | Preserve their actual contract-plan/RxCUI grain and indication text where supplied; do not manufacture a source segment field |
| Pharmacy network is plan-segment + raw 12-character pharmacy number, possibly across parts | Keep both raw number and validated separate NPI lookup key, ZIP/service/preference flags, fee cells and source-part/ordinal. No price or clinical-provider participation foreign key is established |
| Insulin schedule has its own nullable tier and copay/coinsurance fields | Preserve source null states and units. Do not compute an insulin price or apply generic-tier cost sharing without the missing classification/price/rule evidence |

These are evidence-storage responsibilities demonstrated by real files, not an approved transactional schema. The 2027 drug-price relation is absent. NLM and NPPES snapshots remain separate content-addressed reference artifacts; they do not create an enrollment, quote, prescription or provider-network record. The quantity-unit, date-token and two premium discrepancies remain quality state, not silently corrected fields.

## Review decisions

- Approve the three aliases, category/type limits, monetary labels and the explicit missing-PBP behavior, including the cited Naples-to-Collier mapping. The Naples full-source ZIP adds evidence storage, not a new insurance schema.
- Resolve source-use permissions and status meanings, and independently validate representative field values before consumer promotion.
- WP2 demonstrated that files plus a bounded read adapter suffice. Revisit a database only for an actual saved-case/update requirement.
- If SQL is needed, choose the narrow offering read model and source-artifact references above, then review a migration against real input examples and required queries.
- Define release replacement/rollback and evidence retention before publishing changing data. The local report manifest is not an atomic production-release design.
