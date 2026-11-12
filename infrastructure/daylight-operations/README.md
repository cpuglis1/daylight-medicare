# Daylight operations database

Added November 5, 2026. This is the **customer plane**: decision records,
licensed review, model-call traces, the case queue and enrollment status. It is
a separate PostgreSQL database from the research database in
`infrastructure/daylight-data/`, which holds public evidence only. Nothing here
is wired into :8893 yet, and no customer data has been written to it.

## What it holds

| Schema | Table or view | Purpose |
| --- | --- | --- |
| `dl_ops` | `decision_record` | Inputs, evidence and method versions, candidates, order, ties, exclusions, reason codes, holds and the pre-enrollment checklist receipt (I06). Append-only. |
| `dl_ops` | `licensed_review` | Option B: a licensed agent's sign-off on a decision, with staff minutes. Append-only. |
| `dl_ops` | `model_call_trace` | One row per model call: provider, model, stage, outcome, tokens, latency, request hash. **No prompt, response or transcript content.** |
| `dl_ops` | `work_case`, `work_case_event`, `work_case_current` | Exception and handoff queue; state and staff minutes come from append-only events. |
| `dl_ops` | `enrollment`, `enrollment_event`, `enrollment_current` | Submitted → accepted → effective, from a platform webhook, carrier portal, carrier notice or commission statement. |
| `dl_fulfillment` | `commission_line`, `reconciliation`, `unmatched_lines` | Commission statements matched to enrollments. The commercial boundary. |

## Protections enforced by the database

- Any decision document with a commercial key at any depth (commission, payout,
  compensation, referral fee, carrier contract or appointment, lifetime value,
  revenue) is rejected. Keys only; a plan's `referral_required` term is allowed.
- The app role cannot read `dl_fulfillment`. The fulfillment role cannot read
  decisions or traces, and cannot change enrollment status. Reviewers cannot
  write decisions.
- Trace metadata accepts only `service_tier`, `incomplete_reason` and `attempt`.
  Visit references must be opaque SHA-256 digests.
- Decisions, reviews, traces, cases and enrollment events cannot be updated or deleted.

## Python package

`src/daylight_operations/`:

- `tracing.py`: `ModelClient` names the call shape both advisor clients already
  share (`count`, `transport`). `TracingClient` wraps a client, records one
  `TraceEvent` per call and returns the result unchanged. A failed trace write
  increments `dropped` and never fails the user's turn. `PostgresSink` writes rows.
- `records.py`: `build_decision_record` builds the `decision_record` row and
  refuses commercial keys with the same rule as the database.
- `checklist.py`: the twelve CMS pre-enrollment checklist items.
- `database.py`: checksummed, apply-once migrations, same contract as the research database.

## Checks

```sh
cd infrastructure/daylight-operations
PYTHONPATH=src python3 -m pytest -q                               # 30 offline tests
PG_BIN=/opt/homebrew/opt/postgresql@18/bin sh tests/run_sql_tests.sh   # migration, 21 rejection and 4 positive SQL checks
```

The SQL script starts a throwaway cluster in a temporary directory; it never
touches an existing database. On November 5 it passed on PostgreSQL 16.15, and
each rejection was checked for its exact error code. It has not yet been run on
PostgreSQL 18, the version the research database uses.

## Connecting traces to :8893 (not applied)

This changes the live advisor runtime, so it waits for an explicit go-ahead.
Clients are created in one place, `alternatives/advisor-first/server.py` line 93
(`clients = model_clients(...)`). No advisor code type-checks clients, so a wrapper is transparent:

```python
from daylight_operations.tracing import PostgresSink, TracingClient
import psycopg

sink = PostgresSink(lambda: psycopg.connect(os.environ["DAYLIGHT_OPS_DATABASE_URL"], autocommit=True))
clients = {name: TracingClient(client, sink, surface="advisor-8893", provider=MODELS[name].provider)
           for name, client in model_clients(base.client, REPO / ".env").items()}
```

Before enabling it: create the `daylight_operations` database and a login
granted only `daylight_ops_app`, run the migration, and confirm that traces are
covered by the same retention and privacy rules as the budget ledger. The
request hash is derived from prompt content; it is not reversible in practice,
but it stays inside the customer-data boundary.
