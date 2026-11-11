# Isolated preflight and pending deployment

The later persistent fifteen-layer build has a separate
[local operating runbook](PERSISTENT_LOCAL.md) and exact completion/query/recovery
receipts. The original `daylight_data_test` checkpoint below remains retained;
do not apply new migrations to it as part of the persistent build.

This runbook describes the tested local checkpoint. Full restore/release operations and
cloud deployment remain unimplemented; do not use these commands as a production runbook.

The project-local PostgreSQL build is `.postgres18/`; its private data/socket/archive live
under `.state/`, ignored by Git. The isolated test database is `daylight_data_test`, using
socket `.state/socket`, port identifier 55485, TCP disabled. Do not point commands at
either application's SQLite files, runtime source or budget database.

From `infrastructure/daylight-data/`:

```sh
export PYTHONPATH="$PWD/src"
export DAYLIGHT_DATA_DATABASE_URL="host=$PWD/.state/socket port=55485 dbname=daylight_data_test user=cep4u"
.venv/bin/python -m daylight_data.cli health
.venv/bin/python -m daylight_data.cli migrate
.venv/bin/python -m daylight_data.cli import-layer --layer L01 \
  --repository /Users/cep4u/daylight --archive "$PWD/.state/archive" --projections
.venv/bin/python tools/capture_preflight.py
```

`migrate` requires the isolated migration owner. `import-layer` explicitly narrows to
`daylight_writer`, even when supplied an owner DSN. Deployments must use separate actual
logins/secret references; fixture `SET ROLE` proof alone is not a deployed credential setup.
Initial immutable transport derivations remain historical; current selected derivations
additionally bind exact adapter/projection code bytes. Re-imports must not delete old runs.

The API skeleton is not launched automatically and no scheduler/connector is enabled.
Internal results require exact source-use permission; consumer results remain held until
the original authority and required release checks are implemented and pass.

Clean local shutdown preserves all imported data:

```sh
.postgres18/bin/pg_ctl -D .state/pgdata stop -m fast
```

Restart only this cluster, using its private socket:

```sh
.postgres18/bin/pg_ctl -D .state/pgdata -l .state/postgres.log \
  -o '-h "" -k /Users/cep4u/daylight/infrastructure/daylight-data/.state/socket -p 55485' start
```

On this host, PostgreSQL shared memory/Unix sockets require an approved sandbox escalation.
No command initializes, drops or replaces an existing app store. Fixture tests create/drop
uniquely named disposable databases only from an explicit project-local `_test` DSN.

Before paid cloud provisioning, resolve actual account/project, region, private database,
bucket, service identity, secret references, cost and retention/backup settings. No account,
cloud resource, cost authorization or qualified source-use approval is inferred from the
local test. Preserve synthetic-only remote preparation until applicable processing review.
