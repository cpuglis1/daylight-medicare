# D86 frugal live advisor checks — October 30, 2026

The owner restored provider credits and authorized only tests vital to a natural advisor conversation, using credits frugally. This packet uses fictional messages and temporary isolated guest stores, the actual current backend and the existing shared $5/UTC-day allowance. No real profile was saved. No automatic model retries, credit purchase or budget reset occurred.

## Result and cost

The bounded case passes after one targeted guard correction. **Total measured generation estimate: $0.059409 (about six cents), with no new uncertain holds.** Seven generation requests were made: three extraction requests and four composition requests. The fourth composition was a deliberate targeted check following a rejection; the first two messages were not extracted again. These amounts are token-based estimates, not an invoice.

- [Initial live results](results.json): $0.0288365 for two turns / four requests. The first completed; the second captured the profile but its generated wording failed a literal-grounding check. The run stopped immediately, leaving the third turn unissued.
- [Targeted recovery and remaining turn](remaining-results.json): $0.0305725 for three requests. One composition reused the accepted second-turn profile, and the Part B turn ran through HTTP after the actual refresh/resume path. Both completed. No complete fresh three-turn rerun was purchased after the correction.
- [Free regression suite](tests.log): **192 tests pass** in 7.204 seconds. This includes four new grounding tests with multiple subcases.

## What the live checks established

1. [Retirement/birthday report](turn-1.json): clear facts were captured without a confirmation card; November's year remained unknown; retirement did not become retiree insurance. The reply connected the story to getting started and asked one open question about Medicare progress.
2. [Second-turn reports](turn-2.json), [targeted generated reply](targeted-turn-2.json): explicit insurance through the wife's current job became employer coverage plus the spouse-worker relationship. “Not applied yet” did not become actual A/B enrollment, and “getting started” did not become Medicare expertise. The next question asked preferred coverage start rather than repeating the insurance question.
3. [Educational pause](turn-3.json): Daylight answered Part B from the supplied reviewed teaching without adding an intake question. The prior profile survived, and a free service assessment still returned the unanswered desired-start target afterward.

The first live reply was:

> Turning 65 in November is usually the point when people start sorting out Medicare timing, even if they’ve been retired for a while.

It continued: “Where are you with Medicare so far?”

Independent review passed these outputs for this case: useful human connection, concise wording, one relevant question, no routine acceptance card, no false enrollment conclusion and respect for the educational pause. The second reply's coverage-end rationale is general; it does not assert that this person's insurance ends on a particular date.

## Guard correction

Offline reproduction proved that the case-insensitive month detector treated the modal word **may** in “That may help…” as the month **May**. The local `_literal_claims` helper now distinguishes bounded modal/polite constructions from dates while retaining case-insensitive checks for actual May dates, including date prepositions, bare months, birthday/month labels and years. Unsupported dates and amounts remain blocked.

The rejected second live composition's raw text was not retained by the first harness, so this packet does **not** claim to reconstruct its exact offending token. The modal-May false positive was independently reproduced and fixed offline. The targeted harness then captured only its own fictional composition inputs/outputs to verify acceptance; production logging was not expanded.

Only `natural_agent.py` and `tests/test_natural_agent.py` change behavior for this correction. There is no UI/style change. Only the :8893 launchd job was restarted. [Active service status](active-status.json) verifies health without another generation. [Preservation comparison](preservation-after.json) checks protected files, existing database rows and inodes without emitting personal values; prior packets remain unchanged.

## Limits

This is one short fictional scenario, not broad dialogue reliability, consumer comprehension or superiority-over-forms evidence. All source/recommendation and privacy gates remain. Negative application progress is deliberately not mapped to actual A/B enrollment, but it is not yet separately retained as a typed application-progress report; future turns therefore cannot rely on that detail as a stored fact. This known context-model gap needs an explicit, scoped data-contract change rather than inventing enrollment status.

No more paid calls were vital for this check. Future paid testing should target an observed failure or a materially new branch, rather than rerunning this same successful case for confidence alone.
