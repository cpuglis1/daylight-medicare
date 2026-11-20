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


## D174 · November 14, 2026 · Implement natural progression with bounded inference and exact plumbing

The owner supplied a conversation that answered concepts but repeatedly closed with “What would you like to understand next?” and then turned confused “A+B+C” wording into a forced path-clarification question. The requested progression offers useful personal preparation or uses the appropriate existing questions, while leaving room to learn. Correct terms without making an unneeded choice block common preparation.

Owner: “Yes, but how are we going to implement this so that it works? inference times are just increasing as we add more rules. Give it your best shot and then return a diagram of the entire plumbing infrastructure around the conversation in full detail of exact prompts and loops etc”.

Implement the proposed Brain-aligned repair across tasks, preserving the priorities of natural flow, required information and education. Consolidate contradictory instructions instead of stacking more rules or model stages. Preserve report extraction, subject/scope distinctions, unknowns, conditional questions and concept delivery records. Make useful offers and structured next steps survive checking; avoid duplicate lesson cards and generic continuation loops. Record actual payload, timing, question-selection and bounded retry evidence without raw transcripts. Supply the exact prompts, schemas, context and complete pipeline diagram. D171's :8895 restart authorization persists; saved profiles and protected services must be preserved. No agent-run live/paid conversation tests or consumer/source acceptance is authorized.


## D175 · November 14, 2026 · Quiet validator recovery without new model calls

The owner reported a valid preference answer followed by an unrelated Medicare definition and “I couldn’t finish that answer,” then asked why the validator exists. Owner: “Oh, well if that happens, is there a way to hide that without announcing it as an error for now? We can still block it, and do our best as well?”

“But yes, implement the proposed fix. Fix the validator and recovery across tasks without hardcoding these examples or adding model calls, then test and restart :8895.”

Fix false rejection of uncertainty/embedded questions while preserving factual checks. Retain independently supported whole response blocks and approved questions locally. If an accepted report can continue with a useful question, recover quietly using its existing explanation instead of an unrelated lesson/error notice. A substantively unanswered request must remain visible; quiet recovery does not grant eligibility, recommendation, source acceptance or successful-check authority. Record only delivered education. Preserve saved profiles and protected services; the owner explicitly permits ending :8895 in-memory visits. No live/paid conversation probes.


## D176 · November 15, 2026 · Profile-backed question progress

Owner: “it was working, but it then got stuck repeating one question. it knew that it was already asked, but we need the system that tracks the profile and is linked to the questions that we need to ask v. what we should not ask about, but besides the hiccup, I thought the conversation was flowing well.”

The supplied example repeated a compound end-date question after both dates were given and again after prose acknowledged the repetition. Diagnose capture and question selection together. Existing profiles remain factual authority; a model acknowledgment is not a stored report. Fix general question eligibility, partial fields, unknowns/deferrals, correction and repeat handling across tasks rather than recognizing this conversation. Preserve supplied date precision, natural flow and education receipts. Keep unresolved questions visibly open without forcing the same ask; support later answers and explicit editing. Offline-only verification and existing :8895 restart authorization remain; saved profiles, protected services and source/release gates remain unchanged.

## D177 · November 15, 2026 · Responsive recovery and unfinished request continuity

Owner: “I thought we said never to return messages like this: ‘Part of your question is still unresolved.’ like why bother returning that to the user when the rest is reasonable. Block if we have to, but leave as un-resolved and try to work it in later in an appropriate message.” The owner also reported “We can continue with the next detail” after a current-job answer and said the prompts were not as responsive.

Keep useful validated prose and an appropriate structured question without generic internal-status commentary. Preserve unfinished requests in bounded visit-only context so a later relevant response can address them; a blocked draft cannot establish delivery. Restore the loaded question catalog’s explanation where recovery needs it. Diagnose the worker-relationship rejection without weakening actual report requirements. No extra model stage or fixed example-specific conversation branch. This supersedes D175’s generic unanswered/partial notice requirement, not factual/source/action limitations or provider-failure handling. Existing :8895 restart authorization and all saved-profile/protected-service safeguards remain; no live/paid conversation tests.

## D178 · November 15, 2026 · Real backend waiting progress

Owner: “Yes, implement this on :8895. Real backend progress, no extra model calls. Test it on desktop, tablet and phone, then restart. Preserve saved profiles and protected services.”

The accepted proposal acknowledges server acceptance, names an actual doctor/medicine/plan lookup only while it executes, and reports reply preparation when composition starts. Add reassurance around 12 seconds and an honest longer-wait message around 30 seconds; these are experimental display thresholds, not performance promises. Keep one legible accessible status with reduced-motion support. No rotating tips, fake percent bar, generated acknowledgment or unvalidated answer stream. Deliver the validated reply immediately and keep its beginning visible. Status transport failure must not imply continuing backend activity. Preserve existing model stages, retry limits, profiles and protected services; use fictional offline tests only. Existing authorization permits ending :8895 in-memory visits during restart.

## D179 · November 15, 2026 · Profile progress, confirmed details and a useful close

Owner: “remove these warnings” about the standing Part A/Part B status and Social Security instruction, “or anything at the top.” “I liked the old status bar we had before, it was just broken. can we add a very simple status bar that is more or less the % of completed profile? we don't need to say that exactly, but again just a trick. can you give it a go.” The owner reports redundant doctor details after confirmation and the same problem with prescriptions.

Owner: “we should have an end note, when we get there, summarize what we learned, and what the next steps are. make it abundantly clear how we plan to proceed” and “like guide through the plan options step by step with the window open, like lets help them navigate the tool. maybe that guiding we just close with steps for now”. “Can you try and see if we can come up with a plan to address each of these.” “I feel lke the ending on a summary, next steps, and help with them to proceed with a recommendation based on the plans needs to become a core component. That ending needs to be integrated into second brain IMO”.

Record the core closing and requested UX direction in the Brain; provide an implementation proposal. Distinguish identity reuse, repeated result presentation and genuine missing-details questions. Use actual profile progress without claiming verification, enrollment or recommended-plan completion. A guided next research step is not a personal fit finding: deterministic recommendation authority, relevant evidence and explicit choice remain separate. No new model stage or phrase-specific routing. The present deliverable is planning and documentation; application fixes, responsive verification and activation remain pending.

## D180 · November 15, 2026 · Implement profile progress, reuse, closing and guided Plans

Owner: “Yes, implement all four on :8895 without hardcoding my example or adding model calls. Test the full conversation and Plans handoff on desktop, tablet and phone, then restart. Preserve saved profiles and protected services.”

This authorizes implementation and activation of D179. Reuse the existing profile criteria, exact doctor/office and medicine selections, summaries and reviewed handoff. Show real preparation progress, compact unchanged results, provide an automatic useful closing and follow the actual open Plans step in the same visit. No model stage, phrase trigger, commercial influence or source/recommendation acceptance is added. Use fictional offline transports; no live/paid agent-run conversation. Preserve the saved database and protected :8890/:8891/:8896 services and stores. [Evidence](../../audit-evidence/guided-plan-close-20261115/README.md).

## D183 · November 17, 2026 · The profile and education records drive the conversation

Owner: "I agree with your recommended additions for the profile and the same for the proposed education record. … So all of that needs to be integrated into a single prompt. Like implement this profile education records plan as the priority, but keep in mind the additional 6 recommendations. As for my calls, approve the 2 records. Yep, approved. Profile additions, approved. Concept map, approved. … approve, approve." Then: "On a new branch off of dev, give this implementation a shot and report back."

Daylight keeps two records that fill as the conversation goes: the profile (what Daylight has learned) and the education record (what Daylight has explained). Every turn reads both, so nothing is asked or explained twice and explanations match the person's level. The profile holds everything a recommendation, the next enrollment step and Before you enroll need; not every field needs an answer. The interpreter chooses the next question from every open profile field using the readiness views; code validates, computes dates and records what was shown. Code computes the sign-up window when job coverage ends (C46). Fixes work for everyone, never for one case. Spec: [PROFILE_AND_EDUCATION_RECORDS.md](../product/PROFILE_AND_EDUCATION_RECORDS.md).

Same day, second pass. Owner: "But build out what you didn't build and evaluate what you did against the implementation prompt and ensure that you did this correctly. Then copy the 24 change files into your working copy so I can restart 8895 and try it."


## D184 · November 18, 2026 · One-command local Daylight launch

Owner: “ONe command, checks what up, starts if off if required. refreshes daylight +launch all in one”

Use the existing :8895 restart launcher for a cold launch and after edits. Start the existing local PostgreSQL cluster when needed. Verify that the UI and API respond before opening a fresh browser page. Preserve saved profiles, the bound database, protected services and existing gates. [Runbook](../../audit-evidence/unified-demo-8895-20261112/README.md#start-and-use).

## D185 · November 18, 2026 · Hosted demo and online spending limits

Owner requested the small AWS plan on daylightmedicare.com, deployment access, abuse checks, “maybe cap to $2 dollars per session, cap to $20 of online use before shutting down messaging outright” and a demo-only disclaimer. These figures are initial demo settings. [Implementation, release sequence and open account work](../../infrastructure/daylight-pilot/DOMAIN_LAUNCH.md).

## D186 · November 18, 2026 · Namecheap, hosting costs and chat history

Owner confirms Namecheap domain ownership, approves the discussed hosting estimate and accepts a malicious user exhausting the $20 model allowance. Owner requests all chat histories be stored for the hosted pilot. Implement a durable archive of submitted messages and delivered replies/cards/actions with permission, encryption, controlled review, version attribution and deletion. Retention duration is still proposed. The earlier account-specific Virginia policy exception is approved and pending execution. [Plan](../../infrastructure/daylight-pilot/DOMAIN_LAUNCH.md).

## D187 · November 18, 2026 · Reusable demo link, provider cap and Sol 6.1

Owner approves the enforced OpenAI project hard limit and the reusable accelerator demo link, and requests the API return to Sol 6.1 with low reasoning because 6.2 is buggy. Implement GPT-6.1 Sol with low reasoning for interpretation and composition. Reusable links create isolated reviewer visits and retain expiry/revocation and aggregate accounting. OpenAI cap is monthly and may slightly overshoot during enforcement propagation; Daylight retains its cumulative cap. Provider configuration and link implementation remain pending.


## D188 · November 18, 2026 · Pending questions, passes, single-field targets and offers

Owner, after a :8895 conversation asked for the job and insurance end dates twice (visit `12b0f11de2`): "Yes, write me the prompt and update the spec." Approved: (1) a delivered question is marked pending, the interpreter says what the reply did with it, and after a detour Daylight answers and returns to the same question in that reply, with no offer button; (2) a question is parked after two passes, not after being shown twice, which is the November 13 decision as written; (3) a question asks for one value at a time when its fields are the same kind, and a direct answer fills that field; (4) offers are recorded as shown and as taken and are not repeated. Not approved: a change for a turn where the claim check cuts the answer to the person's own question, and the proposed cap of four deliveries. :8895 only, behind `DAYLIGHT_PENDING`. The Brain's prompt named this "D186 or the next free number"; D186 and D187 went to other decisions the same day. Spec: `docs/product/PROFILE_AND_EDUCATION_RECORDS.md`. Evidence: `audit-evidence/pending-questions-20261118/README.md`.

## D189 · November 18, 2026 · Plan checks that state their true cause, and the chat on the Plans pages

Owner, after visit `130911a983` on :8895: the check marks on the paths overview and on each plan said "Not checked" with reasons that blamed details the person had given; the chat beside the Plans pages opened on step instructions; and a typed message there failed with "Unsupported profile field." Approved, with these calls made: do not build a total yearly cost method, show it as not calculated yet; leave the meaning of a path-level "Meets" unchanged and list it as an open question; the Plans chat opens with "Any questions about these plans?", and that line and every changed reason sentence go on the owner sign-off list. Three fixes on :8895 behind `DAYLIGHT_PLANS_FIXES`: every check states one cause decided by code (`needs_person`, `no_data`, `not_calculated`), per side and from the same check results the conversation holds; the Plans chat opens on the one line; messages from it always send and can compare the plans a person selected, reporting differences and never ranking. No new scoring, no edit to chat-first or the sealed contract. Evidence: `audit-evidence/plans-checks-and-chat-20261118/README.md`.

## D190 · November 18, 2026 · Five conversation fixes from the owner's live run

Owner, after running visit `a912962310` on :8895 and reading an assessment of five failures: "Build all five." The failures: "I'm turning 65 next month" was never saved and the age was asked twice; "Local only, but yes i just checked its creditable" was saved but answered with "I don’t have a reliable answer to that yet."; "what plans do you recommend for me" was answered with a request for a Medigap price detail; the "Review your info" button showed under an open question; and the bold question disappeared while a reply was on its way. In the same run the owner asked for the Medigap "Add to compare" buttons to work as they do for Medicare Advantage, and for step 2 not to show a plan the person had not chosen. :8895 only, behind `DAYLIGHT_CONVERSATION_FIXES`. Evidence: `audit-evidence/conversation-fixes-20261118/README.md`.

## D191 · November 18, 2026 · Strict AWS spending authorization

Owner: “okay that pricing is FINE. if you charge more than that for other costs I need to know. Those are the only approved costs that I approve for NOW. Seriously, I am highly concerned about an ai accidently charging me more”. The preceding quote was $72.27/month foundation baseline plus a $30 allowance ($102.27/month estimate at 730 hours), separate from the $20 cumulative AI allowance. Only that presented configuration and estimate are approved. Do not add a paid service, upgrade or expand cost without first disclosing its price and obtaining explicit owner approval. Supersedes the broader D186 $75–$150 range for future work. Finish read-only verification of the foundation already started, then stop provisioning. AWS metered usage and tax are not hard-capped by the estimate; do not claim otherwise. [Execution record](../../infrastructure/daylight-pilot/STEP_2_FOUNDATION.md).

## D192 · November 18, 2026 · CloudFront Pro investigation

Owner: “fixed costs are OK. surprise costs are not” and then “lets look into the $15/month pro plan.” Investigate the plan's compatibility, required origin changes, cost breakdown and uncovered usage risks for Daylight. This is research authorization, not approval to subscribe, expose an origin or increase spending. D191 remains binding. [Feasibility review](../../infrastructure/daylight-pilot/CLOUDFRONT_PRO_REVIEW.md).

## D193 · November 18, 2026 · Continue Pro implementation

Owner: “okay continue!” following the Pro recommendation and the ~$54.42/month baseline plus $7 origin-certificate issuance/renewal disclosure. Continue implementation of that described design, preserving storage, invitation controls and test/pilot separation. D191 remains in force for undisclosed paid additions or scope expansion. This does not authorize automatic upgrades or waive launch/privacy/source gates. [Prepared migration and verification status](../../infrastructure/daylight-pilot/STEP_3_PRO_PREPARATION.md).

D193 execution confirmation, same evening: owner answered “yes.” to the concrete request to remove NAT and reuse its IP on the host while keeping all inbound access blocked. Both stages completed and were verified at 6:54 p.m. Eastern; this does not authorize public ingress or additional paid scope. [Execution](../../infrastructure/daylight-pilot/STEP_3_NETWORK_EXECUTION.md).

## D194 · November 18, 2026 · CloudFront Pro, HTTPS and protected app deployment

Owner: “great. go on: Next: CloudFront Pro, HTTPS/domain setup, and deployment of the protected app.” This follows the reiterated ~$54.42/month hosting baseline plus $7 origin certificate issuance/renewal, separate $20 AI allowance, usage and tax. Continue that implementation. D191 still requires disclosure and approval of other paid additions. Preserve all invitation, history, model-budget and release conditions. [Execution status](../../infrastructure/daylight-pilot/STEP_4_TLS_PREPARATION.md).

D194 execution continuation, same evening: owner said “yes. go it. i signed in. go on pro and make app live if you can” after the temporary setup allowance disclosure. Added and publicly verified three certificate-validation CNAMEs, preserving mail. Both certificates issued; the $15 Pro subscription became ACTIVE at 7:16 p.m. Eastern. The disabled distribution and block-all firewall are deployed, with origin ingress closed. Server prerequisites are installed and the private rehearsal archive staged. A preview grants the existing host read access to one exact archive and its origin certificate only; that specific IAM expansion still awaits action-time confirmation required by browser-control policy. No live app, API key or participant access is claimed. [Execution and scope](../../infrastructure/daylight-pilot/STEP_4_TLS_PREPARATION.md).

D194 permission execution, same evening: owner replied “yeah confirm.” to the exact existing-server read scope. Applied that one-role update and verified the full template/policy. Installed the private archive and origin TLS directly on the host, pinned the sealed Python/dependency versions, and restored the held display database on its encrypted disk. Full eight-table CSG row parity, three PDP payloads, runtime/code bindings, reader privileges and Linux imports passed. No paid model call or public exposure. The fresh Mac-source reconciliation attempt was blocked by local socket permissions; a read-only owner-run helper was prepared. [Private installation evidence](../../infrastructure/daylight-pilot/STEP_5_PRIVATE_INSTALL.md).

D194 hosted-integration continuation, same evening: owner requested “Hosted chat/history integration and final launch checks remain.” The passing owner-run source receipt clears the local-socket blocker. Implemented consented PostgreSQL history, reusable isolated visits, shared-ledger support and explicit GPT-6.1 Sol/low hosted wiring, preserving recommendation/source holds and protected local services. Twenty-nine local checks and eight private PostgreSQL checks passed; no paid model call or public exposure. The revised serving runtime, provider configuration, scheduled retention/backup operations and edge admission checks remain open. [Implementation and exact limits](../../audit-evidence/hosted-history-20261118/README.md).


## D195 · November 18, 2026 · Ninety-day accelerator access

Owner: “yes, can you do 90 day access, thanks”, in response to the proposal to retain the 20-visit limit and $20 total AI cap. Extend the existing accelerator invitation to 90 days, preserving consumed visits and cumulative spending; a replacement signed URL is required. Test invitation duration and data retention are unchanged. No new service or tier authorized.


## D196 · November 18, 2026 · Owner test access after deletion

Owner asks for a master test link that permits clearing chats without losing access, and says “dont do that for the accel link”. Keep the accelerator invitation unchanged. Use separate owner-only test access while preserving cumulative spending. Existing saved-history deletion closes only the current visit; owner can reopen the reusable link for a fresh visit.


## D197 · November 18, 2026 · Reliable invitation links

Owner reports the accelerator/test invitation Continue is blocked or sticky, a new tab shows “A pilot invitation is required”, and asks to make links work seamlessly. Fix invitation navigation and recovery without removing access gates or spending controls. D196 excludes automatic accelerator reset; owner-only test reentry remains separate.


## D198 · November 18, 2026 · Stop unchanged timing-card repetition

Owner supplied the hosted enrollment conversation showing the same timing panel three times and directed: “same panel returned 3x. fix.” Correct delivery memory and revisit scope so enrollment-process follow-ups do not automatically repeat unchanged date results. Preserve the first result, meaningful corrections, explicit requested redisplay, conversation history and factual/permission/spending safeguards.

## D199 · November 19, 2026 · Hosted demo gets the :8895 wiring

Owner asked for an evaluation of how much of the local :8895 backend reached the AWS deployment, then approved the three-phase wiring plan: “Everything is approved, go on phase 1-3.” Phase 1 matches :8895 without changing holds (page switches, Plans and sign-up routes, per-visit concurrency, D163 hold, latency settings, price review). Phase 2 extends the 71 accepted general-education facts to the hosted invited demo and shows checked reply blocks only after they are saved to the visit history. Phase 3 shows Medicare Advantage values under the existing local review label, installs D147 evaluation-only sorting and the D165 doctor/medicine checks for the invited fictional demo. Invitation links, spending limits, model, history consent, participant/consumer release and source gates are unchanged.

D199 execution authorization: the owner subsequently asked the agent to use the screen to deploy the approved fixes and explicitly approved marginal storage for 1–2 GB. This does not authorize an instance upgrade, new service subscription or materially higher hosting costs. Deployment review found and corrected the service memory cap and foundation directory traversal, and added a guard against enabling two large indexes. The server’s new-artifact read permission is a separate action-time browser confirmation; preparation and read-only checks can proceed.

D199 execution completed November19 after the owner explicitly approved the temporary four-file read grant. Test then pilot activation succeeded, final read-only host checks passed, and the grant was removed. Main alone runs the large doctor/drug reader; both sites run D199. Existing server/disk allocation, model, spending limits, links and real-health/source holds remain. See D199 execution evidence.

## D200 · November 19, 2026 · Demo conversation stays open; fresh starts for invited visitors

Owner reviewed two hosted demo conversations and asked for three fixes (“Yes, fix all three”): (1) an answer such as “Ends Dec 2026” was refused as a Medicare number; (2) “Slow down, we are going too fast, why do you need that information?” ended the conversation with a summary instead of answering why and continuing with choices about what the person is comfortable doing or wants to know; (3) people using the accelerator link should be able to restart up to five times. The near-miss Medicare-number rule now requires a digit in each group. The interpreter’s pause stays semantic (D173), but words about pace or purpose without a stop request are treated as a detour: Daylight explains why the open question matters, keeps the visit open and offers text-labeled choices (skip this question, options first, more simply, stop for today). A real stop’s summary names the Social Security step when Part A or B is not in effect or not confirmed. A shared-invitation visitor may start a fresh visit five times from Saved chat; each fresh start clears that saved chat, closes the visit, and does not use one of the link’s 20 visits. Per-visit $2 and cumulative $20 limits, the model and invitation links are unchanged.

D200 execution, November 19: owner approved the temporary read grant and test-only deployment (“oh okay, yes proceed with the paln”). Test now runs `3698e69e9842…`; main remains D199 `99b371765611…` pending explicit promotion approval. Exact host hashes/processes, model/caps, history isolation and public HTTPS checks passed without model calls or invitation redemption. The four-object grant was removed and absence confirmed. No hosting tier or disk allocation change. [Execution evidence](../../audit-evidence/demo-review-d200-20261119/aws-test-deployment-20261119.md).

## D201 · November 19, 2026 · Prioritize the next useful decision

Owner says the hosted conversation works but is still slow and the sequence moves too quickly into fine details: “can we fix/prioritize the most critical questions when the model is selecting next question?” The supplied first-enrollment conversation moved from job coverage/end date/employer size to a compound creditable-drug-notice/gap question, and repeated it after confusion. Prioritize what changes the next useful answer or action, explain the payoff of known answers, and distinguish broad orientation from conditional checks protecting specific conclusions. Confusion calls for a plain-language explanation, not presumed comprehension. Preserve semantic selection (no fixed script), all source/factual and enrollment safeguards, model/caps, saved data and protected variants. Read-only investigation confirms the hosted local-bound token preflight, checked-block release and 20-word/second reveal; no measured latency claim. Local first pass and offline checks are recorded in [D201 evidence](../../audit-evidence/question-priority-d201-20261119/README.md); hosted deployment and owner acceptance remain open.

## D202 · November 19, 2026 · Core questions first, model-selected tiers

Owner: “We should rank questions … tier 1 … location, doctor, prescrip, priorities, current coverage, what they are hoping to accomplish today … questions like [employer size and creditable drug coverage] should be second tier … model prioritize tier 1 unless we go through all tier 1 or a question by the user specifically routes to it … if I don't have Medicare, we need to ask if they know how to enroll … THIS SHOULD NOT BE IF ELSE, but desired behavior.”

Supersedes D201's broad timing-first selection guidance with explicit question-tier metadata and shared model guidance. Existing approved core profile meanings are Tier 1; conditional/optional meanings are Tier 2, with checks-owned and system meanings excluded from general intake. Core questions remain visible in the bounded candidate menu; pending and interpreter-selected meanings remain available. The model selects the next useful question and may prioritize a conditional detail for the person's specifically requested work. A broad timing/options concern does not alone justify a sequence of conditional checks. Unknown/deferred/parked answers remain addressed, not verified. Establish enrollment understanding conversationally, using the existing learner/history context and supported guides; teaching delivery is not proof of comprehension. Do not add a fixed branch, a new intake field, a model stage, or relax any dependent personal conclusion. A delivered conceptual clarification needs no additional automatic work button. Existing pending-question continuity, safeguards and explicit overrides remain.

Local source change and fictional offline controller verification only. Hosted test stays D200; main stays D199. No paid model calls or infrastructure changes. Runtime activation and actual model/UI quality remain separate checks. [Evidence](../../audit-evidence/question-tiers-d202-20261119/README.md).

## D203 · November 19, 2026 · Introduce guides within the conversation

Owner reports that the flow is directionally right but asks for a little more explanation when showing a guide. The example jumps from an A/B-status question into “Confirm with Social Security,” work-coverage rules, contact information, a phone-guide link and call-status controls, then returns to the A/B question.

The existing composer now chooses whether a prepared sign-up guide is useful now through its visual selection. When selected, it receives the actual guide title/route/options plus guidance for two or three short conversational sentences: connect the person's concern to the purpose of the guide, describe what it helps them do, and connect the next question to the remaining uncertainty. Frame it as available help, not an immediate instruction to call or leave Daylight. Unknown Medicare status is not proof an application is needed. Keep detailed rules and contact details in the existing source-backed card. If not selected, continue the conversation without announcing the guide. This is semantic model guidance, not canned introductory text. A deferred guide retains its eligibility to be shown later; only actual display consumes the receipt. All existing facts, source holds, guide contents, Tier 1 selection, model and spending limits remain. Local source and offline checks only; no hosted deployment. [Evidence](../../audit-evidence/guide-introduction-d203-20261119/README.md).

## D204 · November 19, 2026 · Visible content and one next action

Owner requests removing “Your earlier summary and next steps,” “Your doctor check,” “Your medicine check” and all non-source arrow-to-expand sections, explicitly preserving doctor selection dropdowns. Preserve their useful information as visible content. Owner also reports simultaneous “Compare my options”/“Review my coverage” and “Review your info” buttons and requests one coherent action. The existing review checkpoint takes precedence over a generic work offer; superseded offers stop being active. With a valid handoff, show only the existing See plans action; otherwise show Review your info. Preserve review/consent/source gates and editable answers.

For someone with Medicare considering switching, establish whether anything is not working about their current plan and what they want to keep. Reuse an already stated reason. Being curious about switching does not establish dissatisfaction or justify a recommendation to switch. Add semantic model guidance using existing concerns/history and approved goal/priority reports, not a fixed branch, new mandatory question or model stage.

D203 guide introduction remains included. Local :8894 assets/:8895 conversation source only; no AWS deployment. Fictional offline checks verify content retention, selection controls, source disclosures, action uniqueness and existing controller behavior. Local preview-server binding was denied; the browser's URL policy rejected the local-file preview and prohibits a workaround. Responsive visual quality and real model wording remain unverified. [Evidence](../../audit-evidence/visible-content-d204-20261119/README.md).

## D205 · November 19, 2026 · One delivered continuation using both records

Owner: “I dont want to hardcode responses … encourage those priorities, while referencing both the key user profile and education profile … Give that a shot without undoing a lot of the good work we have done.” Approved strategy: represent the next move explicitly, separate continuation from teaching deduplication, validate final delivery and test whole scripted journeys.

Keep the code-owned profile reports, education delivery/depth and tentative learner signals as shared model context. Teaching delivered does not prove understanding. Preserve Tier 1 preferences, consequential conditional checks, guide introduction, visible information, doctor selection, one review/handoff action and current safeguards. The model chooses language and useful work; no Medicare-case branching or canned response is added. Code owns continuation delivery after filtering, checks and closing, and the UI uses that same decision. Conversation memory must reflect actual delivery. Replay/source-withdrawal checks cannot consume question, offer or teaching receipts. Use fictional scripted transport only; no extra provider call, paid probe, new model, budget or hosting change. Protected variants/stores remain unchanged. Local activation, responsive rendering and real model quality are separate from offline verification. [Evidence](../../audit-evidence/delivered-continuation-d205-20261119/README.md).

## D206 · November 19, 2026 · Hosted refresh and accelerator-only speed/reset allowance

Owner approves deploying the current :8895 source to owner/test and accelerator/main while preserving the exact existing invitation URLs. Accelerator only: gpt-6.1-sol Ultrafast service tier, low reasoning, four in-visit fresh starts, and $5 across the original session and its reset descendants. Owner remains standard/low, $2 per visit, $20 link sublimit, existing reentry and five in-visit resets. Both use the existing shared ledger with a $35 cumulative ceiling, including all existing charges and outstanding reservations. No hosting-size or fixed-cost upgrade. Ultrafast rates are reserved at 6× standard; unknown receipts retain holds and fail closed. No paid probes. Existing source/recommendation/privacy restrictions remain. Deploy test then main, verify readiness and invite identity, automatic rollback on readiness failure. Exact Techstars URL, expiration and 20 admissions stay unchanged. D206 is approved for deployment after validation; live completion must be recorded separately.

Offline validation: 98 application tests and four deploy tests pass. The four initially failing legacy assertions were reconciled to the existing friendly invitation redirect and current model-rate/ambiguous-attribution behavior; authenticated/API guards remain asserted. 491 reconstructed release hashes match. Evidence: `audit-evidence/hosted-refresh-d206-20261119/`.

D206 execution: deployed release `01d005129ae9a9942b64cafa4ca404cf0c7420e88cadd19dfeeb7df1bbb2db75` to both services. Both passed readiness, invite-identity, 491-file integrity and public HTTPS/access checks. OpenAI project limit changed to $35 with enforcement enabled; early $20 alert retained. Shared ledger has $1.981591 accounted spend, no holds/block. No paid probe or invitation redemption, no hosting/IAM/credential changes. See D206 evidence for SSM command IDs and remaining verification limits.

## D207 · November 20, 2026 · Report-driven hosted selectors and accelerator allowance reset

Owner reports missing doctor and medicine/strength choices on the AWS accelerator demo and requests restoring them plus resetting their own test usage/accesses. Preserve the exact invitation URL, histories, model isolation, four-reset and $5/original-session limits. Do not increase hosting costs. Restore 20 available admissions and accelerator session/link allowances through audited credits; actual charged costs and unresolved reservations remain under the existing $35 global ceiling. No billing records are deleted or made free; owner allowances remain unchanged. No new provider call or model stage.

Diagnosis: hosted response metadata on November 20 showed saved doctor/medicine reports, a ready location scope, but paused checks because active_task remained timing with no investigation hint. The same code was present locally; the task gate made behavior depend on the journey. D207 lets an existing report qualify for checks in work mode regardless of active task. Discuss/detour/stop/finish gates and source/scope/ambiguity checks remain. Choices are source-owned and staged through the ordinary Send control.

The hosted HTTP reproduction initially failed with no selector; after repair it returns doctor candidates followed by medicine strength/form choices and continues with one delivered action. Scripted model capture follows the same path. 128 Python tests and six JS rendering/continuation checks passed without paid/network model calls. Release 58daf665e2330687429a96ce7166190b94274d539536c3a0ed9e7972fcca246a reconstructs all 492 hashes and differs from D206 only in conversation_planner.py, pilot_budget.py and the new deployment tool. Deployment and counter-reset execution are recorded separately.

## D208 · November 20, 2026 · Accelerator without conversation-count limit; $50 overall AI cap

Owner: “actually bump to the techstars invite link to no conversation limit, but $50 total cap all else the same, i want them to have a good experience.” Remove the accelerator policy's shared-invitation admission-count cap. Preserve exact signed URL, expiry, authentication, revocation, rate/concurrency controls, histories, Ultrafast gpt-6.1-sol/low, four in-session resets and $5 across each original session and reset descendants. Owner admission limits, standard/low model, $2/visit and $20/link remain. Raise the shared cumulative application ceiling and accelerator link ceiling to $50 including actual prior charges/holds; D207 scoped credits remain, no ledger reset. Align the existing dedicated provider project monthly enforced limit to $50. No hosting upgrade, new resource, permission or paid probe. Addresses D188/D191/D195/D206/D207. Validation/deployment evidence: audit-evidence/accelerator-access-d208-20261120/.

D208 execution: both services deployed release `9bfbab345f3d29a5bba254c691474818fb133b309b5f9b81b0948a7f5f49fb1a`; all 493 file hashes, live policy settings and public HTTPS/access checks passed. Exact invitation identity unchanged. Provider project saved at $50, enforcement on, $20 alert retained. Actual ledger remains 100 rows/$7.6387186 with zero holds; $42.3612814 remains. No paid probes, invitation redemption, hosting upgrade or IAM change. See D208 evidence for command IDs.

## D209 · November 20, 2026 · Pilot priorities and formal second-brain review

Owner requests a formal review of the Daylight Brain and updated priorities. He considers the existing 2026 doctor/network, prescription and plan data more or less complete for a demo, wants the pilot and conversations with four communities about interest contingent on pilot success to be the top priority, and expects his father to help recruit in his Naples community. He wants complete synthetic-profile journeys checked against known objectives, actual plan routing/presentation and the profile and education schemas so avoidable bugs do not dominate learning. Voice-to-text/an eventual spoken agent and full enrollment are long-term considerations, outside this pilot; a separate enrollment-software landscape review is pending.

Follow-up in this session: “no participant sessions have already happened”; he wants this to happen “right after Thanksgiving,” with his father rallying participants while he hones and tests the conversation. Thanksgiving is November 26, 2026. This supersedes the old November 17 start. No exact session date or replacement cohort end is supplied. The fourth community name is uncertain; official North Naples Neighbors pages identify Esplanade alongside Heritage Bay, TwinEagles and The Quarry, making Esplanade the likely match rather than a confirmed owner-selected outreach target. His reference to “Bonita” remains to be clarified with the intended list.

Record owner direction separately from the review's recommendations: recruitment and a bounded reliability pass together, reuse existing corpora, independently specified acceptable outcomes including keep/wait/holds, actual journey and record/presentation checks, a small observed first wave and explicit study measures. The live planning sheet conflicts with the Brain on fictional versus own-situation sessions, January versus the older November schedule, thresholds and Option A/B. Record those conflicts; do not silently select a scope or change the sheet's scores, thresholds or operating model.

Review/documentation only. Existing source/method/purpose and real-health participant holds, D64, counsel dependencies, protected variants, stores and budgets remain. No application changes, paid/live agent conversations, participant-data access, outreach, purchase, new spending or deployment are authorized or performed by this review. [Findings and recommended readiness sequence](../reviews/pilot-priorities-2026-11-20/README.md).
