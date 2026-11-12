# Milkman chat: baseline, implementation and model comparison

October 18, 2026. Production configuration remains **gpt-5.4**, with explicit **none** reasoning. No smaller model was selected automatically.

The final current-model run reduced total estimated session cost by **40.4%**, reduced median visible reply length from **67 to 46 words**, and increased cached-input share after the first model-using turn from **28.1% to 63.1%**. A separately measured **ten-visible-turn session cost $0.06852**, with no fallback. The cost targets were met for this synthetic sample; conversation quality still has gaps described below.

## Method and scope

Ran the eleven requested multi-turn fixtures against local live HTTP endpoints. Each scored session includes an opening and three user turns: **44 visible conversational turns / 33 user messages** per configuration. The comparison-view setup is a separate deterministic, zero-model action and is excluded from the conversational denominators. Baseline openings made real API requests; after-change openings are the exact browser-rendered local welcome with zero API tokens/cost. A source snapshot of the instrumented baseline is preserved locally in ignored `tmp/milkman-instrumented-baseline.tar.gz`.

API usage was captured per request and aggregated per turn, including tool rounds and correction retries. Estimates use the versioned standard-rate table in `config/model_rates.json`; reasoning tokens are included in output-token cost, not charged again. The baseline JSON and each final run include per-turn and per-session usage, visible synthetic text, errors and fallback status. Those raw files are git-ignored. Markdown summaries contain no transcripts. Failed development trials and the first complete iteration remain in ignored `reports/eval-private/`; they are excluded from this final before/after table and are additional development usage.

The model comparisons were single runs, with warm cache reuse across synthetic sessions. They do not establish statistical significance or cold-start guarantees. Cached-token figures come from actual API `usage`, not prompt-size estimates. Prefix stability is also covered by automated payload checks. The fair cache metric below excludes the first model-using turn of each session.

The account key is shared with another project. **Account-level billing cannot be attributed to Milkman. Recommend a dedicated Milkman project/key.** These application-level estimates do not reconcile the account invoice or claim that the original reported charge belonged entirely to Milkman.

## Before / after, same model and reasoning

| Measurement | Baseline | Final GPT-5.4 / none |
| --- | ---: | ---: |
| Visible conversational turns | 44 | 44 |
| Model calls | 64 | 44 |
| Input tokens | 172,346 | 114,880 |
| Cached input tokens | 43,008 | 72,704 |
| Output tokens | 6,686 | 9,019 |
| Reasoning tokens | 0 | 0 |
| Total estimated cost | $0.43439 | $0.25890 |
| Median cost / visible turn | $0.00675 | $0.00595 |
| Mean cost / four-turn session | $0.03949 | $0.02354 |
| Cached-input share after first model turn | 28.1% | 63.1% |
| Median reply words, including question | 67 | 46 |
| Replies over 120 words | 2.3% | 0.0% |
| Turns with more than one question | 1 | 0 |
| Unsupported numeric turns, normalized money formats | 11 | 0 |
| Banned recommendation screening flags | 0 | 0 |
| Unchecked-priority satisfaction screening flags | 0 | 0 |
| Exact repeated-question flags | 0 | 0 |
| Repeated explanation-offer screening flags | 3 | 1 |
| Jargon-before-definition turns, screening | 16 | 9 |
| HTTP errors | 0 | 0 |
| Safe fallback turns | 0 | 1 |

Output tokens increased because the model now emits strict transient state updates as well as prose. Lower input volume, real cache reuse, local openings and deterministic actions still reduced overall cost. The measured ten-turn session cost **$0.06852**, versus the **$0.10** starting target; median final turn cost **$0.00595** is below **$0.01**. The older ten-turn figures in individual summaries are explicitly projections, not measured sessions.

## Model / reasoning comparison

All runs used the same final instruction, tool and schema prefix, a 600-token output limit, four rounds, six tool calls, and at most one correction retry. Overrides were process-local evaluation flags and never wrote `.env`.

| Configuration | Median turn cost | Mean four-turn session | Model calls | Median words | Cache share after first model turn | Fallbacks / user turns | Jargon turns | Repeated explanation offers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5.4 / none | $0.00595 | $0.02354 | 44 | 46 | 63.1% | 1/33 | 9 | 1 |
| GPT-5.4 / low | $0.00692 | $0.02760 | 43 | 44 | 58.6% | 0/33 | 11 | 2 |
| GPT-5.4 mini / none | $0.00124 | $0.00604 | 44 | 40.5 | 54.3% | 6/33 | 8 | 0 |
| GPT-5.4 mini / low | $0.00194 | $0.00853 | 43 | 42 | 48.9% | 1/33 | 11 | 0 |

All final runs had zero multi-question turns, zero normalized unsupported-number flags and zero banned recommendation flags. These are narrow checks, not proof that every insurance statement was supported.

**Recommendation: retain GPT-5.4 / none for now.** It meets the measured cost targets and had substantially fewer fallback failures than mini / none. GPT-5.4 / low removed the remaining fallback in this sample but cost more and did not improve the jargon/repeated-offer screens. Mini / low is a promising cheaper candidate, but the review below does not support switching production yet. The owner should decide any configured-model change after reviewing the local visible-text reports.

## Quality rubric and review findings

- **Length and questions:** reply length improved; no final reply exceeded 120 words or asked multiple questions. Exact repeated-question screening found zero, while the more useful repeated-explanation-offer screen still found a current-model failure. A response can ask a differently worded version of the same question without matching the exact-question screen.
- **Jargon:** the stronger screen checks for ordinary definitions of Original Medicare, Advantage, Medigap, Part D, prior authorization and SNP. It found improvement but not the zero-jargon goal. Beginner replies sometimes introduce Part A/B before explaining hospital and medical coverage. These are screening counts, with findings retained in the ignored JSON for review.
- **Tool use:** explicit Advantage/premium browsing, a county-confirmed browse, the doctor-plus-premium list, exact-ID detail/comparison and the final drug-plan browse can bypass the model. Catalog and comparison cards retain engine order. Pure identity/privacy replies and the experienced-person brevity turn did not make unnecessary lookups in the final current-model run. On-screen explanations receive freshly reconstructed source summaries, so no extra model tool call is necessary to cite them. Medicine identity guessing and unselected-plan lookup are blocked in tests.
- **Grounding:** all final numeric claims pass normalized current-turn citation checks. Raw first-pass numeric screens flagged equivalent dollar formatting; `scripts/eval_rubric.py` corrects those false positives without changing usage or reply text. No current-model recommendation or satisfied-doctor-priority flag was observed. This does not certify all prose: manual review still found mini replies that generalized a drug deductible to all initial prescription costs, or added network/cost-sharing detail beyond the short cited evidence. Mini / low also exposed internal fact identifiers in prose. These are reasons to retain the current model.
- **Remaining conversation issues:** some beginner replies still offer an overview after the person already asked to learn. Requests for more depth were not consistently answered with more depth. Current-model doctor follow-up produced one safe fallback. These are real quality limitations, not successes hidden by a lower cost figure. No live retiree/caregiver study or qualified clinical/compliance sign-off is claimed.

## Implementation / verification

Phases 0–5 completed in order and were reported during implementation. The page has the exact local welcome, four opening choices and no form or opening cards. A collapsible panel edits tab state, including human-readable term/selection controls. An in-flight panel edit was verified in Chrome to win over the pending model response. The browser retains only six recent turns of assistant reply/question text. Only cited sources are rendered, collapsed; all 70 plan cards remain reachable in four coverage groups, with the first expanded and engine order preserved within groups. Position numbers were removed and source conflicts remain visible.

The full final automated suite passed **157 tests**, including source-data integrity, deterministic ordering, identity boundaries, request limits, correction/fallback behavior, usage accounting, HTTP guards, private transcript files and portable releases. Browser checks covered the local opening, source disclosure, all-card reachability, latest-only quick replies and the panel edit race. The final portable snapshot is rebuilt and verified separately; no source facts or sorting implementation were changed.

## Owner-requested text logs: scope change

During this task, the owner explicitly requested that all conversations be saved to text files. This supersedes the implementation brief's original no-stored-transcripts constraint. New visible conversations are saved locally in **`reports/conversations/<tab-UUID>.txt`**. A tab keeps one file; refresh/start-over starts a new file. Logs capture the local welcome, user messages, replies/questions, cited sources, displayed plans and failed requests. Existing synthetic evaluation replies remain in their original ignored local reports; no missing historical resident conversations are invented or reconstructed.

Directories use owner-only access and files use mode 0600. The logger redacts API-key patterns and the configured key, excludes hidden reasoning/raw API payloads/state objects, and never feeds saved files back into model context. Logs are ignored by Git and excluded from portable bundles. The browser privacy copy now describes this behavior and surfaces save failures. Usage/timing logs remain content-free. API requests retain `store: false` and the key stays server-side.

## Reproduce / inspect

From the workspace root, see `docs/MILKMAN_CHAT_IMPLEMENTATION.md` for server and evaluation commands. Run `scripts/eval_rubric.py` on report JSON to reproduce normalized numeric, jargon, repetition and cache screening without API calls. The eleven fixtures and the separate ten-visible-turn fixture are in `tests/fixtures/`. Final raw reports are `baseline-eval.json`, `after-gpt54-none-eval.json`, `after-gpt54-low-eval.json`, `after-mini-none-eval.json`, `after-mini-low-eval.json` and `ten-turn-eval.json`; all are local and git-ignored.

Rates and supported request settings were checked against [GPT-5.4 documentation](https://developers.openai.com/api/docs/models/gpt-5.4), [GPT-5.4 mini documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini), and [official prompt caching guidance](https://developers.openai.com/api/docs/guides/prompt-caching). Standard text rates per million input/cached/output tokens are respectively $2.50/$0.25/$15 for GPT-5.4 and $0.75/$0.075/$4.50 for GPT-5.4 mini. Estimates exclude unrelated account traffic and are not invoices.

## Subsequent owner correction: retain the starter questions

After this evaluation, the owner requested restoration of the original Chapter-style starter questions. The Get started page and seven/eight-question flow are restored, with Back and Edit answers controls. Answers populate transient chat state and are saved in the same local text log through a deterministic endpoint. No paid model opening or intake calls were reintroduced. The cost comparisons above measure the earlier conversational scenario set; they are not a new evaluation of the restored starter UI.

Restoration verification: the regression suite passed 158 tests; focused transcript checks also passed after ensuring starter Q&A precedes the chat welcome in the saved file. Chrome checks covered self/caregiver wording, both seven/eight-question branches, invalid ZIP handling, Back/Edit answers, state handoff, and removal of stale timing when changing Medicare status.
