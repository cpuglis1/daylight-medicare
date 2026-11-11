# Daylight: next iteration action guide

**Date:** October 21, 2026  
**Status:** Draft for owner review. This document proposes the next iteration; no interface changes accompany it.  
**Audience:** Adults 65+, people approaching Medicare eligibility, and people helping someone else.

## Recommendation

Start by understanding **what brought the person here today**, then ask the questions and teach the concepts needed for that goal. Keep the step-by-step journey, the existing aesthetic, and the useful visual guide. Make teaching adjustable and assistance available without replacing the task.

The current problem is partly sequencing: Daylight starts explaining before it knows what someone wants to accomplish. More copy or a smaller chat window alone will not resolve that. A beginner, someone comparing Medicare Advantage, and someone asking about a supplement need different routes through the same dependable service.

## 1. What your feedback settles

These are explicit requests to carry into implementation, rather than questions to reopen:

- Let people collapse the Medicare guide. “Skip the guide and compare plans” starts with it collapsed.
- Remove: **“Start with this one idea. You do not need to know any insurance terms yet.”**
- Preserve the current question and answers when explaining a guide topic; avoid a whole-page takeover.
- Make Ask Daylight a pop-up-style conversation and identify Daylight as an AI assistant helping the user make their own decisions.
- Resolve location automatically when the geography is unambiguous. Do not routinely ask people to confirm a county the service can establish.
- Ask whether someone has Medicare before giving Medicare-card instructions.
- Make the final checklist a place to get support, with a clear Back action.
- Explain Medicare Advantage more plainly, and introduce Medigap with a reason and a bridge.
- Use **“What is most important to you?”** for priorities.

Your goal-first proposal, the precise phone help layout, Enter behavior, and an outreach service need product choices. Recommendations follow; they are not recorded as implemented or approved.

## 2. Proposed journey: purpose first, teaching when useful

Suggested first substantive question:

> **What would you like help with today?**

Use visible, generously spaced answer choices, followed by one Continue button. Selecting an answer does not advance automatically. Preserve the caregiver path and ask who the journey is for when needed.

| Stated goal | What Daylight establishes | Teaching approach |
| --- | --- | --- |
| Understand Medicare / I’m not sure where to start | The person’s situation, then relevant enrollment and coverage facts | Guide open; begin with what Medicare is, then build one concept at a time. |
| Compare Medicare Advantage plans | Current Medicare status, location, and relevant doctors, medicines, and priorities | Guide initially collapsed; concise explanations available where needed. Choosing “compare” does not prove expertise. |
| Understand or compare Medicare Supplement plans | Current coverage and whether Original Medicare is understood | Explain the cost-sharing problem, then introduce Medigap. Distinguish education from an actual quote. |
| Change my coverage | What they have, what they want to change, and relevant timing | Explain the transition and uncertainties before presenting replacement options. |
| Add coverage | What they want to add and what they already have | Explain relevant components; avoid treating existing benefits as missing. |
| My job coverage is ending | Work coverage, timing, and what must be confirmed | Prioritize a transition support plan; do not force a general shopping sequence. |
| Compare plans I already have in mind | Exact plans, year, location, and intended comparison | Resolve ambiguous plan names before comparing; keep teaching optional. |

These are routing categories, not a requirement to show seven equally weighted buttons immediately. Use a short first set—understand, compare, change/add, job coverage ending, unsure—with visible follow-up choices only where the answer needs clarification. Prototype the labels before implementation.

**Recommended sequence:** purpose → relevant current situation → necessary location/timing checks → relevant priorities → scoped comparison or support plan. Teaching accompanies each step. Pure explanation should not require a ZIP before it is useful.

Keep the beginner Medicare lesson; move it after intent rather than making every arrival complete it first. The existing experienced shortcut sets a comparison intent and collapses the guide without asking the same goal again. Clarify which coverage the person wants to compare if it is unknown.

A goal remains editable. Changing it preserves entered facts and notes, while updating dependent questions and clearing stale results. Do not make a user repeat information or mistake a preference for a confirmed coverage fact.

## 3. Give the guide, explanations, and chat distinct jobs

| Surface | Purpose | Recommended behavior |
| --- | --- | --- |
| Medicare guide | A growing picture of the relevant concepts | Visible **Show Medicare guide / Hide Medicare guide** control; text plus clear state. Beginner default open, experienced shortcut closed. |
| Picture explanation | Explain one piece of that picture | Open inside the picture area, with a clear **Back to picture** action. Leave the current question, choices, and Continue in place. |
| Ask Daylight | Let the person ask their own question or get additional help | A contained conversation window with explicit Close/Return, the selected question clearly visible, and visible follow-up options. |

**Your instinct about local explanations is right.** Asking what Part B means should not remove the question someone was trying to answer. For longer answers, show a concise explanation first and offer a labeled way to ask more. Do not squeeze an entire conversation into a tiny diagram tooltip.

Remember a manual guide open/closed choice through Continue and Back. A new step must not silently reopen it. Keep explanations and sources available even when the picture is collapsed. This is an explicit reference control, not permission to hide common chat actions in dropdowns.

For desktop Ask Daylight, prefer a compact window over the guide side or available space, preserving the task beneath. Keep the current question, draft, answer history, and return position. Show one help surface at a time; avoid a guide explanation, chat window, and competing follow-ups all opening together.

**Phone recommendation:** adapt the window into a bottom sheet that can grow when the keyboard or answer needs room. A permanently small pop-up would make reading and typing harder. Keep a short reminder of the current task and an obvious Return action. If it becomes modal, contain keyboard focus and restore it on close; a nonmodal panel must allow predictable movement back to the task. Do not trap focus in an otherwise interactive page.

Keep Ask Daylight below Continue and Back, with a visible text label. Preserve the useful answer-view improvements already made: identifiable question, direct answer, visible follow-ups, offline/source-linked explanations, and reliable return.

### AI introduction

Suggested copy at the first help entry and in the conversation header:

> **Daylight · AI assistant**  
> I can explain Medicare, help you review available plan information, and prepare your next steps. You decide what to do.

Keep this accurate to the available data and live-service state. Do not imply that the AI is a licensed advisor, has submitted something, or has contacted someone when it has not. Human service, if offered later, should have a distinct identity and handoff.

## 4. Ask about enrollment before asking about the card

Replace the opening coverage question with:

> **Do you have Medicare yet?**

Use equivalent caregiver wording when appropriate.

| Answer | What it means for the journey |
| --- | --- |
| Yes, Parts A and B | Continue to relevant current-coverage questions. Ask effective dates only where needed. |
| Yes, Part A only | Explain why Part B may matter to the selected goal; retain enrollment/work-coverage checks. |
| Yes, but I’m not sure which parts | Enrollment is reported; parts remain unknown. Offer card help here. |
| No | Follow the appropriate enrollment path without card-reading instructions. |
| I’m not sure | Clarify gently; do not assume either enrollment or non-enrollment. |

“Enrolled, parts unknown” must be a separate state from “not sure whether enrolled.” Neither establishes Parts A and B or their effective dates.

Offer card guidance after a relevant answer—for example, **“If you have your Medicare card nearby, the letters A and B show which parts you have.”** Keep it optional; no card number, upload, or document is needed for this demo. Preserve non-age-65 eligibility paths and current timing safeguards.

## 5. Make the language follow the person’s goal

| Current language / transition | Proposed direction |
| --- | --- |
| “Start with this one idea…” | Remove the sentence entirely. Let pacing and layout provide the reassurance. |
| “A private plan approved by Medicare provides Parts A and B.” | **“With Medicare Advantage, you get your Medicare hospital and medical coverage through a private insurance company’s plan instead of Original Medicare.”** Explain drug coverage, provider rules, and costs when relevant. |
| Two coverage routes → immediate Medigap lesson | Bridge: **“With Original Medicare, you pay part of some care bills. Medicare Supplement insurance, also called Medigap, can help with some of those costs.”** Then offer relevant detail. |
| “How do you get coverage today?” | **“Which coverage do you have now?”** Ask only when the selected task needs it, with a specific reason. |
| “Knowing how the coverage is arranged keeps us from treating existing benefits as missing.” | For a change goal: **“This helps us explain what would change.”** For an addition: **“This helps us check what you already have.”** |
| “What do you want to review first?” | Remove when the goal is already known. Otherwise clarify the missing decision directly, such as **“Which plans would you like to compare?”** |
| “What should we consider?” | **“What is most important to you?”** Keep visible choices, including the ability to continue without choosing a priority. |

The Advantage explanation follows [Medicare’s coverage-options guidance](https://www.medicare.gov/health-drug-plans/health-plans/your-health-plan-options). The supplement bridge follows [Medicare’s Medigap explanation](https://www.medicare.gov/health-drug-plans/medigap/basics). Medigap works with Original Medicare, not Medicare Advantage; teach that relationship before someone makes a consequential comparison.

Do not make every Advantage shopper complete a supplement lesson. Do not treat an educational question as a coverage choice. For someone considering a switch, explain relevant implications without promising enrollment rights, eligibility, a quote, or savings.

## 6. Automate routine location work, retain genuine uncertainty

Remove the routine **“Is ZIP 34102 in Collier County, Florida?”** page when a reliable lookup establishes one county. Show the resolved location with a visible **Change location** action instead.

ZIP codes can cross county boundaries. Use a maintained lookup and ask the county only for multiple matches, missing data, or a failed lookup; never choose the most common county as though it were certain for that person. [HUD’s USPS crosswalk documentation](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) explains these limitations.

Before implementation, verify the actual 34102 mapping against the selected source release; this planning review did not retrieve that record. Automatic location resolution does not expand the existing 2027 Collier County plan catalog or bypass its data-acceptance checks. Preserve an honest path for unsupported locations.

## 7. Enter: a useful shortcut with a narrow boundary

**Recommendation for the demo: Enter activates a clearly focused action; it does not globally mean “next page.”**

- Enter on Continue advances with normal validation.
- Enter or Space on an answer selects that answer. It must not also advance.
- Notes retain normal multiline behavior.
- Chat keyboard behavior stays inside chat; sending a message cannot submit the underlying journey.
- Invalid answers, an open help dialog, or text composition must not trigger background advancement.

A validated single-field form could later support Enter-to-submit if testing shows it is predictable. Avoid a global keyboard listener or advancing on selection. The speed benefit is small compared with losing a user’s chance to read, reconsider, or understand what happened.

## 8. Turn the checklist into a supported next step

Your service instinct is sound: a long list of responsibilities can leave someone informed but stranded. Keep the useful checks, but group them and help the person act on one relevant next step.

Suggested structure: **Your next step** → why it matters → **Help me with this step** → remaining checks → printable details. Keep one primary action; printing and official links remain secondary. Back returns to the actual previous step, including routes that reached the checklist without visiting plans.

| Need | Support Daylight can prepare | Who can confirm the underlying fact |
| --- | --- | --- |
| Job coverage ending | A short benefits-office question list covering coverage type, coordination, and end date | Employer benefits office |
| Medicare enrollment or effective date | A tailored call script and relevant official next steps | Social Security / the appropriate official service |
| Existing prescription coverage | A request for the creditable-coverage notice and explanation of why it matters | Current coverage provider |
| Medicines and replacement plans | An organized medicine list and a checklist for checking the exact plan and pharmacy | Current plan documents, pharmacy, and official plan tools |

Consolidate overlapping enrollment tasks. Keep timing and drug-coverage checks when relevant; do not simplify by deleting necessary distinctions. Clearly distinguish what the user reported from what an external source has confirmed.

**For this demo:** offer to prepare the call, message, or question list, then let the user edit or use it. Preparation is a feasible next capability, not something already implemented. Do not show “we’ll contact them” until someone or something can actually fulfill that request.

### Does Chapter do this?

Yes, in a meaningful but specific sense. Chapter describes licensed Medicare advisors and post-enrollment Member Advocates who help with coverage issues, including provider/carrier coordination and calls about billing problems. This supports the idea of ongoing human assistance. It does not establish that Chapter—or Daylight—can automatically handle every Social Security or employer task. This is Chapter’s own description of its service, not independent evidence of results. [Chapter’s service comparison](https://askchapter.org/magazine/chapter-and-you/medicare-resources/chapter-vs-other-medicare-agents)

### A future outreach service

If Daylight offers outreach, define the responsible person/team and supported tasks first. Then present the proposed recipient, purpose, information shared, and message for the user’s explicit approval. Track requested, sent, and answered separately; give the user a way to change or stop a pending request. Permission to prepare a message is not permission to send it or make a coverage decision.

This would be a real service capability, with an operating model and a clear human handoff—not just new checklist copy.

## 9. Proposed implementation order after review

| Pass | Deliverable | Evidence needed before moving on |
| --- | --- | --- |
| 1. Route by goal | Early intent, distinct Medicare states, relevant current-coverage questions, editable goal | Beginner, experienced, supplement, switch, unsure, caregiver, and job-transition routes reach an appropriate next step without unnecessary repetition. |
| 2. Contain help | Guide collapse, local picture explanations, responsive Ask Daylight window and AI identity | Task and answers survive opening/closing; manual collapse persists; question and answer are clear; keyboard and phone behavior work. |
| 3. Clarify questions | New wording, conditional card help, verified geography lookup, bounded Enter behavior | Unique ZIP bypasses confirmation; ambiguous ZIP asks; unknown facts remain unknown; Enter never selects and advances together. |
| 4. Support action | Grouped checklist, useful preparation help, route-aware Back | Direct job-transition and comparison routes both return correctly; a prepared message never appears sent; useful checks and notes remain. |
| 5. Verify and learn | Targeted regression checks and desktop/phone review, then 6–8 formative sessions | People can explain what they are comparing, find help, recover their task, and identify their next step. Record observed confusion and revise. |

Keep the current centered landing, spacing, readable controls, no-animation direction, source links, date guards, session-only data handling, and catalog acceptance gates. This is a flow and assistance refinement, not another visual overhaul.

Use [W3C’s older-user guidance](https://www.w3.org/WAI/older-users/) and [COGA’s cognitive-usability guidance](https://www.w3.org/TR/coga-usable/) as the design baseline. Include participants with different Medicare familiarity and device confidence. Observe completion and understanding; 6–8 formative sessions identify issues rather than certify accessibility or validate the whole market.

## 10. Decisions for your review

1. **Goal first:** approve intent before the beginner lesson, with teaching tailored to the selected task? **Recommended: yes.** Keep the guided journey rather than returning to chat-first intake.
2. **Phone help:** approve a desktop pop-up and a phone sheet that can grow taller when reading/typing requires it? **Recommended: yes.** A rigidly small window will constrain the people we are trying to help.
3. **Service scope:** should the next demo prepare calls/messages only, or include a genuinely staffed outreach pilot? **Recommended: preparation first**, unless a responsible service owner and fulfillment process are ready.
4. **Enter:** keep native activation of focused controls, without a global next-page shortcut? **Recommended: yes for this demo.** Revisit broader submission shortcuts after observing users.

The explicit copy, collapse, and enrollment requests in section 1 do not need another approval round. The purpose of this review is to settle the product choices before coding the revised flow.

## Relationship to current project requirements

| Existing direction | Proposed refinement |
| --- | --- |
| D26: relevant visual teaching alongside questions | Retain relevant teaching; add the explicitly requested user-controlled collapse. |
| D29: beginner starts with Medicare itself | Keep that teaching sequence inside the learning route; goal-first intake would precede it if approved. |
| D33: visible common help/follow-up actions | Preserve. Collapsing the reference picture does not justify hidden conversation actions. |
| D34–D37: focused answers and reliable return | Preserve question clarity and return behavior; replace the current full-page presentation with the requested contained help, subject to the responsive-layout decision. |
| D12 and the settled progression rule: unanswered new questions, deliberate continuation | Preserve. Do not preselect answers. Enter activates the focused control, not an answer-and-advance sequence. |
| D22 and existing data gates | Preserve unknowns, eligibility/timing uncertainty, source integrity, and truthful geographic/catalog scope. |

Implementation touchpoints reviewed: `beginJourney`, `stop0`–`stop2`, `lessonFor`, `lessonGuide`, `openAsk`/`syncAskLayout`, `stop5`, and `checklistItems`/`stop7` in `cms-slice/apps/chat/app.js`, plus the current product briefs and requirement register. The existing future-service workflow is product intent, not evidence that outreach or case management is live. This draft leaves application code unchanged.
