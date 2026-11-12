# D86 local test allowance — $5 per UTC day

On October 30, 2026 the owner asked the current test limit and authorized increasing it to $5. The prior :8893 allowance was $1 per UTC day. The reviewed local policy now permits **$5 per UTC day for :8893**, using the same aggregate ledger and counting all prior usage/holds. It is not an additional $5 balance and does not purchase API credits.

## Implementation

- `alternatives/advisor-first/budget-policy.json` fixes the approved cap at 5,000,000,000 nano USD and the reset timezone at UTC. Environment variables and requests cannot raise it.
- `advisor_budget.py` adopts the existing budget object as a local subclass before the service is returned. The pinned factory's HTTP closure and all its agents retain that same object. Only cap-dependent summary and reservation methods change; pricing validation, ledger transactions, measured settlement, uncertain holds, clock rollback checks and cross-midnight accounting remain inherited.
- `natural_agent.py` reserves both stages atomically against that instance's cap. Existing callers using the original budget still use $1. The 8,000-input / 900-total-output per-request bounds and no automatic model retry remain.
- The pinned shared engine, :8890/:8891 sources/runtimes, guest records and shared ledger are preserved. Those older surfaces keep their stricter $1 policy; all their spending still counts toward the aggregate seen by :8893. They can reach their lower limit before :8893 does.

The production ledger is `cms-slice/var/ai-budget/usage.sqlite3`. This change does not reset or refund any row, release uncertain charges or change pricing verification dates.

## Verification and activation

[Controlled tests](tests.log) cover shared accounting, exact $5 rejection, atomic two-stage reservations, concurrent calls competing for the same headroom, unchanged token limits, retained rows/inodes, uncertain carryover, settlement, pricing expiry, clock reversal, strict policy validation and service object references. All tests use synthetic temporary ledgers; no paid model calls are made for this change.

Only the :8893 launchd job is restarted. [Live status](runtime-status.json) verifies the active cap and retained accounting without generation. [Read-only preservation check](check_preservation.py) compares protected file hashes and existing row hashes against this change's snapshots; [results](preservation-after.json) record any differences without emitting personal values.

Final results: **188 tests pass** in 6.388 seconds. The live endpoint reports a $5 limit, $0.555257 accounted ($0.387757 measured estimates plus $0.1675 held) and **$4.444743 remaining** for this UTC day. All 77 protected files, all pre-existing database rows and database inodes are unchanged. This change added zero ledger rows and made zero paid calls. [Implementation hashes](build-manifest.json).

**Provider availability remains a separate blocker.** The previous live test returned `insufficient_quota` / `credit_balance_exhausted`, documented in [the natural-flow packet](../natural-advisor-flow-20261030/README.md#live-checks-and-actual-blocker). Raising this local allowance does not replenish provider credits. No further live model requests, billing changes or credit purchases are attempted here.

This addresses D86's explicit budget revision only. It changes no UI, profile/context permission, source acceptance, commercial independence or recommendation gate.
