# Evidence and implementation assessment

Inspected November 4, 2026. No personal guest records were opened. Findings concern source files, synthetic tests, public product references and an empty local advisor visit.

## What is usable today

| Area | Finding | Product implication |
| --- | --- | --- |
| Chat profile | `comparison_profile.build_comparison_profile` already reads `guide` + `readiness` reports, binds revisions/digest and retains report state, subject, item identity and precision | Reuse this adapter; do not scrape the transcript or build another profile database |
| Conditional input model | Adapter validates the 41 meanings, 78 baseline paths, 14 representation gaps and aliases | Questions remain conditional; a coverage-completion counter is not readiness |
| Correction and uncertainty | Existing tests cover stale reports, unknown/defer/none/zero, item invalidation, beneficiary versus learner, provenance and nonmutation | These semantics are a useful foundation; preserve them in the new confirmation service |
| End confirmation | Owner requirement exists. Current UI has profile review, preparation review and internal comparison journey | A single production `Confirm and see plans` receipt bound to the final decision digest/priority order still needs implementation; present review is not evidence of that finished flow |
| Comparison | `ComparisonService` attaches an evidence-bound result and rechecks stale responses | Reuse its boundaries and methods; current personal outputs remain held |
| Ranking | `comparison_methods.py` explicitly never scores/ranks; current engine returns `personalized_recommendation_allowed: false`; prior DECISION_RULES is a proposal | There is no released top-three recommender to reuse. This packet adds a fictional reference and a production specification |
| Catalog | Exact r13 has 72 unique retained offerings for 2026/12021, dated Landscape evidence 2026-09-02 | Match by exact ID/year, not plan names; no full-market or personal-availability claim |
| Prepared fields | 720 field dispositions: 568 candidate values, 141 holds, 11 not applicable | Cards/details must retain conditions and held states; preparation is not acceptance |
| Fictional examples | 288 example dispositions: 200 numeric candidates, 88 holds; 41 plans have all four numeric examples | Keep component scenarios separate; do not sum an annual spending prediction |
| Approval | `consumer-acceptance.json` is pending, release null, reviewer null, empty claims/approved_outputs; r13 `consumer_usable` false | Display, comparison and recommendation each need exact authority. This request does not impersonate an independent reviewer |
| Existing surface | :8893 is the advisor; existing code still references five unvalidated 2027 samples and separately gated internal/fixture views | New Plans entry needs a deliberate supported 2026 route; samples cannot fill missing catalog facts |
| Chat plan awareness | Comparison context currently sends public held-capability markers, not plan rows or browser view state | View-aware plan discussion is a new minimized, permissioned context contract |

The targeted profile suite passed **16 tests** using the existing source paths. Initial execution lacked the shared script import path; rerunning with the correct `PYTHONPATH` passed. This is evidence of the adapter’s covered behavior, not a complete live chat-to-recommendation proof.

## Profile mapping for the new workspace

| Decision input | Existing reports | Added work |
| --- | --- | --- |
| County and residence | T03 scope ZIP/county/location evidence; RC02 home status | Confirm actual beneficiary scope; source-derived location is not a user assertion |
| Intended year/start | RC03 year; T04 requested start/month | Keep year explicit; soonest/month-only cannot invent it |
| Current arrangement | T05 current coverage; relevant RC04/RC07/RC26 | Exact current offering/component baseline remains a separate check |
| Doctors/sites | T06 providers; RC21 entity/practice/city | Reuse item IDs; resolve source identity and exact site participation |
| Medicines | T07 + RC22 entity/name/strength/form/brand | Exact medicine identity; no same-name merging or therapeutic substitution |
| Fill/pharmacy | RC23 quantity/daysSupply/pharmacy/channel/supply; RC24 context | Preserve units/outlet/benefit-part gaps and accepted method conditions |
| Travel | T08 and RC02/RC20 | Resolve routine versus emergency coverage where consequential |
| Assistance/restrictions | RC18 programs; RC19 qualification; RC26 other coverage | Exact level/period/program evidence; reported status is not verification |
| Cost/preferences | T09 cost preference; T10 priorities/other; RC25 budget/includes | Explicit ordering and must-have confirmation; do not infer weights from an unordered set |
| Final decision binding | Existing adapter normalized digest, source bindings and report/item revisions | New end-confirmation receipt, bound priority/constraint metadata and invalidation |

## Reference products and synthesis

The references inform product patterns, not our plan evidence, source permission or proof of their internal correctness.

**eHealth.** Its public Medicare page describes doctor/prescription input, cost/coverage sorting, comparison against current coverage and up to three recommendations from profile information. It also describes side-by-side review. Borrow the quick shortlist and comparable cost/access hierarchy. Daylight’s proposed difference is an inspectable simple ordering rule and a persistent plan-aware conversation. This review did not execute a fresh authenticated eHealth recommendation journey. [eHealth Medicare page and “Top Picks” methodology footnote](https://www.ehealthinsurance.com/medicare/).

**The Pocket Protector.** Its public tools page separates plan discovery, doctor checks, drug costs, current-plan comparison and contextual help. The page was inspected in the browser; its app description connects a plan-specific assistant with plan details. Borrow the continuity between plan investigation and the next practical question. We did not validate its marketing claims about market completeness, commissions or clinical/insurance accuracy. [Public tools](https://thepocketprotector.com/tools), [plan-aware app description](https://apps.apple.com/us/app/the-pocket-protector/id6761775147).

**Medicare.gov.** The official tools page separates plan comparison, drug-cost estimation and Medigap discovery. Keep those category boundaries visible, and make an official next step available when Daylight does not support the requested path or check. [Medicare tools](https://www.medicare.gov/basics/get-started-with-medicare/using-medicare/helpful-tools).

The resulting design uses familiar stacked plan cards and a small shortlist, but makes reasons, tradeoffs, field definitions and unresolved checks first-class. Persistent chat makes the comparison discussable without moving the person away from it. A small visual context payload keeps “this plan” grounded without treating clicks as preferences or streaming browsing to the model.

## Existing sources retained

- [Principles](../../../PRINCIPLES.md), [strategic checklist](../STRATEGIC_THESIS.md#ui-and-system-change-review-checklist), [current delivery scope](../../project/COLLIER_MVP.md).
- [Exact r13 catalog](../recommendation-scope-2026-11-04-r13/display-candidate.json), [methods and holds](../recommendation-scope-2026-11-04-r13/REVIEW.md), [original product plan](../recommendation-scope-2026-11-04-r1/PLAN.md).
- [Profile adapter](../../../alternatives/advisor-first/comparison_profile.py), [comparison service](../../../alternatives/advisor-first/comparison_service.py), [existing proposed rules](../plan-comparison-2026-11-01/DECISION_RULES.md).
- [Owner/variant boundaries](../../../alternatives/advisor-first/AGENTS.md), [consumer registry](../../../cms-slice/data-sources/consumer-acceptance.json).

## D73 review

The proposed task improves self-service understanding and comparison. It reuses consequential reports and leaves browsing possible without universal intake. Coverage paths/current coverage/keep/defer remain visible. Report confirmation and external authority are separate. Reasons, evidence dates, assumptions, disputes and commercial independence are explicit. Saving, AI context and outside sharing have separate controls. Current capability is reported as a design plus an offline reference, not a released recommendation service. Consumer comprehension, live view-aware conversation, accepted personal checks and a supported action path remain to be demonstrated.
