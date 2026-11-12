# Daylight Medicare user walkthrough — October 20, 2026

The education sequence makes sense: dates → Parts A/B → prescriptions → extras → coverage paths → plans → next steps. The app does **not** currently complete that journey reliably. Its central plan comparison and custom chat fail, and several answers are mapped to conclusions the user did not give.

I tested the app through Google Chrome at `http://127.0.0.1:8766/`, clicking controls and reading their rendered results. Inputs were synthetic. I did not edit application code or make an enrollment decision.

The server stopped responding during the session. The initially loaded page said “See your Medicare clearly.” The fresh page after service returned said “Medicare, in plain daylight.” Findings below are confirmed in the fresh version unless explicitly labeled otherwise. The quick entry improved in that version: it now starts at the coverage-path step. The earlier quick-entry behavior is not treated as a current defect.

| Priority | Finding | User consequence |
|---|---|---|
| P0: blocks this demo | Plan catalog and custom chat receive HTML instead of usable API responses | No plans, no usable custom answers, no completed comparison |
| P1: incorrect guidance | Medigap dates are calculated without a Part B start date | A user can believe an enrollment opportunity has already expired |
| P1: incorrect answer mapping | Prescription “I'm not sure” becomes “You said no” | The guide changes an unknown into a negative answer |
| P1: navigation dead end | County “I'm not sure” becomes “Outside our data,” with no correction control | A supported user can be locked out of comparison |
| P1: misleading completion | Skipped and failed work gets completion checkmarks and “Your shortlist” | The map suggests work was completed when it was not |
| P1: missing task outcome | The job-coverage shortcut does not produce the promised transition checklist | A user still lacks the dates and actions needed when work coverage ends |
| P2: decision support gap | Doctor/travel priorities are collected but their underlying evidence is unavailable | The ranking promise exceeds the fit that can be established |
| P2: lost user work | Doctor checklist text disappears after navigation | Returning to the map loses a user's entry |
| P2: weak next action | Free help/enrollment is described but not linked from the main map | A user must discover a help question to obtain phone numbers |

**1. Plan comparison and custom chat are broken in the running configuration.**

Reproduce: choose the quick comparison entry → continue through priorities → choose Original Medicare or “Not sure, show me both” → enter `34102` → choose “Yes, Collier County.” Both routes produce `Unexpected token '<', "<!DOCTYPE "... is not valid JSON` instead of plan results. A newly typed Ask Daylight question produces the same error. Reviewed question buttons still work.

Read-only process inspection showed port 8766 running `python3 -m http.server ... --directory .../cms-slice/apps/chat`. That serves the frontend files without the application API. This is strong evidence for the current integration failure, rather than evidence that every underlying catalog function is broken. The documented packaged application launch also failed with `Demo runtime changed since release; build a new release: apps/chat/app.js`. A workspace launch attempt did not replace anything; it exited because the port was already occupied.

Run the application backend with a compatible frontend/release, then retest. The UI should also show a plain-language service error with retry/recovery, and should not claim plans are ranked when no results loaded. I did not rebuild a release, replace the running server, or bypass data validation.

Evidence: [plan error screenshot](12-plan-loading-final.jpg), [rendered plan page](12-plan-loading-final.txt), [custom chat error](06-current-chat-json-error.jpg).

**2. Exact Medigap dates are guessed from turning 65.**

Reproduce: full journey → “Someone I'm helping” → “Only Part A so far” → January 2025 → Continue. The page says it needs to know whether the person has Part B, while also displaying `Medigap window January 2025 - June 2025`. The user has explicitly said Part A only. The app has not collected a Part B effective date.

Medicare states that the federal six-month Medigap enrollment period begins in the first month a person has Part B and is at least 65. A birth month alone cannot establish that window. [Medicare: Get ready to buy Medigap](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy).

The same page calls October 2024–April 2025 “TODAY'S FOCUS,” even though this walkthrough took place in October 2026. It presents a past initial enrollment window instead of resolving the person's current situation. The date selectors offer only 2025–2028, so a Part A-only person who turned 65 earlier cannot describe that fact accurately. The caregiver path also switches to “What month and year do you turn 65?”

Collect the facts needed for the specific window. Keep unknown dates unknown. Distinguish past, current, and future windows, and handle people who are already older than the offered years.

Evidence: [current date screenshot](08-current-medigap-dates.jpg), [rendered date page](08-current-medigap-dates.txt).

**3. Prescription uncertainty is converted into “no.”**

Reproduce: at Prescriptions, choose “I'm not sure.” The selected answer remains visibly unsure, but the result says “Even with no medicines today” and the foundation map says “You said no.” This was reproduced in both the earlier loaded page and the fresh version.

Preserve yes, no, unknown, and unanswered as separate states throughout the map and any future filters. Unknown should prompt a medication-list task, not a no-medicines conclusion.

Evidence: [current screenshot](10-current-unknown-prescriptions.jpg), [rendered prescription page](10-current-unknown-prescriptions.txt).

**4. An uncertain county answer creates a correction dead end.**

Reproduce: enter `34102`, then choose “I'm not sure” about Collier County. The app shows “OUTSIDE OUR DATA.” The ZIP and county controls disappear. Clicking the Your plans navigation item leaves the same result. “See my plans again” also returns to the saved result rather than offering a location edit.

“Somewhere else” deliberately shows the out-of-area result; that is reasonable for a county-limited prototype. “I'm not sure” is different: it should help resolve the county. Provide Change ZIP / Change county / Back controls, and preserve an unresolved state until the user confirms it. State the Collier-only scope before the long questionnaire, rather than first disclosing it near the end.

Evidence: [current county dead end](11-current-unknown-county.jpg).

**5. The journey map confuses reaching a step with completing its work.**

The quick comparison route marks the earlier stages with checkmarks even though those questions were skipped. More strikingly, the employer-coverage shortcut jumps from the foundation to the final map and marks Prescriptions, Extras, Two paths, and Your plans complete. It labels the plan stage “Your shortlist” even though no plans were viewed or shortlisted. Continuing after a plan-loading error produces the same misleading sense of completion.

Track visited, answered, skipped, blocked, and completed separately. A shortlist label should correspond to saved plans. The final map should explicitly show unresolved tasks and failed services.

Evidence: [employer shortcut map](09-employer-checklist-mismatch.jpg), [final map after plan failure](07-final-map-after-plan-failure.jpg).

**6. The job-coverage shortcut does not deliver its stated task.**

Reproduce: Part A only → January 2025 → foundation → “Yes, coverage from a current job” → “Skip to my checklist for ‘when my job coverage ends’.” The result is the generic final map. It still features the past initial-enrollment dates and guessed Medigap dates. It does not ask when employment or coverage ends and does not build the promised transition schedule.

The employer-coverage explanation appropriately tells users to check with the benefits office and mentions employer size. However, “current job coverage” alone cannot support a personalized deadline. Medicare describes an eight-month Part B special enrollment period tied to employment/coverage ending and advises checking the employer's requirements. [Medicare: Working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65).

Either collect the necessary transition facts and produce the checklist or label the result as general questions to resolve. Avoid promising a personalized retirement checklist that the current result does not contain.

**7. The app asks about fit that it cannot yet establish.**

The path flow collects keeping doctors, travel away from Naples, monthly cost, and predictable bills. The earlier loaded full flow explicitly said the most important priority sets the order used to rank plans. The fresh quick flow still promises ranking by what matters most. Reviewed help says doctor networks are not in the data; the path explanation says travel rules are not scored.

Those limitations are stated, which is useful, but the opening and ranking language still suggest a more complete personal comparison. The app should explain which priorities actually change ordering and which remain unresolved. A doctor-first user needs an actionable way to verify their specific doctor and plan. I could not inspect actual ranking behavior, medicine matching, costs, or benefit detail because the catalog never loaded; this audit does not conclude those underlying features are absent.

The coverage-path illustration also says the user's 20% share is “replaced by a yearly out-of-pocket limit.” The later side-by-side is more accurate: Advantage still involves copays or coinsurance up to a limit. Use that clearer wording in the primary illustration. [Medicare: Costs](https://www.medicare.gov/basics/costs/medicare-costs).

**8. Doctor checklist text is not preserved.**

On the final map, enter a synthetic doctor name → blur the field → choose “See my plans again” → return through Next steps. The doctor field is empty. This was repeated with an explicit Tab before navigating. The visible field promises the entry stays in the tab, yet normal in-app navigation loses it.

Store the entry in the same session state as the answers, and include the value in the printable result. I did not verify printed output.

**9. Next steps and promises need tightening.**

The main map says “Get free help and enroll,” but has no direct counseling or enrollment link there. The reviewed “Who can help me enroll?” question does provide phone numbers for SHINE and Medicare, so help exists but is hidden behind discovery. Put the actual resources on the map and in its printout.

The landing page says seven short steps; the progress text says eight and numbers the first stage zero. Choose one understandable count. Caregiver pronouns also drift between “they” and “you,” including “They'll sign up yourself” in the earlier loaded version. The overall visual hierarchy is calm and the glossary is useful; the main issues are task completion and state fidelity rather than surface styling.

**Coverage and limits**

| Surface | What I exercised | Result |
|---|---|---|
| Landing | Both entry buttons, privacy disclosure, home link | Working; fresh quick entry correctly jumps ahead |
| Start | Self and caregiver choices; both reviewed help questions | Working |
| Timing | All five enrollment choices across the session; month/year controls; Continue with missing dates; unsure-date alternative; all three reviewed help questions | Date assumptions and caregiver wording problems |
| Foundation | All six glossary definitions; close and Escape; employer yes/no/unsure; employer shortcut; all three reviewed help questions; official source link | Controls work; shortcut outcome incomplete; source page loads |
| Prescriptions | Yes/no/unsure; all four definitions; all three reviewed help questions | Unknown incorrectly becomes no |
| Extras | Dental/vision/hearing, none, unsure; mutual exclusion; completion; chat shortcut; both reviewed help questions | Choices and disclosure controls worked |
| Coverage paths | Four priorities, a top-priority selection, all three leanings across the session; full side-by-side; all seven definitions; chat shortcut; all three reviewed questions | Coherent teaching; limitations prevent establishing personal fit |
| Plans | Blank ZIP validation; in-area and out-of-area ZIP examples; county yes/elsewhere/unsure; both definitions; all three reviewed questions; Original and both-path result loading | Backend failure; county correction dead end |
| Final map | Navigation back to plans; doctor text and return; Ask Daylight CTA; both reviewed questions; job-coverage skip | Lost doctor entry; false completion; weak main-page next action |
| Custom chat | Empty send; synthetic typed question before and after server returned; close/reopen | Empty send added no message; custom replies failed; reviewed answers worked |
| Print | Clicked Print my map in the earlier loaded page | Browser control stalled; native preview required unavailable macOS permissions; layout/output unverified |
| Keyboard/accessibility | Escape dismissal and focus return for glossary; skip link clicked | Limited spot check, not a full accessibility audit |

I cannot honestly claim every possible button was tested. Plan cards, plan details, shortlist selection, comparisons, medicine/formulary controls, result sorting/filtering, and any other controls conditional on loaded catalog data were unreachable. Print output also remains unverified. I left a Chrome tab showing the reproducible plan-loading error. No application fixes were made as part of this audit.

Recommended order: restore the actual backend/release pairing; fix date and unknown-state mapping; add answer correction and truthful completion states; make the final map actionable; then run the blocked catalog, medicine, comparison, and print workflows end to end.
