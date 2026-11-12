# Dependency history reconciliation

November 6, 2026 · D94 follow-up · reconciled and verified

The historical lockfile has been recovered byte-for-byte from the retained
implementation archive. The working lockfile and installed packages remain
unchanged. This reconciles two valid dependency revisions without rewriting
sealed history or treating newer comparison-pipeline dependencies as an error.

The unchanged historical verifier now passes **759 SELECT-only database queries
and 756 verification checks**, covering all fifteen layers and all 363 current
execution receipts. The current environment passes `pip check`; **85 focused
tests and 84 subtests** pass, including the comparison pipeline's strict input
validation. See [verification-summary.json](verification-summary.json).

## What differed

`requirements.lock` is a list of exact Python package versions. The October
database build seals its exact file hash; the current file includes later
comparison-pipeline work. The original verifier correctly rejected that changed
file before connecting to PostgreSQL.

| Revision | Packages | SHA-256 |
| --- | ---: | --- |
| [Sealed historical lock](sealed-requirements.lock) | 33 | `375c52227496ddbf0babeaf264dd6326ad30f2a5e0a5194746c8211887d04a87` |
| [Preserved current lock](current-requirements.lock) | 38 | `81946390d9173c21246e42798e902934a4b0551d316c8bb6eb9bc3a4d466bcab` |

The five additions are `jsonschema==4.25.1`, `jsonschema-specifications==2025.9.1`,
`referencing==0.37.0`, `attrs==26.1.0` and `rpds-py==2026.9.1`. They support strict
structured-input validation in the existing
[comparison backend](../../../infrastructure/daylight-data/comparison-pipeline/README.md).
None of the original 33 versions changed or disappeared. The actual installed
versions match all 38 current pins, and `pip check` reports no broken requirements.
Shape validation does not establish that a Medicare interpretation is correct.

## Preservation and verification method

The source is [implementation archive r4](../../data/infrastructure-execution-2026-10-29/implementation-archive-r4.json).
Its whole bundle hash and the historical lock's member hash were verified before
recovery. Both locks are retained here as independent files. The active lock at
its original path is unchanged.

The [preparation tool](../../../infrastructure/daylight-data/tools/prepare_dependency_verification.py)
materializes an isolated root containing every original pinned executable,
receipt and checkpoint needed by the unchanged historical verifier. The recovered
lock occupies its original relative locator **inside that isolated root**.
Every original expected hash still has to match. The retained logical dump uses
an independent APFS COW clone; live database files are never copied. The only
external alias is the existing private Unix socket, which resolves to the same
database/cluster guards. The current working tree and dependency environment are
not downgraded or replaced.

[The completed r2 preparation manifest](preparation-r2/reconciliation.json)
records all input hashes, both lock revisions, installed versions and snapshot
methods. The first preparation's [manifest](reconciliation.json), lock copies
and failed verification remain retained. That first run passed every database
query but omitted the 363 current filesystem execution receipts from its input
snapshot. The corrected preparation includes them, verifies their bytes and lets
the unchanged verifier compare each complete receipt against the actual DB job.
No missing-receipt check or dependency pin was waived.

The final run retains **17,767,179 source rows and 17,823,148 projections**,
exact current/historical job cohorts, canonical r9 claims/conditions, material
unknowns, source STOPs, profile metadata and empty consumer-release state.
The verifier reconciles stored stream digests and performs its named domain
queries; it does not replay original source artifacts or recompute all raw
payload hashes. The earlier D94 full restore/all-column hash proof is separate.

The current Python environment executes the verifier; its 33 common package
versions match the historical lock, with the five later packages retained.
This is not a claim that a pristine historical environment was recreated.
The original verifier still rejects a changed lock at the working-tree locator;
the reconciled command explicitly supplies the historical input root.

## Repeatable command

Run from the project root. The retained verification root is private and
read-only except for its private-socket directory alias. Use a fresh output
filename for every run; preserve previous attempts.

```sh
DAYLIGHT_DATA_DATABASE_URL='host=/Users/cep4u/daylight/infrastructure/daylight-data/.state/socket port=55485 dbname=daylight_research_2026_r2 user=cep4u' \
infrastructure/daylight-data/.venv/bin/python -B \
  infrastructure/daylight-data/.state/maintenance/20261106-lock-r2/verification-root/infrastructure/daylight-data/tools/verify_local_database.py \
  --repository /Users/cep4u/daylight/infrastructure/daylight-data/.state/maintenance/20261106-lock-r2/verification-root \
  --output /Users/cep4u/daylight/infrastructure/daylight-data/.state/maintenance/20261106-lock-r2/full-verification-next.json
```

To regenerate inputs, use `tools/prepare_dependency_verification.py` with new
`--output` and `--snapshot` directories. It rejects other frozen-input drift,
changed/removed historical versions, a current environment that differs from its
lock, existing output directories, archive corruption, missing execution receipts
and path escapes. Run the historical verifier only against the resulting root.
Installing from the 33-package historical lock is not part of this procedure.

The actual report and query timings remain under
`.state/maintenance/20261106-lock-r2/full-verification.json`; its SHA256 is recorded
in the public summary. The first attempt and diagnostics remain in `20261106-lock-r1/`.

## Meaning of the remaining review items

- **Off-machine recovery:** restore a retained backup on another disk or machine,
  proving recovery after loss of this computer. Local restoration has passed;
  a second database on this same disk does not prove survival of disk loss.
- **PITR (point-in-time recovery):** retain a base backup and an unbroken sequence
  of PostgreSQL transaction logs so recovery can stop at a chosen moment. A
  logical dump restores its snapshot; it does not by itself provide this ability.
- **Source/method/purpose acceptance and release gates:** review exact source-use
  permission, interpretation/calculation methods and material coverage checks
  before using results for a particular consumer purpose. Passing infrastructure
  checks does not turn provider identity into network verification, drug identity
  into personal coverage, or incomplete evidence into an approved recommendation.
- **Portable installation proof:** the lockfiles pin versions, not wheel hashes
  or every target platform. A clean installation/container proof remains separate
  from checking the currently installed environment.

D64/D73: source assertions, holds, all 41 meanings and fourteen MVP families are
unchanged. This task adds no consumer intake, economics input, AI call, profile
persistence, source acquisition, recommendation authority or application change.
The useful result is reproducible historical verification with current work
preserved; it is not evidence of consumer readiness.
