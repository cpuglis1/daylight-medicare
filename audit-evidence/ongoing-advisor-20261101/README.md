# Ongoing advisor implementation and verification

D86 · November 1, 2026 · local :8893 only

Implemented the owner's approved conversation structure. The interpreter proposes reports; software resolves them; the advisor generates a useful response from the resolved state, ongoing goal, recent conversation, reviewed teaching and conditional approved questions. Teaching and a consequential follow-up can share a turn. The existing UI is retained.

## Actual model contract

- GPT-5.4; two routine typed-message calls, at most one composition call after a deliberate finite-answer Send. No third planner, hosted conversation store or automatic paid retry.
- Interpretation outputs `updates`, `requests`, `fact_ids`, `agenda`, `situation_proposals`, `goal_quote`. Reports require current-message support; the explicit goal is a bounded exact quote. The legacy agenda is bounded compatibility metadata, not a command to route the conversation.
- Composition receives `resolved_context` and `question_candidates`. It outputs `question_target`, `reply`, `question`, `report_refs`, `evidence_refs`, `agenda_update`. The old exclusive speech-move menu is removed. The 41 approved meanings remain conditional scope/dependency contracts.
- The brief separates product direction, explicit goal, present concern, pending question, pause, explicit familiarity and previously explained topics. Familiarity is tentative prompt/context calibration, not a saved inferred score or proof of comprehension.
- Both reasoning settings currently remain `none`, with a configurable composition setting. Output cap remains 900 tokens. A higher reasoning setting was not evaluated or enabled in this revision.

The service passes newly accepted/reaffirmed reports even when the next question changes the context lens. It supplies related unchanged qualifiers where needed, such as whose current job supplies insurance. Corrections carry validated before/after receipts; old values cannot become current facts. Birthday month, desired start, actual enrollment, job end and insurance end remain separate. Research-only visitors can continue without personal intake.

Canonical question selection normally comes from the model's target. If the model omits a target but supplies the exact, unambiguous canonical wording of an available question, the adapter restores that ID. It does not guess a target from semantic phrase detectors. Educational follow-ups can retain a null target.

## Privacy and preservation

`natural-context-v3` is supplied on deliberate Send. Existing privacy copy already discloses recent conversation and relevant profile transfer to OpenAI; no new modal or visual control was added. Old v1/v2 permissions do not authorize v3 cross-topic memory.

Visit memory is owner/chain-bound RAM: at most six complete exchanges, 5,000 combined characters, a one-hour TTL and 128 visits. An oversized exchange is omitted intact. Raw dialogue, explicit-goal quote and the new working agenda/return point are not saved to guest profiles. Resolved reports remain the personal-fact authority. Saving and sensitive-field saving stay separate choices.

The before/after hash inventories show unchanged HTML, six CSS files and engine lock. The only frontend change is the Send permission version in `advisor.js`; reveal/rendering behavior is covered by the normal suite. No changes to :8890/:8891, pinned engine code, shared evidence releases or guest-store migration are part of this work. The shared ledger and the existing $5/UTC-day :8893 allowance are retained.

## Verification

**379 tests passed** in the final normal suite, including loopback HTTP tests, existing Node-backed Send/render/reveal checks, model-wire validation, natural-flow acceptance, privacy/storage isolation, cross-topic memory bounds, uncertainty/correction, recovery, replay and finite-answer parity. See [tests.log](tests.log). Scripted transports verify controller contracts; their prose is not model-quality evidence.

The real GPT-5.4 checks used fictional inputs and disposable databases, without saving a profile. They exercised:

1. Turning 65 in November, wanting enrollment and reporting limited knowledge.
2. Asking when coverage should start; a reviewed explanation plus current-insurance follow-up.
3. A Part B side question while retaining the practical return point.
4. Current insurance through a spouse's job.
5. A March 2027 job end and distinct April 2027 insurance end.
6. Correcting November to December without inventing a birthday year.

[Accepted journey](accepted-journey.json) records the actual outputs and their source attempts. This was **diagnostic testing followed by continued sessions**, not one uninterrupted final-build journey. To conserve credits, later runs resumed accepted fictional state and bounded visit memory. The final correction was captured live; the last exact-target repair was then checked against that captured response offline, with no paid call. See [offline validation](offline-final-validation.json).

Earlier failed checks remain in `attempt-1` through `attempt-6`. They exposed a new-teaching-ID compatibility error, an uncertain coarse goal restarting intake, a malformed entity value, missing current-report/relationship context, a birthday correction misclassified as a coverage contradiction, and an unsupported computed personal calendar. The integration fixes and regression tests address those failures; the calendar assertion remains blocked, with prompting now directing the advisor to use only authorized supplied calendar results.

All diagnostics together used 32 paid generation stages. **Total accounted estimate: $0.5031975; outstanding holds: $0.00.** The shared ledger recorded the charges. See [per-run accounting](cost-summary.json). Accepted-turn measured latencies ranged from 3.979 to 6.598 seconds in these checks. This is a small local sample, not a latency guarantee.

General first-enrollment education was added locally with reviewed Medicare.gov sources. [Source review](education-source-review.json) records the scope. It does not release a personal timing calculator or modify accepted L01/L03 references.

## Activation and UI observation

Restarted only `com.daylight.advisor-first.8893`. Landing page, configuration and status returned HTTP 200; the served model policy is `D86-ongoing-v3`, live mode, reasoning `none`. See [activation receipt](activation.json). Reload :8893 before starting a new test so Send uses v3 and the restarted service creates a fresh visit chain. Saved reports are retained.

The existing browser tab was observed without submitting or altering its contents. [Landing capture](browser-landing.png) records the unchanged narrow viewport. Full new desktop/tablet/phone interaction testing was not performed for this backend revision; static asset hashes and retained interaction tests support preservation, rather than a new visual-design acceptance claim.

## D73 review and limits

| Review item | Evidence or remaining gap |
| --- | --- |
| Useful self-service and comprehension, D49/D73/D86 | Explanations can accompany useful next questions and side questions preserve continuity. Technical and small model checks exist; consumer comprehension and reduced effort remain unmeasured. |
| Consequential minimal intake, D52 | Clear reports consolidate; ambiguity clarifies; conditional 41-question meanings remain. No mandatory per-turn confirmation or second questionnaire. |
| Coverage paths before policies, D73 | Reviewed path education remains available. Policy recommendations and validation are separate work with separate release gates. |
| Independent, inspectable decisions, D64/D73 | Commercial economics remain excluded from prompting and question selection. Provenance, superseded receipts and evidence/action guards remain. These literal guards are not full semantic entailment checks. |
| Permissioned continuity, D53/D54/D57 | Versioned Send scope, RAM bounds and profile-storage isolation have automated checks. No transcript persistence or silent old-permission expansion. |
| Two distinct gates, D73 | Report completeness does not verify coverage, eligibility, doctors, medicines or plan suitability. Comparison-service holds remain authoritative. |

Natural-language quality and broad language coverage still need observation. A birthday milestone without a usable month does not fit the existing canonical month/year report shape; it is not represented as a complete birthday report. This implementation does not establish consumer approval, recommendation readiness, independent source acceptance, savings or comparative superiority.

Primary implementation files: `alternatives/advisor-first/natural_agent.py`, `natural_flow.py`, `advisor_memory.py`, `advisor-evidence.json`, `server.py`, `model-policy.json` and the Send version in `web/advisor.js`. Requirements and the [execution contract](../../docs/product/ONGOING_ADVISOR_FLOW_2026-11-01.md) record this scope alongside D49/D52/D53/D54/D57/D64/D73/D86.
