# Nightly sync

Every night at 3 AM a macOS launchd job pushes new local **code** to GitHub as
pull requests into `dev`.

```
~/daylight working copy ──select_files.py──▶ candidates
        (read only)                               │
                     headless Claude groups them into
                     nightly/<date>/<slug> branches (worktree, cannot push)
                                                  │
run.sh pushes branches, opens PRs into dev ◀──────┘
        │
Repository checks + Dependency security pass ─▶ auto-merge into dev
        │
standing "Promote dev to main" PR (label no-auto-merge) ─▶ owner merges by hand
```

- **Code only.** `docs/data`, `plans`, Postgres state, `audit-evidence`,
  `outputs`, private paths, bulk/data file types and files over 5 MB stay
  local. The pre-commit baseline checks still run on every commit.
- **Your working copy is never changed.** No staging, stashing, resets or
  branch switches in `~/daylight`; work happens in a separate worktree.
- **Clean-up** means grouping, commit messages and leaving out junk. File
  contents are not edited.
- PRs touching CI, hooks, governance files or files dev changed since the last
  push get `no-auto-merge` and wait for you.
- A file is offered again only when its local content changes
  (`~/Library/Application Support/daylight-nightly/state.json`).

## When it runs

launchd runs it at 3 AM if the Mac is awake. If the Mac is asleep or the lid
is closed, it runs once on the next wake. Closing the Claude app does not stop
it. The GitHub side (checks, auto-merge into dev) runs in the cloud either way.

## Commands

```bash
tools/nightly/install.sh                     # install or refresh (copies to ~/Library/Application Support/daylight-nightly/bin)
tools/nightly/install.sh --uninstall         # remove the job
"$HOME/Library/Application Support/daylight-nightly/bin/run.sh" --dry-run   # show what would be pushed
launchctl kickstart "gui/$(id -u)/com.daylight.nightly-sync"                # run now
```

Logs: `~/Library/Application Support/daylight-nightly/runs/<date>/`.
