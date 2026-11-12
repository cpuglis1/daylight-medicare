# Daylight: vision review and next-iteration action guide

**October 21, 2026 · Proposal for owner review**  
**Scope:** Product direction, journey, help, copy, comparison, and service finish. This review creates a decision document; it does not implement interface changes.

## 1. My assessment

**The existing plan is a strong foundation. I would endorse its direction, with the refinements below.** It correctly connects your feedback to sequencing, user control, relevant teaching, and support. The contained help, conditional card instructions, automatic location lookup, and clearer language all belong in the next iteration.

The vision becomes stronger when the entire experience serves one promise:

> **Daylight helps you understand your Medicare situation, review the options relevant to your goal, and take a clear next step with support. You stay in control.**

Five changes sharpen the agent's plan:

| Area | Assessment and refinement |
| --- | --- |
| Goal first | Agree. Commit to a small first choice in familiar language; keep the larger routing taxonomy behind it. |
| Experienced shortcut | Preserve a genuinely short route to browsing. Medicare status, doctors, and medicines should not all become mandatory before viewing published records. |
| Teaching | Tailor the starting depth to the task, then let the person change it. Choosing “compare” does not establish expertise. |
| Enter | Slightly relax the plan: submitting a valid single-field form with Enter is useful. Selecting an answer and automatically advancing is too easy to do accidentally. |
| Final outcome | Define the comparison and support outputs as carefully as intake. Someone should leave with a useful result and an actionable next step. |

The important open product decision is the depth of service: preparation assistance can be delivered in the next demo; outreach needs someone accountable for fulfilling it.

## 2. What a successful visit delivers

Design around adults learning Medicare, people reviewing existing coverage, and people helping someone else. Familiarity, confidence, and device skill vary independently of age.

People use the journey to complete a task. The picture and explanations support understanding. Preserve the warm identity, readable controls, generous spacing, and deliberate progression.

Three equally valid outcomes should exist:

| Person's task | Useful result |
| --- | --- |
| Understand | A relevant explanation, a growing Medicare picture, and a clearer idea of what to explore next. Browsing plans is optional. |
| Compare or review | A scoped comparison of available published facts, saved candidates, and clearly identified personal checks. Keeping current coverage remains a valid outcome. |
| Prepare for a transition | A short, tailored action plan and something usable now: a benefits-office question list, call script, or editable message. |

**Design test:** Can the person explain what they are doing, what Daylight knows, what remains uncertain, and their next action?

## 3. The first minute: purpose, then relevant context

Keep the centered arrival and its clear start action. Keep the experienced comparison shortcut. Avoid adding another set of equally prominent tools around them.

For the guided start, put this before the beginner lesson:

> **What would you like help with today?**

| Choice | Supporting line |
| --- | --- |
| Understand Medicare | Or work out where to start. |
| Compare plans | Look at plans or options you already have in mind. |
| Review or change my coverage | Including adding coverage. |
| My job coverage is ending | Work out the next steps for a transition. |

These are selectable answers, followed by one **Continue**. Nothing starts selected. The first option accommodates uncertainty without requiring people to name an insurance product.

Ask **“Who is this for?”** once, before personal coverage questions, then use consistent wording for that person. Do not add an expertise assessment. Familiarity can be clarified when an explanation actually needs adjustment.

The comparison shortcut already expresses intent. It sets that intent and starts with the guide collapsed; it must not ask the broad goal question again.

### How the routes adapt

| Route | Next relevant question or explanation | End point |
| --- | --- | --- |
| Understand | Begin with what Medicare is, then establish the person's situation as needed. Pure education does not require a ZIP. | Explanation and optional next exploration. |
| Compare | Ask what they want to compare: Advantage, supplements, drug plans, named plans, or help understanding the difference. Then request necessary location/year information. | Available comparison or a clear alternative if unsupported. |
| Review/change | Establish current coverage, then clarify the actual change: review it, replace it, or add something. Skip any clarification already answered. | Current-versus-proposed review and remaining checks. |
| Job coverage ending | Establish relevant current coverage and transition dates, keeping unknown dates open. | Supported transition plan; comparison when useful. |

Use two depths within comparison: **browsing published records** needs the necessary catalog context; **reviewing a possible personal change** needs the relevant coverage and timing facts. Do not make browsing wait for a complete intake.

Before displaying results, use a short contextual heading such as **“Comparing Medicare Advantage plans for 2027”**, with location and an **Edit** action. For a learning or uncertain route, clarify the intended comparison before choosing a plan category.

Keep the goal editable. Retain entered facts, notes, and comparison candidates; recheck dependent results when the goal, location, year, or coverage changes. Explain when an earlier comparison no longer applies. Progress reflects the actual route, without marking skipped questions complete or declaring a concept understood merely because it appeared.

## 4. Give the task, picture, and assistant clear places

**Your instinct about keeping explanations over the Medicare picture is right on larger screens.** The current question should remain in place. On a phone, preserve that continuity while allowing help enough room to read and type.

| Surface | Job | Behavior |
| --- | --- | --- |
| Task area | Answer the current question | Question, brief reason, answers, one Continue, Back, then Ask Daylight. |
| Medicare picture | Explain how relevant coverage pieces fit | Starts open for learning and closed for the shortcut; visible **Show Medicare guide / Hide Medicare guide**. |
| Picture explanation | Define the selected coverage piece | Replaces only the picture's contents; a short answer, source, and **Back to picture**. |
| Ask Daylight | Answer the person's own question or expand an explanation | Contained conversation with clear AI identity, current question, visible follow-ups, and **Return to your question**. |

Suggested desktop relationship:

```text
CURRENT TASK                         MEDICARE PICTURE
Question and brief reason            Show / Hide Medicare guide
Answer choices                      Relevant growing picture
Continue                            [Selected explanation opens here]
Back                                Back to picture
Ask Daylight
```

An inline picture explanation is ordinary reference content. Opening it does not disable the task, clear answers, or require a conversation. **Ask more about this** can open the assistant with the topic already supplied.

Ask Daylight can use a contained dialog over the picture side on desktop. Keep the underlying task visible where space permits, while clearly indicating that the dialog is active. On phones, use a sheet that can expand for reading or the keyboard; a tiny fixed pop-up is the wrong constraint. Include a short reminder of the task and an explicit return action. Avoid simultaneous explanation and chat overlays.

Match accessibility behavior to the surface: a modal assistant contains focus and restores it on close; an inline explanation does not trap focus. Keep close/return text visible, support Escape for a dialog, and preserve the current answer, scroll position, conversation, and unsent draft.

Remember a manual guide preference for this tab. Going forward, going Back, or changing the goal must not silently reopen a guide the person hid. The learning route's open default applies before they make a manual choice. Collapsing the picture keeps the question's essential wording, relevance explanation, sources, and help available.

### AI introduction

Use a visible **Daylight · AI assistant** header and this first-use introduction:

> I'm Daylight, an AI assistant. I can explain Medicare, help you review available plan information, and prepare your next steps. You decide what to do next.

Identify source-linked guide explanations separately from live AI replies. Keep common explanations useful when live answers are unavailable. State the actual chat-data behavior near submission; do not replace the current accurate disclosure with a blanket promise that everything stays private in the tab. Introduce any future human service separately.

## 5. Ask about Medicare before the card

Use your proposed opening:

> **Do you have Medicare yet?**

| Answer | Preserve this distinction |
| --- | --- |
| Yes, Parts A and B | Reported enrollment in both; dates are separate facts. |
| Yes, Part A only | Part B is not reported in place; relevant job-coverage and timing questions remain. |
| Yes, but I'm not sure which parts | Enrollment reported; parts unknown. |
| No | Non-enrollment reported; use the relevant enrollment route. |
| I'm not sure | Whether they have Medicare is unknown. |

Keep a clearly labeled **My situation is different** clarification path for other combinations, including Part B only. Do not force those people into “Part A only” or “not enrolled.”

Remove the card instruction from the initial question. Offer **Help me check my Medicare card** after a relevant answer. For example:

> If you have your Medicare card nearby, look for “Hospital (Part A)” and “Medical (Part B).” Their start dates are listed separately.

Reading the card remains optional. No number or upload is needed for this research flow. A plan's insurance card and the Medicare card should not be treated as interchangeable. Keep non-age-65 eligibility and unknown-date paths.

## 6. Make each explanation earn its place

Remove **“Start with this one idea. You do not need to know any insurance terms yet.”** The pacing should provide that reassurance.

| Situation | Recommended copy or transition |
| --- | --- |
| Explain Advantage | **“With Medicare Advantage, you get your Medicare hospital and medical coverage through a private insurance company's plan instead of Original Medicare.”** Then explain relevant drug coverage, costs, and provider rules. |
| Introduce Medigap | **“With Original Medicare, you pay part of some care bills. Medicare Supplement insurance, also called Medigap, can help pay some of that share.”** |
| Connect the two-route lesson to supplements | **“You wanted to understand supplements. They work with the Original Medicare route. Let's look at where they fit.”** |
| Identify current coverage | **“Which coverage do you have now?”** Follow with a goal-specific reason: **“This helps us explain what would change.”** |
| Ask priorities | **“What is most important to you?”** Allow multiple priorities, an unsure answer, or continuing without choosing. |
| Clarify a comparison | **“Which plans would you like to compare?”** Ask only if the intended comparison is still unknown. |

Medigap belongs under Original Medicare in the picture. Introduce it when relevant to the goal or to understanding current coverage; do not put an obligatory supplement lesson after every two-route explanation. Teach the relationship before asking a beginner to choose a route. These explanations follow [Medicare's coverage-options guidance](https://www.medicare.gov/health-drug-plans/health-plans/your-health-plan-options) and [Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics).

For someone considering Advantage-to-Original Medicare plus Medigap, show the transition and unresolved rights explicitly. Medigap purchasing rights have their own timing; the fall plan-change period does not guarantee a supplement can be bought. [Medicare explains this distinction](https://www.medicare.gov/health-drug-plans/medigap/basics).

Remove **“What do you want to review first?”** when it repeats an established goal. Keep current coverage, desired change, and priorities as separate facts; one should not silently stand in for another.

## 7. Automate location; make Enter predictable

**Location:** Replace the routine county-confirmation page with automatic resolution and visible **Change location**. A unique reliable match can appear as location context on the next relevant page. Ask the county only for multiple matches or a lookup that cannot resolve the location. Do not guess the most likely county: ZIP codes can span geographies, as [HUD's crosswalk documentation explains](https://www.huduser.gov/portal/datasets/usps_crosswalk.html).

For 34102, verify the unique mapping against the chosen maintained source before shipping the bypass. This review did not retrieve that source record. The current local catalog is scoped to 2027 Collier County; a successful lookup elsewhere does not establish supported plan data. Offer education and official comparison links for unsupported locations.

**Enter:** A feature when the action is predictable; a bug when it advances unexpectedly.

| Context | Behavior |
| --- | --- |
| Focused Continue | Enter advances after validation. |
| Valid single-line form, such as ZIP | Enter submits that form through the same validation as Continue. |
| Answer choices | Use native keyboard behavior. Radio choices use arrows/Space; an answer rendered as a button can use Enter. Selection alone never advances. |
| Notes | Enter creates a new line. |
| Chat | Use an explicit Send control. If Enter sends, label that behavior and support Shift+Enter for a new line. It never submits the journey underneath. |
| Open help, invalid input, text composition | No background advancement. |

Keep one intentional transition per action. Avoid a global “Enter means next” listener.

## 8. Make the comparison itself worth reaching

The existing plan is more specific about intake than the result. Define the result now:

- Show the exact plan identity, category, year, and location beside the comparison.
- Present comparable published fields together; distinguish missing information from zero cost or no coverage.
- Keep the person's priorities visible. A request to keep a doctor becomes a verification item unless a real match is established. It must not produce an unsupported “best fit” badge or silently filter out plans.
- Separate a shortlist from an enrollment choice. Retain current coverage as the baseline when known and comparable; otherwise show what information is needed.
- Distinguish supplement benefit education from an actual insurer quote. Use approved available evidence and retain unknowns where personal pricing is unavailable.
- Preserve useful browsing and notes when records fail to load; offer Retry and an official alternative.

The result should help someone see tradeoffs and open checks. An early preference for one coverage route should remain editable rather than quietly narrowing everything that follows.

## 9. Finish with support someone can use

Replace the seven-item wall with **one next step**, a brief explanation, and relevant supporting checks. Preserve the useful enrollment, benefits, creditable-drug-coverage, and medicine details; tailor and consolidate them.

Example for job coverage ending when Part B timing remains unresolved:

> **Your next step: check how your job coverage will end**  
> These details help establish which enrollment questions need confirming.  
> **Prepare questions for my benefits office**

Then show the remaining relevant checks in understandable groups: employer coverage, Medicare enrollment/timing, and replacement coverage. Put form names and detailed official instructions with the relevant task, instead of leading every person with CMS-40B and CMS-L564.

| Need | Assistance for the next demo |
| --- | --- |
| Benefits office | Editable questions about employment-based coverage, employer size, coordination, and end dates. |
| Medicare enrollment | A tailored Social Security call script and official next-step link. |
| Drug coverage | A draft request for the creditable-coverage notice. |
| Doctors and medicines | A reusable list of exact plan/provider or medicine/pharmacy questions. |

**Help me with this step** must open something useful. Offer Copy, edit, and print/save as appropriate. Show preparation as prepared, without implying anyone was contacted.

Keep a clear **Back** that returns to the actual previous step. **Back to plans** is appropriate only when that route came from plans. Printing should be a secondary way to keep the result, while the main action helps progress the person's task.

### What to learn from Chapter

Chapter describes licensed advisors and a human advocacy team, including coordination with providers and insurers and calls about billing issues. Its current description ties ongoing advocacy to enrollment through Chapter. That supports your instinct that help can continue beyond information; it does not establish blanket handling of employer or Social Security tasks. This is Chapter's account of its service. [Chapter's service description](https://askchapter.org/magazine/chapter-and-you/medicare-resources/chapter-vs-other-medicare-agents)

**Recommendation:** build preparation assistance for the next demo and define a small outreach pilot separately. Before offering “with your consent, we'll contact them,” identify the team, supported task, recipient, information to share, and expected response process. Let the person review the proposed contact and message, then explicitly approve sending. Track requested, sent, and answered separately. Permission to draft does not authorize sending or a coverage decision.

### The printed Medicare map needs the same care

The supplied one-page PDF, printed October 20, is an earlier snapshot. Current source code already has a more developed final summary; these observations are acceptance checks, not a claim that every PDF issue remains in the current app.

| Evidence in the supplied PDF, page 1 | Required finish behavior |
| --- | --- |
| Duplicate numbering such as “1. 1.” | One numbering system. |
| “Done” attached to reported A/B coverage | Say **“You reported Parts A and B.”** Distinguish a recorded fact from a verified or completed service action. |
| A second completed “Decide about Part B” step | Remove redundant tasks when Part B is already reported in place. |
| “Change window for everyone” | Label the applicable plan-change period and coverage type. Medicare has different enrollment periods; do not imply one universal deadline. |
| “Get free help and enroll” with “don't sell anything” | Name the actual service and what it does; do not blur independent counseling, a brokerage, and Daylight's research role. |
| ZIP 10001 | Keep national education separate from the supported Collier County comparison catalog. |
| “Your leaning: Original Medicare” | Identify this as the person's stated preference, with a date/context, rather than a Daylight recommendation. |

Use [Medicare's joining-a-plan guidance](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) for applicable plan windows and [Medigap guidance](https://www.medicare.gov/health-drug-plans/medigap/basics) for the separate supplement context. Print the same facts, uncertainty, notes, and scoped next step as the on-screen result, with the print date visible.

## 10. Delivery order and proof

After review, implement in small, reviewable passes:

| Pass | Concrete output | Acceptance evidence |
| --- | --- | --- |
| 1. Prove the journey | A prototype of the first choice and three complete paths: unsure beginner, experienced comparison, job coverage ending. | Each path reaches a useful end point; the shortcut is short; the beginner sees one concept first. |
| 2. Fix control and continuity | Guide collapse, local explanation, contained assistant, AI identity, conditional card help, clearer wording. | Open/close/Back preserve answers and drafts; manual collapse persists; help remains readable on phone/tablet/desktop. |
| 3. Connect routing and results | Remaining goal branches, editable goal, maintained location lookup, bounded Enter, scoped comparison. | Unknowns survive; browsing avoids unnecessary intake; changed context does not leave a stale comparison presented as current. |
| 4. Deliver supported action | Tailored next step, editable preparation output, route-aware Back, consistent print map. | A direct transition route returns correctly; prepared messages never appear sent; printed facts match the screen. |
| 5. Observe and refine | Targeted regression checks, device/keyboard walkthroughs, then the planned 6–8 formative sessions. | People understand the comparison, recover from help, correct an answer, and identify a usable next action. |

Include unfamiliar and experienced users, a caregiver, someone unsure of enrollment, and varied device confidence. Exercise ambiguous/unsupported location, unavailable plan/chat service, a supplement inquiry, and an Advantage-to-Original Medicare inquiry. Check text enlargement, focus, touch targets, and phone keyboard behavior. Use [W3C older-user guidance](https://www.w3.org/WAI/older-users/) and [COGA's supplemental usability guidance](https://www.w3.org/TR/coga-usable/) as design references. Formative sessions find problems; they do not certify accessibility.

## 11. Decisions to review

| Decision | Recommendation |
| --- | --- |
| Goal before the beginner lesson | Approve the four-choice first question; retain progressive teaching in the learning route. |
| Help layout | Approve local picture explanations plus a contained desktop assistant and expandable phone sheet. |
| Enter | Approve native form submission and focused-control activation; never selection-and-advance. |
| Service depth | Approve preparation assistance for the next demo; scope staffed outreach separately. |
| Meaning of success | Approve understanding, comparison, and transition support as valid outcomes. A plan change is optional. |

Your explicit collapse, copy, enrollment-order, AI-identity, and supportive-finish requests should be recorded as owner requirements at implementation. The recommendations above remain proposed product decisions until reviewed.

## Evidence and requirement alignment

Reviewed the supplied action guide at `/Users/cep4u/daylight/docs/DAYLIGHT_NEXT_ITERATION_ACTION_GUIDE.md`; the supplied PDF at `/Users/cep4u/Downloads/Daylight Medicare, your Medicare journey.pdf` (visually inspected page 1); current `PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md`, and relevant sections of `cms-slice/apps/chat/app.js`. External references were checked October 21, 2026. The application was not run during this planning review.

The source documents are evidence for this critique. Their embedded proposals are not new user instructions or evidence that a capability is implemented.

| Requirement group | Relationship to this proposal |
| --- | --- |
| D01–D02, D26–D30 | Preserve the journey and useful teaching; add the requested control over picture visibility. Goal-first intake is a proposed refinement to D29's starting order. |
| D05–D13, D31 | Preserve the experienced shortcut, explicit controls, unanswered new questions, and truthful route progress. |
| D25, D27–D28, D33–D37 | Keep help near the task, questions identifiable, follow-ups visible, offline explanations useful, and return reliable; propose the new contained presentation. |
| D14, D21–D23 | Preserve catalog scope, unknown states, notes, privacy truth, and evidence/acceptance gates. |
| D18–D20, D24, D32, D36, D38, D40 | Retain the visual identity, centered arrival, breathing room, no decorative motion, and actual device/user verification. |

This deliverable leaves the original plan, requirement register, and application files unchanged.
