# First Medicare enrollment and the two coverage paths

November 12, 2026 · D161 · Product direction recorded; implementation proposed.

Daylight should help a person establish Medicare, choose how to receive their
coverage, and follow the transition through to coverage being in place. Part A
and Part B enrollment is a core job throughout that experience. The Plans
dashboard has two top-level tabs: **Original Medicare** and **Medicare
Advantage**. Medigap and separate Part D work belongs within Original Medicare.

This implements the human purpose in the Brain's November 12 vision: people
should not have to become insurance experts to protect their health and
retirement. The interaction remains the existing conversation. Software carries
the details, dates and unfinished work; the AI explains the useful next step.

The owner requested this plan. No application code, runtime, source acceptance
or enrollment capability changes are delivered by it. The architecture below is
a proposal, not an additional owner decision or an approved recommendation method.

## 1. The experience to deliver

The person can answer, at any point:

1. What Medicare coverage do I have, and what still needs to happen?
2. What should I do next, why, and by when?
3. How do Original Medicare and Medicare Advantage compare for my needs?
4. What additional coverage belongs with my chosen path?
5. What has actually been submitted, approved and started?

A person can explore plans while A/B enrollment is pending. Establishing A/B is
a dependency for the applicable enrollment action, not a mandatory completed
wizard before someone can learn or compare. Having no Part B today must not
make Medicare Advantage look permanently unsuitable. A legitimate decision to
keep current coverage or delay remains a successful outcome.

Use **Part D**, not “Plan D,” for drug coverage. Medigap Plan D is a different
product. Original Medicare is not synonymous with buying Medigap: supplements
are optional, and existing employer, retiree or other coverage can change what
additional coverage is appropriate.

## 2. What exists and what needs to change

| Existing foundation | Gap this work closes |
| --- | --- |
| RC04 distinguishes both, A only, B only, neither, pending and unknown; RC05 and other conditional meanings cover dates and circumstances | Track each part separately through application and coverage, including A active while B is pending. Reuse those meanings instead of replacing the 41-question contract. |
| `ux_pass.enrollment_timing` and `ux_flow` provide a turning-65 card and conversation hooks | A timing explanation is not an application route or follow-through. Add missing status transitions and applicable routes. |
| D159 enables 40 reviewed general facts on :8895 | Reuse exact accepted statements; identify only the new wording/rules that need acceptance. Do not treat general education acceptance as personal date-engine approval. |
| L13 retains 37 enrollment-rule families, official sources and date fixtures | Create a bounded serving contract for the intended enrollment work. L13 remains unaccepted for personal enrollment/penalty decisions. |
| `intent.coveragePath` and two-path explanations exist | Separate navigation, stated preference and evidence-supported recommendation. The current `original_medigap` name should not require a supplement. |
| Existing Medigap, PDP and MA panels have cards, details and comparisons | Reuse those components under two path tabs, with a shared A/B next step and a coordinated coverage summary. |
| D148 supports current-visit recovery; durable saving is separate | Carry unfinished enrollment work across permitted recovery and optional saved progress without promising indefinite or cross-device memory. |

The current timing helper treats an unreported first-day birthday as later in
the month, computes hypothetical dates from the current month, and does not
receive actual A/B effective dates in its `ux_flow.timing` call. These are
specific integration concerns to resolve before expanding its authority. A
hypothetical start cannot become a confirmed start; reporting “both” cannot
prove when either part started. Premium-free A must stay conditional on its
qualification. The existing first-eligibility handoff must also avoid treating
a delayed Part B start as the person's first Medicare eligibility.

Implementation references: [timing helpers](../../../alternatives/advisor-first/ux_pass.py),
[conversation hooks](../../../alternatives/advisor-first/ux_flow.py),
[plans workspace](../../../alternatives/advisor-first/web-8894/plans-workspace.js),
[reported-input review](../../../alternatives/advisor-first/plan_review.py),
[L13 report](../../data/l13-enrollment-2026-10-28/REPORT.md),
[D157 handoff](../../../audit-evidence/ux-pass-pp16-20261112/HANDOFF.md).

## 3. Front one: enrollment within the conversation

### A small visible change supported by reliable state

Keep the opening, composer, answer choices, contextual cards, Back/edit and
current visit. The person need not choose an “enrollment tool.” An opening such
as “I turn 65 soon and don't know where to start,” “I have A but need B,” or
“I applied last week” activates the appropriate work from the same reports.

The conversation should:

1. **Reuse what is known.** Identify the beneficiary and existing A/B reports.
   Ask one consequential missing question, with its reason. Never repeat a full
   intake or treat learning as proof of comprehension.
2. **Resolve how enrollment happens.** Distinguish already enrolled, automatic
   enrollment expected, application needed, pending, deliberate delay and
   unresolved status. Check automatic enrollment against the relevant reported
   benefits/notice situation; age alone does not establish it.
3. **Work out the applicable timing.** Reuse birth month/year and first-day
   status only when needed. For current-work transitions use coverage type,
   employment and coverage dates, employer-size context, HSA and family effects
   when consequential. Do not ask every person every branch.
4. **Provide the usable route.** Explain the relevant official SSA application
   route, or RRB route when applicable, and the preparation it requires. A-only
   adding B is different from an initial A/B application. Identify applicable
   employer evidence/forms without asking for credentials or identity documents
   in chat. An official application necessarily occurs with that agency; Daylight
   prepares the person, preserves the task and continues afterward.
5. **Keep coverage decisions moving.** Teach the two paths when relevant, reuse
   doctors, medicines, pharmacy, travel and cost priorities, and show available
   options without requiring completion of the external application first.
6. **Follow through.** On return, ask what happened only if it is unknown.
   Record an application report, request for information, approved future start
   or active coverage with its provenance. Coordinate the next dependent action.

### What the model should receive

Add a compact, structured enrollment context to the existing conversation
framework: known component states, source-supported applicable explanations,
which action is available, the one missing-question meaning, and what was
already explained. Update capability context and response checks together.

Proposed instruction intent:

> Help the person get their Medicare coverage in place through this same
> conversation. Reuse confirmed reports. Explain the next supported step and
> ask the one approved question needed to continue. Parts A and B matter to
> either coverage path. Let the person explore while an application is pending.
> Treat requested, expected and confirmed dates as different. Never claim an
> application was sent, approved or effective without the corresponding evidence.

This is a prompt contract to implement and evaluate, not a substitute for
software rules. Keep the two existing interpretation/composition stages; no new
model service or extra model round trip is needed just to calculate status.
Dates, deadlines, prices, eligibility and recommendations remain deterministic.
Amounts and source rows remain outside model context under existing controls.
Each active turn retains its approved next question and relevant failure fallback.

### One shared enrollment record

Add a small versioned service within the advisor, provisionally
`enrollment_journey.py`, deriving its result from the existing guide/readiness
reports. It owns no second guest profile or transcript. Separate person reports
from derived steps and independently supported findings.

| Record | Minimum useful content |
| --- | --- |
| Part A and Part B, independently | Unknown / not enrolled / automatic enrollment expected / application pending / approved for future start / active / action needed; a delay decision is recorded separately |
| Dates | Date precision, requested versus estimated versus reported official date, source, subject and revision; application date separate from coverage effective date |
| Enrollment route | Applicable route, rule/source version, needed evidence, official destination, supported action and unresolved conditions |
| Transition | Current coverage and its end, each proposed new component and its start, overlap/gap status and next necessary check |
| Coverage choice | Undecided / leaning / explicitly chosen; Original Medicare or Advantage; retain/decline/unknown decisions for optional components |
| Recommendation result | Separate deterministic result with exact inputs, evidence, reasons and release status; never inferred from which tab was opened |

Use the existing field envelopes, subject boundary, revision checks and
idempotent writes. Add application-status fields only where the current meanings
cannot express them. Map RC04/RC05/RC06/RC08/RC09/RC11 and relevant conditional
meanings explicitly; preserve unknown, deferred, conflicting and stale states.
Existing saved `original_medigap` values get a compatibility mapping to Original
Medicare navigation, with no invented Medigap choice and no destructive migration.

The same deterministic response feeds chat cards and dashboard status. A
correction to a consequential date, coverage type or beneficiary invalidates
only dependent timing, eligibility and comparison findings. Tab changes retain
drafts, entered details and still-valid results. Out-of-order responses cannot
restore an obsolete date or recommendation.

### Timing and route coverage

For the first complete increment, cover ordinary turning-65 applications,
automatic-enrollment confirmation, A-only adding B, B-only adding A, current-work
delay/retirement, COBRA/retiree distinctions, HSA relevance, pending applications,
different A/B start dates, missed windows and unknown/conflicting information.

Recognize disability, ALS, ESRD, railroad, premium-A and exceptional enrollment
situations. Apply only exact supported rules; otherwise retain the personal
uncertainty, give the applicable reviewed explanation and a concrete official
confirmation route. Do not force these people into the turning-65 calculation.
State-specific Medigap holds stay distinct from federal A/B guidance.

Keep four clocks separate: A/B enrollment; MA/PDP election; Medigap rights; the
old-to-new coverage transition. A COBRA end is not a substitute for the end of
current employment or current-work coverage. D157's removal of unnecessary
questions remains: an end date becomes worth asking only when it changes a
transition result the person sees. Never promise no penalty or no gap from
incomplete history, and never automatically terminate existing coverage.

Treat affordability as part of the same transition. Explain sourced A/B premiums
and relevant assistance or surcharge-review routes when the person's reports
make them consequential; reuse existing assistance screening rather than adding
universal income intake. An assistance application is not an award, and an
unresolved subsidy is not a $0 cost. Preserve exact-purpose limits for personal
amounts and eligibility.

## 4. Front two: a dashboard organized around coverage

### Shared structure

The hierarchy is:

```text
Your coverage options                    Location · coverage year
Original Medicare | Medicare Advantage

Your Medicare: Part A [status] · Part B [status]
Your next step: [the applicable enrollment or coverage action]
Continue
Back to conversation · Edit details

[The selected path's coverage components and available plans]
[A compact summary of chosen coverage and unresolved checks]
Ask Daylight
```

The outline specifies hierarchy, not a new visual theme. Keep the current
Daylight typography, palette and plan components. In a ready case the A/B strip
is one compact line, leaving plans prominent. In an unresolved case it explains
the specific action needed; it is not a stack of general notices. There is one
prominent Continue for the current guided task, with clearly labeled secondary
navigation and help. Its label/context makes the destination clear.

The two tabs are views, not enrollment choices. Browsing Advantage does not
change the recorded path. An undecided person gets a balanced path comparison
within the same workspace, without a third category tab or a preselected answer.
An explicit request for Part D opens Original Medicare at the drug section;
an existing Medigap holder is not taken through buying a supplement again.

### Original Medicare

Present the components in a meaningful order, with compact summaries and
labeled navigation to the currently relevant section:

1. **Parts A and B:** what is in place, what is pending, next action and the
   relevant dates. This uses the shared enrollment record.
2. **Help with medical costs — Medigap:** retain an existing supplement, explore
   supported letters/carriers, or consider the path without a new supplement.
   Show the person's applicable window/rights when supported. Reuse existing
   exact-profile prices, filters, details and comparisons.
3. **Prescription coverage — Part D:** retain appropriate existing coverage or
   investigate separate drug plans, using the medicines/pharmacy already given.
   Reuse the PDP panel and its precise checked/unchecked evidence.
4. **Your coverage together:** selected components, dependencies, dates and
   remaining checks. Show known recurring premiums with their basis and missing
   components; do not invent a complete personal cost total.

Medigap and Part D need not become two very long lists on one screen. Render the
relevant section with a visible summary of the other component and a labeled
way to move between them. This preserves quick access to plans on phones and
lets “I only need drug coverage” remain a short journey.

### Medicare Advantage

Use the same A/B status strip and continue action. Retain MA plan cards,
comparisons, filters and the person's priorities. Drug coverage is considered
within the actual plan, with explicit evidence for covered medicines and
restrictions. A separate PDP is not routinely added to an MA plan; exceptional
combinations require the applicable compatibility rule. Medigap is not an add-on
to Advantage.

Both paths show comparable dimensions: access to care, medicine coverage,
recurring premiums, exposure to care costs, restrictions, travel and future
switching considerations. A $0 MA plan premium is not $0 Medicare coverage.
Account for Part B on either path and Part A where applicable, without counting
either twice. The same unresolved provider or medicine check is visible wherever
it matters, without being treated as poor fit.

### Guidance and recommendations

“Based on your needs” must come from an accepted deterministic comparison, with
reasons and meaningful alternatives. A cost-preference routing hint cannot
become a recommendation. Do not default to Advantage when Medigap pricing is
unsupported, or to Medigap because the user opened its section. Keep existing
coverage, waiting and uncompensated options equally available.

The new navigation and enrollment assistance can be built independently of
consumer recommendation release. D147 remains evaluation-only on :8895; the
dashboard must not turn its labels into released advice. Clear task wording
should describe what is ready and what needs checking without internal jargon.

### Responsive and recovery behavior

Inspect desktop, tablet and phone, including narrow phone widths and enlarged
text. Both top-level labels remain readable without a hidden swipe gesture.
Use one-column sections on phone, accessible comparison controls, keyboard
navigation and visible focus. Restore the exact section, scroll context and
draft after chat, external signup or Back. Changing tabs must not call the model,
infer a preference or clear a comparison selection.

## 5. Application follow-through and permissions

The first release prepares and guides the official A/B application; it does not
submit an SSA/RRB application itself. Opening the official link means only that
the destination opened. A user report of submission is labeled as such. An
approval notice with a future date is not active coverage, and reaching an
estimated date is not evidence that an application succeeded.

Make return useful: “I applied” updates the pending task; “Part B starts next
month” updates the appropriate reported date and dependent checks. A problem or
request for more information gets a concrete next action without losing the
plan research. Never request SSNs, Medicare numbers, account passwords or card
images in the ordinary conversation.

Current-visit continuity uses the existing guest visit. Offer optional minimal
saved progress at the point where someone leaves for an application or needs to
return another day, using the existing privacy controls. Do not add a permanent
save control to the plans header or silently expand retention. New fields must
be classified for saving and AI transfer; version consent if the permitted
context expands. No new raw-transcript persistence, automatic reminders,
outreach or family access follows from this plan.

Keep private-plan enrollment as a separate downstream capability. Its eventual
submission, receipt, acceptance and effective-coverage states can use the same
journey framework after the selected fulfillment route and applicable gates are
ready. The A/B work does not need to wait for the FMO/private-plan adapter.

## 6. Build sequence and completion evidence

| Increment | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Shared contract and rules | Map current reports, fill application-status gaps, define date provenance and scoped rule acceptance; specify two-tab routing and legacy mappings | Fictional transition fixtures, field/permission map, reviewed new statements and a list of unsupported rules; no redefinition of the 41 meanings |
| 2. Complete conversation story | Enrollment service, context/prompt changes, timing/action cards, official route, return/status capture and correction | From natural opening through application preparation, pending and reported outcome in one visit, including unknown/failed paths |
| 3. Two-tab dashboard | Shared A/B strip, Original Medicare sections, MA integration, coverage summary and navigation recovery | Each path reached from conversation; direct Part D/Medigap requests route correctly; existing panels and all records preserved |
| 4. Coordinated decision and dates | Distinct enrollment clocks, component compatibility, properly scoped cost presentation, Before you enroll tailored to the intended action | Corrections withdraw affected findings; no unsupported readiness or recommendation; published amounts reconciled to exact sources |
| 5. Full journey verification | Offline scripted stories, realistic source-backed reads, responsive inspection and an owner review packet | Explicit record of implemented, running, technically verified and owner-accepted status; no agent-run live model tests |

Build and activate for review on :8895 first. Account explicitly for the shared
:8894 frontend so it does not advertise a backend capability absent from :8893;
use capability checks or an isolated candidate until both are compatible. One
agent at a time edits the advisor surface. Preserve protected :8890/:8891/:8896
and their stores. Before a restart, inspect concurrent changes and run the
applicable offline checks; no deployment is part of the planning task.

Reuse D157 H2/H4 for medicine evidence and honest checked inputs, H3 for true
first-eligibility handling, and H5 for path amounts. These dependencies should
not block accurate A/B status, official signup assistance or the two-tab
structure. They do block claims that medicines, eligibility or complete path
costs have already been checked.

Bring the ordinary A/B journey into the first-enrollee milestone. The supplied
audit identifies AI-13 and ES-03/ES-15 in the planning sheet; reconcile those
rows during implementation planning and create explicit A/B preparation and
follow-through work there. Do not leave the work buried in a later general
rules task or private-plan submission task. This document is the engineering
specification, not a second live task tracker; no sheet rows or dates were changed.

## 7. Acceptance stories

| Fictional situation | Required observable result |
| --- | --- |
| Turning 65, neither A nor B, wants predictable costs | Establish application route/timing; show both coverage paths; explore Original Medicare components; retain A/B next action |
| Automatic enrollment expected | Confirm what is actually reported; avoid a duplicate application instruction; capture separate effective dates when known |
| Part A active, Part B pending | Preserve both independent states; continue plan research; never mark B active or reapply automatically |
| Part B only | Guide the relevant A route; do not silently turn it into “both”; use distinct product prerequisites |
| Still working with group coverage and HSA | Ask only consequential employment/coverage/HSA details; explain supported delay/transition issues; do not automatically advise enrolling in A |
| PP16: 65, COBRA, neither part | Reuse all known reports; useful signup step and conditional timing early; no repeated COBRA lesson or irrelevant intake |
| Both parts already active; existing Medigap; needs only Part D | Open Original Medicare at prescription coverage; no first-enrollment or Medigap shopping loop |
| Wants Advantage before A/B begins | Allow research and applicable advance planning; show prerequisites for the intended date; do not classify the whole path as unsuitable |
| First-day birthday, missed IEP, earlier disability eligibility or restarting B | Use correct accepted branch or a specific unresolved result; no ordinary-birthday assumption, proxy eligibility decision or invented new Medigap window |
| Changes an employment or Part B date | Recompute affected windows, coverage summary and readiness; preserve unaffected plans, text and preferences |
| Application needs more information, is denied or has conflicting dates | Keep the issue and next action visible; no success badge or false start date |
| Asks for 2027 coverage | Preserve the requested year; never substitute 2026 plan prices or imply next-year availability |
| Missing, stale or withdrawn source; unsupported quote age/ZIP | Withdraw only affected conclusions, keep the coverage path visible and provide a useful next step |
| Helper researching for someone else; reload or expired visit | Preserve subject isolation and permitted recovery; no invented caregiver authority or promise of recovered data |

Also verify: no duplicate intake; no unsolicited model call from navigation;
no automatic choice; no false submitted/approved/active claim; no hidden option
because of commissions or missing evidence; and no regression in existing
Medigap/Part D/MA details, comparisons, drafts or saved profiles. Use the existing
offline network-forbidden interpreter and relevant test suites, not paid probes.

Observe success as the person locating the next step, understanding the relevant
tradeoff, correcting a report, continuing after the official application and
identifying what coverage is still unresolved. Count repeated questions, loops
and unnecessary turns. Tests cannot establish participant comprehension or
owner acceptance; owner-led conversation review remains separate.

## 8. Requirements and authoritative references

Primary direction: D161. Carries forward D49/D52/D54/D57 (conversation, confirmed
reports, privacy and change control), D64/D73 (independent coverage-path
decisions), D109 (useful answers and next questions), D129–D131/D134/D138 (reuse
plan panels and conversation reports), D143/D147 (recommendation and operating
boundaries), D148 (continuity), D154/D157 (natural journey and minimal work),
D158–D159 (accepted fact scope) and D160 (human mission).

The Brain's `01 Vision and strategy.md` and `02 UX playbook.md` were read from
the current vault identified in CURRENT_STATE. The playbook's three-tab
description is superseded by D161's intended structure; it remains a description
of the prior build until implementation. This planning task does not rewrite
the Brain or claim the new journey is already running.

Official sources checked November 12, 2026:

- [Prepare to sign up](https://www.medicare.gov/basics/get-started-with-medicare/sign-up): distinguishes checking whether enrollment is automatic from needing to apply.
- [Official A/B signup routes](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/ready-to-sign-up-for-part-a-part-b): SSA routes, adding B, employer evidence and RRB direction. The workflow must choose the applicable route.
- [When to sign up](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-can-i-sign-up-for-medicare) and [coverage start dates](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start): timing depends on enrollment situation, part and application timing.
- [Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan): MA requires A and B; a standalone drug plan requires A or B, alongside other applicable requirements. Advance plan requests and effective dates must be handled separately.
- [Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics) and [when to buy](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy): supplements belong with Original Medicare; federal open enrollment begins with Part B at age 65 or older and lasts six months.
- [Working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65): employment, COBRA, HSA and existing drug coverage require distinct considerations.

These checks support product planning. New application destinations must be
verified through the official route before implementation; no SSA/RRB account
was accessed. Conflicts already retained in L13 require their recorded review,
not a silent substitution of web overview text. The plan preserves source STOPs,
sealed evidence and independent source/method/consumer-purpose gates.
