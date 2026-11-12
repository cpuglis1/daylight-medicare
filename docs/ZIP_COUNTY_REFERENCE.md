# Daylight ZIP/county reference

The frontend uses a local, dated national reference to resolve a unique county, without sending the entered ZIP to an external geocoder. Plan availability remains governed by the existing 2027 Collier County catalog and consumer-admission gates.

## Source and verification

Reviewed October 21, 2026. The source period is **September 2025**, not a live 2026 lookup. The date and source link appear in the result context.

- Complete [HUD COUNTY_ZIP workbook published by CMS](https://github.com/CMSgov/qpp-eu-data/blob/c2c1de5a2268d006148e24877df5d274a1799f68/staging/2025/COUNTY_ZIP_092025.xlsx), pinned to commit `c2c1de5a2268d006148e24877df5d274a1799f68`.
- County names and states: [2025 Census Gazetteer published in the same CMS source tree](https://github.com/CMSgov/qpp-eu-data/blob/c2c1de5a2268d006148e24877df5d274a1799f68/staging/2025/2025_Gaz_counties_national.txt).
- [HUD's crosswalk documentation](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) explains multiple county rows and missing PO-box-only ZIPs.

The builder reads the **complete workbook**, not CMS's filtered EUC/disaster output. It retains every county association; address weights never pick a county. Results: 39,493 ZIPs, including 11,371 with multiple county matches.

Verified against the complete workbook:

| ZIP | County result | UI behavior |
| --- | --- | --- |
| 34102 | 12021 · Collier County, FL; one row | Resolve automatically; show Change location. |
| 34134 | 12021 · Collier and 12071 · Lee, FL | Ask which county; no preselection. |
| 10001 | New York County, NY | Offer general guidance and Medicare.gov; no Collier records. |
| Missing / unavailable lookup | Unresolved | Ask what the person knows, including unsure; do not assume outside. |

Workbook SHA-256: `c9aa7ba717137175fda15ee693d4f1e7c6db2f21f465ed03cff97104665b9a15`. Gazetteer SHA-256: `1914f0d83243362de83b8ddd298c213b1768d63d62d19464743289abd8bb35b1`. These are also embedded in the generated asset.

## Refresh

Check for a newer complete HUD release before a production launch and at quarterly data maintenance. HUD's current downloads/API may require its own account; no credentials are embedded in this build. Use an authorized download or a complete official publication. Preserve source period, exact URL/version, and original hashes. Do not substitute Census ZIP tabulation areas or an affected-county subset for this postal crosswalk.

From the repository root, rebuild with the new files:

```sh
python3 cms-slice/scripts/build_zip_counties.py \
  --crosswalk /path/to/COUNTY_ZIP_092025.xlsx \
  --counties /path/to/2025_Gaz_counties_national.txt \
  --source-url https://github.com/CMSgov/qpp-eu-data/blob/c2c1de5a2268d006148e24877df5d274a1799f68/staging/2025/COUNTY_ZIP_092025.xlsx \
  --period 'September 2025' \
  --reviewed-on 2026-10-21
```

Update all arguments for the actual replacement release. The standard-library builder rejects malformed or implausibly small input rather than generating a partial map. Compare unique/multiple/missing outcomes, inspect changed associations and names, update this source record, and rerun the frontend geography checks. Regenerate the normal release evidence as required; updating this reference does not grant consumer access to plan data.

The generated asset is `cms-slice/apps/chat/zip-counties.json`. Both the normal local server and synthetic UI fixture server can serve it. The normal server applies the same static-asset admission boundary as the rest of the app. Refresh/restart the local server after changes because it reads fixed assets at startup.
