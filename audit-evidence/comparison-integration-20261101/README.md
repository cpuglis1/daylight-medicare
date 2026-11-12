# Comparison layer integrated with the actual advisor

November 1, 2026 · D87 · Local implementation and bounded technical verification.

The owner approved building the [profile-grounded comparison design](../../docs/product/plan-comparison-2026-11-01/README.md), specifically requiring compatibility with the actual AI/chat architecture. This implementation adds comparison derivation inside :8893's existing turn pipeline. It preserves the ongoing advisor's proposal-only interpretation, service validation, conditional question candidates and grounded composition; it adds no model stage or parallel conversation router.

## Implemented behavior

| Component | Actual behavior |
|---|---|
| [Profile adapter](../../alternatives/advisor-first/comparison_profile.py) | Pure projection of the existing owner-validated guide/readiness snapshot. Checks the frozen baseline metadata and five original source bindings; accounts for all 41 meanings, 78 baseline paths, three aliases, eleven wording variants and fourteen open gaps. Preserves current advisor extensions, truthful provenance, item revisions and partial/unknown/none/stale states. Learner and unscoped legacy reports cannot establish beneficiary applicability. |
| [Evidence boundary](../../alternatives/advisor-first/comparison_evidence.py) | Server dependency with all six real consumer purposes held. No production release loader, database connection or fictional catalog. Client JSON cannot supply evidence authority. Fictional test sources remain labeled and grant no real release. |
| [Comparison engine](../../alternatives/advisor-first/comparison_engine.py) | Deterministic response bindings, partial current arrangement, keep/defer outcomes, condition-preserving findings, external work items and internal all-41/gap accounting. Explicit preferences affect emphasis without inferred weights or ranking. Structural condition logic and exact comparable-value arithmetic are exercised with fictional evidence. |
| [Service bridge](../../alternatives/advisor-first/comparison_service.py) | Attaches a private `comparison` beside the normal turn response, outside saved `guide`/`record`. Rebinds after final report/composition bookkeeping. Optional derivation errors preserve accepted reports and return fixed-code holds. |
| [Natural controller](../../alternatives/advisor-first/natural_flow.py) | Evaluates after resolution for composition, after final bookkeeping for return, and again on replay without extracting/composing again. An obsolete owner chain, changed evidence/method or later profile state cannot republish stale prose/question/derived selection. |
| [Composer](../../alternatives/advisor-first/natural_agent.py) | Receives only bounded public `comparison_status` markers. Existing permitted reports and reviewed teaching retain their own context/reference rules. A hold marker is explicitly not plan evidence or a completed research receipt. |

The existing authenticated/CSRF-protected `/api/conversation/turn` returns this additional derived object. No extra endpoint, questionnaire, review ceremony or consumer storage is introduced. Typed messages retain two model stages; an eligible deliberate finite-answer Send retains at most one composition stage; manual actions need none. The comparison service itself calls no model.

## Compatibility with the ongoing advisor

The separately authorized [ongoing advisor contract](../../docs/product/ONGOING_ADVISOR_FLOW_2026-11-01.md) was implemented concurrently in the shared workspace. The comparison integration preserves its goal/topic distinction, proposal-only wire format, conditional question candidates and `natural-context-v3` visit-memory boundary. The comparison tests script that current wire contract rather than assuming the earlier extractor/router response.

Comparison data is not a new profile authority, saved transcript, AI-context allowlist or independent question planner. The controller supplies eligible questions. The service can identify useful missing report meanings and external holds, while the advisor may answer, explain and ask within the existing approved candidates. Whole comparison traces and extra personal values are never attached to the model request by this layer.

## Verification record

- **51 comparison checks passed** across profile, engine, actual controller/model transport and isolated HTTP/session/save boundaries. An independent agent reran the same set successfully. Two later stale-replay assertions received additional hardening; final results/hashes belong in [VERIFICATION.json](VERIFICATION.json).
- The first broad advisor run executed **346 tests**, with **three failures** retained in [full-suite-first.log](full-suite-first.log). They concerned concurrent v3 permission/next-question expectations. This historical run is not described as passing; final combined-suite disposition is recorded separately.
- The final combined advisor suite passed **350/350 tests in 24.113 seconds**, including the nested Node behavior checks: [full-suite-final.log](full-suite-final.log). The concurrent advisor revision corrected its earlier expectation mismatches and added checks. Independent final comparison review found no unresolved material integration issue; its last replay/prompt recheck passed 10/10.
- A subsequent concurrent advisor-source edit received a fresh **51/51 comparison recheck in 2.221 seconds**: [comparison-final.log](comparison-final.log). The receipt distinguishes the combined-suite snapshot from the latest comparison snapshot; this workstream does not claim to freeze the other ongoing advisor work.
- A disposable fixture server and new temporary synthetic database were used for the browser check. Get started, selecting Find coverage, deliberate Send and the next beneficiary question worked. A draft survived selection, the one composer and quiet controls remained, and no premature comparison/recommendation card appeared. The preview was closed and its own process stopped. [Fictional screenshot](fixture-browser.png).
- No paid AI, real guest-store access, PostgreSQL connection/mutation, cloud provisioning or source release was performed by this workstream. Scripted model transport verifies integration order and payloads; it does not establish live-model language quality.

The normal comparison command is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s alternatives/advisor-first/tests -p 'test_comparison*.py' -v
```

HTTP tests require loopback access and use temporary databases. The full advisor suite remains the standard `unittest discover -s alternatives/advisor-first/tests -v` command, including nested Node behavior cases.

## Exact scope and remaining work

This is a working comparison foundation and chat connection. Its production response is `research_preparation`: `accepted_release_id=null`, no real consumer plan set, and published display/personal comparison/ranking/recommendation/quote/enrollment authority held. It does not query the 58 GB research database or convert research completeness into consumer acceptance.

Still required before actual personal plan comparisons: normalized accepted serving identities and full condition-preserving facts; original-authority replay and a real release loader; reviewed finding-specific input classifiers, domain rules and cost methods; scoped hard-constraint evaluation (G12); actual evidence/identity integrations; independent source/method/release review. All fourteen gaps remain open in the response. The preserved 2027 sample browser is not relabeled as a released 2026 personal comparison.

The original r4 references, full L03 r9 obligations, source stops, D64 economics exclusion, protected :8890/:8891 runtimes/stores and shared budget remain unchanged by this comparison work. Baseline [protected source/asset hashes](PROTECTED_BEFORE.json) and before-images are retained. Concurrent ongoing-advisor changes to `web/advisor.js` and `model-policy.json` are distinguished from this workstream's edits; no comparison patch changes web/CSS/HTML/assets or model/budget settings.

No live-service restart or consumer activation is claimed by this packet. Deployment and broader ongoing-advisor verification are separate from the fixture checks reported here. Technical tests and AI-agent review do not constitute qualified Medicare-domain acceptance, owner approval of output wording, performance certification or observed consumer comprehension.
