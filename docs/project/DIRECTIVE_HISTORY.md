# Directive history

Until November 5, 2026, owner directives were prepended as dated paragraphs to
the agent entry points. That made `AGENTS.md` 18,896 bytes and the advisor's
`AGENTS.md` 39,201 bytes, with current and superseded direction interleaved.

On November 5 the owner directed consolidating that history into one living
document ([CURRENT_STATE.md](CURRENT_STATE.md)) and moving dated history out of
the agent entry points. The two files below are **byte-exact copies** of the
entry points as they stood before that change. Nothing was paraphrased or
removed from them.

| Copy | Original path | Bytes | SHA-256 |
| --- | --- | --- | --- |
| [AGENTS.root.2026-11-05.md](directive-history/AGENTS.root.2026-11-05.md) | `AGENTS.md` | 18,896 | `1bd7d2cd40ed36bee02b6737d3a694992d53658ee110c82938de27287c218fac` |
| [AGENTS.advisor-first.2026-11-05.md](directive-history/AGENTS.advisor-first.2026-11-05.md) | `alternatives/advisor-first/AGENTS.md` | 39,201 | `c409d805d86807e9a0d40b6b25ff8de72116b969485acb8f8a1aec938e200600` |

## How to use this history

- Directives here remain binding where a later directive or
  [CURRENT_STATE.md](CURRENT_STATE.md) has not superseded them.
- Before changing an area, read its entries and the evidence packet each links.
- If the consolidated documents and a directive here disagree, treat it as an
  open question for the owner, not as permission to choose either one.

## New directives

Append below, newest last: date, decision ID, the owner's direction, and the
evidence link. Then update [CURRENT_STATE.md](CURRENT_STATE.md) in place.

| Date | ID | Direction | Evidence |
| --- | --- | --- | --- |
| 2026-11-05 | — | Consolidate governance: short `AGENTS.md` entry points, one living current-state document, dated history preserved here. | [Stack implementation record](STACK_IMPLEMENTATION_2026-11-05.md) |
| 2026-11-05 | D94 | Proceed with inventory, recovery-first exact deduplication and compact MVP storage preparation within existing local capacity. Preserve every source, critical inference, all 41 meanings, fourteen feature families, holds and exact-purpose gates; report actual space observations and remaining review. | [Storage maintenance](../reviews/storage-maintenance-2026-11-05/README.md) |
| 2026-11-05 | D94 | Proceed next with the database/index redesign within current space. Preserve every source and MVP feature; verify recovery before retiring anything. This extends the physical database scope while retaining source, privacy and purpose gates. | [Database/index redesign](../reviews/database-redesign-2026-11-05/README.md) |
| 2026-11-06 | D94 | Reconcile the dependency-lock mismatch while preserving sealed history and current dependency work; rerun verification and explain what remains for review. | [Dependency reconciliation](../reviews/dependency-reconciliation-2026-11-06/README.md) |
| 2026-11-06 | D95 | Evaluate the database against the AI-native brokerage plan and prepare transition actions. Cloud migration is expected soon; off-machine/PITR work is lower priority than AI-native database readiness. Preserve source/history/MVP and recovery-before-retirement; keep actual-target cutover checks. Evaluation does not authorize deployment or consumer release. | [Database readiness assessment](../reviews/ai-native-database-readiness-2026-11-06/README.md) |
| 2026-11-06 | D96 | Implement the backend plan for Collier PDP and Medigap data. No UI changes; keep consumer display gated until data approval, and report what is done and remains open. Preserve existing source/history/privacy boundaries; implementation does not supply data approval. | [Backend plan](../reviews/collier-plan-type-backend-2026-11-06/README.md) |
| 2026-11-07 | D98 | Draft the pilot scope amendment and budget/logging recommendations, and set up the development protections; bring concrete decisions for owner approval. Proposal drafting and SA-02 controls are authorized; scope exceptions, spending/retention changes, purchases and pilot release remain pending. | [Pilot security stage 1](../reviews/pilot-security-stage1-2026-11-07/README.md) |
| 2026-11-07 | D99 | Replace the proposed layered pilot budgets with one $100 total pilot model limit and track usage per participant. No hourly/daily/session/invitation/pool dollar sublimits or monthly reset. Evaluate alternatives to GitHub Pro to keep costs down. Budget direction is approved; runtime activation, retention details, pilot exceptions, paid upgrades and PR merge remain separate. Existing local development budgets remain unchanged. | [Updated pilot decisions](../reviews/pilot-security-stage1-2026-11-07/DECISIONS.md) |
| 2026-11-07 | D100 | Stay on private GitHub Free and accept the documented manual review process for the invite-only pilot. Proceed with free repository protections and P0 security and abuse engineering. Preserve launch, source and retention gates and record actual verification. | [P0 execution](../../audit-evidence/pilot-p0-security-20261107/README.md) |
| 2026-11-08 | D101 | Accept the proposed pilot scope and numeric usage retention. Deploy on AWS `us-east-1` with the OpenAI GPT API. Owner reports signed agreements and account security set. Verify with fictional traffic and review the deployed pilot before admitting participants. Measure actual cost per completion in the pilot. | [Deployment record](../../audit-evidence/pilot-deployment-20261108/README.md) |
| 2026-11-08 | D102 | Owner reports setting a $20/month AWS alert budget for the pilot. Verify the selected workload account and budget scope before provisioning. | [Deployment record](../../audit-evidence/pilot-deployment-20261108/README.md) |
| 2026-11-08 | D109 | Redirect, don't deflect: state the applicable general rule, name the personal gap, ask the approved question; never show a blank turn; every active turn ends with an approved question; rolling discourse brief for bounded context; coverage year defaults to 2026 for the review checkpoint. Pilot-rule statements are pending owner acceptance. | [UX review baseline and run](../../audit-evidence/ux-review-baseline-20261108/README.md) |
| 2026-11-08 | D110 | Owner: “I need to focus on getting the product in front of people legally. Getting licensed and getting user feedback on product should be the focus right now”. Deprioritize the accelerator scramble; advance licensing/operating readiness and legally scoped product-feedback preparation in parallel. Participant scope and existing release/privacy/evidence gates still require their own closure. | [Owner direction and scope](../../DAYLIGHT_REQUIREMENTS.md#change-log) |
| 2026-11-08 | D111 | Live persona evaluation (P01–P09): raise the :8893 allowance to $15/provider/UTC day; a brevity demand is not a pause; the never-blank floor always ends with a question and never states a rule the reports rule out; keep a sound reply when only its question is missing; trial right resolved against the reported start; chip-label typed answers recorded server-side; Plans page derives the priority order from the conversation and drops the reason-code banner; pilot-rules r2 drafted pending acceptance. | [Run log and fixes](../../docs/evaluations/medicare-personas-2026-11-08/run-2026-11-08/RUN_LOG.md) |
| 2026-11-09 | D112 | All-20 grading fixes without paid calls: 14 reviewed-statement drafts in pilot-rules r2 (inert until accepted) with rule triggers from resolved reports and stated money pressure; the person's own dates/figures/names are echoable; plans-chat context compaction before the request bound; clarification loops closed (consistent retirement clauses, phrase answers, affirmative confirms the pending value, “Yes, that's right” chip); “Part A only” records RC04; on-screen plan names and no boilerplate. | [Grading](../../docs/evaluations/medicare-personas-2026-11-08/run-2026-11-08/GRADING.md) · [Fixes](../../docs/evaluations/medicare-personas-2026-11-08/run-2026-11-08/FIXES_2026-11-09.md) |
| 2026-11-09 | D113 | Amends D97: Plans-page entries are the person's own reports — saved quietly (no chat bubbles, no AI call, no “is that right?”), several medicines/doctors per Add, chat additions extend the list; the next chat reply acknowledges them once by name and asks for any others. Plus retest fixes R1–R5 and the Plans-chat memory fix. | [Retest](../../docs/evaluations/medicare-personas-2026-11-08/run-2026-11-08/RETEST_2026-11-09.md) · [Fixes](../../docs/evaluations/medicare-personas-2026-11-08/run-2026-11-08/FIXES_2026-11-09.md) |
| 2026-11-09 | D113 | Owner authorized the full setup in the existing Obsidian vault: local Daylight sources, connected Drive and relevant ChatGPT history; shared skills for Codex and Claude Code; preserve originals and flag conflicts. Single-Mac, private, on-demand scope. Historical discussions, imports and agent agreement do not confer acceptance or alter governing decisions. | [Obsidian setup and maintenance](OBSIDIAN.md) |
| 2026-11-10 | D114 | Pursue a public rebrand. Screen arbitrary wordmarks federally before deeper clearance, including Classes 035, 036, 042 and future 009. Advance Florida entity formation for December accelerator applications and FMO outreach, and advance agency licensing while the brand is under review. Both names remain open. | [Name screen and licensing path](../reviews/brand-screen-2026-11-10/README.md) |
| 2026-11-10 | D115 | Replace the two-word candidate list with single words and closed compounds. Prioritize existing words. | [Second-round screen](../reviews/brand-screen-2026-11-10/README.md#single-word-and-closed-compound-screen) |
| 2026-11-10 | D116 | Screen short single words and closed compounds that are easy to say like Daylight. Move away from botanical-sounding candidates and run USPTO searches before presenting the list. | [Third-round screen](../reviews/brand-screen-2026-11-10/README.md#short-plainspoken-name-screen) |
| 2026-11-10 | D117 | Use familiar dictionary words and established closed compounds. Use Chapter as a benchmark for familiarity. Screen Classes 009, 035, 036 and 042 and distinguish zero records from inactive records. | [Familiar-word screen](../reviews/brand-screen-2026-11-10/README.md#familiar-dictionary-word-screen) |
| 2026-11-10 | D118 | The owner favors Midmorning and asked for familiar alternatives that suit the existing daylight aesthetic. Tagline wording is open for review. | [Midmorning alternatives](../reviews/brand-screen-2026-11-10/README.md#midmorning-alternatives) |
| 2026-11-10 | D119 | The owner identified Mid Morning as the working brand choice and requested a marketplace confusion check, brand story and slogan options. | [Marketplace screen and copy options](../reviews/brand-screen-2026-11-10/README.md#mid-morning-marketplace-and-copy-review) |
| 2026-11-10 | D120 | Screen familiar alternatives whose meanings convey a reason to use the product, using Daylight and Chapter as examples. | [Meaning-led name screen](../reviews/brand-screen-2026-11-10/README.md#names-that-carry-the-product-story) |
| 2026-11-10 | D121 | “Just make the company MidMorning.” Update :8894's visible branding and Ask labels. Hero: “Medicare, on your terms.” Support: “Understand your options, weigh the tradeoffs, and take your next step.” No em dash or text after it; no AI in the hero. Preserve the visual design and functional code/storage identifiers. Necessary AI disclosures and protected surfaces stay. Shared backend/model identity is left unchanged in this frontend increment. | [Implementation and limits](../../audit-evidence/midmorning-8894-20261110/README.md) |
| 2026-11-10 | D122 | “Finish the backend rebrand too so the advisor calls itself MidMorning. Keep the internal code names and saved data unchanged, and check the pending changes before restarting anything.” Update authored backend copy, inspect pending changes and verify offline before local activation; retain protected variants, permissions and acceptance gates. | [Execution and restart review](../../audit-evidence/midmorning-backend-20261110/README.md) |
| 2026-11-10 | D123 | Use the newly purchased CSG Actuarial account through the screen to complete Medigap evidence. After seeing the source-use restriction and download rejection, the owner specifically authorized the XLSX download and stated that CSG permits this use. Collect native exports with fictional inputs into an additive private candidate; preserve exact source/method/consumer gates and existing source STOPs. | [Acquisition and verification](../data/l10-medigap-2026-10-28/csg-2026-11-10/README.md) |
| 2026-11-10 | D124 | Continue using CSG without Data Feeds for the Collier pilot, without solicitation. The owner plans an upgrade afterwards and will include vendor costs in the raise. Use available native exports and carrier evidence now; retain exact coverage and unresolved conditions. No upgrade or new spending is authorized. | [Pilot continuation](../data/l10-medigap-2026-10-28/csg-pilot-2026-11-10/README.md) |
| 2026-11-10 | D125 | “Do one final pass through 8894 for any leftover Daylight branding, including error messages, and clean it up without changing internal names or saved data.” Audit the D121/D122 result; preserve internal names, records and protected variants. No further app changes were needed after the checked surfaces and failure paths passed. | [Final branding audit](../../audit-evidence/midmorning-final-pass-8894-20261110/README.md) |
| 2026-11-10 | D126 | “Prices matched to each participant.” Match exact ZIP, age, sex/gender category, tobacco and date; do not substitute age-65 examples or nearby profiles. Prepare native-export requests for uncaptured profiles and preserve class/eligibility/source/output distinctions. | [Pilot continuation](../data/l10-medigap-2026-10-28/csg-pilot-2026-11-10/README.md) |
| 2026-11-10 | D127 | “prices should appear immediately, but stop after we cover 65-74. thats okay for the pilot :) just say 75+ is not supported for medigap if we get ther”. Precollect exact supported profiles; make the age restriction a pilot pricing limit, never an insurance eligibility finding. Operator-assisted collection is preparation, not the participant workflow. | [Pilot continuation](../data/l10-medigap-2026-10-28/csg-pilot-2026-11-10/README.md) |
| 2026-11-10 | D128 | “read through/scan through: 34101–34108 and get them integrated into the back end db!!” Review the 320-profile complete subset and load an additive private PostgreSQL revision with verified exact-profile reads. The owner explicitly approved the NOLOGIN loader/reader permissions for the new private CSG schema, with public access denied and no memberships added. Further collection remains paused; preserve original sources, public-evidence history and consumer/source gates. | [Backend import](../data/l10-medigap-2026-10-28/csg-backend-2026-11-10/README.md) |
| 2026-11-10 | D131 | Replace duplicate Medigap-page intake with an invitation to the existing conversation; retain chat answer buttons, known reports, drafts and immediate matched prices. | [Implementation and checks](../../audit-evidence/medigap-conversation-entry-20261110/README.md) |
| 2026-11-10 | D130 | Connect chat age, pricing sex and tobacco reports to automatic Medigap prices; ask only missing details with clear purpose. Preserve the eight-ZIP, 65–74 scope, 75+ limit, shared privacy controls and all other tool behavior. | [Implementation and checks](../../audit-evidence/medigap-chat-profile-20261110/README.md) |
| 2026-11-10 | D129 | Wire the eight-ZIP Medigap cache into the existing app tab for immediate matched prices, ages 65–74, with 75+ unsupported for the pilot. Reuse the MA UI; no other tool changes. Authorizes bounded local source-price display with exact profile/date matching, retained conditions and STOPs; no binding quote, eligibility inference, recommendation, general source acceptance or hosted deployment. | [Implementation and checks](../../audit-evidence/medigap-ui-8894-20261110/README.md) |
| 2026-11-10 | D132 | “i dont love mid morning. close but not it. anything better?” Reopen the consumer name search and screen familiar candidates with a product story in the four target USPTO classes. | [Follow-up name screen](../reviews/brand-screen-2026-11-10/README.md#follow-up-after-midmorning) |
| 2026-11-10 | D134 | Connect Part D like Medigap: existing shared chat profile, missing-only conversation entry, published plan cards/details/comparison, exact 2026 Collier scope and explicit personal-cost limits. | [Implementation and checks](../../audit-evidence/part-d-ui-8894-20261110/README.md) |
| 2026-11-10 | D133 | Favor normal one- or two-syllable words. Records in other classes are acceptable for the shortlist, with actual related goods and services considered in screening. | [Shorter name screen](../reviews/brand-screen-2026-11-10/README.md#one--and-two-syllable-names) |
| 2026-11-10 | D135 | “those suck! Day bed sounds like deathbed!! Try again!” Reject Daybed and the previous shortlist; continue the short, familiar-word search. No replacement selected. | [Further screen](../reviews/brand-screen-2026-11-10/README.md#after-the-daybed-rejection) |
| 2026-11-10 | D136 | “i dont love daylong either. can you try another batch of simple, normal words? one or two syllables, with a good story like Chapter. it doesn't have to start with day. check USPTO first.” | [Screen and limits](../reviews/brand-screen-2026-11-10/README.md#short-words-beyond-day) |


## D130 · November 10, 2026 · Shared chat profile for Medigap

Owner: “yes, wire the full chat profile into medigap so age, sex, and tobacco status fill automatically and prices update. only ask for missing info, and don’t change anything else. please be mindful however. This means that we need to introduce a few more questions into the profile as well. and we should ensure to keep language clear, and explain why we are asking certain questions when we do. please read the current way we ask questions just to be sure!”

Add three conditional, purpose-explained local pricing questions; retain the original 41 meanings. Reuse resolved beneficiary reports, preserve unknowns and corrections, and automatically refresh the existing eight-ZIP, age-65–74 cache display. The age is explicitly for November 10, 2026. A helper’s details, gender identity, smoking-only history or a coarse age band must not be silently converted into pricing facts. Existing optional sensitive saving and scoped AI permission apply to the new fields; rates stay outside saved/model data. The 75+ unsupported limit, source conditions/STOPs, D64 independence, original UI and protected variants remain. [Implementation and checks](../../audit-evidence/medigap-chat-profile-20261110/README.md).


## D131 · November 10, 2026 · Medigap intake belongs in the conversation

Owner: “I dont like the click enter, it should be buttons in form mode but in the conversation. like we shouldnt just be a form. does that makes sense. that really shouldn't be there if the convo gets that information out. and we should direct people to engage with the tool in order to get that information, like if people skip to that page, there is just a button and prompt, think medigap is right for you, talk to midmorning to give more info and we can get the right plans for you blah. that needs to be the case”

The Medigap page invites people with missing details to “Talk to MidMorning.” Its button opens the existing chat at the appropriate question without sending a message or replacing a draft. Reuse shared reports; preserve the existing conversational buttons, free text, unknown/defer choices and reasons. Corrections return to the same conversation instead of opening a second form. Ready profiles still load exact source prices automatically. Retain the pilot bounds, source/eligibility limits, sensitive-save controls and MA/Part D behavior. [Implementation and checks](../../audit-evidence/medigap-conversation-entry-20261110/README.md).


## D134 · November 10, 2026 · Part D conversation and published-plan integration

Owner: “incorporate part d in a very similar way to what we just pulled off, great job”

Extend D129–D131’s interaction pattern to the existing Part D tab. Use the ten
retained 2026 Collier PDP offerings, with dated published premiums/deductibles,
all source fields and conditions. Reuse the existing shared profile for person,
ZIP/county, year and medicines; do not introduce another intake form or ask for
Medigap age/sex/tobacco categories. Missing details and edits open the existing
conversation without sending a message or replacing drafts. Keep the 2026 pilot
year default explicit; reported other years, unknowns and conflicts retain their
limits. Personal medicine/pharmacy cost calculations, subsidies, eligibility,
current enrollment availability and recommendations remain unresolved. This is
bounded local display authority, not a fabricated source/method review receipt,
research release promotion or hosted deployment. Preserve the immutable D96
build and its source STOPs, optional sensitive saving and other app behavior.
[Implementation and checks](../../audit-evidence/part-d-ui-8894-20261110/README.md).

## D137 · November 11, 2026 · Restore Daylight

“Okay revert back to daylight, medicare plain as day.” Restore the Daylight name
across :8894 and the advisor backend, the headline “Medicare, plain as day.” and
the previous support sentence. Keep internal names, saved data, newer Medigap
and Part D functionality, protected variants and acceptance gates unchanged.
Check pending changes before restarting. This supersedes D121/D122/D125 branding.
[Execution and verification](../../audit-evidence/daylight-restore-20261111/README.md).

## D138 · November 11, 2026 · Connect the conversation to the Medigap and Part D tabs

“okay excellent. implement.” with: yes, the chat may relay what the Plans tabs
can show; yes, price people about to turn 65 at age 65; no 2027 Part D data for
the pilot. Follows the fix plan written after the six November 10 live
conversations. The first increment changes capture of age, sex category and
tobacco use, tells the model each tab's status, rejects a reply that denies what
a ready tab shows, starts the Medigap or Part D route when the product is named,
opens the Plans page on the matching tab and records a bare ZIP or age without
AI while replies are paused. D129 is unchanged: no rate, plan name or count
enters model context. Acceptance and the live release gate remain open.
[Changes, checks and remaining work](../../audit-evidence/conversation-panels-d138-20261111/README.md).

## D139 · November 11, 2026 · Final Daylight branding pass

“Do one final pass through 8894 for any leftover MidMorning branding, including
the Medigap and Part D tabs and error messages. Keep internal names and saved
data unchanged.” Verify D137 across the active frontend and advisor messages,
using read-only browser inspection and isolated errors. No remaining branding
change was required; no app edit, restart or live model call ran. The saved-data
and source hashes match before and after.
[Verification](../../audit-evidence/daylight-final-pass-8894-20261111/README.md).

## D140 · November 11, 2026 · Login-free guest progress and public launch planning

The owner wants useful demo progress to survive an accidental refresh in the
same browser without a consumer login. Public access to the tool is intended
after the demo in 2027, also without a consumer login. The owner requests an
assessment of the security layer, LLM controls, tooling and cost savings before
that launch. Apply D54 and the existing guest and visit privacy boundaries to
the demo. Keep the D101 invite-only pilot scope, including disabled saved
profiles, distinct from the local fictional demo. Public retention, budget,
deployment and release decisions remain open. See the [guest persistence
design](../product/MASTER_DESIGN.md#8-guest-persistence-privacy-and-security)
and [launch security gates](../company/LAUNCH_SECURITY_SPEC_2026-11-06.md#8-launch-gates).

## D141 · November 11, 2026 · Implement local controls and prepare the AWS launch

The owner approves proceeding with locally feasible guest recovery and security
work, selects AWS CloudFront and AWS WAF, and reconfirms the $100 cumulative
invite-only model budget with re-evaluation afterward. This workstream will
support the eventual secure backend and site launch. Host, edge, account and
deployment-dependent controls can wait until that launch. Consumer use of the
tool remains login-free. Apply the established guest, saving, privacy, source
and pilot admission boundaries. Record implemented checks and unresolved
deployment work in the [launch checklist](../../infrastructure/daylight-pilot/README.md)
and [evidence packet](../../audit-evidence/guest-resume-security-20261111/README.md).

## D142 · November 11, 2026 · Retire the repo vault; use the Daylight Brain

The owner retires the `daylight_obsidian/` vault and its D113 refresh tooling.
Do not run `tools/obsidian/sync.py` or the `daylight-knowledge` skill. Business
context now lives in the Daylight Brain in the owner's Google Drive (Daylight /
Daylight Brain), synced to this Mac at
`~/Library/CloudStorage/GoogleDrive-chris@daylightmedicare.com/My Drive/Daylight/Daylight Brain/`.
Its `AGENTS.md` is the entry point. The old vault remains on disk as reference
only. This repository's authority order, numbered decisions and engineering
rules are unchanged.

## D143 · November 11, 2026 · Option A; CSquared; Spark

The owner chooses Option A over the earlier Option B indication. As the licensed
agent in charge, the owner approves the deterministic decision methods in
advance; recommendation and enrollment are fully self-guided with no per-case
licensed review. Counsel's written answer on required licensed involvement
remains an open dependency before any real recommendation or enrollment. The
legal entity is CSquared, a Delaware C-corp (Clerky; filing planned January 1,
2027); Daylight remains the public brand. Spark Advisors is the FMO in talks.

## D144 · November 12, 2026 · Separate lean Collier demo database

The owner references Claude's proposal to retain the research database locally,
defer RDS and copy only pilot-serving data, and says: “I generally agree. what is
the leanest verified version or subset of the database that can be used for the
local collier county pilot? Don't delete anything. the end result is a 29gb db
and another smaller db that the app can use for the demo.” The owner also directs
consulting the second brain. Build an additive, verified local display subset;
retain the original database, evidence, source STOPs and existing consumer gates.
No cloud spend, budget-alert change or hosted release is implied. See the
[implementation and verification](../../audit-evidence/collier-pilot-subset-20261112/README.md).


## D145 · November 12, 2026 · Unified local demo before AWS

“Would it be possible to wire a local host port that has a tidy front end back
end using the demo db. different from 93+94, just all in one? Would that make
the most sense before we port things into aws. And, please track these
differences in the second brain if so”

Implement the separate local integration baseline at :8895: the current :8894
frontend plus direct advisor API in one process, the D144 verified demo database,
independent guest store/cookies, and the existing shared local model allowance.
Record current local and future AWS differences in the Daylight Brain. Preserve
:8893/:8894, the full research database, protected variants/stores, source STOPs,
sealed history, consent, independent inclusion and all acceptance gates. This
local service does not implement the hosted invitation gate or cumulative pilot
budget and does not authorize participant admission or cloud provisioning.
[Verification and operating instructions](../../audit-evidence/unified-demo-8895-20261112/README.md).
