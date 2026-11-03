# Daylight data infrastructure

Additive D85 implementation, begun October 29, 2026. The target is November 5 in
America/New_York. [The governing plan](../../docs/data/infrastructure-plan-2026-10-29/IMPLEMENTATION_PLAN.md)
and [execution evidence](../../docs/data/infrastructure-execution-2026-10-29/) distinguish
implemented behavior from pending work. This package does not accept new evidence,
change any sealed reference, migrate guest profiles, or release recommendations.

Use Python 3.12+ and PostgreSQL 18/17. Dependencies are pinned in requirements.lock;
the measured local environment uses Python 3.14.7 and PostgreSQL 18.6. Source build
files, private archive and isolated database are ignored. No global PostgreSQL install
or existing service/database is replaced. Container tags are development inputs;
actual-target image digests and cloud restore remain pending.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
export PYTHONPATH="$PWD/src"
# Supply the isolated infrastructure database DSN, never an app SQLite/store path.
export DAYLIGHT_DATA_DATABASE_URL='postgresql://migration-owner@localhost/daylight'
.venv/bin/python -m daylight_data.cli migrate
.venv/bin/python -m daylight_data.cli health
.venv/bin/python -m daylight_data.cli import-layer --layer L01 \
  --repository /Users/cep4u/daylight --archive /private/path/to/archive --projections
```

The archive directory must be private (0700). All fifteen layers now have source-row
adapters and initial research projections. The [local sizing run](../../docs/data/infrastructure-execution-2026-10-30-local-sizing/)
measures full selected source-table populations sequentially in disposable PostgreSQL
databases while preserving the original four-layer research database and a disk reserve.
Its receipts do not establish a simultaneously integrated fifteen-layer service.
After freeing local capacity, the owner authorized a persistent combined database.
The [full local build](../../docs/data/infrastructure-execution-2026-10-30-local-full-db/)
uses `tools/build_local_database.py` to retain the exact fifteen-layer selection in a
separate private database, with atomic raw/projection/checkpoint commits and a 7 GiB
reserve. Its marked target and immutable manifest control resume. The earlier sizing
receipts and original research database remain preserved. Use its documented command
and packet; the general `import-layer` command does not supply these build-specific
ownership, integrated checkpoint and disk-reserve checks.
The completed build-r3 load retains 17,767,179 source/context rows and 17,823,148
initial projections together in `daylight_research_2026_r2` (58,013,032,975 bytes at
load completion). Use [the persistent local runbook](runbooks/PERSISTENT_LOCAL.md);
query verification and backup receipts are separate from the load receipt.
Collier scope IDs remain in the preserved native `fields.id` / `raw_payload.id`;
their material `offering_id` column is unpopulated. The explicit source bridge
checks all 72 IDs against national and r9 offerings without backfilling immutable
rows. That bridge is research validation, not completed domain normalization.
Complete domain-specific relational models, release selection, original-authority
replay, connectors/scheduler, full restore and application bridge remain **pending**. Initial
projection transport deliberately remains separate from source import receipts; neither
receipt proves layer completeness or output acceptance. Parser/config changes require
a new derivation; unchanged rows reuse their immutable identities.

Tests without PostgreSQL run with `.venv/bin/python -m pytest -q`. Integration tests
require an explicit `DAYLIGHT_DATA_TEST_DSN` pointing to a local database whose name
ends in `_test`; they create/drop a unique fixture database rather than alter the two
applications. On the sandboxed host, Unix sockets/loopback require approved execution.

The API is private and read-only. Configure a dedicated research DB login granted only
`daylight_research_reader`, plus separate random service-token and cursor secrets.
Run `python -m uvicorn daylight_data.api.app:build_app --factory --host 127.0.0.1 --port 8897 --no-access-log`.
No browser receives the service token. `/health` exposes no infrastructure details;
`/ready` and `/internal/evidence/query` require service authentication. Internal rows
remain held until their exact source-use permission is established; an internal token
does not establish that permission. Consumer queries fail closed pending exact release
and original authority replay. No personal reports are accepted or logged by these routes.
