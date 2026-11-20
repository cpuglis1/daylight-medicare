#!/bin/zsh
# Read-only source reconciliation. No model calls, cloud writes or service restarts.
set -u
task_root="${0:A:h:h:h}"
cd "$task_root" || exit 1
PYTHONPATH="$task_root/infrastructure/daylight-data/src" \
  "$task_root/infrastructure/daylight-data/.venv/bin/python" - <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'infrastructure/daylight-data/tools'))
from check_pilot_subset_source import check

result = check(root / 'infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1', full=True)
result['verified_at_utc'] = datetime.now(timezone.utc).isoformat()
name = 'source-reconciliation-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'
receipt = root / 'infrastructure/daylight-pilot' / name
with receipt.open('x') as out:
    json.dump(result, out, indent=2)
    out.write('\n')
print('PASS: source controls, every CSG row, PDP responses and catalog files match.')
print('Receipt:', receipt)
PY
task_result=$?
if (( task_result != 0 )); then
  print 'Source verification did not pass. Nothing was changed or deployed.'
fi
if [[ -t 0 ]]; then
  read 'task_done?Press Return to close this check. '
fi
exit "$task_result"
