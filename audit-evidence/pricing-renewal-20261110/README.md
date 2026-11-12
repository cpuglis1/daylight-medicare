# Local AI pricing review renewed

November 10, 2026 ET (November 11 UTC). The owner requested unpausing the
local advisor after its pricing review expired. This is maintenance under
D86/D90, preserving the existing $15 per-provider UTC-day allowance.

Observed before: both :8893 and :8894 reported `canRequest: false` for OpenAI
and Anthropic, with the pricing/persistent-budget pause reason. The local
review expired at `2026-11-11T00:00:00Z` (November 10, 7 p.m. ET).

Official pages were searched and opened before renewal. Stored rates match:

| Model | Input / million | Cached input / million | Output / million | Enabled cache write |
| --- | --- | --- | --- | --- |
| GPT-5.4 | $2.50 | $0.25 | $15.00 | None |
| GPT-6.1 Sol | $2.00 | $0.10 | $10.00 | $2.50 / million, 30 minutes |
| Claude Opus 5.5 | $4.00 | $0.20 | $20.00 | None configured |

Sources checked November 11 UTC:
[GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4),
[OpenAI standard pricing](https://developers.openai.com/api/docs/pricing),
[Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview).
This renews the configured standard routes, not fast/batch/regional/long-context
price categories or unsupported cache lifetimes.

Only the two dates in
`alternatives/advisor-first/pricing-review.json` changed:
`verified_at: 2026-11-11T03:09:40Z`,
`valid_until: 2026-11-18T03:09:40Z` (November 17, 10:09:40 p.m. ET).
Model selection, rates, allowance, accounting and guards were not changed.
The existing local service reads this file at startup, so its launch agent
was restarted after confirming no active backend child. PID 45639 became
46690; the :8894 proxy and protected ports were unchanged.

Verification:

- 30 offline tests passed with temporary ledgers:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=alternatives/advisor-first/tests infrastructure/daylight-data/.venv/bin/python -m unittest test_advisor_budget test_provider_budget -q`.
  This includes review expiry, rate-override rejection, shared-object adoption,
  provider limits, uncertain holds and clock protection. Existing fixture
  SQLite resource warnings are retained in [tests.log](tests.log).
- Status checks on both ports now show `canRequest: true`, empty reasons and
  the new expiry for both providers.
- Original saved-profile tables, charge and model-attribution tables have
  identical hashes. Provider request counts remain 32 OpenAI / 5 Anthropic;
  carried holds remain $1.56470 / $0.55508. No reservations were cleared.
- The ledger clock metadata advanced normally to November 11 UTC when the
  successful status check reached the clock guard. There is no integrity block.
- All 406 protected source hashes match. The pricing review is the only
  changed runtime source/config file. No paid request, live conversation or
  six-run evaluation was performed by this task.

[Before status](status-before-8894.json), [after status](status-after-8894.json),
[verification](verification.json), [runtime before](runtime-before.json),
[runtime after](runtime-after.json), [old dates](before-pricing-review.json),
[new dates](after-pricing-review.json).

The local admission pause is resolved. Provider account availability and live
conversation quality were not tested with paid calls.
