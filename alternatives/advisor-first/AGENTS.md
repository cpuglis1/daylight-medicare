# Working on the advisor-first variant (:8893)

Read the root [AGENTS.md](../../AGENTS.md) and
[CURRENT_STATE.md](../../docs/project/CURRENT_STATE.md) first. This file adds
the rules specific to :8893. The full dated directives for this variant
(D86–D93, November 2–5, 2026) are preserved verbatim, see
[DIRECTIVE_HISTORY.md](../../docs/project/DIRECTIVE_HISTORY.md). They remain
binding where not superseded; read the entries for an area before changing it,
and follow each entry's linked evidence packet.

## Current rules

**UI (D93).** The :8894 refresh lives in `web-8894/`, served by `ui-8894/serve.py`,
which forwards every other request to :8893. Do not edit `web/` for that work;
:8893 stays the reference until the owner promotes :8894. Plans sorting,
filtering and grouping are display only and never enter recommendation logic.
Motion in :8894 (thinking dots and similar) is owner-requested; keep it functional
and keep it off under `prefers-reduced-motion`.
**Plans filters (D97).** Personal filters submit `choice` answers with
`source: plans_filter` (aiConsent false, `PLANS_FILTER_QUESTIONS` only); the
server records provenance method `plans_filter`. Display filters stay client-side.
D113: these saves are silent in the UI (`turn(..., {silent:true})`, no chat
history), taken as given, and T06/T07 Adds union with the existing list at the
Plans entry point. `plans_additions[(owner, chain)]` holds net changes until the
next composed chat reply, which gets `plans_page_additions`, a "Besides …, any
others?" candidate, and a server acknowledgement sentence if the reply omits them.

**Plans backend (D92).** Supported plan details are usable; all 229 material
holds stay. Published-term ordering is separate from personal recommendations.
Missing external verification or method acceptance holds the affected personal
conclusion. `plans-context-v1` is a separate Send-bound permission; scrolling
or selecting never calls AI or infers preferences.

**Conversation (D86, D73, D88, D89).**
- One general framework: the model chooses explanation, clarification or
  consequential intake; backend gates protect evidence and permissions. No
  case-specific scripts, canned prose or prewritten lesson blocks.
- Each active turn ends with an approved question (D109): the server supplies
  `required_target` while a decision-relevant meaning is open; offers to prepare
  material for a third party are never the follow-up. Redirect, don't deflect:
  state the applicable general rule (`applicable_rules.py`, `pilot-rules.json`),
  name the personal gap, then ask. A failed generation shows one reviewed
  statement plus the approved question (owner exception to D88). Person and
  ZIP/county must be known before "Review your info → See plans"; coverage year
  defaults to 2026 (D108); other core dimensions may be explicitly unknown or
  deferred, with holds.
- Only the person's own words end a turn without a question (D111): the server
  sets `pause_allowed` from the message; "just say yes or no" is brevity, not a
  pause. The floor statement comes from `floor_statement` (a rule the reports
  support, never one they rule out, never the calendar). Typed answers that
  name a chip label are recorded by `direct_choices` (exact match only). Later
  rule sets (`pilot-rules-r2.json`, …) load only with `review_state`
  `owner_accepted_<date>`; an owner statement with `[OWNER` blanks never loads.
- The person's own words are echoable (D112): a date, figure, count or name in
  the current message grounds the reply; a bare month name does not. A pending
  clarification stores the value it asks about; a bare affirmative ("Yes.",
  "Just those two") confirms exactly that value (`pending_confirmation`,
  `pending_situation_confirmation`), a plain "No" never does. "Part A only" in
  the person's own sentence records RC04 (`part_status_report`). Composition
  context is compacted in a fixed order (`_fit_context`) before the request
  bound is refused; reports, applicable rules, the brief and the moves are
  never dropped.
- Teaching delivered never proves understanding. Tentative progress cannot
  establish comprehension, verification or recommendation readiness.
- The thirteen pinned educational statements (`understanding-lock.json`) and the
  task-coordination contract stay in force.

**Budgets and reliability (D90).**
- $15 per UTC day for OpenAI and, separately, $15 for Anthropic (raised from $5 on Nov 8, 2026 for the 20-persona evaluation). Admit a turn
  while accounted usage is below the threshold; let the bounded turn finish.
- At most two composition attempts: one recovery slot, shared by connection
  recovery and a same-model repair. Exception (D155 Q5): a reply with an
  unsourced fact or amount gets up to 3 repairs (`FACT_REPAIR_LIMIT`), then the
  retrieved source is quoted or the "reviewed sources don't cover that yet"
  note is shown. HTTP and billing rejections are not retried.
- No fixed input-token ceiling; output and transport limits remain.
- Session recovery is free and never executes the rejected action.

**Privacy.** Raw chat stays visit-only. Saving is a separate choice. No research
row enters saved reports or model context. No new transcript persistence for
real users or the pilot, including in traces. Exception (D155, this branch):
localhost testing may save raw chat and turn traces; the pilot is hard-off.

## Checks

Use offline, network-forbidden tests and fictional personas
(`tests/persona_runner.py`). No paid probes. Agent-run simulated conversations
(`tools/evaluation/sim_conversations.py`, D155) run the simulated person and
judges on the owner's subscription, cap Daylight's own calls at $10 per run, and
run against a live server only when the owner asks; the full set runs only on
request. The owner still assesses conversation quality. Record actual results in a dated
`audit-evidence/` packet.
