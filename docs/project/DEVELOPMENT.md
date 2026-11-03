# Develop the current advisor

This repository contains the current advisor-first source, its exact shared engine dependencies, the data-infrastructure implementation and selected product/company contracts. Start with fictional development. The original Node prototype and older chat/research code remain historical or protected surfaces; they are not the current advisor entrypoint.

## Quick start without credentials or research data

The repository is currently private; contributors need access and authenticated Git. Requirements: Git, Python 3.12 or newer, and Node.js 22 for frontend regression tests. The fixture advisor and public checks use Python's standard library and built-in Node test tools; no pip or npm install is needed for this path.

```sh
git clone https://github.com/cpuglis1/daylight-medicare.git
cd daylight-medicare
python3 -B tools/prepare_advisor.py
DAYLIGHT_DEV_DIR=$(mktemp -d)
python3 -B alternatives/advisor-first/server.py --fixture --port 8903 --database "$DAYLIGHT_DEV_DIR/fictional.sqlite3"
```

Open `http://127.0.0.1:8903/`. Use fictional information. Stop with Ctrl-C. This fixture uses a separate development database and simulated AI. It makes no model calls and connects to no retained research database. It demonstrates the interface and controller, not real-model response quality or personal coverage findings.

The current application source is `alternatives/advisor-first/`; protected :8890/:8891/:8896 source and storage have their own contracts. The included subset of `alternatives/chat-first/` supplies all 58 hash-pinned dependencies and required static contracts for this advisor. It is not the complete standalone :8891 application.

## Run the checks

```sh
python3 -B tools/prepare_advisor.py
python3 -B -m unittest discover -s tools/tests -v
python3 -B tools/run_advisor_checks.py
python3 -B -m unittest discover -s infrastructure/daylight-data/tests -p test_profile_contract_export.py -v
python3 -B -m unittest discover -s infrastructure/daylight-data/tests -p test_whole_offering.py -v
python3 -B tools/smoke_advisor.py
```

The public advisor runner executes every `test_*.py` module except `test_published_reference`. It starts a subprocess without provider credentials or database/service environment variables and blocks external Python network requests. Temporary loopback HTTP is permitted for fixture API tests; the Node wrappers run fictional DOM/transport tests. The shell that runs these checks must permit local sockets.

`test_published_reference` remains in source and requires the separately governed exact r4 evidence, original lookup verifier and review receipt. Its absence from public CI is explicit in the runner's JSON report. No invented reference replaces it. Other infrastructure source-population, PostgreSQL/security/recovery and actual-target tests also require their named private inputs or isolated test database; the public checks above do not claim that those were executed.

GitHub's `repository-checks` job runs the control tests, Git publication checks, metadata preparation, public advisor suite, selected infrastructure contract/safety tests and HTTP smoke check. It uses Python 3.12 and Node 22, SHA-pinned actions, read-only permissions and a standard hosted runner. In the current private setting, branch-protection enforcement requires GitHub Pro or public visibility; maintainers must verify the run before merging. Private-repository Actions allowances and existing billing limits apply. The term public suite describes its fictional/portable inputs, not the repository’s visibility.

## Exact metadata preparation

The original comparison contract binds `docs/data/integration-review-2026-10-29/review-catalog.json` by hash. A content-reviewed, byte-identical metadata copy is distributed under `infrastructure/daylight-data/config/integration-review-catalog.2026.json`. The preparation command materializes it at its historical locator without changing the contract, source hashes or acceptance. This is an October 29 metadata/integration proposal, not the latest data status or a released evidence population.

The same command materializes the explicitly fictional conversation-journey specification and its original evaluator from the test source to the historical audit locators used by the existing test. These operations fetch no research data, open no guest store and copy no live transcript. The evaluator's opt-in live CLI is never invoked by preparation or public checks. Different existing files and symlinks are rejected; matching files are left unchanged. Generated historical-locator files are not part of the Git publication selection. Do not stage them.

## Infrastructure and later integrations

`infrastructure/daylight-data/` contains the Python API/import/archive code, nine SQL migrations, configuration, direct/transitive dependency snapshot, tests and runbooks. It does not contain the loaded research database, original evidence archive or a ready cloud account binding.

The infrastructure requires its own isolated virtual environment and dependencies from `requirements.lock`; its package targets Python >=3.12. The checked-in lock is a version snapshot, not a hash-verified cross-platform install proof. Container tags also remain development configuration pending exact image verification. See its README and runbooks before starting a database or importing evidence. The advisor fixture above does not need this installation.

Live AI, internal retained research, public hosting and customer data each need their actual configuration and permissions. The current Mac-specific launch configuration and real stores are intentionally excluded. Consumer evidence and recommendation holds remain in force, including when reported inputs are complete. Commercial terms never enter substantive comparison or advice.

## Assets and project authority

The selected photo's source attribution is in `alternatives/advisor-first/web/art/arrival-option-a.jpg.origin.md`; the complete upstream SIL Open Font License notices are beside the bundled fonts. These assets retain their own licenses. Publishing this repository does not grant a new blanket license to Daylight's application code or research evidence.

Read `PRINCIPLES.md`, `PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md` and the target folder's `AGENTS.md` before contributing. The [project hub](README.md), [company narrative](../company/README.md), [repository controls](REPOSITORY_CHECKS.md) and [storage handoff](CLOUD_HANDOFF.md) explain ownership, scope and remaining work. Passing technical checks does not establish source, domain or consumer-release acceptance.
