# Implement the person's journey

D205 · November 19, 2026: the final delivered continuation has one owner. Both
models keep reading the user/profile and education records. The model chooses a
useful question or supported work; code retains validated clarification separately
from teaching until delivery, then reconciles profile questions, check controls,
review/handoff actions and intentional finishes. The UI uses `conversationNext`
to avoid a competing automatic action. Validate actual final output, and record
conversational memory only after assembly; a clarification is not a teaching receipt.
Source withdrawal still applies on replay, without consuming asks or offers.
No case-specific dialogue script or added model call. [Evidence](../../audit-evidence/delivered-continuation-d205-20261119/README.md).

D180/D179 · November 15, 2026 · Implemented on the :8895 branch: a useful
closing is part of the ordinary journey. At the natural handoff into comparison,
a supported decision or a requested pause, summarize what was learned, explain
the supported direction, give ordered next steps and provide one working way to
continue. Reuse known reports and exact doctor/medicine selections; show unchanged
research results compactly after their first delivery. Remove standing status
warnings above the chat and derive a quiet progress indicator from actual profile
coverage. Keep consequential uncertainty beside the affected next decision. Reuse
the existing summary, review and Plans handoff and composer call; no new model
stage. The [D179 proposal](MASTER_DESIGN.md#d179--profile-progress-reuse-and-the-transition-into-plans)
defines the required behavior; [D180 evidence](../../audit-evidence/guided-plan-close-20261115/README.md)
records its implementation and release limits. Eleven existing comparison areas
drive progress. Unknown/deferred counts as addressed, not verified. A readiness
transition produces the checked closing; pause/finish extends the existing summary.
Unchanged result digests remain in bounded visit delivery state across detours.
Plans guidance follows the actual view. A valid review receipt is tied to reports,
not the current explanation topic; edits, ambiguity and expiry still block reuse.

D178 · November 15, 2026: waiting status follows actual accepted work. The :8895-only progress channel carries owner/request-scoped codes in bounded RAM; it never carries reports, source rows, draft answer text or model diagnostics. Use actual lookup and composition boundaries, not topic guesses or elapsed-time stage changes. Approximately 12/30-second reassurance requires a current working receipt. A poll failure says only that an update is awaited; ordinary free receipt recovery retains control on connection loss. No new model call, retry or delay before a checked reply. Keep one accessible status, legible body type, reduced motion and reply-start anchoring. [Evidence](../../audit-evidence/turn-progress-20261115/README.md).

D177 · November 15, 2026: useful retained prose or an approved next question must
not acquire a generic unresolved/error notice. Keep up to four unfinished user
requests (600 characters each) in the existing owner/visit-scoped RAM planner;
both stages see them as untrusted concerns, never facts. The composer may mark
offered request IDs addressed when a relevant answer is actually delivered. Only
a complete checked reply without recovery retires them; rejected/partial prose,
detours and history trimming do not. This creates no model stage or retry loop.
Use existing catalog explanations when a question’s `why` is empty; no generic
next-detail filler. Worker relationship questions/conditionals must not be treated
as assertions, while independent actual claims still need their resolved report.
Source/action limitations remain visible when consequential; a wholly unavailable
answer with no useful continuation still needs an honest response.
[Evidence](../../audit-evidence/continuation-recovery-20261115/README.md).

D176 · November 15, 2026: question progress is a projection of the actual profile,
not another fact store. Existing reports, unknowns/deferred fields, entity identity
and explicit edit state govern eligibility. Narrow a partial question to its open
fields. Both model stages receive the delivered-question progress; only controls
actually sent consume an ask receipt. After one follow-up, leave that unresolved
field scope visibly open rather than asking indefinitely. New missing fields and
explicit edits remain answerable, and a later report clears its parked display.
An acknowledgment never establishes capture. Accept ordinary abbreviated month
notation, punctuation and ordinal days; retain the quoted month/day if the model
adds an unsupported year, only when the match is unique. Do not guess years or
change stated dates. Partial dates still hold date-dependent conclusions.
[Evidence](../../audit-evidence/question-progress-20261115/README.md).

D175 · November 14, 2026: the shared :8895 validator distinguishes unresolved
coverage and embedded questions from asserted coverage. Check report references
and source boundaries on actual claims. The composer returns at most four
self-contained `reply_blocks`; retain only whole independently checked blocks,
then revalidate the assembly. Never salvage by deleting arbitrary sentences or
material qualifications. Drop education/task-delivery metadata on partial prose.
A valid approved question can survive a blocked answer. For an accepted answer,
continue with that question’s own explanation without an error announcement or
unrelated lesson. D177 supersedes generic unanswered-request notices with internal
continuity; provider/transport failures and source holds stay explicit. No additional model stage or recovery
slot. [Evidence](../../audit-evidence/quiet-recovery-20261114/README.md).

D174 · November 14, 2026: keep each model stage's complete instructions in one
place. The :8895 path uses `conversation_prompts.py`, with no legacy prompt
splicing or duplicate instruction blocks in context. Explain and advance can
coexist: the composer may answer a detour and choose a consequential existing
question, or offer useful supported work. Correct a term before continuing;
clarify the path only when the ambiguity blocks the next action. A valid typed
process offer/clarification survives validation. Do not manufacture generic
reflection questions when a draft omits a follow-up. Selected teaching cards
replace duplicate prose and record delivery. Prefer valid local retention to
another paid repair; preserve all factual/source boundaries. Numeric and coded
diagnostics distinguish proposed, validated and delivered questions without
retaining their text. [Exact prompts and full pipeline](CONVERSATION_PLUMBING.md).

D173 · November 14, 2026: prioritize natural conversation flow, then required
information, then contextual education. The AI interprets goals and continuation
from the whole exchange and chooses whether to explain, suggest or proceed.
Supported task identifiers are capability boundaries, not wording triggers or a
curriculum. Code supplies existing conditional questions; the model selects the
consequential question and its structured controls. Only mandatory clarification,
explicit non-AI controls or failed composition use deterministic question selection.
Keep the existing profile capture for every relevant report and its subject,
unknowns and corrections. Keep concept delivery receipts: introduce once, deepen
when useful, revisit on request or confusion. Delivery never proves understanding.
Question explanations and key terms belong beside the work that makes them useful.
[Implementation and offline evidence](../../audit-evidence/semantic-guidance-20261114/README.md).

D172 · November 14, 2026: Daylight leads as well as listens. Recommend a useful
next piece of work from the person's context, and let them redirect. Once they
ask to work out a practical task, use the appropriate existing question and its
answer buttons; do not substitute repeated broad reflections or ask permission
again. Answer conceptual detours and resume using known reports. Unknowns remain
unknown. A process suggestion does not choose insurance. Generation failure is
not a reason to ask the person to rephrase clear input: keep the approved useful
next step and accurately state what was not delivered. Start new replies at their
beginning, including tables and visuals; never scroll past them later to expose
the next question automatically.

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
