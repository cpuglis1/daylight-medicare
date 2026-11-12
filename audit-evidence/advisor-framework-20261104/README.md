# General learning and decision framework

November 4, 2026 · D86/D73 · advisor-first :8893

The owner rejected the caregiver-specific implementation. Its role/coverage trigger, fixed explanations, compulsory application question, one-repair limit and fixed document offer have been removed from runtime. The earlier implementation is retained under [before/](before/), alongside its original evaluation packet.

## Shared method

Every permitted advisor conversation receives the same two kinds of context.

1. **Understanding:** the existing 17-concept curriculum now describes useful learning outcomes. Its existing delivery receipts record what was explained. Separate, tentative learner observations retain the current words that support an interpretation about a specific concept or aspect. For example, understanding premiums can coexist with uncertainty about deductibles. Unobserved concepts remain unknown. Self-reported familiarity, application, confusion, misconceptions and a request to skip are distinct observations.
2. **Decision progress:** the existing goal, resolved reports, eligible questions, preparation work and comparison capability describe what is known, what might be consequential to ask, and what remains unverified. Learning does not complete intake or verify coverage; collecting information does not establish understanding.

The existing composition stage considers both. It chooses explanation, clarification, a consequential question, a useful supported action/next step, or an ending. There is no additional planner call, learner score, required lesson sequence or new questionnaire. Ordinary optional questions retain relevance labels but are no longer sorted into a task-specific completion sequence. Actual dependency and ambiguity checks remain protected.

The controller checks source references, approved report meanings, exact supporting quotations, learner/beneficiary scope, privacy and actual capability. It does not replace the model's valid reply with scripted educational text. Current learner uncertainty can support a source-backed clarification even when a lesson was already delivered. The model chooses whether that is useful now.

## Implementation

- [learner_state.py](../../alternatives/advisor-first/learner_state.py) validates and retains observations, without choosing dialogue moves. Latest observations revise the same scope; more specific or overlapping observations remain available in chronological order for nuanced interpretation.
- [education.py](../../alternatives/advisor-first/education.py) adds outcomes to the existing concepts and source-scoped aspects.
- [natural_agent.py](../../alternatives/advisor-first/natural_agent.py) uses one shared instruction across tasks and roles and proposes evidence-linked observations in the existing interpretation stage.
- [natural_flow.py](../../alternatives/advisor-first/natural_flow.py) supplies learner evidence alongside the existing profile, decision and verification context. It retains observations only after successful processing and uses ordinary source/response checks.
- [decision_guidance.py](../../alternatives/advisor-first/decision_guidance.py) supplies advisory relevance rather than a prescribed optional-field order. Failure recovery still offers a valid relevant question.

The learner record contains up to twelve recent observations, each with a bounded quote and interpretation. It uses the existing owner/chain/one-hour v3 visit RAM, separate from saved profiles. Older permission cannot read it. Deletion and expiry apply with the rest of the visit. An exact quote establishes provenance, not semantic correctness: these remain model judgments that can be corrected, never verified comprehension. Existing source-purpose, recommendation, privacy and budget boundaries remain.

## Evaluation

[Four fictional live probes](live.json) used the same GPT‑6.1 Sol configuration and framework. They cost **$0.201268** in total and took **61.89 seconds**. There were no case-specific response substitutions.

| Situation | Observed behavior | Remaining quality concern |
| --- | --- | --- |
| Newcomer asking what Medicare is | Recorded unfamiliarity, explained foundations and offered a next learning question. | The answer introduced several related concepts and leaned toward further education. Depth and practical progression need observation in longer conversations. |
| Caregiver with mixed understanding | Retained premium understanding and deductible uncertainty as separate aspects; explained the deductible and asked about the doctors that mattered. | Must continue checking the learning interpretation against actual user responses. |
| Experienced person seeking a network check | Recorded specific cost understanding and the request to skip basics; asked for clinician and office details, with verification explicitly unresolved. | The actual external network check is still governed by existing capability and source availability. |
| Confident misconception about zero premiums | Identified the misconception, explained costs beyond premiums, and generated its own application question. | Several definitions were introduced; concise pacing remains an evaluation dimension. |

These are independent first-turn probes, not complete consumer journeys or proof of human learning. Small wording refinements about chronology and consequential dependencies followed the probes; they were covered by code checks, not another paid run.

The focused tests cover all concept identities, distinct aspect understanding, correction, wrong-subject/unsupported evidence, memory isolation/expiry, simultaneous profile and learning progress, generated prose preservation, repeat clarification without a scripted repair limit, and failure behavior. Regression expectations that required ZIP or another optional field to be first were replaced with relevance and eligible-choice checks. The underlying personal-fact, source and permission guards were preserved.

The next product evaluation should follow full conversations across these situations and score both understanding and decision progress. It should record unnecessary explanation, consequential information gained, unresolved checks, useful continuation and user effort. Finding a weak response should first improve the shared context, instructions or evidence access rather than introduce another persona-specific route.

Final verification: **925 advisor tests passed** in 159.929 seconds with localhost fixtures enabled, and the latest focused framework checks passed. The local :8893 runtime was restarted and returned HTTP 200. Source hashes are in [source-manifest.json](source-manifest.json). The UI files were not changed and no public deployment or consumer recommendation release was made.
