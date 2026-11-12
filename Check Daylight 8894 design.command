#!/bin/zsh
# Re-runs the Impeccable detector on the :8893 and :8894 front ends and exits.
cd "$(dirname "$0")" || exit 1
OUT=audit-evidence/ui-refresh-8894-20261105
I="$HOME/.agents/skills/impeccable/scripts/impeccable"
"$I" detect --json alternatives/advisor-first/web-8894 > "$OUT/impeccable-8894.json" 2>&1
"$I" detect --json alternatives/advisor-first/web > "$OUT/impeccable-8893.json" 2>&1
echo "Impeccable results saved in $OUT. You can close this window."
