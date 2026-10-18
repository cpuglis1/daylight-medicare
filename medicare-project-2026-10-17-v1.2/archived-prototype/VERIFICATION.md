# Verification record

October 16, 2026 · synthetic local evaluation only

## Completed

- **22 automated tests passed.** These cover deterministic integer-cent costs, compatible bundle accounting, doctor constraints, stale information, missing material facts, unsupported markets, profile revision invalidation, read-only tool boundaries, normalized ingestion validation, the Responses API request/tool loop, fabricated evidence IDs, unavailable enrollment, session isolation, CSRF and origin checks.
- **25,000 generated canonical records validated** in the ingestion scale test. This demonstrates handling of synthetic normalized records; it is not an ingestion of 25,000 real Medicare products and does not exercise national network or pharmacy-price scale.
- **16/16 scripted replay contract checks passed.** Every scenario retains a manual semantic-review rubric. The replay is deterministic application code, not an LLM, and its pass rate measures neither suitability nor language quality. [Replay report](runs/eval-replay-1792180774697.json).
- **Example ingestion CLI passed:** two fictional canonical records, unique identities, expected categories, lineage and manifest checks, with an atomic catalog output under `runs/catalog-demo.json`.
- The local server starts at `http://127.0.0.1:8787`. The initial browser inspection exposed the expected conversation, five example options, evidence controls, profile review, comparison controls, larger text and separate evaluation tools.

## Not established

- **Live OpenAI execution:** no API key/model was configured. The wrapper was tested with controlled transport responses; no live model accuracy or latency claim is supported.
- **Complete browser interaction and responsive accessibility testing:** the browser session was interrupted, and subsequent headless Chromium launch was blocked by the environment's macOS process sandbox. Desktop/mobile interaction, keyboard flow, screen-reader behavior, zoom/reflow and usability with older adults remain to be tested. Initial page inspection is not a full visual or accessibility approval.
- **Real coverage accuracy:** there are no connected CMS/carrier/aggregator feeds, provider confirmations, prescription prices or accepted quote receipts. The five coverage options and all profile data are fictional.
- **Production decision or transaction readiness:** eligibility, underwriting, full Part D simulation, application submission, effective coverage, durable servicing, security certification and the legal basis for autonomous insurance activity remain production work.

## Reproduce

From this directory, with Node.js 22 or later:

```sh
node --test test/*.test.mjs
node eval/run.mjs
node tools/ingest.mjs data/catalog.example.jsonl data/manifest.example.json runs/catalog-demo.json
node src/server.mjs
```

See [README.md](README.md) for explicit live API configuration and the [design](DESIGN.md) for proposed production gates.
