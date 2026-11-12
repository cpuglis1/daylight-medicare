# AI-03 and AI-04: model router and provider-bypass checks

November 8, 2026 (America/New_York). Tracker items AI-03 (remove non-allowlisted
providers from every health-data path) and AI-04 (fail-closed provider router
with a static allowlist). Applies D101 (OpenAI GPT API is the pilot provider and
supersedes Claude for the pilot), keeps the D90 development allowances and the
HP-07 identifier backstop, and does not touch D64 logic, sealed sources, the
protected variants or the hash-pinned shared engine.

The tracker's D106 note (GPT-6.1 Sol via `/v1/responses`, `store: false`, under
the OpenAI BAA) and the owner's November 8 direction to test on the same model
that ships are not yet recorded in `DAYLIGHT_REQUIREMENTS.md`.

## AI-03 part one: key and endpoint audit

| Place | Finding |
| --- | --- |
| Pilot service (`infrastructure/daylight-pilot`) | No model credential. The service runs `--fixture` and denies outbound IP traffic, so no live model call is possible today. |
| Local `.env` (gitignored, blocked by the pre-commit and baseline checks) | Holds `OPENAI_API_KEY`, `OPENAI_MODEL` and `CLAUDE_API_KEY` for development. A repository search during this work printed the two key values into the agent session log; both should be rotated. |
| `.env.example` | Names only. |
| CI workflows | No secrets referenced. |
| Other files | No key-shaped strings outside `.env` (venvs, `.git` and dependency folders excluded). |
| Code that reads keys | `runtime_env.load_model_env` (OpenAI) and `advisor_models.claude_key` (Anthropic), both only outside fixture mode. |
| Code that builds provider requests in :8893 | `natural_agent.py`, `narrative_agent.py`, `provider_tokens.py`, `claude_client.py`. All send through `provider_transport.urlopen`. |
| Pinned shared engine (`alternatives/chat-first/cms-slice/scripts`) | `chat.py`, `guide_agent.py`, `ai_budget.py` and `transcript_log.py` call OpenAI with urllib directly. :8893's UI does not use those paths, but the legacy engine endpoints are reachable on the dev server. The engine is hash-pinned, so it is covered by the bypass guard below instead of being edited. |

## What changed

| File | Change |
| --- | --- |
| `alternatives/advisor-first/model_router.py` | New. Loads and validates the allowlist, authorizes each request, and installs the bypass guard. |
| `alternatives/advisor-first/model-routes.json` | New allowlist. Development: `gpt-6.1-sol` and `gpt-5.4` on OpenAI, `claude-opus-5-5` on Anthropic, fictional data only. Pilot: `gpt-6.1-sol` on OpenAI only, US region, endpoints and project left empty so it stays blocked. |
| `alternatives/advisor-first/provider_transport.py` | Asks the router before every send; sends to the route's endpoint with the route's headers and body. Accepted caller URLs now come from the router's canonical list. |
| `alternatives/advisor-first/transport_diagnostics.py` | Recognizes the router's fixed block categories. They are never treated as recoverable, so they are not retried. |
| `alternatives/advisor-first/server.py` | Installs the bypass guard before loading the pinned engine. A model is shown as available only if its route is allowed in the current environment. |
| `infrastructure/daylight-pilot/daylight-pilot.service` | Sets `DAYLIGHT_MODEL_ENVIRONMENT=pilot`. |
| `alternatives/advisor-first/tests/test_model_router.py` | New: 25 tests, including the AI-03 CI source checks. |
| `tests/test_provider_transport.py`, `tests/test_identifier_guard.py` | Fictional request bodies now name an allowlisted model; no assertion was weakened. |

`changes.diff` in this folder is the exact before/after for every file above.
The `alternatives/` folder is untracked in Git, so `git diff` will not show it.

## How it works

- **One door.** Every live model request already left through
  `provider_transport.urlopen`. That function now calls `model_router.authorize`
  first. A request goes out only if one route for the active environment names
  its provider, exact model and endpoint.
- **No fallback.** A request with no matching route raises a fixed category
  (`model_not_allowed`, `provider_not_allowed`, `route_not_configured`,
  `hosted_tool_blocked`, `feature_not_allowed`, `endpoint_not_allowed`,
  `environment_invalid`). curl is never started, and the caller's existing
  failure path runs without a retry.
- **Feature rules in code.** OpenAI Responses requests are sent with
  `store: false` (forced). OpenAI-hosted tools, hosted-tool includes and stateful
  fields (`previous_response_id`, `conversation`, `prompt`, `background`) are
  refused. Only Daylight's own `function` tools pass. Anthropic server tools,
  `mcp_servers` and `container` are refused.
- **Routes decide endpoint and project.** Callers build the canonical provider
  URL. The route supplies the physical endpoint (for example a US host) and the
  only `OpenAI-Project` header; any caller-supplied project or organization
  header is removed.
- **Environment.** `DAYLIGHT_MODEL_ENVIRONMENT` selects `development` (default)
  or `pilot`. Any other value blocks everything. Pilot routes must carry health
  data, process in the US and have both endpoints and a project before they work.
- **Bypass guard.** Approved traffic runs only in the curl subprocess. The
  advisor process refuses any Python-level lookup of a model provider host,
  which closes the pinned engine's direct urllib calls without editing it.
- **Allowlist validation.** The service will not start if the route file is
  malformed, uses wildcard models, non-HTTPS or non-provider hosts, wrong paths,
  query strings, a key in the project field, a non-US health route, or the same
  model in two routes of one environment.
- **Logs.** Only the block category, environment and endpoint kind. No prompt
  text, key or response content.

## Checks run

Environment: the Linux sandbox on the owner's Mac, Python 3.10.12, offline, with
the same network guard as `tools/run_advisor_checks.py` and no inherited
credentials. Each module ran in its own process.

| Check | Result |
| --- | --- |
| `test_model_router` | 25 of 25 passed. |
| The 24 existing modules that touch the transport, diagnostics, server or HTTP layer, before and after | Before: 364 tests. After: 364 tests plus the 25 new ones. No new failures or errors. |
| Pre-existing failures, identical before and after | 13, all from the sandbox's Python 3.10 and older `jsonschema` (for example `fromisoformat` rejecting a trailing `Z`, `Draft202012Validator` missing). Listed in `tests-before.jsonl` and `tests-after.jsonl`. |
| Mutation check of the AI-03 source scan | A fictional folder with a provider SDK import, a non-canonical provider URL, request builders importing urllib's `urlopen`, a transport that skips the router and a server without the guard: all five checks failed as intended. |

Not run: the full `tools/run_advisor_checks.py` suite (it stalled in this
sandbox before any change was made), Python 3.11/3.12, the JavaScript tests,
GitHub CI, and any live or paid model call (none is permitted).

## Open items

1. **Pilot route values (AI-02/AI-05).** Fill `pilot-openai` in
   `model-routes.json` with the production project id and the endpoints
   confirmed for US processing. Until then every pilot model call is refused.
2. **Test project.** Set `project` on `development-openai` to the separate test
   project once it exists, so test traffic cannot use the production project.
3. **Key rotation.** Rotate the OpenAI and Anthropic development keys in `.env`.
4. **Requirements record.** Record D106 and the same-model testing direction in
   `DAYLIGHT_REQUIREMENTS.md` and `CURRENT_STATE.md`.
5. **Founder review** of this change and a CI run on Python 3.12 before merge.
