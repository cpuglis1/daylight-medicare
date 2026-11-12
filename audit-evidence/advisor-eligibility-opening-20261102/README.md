# Eligibility opening and recovery correction

D86/D73 bug report: “I am 64 and looking to enroll in medicare when eligible, but don't really know when that is” yielded no explanation, a preferred-start question and the generic failed-reply notice.

The generic notice means composition could not be delivered. Retained fixed-code logs include unsupported-personal-finding rejections, but no original generated text or turn identifiers: the exact original rejection cannot be reconstructed. The initial controlled reproduction stopped before generation with both reservations cancelled and $0 charged; it is retained in [reproduction.json](reproduction.json). It did not reproduce the original composition failure.

## Changes

The interpreter now explicitly recognizes confusion about when eligibility/enrollment begins as a request for clarification, separate from a preferred start, a birthday date and actual Medicare status. Composition guidance answers that request with reviewed general rules before asking a preference; it does not declare personal eligibility or invent a birthday/year. No personal-finding or factual guard was relaxed.

Timing tasks now prioritize current insurance before desired start even when no birthday date is recorded. For an initial validated timing-explanation request, recovery uses current insurance if available, preserving mandatory/person clarification and an actual previously delivered return point. The corrected recovery target is recorded so refresh does not revert to the old start-date question. Explicit unknown/defer and comparison-first ZIP ordering remain. No questionnaire, new stage or fixed fallback teaching was added.

## Verification

[Final regression output](tests-final.log) records **236 passing tests** across the interpreter/composer, natural flow, continuity, decision guidance, education, ongoing-advisor and new timing-recovery checks. The new cases cover the exact fresh opening defaulting to comparison, a rejected personal eligibility assertion, preserved correction/unknown/defer/person/edit dependencies, existing return points, bad request quotes, no inferred dates, and target stability across refresh. The [initial run](tests.log) caught the fresh-recovery gap while the fix was being completed; the [nine-case recovery rerun](recovery-tests.log) and final combined run pass.

The [bounded diagnostic](diagnostic.json) used the exact opening as a fictional functional check: two completed stages, **$0.04206** settled, no saved profile, no automatic retry. The reply explained general age-based eligibility/enrollment timing, chose **T05 current insurance**, and returned complete with no failure notice. The earlier pre-generation failure cost $0. This is one functional check, not the longer conversation-quality evaluation the owner will perform. The [harness](reproduce.py) retains a strict one-turn/two-stage ceiling and temporary private database.

Existing general source material was checked against [Medicare’s introduction](https://www.medicare.gov/basics/get-started-with-medicare) and [enrollment timing](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-can-i-sign-up-for-medicare). No source evidence release or personal eligibility determination was added.

[Activation receipt](activation.json) records the :8893 restart and hashes. The 16,000 input/900 output limits, $5 UTC-day allowance, privacy/saving, accepted interface and all real evidence/recommendation gates remain. Only :8893 is activated; protected variants and saved profiles are untouched. Refresh for the updated visit context.
