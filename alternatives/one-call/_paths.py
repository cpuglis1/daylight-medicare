"""Import path for the one-call variant.

The variant reuses advisor-first's deterministic code and its pinned engine
without editing either. Importing this module puts advisor-first on sys.path
and imports its `server` module, which verifies the engine lock, installs the
model-route bypass guard and registers the pinned engine imports.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ADVISOR = REPO / 'alternatives/advisor-first'

for entry in (str(ADVISOR), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import server  # noqa: E402,F401  (side effects described above)
