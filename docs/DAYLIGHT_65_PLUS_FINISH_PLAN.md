# Daylight UI finish plan for adults 65 and older

Method: dual-agent (A: /root/design_review · B: /root/evidence_review).

Preserve Daylight’s warm identity and progressive teaching journey. The highest-value finishing work is to make help easy to read, keep common actions visible, and let the final checklist deliver the value of the journey. The owner approved focused help and all four implementation passes after this review (D37). The implementation and verification record is [DAYLIGHT_FINISH_2026-10-20.md](../audit-evidence/DAYLIGHT_FINISH_2026-10-20.md). Findings and measurements below describe the original review, not the finished UI.

The owner’s current requirements are D25 and D29–D36 in `DAYLIGHT_REQUIREMENTS.md`. The endorsed baseline is [W3C older-user guidance](https://www.w3.org/WAI/older-users/) and [COGA](https://www.w3.org/TR/coga-usable/). Use these to support varied vision, dexterity, attention, and technology confidence. The review is neither a study with older adults nor a WCAG conformance assessment.

## What to preserve

- The first lesson teaches Medicare itself, then the picture adds relevant components gradually.
- The existing sun identity, warm paper, sage/olive palette, and readable self-hosted typography.
- One prominent Continue, explicit Back, and Ask Daylight below those controls.
- The clearly labeled shortcut for people who already understand Medicare.
- No automatic personal selections or advancement; answers and notes survive ordinary navigation and help use.
- Unknown, entered, and verified information remain distinct. Keep sources, official alternatives, privacy behavior, and backend acceptance gates.

## Design assessment

The independent design review scored **27/40** across ten Nielsen heuristics. This is an expert judgment, not a measured usability score or release threshold.

| Heuristic | Score out of 4 | Main finding |
| --- | ---: | --- |
| Visibility of system status | 3 | Progress is clear; the asked question disappears from view. |
| Match with the real world | 3 | Mostly clear language; some caregiver and instruction wording needs work. |
| User control and freedom | 3 | Back, Close, edit, retry, and preview exit work in inspected paths. |
| Consistency and standards | 2 | Help reflows the workspace; final controls have abnormal sizing. |
| Error prevention | 3 | Unknown answers and fresh unanswered states are preserved. |
| Recognition rather than recall | 2 | Hidden questions and collapsed follow-ups create memory/discovery demands. |
| Flexibility and efficiency | 3 | Experienced and caregiver routes remain useful. |
| Aesthetic and minimalist design | 2 | Strong identity; competing pictures and repeated help material weaken focus. |
| Error recognition and recovery | 3 | Disconnected services are described honestly, with alternatives. |
| Help and documentation | 3 | Substantial useful teaching; reading order and findability need finishing. |

Arrival and the first lesson are calm and coherent. The emotional low point occurs when a person asks for reassurance and must search for the question, read past a diagram, and discover how to ask again. The ending has useful retained work but does not bring that accomplishment into view soon enough.

In the worst inspected states, the cognitive-load checklist had four clear failures: single focus, hierarchy, recognition of the current question, and the checklist’s minimal-choice threshold. Several five-option groups are legitimate; improve their grouping and instructions rather than deleting None/Unsure or forcing a universal numeric limit. The eight chapter links are navigation/status, not eight equivalent answers.

## Priority findings

### P1 Keep the question and answer together

Both reviewers reproduced the owner’s complaint. At 1501 × 708, the selected question ended around y217 while the conversation viewport began at y237. At 390 × 844, the options question similarly ended above the visible conversation. The question is present in the transcript; the app automatically scrolls past it.

Large pictures precede the answer text. On phone, one visual reply was 924px tall within a 387px conversation area. Opening help can also leave the underlying task heading above the screen after the page reflows.

Proposed fix: make the active question a visible heading, put a short direct answer immediately below it, and position the exchange from its question. Preserve transcript/history and sources without making the person search them to understand the current reply. Suggested passes: `impeccable clarify`, `impeccable harden`.

### P1 Remove hidden follow-ups and competing reading surfaces

After the first exchange, available questions move into a closed “Ask another question about this step” disclosure. Selecting another question recreates and closes it. Expanding it reduced the desktop conversation area from 261px to about 121px and introduced another scroll region.

Proposed fix: show two relevant follow-up questions as ordinary text-labeled buttons, with the question field clearly available. Keep one natural reading area for the active exchange and its follow-ups. Avoid duplicating a substantial guide picture inside every reply. Suggested pass: `impeccable distill`.

My preferred help model is a focused answer state: asking for help pauses the task, shows the question and answer clearly, and offers **Return to the guide**. Keep the current chapter visible as brief context; restore the exact question, answers, and reading place on return. On desktop, retaining an answer beside the task is an alternative to prototype, but it must avoid resizing/reflowing the task or keeping two competing pictures active.

### P1 Make chat work at short heights

At a 390 × 422 stress-test viewport, the conversation shrank to 20px and the textarea extended beyond the viewport. This was a viewport test, not an actual mobile-keyboard test. Automatic textarea focus makes real keyboard behavior a necessary check.

Proposed fix: shorten the persistent introduction/status area, keep the answer and composer reachable, use the available viewport correctly, and avoid opening the keyboard automatically when the person tapped a suggested question to read an answer. Suggested passes: `impeccable adapt`, `impeccable harden`.

### P1 Bring the checklist into view at the end

The final print-preview button measured 220px high; Retry/Edit controls measured 160px each. Ask Daylight began around y1174. Optional input and oversized controls appeared before the useful checklist. Row-oriented flex bases survive in the vertical final-actions layout.

Proposed fix: normalize control sizes, lead with a concise account of entered information and open tasks, and bring the next actions into view. Keep one clear print/save action near the top. Put optional notes, editing, and recovery controls with the relevant item. Preserve all useful content and factual uncertainty. Suggested pass: `impeccable layout`.

### P2 Put response instructions beside the choices

“Select any” and permission to continue without a priority currently appear below the task and picture. Do not rely on square versus circular indicators to explain how to answer.

Proposed fix: show the short instruction immediately above the choices. Group Dental/Vision/Hearing together and distinguish None/Unsure without removing either. Keep the covered person clear in caregiver wording. Suggested pass: `impeccable clarify`.

## Other finishing work

- The 320px reflow check found a 327px document width caused by a chapter label. Fix this narrow overflow; preserve text and navigation.
- Start over clears all session work and drafts immediately. Explain the consequence before committing it or make the reset recoverable. Do not silently add durable storage for personal notes.
- “What happens to my answers?” currently links to Medicare’s coverage-options page as an Official resource. That page does not substantiate Daylight’s privacy behavior. Use an accurately labeled Daylight privacy explanation instead.
- Separate “A/B reported in place” from “coverage arrangement unknown” in the final status text.
- Review smaller 12–15px secondary text in real reading conditions, while preserving the currently generous 18px choice text and 17px answer text.

The key audience risks are specific: a first-time reader may mistake the diagram for the full answer; a caregiver can lose track of whose coverage an instruction describes; a keyboard or low-vision reader must navigate competing scroll areas and smaller secondary text. These are review hypotheses to test with people, not observed behavior from a participant study. Keep the experienced shortcut for people who do not need the beginner explanations.

## Implementation sequence

| Pass | Outcome | Completion check |
| --- | --- | --- |
| 1 Chat reading and control | Visible question, answer-first reading, visible follow-ups, explicit return, usable short-height layout. | Click a picture or question, understand the first reply without searching, ask a follow-up without opening a menu, and return to the same task and draft. |
| 2 Guide clarity | One current task, necessary instructions near inputs, purposeful current picture, less repeated prose. | A first-timer can explain why each question is asked and which coverage piece it relates to. No essential instruction is hidden or delayed until after answering. |
| 3 Final checklist | Normal controls and useful next actions in the first part of the page. | The person can identify what they entered, what remains unverified, what to do next, and how to print the checklist. |
| 4 Verification and polish | Consistent, accessible interaction across devices and states. | Complete keyboard, reflow, text enlargement, short-height, real phone-keyboard, failure/recovery, and older-user walkthroughs; finish with `impeccable polish`. |

Use `impeccable audit` for the technical verification pass. Keep source/acceptance checks separate from design evaluation. The live conversation and plan service must be genuinely available before evaluating successful live replies or real comparisons; do not substitute unreviewed data or bypass release gates.

## Release checks and older-user sessions

Use desktop including the ordinary 1501 × 708 view, tablet, a 390px phone, narrow 320px reflow, short/landscape heights, and real iOS/Android keyboard states. Test text enlargement to [200 percent without losing content or functions](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html), plus appropriate reflow/zoom checks. A narrow viewport alone is not proof of browser-zoom behavior.

Keep generous targets as a Daylight usability goal; do not describe a preferred pixel size as a universal WCAG requirement. Check visible focus, logical reading/tab order, modal entry/exit, announcements, unsent drafts, error recovery, and accidental reset. Verify actual screen-reader speech as well as semantics.

I recommend a first formative round with 6–8 adults aged 65 and older, varied in technology confidence and device use, including a caregiver scenario. This is a proposed research round, not a statistical validation claim. Ask participants to:

1. Explain Medicare and A/B in their own words after the relevant lessons.
2. Open help, identify the question answered, and ask a follow-up without coaching.
3. Return, correct an earlier answer, and verify that their notes remain.
4. Distinguish entered information from facts still needing confirmation.
5. Find their next action and printable checklist.

Record wrong turns, requests for help, incorrect confidence about coverage, lost context, and whether the person can explain the next action. Passing automated checks or completing a task quickly does not establish comprehension.

## Confirmed build direction

The owner selected **focused help** and **the complete staged finish plan, beginning with chat**, followed by 6–8 formative sessions. Help pauses the guide in a focused reading view, with an explicit return to the same task. All three implementation passes and the browser verification/polish pass have been performed. Real mobile keyboards, physical touch, screen-reader speech, successful live service responses, and participant comprehension remain explicitly unverified. No aesthetic replacement was authorized or made.

Durable resume after closing/refreshing is a separate privacy/product decision. Keep the existing session-only policy until that is explicitly decided; reset clarity can be improved without changing storage.

## Run notes

Target: `cms-slice/apps/chat/index.html`; slug `cms-slice-apps-chat-index-html`. Both assessments used their own new Chrome tabs and did not see each other’s output. The technical detector ran after Assessment A completed. Existing scoped Fraunces and cream-palette exceptions were retained; no critique ignore file or new suppression was applied.

The one named markup scan returned exit 0 and `[]` (0 findings). The existing frontend suite passed 49/49 tests. Those VM/stub checks did not detect the reproduced rendering and scroll problems.

Assessment A inspected the full desktop flow and print preview at 1501 × 708. B checked desktop, 1024 × 768, 390 × 844, 320px reflow, and 390 × 422 height stress. Only synthetic data was used, with no paid model calls. Successful live replies, real plan results, screen-reader speech, true 200% browser zoom, physical touch, and actual mobile keyboards were not verified.

Browser evaluation is read-only, so no detector script injection or user-visible overlay was available. Browser/DOM observations, screenshots, and the source scan supplied evidence. No overlay server was started. The review-only static server was stopped; both reviewers closed their tabs and reset temporary viewport overrides. Original user tabs and app files were left unchanged.

Evidence: `outputs/daylight-65-review-20261020/a/` and `outputs/daylight-65-review-20261020/b/`. Particularly useful captures are `a/02-clicked-question-hidden.jpg`, `a/03-expanded-followups-desktop.jpg`, `a/05-next-actions-desktop.jpg`, `b/10-phone-large-guide-answer.jpg`, and `b/14-short-height-chat-stress.jpg`.
