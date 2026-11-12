# D67: minor refinements to the accepted ten-question flow

October 22, 2026. The owner accepted the D66 direction and asked for these bounded changes. No navigation/data redesign.

- “Choose a start month” replaces “A month and year.” Labeled native Month and Year selectors have blank new selections; stored YYYY-MM values prefill. New year choices cover the current UTC year minus one through plus five, with any recognized saved year retained. This is a UI choice range, not an insurance eligibility window. No exact day is requested. Ambiguous saved wording is displayed and preserved; explicitly keeping it changes no stored date. Already on Medicare and Not sure remain valid.
- **Owner placement correction:** Question 10 uses ordinary Continue below its choices. Only the Review your answers summary keeps See plan options above the ten-answer list. Edit/Back remain explicit; no duplicate primary continuation or automatic advance. The initially implemented top question-10 action is superseded.
- Plan options has the same sun-agent Ask overlay, with sample/validation-held page context and the confirmed profile's existing minimal AI context. Local help explains that samples are unverified. Return preserves position, draft and answers. Its official Plan Finder promotional CTA is removed; necessary CMS source links and limitations remain.
- Database-backed search is future intent only. Target field/dataset is unresolved and needs clarification before any implementation. No database or search provider was chosen.

## Verification

- **173 frontend tests passed**, including all existing ten-step goal/familiarity invariants and six new timing-format/preservation checks. The focused ten-question file has 33 passing tests. Backend code was not changed, so its prior regression evidence is not represented as newly rerun.
- Browser checks at desktop 1440×900, tablet 820×1180 and phone 390×844 confirmed labeled selectors, blank new choices, keyboard Tab from Month to Year, and no horizontal overflow. January 2027 remained exact on Back and summary Edit. Already on Medicare/Not sure retain their existing semantics. Synthetic policy tests additionally cover saved years outside the new-choice range and ambiguous raw wording kept without reinterpretation.
- Initial verification before the owner's placement correction reached question 10, summary and plan options. Its top question-10 action and corresponding screenshots are historical, superseded by the correction below. The summary's See plan options action precedes the ten-answer list; no duplicate primary continuation was added.
- Plan options shows the working sun-agent launcher. Ask identifies “Plan options · unvalidated samples,” explains the held sample scope locally, preserves the unsent draft, and returns focus to the launcher. Scroll at opening and return matched (1px in the desktop check). Returning to the summary retained the start month/year. No model call was needed.
- The promotional Plan Finder CTA is absent from the plan page; all five CMS source links, record identities and unverified/held disclosures remain. Profile/session/backend, pricing/budget, hero/photo and source sample files are hash-checked unchanged. No real profile was written or migrated.

[Browser checks](visual-preview/ten-refinements/browser-checks.json) · [screenshots](http://127.0.0.1:8897/ten-refinements/). Real-device keyboard and assistive-technology speech remain outside this browser-emulation check. No new paid test calls, commit/push or public deployment.

## Preservation

Before-images: `history/2026-10-22-before-ten-refinements/`. Backend/session/profile code, pricing, aggregate $1/UTC-day enforcement, approved hero/photo and sample source data are unchanged. Existing legacy guides remain available; no migration/deletion, commit, push or public deployment. Plan validation/integration remains held.

App: [Daylight](http://127.0.0.1:8890/).

## Owner placement correction · October 22, 2026

The owner clarified that the top action belongs on the review summary, not question 10. Question 10 now has ordinary Continue below its priority choices, like the other questions. The summary renderer is byte-identical and keeps See plan options above all ten answers. This supersedes the initial question-10 placement described in the earlier verification.

Verification: 173/173 frontend tests pass. A fresh unsaved synthetic browser journey reached all ten questions and the summary; desktop 1440×900 and phone 390×844 checks confirmed question 10 choices precede its sole Continue, the summary action precedes the answer list, and neither view overflows horizontally. Back to question 10 retained the answer. Summary Edit retained Save answer and return and returned to the summary. No profile was saved and no AI call was made. Backend/budget/privacy, timing controls, approved photo and source samples are unchanged.

Screenshots: [question 10 desktop](visual-preview/ten-refinements/correction/question10-desktop.jpg), [question 10 phone](visual-preview/ten-refinements/correction/question10-phone.jpg), [summary desktop](visual-preview/ten-refinements/correction/summary-desktop.jpg), [summary phone](visual-preview/ten-refinements/correction/summary-phone.jpg). Before-images: `history/2026-10-22-before-review-action-correction/`. Local app verified in Chrome at <http://127.0.0.1:8890/>.
