# 2026 Collier data validation, November 9, 2026

Load and math checks of the 2026 Collier data against CMS and other official
sources, run by Claude at the owner's request in a read-only pass, followed by
the candidate fixes listed at the end. Owner-facing summary and plan:
"Daylight 2026 Collier data readiness plan" (Google Drive) and the Data
Validation tab of the MVP plan sheet. Check types: 1 Load, 2 Math, 3 Method;
only Method needs a qualified reviewer.

## Results

| Area | Compared against | Result |
| --- | --- | --- |
| L01 federal costs | CMS 2026 A/B fact sheet; Medicare.gov | 54/54 fact-sheet values and 16/16 other rows match |
| Plan list (L02, L04) | Landscape 202609, MA service area Oct 2026, SNP report Oct 2026 | 72 MA (32 MA-PD, 11 MA-only, 29 SNP) and 10 PDP match; 134 Collier contracts accounted for (19 individual, 115 employer/union only); PACE missing (G-05) |
| MA benefits shown (r13) | Landscape, PBP, MPF benefit summary (Dec 23, 2025) | 568 shown cells match; 141 held, all with CMS text; 11 N/A; Landscape and PBP agree on MOOP and Part C premium for 72/72 |
| Cost examples (r13) | Recomputed from Landscape and MPF | 200 shown numbers match; 88 held; 18 omit a medical deductible (G-16, method) |
| Formulary (L05) | Sept 2026 formulary PUF, CY26 Formulary Reference File | 71 plans, 26 formularies; 87,075 basic and 309 excluded rows identical; 4,519/4,547 names match (28 from NLM, G-14) |
| Pharmacy networks (L07) | All six Sept 2026 network files (306,634,467 rows) | 4,054,335 scoped rows identical; 90 Collier pharmacies resolved |
| Medigap benefits (L10) | CMS 2026 Medigap guide | 108/108 cells match |
| Help with costs (L12) | SSA POMS; 2026 Extra Help chart | MSP 6/6; LIS copays, deductible and resource limits match |
| SHINE (L15) | CMS, Florida Elder Affairs, Florida Relay | Phone confirmed; listed TTY is Florida Relay's voice line (G-18) |
| Teaching facts | Medicare.gov, CMS Medigap guide | Every number and date in the 18 facts matches |

Not checked: Florida Medicaid and poverty-guideline tables, drug prices (L06,
held), Star Ratings (not built), the live research database (G-04).

## Scripts

`scripts/` holds the one-off check scripts as run. They expect the working
layout of that session (CMS files unpacked next to them) and are the seed for
DQ-08, turning these checks into automated tests on every load. Checks not
listed here were run as inline commands.

| Script | Check |
| --- | --- |
| `l01_cms_check.py` | L01 costs and IRMAA bands against CMS fact-sheet values |
| `mpf_parse.py` | Extracts Collier rows from the MPF benefit summary |
| `cmp.py` | r13 shown benefit cells against MPF and Landscape |
| `ce.py` | r13 cost-example arithmetic |
| `f_cmp.py` | L05 formulary rows against the September 2026 PUF |
| `pn_sample.py`, `pn_full.py`, `pn_hash.py` | L07 pharmacy-network rows against the CMS network files |

`results/r13-premium-flags.json` lists the 11 MA-only premium differences
that resolved to the Part C premium column (69/69 match after that).

## Candidate fixes added (nothing existing was edited)

| Gap / task | New folder | State |
| --- | --- | --- |
| G-02 / DQ-27 | `docs/data/part-d-national-2026/candidate-r1/` (replaced the Nov 9 draft on Nov 10) | Pending owner acceptance |
| G-18 / DQ-34 | `docs/data/l15-local-counseling-2026-10-29/tty-correction-r1/` | Pending owner acceptance |
| G-05 / DQ-29 | `docs/data/l02-ma-availability-2026-10-25/pace-r1/` | Pending owner acceptance |
| G-07 / DQ-31 | `docs/product/held-cells-published-text-2026-11-09/` | Candidate; needs the owner's DQ-31 decision (D92) |

DQ-28 (back up the accepted L01 release) was not done here. Committing it to git was
considered and stopped: `docs/project/publication-policy.json` routes `docs/data/` and
`audit-evidence/` to the private object archive, not GitHub.

No sealed revision, catalog, app file or database was changed. Web sources for
the new files were read with a web reader and not archived; archive them
before acceptance.
