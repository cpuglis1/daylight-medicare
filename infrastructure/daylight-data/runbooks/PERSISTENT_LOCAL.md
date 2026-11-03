# Persistent fifteen-layer local research database

This build retains the exact selected 2026 research populations together in
`daylight_research_2026_r2`. The current execution packet is
`docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3/`.
`LOAD_COMPLETE.json` proves the load; a passing `QUERY_VERIFICATION.json` proves
the specified integrated research queries. Neither grants source-use permission,
semantic acceptance, personal applicability or a consumer release.

The separate `daylight_data_test` database and the zero-evidence first setup
attempt `daylight_research_2026_r1` remain retained. Never initialize, replace or
drop these databases to rerun a measurement. The original applications keep their
own SQLite profiles and budget ledger; this build contains metadata for the
41-question, 78-field, 14-gap contract and no customer profile migration.

Run from `/Users/cep4u/daylight/infrastructure/daylight-data`:

```sh
export PYTHONPATH="$PWD/src"
export DAYLIGHT_DATA_DATABASE_URL="host=$PWD/.state/socket port=55485 dbname=daylight_research_2026_r2 user=cep4u"
.postgres18/bin/psql "$DAYLIGHT_DATA_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -c 'SELECT current_database(),pg_size_pretty(pg_database_size(current_database()))'
```

TCP is disabled. The socket and data directory are private and ignored by Git.
This local process is not an automatically started production service. See
`PREFLIGHT.md` for this cluster's stop/start commands; do not run its historical
`migrate` example against the retained original database.

## Exact resume

Only after the current invocation has exited, with its code/configuration and
receipts unchanged, rerun the same build command. Never run a second coordinator
against an active target. The database OID, shared catalog marker, cluster system
identifier, selected source hashes, code and selected sizing receipts bind resume.
The loader never drops a database. A changed implementation requires a new execution packet and explicit revision
accounting. This recovery uses the same owned database and unchanged creation
marker, with schema 2 linking the preserved r2 execution, dump and 122 producers.
Only the driver transport changed; source/adapter/schema identities are frozen.

```sh
export DAYLIGHT_DATA_ADMIN_DSN="host=$PWD/.state/socket port=55485 dbname=daylight_data_test user=cep4u"
.venv/bin/python tools/build_local_database.py \
  --repository /Users/cep4u/daylight \
  --summary /Users/cep4u/daylight/docs/data/infrastructure-execution-2026-10-30-local-sizing/SUMMARY.json \
  --output /Users/cep4u/daylight/docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3 \
  --archive "$PWD/.state/archive" --database daylight_research_2026_r2 \
  --batch-size 1000 --reserve-gib 7 \
  --predecessor-packet /Users/cep4u/daylight/docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r2
```

Raw rows, projections and checkpoints commit atomically. Original source ordinals
survive windowing and partial resume. Source stops are honored; a checkpoint or
receipt is never permission to bypass them. A disk-reserve failure preserves
committed rows. Free space and the original failure must be understood before
resuming. Do not lower the 7 GiB reserve to finish a run.

## Read-only verification

This requires a completed exact load. It reconciles all 363 selected windows,
source/derivation metadata and checkpoints, tests the Collier bridge and Florida
PDP relationships, and preserves r9 canonical obligations and all release holds.
It uses one consistent read-only snapshot and bounded fixed queries. The output
path must be new; preserve previous verification attempts.

```sh
.venv/bin/python tools/verify_local_database.py \
  --repository /Users/cep4u/daylight \
  --output /Users/cep4u/daylight/docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3/QUERY_VERIFICATION.json
```

Research SQL may use `SET ROLE daylight_research_reader` and `BEGIN READ ONLY`.
The released-reader view is intentionally empty. Do not add permissions or select
a release to make an empty consumer result look complete.
The Collier scope bridge uses the retained `fields.id` and checks exact raw-parent
identity. Its material `offering_id` column remains unpopulated; the query does not
backfill it or grant semantic acceptance. Storage functions requiring database
privileges are measured in the initial owner read-only phase, with domain queries
remaining under `daylight_research_reader`.

## Private logical backup

The backup operator requires the exact completed r2 target. It streams a custom dump wrapped in bounded Python gzip to a new private file, checks the free-space reserve, hashes the
completed bytes, lists its contents, and decodes every block to SQL without
executing it. Existing `BACKUP.json` or `BACKUP_TOC.txt` is never overwritten.

```sh
.venv/bin/python tools/backup_local_database.py \
  --repository /Users/cep4u/daylight \
  --packet /Users/cep4u/daylight/docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3 \
  --reserve-gib 7
```

`BACKUP.json` records the actual path, hash, bytes and decode result. A successful
decode is not a tested clean-database restore. The custom dump excludes the
external content-addressed evidence archive or cluster-global role definitions;
retain `.state/archive/` and recreate the required roles for a logical restore.
Neither a dump nor an APFS clone on this disk supplies off-machine recovery.

## Physical recovery status

The optional cold-cluster operator is prepared and its mechanics have mock tests.
It was not executed. Automatic action review rejected the attempted checkpoint
stop/restart and whole-cluster clone for service-disruption/filesystem risk.
The recorded alternative was a consistent read-only logical dump; no service
stop, rename, physical clone or SQL restore occurred. Do not retry the rejected
service action through an indirect command as part of this run.

`LOGICAL_CHECKPOINT.json` in the preserved build-r2 packet records the partial
execution checkpoint, compressed-byte hash, gzip CRC and full custom-archive
SQL decode without execution. Its 122 completed receipts and 1,000-row interrupted
prefix remain linked from schema 2. Current 363 execution jobs and historical 123
jobs are separate cohorts; do not add their receipt row totals as physical rows.

A clean logical restore, physical recovery, off-machine backup and PITR remain
separate untested gates. PostgreSQL's
[whole-cluster filesystem backup guidance](https://www.postgresql.org/docs/18/backup-file.html)
requires a clean shutdown for ordinary per-file copying.

## Remaining operating gates

The actual receipts must identify which recovery and query checks ran. Typed
domain-model expansion, useful service/API integration, per-source permission,
independent semantic review, release acceptance, clean logical restore,
off-machine backup and target deployment retain separate obligations. No scheduled
source acquisition or paid cloud resource is enabled by this local build.
