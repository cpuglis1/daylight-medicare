# Repository organization and preservation

The October 21, 2026 sweep is a documentation/organization change under requirement D39. It preserves D01/D02 content, D21 behavior, D23 evidence/privacy gates, and D24 review limits. No runtime import, public asset, test fixture, source registry, data archive, report, runtime config, release pointer, or original v1.2 bundle was moved or edited.

## What changed

- Root README now leads to current architecture, setup, data provenance/gaps, status/planning, review and Git guidance.
- Five older root `DAYLIGHT_*` design/journey proposals moved to `docs/archive/product-history/`. Their teaching content remains available; relative navigation and current product links were corrected.
- `PRODUCT.md` links now locate those histories. `DAYLIGHT_REQUIREMENTS.md` records D39, the owner's no-loss/no-UI-regression/no-push scope. `cms-slice/README.md` gets a current-status warning above its detailed historical commands. `.gitignore` has narrow additive local/generated rules.
- Existing action/dependency plans, current Collier plan/review queue, source evidence, historical findings, audit outputs and original bundle stay in place and are indexed in `docs/README.md`.

This deliberately avoids moving path-sensitive data or forcing a speculative code restructure. `ACTION_REFERENCE.md` and `PLAN_OF_ATTACK.md` remain at their original paths because existing evidence references them, including a historical hashed audit. Runtime imports/manifests depend on many other current paths. Uncertain scratch, tool environments and dated source caches are retained, not assumed disposable.

## Preservation evidence

The inventory was taken before any project writes: **5,106 files**, **434 directories**, **7,408,319,313 logical bytes**, no read errors. It includes all tracked/untracked/ignored files, caches and symlink targets; only the internal `.git/` database is excluded. Git HEAD/status/diff/index state were captured separately. Filesystem mode and modification time were also recorded; hashes establish byte retention, not a copy of all filesystem metadata.

- Full original hash manifest, Git baseline, initial tracked/untracked/ignored lists and pre-existing binary diff: `archive/local-checkpoints/cleanup-2026-10-21/` (ignored local checkpoint).
- Exact before-images of every deliberately edited/moved original document: `archive/cleanup-2026-10-21/originals/`, retaining original relative paths.
- [Migration ledger](reviews/2026-10-21/migration-ledger.json): source/destination/reason/original SHA-256 and before-image location.
- [Final retention check](reviews/2026-10-21/retention-verification-final.json): each original resolves to unchanged bytes at its original path, archived path, or recorded before-image. Intentional document edits are not counted as data loss.
- [Review](reviews/2026-10-21/REVIEW.md): tests, current-vs-baseline conditions, UI screenshots and limits.

No file-content deletion, repository reset/clean, untracking, commit, push, publish or external upload was performed. Ignore rules do not remove files. Existing backups, ignored data and original user changes remain available.

## Review or roll back without deleting anything

Read the ledger and retention result first. Before rollback, preserve the current versions too, especially if work continued after the sweep. **Do not use Git reset/clean**; most work was uncommitted before this task.

From repository root, the dry run prints the exact plan:

```sh
python3 docs/reviews/2026-10-21/rollback.py
```

After inspecting it, apply the non-destructive restore:

```sh
python3 docs/reviews/2026-10-21/rollback.py --apply
```

The script verifies each original before-image against the ledger, checks that the starting HEAD is unchanged, and refuses a second application. It first copies every current cleanup-authored file into a new timestamped local rollback folder, then restores edited original files and the five old root paths from verified before-images. It leaves new documentation and archived versions in place, so no cleanup deliverable is removed. If later versions differ, both copies remain. It does not alter the index, commit history, running service, source data or release pointer. The rollback receipt records restored paths and preserved current versions. Partial failures leave evidence and need inspection rather than blind rerun.

The complete original-content proof can be repeated with:

```sh
python3 docs/reviews/2026-10-21/verify_retention.py
```

That checker needs the local checkpoint. A clone without ignored local evidence cannot reproduce this full-workspace retention claim. Keep the checkpoint and data backup separately before moving computers.
