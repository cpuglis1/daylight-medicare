# Adaptive education alongside the reported profile

November 2, 2026 · D86 with D49/D54/D55/D57 · :8893 only

The owner authorized tracking the concepts Daylight has explained alongside the information it learns about the person. The purpose is to prevent repetitive teaching while continuing toward understanding coverage options. The curriculum is a map of relevant concepts, not another questionnaire or a required sequence of lessons. The current layout, composer, answer choices, reveal, Sources and contextual visual designs remain in place.

The subsequent [conversation-quality increment](../../audit-evidence/advisor-conversation-quality-20261102/README.md) adds optional bounded `aspect_ids` within these same concepts. New supported aspects permit further depth after a concept is already explored. A validated clarification request in the current message can authorize immediate clarification without requiring an earlier open-confusion receipt. Explanation focus can differ from the practical return point; neither forces a personal question. These receipts remain model assertions, not independent proof of the teaching delivered or the person's comprehension.

## Two complementary records

The reported profile retains explicit circumstances, priorities, unknowns and corrections. Its provenance, scope, saving permissions and external verification gates remain unchanged.

The education record tracks 17 concepts across foundations, coverage paths, personal tradeoffs, enrollment and decision research. It stores whether a concept has been introduced or explored, any open clarification, delivery counts and visuals already shown. A delivery receipt never means the person understands the concept. Explicit familiarity remains a separate report; education progress cannot unlock a recommendation.

Concepts map to the existing reviewed teaching facts. This change adds no Medicare claims or new source acceptance. Several concepts can share evidence; citing that evidence does not check off every related concept.

## Model and controller contract

Typed messages retain two generation stages. Interpretation receives the resolved profile, all 41 public question meanings, the current brief, bounded recent exchanges and compact learning history. It proposes supported profile updates and a separate `education_request` containing a request kind, scoped concept IDs and an exact supporting quote from the current message. Source selection alone does not authorize a recap. Ordinary self-reference is interpreted semantically, with caregiver and hypothetical scope preserved.

After validating reports, the controller supplies composition with the goal, pending decision, eligible moves, reviewed evidence, concept catalog and learning history. Composition returns prose, a dedicated next question, citations and a separate `education` object:

```json
{
  "purpose": "advance",
  "updates": [],
  "visual": "none"
}
```

When it teaches, updates identify the concept, introduced/explored depth, why the explanation is useful and the supporting evidence. A visual is an explicit contextual choice. Citation IDs no longer double as diagram instructions. A finite submitted answer still uses at most one composition call and ordinarily advances without another introductory lesson.

The controller validates optional teaching metadata independently of useful prose. It rejects unsupported receipts, repeat introductions and unrequested recaps; permits new depth, clarification and scoped user-requested revisits; and suppresses repeated or unrelated figures. A narrow guard removes a repeated lesson after an ordinary answer when all its claimed teaching was already delivered, retaining the useful next question. Malformed optional metadata cannot trigger this prose suppression. An exact trailing copy of the dedicated question is removed from prose without semantic rewriting.

Learning changes are planned before output and committed only after successful response processing. Failed composition or post-processing cannot mark an undelivered lesson complete. An explicit free Explain action can record the primary concept within an existing permitted visit, without an AI call or fabricated dialogue exchange.

## Privacy, continuity and cost

Learning history uses existing `natural-context-v3` deliberate-Send permission and the same owner/visit isolation as dialogue. It stays in server RAM, expires under the existing one-hour visit policy, and is excluded from saved profiles. Reads and free lessons do not extend expiry. Older permission does not silently gain curriculum continuity. Lessons opened before an authorized visit are not retroactively recorded. Refresh/new chains, expiry and restarts can therefore require an explanation again.

Deleting a guest clears its visit learning/dialogue memory and continuation authority, with conflict protection while a message is in flight. This is not a claim that every inherited cache or provider-side record is deleted. Existing saving and provider retention behavior remain separate.

The model, reasoning settings, stage count, 8,000-input/900-output limits, shared budget ledger and $5/UTC-day allowance are unchanged. Expanded structured context can increase token use. Both stages serialize input JSON compactly without changing its values. Focused retrieval reuses an explicit/actually delivered source, falling back to one primary source per concept instead of adding associated duplicates. Before generation, token-aware packing can remove the oldest whole exchanges until the request fits, with at most seven counting checks. It preserves the current message, profile, learning history, brief, evidence and question meanings, and does not mutate visit memory. A base context that still exceeds the limit fails safely. Network failures receive safe unavailable responses with no automatic retry and no automatic refund of uncertain provider charges.

## Validation and remaining gaps

The [implementation evidence](../../audit-evidence/advisor-curriculum-20261102/README.md) separates deterministic controller/renderer tests, fictional browser checks, provider attempts and runtime activation. Tests cover multi-turn repetition, explicit revisit, new depth, side questions, helper scope, malformed metadata, replay, failed processing, privacy and lifecycle behavior. Existing persona expectations remain independent of observed outputs.

Structured receipts are model assertions validated against allowed evidence and continuity; they do not independently prove every sentence taught the claimed concept. Semantic repetition in arbitrary prose, actual comprehension, retention, live-model extraction and long-conversation token headroom require further observation. There is no consumer recommendation or source-release acceptance in this change.
