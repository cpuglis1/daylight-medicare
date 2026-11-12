# Compact research snapshot: local recovery

This recipe targets the existing private PostgreSQL 18 instance. Use a new empty
database and a new output path. It does not require the original research DB or
either temporary working DB. It does not change an application binding or grant
consumer authority. The full dump excludes cluster-global roles and external
source files; retain the original evidence archive and source paths separately.
Another machine needs role/bootstrap and connection configuration plus its own
recovery validation.

The private packet is `.state/maintenance/20261105-db-r2/`. Retain its
`backup.json`, `complete.json`, `recovery-verified.json`, operator hashes and
`compact-full.dump.gz`. The archive SHA256 is:

`d3b19beffa7f59da5fb285958232b93b0c58381e971a19e6e9fcaaea3e73b154`

Before starting, verify that hash and require free disk of at least
`complete.json.database_bytes + 9 GiB` (7 GiB reserve plus 2 GiB workspace).
Do not decompress the archive to a second large disk file. Roles referenced by
the dump must exist; they already exist in the tested local instance.

Run from `infrastructure/daylight-data/`, choosing a target that does not exist:

```sh
set -o pipefail
export DAYLIGHT_RECOVERY_TARGET=daylight_compact_manual_restore_test
export DAYLIGHT_RECOVERY_DSN="host=$PWD/.state/socket port=55485 dbname=$DAYLIGHT_RECOVERY_TARGET user=cep4u"
.postgres18/bin/createdb --host="$PWD/.state/socket" --port=55485 --username=cep4u "$DAYLIGHT_RECOVERY_TARGET"
gzip -dc .state/maintenance/20261105-db-r2/compact-full.dump.gz |
  .postgres18/bin/pg_restore --exit-on-error --no-owner --dbname="$DAYLIGHT_RECOVERY_DSN"
.postgres18/bin/psql "$DAYLIGHT_RECOVERY_DSN" -X -v ON_ERROR_STOP=1 -f redesign/r2/post_restore.sql
.venv/bin/python -B tools/verify_recovered_compact.py \
  --database "$DAYLIGHT_RECOVERY_TARGET" \
  --receipt .state/maintenance/20261105-db-r2/recovery-verified.json \
  --output .state/maintenance/compact-manual-recovery-verification.json
```

The post-restore index is derived from retained data and preserves legacy text
record-ID equality queries. Its full concurrent rebuild is tested during the
live deployment. The standalone verifier checks population, every sealed
metadata table, every original source/projection checkpoint hash, all offering
columns, index/constraint validity and the empty consumer view. Its fixture test
uses nonexistent original and candidate database names to prove independence.

Keep any failed target and logs for diagnosis. Never force-drop an existing
database or alter release/permission state to make verification pass. Promotion
requires explicit binding/ownership and feature checks; successful data recovery
alone does not activate a release. The original physical backup also remains
retained. Cold-cluster recovery, off-machine recovery and PITR are separate work.
