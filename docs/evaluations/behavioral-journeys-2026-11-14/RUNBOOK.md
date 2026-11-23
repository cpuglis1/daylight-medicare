# Running and reviewing complete journeys

## Preconditions and modes

Use a fresh isolated fictional guest visit per main run. Pin build hashes, planner
switch, rule versions, evidence revisions and viewport. Keep the synthetic persona
and decision criteria outside the app's input. No production participant records.

- **Offline browser:** real rendered app and interaction handlers; isolated local
  backend; network disabled; declared scripted language transport and synthetic or
  permitted local evidence. Measures visible mechanics and recovery. Language
  quality is untested when the replies are scripted.
- **Scripted backend:** useful regression support; never satisfies browser beats.
- **Manual owner:** the owner can conduct and assess natural-language journeys.
  Agent-run live or paid model calls remain prohibited without separate approval.

The grader consumes captured evidence. At D168 creation, a browser automation/capture adapter was
**not implemented in this packet**. D170 supplies the real UI/handler adapter and
[reproduction instructions](../../../audit-evidence/behavioral-fixes-20261114/README.md).
Do not fill a manifest with simulated route
observations and describe that as a test of :8895. Until the actual runner/source
binding is available, leave app runs `not_started`.

Before each run, verify the actual runtime revision and planner switch through
local status and traced response evidence; file edits alone are insufficient.
D167 activation remained open at D170 verification; D170 reran the two local-source checks successfully.
Do not stop the owner's server or alter source gates to force the test through.

## Actual surface map

These are semantic targets inspected in current `web-8894/` source, not a promise
that every control is visible at every state. Discover the live control from its
current DOM/accessibility state. Store its actual label, view and result.

| Persona action | Current source mapping | What must be observed |
| --- | --- | --- |
| Open Plans | `advisor.js` / `DaylightPlans.open`; `plans-workspace.js` `open()` | Actual product view, not merely returned `plans_view` |
| Open side window | Plans `Ask Daylight` → `chat()` drawer | Underlying plan/guide view retained; composer remains usable |
| Close side window | Close / Hide chat / Back to the guide, depending on view | Returns to the same context, not reset or new visit |
| Full conversation | `Back to my conversation` → `close()` | Submitted facts/history and pending question preserved |
| Inspect plan | `See full details` or current plan detail control | Correct plan, date, source scope and return route |
| Switch paths | Original Medicare / Medicare Advantage navigation | View changes without committing a coverage choice |
| Enrollment guide | `openGuide(id, route)` through a visible offered guide link | Applicable guide; no submitted/active status inferred |
| Correct input | Existing edit flow or ordinary message | Confirmed correction updates dependent results and retains unrelated facts |
| Browser refresh | Refresh in isolated active visit | Actual supported recovery, not a fresh hidden seeded guide |

A **side window means the existing Ask Daylight drawer or visible detail dialog**,
not a newly invented second application. If a separate browser tab opens, record
that transition too. Opening a side window, scrolling or selecting a row must not
silently call the model, change preferences or enroll anyone. Explicitly sending
an Ask Daylight question is a separate action.

## Dispatch loop

For each observation:

1. Capture current visible text/controls and route; retain backend snapshot where
   the assertion needs it. Record requested target separately from actual target.
2. Choose the earliest unexecuted beat whose trigger is satisfied. Finish stays
   last unless the goal is independently complete. If none is ready, answer the
   current relevant question from private facts, or ask the next necessary goal
   question. Never force a fixture’s predicted next-question ID.
3. Perform **one** human-level action and observe the result. Wait for a bounded
   completion/error signal, not an arbitrary long sleep. Record silence, error,
   latency and retry explicitly. Do not hide failed attempts by starting over.
4. For UI actions capture before/after evidence. For report updates capture the
   relevant before/after field and provenance, not an invented state summary.
   Confirm that facts supplied only to the persona have not appeared in the app.
5. Log unmet triggers. A missing required beat is untested, not a pass. Mark an
   unavailable control as a product block unless evidence shows a valid scope
   limitation; do not relabel a broken Back button as a source block.
6. Stop under the suite's termination policy and review the finish against the
   declared goal. For BJ10's expiry check use a separate isolated clone and attach
   its evidence with its own visit ID; never expire the main visit to force a pass.

## Evidence manifest

`evaluate.py new-run` creates the empty `run.json`. Fill it only from observations.
Artifacts use paths relative to that run directory, with SHA-256 and origin:
`observed_ui`, `observed_backend`, or `review_notes`. Synthetic evidence **inside a
real isolated app** is declared by `evidence_mode: synthetic`; it is not the same as
invented capture artifacts, which must use `synthetic_self_test` and cannot pass.

Every event needs:

- `id`, sequential `seq`, optional `beat_id` (ad-hoc answers have null beat ID),
  `action`, `status` (`performed`, `blocked`, `not_triggered`), `observation`,
  and `evidence_ids`.
- In its observation artifact: actual visible route and requested route; relevant
  before/after reports, decisions and result revisions; draft/visit identity when
  relevant; visible answer or error; timestamps and latency. Keep screenshot/DOM
  and backend response references distinct.
- Distinguish persona-chosen interruptions from app-imposed detours and repeat
  questions. Do not persist real-person transcripts; these packets are fictional.

`build` records revision, actual file hashes, planner enabled and runtime verified.
`started_at` and `ended_at` use ISO timestamps with offsets. These fields are recorded
claims; the human reviewer must check the linked runtime artifacts. The grader
cannot authenticate an artifact's declared provenance or prevent a dishonest tester.

## Assertions and human review

Use one judgment per ID, `pass`, `fail` or `unreviewed`, with `event_ids`,
`evidence_ids`, a specific `reason`, `reviewer` and `reviewer_role`
(`human_owner` or `human_reviewer`). A model may propose findings, but a model-only
judgment stays unreviewed. Review a complete transcript and relevant screens;
do not pass a multi-step requirement from one cherry-picked screenshot.

| ID | Pass evidence |
| --- | --- |
| goal | All requested deliverables observed for goal_complete; for safe_blocked, the correct external blocker and useful partial work are explicitly identified |
| answer_first | Side question answered or honestly bounded before unrelated intake resumes; no unanswered user message hidden by a chip/shortcut |
| retention | Known relevant reports reused, correct subject retained; no unnecessary reset or loss |
| decision_control | Browsing, explanation and preferences stay separate from explicit decisions; corrections/reversals respected |
| evidence_integrity | Exact scope/year/source and unknowns retained; no fabricated checks/prices or release-gate bypass |
| finish_honesty | Visible summary and recorded state agree; next action is specific; no false enrollment or inflated completion |
| navigation | Every required browser beat actually occurred, expected return context preserved; no hidden API substitute |
| correction | When applicable, old dependent results withdrawn/recomputed, unrelated reports retained |

Critical findings override averages: invented result, unsupported recommendation,
wrong subject, stale material result, unintended decision, false enrollment,
unauthorized transmission or ignored source STOP. Record event-linked rationale.

## Experience ratings

Rate each dimension 0–3 with cited evidence and reviewer identity. Ratings do not
turn blocked goals into completed ones and are never automatic owner acceptance.

| Dimension | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Clarity | Misleads/confuses materially | Repeated jargon or unanswered concern | Understandable with minor friction | Clear answers calibrated to this person |
| Effort | Cannot progress | Repeated rescue/re-entry | Some avoidable work | Only consequential work plus chosen exploration |
| Continuity | Loses task or subject | Frequent resets/detours | Recovers with minor prompting | Resumes naturally after every interruption |
| Control | Commits or overrides without consent | Hard to revise/decline | Corrections possible with friction | Explore, edit, defer and reverse easily |
| Useful finish | False or absent finish | Vague “contact someone” | Correct summary with minor gap | Goal-specific deliverable, limits and concrete next action |

Report the five values and worst cases; do not collapse them into a single success
percentage. Also report goal-complete, safe-blocked, failed, incomplete and not-run
counts separately, by declared goal and evidence mode. A scripted composer does not
provide evidence for Clarity, however polished its fixture text looks.

## Optimization experiments

Start with BJ01, BJ03, BJ05, BJ07, BJ08 and BJ12, each direct/interrupted. They
cover the largest routing, correction and completion risks. Then run BJ02, BJ04,
BJ06, BJ09, BJ10 and BJ11. Exercise desktop, tablet and phone across navigation-heavy
cases; repeat failed responsive cases at all three widths after a fix.

For each pair record:
- Same final facts, priority, source manifest and build? If not, not comparable.
- First useful result and goal finish; what remained open?
- Extra user-chosen detours versus avoidable extra prompts/actions.
- Worst recovery point, lost context, repeat facts and time to regain the task.
- One flow hypothesis (for example: return from drug-plan help to the pending
  pharmacy confirmation rather than general plan browsing), supporting events,
  proposed change and falsifying evidence.

Do not prescribe an exact universal question order or optimize for enrollment
conversion. Counterfactual variations change phrasing and detour timing without
changing facts; reserve those for a held-out pass after fixes, not prompt tuning.
