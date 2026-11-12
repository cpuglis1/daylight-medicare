# Daylight: current state

Living document · last updated November 12, 2026 (America/New_York), through D145. Edit this
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
  from the conversation. D112 fixes (active after D122's November 10 restart review; no new paid calls):
  own words are echoable; plans-chat context compaction; clarification loops
  closed with a "Yes, that's right" chip; "Part A only" records RC04;
  on-screen plan names. `pilot-rules-r2.json` holds statement drafts loaded
  only once the owner sets `review_state` to `owner_accepted_<date>`; until
  then the matching rule triggers stay silent. A live retest waits for the
  owner's clearance. A $1.57 targeted retest (Nov 9) confirmed the loop,
  Part A, brevity, long-opener, bound and judgment-line fixes and found R1–R7;
  D113 fixes R1–R5 and makes Plans-page entries silent, multi-item and
  acknowledged once in the next chat reply. The current source was checked
  offline and activated during D122; unaccepted rule drafts remain unloaded.
  [Restart review and saved-data verification](../../audit-evidence/midmorning-backend-20261110/README.md).
- Use fictional data for development and tests. No agent-run live conversation
  tests or paid probes; the owner assesses conversational quality.
- Report remaining gaps honestly. Do not mark a requirement implemented on intent.

## Surfaces and where to work

| Port | Source | Status |
| --- | --- | --- |
| :8895 | `alternatives/advisor-first/demo_server.py`, current `web-8894/` assets | D145 unified local demo: one loopback process serves the UI and API directly, using the D144 195 MB database. Independent guest store/cookies; shared existing development model budget. No :8893/:8894 proxy. Start with `Start Daylight Demo.command`. [Runbook and checks](../../audit-evidence/unified-demo-8895-20261112/README.md). |
| :8893 | `alternatives/advisor-first/` | Daylight advisor backend (D137 restores the name). The reference `web/` frontend retains Daylight branding. Scoped rules in its [AGENTS.md](../../alternatives/advisor-first/AGENTS.md). |
| :8894 | `alternatives/advisor-first/web-8894/`, `ui-8894/serve.py` | Daylight consumer interface (D137), with “Medicare, plain as day.” and “Understand your coverage options and prepare to enroll, at your pace.” Retains D93/D109 layout and behavior. Forwards API requests to :8893; D137 restores Daylight model instructions and public backend messages. D129 connects the Medigap tab to exact November 10 source prices for ZIPs 34101–34108, ages 65–74, with MA-style cards/details/comparison. D130 connects the shared chat profile and refreshes prices automatically. D131 replaces duplicate Medigap-page intake with “Talk to Daylight”; missing questions and corrections use the existing chat buttons/free text, preserving known reports and drafts. [Conversation entry](../../audit-evidence/medigap-conversation-entry-20261110/README.md). [Profile integration](../../audit-evidence/medigap-chat-profile-20261110/README.md). [Medigap verification](../../audit-evidence/medigap-ui-8894-20261110/README.md). D134 connects the Part D tab to the ten dated 2026 Collier PDP offerings, using the shared chat profile and the same conversation-first entry, cards/details/comparison. Published premiums/deductibles are available; personal drug costs and enrollment checks remain held. [Part D verification](../../audit-evidence/part-d-ui-8894-20261110/README.md). Internal identifiers, saved data and MA logic remain unchanged. |
| :8890 | `cms-slice/apps/ten-question/` | Protected original ten-question journey. |
| :8891 | `alternatives/chat-first/` | Protected alternative; also supplies pinned engine dependencies to :8893. |
| :8896 | `cms-slice/apps/chat/` | Protected previous guide. |
| — | `infrastructure/daylight-data/` | Research database and private read-only API for public evidence; separate private CSG schema and exact-profile repository (D128), read by D129's bounded app-price endpoint. |
| — | `infrastructure/daylight-operations/` | Customer-plane operations schema and model-call traces (added November 5; not wired into :8893). |

Protected variants and their guest stores are not edited or migrated. D137 restores
Daylight branding after D121/D122/D125, preserving current functionality and
saved data. D139's final pass found no leftover MidMorning branding in the
active source or inspected landing, Medigap, Part D and privacy views; isolated
error checks retain Daylight. No further app edit or restart was needed.
[Restoration](../../audit-evidence/daylight-restore-20261111/README.md) ·
[Final branding and saved-data checks](../../audit-evidence/daylight-final-pass-8894-20261111/README.md).

## Current milestone and data

- **Lean local demo database (D144):** `daylight_pilot_collier_2026_r1` is a
  separate 195 MB PostgreSQL display subset; the original research database is
  preserved (now measured at 31.01 GB after later imports). It retains the
  complete 320-profile/55,040-rate/3,840-benefit CSG cache and a separately bound
  copy of the 21 source-linked records behind the ten-plan Part D display.
  The 72 MA offerings keep their existing catalog files (10.46 MB of catalog
  and authority dependencies copied). All-column CSG parity, all 320 Medigap
  panel outputs and the full PDP output pass. The app has an explicit
  `--pilot-data` mode. D145 now runs the current UI and API together on :8895
  against this subset; the running :8893/:8894 services have not been switched.
  Original source controls must be reconciled before use/transfer; future
  STOPs do not propagate automatically between databases. Part D's retained
  earliest review deadline is November 24, 2026 at 00:00 UTC. The 12.18 MB
  compressed export passed full decompression/hash verification. AWS deployment,
  target-host recovery, source acceptance and budget changes remain separate.
  [Evidence and local connection](../../audit-evidence/collier-pilot-subset-20261112/README.md).
- **Demo continuity and AWS launch workstream (D140–D141):** Keep the consumer
  tool login-free. :8894 source now recovers accepted reports, the latest reply
  and the current plan tab after an ordinary reload, using a cookie-bound
  reference to the existing one-hour memory journal. Drafts and earlier chat
  remain unsaved; restart, expiry and eviction can end recovery. Fictional
  HTTP tests and desktop/tablet/phone inspection passed. The local :8893/:8894
  services were restarted and health/free-recovery checks passed. D141 selects
  AWS CloudFront and AWS WAF and reconfirms one $100 cumulative invite-only
  model budget, with public access and its allowance re-evaluated afterward.
  Public access remains a post-demo 2027 target. The
  [AWS launch runbook](../../infrastructure/daylight-pilot/README.md) records
  prepared policies and the pending live adapter, account, host and deployed
  [security gates](../company/LAUNCH_SECURITY_SPEC_2026-11-06.md#8-launch-gates).
  [Local verification](../../audit-evidence/guest-resume-security-20261111/README.md).
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
  was activated by D96. D134 now connects a separate bounded published-PDP display
  adapter to :8893/:8894; the original research API and its zero-review state
  remain unchanged. Personal drug/pharmacy cost calculations and recommendations
  remain held. [Part D integration](../../audit-evidence/part-d-ui-8894-20261110/README.md).
  D123 authorizes native CSG workbook acquisition with fictional profiles; the owner
  specifically authorized downloading and reported permission after the displayed
  license restriction was explained. Its private candidate remains separate from
  this public-evidence schema. D124 continues native export and carrier-document
  collection for the Collier pilot without solicitation, despite Data Feeds being
  absent. The owner plans a later upgrade and includes vendor costs in the raise;
  amount and timing remain unspecified. Feed absence does not stop available
  subscription work. D126 requires prices matched to each participant's exact
  quote profile; age-65 examples are not a substitute. D127 requires immediate prices for ages 65–74, so exact profiles must be
  cached before use. Ages 75+ show “Medigap pricing for ages 75+ is not supported
  in this pilot”; under-65 pricing also remains outside this cache. Missing
  supported profiles require preparation, not an operator during the participant
  session. Collection is paused. D128 authorizes scanning and integrating the complete
  320-profile subset for ZIPs 34101–34108 into an additive private PostgreSQL
  schema, with exact-profile reads. All 320 sources, 55,040 rate observations and
  3,840 benefit sheets are loaded in `dl_csg_medigap`; full stored-value parity
  and all 320 exact-profile reads passed. Existing public-evidence counts and
  selection are unchanged. The approved NOLOGIN roles have no memberships.
  D129 authorizes and locally activates exact-source premium display in the
  existing :8894 Medigap tab, using MA's visual pattern. The session-protected
  endpoint preserves all source classes/conditions and exact date matching;
  D130 now reuses the shared chat profile for ZIP, exact dated age, pricing sex
  and tobacco category. Three local questions ask only missing details and
  explain why. D138 asks “How old are you?”, records plain statements of age,
  sex category and tobacco use, shows a 64-year-old the age-65 prices, tells the
  model each tab's status and opens the Plans page on the tab the conversation
  is about; listed amounts still stay out of model context.
  D131 keeps those questions and corrections in the conversation;
  the Medigap page shows an invitation instead of a duplicate form. Its free
  navigation preserves drafts and does not send a message. Corrections refresh
  prices automatically; unknowns are not guessed.
  [Conversation-entry checks](../../audit-evidence/medigap-conversation-entry-20261110/README.md).
  Existing sensitive-save and scoped AI-context permission govern these reports;
  rate rows remain outside saved profiles and model context. The original 41
  meanings, pinned engine, data build and source STOPs are unchanged.
  The original 320-profile/55,040-rate parity receipt remains. D130 adds offline
  profile/HTTP/UI checks and desktop/tablet/phone inspection; an unrelated old
  visit-history test failure is reproduced on the baseline and remains open.
  [Shared-profile verification](../../audit-evidence/medigap-chat-profile-20261110/README.md).
  75+ is explicitly unsupported for Medigap in this pilot. This age limit does not
  apply to D134’s Part D reference. MA logic is unchanged.
  Independent source/method acceptance, binding quotes, eligibility and
  recommendations remain separate; no hosted deployment occurred.
  [App integration](../../audit-evidence/medigap-ui-8894-20261110/README.md).
  [Backend import](../data/l10-medigap-2026-10-28/csg-backend-2026-11-10/README.md).
  [Pilot continuation](../data/l10-medigap-2026-10-28/csg-pilot-2026-11-10/README.md).
  Medigap census/rating work, exact source/method/output
  approval and deployment remain open. See [CSG acquisition](../data/l10-medigap-2026-10-28/csg-2026-11-10/README.md)
  and [backend execution and remaining work](../reviews/collier-plan-type-backend-2026-11-06/implementation-r1/README.md).
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
| Launch human-involvement level (brokerage plan §3) | D143: owner chooses Option A. The owner, as licensed agent in charge, approves deterministic methods in advance; recommendation and enrollment are self-guided with no per-case review. Counsel's written answer remains required before real recommendations or enrollment. |
| Pilot AWS hosting budget | Owner reports setting $20/month in AWS Budgets (D102). Verify budget scope, workload account access and host estimate before provisioning. |
| Legal and operating route (counsel questions, brokerage plan §7) | Pending counsel. Add: whether HIPAA formally applies to the agency. |
| Legal entity name and consumer brand (D137) | Local :8894 branding and the shared advisor identity are restored to **Daylight**, with **Medicare, plain as day.** The earlier naming screens remain historical evidence. D143: the legal entity is CSquared, a Delaware C-corp (filing planned January 1, 2027); Daylight remains the public brand. Trademark clearance remains open. [Restoration](../../audit-evidence/daylight-restore-20261111/README.md) · [Name-screen history](../reviews/brand-screen-2026-11-10/README.md). |
| Enrollment route and FMO | D143: Spark Advisors is the FMO in talks (demo pending). Enrollment route not yet chosen. |

## How work runs

- **Business context (D142):** direction, status, business decisions and open
  questions live in the Daylight Brain, a small Obsidian vault in the owner's
  Google Drive, synced to this Mac at
  `~/Library/CloudStorage/GoogleDrive-chris@daylightmedicare.com/My Drive/Daylight/Daylight Brain/`.
  Read its `AGENTS.md` for company context. The D113 `daylight_obsidian/` vault is
  retired and kept only as reference; do not run `tools/obsidian/sync.py` or the
  `daylight-knowledge` skill. Neither vault is connected to the consumer advisor.
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
