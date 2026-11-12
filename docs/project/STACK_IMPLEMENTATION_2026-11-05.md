# Stack evaluation: implementation record

November 5, 2026 · owner request: review the repository, then implement the
governance document, data pipeline, schema with provider interface and traces,
and evaluation harness from the solo-founder stack evaluation. Deployment
scripts wait for the AWS or Google Cloud decision. Nothing here changes a
running service, a sealed revision, an acceptance record or a protected variant.

## What the review found

The stack evaluation was written without seeing this repository. Several of its
recommendations already exist here in stronger form:

| Evaluation recommended | Already in the repository | Consequence |
| --- | --- | --- |
| Scheduled Python + DuckDB snapshot builder with manifest | `infrastructure/daylight-data/`: nine checksummed migrations, immutable artifact/snapshot/derivation records, adapters for all fifteen layers, a 58 GB research database | Not rebuilt. Routine network connectors are off in `scope.2026.json`, so a scheduled refresh would breach scope. Added a manual, discovery-only release check instead. |
| One Postgres for everything | Research database deliberately holds public evidence only | Customer-side records go in a **separate** operations database. |
| Thin provider interface | Both advisor clients already share `count(payload)` / `transport(payload)` | Named the contract and wrapped it for tracing; no client rewritten. |
| Evaluation harness with five suites | Persona runner (14 scenarios), grounding and hold tests already exist | Harness reuses them; added the missing I01 counterfactual and checklist scoring. |
| Paperclip trial | Already installed and configured (`docs/project/PAPERCLIP.md`) | No change. |
| Consolidate governance | Root `AGENTS.md` 18,896 bytes and advisor `AGENTS.md` 39,201 bytes of stacked dated directives | Done; see below. |

## What was added

| Step | Files | Verification actually run |
| --- | --- | --- |
| Governance | `AGENTS.md`, `alternatives/advisor-first/AGENTS.md`, `docs/project/CURRENT_STATE.md`, `docs/project/DIRECTIVE_HISTORY.md`, `docs/project/directive-history/` | Byte-exact copies of both previous files made with `cp` on the owner's machine; SHA-256 matched the originals. Every relative link in the new files resolves. |
| Release check | `infrastructure/daylight-data/tools/release_watch.py`, `config/release-watch.2026.json`, `tests/test_release_watch.py` | 12 offline tests pass (Python 3.13). Smoke run with saved pages on the owner's machine (Python 3.10). **No live run yet:** neither environment could reach cms.gov. |
| Operations schema | `infrastructure/daylight-operations/migrations/001_operations.sql`, `tests/sql/`, `tests/run_sql_tests.sh` | Migration applied to a disposable PostgreSQL 16.15 cluster; 21 rejection checks each failed with the intended error code, plus 4 positive checks. **Not yet run on PostgreSQL 18.** |
| Provider interface and traces | `infrastructure/daylight-operations/src/daylight_operations/` | 35 offline tests pass, including no-content-in-traces and broken-sink checks. `PostgresSink` tested against a fake connection only; no psycopg driver was available. **Not wired into :8893.** |
| Evaluation harness | `tools/evaluation/`, `alternatives/advisor-first/tests/test_independence_counterfactual.py` | `--check` passes on the owner's machine. The new counterfactual test passes there (3 tests), as do the reused grounding, ranking and stop suites. Full harness run pending on Python 3.11+. |

## Decisions made along the way

- **Commercial boundary is structural.** Commission lines live in
  `dl_fulfillment`, which the app and reviewer roles cannot read. Decision
  records reject commercial keys in the database and in Python, using one rule.
- **Traces carry no content.** Metadata is limited to three short fields; visit
  references must be opaque hashes. This follows the no-transcript-persistence rule.
- **Option B is supported but not decided.** `licensed_review` records a
  licensed agent's sign-off and staff minutes. The owner's preference for
  Option B still needs recording as a numbered decision.

## Not done, and why

| Item | Reason | Next action |
| --- | --- | --- |
| Wire tracing into :8893 | Changes the live runtime; needs explicit go-ahead | Steps in `infrastructure/daylight-operations/README.md` |
| Deployment scripts | Cloud provider undecided | Decide AWS or Google Cloud |
| Live release check | No network access to cms.gov from the work environments | Run `release_watch.py` on the Mac |
| PostgreSQL 18 run of the operations SQL | Only PG 16 was available | `PG_BIN=... sh tests/run_sql_tests.sh` on the Mac |
| Checklist receipts from the advisor | Requires product and counsel decisions on how coverage is recorded | Counsel question 3 in the brokerage plan |
| Canary checks on model requests (rest of I02) | Needs a fixture that captures serialized requests end to end | Next harness addition |
| Release check for MPF benefit summary, Doctors and Clinicians, hospitals | Upstream release identifiers not recorded in config | Record the pinned identifiers, then add families |

## Commands for the owner's Mac

```sh
cd ~/daylight
python3 tools/evaluation/run_suites.py
cd infrastructure/daylight-data && .venv/bin/python tools/release_watch.py --out reports/release-watch-$(date +%F).json
cd ../daylight-operations && PG_BIN=$(brew --prefix postgresql@18)/bin sh tests/run_sql_tests.sh
```
