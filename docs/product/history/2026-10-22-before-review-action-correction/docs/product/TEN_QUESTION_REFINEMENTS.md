# D67: minor refinements to the accepted ten-question flow

October 22, 2026. The owner accepted the D66 direction and asked for these bounded changes. No navigation/data redesign.

- “Choose a start month” replaces “A month and year.” Labeled native Month and Year selectors have blank new selections; stored YYYY-MM values prefill. New year choices cover the current UTC year minus one through plus five, with any recognized saved year retained. This is a UI choice range, not an insurance eligibility window. No exact day is requested. Ambiguous saved wording is displayed and preserved; explicitly keeping it changes no stored date. Already on Medicare and Not sure remain valid.
- Question 10 has one Review your answers action before its choices, retained while scrolling. The summary's next action sits above the ten-answer list. Edit/Back remain explicit; no duplicate primary continuation or automatic advance.
- Plan options has the same sun-agent Ask overlay, with sample/validation-held page context and the confirmed profile's existing minimal AI context. Local help explains that samples are unverified. Return preserves position, draft and answers. Its official Plan Finder promotional CTA is removed; necessary CMS source links and limitations remain.
- Database-backed search is future intent only. Target field/dataset is unresolved and needs clarification before any implementation. No database or search provider was chosen.

## Verification

- **173 frontend tests passed**, including all existing ten-step goal/familiarity invariants and six new timing-format/preservation checks. The focused ten-question file has 33 passing tests. Backend code was not changed, so its prior regression evidence is not represented as newly rerun.
- Browser checks at desktop 1440×900, tablet 820×1180 and phone 390×844 confirmed labeled selectors, blank new choices, keyboard Tab from Month to Year, and no horizontal overflow. January 2027 remained exact on Back and summary Edit. Already on Medicare/Not sure retain their existing semantics. Synthetic policy tests additionally cover saved years outside the new-choice range and ambiguous raw wording kept without reinterpretation.
- A full browser journey still reached question 10, summary and plan options. There was exactly one Review your answers button, positioned before priority choices. After selecting a lower phone choice, its sticky top was 18px and remained visible. The summary's See plan options action precedes the ten-answer list; no duplicate primary continuation was added.
- Plan options shows the working sun-agent launcher. Ask identifies “Plan options · unvalidated samples,” explains the held sample scope locally, preserves the unsent draft, and returns focus to the launcher. Scroll at opening and return matched (1px in the desktop check). Returning to the summary retained the start month/year. No model call was needed.
- The promotional Plan Finder CTA is absent from the plan page; all five CMS source links, record identities and unverified/held disclosures remain. Profile/session/backend, pricing/budget, hero/photo and source sample files are hash-checked unchanged. No real profile was written or migrated.

[Browser checks](visual-preview/ten-refinements/browser-checks.json) · [screenshots](http://127.0.0.1:8897/ten-refinements/). Real-device keyboard and assistive-technology speech remain outside this browser-emulation check. No new paid test calls, commit/push or public deployment.

## Preservation

Before-images: `history/2026-10-22-before-ten-refinements/`. Backend/session/profile code, pricing, aggregate $1/UTC-day enforcement, approved hero/photo and sample source data are unchanged. Existing legacy guides remain available; no migration/deletion, commit, push or public deployment. Plan validation/integration remains held.

App: [Daylight](http://127.0.0.1:8890/).
