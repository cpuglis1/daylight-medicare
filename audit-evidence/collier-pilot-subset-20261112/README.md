# Collier demo database: 195 MB, original preserved

November 12, 2026 · D144, D128–D134, D94–D96, D64/D73.

Created **`daylight_pilot_collier_2026_r1`**, a separate PostgreSQL database
containing the data required by the existing local Medigap and Part D displays.
The app has an explicit `--pilot-data` connection mode. Its live services were
not restarted or switched; no source database, original file or protected
store was deleted. No AWS resource, budget alert, model call or external
transfer was made.

| Measured artifact | Bytes | Decimal size |
| --- | ---: | ---: |
| Original `daylight_research_2026_r2` | 31,011,337,919 | 31.01 GB |
| New `daylight_pilot_collier_2026_r1` | 195,002,895 | 195.00 MB |
| Compressed PostgreSQL export, `pilot.dump.gz` | 12,179,881 | 12.18 MB |
| Seven copied MA catalog/authority dependencies | 10,462,714 | 10.46 MB |

Database reduction: **99.37%**. The earlier 29.37 GB measurement predates later
imports. These are database/catalog sizes, not a complete app release, PostgreSQL
cluster/WAL footprint, memory requirement or priced AWS configuration.

## Exact contents and exclusions

**Medigap:** the entire private `dl_csg_medigap` schema, including all 320 exact
profiles, 55,040 rate observations, 3,840 benefit sheets, source metadata,
original manifests, completion/selection/STOP history, constraints, indexes,
immutable triggers and reader permissions. Scope remains ZIPs 34101–34108,
ages 65–74, both source sex categories and tobacco categories, requested date
November 10, 2026. The existing upstream age-64-to-65 behavior is unchanged.
The 12 benefit variants and all raw classes, fees, discounts, unknown annual
amounts and source-label warnings remain. This is the smallest verified unit
of the existing sealed CSG build; removing its benefit or completion records
would weaken its original completeness contract.

**Part D:** three exact, source-linked repository responses in the new
`dl_pilot` schema: ten offerings, ten restriction records and the one Collier
County/region mapping. Every original offering field, source pointer, payload
hash, condition and unresolved-check label is retained. The original selected
PDP build manifest and status are bound into a separate subset manifest. This
is explicitly a display projection; it does **not** claim that the original
277,198-record research build is present or newly accepted. The original full
`dl_plan_types` schema is not needed by this mode.

**Medicare Advantage:** all 72 retained offerings use the existing file-backed
catalogs and authority files. Their seven exact dependencies were also copied,
with paths preserved, under `catalog-files/`. The app still reads these at
their existing repository-relative locations. The bundle is a data handoff;
it does not include the rest of the application, pinned engine, teaching/ZIP
references, dependencies or static assets.

Excluded from the new database: the fifteen-layer research corpus, old public
Medigap filing/rate research, provider/drug research services, operations tables,
guest profiles, conversation data and commercial metadata. All remain in their
original locations. Neither the full research bridge nor identity-research
service is configured in `--pilot-data` mode. The current plan panels are the
verified scope; personal drug costs, provider-network conclusions, eligibility,
recommendations and enrollment retain their existing holds.

## What was verified

- Clean logical restore of the complete CSG schema into the initially empty
  new database. Ordered SHA-256 streams compare **every column of every row in
  all eight CSG tables** with the source; all agree.
- **All 320 Medigap panel outputs**, covering all 55,040 rate observations,
  compare exactly with the original database. No sampling or averaged profiles.
- All three Part D repository responses, their stored payload hashes and the
  complete ten-plan panel output compare exactly with the original.
- **98 app/infrastructure assertions** pass: actual price/catalog HTTP reads
  with fictional inputs, both profile extremes, all 72 MA detail routes, all
  229 MA holds (141 fields plus 88 examples), unsupported ages/ZIP/date/year,
  PDP expiry, CSRF/cookie rejection, database/schema grants and a rejected
  read-only write. The full research connection is absent.
- **Nine new offline tests** pass for corrupted/missing snapshots and rows,
  changed code/runtime bindings, unsupported queries, scoped/global STOPs and
  freshness recalculation. STOP insertion is modeled in these tests; no real
  STOP was appended to either database.
- **18 existing Medigap/Part D regressions** pass, using isolated fictional
  stores. No conversational/model probe ran.
- The actual `server.py --fixture --pilot-data ...` CLI starts successfully on
  an ephemeral port with a fresh fictional store and exposes the 72-plan MA
  catalog. Only that temporary process was stopped afterward.
- Source CSG values and source build/completion/selection/review/STOP controls
  compare unchanged before/after export. Source data reads used read-only
  connections. Database creation/ACL changes targeted only the new database;
  no claim is made of hashing every unrelated row in the 31 GB corpus.
- Full custom-archive decoding passes. The gzip export was completely
  decompressed and its SHA-256 equals the native dump. This is a local export
  and CSG clean-restore proof; full subset restore on the eventual cloud host
  and off-machine recovery are still due.

The first HTTP verifier draft mistakenly expected the average 172 rate rows
for a particular profile; the source has 178 non-tobacco and 166 tobacco rows.
It also initially counted 229 holds as fields only; the unchanged source has
141 held fields plus 88 held examples. Both verifier expectations were corrected
against source evidence. These were test-harness assumptions, not data fixes.

Receipts: [copy parity and sizes](verification.json),
[HTTP/access checks](app-verification.json),
[explicit CLI startup](cli-smoke.json),
[compressed export verification](compressed-backup.json),
[implementation hashes](implementation-hashes.json).
Private per-profile output hashes, original source controls and the source
manifest remain alongside the export; no licensed row values are in this packet.

## Private output and app connection

All database artifacts are under the gitignored, owner-only directory:

```text
/Users/cep4u/daylight/infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1/
  binding.json
  manifest.json
  verification.json
  profile-parity.json
  source-controls.json
  medigap-source.dump
  pilot.dump
  pilot.dump.gz
  compressed-backup.json
  app-verification.json
  catalog-files/
```

At a planned local backend restart, use `--pilot-data` with `binding.json`
instead of `--local-research`, and set `DAYLIGHT_PILOT_DATABASE_URL` to the
new database. The existing frontend/proxy can continue to use that backend.
The connection is required explicitly; there is no fallback to the research
database and no credential written into the binding. The local connection is:

```sh
export DAYLIGHT_PILOT_DATABASE_URL='host=/Users/cep4u/daylight/infrastructure/daylight-data/.state/socket port=55485 dbname=daylight_pilot_collier_2026_r1 user=cep4u'
```

Backend argument:

```text
--pilot-data /Users/cep4u/daylight/infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1/binding.json
```

The new database defaults to read-only. The existing NOLOGIN CSG/PDP reader
roles have SELECT-only access to their relevant data; no login or role
membership was added. The local owner connection remains the established
development connection. A hosted login, secret, role memberships and grants
must be configured and tested on the chosen target; do not ship the local
superuser identity. Both original packages' exact code/dependency bindings
remain enforced. The verified environment is Python 3.14.7 / PostgreSQL 18.6
with the existing pinned package environment; Linux portability is not proven
by these Mac checks.

`--pilot-data` intentionally cannot be combined with the old `--local-research`,
identity, comparison-preview or isolated pilot-rehearsal flags. Connecting the
hosted invite gate/model budget and admitted routes remains the AWS workstream.
This does not turn the fictional pilot rehearsal into a deployable live app.

## Source controls and freshness

**Before local demo use or transfer**, run this source reconciliation from
`/Users/cep4u/daylight` (read-only, no model calls):

```sh
PYTHONPATH=infrastructure/daylight-data/src \
infrastructure/daylight-data/.venv/bin/python \
infrastructure/daylight-data/tools/check_pilot_subset_source.py \
infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1 --full
```

It rejects changed selection, STOP, review, completion or source manifests,
changed CSG values, changed PDP responses, expired PDP sources and changed
catalog/authority files. Preserve this revision and export a new one when the
binding changes. The builder refuses existing output directories or database
names and never uses DROP, DELETE, TRUNCATE or restore `--clean`.

The copy is a static snapshot. A future STOP in the research database does not
automatically replicate to it. Stop the affected display immediately or append
a local `dl_pilot.stop_event` with scope `all`, `medigap` or `pdp` using an
authorized operator connection with read-only overridden for that transaction.
These STOPs are checked on each read and cannot be updated/deleted/truncated.
Retain this control history through any later restore. A remote release needs
an operating process for receiving/reconciling source STOPs before activation.

**Part D's earliest existing review deadline is November 24, 2026, 00:00 UTC
(November 23 at 7 p.m. Eastern).** The adapter recomputes expiry on every read;
it does not freeze the export-time `source_review_due=false`. After that
deadline the existing panel refuses display until the applicable review and
new revision are supplied. Do not extend a deadline merely to keep the demo on.
The planned November 17–December 4 pilot therefore crosses this review boundary.

## Commands actually run

From the repository root, using the existing package environment:

```sh
PYTHONPATH=infrastructure/daylight-data/src \
infrastructure/daylight-data/.venv/bin/python \
infrastructure/daylight-data/tools/build_pilot_subset.py \
  --database daylight_pilot_collier_2026_r1 \
  --output infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1

PYTHONPATH=infrastructure/daylight-data/src \
infrastructure/daylight-data/.venv/bin/python -m unittest discover \
  -s infrastructure/daylight-data/tests -p test_pilot_subset.py -v

PYTHONPATH=infrastructure/daylight-data/src:alternatives/advisor-first/tests \
infrastructure/daylight-data/.venv/bin/python -m unittest \
  test_medigap_pilot test_part_d_pilot -q

PYTHONPATH=infrastructure/daylight-data/src \
infrastructure/daylight-data/.venv/bin/python \
infrastructure/daylight-data/tools/verify_pilot_subset_app.py \
  --binding infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1/binding.json \
  --receipt infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1/app-verification.json
```

The HTTP verifier uses the environment DSN above, a temporary fictional guest
store, an ephemeral port and forbidden external transport. It does not access
the active app's guest data. Receipt destinations are exclusive-create; use a
new receipt filename for a later run. Python syntax compilation and targeted
whitespace checks also pass. No UI code changed; no new desktop/tablet/phone
render inspection or owner conversational-quality assessment is claimed.

## Context and remaining work

Read the Daylight Brain's `AGENTS.md`, `04 Data`, `05 Pilot and validation`,
`08 Infrastructure and accounts`, and the November 12 Claude review in
`Inbox/AWS migration plan for Claude review`. Its 2026 hypothetical pilot and
existing panel scopes govern this subset. The data/infrastructure thrust notes
are still stubs; repository/runtime evidence supplied the technical inventory.

This resolves the local database-subset task. At deployment: package the app
and file dependencies, restore this smaller database into a new target with
mapped roles, reconcile current source controls, prove all three panels and
negative cases, and complete the existing source/privacy/invitation/security
and participant-admission gates. Source/method acceptance, binding quotes and
recommendations remain separate. No current AWS price quote was prepared and
the $20 AWS alert was not changed; the hosting estimate still needs a selected
configuration and an explicit budget amount.
