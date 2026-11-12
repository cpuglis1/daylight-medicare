# Daylight strategic thesis and evidence roadmap

Owner direction · October 25, 2026 · D73. **Canonical strategy, not a second flow specification or implementation approval.** Read [PRINCIPLES](../../PRINCIPLES.md) first. [PRODUCT](../../PRODUCT.md), [owner requirements](../../DAYLIGHT_REQUIREMENTS.md), [MASTER_DESIGN](MASTER_DESIGN.md) and the applicable surface contract govern implementation. This strategy extends D64's independence requirements and preserves existing source, privacy, recommendation and release gates.

## Source and status

This is a paraphrased synthesis of the owner's October 25 attachment, **Pasted text(1).txt**, Library ID `libfile_363b065cedd88191813a6fcdeabb68f4`, and the instruction to incorporate its thesis into future UI and system work. It is not a verbatim archival copy. The attachment is strategic source material, not evidence of shipped capabilities, legal conclusions, competitor behavior or achieved outcomes. No external references were checked for this documentation change.

Distinguish four things in every proposal and completion report: binding principles; hypotheses to test; current implementation with dated evidence; and a gated next milestone or later roadmap. A strategic ambition cannot promote data, release recommendations or authorize implementation by itself. Older execution plans remain useful within their scope and yield to current owner requirements and this strategy on strategic direction.

## Thesis and first audience

Build a **free, directly used Medicare decision platform**, funded through a licensed brokerage and distributed through trusted partners. The intended relationship spans initial exploration, comparison and, when authorized and operationally supported, enrollment; automated coverage reviews then help maintain a continuing relationship. The proposition to prove is that consumers can make informed decisions with less staff involvement while retaining control, inspecting recommendations and receiving sound support. Economics must work without degrading recommendation quality.

The initial audience is first-time Medicare decision makers researching independently, sometimes with a spouse or adult child. Existing members and caregivers remain supported audiences; this focus does not discard either local variant or useful existing paths. Evaluate Original Medicare, optional Medigap and separate Part D, and Medicare Advantage comprehensively. **Understand and compare coverage paths before selecting individual policies.** A low premium or a single preference cannot settle that choice.

The differentiation to demonstrate is useful work people can complete themselves and understanding they can retain: gathering consequential facts, exploring tradeoffs, preparing a decision and completing supported actions. Chat, AI branding and assertions of being unbiased are insufficient evidence. Keep the accepted landing, sun/name, sole tagline **Your coverage, plain as day**, visual teaching and simple adaptive conversation; this thesis is not replacement landing copy or permission to redesign navigation.

## Binding product and system commitments

1. **Let people ask questions before extensive personal intake.** Build and correct the profile progressively. Ask a fact because it can change the requested check, comparison or next action, and explain why. More data is not automatically better. Reuse confirmed reports, distinguish explicit none from unknown/deferred, and do not turn the alternative's question inventory into a mandatory interview.
2. **Make tradeoffs revisable and understandable.** Compare costs, provider access, restrictions and future flexibility on consistent evidence and assumptions. Let people change priorities, revisit comparisons, correct facts, challenge a conclusion and inspect its supporting evidence. Preserve current coverage as a baseline. Retaining coverage or deferring with an explicit unresolved check can be a valid outcome.
3. **Make independence testable.** Full-market coverage is an ambition; actual geography, year, categories, included records, exclusions, source dates, assumptions and uncertainty must be disclosed. Include nonrevenue options without penalties. Commissions, sponsorship and partner preferences cannot enter ingestion selection, eligibility, ranking, explanation or the AI context. Apply [I01–I10](INDEPENDENCE_ACCEPTANCE.md), including economics counterfactuals and missing-data neutrality; disclosure alone does not establish independence.
4. **Keep an inspectable decision record.** Before releasing recommendations, preserve the minimized, permissioned inputs and evidence/version identifiers, candidate universe, exclusions, rationale and unresolved checks needed to reproduce and challenge them. Provide independent quality review. Audit human overrides with actor, before/after decision, evidence, reason and review outcome; an override cannot bypass required evidence or quietly favor commercial fulfillment. A saved explanation does not authorize retaining raw health chat or every sensitive fact.
5. **Keep control and permission specific.** Save/resume must reflect actual storage receipts and retention policy. Family participation requires appropriate permission and scoped sharing; a caregiver label is not sharing authority. Saving, AI transfer, family sharing and human handoff are separate choices. Do not promise household accounts or cross-device sharing from a same-browser guest profile.
6. **Use automation where it is reliable.** Automate information gathering, comparison, explanation and preparation only within reviewed rules and verified tool capabilities. Licensed professionals handle required involvement and exceptions through an actually supported service. Offer human help when useful without withholding otherwise supported self-service research or requiring a sales call. Legal/operational requirements need separate review; this is not a finding about which activities require a license.
7. **Make economics fit neutral decisions.** Test commercial viability across the recommendation mix, including no-commission choices, keeping coverage and deferral. Revenue and support analysis stays outside recommendation features, prompts, model selection, training objectives and evaluation labels. Poor economics calls for operational or business-model changes, not steering toward a paying carrier or suppressing an option.

## Current implementation and protected variants

This is a documentation snapshot based on existing local contracts, not a fresh runtime certification. The original app at **:8890** lives in `/Users/cep4u/daylight`, with the ten-question frontend in `cms-slice/apps/ten-question/`. [The ten-question contract](TEN_QUESTION_CONTRACT.md) and [conversational readiness contract](READINESS_CONVERSATION.md) record the accepted sequence, editable summary and optional conversation/sample boundary. The preserved `apps/chat` previous guide on :8896 is distinct from the :8891 alternative.

The **:8891 alternative** has editable source at [/Users/cep4u/daylight/alternatives/chat-first](/Users/cep4u/daylight/alternatives/chat-first) and its preserved separate runtime at `/Users/cep4u/daylight-chat-alternative-runtime`. D75 brought the canonical source into this repository without merging either UI or moving data; see [source/update/rollback instructions](../../alternatives/chat-first/README.md). The old Documents source remains a noncanonical fallback. Its [customer-profile readiness contract](/Users/cep4u/daylight/alternatives/chat-first/docs/product/CUSTOMER_PROFILE_READINESS.md) and [question map](/Users/cep4u/daylight/alternatives/chat-first/docs/product/CUSTOMER_PROFILE_QUESTION_MAP.md) describe 38 primary plus 3 explicit child questions, with overlapping clarification variants. That inventory is conditional capability preparation, not a fixed required question count. Neither variant is abandoned. A small alternative agent pointer references this canonical strategy; it does not synchronize code, profiles or runtime files.

Existing documentation records local AI, permissioned same-browser guest saving, reported-input preparation and a labeled five-record sample subset. Those records do **not** establish a complete market, a validated recommendation engine, exact provider/drug coverage, personalized pricing, Medigap quotes, enrollment or ongoing review operations. Existing acceptance holds and source-review limitations remain. Preserve both variants' guest records, existing consent and shared aggregate budget controls; no strategy edit migrates data or changes a service.

### Customer completeness and external verification are independent gates

| Boundary | Required meaning | What cannot satisfy it |
| --- | --- | --- |
| Reported inputs for a requested capability | Relevant consequential facts are present, confirmed as reports and current; missing, tentative, unknown and deferred stay explicit. Optional preferences are not universal requirements. | Finishing ten screens, a zero queue/count, all-unknown answers, an AI assertion or a client completion flag. |
| External evidence and release acceptance | Exact source/entity/year/location, policy review, coverage scope, network/formulary/pricing and comparison acceptance required by that capability. | A complete customer profile, a name match, a captured dataset, research references or a staff override without required evidence. |
| Sample browsing | Explicit, honestly labeled exploration with scope and limitations. It can remain available without complete personal intake. | Personal fit, ranking, a verified price or authorization to enroll. |

**Ten unknown answers cannot earn a personalized recommendation. Complete reported inputs cannot remove an external hold. A missing external source is not another intake question. Sample browsing is not a recommendation.** Readiness is specific to the requested capability, not a global badge. Changed facts or evidence invalidate affected results while preserving the person's prior reports for review under the existing privacy policy.

## Roadmap: proof before expansion

These are strategic stages and dependencies, not a new approved implementation schedule. No numeric targets or achieved results are asserted.

| Stage | Work and evidence | Gate / limit |
| --- | --- | --- |
| Current prototype | Preserve both local variants, accepted teaching/chat, editable reports, guest privacy and labeled samples. State unresolved personal pricing, matching and market-data gaps. | Technical checks and documented intent are not consumer, legal or data acceptance. |
| Next milestone: scoped consumer proof | Define a first-time-user cohort, requested capabilities, market/year, comparison baseline and acquisition channel. Close and independently accept the exact data/policy/capability gaps needed for that scope; then observe informed decisions, correction/control and staff effort. Exercise economic independence across compensated, uncompensated, keep and defer outcomes. | While external gates remain held, limit work to education, input preparation and labeled samples. Any actual recommendation or enrollment requires its own evidence, authorization and qualified operations. |
| Repeatable acquisition and licensed fulfillment | Test referrals and trusted retirement advisers, employers, benefits platforms and community partners. The partner introduces the member; Daylight maintains the permissioned profile and continuing relationship. Measure completion, support burden and contribution by cohort/channel. | Partner attribution/preferences do not influence recommendations. Brokerage, human escalation and enrollment promises require actual reviewed capability and permission. |
| Continuing coverage reviews | Initially reuse proven profile/evidence infrastructure for coverage changes, medication updates, deadlines and routine notices. Make each check's source date, permission and remaining work visible. | Reliable data refresh, authorized outreach, privacy/retention and exception ownership must exist before promising automation. No recurring task is created here. |
| Later expansion | Add labor-intensive advocacy only after funding and service costs are established. Consider selective government deployments after consumer proof. | Do not divert the first milestone into broad government sales or an unfunded advocacy commitment. |

Defensibility should accumulate in versioned coverage/eligibility evidence, verified provider and drug identities/coverage, reproducible comparisons, permissioned history, reliable integrations/distribution, quality evidence and efficient exception handling. An LLM interface alone does not create that asset. Evidence retention remains purposeful and access-controlled rather than a reason to collect everything.

## Evidence definitions for the first cohort

Before measurement, record cohort eligibility, scope/year, channel, observation window, denominator, baseline/comparator, policy/model/data versions, reviewer and missing observations. Use appropriate permission and minimized records; no private transcript collection is implied. Report exclusions, failures and uncertainty alongside rates. Set decision thresholds explicitly when designing the study; this document invents no targets, traction or results.

| Measure | Evidence definition |
| --- | --- |
| Accuracy and independence | Independently adjudicated material claims/decisions against exact scoped source evidence; report reviewed count, errors by severity, unresolved claims and corrections. Include I01–I10 results and override audit. Do not count unreviewed statements as accurate. |
| Comprehension and control | Observed ability to explain the chosen coverage path and key tradeoffs/uncertainty, inspect a reason and correct an input. Record task rubric, observer, eligible/observed counts and failures; stated confidence or chat satisfaction alone is insufficient. Observation does not impose a new consumer quiz gate. |
| Enrollment completion | Where enrollment is separately authorized and supported, distinguish preference, application started/submitted, accepted and effective coverage with actual receipts/status. Report denominators and pending/failed outcomes. Keeping/deferring is separately classified, not mislabeled as failed enrollment. |
| Staff minutes per outcome | Measured licensed and nonlicensed time for preparation, escalation, support, exceptions and rework, including unsuccessful cases. Report distributions and comparable baseline for the same scope; automated reply counts are not labor savings. |
| Contribution after acquisition and support | Realized revenue with relevant reversals, less attributable acquisition, AI/data, fulfillment, staff and ongoing support costs for the cohort/window. Report neutral outcome mix and allocation assumptions, including zero-revenue outcomes; do not substitute gross commissions or forecast LTV for measured contribution. |
| Retention and continuing value | Among members eligible for follow-up with permission, measure return/use and completed supported reviews over a stated window, plus unresolved work and support cost. An undeleted saved profile does not establish retention. |
| Repeatable acquisition | Record channel/referral source, eligible arrivals, informed-decision outcomes and acquisition effort/cost across repeated cohorts. State selection bias and limits; one favorable demonstration does not establish repeatability. |

Seed evidence means a cohort demonstrating informed decisions with lower staff minutes through a repeatable acquisition route, supported by accuracy, comprehension, completion, contribution and retention evidence. This remains a hypothesis to test, not a financing or performance claim.

## UI and system change review checklist

Every future UI/system proposal and completion report must address the applicable items, name requirement IDs (including D73 where relevant), and give evidence or an explicit unresolved status. A small change can say why an item is unaffected; it cannot silently weaken the boundary.

- [ ] **Consumer task:** What useful work or understanding improves for the initial audience? Does the change preserve the accepted landing, teaching, simple adaptive chat, correction and return paths?
- [ ] **Consequential intake:** Why can each requested fact change this capability's result? Can the person ask/learn/browse before extensive intake? Are optional, none, unknown/deferred and repeated reports handled distinctly without a second mandatory questionnaire?
- [ ] **Coverage path and tradeoffs:** Are Original/Medigap/Part D and Advantage represented fairly before policy selection, with costs, access, restrictions, future flexibility and a current-coverage/keep baseline where relevant?
- [ ] **Two gates and honest scope:** Which reported inputs suffice, and which independent source/release holds remain? Do all-unknown, stale and incomplete cases fail closed for personal recommendations while explicit sample browsing stays accurately labeled?
- [ ] **Independence and challenge:** Could any commercial/partner input change inclusion, ordering, explanation or next research work? Where are source dates, exclusions, assumptions, reproducible reasons, user challenge/correction and independent/override review evidenced?
- [ ] **Permission and control:** What is saved, transferred to AI, shared with family or handed to a human; under which separate permission, access and retention policy? Does the implementation preserve both variants' actual guest data and privacy/budget controls?
- [ ] **Actual capability:** What did the tool/service really execute? Distinguish reported from verified, prepared from sent, sample from recommendation, submitted from accepted/effective coverage. Keep required licensed help and unsupported operations explicit.
- [ ] **Proof and stage:** Which cohort measure or prerequisite improves? Identify current evidence, limits and next milestone; assess economics outside decision logic across neutral outcomes. Do not claim comprehension, savings, complete coverage or readiness from documentation or test totals alone.

## Owner-supplied reference links

Preserved as references supplied with the thesis, **not freshly verified sources or adopted legal/competitive findings**. Recheck the relevant primary source and obtain required domain review before using a claim in consumer advice, rules or marketing. Competitor marketing does not prove internal product behavior or independence.

- [Medicare.gov: ready to buy Medigap](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy)
- [Chapter: comparison with other Medicare agents](https://askchapter.org/magazine/chapter-and-you/medicare-resources/chapter-vs-other-medicare-agents)
- [CMS: agent/broker compensation](https://www.cms.gov/medicare/health-drug-plans/managed-care-marketing/medicare-marketing-guidelines/agent-broker-compensation)
- [Chapter partnerships](https://askchapter.org/partnerships)
