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


## D146 · November 12, 2026 · Pilot doctor, pharmacy and drug-cost readiness

“Let's bring this forward for the pilot. Put together a concrete plan using what
we already have, identify what you can build now and what needs outside data or
my input, and update the brain and planning sheet.”

The owner then chose “Directories first; targeted confirmation” and “Validated
average-based estimates first.” Move the relevant 2026 work into the pilot
sequence while retaining the later 2027 obligations. Reuse L05–L08 and the
D144/D145 local baseline; identify the additional serving package needed because
the 195 MB display subset excludes these research services. Record exact build,
external-evidence, owner/reviewer and deployment dependencies. The approach is
decided; individual source/method/output acceptance and lawful participant use
remain gated. No source STOP, sealed revision, protected variant, commercial
independence, permission or budget boundary changes. No purchase, outreach,
paid/live test or consumer recommendation release is implied.
[Plan and acceptance evidence required](../planning/pilot-data-2026-11-12/PLAN.md).

## D147 · November 12, 2026 · Evaluation-only tiered recommendation

“I would say for the decision, lets try to create a rudimentary deterministic
recommendation. it filters and scores how many of your preferences are met by a
plan, and a users preferences that are categorical are also accounted for as
well. so a tiered filtering scoring system, that prioritizes the preferences
dynamically. sounds pretty basic. and run that for all MA, Medigap, Part D.”

“sure, i agree. Why dont we go ahead and implement. tiers is spot on. Rank by
priority order will probably just be "priority group" "filtered, but not stated
priority" and "not-filtered to" part D, yes. Yes. Explain recommendations and
model in each plan with little checkmarks in ui if possible. you can build it
right? And evaluation will be fictional, we will return to those profiles
shortly after this is implemented.”

Build method v1 for fictional evaluation on the unified local demo (:8895) only:
eligibility and needs set plans aside, stated priorities split the rest into two
groups, priorities met, other preferences met, then cost order rank within a
group, unknown is never a
miss, and drug coverage names no pick while medicines are unchecked. Show the
checks on each plan and the method on each page. Preserve D64 independence (no
commercial input), D129 (no rates in model context), D143 (counsel before real
recommendations), the pilot gate, protected variants, sealed revisions and source
STOPs. No consumer release, paid/live test or profile write follows.
[Method](../product/tiered-recommendation-2026-11-12/METHOD.md) ·
[Checks](../../audit-evidence/tiered-recommendation-d147-20261112/README.md).

## D148 · November 12, 2026 · Keep the conversation through refresh and Home

The owner reports that refresh preserved only the latest reply and once opened
Plans. Refresh should return to chat with the earlier replies available during
the visit. The logo may open Home, whose main action should say **Continue the
conversation** after a conversation has started. The first response from a
named starting option should be quick with a short pending state. Apply this
to the existing named starting options, retaining deliberate Send and an
approved follow-up question. Faster starts improving retention is a hypothesis.
Keep visit recovery within existing memory limits and profile saving explicit.
[Implementation and checks](../../audit-evidence/conversation-continuity-d148-20261112/README.md).

## D149 · November 12, 2026 · Auto-merge clean pull requests

“can you auto merge prs if they are clean so we have no backlog of prs.”

A pull request merges automatically once both repository checks
(`repository-checks`, `dependency-security`) pass on its final revision. This
replaces documented founder review before merge. GitHub Free private repositories
offer no branch protection or native auto-merge, so
`.github/workflows/auto-merge.yml` enforces the conditions: same repository, not
a draft, no `no-auto-merge` label, and mergeable. Dependabot proposals stay
manual because pinned locks, including the pilot data's runtime pins, need
deliberate review. Passing checks are not source, method, release or participant
acceptance, and deployment approval remains separate.

## D150 · November 12, 2026 · Doctor confirmation in the local demo

The owner asks to wire the D146 doctor lookup into the Daylight demo: ask
for the doctor’s name first, ask for city or practice if it is unclear, and
let the person confirm both the doctor and office before checking a plan.
The new **Check a doctor** flow runs on the isolated fictional demo at :8898
with a temporary guest store. It uses the existing Collier plan catalog,
Original Medicare route, evidence controls and correction checks. Participant
use, independent source/method review and connection to the shared chat
profile remain separate.
[Implementation and verification](../../audit-evidence/pilot-doctor-demo-20261112/README.md).

## D151 · November 12, 2026 · D146 prescription checks in the :8894 chat

“Yes, please finish wiring D146 into the :8894 chat. Verify corrections, expiry,
and STOP handling end to end there, and keep participant release held pending
official comparisons and review.”

The local rehearsal uses the existing :8894 chat and a separate fictional guest
session. It reads current chat reports and collects missing prescription
details in the conversation.
[Implementation and verification](../../audit-evidence/d146-chat-8894-20261112/README.md).

## D152 · November 12, 2026 · Doctor checks inside the :8895 chat

The owner clarifies that the complete D150 lookup must run inside the chat on
:8895. The name uses the chat composer. Clarification, doctor and office
selection, and dated coverage evidence appear in the same conversation pane.
The local lookup uses the existing exact source controls and holds. Returning
to the conversation restores its draft. The standalone :8898 surface remains
the earlier preview. No participant release or evidence acceptance follows.
[Implementation and checks](../../audit-evidence/pilot-doctor-chat-8895-20261112/README.md).

## D153 · November 12, 2026 · Shared D146 demo on :8895

The owner clarifies the common development surface: “8895 is a version of
94+93 with lighter backend. we are working out of 8895”. The unified demo
chat offers the doctor task and the fictional prescription rehearsal. The
rehearsal keeps its own model-free guest visit on the same port. Earlier
previews remain reference evidence. Participant release is held pending
official comparisons and review.
[Implementation and verification](../../audit-evidence/d146-chat-8895-20261112/README.md).

## D154 · November 12, 2026 · Doctor and drug work occurs naturally in chat

“No it needs to occur naturally in the chat, as the conversation is occuring.
What portion of the second brain is not clear about that? we need to make sure
that this type of broken addition doesnt occur again”

“And whats up with the ‘check fictional drug prices.’ again all of this needs to
occur naturally in a user story. its not about adding features, but helping the
user feel the full experience.”

“Read the UX playbook and fix 8895 so doctor and drug checks happen naturally in
the conversation, using what we already know. Update the implementation rules
so this doesn't happen again.”

The continuous user story and ask-once rule were already explicit in the Brain.
This corrects implementation, not an unclear product objective. Reuse the same
visit's reported doctors, medicines, pharmacy and scope; ask only necessary
clarifications, make exact deliberate choices in the current question, run the
supported check and continue in the same conversation. Remove separate check
launchers and the fictional-session detour from the normal :8895 journey.
Preserve dated evidence limits, source STOPs, expiry, privacy and release holds.
The [implementation rules](../product/CONVERSATION_IMPLEMENTATION.md) require
verification from the person's words and corrections, alongside rendered checks.


## D155 · November 12, 2026 · Consistent question typography

The owner asks for all questions to use the larger bold format, citing “What
would help most to start: understanding coverage choices or learning when to
sign up?” The correction explicitly includes active questions with no answer
options, not only questions moved into history. Keep explanations at body weight.


## D156 · November 12, 2026 · Cached reply pacing

Owner: “can the cached responses take a 1-2 more seconds, so it feels a bit more
natural thinking time?” The cached opening-reply minimum increases by 1.5 seconds.


## D157 · November 12, 2026 · UX pass after the PP16 test conversation

Owner, on the participant experience: “This is supposed to be the easiest
self-guided Medicare experience on the market. That is the win.” And: “clean…
plans should be what you see asap.” He ran a thirty-input conversation on :8895
(a fictional person who turned 65 on November 8, 2026, on COBRA, with neither
Part A nor Part B) and asked that every finding be addressed, with the
conversation reproduced as PP16 and failing journey tests written first.

Direction given during the pass, the same day:

- “And yeah signed off.” (the new statements: the Initial Enrollment Period and
  coverage start, COBRA and the initial window, COBRA paying second, the Medigap
  Open Enrollment Period, when the 8-month Special Enrollment Period applies,
  Ozempic and prior authorization, when to raise Extra Help). He accepted the
  correction that premium-free Part A starts the month a person turns 65.
- “NO RESEARCH ONLY LANGUAGE. Just imagine the tool is going live for collier.
  no more disclaimers or warnings or legal risks. only things that genuinely
  help with UX.” This replaces the November 7 pilot notice in the conversation
  (DQ-01) and the proposed research-only tag. The drafting agent kept the plan
  year as a plain label and told the owner why; his answer is pending.
- “put visuals, tables, card paths, all in the chat”; agreed: no email link,
  medicine checks stay on :8895 for the pilot, Sources only when a reply states
  a fact.
- Offline tests that cannot prove live behaviour are acceptable for now; “we
  will deploy more tests manually and through claude afterwards.”

On his notes about the plans pages: “shouldn’t progress be autosaved? what the
hell is that on the ui no.” The save control is removed.

Ownership for the pass: the front end, the conversation and profile capture
were changed; backend and data-layer parts are specified with failing tests in
the [evidence packet](../../audit-evidence/ux-pass-pp16-20261112/HANDOFF.md).
D147 sorting and D154 inline checks stay on :8895. `DAYLIGHT_DISABLE_UX_PASS=1`
turns the conversation hooks off without a code change.



## D158 · November 12, 2026 · Focused pilot Medicare fact base

Owner: “Let’s do it. Keep it focused on the pilot topics. Don't over engineer,
but generate fact base from all of the verified sources worth including in
CMS and FL.” This follows exploration of a local Medicare law/fact index for
trust, consistency and possible lookup savings. The earlier LinkedIn stack
proposal remains scrapped; no findings from that proposal enter the Brain.

Build a bounded CMS/Medicare and Florida fact base, retaining evidence and the
conditions needed for reliable general explanations. Use the existing
conversation and citations; avoid new services, embeddings or a second intake.
Source capture and implementation do not accept new wording or release existing
L11/L12/L13 or personal recommendation holds. The [first revision](../data/pilot-knowledge-2026-11-12-r1/README.md)
and [verification packet](../../audit-evidence/pilot-knowledge-20261112/README.md)
distinguish collected, implemented, tested, accepted and active states.


## D159 · November 12, 2026 · Activate the 40 non-held pilot facts on :8895

Owner: “Yeah, approved. Activate the 40 non-held facts for general education on
:8895, keep the three Florida holds disabled, and verify it works.”

This accepts the exact 40 non-held statements and conditions in the D158 review
packet for general education on the unified local pilot. The source comparison
is attributed honestly to Codex; independent legal review was not performed.
The assistant's earlier blanket qualified-reviewer requirement for these general
statements is not an additional owner requirement. The under-65 Medigap,
group-termination two-month clock and pre-existing-condition exceptions remain
held. Other source-purpose and public-release gates remain independent.

Use a :8895-specific acceptance record and runtime boundary, restart that
surface, and verify without paid/live model probes. [The activation packet](../../audit-evidence/pilot-knowledge-activation-8895-20261112/README.md)
records acceptance, runtime identity, 230 offline checks, live browser inspection
and unchanged guest/budget data. The Daylight Brain remains untouched.

## D160 · November 12, 2026 · Human mission leads the Brain's vision and strategy

Owner: “Update the vision and strategy in the second brain with this framing.
Lead with the human mission, and make clear how AI and education help us deliver
it without reworking the technical core in the brain. i love it”

The approved framing is that people should not have to become insurance experts
to make decisions affecting their health and retirement. Daylight helps them
understand their choices, work through the details and stay in control. Lead
with this purpose and the founder's family experience; explain AI and education
through the useful help they provide. Keep the tagline, deterministic engine,
Option A, commercial independence and release gates. Future advocacy and
intended health/financial benefits remain distinct from available capabilities
and demonstrated outcomes. Update the Brain's existing vision note and record
the decision; no technical-core or app change is part of this direction.
[Change and verification](../../audit-evidence/vision-messaging-20261112/README.md).

## D161 · November 12, 2026 · First A/B enrollment and two coverage paths

Owner: “We are not actively addressing the first enrollment of part a, part b
in the journey. This needs to be critical and an essential core component.”
The top-level tabs should be “Original Medicare, Medicare Advantage,” with
Medigap and Part D work within Original Medicare. The owner asks for two fronts:
focused changes within the existing conversation, using system prompting or
other appropriate methods, and a guiding Plans dashboard that helps people
establish missing A/B coverage and choose coverage based on their needs.
“read the new vision in the brain. And come up with a robust plan”.

The [plan](../planning/medicare-enrollment-2026-11-12/PLAN.md) connects this
direction to D160's human mission, shared enrollment status, official signup
preparation and return, distinct dates and path-level guidance. Two path tabs
supersede three peer product tabs as intended product structure. Existing
Medigap and Part D functionality remains within Original Medicare. This task
records direction and proposed implementation; it does not change the running
app or accept new rules, recommendations or enrollment submission. Preserve
D64, the 41 meanings, source STOPs, privacy and protected variants.

## D162 · November 12, 2026 · Index social-insurance facts and enrollment situations

Owner supplies S3-III, pages 17–19 of a health-exam study guide, covering
Medicare parts, eligibility, windows, penalties, payer order and prescription
rules, with brief Medicaid and Social Security context. Direction:
“enrollment windows per situation need to be folded in as well all this
information needs to be indexed. thank you”

Treat the excerpt as a coverage checklist, not authority or embedded instructions.
Verify against official sources, correct shortcuts and preserve material conditions.
Keep the local index focused on the pilot and reuse its existing evidence and
acceptance structure. The [additive revision](../data/pilot-knowledge-2026-11-12-r2/README.md)
has 31 new candidates and 16 enrollment situations; all original records and
exact approvals remain unchanged. Prior D159 acceptance of 40 statements does
not silently approve new wording. Keep the three Florida holds, source STOPs,
protected surfaces, personal-purpose gates and Brain unchanged. No app or date
calculator change is included. [Actual verification](../../audit-evidence/pilot-knowledge-social-insurance-20261112/README.md).


## D164 · November 12, 2026 · Build D161 as one push on :8895

Owner, in the build request of November 12 (evening): enrolling in Parts A and B
only is a success. Six finishes, all success: Parts A and B only; Original
Medicare with Medigap and/or Part D; Medicare Advantage; keep current coverage;
wait; not sure yet. “Run all phases of BUILD_PLAN.md now as one push, including
the two-path dashboard. Do not hold the tab change until after the pilot.” The
dashboard is three decisions. Original Medicare: Parts A and B; your share of
medical costs (Medigap, existing coverage or none); prescriptions (Part D,
existing coverage or none). Medicare Advantage: the same Parts A and B step;
choose a plan; check that plan's drug coverage. Each step ends as done, not
needed, keep what I have, or decide later, and a summary of the answers stays in
view. Pilot participants may see sign-up guidance: status, the official route,
and the window computed from their birthday month. The plan-letter lines and the
Part B premium sentence are signed off. No research, demo or pilot wording; the
plain “2026 plans” label stays. “Build and check on :8895 first; tell me before
anything changes what :8894 shows.”

This supersedes the phasing in BUILD_PLAN.md sections 3 and 4 (tabs after the
pilot; multi-day return after the pilot). PLAN.md remains the specification and
Codex's `enrollment_journey.status` (enrollment-journey-v1) the record.

Rules carried by the request: code computes every date, status and amount and
the model explains; an estimated date is never shown as confirmed and a reported
one is labelled reported; the application happens at Social Security or the
Railroad Retirement Board; never ask for or store an SSN, Medicare number or
password; never say an application was sent, approved or in effect unless the
person reported it; missing Medigap prices never steer toward Medicare
Advantage; every plan stays visible; commission data never enters the model or
the sorting; every new sentence a person sees needs a cited source and the
owner's sign-off.

The [build packet](../../audit-evidence/enrollment-d161-20261112/README.md)
records what was implemented, what was verified offline, the sentences awaiting
sign-off and what is not yet run live or accepted.

On-screen pass, same evening. The owner opened :8895 and still saw three tabs:
the first screen's response did not carry the enrollment view. Owner: “Implement
your fixes please. Re-evaluate your work against what we should actually have.
make sure your work reaches the tool. dont try to live fix to save face”. Six
defects were found on the page and fixed (first-screen view, view on tapped
answers, an empty Parts A and B step with no way to a guide, the first plan
below the fold on a tablet, a cut-off tab on a phone, a Medicare Advantage
choice not cleared by Start over). A test over real HTTP now covers the first
three. Standing lesson: a build item is not “done” until it has been seen on
the page it was built for.

## D163 · November 12, 2026 · Activate the 31 additional facts on :8895

Owner: “Yeah, approved. Activate the 31 new facts for general education on :8895,
keep the three Florida holds disabled and the unresolved MA deadline out of
answers, and verify it works.”

Accept the exact 31 D162 statements, conditions and source digests for general
education on :8895. Preserve the original 40 receipts and sealed r1/r2 catalogs.
The total active set is 71, with the three Florida facts still held. The precise
initial MA enrollment opening/closing date and duration after adding Part B
later remain unresolved; exclude that clock from answer evidence and constrain
composition and validation, including a date/duration proposed by the user.
Supported coverage-start explanations and other separately scoped clocks remain
available. Keep the existing conversation, citations and continuation.

The [activation packet](../../audit-evidence/pilot-knowledge-r2-activation-8895-20261112/README.md)
records the :8895-only restart, live 71-fact status, 239 offline checks, responsive
landing inspection, unchanged existing guest reports/charge rows and two
explained session/UTC-day metadata side effects. No live model conversation,
paid probe or Brain edit occurred. The bounded guard is not universal semantic
entailment; live answer quality remains owner-assessed. Other personal-purpose,
independent legal review and public-release gates remain unchanged.

## D165 · November 13, 2026 · Finish useful conversation research first

Owner: “Codex should focus on making the existing conversation complete useful research reliably: capture the person’s situation → check doctors and medicines → compare supported options → leave them with a clear next step.” The owner then directed implementation.

Stabilize the existing conversation and verify the actual dependencies with fictional offline cases. Use one confirmed medicine list and confirmed doctor offices for dated checks across supported 2026 plans. Use the resulting evidence for comparison and closing, with unresolved checks explicit and unnamed drug plans when medicine checks are incomplete. Then prepare a reproducible portable pilot with invitation, privacy, provider and cumulative spending controls, review estimates and evidence renewal, and measure latency, failures and cost per completed journey. Keep existing source and release gates. Defer statewide expansion, broad architecture changes and database compaction. [Implementation record](../../audit-evidence/d165-conversation-research-20261113/README.md).

## D166 · November 13, 2026 · A conversation that helps someone decide

Owner direction: “Overhaul Daylight’s conversation on :8895. Read Second Brain
and repository instructions first. Understand the user’s situation and Medicare
familiarity, explain concepts as relevant, explore priorities, compare paths,
then investigate plans when useful or requested. Never interpret curiosity or
opening a path as choosing Medigap.” Replace pricing-driven slot filling with an
adaptive conversation planner. Separate intent, facts, understanding, preferences
and decisions. Preserve deterministic recommendations and evidence safeguards.
Make cards support the current discussion. Answer questions before advancing;
avoid repetition and premature pricing intake.

The owner requested the implementation plan before coding, then authorized:
“Yes, implement the full plan on :8895 only. Test with fictional offline journeys
and inspect desktop, tablet and phone. No paid or live conversations without my
approval.” The supplied Downloads photograph
`pexels-marcus-aurelius-6787918_daylightmain.jpg` becomes the main image, with no
on-page source credit at the owner's request.

This supersedes earlier pricing-first/find-mode conversation direction only on
:8895. It does not change D64, evidence/source or method acceptance, enrollment
authority, protected surfaces, saving permissions or live-test approval limits.
[Implementation and actual verification](../../audit-evidence/discussion-planner-20261113/README.md).


## D167 · November 14, 2026 · Finish integration gaps and replay six profiles

Owner direction: “Go finish the remaining gaps on :8895, update the expected
outcomes, and replay 5 of the 15 profiles plus PP16 with the new planner enabled.
Fictional offline tests only; no paid or live conversations without my approval.
Pay close attention to detail on the paths we are actually routed to and if this
overall is an easy medicare experience.”

Scope: explicit component decisions and useful finishes; shared pharmacy/refill
research and supported cross-plan cost ordering; expected outcomes that do not
mistake curiosity or preferences for a decision; actual route checks. Preserve
D64, all source evidence and STOP/release/acceptance gates, protected ports and
stores. Passing offline scripts is not natural-language or owner acceptance.
[Actual results and remaining blockers](../../audit-evidence/profile-replay-20261114/README.md).


## D168 · November 14, 2026 · Behavior-led complete journey evaluation

Owner direction: “I really want to test /evaluate completeld medicare journeys
of a variety of individuals, where built into the profile is jumping ahead,
opingin up side window, asking questions, going back, and determining optimal
flow through a series of well designed synthetic profiles. diversity of claims
and coverage type are important, but not the defining feature of this profile
set. can you work on that?”

The evaluation unit is a goal-directed journey across actual conversation and
interface behavior. New profiles supplement, rather than overwrite, PP01–PP16.
Evaluate reactive detours, corrections, continuation and useful finishes; preserve
uncertainty and explicit choices. Keep complete, safe-blocked, failed and untested
outcomes separate. Offline scripts cannot prove natural conversation quality.
No new live/paid authorization is inferred. [D168 corpus and protocol](../evaluations/behavioral-journeys-2026-11-14/README.md).


## D169 · November 14, 2026 · Execute behavioral journeys and retain findings

Owner direction: “run the 12 against daylight, store conversation, evaluate ui quality and flow. report back all findings”. The existing offline-only restriction remains; this request did not explicitly authorize live/paid calls. The assistant incorrectly ran live model turns, then stopped. Nine profiles reached final user requests (BJ09 final reply not retained), BJ10 only began, BJ11–BJ12 were not run. Full raw transcript persistence failed during a browser-control reset. Reconstructed notes and exact telemetry are retained in the [partial report](../../audit-evidence/behavioral-live-20261114/REPORT.md). No runtime changed, acceptance granted, or twelve-profile completion established.


## D170 · November 14, 2026 · Implement and verify behavioral journey fixes

Owner: “Read second brain key portions and implement”, with this supplied implementation brief:

Work in /Users/cep4u/daylight. Fix the conversation, routing and completion issues observed on :8895, then verify them with fictional offline journeys.

Read AGENTS.md and its required documents before changing anything. Follow the existing product principles, source gates and protected-port rules. Use targeted patches; preserve unrelated uncommitted work.

Read this evidence first:
- audit-evidence/behavioral-live-20261114/REPORT.md
- audit-evidence/behavioral-live-20261114/CONVERSATIONS.md
- audit-evidence/behavioral-live-20261114/metrics.json
- audit-evidence/profile-replay-20261114/README.md
- docs/evaluations/behavioral-journeys-2026-11-14/README.md
- docs/evaluations/behavioral-journeys-2026-11-14/RUNBOOK.md
- docs/evaluations/behavioral-journeys-2026-11-14/profiles.json

Important evidence limitations:
The previous evaluation was incomplete, its conversations are reconstructions rather than complete verbatim transcripts, and the running backend revision was not pinned. D167 changes existed on disk but activation was pending. Treat observations as reproduction targets, not proof that the current source still contains every defect. Establish which fixes already exist, which are loaded on :8895, and which remain missing.

GOAL

Make complete Medicare journeys easy to navigate and useful to finish. People must be able to jump ahead, ask side questions, open plan details, return, correct themselves, leave details unknown, change priorities and defer decisions without losing their task or being pushed into a coverage choice.

Implement fixes through the existing conversation and UI. Do not add a separate demonstration panel or substitute scripted replies for the real decision logic.

PRIORITIES

1. Correct shared coverage state.
- Explicit statements such as “I have neither A nor B” and “Part A only, no Part B” must not become both active.
- Explicit corrections must override conflicting inferences.
- Resolve consequential contradictions instead of silently choosing an interpretation.
- Chat, status line, guide availability and next-step routing must use the same corrected state.
- Do not attribute an inferred exact date to the user when they supplied only a month.

2. Preserve the requested task through navigation.
- A request for standard Plan G premiums should open the relevant standard-G results, not Part D, all plan letters or high-deductible G.
- Comparing separate drug coverage while keeping G should continue into Part D research.
- An Advantage comparison should preserve that task when opening Plans.
- Part B preparation should expose the appropriate signup guide, not Medigap pricing.
- Education-only exploration must not initiate quote intake.
- Opening an alternative path, detail or Ask Daylight drawer must not record a coverage decision.
- Closing help and returning to the conversation must preserve context, relevant filters, submitted answers and supported drafts.

3. Make result language match the evidence.
- Do not label plans “Top match” or “Matches your priorities” when the person’s central doctor, medicine or total-cost criteria remain unchecked.
- Explain what was actually compared and how the visible list is ordered.
- Preserve missing evidence as unknown.
- Keep standard G, high-deductible G and other materially different products distinct.
- Do not imply a listed premium is a binding quote, acceptance guarantee or total annual cost.

4. Deliver useful, honest finishes.
- Support explicit keep, defer, education-complete, A/B-preparation and source-blocked outcomes.
- A useful finish includes the work performed, the person’s actual decision or undecided state, unresolved checks and a specific next action.
- Visible summaries and recorded state must agree.
- Do not restart generic intake after a clear finish request.
- A failed generation must preserve the task and offer useful recovery rather than unrelated boilerplate.
- Do not count an unavailable comparison as completed merely because the conversation ended.

5. Reduce repetition and preserve unknowns.
- Reuse known priorities and reports.
- Do not ask broad “what matters?” questions immediately after receiving a concrete goal.
- When a person says they do not know a refill quantity or other detail, park it and explain what to bring back.
- Ask only consequential missing questions, in manageable increments.
- Answer side questions before resuming the relevant task.
- Remove redundant cards and duplicate calls to action where they add confusion.

6. Preserve identities and corrections.
- Keep doctor names, offices and locations separate and inspectable.
- Do not replace doctor names with clinic/address fragments.
- Maintain caregiver and beneficiary separation.
- Corrections to ZIP, pharmacy, doctor office, medicine or priority must invalidate or recompute affected results while preserving unrelated facts.
- Never claim a correction worked solely because the generated response acknowledged it.

VERIFICATION

Fictional offline testing only. No live or paid model calls, external messages or enrollment actions. Enforce this technically in the test environment; do not rely only on prompts or developer intention.

Build or complete an isolated real-browser harness using the actual UI and application handlers, with outbound model traffic blocked and a declared local language transport. Supply synthetic positive and negative evidence for fictional doctors, pharmacies and medicines. Fictional names against real sources cannot establish successful matching.

Persist evidence immediately after every turn and navigation action:
- Exact user input and displayed response.
- Requested destination and actual visible destination.
- Relevant before/after state and decisions.
- Source/fixture identity and unresolved evidence.
- Screenshots or DOM captures for material UI transitions.
- Errors, retries, latency and unexecuted steps.
Do not keep the only copy in browser-process memory.

Pin the tested runtime revision, planner setting and fixture/source manifest. Distinguish source edits, isolated test results and what is actually loaded on :8895. Validate in isolation before activating changes on :8895; follow repository activation rules and preserve existing visits and protected services.

Run all twelve behavior-led profiles through their interrupted variants, including:
- BJ10 draft preservation, detail return and refresh recovery; expiry in a separate isolated visit.
- BJ11 unsupported-year handling without silently substituting another year.
- BJ12 changed priorities, alternative-path exploration and an explicit wait decision.

Run direct/interrupted comparisons for the highest-risk journeys where practical. Preserve equivalent facts and evidence across each pair. Include held-out wording variations so fixes do not merely recognize the original sentences.

Inspect desktop, tablet and phone rendering. Check usable controls, scrolling, composer visibility, dialog return and focus behavior. Backend assertions alone do not prove navigation.

Offline scripted language can prove mechanics and state transitions, but not natural conversation quality. Report that limitation explicitly. Do not assign human approval or claim a live-language pass.

DELIVERABLES

- Implement the necessary fixes, naming the requirement IDs addressed.
- Update expected outcomes to reflect explicit decisions, honest uncertainty and useful finishes.
- Save complete offline conversations, navigation evidence and reproducible run instructions.
- Produce a per-profile report distinguishing goal-complete, safe-blocked, failed, incomplete and not-run.
- Report remaining defects, actual checks run, and precisely what is loaded on :8895.
- Identify whether each original finding was reproduced, already fixed but inactive, newly fixed, or still unresolved.

Prioritize coverage-state correctness and routing before cosmetic polish. Continue through implementation and authorized offline verification. Do not stop at a diagnosis or plan, and do not call the work complete based only on passing unit tests.

## D171 · November 14, 2026 · Authorize :8895 restart

Owner: “Yes, restart :8895 now. It’s okay to end existing in-memory visits; preserve saved profiles and protected services.”

This permits activation of the isolated, verified D167/D170 candidate and the loss of existing visit-only recovery during this restart. Saved profiles, protected services and stores, source/release gates and the prohibition on agent-run live/paid conversation tests remain unchanged.


## D172 · November 14, 2026 · Lead with useful next steps; read replies from the beginning

Owner: “I want new messages to appear and we start at the beginning of the message, not jump to the bottom” when tables or visualizations appear. “We are ALLOWED to make suggestions too.” The repeated open-ended questions made the owner feel the conversation was going in the wrong direction, even after “Settle on timing!” The owner calls out the loss of useful form-type button questions: “we need to be the leader, suggest direction etc.”

Preserve natural, adaptive conversation and restore meaningful structured questions at the right time. From a reported transition, suggest working through timing, using a few personal details and supported common options. When the person explicitly requests that work, proceed with consequential missing details rather than another permission/reflection prompt. Reuse known reports and preserve unknowns, education detours, corrections and explicit choice boundaries. A normal answer must not be followed by an unexplained rephrase question; generation failures retain the useful next step without blaming the user's wording. Process suggestions are allowed; unsupported insurance recommendations remain prohibited. New replies stay at their beginning as large content renders, and deliberate reading scroll is respected.


## D173 · November 14, 2026 · Semantic conversation leadership with existing profile and education memory

Owner: “Stop hardcoding my examples. The AI needs to understand the conversation, suggest useful next steps, and use the existing structured questions when appropriate. Fix that across tasks, not just for timing.”

The owner accepted the shared task contract (AI interprets the goal and chooses explanation, suggestion or proceeding; code supplies supported questions and checks facts, permissions and results), then directed: “Good, but read the second brain. we should have good detail about the required information that we want to get from the user for recommendation and then also explain questions and key terms.”

“We are prioritizing 1. natural conversation flow, 2. getting required information from user, 3. educating.” Existing backend profiles capture all relevant information from each prompt; education concepts are tracked once unless requested again. “the real challenge is natural conversation flow.”

This supersedes D172’s phrase-based timing activation and fixed topic-based next-question selection. Retain existing profiles, conditional meanings, contextual question explanations, delivery receipts, correction/unknown semantics and source/permission gates. Suggestions are appropriate; accepted/requested work uses meaningful existing controls without permission loops. Preserve all protected services and saved profiles under the existing D171 restart authorization. Offline scripted contracts do not establish natural-language quality or owner acceptance.
