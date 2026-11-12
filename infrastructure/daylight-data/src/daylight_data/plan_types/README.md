# Collier plan-type backend (D96)

This additive package prepares and serves the retained **2026 Collier** PDP and
Medigap evidence for private developer source inspection. It does not serve
consumer data, determine current sale, quote a person, rank plans or enroll anyone.
The existing compact research tables, sealed parsers and all UI surfaces stay
unchanged. Public evidence only: beneficiary facts do not belong in this schema.

## Build and load

Use the existing daylight-data virtualenv and its unchanged 38-package lock.
`runtime-requirements.lock` is an exact separate copy, included in the installed
package. Prepared manifests bind the Python version, dependencies, package code,
SQL schema, selected source hashes and original manifest/audit hashes.

From `infrastructure/daylight-data`:

```sh
export PYTHONPATH="$PWD/src"
.venv/bin/python -m daylight_data.plan_types prepare \
  --repository /Users/cep4u/daylight \
  --selection config/plan-types.2026.r1.json \
  --output .state/plan-types/NEW-CANDIDATE
.venv/bin/python -m daylight_data.plan_types verify-bundle \
  --bundle .state/plan-types/NEW-CANDIDATE
```

Preparation is offline, checks the 7 GiB reserve, rejects an existing output,
checks inputs before/after execution and validates the declared populations.
Incomplete preparations have no final manifest. Each compressed stream retains
source pointers, exact native payloads, typed projections and payload hashes.
Original Decimal source values retain exact strings; money uses integer cents.

Supply the intended database explicitly, never an app SQLite path or discovered
`.env` credentials:

```sh
export DAYLIGHT_PLAN_TYPES_DATABASE_URL='host=/private/socket port=55485 dbname=EXACT_DATABASE user=MIGRATION_OPERATOR'
.venv/bin/python -m daylight_data.plan_types install --expected-database EXACT_DATABASE
.venv/bin/python -m daylight_data.plan_types load --expected-database EXACT_DATABASE \
  --bundle .state/plan-types/NEW-CANDIDATE
.venv/bin/python -m daylight_data.plan_types select-research \
  --expected-database EXACT_DATABASE --build-id EXACT_BUILD_ID \
  --reason 'Select the verified developer research candidate; consumer display held'
```

`install` only creates `dl_plan_types` and its dedicated roles. It does **not** run
the legacy migration chain against the retained compact views. Existing schema
SQL must match exactly; future schema changes need a new reviewed migration.
`load` commits a source's records/checkpoint together, rejects changed streams,
checks counts and exact schedule links, and seals completion. Rerunning the same
load checks and reuses completed source checkpoints. An interrupted source rolls
back while earlier sources remain available for exact resume.

Loader, research-reader, reviewer and publisher privileges are separate. Runtime
roles cannot approve evidence. Completed sources/builds and event history reject
update/delete and late evidence insertion. Only completed builds can be selected
for research. Selection events retain operator identity, time and reason. Rollback
is a new selection of an earlier complete, unstopped, runtime-compatible build;
do not overwrite source rows or silently reuse an incompatible runtime.

## Research reads and pricing boundaries

The CLI `inspect` takes a JSON file containing, for example:

```json
{"reference_year":2026,"county_fips":"12021","intended_use":"developer_source_inspection","kind":"pdp_offering","page_size":100}
```

```sh
.venv/bin/python -m daylight_data.plan_types inspect \
  --expected-database EXACT_DATABASE --build-id EXACT_BUILD_ID --request REQUEST.json
.venv/bin/python -m daylight_data.plan_types status \
  --expected-database EXACT_DATABASE --build-id EXACT_BUILD_ID
```

PDP queries join county to region to exact offering, with no per-county policy
duplicates. Medigap discovery includes source-observed leads and unknown sale
status; it is not a confirmed complete product catalog. A filed-rate query
requires an exact `entity_key` and optionally an ISO `on_date` within 2026.
It joins the exact schedule; it does not guess a form edition or county area.

Filed amounts marked replaced, zero/unresolved, unknown-period or out-of-period
have `supported_rate_cents: null`. Their exact raw source values remain available
for authorized research. A supported source-grid amount is still not a personal
quote. Annual illustrations and monthly tables retain their own bases and holds;
they do not inherit a filed annual schedule or approved billing calculation.
All conditional/native fields remain in `payload`/`conditions`.

The fixed-schema API uses the same repository:

```sh
export DAYLIGHT_PLAN_TYPES_EXPECTED_DATABASE=EXACT_DATABASE
export DAYLIGHT_PLAN_TYPES_BUILD_ID=EXACT_BUILD_ID
# Configure separate random secrets in the server environment, never the browser:
# DAYLIGHT_PLAN_TYPES_SERVICE_TOKEN; DAYLIGHT_PLAN_TYPES_CURSOR_SECRET
.venv/bin/python -m uvicorn daylight_data.plan_types.api:build_app \
  --factory --host 127.0.0.1 --port 8898 --no-access-log
```

Use a dedicated login with only `daylight_plan_research_reader`, not the migration
operator. Login/secret provisioning is separate from the NOLOGIN group roles.
Connections are read-only with a bounded four-connection pool and statement
timeouts. Remote hosts require `sslmode=verify-full`; target database and exact
build/runtime bindings are checked. Moving a source bundle does not require the
original repository or machine OID. Actual-target TLS, permissions, secret setup,
load and recovery checks remain required before cloud deployment.

Routes:

| Route | Behavior |
| --- | --- |
| `GET /health` | Liveness and held consumer state, no DB details |
| `GET /internal/plan-types/ready` | Authenticated exact build, counts and capability-specific approval holds |
| `POST /internal/research/plan-types/query` | Authenticated bounded developer source inspection, maximum 100 records |
| `GET /internal/plan-types/metrics` | Authenticated aggregate counters only; no request bodies or secrets |
| `POST /v1/plan-types/query` | Always HTTP 503 pending exact data approval and a separately reviewed consumer implementation |

No consumer-enable flag exists. Service authentication does not accept sources.
Requests reject personal/commercial inputs and unsupported geography/year. Cursors
bind request, principal and exact build; selection changes invalidate them.
Research results carry source paths/hashes, native qualifications, dates, unknowns,
release holds and a deterministic verification receipt. Do not send this private
research route to the browser or put its output into consumer AI context.

## Approval, changes and source STOPs

`review` is an offline privileged command requiring an external original receipt,
an identical replay copy and an operator-controlled trusted-reviewer registry.
The `daylight-plan-type-review/1` contract in `authority.py` binds exact build,
source collection, code, scope, capability, gate, reviewer qualification and
independence, dispositions, actual review time and expiry. Source-use, method and
output decisions are separate append-only events. The newest event controls a
gate; expiry and revocation hold it. No trust assignments or genuine acceptance
receipts are created by the implementation. Existing narrow legacy receipts are
not automatically broadened or translated into new approval.

Even fully accepted fixture gates retain
`CONSUMER_DISPLAY_DISABLED_PENDING_DATA_APPROVAL`. Enabling consumer output needs
a future reviewed change after actual acceptance; receipts alone do not switch it
on. This is deliberate while new sources remain unaccepted.

Use `stop --build-id ... --reason ...` to append a durable serving STOP. It
invalidates all reads, readiness and reselection of that build. Source-specific
STOPs use `--source-id` and also block later builds reusing that exact source.
They conservatively hold the whole affected build. No clearing command exists.
Existing acquisition STOPs remain in their original evidence; all acquisition is
offline and no routine connector/scheduler is enabled here.

`diff --before BUILD --after BUILD` compares completed versions by source path,
kind, native key and pointer, reporting changed/added/removed rows. It is bounded
to 1,000 entries with an explicit truncation flag. Candidate preparation and
review remain separate from selecting the next research version. Results remain
version-bound; never label an earlier receipt current after selection changes.

## Verification and open work

Run fictional checks with:

```sh
.venv/bin/python -m pytest tests/test_plan_types.py -q
# PostgreSQL tests additionally require the documented isolated local _test DSN.
```

`tools/verify_plan_types.py` checks **every typed column and payload** against the
portable prepared streams in a read-only transaction, then checks authenticated
PDP retrieval and held consumer/personal/unauthenticated requests. It does not
rerun the original PDF extraction or establish source meaning/approval.

Still required: the complete Collier Medigap product/form/current-sale denominator,
other-company documents, exact approved Blue intervals/form editions, unresolved
modal precision/discount/fee/rounding/SELECT/group conditions, qualified R15 and
source/method/output acceptance. The source worklist is retained among imported
research records. Personal PDP cost methods and Medigap rights/underwriting/quotes
remain separate capabilities. Hosting, scheduled acquisition, advisor integration
and consumer display are not activated by this package.
