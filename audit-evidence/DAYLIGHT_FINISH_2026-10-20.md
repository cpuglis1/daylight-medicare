# Daylight staged UI finish

Owner direction: focused help and the complete 65+ finish plan, followed by 6–8 formative sessions. Implements D37 and addresses D06–D12, D21–D28, and D32–D36 while preserving the progressive teaching required by D29–D31.

The established sun, warm palette, typography, lesson content, branching, notes, date rules, and backend acceptance gates remain in place. This work changes the active frontend, its regression tests, and project documentation. No backend or source-data approval was changed.

## Finished behavior

1. **Focused help.** One reading surface replaces the competing task/sidebar arrangement. The literal submitted question is a heading immediately before its answer. Opening a picture or suggested question focuses that heading and does not open the keyboard. The answer precedes any useful supporting diagram. Background controls are inert on every viewport; Tab stays in help, Escape and Return to the guide restore the opener and page position.
2. **Visible follow-ups.** Two relevant questions are ordinary labeled buttons. The old closed “Ask another question” menus and nested scrolling areas are gone. Earlier exchanges remain accessible through a labeled history action. At a new concept, opening help offers questions for that concept, with earlier answers still available. Unsent drafts and guide notes survive help use.
3. **Resilient chat.** The composer stays reachable at short heights. The panel follows the visual viewport, including viewport changes associated with keyboards. A ready-status announcement supports assistive technology without taking more reading space. Known guide questions still work locally; unavailable live replies retain the question and expose Retry. Live responses remain attached to the same question.
4. **Clearer questions.** Response instructions stay immediately above their choices. Dental/vision/hearing choices are grouped separately from None/Unsure. Caregiver location, medicine, and supplement relevance text identifies the covered person. Redundant goal, county, and plan-list instructions were reduced without deleting useful teaching. Chapter names fit at 320px using three columns.
5. **Useful ending.** The checklist leads with next checks, with recorded facts alongside it on larger screens. Print/save, Back, and help have normal-sized controls. Editing and retry actions sit with the relevant content; optional doctor notes follow the checklist. Unknown coverage arrangements remain unknown and produce a checking task. Printed content retains medicine/doctor notes, dates, contacts, and uncertainty.
6. **Safer reset and accurate attribution.** Start over explains what it clears and defaults to Keep my guide. Cancel preserves the session. Daylight privacy answers identify Daylight as their source, rather than linking Medicare as evidence for this app’s behavior. Storage remains session-only.

## Verification

The latest frontend suite passes **54/54** tests; JavaScript syntax passes. New regression coverage checks literal question/reply order, draft preservation, focused modal state, contextual help/history, privacy provenance, unresolved coverage facts, and the live transport contract. The live transport test uses a simulated response: it does not establish live-service readiness. Existing date, unknown-answer, branch, notes, and factual-safeguard tests remain passing.

Browser verification used Chrome through the UI automation tool, with synthetic entries only. A complete caregiver journey was repeated through the checklist and print preview. Returning to edit medicines retained the notes. No paid model calls or real personal information were used.

| Check | Observed result |
| --- | --- |
| Desktop 1501 × 708 | Asked question and direct answer are visible together; both initial follow-ups fit above the composer. Print action about 59px, Back about 50px, help 46px; the original 220/160px control heights are gone. |
| Tablet 1024 × 768 | Help and checklist reflow without horizontal overflow; the input and return action remain available. |
| Phone 390 × 844 | Focused answer, visible questions, reachable composer; checklist actions have normal heights. |
| Narrow 320 × 844 | Document width 320px; no horizontal overflow. Medicines fits on one line; chapter navigation uses three columns. Full-page screenshot inspected. |
| Short height 390 × 422 | Reading area about 242px, versus 20px in the review. Input and Send end at y412, inside the viewport. This is a viewport stress test, not a real phone keyboard. |
| Real Chrome zoom 200% | Chrome’s own zoom indicator confirmed 200%. Help had a usable reading area, reachable return/input, and no horizontal overflow. The guide could advance with controls intact. Zoom restored to 100%. |
| Keyboard | Space selects choices; Tab/Shift+Tab contain focus within help; Escape returns to the opener. Ordinary navigation and help retain notes/drafts. |
| Reset | Keep my guide receives initial focus; cancel preserves the completed guide, doctor note, and answers. Confirmed reset is covered by existing state tests. |
| Privacy and failures | Local guide answers work without conversation requests. Unknown typed questions show an honest unavailable state and Retry. Privacy answer has Daylight provenance. |
| Console | No application-origin JavaScript errors observed. Two unrelated Zotero extension connection errors were recorded. |

Text colors checked from the retained tokens: main text on paper 10.9:1, secondary text on raised paper 5.7:1, and primary-button text 9.4:1 (rounded; see computed values if tokens change). These spot checks are not a full contrast audit.

The frontend remains dependency-free with self-hosted fonts. No new animation, image requests, storage, or tracking was introduced. This was not a performance benchmark or a WCAG conformance assessment.

## Evidence and remaining checks

Screenshots: `outputs/daylight-finish-20261020/screenshots/`:

- `01-guide-320.jpg` — full narrow-page capture.
- `02-help-phone.jpg`, `06-focused-help-desktop.jpg`, `08-help-tablet.jpg` — focused answers.
- `03-checklist-desktop.jpg`, `04-checklist-tablet.jpg`, `05-checklist-phone.jpg` — checklist hierarchy and control sizes.
- `07-short-height-help.jpg` — reachable input at 422px height.

Before participant sessions, check the actual iOS/Android keyboard, touch behavior, and screen-reader speech on the devices participants will use. These were not available through desktop viewport emulation. Successful live replies and real plan comparisons also remain unverified: the local review preview serves the frontend without the API service. Acceptance gates were not bypassed and no records or live answers were fabricated. Print preview was exercised; the system print/PDF dialog was not submitted.

Use the approved 6–8 sessions to observe comprehension and recovery: explain A/B, open and identify an answer, ask a follow-up, return and correct an answer, distinguish reported facts from checks, and find the printable next action. Participant feedback is still necessary; passing these checks does not establish that the UI is usable for every older adult.

Baseline references: [W3C older users](https://www.w3.org/WAI/older-users/) and [COGA usable content](https://www.w3.org/TR/coga-usable/). The original independent critique remains historical evidence; no new usability score is claimed.

Hook triage: no new suppressions. Existing scoped Fraunces and cream-palette exceptions retain the owner-approved identity. Real findings addressed here include hidden questions, competing scroll surfaces, clipped short-height controls, oversized final actions, and narrow overflow. No unrelated historical findings were treated as regressions.

Backups of the pre-finish frontend and product files are in `outputs/daylight-finish-20261020/before/`. The local preview remains at `http://127.0.0.1:8766/`; temporary viewport overrides and native Chrome zoom were reset. One finished preview tab was kept; the duplicate test tab was closed.
