# Proposed comparison response contract

November 1, 2026 · `daylight-comparison-design-2026-r1` · Design only; not an implemented endpoint or approved policy.

Return one consistent comparison object for the requested task. A browser should not have to reconstruct conclusions from research rows. The private service owns evaluation; the model receives only permitted findings and eligible conversational moves. Examples in [synthetic-examples.json](synthetic-examples.json) illustrate a held real-release state and a fictional comparison. They contain no real plans, people, prices or verified findings.

## Response envelope

| Field | Proposed contract |
|---|---|
| `contract_id`, `comparison_id`, `generated_at` | Versioned shape, opaque request/result identity, generation time. Generation time is not evidence currency. |
| `mode` | `published_browse`, `path_comparison`, `same_role_plan_comparison`, or `research_preparation`. Never silently substitute one for another. |
| `binding` | Beneficiary, guide/readiness revisions, item revision digest, profile contract hash, advisor adapter version, requested year/geography/time, scenario and preference revisions, rule/method versions, serving build, evidence manifest, exact accepted release or null, and comparison-purpose authorization reference where applicable. |
| `authority` | Per-purpose decisions for published display, personal comparison, ranking, recommendation, quote and enrollment. Each has `held|permitted`, exact authority refs and structured holds. Independent gates cannot be inherited across purposes. |
| `task` | Explicit requested goal/check and comparison scope; provisional conversation focus is marked separately. Familiarity affects explanatory presentation only. |
| `capabilities[]` | Existing capability key or explicitly labeled proposed capability; relevant report sufficiency, missing inputs, external evidence state, reviewed-policy state and output authority separately. No aggregate readiness score. |
| `universe` | Expected catalog basis, requested scope, completeness `complete|partial|unknown`, discovered/evaluated counts, immutable candidate-set ref, unsupported categories, and every exclusion reason. Pagination limits are not market limits. |
| `units[]` | Current arrangement, a coverage path with component refs, or a same-role offering/product. Identity, period, role, source/release refs, restrictions and evaluation state. |
| `dimensions[]` | Shared row definitions with scope, basis and user relevance. Every unit gets a cell/finding ref or an explicit unresolved/not-applicable cell for every relevant dimension. |
| `findings[]` | Typed, condition-preserving findings defined below. Critical numerical and eligibility claims render deterministically from them. |
| `tradeoffs[]` | Supported pairwise differences, exact dimensions compared, report/evidence/rule refs and unresolved material dimensions. Direction is a stated measurement, not global personal fit. |
| `outcomes[]` | Inspect, continue checking, keep current arrangement or defer, each with remaining checks and authority. Keep/defer are decision outcomes, not fake plan offerings or claims that inaction is safe. |
| `next_question` | At most one service-eligible user question, or null. Existing question/alias ID, exact field/item/person target, known/missing parts, accepted answer meaning, dependency, affected findings and why it matters now. |
| `work_items[]` | External source/identity/reconciliation/policy/release or authorized-human tasks, separately from user questions; owner role, exact subject/source scope, status, reason, closure evidence and affected findings. A proposed task is not a completed tool action. |
| `decision_record_ref` | Owner-bound minimized internal trace: all 41 accounting entries, findings' dependency graph, included/excluded IDs, rule evaluation, ordering/tie policy and versions. Not a public log or new transcript store. |
| `validity` | Exact bound revisions, evidence effective intervals, freshness/revocation rules, and stale dependencies. A timestamp/TTL alone cannot validate a changed report or revoked release. |

Fields are structurally required where applicable; absence must have an explicit reason. The design map is a specification, not a runtime JSON Schema validator. Any future API schema must reject unknown input fields and enforce the semantic invariants here as well as syntax.

## Identities and comparable units

Use a tagged identity union. `cms_offering` retains benefit year, contract, plan and segment, e.g. the existing `2026:Hxxxx:ppp:sss` shape. A source-scoped `medigap_product` instead needs legal issuer identity, state, policy form/edition, standardized design/variant and business/distribution status. Its rate observation additionally binds rating class, geography, effective period and qualifiers. A plan letter is not a unique policy identity or personal quote. These Medigap structures are proposed normalization work; the current CMS-only offering key must not be reused for them.

A `coverage_path` references its medical, drug and supplemental components and any unresolved necessary component. A PDP-only premium cannot stand for the price of an entire Original Medicare arrangement. Same-role comparisons and educational path comparisons use distinct modes. The current-coverage baseline retains reported versus externally bound facts and current/former episode periods; unknown current identity or cost is explicit.

## Finding object

```text
Finding = {
  finding_id, unit_id, dimension_id, subject_or_item_id?,
  report_refs[], question_ids[], gap_ids[],
  input_state, evidence_state, applicability, policy_state, output_state,
  result: supports | conflicts | unresolved | not_applicable,
  value?, cost_basis?, condition_set, reason_codes[],
  evidence_refs[], rule_refs[], dependency_refs[], invalidation_keys[]
}
```

`result` expresses the evidence's relationship to a precisely stated need or assertion. It is not confidence, a plan score or a legal eligibility finding. `supports/conflicts` require the relevant predicates, evidence and accepted method; otherwise return `unresolved`. A legitimate not-applicable state needs a reason such as an explicit report of no medicines for that check. Unknown never means not applicable. An explicitly reported absence is not an external audit of all possible care needs.

Keep these axes separate:

| Axis | States/meaning |
|---|---|
| Input | `sufficient_report`, `partial`, `unanswered`, `unknown`, `deferred`, `declined`, `tentative`, `conflicting`, `stale`; requiredness is finding-specific. |
| Evidence | `missing`, `observed`, `reviewed`, `disputed`, `stale`, `source_stopped`; observed/reviewed do not themselves mean output permitted. |
| Applicability | `applies`, `does_not_apply`, `undetermined`; evaluated from the complete relevant conditions under an accepted rule. |
| Policy/method | `unreviewed`, `reviewed_for_exact_purpose`, `revoked`. Source text alone is not an executable personal policy. |
| Output | `held`, `released_for_exact_purpose`; cite original acceptance/replay and release bindings. A fictional fixture permission is never a real release. |

`condition_set` preserves the full logic: conjunctions/disjunctions, exceptions, network/site, frequency, eligibility/service prerequisites, limit/period, exclusions, missing predicates and scope. Each predicate retains its source/locator, source-native meaning, technical/context notes and `true|false|unknown|conflicting` evaluation. Do not flatten an allowance to an amount, cut a caveat from a quotation, or treat an empty condition array as proof of no conditions. A reference to a sealed condition set is allowed only when the complete set is retrievable and unchanged. The comparison retains disagreement lineage rather than choosing a convenient source by majority or extraction confidence.

Evidence refs bind source file/content hash, source record and derivation, locator/page/table/row, exact entity/period/geography, source-use state, semantic review, acceptance target, release/purpose and revocation/freshness. Consumer links expose only permitted source material. Keep protected/internal locators private.

Cost values additionally require currency, units, period, cost type (`published_component|scenario_estimate|quote`), network/channel, population/personal basis, phase, included/excluded components, assumptions and provenance. Zero is a known value; null is unknown. No annualization, netting, savings or total-cost claim until the corresponding reviewed method and all required components are available. A supported subtotal lists omissions and is never labeled a complete annual cost. An aggregate/average price plus a store listing is not a personal fill quote.

## Holds, progress and stale responses

Use reason codes such as `INPUT_PRECISION_MISSING`, `REPORT_CONFLICT`, `ITEM_IDENTITY_UNRESOLVED`, `SOURCE_MISSING`, `SOURCE_DISAGREEMENT`, `SOURCE_STOPPED`, `WRONG_EFFECTIVE_SCOPE`, `CONDITION_UNRESOLVED`, `POLICY_NOT_ACCEPTED`, `EXACT_RELEASE_REQUIRED`, `BASELINE_INCOMPLETE` and `DEPENDENCY_STALE`. Each code identifies the affected finding/purpose and required closure evidence. Actual code names remain proposals.

If a report or source changes during evaluation, return a typed `STALE_BINDING` result without presenting the old personal conclusion as current. Reassessment reads a consistent new snapshot; it cannot replay a stale action token. Slow external work can return `pending` tasks with a real task ID only after a tool has actually created it. A failed check remains failed/unknown with its receipt, not an invented negative result. The ordinary page can continue showing independently valid published material or preparation where genuinely permitted.

The internal trace accounts for every one of the 41 IDs using `used`, `missing_for_requested_finding`, `optional_unset`, `not_relevant`, `deferred_for_requested_finding`, `clarification_needed` or `alias_reused`, with target refs and affected finding/rule refs. These are audit states, not a consumer questionnaire counter. Response minimization omits irrelevant personal values; do not automatically send the trace or all profile fields to an LLM, shared cache or telemetry.

## Rendering implications

The compact initial view shows comparison context, relevant priorities, baseline, a manageable examined set and material supported differences/unknowns. Keep the complete accessible catalog and visible filters/counts. Detail and compare views use the same dimension names, units and conditions. Source explanations sit beside the claim they qualify. Phone comparisons follow the existing master contract's readable dimension grouping.

This is behavior design only. Preserve the :8893 natural conversation, one composer, optional end review and existing :8890/:8891 surfaces. Do not add a second questionnaire, mandatory profile review or generic permission modal. The existing named-action and consent rules still apply to the particular supported action.
