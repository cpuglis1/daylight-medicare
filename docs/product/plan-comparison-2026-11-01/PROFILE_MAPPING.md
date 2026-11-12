# Reuse the profile; add a comparison view

November 1, 2026 · Proposed D87 mapping · Definitions and code inspected; no personal records read.

## Authority and normalization

The baseline [export](../../../infrastructure/daylight-data/config/profile-contract.2026.json) is `daylight-profile-contract-2026-r1`, content digest `fc91d3f6df8e338b79fdbd6df909d76196c9ac59bca1d792666bb1f7b7387cbb`. Its 78 paths comprise 19 guide paths and 59 readiness paths. The 41 IDs comprise T01–T10, RC01–RC28, RC11.C1, RC16.C1 and RC16.C2. Three aliases reuse parent fields; there are no additional alias answers to collect.

The comparison view must read the relevant existing records with their actual revisions. It must not translate a questionnaire-completion counter into capability readiness. Its canonical references have this proposed shape:

```text
ReportRef = {path, item_id?, subject_id, scope, report_revision, record_revision}
Report = {ref, value, report_state, capture_method, confirmation_state,
          temporal_scope, precision, supersedes_ref?, known_parts, missing_parts}
```

`path` is an inventory path or an explicitly versioned extension path. An `items[]` reference always carries the particular item ID; an array position or name is insufficient. `subject_id` identifies the beneficiary/care item owner, not whoever typed the reply. Whole-profile bindings include both guide and readiness revisions plus the adapter version; item revisions support narrower invalidation. Transactional snapshot consistency must be implemented before these two records support a live comparison.

The proposed view preserves report states `unanswered`, `reported`, `tentative`, `unknown`, `deferred`, `declined`, `explicit_none`, `stale`, `conflicting` and `superseded`. Explicit confirmation is a separate provenance attribute; it is not external verification. A direct unambiguous report can be usable as a report without another acceptance card. Old records retain their original semantics. Do not upgrade old provenance by inference.

The advisor's natural references differ from inventory paths: `guide.needs.providers` and `readiness.RC22.medicine-1.strength` are not literal inventory paths. Map them through declared field and entity bindings. [Natural state](../../../alternatives/advisor-first/natural_state.py) temporarily projects honest report statuses into legacy `confirmed_by_user` for compatibility. That wire marker cannot establish explicit confirmation, consent or verified coverage. Preserve the natural metadata. Similarly, an old readiness shortcut deriving A/B from broad coverage categories must never supply an actual entitlement or timing finding.

The frozen export is a traceability baseline, not the whole product authority. Apply the later owner guidance in [MASTER_DESIGN.md](../MASTER_DESIGN.md), including D79's necessity-first, missing-details-only refinements. RC13 includes consequences for the beneficiary's own group/retiree benefits as well as other people, with exact party/action/effect/period gaps. RC16.C1 asks the relevant actual Advantage episode start, with first-entry/history conditions kept distinct. RC23 can reuse only the particular fill/store fields needed for a supported quantity-limit or pharmacy-network question, without requiring a price request or full pricing interview. Its inherited pricing-only capability metadata is a retained gap, not new activation authority.

Original inventory wording/dependencies remain traceability, not a required consumer prompt or blanket active gate: a narrow RC24 check does not require completing RC23 pricing, and optional RC25 does not automatically require RC03/RC18 or an assistance interview. A proposed finding's accepted rule must establish its actual minimum dependencies.

## Current advisor extensions to preserve separately

| Current location/meaning | Treatment in the proposed comparison view |
|---|---|
| `guide.fields.situation.retirement.value={status,when}` | Explicit circumstance with person/time scope; never infer retiree insurance, enrollment, HSA chronology or desired start. |
| `guide.fields.situation.age65.value={month,year|null}` | Partial milestone; an unstated year stays unknown. No new required birth-date question. |
| T04 `coverage.requestedStart='soonest'` | Preference, with no invented month, deadline or effective date. A superseded exact month is unusable. |
| `readiness.natural.provenance` | Field/item method, report status, subject, scope, revision and supersession. These remain authoritative over compatibility labels. |
| `readiness.natural.dialogue` | Last target, explained/deferred topics and clarifications guide conversation only; reading does not prove comprehension or preference. |
| `readiness.natural.agenda` | Explicit concerns and bounded priority reasons; reasons apply only to the current beneficiary/scope and underlying priority revision. Not weights or hard constraints. |
| Existing `guide.subject.role` mirror and RC18 `programs[]` convenience | Explicit compatibility mapping to RC01 and per-program reports; do not silently count them as new baseline fields or flatten partial assistance knowledge into one boolean. |

This separate adapter specification preserves the baseline **41/78/14** accounting. Two circumstance observations and dialogue/provenance metadata do not create more required questions. Baseline hashes and current extension hashes are recorded in the design map for later drift detection; they are not release receipts.

## The fourteen gaps stay visible

The fourteen bounded optional `readiness.conversation.details.Gxx.value` report paths can retain volunteered context under the existing permission rules. A free-text note does not close the structured representation, evidence or policy gap. Proposed typed objects below belong to a future comparison projection, not new required customer fields.

| Gap | Comparison object or dependency still needed | Consequence if unresolved |
|---|---|---|
| G01 exact eligibility/timing anchors | Rule-specific date/history anchor with precision and provenance | Hold the exact timing/rights result requiring it. No universal birth/clinical intake. |
| G02 Part A chronology | Application/effective/retroactive coverage episodes, distinct from Part B and desired start | No inferred retroactivity or complete timing/HSA result. |
| G03 personal federal premium applicability | Separately scoped premium/subsidy/IRMAA component, if a supported requested calculation needs it | Published reference may be explained within acceptance; no personal federal premium or complete total by default. |
| G04 exact policies and episodes | Current/former policy identity, component, period, provenance and applicable return-right binding | Baseline remains partial; no invented current rate, continuity or right to return. |
| G05 trusted care-item bindings | Stable provider/site, exact drug product and pharmacy IDs with candidate resolution and source lineage | No personal network/formulary/store finding from names alone. |
| G06 care places and periods | Several destinations, routine/emergency needs and periods | No universal travel-access conclusion from one city or emergency clause. |
| G07 contributions | Person-specific HSA contribution and entitlement chronology | No boolean tax/contribution conclusion. |
| G08 costs | Explicit scenario, units, periods, utilization, components, exclusions and accepted method | Show supported components separately; no comprehensive total or savings. |
| G09 assistance/qualification | Exact named program, level, period and verified scope | No inferred subsidy amount or full restricted-plan qualification. |
| G10 payer-order context | Basis-specific employer-size question meaning, threshold and parent revision plus official rule | Reassess when eligibility basis changes; a yes/no answer cannot migrate between threshold variants. |
| G11 medicine method/problem | Per-item administration/dispensing/device/context and any separate coverage problem | Clinic/pharmacy answer alone cannot decide benefit part, approval or clinical appropriateness. |
| G12 preferences/constraints | Explicit scoped constraint or ordering, with report revision and independently reviewed interpretation | Ordinary preferences remain preferences; no invented weights, ranking or must-have. |
| G13 other/partial coverage | Several coverage episodes and unresolved subtype, allowing known positives alongside unknowns | No forced single category or inferred coordination/absence. |
| G14 correction dependencies | Exact correction target, field/item revision and downstream finding/action dependency graph | Ambiguity holds only affected use; stale results/tokens cannot survive a clear correction. |

## What a person would see

Keep the existing optional profile inspection and correction utility. Present a readable account of circumstances, current coverage, care needs and expressed priorities, with meaningful unknowns only where relevant. It should help the person recognize and edit their reports. Do not display the 78-path storage model, an intake-completion percentage or forty-one empty answer slots.

The comparison case adds an inspectable “what this result used” view of the reports and checks material to that result. Unknown external evidence becomes a named remaining check. No full transcript or extra permanent biography is required. Existing optional saving, sensitive saving, v2 AI context and action permissions remain distinct; the design adds no automatic AI transfer or personal-data migration to PostgreSQL.
