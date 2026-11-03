# Synthetic conversation design trace audit

October 25, 2026 · D79. **Declared design segments, not runtime tests, real customer sessions or accepted Medicare policy. Human elapsed time is not measured.**

See [conversation design](SHORTEST_SUFFICIENT_CONVERSATION.md), [field map](CRITICAL_INFORMATION_FIELD_MAP.md) and [trace definitions/results](CONVERSATION_TRACE_AUDIT.json). Each segment tests its stated input boundary only; missing wider eligibility/coverage facts are not presumed satisfied.

| Trace | Narrow design segment | Questions/prompts | Atomic information requests | Turns | Human elapsed time |
| --- | --- | ---: | ---: | ---: | --- |
| S01 | Direct general-learning question | 0 | 0 | 2 | Not measured |
| S02 | Published local/year browsing with scope already supplied | 0 | 0 | 2 | Not measured |
| S03 | Prepare two provider identities with one grouped echo | 1 | 2 | 4 | Not measured |
| S04 | Prepare exact medicine identity for coverage; no price request | 1 | 1 | 4 | Not measured |
| S05 | Prepare one price scenario with only missing fill facts | 1 | 4 | 4 | Not measured |
| S06 | Unknown days supply stops the price conclusion without a loop | 1 | 4 | 4 | Not measured |
| S07 | One specific current-versus-future arrangement conflict | 1 | 1 | 4 | Not measured |
| S08 | Known identity; unavailable external access source | 0 | 0 | 2 | Not measured |
| S09 | Reuse explicit priorities; no routine T09/T10 closing asks | 0 | 0 | 2 | Not measured |
| S10 | Prepare distinct employment and health-coverage end chronology | 1 | 2 | 4 | Not measured |

Every segment keeps independent source/policy/release holds visible; no personal recommendation is allowed by this audit. S06 retains unknown days supply, S08 does not turn a source failure into another provider ask, and S10 does not repeat the child coverage-end ask after the parent answer supplies it. S03 counts two identity requests even though one grouped question collects them.

Audit checks: all references resolve; internal-link/legacy wording does not become an intake question; known/unknown items are not re-asked; the coverage-only drug segment requests no pricing-only fields; unresolved facts and holds remain explicit. Counts are audited from the trace definitions. They do not establish an optimal real-world question count, time improvement, usable UI or actual source verification.
