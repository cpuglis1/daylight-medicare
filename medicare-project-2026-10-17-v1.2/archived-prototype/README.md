> Archived exploratory code. The company has no name. Any old prototype branding is a discarded placeholder. This is not the production build specification; use `../medicare-company-architecture/ARCHITECTURE.md`.

# Archived Medicare evaluation prototype

A robust [implementation design](DESIGN.md) and runnable **synthetic evaluation workbench** for a text-first, autonomous Medicare advisor.

The workbench includes an OpenAI Responses API wrapper, a versioned advisor prompt, deterministic comparison tools, a shared human/agent dashboard, editable fictional profiles, evidence inspection, run export, and evaluation cases. The full production design covers national data ingestion, eligibility, quoting, provider/drug checks, enrollment and continuing service.

See the [verification record](VERIFICATION.md) for completed checks and their limits.

## Run locally

Requires Node.js 22 or later. No dependencies need to be installed.

```sh
cd /Users/cep4u/Documents/Codex/2026-10-15/i-w/outputs/archived-prototype
node src/server.mjs
```

Open [the local workbench](http://127.0.0.1:8787). “Evaluation tools” exposes scenarios, the fixed advisor prompt, experiment instructions, tool traces, model usage, and JSON export. Consumer mode keeps those implementation details out of view.

If Node is not on PATH, this session's bundled executable is:

```text
/Users/cep4u/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

Default mode is **scripted replay**. It exercises the interface and deterministic contracts; it is not an LLM and it does not measure AI performance. All prices, plans, people, provider checks and prescriptions are fictional. There are five example coverage options, not 25,000 ingested real plans.

## Connect OpenAI for synthetic evaluation

Copy `.env.example` to `.env`, set your server-side `OPENAI_API_KEY`, choose an API-project model in `OPENAI_MODEL`, and set `ENABLE_OPENAI=1`. Then:

```sh
node --env-file=.env src/server.mjs
```

Choose **OpenAI Responses API** in Evaluation tools. Use a model supporting Responses, function calling and structured text outputs. Model availability in Codex does not establish availability in your API project. API use incurs charges. The workbench never sends a key to the browser and never accepts one through a chat prompt.

`prompts/advisor.md` is the fixed prompter. Operator experiment instructions are appended below it. `src/agent.mjs` provides the bounded stateless tool loop, schema, structural/scope/readiness validation, and safe error handling. `store:false` is configured; it is not a promise of zero retention or healthcare compliance. No real personal/health information should be entered.

## Validate

```sh
node --test test/*.test.mjs
node eval/run.mjs
node --env-file=.env eval/run.mjs --live --case=ambiguous-doctor
```

The live case flag limits API spend during initial inspection. Omit it to run all cases. Results are written under `runs/`. Automated evaluation checks contracts and selected behaviors; every scenario still has a semantic-review rubric. A replay pass is not a model-quality score.

## Exercise canonical ingestion validation

```sh
node tools/ingest.mjs data/catalog.example.jsonl data/manifest.example.json runs/catalog-demo.json
```

Create `runs/` first if you have not run evaluation (`mkdir -p runs`). This validates normalized adapter output and source lineage, then writes an atomic snapshot. It does not download CMS data, parse carrier files, obtain data rights, or certify market completeness. Source-specific adapters and production persistence are specified in the design.

## Scope

Implemented: local synthetic UI, shared comparison snapshot, typed read-only tools, prompt experimentation, API wrapper, replay, evaluation runner, canonical validator and automated tests.

Not implemented: production accounts, national data feeds, real quotes, full benefits/Part D simulation, legally validated eligibility, beneficiary-data connections, autonomous insurance authority, provider outreach, application submission, effective-coverage verification or year-round servicing integrations. No real enrollment can occur. Consumer research, source agreements, domain validation and the approved operating model are explicit build gates.

## Files

| Path | Purpose |
|---|---|
| `DESIGN.md` | Full product, architecture, data, UI, policy, security and rollout design |
| `prompts/advisor.md` | Versioned advisor instructions |
| `src/fixtures.mjs` | Fictional profiles, products, evidence and educational references |
| `src/domain.mjs` | Shared snapshot, costs, gates, profile revisions and typed tools |
| `src/agent.mjs` | OpenAI adapter, output validation and scripted replay |
| `src/server.mjs` | Loopback-only server and isolated in-memory sessions |
| `public/` | Consumer dashboard and operator workbench |
| `eval/` | Cases, review rubrics and replay/live runner |
| `tools/ingest.mjs` | Normalized catalog validation and atomic publication example |
| `test/` | Domain, wrapper, ingestion and HTTP boundary tests |

The product goal is no human insurance advisor in the consumer journey. This prototype does not establish legal permission for autonomous personalized advice or transactions. The design requires an affirmative state/product/carrier operating basis before such capabilities are enabled.
