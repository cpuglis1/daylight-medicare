# D86 human text reveal restoration — October 30, 2026

The owner reported losing :8891's gradual greeting and typing-like text presentation in :8893 and asked that useful features survive later narrative/model changes. Requirements: D86, the retained D79 interaction and the narrow purposeful-text exception to D18. The [interaction contract](../../alternatives/advisor-first/INTERACTION_CONTRACT.md) records what future changes must preserve.

## Cause and change

The canonical :8891 `adaptive-app.js` renders new assistant text as a complete screen-reader paragraph plus visual word spans. Its existing CSS fades words at 18 ms intervals, with a 650 ms maximum delay and 120 ms fade. :8893 copied that CSS but its `exchange()` and `factBlock()` emitted plain paragraphs, so the behavior was never invoked. Static layout and backend tests did not cover the missing presentation behavior.

`web/advisor.js` now applies that same bounded reveal to the greeting, new assistant replies and teaching bodies. User messages, headings, sources and controls remain immediate. A WeakSet tracks displayed history objects. After an animation finishes **or is cancelled**, its word class/handlers are retired, keeping old words fully visible when the chat-mode selector is reapplied.

The browser caught that last detail: stable DOM alone did not prevent CSS animation restarting after Back → Get started. The corrected class cleanup and two additional tests address it. No text content, layout, stylesheet or backend conversation logic changes. The full validated response still arrives before visual reveal; this is not raw provider-token streaming and makes no extra model request.

## Verification

- **193 Python tests pass** in 6.886 seconds; the new discovery wrapper executes **14 Node renderer cases**. [Full log](tests.log). JavaScript syntax also passes `node --check`.
- Tests execute the production paragraph/fact/history/exchange functions. They cover greeting/reply/teaching reveal, original timing, immediate user/source text, whitespace and HTML text safety, full accessible text once, hidden visual duplication, reduced-motion plain text, bounded long responses, append/repaint/rebuild stability, and completion/cancellation cleanup.
- Actual :8893 browser observation captured all 18 greeting words initially hidden with the expected stagger and 120 ms fade: [motion snapshot](greeting-motion.json). The accessibility tree exposed one complete greeting.
- Selecting a goal and Back → Get started preserved the unsent fictional draft, kept one Send, retained one greeting and left **zero active word animations**: [return snapshot](return-continuity.json).
- A labeled fixture on :8892 verified a new reply plus teaching body both use the reveal wrapper, with immediate user text and two complete accessible paragraphs: [fixture snapshot](reply-motion-fixture.json). It used a temporary database and made no AI call.
- Desktop 1280×800, tablet 768×1024 and phone 390×844 were visually inspected: [desktop](desktop.png), [tablet fixture](tablet-fixture.png), [phone fixture](phone-fixture.png). Phone document width matched viewport width; one Send remained. Reduced-motion markup/CSS are covered by controlled tests; OS preference toggling, physical keyboards and assistive-technology execution remain separate checks.

The static change is already served by :8893 and verified in a fresh tab. No backend or protected-runtime restart was needed. Existing user tabs were not reloaded; the temporary fixture was stopped and its tab closed.

## Preservation and future changes

The [read-only preservation check](preservation-after.json) confirms all 77 protected engine/style/HTML/data/assets, pre-existing database rows and inodes remain unchanged. Its database baseline is the preceding live-check packet's final pre-restoration snapshot. Opening the fresh active browser tab added one normal unsaved guest row (3 → 4); no profile/request/readiness save was added. The AI ledger has **zero new rows or spend** for this restoration. [Backend hashes](backend-preservation.json) independently compare the current natural-flow/model/profile/budget implementation with the prior delivery packets.

`INTERACTION_CONTRACT.md` is now required reading in the scoped AGENTS.md. The owner's requirement/master records make the reveal a retained behavior rather than an optional experiment. The ordinary Python command runs the frontend behavior tests, so they are not an easily omitted separate check.

This is a scoped restoration and a stronger regression guard, not a claim that every historical :8891 feature has been inventoried. Later changes should identify their intended behavioral difference, preserve the listed interactions and add tests for newly observed losses. Source/recommendation/privacy/budget gates and the substantive natural-conversation changes remain intact.

## Owner pacing refinement

The owner then requested slower reveal and the same treatment for the opening question, examples and helper line. Timing is now 40 ms per word, bounded at 2,000 ms per block. All three opening lines reveal in order after the greeting, once per visit; reduced motion stays immediate. All 18 renderer tests pass ([log](slower-opening-tests.log)); actual :8893 browser timing and all three paragraphs were verified ([snapshot](slower-opening-motion.json), [screenshot](slower-opening.png)). No AI requests or backend changes. The earlier manifest/timing above records the initial restoration.
