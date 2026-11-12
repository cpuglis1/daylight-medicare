# Additional edge-profile assessment · October 28, 2026

The owner approved creating and testing a few more targeted profiles after the first five-profile review. Five additional fictional profiles, **P6–P10**, are saved in [PROFILES.json](PROFILES.json), with intended scenarios, submitted actions, observed final guide/readiness snapshots and failing assertions. No product/runtime change or insurance-rule acceptance is claimed by this assessment.

## Results

| Profile | Controlled HTTP test | Live-agent spot-check |
| --- | --- | --- |
| P6 Conflicting dates / correction | Pass: uncertain date held for confirmation, rejection preserves the old date, confirmation applies, and explicit correction changes only the target date. | **Blocked:** the natural uncertain reply returned HTTP 503, “The requested task needs clarification.” The original date remained intact. |
| P7 Mostly unknown answers | **Fail:** seven explicit unknown answers stop intake safely, but only six appear in the open-details summary. | Same defect through the running service; this path needs no model generation. No coverage or readiness was invented. |
| P8 Side question / changing goals | Pass: side education preserves the active question; explicit learning/drug/comparison changes reuse prior information. | **Pass:** real teaching preserved the task; an explicit learning request changed it; returning to comparison reused earlier facts. |
| P9 Mother / helper have different insurance | Pass for integrity: helper facts and a recipient switch cannot overwrite the mother’s profile. | **Safe but blocked:** the profile stayed with the mother and COBRA, but the natural reply returned the same generic HTTP 503. This is not a clean conversational pass. |
| P10 Same medicine name / different strengths | **Fail:** two explicit new reports become one item; the later strength overwrites the first. | **Reproduced with real AI:** “Example Med 5 mg tablets” and “Example Med 10 mg tablets” became one `medicine-1` entry with only 10 mg. |

Three of five profiles pass the controlled invariants, two fail. A separate ambiguous-fill guard test passes: with two distinct named medicines and completed fills, “Change it to 90 days” cannot choose an arbitrary medicine without an item binding.

The live assessment has **one clean workflow, two safe-but-blocked replies and two other failures**. The raw P9 data-integrity checks passed; [assessment.json](assessment.json) explicitly separates that from its failed conversational outcome. These are single-run spot-checks, not population reliability estimates. There were five real generation attempts, with no automatic retries, estimated at **$0.0645275**. All are settled under the unchanged shared $1/UTC-day cap. The ledger’s UTC day is recorded in the evidence; the local review date is October 28, America/New_York.

## Findings requiring fixes

1. **Highest priority: same-name medicine identity collision.** `adaptive_flow.py` resolves a `new` medicine to an existing entry using the name alone before it considers strength/form. The second report overwrites the first. The later fallback matching block has the same name-only assumption. This can lose a distinct reported product and mis-scope later fill work. A new item must remain distinct unless the existing-item binding is actually unambiguous. The controlled and real-agent runs both reproduce this defect.
2. **Open-details summary omits some unknowns.** The controller records a choice-only non-baseline unknown in `record.dispositions`, but the summary gathers only baseline dispositions and per-field skipped details. The demonstrated missing entry is RC01, “Who is this coverage for?” All seven unknowns still prevent a recommendation, but the visible summary lists six. Other choice-only non-baseline entries sharing this path need review; they were not exhaustively tested here.
3. **Task/quote validation produces generic errors for legitimate continuation replies.** P6’s uncertain date and P9’s helper/beneficiary distinction were rejected with HTTP 503 by the task-declaration quote guard. Both old profiles were preserved, so the guard failed safely. The system still needs a useful clarification or valid continuation interpretation instead of stopping the conversation. This assessment did not capture raw model commands or infer a more specific cause than the returned guard error and its code path.

These defects are **open**. No assertions were weakened, marked expected-failure or suppressed to make the results green. No production patch or deployment was performed as part of this test-only request.

## Evidence and limits

- [Controlled traces](controlled-results.json) run the actual HTTP/CSRF boundary, strict language adapter, controller and report validators with scripted model outputs and temporary stores. Five profile tests plus one separate guard test ran: four tests pass, two fail. All five can explicitly browse labeled samples; sample browsing is not completion of a personal comparison.
- [Full bounded regression result](test-summary.json): **157 executed, 155 pass, two fail, zero errors**. The two new counterexamples account for both failures. One earlier source-identity test remains explicitly excluded because the relocated pinned `data-sources/release.json` package is absent; source validation is not declared passed.
- [Live traces](live-results.json) use the normal running :8891 endpoints, CSRF/Origin checks, explicit synthetic AI consent and existing budget guard. The five attempts were not retried or cherry-picked. Answers were visit-only; a final profile read confirmed no saved guide for the new test session.
- [Preservation](store-preservation.json) compares every pre-existing guest/readiness/AI-charge row and database inode. The live API created one new expiring empty authentication session; fictional answers were not written to the customer store. No pre-existing row was intentionally edited or removed, and no save/delete endpoint was used.
- [Source preservation](original-preservation.json) and [runtime comparison](runtime-check.json) record the original and alternative code boundaries. Only test fixtures and evidence/documentation were authored; the existing :8890/:8891 runtime, configuration, consent and source gates are unchanged.

The existing 41 question IDs, 78 field records and 14 representation/evidence gaps remain unchanged. These tests add state/ambiguity counterexamples rather than increasing the inventory denominator. They do not establish complete natural-language coverage, source-backed eligibility, actual plan matching, drug costs or human referral. Physical mobile keyboard, screen-reader execution and older-adult comprehension remain untested. The earlier 2026/2027 sample mismatch remains deferred.

Reproduction: `run_controlled.py` intentionally exits nonzero while the two defects remain. `run_live.py` makes up to five paid synthetic attempts through the guarded service and should be run only within authorized live testing; `assess_results.py` summarizes saved outputs without more model calls. Earlier evidence packets remain retained unchanged.
