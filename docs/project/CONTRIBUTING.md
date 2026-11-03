# Collaborating on Daylight

**Shared development baseline · November 2, 2026:** Start with [the current advisor fixture setup](DEVELOPMENT.md). Required GitHub checks cover the curated source, fictional advisor suite, selected infrastructure contracts and HTTP startup; actual-source and database/recovery tests retain their separate prerequisites. Maintenance belongs to @cpuglis1; independent specialist assignments remain pending. Use a clean checkout and targeted PRs rather than staging from the large original working folder.

The first shared development target is a reproducible version of the current local project, with the [2026 Collier controlled pilot](COLLIER_MVP.md) and the [public repository destination](CLOUD_HANDOFF.md) explicit. The code repository, source evidence, customer state and release authority are separate assets with different access and review rules.

## Read and choose the correct boundary

Read [PRINCIPLES](../../PRINCIPLES.md), [the company narrative](../company/README.md), [the project map](README.md), [PRODUCT](../../PRODUCT.md) and the relevant scoped `AGENTS.md`. For UI changes, also read current requirements/master/design and the surface contract. Latest explicit owner decisions take precedence over older “current” or “latest” paragraphs.

Work on :8893 in `alternatives/advisor-first/` unless the task explicitly targets another surface. Its pinned engine in `alternatives/chat-first/` is a real dependency. Do not repair :8893 by editing the protected upstream engine, changing its hash lock without review or merging guest stores. Source/research work is additive by revision; an accepted packet and its verifier code must not be silently rewritten.

The new CAP-01–CAP-15 labels describe company responsibilities. L01–L15 are data domains. Existing D requirement IDs and C/H/O historical gap identifiers retain their meanings.

## Ownership and review

Actual people remain to be assigned; these are necessary roles, not claims of staffed teams. One person may fill several implementation roles. Independent domain/release review still needs appropriate independence and qualification.

| Boundary | Accountable role | Required review |
| --- | --- | --- |
| Company direction and pilot scope | Founder/product owner | Explicit owner decision recorded in requirements/master when direction changes. |
| Advisor, profile and education | Advisor/product lead | Behavior/privacy review and relevant UI verification; keep report versus verification distinct. |
| Source acquisition and source STOP | Data engineering/source owner | Permitted source route, exact bytes/lineage, maintenance policy and recovery. |
| Semantic meaning and personal methods | Medicare/domain lead | Independent interpretation, discrepancy accounting and purpose-specific acceptance. |
| Infrastructure, archive and CI | Engineering/operations lead | Least privilege, reproducibility, migration/restore and source-authority preservation. |
| Privacy and customer data | Privacy/security owner | Specific permissions, minimization, retention/deletion, staff/family access and vendor boundary. |
| Release authority | Release owner | Exact code/data/method/purpose/wording/operating scope; no author self-promotion. |
| Human service and enrollment | Qualified service/fulfillment owner | Supported recipient/platform, separate action permission, actual receipts and exceptions. |
| Consumer research and economics | Research/growth owner | Task/cohort definitions, factual review, denominators and neutral-outcome cost reporting. |

Do not generate a `CODEOWNERS` file with invented usernames. Configure real reviewers, repository roles and branch/ruleset requirements when people are assigned.

## Work and pull requests

1. Establish a reviewed source baseline before creating independent worktrees/clones. Untracked work in the current folder will not appear in a new checkout. Preserve it and use the explicit [publication preflight](CLOUD_HANDOFF.md#executable-preparation).
2. Use a `codex/` branch by default. Bound the task by capability, requirement IDs, directories and acceptance evidence. Avoid overlapping edits to the same variant/controller or sealed source revision.
3. Keep migrations additive and data builds restartable. Use fictional customer fixtures and disposable databases for tests. Real guest data, transcripts, keys and the shared spend ledger are not test fixtures.
4. Review the exact diff and newly added files. State the behavior change, evidence, test environment/skips, source/release effects and remaining limitations. No silent source reclassification or acceptance inheritance.
5. Merge only the agreed code/evidence snapshot after applicable review. Test the integrated result, not a sum of earlier passing test totals. Keep actual runtime activation separate from merge and from consumer capability acceptance.

Do not stage from another contributor's active shared working tree, reset unrelated changes, run migrations against the live local DB, start a second cluster on port 55485, restart protected services, or use paid model calls as a default CI check. Existing source STOPs survive worker, host and cloud changes.

## Local verification entrypoints

These commands apply to the current fully populated workspace. They do not claim that the current GitHub clone has all dependencies. Run the targeted tests relevant to the change; broader suites are for actual integration changes or final agreed snapshots.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s alternatives/advisor-first/tests -v
node --check alternatives/advisor-first/web/advisor.js
```

For the separately packaged evidence service, use its pinned environment and [package instructions](../../infrastructure/daylight-data/README.md). Database integration tests require the explicit disposable test DSN and their own safeguards. The persistent build/runbooks are not generic development reset commands.

The [advisor fixture instructions](../../alternatives/advisor-first/README.md) create an isolated temporary profile database. Use those instructions for no-model/no-customer behavior checks. Do not copy the workstation launch plist as cloud deployment configuration.

For a smaller verified starting point, use the [isolated developer rehearsal](../reviews/2026-11-02-project-readiness/DEVELOPER_REHEARSAL.md) and its [local bundle](../../outputs/daylight-team-handoff-20261102/daylight-developer-rehearsal.zip). It includes the exact runner and 74 passing in-memory tests, with the contract-metadata dependency exception documented. It is not a complete or publication-approved project export.

## CI to establish with the curated baseline

The repository had no `.github` CI directory at review. Add pipeline checks after the clean fixture/dependency closure is established: syntax/imports, fictional unit/contract tests, ephemeral PostgreSQL migration/role/STOP/recovery tests, engine/code manifest verification, publication/credential checks and targeted frontend behavior. Pin the tested environment and record skipped external capabilities. CI should never require the 124 GiB workstation folder, customer records, paid model calls, unrestricted source fetching or rewriting sealed packets.

For education and decision work, technical tests complement rather than replace qualified factual review and consumer observation. Record source meaning, model behavior, user comprehension and operating outcomes separately in the [capability ledger](CAPABILITIES.md).
