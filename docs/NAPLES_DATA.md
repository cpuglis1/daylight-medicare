# Naples / Collier County: real-data checkpoint

Added October 17, 2026, before continuing to WP2. This uses the same pinned **2027** CMS landscape/PBP release as New York, preserving comparable scope and source lineage. Retirees themselves and caregivers are both intended direct users; no consumer application or ranking is introduced by this data extension.

## Geography confirmed before querying

The [City of Naples](https://www.naplesgov.com/codeenforcement) explicitly places the city in Collier County. The pinned Census county file identifies **Collier County, FL, FIPS `12021`**, at record ordinal **334**. CMS uses the exact state/county labels `FL` / `Collier`. The [versioned alias](../cms-slice/data-sources/markets.json) records the city evidence separately from the Census county identity.

The result is a Collier County query appropriate to the City of Naples request. It does not infer an individual's residence from a Naples mailing address or ZIP, extend into Lee County, or imply that every county in Southwest Florida is interchangeable. Statewide PDP records match `FL` exactly and retain the source label `All Counties`.

## Verified inventory

See the [query](../cms-slice/reports/work-package-1/market-12021-2027.json) and [market profile](../cms-slice/reports/work-package-1/market-12021-2027-profile.json).

| Source category | All matching source records | Included comparison view | Excluded from current comparison scope |
|---|---:|---:|---:|
| MA-PD | 23 | 20 | 3 regional PPO |
| MA | 9 | 7 | 2 regional PPO |
| PDP | 11 | 11 | 0 |
| SNP | 27 | 0 | 27 |
| **Total** | **70** | **38** | **32** |

There are **59 Collier county rows** and **11 statewide Florida PDP rows**. All **70** identities have matching PBP filenames and payload identities; no PBP payload is missing and no landscape/PBP plan-name conflict was observed in this market. The complete payloads total **16,313,662 uncompressed bytes**.

The comparison scope remains ordinary HMO, HMO-POS, PPO and PDP, as in New York. The five ordinary regional PPO records and 27 SNP records remain accessible with explicit reasons. Exclusion is an experiment-scope decision, not an eligibility verdict. Their full raw source data is included in the export.

## Complete raw source capture

Download the [Naples / Collier source ZIP](../cms-slice/reports/work-package-1/market-12021-2027-sources.zip). It contains:

- `landscape.csv`: all 70 rows and all 53 fields, preserving leading zeros, whitespace, negative currency notation and sentinel strings. This is a derived CSV serialization; exact source-record locators are retained separately.
- `pbp/`: **all 70 complete JSON members copied byte-for-byte**, including excluded options and unmodeled nested benefits/nulls.
- `landscape-lineage.json`: original CSV member/hash, record ordinal, identity and comparison disposition for each row.
- `market-query.json` and `market-profile.json`: included records, exclusions, geography, counts and explicit gaps.
- `release.json`, `field-mapping.json` and original `landscape-readme.txt`: pinned sources, documented mappings and original source instructions.
- `manifest.json`: source/configuration/code identity, SHA-256 for every other exported file, and any missing PBP identities. Here the missing list is empty.

The ZIP has fixed member timestamps and ordering so repeated exports on the tested runtime are deterministic. Tests compare every exported PBP member to the original national archive and every CSV field to the original source records. All market PBP identities are verified before export, including excluded records. No benefits are decoded from undocumented field names.

For example, `H1032-198-000-2027`, Wellcare Giveback (HMO-POS), appears at landscape record ordinal **11,936**. Its published Part D basic component is `"($2.00)"`, supplemental component `"$2.00 "`, and total `"$0.00 "`. These become **−200**, **200** and **0 cents**, preserving the negative component rather than clipping it. The raw PBP member `H1032-198-000-2027.json` is present. This is a parsing/lineage example, not a recommendation or personalized quote.

## Reproduce

From `cms-slice/`:

```sh
python3 scripts/cms_slice.py fetch
python3 scripts/cms_slice.py run
python3 scripts/cms_slice.py query --year 2027 --county-fips 12021 --out /tmp/naples-cms-query.json
python3 scripts/cms_slice.py export-market --year 2027 --county-fips 12021 --out /tmp/naples-cms-sources.zip
python3 -m unittest discover -s tests -v
python3 scripts/cms_slice.py verify
```

`run` regenerates all three market queries, the Naples complete-source ZIP/profile, and the national quality/join reports. Original archives remain intact. A standalone export can be made for another already-inspected county; missing PBP evidence stays in its manifest instead of being substituted.

## What “all real data” covers here

This is all matching data in the **pinned landscape and PBP sources**, including source records outside the comparison scope. It does not include every Medicare data family or every potential source correction. It uses 2027 consistently with New York; it does not assert that 2026 is supported or that the pinned release is a permanent latest version.

Still separate: actual drug/formulary/pharmacy/pricing evidence; exact provider/location/network checks; Medigap rates, quotes and underwriting terms; personal eligibility; carrier transaction access and enrollment receipts. Those remain the real-data acquisition dependencies in the [plan](../PLAN_OF_ATTACK.md). Complete raw PBP capture does not satisfy them.

The national Virginia identity gap remains unresolved, even though no such gap was found in Naples. PBP `Submitted` status, undocumented benefit codes, source freshness/use permissions and independent authoritative value checks retain their existing limitations. The [persistence proposal](PERSISTENCE_PROPOSAL.md) remains a review proposal; this checkpoint adds no schema migrations or licensed-purchase capability.
