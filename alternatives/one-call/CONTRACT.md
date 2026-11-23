# One-call loop: module contract

Experimental variant on branch `feature/one-call-loop`. One model call per typed
turn reads the message, saves what it learned through tools, asks code for
facts, and writes the reply. Code owns every date, amount, check and plan
result. This file is the interface the modules are built against. If a
signature here cannot work against the real code, say so in your hand-back and
propose the smallest change; do not silently diverge.

## Rules for every module

- Write only inside `alternatives/one-call/`. Never edit `alternatives/advisor-first/`,
  `alternatives/chat-first/`, `cms-slice/`, `infrastructure/` or any protected variant.
  Reuse their code by importing it (`import _paths` first; see `_paths.py`).
- No network and no live model calls, in code you run or in tests. Tests use a
  scripted transport (`ResponsesClient(key='synthetic', model=..., transport=fn)`),
  temporary ledgers and fictional people only.
- Python 3.10 compatible, standard library only, `unittest` only. Tests live in
  `alternatives/one-call/tests/test_*.py` and start with
  `sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths`.
  Run them with `cd alternatives/one-call && python3 -m unittest discover -s tests -q`.
- Logs carry no content: fixed literal format strings, and never a message,
  reply, prompt, payload, report value or tool argument as a log argument.
- No Medicare facts in code or prompts you write. Facts reach the model only
  from the reviewed, owner-accepted sources that advisor-first already loads.
  No case-specific scripts, canned replies or keyword lists that route
  conversation. The model reads meaning; code checks structure and facts.
- No git commands that change the repository (no commit, checkout, stash, reset).

## Modules and owners

| File | Purpose |
|---|---|
| `one_call_tools.py` | Tool schemas and `ToolRunner`, wrapping advisor-first's deterministic code |
| `one_call_prompt.py`, `prompt/core.md`, `prompt/playbooks/*.md` | The fixed instructions, the per-turn input and the reply schema |
| `one_call_check.py` | The narrow reply check |
| `one_call_agent.py` | The model loop: one request, at most one tool round, budget and transport |
| `one_call_flow.py`, `one_call_reconcile.py`, `one_call_server.py` | The conversation subclass, the background record pass and the server |
| `sim/` | Simulated-person test harness and graders |

## `one_call_tools.py`

```python
TOOLS: list[dict]          # Responses API function tools: {'type':'function','name','description','parameters','strict':True}
def field_catalog(flow) -> list[dict]
    # Every profile meaning the model may save: [{'id','label','purpose','choices','fields'}], stable order.

class ToolRunner:
    def __init__(self, flow, owner, guide, record, message, *, today=None, asked=None): ...
    plans_requested: bool  # offer_plans was called this turn
    plans_offered: bool    # ... and code found the profile ready
    guide: dict            # working copy; successful saves update it
    record: dict           # working copy; successful saves update it
    results: list[dict]    # every call in order: {'name','arguments','output'}
    saved: list[dict]      # accepted updates: [{'id','entity','fields'}]
    cards: list[dict]      # UI card dicts requested with show_card (advisor-first card shape, keyed by 'kind')
    def run(self, name: str, arguments: dict) -> dict
        # Never raises for a bad model request: returns {'ok': False, 'error': '<fixed_code>'}.
```

Tools (names are fixed):

- `save_profile_fields(updates)`: each update is advisor-first's update shape
  (`{'id','entity','fields','subject','correction'}`). Goes through
  `classify_update` and `flow.capture(..., method='direct_report')`. Returns one
  outcome per update (`accepted | already_known | needs_confirmation | rejected`
  with a fixed reason code) and the ids still open afterward. Each update runs
  advisor-first's own extraction validators before capture, so a value the
  person did not state is rejected. A correction of an existing value is
  accepted on the same terms. A change to who the coverage is for, once personal
  reports exist, returns `needs_confirmation` and is applied only when the
  person confirms through a code-built control; the reports stay attached and
  the old value is kept in history. (An earlier line of this contract said that
  correction "must be accepted"; this replaces it.) Code asks for a confirmation
  only for that change and for a report that contradicts a saved value
  (`conflicting_report`). Any other `needs_confirmation` is not saved and is
  left to the conversation. A first-time value the validators accept, the goal
  (T01) and its words included, is saved with no confirmation. Outcomes name an
  update by index and field id only and never echo model-supplied text.
- `get_signup_dates()`: sign-up window, Part A and B starts, Medigap window and
  the job-coverage window, computed by existing code from the saved reports.
  Dates returned as ISO strings plus a plain-words `basis` for each.
- `check_doctor(name, place)` and `check_medicine(name)`: use the flow's
  configured check services; return `{'ok': False, 'error': 'check_unavailable'}`
  when none is configured.
- `get_plan_status()`: readiness for each outcome, the missing inputs and, when
  the engine is configured, its state, picks and no-pick reason. Never a ranking
  invented here, and never a plan list, a group label, a plan name or a number
  of plans.
- `offer_plans()`: no arguments. The model calls it when the person asks to see
  plans, compare plans or move on to plans. Ready (`plan_review` `canReview`,
  read through `journey_completion.reviewed_status`): returns
  `{'ok': True, 'ready': True, 'shown': 'review_and_see_plans'}`, and the
  conversation ends the turn on advisor-first's guided close with its one
  button, keeps the first reply block only and delivers no model question. Not
  ready: returns `{'ok': True, 'ready': False, 'missing': [{'id', 'label'}]}`
  and nothing else. The request is remembered for the visit until the close has
  been shown. Independently of this tool, a typed turn ends on the close
  whenever `journey_completion.closing_due` is true.
- `show_card(kind)`: builds an existing card kind from state and appends it to
  `cards`. Unknown or unsupported kinds return a fixed error.

## `one_call_prompt.py`

```python
def static_instructions(flow) -> str
    # Byte-identical on every turn of every visit for the same accepted sources:
    # core rules, all playbooks, the field catalog and the fact library
    # (every owner-accepted fact, rule statement and lesson, each with its id).
def fact_texts(flow) -> dict[str, str]      # fact id -> text, the same set rendered above
def turn_input(*, transcript, profile, open_items, readiness, education,
               concerns, today, pending_note=None, stage=None) -> str   # one JSON string, stable key order
REPLY_SCHEMA: dict                          # strict JSON schema for the final output
REPLY_SCHEMA_NAME = 'daylight_one_call_reply'
```

Final reply (all keys required; nullable where shown):

```json
{"reply_blocks": [{"text": "…", "fact_ids": ["…"]}],
 "question": {"target": "T05 or null", "text": "…"} ,
 "pause": false,
 "detail_step": "talk",
 "concerns": {"why_now": "… or null", "worries": ["…"], "tried": ["…"]}}
```

`question` may be null only when `pause` is true or nothing useful is open.
The same reply describes the conversational move in `detail_step`. Its values are
`talk`, `invite`, `agree`, `later` and `requested_work`. Only an invitation that
reached the screen can make the next acceptance grant visit-wide permission
for profile questions. A direct request permits its own prerequisites.
`stage.detail_permission` is visit-local and separate from data-use consent.

`reply_blocks` has one to four blocks. `fact_ids` names the library facts a
block states. `transcript` is the whole visit: `[{'role': 'person'|'daylight', 'text'}]`.

## `one_call_check.py`

```python
def check_reply(reply: dict, *, grounding: dict) -> dict
# grounding = {'person_text': [str], 'reports': <json>, 'tool_outputs': [<json>],   # whole visit, not only this turn
#              'fact_texts': {id: text}, 'open_ids': set[str]}
# returns {'ok': bool, 'blocks': [kept blocks], 'rejected': [{'index': int, 'code': str}],
#          'question': question-or-None, 'question_code': None | str}
```

Narrow on purpose. It rejects a block only for: an amount, percentage, date or
plan/doctor/medicine name that appears nowhere in the grounding
(`ungrounded_amount`, `ungrounded_date`, `ungrounded_name`); a first-person plan
pick (`personal_pick`); a request for an ID, Social Security or Medicare number
(`identifier_request`); a `fact_ids` entry that is not in the library
(`unknown_fact_id`). The question is dropped only for `identifier_request` or a
`target` that is neither null nor in `open_ids`, or when its own text fails
any block-level check. Further block codes added after independent review:
`ungrounded_check_claim` (a stated check result with no check tool output
behind it) and `held_claim` (a claim the owner has held). It never judges
wording beyond these.

## `one_call_agent.py`

```python
class OneCallAgent:
    def __init__(self, base, *, max_tool_rounds=1): ...   # base: advisor-first NaturalAgent (client, budget, effort)
    def reply(self, owner, *, instructions, input_text, runner, request_id, reservation) -> dict
        # returns {'reply': <parsed REPLY_SCHEMA object>, 'requests': int, 'tool_calls': int}
        # raises chat.ModelUnavailable on transport, budget or format failure.
```

Each request resends the full input (response chaining by id is refused by the
route check). A turn makes at most two requests: the first, and one more after
tool results. Budget: the turn reserves advisor-first's two stage names; the
first request uses `extract`, the second uses `compose`; an unused stage is
released by `reservation.close()`. The conversation pins the reasoning effort
of these requests to `low` (`one_call_flow.ONE_CALL_REASONING_EFFORT`).

## `one_call_flow.py`, `one_call_reconcile.py`, `one_call_server.py`

Answer buttons are shown only with code-owned wording: a catalog question's
approved text and buttons when the coverage is for the person typing, and the
model's checked wording as a free-text question with no buttons otherwise.

`OneCallConversation(NaturalConversation)` replaces only the typed-message step.
It keeps advisor-first's request validation, identifier check, consent check,
continuation binding and response shape, so the existing web UI works unchanged.
It keeps the whole visit transcript in visit-scoped RAM under the same
permission rule as `advisor_memory` (no new persistence). It never guesses who
the coverage is for from words in a message. `Reconciler` runs advisor-first's
existing extraction stage after the reply, off the request path, and holds any
missed facts for the start of the next turn. `one_call_server.build_one_call()`
serves the variant on its own port (8897). A live server writes one
content-free line per typed turn to `var/one-call-turn-trace.jsonl`
(`python3 -m sim.cost` sums it per visit), and `metrics.oneCall.fallbackReason`
carries a fixed code whenever the reviewed fallback was shown.

## `sim/`

```python
sim.person.ScriptedPerson(profile)      # offline: answers what was asked from the profile's ground truth
sim.person.ModelPerson(profile, client) # live: refused unless the owner's clearance is passed explicitly
sim.graders.grade(run, profile) -> dict # profile accuracy, repeated questions, repeated teaching, turns to plans,
                                        # forbidden content, finish reached, replies rejected by the check
sim.run.run(make_flow, make_person, profiles, *, runs=1, max_turns=40) -> dict
```

The harness drives any conversation class through `flow.turn(owner, payload)`,
so the two-call loop and the one-call loop are graded the same way.
