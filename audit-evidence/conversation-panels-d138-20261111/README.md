# D138 conversation-to-panels fixes, first increment

November 11, 2026 · Implements part of the [fix plan](https://docs.google.com/document/d/1ibQPr1Jsd5M6ZhWYBq46BV6SsPfaXSvPCVg6JV0KHGE/edit)
written after the six owner-cleared live conversations of November 10. This is
not acceptance. No live model conversation was run on this revision.

## Owner direction

"okay excellent. implement." with three answers: the chat may relay what the
Plans tabs can show (yes), people about to turn 65 are priced at 65 (yes), and
2027 Part D data is not loaded for the pilot (no).

## What changed

| Area | Change | Files |
|---|---|---|
| Capture | Age is judged by the words around the number, so "I'm 66 and I'm retiring next month" and "I was 66" are recorded. "I'm a woman" / "I am a man" report the sex category. "I don't smoke", "never smoked" and "non-smoker" report Non-Tobacco; "I'm a smoker" reports Tobacco User. Quitting, former use, names, pronouns and questions still establish nothing. | `medigap_profile.py`, `natural_agent.py` (interpreter instructions, question check) |
| Age question | "How old are you?" replaces "How old were you on November 10, 2026?". The reported age is matched to the dated price list. | `medigap_profile.py` |
| Turning 65 | A reported age of 64, or a 65th birthday in November or December 2026, is shown the listed age-65 prices with a visible note. Ages under 64 stay unsupported. | `medigap_profile.py`, `web-8894/medigap-plans.js` |
| Model is told what the tabs show | Every v3 composition context carries `plans_pages`: each tab's status (ready, missing, unsupported), the details still needed and any message. Status only; no rate, plan name or count enters model context (D129 unchanged). | `natural_flow.py`, `natural_agent.py` |
| Reply guard | A reply that says prices or plan listings are unavailable while that tab is ready, and does not point to the tab, is rejected and recomposed (`false_unavailability`). | `natural_agent.py`, `composition_recovery.py`, `natural_flow.py` |
| Route into the tabs | Naming the product is enough to start its route: "supplement plans", "Plan G", "drug plan", "Part D". The earlier rule needed the word Medigap plus a price word, and Part D had no conversation trigger. Medigap goes first when both are named. | `natural_flow.py` |
| Landing tab | The Plans page, including "See plans" after the review, opens the Medigap or Part D tab when that is what the conversation is about. | `web-8894/plans-workspace.js`, `web-8894/advisor.js` |
| Buttons in the conversation | "See your Medigap prices" and "See your Part D drug plans" appear when those tabs are ready. | `web-8894/advisor.js` |
| One journey | "Next: see Part D drug plans" on the Medigap tab and "Back to Medigap prices" on the Part D tab. | `web-8894/plans-workspace.js` |
| AI paused | While AI replies are paused, a bare ZIP or age that answers the question on screen is recorded without a model call. | `natural_flow.py` |

## Checks actually run

Offline, scripted transport, no network or model billing, in a Linux VM against the working tree:

- `test_d138_conversation_panels` (new, 6 tests), `test_medigap_profile` (14, three new), `test_medigap_pilot`, `test_medigap_profile_http`, `test_part_d_pilot`, `test_natural_agent`, `test_composition_recovery`, `test_persona_capture_regressions`, `test_plans_workspace`: all pass.
- `test_natural_flow`: 1 failure, `test_pending_ambiguity_does_not_leak_to_another_visit_with_matching_versions`. It fails identically on the files as they were before this change.
- Node: `test_medigap_view.js`, `test_part_d_view.js`, `test_plans_handoff.js`, `test_utility_buttons.js`, `test_ai_send.js` pass.
- The complete regression suite was not run.
- In the built-in browser on :8894, with no AI call: the page loads with no console errors, "Talk to Daylight" on the Medigap tab opens the conversation, and the Plans button then opens directly on the Medigap tab.

Two existing expectations in `test_medigap_profile.py` were changed to the new direction: the age question no longer mentions November 10, and "I do not smoke." is now accepted.

## Activation

The D137 brand-restore session restarted :8893 and :8894 at about 11:48 UTC on
November 11 while this work was in progress. Its tested source hashes included
every backend change listed here, so these changes are running. Comment labels
were renumbered from D137 to D138 after that restart; no behaviour changed.

## Second increment (later on November 11)

Owner direction: continue with the remaining items; the tobacco category is
about tobacco, not smoking; check that the CMS pre-enrollment topics are always
covered; age matching is not a concern for the pilot.

| Area | Change | Files |
|---|---|---|
| Tobacco | Reverted the first increment's smoking synonyms. "I don't smoke" and "I'm a smoker" record nothing. The question is now "Do you use tobacco of any kind?"; "I don't use tobacco" and a plain yes or no to that question record the category. The composer is told not to call this a recording problem. | `medigap_profile.py`, `natural_agent.py` |
| CMS checklist | New deterministic account of the twelve items, returned on every v3 turn and shown in "Review your info". Six items have no complete reviewed content; see [the check](cms-checklist-check.md). | `cms_checklist.py`, `natural_flow.py`, `web-8894/advisor.js` |
| Medigap tab | "Plan letters at a glance" (count and listed range per letter, with a button to filter); Plans C, F and high-deductible F marked as only for people eligible before January 1, 2020; an underwriting notice taken from the reviewed `ma_trial_right` statement. | `web-8894/medigap-plans.js` |
| Monthly total | "Use in my monthly total" on a Medigap rate and on a Part D plan; both tabs show the two listed premiums and their sum, with what is not included. Visit-only and display-only. | `web-8894/medigap-plans.js`, `web-8894/part-d-plans.js` |
| Part D cards | The source plan ID moved from the card to the source details. | `web-8894/part-d-plans.js` |
| Review screen | The current-insurance row no longer says "(Parts A and B)" when the person reported one part or none; routing answers such as "details" are not read back; a typed month name is capitalized. | `natural_flow.py`, `web-8894/advisor.js` |
| Paused wording | Budget and pricing-review messages are replaced with one plain sentence for the participant. | `web-8894/advisor.js` |
| Start over | "Start over" in the privacy panel when saving is off, with a confirmation. | `web-8894/advisor.js` |
| Log timestamps | Warning lines carry a UTC time. | `log_guard.py` |

Checked offline and found already resolved by the first increment: with the
Medigap or Part D route set, the next questions are timing and current coverage
(Medigap) or medicines (Part D); doctors and travel are not asked.

Not a defect after all: the hidden model picker defaults to `gpt-6.1-sol`, which
`model-routes.json` names as the model that ships to the pilot. `/api/status`
reports the default agent (`gpt-5.4`), not the model a turn uses.

### Checks actually run for the second increment

- `test_d138_conversation_panels` (11 tests), `test_medigap_profile` (16),
  `test_medigap_profile_http`, `test_part_d_pilot`, `test_content_free_logs`: pass.
- `test_natural_flow`: the same single pre-existing failure.
- Node: `test_medigap_view.js`, `test_part_d_view.js`: pass.
- A wider pass of 52 further test modules (657 tests) found failures in `test_button_backend_gates` (7), `test_curriculum_flow` (4), `test_education_lifecycle` (4), `test_advisor_budget` (1), `test_advisor_models` (3) and `test_comparison_http` (setup). The first three were re-run with this work's backend files swapped back to their earlier versions and failed identically, so they predate it. `test_persona_journeys` fails in setup the same way before and after. The budget, model and HTTP errors were not compared.
- About 40 test modules were not run (they exceed the session's time limit per command). No live model conversation was run.
- These backend changes are not active until :8893 is restarted.

## Third increment: the fixed "Before you enroll" step (November 11)

Owner direction: add a fixed step that shows all twelve reviewed statements and
records the time, with the conversation count as supporting evidence. Owner
sign-off on the six new statements, the Plans C and F wording and the
underwriting notice: "Okay, I sign off now."

- `pilot-rules-r3-cms-checklist.json` holds the six statements, `owner_accepted_2026-11-11`. Each was checked against the Medicare.gov or CMS page it cites on November 11. An independent reviewer has not checked them.
- `cms_checklist.before_enroll()` returns the twelve topics, each with its reviewed statements, a completeness flag and a digest of the exact wording.
- Two turn actions, `before_enroll_open` and `before_enroll_ack`, return the step and record when it was shown and acknowledged for the visit. No model call and no profile change. Acknowledgement is refused if any topic lacks a statement. The times are visit-only until enrollment records exist.
- :8894 opens the step from "Review your info" and from the Plans page header. Topics that also came up in the conversation are marked.
- Tests: `test_d138_conversation_panels` now has 13 tests. Suites re-run after this increment show only the failures that predate this work.
- Whether this step satisfies the CMS "discuss" requirement remains a counsel question.

## Live rerun, first profile only (November 11, about 9:15 am ET)

Owner-cleared. Run on the backend as restarted at 14:00:43 UTC, which had the
first and second increments but not the "Before you enroll" actions. One
profile (66, 34102, female, non-tobacco) was run; cost $0.44 over 18 model calls.

- Worked: "I'm a woman." was recorded; the tobacco question read "Do you use tobacco of any kind?"; "I don't smoke." recorded nothing and the tobacco question was asked again; "No, I don't use tobacco." was recorded; the reply then said the Medicare Supplement (Medigap) tab now lists premiums; "See your Medigap prices" and "See your Part D drug plans" appeared in the conversation; the Medigap tab opened on 178 rates with the letter overview, the Plans C and F note and the underwriting notice; the monthly total added one Medigap rate and one Part D plan.
- Regression found: four of nine replies failed with "I couldn't finish that answer". The log shows `ungrounded_literal` and `ungrounded_entity`. The model was told to name the tab and the pilot scope, but the grounding check did not count that service-supplied wording as a source. Fixed in `natural_agent.py` (the Plans-page status and the Medigap scope are now grounding sources) with a test that reproduces the failure. Not yet active; needs a restart.
- Still wrong: "who is this for" was asked after a first-person opening, and the age in that opening was not kept because it arrived before that answer; the doctors question was asked after Medigap prices were ready.
- The other five profiles were not run, to avoid paying for replies the regression would fail.

## Still open

- Listed amounts relayed in the chat as a software lookup. It crosses the D129 boundary and the reply-grounding checks and needs its own design.
- Independent reviewer check of the six owner-accepted checklist statements; counsel's view on the "discuss" standard.
- A recorded coverage-path field. Routing uses the conversation task.
- One-line descriptions of each plan letter; grouping of rating classes; the Part D "Actuarially Equivalent Standard" label.
- Tap-to-send consistency; the stale draft notice.
- A warning before the pricing review expires.
- Reviewer confirmation of the Plans C and F wording and the underwriting notice placement.
- The six-profile fixture set and scorecard runner; the live release gate.
