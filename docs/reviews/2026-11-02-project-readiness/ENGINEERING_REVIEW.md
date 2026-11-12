# Daylight engineering, privacy and cloud/team readiness review

Owner choices incorporated into the main assessment: the existing public `cpuglis1/daylight-medicare` repository is the code destination; the first Collier controlled pilot targets 2026. The [current hub](../../project/README.md) and [cloud handoff](../../project/CLOUD_HANDOFF.md) provide the reconciled plan. Workstream counts and checks below remain scoped to their inspection snapshots.

Reviewed November 2, 2026 (America/New_York). Read-only source and metadata review; no service, source packet, customer store, database, Git index or cloud resource changed. No secrets or customer rows printed. This review does not replace independent domain acceptance or a security assessment.

## Judgment

Daylight has a substantial local research and prototype platform, including real PostgreSQL imports, immutable evidence transport, research queries, local AI/privacy controls and an integrated internal advisor research path. It is not yet a reproducible team checkout, deployed cloud backend, recoverable off-machine service, or consumer recommendation system. The shortest responsible path is a curated code repository plus a private evidence archive and separately controlled databases; moving the whole folder into Git or copying the Mac's runtime wholesale would preserve the wrong boundaries.

## Observed maturity

| Area | Present and evidenced | Remaining boundary |
| --- | --- | --- |
| Repository | Git on `main`, existing origin `https://github.com/cpuglis1/daylight-medicare.git`; 219 tracked files; last local commit October 21 (`7d15873`) | Current source, variants, data infrastructure and extensive governance work are largely untracked; no `.github` CI directory. Parent independently verified origin is public. No push performed. |
| Evidence backend | Separately packaged Python service; pinned requirements; PostgreSQL 17/18 check; nine checksummed migrations; stable source/derivation identities; roles; fenced leases; transactional COPY/checkpoints; immutable filesystem archive and an S3 adapter | Scheduler/connectors, general production release selection and original authority replay, full domain normalization and production deployment remain incomplete. S3 adapter is implementation, not evidence of a configured bucket. |
| Integrated local data | Build-r3 retains 17,767,179 source/context rows and 17,823,148 initial projections across 15 layers, ~58.0 GB | Counts do not prove unique facts, full reconciliation, permission or accepted personal use. Retained source/context JSON and initial projections are not complete relational domain models. |
| Query proof | `QUERY_VERIFICATION_R2.json` passes selected integrated population/lineage/query checks; read-only snapshot; no customer rows | Earlier `QUERY_VERIFICATION.json` is a failed attempt and is preserved; use the R2 receipt. It does not replay all original sources, grant semantics, or prove performance under cloud concurrent load. |
| Current app bridge | :8893 advisor's November 1–2 work uses retained 72 Collier identities and bounded real research queries; explicit internal identity preparation is locally active per dated packets | This is narrower than a consumer evidence service; research content stays out of consumer findings and AI context. The infrastructure README's unqualified “app bridge pending” wording is stale for this internal path. |
| API | FastAPI service-token authentication, separate cursor secret, strict request model, scope-bound pagination, pooled bounded read-only queries; consumer route explicitly returns 503 | Private skeleton is not a public production API. Dedicated deployed logins, network controls, target secrets, source authority loading and actual service deployment remain unproved. |
| Local privacy | Ignored `.env` at mode 0600; guest stores deliberately isolated; opt-in/sensitive saving; owner/revision/CSRF controls; seven-day guest scope; request text excluded from logs; memory-only conversation and learning | Cloud accounts/recovery, staff roles/SSO, actual vendor/data-flow review, cloud retention/deletion/incident operations and allowed remote processing require explicit implementation and review. This audit did not inspect customer data. |
| Backup | 5,214,333,924-byte logical backup, hash/CRC and full decode to SQL without execution; no customer profiles in this research backup | No clean database restore, cluster-global roles, external evidence archive or off-machine copy in that backup. Same-machine archive/dump does not establish disaster recovery. |
| Portability | Dockerfile/compose and package exist; core archive has non-macOS streaming fallback; dependencies pinned | Image tags not exact verified digests; builds/cloud restore unverified; local launchd/plist and private socket/build receipts bind this Mac; ordinary installation does not recreate source/archive closures or pinned variants. |
| Multiworker reliability | Ingestion queue uses SKIP LOCKED, owner/fence/expiry checks and durable STOP states | Advisor conversation, learning, identity offers, active operations and some rate limits are process RAM; local profiles and shared AI ledger are SQLite. Multiple application replicas need a reviewed state/TTL/budget design and failure tests. Do not enable replicas mechanically. |

## Current file and Git census

At this review snapshot, `git ls-files --others --exclude-standard` found **60,708 untracked nonignored files**, including 56,805 under `docs`, 1,770 under `audit-evidence`, 1,010 under `cms-slice`, 744 under `alternatives`, 105 under `infrastructure`, 145 under `outputs` and 118 under `plans`. These are publication candidates only by Git's visibility rules, not a reviewed publication set. Concurrent authorized work can change these totals.

Numerous nonignored data artifacts exceed 50 MiB, including SQLite databases, compressed source inventories, extracted provider files and bulk source archives. Individual provider databases reach roughly 2.5 GB. Preserve the files and their immutable paths/hashes; exclude them from a curated code export and map them to private object storage without rewriting sealed manifests.

`git count-objects -vH` reports 26,516 loose objects (6.24 GiB), 2.45 GiB in packs and **58 temporary/garbage objects totaling 4.35 GiB**. The object tree is about 14.1 GB. No repair or pruning was attempted. A separate preserved repository/checkpoint and deliberate recovery investigation should precede any cleanup; do not delete, reset or garbage-collect while concurrent work is active.

Root `.gitignore` appropriately excludes `.env`, known runtime stores and selected generated outputs. It does not classify the majority of current evidence and artifacts. Nested infrastructure ignore rules exclude `.venv`, `.build`, `.postgres18`, `.state`, cache and package metadata. A blanket `git add -A` would be unsuitable.

## Concrete destination split

| Destination | Put here | Keep out |
| --- | --- | --- |
| Team Git repository (owner subsequently confirmed existing public origin) | Current source, tests with fictional fixtures, SQL migrations, locked dependency inputs, source adapters, schemas, small reviewed source/acceptance manifests, runbooks, product/company documentation, CI and sanitized config examples | Raw PDFs/ZIPs, massive CSV/SQLite/JSONL evidence, local database clusters, dumps, logs/transcripts, guest data, credentials, machine caches and audit binaries |
| Private content-addressed object storage | Exact original source bytes, immutable revision packets, extraction/build artifacts and manifests, reviewed retained audit exports, DB backups with separate prefix/policy | Public access, customer data mixed with public-source ingestion, mutable overwrites of sealed evidence |
| Managed PostgreSQL evidence service | Typed identities/relationships, provenance and object references, observations/conditions, jobs/checkpoints, review events, release/acceptance bindings | Treating imported observations as accepted facts or using a generic JSON payload as the final semantic model |
| Separately scoped private customer store | Permissioned profiles, authorizations and the eventual reviewed decision/delivery journal, only after retention/access requirements are implemented | Automatic migration of current local guests, raw transcripts by default, public-source ingestion roles |
| Secrets/operations systems | Service/database secrets, cloud identities, structured redacted monitoring, backup/restore receipts | `.env` in source control, browser database credentials, credentials inside evidence manifests |

Supabase versus AWS is a hosting choice after boundaries, account/region, cost and operational ownership are fixed. The existing package already targets standard PostgreSQL plus an S3-compatible interface; retain that portability rather than introducing a second schema or rewriting frozen evidence to match a vendor. Supabase requires explicit compatibility proof for the project's database roles/migrations and customer-access design; AWS requires actual account/IAM/network/compute/backup ownership. Neither is presently deployed in the reviewed repository.

Today, `~/.aws/config` and `~/.aws/credentials` are absent, no `supabase/` project directory exists, and the finite cloud/service environment variable check found none in this execution process. This is a local configuration observation, not proof that the owner has no accounts elsewhere. The prior `CLOUD_DECISION.json` also records no configured account or provisioned resource.

## Smallest useful organization and preflight work

1. Add one current project entrypoint linking the variant map, capability ledger, source/release state and operating runbooks. Keep dated evidence intact; use indexes and a manifest to reduce navigation noise before any physical relocation.
2. Build a metadata-only publication inventory with an explicit reviewed allowlist. Flag private/machine roots, paths outside the checkout, symlinks, large artifacts, unresolved classifications and destination visibility. Report counts/bytes and path categories, never customer rows or credential values.
3. Produce a curated export for the confirmed public repository, preserving relative source paths initially, plus an immutable path-to-object manifest for evidence. Do not move frozen packets or change their absolute paths in place. Verify export contents and a clean-checkout bootstrap before any push.
4. Add CI appropriate to each package: Python/Node syntax checks; fictional unit/contract tests; disposable PostgreSQL integration/security tests; manifests and code-binding validation; dependency/secret/publication checks. Keep paid model calls, real customer stores and sealed-source mutation out of CI. Capture exact test environment and skips rather than reporting a total alone.
5. Document package ownership and PR/review rules, especially protected variants, sealed data code, shared budget and source/release authorization. The current single working tree is actively changing; independent branches/worktrees and exact version snapshots are needed for reliable parallel review.
6. Prepare target configuration and a least-privilege/private architecture, then exercise one bounded synthetic archive/DB/API round trip and a clean isolated restore with roles and archive mappings before importing the entire evidence population.
7. Upload verified public-source evidence and restore/rebuild research data only after actual account/region/bucket/database/network/cost choice. Keep customer migration and consumer advice activation as separate gates.
8. Resolve process RAM versus shared ephemeral state deliberately. A single-instance private demonstration is a defensible initial topology; high availability later needs shared TTL state or explicit restart semantics, cross-worker authorization, distributed rate/budget enforcement and a tested recovery path. Persisting current conversation memory would change privacy behavior and is not an incidental scaling fix.

## Priority blockers

- **Team code handoff:** curate and preserve the current uncommitted source before collaborating through the confirmed public GitHub origin; verify every selected file against that visibility. Do not publish the entire workspace to the existing public origin.
- **Recoverability:** execute a clean restore on an isolated target and establish encrypted off-machine retention of database, roles/config and content archive. Restore proof matters more than another dump.
- **Cloud target:** explicit actual account, region, cost, managed database version, object store, service identities and owner. No paid provision was authorized or performed by this review.
- **Consumer serving:** exact source-use/method/output acceptance, immutable release selection/revocation, accepted-reference replay and supported domain models remain required. Internal identity inspection does not satisfy these.
- **Current-year scope:** the real integrated research populations are 2026; the UI's five sample plans are unvalidated 2027 records. Choose and implement an explicit live MVP effective-year scope without overwriting 2026 or implying the sample supports 2027 recommendations.

## Verification performed and limits

Read PRINCIPLES and infrastructure/variant instructions; inspected exact local load, R2 query, backup, cloud-decision and historical QA receipts; sampled archive/jobs/API/app/privacy code; checked Git/file metadata, ignore configuration and cloud configuration presence. Parsed **394 relevant Python source files successfully** with `ast.parse`, without writing bytecode. No full suite, live HTTP call, paid model, database query, restore, service restart, Git mutation, credential-content scan, cloud call or customer-data read was performed. Historical test receipts are reported as historical evidence, not rerun results.

Primary local references:

- `infrastructure/daylight-data/README.md`
- `infrastructure/daylight-data/runbooks/PERSISTENT_LOCAL.md`
- `infrastructure/daylight-data/runbooks/PREFLIGHT.md`
- `docs/data/infrastructure-plan-2026-10-29/IMPLEMENTATION_PLAN.md`
- `docs/data/infrastructure-execution-2026-10-29/README.md`
- `docs/data/infrastructure-execution-2026-10-29/QA_PREFLIGHT.md`
- `docs/data/infrastructure-execution-2026-10-29/CLOUD_DECISION.json`
- `docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3/LOAD_COMPLETE.json`
- `docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3/QUERY_VERIFICATION_R2.json`
- `docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3/BACKUP.json`
- `alternatives/advisor-first/AGENTS.md` and `README.md`
- `alternatives/advisor-first/advisor_memory.py` and `identity_journey.py`
- `cms-slice/scripts/guest_profiles.py`, `guide_server.py` and `ai_budget.py`
- `docs/planning/ARCHITECTURE_ALIGNMENT_AND_IMPLEMENTATION_2026-11-02.md`

## Authorized preparation follow-up

The owner subsequently confirmed the existing public GitHub repository and a controlled 2026 pilot first. The root agent delegated additive publication preparation. Implemented only `tools/project_readiness.py`, `tools/tests/test_project_readiness.py` and `docs/project/publication-policy.json`; no existing source/evidence/ignore files changed. Six focused tests use fictional temporary Git repositories and pass. The metadata-only tool blocks protected/ignored paths, symlinks/escape, bulk artifacts, nonmigration SQL, unclassified files and candidates over 50 MiB. A candidate is eligible for content review, explicitly not certified safe to publish. Public destination scope is recorded without inventing another approval requirement.

The refreshed logical inventory at 2026-11-02 18:16:22 UTC counts 219 tracked files (11,378,346 bytes), 60,722 untracked nonignored files (25,282,543,469 bytes) and 33,054 ignored paths (93,953,623,387 bytes). This excludes Git objects and sibling runtime and does not account for APFS clones/deduplication. It classifies 1,129 code and 380 documentation review candidates, 59,136 evidence-archive artifacts, 33,058 private/local paths and 292 unclassified paths. Results are at `/private/tmp/daylight-project-readiness-inventory-20261102.json`; concurrent work can change counts.
