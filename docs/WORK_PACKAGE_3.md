# Work package 3: actual 2027 prescription evidence

Inspected October 17, 2026. The working slice captures real Naples / Collier plan, formulary, cost-sharing and pharmacy-network evidence. It provides exact-code queries and a public example in the local browser view. It does not calculate a personal prescription price, annual drug cost, suitability ranking or purchase readiness.

## Sources and actual layout

The [CMS monthly dataset](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information) exposes October 2026 as the latest release for 2027 benefits. The CMS use agreement was accepted through the Codex extension in Chrome after the user explicitly authorized the pending agreement. The browser's bundled download preparation was canceled to avoid a duplicate transfer; the same actual artifact was then fetched directly from the distribution URL in CMS's documented public catalog. No agreement was bypassed.

The pinned archive is `2027_20261008.zip`, **2,290,695,063 bytes**, SHA-256 `5f3bbe4e9ca29bce965403f3780d66452ec446cef5bf01fa050d3c6a990f053c`. The [registry](../cms-slice/data-sources/prescription.json) pins the official methodology/layout PDFs, exact outer/inner members, nested hashes, actual headers and encodings. The full archive, nested compressed members and retrieval receipts remain in the ignored source cache. The national network text is streamed, not expanded to disk.

There are eight table families, with the pharmacy network split into six parts: 13 inspected nested data archives, plus a separate sample archive. The samples were inspected for layout and are never substituted for full data.

Observed differences from a casual reading of the documentation:

- Collier's locator row is **SSA county code `10100`**, with MA region `09` and PDP region `11`. The reviewed Census geography remains **FIPS `12021`**. These are different code systems; neither is inferred from the other by padding or arithmetic.
- The monthly archive contains no drug-pricing table. The latest [quarterly distribution](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/quarterly-prescription-drug-plan-formulary-pharmacy-network-and-pricing-information) is `SPUF_2026_20261007.zip`, contract year **2026**. Its methodology describes plan-level average monthly unit costs. It is not imported into a 2027 query or labeled an actual pharmacy fill price.
- Actual network headers use `SELECTED_DISPENSING_FEE_*`; the layout says `SELECTED_DRUG_DISPENSING_FEE_*`. Actual insulin amount headers are lowercase. The capture retains observed names; it does not silently rename them to match a guessed schema.
- The plan-information file is not entirely ASCII despite the methodology's description: observed bytes `0xD3` and `0xE1` occur in names outside this market. A byte-preserving Latin-1 decode is explicitly registered for that file; no bytes are dropped or replaced. ASCII remains strict for the other inspected files.
- Outer filename and HTTP last-modified say October 8, catalog metadata was modified October 15, and inner member names contain **October 31**, a future date at inspection. This unresolved naming/date discrepancy is visible in queries and the browser. No claim of data current as of October 31 is made.
- Pharmacy numbers contain the literal prefix `10` followed by the ten-digit NPI. Both the raw 12-character number and the separate queried NPI remain strings.

## Joins, full capture and quality

The [quality report](../cms-slice/reports/work-package-3/quality.json) records the full scanned table counts, inner hashes/headers, source ordinals, selected grains, versions and null states.

| Evidence | Observed result |
|---|---|
| All Naples landscape records considered | 70, including exclusions |
| Exact contract-plan-segment plus source-geography matches | 61 drug-bearing records, each one Collier/region row |
| Other landscape records | Nine MA-only records; expected absence from the Part D PUF, not missing drug benefits filled from another plan |
| Suppressed among matched records | None; future/unknown suppression is not treated as usable data |
| Distinct matching formularies | 24, each with one observed version in this release |
| Captured basic-formulary rows | 79,793 |
| Captured beneficiary cost rows | 1,771 |
| Captured supplemental excluded-drug rows | 229 |
| Captured insulin cost rows | 415 |
| Captured indication-specific rows | Zero for these contract-plans; the national table has 112 rows |
| Captured full plan-network rows | 3,506,965, across all six national parts; no ZIP-based county filtering |
| Duplicate tested formulary / selected plan-pharmacy candidate grains | None |
| Candidate premium/deductible cross-checks | 120 agreements; two premium disagreements, retained below |

All matching raw cells and original line endings are captured in deterministic gzip pipe files with table/part and source-row metadata. For an exact query, the response identifies the source archive, nested text member and ordinal. The capture includes excluded SNP/regional records as evidence; their presence does not expand comparison scope. Network rows describe the plans' complete published networks, not just pharmacies physically in Naples.

Blank spaces remain different from empty strings, absent fields and reported zero. Cost-share type `0` means **not offered**, even if an accompanying amount is `0`; type `1` is a dollar copay; type `2` is a fraction for coinsurance. For example, raw `0.25` is 25%, not 25 cents. Unknown types, missing amounts and invalid numeric values stay unresolved. Coverage phase, tier, supply category, pharmacy channel, minimum/maximum and deductible/insulin conditions remain attached to their actual rows.

## Discrepancies and independent checks

Two excluded D-SNPs have PUF `PREMIUM=0.00` versus landscape Part D total `$7.30`: `H1889-026-000-2027` and `H5594-017-000-2027`. The first has 66 PUF county rows, all with the same zero premium; the second has one. Each has exactly one matching Collier row and no alternative segment. Their landscape LIS-adjusted beneficiary premium is zero. That is a useful observation, not evidence authorizing replacement of the premium mapping. Source-date and premium-basis differences remain possible explanations requiring authoritative clarification. The repeatable [discrepancy ledger](../cms-slice/reports/work-package-3/premium-discrepancies.json) retains both values, surrounding fields and original lineage.

The carrier's actual 2027 formulary, linked from the inspected Florida Blue Select page, prints formulary ID `00027047` and covers H5434-002/045. Its October 15 version, PDF page 64 / printed page 48, corroborates tier 3 and prior authorization for the inspected Trulicity 0.75 mg/0.5 ml product. Both carrier and CMS specify a 28-day quantity interval. CMS raw quantity is `2`; the carrier says `4 pens`. The inspected CMS field definition does not state that quantity's unit. NLM supplies packaging/concept evidence, but no quantity conversion is silently approved. The report flags this unit question rather than calling the amounts either a validated match or a confirmed conflict.

The [public-reference report](../cms-slice/reports/source-diligence/observations.json) pins the real NLM responses: an October 5 RxNorm version, exact RxCUI `1551300`, and proxy NDC `00002143380`. A brand-only Trulicity search returns **four specific strength/form concepts**. It leaves the confirmed product unset. Vocabulary identity is not coverage or a prescribed quantity. The carrier document does not print this proxy NDC; the report distinguishes the NLM mapping from carrier corroboration.

NPPES supplies an actual Naples location for pharmacy NPI `1609197854`; the exact `101609197854` row is listed in the chosen plan's pinned network. The UI calls this dated network evidence and leaves current store operation unconfirmed. NPI identity alone still proves no doctor's plan participation, licensure, credentialing or accepting-patient status.

## Run and inspect

From `cms-slice/`:

```sh
python3 scripts/prescription.py fetch
python3 scripts/prescription.py build
python3 scripts/reference_evidence.py fetch
python3 scripts/reference_evidence.py build
python3 scripts/prescription.py verify
python3 scripts/reference_evidence.py verify
python3 scripts/prescription.py query --plan H5434-002-000-2027 --ndc 00002143380 --pharmacy-npi 1609197854 --out /tmp/naples-drug-evidence.json
python3 scripts/audit_prescription.py /tmp/naples-drug-evidence.json --out /tmp/naples-drug-audit.json
python3 scripts/research.py build
python3 scripts/research.py serve --port 8765
```

Only fetch commands need the network. A changed mutable API response is not installed under an old snapshot's hash. Recover the original capture or deliberately inspect/register a new snapshot. The visible NPPES documentation capture is a Chrome artifact and is recovered or recaptured explicitly. Poppler is required for rebuilding carrier PDF checks. Both build and query preserve source year and identifiers; shorthand plan IDs, ten-digit unpadded drug codes, brand names in an RxCUI field, unsupported markets/years and commercial ranking arguments are rejected.

For an independent full capture, use `prescription.py build --out /tmp/naples-rx-replay --cache /tmp/naples-rx-replay-cache`. The generated manifest covers report/code/config/input identities and every compressed capture. The loopback API verifies source/capture integrity at startup and checks the captures used in each lookup against its startup-pinned hashes. No external medicine search, analytics, personal profile or submission occurs from this page.

The delivered [query example](../cms-slice/reports/work-package-3/query-example.json) was also checked by an independent source reader: all returned raw cells in ten plan/formulary/cost/insulin/pharmacy rows replay to the original nested archives. The [audit receipt](../cms-slice/reports/work-package-3/query-source-audit.json) pins the query, auditor and nested source hashes. This includes pharmacy part 4 row 26,281,555, not a lookup against a sample file. The browser example was exercised through the Codex Chrome extension at desktop and 390px width; the latter had no horizontal document overflow. This is engineering QA, not a consumer comprehension study.

The separate full replay produced **66 byte-identical compressed captures** and byte-identical quality, premium-discrepancy and manifest files. See the [replay receipt](../cms-slice/reports/work-package-3/replay-verification.json). The final complete suite passed **58 tests** in 29.066 seconds; the [validation record](../cms-slice/VALIDATION.md) links exact evidence and limits.

The new national Part D source also supports a focused follow-up on WP1's Virginia gap. `check_missing_pbp.py` finds the exact H3931-143-000 identity in 16 unsuppressed rows and matches all 16 landscape state/county labels through the SSA locator. The [follow-up](../cms-slice/reports/source-diligence/missing-pbp-followup.json) keeps that evidence separate from the still-missing PBP payload and leaves its cause unresolved.

## Acceptance still open

This completes a real ingestion/query/evidence slice, not the entire prescription package's consumer acceptance. Missing basic-formulary evidence alone is not labeled noncoverage; supplemental and indication cases need proper resolution. A real person's medicine, strength/form, quantity, days, pharmacy and subsidies remain unconfirmed. Independent domain review, broader restriction checks, quantity units, the two premium discrepancies, source-date clarification and a usable 2027 price source remain open. Insulin schedules are preserved but do not trigger an invented calculation. Annual scenario costing and ranking stay unavailable until their exact inputs and rules are proven.

Medigap quotes and exact clinical provider-network evidence are separate dependencies. No vendor adapter, quote success, underwriting acceptance, licensed agent session, submission, effective policy or retention result has been fabricated to pass the later work packages.
