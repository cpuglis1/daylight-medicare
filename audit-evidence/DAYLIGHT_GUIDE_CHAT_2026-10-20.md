# Daylight: visual teaching and Ask Daylight

The owner likes the journey flow but found the visual guide and Ask Daylight harder to find and less helpful. This pass preserves the journey and addresses D07, D25–D28, with D01–D02, D08, D19–D24 as constraints. It does not replace the visual identity or change backend acceptance gates.

## What changed

- Arrival now shows the coverage picture alongside the guided start, with Ask Daylight visible in the header and lesson.
- Questions have a relevant visual lesson beside the task on desktop/tablet. Phones show a compact explanation near the question, explicit access to the full picture, and Ask Daylight. Deeper teaching follows the task.
- Part A, Part B, coverage-route, drug-coverage, and Medigap blocks open matching explanations in the conversation panel. Exploring a picture does not select a personal answer or advance the journey.
- Chat has a visible transcript, labeled question field and Send/Close controls, contextual suggested questions, source links, and the relevant picture in guide answers. Suggested follow-ups collapse after the first question to leave room to read the conversation.
- Common guide questions work when typed or tapped without a live service. The interface labels them as guide explanations. Unsupported questions use the existing live-service path and show an honest unavailable state when it is disconnected; they are not answered through guessed keyword matches.
- Phone chat has protected focus and background scroll locking. Resizing between phone and desktop updates modal/background behavior. Closing chat returns focus to its opener.
- Existing A/B detail, cost illustration, foundation explanation, full route comparison table, dates, checklist, catalog behavior, and notes remain. Duplicate route-picture instances were consolidated around the new contextual lesson; useful detail was retained.

`PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md`, and `AGENTS.md` record this balance. D25–D27 reflect the latest owner feedback; D28 records the implementation safeguard for truthful service availability. The earlier rule placing all teaching below the complete task was refined rather than used to bury the guide again.

## Observed behavior

Used Chrome against `http://127.0.0.1:8766/` at 1440 × 1000 desktop, 1024 × 768 tablet, and 390 × 844 phone; also restored and checked the ordinary 1501 × 708 viewport. No horizontal page overflow was observed. Temporary viewport overrides were reset.

- Opened Ask Daylight on arrival and from a question/diagram. Typed Part B and Part D questions returned the correct source-linked explanation and picture.
- A doctor-participation question showed the disconnected live-service state rather than an invented answer.
- Selected Part A only, opened/closed chat, and continued the same journey with that selection intact.
- Walked through job coverage, birth timing, medicines, extras, priorities, coverage route, disconnected catalog, final map, and HTML print preview. The synthetic medicine note remained in the checklist and preview. Route choices remained unanswered until explicitly selected.
- Confirmed one primary Continue on guided question states. Opening chat did not advance a question or select a route.
- On phone, checked the compact teaching summary, full-screen conversation, typed drug question, readable drug diagram, and return to the same question/note. With chat open, resizing to tablet removed modal background restrictions; closing returned normal interaction.
- Browser logs contained only unrelated extension connection errors; no app-origin JavaScript exception was observed.

All personal inputs were synthetic. No paid model calls or real personal data were used. The isolated review tab was reloaded to clean arrival after verification; the user's original tab was not reset.

## Verification

- JavaScript syntax check passed.
- Frontend journey checks: 41 passing, including topic matching, avoiding personal-decision keyword guesses, local typed replies, bounded explicit conversation history, modal behavior, and reset behavior.
- Existing backend smoke checks: 45 demo tests and 14 Naples MVP tests passed.
- `git diff --check` passed.

These checks supplement the rendered walkthrough and do not establish owner approval of the design.

## Review artifacts

Starting frontend files: `outputs/daylight-guide-chat-20261020/before/`.

Screenshots in `outputs/daylight-guide-chat-20261020/after/`:

- `desktop-arrival.jpg`: the restored coverage picture and visible Ask Daylight.
- `desktop-lesson.jpg`: current question paired with its visual teaching.
- `desktop-chat.jpg`: the question remains alongside an actual conversation panel.
- `tablet-lesson.jpg`: paired lesson at tablet width.
- `phone-question.jpg`: compact teaching and labeled help near the question.
- `phone-chat.jpg`: focused drug-coverage picture in the conversation.

## Concrete limits

This preview is served by the existing static server. Open-ended generated replies and live plan records remain unavailable. Source-linked guide answers are usable locally, and live unavailability is displayed explicitly. No release approval or consumer-acceptance record was fabricated or changed. OS printing/PDF output was not exercised; the HTML preview was verified.

Coverage explanations were checked against Medicare.gov's coverage-options page and Part D page:

- https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options
- https://www.medicare.gov/health-drug-plans/part-d

## Design-hook triage

The earlier seven findings were resolved in the restoration pass: functional small text enlarged, thick side accents removed, and the incumbent Fraunces retained with an existing narrow value exception for the two frontend files. This pass added no suppression and left no new reported finding unresolved. The existing typeface and palette were preserved intentionally.
