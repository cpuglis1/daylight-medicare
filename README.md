# Daylight

Daylight is a Medicare learning and research prototype: a step-by-step visual guide, supporting Ask Daylight help, and a published-plan comparison implementation. Its operating model is **self-directed research, licensed transaction**. This repository does not provide insurance enrollment, a binding quote, or a validated personal recommendation.

The active application is **`cms-slice/apps/chat/` with the Python service in `cms-slice/scripts/`**. The Node app inside the original v1.2 bundle is archived history.

## Start here

| Need | Read |
| --- | --- |
| Binding product direction | [PRODUCT.md](PRODUCT.md), [owner requirements](DAYLIGHT_REQUIREMENTS.md), [agent instructions](AGENTS.md) |
| Current implementation, blockers, next work | [Current status and plan](docs/CURRENT_STATUS.md) |
| Run and verify the project | [Developer setup and commands](docs/DEVELOPMENT.md) |
| Understand modules and request boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Know what data is captured, usable, or accepted | [Data inventory, provenance and gaps](docs/DATA_INVENTORY.md) |
| Find all documentation and historical sources | [Documentation index](docs/README.md) |
| Review this cleanup or roll it back | [Organization and preservation guide](docs/REPOSITORY_ORGANIZATION.md), [review report](docs/reviews/2026-10-21/REVIEW.md) |

The [one-page Collier MVP objectives plan](docs/planning/collier-mvp-2026-10-21/collier-mvp-plan.pdf) remains in place, with its [HTML source](docs/planning/collier-mvp-2026-10-21/collier-mvp-plan.html). It covers data, UX, the model/hosting decision, plan comparison, and a consented human closing handoff. Planned outcomes are not implemented capabilities.

## Current state — reviewed October 21, 2026

- The guide starts with what Medicare is, introduces concepts gradually, preserves an experienced comparison shortcut, and offers focused contextual help. Guide answers and notes live in tab memory; explicitly submitted service chat may be sent to the configured model and logged locally. See [privacy and runtime boundaries](docs/ARCHITECTURE.md#state-and-privacy).
- Repository captures cover **70 published 2027 Collier County records**: 23 MA-PD, 9 MA-only, 27 SNP, and 11 PDP. All **61 drug-bearing pharmacy networks** are packaged. Separate CMS ratings cover **24 contracts**, retaining numeric and official nonnumeric states. Capture and successful joins do not establish current availability or personal suitability.
- **Consumer data acceptance is pending, with zero approved claims.** Required field, interpretation, source, and exact-release review must be completed. The actual Python consumer service fails closed; a static guide preview is not evidence that consumer data or live chat is available.
- Personal drug prices, validated Medigap rates/quotes, exact clinical participation, complete benefit review, and qualified release acceptance remain unresolved. The Medicare.gov collector's STOP remains active. No external inquiry or data refresh was performed during this cleanup.
- Baseline checks: **201 Python tests, 54 frontend tests, and 22 archived-prototype tests pass**; the WP1 hash verifier passes. The selected release `naples-98038a43549f438d8c38` already fails runtime verification against the newer `app.js`, and its engineering review deadline has passed. See the [review evidence and limits](docs/reviews/2026-10-21/REVIEW.md).

## Local use

Python **3.14.7** and Node **23.11.0** were available for this review. The active app uses Python's standard library and plain HTML/CSS/JavaScript; it has no frontend package install or build step. Node is used for frontend regression checks. Optional source-collection tooling has separate dependencies.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cms-slice/tests -v
node --test cms-slice/tests/frontend/journey.test.cjs
```

To inspect only the guide layout on a free loopback port:

```sh
python3 -m http.server 8877 --bind 127.0.0.1 --directory cms-slice/apps/chat
```

Open `http://127.0.0.1:8877/`. This is a **static preview**: source-linked guide explanations work, while catalog APIs and live replies are unavailable. Do not enter real medical or financial details. A separate conspicuously labeled synthetic catalog test server is documented in [Development](docs/DEVELOPMENT.md).

The Python service requires a matching verified release. Do not skip a failed check:

```sh
cd cms-slice
python3 scripts/demo_release.py verify current
# Only after the verification succeeds and review scope is understood:
python3 scripts/demo.py serve --release current --port 8878
```

The current selected release fails the first command. Rebuilding is deliberate evidence/review work, not part of organizing files; a new build never supplies human acceptance. Optional model configuration and the difference between workspace, research, and consumer modes are in [Development](docs/DEVELOPMENT.md).

## Repository layout

```text
PRODUCT.md / DAYLIGHT_REQUIREMENTS.md / AGENTS.md   Product authority
cms-slice/                                       Active app, service, data registries, tests, evidence
docs/                                           Current guides and indexed historical findings
  planning/                                     One-page objectives plan
  archive/product-history/                      Older UI proposals and visual-content specifications
  reviews/2026-10-21/                            Cleanup ledger, checks, and screenshots
archive/cleanup-2026-10-21/originals/             Exact before-images of edited/moved documents
archive/local-checkpoints/                      Ignored local inventory and pre-existing work checkpoint
audit-evidence/ / outputs/                       Prior walkthroughs, workbooks, exports, before-images
medicare-project-2026-10-17-v1.2/                 Unchanged original research/prototype bundle
tmp/                                            Existing ignored scratch/tooling, retained
```

Runtime data and historical evidence remain at their original paths. Existing [action reference](ACTION_REFERENCE.md), [broad implementation plan](PLAN_OF_ATTACK.md), [Collier gap plan](COLLIER_DATA_GAP_PLAN_current.md), and [owner review queue](COLLIER_OWNER_REVIEW_REQUIRED.md) remain findable; their dates and scope matter. Older proposal prose does not override `PRODUCT.md` or the numbered owner requirements.

## Working-tree and GitHub publication scope

The organization review itself made no commit, remote change, upload, publish, or push. The owner subsequently authorized a cleanup commit and push to `cpuglis1/daylight-medicare`. That repository was verified as public and empty at publication preflight. The local branch is `main`, with an existing root commit and substantial pre-existing uncommitted work.

**This documentation reviews the full local working tree. A cleanup-only commit excludes the pending application, backend, source-evidence and test changes. A fresh clone will therefore not reproduce the reviewed UI or every linked local artifact until that separate work is reviewed and committed.** Public push must also account for the existing root commit; it cannot be omitted from an ordinary push of this branch. Review [Git readiness](docs/GIT_READINESS.md) before staging. In particular, local raw data/releases are ignored and will not be backed up by a normal push; preserve them separately. A retained generated audit ZIP exceeds GitHub's usual single-file limit and is now narrowly ignored rather than removed.
