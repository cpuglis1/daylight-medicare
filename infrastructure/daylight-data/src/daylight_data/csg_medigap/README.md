# Private CSG Medigap repository

D128 integrates the retained 320-profile subset for ZIPs 34101–34108, ages
65–74, all four source sex/tobacco combinations and requested date 2026-11-10.
This package provides local research access to licensed evidence, with
`consumer_release: held` and `personal_quote: false` on every query response.
It does not determine eligibility or activate an advisor route.

The later D129 adapter in `alternatives/advisor-first/medigap_pilot.py` now reads
this repository for owner-authorized, bounded local source-price display in
the :8894 Medigap tab. Its separate display scope does not change this build's
historical holds or establish binding quote/eligibility/recommendation authority.
See `audit-evidence/medigap-ui-8894-20261110/README.md` at the repository root.

## Current build

Database: `daylight_research_2026_r2`; schema: `dl_csg_medigap`.

Build: `7be76407ca94d33223ec0144bac16f2e220fba0205496bdf05577a42ab32831f`.

Candidate relative to `infrastructure/daylight-data`:
`.state/csg-medigap/2026-11-10-db-r1/candidate-r1`.

The build binds all source/candidate hashes, importer hash, package Python/SQL
hashes and runtime versions (Python 3.14.7, psycopg 3.3.6). Preserve archived
code and source bytes. Runtime/code changes require a new reviewed build;
editing or rebinding an existing build is not supported.

## Read access

Run from `infrastructure/daylight-data`. Set `DAYLIGHT_CSG_DATABASE_URL` to the
intended local database connection, using the existing authorized operator.
No login or role memberships were added by this implementation. Do not place
credentials in the repository. The checked local connection uses the Unix
socket in `.state/socket`, port 55485; TCP listening is disabled.

```sh
PYTHONPATH=src .venv/bin/python -m daylight_data.csg_medigap status \
  --expected-database daylight_research_2026_r2 \
  --build-id 7be76407ca94d33223ec0144bac16f2e220fba0205496bdf05577a42ab32831f
```

For `query`, add `--request /path/to/fictional-request.json` to the same
database/build arguments. The request shape is:

```json
{
  "zipcode": "34101",
  "age": 65,
  "gender": "Female",
  "tobacco": "Non-Tobacco",
  "effective_date": "2026-11-10",
  "variant": "G"
}
```

Omit `variant` for all source variants/classes. Inputs are explicit; there are
no default profile answers. Missing ZIP/date combinations return
`needs_source_export` with no records. Ages outside 65–74 return
`unsupported_pilot_age`; age 75+ uses the owner-approved pilot-limit copy.
All returned rows retain unknown qualifications and source fields. The caller
must not treat a class/discount/SELECT observation as a qualified quote.
Rating/outlook anomalies appear in `field_issues`, with raw labels preserved.
The repository itself does not persist request profiles.

Python callers use `Repository(connection_factory, expected_build)` from
`daylight_data.csg_medigap.store`; supply a connection from
`connect(dsn, expected_database, readonly=True)`. `status()` and `query(...)`
open a read-only repeatable-read transaction, switch to the private reader
role, verify the selected build/runtime and enforce source STOPs. A stopped,
unselected or changed build fails closed. No app caller was connected here.

## Import, selection and verification

The CLI also provides `install`, `load`, `verify` and `select-research`.
`load`/`verify` require `--candidate`; selection requires `--build-id` and
`--reason`. `install` is restricted to a new schema or the identical schema
hash. Installation and role changes require the authorized database operator.
The current schema and named roles were explicitly approved by the owner.

Load validates all source files and the full 320-profile grid before writing,
then imports and compares every typed value and payload in one transaction.
Completion is appended only after parity passes. Repeated loading of the same
build verifies existing contents; it does not duplicate rows. Selection is a
separate append-only research event, not consumer acceptance. A source STOP
also blocks later builds reusing that source hash. Existing tables and event
history cannot be updated, deleted or truncated through the normal controls.

For the comprehensive read-only check, run `tools/verify_csg_medigap.py` with
`--expected-database`, `--candidate` and a new `--output` path. It compares all
stored values and every exact profile, plus missing-profile/age/date behavior
and permissions. Never overwrite an earlier verification receipt.

Tests are `tests/test_csg_medigap.py`. Supplying `DAYLIGHT_DATA_TEST_DSN`
enables a uniquely named disposable PostgreSQL fixture with fictional data;
without that variable the four database tests skip. The seven-test database
run passed for this build. The evidence packet is
`docs/data/l10-medigap-2026-10-28/csg-backend-2026-11-10/` at the repository root.
