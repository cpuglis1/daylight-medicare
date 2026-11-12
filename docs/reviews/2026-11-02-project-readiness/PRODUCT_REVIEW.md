# Daylight product, company and operating capability audit

Owner choices incorporated into the main assessment: the existing public `cpuglis1/daylight-medicare` repository is the code destination; the first Collier controlled pilot targets 2026. The [current hub](../../project/README.md) and [cloud handoff](../../project/CLOUD_HANDOFF.md) provide the reconciled plan. Workstream counts and checks below remain scoped to their inspection snapshots.

Read-only review · November 2, 2026 · product/company workstream for the broader local-to-team readiness assessment.

## Assessment

Daylight has made substantial progress beyond a mockup. The current advisor can interpret a situation, retain scoped reports, teach reviewed concepts, ask conditional follow-ups, recover from corrections and failures, and prepare an editable next-step checklist. It has a growing body of meaningful controlled tests and explicit privacy boundaries. The company thesis is unusually well specified: useful self-service, coverage paths before policies, evidence inspection, economic independence and consumer control.

The central promise is only partly delivered. The current real comparison response contains **zero consumer-evaluated plans**, **no automatic personal ordering**, and `personalized_recommendation_allowed: False`. Research is increasingly connected internally, but the advisor has not become a released service that completes a person's plan research and helps them select supported coverage through accepted personal comparisons. Human fulfillment, continuing service, acquisition and actual consumer/economic outcomes remain mainly specified rather than operated.

The bottleneck is now connecting and accepting the whole service, not inventing more product direction. Another general strategy rewrite would add less value than a current capability ledger, bounded implementation ownership, independently reviewed evidence and a real consumer study. Hosting and collaborative engineering can progress independently; moving the code to the cloud will not close those product or evidence gaps.

This audit does not assign an arbitrary completion percentage. A company component may have strong local mechanics and no released consumer outcome at the same time.

## Current surface and authority

- **Current active development surface:** `alternatives/advisor-first/`, localhost **:8893**, governed by its scoped `AGENTS.md`, current D86/D87 amendments and the retained interaction contract. The latest inspected README records November 2 curriculum and persona work as implemented/active; identity preview is explicitly internal research.
- **Protected existing surfaces:** :8890 ten-question (`cms-slice/apps/ten-question/`), :8891 chat-first (`alternatives/chat-first/`, with its separate sibling runtime), and :8896 previous guide. Their sources, stores and permissions are not abandoned or merged merely by choosing a primary development surface.
- **Actual implementation boundary:** :8893 imports 58 hash-pinned engine paths from `alternatives/chat-first/cms-slice/scripts/`; it is not a fully independent application directory. Startup enforces that lock in `alternatives/advisor-first/server.py:13`.
- **Latest evidence packets:** `audit-evidence/advisor-curriculum-20261102/`, `advisor-persona-coverage-20261102/`, `advisor-button-audit-20261102/`, `advisor-engagement-20261102/`, `comparison-milestone-20261102/`. Snapshot counts and activation statements must be read within each packet; older test totals are not cumulative coverage or a certification of the final merged build.
- **Current source reconciliation:** the newer L03 r12 packet exists, while the advisor README still calls the whole-offering work in progress. Defer the exact r12 disposition to the data workstream's latest retained receipts. Do not infer pilot closure from advisor tests or internal identity routing.

The most useful existing roadmap is `docs/planning/ARCHITECTURE_ALIGNMENT_AND_IMPLEMENTATION_2026-11-02.md`. It already names real architectural gaps and sixteen implementation steps, with owners/dependencies/exit evidence. Its sixteen practices, the user's new **15 company capabilities**, and **L01–L15 data layers** are three distinct maps. Cross-reference them instead of renaming one into another.

## Capability assessment

| Company component | Current maturity | Evidence-backed state | Material MVP gap / next closure |
| --- | --- | --- | --- |
| 1. User experience and education | Working local prototype; consumer validation open | Natural single-composer conversation, bounded answer buttons, source footnotes, contextual visuals, editable preparation output, responsive engineering evidence. Seventeen-concept visit learning record separates introduced/explored/unclear from comprehension. | Observe first-time Collier users, including correction, unknowns, pauses and return. Verify physical mobile keyboard, screen reader and cognitive usability. Run same-evidence interaction study; do not infer value from more conversation or a larger test count. |
| 2. Customer understanding and profile | Working local capture, partial semantic completeness | Forty-one conditional meanings, honest report provenance/state, person/time/entity scope, correction/invalidation, optional same-browser saving and sensitive-save choice. Offline persona coverage has independently authored expected profiles. | Thirteen extra detail paths remain held/unwritten; two legacy fields have no writer. Resolve a known safe-but-overrestrictive beneficiary-change case. Establish material-input confirmation immediately before an accepted personal action; legacy compatibility flags are not this receipt. Cross-device/family/staff access is not implemented. |
| 7. Coverage analysis and recommendation | Structural foundation; consumer purposes held | Deterministic conditions, compatible Decimal comparisons, baseline/keep/defer outcomes, profile/evidence revision bindings, missing-data neutrality. | Accepted coverage-path/timing/personal methods, exact source-purpose loader, real alternatives, complete relevant coverage universe, scenario costs, reviewed ranking/reasons and independent release. Current real consumer evaluated count is zero. |
| 8. Agentic conversation and execution | Working conversation/control loop; research execution partial | Interpret → validate/capture → compose; eligible question selection; practical return point during learning; scoped memory and correction; real prepared checklist. Internal research and explicit identity choices are connected separately. | The model gets capability/hold markers, not plan result tools. Integrate accepted checks/results as tools with source/method authority, action receipts, stale-result recovery and escalation. Measure sustained real-model behavior rather than only injected outputs and diagnostic continuations. |
| 9. Trade-offs and decision support | Teaching and structural mechanics; personal trade-offs held | Explicit priorities retained as an unordered set; no guessed weights; generic path teaching; pure scenario/constraint helpers exist. | Current case preparation emits empty declared constraints/scenarios, and hard constraints are unevaluated. Add explicit priority/constraint confirmation, same-basis scenario inputs, reversible what-if results and accepted personal explanation blocks. |
| 10. Trust and independence | Strong specification and useful enforced boundaries; full release proof open | Principles and I01–I10 contract, economic-field rejection, held purpose gates, source visibility, no invented action receipts; commercial canary tests pass in the comparator. | Full invariance across ingestion, retrieval, prompts/tools, caches, model/experiment selection, human overrides and outcomes. Durable minimized decision record, exact universe report and independent review. Specification is explicitly not certification. |
| 11. Human service and fulfillment | Preparation works; operations not established | Named-action preparation, editable checklist with copy/print, explicit statement that no one was contacted. Local counseling source work may support a future referral route. | Accountable staffed exception route, approved workflow/receiving service, minimal-context consent, queue/status/receipts, supported enrollment adapter and submitted/accepted/effective reconciliation. Resolve older mandatory-agent plan versus newer self-service target through the actual operating route. |
| 12. Ongoing customer relationship | Same-browser resume foundation; ongoing service not established | Optional seven-day guest profile, sensitive-save separation, explicit deletion, correction. Visit dialogue/learning is transient. | Purposeful persistent identity/permissions, cross-device recovery, family sharing, change detection, authorized follow-up, coverage-review tasks and accountable exception handling. No evidence of operated retention cohorts or recurring customer review service found. |
| 14. Distribution, partnerships and economics | Strategy and measures defined; operating evidence absent in inspected sources | First-transition independent researchers without a trusted agent are the latest starting audience. Trusted advisers/employers/community partners and free consumer access are hypotheses. Neutral-outcome economics is clearly required. | Select and measure one initial acquisition route, recruit a consented cohort, define actual partner roles, measure acquisition/support/AI/data costs and staff minutes across keep/defer/uncompensated outcomes. No measured CAC, cohort contribution or repeatable acquisition proof found. |
| 15. Quality and organizational learning | Strong technical regression practice; consumer/operating learning unproven | Rich dated audit packets, controlled persona oracles, negative/privacy tests, recovered model-failure traces, explicit evidence limits and cohort definitions. | Consolidated current-build evaluation manifest; held-out language/task set; sustained current-revision real-model tests; qualified factual review and consumer comprehension/control evidence; measured support/rework/outcome data. Test totals are not customer outcomes. |

## Implementation evidence and exact limits

### Conversation, teaching and profiles

`alternatives/advisor-first/natural_flow.py:57` constructs `NaturalConversation` over the pinned engine and creates owner-bound turn journals, state heads, chains, revocation tracking and visit memory. It captures reports before composing language and keeps comparison response data outside saved profiles. `natural_agent.py`, `natural_state.py` and `narrative_agent.py` supply the bounded interpretation/composition contracts and grounded report/state handling.

`alternatives/advisor-first/education.py:29` defines seventeen concepts. `education.py:78` explicitly exposes `delivery_is_not_comprehension: True`. Citation, teaching receipt and requested visual are distinct; merely citing a source or displaying a diagram cannot establish learning. This is an appropriate educational foundation, but the receipts are model/controller metadata, not independent proof of correct teaching or consumer retention.

`alternatives/advisor-first/advisor_memory.py:16` establishes v3 permission, six exchanges, a 5,000-character limit, one-hour TTL and 128-visit bound. It keeps dialogue and education in server RAM under owner/chain isolation. Expiry/restart loses that learning history. It is not the ongoing customer relationship in component 12.

The November 2 persona packet reports 30 scenarios and 2,164 executed assertions. Its original 78 paths comprise 71 captured, five derived and two legacy fields without a current writer. Fourteen added detail paths comprise one derived and thirteen held/unwritten; four current extensions comprise three captured and one derived. Every original meaning is traceable, but this is not every option, combination, person/time scope or language form. A current known limit is rejecting RC01 beneficiary change after goal and familiarity even when personal coverage facts are absent. That is a safe rejection, not a data leak, but remains a usability gap.

Current persona expectations are independently authored and compare exact final profiles, which is materially stronger than assertions that mirror the implementation. They still use scripted interpretations/compositions and cannot establish model extraction reliability.

### Personal comparison is deliberately unavailable

`alternatives/advisor-first/comparison_engine.py:489` builds the owner-bound response. Lines 515 onward explicitly exclude real research rows from consumer units; fictional alternatives are tests only. Lines 592–622 keep consumer purpose/output authority held, real evaluated count at zero, personal ordering null and personalized recommendation false.

`comparison_evidence.py:17` defines six separate purposes: published display, personal comparison, ranking, recommendation, quote and enrollment. `purpose_authorities` at line 146 grants none. The exact accepted L03 r4 lookup is a narrower reference path and does not remove these general holds.

`comparison_engine.py:319` retains priorities as an unordered set with `inferred_weights: None`; `hard_constraints_evaluated: False`. `comparison_case.py:91` emits empty declared constraints/scenarios. Pure helpers in `comparison_methods.py` are useful engineering, but they are not an accepted Medicare recommendation policy or a connected conversational what-if workflow.

`comparison_service.py:121` gives composition only public held-state codes, no extra personal profile values, source records or findings. Therefore the current AI does not carry out plan-result retrieval or use newly connected research rows to answer personal plan questions. This is the biggest gap between the current product and the user's narrative that it “does the research.” It is an intentional authority boundary, not simply a missing UI card.

`comparison_engine.py:580` states that the trace is owner-bound response data only and never persisted by the module. A hash-shaped decision reference is not a durable decision journal. Adding one requires purposeful fields/access/retention, not raw chat logging.

### Useful execution stops at preparation

`alternatives/advisor-first/advisor_flow.py:388` builds reported-information checklists with questions for employer/coverage/drug/provider follow-up, scope limitations and no-outside-contact statement. Preparation uses exact input digests and owner-bound expiring review tokens. `web/advisor.js:644` renders editable text, copy and print, warns when reports changed, and states “Nothing has been sent.” This is genuinely useful supported work; it is not referral fulfillment, benefit verification or enrollment.

`identity_journey.py:1` and `server.py:103` make the identity path internal-only under `--identity-research`. Explicit drug/provider-site selection is bound to current reports/source state, remains in RAM and grants no consumer source use, clinical coverage or model-context permission. It should be valued as an integration milestone without being described as a completed doctor/drug check.

### Trust requirements are partly enforced, not fully accepted

`PRINCIPLES.md` is a clear strategic invariant: commercial relationships must not affect inclusion, investigation, ranking, explanation or personal fit; keep/defer and uncompensated alternatives remain legitimate. `docs/product/INDEPENDENCE_ACCEPTANCE.md` explicitly labels I01–I10 “Specified, not implemented or certified.”

Current comparator tests reject commercial canaries and unreviewed extra keys, preserve source ordering and keep real research rows outside consumer units. These are meaningful safeguards. They cannot establish counterfactual independence of a real recommendation workflow that is not yet released, nor prove complete market coverage.

## Collaboration/cloud implications specific to the product

1. Keep :8893 as the explicitly named primary development target while retaining the protected variants. Do not describe it as the public production default or physically relocate it without a dependency/path migration plan.
2. Package the pinned shared engine as a reproducible dependency or retain its reviewed relative layout for the first clean clone. Moving only `advisor-first/` will break imports, hash checks and data/asset references.
3. Replace workstation launch configuration with parameterized deployment configuration before hosting. `server.py` currently loads root `.env`, enforces a local private `var` path, uses local SQLite profiles and a shared SQLite budget ledger, and imports research adapters with exact local target checks. The plist is operational evidence for one Mac, not portable deployment infrastructure.
4. Resolve process-local continuity before multiple replicas. Binding keys, state heads, journals, revocations, identity choices and learning live in memory. A generic load balancer over independent workers would not preserve current continuation guarantees. Either keep an explicitly bounded single-instance staging architecture initially or design reviewed shared ephemeral state/session routing. Do not make raw transcripts durable merely to solve deployment.
5. Multi-developer collaboration and multi-user customer service are separate. GitHub review/CI can start without a production identity system. Staff access, caregiver access and cross-device customer recovery need their own authorization/permission model; the existing cookie-owned guest store is not those systems.
6. Gate merged builds, not historical totals. The identity milestone packet notes concurrent frontend changes after its passing snapshot. A clean-checkout test command, pinned code/evidence manifest and one integration result are needed for team release confidence. Preserve earlier snapshots as evidence.

## Company identity source map and proposed organization

The user's new paragraph should become the current **company narrative**, reproduced exactly, while the sole approved visual tagline stays **Your coverage, plain as day**. It should not be silently pasted into the UI as a new slogan or mistaken for a claim that recommendations are already released.

> we’re building a self-service AI Medicare advisor that helps first-time enrollees understand Medicare and choose coverage through conversation. It meets people where they are, teaches what matters for their situation, and does the research so they can make an informed choice at their own pace.

Recommended `docs/company/` structure is a small canonical index and synthesis, with links to retained originals; do not duplicate full product contracts or move sealed artifacts:

| New company section | Existing sources to index | Authority/use |
| --- | --- | --- |
| Narrative and purpose | User's November 2 paragraph; `PRINCIPLES.md`; `PRODUCT.md` purpose; `docs/product/STRATEGIC_THESIS.md` | Exact current narrative, promise, audience and what remains a hypothesis. Preserve tagline separately. |
| Fifteen company capabilities | User's map; a current capability register with evidence/status/owner/next closure | Company operating map. Prefix C01–C15 or CAP-01–CAP-15; never reuse L01–L15 data layer identifiers. |
| Strategic thesis and audience | `docs/product/STRATEGIC_THESIS.md`; dated `STRATEGIC_THESIS_2026-10-30.md`; `docs/scale/GUIDE.md` | Undated thesis remains canonical strategy, dated copy historical. Depth/interaction hypotheses and consumer proof obligations. |
| Principles and independence | `PRINCIPLES.md`; `docs/product/INDEPENDENCE_ACCEPTANCE.md` | Binding invariant and release evidence, not marketing certification. |
| Brand/design | root `DESIGN.md`; `alternatives/advisor-first/DESIGN.md`; exact approved assets/provenance; `INTERACTION_CONTRACT.md` | Brand tokens/tagline plus variant-specific current interaction/visual authority. |
| Operating model and economics | Latest D73 thesis; `docs/planning/ARCHITECTURE_ALIGNMENT_AND_IMPLEMENTATION_2026-11-02.md`; older `docs/PRODUCT_WORKFLOW.md` and v1.2 architecture | Current target and unresolved qualified operating route; historical human-required assumptions flagged explicitly. |
| Product strategy and decisions | `PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md`, `docs/product/MASTER_DESIGN.md`, scoped AGENTS and current contracts | Preserve requirement IDs and explicit decisions. Company index does not supersede implementation contracts. |
| Evidence and quality | Thesis cohort definitions; `docs/RESEARCH_REVIEW_PROTOCOL.md`; current `audit-evidence/` | Separate technical evidence, model checks, qualified domain review and real consumer outcomes. Older protocol is a source for tasks, not a current 2026 release protocol. |
| Historical research and identity | `medicare-project-2026-10-17-v1.2/medicare-ai-landscape.md`, `medicare-ai-evidence-bank.md`, architecture package; `docs/Daylight Medicare, your Medicare journey.pdf`; vision guide; archived root proposals | Preserve original bytes/provenance; label date and superseded assumptions. Do not treat unnamed-company/caregiver-first/mandatory-agent prose as current identity. |

The original owner thesis attachment is described in the canonical strategy as Library ID `libfile_363b065cedd88191813a6fcdeabb68f4`, not a local verbatim source. The canonical strategy is an acknowledged synthesis. An index should say this instead of implying the original attachment is locally archived.

## Navigation conflicts and stale status findings

These are documentation/onboarding defects, not a request to rewrite sealed history:

- `docs/CURRENT_STATUS.md` calls itself a “current entrypoint” but is dated October 21. It describes :8766 static preview, the 70-record/2027 catalog and older runtime mismatch. Those facts are a historical snapshot, not the current :8893/2026 integrated state.
- Root `README.md` still leads with D66 :8890 and describes a step-by-step guide with supporting chat. It understates the active D86 advisor work.
- `docs/product/STRATEGIC_THESIS.md`'s current implementation map stops at :8890/:8891. Retain its strategy, but current runtime routing should link to a maintained map that includes :8893.
- Root `DESIGN.md` describes a two-column growing guide, repeated Continue and fixed phase labels. Scoped :8893 instructions explicitly override those with the accepted single-composer shell, current-focus labels, contextual inline visuals and newer reveal behavior. New contributors need this distinction early.
- `PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md` and `MASTER_DESIGN.md` prepend many latest amendments but retain earlier “latest/current” statements below. A dated active authority index is safer than requiring every contributor to infer chronology from 600-line documents.
- `docs/PRODUCT_WORKFLOW.md` still says caregiver-first acquisition and mandatory licensed-agent purchase with a complete transcript handoff. Latest D73 focuses first-transition independent researchers, minimal routine human involvement and minimized permissioned records. These claims must be labeled as historical; actual human requirements remain a route-specific operating decision, not something to infer either way.
- `docs/RESEARCH_REVIEW_PROTOCOL.md` and older MVP plans refer to 2027, 70 records and a future AI stage that is now locally implemented. Reuse the review method, not those old current-state claims.
- `alternatives/advisor-first/README.md` has a current v3 top amendment but its bottom summary still says raw history is not attached; v3 actually permits bounded visit dialogue in RAM. Its source table also calls one identity choice seam “not routed” while newer internal routing exists. Scoped context distinctions are explainable, but wording should be clarified to avoid false privacy/integration assumptions.

## Collier MVP sequencing

Maintain separate milestones; none waives the full frozen data obligations:

1. **Team-ready internal build.** Clean clone, one current map, exact source/evidence dependency manifests, environment setup, synthetic tests, CI and documented review ownership. This can precede consumer release and should be the near-term organizational outcome.
2. **Scoped education/preparation study.** Specify audience/year, supported tasks, privacy and study ownership. Observe real participants using the education/correction/preparation path without representing samples or internal research as recommendations. This gives component 1/2/8/15 evidence while evidence work continues.
3. **Accepted personal comparison milestone.** Complete the current whole-offering pilot and its independent review; implement the relevant source-purpose/method gates, decision-input confirmation, exact benefit/drug/provider/price/rule integrations, minimized decision journal and reviewed explanations. One offering is a vertical integration proof, not a comprehensive Collier recommendation universe.
4. **Collier choice MVP.** Declare exact year/geography/categories/universe and actual exclusions. Cover Original Medicare plus relevant Medigap/Part D and MA paths fairly, with current coverage/keep/defer. Release only accepted capabilities; demonstrate independently reviewed decisions, correction, understandable trade-offs and no economic influence.
5. **Supported fulfillment and continuing service.** Establish the approved operator/platform route, permissions and transaction/exception receipts before claiming enrollment or ongoing review. Measure actual support cost and retained value across neutral outcomes.

Consumer research and engineering should run in parallel with source work. Do not wait for the entire national ambition to observe whether current teaching is useful, and do not redefine the full L03 commitment as an MVP exemption. A 2026 internal research milestone also does not determine the correct launch coverage year; that choice must be explicit.

## Checks performed in this review

Read `PRINCIPLES.md` first, current strategy/product/requirements/master/design and scoped :8893 instructions. Inspected actual conversation, profile, memory, comparison, identity, server and frontend preparation code plus dated audit packets. Did not access real guest records, spend model credits, create an enrollment/communication, change the UI or restart services.

Fresh offline checks against the present workspace:

| Existing test module | Result | What it supports |
| --- | --- | --- |
| `test_persona_journeys.py` | 7 tests passed, 15.278 seconds | Current controller replay against independent retained-persona expectations, exact profile oracle, isolation and network-forbidden transport. |
| `test_comparison_engine.py` | 22 tests passed, 0.561 seconds | Held real purposes, all-meaning/gap accounting, missing-data semantics, fixture isolation, commercial-key rejection and revision binding. |
| `test_advisor_memory.py` | 12 tests passed, 0.002 seconds | Owner/chain isolation, v3 scope, TTL and bounded memory. |
| `test_education.py` | 33 tests passed, 0.007 seconds | Teaching receipt/citation/visual separation, no comprehension claim, revisits and permission/lifecycle boundaries. |

Total fresh targeted tests: **74 passed**. This is not a full-suite rerun, live runtime certification, consumer validation or an independent Medicare recommendation review. The latest retained curriculum packet reports 712 full-suite tests and controlled responsive checks; those are cited as dated evidence, not rerun results. This review found no recorded real consumer comprehension cohort, operated enrollment service, realized contribution cohort or retention outcome in the inspected current sources. That is an evidence finding within this inspection, not a claim to have audited every private company record.
