# D87 next local comparison increment

Started November 1; checks continued November 2, 2026 (America/New_York).
The owner authorized continuing the whole-offering pilot and identity work
within the local 1–5 program. This increment adds source preparation and callable
identity tools. It does not complete that program or activate a new customer
journey. Revision paths retain their original start date.

## What is implemented

- The additive [r11 packet](../../docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/README.md)
  accounts for H5652-002's exact 4,675 obligations and hydrates every retained
  source link. Its 217-ID inpatient preparation is disjoint from r10's 71-ID
  deductible preparation. Both are work selections, not verified-benefit counts.
- [Literal drug discovery](../../infrastructure/daylight-data/src/daylight_data/serving/drug_candidates.py)
  searches the retained 2026 dictionary by name, optionally strength/form,
  without requiring a known RxCUI. Literal SQL wildcard characters are escaped;
  there is no fuzzy ranking, unit conversion or automatic identity selection.
  Packs, missing source details and historical terminology remain explicit.
- [Provider identity lookup](../../infrastructure/daylight-data/src/daylight_data/serving/provider_identity.py)
  accepts an exact NPI or retained entity key. It preserves the composite
  directory's separate entities, roles, sites, missing actor records and
  conflicts. An NPI is not an office, network membership or appointment promise.
- [Explicit drug identity choice](../../alternatives/advisor-first/identity_resolution.py)
  associates a selected source candidate with a fictional or caller-supplied
  trusted profile only after an explicit confirmation. It binds owner, subject,
  item, current report revisions, year/scope, candidate and source snapshot;
  it expires in memory and rechecks source/report state before confirmation.
  Corrections invalidate affected choices. Source identity selection does not
  establish clinical equivalence or consistency with the person's reported
  strength/form; those remain separate reconciliation work.

These identity modules are operator/callable seams. They are not connected to
HTTP routes, the customer UI, the conversation controller or AI tools. Caller
authentication and trusted profile loading remain composition responsibilities.
No new source rows enter model context or customer plan alternatives.

## Whole-offering evidence

The frozen inventory remains **392,570 global obligations**. The first offering
remains **1,778 claims + 2,897 conditions = 4,675**, with **4,659 pending and 16
required missing**. This work changes zero inventory dispositions and accepts
zero entries. The 535-entry r4 reference, its six conservative dispositions and
all historical held claims remain unchanged.

The source capture retains 6,577 observations, 2,806 source-disposition records,
2,141 clauses, all 206 carrier pages, all 93 native CMS services, 93 earlier
retained service records and 2,377 field dispositions. Native quote and logical
parent reconstruction is exact against the frozen extraction. Printed semantic
meaning remains a separate check: direct EOC extraction has shifted glyphs, so
the source-first preparation inspected original rendered pages.

A fresh-context agent froze the [carrier-only candidate](../../docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/independent-expected/FREEZE.json)
before reading CMS, canonical obligations, previous comparisons or producer
outputs. It retained nine observations, 44 condition candidates, 51 passage
locators and ten gaps after inspecting 39 original rendered pages. The initial
producer's prior exposure is separately disclosed and its transcription remains
unchanged. Fresh context and agent corroboration do not establish expert approval.

The inpatient derivation retains complete CMS 1a/1a1 objects and conditions.
Six nominal component comparisons match, while every complete-meaning outcome
stays `insufficient_evidence`. All 44 fresh condition candidates remain unresolved
(14 proposed span mappings, 30 not compared to the initial producer spans), and
all ten gaps remain attached. [Technical QA](../../docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/comparison-review/README.md)
discloses prior r10 authorship and grants no domain or source acceptance.

The [offline reproduction](inpatient-reproduction-review.json) reproduced all
nine derived artifacts and their receipt byte for byte. The
[subpacket-preservation check](r11-subpacket-preservation.json) checked all
304 source-preparation, 52 fresh-candidate and 12 technical-review members.

## Corrections retained

1. The first native capture stopped at the frozen reader's unsupported
   `SOURCE_REQUIREMENT` prefix. A new, exact-allowlist read retrieves only the
   offering's 16 retained missing-requirement metadata records. It supplies no
   missing evidence; the frozen reader and failed run remain intact.
2. The initial relationship aggregate counted 2,152 endpoint/relation triples.
   Native identity also includes `source_id`: the original captured batches
   contain **2,476 source-scoped rows**, including 324 additional source bindings.
   No source row was lost. The stopped derivation, earlier receipts, producer
   history and exact [grain correction](../../docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/RELATIONSHIP_GRAIN_CORRECTION.json)
   are preserved separately.
3. Independent identity-choice QA found that a source STOP already present at
   offer time and expiry occurring during a source read needed stricter checks.
   Both are fixed and covered by adversarial tests. Confirmation rejects
   stopped/unknown policy states and rechecks expiry after the source read.
4. Independent provider QA found that returned source locators could disagree
   with their retained raw parent while passing the initial operator guard.
   The corrected r2 validates raw parent hashes, native columns, selected source
   bindings and every normalized claimant, and rejects foreign/duplicate locators.
   Independent QA reproduced the original tamper and a self-consistent foreign
   entity with a recomputed raw hash; both now reject. Legitimate missing data
   remains partial. Historical r1 code/tests are retained in `code-history/`,
   and the original actual-read report remains unchanged. This synthetic
   reproduction did not establish corruption of the real source records.

## Verification and practical limits

The [474-test advisor regression run](advisor-full-suite-final.log) passed before
the later concurrent chat edits, including 17 focused identity-choice tests.
The latest isolated [identity-choice check](identity-choice-unit-tests-r3.log)
passes all 17 tests. The corrected [infrastructure identity suite](identity-infrastructure-pytest-r2.log)
passes 155 tests (58 provider, 48 drug discovery, 34 exact-drug and 15 serving).
An earlier root invocation used system Python/unittest for these pytest-based
files and failed at import; its log is preserved, and the corrected run uses
the existing infrastructure virtualenv and pytest. Actual read-only cases are pinned in the
[corrected provider report](../../infrastructure/daylight-data/reports/research-provider-identity-2026-11-01-r2.json)
and [drug-discovery report](../../infrastructure/daylight-data/reports/research-drug-candidates-2026-11-01-r1.json).
The latter records 33 assertions across eight queries/pages; the original
provider r1 report records 27 assertions across five cases. Provider r2 passes
34 checks across those same cases, including eight indexed original-SQLite
observation row cross-checks. Counts, native site IDs and identity states match
r1. Correction replays are separate revisions, not replacements for old receipts.

[Source preparation](whole-offering-unit-tests.log) passes 12 tests;
[technical source/comparison QA](all-inpatient-review-unit-tests.log) passes 13.
The [459 fresh-packet checks](fresh-source-validation.log) establish integrity
and omission accounting only. Counts are distinct checks with overlapping
scope, not additive evidence of source acceptance or consumer comprehension.

The [latest composed actual-data audit](actual-identity-choice-r4.json) passes
11 checks in 82.543 ms, using the final corrected serving bundle. It uses public dictionary labels mirrored in an
explicitly fictional, in-memory profile. Discovery, explicit choice, correction
invalidation and forgetting are checked together. It is not a real customer's
confirmation, a clinical match, an HTTP journey or an AI interaction. Earlier
receipts remain historical when the code-bound serving snapshot changes.

Actual drug discovery reads were approximately 10–27 ms in the retained r1
report. Corrected provider r2 reads ranged from about 110 ms to 5.37 seconds; it is not ready
for a subsecond consumer promise. Bounded entity/role pagination preserves
snapshot identity. Location/site caps are reported as partial; there is no site
continuation cursor, so callers must retain that limit rather than infer full
site coverage. Neither test fixtures nor these isolated timings establish p95
latency under load.

All reads use the existing exact PostgreSQL physical-target/build/source guards,
READ ONLY transactions and the research-reader role. There is no database/domain
write, source acquisition, paid AI call, real guest/profile-store read, ledger
reset, cloud provisioning, service restart or new UI behavior in this increment.
The existing :8893 activation belongs to the preceding milestone. No protected
variant, saved customer report or original accepted-reference adapter is edited.

The [final verification](VERIFICATION.json) binds the final code/check receipts
and the [source-after accounting](SOURCE_AFTER.json). This workstream changes
three operating documents among the 209 preexisting baseline files; their
before-images are retained in `before/`. Later concurrent chat-refinement edits
were observed in other baseline files and are preserved with their own
[observation](concurrent-workspace-observation-r1.json). They are neither reverted
nor attributed to this increment. The 474-test result predates those additional
edits; later checks must bind the source actually tested. Tests do not imply
owner approval.

Two broad rechecks overlapped those concurrent edits. The first run's local
fixture sockets were sandbox-blocked and its two UI fragment wrappers failed
against changing code/tests; [diagnostics](concurrent-suite-diagnostics-r1.json)
confirm all 17 identity tests passed unchanged. With local fixture sockets
allowed, the [second run](advisor-concurrent-workspace-suite-r2.json) executed
481 tests with one reveal-wrapper failure while that test and CSS changed.
The updated [Send/reveal wrappers then both passed](concurrent-fragment-check-r3.json)
against stable before/after hashes, without editing those concurrently owned
files. Neither changing-snapshot run is described as a clean full current-UI
certification. The new backend identity/source checks above are independently
passing; the concurrent frontend change retains its own validation responsibility.

## Remaining work within 1–5

Complete substantive whole-meaning reconciliation for this offering, including
the unresolved linked conditions, remaining 4,387 obligations outside the two
component selections (including the 16 required missing predicates). Continue all
required whole-offering representatives/strata and inventory-wide work; obtain
independent interpretation review and exact new-release acceptance.

Compose provider site selection and the identity tools with authenticated current
profiles, deliberate correction and safe lifecycle handling before any customer
route. Then add source-authorized plan comparison display and actual end-to-end
AI/chat journeys under the existing permissions and purpose gates. Finding-specific
question meanings remain tied to the existing 41 meanings; no new questionnaire
or hidden ranking score is introduced. Exact identity never supplies missing
coverage evidence. Personal cost totals, ranking, recommendations, quotes and
enrollment remain held.

Cloud migration is not undertaken here. Target-specific roles, secrets, network
access, pooling and restore/recovery checks remain future deployment work under
the owner's instruction to report account identifiers and cost before provisioning.
