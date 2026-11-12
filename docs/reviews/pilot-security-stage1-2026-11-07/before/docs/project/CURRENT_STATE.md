# Daylight: current state

Living document · last updated November 6, 2026 (America/New_York). Edit this
file in place when direction changes. Do not prepend dated directives here or
to any `AGENTS.md`; record them as described in "Changing direction" below.

## What Daylight is today

Daylight is a local advisor and research platform for an AI-native Medicare
brokerage. Its first target is a **2026 controlled pilot in Collier County,
Florida** for first-time Medicare enrollees. It is not yet a released advice,
recommendation or enrollment service. Consumer recommendation purposes are held.

## Authority, in order

1. [PRINCIPLES.md](../../PRINCIPLES.md), including D64: commercial economics never
   enter inclusion, eligibility, filtering, ranking, explanation or personal fit.
   [Independence acceptance](../product/INDEPENDENCE_ACCEPTANCE.md) (I01–I10) defines
   the release evidence.
2. Numbered owner requirements in [DAYLIGHT_REQUIREMENTS.md](../../DAYLIGHT_REQUIREMENTS.md)
   and [MASTER_DESIGN.md](../product/MASTER_DESIGN.md). A newer explicit owner
   decision wins; record it there.
3. [D73 strategic thesis](../product/STRATEGIC_THESIS.md) and its change-review checklist.
4. This document, for current scope and where to work.
5. Dated directive history ([DIRECTIVE_HISTORY.md](DIRECTIVE_HISTORY.md)): still
   binding where not superseded; read the entries for an area before changing it.

[PRODUCT.md](../../PRODUCT.md) "Requirement Precedence" governs older design briefs.

## Rules that hold in every task

- Coverage paths before policies. Keeping current coverage, deferring and
  uncompensated options are valid outcomes.
- Unknown evidence stays unknown: never scored as worse, hidden or described as unsuitable.
- Source-use, method and consumer-purpose acceptance are separate gates.
  Acquisition, extraction, a test count or a model's agreement is not acceptance.
- Keep the 41 conditional meanings, source STOPs, material holds and exact-purpose gates.
- Changing accepted or sealed data/code means a new revision with exact
  before/after accounting and the applicable review. Never edit a sealed revision.
- Privacy: no new raw-transcript persistence; chat stays visit-only; saving, AI
  transfer, family sharing, human handoff and enrollment are separate permissions.
- Use fictional data for development and tests. No agent-run live conversation
  tests or paid probes; the owner assesses conversational quality.
- Report remaining gaps honestly. Do not mark a requirement implemented on intent.

## Surfaces and where to work

| Port | Source | Status |
| --- | --- | --- |
| :8893 | `alternatives/advisor-first/` | Active advisor development. Scoped rules in its [AGENTS.md](../../alternatives/advisor-first/AGENTS.md). |
| :8894 | `alternatives/advisor-first/web-8894/`, `ui-8894/serve.py` | UI refresh (D93); forwards everything else to :8893. :8893 stays the reference until promoted. |
| :8890 | `cms-slice/apps/ten-question/` | Protected original ten-question journey. |
| :8891 | `alternatives/chat-first/` | Protected alternative; also supplies pinned engine dependencies to :8893. |
| :8896 | `cms-slice/apps/chat/` | Protected previous guide. |
| — | `infrastructure/daylight-data/` | Research database and private read-only API (public evidence only). |
| — | `infrastructure/daylight-operations/` | Customer-plane operations schema and model-call traces (added November 5; not wired into :8893). |

Protected variants and their guest stores are not edited or migrated.

## Current milestone and data

- **Next release target (D91 r6):** one complete Collier consumer journey:
  consequential eligibility, doctor and medicine checks, supported comparison
  and a usable next action. See [CONSUMER_JOURNEY.md](../product/recommendation-scope-2026-11-04-r6/CONSUMER_JOURNEY.md).
- **Data milestone (D91):** all 72 retained 2026 Collier offerings prepared for
  tool access. The latest offline catalog is
  [r13](../product/recommendation-scope-2026-11-04-r13/REVIEW.md). Report plan
  coverage, field preparation, source/method acceptance and app access
  separately, never as one "done".
- **Pilot backlog:** P01–P15 in [COLLIER_MVP.md](COLLIER_MVP.md). P06–P10 are
  what stands between today and personal recommendations.
- **Counts that are not interchangeable:** L03 r9 freezes 392,570 claim and
  predicate obligations; the accepted r4 reference is 535 entries; the r12
  whole-offering pilot covers 4,675 obligations and is unaccepted. L01's
  published federal reference is accepted within its stated scope.
- **Scope settings** (`infrastructure/daylight-data/config/scope.2026.json`):
  routine network connectors off; cloud deployment pending an account decision;
  consumer release held.
- **Collier plan-type execution (D96):** owner authorized the
  [PDP/Medigap backend plan](../reviews/collier-plan-type-backend-2026-11-06/README.md).
  The selected build in the additive `dl_plan_types` research schema holds 277,198
  source/serving records, including all ten PDP offerings and the omitted Medigap benefit/monthly
  table files. All loaded values/conditions passed parity; 17 new backend tests
  and 29 reference regressions passed. The authenticated research API/CLI and
  version/role/STOP controls are implemented; no UI, daemon or advisor integration
  was activated. Consumer display remains held with zero genuine approvals.
  Medigap census/rating work, source/method/output approval and deployment remain
  open. See [execution and exact remaining work](../reviews/collier-plan-type-backend-2026-11-06/implementation-r1/README.md).
- **Next database priority (D95):** prepare the evidence-to-decision service and
  permissioned customer plane for the AI-native brokerage. The
  [assessment and proposed sequence](../reviews/ai-native-database-readiness-2026-11-06/README.md)
  cover portable release bindings, typed evidence tools, exact authority,
  customer permissions and durable decision/review records. The five offline
  evaluation suites and operations SQL on PostgreSQL 18.6 pass; operations is
  still not deployed or connected to the advisor. Fictional probes confirmed
  missing recommendation and enrollment workflow guards. Further local
  off-machine/PITR work is lower priority; retain recovery-before-retirement
  and check recovery on the selected cloud target at cutover.
- **Storage maintenance (D94):** recovery-verified exact copies share APFS blocks
  while retaining original paths and bytes. The restored offline MVP snapshot
  preserves all 72 offerings, fourteen feature families, 41 meanings and 229 holds.
  The database/index redesign is complete: the research DB is 29.37 GB (previously
  58.01 GB), with 22.43 GB accounted reduction after new recovery/trial storage.
  Full local clean restore, all 1,283 original/staged chunk hashes, live feature
  checks and post-retirement reads passed. The same database identity serves
  compact read views. The active advisor, customer stores and source values
  remain unchanged. The historical dependency-lock mismatch is reconciled:
  exact archived inputs pass 759 queries and 756 checks, while the current
  38-package lock remains unchanged. Clean target installation and cloud-cutover
  recovery proof remain open under the D95 priority above. See [dependency reconciliation](../reviews/dependency-reconciliation-2026-11-06/README.md),
  [file-cleanup measurements](../reviews/storage-maintenance-2026-11-05/README.md)
  and [database/index execution](../reviews/database-redesign-2026-11-05/README.md).

## Open owner decisions

| Decision | State |
| --- | --- |
| Launch human-involvement level (brokerage plan §3) | Owner has indicated Option B (async licensed review). Record it as a numbered decision to make it binding. |
| Cloud provider (AWS or Google Cloud), region, budget | Undecided. Deployment scripts wait for this. |
| Legal and operating route (counsel questions, brokerage plan §7) | Pending counsel. Add: whether HIPAA formally applies to the agency. |
| Enrollment route and FMO | Not started. HealthSherpa Medicare is the first candidate to evaluate. |

## How work runs

- The main folder holds substantial uncommitted work. Use targeted changes;
  never reset, stash or discard unrelated changes.
- Paperclip agents work in separate snapshot worktrees, never in this folder.
  Patches return for deliberate integration. See [PAPERCLIP.md](PAPERCLIP.md).
- Evidence for a change goes in a dated packet under `audit-evidence/` or
  `docs/`, with exact checks run and their actual results.
- The [stack evaluation](STACK_IMPLEMENTATION_2026-11-05.md) maps the recommended
  solo-founder stack onto what already exists here.

## Changing direction

When the owner gives a new instruction:

1. Add a numbered entry to the change log in `DAYLIGHT_REQUIREMENTS.md`.
2. Append the dated directive text to [DIRECTIVE_HISTORY.md](DIRECTIVE_HISTORY.md).
3. Edit the affected lines of this document so it describes the new present.
   Remove what the new direction supersedes rather than stacking a new paragraph on top.
4. Leave `AGENTS.md` files alone unless the reading order or a hard rule changed.
