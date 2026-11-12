# Follow-up contract, profile review and Plans handoff

November 4, 2026 · D86/D73/D90 · active advisor at :8893.

The owner requested a follow-up on active turns and a consolidated, editable profile checkpoint before opening the separately owned Plans workspace. This increment implements that checkpoint and its integration boundary. It does not implement the receiving Plans tab or release recommendations.

## Behavior

- Active composition requires a validated follow-up, including after educational answers. Missing or removed questions enter the existing bounded repair; a still-incomplete response cannot report successful completion. Only an actually pending or required approved question may accompany a retained answer. There is no unrelated intake fallback or added generation stage. Explicit pauses remain supported by the existing conversational pause interpretation and the authoritative “No more questions” override. Semantic interpretation of a pause remains model-dependent; this is not a guarantee of perfect intent recognition or provider availability.
- Review readiness depends on eleven meanings: goal, beneficiary relationship, ZIP/county, coverage year, current insurance, actual Medicare enrollment, doctors/hospitals, prescriptions, care away from home, cost preference and priorities. It is not a turn count, prescribed interview order, curriculum exam or requirement to fill all 41 meanings. Information supplied together is reused. Education-only and timing-only visits do not inherit a comparison questionnaire from the router's default task.
- The person, location and year must be known. Other minimum dimensions can explicitly remain unknown or deferred. Lists selected for entry need retained names. Conflicts, stale required facts and a live clarification hold review. Detailed offices, product strengths/forms, fills, pharmacies and other conditional data are still needed when an actual check depends on them.
- **Review your info** presents the consolidated profile, existing edit actions and visible open checks. **See plans** confirms that exact profile and calls a registered same-page destination. Draft text is protected. Corrections require a fresh review. The receiving UI is outside this increment; with no handler, the advisor honestly reports that the Plans workspace is not connected and preserves the reviewed state.
- An owner/visit/report-bound, ten-minute receipt resolves through the current server head. The endpoint accepts a token, never a client-supplied profile. Wrong-owner, stale, historical, expired and deleted visits cannot authorize the handoff. Nothing is placed in URLs or persistent browser storage. Review does not mark reported facts externally verified or authorize personal recommendations.

The [integration contract](../../docs/product/plan-review-2026-11-04/HANDOFF.md) contains the minimum table, callback, API and exact next implementation step for the other chat.

## Executed checks

- `final-focused.log`: **234 Python checks passed**, covering the checkpoint, correction and clarification paths, turn contract, factual validation, profile normalization, recovery, learner state and curriculum contract.
- `http-tests.log`: **19 local HTTP checks passed**, including the handoff endpoint, origin/CSRF protection, owner isolation, session recovery and existing HTTP behavior.
- `frontend-tests.log`: **39 Node checks passed**, including unsent-draft protection, explicit navigation, destination failures, retry and the handoff adapter.
- Desktop browser fixture: reviewed the fictional consolidated profile, preserved two medicine strengths, corrected the cost preference without re-asking the old question, and used **See plans** to open an explicitly labeled destination fixture. The real Plans tab was not simulated as completed work.
- Responsive fixtures: phone 390 px and tablet 820 px have matching client/scroll widths and no horizontal overflow. Editable rows, open checks and closing actions remain available. Screenshots are retained beside this note. These fixtures use a temporary database and disabled models.
- The original r2 source/calculator replay passed: all six numeric cells and the three-to-four-day hospital change from $540 to $720. The frozen `natural_state.py` remains byte-identical (`6b89b84b857ff02facd95b254461261379b64cc2020f4f046a5779cc44e2b411`).
- `protected-check.json`: all 44 checked curriculum, learner, evidence, provider, pricing/budget and out-of-scope UI files retain their prior hashes. The narrow review UI and server integration are intentional changes.

`run_offline.py` blocks non-loopback connections and real curl provider transport. Local HTTP fixtures required permission to bind localhost; no live AI evaluations or paid provider calls were made. Scripted fixture replies were updated to include a follow-up under the new contract; dedicated negative tests disable that helper. Scripted prose proves state/authority behavior, not naturalness, comprehension or good model-selected pacing.

The initial broad run is preserved, including genuine regressions subsequently fixed, outdated answer-only expectations, restricted localhost bindings and existing prepared-lesson/visual expectations. Do not read it as the final result or describe every initial failure as pre-existing.

The final broad run executed **1,022 checks**: 1,004 passed, with 13 failures and 5 errors (`final-full.log` / `final-full-result.json`). Seventeen issue identities match the previous increment's recorded baseline failures for removed lesson/visual blocks and their former state/replay behavior. One additional persona expectation still supplied an answer-only educational reply. Its composition fixture now includes a follow-up; its independently authored profile oracle is unchanged. A second fixture now distinguishes pausing intake to learn from pausing conversation. **All ten subsequent persona/follow-up checks passed** (`persona-contract.log`). No full-suite-green claim is made, and canned output was not restored to satisfy historical tests.

## D73 review

The checkpoint supports consequential intake, inspectable reports, corrections and a concrete next action. Comprehension remains a separate tentative learning assessment; personal applicability remains externally unverified. Coverage path and existing-coverage alternatives remain in the normalized profile. No economics entered inclusion, fit, explanation or recommendation logic. No source acceptance, saving consent, historical research denominator, protected variant or released recommendation gate changed.

## Remaining integration and product evidence

The other chat must register its actual Plans workspace activation callback and re-resolve the receipt on the backend before using the profile. It must preserve requested year/geography and evaluate its own source, eligibility, network and medicine gates. Receiving 2027 reports does not make the 2026 catalog applicable. Consumer review of live conversational quality remains outstanding; no such evaluation was run or claimed here.

## Local activation

The existing :8893 LaunchAgent was restarted after the affected checks passed. `activation.json` records the process change from 20314 to 45533 and successful read-only responses for the page, status endpoint and current handoff module. The temporary :8917 fixture server and browser tab were closed. No model call, profile migration, external publication or other variant restart accompanied activation.

`before-hashes.json`, `after-hashes.json` and `tracked-snapshot.diff` preserve the selected source changes independently of the repository's substantial pre-existing uncommitted work. The audit recording window starts at `started.txt`; it began after the initial repository/requirements review and is not a measurement of the whole chat.
