# Complete Medicare journeys: behavior-first evaluation

D168 · November 14, 2026 · Proposed evaluation corpus v1.

**The test unit is a person accomplishing a goal across conversation, browsing,
questions, corrections and return—not a list of claims or eight scripted replies.**
The earlier PP01–PP16 corpus stays intact as clinical/coverage regression material.
This suite supplements it with twelve behavior-led personas and two paired variants
per persona: **24 planned journeys**. A later attempted run is incomplete: nine
profiles reached final user requests, BJ10 only began, and BJ11–BJ12 were not run.
It incorrectly used live models despite the offline restriction and did not retain
complete raw transcripts. See the [partial findings and execution incident](../../../audit-evidence/behavioral-live-20261114/REPORT.md). No paired run or formal pass is established.

Start with [JOURNEYS.md](JOURNEYS.md) to review the actual people and detours.
[profiles.json](profiles.json) is the machine-readable source. The
[RUNBOOK.md](RUNBOOK.md) defines how to drive, observe and grade them.

D170 adds an isolated real-browser adapter and [updated expected outcomes](EXPECTED_D170.md).
Its [implementation and offline results](../../../audit-evidence/behavioral-fixes-20261114/README.md)
are a separate pinned run, not a repair or acceptance of the historical live evidence above.

## What changes from the previous replay

| Before | This evaluation |
| --- | --- |
| Send the next stored line regardless of what the app asked | React to the actual question or visible control, using only disclosed persona facts |
| Fixed response sequence | Triggered behaviors with explicit unavailable/blocked branches |
| Backend response used as proof of the screen | Capture the route, visible result, relevant backend state and return behavior |
| Reached the last line = finished | Verify the declared goal, usable deliverable and next action |
| Predetermined product destination | Evaluate decision conditions; curiosity never predetermines Medigap or Advantage |
| Nonempty scripted reply = conversation success | Separate mechanical assertions from evidence-linked human review of answer quality |
| Count all safe exits as success | Separate goal-complete, safe-blocked, failed, incomplete and not-run |

A keep decision can complete a real decision goal. Education can finish without
personal intake. A missing critical drug input or unsupported coverage year cannot
complete a cost comparison, even if the agent explains that limitation well.
Opening an enrollment guide is never an enrollment. A complete **preparation** goal
requires an actionable, correctly scoped preparation result, not an application.

## Coverage and behavior matrix

| ID | Defining behavior | Coverage context | Declared finish |
| --- | --- | --- | --- |
| BJ01 | Beginner jumps to plans, asks from side chat, goes back | New A/B enrollment | Preparation, undecided on policy |
| BJ02 | Expert skips teaching, inspects details, corrects ZIP | A/B + G + Part D | Exact-input premium research, keep G |
| BJ03 | Interrupts cost work, changes pharmacy, revisits inputs | A/B + G + Part D | Corrected drug-cost comparison |
| BJ04 | Browses alternate path then returns to current HMO | Advantage with drug coverage | Comparison blocked on exact insulin |
| BJ05 | Disambiguates doctor, corrects office, reopens findings | First Medicare coverage | Two-doctor path comparison |
| BJ06 | Caregiver asks about himself mid-task then returns to mom | Mother A/B + G + Part D | Subject-correct research summary |
| BJ07 | Pressures for a plan name, checks details, chooses to stay | Current large-employer plan | Keep decision with timing next action |
| BJ08 | Corrects employment status after seeing timing/guide | COBRA + A only | Corrected enrollment preparation |
| BJ09 | Refuses personal questions, explores, stays undecided | Undisclosed | Education only |
| BJ10 | Types draft, navigates, refreshes; separate expiry branch | Existing Advantage | Continuity and research summary |
| BJ11 | Insists on next year, inspects sample, challenges assumptions | A/B + G + Part D | Safe block on unsupported year |
| BJ12 | Changes priorities, switches views, reverses direction | A/B active; no added coverage | Explicit wait, unresolved timing visible |

Coverage, claims, doctor/drug complexity, caregiver role, expertise, privacy and
uncertainty vary. Their purpose is to exercise different user behavior. This is
not a representative beneficiary sample or a prevalence-weighted pass-rate study.
Specialty eligibility populations remain in the existing coverage corpus; do not
claim these twelve alone establish universal Medicare coverage.

## Reactive persona rules

1. Begin with only `opening`. Keep `private_facts`, expected results and finish
   criteria outside the app/model context. Do not preload a complete guide.
2. Answer the app's **actual** consequential question from the profile. Use short,
   natural replies. For an absent fact say “I don't know”; for a declined one,
   decline. Do not invent an answer to unblock software.
3. Trigger each behavior when its `when` condition is visible. Use its action as
   intent; semantic wording variations are allowed and recorded. Do not answer
   yesterday's question just because a script says it is next.
4. After a detour, observe whether the app returns to the pending task with the
   known facts. Do not re-supply the facts to rescue it. A forced repeat is evidence.
5. If a control is missing, capture it, ask once for the intended action, and
   record unavailable/blocked if it still cannot happen. Never call a hidden
   function and count that as user navigation.
6. A scenario with changing facts uses the final corrected facts in **both** paired
   variants. The direct version omits optional detours, not material corrections.
7. Stop at verified goal completion, a genuine safe block, the hard action budget,
   or the same unanswered request twice. Record which. Do not stop merely because
   the final stored beat ran, or continue manufacturing trouble after completion.

## Choosing a better flow

There is no single optimal question order. Compare the direct and interrupted
versions **on the same build, evidence snapshot, facts, final preferences and screen
size**. Separate required user-chosen detours from unnecessary app-imposed work.

First require decision control, factual safeguards and the goal's useful finish.
Then compare unnecessary repeat questions, off-goal intake, wrong-route detours,
actions to recover, lost drafts/reports, time to first useful result and total
active time. A shorter flow that guesses, suppresses unknowns or ignores a question
loses. More turns can be appropriate when they answer the person's questions.

Use profile-paired differences, not an average that hides one catastrophic journey.
Record product defects separately from data/source blocks, harness limitations and
persona ambiguities. Change one flow hypothesis, rerun its paired cases and nearest
neighbor cases, then decide whether to keep the change. Do not add special-case
production behavior keyed to these profile IDs or their literal phrases.

Initial soft/hard budgets are **24/40 user actions**, diagnostic limits chosen for
v1, not empirically established optimal lengths. Count turns and UI actions
separately in the review. A slow source call is latency, not user indecision.

## Tools and present status

`evaluate.py` validates the corpus, creates blank run manifests and checks a
captured run's evidence and recorded judgments. It does **not** drive a browser,
call a model, grade medicine/legal truth from keywords or independently verify a
reviewer's judgment. It rejects missing/tampered artifacts and refuses to turn a
backend-only replay into a completed visible journey. Quality review and owner
acceptance remain separate from technical completion.

```sh
python3 docs/evaluations/behavioral-journeys-2026-11-14/evaluate.py validate
python3 -m unittest discover -s docs/evaluations/behavioral-journeys-2026-11-14 -p test_evaluate.py -v
python3 docs/evaluations/behavioral-journeys-2026-11-14/evaluate.py new-run BJ01 --variant interrupted --output audit-evidence/behavioral-journeys-20261114/BJ01-interrupted/run.json
python3 docs/evaluations/behavioral-journeys-2026-11-14/evaluate.py score audit-evidence/behavioral-journeys-20261114/BJ01-interrupted/run.json
```

Actual verification: corpus validates; **18 evaluator mutation tests pass**.
These tests use invented trace evidence solely to test the grader. **0/24 app
journeys executed; no completion rate exists.** The blank BJ01 manifest scores
`not_run`, as it should. See the [verification packet](../../../audit-evidence/behavioral-journeys-20261114/README.md).

Execution still needs an isolated real-UI capture adapter with the planner enabled,
and a verified runtime/source binding. Scripted offline language can test mechanics
but cannot establish natural conversation quality. This work does not restart or
change the app, source gates, stores or protected ports. No live/paid conversation
or external enrollment action is authorized by this corpus; previous owner limits
remain in force.
