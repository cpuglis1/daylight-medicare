# Developer handoff · November 20, 2026

Start here if you are picking up Daylight from the owner's laptop.

## Which branch

**Use `for_charlie_112026`.** It is the owner's whole local working copy as of
November 20, 2026, which is what runs the :8895 demo on the laptop. It also
contains everything deployed on AWS (see below).

It is built on `integrate/local-2026-11-20`, the cleaned-up code proposed for
`dev` in PR #24, with two more commits:

- local files the publication policy does not yet categorize
- the data files and release bundle the hosted site uses

Because of those additions this branch does not pass the repository's
publication checks. Do not merge it into `dev` as is. `main` and `dev` lag behind it.

```bash
git clone https://github.com/cpuglis1/daylight-medicare.git daylight
cd daylight
git checkout for_charlie_112026
```

Then follow the [README quick start](../../README.md) to run :8895. It covers
the pinned Python 3.14.7, PostgreSQL 18, and the pilot data folder.

## What is running on AWS

https://daylightmedicare.com (pilot) and https://test.daylightmedicare.com (test)
both run release **D208**, `9bfbab345f3d29a5bba254c691474818fb133b309b5f9b81b0948a7f5f49fb1a`.
The release has 493 files, and the November 20 deployment check matched every
file hash on the host. Every one of those files is on this branch with the same
bytes:

- application code under `alternatives/`, `infrastructure/daylight-data/` and `cms-slice/`
- the deploy tools: the host's `deployment/*.py` are the same files as
  `infrastructure/daylight-pilot/deploy_hosted_d*.py`, `hosted_operations.py`,
  `hosted_egress_guard.py` and `install_hosted_*.py`
- the pilot knowledge base it reads, `docs/data/pilot-knowledge-2026-11-12-r2/`:
  captured Medicare.gov, CMS and SSA pages
- the exact deployed delta bundle and plan, in `infrastructure/daylight-pilot/d208-release/`

**Not in Git:** the hosted Postgres data (`evidence/pilot.dump.gz` on the host,
the local `.state/pilot-subset/2026-11-12-r1/`). It contains licensed Medigap
pricing data with use and transfer terms; get it from the owner. Secrets,
invitation signing keys and the AWS account itself are also not in Git.
Deployments run through AWS Systems Manager from the owner's console. The
procedure and history are in
[infrastructure/daylight-pilot/README.md](../../infrastructure/daylight-pilot/README.md)
and `audit-evidence/*d20[6-8]*` (local only). Spending limits are in
CURRENT_STATE under D208: a $50 cumulative app cap and a $50 provider project limit.

## Running :8895 locally

Tested November 20, 2026 from a fresh clone of this branch on macOS:

- the README quick start
- Python 3.14.7 and the pinned `requirements.lock`
- a new PostgreSQL 18.6 cluster restored from `pilot.dump.gz`
- `demo_server.py --fixture`

The page and every asset it loads were served, and 14 of 15 checks in
`test_unified_demo` passed, including the plan counts. The one failure,
`test_every_current_frontend_file_is_served_unchanged`, is an outdated test: the
server deliberately adds the enrollment, guided-close and turn-progress scripts
and a newer hero photo to `index.html`.

**What Charlie needs from the owner:** the `pilot-subset/2026-11-12-r1` folder.
It needs `pilot.dump.gz`, `binding.json` and the small JSON files; the two
~150 MB uncompressed `.dump` files are not needed.

**What works:**

- the conversation with `--fixture`: fictional, offline replies with no API key
- Medicare Advantage, Medigap and Part D plan panels for Collier County, using the real pilot data

**Needs more than the branch:**

- **Live AI replies:** an `.env` with `OPENAI_API_KEY` (and `ANTHROPIC_API_KEY` for Claude).
  These cost money, are capped by the daily ledger, and only work while
  `pricing-review.json` is less than 7 days old.
- **Doctor checks and prescription checks** (`--doctor-chat`, `--doctor-foundation`,
  `--conversation-checks`), which the owner runs on the laptop: they read the
  local research database (`daylight_research_2026_r2`, part of the ~63 GB
  Postgres state) and the `pilot-foundation-2026-r1` package. Neither is in Git.
  Without them, the server says doctor research is unavailable and keeps running.

## Read before changing anything

1. [AGENTS.md](../../AGENTS.md) and [PRINCIPLES.md](../../PRINCIPLES.md)
2. [CURRENT_STATE.md](CURRENT_STATE.md): current decisions (D-numbers), where to work, open questions
3. The scoped `AGENTS.md` for your surface, for example [alternatives/advisor-first/AGENTS.md](../../alternatives/advisor-first/AGENTS.md)
4. [DEVELOPMENT.md](DEVELOPMENT.md) and [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md)

## What is where

| Material | Location |
| --- | --- |
| Advisor (:8895), pilot, data-serving code, docs, tests | this branch; also PR #24 into `dev` (`integrate/local-2026-11-20`) |
| Files the publication policy does not yet categorize: preview and history images, `.command` launchers, launchd plists, scripts under `docs/`, security-program `.docx`, Caddyfile, schema SQL (356 files) | this branch; also `backup/local-extras-2026-11-20`. They need an owner decision on [publication-policy.json](publication-policy.json) before they can go into `dev`. |
| Pilot knowledge base used by the hosted app (`docs/data/pilot-knowledge-2026-11-12-r2`, 11 MB) | this branch only |
| Pilot database (`.state/pilot-subset/2026-11-12-r1`, also on the AWS host) | From the owner. Not in Git. |
| Rest of `docs/data/`, `plans/`, Postgres research state, `audit-evidence/`, `outputs/` | Owner's machine only. Not in Git because of source-use terms and size. |

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
