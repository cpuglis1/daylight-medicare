# D131: Medigap details stay in the conversation

Implemented November 10, 2026. The existing local :8894 server serves all four
changed UI assets; [read-only verification](live-assets.json) confirms exact
source hashes at 20:52 ET. No backend restart or hosted deployment was needed.
An already-open browser tab needs a refresh to load the changed JavaScript;
no user's tab, draft or stored profile was refreshed or altered by this work.

## Scope and behavior

Addresses D131, refining D130's presentation while retaining D49/D54/D64/D86,
D129's source-price scope and the existing MA/Part D behavior. CAP-01, CAP-02
and CAP-06 feature notes link this packet.

- Missing Medigap details show “Considering Medigap?” and “Talk to MidMorning,”
  not a duplicate form, select menu or pricing-entry submit button.
- The button uses the existing free Medigap task action and opens the existing
  conversation at its current missing detail. It neither sends invented user
  words nor consumes an unsent draft. Focus moves to the question, not the
  keyboard. No AI call is made just to navigate.
- Existing chat answer buttons, optional free text, purpose explanations,
  unknown/defer choices and deliberate Send remain. Already shared reports
  are reused; no new question meanings, extraction rules or age buckets.
- “Your pricing details” remains inspectable. Its edit buttons open the
  corresponding chat question. Explicit unknowns are not automatically reasked;
  the person can deliberately reopen one for correction.
- Complete profiles continue to load exact source prices immediately. Profile
  changes clear stale prices and comparisons; errors retain a deliberate retry.
  ZIPs 34101–34108, ages 65–74 and November 10, 2026 remain exact. The 75+
  unsupported message and source qualification/eligibility limits remain.
- Backend capture, optional sensitive saving, AI permissions, stored source data,
  the original 41 meanings and source STOPs are unchanged. No acquisition resumed.

## Checks actually run

All conversation inputs and browser prices were fictional. Preview servers used
temporary stores, fixture mode and the fictional repository; no live model tests
or paid probes were run.

| Check | Exact command | Result |
| --- | --- | --- |
| Source-price endpoint, shared profile, free entry, unknown/edit, initial HTTP and save/privacy boundaries | `infrastructure/daylight-data/.venv/bin/python -m unittest discover -s alternatives/advisor-first/tests -p 'test_medigap*.py' -q` | [20 passed](medigap-tests.log) |
| Invitation without a form, routing callbacks, automatic prices, delayed results, retry, 75+, comparison and handoff | `node --test tests/test_medigap_view.js tests/test_plans_handoff.js` from `alternatives/advisor-first` | [9 passed](frontend-tests.log) |
| Existing MA profile-filter behavior | `../../infrastructure/daylight-data/.venv/bin/python -m unittest discover -s tests -p test_plans_filters.py -q` from `alternatives/advisor-first` | [4 passed](plans-filter-tests.log) |
| Syntax | `node --check` for `advisor.js`, `plans-workspace.js`, `medigap-plans.js` in `web-8894` | Passed |
| Protected source | SHA-256 comparison against [task baseline](before.json) | [392 unchanged](verification.json); previous backend source hashes also unchanged |
| Local delivery | Four static GETs from :8894 | [All equal final source](live-assets.json) |

The broader natural-conversation suite was not rerun because backend behavior
was unchanged. Its previously reproduced unrelated visit-history failure remains
recorded in the [D130 packet](../medigap-chat-profile-20261110/README.md); this task
does not claim that suite passes.

## Rendered observations

Inspected the real app UI with [a disposable fixture server](preview.py) at
1280×900 desktop, 768×1024 tablet and 390×844 phone. No document-level horizontal
overflow. The main CTA uses the existing olive action style, 18px type and 54px
height. Chat choices remain unselected initially, have 52px targets and retain
visible question/reason text and keyboard focus. No console warnings/errors
were observed in either preview.

Verified direct landing → Plans → Medigap → Talk to MidMorning. A partial
profile with known ZIP, age and pricing sex opened only the tobacco question.
An unsent draft survived this route, and no invented chat history appeared.
After an explicit chat answer, opening Medigap showed matched fictional prices.
A pricing-sex edit returned to its chat buttons; the next view showed the
corrected Male profile. Fresh-profile entry opened “Who is this for?” before
asking personal pricing details. The existing Back action still focused the
composer. All temporary tabs/listeners were closed and viewport override reset.

Screenshots: [desktop invitation](screenshots/desktop-invitation.jpg),
[tablet chat buttons](screenshots/tablet-chat-buttons.jpg),
[phone invitation](screenshots/phone-invitation.jpg),
[phone answer buttons](screenshots/phone-chat-buttons.jpg),
[matched fictional prices](screenshots/desktop-matched-prices.jpg),
[fresh-profile entry](screenshots/fresh-profile-chat.jpg).

## Change identity and limits

[Task diff](change.diff) and [source hashes](source-hashes.json) identify the
four frontend files, two test files and direction/feature documentation.
Before/after copies are retained privately under
`infrastructure/daylight-data/.state/csg-medigap/2026-11-10-conversation-entry-r1/`.
No unrelated uncommitted work was discarded, and no commit or push was made.

Technical verification is separate from owner approval of every wording,
participant comprehension, live-model conversational quality and independent
source/method acceptance. These checks do not establish an insurance
recommendation, eligibility or a binding quote.
