# Daylight principles

Owner direction · October 21, 2026 · Read before product, model, data or commercial decisions.

**Our purpose is Medicare expertise without giving up control of the process.** “AI-first Chapter” is an internal business thesis, not permission to copy another product or claim exclusivity. The intended positioning is an AI Medicare advisor that helps people understand, compare and act on their own terms, with humans available when needed. This is positioning, **not another website tagline**. D137 (November 11, 2026) restores **Daylight** and **Medicare, plain as day.** on :8894, with **Understand your coverage options and prepare to enroll, at your pace.** beneath it. The advisor identity and public messages also return to Daylight. Protected variants and historical evidence remain unchanged.

These are binding design and governance requirements, including [D64](DAYLIGHT_REQUIREMENTS.md#independence-and-completeness--october-21-2026). They are not a claim that a validated recommendation engine, comprehensive market coverage, enrollment or human handoff is implemented. Current personalized comparisons remain gated. Use the [master design](docs/product/MASTER_DESIGN.md) for flow and [acceptance appendix](docs/product/INDEPENDENCE_ACCEPTANCE.md) for evidence required before release.

**Strategic extension · October 25, 2026 · D73:** [The canonical thesis and evidence roadmap](docs/product/STRATEGIC_THESIS.md) defines the free consumer platform, brokerage/partner hypothesis, staged continuing service and measurable consumer proof. Apply its change-review checklist alongside these principles. Ambition is not implementation evidence or release approval.

## 1. The user's interests determine the answer

Commercial commissions, payouts, carrier contracts, appointments, referral fees, conversion targets and lifetime value must not affect eligibility, inclusion, filtering, ranking, tie-breaking, personal fit, explanation, uncertainty or the user's next research step. Uncompensated plans receive the same treatment. Keeping current coverage and doing nothing can be appropriate outcomes; an enrollment is not the definition of success.

**Same confirmed user facts + same plan evidence + same user priorities + same policy/model versions must produce the same substantive outputs when commercial economics change.** Disclosures cannot substitute for that invariant. Insurer quality, complaints and service evidence can matter when relevant and sourced; an insurer's commercial relationship with Daylight cannot.

## 2. Comprehensiveness and independence are separate obligations

We aim to investigate the complete relevant coverage universe. We must state the actual category, geography, year, sources, freshness and exclusions, including missing, unsupported and uncompensated options. We cannot claim an all-market comparison merely because a captured subset is treated impartially. Independence within available records does not establish complete coverage.

A missing or unverified field means **unknown**, not poor fit. Missing plans and unsupported checks stay visible with a way to investigate officially. No silent exclusion, invented benefit or substitution of a nearby year/location may make the result look complete.

Compare coverage paths before individual policies: represent Original Medicare with optional Medigap/separate Part D and Medicare Advantage fairly, including access, restrictions, costs and future flexibility. Reported customer completeness and verified external evidence are independent requirements; finishing intake cannot supply either missing facts or missing source acceptance. Samples remain browsing, not recommendations.

## 3. Economics belongs downstream of the decision

Daylight may be funded by commissions. Its recommendation and AI systems must remain structurally independent: commercial metadata stays in a separate fulfillment/revenue boundary, outside comparison features, retrieval, prompts, tools, model context and training/evaluation labels. The evidence decision is recorded before optional fulfillment consults commercial arrangements. Model/version selection and experiment routing must also be independent of those economics.

If Daylight cannot fulfill a chosen option, say so and offer a neutral external route. Do not hide that option, alter the recommendation or funnel the user toward a compensated substitute. Any changed evidence or user preference requires a new explained decision; a revenue opportunity does not.

Commercial viability must be tested across the neutral outcome mix, including no-commission options, retaining coverage and deferral. Acquisition and service costs belong in business evaluation outside the decision engine; weak contribution cannot justify changing the recommendation mix.

## 4. The agent does useful work while the user stays in control

The agent understands the goal, teaches in context, gathers and confirms necessary facts, investigates through authorized verified tools, explains tradeoffs and carries context forward. It executes supported tasks rather than merely producing conversation. Unavailable tools and unsuccessful checks remain explicit; saying an action happened is not execution.

Depth adapts to knowledge, separately from the goal. Beginners learn one concept at a time; experienced users can move quickly and reopen explanations. Decisions and profile facts are inspectable and correctable. Progress, Back, help return and unknown states remain stable. Self-service progress must be useful without a sales call. An optional, consented human handoff preserves context and does not force repetition or unlock otherwise withheld research.

Allow useful questions before extensive intake; progressively collect only consequential facts and explain their purpose. Saving, AI disclosure, family participation and human handoff need their own appropriate permission. More retained data is not automatically better. Same-browser guest saving does not establish household sharing or cross-device recovery.

## 5. Explain the evidence, costs and uncertainty

Use the person's priorities and consistent comparison dimensions. Show the cost basis, period, assumptions and missing components. Distinguish a binding quote, a published amount and an estimate; never turn an incomplete premium comparison into a promise about personal total cost. Link source, effective date, coverage scope and version to material claims. Explain meaningful alternatives and why an option could fit differently under another stated priority.

A clear answer includes what remains unresolved. Privacy choices, minimal AI context, confirmation before recording interpretations and factual release gates remain binding even when they slow conversion.

## 6. Prove the operating model

The defensible product is verified data, reliable integrations, exception handling and observed user outcomes. A polished conversation or a large test count does not establish a complete advice-and-action service. We have not earned a “TurboTax for Medicare” equivalence claim. Evaluate comprehension, retained control, correction/recovery, coverage gaps and completed supported tasks—not just enrollments, revenue or conversation satisfaction.

Before any personalized recommendation release, require counterfactual commission tests, commercial-context leak checks, coverage reports, reproducible reason codes and independent review. Record conflicts, evidence and remediation. The [acceptance appendix](docs/product/INDEPENDENCE_ACCEPTANCE.md) makes these release requirements concrete; they are not claimed completed today.

Use the [cohort evidence definitions](docs/product/STRATEGIC_THESIS.md#evidence-definitions-for-the-first-cohort) for accuracy, comprehension/control, completion, staff minutes, contribution after acquisition/support, retention and repeatable acquisition. Audit human overrides with reasons and evidence under the same independence/release gates. Lower staff involvement is a hypothesis to measure against a comparable baseline, not an assumed benefit of AI.

## When a request conflicts with these principles

Name the conflicting requirement and proceed with compatible work. Do not silently add a commercial feature, suppress a plan, change the candidate universe or weaken an evidence gate. Offer a design that preserves independence, such as separate downstream fulfillment. A conflicting explicit owner proposal requires an explicit recorded decision and governance review before dependent work; disclosure or a styling request is insufficient. Legal/source/privacy safeguards still apply. Update [owner requirements](DAYLIGHT_REQUIREMENTS.md) and the master decision record rather than letting later prompts drift.
