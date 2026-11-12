# Nonblocking conversational recovery · :8893

October 30, 2026. Implements the owner's reported opening blocker under D86, retaining D49/D50's agent-led conditional flow, D54 privacy, D64/D73 independence/evidence gates and D75 variant protection.

## Findings and changes

The anonymous opening used for verification was: “I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options”. The first live reproduction did not repeat the exact historical rejection; it exposed another dead end: `task=learn`, no useful next question, and unsolicited insurance teaching with no selected evidence. The historical original rejection reason was not logged, so its exact guard is unknown.

A local typed `practical_request` now distinguishes requested capability from familiarity. The extractor can identify the enrollment/timing request separately from T02 knowledge. Exact current-message support and the existing timing/hypothetical guards apply. This is an internal planning hint, not a new profile question, eligibility finding or authority to enroll. Invalid advisory task/request commands are quarantined independently; malformed envelopes, types, bounds, modes and unsupported evidence references remain rejected. Valid profile reports do not depend on a perfect unrelated routing quote.

Initial/early learning has three bounded reviewed foundation candidates, available for selection by the model when an actual learning question needs them. They are not automatically displayed for a life story. The existing input-token preflight remains in force. No response is hardcoded for this opening.

On composition failure, invalid prose stays out of the transcript. The controller retains the already-approved post-capture question and emits one status notice. Learning-open and intentional-pause states survive failure without a false completion/review panel. The client no longer accumulates identical generic failure paragraphs or invents an already-answered question. `note()` now uses the existing status live region alone; the second screen-reader announcer was removed.

Fixed-code extraction/composition diagnostics go to the existing server error log, without user text, profile values, raw provider errors or identifiers. The composition memory ring is capped at 50 value-free entries. Source, action, permission, saving, ledger and protected-variant guards remain.

## Verification

[Full free suite](tests.log): **245 Python tests pass**, including **50 Node behavior cases** (37 rendering, 13 Send/history). New cases exercise practical intent vs knowledge, unsupported/hypothetical focus, independently bad routing/check quotes, preserving valid insurance reports, post-failure approved choices, learning/pause flags, bounded diagnostics, repeated unavailable replies and one live announcement. JavaScript syntax passes.

[Preservation](protected-files.json): all **676** protected chat-first source/assets and advisor styles match the prior baseline. No :8891 engine/UI/store change, source acceptance, recommendation release, public deployment or ledger reset. Only :8893's local job was restarted. [Final changed-source manifest](source-manifest.json).

Live tests used anonymous fictional inputs, temporary private databases and fixed stage ceilings, with no automatic retry. [Total measured estimate](live-totals.json): **$0.0804635**, no new uncertain holds.

- [Original reproduction](results.json) exposed the learn/no-question dead end; it is not recorded as a passing natural conversation.
- [Opening after correction](latest-results.json): the exact opening produced a normal reply and **T05: current health insurance** in 6.758 seconds. The following HTTP test failed before the final advisory-command fix; its response body was not retained, so its exact original validation reason is unknown.
- [Final follow-up](followup-results.json): resumed the accepted fictional opening reports through refresh, seeded their actual prior exchange into that new test visit, and verified spouse-job insurance → **T04: desired start** in 6.124 seconds. “As soon as possible” then advanced without another model call. No opening extraction was repeated. A stale-continuation harness setup error occurred before any paid call and is separately retained in `harness-setup-409.json`.
- [Actual browser/model response](browser-live-response.json): the exact opening passed again through the real frontend and model with an isolated test cookie/database. It generated “I can help you look at the main Medicare paths step by step.” and asked “What health insurance do you have now?” [Screenshot](verified-opening.png), [DOM checks](browser-verification.json), [isolated browser cost](browser-live-cost.json). No fallback paragraph, duplicate announcer, extra input or horizontal overflow was present. This preview ran the product's source on temporary :8894 and was stopped afterward; the deliverable remains :8893.

A no-credit synthetic preview separately exercised an intentionally unavailable composition while the approved question/buttons remained usable. Such injected failures verify recovery presentation, not model naturalness. The browser showed the duplicate live-announcer issue, now covered by the actual-note regression and confirmed absent in the real browser check.

These are narrow scenario checks, not proof of every future model reply or observed audience comprehension. The existing factual guard remains bounded and source/recommendation release remains held. No historical failed check was relabeled as a pass.
