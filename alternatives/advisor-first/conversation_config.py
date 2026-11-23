"""Editable conversation checks and ordering guidance for the advisor (D155 Q2, Q8).

Purpose: one place that reads, validates and saves the two owner-editable files:

* ``config/conversation-checks.json``: the evals the simulated-conversation runner
  judges (one judge per check). Gates (privacy, sources) are read-only here: a save
  that changes a gate, adds or removes a check, or changes an ID is refused.
* ``config/conversation-instructions.json``: the ordering guidance paragraph the
  compose model reads (``natural_agent.compose_instructions``). Question order is
  AI guidance under D155 Q2, so the owner may tune it; the code gates stay in code.

Role: imported by natural_agent (guidance), dev_checks_http (the localhost
"Checks and instructions" page) and tools/evaluation/sim_conversations.py.

Decisions: files are re-read when their modification time changes, so an edit on
the dev page takes effect on the next turn with no restart; a missing or invalid
guidance file means "use the built-in text", never an error in a live turn;
writes are atomic (temp file, then replace) so a reader never sees half a file.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import tempfile
import threading

HERE = Path(__file__).resolve().parent
CHECKS_PATH = HERE / 'config/conversation-checks.json'
INSTRUCTIONS_PATH = HERE / 'config/conversation-instructions.json'
CHECK_ID = re.compile(r'[a-z][a-z0-9_]{1,40}')
# Bounds keep a pasted essay out of every compose prompt and every judge prompt.
MAX_GUIDANCE = 2000
MAX_QUESTION = 1200
MAX_TITLE = 80
EDITABLE_FIELDS = ('title', 'question', 'floor', 'failOnAny')
LOG = logging.getLogger('conversation_config')
_lock = threading.Lock()
_cache: dict[Path, tuple[float, object]] = {}


class ConfigError(ValueError):
    """A config file or a proposed edit is invalid; ``code`` is the HTTP status to report."""

    code = 422


def _read_json(path):
    """Return the parsed JSON at path, cached by modification time.

    Raises:
        OSError: the file cannot be read.
        ValueError: the file is not valid JSON.
    """
    mtime = path.stat().st_mtime_ns
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
    value = json.loads(path.read_text(encoding='utf-8'))
    with _lock:
        _cache[path] = (mtime, value)
    return value


def _write_json(path, value):
    """Atomically replace path with value as pretty JSON (0644; the file is in the repo)."""
    raw = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(raw)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    with _lock:
        _cache.pop(path, None)


def validate_checks(value):
    """Check the shape of a checks document.

    Args:
        value: the parsed conversation-checks.json.
    Returns:
        The list of check dicts.
    Raises:
        ConfigError: with a short reason naming the bad check.
    """
    if not isinstance(value, dict) or not isinstance(value.get('checks'), list) or not value['checks']:
        raise ConfigError('checks must be a non-empty list')
    seen = set()
    for check in value['checks']:
        if not isinstance(check, dict) or not CHECK_ID.fullmatch(str(check.get('id', ''))):
            raise ConfigError('each check needs a snake_case id')
        cid = check['id']
        if cid in seen:
            raise ConfigError(f'duplicate check id {cid}')
        seen.add(cid)
        if not isinstance(check.get('title'), str) or not 0 < len(check['title']) <= MAX_TITLE:
            raise ConfigError(f'{cid}: title must be 1-{MAX_TITLE} characters')
        if not isinstance(check.get('question'), str) or not 20 <= len(check['question']) <= MAX_QUESTION:
            raise ConfigError(f'{cid}: question must be 20-{MAX_QUESTION} characters')
        floor = check.get('floor')
        if isinstance(floor, bool) or not isinstance(floor, (int, float)) or not 0 <= floor <= 1:
            raise ConfigError(f'{cid}: floor must be a number from 0 to 1')
        for flag in ('gate', 'editable', 'failOnAny'):
            if not isinstance(check.get(flag), bool):
                raise ConfigError(f'{cid}: {flag} must be true or false')
        if check['gate'] and check['editable']:
            raise ConfigError(f'{cid}: a gate cannot be editable')
    return value['checks']


def load_checks(path=CHECKS_PATH):
    """Return the validated checks document (a dict with a ``checks`` list).

    Raises:
        ConfigError: the file is missing or invalid. Callers that judge
        conversations must not run with an unknown check set.
    """
    try:
        value = _read_json(path)
    except (OSError, ValueError) as error:
        raise ConfigError(f'cannot read {path.name}: {error}') from None
    validate_checks(value)
    return value


def save_checks(edits, path=CHECKS_PATH):
    """Apply owner edits to editable checks and save.

    Args:
        edits: a list of ``{id, title?, question?, floor?, failOnAny?}``. Every
            listed ID must exist; only EDITABLE_FIELDS of editable checks change.
    Returns:
        The saved document.
    Raises:
        ConfigError: an unknown ID, an edit to a read-only gate, an unknown
        field, or a value that fails validation. Nothing is written then.
    """
    current = load_checks(path)
    if not isinstance(edits, list):
        raise ConfigError('send checks as a list')
    by_id = {check['id']: dict(check) for check in current['checks']}
    for edit in edits:
        if not isinstance(edit, dict) or edit.get('id') not in by_id:
            raise ConfigError('unknown check id')
        target = by_id[edit['id']]
        changes = {key: value for key, value in edit.items() if key != 'id'}
        unknown = set(changes) - set(EDITABLE_FIELDS)
        if unknown:
            raise ConfigError(f"{edit['id']}: cannot change {sorted(unknown)}")
        if any(target.get(key) != value for key, value in changes.items()) and not target['editable']:
            # Gates change only by a reviewed commit (D155 Q8); the page shows them read-only.
            raise ConfigError(f"{edit['id']} is a read-only gate")
        target.update(changes)
    saved = {**current, 'checks': [by_id[check['id']] for check in current['checks']]}
    validate_checks(saved)
    _write_json(path, saved)
    return saved


def ordering_guidance(path=INSTRUCTIONS_PATH):
    """Return the owner's ordering guidance text, or None to use the built-in text.

    Never raises: a live turn must not fail because this file is missing or
    malformed; the problem is logged (file name only) and the default applies.
    """
    try:
        value = _read_json(path)
        text = value.get('orderingGuidance') if isinstance(value, dict) else None
        if isinstance(text, str) and text.strip() and len(text) <= MAX_GUIDANCE and '\x00' not in text:
            return text
        LOG.warning('conversation_config: %s has no valid orderingGuidance; using the built-in text', path.name)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        LOG.warning('conversation_config: cannot read %s; using the built-in text', path.name)
    return None


def save_ordering_guidance(text, path=INSTRUCTIONS_PATH):
    """Save new ordering guidance text.

    Raises:
        ConfigError: empty, longer than MAX_GUIDANCE, or containing NUL.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_GUIDANCE or '\x00' in text:
        raise ConfigError(f'ordering guidance must be 1-{MAX_GUIDANCE} characters')
    try:
        current = _read_json(path)
    except (OSError, ValueError):
        current = {}
    _write_json(path, {**(current if isinstance(current, dict) else {}), 'orderingGuidance': text})
    return text
