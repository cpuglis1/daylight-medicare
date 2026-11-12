# D66 implementation evidence and recovery

October 21, 2026. [Screen contract](TEN_QUESTION_CONTRACT.md). Owner authorized implementation through local activation. The new route is locally activated and verified at [localhost:8890](http://127.0.0.1:8890/). The [previous guide](http://127.0.0.1:8896/) remains available with its original saved data. Technical results below are not owner acceptance or a personalized-plan release.

## Protected baseline and reproduced defect

31 current UI/service/design files are hashed and copied under `history/2026-10-21-before-ten-question/`, along with before screenshots. Existing D65 captures remain unchanged. The old UI is preserved under `cms-slice/apps/chat`; no old profile/database or data-source record is migrated, reset or deleted.

Browser reproduction: learning → Part D E02 → parts E01 → Part D E02. `E02.parts.next=E01` and `E01.drugs.next=E02`; per-node selection drafts remain selected on return. After making the choices once, repeated Continue can alternate those screens without making task progress. This is a user-visible navigation cycle, not an unbounded JavaScript recursion. Finish existed, but the default experience lacked a single forward path. The new route never calls these menu resolvers.

## Verification

- **16 actual browser combinations** (four goals × New/Know a little/Comfortable/Not sure) each visited ten distinct questions in order and reached the summary. No repeated step or topic-menu detour. The separate activated-app walk at port 8890 also completed ten distinct questions and reached summary. [Machine-readable browser evidence](visual-preview/ten-question/browser-matrix.json), [activated-app evidence](visual-preview/ten-question/browser-active.json).
- A populated synthetic browser journey retained requested month, provider, medicine, dose/pharmacy and travel/priority answers. Summary Edit returned directly to summary, preserved later answers and displayed review-needed assumptions. See plan options opened the five source-labeled samples directly, without another questionnaire or ranking.
- Ask kept the prescription step and input draft. Desktop/tablet/phone checks covered 1440×900, 820×1180, 390×844 and short phone 390×520 fixture views; the activated main app was also checked at its natural desktop viewport and 390px phone width. No horizontal overflow in checked states. The overlay remained 600px desktop/370px phone, with composer reachable at short height. Its opening did not change task/guide dimensions. Escape returned focus to the launcher; Shift-Tab stayed inside the overlay. Real phone keyboard and screen-reader speech are not claimed verified.
- Mock AI proposed a current answer, required confirmation, filled its draft and remained on question 1 until explicit Continue. Policy tests reject stale proposals, unsupported/oversized drafts and overwriting confirmed answers. Sensitive provider/drug/date context stays excluded from automatic model context. Main runtime reports real OpenAI GPT-5.4 available with mock mode false; no new paid smoke request was made.
- Dedicated synthetic guest saving produced a Saved receipt, and refresh/resume restored the exact summary and entered notes after separate sensitive-note opt-in. A fixture initially lacked the reference file used for derived county validation; the save failed visibly rather than falsely reporting Saved. The fixture dependency was corrected and save/resume passed. No real profile was used for these writes.
- **Full regression:** 271 Python tests passed before the final new-field proposal guard; the final nine ten-question backend tests, existing guest/agent regressions and budget regressions were then rerun. **167 frontend tests passed** in the final suite, including 27 ten-question checks. These complement the browser completion proof; counts alone are not a cohesive-flow claim.
- Old UI source files remain byte-identical to the protected baseline. The original photo, fonts/styles and source-plan records are copied unchanged. Existing old-profile storage was not migrated or overwritten; its Resume button remained available on the previous-guide page. New compatible profiles resume their exact step; legacy state is rejected safely rather than guessed into the sequence.

[Visual review gallery](http://127.0.0.1:8897/ten-question/) contains thirteen before/current views. Original D65 evidence remains separate and unchanged.

## Local activation

The new app responds at port 8890; the previous guide responds at 8896. Both use the same original budget ledger and no automatic retries. At activation the ledger was unchanged across the switch: five existing requests, $0.038485 estimated from measured tokens, $0 held (point-in-time diagnostic, not an invoice). No paid calls were made by this task. Ordinary user-initiated local AI remains authorized under the existing $1/UTC-day aggregate cap. Cookie/database isolation was checked with synthetic services; no new credentials or public exposure.

Core navigation and existing AI/profile infrastructure are separate: the default now uses `apps/ten-question`; `apps/chat` remains the original route. Backend changes add only a local cookie namespace/test-config hook, sensitive-date/note categories and allowlisted travel/cost preference proposals. Production cannot enable those local cookie/mock overrides. Budget enforcement/pricing files remain byte-identical. Main and previous process IDs are recorded in [activation metadata](visual-preview/ten-question/activation.json).

The hero/brand, source teaching and held plan boundary are preserved. No commit, push, public deployment, data-source promotion or profile migration occurred.

## Operational boundaries

The main ten-question entry is `python3 cms-slice/scripts/ten_server.py --port 8890`; `--legacy --port 8896` opens the preserved previous UI with its original guest cookie/database. The new guide has a separate cookie/database, preventing overwrites of an existing saved guide. Both paid surfaces share the original $1 per UTC-day budget ledger with no automatic retries. Fixture mode does not load credentials or use that ledger.

Rollback: stop only the recorded ten-question process on port 8890 and start `python3 cms-slice/scripts/ten_server.py --legacy --port 8890` (or the original guide_server.py command). Do not restore/delete any database. Keep both profiles for recovery. No commit, push or public deployment.

Real personalized plan comparisons remain held. The sample page is not a verified recommendation or comprehensive market list. Desktop emulation cannot establish real mobile-keyboard, screen-reader speech or older-adult comprehension results.

## October 22 · D67 accepted direction and refinements

The owner accepted the ten-question direction and requested focused improvements to start-month controls, final-action placement and plan-page help. See [D67 refinement evidence](TEN_QUESTION_REFINEMENTS.md) for current checks; earlier D66 evidence remains historical and unchanged. Search against a future database is recorded as intent with target field/dataset unresolved, not implemented or approved in concrete scope.
