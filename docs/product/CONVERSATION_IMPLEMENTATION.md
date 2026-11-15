# Implement the person's journey

D154 · November 12, 2026. Applies to every interface, conversation and backend
capability exposed by the advisor. Read the Daylight Brain's **02 UX playbook**
first; its location is in `docs/project/CURRENT_STATE.md`.

The unit of delivery is a user story through the existing conversation. A
working endpoint, standalone preview, launch button or panel is not a completed
integration. The owner corrected the D150–D153 doctor/drug implementation because
placing a separate tool inside the chat still interrupted the experience.

On :8895, D166's discussion planner owns conversational direction. A question
must receive an answer before unrelated intake resumes. Intent, facts,
understanding, preferences, exploration and decisions are separate: a topic,
card, view, reported priority or plan investigation cannot establish a choice.
Explain relevant concepts and compare tradeoffs before narrowing when useful;
honor a direct investigation request without a fixed education interview.
Only consequential missing details belong in the next question. Cards support
that turn's purpose, with no unrequested pricing counters or repeated teaching.
Delivery does not establish comprehension. Recommendations and evidence
authorization remain in their existing deterministic services.

Before implementation, name:

1. The person's goal and natural opening or already-active conversation.
2. The reports already known, their subject and provenance, and the one next
   unresolved detail that matters. Reuse current reports; do not repeat intake.
3. The condition that causes software to do useful work, the evidence or
   limitation the person sees, and how the conversation continues afterward.
4. Correction, uncertainty, deferral, unsupported scope, source STOP, expiry,
   refresh and draft recovery. Changed inputs invalidate the affected result.

Implement within the same guest visit, transcript, composer and current question.
Doctor, medicine and pharmacy matching follows the person's reports and current
goal. Exact identities still need deliberate confirmation where ambiguous or
consequential; asking a missing detail is different from asking someone to start
another tool. Choices are staged and submitted with the existing Send control.
Free text and questions remain available throughout. No preselected answers.

Do not add a permanent check button, setup wizard, second tab, parallel intake or
separate guest profile as the delivery path unless the owner explicitly asks for
an independent tool. Keep engineering words such as fixture, rehearsal and test
scenario out of consumer task labels. Retain an honest local evaluation scope
notice and exact evidence limitations where relevant; removing internal wording
does not authorize personal recommendations or consumer release.

When capability changes, update what the model knows exists in the same patch.
Give it capability state and the appropriate missing-question meaning. Source
rows, candidate IDs, prices and receipts remain in deterministic software under
their existing permissions. The model must not deny a usable capability, invent
execution or replace a supported check with a referral elsewhere.

Verification must start from the person's words or previously entered reports,
using a network-forbidden scripted interpreter for offline tests. A test that
opens the tool directly or seeds a complete result is supplemental evidence only.
Verify a full story, a correction and an unknown/held outcome; inspect desktop,
tablet and phone. Record which parts used scripted interpretation and which used
real local source data. Live model conversation quality is for the owner to
assess; no agent-run paid or live model tests.

Before reporting completion, activate the changed backend on the requested local
surface and inspect it. Keep implemented, running, technically verified and
owner-accepted distinct. A passing test count cannot approve the experience.

## Rules added by D157 (November 12, 2026)

- Don't ask for a fact unless the person sees the result within a turn or two.
- Ask for a missing detail; never announce that one is missing. Never call a recorded fact missing.
- Say each teaching point once. The visit-long record is `flow.ux` (`ux_pass.VisitLedger`); the model only
  sees the last six exchanges.
- When the person asks what is best for them or to see plans, stop the curriculum and ask the next missing
  detail or decision. Never a menu of topics.
- Windows and start dates that follow from fixed rules are computed in code and shown in a card. The model
  introduces a card; it never restates or computes what the card shows.
- A failed generation uses what the person said and asks the next question. No “I couldn't finish”.
- No pilot, demo, sample, research or evaluation wording to a person.

## Run and check

Moved here from the Brain's UX playbook on November 12, 2026.

Offline checks, from the repo root (no network, no model billing):

```
PYTHONPATH=alternatives/advisor-first/tests infrastructure/daylight-data/.venv/bin/python -m unittest \
  test_pp16_journey test_conversation_checks_ux test_d138_conversation_panels test_medigap_profile \
  test_part_d_pilot test_natural_agent -q
node --test alternatives/advisor-first/tests/test_ux_pass_view.js \
  alternatives/advisor-first/tests/test_medigap_view.js alternatives/advisor-first/tests/test_part_d_view.js \
  alternatives/advisor-first/tests/test_recommendation_view.js alternatives/advisor-first/tests/test_plans_handoff.js
```

`tests/known-failures.json` lists tests that disagree with the current code and why; they still run. Failures
that predate D138 are in `test_button_backend_gates`, `test_curriculum_flow` and `test_education_lifecycle`.
`test_ux_pass_handoff.py` holds the failing contracts for the backend and data layer.

Ports: :8893 is the advisor backend; :8894 is the participant interface (forwards the API to :8893); :8895 is
the unified local demo with D147 sorting and D154 checks. After a backend change restart :8893 (“Restart
Daylight 8893.command”) and, for the demo, “Restart Daylight Demo.command”; the owner approves computer access
for each session. A front-end change needs only a refresh. Before a live run check `/api/status` (canRequest
true, pricing review not expired), run one profile, then the rest; live runs need the owner's clearance. One
agent at a time edits `alternatives/advisor-first/`. `DAYLIGHT_DISABLE_UX_PASS=1` turns the D157 conversation
hooks off.

Related authority: D49, D52, D54, D57, D64, D73, D79, D86, D109, D130–D131,
D138, D146, D148, D154 and D157. D154 supersedes the separate-entry interpretation of
D150–D153; their original evidence packets remain historical records.
