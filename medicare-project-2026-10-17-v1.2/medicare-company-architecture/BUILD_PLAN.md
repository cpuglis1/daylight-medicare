# Ground-up implementation plan

Company name undecided · revised October 17, 2026 · [Architecture](ARCHITECTURE.md)

## Implementation rule

Build one complete, verifiable capability at a time, using actual source data. Do not generate a complete database or pretend a vendor integration exists to make an end-to-end demo pass. No company name has been chosen. The earlier prototype is archived and is not the production repository.

The operating model is **self-directed research, licensed transaction**. The deterministic engine ranks from user-stated criteria and verified data; the AI explains without changing the ordered result set. A licensed, appointed agent of record performs purchase review/re-verification and submits or authorizes the application. Optimize **human minutes per effective, retained policy**, with quality, retention and response-time guardrails.

The competitive position is **auditable neutrality**: reproducible, inspectable rankings independent of compensation, not “unbiased AI.” Prioritize **caregivers → self-directed researchers → Medigap shoppers**. Distribution proceeds **direct caregiver content/search → financial-advisor software and publishers → health systems after outcome evidence**. The 12–24 month incumbent-response window is a planning hypothesis. The edge is access for people poorly served by the phone model and scalable research capacity, not eliminating licensed labor.

## 1. What exists now

- Company/product/software architecture for review.
- Actual-source reconnaissance of the 2027 CMS landscape and PBP archives: a full CSV structural profile, archive metadata, five parsed PBP samples and a candidate filename join. See [DATABASE.md](DATABASE.md) and its evidence.
- Proposed application behavior contracts.
- The [archived experimental workbench](../archived-prototype/README.md) and [unchanged code snapshot](../prototype-code-snapshot.zip).

There is no production database, completed CMS ingestion, purchased data feed, validated cost/eligibility engine, operational licensed-agent purchase process, carrier enrollment connection or real customer environment.

## 2. Repository approach

Start a fresh implementation repository after this design review. A sensible initial structure is:

```text
docs/                  architecture, source observations, decisions, operating gates
data-sources/          versioned manifests, field mappings and inspection reports
scripts/               small reproducible inspection/import commands
packages/contracts/    only the internal schemas needed by implemented queries
packages/domain/       validated interpretation and decision logic as it emerges
apps/api/              application endpoints and authorization
apps/web/              consumer workspace and restricted operations view
workers/               adapters and asynchronous jobs when required
tests/                 source, domain, workflow and end-to-end cases
infra/                 deployment definitions introduced with a deployment need
```

Do not create empty services, generalized frameworks or migrations for every eventual company function. Start with the files required by the first milestone. Select/pin the toolchain, package manager and supported versions during repository setup. Keep large raw files, credentials and personal data out of source control; store source manifests and permitted minimized test fixtures.

## 3. Work packages and acceptance

| Package | Build | Exit evidence |
|---|---|---|
| **0. Review and discovery** | Review the caregiver-first strategy and architecture; select first questions/geography/categories for a data experiment; obtain source documentation and supplier samples/terms | Ordered segment hypotheses, actual inspected inputs, chosen query, legal/data/partner gaps and an incumbent-response watchlist; no speculative DDL |
| **1. Real public-data slice** | Reproduce landscape/PBP inspection; explain source populations and candidate-join discrepancies; map selected identity/geography/premium/benefit fields | One actual market query, source-to-output paths, verified interpretations, rejected/unknown values and repeatable tests |
| **2. Minimal read model and UI** | Persist only the validated fields needed by that query; expose a bounded read API and accessible comparison view | Every displayed fact traced to source; no hidden mismatched year/county; documented coverage limitations; first schema reviewed against real inputs |
| **3. Prescription evidence** | Inspect current formulary/pharmacy/pricing layouts; implement confirmed medicine/pharmacy identity and restriction checks | Drug/plan/year joins proven; missingness handled; independently checked price scope; no claim of complete cost simulation yet |
| **4. Medigap evidence and quoting** | Secure representative vendor data/rights; model only demonstrated product/rate/quote fields and underwriting conditions | Actual quote receipts, exact input assumptions, discounts, validity and unresolved acceptance conditions; documented source coverage |
| **5. Provider verification** | Inspect actual identity/network payloads; implement exact provider/location/plan queries and conflict/freshness handling | Required provider check with supported evidence; ambiguous/stale/out-of-network cases tested |
| **6. Customer, rules and calculations** | Add consented saved profiles/current coverage and parent/caregiver sharing with actor provenance; supported rules/scenarios/bundles; deterministic ranking with confirmed criteria/weights and pinned inputs/data versions | Qualified case review, exact calculations/ranking reproducibility, full results/exclusions, unchanged ranking under different compensation/partner attribution, explicit uncertainty and permission tests |
| **7. Conversational research and shared workspace** | Add OpenAI adapter, explanation rules, saved/resumable research, caregiver sharing/invitation, criteria controls and an engine-ordered shortlist with persistent full results/exclusions | Held-out comprehension/grounding and evening/weekend/save-return tests prioritizing caregivers; exact AI/engine agreement; no verdicts, invented facts, silent profile change or purchase authority |
| **8. Licensed purchase handoff and enrollment** | Establish operating authority, licensed/appointed agent coverage and carrier access; implement Ready to purchase, full-context handoff, seasonal response targets/queue/scheduled fallback, checklist, re-verification, consumer/agent authorizations and submit/status/reconcile | Complete transcript/profile/snapshot; qualified agent assignment; identity/consents, SOA (MA/PDP), pre-enrollment/provider/drug/replacement/GI checks; changed facts return for consumer review; no submission without required approvals; duplicate/timeout/partial-success and effective-coverage tests |
| **9. Continuing service and operating control** | Active-policy record, notices/change reviews, issues/complaints, human work tracking, compensation/chargeback reconciliation | Service outcomes/open tasks recorded accurately; attributable agent/follow-up/failed-case/service minutes captured; finance isolated from ranking; material changes trigger the appropriate review |
| **10. Pilot and expansion** | Start with direct caregiver acquisition, test segments in order, establish cohort/retention-window/staffing and self-serve conversion baselines; integrate software partners next; publish outcome evidence before health systems | Human minutes per retained policy plus suitability, complaints, retention, comprehension, wait/abandonment and channel conversion; declared publication methodology and scope-specific gates |

This is a dependency order, not a fixed calendar or staffing promise. Work can overlap where inputs permit it: company/legal/data diligence should run alongside engineering; accessible interaction research can use truthful limited data. No consumer rollout depends solely on a developer declaring the software complete.

## 4. First coding task, precisely

The first build task is **not** the LLM interface or a national schema. It is a repeatable real-data path for one explicitly scoped query.

1. Read the CMS README/layouts and the reconnaissance evidence.
2. Verify source URLs, artifacts and checksums; preserve raw data according to terms.
3. Reproduce counts and inspect distributions, not just the first row.
4. Investigate the one unmatched landscape candidate and a representative sample of the PBP-only population.
5. Resolve geography with authoritative mappings and documented category scope.
6. Choose a small set of display fields and prove their semantics, units and null behavior against actual records and documentation.
7. Return matching products and those fields for one test market/year, with source paths and explicit gaps.
8. Propose the smallest persistent schema for that demonstrated query and review it before migrations.

A CSV/JSON query and mapping report are valid first outputs. A large generated schema without proven joins is not.

## 5. What the agent must not invent

- A universal 25,000-plan count or a definition of “all” without a stated source scope.
- Vendor fields, pricing terms, credentials, data rights or contracted carrier access.
- Meanings for source status codes or nested benefits based only on their names.
- A quote from a published rate, network confirmation from an NPI, or drug coverage from vocabulary matching.
- Permission to bypass licensed purchase review because the research interface is described as self-directed or the company has an agency license.
- An AI-generated ranking order or subset, hidden weights, unavailable licensed-agent capacity, completed checklist or agent authorization.
- A successful enrollment, coverage activation or resolved service issue without its actual authoritative evidence.
- A claim that passing structural/replay tests proves insurance suitability or consumer understanding.
- A proven incumbent lead time, existing distribution contracts, achieved caregiver brand ownership or published outcomes that do not yet exist.
- A conversion improvement that justifies suppressing external resources, changing ranking, or turning a partner's commercial preferences into the user's criteria.

## 6. Company work that cannot be replaced by code

| Owner/function | Work product needed |
|---|---|
| Founder/product/distribution | Caregiver-first content/search and segment research, then financial-advisor/publisher integrations; self-serve conversion learning, auditable-neutrality positioning, primary metric/retention window and quality guardrails |
| Data partnerships | Actual supplier samples, coverage matrix, contracts/rights, pricing, SLAs and exit terms |
| Insurance/legal | Written assessment of research/ranking and licensed purchase activities by state/product/channel; entity/personnel requirements, current licenses/appointments and agent-of-record setup; carrier approvals, disclosures/records and remediation paths |
| Domain quality | Source/rule/calculator interpretations, critical labels, suitability review, auditable-neutrality tests, error adjudication and publishable outcome methodology |
| Security/privacy | Data-role assessment, agreements, access/retention design, production threat model, incident program and approval of sensitive-data environment |
| Licensed purchase and servicing operations | Qualified staffing/routing, seasonal first-response targets and scheduled fallback, full-context sessions, required checklist/re-verification, carrier test access, reconciliation and servicing ownership |
| Finance/operations measurement | Actual compensation/chargeback terms, supplier/agent costs, complete human-minute accounting, cohort/retention denominator, contribution model and incentive separation |

These functions can use AI assistance and share personnel early. They require real decisions, agreements and accountable owners. The licensed agent is an explicit part of the purchase journey; software should remove repetitive preparation and preserve context while keeping that agent's required work complete and measured.

Consumer self-enrollment through a carrier link with our agency as agent of record is a future option, disabled initially. Create a separate later work package only after carrier/state-specific approval, quality evidence and validated attribution/status reconciliation. It must not become an automatic response to an overloaded agent queue.

## 7. Review rhythm and definition of done

For each work package, review: observed facts; new assumptions; implemented capability; tests and representative failure cases; scope gaps; required outside access; and the smallest next step. Update architecture decisions only when evidence changes them.

A package is done when its real input-to-output path works, its scope is honest, meaningful failure cases are tested, and its operating dependencies are resolved or explicitly blocked. A mock can test plumbing but cannot satisfy an actual-data, carrier, legal or model-quality gate.

Keep a decision log for unresolved matters: initial launch scope, supplier choice, exact completeness claim, first storage layout, identity strategy, criteria/weight confirmation, cost/reference comparisons, licensed purchase staffing/authority, seasonal response targets, retention window/labor allocation, privacy roles, model choice and deployment economics. Avoid choosing these by accident in generated code.

Also track the competitive/distribution assumptions: caregiver need and acquisition economics, reasons for leaving to outside resources, partner demand and integration effort, what evidence health systems require, and actual incumbent releases. Reassess the 12–24 month window rather than treating it as guaranteed runway.

## 8. Codex kickoff prompt

Use this after reviewing the architecture, in the intended fresh repository:

> We are building an unnamed, direct-to-consumer Medicare company under the operating model “self-directed research, licensed transaction.” Prioritize caregivers, then self-directed researchers, then Medigap shoppers. Position around auditable neutrality, not “unbiased AI”: the engine ranks from confirmed user criteria and verified data, storing inputs/weights/data versions with accessible full results/exclusions; compensation and partner attribution cannot influence ranking. The AI explains without reordering/adding/removing options or saying “you should buy.” Ready to purchase opens a licensed, appointed agent-of-record session with full transcript/profile/snapshot for review, re-verification and authorized submission. Primary metric: human minutes per effective, retained policy. Distribution is direct caregiver content/search, then financial-advisor software/publishers, then health systems after outcome evidence; the 12–24 month incumbent-response window is a hypothesis. Read ARCHITECTURE.md, DATABASE.md, CONTRACTS.md and BUILD_PLAN.md and the source evidence. Implement work package 1 first: a repeatable real CMS landscape/PBP query with lineage and a mapping/quality report. Inspect files/layouts before proposing a schema; investigate join discrepancies and preserve identifiers/null semantics. Do not invent the full schema, vendor adapters, quotes, enrollment or outcomes. Keep the archived prototype separate. Deliver the working slice, verified observations, unresolved questions and a minimal proposed persistence model for review. Tie later work to actual dependencies, acceptance evidence and the licensed-purchase boundary.

After that slice is reviewed, proceed through the packages. The ambition is the complete company; the engineering method is small, evidence-based increments.

## 9. Distribution and evidence workstream

Run this alongside the technical packages, in the same ordered sequence as the founding strategy:

| Stage | Work | Evidence before expansion |
|---|---|---|
| **Direct: caregiver content/search** | Useful caregiver-focused education, immediate research entry, after-hours save/return, secure parent sharing and explicit licensed handoff | Real caregiver comprehension, return and purchase behavior; reasons to use us or leave; no claim that outbound clicks prove external enrollment |
| **Software partners: financial advisors/publishers** | Embed the same engine/workspace with permissioned context continuity, partner entry/return and outcome attribution | Actual partner demand/agreements, validated handoffs and access boundaries; rankings identical regardless of partner fees; measured completed/effective policies rather than widget traffic alone |
| **Health systems / later patient portals** | Define and negotiate a scoped integration after evidence exists | Published suitability, complaint and retention methodology/results for AI-first research with licensed enrollment; required data/role approvals and actual partner agreement |

Within the assumed competitive window, build caregiver brand ownership, embedded integrations, self-serve conversion knowledge and outcome evidence. The channel sequence is deliberate: health systems are not an initial launch dependency. Research scale without proportional research hiring is the thesis; measure licensed purchase/service capacity separately.

Define outcome cohorts, follow-up/retention windows, denominators, independent suitability review and complaint handling before claiming success. Publish limitations and the licensed human role. Improve conversion through useful explanations, trustworthy comparisons and continuity; do not block Medicare.gov/carrier resources or optimize ranking for commission.
