# Simulated-person harness

The project's test profiles used to be typed in script order, whatever question
was on screen. That checks claims, not conversation flow. This harness lets a
simulated person answer the question the advisor actually asked, runs each
profile several times, and grades every run the same way for any conversation
loop that answers `flow.turn(owner, payload)`: the existing two-call loop and
the new one-call loop.

It is offline unless the owner clears a live run. See
[Live runs](#live-runs-cost-money-and-need-the-owners-clearance).

## Files

| File | What it holds |
|---|---|
| `person.py` | `load_profiles`, `ScriptedPerson` (offline), `ModelPerson` (refused without clearance) |
| `run.py` | `run(make_flow, make_person, profiles, *, runs=1, max_turns=40)` and the command line |
| `graders.py` | `grade(run, profile)` and `summary(grades)` |
| `../tests/test_sim.py` | Offline tests with a fake flow whose right answers are known |

## Running it offline

From `alternatives/one-call/`:

```sh
python3 -m unittest tests.test_sim -q

# A scripted model behind the real conversation class (no key, network blocked):
python3 -m sim.run --profiles ../../docs/evaluations/plan-paths-2026-11-12 \
  --loop two-call --runs 3 --out /tmp/sim-two-call \
  --scripted-model path/to/scripted.py:transport

# Or any offline flow object:
python3 -m sim.run --profiles ../../docs/evaluations/behavioral-journeys-2026-11-14 \
  --loop one-call --runs 3 --out /tmp/sim-one-call \
  --flow-factory some_module:make_flow
```

- `--scripted-model` names a `transport(payload) -> response` function. The
  harness builds the conversation class for `--loop` around
  `ResponsesClient(key='synthetic-offline-only', transport=...)`, as
  `advisor-first/tests/persona_runner.py` does. That is the bare class, without
  the feature switches the shared demo turns on, so its responses carry no
  `conversationNext`.
- `--flow-factory` names a zero-argument function that returns a flow. Use it for
  a flow configured the way you want to compare.
- Without `--live`, every turn runs with outbound connections blocked. A flow
  that reaches for the network fails; it does not get through.
- `--only PP01,PP05` picks profiles. `--max-turns` caps a conversation (default 40).
  `--patience profile` makes the person leave at the profile's own stop rule
  (eight or nine messages in the two older sets); the default is to keep
  answering.
- Output: one `<profile>-run<n>.json` per conversation (the run and its grade),
  `summary.json` and `summary.md`. The run files hold the full fictional
  conversation. Progress lines hold counts and ids only.

The real conversation classes need the advisor's local metadata
(`python3 -B tools/prepare_advisor.py` from the repository root). Without it the
one test that drives the real two-call class is skipped and says why.

## The people

`load_profiles(path)` reads all three corpora into one shape: id, opening, who
is typing (`self` or `helper`), ground-truth facts, scripted replies, stop rule.

| Corpus | Profiles | What it gives the person |
|---|---|---|
| `plan-paths-2026-11-12/profiles.json` | 16 | Structured facts from `person`, `ground_truth` and `expected_sorting.inputs_to_capture`; the profile's own questions |
| `medicare-personas-2026-11-08/personas.json` | 20 | ZIP, age, birth month, parts, doctors and medicines; coverage and priorities as words only |
| `behavioral-journeys-2026-11-14/profiles.json` | 12 | `private_facts`, declines, and the beats that are typed words |

`ScriptedPerson(profile, *, seed=0)` answers from ground truth:

- A question with an id is matched to a fact by that id (`T03` is the ZIP, `T06`
  the doctors, and so on). When the question offers choices, the person picks
  the choice that matches the fact and types its label.
- A question with no id falls back to a short word list. If nothing matches, the
  person says they are not sure what is being asked.
- A fact the profile does not hold gets "I don't know." A declined fact gets a
  decline.
- "What would you like help with?" is answered with the ask from the person's
  own opening.
- The profile's own questions (the "Unprompted" script lines, and the typed
  beats) are sent when nothing is being asked, in order, the last one last.
- `seed` picks the style and fixes every random choice: `terse` (0), `talkative`
  (1, volunteers one more fact per answer), `unsure` (2, says "I don't know" to
  about three questions in ten). The same seed always types the same words.

What it cannot do: press buttons or open screens (it types messages only),
judge when a behavioral beat's trigger has been met, answer a confirmation such
as "did you mean…?", work through the doctor and medicine check steps, or
answer questions outside the fifteen facts in `person.FACT_TARGETS`. A corrected
fact (a journey's `zip_corrected`) is stated in its corrected form from the
start.

## The grades

`grade(run, profile)` returns these. None of them judges whether the guidance
was right or well put; the owner assesses that.

| Grade | Meaning | How it is measured |
|---|---|---|
| `profile_accuracy` | Of the facts the person stated, the share saved correctly at the end, with `missed` and `wrong` lists | Exact for facts the person stated through an answer built from ground truth. A talkative person may answer with the profile's own scripted line for that topic; the fact asked about is then counted as stated even if the line words it loosely. In free-text openings and unprompted lines only a literal ZIP or age is counted as stated. Facts with no structured value are listed as `ungraded`. Doctors and medicines match on the name appearing in the saved text |
| `repeated_questions` | Questions asked again after the person answered them (`after_answer`), and questions asked while the answer was already saved (`while_saved`) | By question id, or by the question's words when it has no id. An "I don't know" does not count as an answer |
| `repeated_teaching` | The same teaching delivered in more than one turn | By library fact id when any turn exposes one (`basis: fact_ids`); otherwise by identical sentences of six or more words (`basis: sentences`), which misses a reworded repeat |
| `turns_to_plans` | The first turn where `planReadiness.canReview` was true, or none | Exact. `within_profile_limit` compares it with the profile's stop rule |
| `forbidden` | First-person plan picks, requests for an ID number, amounts and dates not traceable to the cards, tool outputs or the person's words | `one_call_check.check_reply`, one sentence at a time, when it imports (`method: one_call_check`); otherwise simple patterns (`method: patterns`). The harness sees only what the response exposes, so a figure that came from a tool the response does not show is counted as untraceable |
| `no_answer_turns` | Turns where the person typed something and got no reply text | Exact. `nothing_at_all` lists the turns with no question either; `after_i_dont_know` lists those that followed "I don't know" |
| `finish` | Whether the run ended in a recognised finish | `plans_handoff` (plans ready and the closing or hand-off delivered) or `finish`. `person_stopped`, `max_turns`, `error` and `call_limit` are not finishes |
| `wrong_person` | For helper profiles, replies that speak to the helper as the covered person | A pattern for second-person coverage wording ("How old are you?", "your medicines"). An approximation: it can miss cases and can flag a fair question to the helper |
| `seconds` | Median and longest turn time | Wall clock around `flow.turn` |
| `model_requests`, `rejected_replies` | Totals, when the response exposes them | Read from `metrics.llmCalls` and similar keys; `None` when absent |

`summary(grades)` adds the totals and, per profile, the differences between
its runs: how many distinct saved profiles and finishes there were, and which
fields differ. A field the person stated in some runs and not in others is
listed under `differing_fields_person_varied`; a field that differs although
the person said the same in every run is listed under
`differing_fields_same_statements` and makes the profile `consistent: false`.

## Live runs cost money and need the owner's clearance

**A live run is never started by an agent.** The repository's rule stands: no
agent-run live conversations or paid probes; the owner assesses conversational
quality.

- The command line refuses `--live` unless `--clearance` carries the owner's own
  text beginning `Owner clearance:`. It then prints the estimated number of
  model calls before anything is built, and still refuses without a budget
  (`--max-calls`) and a live flow (`--flow-factory`). The harness builds no live
  client of its own.
- The call limit is enforced during the run: a conversation stops (`call_limit`)
  before a turn that could pass it.
- `ModelPerson(profile, client, clearance=...)` raises `PermissionError` without
  that clearance text. It has no network code: each request goes through the
  `client.transport` the caller injects. It is given a persona brief (situation,
  private facts, disclosure style) and never the answer key.
- The clearance text is written into `summary.json`.

Estimate, per typed turn: two or three model requests for either loop (two-call:
read and reply, plus at most one recovery; one-call: one or two on the reply
path plus the background record pass), and one more if a model plays the
person. At about twelve turns that is 24 to 36 requests a conversation; the
ceiling at forty turns is 120. Sixteen profiles, three runs each, on both loops
is 96 conversations. These are estimates, not measurements.

A live comparison needs: the owner's clearance and call limit, a flow factory
for each loop configured the same way, the day's remaining model budget, and
the same profiles, seeds and turn cap for both loops.

## Cost of live visits

`sim/cost.py` is separate from the simulated-person harness. It reads the content-free turn trace the live 8897 server writes (`var/one-call-turn-trace.jsonl`) and prints, for each visit, the turns, model requests, input, cached and output tokens, the dollars the budget ledger settled, and how many turns ended in the fallback with which reason code.

```
cd alternatives/one-call
python3 -m sim.cost
```
