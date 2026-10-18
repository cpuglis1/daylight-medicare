# Medicare company workspace

Company name remains undecided. Current operating model: **self-directed research, licensed transaction**.

Retirees use the AI directly to research and understand their own Medicare coverage. Caregivers can also research with or for a beneficiary through permissioned sharing. Caregiver-first acquisition is a distribution priority; both are direct product users.

The original v1.2 bundle is preserved in `medicare-project-2026-10-17-v1.2/`. New implementation is in `cms-slice/`; it imports no archived prototype code or fixtures.

## Review and use

Start with the [latest Naples audit](docs/NAPLES_DEMO_REAUDIT.md) and [demo execution checkpoint](docs/DEMO_EXECUTION.md). The [original audit](docs/NAPLES_DEMO_AUDIT.md) is retained as the before-state, including the two defects subsequently fixed.

The current demonstration is one Python process with a simple source-grounded chat. It supports published 2027 Collier plan facts, medicine/store identity choices, dated prescription evidence and local provider notices. Personal prices and exact clinical network confirmation still require missing evidence. The source-only mode needs no API key; the optional Responses adapter has controlled tests but has not been exercised with a live account.

From `cms-slice/`, launch the packaged snapshot:

```sh
python3 scripts/demo_release.py verify current
python3 scripts/demo.py serve --release current
```

Open `http://127.0.0.1:8766/`. See the [facilitator handoff](docs/DEMO_HANDOFF.md) for the concrete review and session tasks. Rebuilding the release needs the pinned workspace sources and Poppler; the extracted approximately 26 MB bundle runs with Python alone. The release directory is ignored by Git and must be preserved separately.

1. [Action reference](ACTION_REFERENCE.md): runnable commands, consumer actions, permissions and failure handling.
2. [Plan of attack](PLAN_OF_ATTACK.md): actual dependencies, owners and acceptance evidence.
3. [Architecture review](docs/ARCHITECTURE_REVIEW.md): directory inventory, current capabilities and design assessment.
4. [Work package 1 findings](docs/WORK_PACKAGE_1.md): verified counts, mappings, lineage, gaps and acceptance limits.
5. [Minimal persistence proposal](docs/PERSISTENCE_PROPOSAL.md): a review proposal; no migrations were created.
6. [Product workflow](docs/PRODUCT_WORKFLOW.md): direct retiree use and permissioned caregiver participation.
7. [Naples / Collier County findings](docs/NAPLES_DATA.md): the next real-data market, complete source capture and scope limits.
8. [Work package 2](docs/WORK_PACKAGE_2.md): working local comparison, independent carrier sample and Chrome QA.
9. [Work package 3](docs/WORK_PACKAGE_3.md): real 2027 prescription capture, exact medicine/pharmacy queries and unresolved source questions.
10. [Execution status](docs/EXECUTION_STATUS.md): progress and concrete remaining dependencies for every plan package.
11. [Research review protocol](docs/RESEARCH_REVIEW_PROTOCOL.md): concrete retiree/caregiver tasks and acceptance evidence; no study results claimed.

## Working public-data slice

From `cms-slice/`, using the tested Python **3.14.7**, with no third-party dependencies:

```sh
python3 scripts/cms_slice.py fetch
python3 scripts/cms_slice.py run
python3 -m unittest discover -s tests -v
python3 scripts/cms_slice.py verify
```

Only `fetch` needs the network. It accepts the exact pinned government artifacts, not silently updated content at the same URL. Query, run and tests use local archives. Raw downloads and receipts are ignored by version control. If a pinned URL changes, recover the exact hashed artifact or inspect/register a new release before changing the manifest.

The delivered [New York County query](cms-slice/reports/work-package-1/market-36061-2027.json) includes 35 scoped source records and retains 35 excluded SNP records. The [Stafford query](cms-slice/reports/work-package-1/market-51179-2027.json) also exercises missing PBP evidence. These are public-source experiments, not personalized rankings, approved launch markets or purchase-ready results.

The next market is [Naples / Collier County, FL](cms-slice/reports/work-package-1/market-12021-2027.json), using the same 2027 release. All 70 matching records and all 70 complete PBP payloads are preserved in a [market source ZIP](cms-slice/reports/work-package-1/market-12021-2027-sources.zip), including records outside the current comparison scope. See the [market profile](cms-slice/reports/work-package-1/market-12021-2027-profile.json).

The earlier read-only comparison remains available for source inspection: 38 scoped records, all 32 exclusions and comparison of up to three records. Its original five-carrier-document sample checked twelve monetary fields. The newer demo quality matrix expands that to sixteen records across three parent organizations and checks all 96 applicable selected monetary fields against actual Medicare.gov observations. From `cms-slice/`:

```sh
python3 scripts/validate_naples.py fetch
python3 scripts/research.py build
python3 scripts/research.py serve --port 8765
```

Open `http://127.0.0.1:8765/`. Rebuilding the carrier sample requires Poppler's `pdftotext`; the read server requires only Python. This earlier source view is separate from the new chat. There is no private customer store, personal ranking/quote engine or enrollment service.

The prescription extension captures 61 drug-bearing Naples records, 24 formularies, 79,793 formulary rows and 3,506,965 complete plan-network rows. Run `python3 scripts/prescription.py fetch`, then `build` and `verify`; the pinned source download is **2.29 GB**. Exact-code queries and the browser's public drug example expose restrictions and source lineage, with 2027 prices explicitly unavailable. See WP3 for required reference snapshots, commands and the two premium/quantity/date questions. Medigap quote access and clinical provider-network evidence remain external dependencies.

See the [validation record](cms-slice/VALIDATION.md) for the test result, independent replay and original-bundle integrity checks.
