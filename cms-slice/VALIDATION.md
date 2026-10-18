# Validation record

The October 17/18 demo follow-up passed **115 full-suite tests**, plus affected demo/package checks after the static NLM attribution was added. See the [current execution receipt](reports/demo-execution-receipt.json), [re-audit](../docs/NAPLES_DEMO_REAUDIT.md) and [execution guide](../docs/DEMO_EXECUTION.md). The original WP1–3 checkpoints below are preserved as history, including their earlier counts.

Checked October 17, 2026, on Python 3.14.7 and Poppler `pdftotext` 25.04.0. This records engineering verification, not insurance suitability, operating approval or consumer outcomes.

| Check | Observed result |
|---|---|
| Fresh CMS downloads | Both archive sizes and SHA-256 values match the original reconnaissance manifests |
| `python3 scripts/cms_slice.py run` | 130,307 landscape rows; 7,969 parsed PBP payloads; all three county queries and complete Naples source ZIP/profile generated |
| Final `python3 -m unittest discover -s tests -v` | **58 tests passed**, 29.066 seconds; [full log](reports/test-run-20261017.log) |
| `python3 scripts/cms_slice.py verify` | Source, code, configuration and all declared output hashes verified |
| Second full `run --out /tmp/medicare-cms-naples-replay-20261017` | **All ten derived files byte-identical**, including the complete Naples source ZIP; run-manifest timestamps are intentionally different |
| Standalone CLI query/export | Naples query and complete source ZIP compared to delivered files |
| CLI unsupported Naples ZIP as county | Exit code 2; no output file created; no input substitution |
| Naples full source preservation | All 70 PBP members byte-identical to original archive; all 53 CSV fields replay for all 70 records, including exclusions |
| Original bundle manifest | **44 original files** still match their recorded sizes/hashes |
| New documentation local links | All targets present |

WP1 code SHA-256: `5bdb6c58d0c19b913373abee5d595373f0751d82018bef2aad003cba01064de9`.

Original WP1 test-file SHA-256: `94cce62ea7f2f58b1701b7a3f0d9a198d94107ffd71d81e72045dcffc697d490`. Additional tests now cover the actual carrier, read API, prescription and public-reference paths.

The delivered [run manifest](reports/work-package-1/run-manifest.json) pins source versions, code/configuration identity and each derived output hash. Re-run `fetch`, `run`, the test command and `verify` from this directory to repeat the checks. Independent replay compares the two manifests' `outputs_sha256` maps and verifies the actual files.

## WP2 and WP3 verification

| Check | Observed result |
|---|---|
| Real carrier sample | Five records / twelve monetary fields agree; three real wrong-plan/county/year candidates rejected; only those fields carry corroboration |
| Read model build and verify | All 70 Naples source records, 38 comparison options and 32 exclusions; code/configuration/assets/upstream/output pins verified |
| Real prescription source | 2,290,695,063-byte CMS October archive for 2027; 13 actual nested data archives and documented layout/date/encoding differences inspected |
| Prescription capture | 61 exact plan/geography joins; 24 formularies; 79,793 basic rows; 3,506,965 complete plan-network rows; costs/supplemental/insulin data retained |
| Candidate premium/deductible comparisons | 120 agreements and two retained premium conflicts, both excluded D-SNPs; exact identity/geography and alternative-segment checks recorded |
| Independent full prescription replay | **All 66 gzip captures plus quality, premium-discrepancy and manifest files byte-identical** in a separate output/cache directory; [receipt](reports/work-package-3/replay-verification.json) |
| Independent sample source replay | All raw cells in ten returned plan/formulary/beneficiary/insulin/pharmacy rows matched original nested ZIP records; [audit receipt](reports/work-package-3/query-source-audit.json) |
| Public reference replay | Four actual NLM brand candidates remain unconfirmed; exact proxy mapping retained; NPPES mailing-first case parsed by explicit address purpose; no provider/quote facts manufactured |
| Additional missing-PBP probe | The October Part D source contains the exact H3931-143-000 identity, unsuppressed, with 16 exact state/county matches through SSA locator rows; no PBP or cause is inferred; [follow-up](reports/source-diligence/missing-pbp-followup.json) |
| Final source/read verifiers | `research.py verify`, `prescription.py verify` and `reference_evidence.py verify` all passed |
| Chrome Codex extension | Plan comparison/source/exclusion flows; actual drug/pharmacy lookup; changed product/PDP case; unchanged 38-option membership/order; desktop/mobile screenshots |
| Final frontend | Source booleans read as Yes/No; cost types/percentages retained; lookup controls re-enabled and product label bound to request; 390px viewport and document width both 390 |
| Original archive | All 44 files still match their bundle manifest; no archived code imported or modified |

The [Chrome observation record](reports/work-package-3/browser-qa.json) pins final frontend assets/screenshots. The [read manifest](reports/work-package-2/read-manifest.json), [prescription manifest](reports/work-package-3/manifest.json) and [reference manifest](reports/source-diligence/manifest.json) pin their respective implementation and input/output identities. The final full test run includes source corruption, wrong identity/year/county, amount conflict, raw null/zero/type semantics, exact plan/drug/pharmacy joins, post-startup capture tampering, unsupported/commercial query inputs, file/Host/write guards and brand/location ambiguity.

The unresolved Virginia source gap, opaque status/benefit codes and source-use/domain approval remain open. WP3 adds unresolved quantity units, source-date tokens, two premium-basis discrepancies and missing 2027 pricing. The sample and engineering checks do not certify every source fact. No schema migration, personal ranking, quote, enrollment, operating approval or policy outcome is validated by this record. See [WP3](../docs/WORK_PACKAGE_3.md) and the [execution ledger](../docs/EXECUTION_STATUS.md).
