# Daylight

**Current advisor development · November 2, 2026:** The shared advisor source is `alternatives/advisor-first/`. Start with the [credential-free fixture quick start](docs/project/DEVELOPMENT.md); it includes the exact shared-engine dependencies, fictional tests and explicit private-research test limits. The [project hub](docs/project/README.md) maps current work and protected variants. Public source publication does not activate hosting, accepted personal findings or recommendations.

**Start here · November 2, 2026:** [Current project hub](docs/project/README.md) — [company narrative](docs/company/README.md), [all fifteen company capabilities](docs/project/CAPABILITIES.md), [2026 Collier controlled pilot](docs/project/COLLIER_MVP.md), and [GitHub/cloud handoff](docs/project/CLOUD_HANDOFF.md). The current advisor development surface is **:8893 in `alternatives/advisor-first/`**; the earlier variants and stores remain protected. The owner confirmed the existing public `cpuglis1/daylight-medicare` repository and a 2026 controlled pilot first. The review adds organization and preparation, not a push, cloud deployment or consumer recommendation release.

**Reading the history below:** the October 21–26 status, test counts, 2027 catalog and :8890/:8891 descriptions are dated snapshots. Use the current hub for the newer advisor, full local database, r12 evidence work and exact remaining gaps. The original material remains preserved rather than silently rewritten as today's state.

**2026 L03 source update · October 26:** [Owner-supplied reconciliation r7](docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/) matches all 72 observed offerings to SB/EOC pairs, including the ten new Erickson PDFs. It adds 177 named Erickson checks and 75 optional-dental amount comparisons. Full cost/condition corroboration and exact new-evidence review remain open; the accepted r4 reference is unchanged. See the explicit gap register before making a completeness claim.

**D66 current local route:** the owner authorized a single ten-question sequence through local activation. Read [the ten-question contract](docs/product/TEN_QUESTION_CONTRACT.md) before navigation work. The default UI is `cms-slice/apps/ten-question/`, served by `python3 cms-slice/scripts/ten_server.py --port 8890`; `cms-slice/apps/chat/` is the preserved previous guide on port 8896 (`--legacy`). Existing guest data stays in its original storage; do not silently migrate or overwrite it. The two surfaces share the persistent $1/UTC-day budget cap. Latest D66 overrides conflicting variable-routing/shortcut instructions below; brand, source teaching, privacy, independence and plan gates remain.


**Read first: [Daylight principles](PRINCIPLES.md)** — user control, comprehensive evidence and strict separation of recommendations/AI from commercial economics. Current core runtime: [service guide](docs/product/CORE_SERVICE.md) and [local AI activation](docs/product/AI_ACTIVATION.md). The dated cleanup findings below remain historical evidence; they do not override these current contracts.

**Strategy · October 25, 2026 · D73:** [Canonical thesis and evidence roadmap](docs/product/STRATEGIC_THESIS.md). The intended free consumer platform combines independent decision support, licensed brokerage fulfillment, trusted-partner distribution and continuing reviews. Its next proof is informed decisions with less staff effort and viable economics across neutral outcomes. These are goals to test, not shipped capabilities or measured results; use the linked review checklist for future UI/system work. Customer completeness and external verification remain separate gates, and samples are not recommendations.

Daylight is a Medicare learning and research prototype: a step-by-step visual guide, supporting Ask Daylight help, and a published-plan comparison implementation. Its operating model is **self-directed research, licensed transaction**. This repository does not provide insurance enrollment, a binding quote, or a validated personal recommendation.

The original default application is **`cms-slice/apps/ten-question/` with the Python service in `cms-slice/scripts/`**; `apps/chat` preserves the previous guide. The separate **:8891 alternative remains supported alongside :8890**; see [source/runtime locations and boundaries](docs/product/STRATEGIC_THESIS.md#current-implementation-and-protected-variants). The Node app inside the original v1.2 bundle is archived history.

**Alternative source · D75:** The :8891 chat-first product is now editable in [alternatives/chat-first/](alternatives/chat-first/README.md). Its existing runtime and guest records remain separate; :8890 stays in the root `cms-slice/`.

## Start here

| Need | Read |
| --- | --- |
| Strategic thesis, staged roadmap and change review | [D73 canonical strategy](docs/product/STRATEGIC_THESIS.md) |
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
cms-slice/                                       Original app, service, data registries, tests, evidence
alternatives/chat-first/                        Canonical editable :8891 alternative; separate live runtime
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
