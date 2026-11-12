# Held benefit cells: CMS published text (candidate)

Created November 9, 2026 for DQ-31 (validation gap G-07). Built by
`build_overlay.py` from files already in the repository; re-running it
reproduces `held-cells-published-text.json` byte for byte.

The r13 display candidate holds 141 of 720 benefit cells under Daylight's own
interpretation rules, although CMS publishes text for every one. This overlay
gives each held cell its published text, verbatim with markup removed, and the
label it would carry:

| Outcome | Cells | Rule |
| --- | --- | --- |
| Published-text candidate | 103 | Shown as published, labeled "As shown on Medicare.gov (CMS Plan Finder benefit summary, file dated Dec 23, 2025)"; the 2 Part D deductible cells use the CY2026 Landscape |
| Remains held | 38 | All cells on the 6 plans whose sources conflict: H1032-241, H1032-243, H1036-340, H1609-078, H1889-026, H2509-003 (DQ-32) |

Every source-conflict reason code in r13 falls on those 6 plans. Computed cost
examples are untouched and stay held until their method is reviewed.

**Status:** candidate, not loaded. D92 keeps all r13 material holds, and the
catalog and publication gate are hash-pinned, so this changes nothing until the
owner decides DQ-31 and a new catalog revision adopts it.

**Open:** the benefit summary file is dated December 23, 2025. The founder's
Plan Finder session (DQ-30) checks whether Medicare.gov shows the same text today.
