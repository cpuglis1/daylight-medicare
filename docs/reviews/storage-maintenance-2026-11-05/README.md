# Source-preserving storage maintenance

November 5, 2026 · D94, D85, D91, D64/D73 · local execution

The owner authorized recovery-first storage cleanup within existing local disk
capacity, preserving every source, critical inference and MVP feature. This run
retains every original source path and byte. It changes physical block sharing,
adds recoverable manifests and prepares an offline indexed MVP snapshot. The
active advisor, research database, customer stores and release authority are unchanged.

## Measured space

All GB figures below are decimal. APFS can defer reclamation, and volume free-space
counters include concurrent activity. Logical file sizes do not identify unique
physical blocks. The workspace's logical total increases because recovery bundles
were added even while physical space was reclaimed.

| Measurement | Bytes | GB |
| --- | ---: | ---: |
| Immediate free-space increase across source coalescing | 4,537,622,528 | 4.54 |
| Immediate free-space increase across Git temporary-pack coalescing | 8,255,840,256 | 8.26 |
| Total immediate operation measurements | 12,793,470,976 | 12.79 |
| Three retained independent compressed recovery bundles | 3,268,582,672 | 3.27 |
| Operation measurements less recovery bundles | 9,524,888,304 | 9.52 |
| Whole-volume free increase at final census | 12,683,862,016 | 12.68 |

Manifests, the 9.42 MB shadow snapshot, logs, governance before-copies and new
tooling also consume space. The detailed accounting in [results.json](results.json)
subtracts all maintenance-directory allocation. **About 9.5 GB net** is the
cleanup accounting result. The larger volume delta includes deferred APFS and/or
other activity; it is not claimed as fully attributable savings. At the final
census the volume had 59,990,122,496 bytes free, up from 47,306,260,480.

## What changed

- Inventoried and SHA-256 hashed **77,800** source/code files. Live database
  files, guest stores, credentials and runtime directories are outside mutation
  scope. The post-source-cleanup parity check found **zero content changes**.
- Found **157 exact duplicate groups**, representing 11,558,152,403 repeated
  logical bytes. Built a separate compressed recovery bundle, restored every
  unique object to scratch and verified its full hash before replacement.
- Coalesced **225** exact copies with independent APFS COW inodes. Original
  paths, content, modes, timestamps and native ACL/xattr metadata are preserved.
  Four existing hardlinks in L10 were already sharing storage and were skipped.
  No source was merged by meaning, renamed or removed.
- Identified **87** stale Git temporary packs in seven full-prefix-equivalent
  groups. Restored and checked every original file's bytes from a separate bundle,
  then coalesced **80** copies. All original names, lengths, hashes and metadata
  survive. Open-handle checks ran before replacement. No Git prune, ref/index
  change or normal-object replacement occurred. The remaining temporary packs
  stay retained; this is storage sharing, not removal of recoverable Git history.
- Added four narrowly scoped D94 governance updates. Byte-exact copies of their
  previous versions were reconstructed and checked against the initial inventory
  before retaining them in the private packet. Prior directive text is intact.

The first Git apply attempt stopped before any replacement because its private
clone inherited a read-only mode. The corrected operator makes only that scratch
clone writable before truncation, then restores the target's metadata. The
read-only case is covered by a passing regression test. The failed empty journal
remains preserved.

## MVP snapshot and inference preservation

The **9,424,896-byte** SQLite snapshot is an unactivated local operator artifact.
It round-trips all JSON values from the exact six retained inputs: r5 native
catalog, r9 family/gap matrix, r10 critical medical records, r13 display/examples,
r1 question/capability map and existing profile contract. Source hashes are pinned.
It was compressed, restored to a separate scratch database and reverified.

| Preserved index | Count |
| --- | ---: |
| Exact 2026 offerings | 72 |
| Published-field dispositions | 720 |
| Scenario dispositions | 288 |
| Offering/family pairs | 1,008 |
| Medical-service records | 1,440 |
| Conditional question meanings | 41 |
| Material published/scenario holds | 141 + 88 = 229 |

All fourteen families remain represented: identity/scope, premiums/deductibles,
spending limits, office/hospital, other core medical services, extended care/equipment,
providers, medicines, pharmacy/drug costs, away care, supplemental benefits, quality,
current coverage/transitions and alternative paths/next help. The r9 gap matrix is
explicitly labeled historical; its states do not override newer r10/r13 findings.
Representation does not imply complete field preparation or acceptance.

No interpretation was collapsed during storage deduplication. Source assertions,
conditions, review evidence, reason codes, parent references and method assumptions
remain reconstructable. Doctor identity versus participation/availability, drug
identity versus coverage/approval/fill price, separate premium/Part B/medical/drug
bases, protected SNP costs, hospital day/admission rules, selective deductibles and
correction invalidation retain their original logic. The frozen 392,570 research
obligations, 4,675 pilot obligations and accepted 535-entry reference are unchanged.

| Delivery measure | Result |
| --- | --- |
| Plan coverage | All 72 retained identities indexed and reconstructable |
| Field preparation | Existing 720 field, 288 scenario and 1,440 medical-record dispositions preserved; fourteen-family depth remains uneven |
| Source/method acceptance | Unchanged; no new acceptance or inherited consumer authority |
| App access | Existing :8893 behavior unchanged; shadow snapshot is not connected to app reads |

## Verification executed

- **13** maintenance/recovery/snapshot tests passed, including corrupt backup,
  changed source, wrong equivalence, open-handle rejection, read-only files,
  independent COW writes and corrupted query-index detection.
- **69** existing meaning/profile/method/temporal regression tests passed with
  provider credentials stripped and Python network actions denied.
- Original **r5, r12 and r13 calculation/catalog replays passed**.
- Git full integrity checks passed before and after; their output was identical.
  Refs and index hashes were unchanged. All **87** selected Git files passed a
  separate final full-hash/length/mode/timestamp check.
- The live database was checked in a read-only transaction: **58,013,193,919
  bytes**, **17,767,179 source rows**, **17,823,148 projections**, and **zero**
  rows in its held released-offerings view. No database writes, source reloads,
  service restarts, UI changes, paid probes or raw-chat persistence occurred.

## Remaining review and work

1. **Full PostgreSQL recovery remains unexecuted.** The 58 GB copy plus the
   required 7 GiB reserve and WAL/restore headroom still exceeds available space.
   The tested recovery in this run covers every coalesced source/Git file and the
   entire MVP shadow snapshot. It is not a full research-database restore or an
   off-machine backup. No research database, original backup or source revision
   was retired to create room.
2. **Serving cutover requires review.** The snapshot preserves the current MVP
   core and dependency/gap mappings. It does not replace the full provider, drug,
   pharmacy or rules populations; their retained lookup paths stay in place.
   Review the query contract, authority binding, refresh/correction behavior and
   rollback before connecting any app reader.
3. **PostgreSQL schema/index redesign is prepared for assessment, not applied.**
   The two main tables still use approximately 18.8 GB of indexes. A new revision
   can dictionary-encode repeated derivation/type/table keys and use compact
   source-row references while preserving every external logical ID and locator.
   Separate source payload storage from derived fields only where reconstruction
   proves the projection can be recovered exactly. Benchmark actual lookups and
   verify permissions/holds before replacing any reader or retiring an index.
4. **Physical archive relocation/off-machine recovery remains open.** The source
   map is organized by content hash while original paths remain. All current
   recovery copies share this machine's failure domain. No cloud account,
   publication, vendor purchase or broader evidence acceptance was inferred.

## Tools and private evidence

- [Source preservation/coalescing operator](../../../tools/storage_maintenance.py)
- [Git temporary-prefix operator](../../../tools/git_pack_storage.py)
- [Offline MVP snapshot builder](../../../tools/mvp_serving_snapshot.py)
- [Source safety tests](../../../tools/tests/test_storage_maintenance.py),
  [Git prefix tests](../../../tools/tests/test_git_pack_storage.py),
  [snapshot tests](../../../tools/tests/test_mvp_serving_snapshot.py)

The private packet is
`infrastructure/daylight-data/.state/maintenance/20261105-r1/` (ignored by Git).
It contains inventories, hash/occurrence mappings, fsynced replacement journals,
compressed recovery bundles, before/after space censuses, exact governance parents,
snapshot/recovery receipts, original replay logs and Git integrity outputs.
The public-sized summary links the packet by hashes; it is not publication approval.
