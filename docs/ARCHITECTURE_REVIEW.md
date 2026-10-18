# Directory and architecture review

Reviewed October 17, 2026 against the four v1.2 architecture documents, their evidence packet, original reconnaissance scripts/README/archives and earlier research. The revised architecture governs; historical research and prototype language do not override its licensed-purchase boundary.

## What is present

| Directory/file | Observed role | Treatment |
|---|---|---|
| `medicare-project-2026-10-17-v1.2/medicare-company-architecture/` | Company/software design, behavior contracts, build order and initial data observations | Reference specification, not executable production capability |
| Original `source-recon/` | Two real CMS ZIPs, manifests, full landscape profile, five-sample PBP profile and CSV profiling script | Preserved evidence; new code independently reproduces and extends it |
| Original research `.md` files | Competitive/adoption/decision-support evidence with stated limitations | Hypotheses and research context; no demonstrated company outcomes |
| Original `archived-prototype/` and snapshot ZIP | Synthetic Node workbench, prompts, UI, fixtures and tests | Historical artifact; not imported, modified, deployed or used as data |
| Original `BUNDLE_MANIFEST.json` | Inventory and hashes at packaging time | Preserved snapshot manifest, not a manifest of new workspace files |
| New `cms-slice/` | Standard-library Python landscape/PBP and prescription capture, bounded read API, local browser view, source registries/reports/tests | Actual public-evidence implementation under the revised operating model |
| New workspace guides and `docs/` | Action guide, dependency plan, findings, storage proposal and user journey | Reviewable next-step reference |

The original package occupies roughly 83 MB, dominated by government archives. There was no production database, standalone production application or enrollment connection in it. The original CSV profiler overwrites its reconnaissance profile when run; the new implementation writes separate reports instead.

## Architecture assessment

The strongest decisions are the separation of data from explanation; an engine that owns option order/membership; explicit discovery versus transaction scope; caregiver/beneficiary actor separation; and a licensed, appointed agent who owns purchase review and authorized submission. These boundaries fit the proposed product and make neutral ranking testable.

Keep the application modular and initially small. Reference/private access separation is required when private records arrive; it does not require deploying the complete topology now. PostgreSQL, TypeScript application modules and asynchronous workers remain plausible future choices, not installed or validated infrastructure. The source query uses Python and files; WP2 adds a loopback read-only HTTP server for the browser. Neither requires a database. WP3 streams the actual large pharmacy files into source-shaped, compressed market captures rather than expanding a speculative benefit schema.

The working view preserves all 70 Naples records and 32 exclusions, compares up to three supported records in source order and exposes twelve carrier-checked amounts across five records. It also provides a labeled public prescription example using actual 2027 CMS rows, NLM product candidates and an exact NPI pharmacy-network join. This is narrower than personalized AI research: it does not confirm a person's facts, calculate annual costs or make a suitability ranking. See [WP2](WORK_PACKAGE_2.md), [WP3](WORK_PACKAGE_3.md) and the [execution ledger](EXECUTION_STATUS.md).

The main risk is promoting structural evidence into a product claim. A successful join establishes identity correspondence, not eligibility, suitability, exact provider access, a quote or enrollment authority. `Submitted` in all PBP payloads is a source token; it is not a launch approval. Public-source fields must remain narrower than future option cards until their meanings and dependencies are proven.

The AI/engine contract is correctly strict. Later tests must compare both structured output and conversational lists against the same immutable engine snapshot. Full results and exclusions must remain reachable. Ranking replay must pin confirmed profile, criteria/weights, exact data and engine versions, and tie-breaking. Channel/partner/commission changes must leave order and membership unchanged. Nothing in WP1 implements that ranking contract yet.

The caregiver priority has concrete consequences: useful education before account creation, resumable evening/weekend research, separate researcher and beneficiary identities, explicit sharing grants and provenance for supplied versus confirmed facts. Family relationship cannot imply purchase authority. The licensed agent receives the complete transcript/profile/snapshot and checks identity and representative authority.

Retirees also engage the AI directly for their own coverage from the outset. A caregiver is optional. The clarified workflow includes a direct retiree entry, control of their own facts and criteria, saved research and the same licensed handoff. Caregiver-first acquisition does not restrict who can use the product.

The company plan has real dependencies beyond engineering: source rights, domain review, activity/state/product/channel authority, appointments/carrier access, staffing and seasonal response targets. No code completion can satisfy those gates. Ongoing service, failed-case labor and exceptions must be included in the retained-policy metric.

## Decisions still open

- Approve a launch scope after legal/data/carrier diligence; the three inspected test counties, including the Naples extension, do not select it.
- Confirm required source permissions, release freshness and the missing PBP identity's cause.
- Review the small proposed persistence model before migrations. A file-backed read API is implemented and is sufficient for the observed query volume/shape.
- Resolve actual 2027 prescription quantity/date/premium questions and missing pricing; obtain Medigap and clinical provider-network samples/terms. Public vocabulary/identity data and vendor marketing pages do not establish those capabilities.
- Establish criteria/weight confirmation, outcome cohorts, retention windows, human-work allocation and independent quality review.
- Establish qualified purchase capacity and real scheduling fallback before presenting a purchase request as fulfillable.

The 12–24 month incumbent-response window remains a hypothesis. The execution order is caregiver content/search, then financial-advisor software and publishers, then health systems after actual suitability/complaint/retention evidence. Neither the research packet nor this data slice demonstrates demand, acquisition economics or a defensible incumbent lead.
