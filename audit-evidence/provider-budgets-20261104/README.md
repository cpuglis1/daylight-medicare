# D86/D90 provider-scoped daily allowances

Owner requested provider-dependent costs after the shared local allowance blocked testing despite remaining provider account credits. Active on **:8893** at **18:07:15 EST, November 4, 2026**.

## Result

The local allowance is **$5 per UTC day for OpenAI** and separately **$5 for Anthropic**. GPT-5.4 and GPT-6.1 Sol share OpenAI's allowance, retaining their distinct model prices. Claude Opus 5.5 uses Anthropic's allowance. This is local usage accounting, not synchronization with either provider's console credit balance.

At activation:

| Provider | Metered estimate | Unresolved holds | Accounted | Remaining local allowance |
| --- | ---: | ---: | ---: | ---: |
| OpenAI | $2.7079722 | $0.7755 | $3.4834722 | $1.5165278 |
| Anthropic | $1.151588 | $0.448084 | $1.599672 | $3.400328 |

Both providers can accept new turns. The prior start-of-turn policy remains: a turn admitted below its provider's threshold may finish, including bounded recovery, even if its final cost crosses $5. New turns then stop for that provider. Model prices, counting, exact receipt validation and recovery limits are unchanged.

## Accounting and preservation

An additive `advisor_charge_models` side table records model, provider and attribution method. New reservations and their model/provider records are inserted atomically. Counting, admission, recovery and settlement use the selected model's provider; receipts cannot be recounted or settled as another model. Error messages name the provider. Free usage/status endpoints include `providerBudgets` for both providers; the existing primary budget is labeled with its provider.

Historical rows lacked provider identity. All **675** existing records uniquely match the retained reservation/pricing signatures: 534 GPT-5.4, 115 Sol and 26 Claude. This is recorded as **`legacy_unique_rate_match`**, an inference from stored accounting rather than a newly acquired provider receipt. Historical normal-input and cache-write-maximum reservation formulas and imported metered rows are recognized. Ambiguous attribution is never guessed: it remains visible as `unattributedUsd` and blocks new paid requests until reconciled.

The trial migration used a disposable database copy. After live activation, the SHA-256 of every original `ai_charges` row still matched the pre-migration snapshot. No charges, holds, amounts or ledger rows were deleted, reset or reassigned between existing records. Only attribution metadata was added. Selected-provider totals sum to the previous aggregate **$5.0831442**. See `attribution-check.json` and `activation.json`.

The original ledger schema and pinned shared engine remain unchanged. Other local variants retain their aggregate policies. Shared clock, pricing and unverified-usage integrity blocks still apply; provider separation changes spending attribution, not permission to ignore an accounting integrity failure. Existing uncertainty carries across midnight with its provider.

## Verification

**195 technical checks passed** (`checks.txt`): independent provider exhaustion in both directions, both GPT models sharing OpenAI, exact distinct model prices, provider-specific uncertainty across midnight, additive/idempotent historical attribution, unknown attribution, model/receipt mismatch rejection, concurrent admission, bounded recovery, free replay and existing factual/education contracts. Updated former shared-budget assertions now address the intended provider explicitly. These are synthetic ledgers and injected transports, not conversational quality tests.

Compilation passed. Hash checks preserve all **38 web assets** and nine curriculum, learner/profile state, memory, evidence and comparison files. Neither conversation instructions nor UI assets changed in this task.

Only the :8893 launch agent was restarted, listener PID **89927**. The page, unchanged served JavaScript, usage and status endpoints returned HTTP 200. Both diagnostic endpoints returned the separate provider balances. No live model conversations or paid API calls were made.

D73 review: provider-specific test costs are inspectable; permissions, independence, consequential intake, reported-versus-verified distinctions and recommendation/source gates remain unchanged. No provider funding was purchased and no provider credit balance was asserted or integrated.

Re-run:

```sh
PYTHONPATH=alternatives/advisor-first/tests infrastructure/daylight-data/.venv/bin/python -m unittest test_provider_budget test_advisor_budget test_composition_recovery test_connection_recovery test_advisor_models test_natural_agent test_education_contract test_education_followups -v
```
