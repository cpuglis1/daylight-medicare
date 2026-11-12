# Backend finite-answer and dependency review

Scope: the local :8893 advisor variant, D49/D54/D55/D57/D86. This is code and deterministic service testing, without browser automation or paid/model-provider calls. The retained :8890/:8891 dependency engine was inspected but not edited. No evidence, recommendation, comparison-purpose, privacy, store or budget gate was unlocked.

## Inventory and method

`backend-question-audit.json` enumerates all **41 approved inventory meanings**, their **38 distinct parent questions**, the **103 default finite-choice entries**, field names, dependencies, optional/internal dispositions and the T10 maximum. RC11.C1, RC16.C1 and RC16.C2 remain aliases within their parent questions, not extra survey screens. Some of the 38 parents are conditional or internal; enumeration is not an instruction to ask every question.

`tests/test_button_backend_gates.py` submits every one of the 103 current default question choices through the actual `NaturalConversation.turn` service with `aiConsent=False`. The test checks the committed field/fact or explicit disposition and verifies that input completeness never becomes verified coverage or permission for a recommendation. It also submits Unknown and Check later for every parent question, with required medicine identity supplied for fill details. A separate production-renderer matrix audits the actual rendered payloads and conditional field buttons; see the enclosing audit packet.

More consequential state transitions receive explicit expected-question, field, entity and stale-report assertions instead of only acceptance checks:

| Meanings | Backend routing reviewed and tested |
| --- | --- |
| T01 / T02 / RC01 | Goals navigate; explanation preference remains a presentation preference; who-this-is-for is distinct from research-only and unknown/deferred. Research-only and leaving the subject open no longer repeat RC01. Explicit task/goal changes clear the former topic's question target. |
| T03 / RC02 / RC03 | ZIP/county/year collection keeps its retained validation and location-reference rules. County/year field payloads are included in the separate renderer matrix; they do not establish exact plan availability. |
| T04 | Soonest, already covered, typed month/year and unknown remain distinct. An intended start preference establishes neither birthday nor actual enrollment. Existing typed-date/correction tests remain in force. |
| T05 / RC09 / RC11 | All 11 default insurance choices and all five worker choices are checked. Current-job coverage asks whose current job; COBRA/retiree coverage asks only coverage end unless another explicit check needs job end. Medicaid does not become Medicare or job insurance. Changing from employer coverage to Medicaid removes the obsolete work-date target and holds older work reports. |
| RC04 / RC05 / RC06 / RC10 | Part enrollment and Part B start stay distinct from current coverage and qualification basis. Payer-order requests require their retained dependencies; the employer-size buttons use 20 for age qualification and 100 for disability qualification. A button never adjudicates actual payer order. |
| RC07 / RC08 / RC12 / RC13 / RC14 / RC15 / RC17 / RC19 / RC24 / RC26 / RC27 / RC28 | Every constructor-exposed finite value is submitted and its meaning retained. Conditional/internal questions remain conditional/internal, with source and personal-purpose holds. An answer is not an enrollment event, verified creditability, Medigap right, SNP eligibility or provider/drug coverage finding. |
| RC16 and RC11/RC16 child aliases | Partial start/prior-Medigap and job/coverage-end clarifications resolve only supplied fields. Remaining fields stay open instead of forcing a repeated multi-field answer. |
| T06 / RC21 | Explicit no doctors retires prior active names/details while retaining recoverable history/provenance. Reintroducing a new list includes only new reports, even if a new office has the same name. Office entities remain distinct. |
| T07 / RC22 / RC23 | Explicit no prescriptions retires old identity/fill facts from model context and comparison. A new list cannot resurrect retired names. Fill controls require an existing active medicine; sibling medicine identities and partial strength/form or days/channel resolution remain separate. |
| T08 / RC20 | Local-only and unknown do not force an away-from-home location question. Explicit domestic/international routine-care needs ask the missing location. A corrected local-only report cannot revive an old away-care target. |
| T09 / T10 / RC25 | Preferences/budget scope do not become personal total-cost findings. Finite T10 selection exposes and enforces a maximum of three. Explicit longer text reports are preserved rather than silently truncated. Conditional budget field payloads retain validation. |
| RC18 | A submitted named-program selection replaces that selection, so deselecting a program works. Text-derived additional program reports remain additive. Explicit None is distinct from decline/unknown; declining or leaving the answer unknown preserves previously reported positive programs without treating them as externally verified. |
| Unknown / Check later | Buttons now use the same precise pending-target semantics as typed unknown/defer. They preserve other fields/items and their aggregate hold, and release it only after all pending clarification targets are resolved or explicitly left open. |

## Defects corrected

1. Unknown/Check later buttons could leave the old medicine/provider target visible and discard sibling clarification queues on the next candidate calculation.
2. A partial finite field or submitted field could commit successfully yet leave the full original clarification pending forever.
3. A model-selected second item's field could be replaced by the first item's default dependency, misdirecting or rejecting its visible controls.
4. A corrected dependency could resurrect an obsolete question: for example no prescriptions still asking for fill details, or Medicaid still asking for the former employer's end date.
5. Research-only or an unknown/deferred beneficiary could repeat who-this-is-for.
6. No doctors/no prescriptions left old detailed facts usable by composition and comparison.
7. Starting a new list after No could revive retired names in the new active summary; retired collections now remain in history while the active collection starts afresh with new entity allocation.
8. RC18 edits accumulated removed programs instead of replacing finite selections; declining could erase earlier known positive program reports.
9. More than three finite priority choices were accepted despite the approved maximum, and the service question descriptor omitted that maximum.
10. An explicit fill entity could refer to a medicine that was never reported or had been retired by no prescriptions.
11. An ambiguous combined current Medicare route (Original + Advantage, or Advantage + Medigap) could become an active fact without clarification. New submissions now request clarification before mutation; typed proposals remain pending. Other named combinations, including Original + Medigap + separate drug coverage and Advantage + Medicaid/employer/retiree coverage, remain supported as reports without inferred enrollment or eligibility. Retained ambiguous profiles are not rewritten: assessment offers T05, candidate selection makes that clarification required, model context exposes only a conflicting presence marker, and the comparison adapter derives an unusable/conflicting report and hold until the person clarifies or explicitly leaves it open.

## Verification and limits

The 25 new backend tests passed in 27.323 seconds, the retained 43 natural-flow tests passed in 11.045 seconds, seven advisor-planning tests passed, 38 natural-state tests passed and 16 comparison-profile tests passed. These are deterministic software checks; typed retraction/clarification parity tests use an in-process scripted transport, never a model provider. No paid LLM calls, automatic retries, browser automation or changes to a real customer profile were used for this review. The encompassing packet records final combined-suite results and activation separately.

An ordinary finite `choice` action intentionally supports explicit report correction and settings actions beyond only the canonical scheduler's first question; a blanket current-question rejection would break those supported paths. `stage` remains bound to the actual current question and entity, and pending unknown/defer controls are bound to the precise pending target. The review does not claim every possible report combination or real-model response has been tested, nor that all source or personal recommendation holds are resolved.
