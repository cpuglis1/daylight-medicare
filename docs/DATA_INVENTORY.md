# Data inventory, provenance and gaps

Repository evidence checked October 21, 2026. **Captured**, **queryable in offline research**, **packaged**, and **accepted for consumer use** are different states. Current consumer acceptance is pending, with zero approved claims. This document is a repository synthesis, not a refreshed external Medicare fact sheet.

## Reconciled coverage

The original [15-layer assessment](../Collier%20County%20Medicare%20Data%20Inventory.md) and Data Layers audit workbook remain unchanged. They describe an earlier state: separate ratings were subsequently imported and all 61 pharmacy networks packaged. The historical 38-plan core-benefit comparison scope does not equal the 70-record catalog universe.

| Layer | Repository evidence now | Remaining gap / consumer boundary |
| --- | --- | --- |
| Original Medicare costs | Sourced explanations and guide date logic | Accepted effective-dated 2027 A/B/IRMAA/penalty inputs and complete total-cost cases remain open (C29–C32). No inferred annual total. |
| Advantage availability | 59 captured records: 23 MA-PD, 9 MA-only, 27 SNP | All-plan/four-ZIP current two-way availability reconciliation and restricted eligibility remain unresolved. |
| Advantage benefits | All 70 PBP payloads captured; 70 × 24 core matrix = 1,680 cells | Selected corroboration is partial; complete exact SB/EOC field/condition review and premium-basis disputes remain open. |
| Standalone Part D | 11 captured PDP records | Availability, source conflicts, and exact-release review still required. |
| Formularies | 61 drug-bearing plans, 24 formularies, 79,793 captured formulary rows | Quantity/date meanings, broader restriction/noncoverage checks, and accepted interpretations remain open. |
| Personal drug prices | No adequate accepted 2027 personal pricing feed | A 2026 quarterly source cannot fill 2027 costs; calculator H01 remains held. |
| Pharmacy networks | 3,506,965 captured rows; all 61 plan network files packaged and exact-plan replayed | Captured joins do not establish current personal price or domain approval. Nine MA-only records are not applicable. |
| Doctors/hospitals | NPI identity examples, dated notices, insurer discovery; 118 hospital × plan cells explicitly unknown | Zero confirmed exact clinical participation; verify provider, location, network, year and plan. Eleven PDPs do not have clinical networks. |
| CMS ratings | 24 contract joins, 70 record states; CSV/workbook extraction cross-check | Contract-level ratings and official nonnumeric states retained. Same-publication cross-check is not independent corroboration or acceptance. |
| Medigap rates/products | 3,876 illustrative CHOICES annual comparison rows across 33 insurer names | Zero accepted rates; NAIC/form, effective dates, discount/fee basis, filed-rate replay and actual quote/underwriting remain unverified. OIR request 26-045612 awaits responsive records per saved status. |
| Medigap buying rules | Source-linked guidance and date safeguards | Qualified jurisdiction/population/effective-period review and unresolved cases remain open. |
| Assistance programs | Sourced local-program/coordination evidence and referral material | Accepted effective-dated thresholds and personal eligibility are not established. |
| Enrollment/penalties | Guide handles reported A/B, birth timing, first-day/unknown answers and work transitions | General date logic does not establish an individual's enrollment rights or accepted penalties. |
| Other plan types | PACE/coordination research with explicit assessment limits | Current address-based availability and eligibility are not established by the reference capture. |
| Local counseling | SHINE referral/source evidence captured | Recheck current contact/service details before operational use; no completed counseling or personal outcome claimed. |

Primary local evidence: [market profile](../cms-slice/reports/work-package-1/market-12021-2027-profile.json), [validation status](../cms-slice/reports/collier-gap-20261020/validation/validation-status.json), [technical inventory](../cms-slice/reports/collier-gap-20261020/validation/current-technical-verification.json), [required review packet](../cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md). These are dated captures; see the review for checks repeated today.

## Where the bytes and lineage live

| Location | Meaning / handling |
| --- | --- |
| `cms-slice/data-sources/*.json` | Pinned source inventories, hashes, mapping/markets, review checkpoints, fixed collector tasks and pending consumer registry |
| `cms-slice/data-sources/raw/` | Ignored national archives, original retrieval receipts, prescription nested archives and compressed market captures; about 4.9 GB logical file bytes in this inventory |
| `cms-slice/reports/work-package-{1,2,3}/` | Original queries, raw-record exports, source/manifold hashes, structural and corroboration reports |
| `cms-slice/reports/collier-gap-20261019/` | Gaps C02 onward, rating/source discovery, local programs, supplier and source-policy evidence |
| `cms-slice/reports/collier-gap-20261020/` | Benefit/Medigap research, blocked collector runs and per-claim acceptance packet |
| `cms-slice/releases/` | Ignored immutable local releases, bundles, and selected pointer; retain independently of Git |
| `outputs/daylight-audit-20261019/` | Original workbook, exports, screenshots and source notes; historical assessment, not current acceptance |
| `cms-slice/var/medicare-collector/` | Ignored persistent STOP, locks/cache/request accounting; operational state, not disposable scratch |
| `medicare-project-2026-10-17-v1.2/` | Preserved original source reconnaissance, research and synthetic prototype |

Logical file sizes count duplicate archives, extracted caches, retained releases, and symlinks separately. They are not unique data volumes. The full original 5,106-file hash inventory includes ignored files and caches; see [preservation/rollback](REPOSITORY_ORGANIZATION.md).

## Provenance and release constraints

Keep source URL, retrieved time, exact bytes/hash, identity/year/geography, raw pointer/page and transformation version together. Preserve conflicting observations and raw values. Missing is not zero; not-applicable and official nonnumeric states need explicit handling. Source/public access does not itself grant reuse authority. Do not turn notes, a working join, a classifier state, or an engineering test into a validated consumer claim.

The selected release has **2,036 required acceptance claims** across six workstreams and a pending registry. The saved engineering checkpoint deadline `2026-10-21T01:33:00.069116+00:00` is past at review time. Runtime hashes also differ. The Medicare.gov collector is stopped after a saved HTTP 403; no retries, alternate-browser collection, or STOP reset were part of this task.

Follow [acceptance standard](DATA_VALIDATION_ACCEPTANCE.md), [validated operations](VALIDATED_DATA_OPERATIONS.md), the [C/H checklist](../COLLIER_DATA_GAP_PLAN_current.md), and [owner queue](../COLLIER_OWNER_REVIEW_REQUIRED.md). No supplier choice, data license, reviewer approval, or outreach was created by this documentation cleanup.
