# D87 local comparison milestone

November 1, 2026. The owner authorized continuing items 1–5 locally. The updated
advisor is active at **http://127.0.0.1:8893/**. Its separate internal source
workspace is **http://127.0.0.1:8893/research.html**. This is a working local
milestone, not completion of the entire comparison or L03 program.

## Implemented behavior

| Work | Actual implementation and limits |
| --- | --- |
| PostgreSQL serving | Guarded, snapshot-bound, read-only queries over the existing `daylight_research_2026_r2` cluster. Lists the exact 72 retained L02 Collier MA identities; inspects L03 native claims/conditions and L09 contract observations with raw parents, provenance and explicit continuation. Query paths use existing indexes and bounded pages. This is not an accepted all-market or all-fifteen-layer consumer service. |
| Profile and comparison methods | Reuses the existing profile and all 41 meanings/14 gaps. Adds finding-specific input leaves, exact identity bindings, explicit scoped must-haves and Decimal scenario mechanics. Current versus historical/intended reports and explicit none versus unknown are preserved. No guessed weights, automatic must-haves, utilization or personal annual totals. Real methods and findings remain held. |
| Actual drug identity seam | Operator-only exact RxCUI lookup over 4,547 retained L05 dictionary rows. Product, pack, partial historical and missing-ID states preserve native strength/form/type/history and raw-parent hashes. No free-text resolver, NDC conversion, clinical substitution, formulary/offering membership or automatic profile binding. Absent durable source registration remains explicitly unregistered; all consumer purposes remain held. |
| Accepted reference | Every exact request runs the original unmodified `l03_scoped_reference.lookup(research=False)` in a fresh isolated process, including its original ancestry/code/manifest/receipt/allowlist/revocation checks. Preserves the entire original result, related schedules, qualifications, evidence, six dispositions and masked disputed values. Authority is only the already accepted 535-entry r4 reference subset, not the research DB or personal comparison. |
| Display | Optional inline preparation at the existing advisor summary; one composer, normal conversation/AI stages, drafts and saving controls remain. A separate internal workspace selects up to three actual source offerings in source order, shows their native fields and paginated evidence, and opens the exact accepted reference on explicit request. Empty typed condition objects are expressly not evidence of no conditions. No source record enters consumer alternatives or model context. |
| Source reconciliation | New additive [r10 work packet](../../docs/data/l03-ma-benefits-2026-11-01-comparison-pilot-r10/README.md) prepares 71 canonical obligations, retaining 72 representations, 81 observations and 19 source dispositions. Exact CMS/carrier source pages, clause/parent reconstruction, selective-deductible context and proposed mappings are inspectable. Zero new entries are accepted; no whole-offering pilot is complete. |

The owner-bound review route is read-only with respect to the conversation: it
checks the signed profile/current chain/head and latest trusted journal response
before and after research. It returns only derived comparison plus continuation.
It cannot unpause the advisor or overwrite current saving/privacy choices. A
newer response at the same signed head also invalidates the old snapshot. Fixed
errors do not disclose source exceptions, credentials or customer values.

## Verification

- [Final advisor suite](full-suite-final-r3.log): **457 Python tests passed** in
  45.136 seconds, including nested Node interaction/security cases. Do not add
  nested cases again to the Python count. Earlier failed runs are retained;
  fixture contract omissions and an explicit-no-prescriptions fill dependency
  were corrected before the final run.
- [Actual-data HTTP journey](actual-journey-r3.json): **38 checks passed** with
  the real retained research build and a new temporary fictional guest DB.
  Covers all 41 meanings/14 gaps, a doctor correction, actual 72 identities,
  condition/raw lineage, pagination, exact original r4 lookup and related hospital
  endpoints, historical restricted subset visibility, wrong-year/stale rejection,
  no research-to-consumer promotion, held recommendations and sensitive-save
  minimization. It uses no paid AI or existing customer reports.
- [Serving audit](../../infrastructure/daylight-data/reports/research-serving-2026-11-01-r2.json)
  independently traverses the 72 distinct IDs in pages 20/20/20/12, first/last
  details and continuation, with exact build hashes and query plans.
- **49 isolated serving/identity tests passed** (34 new identity plus 15 serving).
  A separate agent independently reran them and reviewed source/projection,
  lineage, guard and unknown/pack boundaries without DB access.
  [Actual identity audit](../../infrastructure/daylight-data/reports/research-identity-2026-11-01-r1.json)
  passes **21 checks**, with final query plan, exact physical/source/code binding,
  candidate parent hashes, unregistered source-access state and held purposes.
- [Pilot tests](pilot-tests.log): **17 passed**. Root reproduced all eleven
  generated JSON files [byte identically](pilot-reproduction-check.json) and
  inspected the four retained SB/EOC page images. This is technical review of
  preparation; no independent policy ground truth or semantic acceptance is
  claimed.
- Independent review of the HTTP/reference/rendering integration found no
  remaining material issue. A test exposed a renderer boundary that could show
  an unmasked held value in a malformed response; the renderer now rejects that
  response before replacing the previous view. The real original adapter already
  enforced masking. Exact source text is rendered as text, never HTML.

The final actual journey observed a 24.990 ms catalog request and 17.094–32.808 ms
bounded detail requests after local warm-up. Accepted-reference replays took
356.590–426.175 ms. Earlier independent first/last reads took 560–587 ms; these
are individual local measurements, not production latency percentiles. Final
identity replay measured 22.682 ms for guarded lookup and 1.055 ms SQL execution,
separately from prior measurements in its receipt. No schema/index changes were
made to obtain these results.

## Browser and interaction checks

The disposable :8914 fixture used real public research plus a temporary guest DB,
with clearly labeled mocked AI and no paid calls. Desktop, 768×1024 tablet and
390×844 phone views were inspected. Phone body width and scroll width both
measured 390 pixels; source comparisons stack fields with explicit plan labels.
Selection is unranked, selecting H5652-002 before H5652-001 still displays source
order, and continuation appended records rather than replacing earlier evidence.

The main fictional advisor path reached its genuine optional summary after
explicit reports/deferred ZIP. Opening comparison preparation showed reported
Original Medicare, distinct no-doctor/no-prescription checks and keep/defer
choices. Returning preserved the summary and an unsent draft exactly. This
does not establish consumer comprehension, physical keyboard behavior or
assistive-technology execution.

| View | Screenshot |
| --- | --- |
| Internal comparison, desktop | [research-desktop.png](research-desktop.png) |
| Internal comparison, tablet | [research-tablet.png](research-tablet.png) |
| Internal comparison, phone | [research-phone.png](research-phone.png) |
| Original accepted reference with qualifications | [reference-desktop.png](reference-desktop.png) |
| Advisor preparation, desktop | [preparation-desktop.png](preparation-desktop.png) |
| Advisor preparation, tablet | [preparation-tablet.png](preparation-tablet.png) |
| Advisor preparation, phone | [preparation-phone.png](preparation-phone.png) |

## Activation and preservation

The existing private PostgreSQL cluster was confirmed stopped, physically bound
to its recorded cluster identity, and started using its documented private Unix
socket. No init, clone, stop/restart, domain mutation or schema migration was
performed. The historical rejected whole-cluster stop/clone operation was not
retried. The existing research database, original test DB, source stops and all
sealed source/code parents were preserved.

Only the advisor :8893 launchd job was reloaded, using the already installed
project Python/psycopg and `--local-research`. Initial immediate bootstraps returned
OS error 5; the original job was restored, then separate bootout, old-process
exit confirmation and bootstrap activated the updated job. Attempts are retained
in [runtime-activation.json](runtime-activation.json) and
[original recovery](runtime-original-recovered.json). [Final runtime checks](runtime-after.json)
pass all nine checks, including real database and original-reference reads through
the active job. That health audit created and deleted only its own empty session;
it did not load existing customer reports. No other Daylight job, protected guest
store path, model/budget policy or shared ledger was changed.

No cloud resources or paid AI were used. New source observations, identity
candidates and technical tests create no acceptance. The exact accepted r4
reference remains 451 numeric source observations plus 84 qualified notes and
six conservative dispositions; all 153 disputed claims stay held. The global r9
denominator remains **143,505 claims + 249,065 conditions = 392,570 obligations**.

[Before hashes](SOURCE_BEFORE.json), targeted before-images, final source hashes
and [verification receipt](VERIFICATION.json) bind this milestone. Shared engine
pins and original r4 replay were rechecked. The Impeccable detector's one narrow
persisted exception is literal malicious image markup in a security test, not a
shipped image; its existing false-positive disposition is preserved.

## Remaining work

The 1–5 program is not complete. Important internal work remains:

1. Finish the selected whole offering's 4,675 canonical obligations and the other
   required whole-offering representatives/layout strata, preserving linked
   service/condition meaning and the exact global inventory. The 71 prepared
   obligations remain pending, with ten condition families and 30 proposed
   mappings unreviewed. Missing source predicates remain required, not waived.
2. Complete actual provider/practice/site and customer-confirmed drug/fill
   resolution, assistance/administrative and transition dependencies, and exact
   cross-category coverage episodes. The new dictionary lookup is only a
   bounded exact-ID seam.
3. Review finding-specific input sufficiency, policy/domain rules, must-have
   interpretation and cost scenarios against independent expected records;
   integrate exact accepted methods and consumer-purpose releases. No invented
   authority object or whole-offering acceptance can replace this.
4. Extend the real serving projection only with genuinely released evidence for
   its exact purpose, then check complete personal comparison journeys and
   consumer comprehension. The advisor currently offers preparation; the
   existing five 2027 samples remain separate and unvalidated.
5. Before hosting: establish target-specific DB/source authority, roles, secrets,
   private network/pooling and object-storage adapters, retention and a full
   backup/restore rehearsal. Local measurements do not prove an 8 GB managed DB
   will fit. The last full build measured about 58.013 GB and its compressed dump
   5.214 GB; no full clean restore or off-machine recovery is certified here.

This work improves D73 self-service and inspectability while retaining
consequential conditional intake, coverage-path teaching, independent outcomes
and permissioned continuity. Actual comprehension, independent policy/source
ground truth, purpose acceptance and complete personal results remain explicit
gaps. Genuine source-access blockers must stay separate from this unfinished
internal work. D64 commercial economics enter none of the methods or ordering.
