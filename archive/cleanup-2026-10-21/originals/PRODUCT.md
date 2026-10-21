# Daylight

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Older adults learning about Medicare, people approaching eligibility, and people reviewing coverage they already have.
- Adult children, spouses, and other caregivers researching with or for the person receiving coverage. Questions must make clear whose situation is being entered.
- People may be unfamiliar with insurance terminology, use an iPad or phone, and need large, readable, explicitly labeled controls.
- People who already understand their options may take a clearly identified route to plan comparison without completing the teaching journey.

## Product Purpose

Help a person understand their Medicare coverage choices, connect the explanation to their situation, compare available published plan facts, and leave with useful next steps.

Success means the person understands what they are doing and why, knows where they are in the journey, can review or correct their answers, and can distinguish confirmed information from things they still need to check.

## Positioning

Self-directed research, licensed transaction. Daylight offers an immediate automated helper and visual explanations; this build does not sell insurance or enroll anyone. The person makes their own choices.

## Operating Context

- The active frontend is `cms-slice/apps/chat/` (`index.html`, `app.js`, `styles.css`). It uses HTML, CSS, and JavaScript with a Python service. The archived prototype is historical evidence, not the active app.
- Keep the step-by-step journey and restore its picture-based lessons, diagrams, and map. The owner explicitly confirmed this direction on 2026-10-20; returning to a chat-led product is not the agreed direction.
- Ask Daylight is a supporting conversation interface below Continue and Back, close to the person's interaction. Help opens a focused answer view with the selected question, an answer first, visible follow-ups, and an explicit Return to the guide; preserve the guide’s answers, unsent chat draft, and reading position on return. Keep a corresponding arrival entry below its actions; do not duplicate it in the header or lesson heading. Typing remains optional.
- General education can be useful outside the local plan-data market. The current local comparison dataset concerns published 2027 Collier County, Florida records. Do not imply nationwide local-plan availability.
- The running frontend and the accepted data service are separate concerns. API availability, accepted releases, and review status must be checked before claiming that real comparisons or typed chat work.
- Guide answers and notes are session state. Explicitly submitted chat can be transmitted to the configured service and locally logged. Do not make blanket privacy promises that contradict that distinction.

## Capabilities and Constraints

- A guided journey adapts to reported enrollment, current coverage, job coverage, needs, and goals. Preserve useful branching rather than resetting everyone to the same beginner path.
- Beginner teaching starts with one concept: what Medicare is. The picture accumulates A/B, drug coverage, costs, coverage routes, and Medigap as each becomes relevant. Explain why every personal question is asked. The owner compared this pacing to learning a new video-game universe; it does not authorize decorative gamification.
- Restore and preserve the visual teaching content: coverage pictures, how the parts fit together, coverage-route diagrams, side-by-side comparisons, personal timelines, and the final map/checklist. Simplifying navigation does not authorize deleting explanations.
- The visual guide must be useful while making a choice, not buried below an entire form. Show a concise relevant visual beside the task on larger screens and close to the question on phones. Keep deeper explanation below and link the same teaching topics to chat.
- Source-linked guide answers and live generated replies are distinct. Basic guide explanations remain available independently of the live service; report unavailable live answers honestly.
- Keep the landing page focused on its main introduction and actions. The owner removed the separate “A clearer picture” preview, Medicare tile, and three-step explanation; visual teaching begins inside the journey (D38).
- Make plan comparison a clearly labeled shortcut for people who already understand their options. The guided start remains the obvious first route for a newcomer.
- Give each guided question a single, consistently placed Continue action. Answer choices are inputs, not additional competing ways to advance. Back, editing, and help must remain visible and labeled.
- Ask literal questions that people can answer directly. Do not require them to calculate the calendar year of their 65th birthday. Derive age-based dates from the information they actually know, preserving any timing distinctions required by the existing rules.
- Do not select an answer for the person. Preserve answers they explicitly entered when they go back; distinguish that from choosing defaults on a fresh question.
- Keep progress truthful and aligned with the displayed question. Skipping, viewing, an unknown answer, an API failure, and completing an action are distinct states.
- A first name may be offered optionally. It must not become a sign-up requirement or imply an account exists.
- Keep entered notes, accurate date logic, unknown-answer handling, recoverable service failures, catalog controls, and actionable final checklists while restoring the visual guide.
- Source labels and limitations remain visible. Published-field ordering is not personal suitability, a recommendation, or a promise of savings.
- Doctor participation, personal drug costs, Medigap quotes, eligibility, and other unverified facts must stay unresolved until supported. Preserve review/acceptance gates and backend evidence checks.
- `DAYLIGHT_REQUIREMENTS.md` is the running, numbered list of owner requirements and the acceptance criteria for interface work. Only an explicit later owner decision changes a binding requirement.

## Brand Commitments

- Product name: Daylight. The browser tab should show the existing sun favicon and the title `Daylight`.
- Use the existing header sun identity; the owner rejected the duplicate sun/logo in the arrival content.
- Voice is literal, calm, and clear. Microcopy matters. Avoid jargon, ambiguous next-action labels, and unexplained technical terms.
- The owner explicitly requires breathing room, large tappable choices, text-supported icons, no hidden gesture-dependent actions, and no decorative animation.
- Common chat actions and follow-up questions must remain visible without collapsed menus. Help must identify the person's question clearly and avoid competing with the guide, picture, and answer choices for attention.
- Communicate information with useful visuals, grids, and tables. Do not substitute walls of prose for the visual teaching guide.
- The prior mascot and aesthetic proposals are not blanket authorization for new decoration. Preserve existing assets as evidence; settle any later identity replacement separately.

## Evidence on Hand

- Current progressive-teaching structure and service finish: `docs/DAYLIGHT_LEARNING_FLOW.md`. It records D25 and D29–D32 and the owner’s latest learning/placement direction.
- Current implementation: `cms-slice/apps/chat/`.
- Visual guide content and component inventory: `DAYLIGHT_GUIDE_REDESIGN.md` (V0–V8 and Basics cards). Its older arrival/chat structure is historical.
- Journey specification: `DAYLIGHT_JOURNEY_PLAN.md`. Preserve the teaching content and journey intent subject to the owner's newer interaction requirements.
- Earlier visual captures: `cms-slice/reports/ui-redesign/phase-core/`, `cms-slice/reports/ui-aesthetic/phase-core/`, and `cms-slice/reports/ui-journey/phase-core/`. Compare against current code before treating a capture as current.
- Recent walkthroughs and implementation report: `audit-evidence/USER_WALKTHROUGH_2026-10-20.md`, `audit-evidence/FLOW_REVIEW_2026-10-20.md`, and `audit-evidence/FLOW_FIXES_2026-10-20.md`. These record technical work; they do not constitute owner approval of the resulting design.
- Published-source data and evidence live in `cms-slice/`. Preserve provenance and current review status. Do not invent approval, testimonials, study results, live service availability, or independently verified personal coverage.

## Product Principles

1. Teach with a visual guide, one understandable task at a time.
2. Make the next action obvious and give the person control over advancing.
3. Preserve useful content and progress across refinements and model changes.
4. Show sources, uncertainty, and the limits of the product honestly.
5. Treat the owner's recorded requirements as the baseline for every change.

## Accessibility & Inclusion

- Design for readable text, generous separation, large touch targets, keyboard operation, and visible focus on desktop, iPad, and phone.
- Use W3C's older-user guidance and COGA as the endorsed baseline. Design for varied vision, dexterity, confidence, and attention; do not assume every person over 65 has the same needs. Include older users in comprehension and task testing.
- Icons accompany visible text. Important actions cannot depend on icon recognition, hover, swiping, or other hidden gestures.
- Choice cards must be tappable across their visible area, with explicit selected/unselected states and accessible names.
- Use real DOM text, semantic grids/lists/tables, and labeled diagrams so explanations remain readable, selectable, and accessible.
- Do not require animation to explain progress or a state change. Respect reduced-motion preferences and avoid decorative motion.
- Pair the question with a compact visual explanation and explicit Ask Daylight access. Keep deeper explanations below the main task, rather than burying either the controls or all teaching under long content.

## Requirement Precedence

The owner's 2026-10-20 review and confirmed restoration direction, captured here and in `DAYLIGHT_REQUIREMENTS.md`, override conflicting older briefs. Existing factual safeguards remain binding.

- `DAYLIGHT_LEVELS_PLAN.md`: the chat-first/late-map product structure is superseded.
- `DAYLIGHT_DESIGN_BRIEF.md`: its earlier chat-first arrival is superseded; retain useful content and factual constraints.
- `DAYLIGHT_AESTHETIC_PLAN.md`: previously placed on hold by the journey plan. Its mascot, motion, and decoration proposals do not override the current owner requirements.
- `DAYLIGHT_JOURNEY_PLAN.md`: retain the journey and visual lessons. Older multi-action, gesture, auto-advance, or interaction proposals yield to the current explicit controls and single Continue rule.
- `audit-evidence/FLOW_FIXES_2026-10-20.md`: retain valid functional fixes, but its test count and implementation claims do not override the owner's rejection of lost content and confusing UI.

## Deliberately Unset

No replacement visual identity, new palette, mascot direction, or landing-page image-generation default was selected in this product initialization. This is restoration of an existing app, not an instruction to replace its visual world.
