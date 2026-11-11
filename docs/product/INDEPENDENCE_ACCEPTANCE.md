# Independence and completeness acceptance contract

October 21, 2026 · D64 · [Principles](../../PRINCIPLES.md) owns the invariant. **Specified, not implemented or certified.** Personalized comparisons remain held for plan validation/integration. This appendix neither approves financial advice nor changes existing release gates.

## Architecture boundary

```text
Confirmed user facts + user priorities + verified plan/source evidence
    → versioned admissibility/comparison policy + bounded AI explanation
    → recorded candidate universe, unresolved checks and reason codes
    → user review/choice
    → optional consented fulfillment/human support
    → commercial arrangements, availability and revenue accounting
```

Only the last boundary may read commercial arrangements. There is no reverse feature, prompt, tool-response, cache or ranking dependency. Commercial disclosures are rendered separately from personal-fit reasoning. No outreach, enrollment or sensitive-data transmission is authorized merely by this diagram.

Decision inputs are explicitly allowlisted: necessary confirmed person/coverage facts, expressed priorities, requested year/geography/category, verified benefit/cost/provider/drug/quality evidence and source validity. Existing privacy/minimization rules apply. Deny commissions, payout rates, contract/appointment status, referral attribution, sales channel, commercially selected model/version or experiment assignment, lead scores, conversion probability, acquisition cost, LTV, revenue experiments and derived proxies for them. Unknown or newly added fields fail schema validation until reviewed; removing an obvious column while retaining its derived score fails the boundary.

Do not train or reward personal-fit outputs using enrollment, commission, revenue or sales-agent acceptance as truth labels. Keep commercial analytics outside comparison feedback loops. Independently review any proposed outcome label for economic proxies; user outcomes need evidence, consent and a defensible definition. Carrier identities and legitimate quality evidence require provenance and proxy-bias evaluation; they are not permission to memorize commercial preference.

## Required release evidence

| ID | Test or artifact | Passing condition |
|---|---|---|
| I01 | Commission counterfactual | Hold confirmed facts, priorities, plan evidence and versions fixed; zero, multiply, swap and remove all carrier payouts/contracts/referrals. Candidate inclusion, filters, scores, ordering/ties, fit judgments, reason codes and substantive explanations stay identical. |
| I02 | AI/context isolation | Inspect serialized model requests, retrieved records, tool schemas/results, caches and feature exports with synthetic commercial canaries. No economic feature or instruction reaches the comparison/teaching agent; injection cannot add it. |
| I03 | Metamorphic no-compensation case | A well-supported uncompensated option remains discoverable and evaluated identically. An inability to fulfill it produces only a downstream limitation and neutral official route. |
| I04 | Coverage-universe report | Record requested scope, expected universe/source basis, included count/IDs, unsupported categories and missing/rejected/stale records with reasons. Unknown completeness prohibits “all market” claims. Reconcile compensated and uncompensated coverage without selective ingestion. |
| I05 | Missing-data neutrality | Remove one plan's field or evidence source. Its state becomes unresolved and checking tasks appear. It is not automatically assigned a worse fit score, silently hidden or described as unsuitable. Any evidence-completeness ordering must be explicitly separate from fit. |
| I06 | Decision reproducibility | Retain minimized, access-controlled decision inputs/snapshot identifiers, policy/model/prompt versions, candidate/exclusion IDs, dimensions/weights, uncertainty, ties and structured reason codes. Same-version replay yields the same substantive result. AI wording may vary only if it cannot alter meaning/order/reasons; deterministic templates are preferred for critical conclusions. |
| I07 | Costs and priorities | Show the user's priorities, common comparison dimensions, period/basis/assumptions and unresolved cost components. Published amounts, estimates and quotes have distinct labels and source dates. No personal total appears until all required evidence is accepted. |
| I08 | Conflicts and fulfillment | Publish understandable compensation/conflict information and representation/fulfillment limits. User can continue research, keep coverage, choose an uncompensated option or request independent official help. No forced sales-call gate. Disclosure alone does not pass I01–I03. |
| I09 | Objective and feedback review | Feature/training/experiment inventories show no commercial objective or proxy changing comparison or explanation. Legitimate sourced quality evidence has a documented purpose, limitations and separate evaluation. |
| I10 | Recovery and exceptions | Contradictory/stale evidence, unsupported geography/year, model failure and tool failure preserve entries and identify unresolved work. Optional human handoff has consent, context review and actual capability; no invented completed action. |

Run at least synthetic cases for a beginner, experienced comparer, caregiver, job transition, incomplete data, uncompensated best-supported option, ties, unknown priorities and a person who keeps current coverage. Test schema rejection of commercial fields and a source/prompt instruction requesting a paid-carrier preference. Perturb economics at every boundary, including ingestion and training labels—not only the final sorter. These tests supplement, not replace, domain and source acceptance.

Before recommendation release, the founder assigns accountable comparison/data owners and a reviewer independent of sales incentives; they record evidence and sign-off scope. Commercial experiments must declare whether any decision boundary changes. A failed invariant holds the affected release, preserves prior evidence and triggers a documented investigation/correction. Changes require a versioned principle/requirement decision, not an unrecorded prompt edit. Public claims remain limited to measured coverage and tested scope.

Decision evidence must itself follow privacy/retention policy. Reproducibility does not authorize storing raw health chat, all historical sensitive answers or credentials. Use synthetic minimized evaluation fixtures where possible.

## Competitive context — checked October 21, 2026

These are descriptions from official marketing, not interactive product tests, completeness verification or proof of competitors' internal independence. They rule out claiming AI or no-phone access as exclusive to Daylight:

- [Healthpilot](https://www.healthpilot.com/) advertises AI-powered recommendations, online application and browsing without unsolicited sales calls. Its described comparison universe includes plans from represented carriers.
- [The Pocket Protector](https://thepocketprotector.com/tools) advertises no-sales-call research/enrollment tools and its Dorothy plan assistant. Its public claims about commission-independent comparisons are claims, not findings from our architecture or outcome testing.
- [Chapter](https://askchapter.org/) prominently offers licensed-advisor help alongside exploration. It is an internal business reference for Daylight, not evidence that Daylight has equivalent data, execution or support capabilities.

Daylight's differentiation must be demonstrated through comprehensive verified evidence, inspectable unbiased decisions, effective self-service execution and optional context-preserving support. Do not describe these principles as a certification or make unsupported “first,” “only,” better-outcome or competitor-bias claims.
