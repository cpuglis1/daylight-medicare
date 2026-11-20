# Developer handoff · November 20, 2026

Start here if you are picking up Daylight from the owner's laptop.

## Which branch

**Use `dev`.** As of November 20, 2026 it holds all local code, including the
:8895 Collier pilot demo. `main` lags behind `dev`. The standing
"Promote dev to main" pull request moves it forward, and only the owner merges it.

```bash
git clone https://github.com/cpuglis1/daylight-medicare.git daylight
cd daylight
git checkout dev
```

Then follow the [README quick start](../../README.md) to run :8895. It covers
the pinned Python 3.14.7, PostgreSQL 18, and the pilot data folder.

## Read before changing anything

1. [AGENTS.md](../../AGENTS.md) and [PRINCIPLES.md](../../PRINCIPLES.md)
2. [CURRENT_STATE.md](CURRENT_STATE.md): current decisions (D-numbers), where to work, open questions
3. The scoped `AGENTS.md` for your surface, for example [alternatives/advisor-first/AGENTS.md](../../alternatives/advisor-first/AGENTS.md)
4. [DEVELOPMENT.md](DEVELOPMENT.md) and [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md)

## What is where

| Material | Location |
| --- | --- |
| Advisor (:8895), pilot, data-serving code, docs, tests | `dev` |
| Files the publication policy does not yet categorize: preview and history images, `.command` launchers, launchd plists, scripts under `docs/`, security-program `.docx`, Caddyfile, schema SQL (356 files) | branch `backup/local-extras-2026-11-20`, not merged. They need an owner decision on [publication-policy.json](publication-policy.json) before they can pass CI. |
| Pilot data folder (`.state/pilot-subset/2026-11-12-r1`) | From the owner. Not in Git. |
| `docs/data/`, `plans/`, Postgres research state, `audit-evidence/`, `outputs/` | Owner's machine only. Not in Git because of source-use terms and size. |

Tests that need the local-only data are listed in `PRIVATE_TESTS` in
[tools/run_advisor_checks.py](../../tools/run_advisor_checks.py). CI skips them.
Failures already known are listed in
[known-failures.json](../../alternatives/advisor-first/tests/known-failures.json).
CI runs these tests and reports them, but only a failure not on that list
fails the check.

## Superseded branches

The following hold older copies of work that is now on `dev`:

- `nightly/2026-11-16/*`
- `sync/working-copy-2026-11-14`
- `pilot-demo/8895`, a November 12 snapshot that also carried evidence folders
- the local-only `feature/latency-plumbing` and `feature/profile-education-records`

Do not merge them.

## Open items

- **First job: advisor test drift.** On November 20, 2026 the local :8895 code
  failed 32 advisor tests that are not on the known-failures list, about 26 of them
  outside environment issues. Groups: `test_conversation_checks_ux` replaces
  `daylight_data.serving` in `sys.modules`, which breaks later doctor and
  drug tests. There are also expected inventory IDs (`T05` vs `T02`), a missing
  `understanding` key, a hosted selector (D207, D199), guided close and plan
  review. Run `python -B tools/run_advisor_checks.py` for the current list.

- The nightly sync to `dev` (`tools/nightly/`, open PR on `ci/nightly-dev-flow`)
  has not pushed anything since November 16. Its headless Claude run fails
  because the OAuth session expired, or the run times out.
- `.github/workflows/repository-checks.yml` on `dev` runs the advisor suite as a
  single job. The parallel-shard version is on `ci/parallel-advisor-tests`, not merged.
- Repository owner roles in [owners.json](owners.json) are still unassigned:
  consumer release, data evidence review, infrastructure recovery, privacy and
  security review.
- Use fictional data only. Do not run live conversation tests or paid model
  probes without the owner's approval.
