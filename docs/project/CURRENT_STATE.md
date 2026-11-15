# Daylight: current state

Living document · last updated November 14, 2026 (America/New_York), through D171. Edit this
file in place when direction changes. Do not prepend dated directives here or
to any `AGENTS.md`; record them as described in "Changing direction" below.

## What Daylight is today

Daylight's mission is to help people understand Medicare choices, work through
the details and stay in control of decisions affecting their health and retirement.
AI and contextual education serve that mission (D160); the current product is a
local advisor and research platform for an AI-native Medicare brokerage. Its
first target is a **2026 controlled pilot in Collier County,
Florida** for first-time Medicare enrollees. It is not yet a released advice,
recommendation or enrollment service. Consumer recommendation purposes are held.

D161 makes first Part A/Part B enrollment an essential core journey and directs
two top-level Plans tabs: **Original Medicare** and **Medicare Advantage**, with
Medigap and separate Part D within Original Medicare. The
[conversation and dashboard plan](../planning/medicare-enrollment-2026-11-12/PLAN.md)
keeps the existing conversation and adds shared enrollment status, signup
preparation, return/follow-through and coordinated coverage steps. D161 changes
the intended structure; it does not release recommendations, application
submission or consumer use.

D164 builds D161 as one push for :8895 only. **Running on :8895. The two path
tabs, the three decisions and the sign-up guides were checked on the real page
at desktop, tablet and phone widths with no model call. The status line, the
chat cards, the recorded finishes and status updates are verified offline only,
because seeing them on the page takes a conversation. Not run live and not
owner accepted.** The first report of this build called it done after offline
tests; six defects then turned up on the page (the old three tabs first) and
are listed in the build packet's ledger. After the owner's own test conversation on
November 13 (evening): fifteen profiles were run live on :8895 and evaluated (`audit-evidence/enrollment-d161-20261112/profile-runs-20261113/EVALUATION.md`), and the fixes were built the same evening: a coverage reader for what people already have, Parts A and B derived from a Medicare Advantage plan or a Medigap policy, a two-shows-then-park question budget, doctor entries split before the search, no silent or doubled fallback turns, cards and plan buttons triggered from the state of the conversation, word-group matching for the approved catalog, near-miss identifier rules, a checker rule against first-person recommendations, and a per-turn trace. **Built, passing offline and loaded on :8895 (restarted that evening, after the server log was read: the two 93-second failures and most dropped replies were traced and fixed; see `LOG-FINDINGS.md`). Not yet run live.** What was not built and which fixes sit in files :8893 also loads: `BUILD.md` in the same folder.

November 13, quick fixes followed on :8895 (no text between the top of a plans page
and the plans beyond tabs, steps and filters; a tab opens at step 1, then where the
person left off; the repeat Parts A and B question; date and address formats on the
doctor card); the rest of his comments are design work, tracked in the Brain's UX
playbook, issues 32 to 44. With the :8895 switch on (`enrollment_flow.enable`,
called by `demo_server.py`): a Part A / Part B status line with the next step in
the chat and on the plans pages; a sign-up route card; “Parts A and B only”,
keep current coverage and wait as recorded finishes with a summary; status
updates from the person's own words (`enrollment.partA`, `enrollment.partB`,
`intent.components`, extended `intent.coveragePath`); two path tabs (Original
Medicare, Medicare Advantage) with three decisions each over the existing
Medigap, Part D and Medicare Advantage panels; three sign-up guides served from
`enrollment-content.json`; coordinated dates. The record is Codex's
`enrollment_journey.status`. **:8893/:8894 are unchanged:** the switch is off
there, so they keep the three plan tabs and none of the new wording. The new
sentences await the owner's sign-off. [Build packet](../../audit-evidence/enrollment-d161-20261112/README.md).

D165 connects the doctor and medicine checks to the existing :8895 conversation
and evaluation sorting. The local matrices cover 72 MA offerings for networks
and 71 drug-bearing offerings for formularies, with separate Original Medicare
assignment evidence. The latest build and review limits are recorded in the
[implementation packet](../../audit-evidence/d165-conversation-research-20261113/README.md).
The hosted fictional display rehearsal uses the existing invite gate and a
portable archive. Live-provider approval, release review and host verification
remain open.

D166 changes how the :8895 conversation decides what to do next. A bounded,
visit-only planner separates current purpose, established reports, tentative
understanding, preferences, explored paths and explicit decisions. It answers
questions before advancing, permits requested pricing without a teaching
interview, and suppresses premature pricing intake and unrelated cards. Opening
Original Medicare, asking about Medigap or preferring predictable costs does
not choose a path. Deterministic recommendation methods and exact-purpose
evidence gates remain unchanged. The owner-supplied laptop photograph is the
:8895 main image, with no on-page photo credit at the owner's request. These
overrides are enabled by `conversation_planner.enable` only on :8895 and
isolated fixtures. :8893/:8894 and protected ports retain their behavior.
Implementation, activation and actual checks are recorded in the
[D166 packet](../../audit-evidence/discussion-planner-20261113/README.md).
D167 adds explicit spoken component decisions, direct investigation routing and
shared pharmacy/refill research across plans, with supported retail-average
premium-plus-drug amounts as an optional within-group ordering. Missing estimates
remain visible and unranked; estimates do not release recommendations or establish
exact-store prices. Expected outcomes now preserve PP16's undecided state.
138 offline checks passed, including six scripted profile replays (PP07, PP09,
PP12, PP13, PP15 and PP16). A separate synthetic ten-plan journey exercises
cost collection, sorting and correction/source-STOP withdrawal. D170 reran the two retained local-source
journeys successfully with read-only local database access and model sockets
blocked. D171 explicitly authorized ending in-memory visits and activated the
verified D167/D170 backend on :8895; saved profiles and protected services were preserved.
The [D167 packet](../../audit-evidence/profile-replay-20261114/README.md) separates
implemented behavior from verification limits. Live model quality, full actual-source
journeys and owner acceptance are not established by these offline tests.

D168 changes the evaluation unit to complete behavior-led journeys across chat
and actual navigation. The [new corpus](../evaluations/behavioral-journeys-2026-11-14/README.md)
contains twelve reactive fictional personas, each with direct/interrupted variants,
private facts, observable detours, decision boundaries and useful-finish criteria.
The prior PP01–PP16 corpus remains coverage regression evidence. The corpus, run protocol and evidence grader are prepared; corpus validation and
18 grader tests pass. D169 requested actual runs and retained conversation/UI findings.
The attempted evaluation incorrectly used live models despite the offline restriction:
37 messages across ten started visits, nine reaching final user requests; BJ10 only
began and BJ11–BJ12 were not run. Full transcript capture failed during a browser
reset; reconstructed notes and exact telemetry are retained in the
[partial report](../../audit-evidence/behavioral-live-20261114/REPORT.md). No runtime
was changed. False A/B status, wrong destinations and incomplete finishes were
observed on the running build, whose exact revision was not pinned. D170 supplies an isolated
offline browser/source binding and retained replay evidence; human review remains open.
No passing profile rate, completed twelve-profile run or optimal flow is claimed for D169;
live/paid restrictions are unchanged.

D170 repairs explicit A/B precedence, contradiction handling and date precision;
retains the requested investigation through side questions and Plans; suppresses
personal-match labels with unchecked criteria; and records useful visit summaries
without restarting intake. Partial medicine-detail updates retain unresolved siblings. Standard Plan G and education-only exploration have
separate destinations. The browser harness uses real handlers and UI, fresh
temporary stores, declared local language and synthetic positive/negative sources,
with backend socket/DNS/subprocess and browser-origin restrictions. Each action is flushed
to durable evidence. See the [D170 packet](../../audit-evidence/behavioral-fixes-20261114/README.md)
for exact checks, per-profile outcomes and runtime hashes. Under D171, the owner
explicitly authorized a restart and ending existing in-memory visits. :8895 now
runs the verified backend (PID 93906; revision
`7e2ab919e4935398e34f75cc5eafa352a65286e67a50aa81eef19b9026c09bb0`).
Read-only checks confirmed the frontend hashes, unchanged saved-profile bytes,
753 unchanged protected files, source gates and unchanged model-call counters.
Existing pages need a refresh. [Activation evidence](../../audit-evidence/behavioral-fixes-20261114/activation/README.md).
Live-language quality and owner acceptance remain open.

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
| :8895 | `alternatives/advisor-first/demo_server.py`, current `web-8894/` assets | D145 unified local demo: one loopback process serves the UI and API directly, using the D144 195 MB database. Independent guest store/cookies; shared existing development model budget. No :8893/:8894 proxy. Start with `Start Daylight Demo.command` (restart: `Restart Daylight Demo.command`). D147 turns on evaluation-only tiered sorting here only. [Runbook and checks](../../audit-evidence/unified-demo-8895-20261112/README.md). |
| :8893 | `alternatives/advisor-first/` | Daylight advisor backend (D137 restores the name). The reference `web/` frontend retains Daylight branding. Scoped rules in its [AGENTS.md](../../alternatives/advisor-first/AGENTS.md). |
| :8894 | `alternatives/advisor-first/web-8894/`, `ui-8894/serve.py` | Daylight consumer interface (D137), with “Medicare, plain as day.” and “Understand your coverage options and prepare to enroll, at your pace.” Retains D93/D109 layout and behavior. Forwards API requests to :8893; D137 restores Daylight model instructions and public backend messages. D129 connects the Medigap tab to exact November 10 source prices for ZIPs 34101–34108, ages 65–74, with MA-style cards/details/comparison. D130 connects the shared chat profile and refreshes prices automatically. D131 replaces duplicate Medigap-page intake with “Talk to Daylight”; missing questions and corrections use the existing chat buttons/free text, preserving known reports and drafts. [Conversation entry](../../audit-evidence/medigap-conversation-entry-20261110/README.md). [Profile integration](../../audit-evidence/medigap-chat-profile-20261110/README.md). [Medigap verification](../../audit-evidence/medigap-ui-8894-20261110/README.md). D134 connects the Part D tab to the ten dated 2026 Collier PDP offerings, using the shared chat profile and the same conversation-first entry, cards/details/comparison. Published premiums/deductibles are available; personal drug costs and enrollment checks remain held. [Part D verification](../../audit-evidence/part-d-ui-8894-20261110/README.md). Internal identifiers, saved data and MA logic remain unchanged. |
| :8890 | `cms-slice/apps/ten-question/` | Protected original ten-question journey. |
| :8891 | `alternatives/chat-first/` | Protected alternative; also supplies pinned engine dependencies to :8893. |
| :8896 | `cms-slice/apps/chat/` | Protected previous guide. |
| — | `infrastructure/daylight-data/` | Research database and private read-only API for public evidence; separate private CSG schema and exact-profile repository (D128), read by D129's bounded app-price endpoint. |
| — | `infrastructure/daylight-operations/` | Customer-plane operations schema and model-call traces (added November 5; not wired into :8893). |

D155 gives active free-text questions, questions with choices and retained chat
questions the same bold, larger type on the shared :8894/:8895 frontend.

Protected variants and their guest stores are not edited or migrated. D137 restores
Daylight branding after D121/D122/D125, preserving current functionality and
saved data. D139's final pass found no leftover MidMorning branding in the
active source or inspected landing, Medigap, Part D and privacy views; isolated
error checks retain Daylight. No further app edit or restart was needed.
[Restoration](../../audit-evidence/daylight-restore-20261111/README.md) ·
[Final branding and saved-data checks](../../audit-evidence/daylight-final-pass-8894-20261111/README.md).

## Current milestone and data

- **Pilot Medicare fact base (D158–D159, D162–D163):** 71 of the [74 source-backed statements](../data/pilot-knowledge-2026-11-12-r2/REVIEW.md)
  are owner-accepted for general education and active on :8895 only: the original
  40 plus 31 additions. Exact acceptance lives in
  `alternatives/advisor-first/pilot-knowledge-review-8895-r2.json`; the original
  approval file and both sealed catalogs remain unchanged. The
  [16-situation enrollment reference](../data/pilot-knowledge-2026-11-12-r2/ENROLLMENT.md)
  distinguishes windows, actions, coverage starts and prerequisites.
  `pk_fl_under65`, `pk_fl_group` and `pk_fl_waiting` remain disabled with legal holds.
  The exact initial MA opening/closing date and duration after adding Part B later
  remain withheld because official summaries differ. Composition receives that
  restriction; bounded validation rejects tested numeric/date/worded deadline
  claims, including user-suggested clocks and cached answers.
  Local selection uses the existing conversation and Sources disclosure, with no
  extra model stage or service. Live status confirms 71 available facts after the
  :8895 restart. All 239 offline checks pass; desktop/tablet/phone landing screens
  were inspected. Existing guest reports and all charge/reservation rows remain
  unchanged; the checks added one empty anonymous guest and advanced UTC-day
  metadata. :8893 and protected listeners were unchanged. No Brain edit or
  paid/live model conversation occurred. Live answer quality remains owner-assessed;
  this is general education, not personal deadline or recommendation authority.
  [Acceptance, verification and limits](../../audit-evidence/pilot-knowledge-r2-activation-8895-20261112/README.md).
- **UX pass after the PP16 test conversation (D157):** the shared :8894/:8895 conversation and Plans pages were
  reworked toward the owner's goal (“the easiest self-guided Medicare experience on the market”). Deterministic
  legacy helpers live in `ux_pass.py` (enrollment timing, say-once record, reply clean-up, coverage path) and
  `ux_flow.py` (the four hooks `natural_flow.py` calls); five signed-off statements are in
  `pilot-rules-r4-ux-pass.json`. The conversation no longer shows pilot, demo or research wording; the plan year
  stays as a plain label pending the owner's confirmation. The coverage path is a profile field
  (`intent.coveragePath`). On :8895, D166 supersedes inferred path leans, fixed reply cleanup and pricing-first selection;
  it keeps actual enrollment reports and the existing evidence/check services. `DAYLIGHT_DISABLE_UX_PASS=1` turns the legacy hooks off. **State: implemented and offline
  verified; current code is running on :8895 after D159's restart.** D159 checked the live landing at
  three widths; the complete PP16 experience still needs browser/live review and owner acceptance.
  :8893 has not been restarted for these changes. Six backend and data-layer items are handed off with failing tests. Eight
  older tests that script the removed familiarity and COBRA-start questions are in `tests/known-failures.json`.
  [Evidence](../../audit-evidence/ux-pass-pp16-20261112/README.md) ·
  [Handoff](../../audit-evidence/ux-pass-pp16-20261112/HANDOFF.md).
- **Evaluation-only tiered recommendation (D147):** on :8895 only, a
  deterministic method sorts Medicare Advantage, Medigap and Part D plans and the
  two coverage paths into “Matches your priorities”, “Meets your needs, not all
  your priorities” and a set-aside group, with ✓ / ✗ / ? checks on each plan.
  D165 feeds dated exact-product formulary and clinician-office observations into
  local evaluation sorting. Individual plan checks may remain unknown. Named
  drug suggestions with reported prescriptions still await evidence and method
  review. [Method](../product/tiered-recommendation-2026-11-12/METHOD.md) ·
  [D165 verification](../../audit-evidence/d165-conversation-research-20261113/README.md).
- **Pilot doctor, pharmacy and cost priority (D146):** Bring the necessary
  2026 identity search, pharmacy/drug normalization, network evidence, deterministic
  cost validation and serving/freshness work into the November pilot. The owner
  selects directories first with targeted confirmation and validated average-based
  estimates first. The [concrete plan](../planning/pilot-data-2026-11-12/PLAN.md)
  maps existing DQ tasks to a November 16 first-session readiness checkpoint and
  November 20–23 expanded-candidate/review checkpoints. The first foundation
  increment has a separate local PostgreSQL package
  `daylight_pilot_foundation_2026_r1` with 46 evidence datasets, 2,742,964
  source-parity records, and bound offline-only Python reads. The database is
  2.39 GB with a 165.30 MB compressed export. Wrong year, missing acceptance,
  stale evidence and source withdrawal fail closed. The 195 MB display database
  still runs :8895. [Evidence and handoff](../../audit-evidence/pilot-data-foundation-20261112/README.md).
  DQ-16 and DQ-20 now have a regional doctor index, exact dated Medicare
  Advantage and separate Original Medicare evidence, and correction invalidation
  in an opt-in loopback fixture. The 67-query fixture found the expected
  identities in the top five for 64/64 known-answer queries. All 72 MA offerings
  are accounted for, with qualified dated edges for 43. D154 replaces the D152
  doctor launcher with checks that follow doctor reports in the ordinary :8895
  conversation. Known names and locations are reused; software asks for the
  remaining exact identity, office, coverage and date and presents dated evidence
  inline. The task remains visit only. The standalone D150 preview at :8898 is
  historical evaluation tooling. Independent review and participant use remain held.
  [Chat verification](../../audit-evidence/pilot-doctor-chat-8895-20261112/README.md).
  [Doctor review packet](../../audit-evidence/pilot-doctors-20261112/README.md).
  DQ-12/13/18/19/27/33 have an offline prescription candidate for exact
  product and outlet selection and deterministic average-based estimates.
  Thirteen priced comparisons matched independent arithmetic across 213 fills,
  and 15 comparisons stayed held. :8895 remains the shared working demo.
  D154 removes the separate fictional-cost entry and parallel `/d146/` visit
  from its normal launcher. Drug checks now use the same conversation's medicines,
  refill quantities, days supply, pharmacy and assistance reports, asking only for
  missing exact selections or calculation inputs. The result appears inline and
  changed inputs, expiry and source STOPs withdraw it. The earlier rehearsals remain
  historical evidence. These local checks do not authorize participant use or
  supply accepted results to D147 sorting; official comparisons, exact-purpose
  approval and hosted verification remain open.
  [D154 journey verification and limits](../../audit-evidence/conversation-checks-8895-20261112/README.md).
  The Brain UX playbook and [implementation rules](../product/CONVERSATION_IMPLEMENTATION.md)
  now explicitly require delivery through the person's existing story, not a tool
  entry, separate setup or repeated intake. Runtime and offline checks are distinct
  from owner acceptance of live conversation quality.
  [Prescription candidate and review pack](../../audit-evidence/d146-drug-estimate-20261112/README.md) ·
  [Shared :8895 chat verification](../../audit-evidence/d146-chat-8895-20261112/README.md).
  Exact-store prices, unresolved network crosswalks,
  missing criteria/units, independent review and host readiness remain distinct
  dependencies. H01's first-target choice is decided; personal cost serving and
  recommendation holds remain until their exact gates pass. Later 2027 work remains.
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
- **Demo continuity and AWS launch workstream (D140–D141, D148):** Keep the consumer
  tool login-free. The shared :8894/:8895 UI returns to chat on reload and
  reconstructs earlier replies and available recent inputs from the existing
  cookie-bound, one-hour visit memory. The logo opens Home in place, where
  **Continue the conversation** preserves drafts. Three named opening choices
  show a fixed local reply after a minimum 1.85-second pending state (D156). Durable profile saving
  is opt-in. Restart, expiry and eviction can end recovery. See
  [D148 verification and runtime status](../../audit-evidence/conversation-continuity-d148-20261112/README.md).
  D141 selects
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
  The owner approved private GitHub Free. Changes reach `main` by PR. Under D149,
  a PR merges automatically once both checks pass on its final revision
  (`.github/workflows/auto-merge.yml`). Exceptions: Dependabot proposals,
  drafts and PRs labeled `no-auto-merge` still need founder review.
  Deployment needs separate approval. See the
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
