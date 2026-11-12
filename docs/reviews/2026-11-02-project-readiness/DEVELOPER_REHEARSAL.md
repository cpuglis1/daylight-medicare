# Daylight clean-source rehearsal

November 2, 2026 · local-only developer bootstrap check

**Result: all 74 selected offline tests passed from the isolated exported tree in 17.274 seconds**, with no real model key, original-workspace access, network/server connection, database access, subprocess call from tests or test file writes. No original source, customer record, store, usage ledger, runtime or evidence acceptance was changed.

## Export and integrity

- Private export: `/private/tmp/daylight-team-rehearsal-20261102`, directory mode **0700**.
- **185** source/dependency files, **11,174,644 logical bytes**.
- **58/58** pinned shared-engine files match `engine-lock.json`.
- Every copied source/dependency file matched the original selected working-tree bytes when checked after the final test. This is a working-tree snapshot, not a Git commit or clone.
- Source manifest: `developer-source-manifest.json`.
- Source manifest SHA-256: `c3a6c2f9fb04e567aee33d86fd24bd5d1b4debdd6b59441825f5d76af5075080`.
- Selected roots: variant top-level Python/JSON, frontend assets/config, the four tests with persona helper/fictional fixtures, exact pinned engine paths, specific shared public profile/ZIP/baseline configuration, infrastructure source/config/migrations/package metadata and the decision-map contract. Full relative paths are in the manifest.

Explicit exclusions were applied independently of the current publication policy: `.env`, `.git`, `.state`, `.venv`, `__pycache__`, runtime, logs, customer/profile stores, credentials, raw data, audit snapshots, plans, outputs and archive trees. No symlinks were followed. One archive-classified contract metadata exception was subsequently authorized for this local rehearsal only, as described below.

## Tests and guard

Inspected the four test modules and persona helper for absolute original paths, saved-profile operations, model/network clients, server startup, DB calls and output writes before execution. The persona helper imports the pinned server to register modules but does not call `build`; the flow uses `None` persistence/budget dependencies and injected synthetic model transport. Its CLI-only optional output writer is not used by the tests.

| Module | Passed |
| --- | ---: |
| `test_persona_journeys.py` | 7 |
| `test_comparison_engine.py` | 22 |
| `test_advisor_memory.py` | 12 |
| `test_education.py` | 33 |
| Total | **74** |

Executed with Python **3.14.7**, `-I -B`, a minimal environment containing only PATH/PYTHONDONTWRITEBYTECODE/LC_ALL, and the export as the working directory. A Python audit guard rejected original workspace file reads, network connection/DNS/bind, SQLite connections, subprocess creation and test writes. The runner recorded **zero prohibited attempts**, 47 imported project modules within the export and no missing non-bytecode dependency reads. This is an application-level guard for inspected code, not a claim of general sandbox security. Standard interpreter libraries remain host dependencies.

The exact runner, command, final stdout JSON and unittest log are in the export. Python's harmless attempts to locate absent bytecode cache files are retained in raw diagnostics; bytecode was not written.

## Dependencies discovered by actual failures

| Exact additional dependency | Bytes | SHA-256 | Why needed / disposition |
| --- | ---: | --- | --- |
| `alternatives/chat-first/cms-slice/config/model_rates.json` | 383 | `d1ae1602859b09b99243df1be8831ac98090a204cdc8a6e319903c0c5e859249` | Import-time public model pricing configuration, not credentials. Added under code/config scope. |
| `alternatives/chat-first/cms-slice/apps/chat/zip-counties.json` | 2,161,924 | `02a7418c61dcb476ddf27f8af7d94cc24ac10c1a5d54d44972930931a81c3923` | Shared guide validation requires this retained published ZIP/county lookup even though the alternative frontend has its own copy. Added under static configuration scope. |
| `docs/data/integration-review-2026-10-29/review-catalog.json` | 683,939 | `1585b420d137456a3aa2c1dc83d76c4a6794a29fe2485aa1c8e74ac879b29ba9` | `comparison_profile.py` verifies this exact review metadata against the profile contract. **Explicit local-only metadata dependency exception**; publication policy remains `evidence_archive`. No public upload, source acceptance or policy relaxation. |

The review catalog was inspected as metadata/integration proposal, with top-level layers/questions/profile-field/gap/capability/issue/action/entity/artifact descriptions and no credential/customer identifier fields found. It references many artifacts that were **not** copied. Hash verification of this catalog is enough for these structural tests, but does not supply or verify its referenced research populations.

The first run had a persona import error and comparison contract errors; the second exposed the shared ZIP lookup. Exact failed logs remain under `diagnostics/` with a clear summary. They are preserved dependency-discovery evidence, not the final status.

## Meaning for a team bootstrap

A narrow fictional developer bootstrap is feasible without the original workspace, real profiles or research DB. The required code/config fixture boundary is now concretely enumerable. A curated repository/export must include the hash-pinned engine and all named static/contract dependencies. Omitting every `docs/data/` object currently breaks comparison-profile contracts; solving public packaging requires a specifically reviewed metadata export or a deliberate new fixture contract, not a blanket permission to publish research evidence or silently loosen hashes.

This rehearsal did not install infrastructure dependencies, start HTTP/UI servers, run the full advisor suite, exercise PostgreSQL/source reads, restore backups, validate browser rendering or call the model. It proves neither a full platform clean clone nor production readiness, independent domain acceptance, customer privacy approval, personal comparison/recommendation capability or enrollment. The inspected standard-library tests are intentionally narrower.

## Local handoff archive

The [local archive](../../../outputs/daylight-team-handoff-20261102/daylight-developer-rehearsal.zip) contains this isolated rehearsal, with exact size, hashes and packaging checks below.

- Archive: `/Users/cep4u/daylight/outputs/daylight-team-handoff-20261102/daylight-developer-rehearsal.zip`
- Compressed bytes: **1,894,615**; entries: **198**.
- Archive SHA-256: `38099dfa06e19c3ed3d08e1b9cf332f0f35e255474307a59dd6e9334df8c4130`.
- Bundle manifest SHA-256: `97e5b2deac126835618206902aa87b3faf7026b4737a79e303eb1c77f6c49942`.
- Packaging validation: ZIP CRC and every bundled file's size/SHA-256 verified against its manifest. Output directory mode is 0700; archive mode is 0600.
- Receipt: `/Users/cep4u/daylight/outputs/daylight-team-handoff-20261102/ARCHIVE_RECEIPT.json`.

The source snapshot, metadata dependency exception, guard and successful check remain the same after packaging. No upload was performed.
