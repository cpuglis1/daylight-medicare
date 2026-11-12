# Chat-first source relocation · October 25, 2026

Owner authorization: move the alternative Daylight chat product into Daylight without disturbing either UI. **D75 changes source organization only.** D63/D64 privacy, aggregate spend and independence, D73 review criteria, original D66/D71/D72 contracts and alternative ALT73/ALT74 gates remain in force.

## Final locations

| Item | Location / disposition |
| --- | --- |
| Canonical alternative source | `/Users/cep4u/daylight/alternatives/chat-first` · edit here |
| Original source/UI | Root `cms-slice/` · http://127.0.0.1:8890/ · unchanged |
| Alternative UI | http://127.0.0.1:8891/ · separate conversation, unchanged |
| Existing alternative runtime | `/Users/cep4u/daylight-chat-alternative-runtime` · unchanged |
| Old editable source | `/Users/cep4u/Documents/Codex/2026-10-23/task/daylight-chat-alternative` · retained noncanonical fallback |
| Profile question map | `alternatives/chat-first/docs/product/CUSTOMER_PROFILE_QUESTION_MAP.md` |
| Profile readiness contract | `alternatives/chat-first/docs/product/CUSTOMER_PROFILE_READINESS.md` |
| Empty profile template/schema | `alternatives/chat-first/cms-slice/config/profile/customer-profile.template.json` and `customer-profile.schema.json` |

The new source belongs to the main `/Users/cep4u/daylight` Git repository. The old source was not its own Git checkout (Git discovered an ancestor home-directory repository); no Git metadata was copied or changed.

## Work completed

- Inventoried source/runtime and the actual launchd service before edits. All 131 deployable apps/scripts/config files matched. The live job is `gui/501/com.daylight.chat-alternative.8891`, using the existing sibling runtime's plist, Python script and working directory. macOS's prior Documents restriction required no permission change.
- Copied **590 files / 31,570,003 bytes**, verifying every copied file against its old-source SHA-256 before documentation/helper edits. Retained the small historical evidence and original-guide snapshots as context. Excluded two Python cache directories and two runtime log files. No `.git`, dependencies, credentials or live guest/budget stores were copied; none needed moving.
- Updated canonical source pointers, root entry points and development instructions. Shared main principles/strategy/master remain authoritative; local ALT73/ALT74 contracts retain the alternative's interaction. Inherited copies are explicitly scoped as dated context. The old source received only an AGENTS notice and `SOURCE_MOVED.md`; its app payload remains intact.
- Replaced one-off, implicit deployment helpers with one canonical comparison/source-sync entry point. Default and `--check` are read-only; future explicit `--apply --restart` backs up changed source and checks launchd/PID/8891 ownership. It excludes stores, settings, launch configuration and logs and preserves runtime-only files. Old helper filenames route to that workflow. The source-side plist/metadata now describe the existing runtime accurately; the live plist was not edited.
- No runtime deployment, restart, install, deletion of user files, commit or push. Original app payloads, both live services and original settings were not edited.

## Checks and limits

| Check | Result |
| --- | --- |
| Before/after HTTP | Both roots, their JS/CSS, status and alternative config returned 200 with identical response hashes. Alternative config still identifies :8891 and links to :8890. |
| Source identity | Original `cms-slice/apps`, `scripts`, `config` hashes unchanged. Alternative canonical deployable payload matches runtime exactly. No change to either UI's source/design. |
| Process identity | Listener PIDs remained 72890 (:8890) and 91311 (:8891); launchd identified the expected alternative job/runtime. No process was stopped. |
| Existing data | All 32 pre-existing files in main `cms-slice/var` and the alternative guest database retained their hashes; no existing file disappeared. During checking, five additional L01-related rollback/log files appeared in main `var`; these were not created or changed by this relocation and were left alone. |
| Budget/guest boundary | Existing original, previous-guide and alternative guest databases stay in their original places. Alternative cookie remains `daylight_chat_alt_dev`. Both status responses showed the same $1/UTC-day budget, $0 accounted and 0 requests. Ledger path remains `/Users/cep4u/daylight/cms-slice/var/ai-budget/usage.sqlite3`. |
| Focused Python tests | 6 alternative model/HTTP/guest-isolation checks and 10 profile-readiness checks passed from the new source, using synthetic model responses and temporary databases. |
| Focused Node checks | Existing conversation-core, semantic DOM, conditional needs and profile-gate scripts passed. All-unknown input remains incomplete; explicit samples remain separate; external recommendation holds remain. These are not rendered-browser tests. |
| Sync/settings/config | `runtime/sync_runtime.py --check` reports 131 files and zero differences. Local profile JSON imports work in focused tests. Existing `.env` lookup still points to the original location without reading or copying credentials for relocation. |
| Ignore rules | New-source stores, `.env`, logs, caches, dependencies, raw/releases and future runtime backups are excluded. Checkpoint path is ignored. |

**Not exercised:** browser/Firefox, rendered desktop/tablet/phone review, microphone, real paid-provider behavior, or the future sync write/restart branch. Browser access remains paused. Since live payloads already matched, applying a deployment or restart would add no relocation evidence. Tests do not establish owner usability approval, source/domain acceptance or a recommendation release.

D73 checklist: consumer task/accepted teaching/correction paths, consequential intake and fair coverage-path presentation are unaffected because UI/service payloads did not change. Synthetic checks preserve reported-input versus external verification gates and sample labeling. No commercial decision feature, source evidence or acceptance state changed. Permission/control is evidenced by retained guest stores, unchanged budget/cookies/settings and zero paid requests. Actual capability is a source relocation and reproducible source/runtime comparison; consumer comprehension, economics, complete market coverage and future enrollment/review operations remain unproved.

## Preservation evidence, Git scope and rollback

Local ignored checkpoint:

`archive/local-checkpoints/chat-first-relocation-20261025T180902Z/`

It contains `before.json`, `copy-manifest.json`, `after.json`, HTTP after-evidence, main-doc before-images and a generated synthetic conditional trace. Manifests contain hashes/paths and sanitized service status, not raw guest records or credentials. The original pre-copy source and before-images preserve all deliberately revised documents/helpers.

This task added `alternatives/` and this report and made targeted additions to root `README.md`, `AGENTS.md`, `DAYLIGHT_REQUIREMENTS.md`, `docs/DEVELOPMENT.md`, `docs/product/MASTER_DESIGN.md` and `docs/product/STRATEGIC_THESIS.md`. The repository already had substantial staged/untracked/modified work; this task did not stage, reset, discard, commit or push it. New alternative files remain untracked. Full pre/post status is in the checkpoint; do not interpret the whole repository diff as this task's changes.

Rollback now requires **no service or data action**: both apps still run from their former runtime locations. Keep the copied tree and fallback. If deliberately returning to the old source as canonical, first compare later work, then update the pointers/notice; selectively restore documentation before-images only after checking for later edits. Do not reset the working tree or restore databases.

For a future source deployment, use its ignored `runtime/backups/<timestamp>/manifest.json` to restore only the listed existing source files, verify the exact alternative job/port identity, and restart only that job if needed. Preserve newly added files for inspection and never include guest/budget data in source rollback.

No remaining relocation blocker. Sandbox-restricted loopback checks/tests and the two old-source notices were completed through narrowly scoped approved execution; no security setting or privacy permission was expanded.
