# Milkman conversational chat

Implemented October 18, 2026 from `milkman_implementation_prompt.md`; the audit in `MILKMAN_CHAT_REVIEW.md` is the before-state.

The owner requested that the original Chapter-style starter flow be restored after the cost/conversation implementation. The page now opens with **Get started**, then asks one question per screen: who coverage is for, ZIP, existing Medicare coverage, timing only when Medicare is not yet in place, prescription coverage, hearing, vision and dental. There are seven questions, or eight with timing. Back navigation retains answers, and **Edit answers** returns to the flow. Completion opens the local chat welcome without a paid model request. The beneficiary relationship, ZIP and coverage/benefit answers populate transient state before the first chat request; a ZIP never silently confirms county. Not-sure answers become `unknown` in model state.

Each starter answer is validated and saved to the same local text file as the later conversation, through `/api/intake-answer`, without a model call. Answers are recorded in order; chat waits for that logging queue before sending its next request. The editable **What I know so far** panel remains available after intake. Refreshing or starting over discards tab memory and starts a new conversation log. Clearing a detail removes recent model history so a forgotten answer is not silently recovered.

Plan browsing, filtering, ordering, selection and comparison use `/api/catalog`. Conservative matching also handles explicit list/order/ID-comparison text without a model. Mixed questions and explanation requests use live conversation. The first plan view asks about Collier County; no ZIP is treated as proof of county residence. All 70 captured records remain reachable in coverage groups, with engine order preserved within each group. Cards preserve source conflicts and restricted eligibility. There is no personal fit score or model-chosen shortlist.

`/api/live-chat` accepts a bounded `state`, message and recent native `user`/`assistant` messages. The model receives only the last six turns, with assistant reply/question text, plus current transient state. Local source lookups provide compact educational facts when clearly relevant. Catalog context contains counts, sorting, unscored priorities, metric range/ties and conflicts; it never contains the catalog rows. Detail/comparison context includes the selected plans' numeric fields, known/unknown/conflict states and fact IDs. The browser still receives full cards.

The output contract is `reply`, `question`, `quick_replies` (at most three), `fact_ids`, and `state_update`. Strict nullable update fields are stripped when unchanged. Product identities and on-screen selections come from user actions, not model state updates. Browser field revisions prevent an in-flight reply from overwriting a person's panel edits. Only cited facts appear in the reply's collapsed Sources section.

Requests keep a constant instruction/tool/schema prefix and `prompt_cache_key`, put dynamic inputs last, set `store: false`, use explicit `none` reasoning and low verbosity, and cap output at 600 tokens, four rounds and six tool calls. Low reasoning and a smaller model are evaluation-only overrides. Only one correction retry is allowed. Invalid or incomplete output uses the requested safe fallback. Numeric values are checked against cited facts, including normalized money formatting; recommendation wording and extra questions are blocked. Long replies are flagged without another model call. These checks do not prove semantic correctness; the evaluation includes visible reply review and records limitations.

The server creates no profiles, accounts or provider conversation objects. After implementation began, the owner explicitly requested saved text conversations, superseding the original no-transcript constraint. Visible conversations now append to owner-only `.txt` files in `cms-slice/reports/conversations/`. Logs include the local opening, user messages, replies, questions, cited facts and displayed plan details, including failed requests. They exclude API keys, hidden reasoning, raw model payloads and state objects. A tab UUID groups turns; it is not an account or customer profile. Saved logs are never loaded into model context. The folder is ignored by Git and excluded from portable bundles. The UI describes local logging, and reports a save failure instead of silently claiming success. The API key stays in the ignored `.env`; `.env.example` is a placeholder. Normal usage logs contain only counts, tokens, model/tool names, flags, timing and standard-rate estimated cost. Costs use `cms-slice/config/model_rates.json`. Debug usage is returned only with `--debug-metrics`. External provider account data controls still apply to `store: false` requests.

Run from the workspace root:

```sh
python3 cms-slice/scripts/demo.py serve --env-file .env
```

For development measurement, use a separate server and run the fixtures:

```sh
python3 cms-slice/scripts/demo.py serve --env-file .env --port 8770 --debug-metrics
python3 cms-slice/scripts/eval_conversations.py --endpoint http://127.0.0.1:8770/api/live-chat --output cms-slice/reports/after-current-eval.json
python3 cms-slice/scripts/eval_rubric.py cms-slice/reports/after-current-eval.json
```

Temporary evaluation flags are `--model-id gpt-5.4-mini` and `--reasoning-effort low`; neither writes configuration. The 11 multi-turn fixtures are in `cms-slice/tests/fixtures/milkman_scenarios.json`. Raw evaluation JSON includes synthetic visible text and is git-ignored; normal application operation writes the separately requested local `.txt` conversation logs. Content-free Markdown summaries can be reviewed or committed. The instrumented baseline source snapshot is locally preserved in ignored `tmp/milkman-instrumented-baseline.tar.gz`.

See [the final evaluation](../cms-slice/reports/milkman-eval-after.md) for measurements, model comparisons, rubric limitations and the production-model decision. A dedicated Milkman API key/project is recommended because the current account key is shared with another project.
