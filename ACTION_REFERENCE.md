# Action reference

This guide covers the working source commands and local read-only comparison, followed by the eventual product actions. Personalized AI research and licensed purchase are still dependency-gated.

The current simple chat has its own [execution guide](docs/DEMO_EXECUTION.md), [re-audit](docs/NAPLES_DEMO_REAUDIT.md) and [facilitator handoff](docs/DEMO_HANDOFF.md). Run `python3 scripts/demo.py serve --release current` from `cms-slice/` after `python3 scripts/demo_release.py verify current`; open `http://127.0.0.1:8766/`. This source-grounded factual demo is separate from the eventual personalized ranking/purchase actions below.

## Run the working slice

From this workspace, change to `cms-slice/`. Use Python 3.14.7; there are no third-party dependencies.

| Action | Command | Evidence / expected behavior |
|---|---|---|
| Acquire exact public inputs | `python3 scripts/cms_slice.py fetch` | Downloads missing archives; verifies SHA-256/size; never replaces changed cached bytes |
| Reproduce full inspection and three test queries | `python3 scripts/cms_slice.py run` | Writes `reports/work-package-1/`; 130,307 landscape rows, 7,969 parsed PBP payloads, plus complete Naples source export |
| Query New York County | `python3 scripts/cms_slice.py query --year 2027 --county-fips 36061 --out /tmp/ny-cms-query.json` | 35 included, 35 excluded source rows; nine included statewide PDP records |
| Query Naples / Collier County | `python3 scripts/cms_slice.py query --year 2027 --county-fips 12021 --out /tmp/naples-cms-query.json` | 38 included, 32 excluded; all 70 records retained; 11 statewide Florida PDP records |
| Export complete Naples source data | `python3 scripts/cms_slice.py export-market --year 2027 --county-fips 12021 --out /tmp/naples-cms-sources.zip` | All 53 CSV fields and all 70 complete original PBP payloads, including excluded records; per-file hashes and lineage |
| Query the missing-PBP case | `python3 scripts/cms_slice.py query --year 2027 --county-fips 51179 --out /tmp/stafford-cms-query.json` | 35 included, 26 excluded; one included record lacks PBP |
| Run actual-source and negative checks | `python3 -m unittest discover -s tests -v` | Actual archive, geography, full-payload export and negative checks; missing archives fail with instructions, never a fixture fallback |
| Verify delivered report integrity | `python3 scripts/cms_slice.py verify` | Rechecks source, code/configuration and generated-file hashes |
| Write a separate review run | `python3 scripts/cms_slice.py run --out /tmp/cms-review-run` | Leaves delivered reports alone; compare declared output hashes for replay |

Only `fetch` needs network access. A normal `run` replaces only the generated report files in its output directory after processing all source inputs; it writes the output manifest last. Do not edit reports by hand and expect `verify` to pass. Inspect source evidence, change reviewed mapping/code if warranted, rerun, retest and review the difference.

## Local comparison and independent sample

From `cms-slice/`:

| Action | Command | Evidence / expected behavior |
|---|---|---|
| Acquire pinned carrier sample | `python3 scripts/validate_naples.py fetch` | Exact carrier pages/PDFs with receipts; current 2027 and real wrong-plan/year candidates |
| Build the read model | `python3 scripts/research.py build` | Source-pinned catalog of all 70 records; twelve checked amounts across five records; refuses corroboration conflicts |
| Verify the read model | `python3 scripts/research.py verify` | Source, code, configuration, carrier artifacts and output hashes |
| Start local browser review | `python3 scripts/research.py serve --port 8765` | Open `http://127.0.0.1:8765/`; loopback only, no private information or writes |
| Inspect one source record | `GET /api/options/H5434-002-000-2027` | Exact evidence/raw fields; excluded identities also inspectable |
| Compare selected records | `GET /api/compare?ids=H5434-002-000-2027,H5434-042-000-2027,S5904-001-000-2027` | One to three in-scope identities in unchanged source order; no suitability ranking |

The browser offers **Inspect sources**, selection checkboxes, **Compare selected**, **Clear**, and the complete exclusions list. These operate only on public evidence. A comparison checkbox does not authorize an application. Poppler's `pdftotext` is needed to rebuild the PDF checks. See [WP2 evidence and limits](docs/WORK_PACKAGE_2.md).

## Actual prescription evidence

| Action | Command / resource | Evidence / expected behavior |
|---|---|---|
| Acquire pinned 2027 prescription files | `python3 scripts/prescription.py fetch` | 2.29 GB actual CMS archive plus inspected layouts/methodologies; exact bytes/hashes required |
| Capture all matching Naples prescription evidence | `python3 scripts/prescription.py build` | 61 plan joins, 24 formularies, full matching cost/restriction/network rows; both premium discrepancies retained |
| Verify sources/captures | `python3 scripts/prescription.py verify` | Source/code/configuration/report and every compressed capture hash |
| Exact drug/pharmacy query | `python3 scripts/prescription.py query --plan H5434-002-000-2027 --ndc 00002143380 --pharmacy-npi 1609197854 --out /tmp/naples-drug-evidence.json` | Exact source rows, tier/PA/QL, source ordinal and pharmacy status; no 2027 price or annual cost |
| Replay returned raw cells independently | `python3 scripts/audit_prescription.py /tmp/naples-drug-evidence.json --out /tmp/naples-drug-audit.json` | Reads original nested ZIP rows directly; rejects changed cells and mismatched plan/medicine/pharmacy joins |
| Replay public vocabulary/identity diligence | `python3 scripts/reference_evidence.py build` | Four real Trulicity candidates; exact NDC/RxCUI mapping; actual NPI location-purpose discrepancy; no quote/provider-network claim |
| Recheck the original missing-PBP case against the new source | `python3 scripts/check_missing_pbp.py` | Exact unsuppressed Part D identity and 16 matching source counties; missing PBP remains unresolved, with no benefit substitution |
| Read prescription example context | `GET /api/prescription/context` | 31 supported drug-bearing plan records, four public product candidates and one public pharmacy identity; none confirmed for a person |
| Exact prescription API lookup | `GET /api/prescription/lookup?plan_id=H5434-002-000-2027&rxcui=1551300&pharmacy_npi=1609197854` | Same source query, with source-year, unit/date questions and conditional cost schedules; unexpected/commercial arguments rejected |

Use **Open the prescription evidence example** in the local browser. Its selected product is an explicitly labeled public test case, not a person's confirmed prescription. The code does not infer a drug from a brand name, equate SSA/FIPS codes, use 2026 prices for 2027, treat a missing basic-formulary row as proven noncoverage or convert quantity units silently. [WP3](docs/WORK_PACKAGE_3.md) gives full scope and unresolved questions. The remaining work-package gates are in the [execution ledger](docs/EXECUTION_STATUS.md).

## Read the evidence

| Need | Artifact |
|---|---|
| Source URLs, exact versions/hashes and header | [release registry](cms-slice/data-sources/release.json) |
| Supported county aliases and category/type scope | [market configuration](cms-slice/data-sources/markets.json) |
| Field paths, meaning, money units and null policy | [field mapping](cms-slice/data-sources/field-mapping.json) |
| Counts, full PBP identity audit and join investigation | [quality report](cms-slice/reports/work-package-1/quality.json) |
| Every PBP-only identity and classification evidence | [PBP-only ledger](cms-slice/reports/work-package-1/pbp-only.jsonl) |
| All rows affected by missing PBP | [missing-PBP ledger](cms-slice/reports/work-package-1/landscape-without-pbp.jsonl) |
| Full source results and exclusions | [New York](cms-slice/reports/work-package-1/market-36061-2027.json), [Stafford](cms-slice/reports/work-package-1/market-51179-2027.json), [Naples / Collier](cms-slice/reports/work-package-1/market-12021-2027.json) |
| Complete Naples raw PBP data and source CSV | [Source ZIP](cms-slice/reports/work-package-1/market-12021-2027-sources.zip), [market profile](cms-slice/reports/work-package-1/market-12021-2027-profile.json), [findings](docs/NAPLES_DATA.md) |
| Included CMS layout and explanatory notes | [hashed landscape README](cms-slice/reports/work-package-1/landscape-readme.json) |
| What remains unverified | [findings and open questions](docs/WORK_PACKAGE_1.md) |

For a displayed value, follow its `evidence` to the exact ZIP member and column/JSON pointer. `record_ordinal` counts CSV records, including header as 1. Follow the release registry for its origin URL/hash. Raw PBP JSON stays in the archive; the query does not decode unreviewed benefit codes.

## Failure handling

| Condition | Required action |
|---|---|
| Missing pinned archive | Fetch it or copy the exact hashed original to the configured cache path |
| Download/cache checksum mismatch | Preserve the differing bytes separately if needed; recover the pinned release or inspect/register a new release; do not merely relax the checksum |
| Header, identity, PBP cardinality or county alias disagreement | Stop that input path and investigate; do not guess a mapping |
| Unknown year/county | Return unsupported; do not substitute a nearby county, ZIP or year |
| Missing PBP for a landscape identity | Keep the source record, mark missing evidence and prevent unsupported benefit claims |
| Blank/inapplicable/unavailable value | Preserve its state; never make it zero, false, covered or in-network |
| Undocumented PBP code or `Submitted` status | Show as source evidence in review artifacts; do not infer marketability or a benefit meaning |
| Report hash/code/configuration changed | Reproduce, test and review; hash integrity alone does not establish domain correctness |

## Product action reference: planned behavior

| User action | What it means | Boundary / prerequisite |
|---|---|---|
| Ask a Medicare question | Immediate plain-language education | Approved dated sources and supported activity; no purchase-ready identity packet just to learn |
| Research my own coverage | Retiree engages the AI directly, confirms their own facts/priorities and controls saved research | No caregiver required; the same auditable comparison and licensed purchase requirements apply |
| Start research for a parent | Identify researcher and beneficiary separately | Family relationship grants no authority; collect only purpose-needed facts |
| Save/resume/share | Keep consented work and invite the appropriate person | Identity, subject-level grants, revocation and actor provenance; no unrestricted share-link authority |
| Confirm facts/criteria/weights | Approve the basis for comparison | Material AI or partner suggestions remain proposals until confirmed |
| Compare | Engine computes within stated year/market/product scope | Pinned verified inputs; full results/exclusions; missing checks visible; staying is a legitimate option |
| Ask about an option | Explain exact engine facts, tradeoffs and uncertainty | AI preserves engine order/membership; no “you should buy” verdict |
| Change priorities | Confirm new criteria, then recompute | New immutable basis/snapshot; no silent AI resorting |
| Select an option | Express the person's choice | No signature, submission approval or cancellation of current coverage |
| Ready to purchase | Request a licensed, appointed agent-of-record session | Server carries full transcript/profile/snapshot, selection and open checks; real queue/seasonal target/scheduled fallback |
| Review with the agent | Complete identity/authority/consents, applicable review, re-verification and replacement checks | Qualified current agent authority; changed material facts return to the person for renewed review |
| Authorize application | Approve the exact reviewed payload | Explicit consumer authorization plus licensed-agent submission/authorization through an approved channel |
| Check status | Read actual carrier receipts and reconciled status | Submitted, accepted and effective remain distinct; uncertain transmission is reconciled before retry |
| Get continuing help | Track notices, issues, corrections and permissioned annual review | Actual policy evidence and accountable open cases; policy changes return through licensed purchase |

The implementation currently supports public evidence inspection and local comparison. The personalized actions above require the packages and operating gates in the [plan](PLAN_OF_ATTACK.md). Carrier-link self-enrollment remains a future, default-disabled option and cannot bypass an overloaded agent queue.
