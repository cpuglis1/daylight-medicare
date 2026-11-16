Daylight follow-up to D164: enrollment record v2, doctor candidates, top options. You own the backend and data layer. Claude owns the front end, the conversation and profile capture, and is waiting on items 1 to 3 before building. :8895 only.

READ FIRST
- Daylight Brain (Google Drive > Daylight > Daylight Brain): AGENTS.md, 02 UX playbook (principles 2, 4, 8, 9; issues 32 to 44), Decisions (2026-11-13), Open questions C32 to C35. If anything in this prompt conflicts with the Brain, stop and tell me.
- Repo ~/daylight: docs/planning/medicare-enrollment-2026-11-12/DESIGN_2026-11-13.md (approved November 13), ENROLLMENT_RECORD.md (your v1 contract), audit-evidence/enrollment-d161-20261112/LEDGER.md (handoffs A to E and the November 13 quick fixes).

WHAT HAPPENED
I ran one live conversation on :8895 as a person who turned 65 on October 20, 2026, has coverage through his own current job, and retires at year end. Four things traced back to the data layer:
- After "I just called and finished my application", the next step still read "confirm your sign-up timing with Social Security". The held situation (coverage from current work) overrides every report.
- "Retiring at EOY" was said twice and nothing usable was kept, so Daylight could not even repeat the date back.
- "Dr. Smith in Naples" returned one candidate: STEPHEN E SMITH MD, 4225 EVANS AVE, FORT MYERS, FL, 339019311.
- The conversation ended with "Ready to review your info?" instead of the top options and why.

OWNER DECISIONS (November 13)
- The design is approved as written and its wording is signed off. Claude owns every sentence a person sees. Return ids, states, dates and amounts, never prose.
- Closing summary rule. For someone who said predictable costs matter more: Medigap Plan G first, Plan N beside it as the lower-premium option. The company is the lowest listed premium for that letter at the person's age, sex category, tobacco category and ZIP. It is described as "lowest listed premium", never "best" and never "recommended". Part D is always addressed; a plan is named only when the medicine check against each drug list has actually run. The doctor line is "accepts Medicare" for Medigap; "in network" only for a Medicare Advantage plan that was actually checked.
- There is no rule yet for someone who leans Medicare Advantage. Do not invent one.

BUILD (fixed list)

1. Reports before the held step (enrollment_journey.status).
   Today `if unsupported:` sets `route` and `next_step` to `confirm_with_social_security` before any report is considered.
   Change: when an unsupported reason is present and no part is `needed` or `unknown` (every part is active, pending, approved_future or needs_info), `next_step` follows the reports in your existing order (answer_request, confirm_start_date, wait_for_decision, confirm a future approved start) and `route` is `none_needed`. `unsupported` is still returned unchanged. Computed starts and next-action dates stay suppressed. A denial keeps `confirm_with_social_security`. If any part is still needed or unknown, today's behavior stands.

2. When coverage from current work ends (enrollment_journey.status).
   Add one key, `coverage_end`: null, or `{"date": "YYYY-MM-DD", "precision": "day" | "month", "basis": "reported", "source": "<which report>"}`.
   Read it from the reports that already exist: RC11 `coverageEnd`, else RC11 `jobEnd`, else the retirement situation (S_RETIREMENT). A month-only report is the last day of that month with precision `month`. It is reported only, never estimated. It does not lift the current-work hold, does not compute a Part B date and is never a deadline. Tell Claude exactly which reads you used, so capture of "retiring at the end of the year" can be made to land there.
   Version becomes `enrollment-journey-v2`. Every other key and value is unchanged from v1.

3. Doctor candidates (the search behind conversation_checks, and its data).
   When the person states a place: return up to five candidates; each office carries its city and `place_match` true or false against the stated place; matches come first; a sole candidate from another town is returned flagged, never as an unqualified match. Return address parts (line, city, state, zip5, zip4) so the view can write them normally. Tell me whether the retained directory holds other Smiths in Naples: I need to know if this was a search fault or a data gap. Claude changes the question labels and the card; do not change what the person reads.

4. Top options for the closing summary (new pure function, your naming; suggested `closing_options.status(flow, guide, record, today=None)`, version `closing-options-v1`).
   Inputs: existing reports and the Medigap rates already served to the Plans page. No model, no network, no persistence, no mutation.
   Output for the Original Medicare lean:
   - `basis`: the reported preference and priorities it rests on (ids, not sentences).
   - `medigap`: `status` (ready, missing with the still-needed detail ids, unsupported), then `first` = letter G and `alternative` = letter N, each with company, rate id, monthly cents, the rate's date, and how many companies list that letter. Lowest listed premium; ties broken by company name. Plans the person cannot buy are left out by the existing eligibility filter and counted.
   - `part_d`: `{"address": true, "named": null, "reason": "medicines_not_checked"}` until the drug-list check runs; say what it would take to name one.
   - `doctors`: for each reported doctor, the existing evidence state for Original Medicare (accepts, may accept, unknown) and the record date.
   For a Medicare Advantage lean return `null` with reason `no_rule_yet`.
   Commission and any carrier payment data are never read. If a Medigap price is missing, nothing in the output points toward Medicare Advantage.

NOT IN THIS BUILD (tell me what each would take; do not start)
- Handoff A: an explicit report that Social Security is enrolling the person automatically.
- Handoff B: the chosen Medicare Advantage plan and its drug check in the record (today they live in the browser tab only).
- A per-visit usage ledger: one row per model call with visit id, turn, provider, model, tokens, estimated cost, purpose and outcome; no message text. Today the ledger has day and model only, and the daily meter re-counts old unsettled holds (32 OpenAI, 5 Anthropic from November 4 to 5).

RULES
- Code computes every date, status and amount; the model explains. An estimated date is never shown as confirmed; a reported one is labelled reported.
- Never ask for or store an SSN, Medicare number or password. Never say an application was sent, approved or in effect unless the person reported it.
- Missing Medigap prices never steer toward Medicare Advantage. Every plan stays visible. Commission data never enters the model or the sorting.
- :8895 only. Tell me before anything changes what :8894 shows. Protected variants :8890, :8891, :8896 untouched.
- The repo has a lot of uncommitted work. Targeted patches only; never reset, stash or discard. Commit only when I ask.
- Do not edit the files Claude created (enrollment_flow.py, enrollment-content.json, web-8894/enrollment-view.js, web-8894/enrollment.css, tests test_enrollment_flow.py, test_enrollment_http.py, test_enrollment_view.js) or Claude's D161 edits in ux_flow.py, natural_flow.py, server.py and the web-8894 files plans-workspace.js, medigap-plans.js, advisor.js and conversation-checks.js. If one needs to change, say what and why.
- Ask me before any computer-access session (restarts, browser checks) and before any live model run.
- Keep to this list. If something takes much longer than expected, stop and tell me why.

FINISH WITH
- ENROLLMENT_RECORD.md updated to v2: the exact output for my test person before and after "I applied", and the list of reads.
- The contract for item 4 with one exact example, and for item 3 the new candidate shape.
- What Claude must change to adopt each item (key names, version check, call sites).
- Tests run with counts, offline and fictional; what was not verified.
- A ledger: each item Done (how checked), Handoff, Needs Chris or Blocked.
