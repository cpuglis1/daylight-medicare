# Daylight chat-first alternative

**Canonical editable source:** `/Users/cep4u/daylight/alternatives/chat-first`.
This is the separate **:8891** product, relocated on October 25, 2026; the original **:8890** UI remains in the root `cms-slice/`.
Keep the two designs, guest identities and storage separate.

| Item | Location |
| --- | --- |
| Chat-first UI | http://127.0.0.1:8891/ · `cms-slice/apps/chat-alternative/` here |
| Alternative service source | `cms-slice/scripts/chat_server.py` here |
| Existing live runtime | `/Users/cep4u/daylight-chat-alternative-runtime` |
| Existing alternative guest database | `/Users/cep4u/daylight-chat-alternative-runtime/cms-slice/var/chat-alternative-profiles/guides.sqlite3` |
| Shared $1/UTC-day AI ledger | `/Users/cep4u/daylight/cms-slice/var/ai-budget/usage.sqlite3` |
| Original UI | http://127.0.0.1:8890/ · `../../cms-slice/apps/ten-question/` |
| Retained old source snapshot | `/Users/cep4u/Documents/Codex/2026-10-23/task/daylight-chat-alternative` · noncanonical fallback |

## Current D79 conversation

The owner authorized the task-based hybrid conversation on October 27. Deterministic controls avoid model calls; natural text uses the existing grounded AI service when needed. See [delivery and limits](docs/product/ADAPTIVE_CONVERSATION.md). The 41-ID inventory/78 original field paths remain traceability, with 14 explicit gaps and independently held source/recommendation gates.

## Product authority

Read the main repository's [principles](../../PRINCIPLES.md), [strategy and change checklist](../../docs/product/STRATEGIC_THESIS.md), [owner requirements](../../DAYLIGHT_REQUIREMENTS.md) and [master design](../../docs/product/MASTER_DESIGN.md).
The alternative's [ALT73/ALT74 decisions](docs/product/MASTER_DESIGN.md), [delivery history](docs/product/CHAT_ALTERNATIVE_DELIVERY.md), [customer question map](docs/product/CUSTOMER_PROFILE_QUESTION_MAP.md) and [readiness contract](docs/product/CUSTOMER_PROFILE_READINESS.md) preserve its own accepted conversation and capability gates.
Its 38 primary plus 3 child questions are conditional preparation, not mandatory intake. Reported information, external verification and sample browsing remain separate.

Machine-readable profile inputs are [the empty template](cms-slice/config/profile/customer-profile.template.json) and [schema](cms-slice/config/profile/customer-profile.schema.json). They are source configuration, not customer records.
Inherited root product documents and original guide copies here are retained historical context; they do not create another shared master or change the main UI.

## Run and update the existing service

The existing launchd job `gui/501/com.daylight.chat-alternative.8891` continues to run the dedicated runtime's `cms-slice/scripts/chat_server.py --port 8891`.
Its plist, working directory, logs, credentials lookup and guest data were left in place. No restart was needed for the relocation because runtime code already matched the copied source.
Live settings still load from the original `/Users/cep4u/daylight/.env`; do not copy or print that file.

From this directory, compare all deployable apps/scripts/config files without writing or restarting:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 runtime/sync_runtime.py --check
```

After making and checking an authorized alternative change, update from **this canonical source**, with a source-only before-image and identity-checked alternative restart:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 runtime/sync_runtime.py --apply --restart
```

The script requires this canonical location, checks the exact launchd service and port ownership before an update, and copies only allowlisted source assets. It never copies `.env`, runtime stores, logs, budget data, launch configuration or main-repo files. It does not remove runtime-only files. Backups go to ignored `runtime/backups/`. A backend update needs `--restart`; unchanged code never triggers a restart.
The former `install_runtime.py` and `deploy_profile_gates.py` names delegate to this same explicit workflow; they no longer install or restart by default.
Do not run the live server directly from this nested source: its inherited storage guard rejects profiles under the original repository. Use the preserved runtime for live operation and temporary fixture storage for development.

## Development without paid AI or live guest writes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cms-slice/tests -p 'test_chat_alternative.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cms-slice/tests -p 'test_profile_readiness.py'
node cms-slice/tests/test_chat_alternative_core.js
node cms-slice/tests/test_chat_alternative_dom.js
node cms-slice/tests/test_chat_conditionals_dom.js needs
node cms-slice/tests/test_profile_gate_dom.js
```

These use synthetic models and temporary databases. For an isolated fixture service on an unused port, choose a new temporary database (never a live store):

```sh
fixture_dir=$(mktemp -d /tmp/daylight-chat-fixture.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 python3 cms-slice/scripts/chat_server.py --fixture --port 8892 --database "$fixture_dir/guides.sqlite3"
```

For D79 on October 27, the owner separately authorized browser testing and bounded live AI verification under the existing $1/UTC-day cap. The relocation itself did not authorize those checks.

## Preservation and rollback

The retained Documents source is a fallback, not an editing or deployment target. Historical paths inside before-images and dated verification records describe prior work.
[Relocation evidence](../../docs/reviews/2026-10-25/CHAT_FIRST_RELOCATION.md) records integrity, checks, exclusions and the checkpoint path.
No live source or launch change occurred: rollback of the relocation needs **no service action and no data restore**. Both URLs continue to run from their original locations even if work in the new folder is paused.
Before resuming edits in the retained source, deliberately reconcile any later changes and update the canonical pointers; do not deploy divergent copies. Restore documentation selectively from the checkpoint only after comparing later edits. Keep both source trees and all storage.
For a future source deployment rollback, use that deployment's `runtime/backups/<timestamp>/manifest.json` to restore only listed source files to the alternative runtime, then identity-check and restart only its 8891 job. Never restore or reset guest databases or the shared ledger as part of a source rollback.
For D79 records, retain additive readiness readers/validators when reverting the interface or controller; see [the data-compatible rollback limits](docs/product/ADAPTIVE_CONVERSATION.md#operations-and-rollback).
