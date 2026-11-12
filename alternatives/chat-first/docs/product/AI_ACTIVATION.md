# Local AI activation — October 21, 2026

**D63 is installed and live for local development.** [Open Daylight](http://127.0.0.1:8890/) · [Rendered evidence](http://127.0.0.1:8897/ai-activation/). The earlier installation denial was resolved by fresh explicit owner authorization; one guarded retry installed the package. No commit, push, public deployment, new account or new credential occurred. Personalized plan comparisons remain held.

## Exact operating configuration

```sh
python3 cms-slice/scripts/guide_server.py --port 8890 --model-env .env --enable-live
```

The existing OpenAI GPT-5.4 key/model is read into process memory, never copied into source, fixtures or logs. The service binds loopback. It is currently running as a local background process without automatic restart. Stop it when not needed; no request is made merely because it runs. Browser status polling is read-only and does not invoke a model.

- **Total allowance:** $1 USD per UTC day, shared by every guest on this app. Reset is **00:00 UTC**. This is an app-level model-token budget, not a limit on unrelated API-key/account usage, provider taxes or an invoice guarantee.
- **Persistent ledger:** ignored private `cms-slice/var/ai-budget/usage.sqlite3`; independent of guest profiles. Deleting a guest or changing the profile database does not reset usage. All ordinary local runs use this fixed ledger. Do not remove it or choose a different copy to bypass the cap.
- **Concurrency/restart:** integer nano-dollar reservations are committed in SQLite `BEGIN IMMEDIATE` transactions before generation. Separate instances/processes share the same cap. Restart does not refund or reset reservations. Only valid completed provider usage releases unused reserved cost.
- **Preflight:** same model, instructions, message, tools and schema are sent to OpenAI's exact input-token count endpoint. Unknown count or more than 8,000 input tokens stops generation. Each generation is bounded at 900 output tokens, default processing tier, no paid tools and no provider storage request. Maximum output is reserved even if the actual response is short.
- **Prices:** reviewed `cms-slice/config/ai-pricing.json` pins GPT-5.4 standard prices: $2.50 input/$0.25 cached/$15 output per million tokens. Counted input reserves the full uncached rate. The observed snapshot and processing tier must match the reviewed list before settlement. Unknown cache-write charges or inconsistent/missing usage retain the maximum hold and pause paid requests for reconciliation.
- **Price freshness:** checked October 21, 2026; the reviewed card expires **October 28, 2026 at 00:00 UTC**. Reverify official prices before updating that card. Unknown model, changed/unverified prices, expired review, storage failure or backward day movement fails closed. The cap cannot be raised via request body or environment variable.
- **Uncertainty:** cancellation, network failure or process interruption may still incur vendor usage. Their reservation remains held. Unresolved prior-day requests carry into later days; late completion also counts on completion day. No timeout-based refund or hidden retry occurs. Completed short-lived request-cache replay makes no additional model request; an explicit later retry may be a new budgeted request.
- **UI:** the shared estimate, held amount, $1 cap, UTC reset and no-auto-retry statement are visible above the journey and in Ask. The UI distinguishes measured-token estimates from held/uncertain amounts and keeps reviewed/manual guidance available when paid requests stop. Provider figures remain estimates from token usage, not an invoice.

## Verified results

| Evidence | Result |
|---|---|
| New targeted budget suite | **20 passed**: exact boundary, concurrent ledger instances, restart, settlement, uncertainty, midnight carry/late completion, backward clock, model/tier/pricing validation, count failure, no hidden retries, shared cap and idempotent historical usage |
| Existing guide/profile suite | **37 passed** with synthetic providers/temp databases; approved code package unchanged after this run |
| Prior full baseline | 238 Python and 128 frontend passed for the preceding core completion; not rerun wholesale for this bounded activation |
| Actual new paid check | **One** synthetic generation after a successful exact-count request. Browser showed editable, uncommitted goal/knowledge proposals and a reviewed Medicare fact. No profile was saved. No retry was needed. |
| New measured tokens | 2,610 input, 0 cached, 82 output; preflight count exactly matched observed input |
| New charge estimate | **$0.007755**, from measured tokens at the verified rates; preflight maximum reservation $0.020025 |
| Today's imported history | Three earlier successful smoke calls, 7,783 input + 258 output; **$0.0233275** estimated, imported once |
| Today's post-check total | **4** generations; **$0.0310825 estimated**, $0 held, **$0.9689175 remaining** |
| Actual service restart | Paid mode remained enabled and the same four calls/estimate remained; historical import did not duplicate |
| Browser | 1440 desktop, 820 tablet, 390 phone; document width matched viewport. Usage visible, no page overflow. Phone Ask stayed inside x12/y96/w366/h736 and returned to the task. |
| Plan service | `/api/status`: `plan_validation_status=pending`, `consumer_ready=false`, five source samples. No ranking/validation gate bypass. |

Current local usage may change after this report as explicitly authorized users submit requests. The live JSON status and server ledger are the current numeric authority. No real sensitive profile or chat was used for verification. Physical keyboards, screen-reader speech, public deployment/security/privacy approval and participant comprehension remain separate from this check.

## Preservation and files

Ten pre-activation originals and hashes are retained in [history/2026-10-21-before-ai-activation](history/2026-10-21-before-ai-activation/manifest.json). Current-file hashes were checked before installation. D63 is recorded in the owner requirements and PRODUCT.md; approved visual identity and all source-plan evidence remain intact. Runtime changes are the new `ai_budget.py`/pricing card/test, targeted guide-agent/server integration and the small usage text/CSS; no broad redesign was performed.

The separate founder/agent principles documentation is described in [PRINCIPLES.md](../../PRINCIPLES.md); it changes requirements/read order, not app behavior or current recommendation availability.

Sources: [official GPT-5.4 prices/snapshot](https://developers.openai.com/api/docs/models/gpt-5.4), [exact input-token counting](https://developers.openai.com/api/docs/guides/token-counting), [OpenAI spending-controller pattern](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api). Application limits, persistence and tests are Daylight implementation evidence, not vendor guarantees.
