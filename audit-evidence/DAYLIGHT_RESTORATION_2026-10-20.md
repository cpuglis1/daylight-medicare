# Daylight: owner requirements and visual-guide restoration

## Confirmed direction

The owner explicitly chose **keep the journey and restore the visual guide** after reviewing the current implementation. Their review supersedes conflicting older design proposals.

`PRODUCT.md` records the audience, purpose, capabilities, limits, and confirmed journey. `DAYLIGHT_REQUIREMENTS.md` contains D01–D24, the running list of binding owner requirements. Root `AGENTS.md` and the README direct future agents to read them first. No replacement visual identity was selected, and init did not create DESIGN.md.

## Changes against the frontend present at the start of this turn

The starting files were preserved in `outputs/daylight-restoration-20261020/before/`. Changes were targeted; the preexisting dirty workspace was not reset.

| Owner requirements | Result |
| --- | --- |
| D01–D02, D20: restore useful visual teaching | Restored a visible coverage foundation, labeled hospital/medical illustrations, the three coverage gaps, the existing A/B detail grid, the existing cost illustration, a two-route coverage diagram, and the existing full comparison table. The personal timeline and final map/checklist remain. |
| D03–D05: identity and entry | Removed the duplicate arrival sun and repeated identity; tab title is Daylight with the existing sun favicon. The main action starts the guide; the shortcut explicitly addresses people who already understand their options. |
| D06–D09, D15: explicit controls and space | One prominent Continue on each guided question; Back is lower emphasis. Questions, choices, optional note inputs, and Continue precede supporting explanation. Replaced the ZIP screen's Check location plus Continue with one Continue, then an explicit county question. Split priorities, conflicting-priority selection, and route selection into separate tasks. |
| D10–D11: labeled, tappable controls | Preserved full-card answer targets and text-supported navigation. Close and Send in help now have visible words. Phone journey navigation wraps into a visible grid, with no horizontal swipe required to discover steps. |
| D12: no automatic answers | Removed the initial `leaning: unsure` choice. New personal questions and route choices are unanswered; explicit answers remain selected when revisiting. Answer selection no longer scrolls/focuses the explanatory payoff automatically. |
| D13–D14: progress and repeated context | Progress uses consistent one-based numbering and names the current question within a stage. Unknown birth timing stays an open check. Removed the repeated Collier paragraph from each intake screen; scope is stated on arrival and contextual confirmation occurs at the location/plan steps. |
| D16–D19: direct questions and clear behavior | Ask birth month and birth year; calculate the age-65 year internally. Preserve first-day-of-month handling, actual Part B date requirements, and an explicit unknown/different-eligibility path. No mandatory name/identity field was added. Disable UI animation and transitions. |
| D21–D23: retain useful work | Retain adaptive branches, entered notes, sources, date safeguards, API error recovery, catalog controls, and the final actionable map/print preview. Backend evidence and acceptance code was left in place. |

## Visual and interaction verification

Used Chrome against the existing local app at `http://127.0.0.1:8766/`. Tested the ordinary desktop viewport (1501 × 708), tablet (1024 × 768), and phone (390 × 844). Temporary viewport overrides were reset.

- Walked the complete beginner path using synthetic input, including ZIP/county, current coverage, birth month/year, medicines, extras, multiple priorities, first priority, route selection, disconnected plan service, final checklist, and print preview.
- January 1962 produced a January 2027 age-65 month and an October 2026–April 2027 initial window when the birthday was not on the first. No arithmetic was requested from the person.
- Confirmed one Continue action and zero selected answers on fresh route questions. Confirmed the priority grid renders in two columns on desktop and the page does not overflow horizontally at tablet or phone widths.
- Confirmed a synthetic medicine note survived forward navigation, appeared in the final checklist and print preview, and was retained when returning to the medicine step.
- Walked the experienced comparison shortcut for a caregiver; it asks for the beneficiary's ZIP and leaves skipped guide steps unanswered.
- Walked the unknown-birth-date caregiver path; it remains usable without producing an exact personal deadline.
- Opened help and checked visible Close/Send controls. No typed conversation was submitted.
- Inspected the restored diagrams at reading size. Browser log inspection showed unrelated extension connection messages; no app-origin JavaScript exception was observed during these walkthroughs.

Screenshots are in `outputs/daylight-restoration-20261020/after/`: phone arrival, phone guide, phone checklist, tablet guide, tablet foundation detail, and desktop priorities. The checklist capture contains explicitly synthetic test input.

## Automated verification

- `node --check cms-slice/apps/chat/app.js`
- `node --test cms-slice/tests/frontend/journey.test.cjs`: 34 passing tests, including actual-birth-year conversion, first-day timing, confirmed Part B dependence, unknown dates/progress, and fresh unanswered state.
- `python3 -m unittest discover -s tests -p test_demo.py -q`: 45 passing tests.
- `python3 -m unittest discover -s tests -p test_naples_mvp.py -q`: 14 passing tests.
- `python3 -m unittest discover -s tests -p test_consumer_acceptance.py -q`: 8 passing tests.
- `git diff --check` and product-record structure checks passed.

The test results supplement the visual walkthrough and content inventory; they do not establish owner approval of the design.

## Remaining concrete limits

The existing local server does not provide the live plan API. Real plan loading still shows a recoverable disconnected-service state. No acceptance record, immutable release, or backend gate was changed to make it appear available. Typed live chat was not submitted, and OS print/PDF output was not exercised; the HTML print preview was verified.

The earlier V0/V1/V7/V8 proposal inventory remains historical reference. This pass restores the foundation, route and cost teaching visuals and exposes the current comparison/timeline content; it does not claim that every visual proposed in every prior brief has been reimplemented. Future additions must preserve the new owner requirements and current factual safeguards.

## Stop-hook review

Reviewed all seven reported findings without treating unknown attribution as a new regression.

- Fixed the undersized Medicare brand descriptor (9px to 12px); also raised the related plan-type label from 10px to 12px. These address D09/D24 legibility requirements.
- Replaced the four thick side-accent borders on trust, warning, next-action, and source-tag styles with ordinary thin outlines. No content or interaction was removed.
- Retained the incumbent self-hosted Fraunces. Persisted an `overused-font=fraunces` value exception scoped only to `cms-slice/apps/chat/index.html` and `styles.css`, with the reason that this task preserves the existing identity. This is an agent decision based on the incumbent implementation, not a claim that the owner specifically approved that font. No whole-file or whole-rule suppression was added.
- Rescanning the two files returned `[]` with exit code 0. No reported finding remains unresolved.
- Verified the 12px brand label and absence of horizontal page overflow at desktop, tablet, and phone widths. No additional behavior tests were needed for these CSS-only refinements.
