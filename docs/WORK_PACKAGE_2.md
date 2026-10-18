# Work package 2: local Naples comparison and corroboration

Implemented October 17, 2026. This is an engineering review slice for retirees researching their own coverage and caregivers helping someone else. It remains local and read-only. Public-use/operating approval, qualified domain sign-off and a consumer accessibility/comprehension study remain separate gates.

## What works

- A file-backed read model pins the actual Naples source release, configuration, code and validation artifacts. No SQL migration or private customer schema was needed.
- A bounded read API serves all 70 source records, the 38-record comparison scope, all 32 exclusions and exact raw field/provenance detail.
- A browser view lets the researcher inspect sources and compare up to three in-scope records. Selection preserves source identity order and changes no source facts. There is no suitability ranking, AI explanation, quote or purchase action.
- Monthly premium labels use the correct source field: consolidated C+D for MA-PD, Part C for MA-only, and Part D total for PDP. Inapplicable consolidated/drug/medical fields remain inapplicable rather than becoming zero.
- Only the five sampled records and twelve specific monetary fields receive carrier corroboration metadata. The remaining 65 records and other fields do not inherit that label.

## Independent carrier sample

The [validation report](../cms-slice/reports/work-package-2/validation.json) and [pinned source registry](../cms-slice/data-sources/validation.json) cover five records across MA, MA-PD and PDP, all from one carrier. This is a purposive sample, not a statistical estimate or nationwide certification.

| Record | Carrier document | Monetary checks |
|---|---|---|
| H5434-002-000-2027 | BlueMedicare Select, 2027 Summary of Benefits, FBM2813 | Consolidated premium, Part D deductible and in-network medical limit agree |
| H5434-045-000-2027 | BlueMedicare Select, 2027 Summary of Benefits, FBM2814 | Consolidated premium, Part D deductible and in-network medical limit agree |
| H5434-042-000-2027 | BlueMedicare Patriot, 2027 Summary of Benefits, FBM2825 | Part C premium and in-network medical limit agree |
| S5904-001-000-2027 | BlueMedicare Premier Rx, 2027 Summary of Benefits, FBM2829 | Part D total premium and deductible agree |
| S5904-002-000-2027 | BlueMedicare Complete Rx, same two-column document | Part D total premium and deductible agree |

All twelve checked amounts agree. Benefit year, contract-plan identity, coverage category/name and county/state scope were checked on the covers. These summaries do not print segment 000; the prior CMS payload join remains the segment evidence. There is no claim of independent carrier confirmation of every identity component.

The carrier's [Select](https://www.floridablue.com/medicare/forms/h5434-bluemedicare-select-ppo), [Patriot](https://www.floridablue.com/medicare/forms/h5434-bluemedicare-patriot-ppo) and [Premier Rx](https://www.floridablue.com/medicare/forms/s5904-bluemedicare-premier-rx) pages link the exact PDFs. Download receipts pin retrieved bytes/URLs/dates. Original PDFs/HTML are kept in the ignored raw cache. Covers and relevant page 3 tables were read; all four positive tables were rendered and visually checked. The narrow parser checks inspected table anchors and PDP column identities/order; it is not a generic insurance PDF ingestion engine.

Three real candidate documents are rejected: the same Select name under the wrong plan ID; Select H5434-047 for Monroe instead of the requested Collier plan; and a 2026 Patriot summary. A 2026 marketing/approval footer on a correctly dated 2027 cover does not cause a false year rejection. This distinction is tested.

## Display implications

A published annual drug deductible does not establish how a particular medicine is treated. The checked summaries contain tier/insulin qualifications, so the view explicitly asks the researcher to keep drug-specific conditions open. Medical MOOP is not an all-expense ceiling. Plan premiums do not remove other Medicare obligations. Component premium splits, ratings, opaque PBP codes and `Submitted` status were not independently checked by this sample.

The UI explains those limits while preserving access to full source detail. An excluded plan's raw source record remains inspectable, but it is not promoted into the supported comparison view. Neither a checkbox nor a comparison constitutes selection for an application.

## Run and verify

From `cms-slice/`:

```sh
python3 scripts/validate_naples.py fetch
python3 scripts/research.py build
python3 scripts/research.py verify
python3 -m unittest discover -s tests -v
python3 scripts/research.py serve --port 8765
```

Then open `http://127.0.0.1:8765/`. Only the first command needs network access for missing validation artifacts. Poppler's `pdftotext` is required to rebuild the carrier checks. The server uses the generated read files and verifies their input/output hashes at startup. It binds to loopback, accepts only the supported market/year, exposes fixed read resources, rejects commercial query arguments and all writes, and does not collect private information.

The observed full suite passed **39 tests**. Checks cover actual documents, adjacent-plan/year/county mistakes, PDP column swaps, amount conflicts, source/cell replay, read-file tampering, source-order comparisons, unsupported input, nonpublic file paths, untrusted Host headers and write rejection.

Chrome's Codex extension was used for browser QA after native computer-use access was unavailable. The actual page loaded 70 records, compared MA-PD/MA/PDP correctly, enforced the three-record limit, opened evidence, exposed all 32 exclusions and cleared selection. The 390px mobile check had no horizontal document overflow. Desktop and mobile screenshots are [saved with the evidence](../cms-slice/reports/work-package-2/comparison-desktop.png). This is not a complete accessibility audit or proof of retiree comprehension.

## Remaining gates and next work

This implementation proves the bounded source-to-view path. It does not approve source redistribution, insurance activities, legal claims, source freshness intervals or the launch market. Independent domain approval and broader sample validation remain open. No database is necessary at this volume/query shape; revisit persistence when consented saved cases or real update requirements are implemented.

The next data package is actual formulary/pharmacy/pricing evidence. Its file release, benefit year, layout, use agreement, join grain and price scope must be inspected independently before any medicine or cost claims are added. Ready to purchase remains reserved for the future qualified, licensed-agent workflow.

That next engineering slice is now recorded in [WP3](WORK_PACKAGE_3.md). The same view includes a clearly labeled public drug example when its real source manifests are present. It does not change the WP2 comparison order/scope or turn the sampled monetary checks into full-plan verification.
