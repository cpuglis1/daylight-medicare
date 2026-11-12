# C14 — 2027 drug-price source feasibility

**Decision: NO GO for a personal calculator.** No adequate authorized 2027 negotiated price feed was obtained. [The decision record](c14-price-source-decision.json) states evidence, limits, acceptance criteria and reopening triggers. H01/H08/H09 remain held; DQ-007 and DQ-008 remain open.

The planned three-day feasibility effort was completed as an expedited point-in-time assessment on October 19–20 Eastern. This is not a claim of three elapsed days, multi-day availability monitoring or vendor responses. The current evidence supports a decision now; it does not predict future publication or commercial availability.

| Route | Verified finding | Decision |
| --- | --- | --- |
| CMS monthly 2027 | Fresh catalog selects `2027_20261008.zip`; full retained 2,290,695,063-byte archive hash verified and eight table-type headers re-read. Formulary, tier cost sharing and dispensing fees lack a complete per-drug unit-price table. | Useful coverage/network evidence; insufficient pricing. |
| CMS quarterly pricing | Latest catalog candidate remains `SPUF_2026_20261007.zip`. Official retained methodology/layout describe plan-level average monthly retail unit costs by plan/segment/NDC/days supply; pricing table lacks pharmacy ID. Quarterly ZIP not newly downloaded. | Wrong benefit year; average grain also cannot support store-specific quotes. |
| CMS external access | C11 inquiry sent; reply/access grant pending. | No authorized feed assumed. |
| ConnectureDRX | Primary API page advertises dosage pricing and monthly OOP estimates. No 2027 Collier payload, signed license, refresh SLA or quote obtained. | Commercial lead, not an available verified feed. |
| SunFire | Primary pages advertise MAPD/PDP quoting and existing/custom APIs. Standalone negotiated drug-price API scope and rights not established. | Commercial lead requiring validation. |
| CSG | C10 subscription purchase deferred; tool marketing/subscription does not establish raw price-feed rights. | No purchase or adequate feed. |
| Medicare.gov observations | Potential future C20 fixed synthetic reference cases under C13/G9. | Dated examples, not a personal calculator or real-user query service. |

See [fresh release discovery](cms-release-discovery.json), [archive inspection](monthly-archive-inspection.json) and the linked source URLs/receipts in the decision JSON. Retained official PDFs are hash-verified, with their original provenance distinguished from new HTTP captures. The inner `20261031` tokens are not claimed as publication or retrieval dates; DQ-008's naming/date ambiguity remains explicit.

To reopen: obtain an authorized 2027 source with exact plan/year/NDC/quantity/days/pharmacy or clearly labeled average grain, price/dispensing-fee definitions, effective dates and refresh terms; validate worked synthetic cases and missing-data behavior, then obtain the existing H01 approval. Never substitute 2026 prices. Until then R1 shows all 61 plans' coverage/pharmacy evidence and links Plan Finder for personal estimates. No money, accounts, new vendor outreach or runtime prices were added.
