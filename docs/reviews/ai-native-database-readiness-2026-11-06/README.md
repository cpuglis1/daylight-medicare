# Database readiness for the AI-native brokerage

November 6, 2026 · D95 evaluation and proposed actions · Local inspection and
fictional checks; no deployment or consumer release.

## Assessment

**Keep PostgreSQL and the compact research database. The next investment should
be a reliable evidence-to-decision service, with a permissioned customer plane.**
The physical database is in a reasonable place for the next engineering step.
The important gaps are authority, identity, durable workflow and application
integration. Moving the existing database unchanged to managed hosting would
carry those gaps with it.

This evaluates the [AI-native brokerage plan](../../company/AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md),
especially §§1–3 and 5, against inspected code, current database catalogs and
the retained verification receipts. It does not independently validate the
plan's legal conclusions, vendor capabilities or source-access claims.

Owner direction for this review: prepare for cloud and the AI-native operating
model; off-machine recovery and PITR are lower priority now. Keep the existing
local recovery evidence. Configure and test recovery on the selected cloud
target as part of cutover rather than making another local recovery project
the next workstream. Sources may be retired only after verified recovery.

## What is already worth keeping

| Foundation | Evidence and practical meaning |
| --- | --- |
| Compact PostgreSQL with original lineage | Live catalog: **29,374,584,511 bytes**, 315 source sets, 15 layers; all 18 compact indexes valid and ready. The three original evidence relations are compatible read-only views. This is a useful research foundation, not an application-ready domain model. |
| Source preservation and local recovery | The [November 5 redesign](../database-redesign-2026-11-05/README.md) preserved 17,767,179 source rows and 17,823,148 projections; full local restore and 1,283 logical checkpoint hashes passed. Those are earlier measured results, not rerun in this review. |
| Strict historical reproducibility | The [November 6 reconciliation](../dependency-reconciliation-2026-11-06/README.md) passed 759 queries and 756 checks while retaining both the historical 33-package lock and current 38-package lock. Preserve both revisions. |
| Independent deterministic mechanics | Existing comparison/ranking code, source locators, explicit unknowns and holds should be reused. Current commission-counterfactual and grounding suites pass. Tests do not establish recommendation acceptance. |
| Separate research and customer planes | Public evidence belongs in `daylight-data`; customer decisions, permissions and operations belong in a separately controlled database. The operations schema already separates commercial fulfillment from decisions. |
| Operations scaffolding | Decisions, licensed review, metadata-only traces, cases and enrollment events exist as code. **35 offline tests and the existing SQL assertions pass on PostgreSQL 18.6 in this review.** There is no `daylight_operations` database in the inspected local cluster, and the advisor does not use the package yet. |

The compact raw-source layout is appropriate for retained research. Add small,
typed serving tables beside it for frequent tools and joins. No further broad
rewrite or blanket index removal is justified by the evidence reviewed here.
The AI should call bounded capabilities; it should not choose arbitrary SQL or
receive a dump of the research archive as context.

## Fit with the four directions in the plan

| Plan direction | Database readiness | Main missing chain |
| --- | --- | --- |
| Complete brokerage | Partial foundation | Confirmed profile → accepted evidence and methods → reproducible decision → licensed review where required → separately authorized enrollment → verified status. |
| Continuing representative | General case/event tables only | Beneficiary-bound issues, supporting documents, representation authority, deadlines, evidence changes and resolution outcomes. |
| Family service | Not implemented by the operations schema | Separate beneficiary and helper identities; granular grants, revocation and audit. A caregiver label or visit digest is insufficient. |
| Service other AIs call | Internal research interfaces exist | Stable typed tools, partner/principal scopes, action permissions, idempotency and attributable receipts. MCP is a later interface over the same service. |

## Findings that most affect the transition

1. **The retained database is held research, not a released evidence service.**
   Live counts are zero for acceptance bindings, release manifests, active
   releases and released offerings. Some advisor publication/finding controls
   live in separate JSON files. Those controls need a coherent, exact-version
   authority path; neither a cloud move nor a database count should promote them.
2. **The read path deliberately rejects another machine.**
   `serving/repository.py` verifies a local socket, port 55485, database OID,
   cluster identifier and marker; `binding.py` selects a particular build-r3
   packet and receipts. The advisor's `comparison_research.py` constructs that
   local connection. A cloud binding must be a new verified revision, rather
   than weakening these local guards.
3. **Customer operations are a starting schema, not an enforced workflow.**
   In an isolated PostgreSQL 18 cluster, the app role could insert an
   `available` personal recommendation with empty inputs/evidence, no visit
   reference and no confirmation/review reference. It could create enrollment
   without a decision reference. No real recommendation was issued; these are
   missing protections to address before wiring the schema into the app.
4. **Enrollment events are not safe against normal callback behavior yet.**
   Fictional probes accepted duplicate callbacks and regressed `effective` to
   `submitted` when a later-arriving event was inserted. The current view uses
   the last inserted event. This needs explicit ordering, reconciliation and
   idempotency before vendor callbacks are connected.
5. **Identity and year contracts differ across boundaries.**
   Research IDs use `2026:H…:…:…`; operations use `H…-…-…` plus a year. Multiple
   research constraints/API types are fixed to 2026. The enrollment shape covers
   MA/PDP-style IDs and does not model a Medigap product/quote/application.
   This should be resolved in new serving and operations revisions before 2027
   or nationwide expansion, while preserving all 2026 evidence.
6. **Automation and observability are only partly connected.**
   Routine connectors are off. The release watcher discovers candidate links;
   it does not acquire, validate or publish a release, and its config lacks some
   MPF/provider release identifiers. The tracing wrapper and evaluation harness
   exist, but traces are not wired into the advisor and the five-suite harness
   is not named in the inspected repository workflow.

## Prioritized action list

These are recommendations, not a claim of implementation or authority to release
consumer outputs. P0 can be developed locally with fictional records and retained
evidence; actual cloud provisioning waits for the target decision.

| ID / priority | Action | Concrete completion evidence | Plan / existing backlog |
| --- | --- | --- | --- |
| **A01 · P0, start now** | **Make a portable, release-bound runtime package.** Separate logical dataset/release identity from machine OID/socket identity; retain strict local bindings. Declare code, dependencies, migrations **and compact-layout revisions**, source manifests and bootstrap files. Add a separately verified remote connection factory, dedicated roles, TLS and bounded pools. | A clean isolated package with fictional fixtures starts without `/Users/cep4u` or the original repository; local wrong-target checks still fail; a new target can verify the selected release without editing old receipts. Managed-role/privilege compatibility is tested on the chosen target before real cutover. | §5 database/hosting; P01–P03/P12 |
| **A02 · P0** | **Define the serving domain contract.** Reuse the current catalog, critical-benefit preparation and identity adapters. Add typed/versioned offerings, availability/restrictions, benefit terms and conditions, provider sites/network assertions, drug/formulary/pharmacy terms, cost assumptions and policy rules as needed by the MVP. Include effective/observed dates, scope, state and exact lineage. Define year-aware IDs and crosswalks, including Medigap. | All 72 retained offerings and fourteen feature families map without losing the 41 meanings or 229 holds. A new-year fixture cannot join to 2026 by accident. Missing/qualified/conflicting evidence round-trips without zero-filling or false coverage. Original research rows remain untouched. | §§2/5 data/engine; P06–P08 |
| **A03 · P0, before supported personal outputs** | **Complete exact-purpose release authority.** Load independently reviewed source-use, method and output receipts; replay original authority; select immutable manifests through an audited mechanism. Make publication, comparison, ranking and recommendation permissions distinct. Unify the application and database view of those bindings. | An authorized exact output works in a fixture; held, stale, revoked, mismatched, wrong-year and unsupported-purpose outputs fail closed at the service. Keep r4/r1 acceptance narrow; no blanket promotion of research. | §§2/5; P09 |
| **A04 · P0** | **Expose typed tools with verification receipts.** Use plan lookup, identity resolution, supported network/formulary checks, deterministic cost scenarios and checklist status as separate capabilities. Return evidence/version, scope, freshness, conditions, holds and a result receipt. Pin evidence consistently across a decision and invalidate affected results after corrections. | One fictional case and one material hold/correction run end to end. Provider identity never becomes network coverage; drug identity never becomes formulary/personal cost. Invalid inputs, unavailable checks, stale receipts and unauthorized tool calls are rejected. The model cannot invent eligibility or arithmetic. | §5 agent/engine; P07/P08/P10 |
| **A05 · P0, before customer cloud use** | **Finish the customer identity, facts and permission model.** Separate actor, beneficiary, case and profile revision. Reference specific saving, AI-transfer, sharing, handoff and enrollment permissions, with scope, version, expiry and withdrawal. Enforce ownership in services and database access paths; broad app roles alone are insufficient. Define retention and deletion treatment for sensitive inputs, journals, documents and metadata. | Two fictional beneficiaries cannot access each other's records. Revoked family/action grants stop access. Save-off/restart tests do not silently persist chat. Profile migration has an explicit mapping and reconciliation; protected guest stores remain intact. Legal retention exceptions are documented before durable customer records are enabled. | §§1/6; P10/P12/P15 |
| **A06 · P0** | **Connect and harden decision, review and checklist records.** Store minimized confirmed input revision, evidence release, method/policy/model/prompt versions, candidates/exclusions, keep/defer outcomes, reasons, unresolved checks and tool receipts. Bind licensed review to that exact decision and verified reviewer identity. Checklist entries need item, supporting event/evidence, time and status rather than just `covered: true`. Persist critical workflow receipts durably. | Replay yields the same substantive decision; corrections create a new revision and invalidate old approval. An `available` recommendation cannot be written through the authorized production path without the applicable evidence/confirmation gates. Missing durable writes hold the action. Whether review precedes submission and which checklist record is legally sufficient remain owner/counsel decisions. | §§2/3/5; P10/P13 |
| **A07 · P0, parallel** | **Turn existing evaluation and traces into release controls.** Run offline suites on prompt/model/rule/data changes and bind results to exact versions. Add serialized-request commercial canaries, tool grounding, stale-release/permission tests and SQL probes for the gaps found here. Wire minimized trace context across turn, tool, decision and review. | A candidate's evaluation receipt names its exact inputs; injected commercial context and cross-user access fail. No prompt/response/transcript content enters telemetry. Dropped diagnostic traces are observable; decision, consent, budget and action receipts have a stricter durable-write policy than optional telemetry. | §5 evaluation/observability; P03/P10/P12 |
| **A08 · P1, after the first complete path** | **Automate versioned data refresh and exception review.** Reuse immutable archives, adapters, job fencing, source STOPs and comparison caches. Add discovery → acquisition → validation → transformation → reviewed release, with diffs and rollback. Add the missing release identifiers. Evaluate the plan's Dagster/dbt adapters against one existing pipeline before replacing working machinery. | One allowed source revision builds a new isolated snapshot; a failed/partial run cannot replace the last good release. Every material disagreement, missing dependency and stale result gets an explicit disposition. Automated checks and sample review do not override exact source/method/purpose gates. Routine network access remains off until its scope is authorized. | §5 data; P06–P09/P15 |
| **A09 · P1, before moving source objects** | **Complete the private archive relocation contract.** Enumerate exact source closure, hashes, sizes, original locators, rights/STOPs and release dependencies. Implement the selected object-store path with streaming/resumable transfer and read verification. Keep local originals. | All selected release dependencies resolve with matching bytes on the target. Large objects are supported: the existing `S3Archive.put` explicitly caps at 5 GiB, below the retained 5,813,006,603-byte compact dump. No GCS archive adapter was found. Database and object manifests remain linked, without uploading the whole workspace. | §5 data/hosting; P01/P02/P12 |
| **A10 · P1, before enrollment integration** | **Harden enrollment and case events around the chosen rail.** Require action-specific authorization, identity, supported product, agent-of-record and applicable decision/review references. Add vendor event IDs, signatures, idempotency, observed/effective time, explicit transition/reconciliation rules, failure/retry ownership and a durable outbox for authorized outbound work. | Duplicate, delayed, replayed and out-of-order callbacks leave the correct state; cancellation and rejection are explicit; a held decision cannot silently become a submitted application. Sandbox receipts prove submitted → accepted → effective and an exception path. Commercial statements remain downstream and separately permissioned. | §§2/5 enrollment/operations; P13 |
| **A11 · P1, before cloud sizing/cutover** | **Benchmark the real tool workload.** Measure plan lookup, site/network and drug/pharmacy joins, cost scenarios, release checks and decision writes under concurrency. Use query plans to add only justified indexes or derived serving tables; measure storage and refresh cost separately. | A stated workload yields latency distributions, timeouts, query plans, pool bounds and storage growth. The current 29.37 GB and prior single-query timings inform sizing but do not establish national or concurrent performance. Cloud version, roles, secrets and deployment are tested on the actual target. | §5 database/hosting; P02/P03/P12 |
| **A12 · P2, preserve extension points now** | **Extend proven primitives into advocacy, family and partner service.** Add issue/document/deadline/representation records, authorized relationship grants and scoped partner/MCP access over the same tools. Keep acquisition attribution and economics outside decision retrieval and model context. | A permissioned change → task → review → resolution cycle is attributable and revocable. Another assistant can request only its delegated capability. Broader advocacy, family sharing and partner actions wait for their own operating/privacy proof. | §1 four directions; P14/P15 |

### Recommended sequence

1. Start **A01 and the A02–A04 contracts**, using the retained 72-plan catalog.
   Prove a portable, bounded evidence-tool path, including a held response.
2. Build **A05–A06** against an isolated operations database with fictional
   records. Join confirmed inputs, tool receipts, decision, checklist and review
   into one reproducible case. Do **A07** alongside this work.
3. Use that measured path to implement **A08–A11** and prepare the selected cloud
   target. The cloud decision should not block the contracts or offline proof.
   Real source migration and real customer processing retain their exact gates.
4. Expand into **A12** after the Collier journey works. Do not make a national
   refresh platform, family product or MCP launch a prerequisite for the first
   complete pilot.

## Decisions and reviews still needed

- Cloud account/provider, region, budget and runtime/operator ownership. Verify
  the actual contracted services, access controls and processing terms; this
  review does not certify a BAA or legal suitability.
- Record the owner's preferred human-review level as a numbered decision;
  determine when review must occur and what authority supports it. The plan's
  Option B is not itself permission for post-submission approval.
- Exact relevant-market scope and source/method/output acceptance for the
  supported Collier tasks, including usable doctor, medicine, Medigap and
  eligibility evidence. Full historical L03 reconciliation remains preserved
  research, rather than a blanket prerequisite for a narrowly accepted output.
- Counsel/operating decisions on required records, retention, checklist evidence,
  enrollment route and representation authority. Keep raw conversation visit-only
  under current rules while these questions are unresolved.

## Verification actually run

| Check | Result / retained evidence |
| --- | --- |
| Catalog inspection | One repeatable-read, read-only transaction, 15-second timeout. [SQL](evidence/catalog.sql), [result](evidence/catalog.json). No source or customer writes. |
| Operations Python tests | **35 passed**, Python 3.14.7. [Log](evidence/operations-tests.log). |
| Existing operations migration and SQL assertions | **Passed on PostgreSQL 18.6**, disposable cluster removed afterward. 21 expected rejection checks and four positive assertion groups. [Log](evidence/operations-pg18.log). This closes the earlier PG18-test gap; it does not deploy operations. |
| Five-suite evaluation harness | **All five passed**: 14 fictional personas/1,244 assertions; checklist scorer; factual grounding; commission counterfactuals; abstention. [Final report](evidence/evaluation-r2/report.json). Injected model replies, zero paid/live calls. |
| Additional operations gap probes | **Four missing guards reproduced**, using fictional app-role writes in a disposable cluster, then rollback/removal. [SQL](evidence/operations-gap-probes.sql), [results](evidence/operations-gaps.jsonl), [runner](evidence/run_operations_gap_probes.sh). A true result means a gap exists. |
| Initial harness attempt | Failed because a relative output path was resolved under a test subprocess and sandboxed loopback fixtures could not bind. Corrected invocation uses an absolute output path and approved fictional loopback execution. [Initial report retained](evidence/evaluation/report.json); no product code was changed to make the suites pass. |

The full database verifier, source re-extraction, model quality, load test,
cloud install and actual target migration were not rerun/performed here.
The [input manifest](evidence/inputs.json) pins the primary inspected files;
the [result summary](evidence/summary.json) records this review's outcomes.

D64/D73 review: recommendations preserve path-first comparison, unknown evidence,
revisable decisions, keep/defer and uncompensated outcomes, separate permissions
and commercial isolation. No UI, source acceptance, protected variant/store,
41-meaning contract, consumer release or running service was changed. The next
proof is one supported, inspectable end-to-end case, with its holds preserved.
