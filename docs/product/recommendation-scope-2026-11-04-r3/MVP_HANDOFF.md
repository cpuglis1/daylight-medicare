# From the successful experiment to a useful Daylight MVP

November 4, 2026 · D91 revision 3 · Handoff for the implementation chat

**Recommendation: build one small, user-facing educational comparison in the existing :8893 advisor.** A person should understand two or three actual plans, explore the three supported cost components, and see the checks that still matter. The internal research view can help verify implementation, but it is not the user milestone. Do not resume exhaustive whole-plan reconciliation as the delivery path.

This is a delivery plan, not a consumer release receipt. The owner requested this handoff after the successful experiment. No runtime, source acceptance, saved profiles or historical research status changes with this document. The next chat should check its current implementation authorization before treating this planning document as an instruction to deploy or release.

## 1. What the experiment establishes

Read [RESULT.md](../recommendation-scope-2026-11-04-r2/experiment/RESULT.md) and [COMPARISON.md](../recommendation-scope-2026-11-04-r2/experiment/COMPARISON.md) first. The producer reports approximately nine minutes for the bounded experiment. It produced five numeric cells and one explicit hold across two plans:

- Both plans: $0 monthly base plan premium, $0 for twelve months, and $0 for four ordinary covered in-network PCP visits.
- Humana H1036-217-000: $540 for three counted inpatient days; $720 for four, under the stated conditions.
- Erickson H5652-002-000: hospital arithmetic held because the applicable annual deductible balance is unspecified.
- Specialist ranges and coinsurance without a charge base did not become exact dollar amounts.

This demonstrates a practical structured-source plus targeted-check workflow. It does **not** establish general support for arbitrary hospitals, lengths of stay, plan years, eligibility, drug costs or personal annual spending. The runner currently supports the fixed fictional case and three/four-day correction. Its technical checks are not independent interpretation review.

Two product implications matter immediately:

1. **The engineering pair is not a consumer shortlist.** Erickson has a published residence requirement and no drug coverage. Retain it as a valuable restriction/deductible regression case. For an ordinary MA-PD pilot, select comparable offerings through the existing scoped catalog and a documented neutral rule, or let the user select them. Do not imply that these two test plans are the best available choices.
2. **Keep 2026 explicit.** A 2026 comparison can support a clearly labeled 2026 usability/education pilot. It cannot answer a request to choose 2027 coverage. Ask the intended year when absent; route an unsupported year to education and an explicit data gap. If the intended launch task is 2027 shopping, an equivalent 2027 source intake is a prerequisite for that task. Do not silently change the fixed 2026 scope.

## 2. The first user milestone

From the existing chat, a user can open a real, clearly scoped comparison, understand the important differences, change a simple scenario, inspect its source and correct their inputs. No second questionnaire and no requirement to complete all 41 meanings.

The comparison should answer:

1. What kind of coverage are these plans, and are there important entry restrictions?
2. What is the plan premium, and what other costs can still apply?
3. What do an ordinary visit and the supported hospital example illustrate?
4. What is known and unknown about my doctors, medicines and stated needs?
5. What should I check next before making a decision?

This is useful without declaring a winner. The chat may explain factual tradeoffs and how a stated priority relates to a dimension. A claim that a particular plan fits this person better still requires the separate recommendation evidence and method acceptance. Do not build a weighted score or total-cost prediction merely to make the MVP feel personalized.

### Minimum information in a comparison

These are required **rows or statuses**, not a demand to resolve every field for every plan before anything can be shown. Missing material facts hold dependent conclusions, not unrelated supported rows.

| Information | Minimum useful presentation |
| --- | --- |
| Scope and identity | Coverage year, county, full offering identity, plan name/type, limited catalog scope and how displayed plans were selected. No all-market claim. |
| Coverage and restrictions | Whether prescription coverage is included; applicable special eligibility/residence restrictions; network type and consequential referral/authorization qualifications. Unknown eligibility is not confirmed availability to this user. |
| Recurring cost | Base monthly plan premium and clearly labeled multiplication by selected months. Separate federal premiums, optional packages and other spending; do not add them without supported inputs. |
| Financial exposure | Published medical deductible and medical out-of-pocket maximum with network/period scope; drug deductible when applicable and supported. Explain that the displayed medical maximum does not describe every possible expense. Unknowns stay visible. |
| Common care | PCP and specialist published terms, plus inpatient charging schedule and relevant deductible conditions. A readable range or percentage is useful even when arithmetic is unavailable. |
| Three scenarios | Plan-premium arithmetic; an ordinary covered in-network visit count; one bounded acute facility admission. Each shows included costs, assumptions, exclusions and a number or specific hold reason. No combined annual-spending total. |
| Personal checks | Doctor/site network status and medicine coverage/cost status, plus any stated must-have. Identity resolution and user reports remain distinct from verified coverage. “Not checked” must be prominent when it could change the decision. |
| Explanation and evidence | A short explanation of consequential differences, source/year/date access, and a concrete next check. Show conditions beside affected amounts; do not bury them in a generic disclaimer. |

The compact view can group these into identity, money, care and remaining checks, with detail expandable. Preserve the current design. Dental/hearing/vision, every procedure frequency, comprehensive drug pricing, star-based ranking and full annual forecasting are not required for this first milestone. If a user raises one of these as important, show its unresolved status and investigate that specific need before making a dependent fit claim.

For browsing, reuse location/year and the requested coverage category. For personal relevance, reuse the existing profile and ask only missing consequential questions. Preserve fair coverage-path education and current-coverage/keep/defer outcomes; an MA-only comparison does not choose the best Medicare coverage path.

## 3. Execute in this order

### A. Review the small existing result, then freeze its usable scope

Start with the six result cells and their shared material conditions, not the full plans. Reuse exact applicable prior reviews. An independent reviewer should inspect the bound source passages and arithmetic, including units, charging days, deductible application, medical spending-limit assumptions, no-Rx/residence restrictions and any material state variation or amendment. Rerunning the producer's checks is useful but is not that independent review.

Produce one compact review record: exact source/method versions, reviewed claims, corrections, unresolved conditions, reviewer identity and the proposed purpose. A remaining unknown holds the affected output. Do not open unrelated dental or HPMS work. Prepare the exact reviewable release candidate before requesting any required acceptance; do not repeatedly ask permission for ordinary local implementation.

The default first work block is **30 elapsed minutes**, ending sooner if complete. If the review cannot finish, record the precise unresolved claim and the narrower usable result; do not automatically extend it into a new research project. This is a work limit, not a promise that independent review will pass in 30 minutes.

### B. Build one complete path through the current app

Use the reviewed experimental scope for integration behind an internal preview boundary. Add only what is needed to prove: existing chat/profile → server comparison → understandable display → scenario edit → correct refreshed result.

- Reuse the current profile adapter and source/version bindings. Keep fictional scenario assumptions separate from reported beneficiary facts. Do not assume actual authorization, eligibility, deductible satisfaction or network participation because a scenario uses those assumptions.
- Start with the already supported three/four-day hospital example. Display the exact meaning of counted days; do not treat a vague “three-day stay” or discharge date as an executable billing rule. Reject other scenarios until their method is supported.
- Wire the result into the existing advisor's comparison presentation. A research-view preview is acceptable as an intermediate check, but stop calling that the completed MVP.
- Let the existing conversation explain only server-supported result fields and holds. It must not infer a winner, complete missing prices or turn an internal research amount into an approved personal finding.

Deliver a working local preview and a short execution note. Keep consumer access gated while review or purpose acceptance is outstanding. Do not block all reversible integration work on a release decision.

### C. Make the preview useful for an ordinary pilot user

Reuse Humana if its selected claims pass review. Add one comparable, appropriately scoped offering using the same extraction and methods; keep Erickson in tests. Show the minimum rows above. User-selected plans or a disclosed neutral selection rule are required; source convenience, missing fields and commercial arrangements cannot masquerade as fit.

The first release can cover two or three clearly identified plans. State that limited scope and keep other retained options discoverable at their supported display level or explicitly listed as outside this comparison release. Do not imply that unsupported plans are unavailable, inferior or excluded from the market. Broad 72-offering calculation coverage is later work, not the condition for this small pilot.

Review the reusable field families and selected consequential exceptions. Do not create a full-plan reconciliation queue for the added plan. If one hospital method does not apply, keep the published terms and a hold; useful premium and visit comparisons can still work.

### D. Prepare the exact pilot release and observe actual use

Assemble one small release manifest covering the exact offerings, displayed fields, methods, source versions, assumptions, known holds and intended consumer purposes. Obtain the applicable independent review and exact-purpose acceptance. Internal research-purpose acceptance alone does not authorize a consumer display or scenario. Do not infer acceptance from this handoff, a test count or a blanket `consumer_usable = true` flag.

After acceptance, the cheapest initial user test is a founder-facilitated session on the local app with a few volunteers using fictional or voluntarily supplied minimal information. No cloud migration is needed for that. Do not contact testers without the owner's instruction. Remote self-service access is a separate delivery step: prepare the concrete hosting, access/privacy, operating-cost and rollback proposal before provisioning or public deployment. Reuse existing permission and budget policies.

Observe whether people can explain premium versus scenario cost, notice unverified doctors/medicines, understand a hold and change an input. Do not add a mandatory quiz. Record actual task success, confusion and founder assistance. This is the first product-quality evidence; the nine-minute result is engineering evidence.

## 4. Implementation guidance: use what exists

Read these targeted entrypoints rather than all historical work:

- [Root instructions](../../../AGENTS.md), [principles](../../../PRINCIPLES.md) and [advisor instructions](../../../alternatives/advisor-first/AGENTS.md).
- [Current product](../../../PRODUCT.md), [requirements](../../../DAYLIGHT_REQUIREMENTS.md), [design](../../../DESIGN.md), [master design](../MASTER_DESIGN.md) and the [D73 change checklist](../STRATEGIC_THESIS.md#ui-and-system-change-review-checklist) before app changes. Latest explicit D91 scope overrides older whole-L03 critical-path language; it does not erase those inventories.
- [All-41 capability mapping](../recommendation-scope-2026-11-04-r1/question-capability-map.json), [profile mapping](../plan-comparison-2026-11-01/PROFILE_MAPPING.md), and current [interaction contract](../../../alternatives/advisor-first/INTERACTION_CONTRACT.md).
- Experiment [runner](../recommendation-scope-2026-11-04-r2/experiment/run.py), [evidence](../recommendation-scope-2026-11-04-r2/experiment/evidence.json), [fictional input](../recommendation-scope-2026-11-04-r2/experiment/fictional-profile.json), [JSON output](../recommendation-scope-2026-11-04-r2/experiment/comparison.json) and [MPF intake](../../data/mpf-benefit-summary-2026-11-04-r1/README.md).

| Existing seam | Next use |
| --- | --- |
| [comparison_profile.py](../../../alternatives/advisor-first/comparison_profile.py), [comparison_case.py](../../../alternatives/advisor-first/comparison_case.py) | Reuse resolved reports, beneficiary/item identity, meaningful unknown states and input revisions. |
| [comparison_service.py](../../../alternatives/advisor-first/comparison_service.py) | Coordinate server-owned comparison outputs and invalidate changed inputs/source bindings. Preserve current stale-response behavior. |
| [comparison_evidence.py](../../../alternatives/advisor-first/comparison_evidence.py) | Currently supports held/fictional snapshots only; there is no real consumer release loader. Implement an additive, narrowly scoped accepted-release path when needed, preserving held defaults and purpose separation. This is real remaining engineering, not just a UI toggle. |
| [comparison_methods.py](../../../alternatives/advisor-first/comparison_methods.py), experiment runner | Reuse deterministic arithmetic and typed units. Extract only the methods needed; do not grow a universal benefit-rule engine. |
| [web/comparison-view.js](../../../alternatives/advisor-first/web/comparison-view.js) | Extend the existing presentation for understandable facts, components, assumptions, corrections and holds; preserve chat and current design. |
| [research_http.py](../../../alternatives/advisor-first/research_http.py), [web/research.js](../../../alternatives/advisor-first/web/research.js) | Optional internal preview using existing access boundaries. Research authority must never leak into consumer/model authority. |

For fast display, serve a compact versioned bundle of approved facts through the existing backend, loaded once or cached by release/version. A small JSON serving artifact is sufficient for the first slice; retain PostgreSQL and evidence as the source system. No new database, ORM migration, vector store or cloud service is required just to render this comparison. Do not parse workbooks, scan the archive or call an LLM per displayed cell during a user request.

Keep browser inputs to allowed offering IDs and bounded scenario values. Resolve facts, authority, source IDs and arithmetic on the server. Do not deserialize a browser-supplied evidence/approval object. Render published text as text, not executable workbook HTML. Public source links must not expose private filesystem paths or unrestricted evidence files.

The existing two-stage AI architecture, grounded composition, deliberate-send permissions, separate saving, visit-only raw chat, shared budget and owner-bound state remain. No extra paid model stage, automatic retry or wholesale research dump into context. Preserve protected :8890/:8891 variants and their guest stores.

## 5. Verify the risks that matter

Use focused tests and one rendered end-to-end journey. Do not generate hundreds of tests that merely repeat constants.

- Replay the existing source/calculation check; preserve the five numeric cells, named deductible hold, range/percentage refusals and $540 → $720 correction.
- Verify supported hospital boundaries and rejection of unsupported days/settings; no invented deductible balance, charge base or total cost.
- Reject mismatched year/county/offering and stale source releases. A changed profile/scenario invalidates dependent findings; one user's result cannot appear for another.
- A browser/model flag cannot grant source acceptance or recommendation authority. Unknown coverage and special eligibility restrictions remain visible.
- Provider identity is not network confirmation; medicine identity is not formulary/cost confirmation. All-unknown reports cannot produce a recommendation.
- Keep incomplete/uncompensated alternatives visible at the truthful supported scope. Commercial fields cannot affect order, inclusion or explanation; apply the [independence acceptance contract](../INDEPENDENCE_ACCEPTANCE.md) before any recommendation release.
- Check desktop, tablet and phone rendering, source/condition access, scenario correction and returning to chat. Exercise realistic AI wording so it cannot call a component “your total cost” or make an unsupported fit claim.

Do not repeat the entire historical source audit. Run the existing tests appropriate to modified seams; broaden only for affected behavior, failures or unresolved concerns.

## 6. Keep the work bounded and reusable

The nine-minute result replaces speculation with evidence for this narrow workflow. It does not justify either the old 90–180-hour MVP estimate or “nine minutes times 72 plans.” Do not publish another large forecast before measuring integration.

After the first 30-minute review block, use short implementation checkpoints, ordinarily 30 minutes each. At each checkpoint report: working artifact, checks performed, time spent, exact remaining issue and smallest next change. A checkpoint is a progress boundary, not a guarantee of completion; do not silently expand a blocked source investigation. Stop when the requested slice is done rather than using the full allowance.

For subsequent plans: batch exact-identity extraction → apply supported family rules → check units and conditions → reuse applicable reviewed interpretations → queue only exceptions. Retain readable terms where no formula applies. Cache accepted interpretations by source/version and scope; invalidate affected claims when the source changes. Review new parser/method families and consequential exceptions, not every plan's entire EOC on every request. A known conflict still holds its affected output.

Measure onboarding effort separately from per-user runtime. Once a source fact and method are approved, ordinary comparison requests should reuse them. On-demand lookup is for a missing decision-relevant detail, with a visible pending state; it must not make the main result wait for an open-ended investigation.

### Definition of done for the first user pilot

An accepted, limited 2026 comparison is reachable from the actual advisor; two or three neutrally selected or user-selected real plans have the minimum information/statuses; supported scenarios recompute correctly; material unknowns and restrictions are understandable; sources and correction controls work; privacy and independence boundaries survive; and observed user sessions identify what users understood and where they needed help. Hosting and broader recommendation coverage have explicit separate status.

The 392,570 r9 research obligations, 4,675 first-plan obligations, accepted 535-entry r4 reference and 16 original named gaps remain preserved with their existing status. They are not this pilot's completion checklist. No global acceptance or completion credit is granted.

## Start prompt for the other chat

> Read this handoff and the linked experiment result. First, report what has already been implemented in this checkout so you do not duplicate concurrent work. If implementation is authorized in this chat, begin with step A: a bounded review of the six experimental cells and their material conditions. Reuse applicable existing reviews, preserve the frozen research work, and prepare the exact next comparison slice in :8893. Keep the destination a usable educational comparison in the current advisor. Do not restart whole-plan reconciliation, add a questionnaire, promise a total-cost ranking, provision cloud resources or release unaccepted data. Report concrete artifacts and actual elapsed time at each checkpoint.
