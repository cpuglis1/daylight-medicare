# Daylight: current state

Living document · last updated November 10, 2026 (America/New_York), D120 added. Edit this
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
- Redirect, don't deflect (D109, November 8): state the general rule the
  person's reports make relevant, name the personal gap in one clause, then ask
  the approved question. Outside parties are the confirming step, never the
  answer or the follow-up question. Every active turn ends with an approved
  question; a failed generation shows one reviewed statement plus that
  question, never a bare status line. The seven statements in
  `alternatives/advisor-first/pilot-rules.json` were accepted by the owner on November 8, 2026.
- Live persona evaluation (D111–D112, November 8–9): all 20 fictional personas in
  `docs/evaluations/medicare-personas-2026-11-08/` were run and graded
  ($9.80 total, 364 calls; 0/86 must-not-claim violations; must-cover 41 ✔ /
  12 ◐ / 31 ✗, nearly every ✗ a missing reviewed statement; plan-comparison
  add-on 0 judgment / 0 invented). The :8893 allowance is $15/provider/UTC day.
  D111 fixes: a brevity demand is not a pause; the floor always ends with a
  question and never states a rule the reports rule out; sound replies survive
  a missing question; trial right resolved against the reported start;
  chip-label answers recorded server-side; Plans page derives the priority order
  from the conversation. D112 fixes (no paid calls; on disk, awaiting restart):
  own words are echoable; plans-chat context compaction; clarification loops
  closed with a "Yes, that's right" chip; "Part A only" records RC04;
  on-screen plan names. `pilot-rules-r2.json` holds 14 statement drafts loaded
  only once the owner sets `review_state` to `owner_accepted_<date>`; until
  then the matching rule triggers stay silent. A live retest waits for the
  owner's clearance. A $1.57 targeted retest (Nov 9) confirmed the loop,
  Part A, brevity, long-opener, bound and judgment-line fixes and found R1–R7;
  D113 (on disk, awaiting restart) fixes R1–R5 and makes Plans-page entries
  silent, multi-item and acknowledged once in the next chat reply.
- Use fictional data for development and tests. No agent-run live conversation
  tests or paid probes; the owner assesses conversational quality.
- Report remaining gaps honestly. Do not mark a requirement implemented on intent.

## Surfaces and where to work

| Port | Source | Status |
| --- | --- | --- |
| :8893 | `alternatives/advisor-first/` | Active advisor development. Scoped rules in its [AGENTS.md](../../alternatives/advisor-first/AGENTS.md). |
| :8894 | `alternatives/advisor-first/web-8894/`, `ui-8894/serve.py` | UI refresh (D93) plus the November 8 pre-pilot fixes (D109): question kept in view, sticky progress track, inline notices, coverage-path page before plan lists, one intake, sticky Plans header. Forwards everything else to :8893. :8893 stays the reference until promoted. |
| :8890 | `cms-slice/apps/ten-question/` | Protected original ten-question journey. |
| :8891 | `alternatives/chat-first/` | Protected alternative; also supplies pinned engine dependencies to :8893. |
| :8896 | `cms-slice/apps/chat/` | Protected previous guide. |
| — | `infrastructure/daylight-data/` | Research database and private read-only API (public evidence only). |
| — | `infrastructure/daylight-operations/` | Customer-plane operations schema and model-call traces (added November 5; not wired into :8893). |

Protected variants and their guest stores are not edited or migrated.

## Current milestone and data

- **Immediate owner priority (D110):** getting licensed and getting the product
  in front of people legally for feedback. Advance the founder's and business's
  licensing/operating readiness alongside preparation for a legally scoped
  feedback pilot; prioritize product work that enables this learning.
  D114 sets a December formation milestone for accelerator applications and
  FMO outreach. Advance the Florida entity and agency license alongside federal
  clearance for a replacement consumer mark. Establish the exact participant-facing
  scope and close its study/privacy and applicable launch gates before admitting
  participants. [Name screen and licensing path](../reviews/brand-screen-2026-11-10/README.md).
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
- **Pilot P0 security (D98–D101):** the owner approved one **$100 cumulative
  pilot model budget**, with per-participant usage tracking and no hourly/daily,
  session/invitation or pool dollar sublimits. An isolated fictional rehearsal
  implements the invite gate and ledger. Deployed enforcement remains open.
  D101 approves the guest-only scope and numeric usage retention and selects
  AWS `us-east-1` with the OpenAI GPT API. See the
  [decision packet](../reviews/pilot-security-stage1-2026-11-07/DECISIONS.md).
  The SA-02 local pre-commit hook is active. The founder merged
  [PR #4](https://github.com/cpuglis1/daylight-medicare/pull/4) into private `main`
  at `ebced4e`. Both checks and the initial Dependabot runs passed there.
  Actual local/hosted state is recorded in the
  [execution record](../reviews/pilot-security-stage1-2026-11-07/README.md).
  AWS CLI access and exact hosted verification remain open. Participant
  admission follows deployment review and the applicable launch gates.
  The owner approved private GitHub Free and the temporary manual review
  exception. Require a PR, documented founder review and passing checks on the
  final revision, with separate deployment approval. See the
  [P0 execution record](../../audit-evidence/pilot-p0-security-20261107/README.md)
  for local checks and remaining deployment and account evidence.
- **Counts that are not interchangeable:** L03 r9 freezes 392,570 claim and
  predicate obligations; the accepted r4 reference is 535 entries; the r12
  whole-offering pilot covers 4,675 obligations and is unaccepted. L01's
  published federal reference is accepted within its stated scope.
- **Scope settings** (`infrastructure/daylight-data/config/scope.2026.json`):
  routine network connectors off. Consumer release remains held.
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
| Pilot AWS hosting budget | Owner reports setting $20/month in AWS Budgets (D102). Verify budget scope, workload account access and host estimate before provisioning. |
| Legal and operating route (counsel questions, brokerage plan §7) | Pending counsel. Add: whether HIPAA formally applies to the agency. |
| Legal entity name and consumer rebrand (D114–D120) | Chris Paluzzi Insurance Agency, LLC is the recommended legal name. Mid Morning is the owner's working brand choice. The owner is also exploring familiar names with an immediate connection to the product. Clearance and tagline review remain open. [Meaning-led name screen](../reviews/brand-screen-2026-11-10/README.md#names-that-carry-the-product-story). |
| Enrollment route and FMO | Not started. HealthSherpa Medicare is the first candidate to evaluate. |

## How work runs

- **Shared knowledge (D113):** the private `daylight_obsidian/` vault indexes local
  sources, connected Drive material and relevant owner ChatGPT history for use
  on this Mac by Codex and Claude Code. Originals retain their authority;
  generated snapshots and historical conversations are not acceptance. Use the
  [Obsidian runbook](OBSIDIAN.md) for refresh, conflicts, shared skills and backup.
  Refreshes are on demand; the vault is not connected to the consumer advisor.
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
