# Medicare public-evidence slice

This independent Python implementation proves one bounded public-data path. It does not use the archived Node prototype.

See the workspace [action reference](../ACTION_REFERENCE.md), [findings](../docs/WORK_PACKAGE_1.md), and [persistence proposal](../docs/PERSISTENCE_PROPOSAL.md).

## Current simple chat demo

```sh
python3 scripts/demo_release.py verify current
python3 scripts/demo.py serve --release current
```

Open `http://127.0.0.1:8766/`. The offline release includes saved medicine/pharmacy identity examples and verified derived query inputs. No national archives, PDF tools or key are needed to run an extracted bundle. It is a factual research prototype with qualified review pending, personal drug pricing unavailable, and exact clinical participation unresolved.

Workspace mode, `python3 scripts/demo.py serve --online`, permits bounded public NLM/NPPES identity requests. The immutable offline release cannot fetch new examples. `OPENAI_API_KEY` and `OPENAI_MODEL` configure the optional server-side Responses adapter; `.env` files are not automatically loaded. The live adapter still needs actual-account evaluation. See [execution](../docs/DEMO_EXECUTION.md), [re-audit](../docs/NAPLES_DEMO_REAUDIT.md) and [handoff](../docs/DEMO_HANDOFF.md).

To rebuild, run `python3 scripts/drug_validation.py`, review the checkpoint in `data-sources/demo-review.json`, then `python3 scripts/demo_release.py build` and `python3 scripts/demo_release.py bundle current`. A changed data basis requires an explicit new engineering review receipt; rebuilding old bytes does not renew their review date. Use `python3 scripts/source_refresh.py --refresh` for public CMS catalog discovery only; it does not automatically import a new release.

## Commands

Run from this directory with Python 3.14.7; all imports are standard library.

```sh
python3 scripts/cms_slice.py fetch
python3 scripts/cms_slice.py run
python3 -m unittest discover -s tests -v
python3 scripts/cms_slice.py verify
python3 scripts/cms_slice.py query --year 2027 --county-fips 36061 --out /tmp/ny-cms-query.json
python3 scripts/cms_slice.py query --year 2027 --county-fips 12021 --out /tmp/naples-cms-query.json
python3 scripts/cms_slice.py export-market --year 2027 --county-fips 12021 --out /tmp/naples-cms-sources.zip
```

`fetch` downloads about 85.5 MB total, verifies bytes and SHA-256 before installation, and leaves existing differing files untouched. Fresh CMS download hashes matched the original reconnaissance manifests on October 17, 2026. The pinned Census county file was separately inspected; its observed delimiter is a pipe (`|`). Receipts contain retrieval time and selected response headers when fetched by the CLI. Cached bytes are always reverified.

To avoid redownloading CMS, copy the original bundle's `source-recon/landscape.zip` and `pbp.zip` to the corresponding paths in `data-sources/raw/`, then run `fetch` for missing artifacts. Copying does not create a new download receipt or establish an original retrieval timestamp.

`run` scans every landscape row and parses every PBP JSON, then emits all three supported test-market queries, report ledgers and the complete Naples source ZIP/profile. It finishes input processing before replacing report files and writes `run-manifest.json` last. This is a local experiment, not a production transactional release mechanism. `verify` checks source, code, configuration and output hashes; tests provide the separate structural and replay checks.

Only county FIPS `36061` (New York County, NY), `51179` (Stafford County, VA), and `12021` (Collier County, FL, for the confirmed City of Naples request), and benefit year `2027`, are accepted. An unsupported input exits with code 2 and does not substitute another location/year. Identifiers are strings; `10001` and Naples ZIP `34102` are not accepted as county identifiers. Query ordering is source identity order and conveys no preference.

Naples has 70 matching source records: 38 within the comparison scope and 32 retained exclusions. All 70 full PBP payloads are copied unchanged into the [market source ZIP](reports/work-package-1/market-12021-2027-sources.zip), along with all 53 landscape fields, lineage and file hashes. This is complete capture within the two pinned CMS source families, not a provider, drug-price or Medigap quote feed. See the [Naples findings](../docs/NAPLES_DATA.md).

## Files

| Path | Purpose |
|---|---|
| `scripts/cms_slice.py` | Fetch, structural inspection, market query and evidence verification |
| `data-sources/release.json` | Exact artifacts, hashes, layout and release metadata |
| `data-sources/markets.json` | Three explicit county aliases, cited Naples mapping and bounded category/type scope |
| `data-sources/field-mapping.json` | Raw paths, units, meaning and sentinel policy |
| `data-sources/raw/` | Ignored government archives and retrieval receipts |
| `reports/work-package-1/quality.json` | Full-file counts, money/null checks and join reconciliation |
| `reports/work-package-1/pbp-only.jsonl` | All 2,086 PBP-only identities with population evidence |
| `reports/work-package-1/landscape-without-pbp.jsonl` | All 16 geographic rows for the single missing identity |
| `reports/work-package-1/market-*-2027.json` | Included source options, exclusions, raw values and fact lineage |
| `reports/work-package-1/market-12021-2027-sources.zip` | All 70 raw PBP payloads and all matching landscape fields, including exclusions |
| `reports/work-package-1/market-12021-2027-profile.json` | Naples geography, category/type counts, complete-payload count and gaps |
| `reports/work-package-1/run-manifest.json` | Source/configuration/code/output hashes and run metadata |
| `tests/test_cms_slice.py` | Actual-archive verification plus narrowly synthetic corruption tests |

The WP1 commands need no third-party packages, database, API keys, customer information or running server. The two scope files are reviewed configuration, not a national product taxonomy. Do not promote nested benefit codes by guessing from field names.

## Local read view and carrier corroboration

```sh
python3 scripts/validate_naples.py fetch
python3 scripts/research.py build
python3 scripts/research.py verify
python3 scripts/research.py serve --port 8765
```

Open `http://127.0.0.1:8765/`. The loopback server exposes only fixed read assets/APIs, collects no private facts and rejects writes and commercial query inputs. The view preserves all 70 records/32 exclusions, supports up to three comparisons in source order and exposes exact source lineage. The real carrier sample corroborates twelve monetary fields on five records; three wrong-plan/county/year candidate documents are rejected. Rebuilding PDF corroboration requires Poppler's `pdftotext`. There are no Python package dependencies. See [WP2](../docs/WORK_PACKAGE_2.md).

## Prescription evidence extension

```sh
python3 scripts/prescription.py fetch
python3 scripts/prescription.py build
python3 scripts/reference_evidence.py fetch
python3 scripts/reference_evidence.py build
python3 scripts/prescription.py verify
python3 scripts/reference_evidence.py verify
python3 scripts/prescription.py query --plan H5434-002-000-2027 --ndc 00002143380 --pharmacy-npi 1609197854 --out /tmp/naples-drug-evidence.json
python3 scripts/audit_prescription.py /tmp/naples-drug-evidence.json --out /tmp/naples-drug-audit.json
```

The actual CMS download is **2.29 GB**. It contains nested ZIPs; the six national network text parts are streamed, not fully expanded. The market cache retains all matching source rows, including 3,506,965 complete plan-network rows and 79,793 formulary rows for 61 matched Naples records. Capture files are deterministic gzip pipe files in the ignored raw cache; the small reports/manifests stay under `reports/work-package-3/`. The independent auditor reads original ZIP rows directly rather than trusting the capture parser's output.

Exact NDC11/RxCUI and NPI queries preserve source conditions, blanks, zero and typed cost shares. There is no 2027 pricing table in this monthly release; the latest quarterly pricing source inspected is for 2026. It cannot supply 2027 costs. Two premiums, the drug quantity unit, source-date tokens and actual layout differences remain explicit open questions. The source registry records the specific CMS agreement accepted in Chrome under the user's authorization; no changed future agreement is accepted automatically by the fetch command.

`reference_evidence.py` replays actual NLM vocabulary and NPPES identity snapshots plus carrier/OIR supplier diligence. Public endpoints can change: fetch refuses bytes that differ from the pinned snapshot. Recover exact captures or inspect/register a new version. The NPPES visible documentation text was captured through Chrome; a missing copy needs explicit recovery/recapture, not substitution of a JavaScript HTML shell.

When the prescription and public-reference manifests are present and valid, `research.py serve` also enables the labeled public drug example. It leaves the confirmed product unset, performs no outside request from the browser and computes no personal price, ranking or purchase result. See [WP3](../docs/WORK_PACKAGE_3.md), the [action reference](../ACTION_REFERENCE.md), and the [remaining dependency ledger](../docs/EXECUTION_STATUS.md).
