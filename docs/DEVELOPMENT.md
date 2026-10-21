# Developer setup and commands

Run commands from the stated directory. Read [PRODUCT](../PRODUCT.md), [requirements](../DAYLIGHT_REQUIREMENTS.md), and [AGENTS](../AGENTS.md) before app changes. Preserve uncommitted work; do not clean/reset this repository.

## Runtime

This review used Python 3.14.7 (`cms-slice/.python-version`) and Node 23.11.0. The active app and offline tools use Python's standard library and browser JavaScript; there is no active `package.json`, npm build, or Python dependency install. Poppler (`pdftotext`) is needed for PDF-based source rebuilding/tests. The optional Medicare.gov collector uses its separately documented Playwright environment; a stopped collector must remain stopped.

Source tests require the retained local archives and reports. A Git clone alone will not contain ignored `data-sources/raw/` or `releases/`; missing-source failures are not solved by inventing fixtures. See [data inventory](DATA_INVENTORY.md) and existing [slice instructions](../cms-slice/README.md) for pinned recovery. Fetch commands can involve multi-GB downloads and changed sources; do not use them as a generic setup step.

## Safe checks from repository root

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cms-slice/tests -v
node --test cms-slice/tests/frontend/journey.test.cjs
node --check cms-slice/apps/chat/app.js
PYTHONDONTWRITEBYTECODE=1 python3 cms-slice/scripts/cms_slice.py verify
```

The portable release tests build and bundle temporary candidates without selecting the project's active release. The October 21 baseline passed 201 Python and 54 frontend tests; tests do not substitute for source/reviewer acceptance or UI sessions. The archived Node prototype has its own 22 checks: run `node --test test/*.test.mjs` from `medicare-project-2026-10-17-v1.2/archived-prototype/` only when inspecting that historical component.

## UI previews and the real service are different

Check an existing port before starting another process; leave the owner's running work alone. The observed port 8766 is a static preview, so its API 404s are expected. Use a free port for new review processes.

Static guide preview, from repository root:

```sh
python3 -m http.server 8877 --bind 127.0.0.1 --directory cms-slice/apps/chat
```

Open `http://127.0.0.1:8877/`. This supports guide teaching, local help, and layout inspection. Catalog/live requests do not work on a static server; it is not a release or gate bypass.

Synthetic catalog UI test double, from `cms-slice/`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/frontend/fixture_server.py --port 8876
```

Its banner and invented TEST records must stay conspicuous. It is suitable for checking filter/ordering/compare layout, never coverage evidence or real-user demonstrations.

Actual consumer service, from `cms-slice/`:

```sh
python3 scripts/demo_release.py verify current
# Proceed only after verification succeeds:
python3 scripts/demo.py serve --release current --port 8878
```

Currently verification fails because the selected release predates frontend edits. The consumer registry also remains pending, and the engineering review deadline has expired. A working static guide is not proof that the consumer service can admit facts. Do not edit acceptance records, freshness dates, or stored runtime hashes to silence these failures.

## Optional model configuration

`.env` is private/ignored. `.env.example` documents supported settings; do not copy a key into browser code, logs, reports, or a release. The service does not automatically load `.env`; append `--env-file ../.env` to the serve command only when live help is intended and release/source gates permit it. This review made no model calls. User-entered notes are not automatically the live model context; explicit chat is a separate transmission boundary.

## Evidence and release maintenance

From `cms-slice/`, `python3 scripts/demo_release.py build --candidate` builds without selecting the active pointer, but it regenerates supporting reports and writes a new local release. Preserve previous evidence first, inspect the source checkpoint, and follow [validated operations](VALIDATED_DATA_OPERATIONS.md). Do not use plain `build` as an incidental cleanup action: it can select a release. `select` and `bundle` are deliberate operations with their own review scope.

Existing verification commands include `scripts/prescription.py verify`, `scripts/reference_evidence.py verify`, `scripts/research.py verify`, and `scripts/star_ratings.py verify`. See [slice README](../cms-slice/README.md) for specialized data commands and their inputs. Verify failures against the historical baseline; never refresh a date merely by repackaging identical bytes.

`python3 cms-slice/scripts/medicare_collector.py status` is a local inspection. Do not run preflight/live collection or clear STOP; current source-access restrictions remain binding. See [collector operations](MEDICARE_COLLECTOR.md).

## UI review

Inspect desktop, tablet, and phone, including fresh unanswered questions, Back/edit, source-linked help, unsent drafts, unknowns, experienced comparison, and missing APIs. Keep screenshots/evidence separate from participant acceptance. The [October 21 review](reviews/2026-10-21/REVIEW.md) gives the actual checked scope and limitations.
