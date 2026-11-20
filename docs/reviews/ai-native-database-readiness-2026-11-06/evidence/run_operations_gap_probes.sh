#!/bin/sh
# Isolated local evaluation. No existing service/database is used or changed.
set -eu
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
PG_BIN="$ROOT/infrastructure/daylight-data/.postgres18/bin"
PROBE_WORK=$(mktemp -d)
cleanup() { "$PG_BIN/pg_ctl" -D "$PROBE_WORK/data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$PROBE_WORK"; }
trap cleanup EXIT
"$PG_BIN/initdb" -D "$PROBE_WORK/data" -U ops_probe_owner --auth=trust >/dev/null
"$PG_BIN/pg_ctl" -D "$PROBE_WORK/data" -o "-p 55432 -k $PROBE_WORK -c listen_addresses=''" -l "$PROBE_WORK/log" -w start >/dev/null
"$PG_BIN/psql" -X -q -v ON_ERROR_STOP=1 -h "$PROBE_WORK" -p 55432 -U ops_probe_owner -d postgres \
  -f "$ROOT/infrastructure/daylight-operations/migrations/001_operations.sql"
"$PG_BIN/psql" -X -q -A -t -v ON_ERROR_STOP=1 -h "$PROBE_WORK" -p 55432 -U ops_probe_owner -d postgres \
  -f "$ROOT/docs/reviews/ai-native-database-readiness-2026-11-06/evidence/operations-gap-probes.sql"
