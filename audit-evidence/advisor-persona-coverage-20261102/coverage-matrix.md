# Current :8893 offline persona field coverage

30 executed scenarios; 2164 assertions; 0 failures; **zero paid model calls**.

Original 78 paths, 14 additive gap-report paths and 4 current report extensions remain separate. Unknown, absence, rejection, derived links and reuse are not independently reported capture. These deterministic contracts test software state handling, not real LLM reasoning or consumer comprehension.

| Inventory | Paths | Any assertion | Successful capture | Derived | Explicit absence | Rejection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_78 | 78 | 78 | 71 | 5 | 35 | 0 |
| additive_14 | 14 | 14 | 0 | 1 | 13 | 13 |
| current_extension | 4 | 4 | 3 | 1 | 3 | 0 |

All observed state/mode counts below come from executed assertions. Each JSON witness includes its scenario, step, exact expected value and independently observed result. A blank state remains an untested state, not presumed support.

| Field | Class | States witnessed | Modes witnessed | Scenario witnesses |
| --- | --- | --- | --- | --- |
| `guide.fields.intent.goal` | capture | known (27) | reused (25), volunteered (2) | F01, F03, F04, F05, F06, F07, F08, F09, F10, F13, F16, P1, P1-payer, P10, P2, P2-browse, P3, P3-replacement, P4, P4-unknown, P5, P6, P7, P8, P9 |
| `guide.fields.intent.goalDetail` | capture | known (2) | reused (1), volunteered (1) | F01 |
| `guide.fields.knowledge.general` | capture | known (4) | reused (2), volunteered (2) | F07, P5 |
| `guide.fields.comparison.scope.zip` | capture | known (16), unknown (1) | questioned (5), reused (8), volunteered (4) | F01, F13, F14, P2-browse, P3, P3-replacement, P5, P7, P8 |
| `guide.fields.comparison.scope.county` | capture | known (8), unknown (1) | derived (8), questioned (1) | F01, F13, F14, P2-browse, P3, P3-replacement, P5, P7, P8 |
| `guide.fields.comparison.scope.locationEvidence` | derived | known (8), unknown (1) | derived (8), questioned (1) | F01, F13, F14, P2-browse, P3, P3-replacement, P5, P7, P8 |
| `guide.fields.coverage.requestedStart` | capture | known (20), stale (1), unanswered (1), unknown (2) | explicit_absence (1), questioned (6), reused (11), volunteered (6) | F05, F13, F15, P1, P1-payer, P2, P3, P3-replacement, P5, P6, P7, P8, P9 |
| `guide.fields.coverage.requestedStartMonth` | capture | known (13), stale (1), unanswered (6), unknown (2) | explicit_absence (6), questioned (4), reused (7), volunteered (5) | F01, F02, F05, F13, F15, P1, P1-payer, P2, P3, P6, P7, P8, P9 |
| `guide.fields.coverage.current` | capture | explicit_none (2), known (26), unanswered (7), unknown (1) | explicit_absence (7), questioned (6), reused (13), volunteered (10) | F06, F07, F10, F12, F13, F15, F16, P1, P1-payer, P10, P2, P2-browse, P3, P3-replacement, P4, P5, P6, P7, P8, P9 |
| `guide.fields.needs.providersStatus` | capture | deferred (1), explicit_none (6), known (4), unanswered (1), unknown (1) | explicit_absence (1), questioned (6), reused (5), volunteered (1) | F09, F13, F16, P4, P5, P7, P8 |
| `guide.fields.needs.providers` | capture | deferred (1), known (4), stale (1), unanswered (2), unknown (1) | explicit_absence (2), questioned (4), reused (3) | F09, F13, F16, P4, P7 |
| `guide.fields.needs.medicinesStatus` | capture | explicit_none (4), known (14), unknown (1) | questioned (7), reused (9), volunteered (3) | F03, F04, F08, F11, P10, P4, P4-unknown, P5, P7, P8 |
| `guide.fields.needs.medications` | capture | known (14), unknown (1) | questioned (4), reused (7), volunteered (4) | F03, F04, F08, F11, P10, P4, P4-unknown, P7 |
| `guide.fields.needs.medicationDetails` | legacy | unanswered (2), unknown (1) | explicit_absence (2), questioned (1) | F03, F11, P7 |
| `guide.fields.needs.pharmacies` | legacy | unanswered (2), unknown (1) | explicit_absence (2), questioned (1) | F03, F11, P7 |
| `guide.fields.needs.travel` | capture | known (4), unknown (1) | questioned (3), reused (2) | P5, P7, P8 |
| `guide.fields.needs.costPreference` | capture | known (4) | reused (2), volunteered (2) | F13, P3-replacement |
| `guide.fields.needs.priorities` | capture | known (6) | reused (3), volunteered (3) | F01, F13, P3-replacement |
| `guide.fields.needs.priorityOther` | capture | known (2) | reused (1), volunteered (1) | F01 |
| `readiness.facts.RC01.value.choice` | capture | known (58), unknown (2) | questioned (25), reused (29), volunteered (6) | F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15, F16, P1, P1-payer, P10, P2, P2-browse, P3, P3-replacement, P4, P4-unknown, P5, P6, P7, P8, P9 |
| `readiness.facts.RC02.value.choice` | capture | known (4) | reused (2), volunteered (2) | F01, F14 |
| `readiness.facts.RC02.value.zip` | capture | known (4) | reused (2), volunteered (2) | F01, F14 |
| `readiness.facts.RC02.value.county` | capture | known (2), unknown (1) | questioned (1), reused (1), volunteered (1) | F01, F14 |
| `readiness.facts.RC02.value.homeStatus` | capture | deferred (1), known (2) | questioned (1), reused (1), volunteered (1) | F01, F14 |
| `readiness.facts.RC03.value.choice` | capture | known (2) | questioned (1), reused (1) | P2-browse |
| `readiness.facts.RC03.value.year` | capture | known (2) | questioned (1), reused (1) | P2-browse |
| `readiness.facts.RC04.value.choice` | capture | known (8), unanswered (12) | explicit_absence (12), questioned (3), reused (4), volunteered (1) | F12, F15, F16, P1, P1-payer, P10, P2, P2-browse, P3, P3-replacement, P4, P5, P6, P7, P8, P9 |
| `readiness.facts.RC05.value.choice` | capture | known (4), unanswered (3) | explicit_absence (3), questioned (1), reused (2), volunteered (1) | F02, F05, F15, P3, P3-replacement |
| `readiness.facts.RC05.value.month` | capture | known (4), unanswered (3) | explicit_absence (3), questioned (1), reused (2), volunteered (1) | F02, F05, F15, P3, P3-replacement |
| `readiness.facts.RC06.value.choice` | capture | known (8) | questioned (1), reused (4), volunteered (3) | F02, F06, P1-payer, P5 |
| `readiness.facts.RC06.value.ageBand` | capture | known (2) | reused (1), volunteered (1) | F02 |
| `readiness.facts.RC07.value.choice` | capture | known (3), unanswered (3) | explicit_absence (3), questioned (2), reused (1) | F12, F16, P3-replacement |
| `readiness.facts.RC08.value.choice` | capture | known (2), unanswered (1) | explicit_absence (1), reused (1), volunteered (1) | F01, P2 |
| `readiness.facts.RC08.value.eventDate` | capture | known (2), unanswered (1) | explicit_absence (1), reused (1), volunteered (1) | F01, P2 |
| `readiness.facts.RC09.value.choice` | capture | known (14), unanswered (2) | explicit_absence (2), questioned (1), reused (7), volunteered (6) | F06, F07, F15, P1, P1-payer, P2, P6, P8, P9 |
| `readiness.facts.RC10.value.choice` | capture | known (2), stale (1), unanswered (1) | explicit_absence (1), questioned (1), reused (2) | F06, P1-payer |
| `readiness.facts.RC11.value.choice` | capture | known (10), stale (1), unanswered (2) | explicit_absence (2), questioned (2), reused (6), volunteered (3) | F15, P1, P1-payer, P2, P6, P9 |
| `readiness.facts.RC11.value.jobEnd` | capture | known (5), stale (1), unanswered (4) | explicit_absence (4), questioned (2), reused (3), volunteered (1) | F15, P1, P1-payer, P2, P6 |
| `readiness.facts.RC11.value.coverageEnd` | capture | known (10), stale (1), unanswered (2), unknown (1) | explicit_absence (2), questioned (5), reused (5), volunteered (2) | F15, P1, P1-payer, P2, P6, P9 |
| `readiness.facts.RC12.value.choice` | capture | known (4) | questioned (1), reused (2), volunteered (1) | F02, P2 |
| `readiness.facts.RC12.value.gap` | capture | known (2) | reused (1), volunteered (1) | F02 |
| `readiness.facts.RC13.value.choice` | capture | known (2), unknown (2) | questioned (3), reused (1) | F16, P2 |
| `readiness.facts.RC14.value.choice` | capture | known (2) | reused (1), volunteered (1) | P1-payer |
| `readiness.facts.RC15.value.choice` | capture | known (2) | reused (1), volunteered (1) | P3 |
| `readiness.facts.RC15.value.event` | capture | known (2) | reused (1), volunteered (1) | P3 |
| `readiness.facts.RC16.value.choice` | capture | known (2) | questioned (1), reused (1) | P3 |
| `readiness.facts.RC16.value.start` | capture | known (2) | questioned (1), reused (1) | P3 |
| `readiness.facts.RC16.value.priorMedigap` | capture | known (2) | questioned (1), reused (1) | P3 |
| `readiness.facts.RC17.value.choice` | capture | known (2) | reused (1), volunteered (1) | P3-replacement |
| `readiness.facts.RC18.value.choice` | capture | known (4) | questioned (1), reused (2), volunteered (1) | P4, P5 |
| `readiness.facts.RC19.value.choice` | capture | known (2) | reused (1), volunteered (1) | P5 |
| `readiness.facts.RC19.value.qualification` | capture | known (2) | reused (1), volunteered (1) | P5 |
| `readiness.facts.RC20.value.choice` | capture | known (2) | questioned (1), reused (1) | P5 |
| `readiness.facts.RC20.value.location` | capture | known (2) | questioned (1), reused (1) | P5 |
| `readiness.facts.RC21.value.choice` | capture | known (2), stale (1), unanswered (1) | explicit_absence (1), reused (2), volunteered (1) | F09, F16 |
| `readiness.facts.RC21.value.items[].entity` | derived | known (3), stale (1), unanswered (1) | derived (3), explicit_absence (1), reused (1) | F09, F16, P4 |
| `readiness.facts.RC21.value.items[].practice` | capture | known (6), stale (1), unanswered (1) | explicit_absence (1), reused (4), volunteered (3) | F09, F16, P4 |
| `readiness.facts.RC21.value.items[].city` | capture | known (6), stale (1), unanswered (1) | explicit_absence (1), reused (4), volunteered (3) | F09, F16, P4 |
| `readiness.facts.RC22.value.choice` | capture | known (6), unanswered (3) | explicit_absence (3), reused (3), volunteered (3) | F03, F04, F08, P5, P7, P8 |
| `readiness.facts.RC22.value.items[].entity` | derived | known (11), unanswered (3) | derived (11), explicit_absence (3) | F03, F04, F08, P10, P4, P4-unknown, P5, P7, P8 |
| `readiness.facts.RC22.value.items[].name` | capture | known (20), unanswered (3) | explicit_absence (3), reused (9), volunteered (11) | F03, F04, F08, P10, P4, P4-unknown, P5, P7, P8 |
| `readiness.facts.RC22.value.items[].strength` | capture | known (16), unanswered (4), unknown (2) | explicit_absence (4), questioned (2), reused (7), volunteered (9) | F03, F04, F08, P10, P4, P4-unknown, P5, P7, P8 |
| `readiness.facts.RC22.value.items[].form` | capture | known (20), unanswered (3) | explicit_absence (3), reused (9), volunteered (11) | F03, F04, F08, P10, P4, P4-unknown, P5, P7, P8 |
| `readiness.facts.RC22.value.items[].brand` | capture | deferred (1), known (2), unanswered (3) | explicit_absence (3), questioned (1), reused (1), volunteered (1) | F03, F04, P5, P7, P8 |
| `readiness.facts.RC23.value.choice` | capture | known (6), stale (1), unanswered (2) | explicit_absence (2), questioned (2), reused (4), volunteered (1) | F03, F04, F08, P10, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].entity` | derived | known (9), stale (3), unanswered (2) | derived (11), explicit_absence (2), reused (1) | F03, F04, F08, P10, P4, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].quantity` | capture | deferred (1), known (15), stale (2), unanswered (2) | explicit_absence (2), questioned (9), reused (8), volunteered (1) | F03, F04, F08, P10, P4, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].daysSupply` | capture | deferred (1), known (13), stale (2), unanswered (2), unknown (1) | explicit_absence (2), questioned (10), reused (7) | F03, F04, F08, P10, P4, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].pharmacy` | capture | deferred (2), known (13), stale (2), unanswered (2) | explicit_absence (2), questioned (10), reused (7) | F03, F04, F08, P10, P4, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].channel` | capture | deferred (2), known (13), stale (2), unanswered (2) | explicit_absence (2), questioned (10), reused (7) | F03, F04, F08, P10, P4, P4-unknown, P8 |
| `readiness.facts.RC23.value.items[].supply` | legacy | known (2), stale (1), unanswered (2) | explicit_absence (2), questioned (1), reused (2) | F03, P10, P4-unknown, P8 |
| `readiness.facts.RC24.value.choice` | capture | known (4) | reused (2), volunteered (2) | F03, P4 |
| `readiness.facts.RC25.value.choice` | capture | known (2) | reused (1), volunteered (1) | P5 |
| `readiness.facts.RC25.value.amount` | capture | known (2) | reused (1), volunteered (1) | P5 |
| `readiness.facts.RC25.value.includes` | capture | known (2) | questioned (1), reused (1) | P5 |
| `readiness.facts.RC26.value.choice` | capture | known (4) | questioned (1), reused (2), volunteered (1) | F10, P5 |
| `readiness.facts.RC27.value.choice` | capture | known (2) | reused (1), volunteered (1) | P5 |
| `readiness.facts.RC28.value.choice` | capture | known (2) | questioned (1), reused (1) | F12 |
| `readiness.conversation.details.G01.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G02.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G03.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G04.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G05.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G06.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G07.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G08.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G09.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G10.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G11.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G12.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `readiness.conversation.details.G13.value` | derived | known (2) | reused (2) | F10, P5 |
| `readiness.conversation.details.G14.value` | held | unanswered (2) | explicit_absence (1), rejected (1) | F10 |
| `guide.fields.situation.retirement` | capture | known (2), unanswered (1) | explicit_absence (1), reused (1), volunteered (1) | F15, P9 |
| `guide.fields.situation.age65` | capture | known (2), unanswered (7) | explicit_absence (7), reused (1), volunteered (1) | F02, F05, F06, F15, P1, P1-payer, P2-browse, P5 |
| `guide.fields.subject.role` | derived | known (59), unanswered (3), unknown (1) | explicit_absence (3), questioned (26), reused (28), volunteered (6) | F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15, F16, P1, P1-payer, P10, P2, P2-browse, P3, P3-replacement, P4, P4-unknown, P5, P6, P7, P8, P9 |
| `readiness.facts.RC18.value.programs[]` | capture | known (4) | questioned (1), reused (2), volunteered (1) | P4, P5 |

## Retained gaps and limits

- `guide.fields.needs.medicationDetails`: Retained guide-level field has no current T07 writer; product-level details belong to RC22. Preserve it in the denominator without manufacturing capture.
- `guide.fields.needs.pharmacies`: Retained guide-level pharmacy field has no current T07 writer; per-medicine pharmacy detail belongs to RC23. Preserve its unsatisfied capture gap.
- `readiness.facts.RC23.value.items[].supply`: Retained legacy combined supply field accepts an explicit voluntary typed report through the current C1 validator; the current fill question requests quantity and daysSupply separately. The tested typed value does not imply the field is routinely asked or substitute for those separate leaves.
- `readiness.conversation.details.G01.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G02.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G03.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G04.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G05.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G06.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G07.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G08.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G09.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G10.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G11.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G12.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.
- `readiness.conversation.details.G14.value`: Optional stored representation is retained, but the current controller exposes no writer. Explicit absence is not successful capture and does not close this gap.

## Separate visit/audit metadata

These paths remain visible but are excluded from the personal report-field denominator. Their role is not equivalent to collecting another consumer answer.

| Metadata path | Classification | Meaning |
| --- | --- | --- |
| `readiness.natural.provenance` | derived_audit_metadata | Capture method, report status, subject, temporal scope and revisions; not extra consumer answers. |
| `readiness.natural.dialogue` | derived_visit_metadata | Approved return targets, deferred/clarification targets and explained topics; exposure does not establish comprehension. |
| `readiness.natural.agenda.concerns` | explicit_visit_context | Explicit scoped open/addressed/deferred concerns; not facts, eligibility or priority weights. |
| `readiness.natural.agenda.priorityReasons` | explicit_visit_context | Explicit quoted reason tied to the accepted current T10 priority revision; not an inferred weight. |
| `readiness.natural.agenda.lastMove` | derived_visit_metadata | Validated advisor move kind/topic/reason; not a personal report. |
| `readiness.conversation.task` | derived_visit_metadata | Current authorized workflow goal; not insurance or an enrollment finding. |
| `readiness.conversation.baselineDispositions` | derived_visit_metadata | Unknown/deferred baseline states; not known answers. |
| `readiness.conversation.skippedDetails` | derived_visit_metadata | Per-field and per-entity unknown/deferred states; not known answers. |
| `readiness.conversation.itemRevisions` | derived_audit_metadata | Per-item revision bookkeeping; not customer answers. |
| `readiness.conversation.itemInvalidations` | derived_audit_metadata | Dependent stale-item revision bookkeeping; not customer answers. |
| `advisor_memory.exchanges` | ram_only_visit_context | Permissioned bounded dialogue in server RAM; never saved profile fields. |
| `advisor_memory.brief` | ram_only_visit_context | Goal/current concern/pause/return point; tentative explanation calibration derives from dialogue, not a comprehension score. |

## Remaining state coverage

This corpus is not exhaustive across every valid option, correction, entity count, time scope or answer combination. The JSON exposes `untested_states` for every field. A no-writer rejection/absence test does not close a capture or semantic gap.

## All 41 reviewed question meanings

Field assertions are distinct from asserted question display. Documented child meanings reuse their parent fields; their mapped field coverage does not mean a new child question was shown.

| ID | Kind / parent | Fields with assertions | Fields with capture | Asserted displays |
| --- | --- | ---: | ---: | ---: |
| T01 | baseline | 2/2 | 2/2 | 0 |
| T02 | baseline | 1/1 | 1/1 | 0 |
| T03 | baseline | 3/3 | 1/3 | 0 |
| T04 | baseline | 2/2 | 2/2 | 0 |
| T05 | baseline | 1/1 | 1/1 | 0 |
| T06 | baseline | 2/2 | 2/2 | 0 |
| T07 | baseline | 4/4 | 2/4 | 0 |
| T08 | baseline | 1/1 | 1/1 | 0 |
| T09 | baseline | 1/1 | 1/1 | 0 |
| T10 | baseline | 2/2 | 2/2 | 0 |
| RC01 | conditional | 1/1 | 1/1 | 0 |
| RC02 | conditional | 4/4 | 4/4 | 0 |
| RC03 | conditional | 2/2 | 2/2 | 0 |
| RC04 | conditional | 1/1 | 1/1 | 0 |
| RC05 | conditional | 2/2 | 2/2 | 0 |
| RC06 | conditional | 2/2 | 2/2 | 0 |
| RC07 | conditional | 1/1 | 1/1 | 0 |
| RC08 | conditional | 2/2 | 2/2 | 0 |
| RC09 | conditional | 1/1 | 1/1 | 1 |
| RC10 | conditional | 1/1 | 1/1 | 2 |
| RC11 | conditional | 3/3 | 3/3 | 1 |
| RC12 | conditional | 2/2 | 2/2 | 0 |
| RC13 | conditional | 1/1 | 1/1 | 1 |
| RC14 | conditional | 1/1 | 1/1 | 0 |
| RC15 | conditional | 2/2 | 2/2 | 0 |
| RC16 | conditional | 3/3 | 3/3 | 0 |
| RC17 | conditional | 1/1 | 1/1 | 0 |
| RC18 | conditional | 1/1 | 1/1 | 0 |
| RC19 | conditional | 2/2 | 2/2 | 0 |
| RC20 | conditional | 2/2 | 2/2 | 1 |
| RC21 | conditional | 4/4 | 3/4 | 0 |
| RC22 | conditional | 6/6 | 5/6 | 0 |
| RC23 | conditional | 7/7 | 6/7 | 0 |
| RC24 | conditional | 1/1 | 1/1 | 0 |
| RC25 | conditional | 3/3 | 3/3 | 0 |
| RC26 | conditional | 1/1 | 1/1 | 0 |
| RC27 | conditional | 1/1 | 1/1 | 0 |
| RC28 | conditional | 1/1 | 1/1 | 1 |
| RC11.C1 | documented_child / RC11 | 1/1 | 1/1 | 0 |
| RC16.C1 | documented_child / RC16 | 1/1 | 1/1 | 0 |
| RC16.C2 | documented_child / RC16 | 1/1 | 1/1 | 0 |
