# Recovery-first database and index redesign

November 5, 2026 · D94 follow-up · completed local physical redesign

The owner authorized a redesign within existing local capacity, preserving every
source and MVP feature and verifying recovery before retiring a replaced structure.
The original source files, prior backups, protected applications, customer stores,
41 meanings, fourteen feature families, material holds and acceptance gates remain.

The original database now serves the compact layout through the same read
contract, with its database identity and original control history preserved.
Full clean recovery and staged parity passed before the switch; all live checks
passed before the redundant legacy tables were retired. A post-retirement audit
also passed. No PostgreSQL or application restart was required.

## Actual space result

GB below are decimal. Detailed measurements are in [results.json](results.json).

| Measurement | Bytes | GB |
| --- | ---: | ---: |
| Original research database | 58,013,193,919 | 58.01 |
| Current compact research database | 29,374,584,511 | 29.37 |
| Database reduction, including index work | 28,638,609,408 | 28.64 |
| New maintenance allocation, including the recovery archive | 5,816,049,664 | 5.82 |
| Retained pilot and fictional trial databases | 391,185,469 | 0.39 |
| Accounted reduction after maintenance and trials | 22,431,374,275 | 22.43 |
| Observed volume free-space increase since the previous phase's final census | 21,491,683,328 | 21.49 |
| Volume free after completion | 81,481,805,824 | 81.48 |

The 5,813,006,603-byte compact recovery archive is retained, alongside every prior
backup and original source file. Small new code/document allocations are outside
the net accounting row. APFS reclamation, PostgreSQL WAL and concurrent host work
affect volume counters; the volume delta is not claimed as solely attributable.
The intermediate index reductions below are included in the database reduction
and must not be added again. The 7 GiB reserve stayed enforced throughout.

## Completed live index work

Three non-unique replacements were built and then fully rebuilt concurrently
against all retained rows before their predecessors were retired:

| Original | Replacement | Original bytes | Replacement bytes |
| --- | --- | ---: | ---: |
| Broad observation query index | Scoped offering lookup with deduplicated repeated keys | 3,339,272,192 | 68,182,016 |
| Source lineage with repeated table/type text | Derivation and ordinal lookup | 4,707,819,520 | 1,873,158,144 |
| Text B-tree source identity | Equality hash source identity | 2,210,824,192 | 536,887,296 |

Their measured relation reduction is **7,779,688,448 bytes**. The 72-plan serving
audit passed before and after, including source lineage, pagination, quality and
held purposes. Observed plan-detail reads were roughly 0.56–0.60 seconds before
and 0.85 seconds afterward; the storage tradeoff remains within the existing
five-second query budget. This is a measured local run, not a latency SLA.

The source primary key was concurrently rebuilt with the same definition,
reducing it from 3,707,084,800 to 2,043,994,112 bytes. PostgreSQL completed the
validated swap, then its invalid old-copy cleanup hit a short lock timeout while
the copy was active. The new primary key and FK/constraint ownership were checked,
and the exact unused old copy was then retired. This saved another **1,663,090,688
bytes** without changing source values or key meaning. The observation primary
key has not been repacked by this operation.

## Compact physical revision

The first dictionary/key pilot remains preserved separately. The r2 pilot uses
compact numeric source/type/state references, binary hash storage, targeted
indexes and small native JSONB blocks for cold source payloads. Derived fields
remain directly queryable. The compatibility views return every original logical
column and identifier; byte-for-byte PostgreSQL binary COPY parity is required
before each chunk commits. No source assertions are merged by meaning.

The 109,218-source-row / 113,528-projection pilot covered all fifteen layers.
The full copy now contains **17,767,179 source rows, 17,823,148 projections and
5,972 offering rows**, with every logical column matched before each chunk
committed. Its finalized initial database size is 29,457,061,567 bytes. The 5,813,006,603-byte
native backup passed full gzip CRC and PostgreSQL archive decoding.

A conventional second full restore was refused by the capacity preflight before
creating a target. Recovery now restores complete tables into one clean database,
compares a duplicate-preserving multiset of native binary-row SHA256 digests, and
only then releases the matching temporary candidate table storage. The original
research database and backup remain complete throughout. All restored tables,
indexes, foreign keys and views must coexist in the final recovery database;
every original logical checkpoint is then rehashed and serving checked. This
keeps the monitored **7 GiB reserve** without weakening the full-recovery gate.

The first pre-data attempt completed successfully in PostgreSQL but exposed a
client pipe-handling error when `pg_restore` exited before consuming unused
archive data. Its empty owned target was checked and removed, and its logs remain
in `bounded-predata-attempt1/`. The corrected operator accepts early pipe closure
only with a successful native exit. The native fixture recovery and explicit
failure-exit regression both pass. No original data were retired by that attempt.

The first logical-column verification matched 729 chunks, then hit its 180-second
statement limit on a large `new-source-pages` range. Its materialized JSON
expansion was underestimated and repeatedly rescanned. The bulk-only range reader
now uses transaction-local hash/merge joins; the exact failed range matches its
original hash in 3.83 seconds and the connection setting returns to its prior
value. Runtime point-read planning is unchanged. The failed log is retained in
`logical-verify-attempt1/`; full verification is rerun with the corrected reader.

The next attempt matched all 1,283 data chunks, then identified a bookkeeping
comparison error: the independently initialized compact target has its own
migration execution timestamps. Migration names/code hashes are compared
separately from those timestamps. Original live migration rows and their exact
hashes remain unchanged; recovery seals both histories. The completed data log
and failed final metadata check remain in `logical-verify-attempt2/`.

**Full recovery now passes:** all 1,283 original logical chunks, all 17,767,179
source rows, 17,823,148 projections, 5,972 offering rows, exact control metadata,
valid constraints/indexes and the 72-plan serving audit. A strict five-second
precheck exposed a view-planning regression before deployment. The additive
[r3 read adapter](../../../infrastructure/daylight-data/redesign/r3/read_views.sql)
keeps cold payload lookup out of the large outer join graph, preserving every
column while fetching selected records through primary keys. Fictional full
column/metadata/cutover/rollback tests pass. Actual restored plan-detail calls
then measured 31–47 ms under the five-second budget. The original live database
remained active throughout. These timings are observed runs, not an SLA.

The first staging transaction rolled back because native namespace filtering
omitted `CREATE SCHEMA`. No compact objects remained and all three original
tables stayed active. Staging now selects the compact schema's exact archive TOC
entries, including namespace creation and ACLs. That full-archive selection,
column preservation, atomic cutover and real rollback pass on fictional data;
the failed attempt is retained in `stage-attempt1/`.

Cold blocks use PostgreSQL's existing [JSONB operators](https://www.postgresql.org/docs/18/functions-json.html)
and [native TOAST storage](https://www.postgresql.org/docs/18/storage-toast.html).
No custom extension or binary dependency is introduced. The pilot established
that short individual values often stay inline, so merely lowering the TOAST
target did not provide the needed reduction. Full recovery uses the native
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html) path.

## Completed recovery and retirement gates

1. Full 17,767,179-source-row / 17,823,148-projection copy, plus all 5,972 offering rows.
2. Exact control/lineage/condition/value parity, including decimal/null distinctions.
3. Full backup, clean integrated restoration and complete restored-column rehash.
4. Space-bounded staging into the original database without changing its identity
   or active tables; all staged logical values match the original hashes, with
   original controls/counts and column names/types/order/collations checked.
5. Atomic compatibility-view cutover with the old tables retained for rollback.
6. Live research, provider/drug, permission/STOP, count and MVP checks.
7. Only then retirement of three redundant legacy tables, followed by a passing
   post-retirement 72-plan audit and full row/control-history checks. Original
   source files and backups stay retained.

The final suite passed **19** fictional PostgreSQL/recovery/rollback/reserve
tests, and the existing research/provider/medicine/profile suite passed **176**
tests. Actual live validation passed 35 provider checks across nine cases;
provider outputs and the three complete medicine-result hashes match their
baselines. All 72 offerings, 41 meanings, fourteen families and 229 MVP holds
remain. Live detail calls measured 0.44–0.70 seconds in the observed runs, within
the existing five-second query budget. Released offerings remain zero.

The current frozen research database is a read-only served snapshot. New source
builds continue using separately owned versioned build targets and the existing
source/method/purpose reviews. No new consumer authority, source acquisition,
raw-chat persistence, cloud service or off-machine-recovery claim is introduced.

## MVP preservation and scope

All 185 files referenced by the frozen source snapshots were rehashed against
their original controls: **6,655,325,543 bytes matched**. Original source paths,
PDFs, extraction evidence and prior backups stay retained. The database copy
preserves separate assertions and all six review/use/output state columns.

| Delivery measure | Preserved scope |
| --- | --- |
| Plan coverage | Exact 72 retained 2026 Collier offerings |
| Field preparation | 720 field dispositions, 288 scenario dispositions, 1,440 medical records and 1,008 offering/family pairs; family depth remains uneven |
| Source/method acceptance | Unchanged; no new acceptance, no changes to the 535-entry accepted reference or 392,570 research obligations |
| App access | Existing live plan/provider/medicine reads pass through the same binding; consumer holds remain and the offline MVP snapshot is not a new app integration |

The fourteen families remain identity/scope, premiums/deductibles, spending limits,
office/hospital, other core medical services, extended care/equipment, providers,
medicines, pharmacy/drug costs, away care, supplemental benefits, quality,
current coverage/transitions and alternative paths/next help. All 41 conditional
meanings and 229 material published/scenario holds remain required.

D64/D73 review: this is physical storage work behind existing read contracts.
It changes no consumer intake, teaching, coverage-path representation, commercial
input, user correction, permission, AI transfer or guest persistence. Reported
facts and verified coverage remain separate. Recovery and query checks establish
technical preservation; they do not establish recommendation readiness or
consumer comprehension. Protected application variants and customer stores are
outside the database mutation scope.

## Code and evidence

- [r1 schema](../../../infrastructure/daylight-data/redesign/r1/schema.sql) and
  [r2 schema](../../../infrastructure/daylight-data/redesign/r2/schema.sql)
- [Bounded r2 copy](../../../infrastructure/daylight-data/tools/compact_database_r2.py)
- [Recovery](../../../infrastructure/daylight-data/tools/compact_recovery.py),
  [bounded clean recovery](../../../infrastructure/daylight-data/tools/compact_bounded_recovery.py),
  [range verifier](../../../infrastructure/daylight-data/tools/compact_range.py),
  [restore reserve monitor](../../../infrastructure/daylight-data/tools/compact_process.py)
- [Deployment and rollback](../../../infrastructure/daylight-data/tools/deploy_compact.py)
- [Local recovery recipe](../../../infrastructure/daylight-data/redesign/r2/RECOVERY.md)
  and [independent recovery verifier](../../../infrastructure/daylight-data/tools/verify_recovered_compact.py)
- [Index recovery and retirement](../../../infrastructure/daylight-data/tools/redesign_research_indexes.py)

Private receipts and logs are under `.state/maintenance/20261105-index-r1/`,
`20261105-db-r1/` and `20261105-db-r2/` in the infrastructure package. They are
ignored by Git and include source/code bindings, exact byte hashes, failed-attempt
evidence, measured timings and the durable checkpoint/retirement gates.

## Still needs review

**November 6 follow-up:** the dependency-lock item below is now reconciled.
The exact archived inputs passed the unchanged historical verifier's 759 queries
and 756 checks, while the current dependencies and sealed receipts remain
unchanged. See [the reconciliation record](../dependency-reconciliation-2026-11-06/README.md).
The November 5 failure and measurements below remain historical evidence.

- The historical full-build verifier correctly refused its frozen dependency
  lock pin: current `requirements.lock` differs from the October build's hash.
  Its mtime is November 4 UTC, before this maintenance, and this work did not
  edit it. No before-content hash was recorded for that file. The failed receipt
  is retained; no frozen manifest/pin was changed or gate waived. Reconcile that
  dependency revision separately. Current recovery, all-column parity, control
  history and live-feature checks passed independently.
- Off-machine recovery, cold-cluster recovery and PITR remain untested. The new
  native backup has an actual full local clean restore; backups on this disk
  remain exposed to loss of the disk.
- This remains a frozen read-only research snapshot. New ingestion continues
  through fresh versioned build targets; a generalized compact write path and
  full domain normalization remain separate work. The small r1 pilot and two
  fictional trial databases remain as retained execution evidence (0.39 GB).
- Source/method/purpose acceptance, unresolved medical/material checks and
  consumer recommendation release remain unchanged. Technical recovery is not
  domain acceptance or completed MVP delivery across all four measures.
