"""Localhost turn traces for the :8893 advisor and its :8894 preview (D155 Q6).

Purpose: when Charlie tests the advisor on his own machine, every conversation
turn is saved as one JSON file keyed by its turn ID (the request's
``requestId``), so the :8894 side panel and agents (``tools/show_turn.py``) can
show exactly what happened in that turn: the facts saved, the source lookups,
each model call with its full prompt and raw output, the checks that fired and
the next question.

Role: ``install_turn_traces(service, root)`` wraps one built server in place.
``server.build`` calls it only for a local, non-pilot, non-hosted run; a pilot
or hosted run refuses it outright (D155 Q6a: localhost saves everything, real
users save nothing, the pilot is hard-off).

Key decisions:
- Capture is by wrapping, never by editing the pinned engine or the turn
  logic: the turn method, each agent's ``_complete`` (composition) and ``run``
  (extraction), the client ``transport`` when one is already set, and the
  ``urlopen`` name inside ``narrative_agent`` (extraction without a transport).
  Every wrapper returns the original result and re-raises the original error,
  so behavior is unchanged; tests assert this.
- A thread-local collector ties calls to the turn: one HTTP request thread runs
  one whole turn (no worker threads in the turn path), so nothing leaks across
  visitors.
- Checks fired are the bounded WARNING diagnostics the agent and flow already
  log (they never contain the person's words), plus the turn's
  ``validation_recovery`` and ``source_fallback`` records.
- Files are owner-scoped: each record stores a hash of the owner digest, and
  the HTTP routes only return records whose owner matches the caller's cookie.
- The store keeps the newest ``MAX_TURNS`` files so a long test day cannot
  fill the disk.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

TURN_ID = re.compile(r'[A-Za-z0-9-]{10,80}')
MAX_TURNS = 2000
# Loggers whose WARNING lines are the turn's bounded check diagnostics.
CHECK_LOGGERS = ('natural_agent', 'natural_flow', 'narrative_agent')

_local = threading.local()


class TraceDisabled(ValueError):
    """Raised when traces are requested for a pilot or hosted service."""


def owner_key(owner):
    """Return a short stable hash of an owner digest for file records.

    Args:
        owner: the profile owner digest the engine passes to ``turn``.
    Returns:
        A 24-character hex string; never the digest itself, so a trace file
        cannot be replayed as a session identifier.
    """
    return hashlib.sha256(('turn-trace:' + str(owner)).encode()).hexdigest()[:24]


class _Collector:
    """Everything observed during one turn on the current thread."""

    def __init__(self):
        self.calls = []
        self.checks = []
        self.requests = []


def active():
    """Return the current thread's collector, or None outside a traced turn."""
    return getattr(_local, 'collector', None)


class _CheckHandler(logging.Handler):
    """Copies WARNING-and-above diagnostics into the active collector only."""

    def emit(self, record):
        """Append the formatted diagnostic when a turn is being traced on this thread."""
        collector = active()
        if collector is None:
            return
        try:
            collector.checks.append({'source': record.name, 'level': record.levelname,
                                     'message': record.getMessage()})
        except Exception:  # A trace must never break the turn it observes.
            pass


_HANDLER = _CheckHandler(logging.WARNING)


class TraceStore:
    """One JSON file per turn under ``root``, newest ``MAX_TURNS`` kept."""

    def __init__(self, root, max_turns=MAX_TURNS):
        """Create the store directory with owner-only permissions.

        Args:
            root: directory for trace files (gitignored ``cms-slice/var``).
            max_turns: how many files to keep before pruning the oldest.
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.max_turns = max_turns
        self.lock = threading.Lock()

    def path(self, turn_id):
        """Return the file path for a validated turn ID.

        Raises:
            ValueError: when the ID is not a request ID shape (no path tricks).
        """
        if not isinstance(turn_id, str) or not TURN_ID.fullmatch(turn_id):
            raise ValueError('Use a turn ID.')
        return self.root / f'{turn_id}.json'

    def save(self, record):
        """Write one turn record atomically, then prune the oldest files."""
        target = self.path(record['turnId'])
        temporary = target.with_suffix('.tmp')
        with self.lock:
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str))
            os.chmod(temporary, 0o600)
            temporary.replace(target)
            files = sorted(self.root.glob('*.json'), key=lambda item: item.stat().st_mtime)
            for old in files[:max(0, len(files) - self.max_turns)]:
                old.unlink(missing_ok=True)

    def get(self, turn_id, owner=None):
        """Return one record, or None when missing or owned by someone else.

        Args:
            turn_id: the request ID of the turn.
            owner: when given, the caller's owner digest; other owners' turns
                read as missing. The CLI passes None (local agent access).
        """
        try:
            record = json.loads(self.path(turn_id).read_text())
        except (OSError, ValueError):
            return None
        if owner is not None and record.get('owner') != owner_key(owner):
            return None
        return record

    def list(self, owner=None, limit=200):
        """Return turn summaries, oldest first, for one owner (or all when None)."""
        rows = []
        for item in sorted(self.root.glob('*.json'), key=lambda p: p.stat().st_mtime)[-limit * 4:]:
            try:
                record = json.loads(item.read_text())
            except (OSError, ValueError):
                continue
            if owner is not None and record.get('owner') != owner_key(owner):
                continue
            rows.append({key: record.get(key) for key in
                         ('turnId', 'startedAt', 'action', 'message', 'status', 'nextQuestion', 'latencyMs')})
        return rows[-limit:]


def _guide_fields(value):
    """Return the guide's ``fields`` dict from a turn payload or result."""
    guide = value.get('guide') if isinstance(value, dict) else None
    fields = guide.get('fields') if isinstance(guide, dict) else None
    return fields if isinstance(fields, dict) else {}


def facts_saved(before, after):
    """Return the guide fields this turn added, changed or removed.

    Args:
        before: the turn request payload.
        after: the turn result.
    Returns:
        A list of ``{'field', 'before', 'after'}`` rows, sorted by field.
    """
    old, new = _guide_fields(before), _guide_fields(after)
    return [{'field': key, 'before': old.get(key), 'after': new.get(key)}
            for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)]


def _lookups(calls):
    """Return the source lookups this turn's model calls were given.

    Retrieval runs in code before each model call (D155 Q5), so the lookup's
    input and output are read back from the prompt each call received.
    """
    tools = []
    for call in calls:
        try:
            content = json.loads(call['request']['input'][0]['content'])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if call['kind'] == 'compose':
            context = content.get('resolved_context') or {}
            evidence = context.get('evidence') or []
            tools.append({'tool': 'reviewed_source_lookup', 'stage': 'compose',
                          'input': {'message': context.get('current_message')},
                          'output': {'messageEvidenceIds': context.get('message_evidence_ids'),
                                     'evidence': [{'id': item.get('id'), 'title': item.get('title'),
                                                   'kind': item.get('kind')} for item in evidence
                                                  if isinstance(item, dict)]}})
        elif call['kind'] == 'extract':
            facts = content.get('reviewed_facts') or []
            tools.append({'tool': 'reviewed_source_lookup', 'stage': 'extract',
                          'input': {'message': content.get('submitted_text'), 'node': content.get('current_node')},
                          'output': {'facts': [item.get('id') if isinstance(item, dict) else item for item in facts]}})
    return tools


def _turn_checks(collector, result):
    """Return the diagnostics and recovery records that fired this turn."""
    checks = list(collector.checks)
    generated = result.get('generated') if isinstance(result, dict) else None
    if isinstance(generated, dict):
        for key in ('validation_recovery', 'source_fallback'):
            if generated.get(key):
                checks.append({'source': 'generated', 'level': 'INFO', 'message': key,
                               'detail': generated[key]})
    return checks


def _wrap_call(agent, name, kind):
    """Wrap one agent method so each call is recorded in the active collector.

    The wrapper returns the method's own result and re-raises its own error.
    """
    original = getattr(agent, name)

    def traced(*args, **kwargs):
        collector = active()
        if collector is None:
            return original(*args, **kwargs)
        mark, usage = len(collector.requests), getattr(agent, 'usage', [])
        usage_mark = len(usage)
        entry = {'kind': kind, 'model': getattr(agent.client, 'model', None), 'status': 'error'}
        started = time.perf_counter()
        result = None
        try:
            result = original(*args, **kwargs)
            entry['status'] = 'ok'
            return result
        except Exception as error:
            entry['error'] = f'{type(error).__name__}: {error}'
            raise
        finally:
            entry['latencyMs'] = round((time.perf_counter() - started) * 1000)
            if name == '_complete':
                entry['request'] = args[0] if args else kwargs.get('payload')
                if isinstance(result, tuple) and len(result) == 2:
                    entry['response'], entry['rawOutput'] = result
                    entry['providerStatus'] = (result[0] or {}).get('status')
            else:
                noted = collector.requests[mark:]
                entry['request'] = noted[0] if noted else None
                if not noted and entry['status'] == 'ok':
                    entry['status'] = 'cached'  # Answered from the turn cache; no model call.
                entry['rawOutput'] = result
            entry['usage'] = usage[-1] if len(usage) > usage_mark else None
            entry = copy.deepcopy(entry)
            if isinstance(entry.get('usage'), dict):
                entry['tokens'] = {key: entry['usage'].get(key) for key in ('input_tokens', 'output_tokens', 'total_tokens')}
            collector.calls.append(entry)

    setattr(agent, name, traced)


def _note_request(payload):
    """Record a request payload sent by the agent on this thread, if traced."""
    collector = active()
    if collector is not None:
        collector.requests.append(copy.deepcopy(payload))


def _wrap_transport(client):
    """Wrap a client's existing ``transport`` to note each payload; skip when unset.

    A client with no transport streams through ``urlopen`` instead; wrapping
    None would switch it to the transport path and change behavior.
    """
    original = getattr(client, 'transport', None)
    if not original or getattr(original, '_daylight_traced', False):
        return

    def traced(payload):
        _note_request(payload)
        return original(payload)

    traced._daylight_traced = True
    try:
        client.transport = traced
    except AttributeError:  # A transport defined as a read-only method is left alone.
        pass


def _wrap_extraction_urlopen():
    """Note the JSON body of extraction requests sent through ``urlopen``.

    Only the request body is copied (never headers, which carry the key).
    """
    import narrative_agent
    original = narrative_agent.urlopen
    if getattr(original, '_daylight_traced', False):
        return

    def traced(request, *args, **kwargs):
        data = getattr(request, 'data', None)
        if data and active() is not None:
            try:
                _note_request(json.loads(data))
            except ValueError:
                pass
        return original(request, *args, **kwargs)

    traced._daylight_traced = True
    narrative_agent.urlopen = traced


def instrument_agent(agent):
    """Wrap one agent's composition and extraction calls, once."""
    if getattr(agent, '_daylight_traced', False):
        return
    _wrap_call(agent, '_complete', 'compose')
    _wrap_call(agent, 'run', 'extract')
    _wrap_transport(agent.client)
    agent._daylight_traced = True


def _message(payload):
    """Return the person's message text and the action type from a turn payload."""
    action = payload.get('action') if isinstance(payload, dict) else None
    if not isinstance(action, dict):
        return None, None
    text = action.get('message')
    return (text if isinstance(text, str) else None), action.get('type')


def trace_turn(store, original, owner, payload):
    """Run one turn under a collector and save its record; return its result.

    Args:
        store: the TraceStore.
        original: the unwrapped ``turn`` callable.
        owner: the owner digest.
        payload: the turn request payload.
    Returns:
        Exactly what ``original`` returns; its errors propagate unchanged.
    """
    if active() is not None:  # A nested turn joins the outer trace.
        return original(owner, payload)
    collector = _Collector()
    _local.collector = collector
    started_at = time.time()
    started = time.perf_counter()
    result, error = None, None
    try:
        result = original(owner, payload)
        return result
    except Exception as failure:
        error = failure
        raise
    finally:
        _local.collector = None
        try:
            _save(store, collector, owner, payload, result, error, started_at, started)
        except Exception:  # Saving a trace never fails the person's turn.
            logging.getLogger(__name__).warning('Daylight turn trace not saved')


def _save(store, collector, owner, payload, result, error, started_at, started):
    """Build and write one turn record from the collector and the turn result."""
    request_id = payload.get('requestId') if isinstance(payload, dict) else None
    if not isinstance(request_id, str) or not TURN_ID.fullmatch(request_id):
        return  # The turn itself rejects such a request; nothing to key it by.
    text, action = _message(payload)
    out = result if isinstance(result, dict) else {}
    assessment = out.get('assessment') if isinstance(out.get('assessment'), dict) else {}
    record = {
        'turnId': request_id, 'owner': owner_key(owner),
        'startedAt': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(started_at)),
        'latencyMs': round((time.perf_counter() - started) * 1000),
        'action': action, 'message': text,
        'model': payload.get('model') if isinstance(payload, dict) else None,
        'status': 'error' if error else 'ok',
        'error': f'{type(error).__name__}: {error}' if error else None,
        'reply': out.get('reply'),
        'nextQuestion': assessment.get('nextQuestion'),
        'factsSaved': facts_saved(payload, out),
        'toolCalls': _lookups(collector.calls),
        'modelCalls': collector.calls,
        'checks': _turn_checks(collector, out),
        'metrics': out.get('metrics'),
    }
    store.save(record)


def install_turn_traces(service, root, *, pilot=False, hosted=False):
    """Save every turn of a local service and add the dev trace routes.

    Args:
        service: a built advisor server (before any pilot gate).
        root: trace directory.
        pilot: True for a pilot rehearsal; refused.
        hosted: True when a public origin is set; refused.
    Returns:
        The same service, with ``turn`` wrapped and handler routes added:
        GET ``/api/dev/turns`` (the caller's turns) and
        GET ``/api/dev/turns/<turnId>`` (one full record).
    Raises:
        TraceDisabled: for a pilot or hosted service (D155 Q6a hard-off).
    """
    if pilot or hosted:
        raise TraceDisabled('Turn traces run only for local testing, never in the pilot or a hosted service.')
    store = TraceStore(root)
    adaptive = service.adaptive
    agents = {adaptive.agent, *getattr(adaptive, 'model_agents', {}).values()}
    for agent in agents:
        instrument_agent(agent)
    _wrap_extraction_urlopen()
    for name in CHECK_LOGGERS:
        logger = logging.getLogger(name)
        if _HANDLER not in logger.handlers:
            logger.addHandler(_HANDLER)
    original = adaptive.turn
    adaptive.turn = lambda owner, payload: trace_turn(store, original, owner, payload)
    service.turn_traces = store

    base = service.RequestHandlerClass

    class TraceHandler(base):
        """Adds owner-scoped GET routes for this caller's turn traces."""

        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            """Report honestly on /api/status that local chat traces are being saved."""
            if code == 200 and isinstance(value, dict) and urlsplit(self.path).path == '/api/status':
                value = {**value, 'conversation_logging': True, 'dev_turn_traces': True}
            return super().respond(code, value, mime, cookie)

        def do_GET(self):
            """Serve /api/dev/turns and /api/dev/turns/<turnId>; defer everything else."""
            url = urlsplit(self.path)
            if url.path != '/api/dev/turns' and not url.path.startswith('/api/dev/turns/'):
                return super().do_GET()
            try:
                if not self.safe():
                    return self.respond(403, {'error': 'Request origin rejected.'})
                if url.query:
                    return self.respond(422, {'error': 'Do not put details in URLs.'})
                token = self.token()
                if not token:
                    return self.respond(401, {'error': 'Start a visit first.'})
                owner = service.profiles.digest(token)
                if url.path == '/api/dev/turns':
                    return self.respond(200, {'turns': store.list(owner)})
                turn_id = unquote(url.path[len('/api/dev/turns/'):])
                if not TURN_ID.fullmatch(turn_id):
                    return self.respond(404, {'error': 'No such turn.'})
                record = store.get(turn_id, owner)
                return self.respond(200, record) if record else self.respond(404, {'error': 'No such turn.'})
            except Exception as error:
                code = getattr(error, 'code', 500)
                return self.respond(code if isinstance(code, int) else 500, {'error': str(error) or 'Trace unavailable.'})

    service.RequestHandlerClass = TraceHandler
    return service
