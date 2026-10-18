# Naples demo re-audit

October 17, 2026 local time / October 18 UTC. This is the after-state of the work authorized following [the original audit](NAPLES_DEMO_AUDIT.md). The original audit and original v1.2 bundle remain historical evidence. UI design is outside this review.

## Assessment

**There is now a runnable, portable factual research demo. The remaining gap is reliable personal answers, especially exact clinical participation and personal drug cost.** The original ingestion is worth keeping. Rewriting it, introducing a database, or extending the old prototype would move us away from the next useful local test.

The demo can explain selected published 2027 Collier plan facts, resolve medicines and pharmacy locations, inspect dated formulary/network rows, and explain local source notices. It can distinguish uncertainty without asking an LLM to invent the answer. That is enough to prepare a qualified, facilitated research review. It does not establish readiness for unrestricted consumer use, a recommendation, a quote, or enrollment.

The latest machine receipt is [demo-execution-receipt.json](../cms-slice/reports/demo-execution-receipt.json). Runnable instructions are in [DEMO_EXECUTION.md](DEMO_EXECUTION.md); the practical handoff is [DEMO_HANDOFF.md](DEMO_HANDOFF.md).

## What changed against the audit

| Audit priority | Implemented evidence | Remaining limit |
|---|---|---|
| Repair the two reproduced defects | Alternate-cache CLI verifies the actual selected cache; MA-only plus a pharmacy retains the correct non-Part-D state; actual-row regressions | These fixes do not resolve publisher ambiguities |
| Check all headline facts used in the demo | 38 plans × three fields = 114 cells; actual Medicare.gov cards agree on all 96 applicable amounts and 18 inapplicable states | Independent presentation check; Medicare.gov and CMS can share submissions; no qualified full-plan certification |
| Diversify carrier corroboration | 16 plan records across three parent organizations; 39 monetary agreements from exact carrier documents | 57 applicable amounts lack separate carrier-document corroboration; eight parent organizations exist in the market |
| Add local evidence | Dated NCH change notice, hospital/medical-group distinctions and Physicians Regional group notice | No exact clinician/location/plan/year confirmation or new-patient status |
| Resolve actual medicines and stores | Real NLM and NPPES requests, saved public examples, explicit identity choices, generic/combination ambiguity retained | NPI is identity; vocabulary is product identity; neither confirms a prescription, operation, approval or participation |
| Broaden drug checks | Twelve product/formulary cases across two carriers; 58 specific agreements; all twelve rows replayed to the original national ZIP, including two positive ST products | Still a small sample; no independently adjudicated noncoverage decision; quantity units remain unresolved |
| Compare medicine lists | Up to 15 explicit RxCUI products across up to 38 supported plans, preserving every per-product state and source order | Exact codes or confirmed identity are required; no fill or annual price; the tiny browser stores one product choice at a time |
| Connect a simple grounded chat | Compact tools; strict Responses contract; server renders factual text; complete lists, source order, limitations and confirmation prompts retained | Live account/model evaluation not performed; source-only routing is bounded, not arbitrary natural-language understanding |
| Package and operate the demo | Verified approximately 26 MB offline archive, atomic release selection, same-code data rollback, dated review checkpoint | Local Python process; no public hosting or operating sign-off; raw source backups still need a durable owner |

See the [field matrix](../cms-slice/reports/demo-quality.json), [official browser observations](../cms-slice/data-sources/medicare-gov-observations.json), [first drug sample](../cms-slice/reports/drug-validation.json), [second-carrier follow-up](../cms-slice/reports/devoted-drug-validation.json), and [provider discovery](../cms-slice/reports/provider-api-discovery.json). Each check is scoped; an agreement on one fact does not approve another.

## Data quality findings

The full captured non-SNP population reconciles exactly with the inspected public Medicare.gov scenario: **32 MA records and 11 PDP records**. The demo still supports 38 of those 43. The five Regional PPOs and 27 SNPs remain visible exclusions. Calling 38 the complete market would still be misleading. Expanding scope requires reviewed geography, applicability and benefit interpretation rather than removing the filter.

The new amount checks are meaningful but narrow: published plan premium, maximum published Part D deductible, and in-network medical spending limit. Tier exemptions remain attached where carrier tables qualify deductibles. Premium is not total Medicare premium; medical MOOP does not include premiums or Part D costs. Stars, complete medical deductibles, supplemental allowances and full EOC conditions were not certified.

The official cards also preserve primary/specialist visit text. A published range such as a specialist copay range stays a range. The demo does not turn the lowest endpoint into a promise. Referral, deductible, service-setting and EOC qualifications remain open. Add another medical benefit only when a real review question needs it.

The nine-product sample spans plain generics, different strengths, immediate/extended release, brands, PA, QL and insulin. All 45 checked markers/days/tier values agree. This is more useful than repeating the original single-product example, but it still samples one carrier/formulary. Quantity numbers coincide in seven cases and differ in two; **none receives a CMS unit by inference**. The source PDF does not print the matched NDCs. Product identity and package equivalence remain separate. The pinned [carrier formulary](https://files.guidewell.com/asset/aece76d0-71bb-4563-ab8c-47ce4a79ef7a/medicare-forms-2027-comprehensive-formulary-fbm2836.pdf), PDF pages 62–65 and 67, was rendered and visually inspected; the case file records exact row anchors.

After that audit checkpoint, an actual carrier document lookup for the public Naples ZIP reached Devoted's exact H9884-016-000-2027 document page. Its linked approved formulary 00027129 includes the matching plan name and two positive ST product strengths. Those markers and an additional brand/QL row agree with 13 specific CMS values, replayed independently. The linked ST criteria were captured and visually inspected without evaluating a person's eligibility or treatment. A related branded RxCUI absent from the basic capture remains unresolved; generic listing does not confirm the brand. This brings the combined sample to twelve product/formulary cases, not twelve distinct medicines or full cross-carrier validation. [Exact plan documents](https://www.devoted.com/plan-documents/benefit-and-coverage-details/H9884-016-000-2027/), [formulary PDF](https://assets.devoted.com/formulary/2027/2027_Devoted_Health_GSC_EXC_MOD_Y0142_27M61_C_ENG.pdf), PDF pages 2, 13 and 65, [2027 criteria index](https://www.devoted.com/prescription-drugs/drug-coverage-limits/2027-part-d-step-therapy-criteria/).

The two excluded D-SNP premium discrepancies, uncertain source-date tokens and quantity-unit issue from WP3 remain unresolved. They were not silently fixed. A future date inside a filename is not a retrieval or effective date. No 2027 personal pricing feed appeared during actual CMS metadata discovery; the latest quarterly candidate filename is still for 2026. Even a correct-year quarterly average would need its estimation scope assessed before a personal cost claim.

## Integration findings

NCH's dated notice is immediately useful locally: it announces Cigna/HealthSpring and Wellcare MA changes effective January 1, 2027, while distinguishing 2026 care. Its payer page distinguishes the hospital from the medical group and warns that carrier contracts do not cover every product. Both limitations accompany the demo's provider answer. [NCH notice](https://nchmd.org/maupdate/), [contracted plans](https://nchmd.org/patients-and-visitors/contracted-insurance-plans/).

Clinical provider automation remains the largest integration gap. CMS's public FHIR directory responded, but five target searches and a positive-control name search returned no entries. Sample resources had 2026 periods and one HMO/PPO text conflict. Medicare.gov's public provider search also returned no match for the inspected Naples physician example under shortened and complete surname variants. These are failed discovery cases, not out-of-network evidence. An adapter that mapped empty responses to “no” would make the product worse.

A final [carrier directory probe](../cms-slice/reports/carrier-provider-probe.json) successfully selected 2027, Collier and Devoted H9884-016 through the carrier's public UI. The public physician example and NCH name search displayed no matches. The plan-specific search flow is useful integration discovery, but neither empty result establishes participation or nonparticipation. The carrier also displayed location/change/completeness and plan-specific confirmation qualifications. No network verdict was enabled from these results.

NPPES store lookup is usable for identity and exact location selection. The existing CMS pharmacy rows support a dated exact-NPI check. Neither proves the store is open now, the preferred channel for this fill, or a quoted price. The saved Naples query is a city query, not a complete county census.

The optional model adapter is implemented against the Responses API with strict tool schemas, bounded calls and `store:false`. No live request was made because the environment has neither a configured API key nor a selected model. Controlled responses test transport and factual boundaries; they cannot prove live model grounding or comprehension. `store:false` is one request setting, not a complete privacy, retention or account-approval assessment.

No actual Medigap supplier payload, authorized clinical payer feed, quote receipt or enrollment access exists. Those should remain absent from the demo promise until inspected. Public marketing pages and draft adapters would not establish those integrations.

## What went well and what still needs improvement

The strongest decisions were reusing real sources, repairing observed bugs before expansion, keeping source hashes and exact identities, broadening independent comparisons, and packaging only the derived inputs needed to run. The portable tests run after clean extraction without the national archives or PDF executables. The simple chat uses ordinary Python and browser files; no new framework, account system, orchestration service or speculative database was needed.

The second pass also caught failures a happy-path test would miss: an overly small medicine candidate cap hid a plain generic behind combination products; provider questions could route to unrelated plan premiums; future-year requests could receive 2027 facts; a model could omit important provider qualifications. These were corrected and regression-tested. Rebuilding old source bytes now retains the explicit review deadline rather than pretending the data was freshly published.

Improvement should now be measured by **supported question coverage and corrected misunderstandings**, not script count, lines of code or number of manifests. Keep one current audit, one runnable guide and one handoff. Preserve earlier evidence as history rather than repeatedly expanding general architecture paperwork.

## Next steps that actually advance a Naples demo

1. **Review the concrete release with a qualified domain reviewer.** Use the exact source facts and unresolved cases in the handoff. Record factual corrections, source-use/freshness dispositions and the permitted demo promise. This requires a real person and accountable operating owner; no sign-off is fabricated here.
2. **Exercise the real model account, then run the prepared grounding cases.** Configure the actual approved account/model; record release, model, exact inputs, evidence membership and failures. Include omission, ambiguity, stale data, unsupported year/location, missing basic evidence and request-to-enroll cases. A key alone is not a passing evaluation. Source-only review can proceed without it.
3. **Close a small exact local provider case set.** Start with facilities/practices actually named in review. Obtain exact plan/network/year and location evidence, with positive, stale, conflicting and unresolved cases. A reviewed manual record is acceptable for a small facilitated demo; a universal provider API is unnecessary.
4. **Expand independent drug validation across carriers.** Build on the newly checked positive ST and brand/QL cases; prioritize the other carriers, insulin package distinctions, and absent basic evidence. Obtain the actual carrier PA/ST criteria when the answer depends on approval. Keep quantity-dependent conclusions unavailable until the unit/package is supported.
5. **Run 8–12 facilitated sessions after the applicable review.** Include direct retirees and caregivers, use consented public scenarios first, and record actual task failures and comprehension. No recruitment, consent or participant result occurred during this work. Fix severe misunderstandings before widening access.
6. **Add price access only if the next promise depends on personal cost.** Require actual 2027 plan/drug/pharmacy/quantity/days inputs, inspected estimation scope and independent receipts. Medigap quotes and enrollment each require their own access and operating evidence. They are not prerequisites for this narrower factual research review.

The immediate critical path is qualified review, actual model evaluation if used, and observed local comprehension. Provider and pricing work should follow the questions those reviews expose. UI redesign and the Virginia source gap are off that critical path.
