# SPEC-D5: approved content-free usage contract

November 8, 2026 · D99 approves per-participant usage tracking against one $100
whole-pilot limit. D101 approves the numeric contract and retention. Hosted
schema integration and retention enforcement still need verification.

## Existing contract

`infrastructure/daylight-operations/src/daylight_operations/tracing.py` already
records provider, model, operation, stage, outcome, token/cache counts, latency,
opaque visit reference and request digest. Its metadata permits only
`service_tier`, `incomplete_reason` and `attempt`. Do not open that dictionary to
arbitrary keys. The current wrapper is best effort: failed trace writes do not
stop a model call. That behavior cannot enforce a spending ceiling.

## Proposed additional typed record

Use an additive `pilot-usage-v1` schema and durable accounting ledger. Existing
sealed or append-only tables retain their exact definitions until a separately
reviewed migration adds the necessary version and expiry role. No blanket DELETE
permission for the application or reviewer.

| Field group | Allowed values | Purpose |
| --- | --- | --- |
| Linkage | Random opaque cohort/participant/session/invitation references; no email/name hash or content-derived identifier | Relate calls and cumulative participant usage across sessions without a personal quota or conversation content. A restricted mapping remains outside telemetry. |
| Classification | Fixed pool (`guest`, `saved`, `checkout_disabled`), approved provider/model/pricing revision, fixed stage and event enums | Attribute cost, reproduce pricing and reject routing drift. Never accept a client-supplied model/pool label as authorization. |
| Timing | Server timestamp, duration milliseconds, active-duration milliseconds | Reconcile charges and session lengths. No location or raw network/device identifier. |
| Usage | Nonnegative integer input/output/cache-read/cache-write tokens, turn count, tool calls by approved tool-type enum, cache-hit count | Measure activity; never tool arguments/results, document titles or free-form tool names. |
| Money | Reserved, settled and unresolved cost as integer micro-US-dollars; exact approved pricing revision | Avoid floating-point accounting and retain uncertain charges. Unknown remains null/unknown, never zero. |
| Accounting | Fixed states: reserved, settled, released_unspent, uncertain; server idempotency reference | Prevent duplicate charging or refunding ambiguous calls. An interruption does not automatically release the reservation. |
| Session outcome | completed_supported_task, saved, abandoned, handed_off, abuse_ended, budget_paused, unknown | Report all outcomes; completion requires a supported application receipt or explicit founder classification, not a model's claim. |
| Controls | Fixed denial/kill-switch reason codes, count of denials, configuration revision | Demonstrate protection operation. Record no suspicious message excerpts. |
| Retention | Server-created expiry timestamp, contract version | Apply a defined lifetime to detailed usage data. |

No trust score or network-class fields in this pilot; their proposed deferral is
explicit in the scope amendment. Generic errors use fixed codes, never exception
messages, URLs or stack locals. No added prompt/response hashes; existing request
digests are not public or proof that telemetry is anonymous. Reject extra fields,
nonfinite/negative amounts, booleans masquerading as integers and unconstrained
strings before storage. Do not serialize rejected values into validation logs.

## Storage, retention and reporting

Keep usage/accounting inside the approved customer operations environment with
encrypted storage and founder-only audited reads. API/web/access logs must also
exclude invitation tokens, query strings and request bodies. Never use telemetry
to infer recommendation eligibility, personal fit or commercial value.

Propose 90 days from creation for detailed usage data. Authorized expiry removes
eligible detail without granting runtime update/delete rights. Non-identifying
cohort totals may remain for 12 months; no per-person timelines, join keys or
rare health facts in retained aggregates. This lifetime does not change required
security access-audit or legal records; those need separate retention decisions.

Report: total paid/estimated/reserved/uncertain spend; number of attempted and
completed sessions; median and observed maximum among completed sessions;
incomplete-session spending; shared/unattributable cost; date/pricing version;
sample size and missingness. Also show total pilot spend divided by completed
supported journeys, with both numerator and denominator visible; zero completed
journeys means “not available,” not $0. Do not discard abandoned/failed calls or
claim a stable p99 from 20 participants. Reconcile provider totals and retain
evidence that the budget/kill-switch tests worked.

The founder's restricted report must also show each opaque participant's total
settled cost, separate unresolved reservations, tokens, session count and
completed/incomplete sessions across the whole pilot. Keep shared/unattributable
cost separate but included in the $100 total. Guest/saved classifications do not
create pool allowances. No hourly, daily, session or participant dollar ceiling;
no calendar or return-visit reset. Do not double-count reservations as settled
spend. User-level reports stay in the approved operations environment.

## Acceptance work after approval

Fictional tests must prove strict field rejection/redaction, isolation, concurrent
reservations, idempotency, retries/disconnect uncertainty, rollover without
resetting the cohort total, no paid calls during accounting failure, and expiry
without weakening the audit boundary. No agent-run live conversation or paid
probe is authorized. Founder pilot observations remain necessary; schema/tests
alone cannot establish acceptable session cost or user experience.
