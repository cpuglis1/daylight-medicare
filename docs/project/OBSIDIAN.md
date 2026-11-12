# Daylight knowledge in Obsidian

> **Retired (D142, November 11, 2026).** This vault and its refresh tooling are no longer used. Business context now lives in the Daylight Brain; see [CURRENT_STATE](CURRENT_STATE.md), "How work runs". This runbook is kept as history.

D113 · November 9, 2026 · Owner's Mac · Codex and Claude Code.

The existing vault is `/Users/cep4u/daylight/daylight_obsidian`. Open
`00 Start/Daylight Home.md`. The vault is ignored by Git because it contains
private Drive representations and owner ChatGPT history. The shared skills and
maintenance code are project files; no remote publication is performed by setup.

## Authority and scope

The authority order in `CURRENT_STATE.md` remains binding. Local originals,
sealed evidence and Drive originals stay in place. Notes under `90 Sources`
are generated reference copies; edit their personal-notes sections or author
separate notes. Old capability tables and chats remain visibly dated. Never
promote an import, test result or model assertion into source/method/purpose
acceptance. Source STOPs persist. This knowledge layer does not feed the advisor,
its recommendation context or customer stores. Commercial/business notes must
stay outside consumer decision inputs under D64.

Local scope covers the Daylight tree with an exact path/disposition inventory.
Dependencies, generated vault/backup paths, credentials, databases and private
runtime conversation/guest stores are excluded explicitly. Code and bulk evidence
are linked in file catalogs; Markdown and selected narrative text are searchable
snapshots. Connected scope covers the DaylightMedicare folder tree plus targeted
Drive discovery, and relevant ChatGPT discussions. Neither listing titles nor
extracting text establishes all-account semantic completeness. The vault's
coverage report records the actual scope and remaining gaps.

## Refresh

From `/Users/cep4u/daylight`:

```sh
python3 tools/obsidian/sync.py refresh
python3 tools/obsidian/sync.py check
python3 tools/obsidian/sync.py status
python3 tools/obsidian/sync.py backup
```

`refresh` scans local sources and renders already captured Drive/ChatGPT inputs.
It makes **no network or model calls**. For fresh connected sources, ask Codex
to use `$daylight-knowledge` and run the connector collection procedure in
`tools/obsidian/CONNECTED_REFRESH.md` first. Claude can read the shared local
vault; direct connected refresh needs its own authorized connector or a Codex
capture. No credentials are copied between agents.

Source IDs and content hashes control identity and change detection. A renamed
Drive document keeps its note identity. Existing generated-body edits are not
overwritten: incoming copies go into `91 Reviews/Incoming`. Personal notes below
the explicit divider survive normal refreshes. Previous changed projections are
kept in the hidden `.knowledge-imports/history` directory. Missing sources retain
their last note and get flagged. The importer never writes back to a source.

## Shared skills

Canonical project skills are in `.agents/skills`. `.claude/skills` links to the
same files. `CLAUDE.md` imports `AGENTS.md`; it does not create another set of
project rules. The vault's `AGENTS.md` gives the same authority and editing
boundaries when an agent starts inside the vault. New skills become available on
the next Codex turn; restart a Claude session if its skill picker is stale.

The pinned Obsidian format skills are from kepano/obsidian-skills. Daylight
handoff and domain-modeling adaptations retain Matt Pocock attribution/license;
reflection and feature verification adapt Lauren Tan's workflow concepts to
Daylight's existing governance. See `tools/obsidian/skills.lock.json` and the
vault's skill catalog. No timers, agent creation or paid probes were enabled.

## Conflicts and recovery

Open `91 Reviews/Owner decisions needed.md` for substantive conflicts, and
`91 Reviews/Import review queue.md` for mechanical changes and extraction limits.
Write resolutions in separate review notes with source/version/evidence links.
Binding direction follows the existing numbered requirement and directive-history
process. A review note by itself does not release a consumer purpose.

`backup` creates a full vault archive under `tmp/obsidian-backups`, reads every
archived file back and compares its SHA-256, and writes a hash manifest. Restore
into a new empty folder, verify against the manifest, then open that folder as a
separate vault before any deliberate replacement. Same-Mac copies protect against
editing errors; an independent off-machine backup destination remains to be chosen.
Pre-setup files are preserved under `tmp/obsidian-setup-20261109/before`.

## Validation

```sh
python3 -m unittest discover -s tools/obsidian -p 'test_*.py' -v
python3 tools/obsidian/sync.py check
```

Tests use isolated fictional files and cover idempotence, annotation preservation,
edited-copy conflicts, missing-source retention, exclusion and path boundaries,
link rewriting, document tabs, chat attribution and backup readback. The vault's
`99 System/Setup verification.md` records actual setup counts and checks. Product
tests and consumer acceptance are separate and are not claimed by this setup.
