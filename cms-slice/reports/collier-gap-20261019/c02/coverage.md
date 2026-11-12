# Collier coverage baseline

Release: `naples-7a0b8eff1577df6e41eb`. Extracted: 2026-10-20T01:32:39.481520+00:00.

Historical baseline: 70 catalog / 61 drug-bearing / 59 medical / 31 packaged networks. The original 38/32 evidence scope is retained as history.

This table records C02 status before C03–C05. Later closure receipts supplement it; they do not rewrite these counts. Source publication dates are distinct from this extraction date.

| Layer | Captured | In app | Reviewed | Source | Retrieval date | Open issues | Owner | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original Medicare A/B | not captured | not integrated | pending | CMS annual cost publication | Not captured | R1 coverage gap | analyst | C29: published 2027 figures only |
| Advantage plan list | 59 records | 59 browsable | live-market check pending | CMS landscape / PBP | 2026-10-17 (CMS archive receipts; carrier checks separate) | DQ-005, DQ-006 | data engineering + analyst | C17–C18: two-way ZIP market check |
| Advantage benefit detail | 59 full PBP payloads | selected landscape fields | carrier sample: 16 records / 3 parents | CMS PBP; carrier documents | 2026-10-17 (CMS archive receipts; carrier checks separate) | DQ-006 | analyst | C19: field dictionary and reviewed matrix |
| Standalone Part D list | 11 records | 11 browsable | live-market check pending | CMS landscape | 2026-10-17 (CMS archive receipts; carrier checks separate) | DQ-005 | data engineering + analyst | C18: reconcile statewide PDPs |
| Formularies | 61 drug plans | 31 legacy-scope drug plans | limited drug samples | CMS monthly Part D PUF | 2026-10-17 (PUF retrieval) | DQ-010 | data + app engineering | C05: enable all 61 |
| Drug prices | no 2027 pricing table | unavailable | source feasibility pending | CMS monthly / quarterly inspections | See frozen receipt; no date inferred | DQ-007, DQ-008 | data engineering + supplier owner | C14: source decision; H01 held |
| Pharmacy networks | 61 captured | 31 packaged | C05 extracted-bundle replay pending | CMS monthly Part D PUF | 2026-10-17 (PUF retrieval) | DQ-010 | data + app engineering | C05: package 61 with capability-based access |
| Doctor/hospital networks | dated hospital notices | notices; exact participation unresolved | 59 plan mappings pending | Hospital pages; directory discovery | See frozen receipt; no date inferred | DQ-009 | data engineering + analyst | C15, C26–C28: hospital table and qualified APIs |
| Stars | landscape columns blank | unavailable | 24 contract joins pending | CMS 2027 star data tables | See frozen receipt; no date inferred | DQ-002 | data engineering | C04: sourced numeric or nonnumeric state |
| Medigap products/rates | source diligence only | no product/rate dataset | pending | Florida OIR / CHOICES | See frozen receipt; no date inferred | DQ-011 | supplier owner + analyst | C09, C22–C24: request, capture, reconcile |
| Medigap buying rules | limited education | limited education | full rules review pending | Medicare / Florida guidance | See frozen receipt; no date inferred | DQ-011 | analyst | C25: sourced rules and boundaries |
| Help programs | not captured | not integrated | pending | SSA / Florida DCF / SHINE | See frozen receipt; no date inferred | R1 coverage gap | analyst + app engineering | C31: may-qualify screener and referral |
| Enrollment/penalties | limited education | limited education | pending | Medicare official guidance | See frozen receipt; no date inferred | R1 coverage gap | analyst + app engineering | C30: windows and compatibility checks |
| Other plan types | not reconciled | not integrated | pending | AHCA / CMS | See frozen receipt; no date inferred | R1 coverage gap | analyst | C06: Hope PACE and dated searches |
| Local counseling | not verified | not integrated | pending | Official Collier SHINE directory | See frozen receipt; no date inferred | R1 coverage gap | analyst | C07: verify usable referral |

## Existing issue ownership

| Issue | Owner | Next action |
| --- | --- | --- |
| DQ-001 | national data engineering | H06: retain national missing-PBP issue; outside Collier gate |
| DQ-002 | data engineering | C04: import and independently check all 24 contracts |
| DQ-003 / DQ-004 | analyst | C21: explain premium basis or display both values |
| DQ-005 | data engineering | C17–C18: extend Medicare.gov observation and reconcile market |
| DQ-006 | analyst | C19: carrier checks for all displayed core fields |
| DQ-007 | data engineering + supplier owner | C14: price feasibility; H01 remains held |
| DQ-008 | data engineering | C14: retain separate filename, publication, period and retrieval dates |
| DQ-009 | data engineering + analyst | C15, C26–C28: mapped network evidence |
| DQ-010 | data + app engineering | C05: 61 packaged and queryable networks; extracted-bundle proof |
| DQ-011 | supplier owner + analyst | C09, C22–C25: product universe and rates/quote routes |
| DQ-012 | qualified domain reviewer | C36: named review of exact candidate hash and scope |
| DQ-013 | national data engineering | H06: retain 148-identity field-variation issue |
| DQ-014 | data engineering | C03: new catalog retrieval, change assessment and deadline |

Owners are role assignments from the plan, not claims of named staffing. Source hashes and historical parser versions are in baseline.json. C34 will align the regenerated workbook with the eventual candidate release.
