# Conversation progress toward comparison

Owner clarification, November 2, 2026 (America/New_York): bad-chat reports request a UX diagnosis and repair toward the MVP. The preceding generic unavailable-feature response solved the wrong problem. This scoped pass adds no synthetic catalog, UI layout or real plan release.

## What changed — D86 / D73

`natural_agent.py` removes the generic hard-stop paragraph and instead guides useful comparison preparation. The advisor acknowledges answers, explains a relevant point when helpful, asks one consequential question and answers direct questions before continuing. It must reuse reports and respect unknown/deferred details, without repeated lesson menus or blanket feature disclaimers. Actual findings still require source authority; preparation must not imply that checks happened or that completing a profile releases a hold.

`decision_guidance.py` fixes the structural priority problem: an age-65 report no longer automatically turns a comparison task into a timing task. Compare/review/browse now rank eligible location/current-coverage/doctor/prescription questions before preference refinements. A retained timing concern cannot indefinitely starve that preparation. Explicit timing tasks, direct explanation requests, substantive doctor/drug concerns, required clarifications and beneficiary identity retain their roles. Candidate membership is unchanged; this is adaptive guidance, not a mandatory questionnaire.

## Verification

193 focused regression tests passed: 175 natural-agent/claim/education/COBRA checks in `tests.log`, plus 18 decision-guidance tests in `decision-tests.log`. New checks exercise progression through remaining ZIP, doctor and prescription candidates despite a birthday and retained timing concern, and preserve a requested timing explanation with an optional practical return point.

`live_check.py` uses a temporary fictional self/retiree/soonest profile and at most six paid generation stages to test three turns toward ZIP, doctors and prescriptions. `live-result.json` records actual output, source hashes, costs and any failure without retry. The supplied customer transcript is not copied into this packet or sent to the provider. `activation.json` records the :8893 restart; saved profiles are unchanged, while server restart clears unsaved visit continuity.

The live sequence passed all three turns on unchanged final source: the comparison request asked T03 ZIP; the ZIP answer led to T06 doctors; “No doctors to include” led to T07 prescriptions. Every generated turn completed. Total measured/accounted cost was $0.1190475 across six settled stages, with no retry or uncertain hold from this check. This proves the targeted progression for one seeded fictional visit, not the entire entry-to-results journey. Tone still merits observation (the model used “Perfect” and some procedural wording); no claim of fully natural conversation is made.

No frontend changes or responsive browser replay were part of this conversation-layer pass. A focused live result and regression tests do not establish whole-journey quality or consumer comprehension. All existing real research/recommendation gates, model/stage budgets and privacy boundaries remain. The synthetic-plan work was interrupted before any edits, and was not resumed after the owner's clarification.
