# Reusable local comparison backend

This backend turns retained comparison records and source artifacts into repeatable, incremental research batches. The same code handles every exact offering; offering IDs and catalog paths belong in manifests. It does not approve source interpretations, finish an original by implication, accept a reference release, recommend a plan or publish consumer results.

The owner authorized this D85/D87 engineering work on November 3, 2026 to reduce repeated comparison work, then evaluate the requirements for future recommendations/comparisons. D64 independence, D73 reported-versus-verified gates and the entire D77 inventory remain binding. The current profile, 41 conditional question meanings, chat, PostgreSQL data and protected interfaces are unchanged.

## What runs automatically

| Step | Reusable behavior | Boundary |
| --- | --- | --- |
| Inventory | Verify the sealed r9 source bytes and build a small SQLite index once; repeat runs verify its complete row digest without decoding the master again. | All 392,570 originals across 72 offerings remain required. |
| Source discovery | Resolve cited hashes from explicitly selected local manifests and actual file bytes; preserve false-claim, limit and missing-file diagnostics. | Finding bytes does not establish their meaning or applicability. |
| Preparation | Verify catalog pins, preserve every record/component and optionally group exact identical original-ID sets. Publish a new, atomic batch directory with full lineage. | Grouping is a work envelope, never a completeness or equivalence decision. |
| Normalization | Dispatch through a versioned registry: strict r9, explicit component bundles, complete carrier price cells, native literals and named source gaps. | Unsupported qualifiers and native meanings stay unresolved. No universal coded enums, currency guesses or missing-to-zero conversions. |
| Comparison | Replay every component through the exact sealed r9 guard. Exact reviewed mappings require complete observation hashes and actual receipt bytes. | Matching prices, stored producer outcomes and templates cannot substitute for complete meaning. |
| Incremental work | Reuse an evaluation only with unchanged normalized input, exact original bindings, source dependencies, rules, adapters, runtime and review fingerprints. | No acceptance or independent review is cached into a different scope. |
| Review | Produce concrete exception paths, dependencies, source-review work and added/removed/changed tasks; distinguish unchanged records in a changed container. | Every task and original survives grouping. Review work groups are not counts of distinct benefits or verified facts. |
| Query/export | Query completed snapshots by offering/status and export tasks, queues, the entire no-input backlog and byte hashes. | Results remain research-only; a failed batch cannot replace the last complete snapshot. |

## Run locally

The existing environment now includes pinned `jsonschema==4.25.1` and its locked dependencies. No credentials, AI calls, cloud resources or network access are needed to run the pipeline. From the repository root:

```sh
PY=infrastructure/daylight-data/.venv/bin/python
CLI=infrastructure/daylight-data/tools/comparison_pipeline.py

$PY -B "$CLI" prepare \
  --spec infrastructure/daylight-data/comparison-pipeline/first-plan-preparation-spec.json \
  --output infrastructure/daylight-data/comparison-pipeline/prepared-next

$PY -B "$CLI" run \
  --manifest infrastructure/daylight-data/comparison-pipeline/prepared-next/batch-manifest.json \
  --workspace infrastructure/daylight-data/.local/comparison-work

$PY -B "$CLI" status \
  --workspace infrastructure/daylight-data/.local/comparison-work \
  --offering 2026:H5652:002:000

$PY -B "$CLI" queue \
  --workspace infrastructure/daylight-data/.local/comparison-work --limit 10

$PY -B "$CLI" export \
  --workspace infrastructure/daylight-data/.local/comparison-work \
  --output infrastructure/daylight-data/comparison-pipeline/review-export-next
```

Preparation/export destinations must be new directories. Repeat `run` against the same work directory for cache reuse. Use `tasks --offering ... --status ... --limit ...` to inspect actual records; use `diff --before RUN_ID` to compare completed snapshots. `status` describes the last checked snapshot, not an assertion that source files have remained unchanged since that run; rerun the manifest to recheck freshness.

`sources --spec SPEC --seed MANIFEST --seed ANOTHER_MANIFEST --output NEW_REPORT` discovers source bindings from explicit local references before preparation. It never scans unrelated directories or treats discovery limits as evidence that a source does not exist. The resulting report is inspected and its byte-verified bindings added to the preparation spec; source meaning remains unaccepted.

The package also supports `python -m daylight_data.comparison_pipeline` when `src` is on `PYTHONPATH`, and the `daylight-comparisons` entry point when the package is installed.

## Cache and review contract

`inventory.sqlite3` contains minimal canonical identity/hash metadata, not the 3.4 GB expanded source snapshot. `comparisons.sqlite3` contains content-addressed artifact/normalization/evaluation caches, completed run records and indexed task results. These are local work stores alongside the existing PostgreSQL evidence infrastructure; they do not replace PostgreSQL or alter accepted serving data. They can be rebuilt from the pinned sources and manifests. Archives and published source documents are byte-hashed on each run.

A task ID depends on the exact offering and stable source record ID. Its content fingerprint includes the complete input; source changes therefore update the same task. Cache keys bind full components, original hashes, actual source files, exact mapping entries/receipts, adapter/rule code and dependencies, Python/Decimal versions and current source-review receipts. A container edit that leaves an individual record unchanged is reported as container rebinding, without inventing a material change to that record. Changed source context, parent/proof data, condition, unit, network, variant, rule or review does invalidate the affected work even when the dollar amount stays equal.

Strict r9 schema checks remain separate from mechanical comparison. Every component in an explicit bundle is evaluated; one unresolved component keeps the task held. Complete price cells retain qualifiers and literal tokens; they do not fabricate fully interpreted benefits. Native literals preserve null versus zero and exact decimal input without executing native rules. Strict r9 numeric provenance preserves its original JSON number type only with exact decimal serialization round trips; values that cannot safely round trip are quarantined with their source context.

Independent source reviews support two explicit contracts. V1 (`daylight-source-review-receipt/1`) retains exact task/content/rule/mapping/source/component bindings. V2 (`daylight-source-review-receipt/2`) binds the stable task, complete `source_meaning_sha256`, every component ID, named reviewer/review ID, explicit `source_reviewed` or `held` decision, and false reference/consumer flags. The V2 meaning hash includes the full exact originals, source bytes/archive members, components, conditions, scope, interpretation/parent/child metadata, source artifacts and semantic-contract pins. Unknown new metadata is included; no nested field is discarded.

V2 separates source reading from technical replay. Routine CLI/store/runtime changes can retain an identical, exactly bound reading while still invalidating mechanical evaluation. Changed meaning, source/proof, component, semantic contract, identity or original binding makes it stale. Mapping/equivalence review remains separately bound and rerun; a source-reading receipt never approves a new mapping. Artifact reauthoring, interpretation changes and source relocation may conservatively require review even where a person might later establish equivalence.

Stale receipts become unreviewed work. These receipts describe the scoped components; this pipeline grants **zero whole-original completion credit**. Unsupported/native/missing-source and mechanical holds remain even with a valid reading receipt. Historical review formats are not auto-imported or assigned new authority. Exact reference acceptance and consumer-purpose release still require the established external process. A successful adapter, cache hit, comparison or peer code review cannot grant either.

## Current trial and remaining work

The trial imports existing clinical, dental, glossary, access/transition, remaining-definition, trial and nominal-premium/Part-D comparison catalogs. It also carries the same 16 named required-missing originals from the sealed first-plan inventory. These are not 16 new gaps. Their complete detail and lineage remain visible in the queue. Any unresolved internal source-file binding is a separate engineering exception, not a newly declared source-access blocker.

The global denominator remains 143,505 claims plus 249,065 condition predicates. The first offering remains 1,778 claims plus 2,897 conditions (4,675 total). Candidate coverage, component counts, mechanical outcomes, review states and reference acceptance are reported separately. Originals without any candidate input are counted for every selected offering and exported individually; selecting a small catalog never shrinks the required inventory.

This removes repeated machine work and bespoke per-plan orchestration. It does **not** prove a future plan can be fully verified in a few seconds. Missing source definitions, native-field authority and substantive interpretation remain real work. The next scale assessment should measure the next actual offering: new adapter work, reused source parsing, exception counts, source-review effort and unresolved conditions. Any decision to change the required verification scope needs a separate reviewed revision; no MVP exemption is inferred here.

Work remains local and research-only. There is no recommendation algorithm, personal cost calculation, API activation, profile migration, consumer release or cloud provisioning in this change.

## Verification

The implementation has adversarial checks for source/scope drift, cross-offering roots, duplicate IDs/keys, component omissions, malformed schemas, full-cell qualifiers, native unknowns, exact decimals, stale reviews, parser-format collisions, pinned-source bytecode bypass, cache corruption, source changes during processing and transaction rollback. The source inventory index was independently compared against all 4,675 first-plan originals in the existing r11 export.

The reproducible benchmark tool runs actual-input cold and warm batches, changes one condition in an explicitly synthetic copy while retaining its amount, then restores the exact actual-input manifest. It measures the complete function call including snapshot publication; processing-before-publication timing is separately labeled. It measures machine work, not human review time. Final timings and verification receipts are recorded with the execution evidence below.

### Retained V1 execution checkpoint · November 3, 2026

[Final benchmark](benchmark-r2/benchmark.json) used the same pinned actual inputs for all ordinary runs. Ten catalogs retain 1,384 source records: 1,368 strict comparison components and the same 16 source gaps. Exact-root grouping produced 1,318 work tasks while retaining every component.

| Operation | Measured result |
| --- | --- |
| New inventory index, included in cold batch | 17.64 seconds; 392,570 rows / 72 offerings |
| Entire cold batch, including publication | 46.64 seconds |
| Entire unchanged repeat batch | 31.17 seconds; all 1,318 task evaluations / 1,368 components reused |
| Synthetic single-condition change, amount unchanged | 32.61 seconds; 1 task / 1 component recomputed, 1,317 tasks / 1,367 components reused |
| Restored exact actual-input batch | 31.96 seconds; no synthetic modification remains in the current snapshot |
| Retrieve 20 actual first-plan task results | 0.031 seconds |

The first profiling run is retained in `benchmark-r1/`; it found repeated hashing inside mapping lookup. Computing the full observation hashes once per component reduced the repeat batch from 39.34 to 31.17 seconds with identical outcomes. Its original query accidentally selected an offering without inputs; that zero-row timing is **not** display evidence. The final benchmark selects the actual input offering and returned 20 records.

The single-condition delta reports one material change and one affected original, plus 390 informational rebindings for unchanged records sharing the changed input container. The retained V1 actual snapshot is `d3220e8bd0024d54b70a222b8b0c969f`, rule fingerprint `af44eaa1255582f3d633e744cc2c7612a01f58c72c40646aeb109e26e5c5a769`, in ignored `.local/comparison-work-r2/`. The [V1 review export](review-export-r1/MANIFEST.json) pins all output bytes. Export verification counted all 1,318 tasks, all 1,368 components and 390,812 individual originals without candidate inputs across the selected global scope. First-plan candidate inputs touch 1,758 originals; its other 2,917 originals remain explicit work. These are coverage-of-input counts, not completed or verified benefits.

| Inventory / authority | Before | After |
| --- | --- | --- |
| Required global originals | 392,570 | 392,570 |
| Required first-plan originals | 4,675 | 4,675 |
| Existing accepted r4 reference entries | 535 | 535, preserved |
| Named first-plan missing-information originals | 16 | Same 16 retained |
| New reference acceptance / consumer release | 0 / false | 0 / false |
| Whole-original completion granted by this backend | 0 | 0 |

The final selected regression run passed **206 tests and 122 subtests**: the new pipeline plus existing comparison, whole-offering, reconciliation and research-serving boundaries. The code's output and timing evidence do not constitute owner approval or source acceptance.

Reproduce the benchmark with **new** destination names:

```sh
infrastructure/daylight-data/.venv/bin/python -B \
  infrastructure/daylight-data/tools/benchmark_comparison_pipeline.py \
  --manifest infrastructure/daylight-data/comparison-pipeline/prepared-r1/batch-manifest.json \
  --workspace infrastructure/daylight-data/.local/comparison-benchmark-next \
  --evidence infrastructure/daylight-data/comparison-pipeline/benchmark-next
```

Existing source-review evidence remains preserved in its original packets. The trial does not automatically reinterpret historical review formats as the new receipt contract: its current source-review states remain unreviewed until exact review bindings are migrated or recorded. This is remaining internal integration work; it does not mean all reviewed passages need to be reread from scratch. The whole-offering comparison and its source/reference acceptance remain unfinished.

### Additive source-review contract V2

The exact measured V1 code is retained in [code-r1](code-r1/MANIFEST.json), with [its independent review](independent-review.json). That review independently replayed all 1,368 actual components and 266 selected mappings with no differences, verified every original/source/component binding and explicitly identified the unnecessary coupling between source reading and whole-build fingerprints.

The additive V2 implementation is retained in [code-r2](code-r2/MANIFEST.json). V1 receipts remain strict. The new contract addresses future technical maintenance without granting new source authority or automatically migrating historical reading decisions. The selected regression run for this revision passed **223 tests and 181 subtests**, including an actual batch test proving that a technical-rule change reruns mechanics while retaining an exact V2 reading, and that a changed condition makes that reading stale. [Independent review](independent-review-r2.json) passed with explicit limits: all 1,368 mechanical outputs, 266 exact mappings, 48 input/source bindings and every current source-meaning hash replayed; source gaps, native unknowns and mapping withdrawals remained held. This is code/binding review, not source-fact approval.

[The final V2 benchmark](benchmark-r3/benchmark.json) measured **48.43 seconds cold**, **32.71 seconds unchanged**, **33.26 seconds for one changed condition** and **33.36 seconds restoring actual inputs**. It reused 1,317 tasks / 1,367 components and recomputed exactly one task/component for that change. Retrieving 20 actual first-plan records took **0.0315 seconds**. All inventory, task, component, source-gap and authority counts match V1. The current actual-input snapshot is `1132805f3faf4f4dbf20f36e7b433920`, fingerprint `fcff83aabc0787b86b7e05e4027e3220d4fba3d3db2011a5a8b5ef9890002ecc`, in `.local/comparison-work-r3/`. [Its export](review-export-r2/MANIFEST.json) and [implementation receipt](IMPLEMENTATION_RECEIPT.json) pin the exact checked result. No synthetic condition remains in that current snapshot.

These measurements cover one offering's existing comparison records plus the complete 72-offering inventory metadata. They do not measure full interpretation/review of the other 71 offerings, future-plan human effort, network/API/render latency or consumer readiness. New years/inventory releases require their own reviewed source and semantic-contract revisions. Historical review migration and the first whole-offering source/acceptance work remain explicit next work.

## D73 system review

| Checklist item | Evidence / remaining gap |
| --- | --- |
| Consumer task | Reusable research preparation and fast saved-result queries improve the prerequisite for trustworthy comparisons. Current landing/chat/teaching/correction paths are preserved; consumer comprehension remains unmeasured. |
| Consequential intake | No additional personal facts or questionnaire are requested. Existing 41 conditional meanings and optional/unknown/deferred reporting stay in their current profile contract. |
| Coverage path and tradeoffs | This pass changes source operations only. It neither narrows coverage-path choices nor makes MA policy recommendations; consumer tradeoff presentation remains gated. |
| Two gates and honest scope | Candidate input coverage, mechanics, source reading, whole-original completion, external reference acceptance and consumer release remain separate. Unknown/stale/incomplete source cases stay held. |
| Independence and challenge | No commercial terms select/score plans or review priority. Exact source pins, concrete differences, full raw/quarantine context and independent replay make results inspectable and challengeable. |
| Permission and control | New stores contain published-source work, not beneficiary profiles. No AI transfer, sharing, profile migration, enrollment action, budget change or protected guest-store change is introduced. |
| Actual capability | The CLI prepared, compared, cached, queried and exported local research snapshots. It did not send applications, verify personal coverage, calculate actual bills or release recommendations. |
| Proof and stage | Timings measure backend work and a saved-result query. Tests and independent replay establish technical boundaries; they do not establish consumer savings/comprehension, source acceptance or complete L03. The remaining milestone is the trustworthy whole-offering comparison and exact release process. |
