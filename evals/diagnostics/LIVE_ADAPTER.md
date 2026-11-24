# Local single-turn trials

Use a dedicated Daylight dev checkout. Run the preview without a model call.

```sh
python evals/diagnostics/run_live.py --case question_timing-pause-1 --trials 2
```

A live run requires an explicit owner request. Add `--owner-authorized-live` for
that run only. The selected reviewed API model must be configured and its
pricing review current. Use `--cap-cents` to lower the $10 maximum. Each
charge is checked against the run ceiling and the diagnostic ledger's existing
provider daily ceiling in one transaction. The ledger persists across runs
and keeps uncertain charges. Each trial gets a new owner, state binding and
request ID. The advisor server is never started as an HTTP service.

The normal advisor checks its sealed profile contract before any live run.
If the dev checkout lacks a bound source, restore the byte-identical file from
a reviewed local checkout at the path shown in
`infrastructure/daylight-data/config/profile-contract.2026.json`. For the
current dev checkout, the missing file is
`docs/data/integration-review-2026-10-29/review-catalog.json`. Verify its
SHA-256 matches the contract's `review_catalog` source binding before copying
it into the isolated checkout. Keep it out of the patch. The adapter also
checks the original contract's digest and every bound source and refuses
before a trial if anything differs.

The typed pause and ZIP correction starts use ordinary structured answers.
The correction case also seeds fictional exchanges in the actual visit-memory
store. These exchanges supply context only. The seal and profile gates still
apply. The 480 calibration rows are unchanged. Unsupported starting states
fail at preflight. The runner sends only the case's exact bound visitor message
and never forwards its prose context, sample reply, expected behavior or label.

The private report stores local code and evidence digests, elapsed run
timestamps, provider model receipts where captured, response, state changes
and available trace entries. The existing trace recorder captures composition
requests and responses, but extraction can lack a raw provider response.
Tool observations are limited to what the recorder sees at the model boundary.
Use only fictional inputs and keep the report local. Temporary profiles and
working traces are cleaned up after the run. Output reports and the isolated
usage ledger persist under `alternatives/advisor-first/var/eval-diagnostics`.

Local observations are diagnostic evidence only. Model aliases and unsigned
digests cannot attest a release identity. Live judge scoring, complete
executable validation coverage and matched baseline evidence are absent. The
adapter emits no release comparison and cannot feed the deployment gate.
