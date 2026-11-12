# D86: situation reasoning and categorical grounding

October 30, 2026 · Separate :8893 variant · Owner-authorized correction

The owner authorized implementing the diagnosis of the retired/turning-65 example. This work addresses D86 with D19/D21–D24/D49/D53/D57/D64/D73. The restored :8891 visual layout is preserved.

## Implemented boundaries

- The local `narrative_agent.py` removes incidental-word retrieval. Reports without educational questions receive no unsolicited teaching. Recognized topics and meaningful title/question matches supply relevant blocks; an empty retrieval is valid. The spurious match on “been” is gone. The orphan “No.” prefix was removed from the local checks block without adding an insurance claim or changing the other 17 blocks.
- The prompt distinguishes already retired, retiring now, actual insurance, desired coverage timing, actual enrollment and a reported age-65 milestone. It no longer equates retirement with a work transition. Full public question wording/options, purpose, requiredness, dependencies and important cannot-infer distinctions are supplied for all 41 IDs; child inputs normalize to their existing parent.
- Categorical guards reject the diagnosed unsupported leaps, including retired → retiree insurance, no Medicare → no health insurance, A/B entitlement → Original delivery, birthday → desired/actual start, negated insurance → positive coverage and historical work insurance → current work insurance. Supported parts of a multi-choice report are retained. These are specific guards alongside the language model and original validators, not a claim of universal logical entailment.
- Two additive fields, `situation.retirement` and `situation.age65`, preserve supported reported circumstances. The original 41 IDs, 78 field paths and 14 gap obligations remain unchanged. There are zero new required questions. The local observation recognizer preserves explicitly supported partial meaning, including an unstated year, without calculating an eligibility date or coverage start.
- Relevant circumstances produce a concise acknowledgment. Review includes personal reports rather than an inferred navigation goal. Accepting the interpretation advances to the missing question without repeating the same acknowledgment. The provisional timing focus is labeled accordingly and does not preselect Find coverage when editing the goal.
- Current insurance is asked before preferred start for an identified person who has supplied these timing circumstances. Someone already retired is not shown a job-ending timeline solely because their task concerns Medicare timing. Their birthday and unstated insurance/start values remain separate.
- Situation corrections use the existing composer and staged review; stale preparation authorization is invalidated by a revised report. Earlier sensitive values and raw history are not newly attached to AI. Public question semantics, not private dates, were added to context.
- Both conversation saving and the retained direct profile PUT omit the two new fields unless separate sensitive saving is enabled. Opted-in round trips preserve `year: null`. No new tables, customer migration, source release or transcript logging were introduced.

The :8891 engine remains hash-pinned and read-only. The local adapter includes a static copy of its bounded request runner to make reasoning effort explicit without changing the shared implementation. The default is now GPT-5.4 with **low** reasoning, strict JSON, no model tools, 8000 counted input tokens maximum, **900 total output tokens**, no automatic retries and the same persistent **$1/UTC-day** ledger. Rates and their expiration are unchanged. `model-policy.json` records the local selection; `/ten-config.json` exposes that public policy.

## Actual verification

**51 controlled tests pass:** 23 retained controller tests, 18 adversarial meaning tests and ten actual loopback HTTP/session/privacy/save tests. These include malformed birthday values, helper/hypothetical scope, genuine retiree insurance, preservation of supported Advantage reports, correction invalidation, sensitive-saving omission, direct-PUT protection and opted-in resume. See [test output](tests.log). JavaScript parses successfully.

Live evaluations use fictional inputs, existing AI consent/budget rules and no saved profiles:

| Model check | Result | Input/output tokens | Reasoning tokens |
| --- | --- | --- | --- |
| GPT-5.4 none: retired/birthday | Pass | 6879 / 176 | 0 |
| GPT-5.4 low: retired/birthday | Pass | 6879 / 425 | 260 |
| GPT-5.4 low: current-job transition | Pass; employer, job end and intended start retained; no invented insurance end | 6897 / 804 | 421 |
| GPT-5.4 low: genuine retiree insurance | Pass; explicit retiree coverage retained | 6891 / 686 | 342 |

The comparison shows these bounded cases work; it does not establish a general quality advantage for low over none. The 900-token limit remains a material bound for longer responses. The evaluation JSON files preserve per-case checks and usage. They precede the final review-label/acknowledgment/timeline presentation refinements; the final browser walkthrough checks the activated revision.

The real :8893 browser walkthrough consented to the fictional retired/birthday example, reviewed the supported facts, confirmed them and reached **“What health insurance do you have now?”** with no answer preselected. It verified the corrected timing guide, preparation-review return, the preserved chat shell and visit-only state. A second clean visit checked the final frontend/controller together. Screenshots and responsive geometry are retained alongside this report. No fictional profile was saved to the live store.

Only :8893 was restarted. `preservation.json` accounts for protected source hashes, pre-existing customer/ledger rows, store inodes and new settled test charges. Six bounded real-model checks settled in the shared ledger, estimated at $0.120324 in total. The final targeted design scan is `[]`; no new design-detector exceptions were added.

## D73 review and remaining limits

The consumer task improves through a relevant next question and truthful reuse of explicitly reported circumstances. Consequential minimal intake, optional learning/browsing, inline teaching, source inspection, correction and named preparation authorization remain. Original/Medigap/Part D and Advantage content, sample ordering and commercial independence are preserved. Reported completeness and external source acceptance remain separate; recommendations, personal prices, exact provider/drug fit, eligibility/enrollment adjudication and all source holds remain unavailable.

Observation recognition is intentionally conservative and finite. It is not a complete general-life narrative model or a replacement for the 14 documented representation/evidence gaps. In particular, these new birthday observations preserve month and stated year, not a complete day-level eligibility chronology. Unknowns remain unknown. Unsupported phrasing may still require clarification; larger inputs or outputs can hit the retained budget limits and fail closed.

No previously accepted or saved customer report was automatically rewritten. The old system did not retain sufficient semantic evidence to safely distinguish a genuine confirmed retiree-insurance report from a mistaken classification. Affected existing reports remain inspectable/correctable. Older open tabs should refresh to load the new frontend; in-memory reviews from before the restart may expire safely.

Physical mobile keyboards, screen-reader execution, older-adult comprehension and broad natural-language accuracy/latency benchmarks remain unperformed. Test totals and this small live sample do not establish consumer superiority or independent domain acceptance.
