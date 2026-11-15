#!/bin/bash
# Daylight nightly sync: push new local code to GitHub as PRs into dev.
#
# launchd runs this at 3 AM (com.daylight.nightly-sync). If the Mac is asleep
# then, launchd runs it once on the next wake. Flow:
#   1. select_files.py lists new/changed local code files missing from dev
#   2. headless Claude groups them into nightly/<date>/<slug> branches in a
#      separate worktree (it cannot push)
#   3. this script pushes those branches and opens PRs into dev; the
#      auto-merge workflow merges them once Repository checks and Dependency
#      security pass
#   4. keeps one dev -> main PR open for the owner to merge by hand
# The owner's working copy, index and stash are never modified.
#
# Options: --dry-run (selection only), --no-claude (stop before Claude).
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="${DAYLIGHT_REPO:-$HOME/daylight}"
APP="$HOME/Library/Application Support/daylight-nightly"
BIN="$APP/bin"
WT="$APP/worktree"
DAY="$(date +%F)"
RUN="$APP/runs/$DAY-$(date +%H%M%S)"
GH_REPO="${DAYLIGHT_GH_REPO:-cpuglis1/daylight-medicare}"
DRY=0; NOCLAUDE=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --no-claude) NOCLAUDE=1;; esac; done

mkdir -p "$RUN"
exec > >(tee -a "$RUN/run.log") 2>&1
echo "== Daylight nightly sync $(date) =="

if ! mkdir "$APP/lock" 2>/dev/null; then echo "Another run holds $APP/lock; exiting."; exit 0; fi
cleanup() {
  git --git-dir="$REPO/.git" worktree remove --force "$WT" >/dev/null 2>&1 || true
  git --git-dir="$REPO/.git" worktree prune >/dev/null 2>&1 || true
  rmdir "$APP/lock" 2>/dev/null || true
}
trap cleanup EXIT
G=(git --git-dir="$REPO/.git")
notify() { osascript -e "display notification \"$1\" with title \"Daylight nightly sync\"" >/dev/null 2>&1 || true; }

"${G[@]}" fetch origin dev main --quiet || { echo "fetch failed"; notify "Fetch failed; see $RUN/run.log"; exit 1; }

python3 "$BIN/select_files.py" select --repo "$REPO" --base origin/dev \
  --state "$APP/state.json" --out "$RUN/candidates.json" || { notify "File selection failed"; exit 1; }
COUNT=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["candidates"]))' "$RUN/candidates.json")
echo "candidates: $COUNT"
if [ "$DRY" = 1 ]; then echo "dry run; candidates in $RUN/candidates.json"; exit 0; fi

if [ "$COUNT" -gt 0 ] && [ "$NOCLAUDE" = 0 ]; then
  rm -rf "$WT"; "${G[@]}" worktree prune
  "${G[@]}" worktree add --detach "$WT" origin/dev >/dev/null || { notify "Worktree setup failed"; exit 1; }
  cd "$WT" || exit 1
  PROMPT=$(sed -e "s|@REPO@|$REPO|g" -e "s|@RUN@|$RUN|g" -e "s|@DAY@|$DAY|g" "$BIN/prompt.md")
  # Two-hour ceiling so a stuck run never blocks the next night.
  perl -e 'alarm shift; exec @ARGV' 7200 claude -p "$PROMPT" \
    --add-dir "$REPO" "$RUN" \
    --allowedTools "Read" "Write" "Grep" "Glob" "Bash(git switch:*)" "Bash(git add:*)" \
      "Bash(git commit:*)" "Bash(git rm:*)" "Bash(git status:*)" "Bash(git diff:*)" \
      "Bash(git log:*)" "Bash(git restore:*)" "Bash(git show:*)" "Bash(rsync:*)" \
      "Bash(rm:*)" "Bash(ls:*)" "Bash(wc:*)" "Bash(head:*)" "Bash(jq:*)" \
    --disallowedTools "Bash(git push:*)" "Bash(git remote:*)" "Bash(git config:*)" \
    > "$RUN/claude.txt" 2>&1
  echo "claude exit: $? (transcript: $RUN/claude.txt)"

  PUSHED=()
  OPENED=0
  if [ -f "$RUN/manifest.json" ]; then
    gh label create no-auto-merge -R "$GH_REPO" --color B60205 \
      --description "Owner reviews before merge" >/dev/null 2>&1 || true
    N=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("prs",[])))' "$RUN/manifest.json")
    for ((i=0; i<N; i++)); do
      python3 - "$RUN/manifest.json" "$i" "$RUN/pr-$i" <<'PY'
import json, sys
pr = json.load(open(sys.argv[1]))["prs"][int(sys.argv[2])]
base = sys.argv[3]
open(base + ".branch", "w").write(pr["branch"])
open(base + ".title", "w").write(pr["title"])
open(base + ".body", "w").write(pr["body"])
open(base + ".auto", "w").write("yes" if pr.get("auto_merge") else "no")
PY
      B=$(cat "$RUN/pr-$i.branch")
      case "$B" in nightly/"$DAY"/*) ;; *) echo "skip unexpected branch $B"; continue;; esac
      "${G[@]}" rev-parse --verify --quiet "refs/heads/$B" >/dev/null || { echo "missing branch $B"; continue; }
      if "${G[@]}" diff --quiet origin/dev "refs/heads/$B"; then echo "empty branch $B"; continue; fi
      "${G[@]}" push origin "refs/heads/$B:refs/heads/$B" || { echo "push failed $B"; continue; }
      LABEL=(); [ "$(cat "$RUN/pr-$i.auto")" = no ] && LABEL=(--label no-auto-merge)
      gh pr create -R "$GH_REPO" --base dev --head "$B" --title "$(cat "$RUN/pr-$i.title")" \
        --body-file "$RUN/pr-$i.body" "${LABEL[@]}" && OPENED=$((OPENED+1))
      PUSHED+=("$B")
      "${G[@]}" branch -D "$B" >/dev/null 2>&1 || true
    done
    JSON=$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${PUSHED[@]+"${PUSHED[@]}"}")
    python3 "$BIN/select_files.py" record --state "$APP/state.json" --candidates "$RUN/candidates.json" \
      --manifest "$RUN/manifest.json" --pushed-branches "$JSON"
  else
    echo "no manifest written; nothing pushed"
  fi
  notify "Opened $OPENED PR(s) into dev from $COUNT changed file(s)."
fi

# Keep one owner-merged dev -> main PR open whenever dev is ahead.
"${G[@]}" fetch origin dev main --quiet || true
AHEAD=$("${G[@]}" rev-list --count origin/main..origin/dev)
if [ "$AHEAD" -gt 0 ] && [ -z "$(gh pr list -R "$GH_REPO" --base main --head dev --state open --json number --jq '.[0].number')" ]; then
  gh pr create -R "$GH_REPO" --base main --head dev --label no-auto-merge \
    --title "Promote dev to main" \
    --body "Standing promotion PR, opened by the nightly sync. dev is $AHEAD commit(s) ahead of main. Merge it by hand when dev is ready; it never auto-merges.

🤖 Generated with [Claude Code](https://claude.com/claude-code)" || true
fi
echo "== done $(date) =="
