# Manual Plan Finder evidence packet

Prepared November 10, 2026 for DQ-30 and DQ-33. The [two-page worksheet](plan-finder-worksheet.pdf) is fillable or printable on US Letter in landscape. Save the completed copy as `plan-finder-worksheet-filled.pdf` beside it. Place original PNGs in `screenshots/` and put any overflow notes beside the completed worksheet.

## What to capture

- Use guest browsing and the 2026 plan year for every pass. Record the actual date, county, results count, filters and any eligibility or assistance choices. Capture the year, ZIP and county selection at the start, then every results page or scroll batch. Use the Collier branch for 34134. If the site offers only 2027, cannot confirm Collier, or hides SNPs behind a filter, keep a screenshot of that state and mark the affected rows `?` until the comparable view is available. Use fictional inputs if the site requires them.
- Record any extra plan's displayed ID, name, type and SNP type, and the screenshot where it appears. Record partial IDs as shown. The same plan name may appear for multiple segments.
- For each detail page capture the exact plan ID and the relevant sections. Keep text for any network, assistance, deductible, tier, or charging-unit qualifications. Use the corresponding screenshot or an overflow note for wording that does not fit. The drug pass compares the five exact products, including brand, release form, or vial versus pen where specified. If the site does not show a flag or amount, enter `NS`. Use `N` for an explicit negative.
- Use `YYYY-MM-DD_2026_ZIP_COUNTY_KIND_ID-or-VIEW_01.png` with the actual ZIP and county. For example, `2026-11-10_2026_34134_Collier_list-ma_all_01.png` and `2026-11-10_2026_34102_Collier_benefit_H1889-026-000_02.png`. The kinds are `list-ma`, `list-pdp`, `benefit` and `drug`. Advance the sequence for each capture within the same view or plan. If year or county differs, use what the site actually shows in the filename and note why it differs.

## Pinned Daylight baselines

| Source | SHA-256 |
| --- | --- |
| [r11 listing](../../docs/product/recommendation-scope-2026-11-04-r11/display-candidate.json) | `7a5f572334d0c47a019e2ce397cf26e16f3ecd7a8114fd28604e501eaabda382` |
| [L02 build-r5 Collier offerings](../../docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json) | `cab771cebb27a1c80f9077b4ba5e9f3005368c214bff5d16fa7cd8f7467987d7` |
| [L04 build-r4 Florida PDP records](../../docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json) | `bb706ac4d32f4efe16689ae452e6c4bb519f7287f65f4182b25b03ce800fd547` |
| [r13 display candidate](../../docs/product/recommendation-scope-2026-11-04-r13/display-candidate.json) | `ba625a2968a53a46dc72dddf52a4e74064b56b0b14e55c9e8768d2b580fa3609` |
| [December 23, 2025 CMS benefit summary workbook](../../docs/data/mpf-benefit-summary-2026-11-04-r1/source/MPF_BenefitSummary_CY2026_12232025.xlsx) | `d961e55cb5088984d6bb657205be4de90957477718ee37aab22d70b38c72cd6d` |
| [L05 build-r3 plan-to-formulary map](../../docs/data/l05-drug-coverage-2026-10-25/build-r3/plans.csv) | `ed46890779d275cd87849aee719a7180c1b3333e0617cdb7ff7fdc7cefcc91b3` |
| [L05 build-r3 September basic rows](../../docs/data/l05-drug-coverage-2026-10-25/build-r3/basic.csv.gz) | `c6612627d3fb4115a51dfa4fe30147b6ea1270c4e806a1f29329d54413d64c9e` |
| [L05 build-r3 drug identities](../../docs/data/l05-drug-coverage-2026-10-25/build-r3/identities.json) | `57d53df5b352c1528bc2568a5972becbe202f6027964c2ebf5ca8045faeffbd1` |

The worksheet separates network type from SNP subtype and keeps all three components of the plan ID, including leading zeros. The Collier list is a dated county reference. [Daylight ZIP/county reference](../../docs/ZIP_COUNTY_REFERENCE.md)

The HMO and PPO sample provides two published-value comparisons with different deductible and spending-limit terms. The D-SNP tests the emergency and urgent care source disagreement and the assistance basis of quoted values. The C-SNP tests condition-specific variations. The giveback plan tests the Part B reduction and how the medical deductible applies to inpatient care. Compare the owner’s screenshots with the original workbook rows and their bases separately from r13’s display dispositions. A live wording difference can show changed terms in Plan Finder. A revised workbook or other dated CMS publication would be needed to establish that the downloadable file itself was corrected. [Extracted Collier workbook rows](../../docs/data/mpf-benefit-summary-2026-11-04-r1/collier-main.jsonl) · [Held-cell source comparison](../../docs/product/held-cells-published-text-2026-11-09/README.md)

The drug pairs exercise tier and quantity differences for common generics, prior authorization for Ozempic, step therapy for fluvastatin, and vial insulin. The QL column preserves the raw flag, amount and days from the September PUF. Record the site's physical unit as shown.

| Worksheet product | RxCUI | Plan ID | Formulary/version | Source row in September basic drug member |
| --- | --- | --- | --- | --- |
| Atorvastatin | 617310 | S4802-146-000 | 00026195 / 18 | 457925 |
| Atorvastatin | 617310 | H1036-311-000 | 00026412 / 17 | 996812 |
| Metformin HCl | 861007 | H1036-217-000 | 00026411 / 16 | 994315 |
| Metformin HCl | 861007 | H1889-026-000 | 00026002 / 23 | 9929 |
| Ozempic | 2619154 | S4802-146-000 | 00026195 / 18 | 456270 |
| Ozempic | 2619154 | H1036-311-000 | 00026412 / 17 | 995121 |
| Fluvastatin | 310404 | S4802-146-000 | 00026195 / 18 | 456443 |
| Fluvastatin | 310404 | H1036-217-000 | 00026411 / 16 | 991946 |
| Lantus vial | 285018 | H5434-002-000 | 00026250 / 18 | 568669 |
| Lantus vial | 285018 | H1889-026-000 | 00026002 / 23 | 7073 |

[Retained September CMS members](../../docs/data/l05-drug-coverage-2026-10-25/build-r3/source-members.json)

## Preparation checks and next step

The r11 and r13 `--check` replays passed. The 72 r11 IDs, names, types and SNP classes matched L02, and the 10 L04 Florida IDs, names and types matched across its CSV and JSON. All ten drug-pair rows matched the retained CMS basic drug member by exact formulary version, product, source row and restrictions. The rendered PDF has two pages, all 82 exact inventory IDs, 50 benefit inputs and 50 drug inputs. The form field check verified all 350 blank, printable inputs and a sample save/reopen on both pages.

Part B awaits the completed worksheet and screenshots. The comparison will log every observed difference and unresolved item, record DQ-30 and DQ-33 evidence, and assess G-06, G-09 and G-12. The automated collector STOP, r13 field holds and owner sign-off for display changes remain in effect.
