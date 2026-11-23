# The one-call loop (experimental, port 8897)

This folder holds an experimental variant of the Daylight conversation. The owner ran it against a live model for the first time on 2026-11-22, and the section "After the first live visit" lists what changed because of that visit. Every test here uses a scripted stand-in for the model, so the tests show what the software does with a model's output and show nothing about how well a real model holds the conversation.

## What it is

Advisor-first, the conversation behind ports 8893 to 8895, answers a typed message with two model requests. The first request reads the message and proposes what to save. Code saves what passes its gates and builds a compacted context. The second request writes the reply from that context.

The one-call loop answers a typed message with one model request. That request carries fixed instructions, the whole visit so far, the saved profile and seven tools. The model saves what it learned through a tool, asks code for dates, checks and plan status through the other tools, and writes the reply. When the model calls tools, one more request follows with the tool results, so a typed turn makes one or two requests. Code still owns every date, amount, check and plan result, and a narrow check removes any reply block that states an amount, a date or a name that appears nowhere in the visit, the tool results or the fact library.

`CONTRACT.md` is the interface the modules were built against. The simulated-person harness in `sim/` has its own `sim/README.md`.

## How to start it

The server needs the same local setup as the :8895 demo: the model key in the repository's `.env`, the shared budget ledger and the local display database.

Double-click `Start Daylight One-Call 8897.command` in this folder, or run it from a terminal. It mirrors the repository's `Start Daylight Demo.command`: it moves to the repository root, exports the two `DAYLIGHT_FOUNDATION_*_DSN` values for the local database, sets `DAYLIGHT_DEFAULT_MODEL=gpt-6.1-sol` and a default `DAYLIGHT_TOKEN_PREFLIGHT` of `local_bound`, and starts the server from the data package's Python with `--doctor-foundation` and `--conversation-checks`.

Those two options are what put the doctor and medicine picker on screen. The server can also be started by hand:

```
cd alternatives/one-call
python3 one_call_server.py
```

Started that way it has no check services: no picker appears, and `check_doctor` and `check_medicine` answer `check_unavailable`. The server prints a line saying so. The :8895 launcher's `--doctor-chat` option has no equivalent here and needs none. On :8895 it adds a separate doctor page and its routes, which advisor-first's HTTP layer allows on port 8895 only, and `demo_server` turns it off whenever `--conversation-checks` is on. The picker is drawn from the turn response by `conversation-checks.js`, which this server serves when the checks are attached.

It listens on `http://127.0.0.1:8897/` and serves the same interface files as :8895. It refuses ports 8890, 8891, 8893, 8894, 8895 and 8896. The browser cookie has the same name as the :8895 demo's cookie, and browsers share cookies across ports on one host name. If :8895 is open in the same browser, open one of the two under `127.0.0.1` and the other under `localhost`, or use a private window.

To look at the interface with no database, no model and no network:

```
python3 one_call_server.py --fixture
```

In that mode a typed message is not read by anything. The reply is the reviewed fallback described below, with a notice that says so.

To run the tests:

```
cd alternatives/one-call
python3 -m unittest discover -s tests -q
```

## The switches

| Switch | Default | Effect |
|---|---|---|
| `DAYLIGHT_ONE_CALL_RECONCILE` | on | `0` turns off the background record pass. |
| `DAYLIGHT_ONE_CALL_TRACE` | on | `0` stops the live server writing its content-free turn trace. See "Cost per visit". |
| `DAYLIGHT_ONE_CALL_EVAL` | off | `1` adds each turn's tool outputs to the response under `metrics.oneCall.toolOutputs`, for the offline graders. |
| `DAYLIGHT_ONE_CALL_ENROLLMENT_STATEMENTS_ACCEPTED` | off | `1` lets `show_card` build the five card kinds whose sentences come from `enrollment-content.json`. See "Owner acceptance" below before using it. |
| `DAYLIGHT_PLANS_FIXES` | on | Same meaning as on :8895. |
| `DAYLIGHT_RECORDS`, `DAYLIGHT_PENDING`, `DAYLIGHT_CONVERSATION_FIXES` | on | Honoured for the two-call comparison flow. The one-call conversation always turns these three on, because its tools and prompt were built on them. |

Advisor-first's other switches, such as `DAYLIGHT_DISABLE_PILOT_KNOWLEDGE`, keep their meaning.

## Owner acceptance

Two bodies of reviewed content are accepted by the owner for other surfaces and not for this one. Each stays out of what the model reads and shows until the owner acts.

- **Pilot knowledge.** The 71 reviewed pilot facts are accepted for the surfaces `unified-8895` and `hosted-demo` only. This server claims neither surface, so none of those facts is in the fact library on 8897. The owner must extend the acceptance to a surface for this port, and that surface must then be set on the conversation (`pilot_knowledge.surface`), before they can appear. There is no environment switch for this.
- **Enrollment statements.** Advisor-first's `enrollment-content.json` is marked `awaiting_owner_sign_off` and "shown on :8895 only". Nothing from that file is in the fact library here, whatever state a single sentence carries. Five card kinds are made of its sentences: `two_paths`, `signup_route`, `trade_off`, `discussion_paths` and `finish_summary`. On this variant `show_card` answers those kinds with the fixed error `card_needs_owner_acceptance`. The owner must accept those statements for this surface before `DAYLIGHT_ONE_CALL_ENROLLMENT_STATEMENTS_ACCEPTED=1` is set.

One thing is outside that switch. The server enables advisor-first's enrollment journey the way :8895 does, so advisor-first's own code still shows that file's content in the interface: the enrollment dashboard, the sign-up guides and the cards its button flows attach. That is the :8895 interface served on another port. If the owner's acceptance is meant to stop that too, the journey has to be turned off for this port.

## What differs from the two-call loop

Only the typed-message step is replaced. `one_call_flow.OneCallConversation` subclasses advisor-first's `NaturalConversation` and overrides seven methods: `__init__`, `_turn` (a thin wrapper), `message`, `direct_disposition`, `direct_local_answer`, `replay_response` and `forget_owner`.

- **Every typed sentence goes to the model.** Advisor-first answers some typed messages without a model: "I don't know", "check later", a bare ZIP code while the budget is paused, an exact chip label, and a typed answer to a doctor or medicine check question. Here none of these shortcuts takes a typed sentence. A typed answer to a check question is still recorded by the same check code, and the message also goes to the model.
- **The model sees the whole visit.** Every exchange of the visit is kept in server memory and sent on every turn. It is never trimmed. Advisor-first sends at most six recent exchanges.
- **The model sees the whole saved profile.** Every saved report goes to the model on every turn with its value. Advisor-first sends only the reports its capability allowlists select for the current task. This is a real widening of what reaches the model provider, and the owner should review it before any live run.
- **Nothing guesses who the coverage is for.** Advisor-first's typed-message step records "self" when a message with a birthday report contains words such as "I turn". This loop saves who the coverage is for only when the model saves it through the tool.
- **The save tool runs advisor-first's own gates.** Every update the model sends goes through the validators the two-call loop applies to its first stage (`NaturalAgent.validate_output`, which includes `_validate_fields`, the Medigap proposal check and the situation check), then `classify_update`, then `capture`. A value those validators drop is rejected. One rule is stricter than advisor-first's: a ZIP code is saved only when its digits are in the person's message. A tool result names each update by its position and a catalog id and never repeats anything the model wrote, because tool results ground later replies.
- **Code asks for a confirmation in two cases only.** The first is a change to who the coverage is for once personal reports exist, with or without the model's correction flag. The second is a report that contradicts a value already saved (`conflicting_report`). In those cases the report is held in advisor-first's own pending store and nothing is saved. The turn ends on a question that code words from advisor-first's row label and the held value, with advisor-first's two buttons, "Yes, that's right" and "No, let me fix it". Only a yes to that question, at that exact state, saves the report; the tool applies it and the message still goes to the model. Any other typed message withdraws the held report and is read normally. When a change of person is confirmed, every report stays attached and the earlier value goes into revision history.
- **A first-time value is never put back to the person by code.** A value that advisor-first's validators accept and that contradicts nothing saved is saved. A doubtful first-time report (the gates' `tentative` or `unclear_scope`) comes back to the model as `needs_confirmation`, is not saved, and is not asked about by code; the model may ask about it in its own question. Coverage reports (Part A, Part B, a held plan) that need confirming are handled the same way.
- **The goal is saved from the person's own words.** What the person wants help with (T01) has no time scope and its category is a coarse label, so a doubt flag or an unknown scope on it does not hold it back. Words that fit no listed goal are saved under the catalog's own "Something else" answer. A restated goal, or a request for coverage work, replaces an earlier goal with no question, as advisor-first's planner replaces it. Moving away from coverage work contradicts the saved goal and is confirmed like any other contradiction. Once a goal is saved, a goal question from the model is dropped by the reply check (`target_not_open`).
- **Answer buttons appear only under wording that code owns.** When the model's question targets an open catalog field that has choices and the coverage is for the person typing, the turn delivers that field's approved catalog question with its buttons, and the model's wording is not shown. When the coverage is for someone else, or who it is for is not saved yet, or the field has no choices, or the question has no target, the model's checked wording is delivered as plain text with no buttons, and the typed answer comes back through the model and the validated save.
- **Getting to plans is decided by code.** The handoff is advisor-first's guided close ("Your plan from here") with its one button, which leads through its review step to the Plans page. A typed turn ends on it when `journey_completion.closing_due` says it is due: the saved profile can be reviewed and the close has not been shown for these exact details. On that turn no question from the model is delivered. When the model calls `offer_plans`, the request is remembered for the visit, the close is shown again even if it was shown before, the reply is cut to its first kept block, and the details advisor-first would ask before its close are set aside for the visit. When the profile is not ready the tool returns only the ids and labels of the missing details. The request stays owed until the close has been on screen, so the model does not need to call the tool a second time.
- **A detail asked before the close is asked by code.** When the profile can be reviewed and advisor-first wants one detail first (the birthday month, or a Medigap price detail when the close will point to Medigap), the turn ends on that question in advisor-first's wording. Its question ledger then counts it, stops asking after four turns, and the close follows. This applies when the coverage is for the person typing. For a helper those details are set aside and the close is shown.
- **Open checks never hold plans back.** Plan readiness (`plan_review.readiness`) reads reports only. An unchecked doctor or medicine is listed there as a hold to show, and the Plans page shows it as not checked. On a handoff turn the picker is kept off the screen so the close is the one thing asked. The one exception is a name the person typed in that same message when they did not ask for plans: its picker comes first and the close follows on the next typed turn.
- **The doctor and medicine picker runs from code.** When the check services are attached, advisor-first's post-processing runs its check controller on every typed turn. A doctor or medicine saved in that turn gets its picker in the same turn, with code's wording and choices, and the picker replaces any question the model asked. The model does not have to call `check_doctor` or `check_medicine`. Advisor-first reads "no button question this turn" as a pause and holds the picker back; here a reply without a button question is an open conversation, so the picker still appears. The picker needs working mode, which means a saved goal of finding or reviewing coverage.
- **The fallback says what was saved.** When no model reply can be shown and the message saved something, the reply is advisor-first's own acknowledgement built from the profile rows ("I've saved what you told me: ..."), followed by the next open question. A doctor or medicine the person typed is named even then.
- **Reasoning effort is pinned.** Every one-call request asks for `low` reasoning (`one_call_flow.ONE_CALL_REASONING_EFFORT`), whatever advisor-first's agent holds. The background record pass is advisor-first's own extraction stage and keeps advisor-first's setting.
- **The reply check is narrower.** Advisor-first validates a composed reply with many rules and drops whole replies. Here `one_call_check.check_reply` removes single blocks for six structural reasons, and the conversation adds advisor-first's own held-claim guard and two length bounds.
- **One retry.** When a block is rejected and the turn made only one request, the turn's unused second budget stage pays for one more request with tools turned off. That request is told only the rejection codes.
- **A background record pass.** After the reply is delivered, `one_call_reconcile.Reconciler` runs advisor-first's existing extraction stage on the same message in a worker thread, with its own budget reservation. Facts it finds that the save gates accept and the profile does not hold are kept in memory. The next typed turn of that visit applies each one only if its field is still open, and tells the model which field ids code filled in. The pass never changes saved state between turns.
- **No interpreter reading of the discussion.** Advisor-first's first request also proposes a discussion mode, a task and a coverage decision. This loop has no such reading. A saved goal of finding or reviewing coverage puts the visit in working mode, exactly as advisor-first treats that goal when it is tapped as a button. Pausing comes from the checked reply. A coverage path is recorded only from the on-screen controls.
- **The standing question is released each typed turn.** Advisor-first returns to an unanswered question until it is answered or passed twice. Here the model reads the whole visit and chooses what to return to. A question shown four times without an answer is still parked.
- **Typed answers to a check question.** `OneCallConversation.conversation_checks` is a property. Whatever check controller is assigned to it is wrapped in `TypedChecks`, which passes everything through except `text_answer`: the typed answer is recorded by advisor-first's own method, and the wrapper then reports "not handled" so the message also reaches the model.
- **An older context policy is refused.** A typed message whose context policy is not `natural-context-v3` deletes the visit's transcript, tool outputs, concerns record and held facts, and is answered with status 428. Advisor-first serves such a request with a reduced context.

## What is reused unchanged

Request validation, the identifier check, the consent check, continuation binding, the turn journal and replay, recovery, saving, every button and structured action, and the whole response post-processing are advisor-first's code and run as they are. That includes the planner's delivery step, which decides how each turn ends and produces `conversationNext`, and the builders for `questionProgress`, `profileProgress`, `whatsLeft`, `planReadiness`, `enrollment`, `cmsChecklist`, the guided close and the conversation checks.

A tapped answer sent with AI permission still gets advisor-first's own one-request composed reply, written by its composer and its prompt. The question, the answer and any reply shown are added to the visit transcript so the one-call model sees them on the next typed turn. A button pressed with no AI permission adds to a transcript that already exists and never creates one.

The tools wrap advisor-first's gates (`classify_update`, `flow.capture`, `classify_situation`, `validate_coverage_reports`), its date code, its check controller and, on the server, `recommendation_http.evaluate`. The fallback uses `applicable_rules.floor_statement` through advisor-first's `recovery_statement`, followed by the next open question in its catalog wording. The education ledger is `conversation_records.record_shown`, and the delivered-concept record that the pre-enrollment checklist reads is updated through `education.plan_update`.

`one_call_server.build_one_call` builds advisor-first's server with `server.build`, re-classes the conversation it constructed with `OneCallConversation.adopt`, applies the switches `demo_server.build_demo` applies for :8895, and installs the same HTTP layer with `demo_http.install`. `demo_server.build_demo` itself cannot be called for this port, because it turns the planner, the records and the checks on for port 8895 only.

## What a response carries

Each typed turn publishes its counts under `metrics.oneCall`: `requests`, `toolCalls`, `rejected`, `rejectedCodes`, `questionCode`, `fallback`, `retry`, `reconciled` (facts the background pass supplied and this turn applied), `saved`, `confirmed`, `staged`, `questionDelivery` (`catalog`, `free_text`, `confirmation`, `pre_close` or `plans_handoff`), `factIds`, `failure`, `fallbackReason` (a fixed code when the reviewed fallback was shown, otherwise null), `plansAsked` (the model called `offer_plans` this turn) and `plansHandoff` (code put the close on this turn). `metrics.llmCalls` equals `requests`. The background pass's own request happens after the response and is not counted in it.

## Cost per visit

The live server writes one JSON line per typed turn to `alternatives/one-call/var/one-call-turn-trace.jsonl`. Advisor-first's server confines only the guest store to its own folder, so the trace stays in this one, and `var/` is ignored by git. A line holds the time, an opaque visit id (a hash of the owner digest and the visit, never the owner token), the turn number, the number of model requests, the names of the tools called, the rejection codes, whether the fallback was shown and its reason code, the retry flag, the number of reconciled fields, whether the close was put on the turn, the input, cached and output token counts, the amount the budget ledger settled for the turn in billionths of a dollar and in dollars, the number of requests the ledger could not settle, and the seconds the turn took. It holds no message, reply, value, name or tool argument. A turn that ends in an error is written with the reason `turn_failed`. Button turns and the background record pass are not in it.

To see requests, tokens and dollars for each visit:

```
cd alternatives/one-call
python3 -m sim.cost
```

A different trace file can be given as the one argument. The fallback reason codes are the ones in `metrics.oneCall.fallbackReason`: a model or transport code such as `invalid_structure` or `transport_or_format`, `reply_rejected` when no block passed the check, `reply_check_unavailable`, `input_bound`, or `synthetic_fixture`.

## After the first live visit

The owner's first visit on 8897 (2026-11-22) led to these changes.

- **Plans.** The person asked for plans three times and was never handed over. In advisor-first's delivery step a question the model words outranks the close, and the close is then withdrawn. The variant passed the model's question on every turn, so the close stayed due and was never shown, and the "Review your info" button is drawn only on a turn that ends on the close. Code now drops the model's question when the close is due, and `offer_plans` gives the model a way to ask for it. Whether that visit's profile was ready cannot be told from the transcript.
- **Plan counts.** `get_plan_status` passed the engine's group labels and the number of plans in each group to the model, which repeated them. It now returns readiness, the missing inputs and the engine's state, picks and no-pick reason only.
- **Doctor and medicine picker.** That server was started without `--conversation-checks`, so there were no check services. The start script turns them on.
- **"Let's keep going with the next useful detail."** This was the fallback after the person typed a doctor's name with her office. Offline, the validators accept that report with or without the office in the value, and the reply check passes a reply that names the doctor and the street. The next question had moved on, which shows the save ran, so the reply after the tool round was lost to a format, transport or check failure. A turn that used tools has no budget stage left for a second attempt. The cause could not be narrowed further without a trace. The fallback now names what was saved, and the trace records the reason code.
- **Goal confirmation and the repeated goal question.** Both are covered under "What differs from the two-call loop".

## Known limits

- **One live visit.** The owner has run one visit. No test and no agent has made a live call. Prompt quality, tool use, cost and latency are unmeasured beyond that visit.
- **Budget stages.** A turn reserves advisor-first's two stage names. The first request uses `extract`, and the request after tools or the retry uses `compose`. A turn that used tools therefore has no stage left for a retry. The ledger and the per-turn trace label the requests with those borrowed names. The background pass adds one more reserved request per typed turn.
- **Request bound.** The variant's own bound is 400,000 bytes for one request (`ONE_CALL_REQUEST_BYTES`). Measured here, the fixed instructions are about 65,000 characters with the real field catalog and 38 facts, and a first request is about 77,000 bytes. When a visit grows past the bound, the turn ends in the fallback with code `input_bound`, as advisor-first reports an oversize composition, and stays that way for the rest of the visit. Advisor-first's sender (`NaturalAgent._complete`) also refuses any single stream line over 200,000 bytes and any reply text over 20,000 characters. Those two limits apply to what the provider sends back and are unchanged.
- **A small library.** The fact library on 8897 holds 38 entries: 18 lessons, 2 evidence lessons and 18 accepted rules. It holds no pilot-knowledge fact and no enrollment statement (see "Owner acceptance"). Receipts that let a replayed reply be withdrawn when a pilot fact goes stale are not implemented and would be needed if those facts are accepted here.
- **Plain-text questions are not tracked.** A question delivered as plain text is not counted by advisor-first's question ledger, so it is never parked, and a helper's visit shows no answer buttons for profile questions. The one question code delivers itself before the close is counted.
- **The close can follow a turn that asked for something else.** When the close is due, the model's question on that turn is dropped, whatever it was. The person can still type, and the next turn is an ordinary one.
- **A request for plans is known only through the tool.** Code never reads the person's words for it. If the model does not call `offer_plans` and the close was already shown for the current details, nothing new appears; the "Review your info" button is on screen only on a turn that ends with no question.
- **Details set aside for plans.** After `offer_plans`, the birthday month and the Medigap price details that advisor-first asks before its close are not offered again in that visit. The Plans page asks for the Medigap details itself.
- **A stale pass is withdrawn.** Clearing a visit (an older context policy, a new start, a deleted guest) withdraws any record pass still queued for it before it sends anything, and drops the result of one already in flight.
- **Models.** The tools are sent in the OpenAI Responses format only. The server removes other providers' models from the conversation, so choosing one in the interface is answered with "That AI model is unavailable". Reasoning effort is pinned to `low` for the one-call requests.
- **Plans-page chat.** A message sent from the Plans page arrives with a Plans context. Advisor-first validates it and binds the response to it, but this loop does not show that context to the model, so the model cannot discuss the plans on screen and a plan name it repeats would be removed by the check.
- **No reply blocks before the turn ends.** Advisor-first can show checked blocks while a reply is still being written. This loop shows the reply when the turn is complete.
- **Doctor and medicine checks.** The tests run advisor-first's real check controller over its fictional doctor and drug services (`tests/behavioral_offline_server.py`). The data package imports its database driver when loaded, and the driver is not installed where the tests run, so the test support puts an empty stand-in module in its place; nothing connects. The real services behind `--conversation-checks` are not exercised by any test. The picker appears only in working mode, so a visit with no goal of finding or reviewing coverage saved gets none.
- **Working mode is coarse.** With a saved goal of finding or reviewing coverage the visit stays in working mode, so the guided close can appear right after a turn that only explained something.
- **The record pass skips some facts.** It supplies fields that are open in the profile. It does not supply corrections, doctor or medicine item details, or anything the gates would want confirmed.
- **Live start.** The owner has started the server by hand, without the check services. The start script is checked for its lines, its mode and its shell syntax, and has not been run by a test or an agent. The guest store is at `alternatives/advisor-first/var/demo-8895/one-call-8897.sqlite3`, which advisor-first's server requires to be inside that folder. The two bake-off factories have not been run with no client.
- **Local data.** Tests skip with a stated reason when advisor-first's profile contract sources are absent from the checkout.

## Files

| File | Purpose |
|---|---|
| `one_call_flow.py` | The conversation subclass, the visit store and the typed turn. |
| `one_call_reconcile.py` | The background record pass. |
| `one_call_server.py` | The 8897 server and the shared :8895 switches. |
| `Start Daylight One-Call 8897.command` | Starts the server with the :8895 demo's local wiring and the checks. |
| `sim/cost.py` | Sums the turn trace per visit: `python3 -m sim.cost`. |
| `sim_factories.py` | `make_two_call_flow` and `make_one_call_flow` for the bake-off harness. |
| `one_call_tools.py`, `one_call_prompt.py`, `prompt/`, `one_call_check.py`, `one_call_agent.py` | The tools, the instructions, the reply check and the model loop. |
| `sim/` | The simulated-person harness and graders. |
| `tests/` | Offline tests. `tests/_one_call_support.py` holds the scripted transport and the visit driver. |

For a like-for-like bake-off, pass the factories to the harness, for example `python3 -m sim.run --flow-factory sim_factories:make_one_call_flow ...`. Called with a scripted client they are offline. Called with no client they build the live wiring and make paid model calls, which needs the owner's clearance.

## Changes after the owner's second visit (November 22, 2026)

- **Working mode.** A reported doctor or medicine, or a request to see plans, puts advisor-first's planner in working mode whatever goal is saved. Advisor-first shows its doctor and medicine pickers and reaches its close only in that mode, so a goal saved under other words used to leave both off.
- **Getting to know the person.** The fixed core prompt and discovery playbook lead with why the person came, what concerns them and what they have tried. The advisor answers questions and saves volunteered facts along the way. Before asking for profile details, it connects those details to the person's goal and asks permission in a separate turn. The next input carries the person's response in the transcript and the visit's `detail_permission`. A person can decline, change their mind, or request specific work directly. Elapsed turns and completed discovery topics cannot grant permission.
- **Fallback sentence.** After a saved answer the fallback says one plain sentence in the person's own words. A structured value is never printed.

## Changes after the owner's third visit (November 22, 2026)

- **Picker choices.** Directory candidates whose displayed label is identical are shown as one choice. The answer still goes through advisor-first's own `check_answer` path.
- **After a pick.** The chat shows a short confirmation: advisor-first's existing `doctor` evidence form (the doctor, the office, the date checked and its Medicare lines) or a one-line `note` naming the medicine product matched. The full per-plan rows stay on the server for the close, the sorting and the Plans pages. `/api/conversation/checks` answers with the same short form.
- **The ending.** When plans were asked for, this turn or earlier, and the profile can be reviewed, the turn ends on advisor-first's close with its summary, direction line and one button, whatever happened to the model's reply. When the profile cannot be reviewed yet, the turn ends on a short code-built line and the first missing detail in its approved wording, and the close appears once the last detail is in. A request for plans saves a goal of finding coverage. The close does not depend on the enrollment-statements switch.
- **Parts A and B in words.** "My card says Part A and Part B both start December 1" is now counted by plan readiness. advisor-first wrote the derived answer with no record of whom it was about, so the close could never become due in a visit like the owner's.
- **One retry after a tool round.** A reply that is lost or rejected after a save gets one more request with its own budget reservation and tools off. Three request-path requests at most.
- **Reply check.** A result inside a condition, a task still to do or a wish ("we'll check whether Dr. Wise is in network") is not a claim.
- **Trace.** Each line also records `can_review`, `missing_count`, `plans_requested`, `close_due`, `handoff_reason` and a value-free `fallback_detail`.
