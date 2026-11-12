# Collier C02–C05 completion evidence

C01 is deferred by owner instruction. C02–C05 are complete. Selected engineering test release: `naples-63ae25f4b9a870fe7848`. The original release `naples-7a0b8eff1577df6e41eb` and prior engineering candidates remain as artifacts. Full R1 and qualified domain sign-off remain pending.

| Item | Result | Evidence |
| --- | --- | --- |
| C02 | Preserved 70 catalog / 61 drug / 59 medical / 31 packaged baseline, source hashes and coverage/issue ownership table | [Baseline](c02/baseline.json), [coverage table](c02/coverage.md), [retrieval receipts](c02/source-receipts.json) |
| C03 | Fresh catalog retrieval; monthly and quarterly distributions unchanged; next review 2026-10-21T01:33:00.069116+00:00 | [Discovery](c03/discovery.json), [assessment](c03/change-assessment.json), [prior receipt](c03/previous-catalog-receipt.json) |
| C04 | 24 contracts, 72 independently extracted CSV/XLSX cell comparisons, all 70 records sourced; 68 numeric displays and 2 stated CMS unrated reasons | [Ratings](c04/ratings.json), [checks](c04/independent-check.json), [technical-note review](c04/technical-review.json) |
| C05 | 61 networks packaged; all 61 drug plans and 9 MA-only records replayed offline from extracted bundle; 20-plan pages | [Offline replay](c05/extracted-bundle-replay.json), [selection receipt](c05/selection-receipt.json), [166 passing tests](c05/tests.log) |

The historical workbook, issue rows and counts were not rewritten. [Closure receipts](closure-receipts.json) supplement DQ-002, DQ-010 and DQ-014. App/workbook regeneration remains C34.

The offline replay ran without network access, national archives, PDF tools or a model key. Each drug plan was checked against captured-row formulary and pharmacy queries, including newly accessible SNP and Regional PPO records. Both chat adapters reject incomplete paginated comparisons. Drug-cost calculation remains unavailable and SNP eligibility remains unconfirmed.

The candidate review deadline is 2026-10-21T01:33:00.069116+00:00: the earliest of the retained upstream engineering deadline (2026-10-25T03:04:03+00:00), fresh catalog deadline, and new star-source deadline (2026-10-27T01:33:00.060988+00:00). Packaging unchanged inputs does not renew their source reviews.

Measured on this machine: startup 0.220 s; peak RSS 164.3 MB; largest cold page 1.639 s; cached 20-plan page 0.208 ms; snapshot 50.0 MB. Measurements are a single synthetic replay, not a production benchmark. No additional index was added.

Validation command: `python3 -m unittest discover -s tests -v` from `cms-slice/`. Source and bundle replay commands are documented in `cms-slice/README.md`. A browser check confirmed labeled CMS stars on the local plan cards. Live model calls were mocked in regression tests; no paid model evaluation was run. The temporary QA server was stopped.
