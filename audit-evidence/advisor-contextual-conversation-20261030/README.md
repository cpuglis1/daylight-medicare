# Contextual conversation correction · :8893

October 30, 2026. Owner-authorized implementation addressing D86's latest conversation/UI corrections under D49/D50 (agent-led conditional progression), D54 (permissioned continuity), D64/D73 (independence and separate evidence gates), and D75 (protected variants).

The active local service is http://127.0.0.1:8893/. Only this variant was restarted. No public deployment, source acceptance, recommendation release or customer-store migration occurred.

## What changed

- The approved T02 familiarity question and its choices replace the locally added vague orientation question. The 41 original meanings remain conditional capabilities rather than a mandatory sequence.
- Both AI stages receive server-owned recent discourse under `natural-context-v2`: at most three exchanges and 3,000 characters, one-hour access expiry, owner/visit/task isolation. It is excluded from saved profiles. Legacy v1 keeps its earlier profile context and never receives dialogue history. New report quotes must still come from the latest message; resolved profile/evidence remain factual authority.
- Context follows the approved current question's capability as well as the broad task. At a comparison route's timing question, the model can use the actual birthday/retirement/worker-relationship reports rather than trying to repeat facts hidden from its grounding context.
- Explicit ASAP is an intended soonest-possible preference, not an invented month. It advances intake while the exact-month and external validation gates remain open. A spouse's job mention no longer discards the beneficiary's own retirement/birthday clauses.
- Prompts permit concise question-only turns and discourage repeated acknowledgments, priorities and unsolicited lessons. An explicit educational pause has an empty-question output schema. Factual teaching still needs reviewed evidence.
- All free-text answers use the one composer. Approved finite choices remain buttons. Premature unknown-filled timeline/basic diagrams and Back/Review/Prepare intake utilities are removed. Review/preparation are optional at an actual summary, not during an educational pause.
- Current questions, opening helper/shortcut labels and answer buttons use the retained slower, bounded reveal. Reduced-motion and accessible full text remain. Prior asked questions stay in the transcript before the answer, once; retries/rerenders do not duplicate or reanimate them.
- GPT-5.4 remains the model. The extraction reasoning setting is now `none`; composition already used `none`. Both bounded resolve/validate/compose stages, token counts, default tier, 8,000-input/900-output limits, shared $5 allowance and no automatic retries remain.

## Verification

[Final free suite](tests.log): **233 Python tests pass**, including **43 Node behavior cases** (33 rendering, 10 Send/history). Syntax passes. Scripted coverage includes profile scope, ASAP, unknown/defer, ambiguity/entity preservation, context permissions, recent dialogue bounds/isolation/replay, current-question context, educational pauses, progressive presentation, stale hidden answers and historical-question retention.

[Protected files](protected-after.json): all **676** hashed chat-first source/assets and advisor styles match the before snapshot. This change does not modify :8891's engine, styles or data. :8890 was not edited.

Browser verification covered desktop, 768-pixel tablet and 390-pixel phone. One composer, no extra current-question text/date fields, no overflow, privacy-only intake footer, suppressed early reference and actual choice progression were inspected. [Question/button delays](browser-behavior.json), [active opening delays](live-opening-motion.json), [desktop](desktop-timing.png), [tablet](tablet-timing.png), [phone](phone-timing.png), and [active delivery](active.png). A post-update browser check also confirmed the opening question remains in history after Send.

## Live checks and spending

Fictional temporary databases only; no saved profile or actual customer inputs. [Totals](live-totals.json): **10 generation stages, $0.0893475 measured estimate, zero new holds**, no automatic retry. Two initial assertions exposed real scope/context defects and stopped their harnesses; those failures are retained in `attempt-1/` and `attempt-2/` rather than presented as passes.

The accepted reports were then refreshed into a new fictional visit to avoid paying for extraction again. [Remaining check](remaining-results.json) verified corrected context and **ASAP → next question**, measured **4.630 seconds** for that HTTP turn. Its educational extraction/answer exposed a further stray follow-up question. The schema was corrected, and [one final composition](final-education-results.json) verified a sourced Part B explanation, no intake question, retained ASAP and an explicit pause (**2.246 seconds for composition only**, not a full-turn latency). [All three final outputs pass the latest guard offline](latest-guard-recheck.json).

This is targeted verification, not a claim that one untouched end-to-end transcript passed every revision. Earlier live checks took roughly 11–13 seconds; the current full ASAP turn took 4.6 seconds. Generation plus two token-count calls remain serial, and first/complex turns can take longer. No unvalidated provider stream is displayed. Naturalness across broader audiences, long visits and real assistive technology remains consumer-validation work; technical checks do not constitute owner approval.

## Strategic review

Self-service is more direct: one conversational input, inspectable reports at the end, and useful choices without a second form. Intake remains consequential and conditional. Correcting reported facts remains distinct from verifying insurance, providers, medicines, exact costs and eligibility. Source/recommendation holds, uncompensated options and commercial independence are unchanged. No evidence gate or sealed L01/L03 inventory was altered.

The implementation uses the existing API with manual conversation context, consistent with [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state). Latency was measured at count/extract/compose boundaries, following the [latency optimization guidance](https://developers.openai.com/api/docs/guides/latency-optimization); this is not a provider latency guarantee.
