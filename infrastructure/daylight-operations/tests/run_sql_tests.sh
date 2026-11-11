#!/bin/sh
# Apply every migration to a disposable PostgreSQL cluster and run the SQL
# assertions. Nothing outside the temporary directory is touched.
#
#   sh tests/run_sql_tests.sh              # uses initdb/pg_ctl from PATH
#   PG_BIN=/opt/homebrew/opt/postgresql@18/bin sh tests/run_sql_tests.sh
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
PG_BIN=${PG_BIN:-$(dirname "$(command -v initdb || echo /usr/lib/postgresql/16/bin/initdb)")}
WORK=$(mktemp -d)
PORT=${PORT:-55431}
cleanup() { "$PG_BIN/pg_ctl" -D "$WORK/data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

"$PG_BIN/initdb" -D "$WORK/data" -U ops_test_owner --auth=trust >/dev/null
"$PG_BIN/pg_ctl" -D "$WORK/data" -o "-p $PORT -k $WORK -c listen_addresses=''" -l "$WORK/log" -w start >/dev/null
PSQL="$PG_BIN/psql -X -q -v ON_ERROR_STOP=1 -h $WORK -p $PORT -U ops_test_owner"
$PSQL -d postgres -c "CREATE DATABASE daylight_operations_test"
"$PG_BIN/postgres" --version
for migration in "$HERE"/migrations/*.sql; do
  echo "apply $(basename "$migration")"
  $PSQL -d daylight_operations_test -f "$migration"
done
for test in "$HERE"/tests/sql/*_test.sql; do
  echo "run $(basename "$test")"
  $PSQL -d daylight_operations_test -f "$test"
done
