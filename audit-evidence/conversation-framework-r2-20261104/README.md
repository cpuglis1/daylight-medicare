# Conversation framework r2

November 4, 2026 · D86/D73 · advisor-first backend; UI unchanged

**Status: implementation complete; all 952 regression tests pass. Live conversation validation is blocked and the candidate has not been activated. No improvement in model conversation quality is claimed.**

The owner requested a flexible underlying framework, removal of conflicting instructions and complete conversation tests before describing the experience as improved.

## Changes

- Replaced the accumulated composition instructions with one shared policy: respond to the person's current meaning, use their words as tentative evidence of understanding, and choose explanation or consequential intake according to their goal and available capabilities. Removed the 80–140-word target. A short answer, question or natural ending can be sufficient. The model need not follow an acknowledgment/lesson/question pattern.
- Separated evidence constraints from conversational depth. A narrow explanation retains the conditions material to its claim; available source material is not a requirement to teach every detail. An unavailable personal result calls for a specific boundary and an available next step, without further intake that cannot resolve it. Personal calculations and external verification still need their existing authority.
- Removed the COBRA-specific question promotion and automatic lesson following a routine COBRA answer. Relevant source material remains available to the advisor; it does not prescribe dialogue.
- Removed a broad-task override of the person's open concern. Candidate relevance stays advisory. Natural expressions of a clear preference can be captured alongside uncertainty about how to achieve it.
- Removed whole-answer deletion based on rejected education delivery metadata. Source-validated prose and citations survive; invalid delivery updates still receive no learning credit or repeated visual.
- A failed generation retains an unresolved previously asked question or actual required clarification. It cannot choose a new optional intake direction. Same-visit refresh preserves that presentation, and short answers cannot be bound to an unseen default question.

The composer decreased from 9,943 to 6,510 characters. This measures instruction size, not quality. The existing learner record, profile, two-stage architecture, source validation, 41 meanings, permissions and shared spending cap remain.

## Complete-conversation evaluation

[journeys.json](journeys.json) freezes 17 user turns across retirement timing, a caregiver review with changing understanding, and an experienced user's doctor-check request. It includes clarification, application in the learner's own words, a detour, correction and explicit closure. Assistant responses are never authored by the harness. The same model, exact token checks, ordinary controller and shared ledger are used.

The review requires reading every response for continuity, demonstrated adaptation, consequential questions, repetition, practical resolution and truthful capability limits. Technical completion alone is not a passing quality score. These fictional journeys cannot establish human comprehension or consumer release readiness. The method follows the distinction between application-specific evaluation and generic scores in [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

[run_live.py](run_live.py) creates a fresh immutable attempt, uses disposable profiles, limits evaluation accounting to $1.10 within the unchanged $5 shared cap, records actual receipts and stops on a failed turn. It never repairs a journey with authored assistant text, replays a successful prefix or switches providers.

The first setup attempt made no model call: the harness omitted explicit provider selection, which the ordinary consent boundary correctly rejected. After fixing the harness, the [first provider attempt](attempts/20261104T211934741353Z/result.json) stopped at the first interpretation call with `credit_balance_exhausted`. Two fresh attempts after the owner's credit-restoration confirmations returned the same code, including the [final attempt](attempts/20261104T213040975231Z/result.json) against the final source. No conversation response was generated and no complete journey ran. Measured usage was unavailable; **$0.192 remains conservatively held across the three provider attempts**, rather than being reported as an actual bill or refunded. A value-free configuration check confirmed the fresh process loaded the project API key, with no inherited key overriding it. The provider's actual balance and the reason restoration is not reflected in its response remain unresolved. No further provider attempts were made.

To resume after credits are restored, run from the repository root:

```sh
infrastructure/daylight-data/.venv/bin/python audit-evidence/conversation-framework-r2-20261104/run_live.py --live
```

Review all three full transcripts against the frozen criteria before claiming improved quality or activating this candidate. A failed or incomplete run stays visible as such.

## Verification and preservation

[implementation-checks.json](implementation-checks.json) confirms all 38 web files retain their original hashes. [before/](before/) retains the preceding source and affected tests. Updated tests replace assertions that required automatic question selection or prose deletion with assertions for preserving facts, required clarification, source citations, learning-credit boundaries and displayed-question continuity. The final suite passed **952 tests in 169.104 seconds**, including exact-request replay, session recovery, privacy, HTTP and frontend contract checks. See [regression-final.log](regression-final.log), [source hashes](source-manifest.json) and [completion receipt](completion.json). Implementation/checking elapsed time was 17.17 minutes after the initial investigation checkpoint; this excludes the preceding conversation review.

For D73 review, the intended benefit is more consequential help with less repetitive intake. Keeping current coverage and neutral coverage-path education remain supported. Report completeness and verification are separate, and no commercial input or new recommendation authority is introduced. Source acceptance, privacy, saving, budget and protected-variant boundaries remain. Personal date computation and outside doctor/medicine checks are still governed by their existing capability limits; prompt changes do not supply those capabilities. The local service has not been restarted for this candidate while live quality validation is blocked.
