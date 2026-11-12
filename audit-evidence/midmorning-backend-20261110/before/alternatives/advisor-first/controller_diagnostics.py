"""Value-free locations for unexpected controller failures, never request data."""
from pathlib import Path
import re
import traceback


HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / 'chat-first' / 'cms-slice' / 'scripts'


def unexpected_failure(error):
    """Return only a code-defined exception class and allowlisted source lines.

    Exception messages, source text, locals, payloads and identifiers must never
    enter operational diagnostics. Keep the original exception/HTTP behavior.
    """
    name = type(error).__name__
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
        name = 'Exception'
    locations = []
    for frame in traceback.extract_tb(error.__traceback__):
        path = Path(frame.filename).resolve()
        if path.parent not in {HERE, ENGINE}:
            continue
        if not re.fullmatch(r'[a-z_]+\.py', path.name):
            continue
        locations.append(f'{path.name}:{frame.lineno}')
    return {'code': 'unexpected_exception', 'type': name,
            'locations': ','.join(locations[-8:]) or 'unavailable'}
