# AI-07: two-stage controller audit

November 8, 2026 (America/New_York). Tracker item AI-07: "Every model
interpretation passes a schema and rule check before any output; rejected
proposals route to clarification or a person." Related requirements: P10, D73,
D86, D90 (one recovery slot), HP-07, AI-01 (engine owns every number and rule).

**Result.** The :8893 advisor already implements the two-stage controller. This
audit found no path where model text reaches the person before its checks, and
no code change was needed. Seven contract tests now pin the acceptance so a
later change cannot quietly break it. One clause needs an owner decision: there
is no route to a person in the guest-only pilot (see Open items).

## Path map

| Path | What the model returns | Schema check | Rule checks | When a check fails |
| --- | --- | --- | --- | --- |
| Stage 1, interpretation (`natural_agent.extract`) | Proposed reports, requests and situation readings; never prose or routing | Strict JSON schema on the request (`daylight_guide_commands`), then `NaturalAgent.validate_output`: exact envelope keys, size bounds and the per-report validators | `natural_state.classify_update` per proposal: the supporting quote must appear in the person's message; hypotheticals, the wrong person and non-current coverage are rejected; unclear scope, tentative wording and conflicts become clarifications. Accepted proposals still pass the domain validators in `capture`. | A malformed envelope fails the turn before composition, with nothing changed. A rejected proposal is not recorded. An uncertain or conflicting one is held and becomes the required question. |
| Stage 2, reply (`natural_agent.compose`) | Reply, question, cited reports and evidence | Strict JSON schema (`daylight_resolved_conversation`), then `validate_composition` | The question must be one of the offered candidates, and a required clarification cannot be skipped; cited reports and evidence must be ones supplied; length bounds; no unsupported personal findings or actions; no claims of research done; plan claims need cited plan evidence; every date and amount must appear in the supplied sources (the AI-01 boundary); names must be grounded; coverage, application and provider statements must match resolved reports (`conversation_claims`). | In production one repair attempt goes to the same model and is checked again (D90). If it still fails, only an independently checked part (the approved question) is shown, or nothing is. Facts already accepted are kept. Rejected text is not shown, logged or stored. |
| Optional drafts (education, follow-ups, task work) | Teaching and task metadata | Validated separately (`_validate_education` and related) | Same literal and action guards | The draft is dropped; the checked reply still goes out. |
| Claude in development | Same two stages | `ClaudeClient` validates the JSON schema, then the same validators run | Same | Same. The router blocks Claude in the pilot (AI-04). |
| Pinned-engine legacy endpoints (`/api/agent` and similar) | Legacy guide output | Not this controller | Not this controller | Not used by the UI, not on the pilot gate's route list, and unable to reach a provider since the AI-03 bypass guard. |
| Fixture mode | Scripted, no model | n/a | n/a | n/a |

While a model call runs, only fixed status messages ("Finding reviewed
teaching…") are sent to the browser. The reply is returned only after the
checks above.

## Acceptance mapping

| Clause | Where it holds | Pinned by |
| --- | --- | --- |
| Interpretation passes a schema check before use | `validate_output` | `test_malformed_interpretation_changes_nothing_and_never_reaches_composition` |
| Interpretation passes rule checks before use | `classify_update`, `capture` | `test_report_without_a_supporting_quote_is_never_recorded` |
| Rejected interpretation routes to clarification | `queue_pending`, required question candidate | `test_uncertain_report_becomes_a_required_clarification_not_a_fact` |
| Reply passes checks before any output | `validate_composition` | `test_rejected_reply_is_never_shown_and_accepted_facts_survive` (eight cases), `test_checked_reply_is_shown` |
| Repair is bounded and re-checked | `composition_recovery` | `test_production_repair_slot_is_used_once_and_only_checked_parts_are_shown` |
| No model text streams before the checks | `emit` calls | `test_only_fixed_status_events_are_emitted_while_a_model_call_runs` |

Existing tests that already covered parts of this: `test_natural_agent`,
`test_natural_flow`, `test_response_failures`, `test_composition_recovery`,
`test_conversation_claims`, `test_name_grounding_boundaries` and
`test_education_followups`.

## Checks run

Linux sandbox on the owner's Mac, Python 3.10.12, offline, fictional text only,
no provider calls.

| Check | Result |
| --- | --- |
| `tests/test_ai07_controller_contract.py` | 7 of 7 passed. |
| Mutation: proposal checks always accept | The new tests failed, as intended. |
| Mutation: date and amount grounding removed | The new tests failed, as intended. |

No source file changed, so the earlier before/after module runs for AI-03/AI-04
still describe the rest of the suite. Not run: Python 3.11/3.12 and CI.

## Open items

1. **"Or a person."** The guest-only pilot (SA-27) has no human handoff, which
   is a separate permission. Today a rejected proposal becomes a clarifying
   question, or the turn fails safely with the person's facts kept and the
   plan tools still working. Owner decision: accept that reading for the
   pilot, or require a handoff path. Licensed review of recommendations is
   AI-16.
2. **Literal checks, not meaning.** The rule checks catch fabricated dates,
   amounts, names and claims. They do not prove that a reply's meaning follows
   from its sources; the held-out language evaluation remains a separate
   release requirement (Validation & Evals).
3. **Founder review and a CI run on Python 3.12** before merge.
