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

The typed validation starts use structured answers, verified visit memory and available local evidence.
The correction case also seeds fictional exchanges in the actual visit-memory
store. These exchanges supply context only. The seal and profile gates still
apply. Each start is pinned to the exact version of its calibration case.
A wording change requires reviewing what the visitor could actually see or
have said before binding the new version. Unsupported starting states
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
digests cannot attest a release identity. Complete executable validation coverage and matched baseline evidence remain open. The
adapter emits no release comparison and cannot feed the deployment gate.

### Validation preflight and grading

Run `python evals/diagnostics/run_live.py --available-validation --trials 1` to list the bound holdout cases and identify missing fixtures without spending. A paid subset run adds the owner authorization flag and an explicit cap in cents. Each trial starts from a fresh visitor state. Per-run manifests and intermediate JSONL observations are retained in the private diagnostics progress directory. A partial run cannot qualify a release.

To score a completed private artifact, run `python evals/diagnostics/score_observations.py PATH` in the D155 Python environment with a signed-in Claude subscription. Case reference replies and agent labels stay out of grader requests. The report describes the individual outcomes and identifies errors or missing evidence. These scores evaluate the current candidate; a release comparison also requires the same checks, cases and trial counts on the previous build.

### Fixture demo export

The local operator can prepare a private review artifact from a completed
validation run. The inputs contain provider payloads and untrusted model
text. Someone with access to a shared path could try to substitute a file,
and reply text could expose identifiers or carry active markup. The exporter
admits owner-only files under the diagnostic directory, pins prompts to the
reviewed corpus, verifies the manifest and trial identities, and copies only
allowlisted fields. It suppresses unsafe replies as a whole. Keep exported
text inert in the demo and review the actual artifact before publishing it.

Use a restrictive umask when running the live adapter so its progress manifest
also has private permissions. Export from the same checkout:

```sh
python evals/diagnostics/export_demo_observations.py PATH_TO_LIVE_OBSERVATION
python evals/diagnostics/export_demo_observations.py PATH_TO_LIVE_OBSERVATION --scores PATH_TO_LIVE_SCORES
```

The run's manifest is read from `progress/` by run ID. A missing, in-progress,
or inconsistent file stops the export. The score file is optional and must
match the exact observation file and its trial keys. Only a valid subscription
judge outcome on an observed trial appears in the export, including a judge
error. Screened judge reasons accompany displayable replies when available. A
suppressed or missing reply is omitted. Unbound case IDs identify fictional cases
without trials.

When there is a verified change that triggered the evaluation, add
`--change-reason 'One sentence describing the change.'` to the export command.
Use a single line of at most 300 characters suitable for display. The exporter
refuses unsafe reasons and adds `changeReason` only when the option is supplied.

The content-addressed export stays in the private diagnostic directory. Review
every projected reply, judge reason and change reason before deployment and
attest the exact SHA-256 of the reviewed bytes at demo launch. This command has
no network or publishing step. Remove private artifacts through the operator's
normal local retention process.

A signed-in Codex subscription can score a completed run or follow its private progress
journal. In the D155 Python environment, run
`python evals/diagnostics/score_codex.py RUN_UUID` after the owner authorizes scoring.
The scorer uses `gpt-6.2-sol` on ChatGPT authentication, checks each trial against its
suite rubric and case criterion, and saves completed receipts as it goes. Run the same
command to resume an interrupted scoring process against the same judge and case versions.
A final score report is linked to the exact completed observation artifact after checking
each receipt. Private outputs contain fictional scoring evidence. Treat model names as
requested aliases and judge grades as diagnostics subject to owner review.

The scorer accepts only bounded, owner-owned files in the private run folder. It
sends the tracker's fictional evidence and untrusted generated text as delimited data,
with reference labels and mock outputs excluded. The CLI runs in an empty directory
with ChatGPT-only authentication, a read-only sandbox, disabled tools, and a bounded
worker pool. The grader gets no inherited model-routing or API credential variables.
A removed or expired subscription fails closed. The temporary CLI directories are
removed after each trial, the receipt journal is removed after final publication, and
the owner retains the private reports under the existing diagnostics retention policy.
