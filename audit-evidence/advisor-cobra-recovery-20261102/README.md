# COBRA conversation correction

November 2, 2026 · D49/D50/D54/D55/D57/D73/D86 · :8893 only

The owner reported a conversational failure: a relative start preference was repeatedly requested as a calendar date, and COBRA was mislabeled as current work insurance. This packet retains fictional verification only; the customer's transcript was not copied into evidence or sent to the provider.

## Changes

- T04 accepts `after_coverage` as an open-ended desired-start preference, alongside the existing `soonest` and explicit-date choices. It supplies no calendar month, eligibility, safe delay or actual Medicare enrollment. An explicit later preference can refine it, and a change in current coverage invalidates the dependent relative preference. The existing 41 question meanings and profile paths remain unchanged.
- RC11 retains a stated month or month/day without supplying a year, accepts ordinal spelling, and treats compatible added precision as refinement. A conflicting month still needs clarification. Job and coverage ends, unknown/defer, person scope and provenance stay separate. Published source/personal-output gates remain held.
- COBRA and retiree end questions use their actual coverage labels, including recovery questions. A generated COBRA question cannot silently substitute current work insurance. Actual A/B status is available as a consequential timing candidate; its availability does not force intake or assume enrollment.
- The source-backed COBRA teaching and composition guidance explain the timing concern before demanding a preferred calendar date. Current timing context carries the already reported preference. The new source belongs to the existing current-coverage teaching concept; the 17 concepts remain.
- Request packing excludes source URLs, titles and display questions from model evidence copies, retaining evidence IDs, complete text and summaries. Server-side source records, validation, citations and display remain intact. Redundant extraction instructions were shortened; all 41 question-table rows retain their exact meanings and qualifiers. The 8,000-input/900-output limits, model/reasoning, two stages, permission, budget and no-retry policy are unchanged.

## Source review

The additive `cobra_timing` teaching fact was checked against [Medicare.gov working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65), its [COBRA page](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65/cobra-coverage), and the [SSA current-employment distinction](https://www.ssa.gov/faqs/en/questions/KA-02983.html). The warning about not waiting applies to people turning 65 who have not signed up; it is not a personal enrollment ruling or calculated effective date. No L01/L03 evidence, sealed revision, source acceptance or recommendation authority was changed.

## Verification and limits

Thirteen focused free tests cover relative preferences, month-only/ordinal dates, compatible refinement, real conflict, scope/negation, mixed unknown/known dates, dependent invalidation, COBRA question meaning and evidence packing. The final combined suite is recorded in `verification.json`; earlier failures and corrected snapshots remain in this directory.

The six-message fictional model check did **not** complete. The initial attempt stopped on an undiagnosed transport/format error; a diagnostic attempt found an input-ceiling failure. After packing/instruction changes, three turns completed, and turn four retained the relative preference with no invented date or repeated start question, but the generated prose was withheld by the proper-name guard. These are failed journeys, not successful closure or consumer-comprehension evidence. Detailed results and all charge/hold receipts are preserved separately.

The [final targeted live preference check](preference-live.json) used explicitly seeded fictional reports. GPT-5.4 returned a complete source-grounded explanation of the preference and COBRA timing, with **no follow-up question**; the preference and month-only end remained intact. It is one targeted check, not a six-turn reliability result. The full generated sequence and the undiagnosed prior name-guard failure remain limitations. No automatic paid retries were added.

The only failing assertions in the first 795-test snapshot expected the previous deterministic recovery order. Keeping RC04 as a lower-priority eligible candidate preserves that recovery order; the eight affected provider HTTP tests then passed. The earlier 793-test run also exposed the missing primary teaching-receipt mapping for the additive source; the mapping was added rather than relaxing the assertion.

Protected frontend/styles/assets, shared engine, model and budget files are checked against `protected-before.json`. No browser replay of the changed conversation was performed; existing rendering tests are part of the suite. Local activation/status are recorded in `activation.json`. Process restart clears temporary visit memory; saved profiles are untouched. No customer reports were migrated or repaired behind the user's back.

## D73 review

The useful task is understanding coverage and the timing obstacle with fewer repeated asks. Preference, reported facts, missing precision and external verification remain distinct. Coverage paths remain available before policy comparison; no commercial inputs or personal plan findings enter this correction. Permission and control retain current v3 deliberate Send, optional saving and existing visit bounds. Actual consumer comprehension and broad model reliability remain unmeasured.
