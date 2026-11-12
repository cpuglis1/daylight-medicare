#!/bin/zsh
# Daylight :8894 UI refresh. Runs the Impeccable detector on the old and new
# front ends, then serves :8894 in front of the running :8893 backend.
# Close this window (or press Control-C) to stop :8894. :8893 is unaffected.
cd "$(dirname "$0")" || exit 1
OUT=audit-evidence/ui-refresh-8894-20261105
mkdir -p "$OUT"
I="$HOME/.agents/skills/impeccable/scripts/impeccable"
echo "Running Impeccable…"
"$I" context > "$OUT/impeccable-context.txt" 2>&1
"$I" detect --json alternatives/advisor-first/web-8894 > "$OUT/impeccable-8894.json" 2>&1
"$I" detect --json alternatives/advisor-first/web > "$OUT/impeccable-8893.json" 2>&1
echo "Impeccable results saved in $OUT"
exec python3 alternatives/advisor-first/ui-8894/serve.py
