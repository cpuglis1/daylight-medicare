"""Provider interface and metadata-only tracing for model calls.

Both advisor clients (the pinned OpenAI ``ResponsesClient`` and ``ClaudeClient``)
already share one call shape: ``count(payload) -> int`` and
``transport(payload) -> dict`` returning a Responses-style result. ``ModelClient``
names that contract. ``TracingClient`` wraps any such client, records one
``TraceEvent`` per call and returns the wrapped client's result unchanged.

A trace never contains prompt, response or transcript content. It holds the
provider, model, stage, outcome, token counts, latency and a SHA-256 of the
request for correlating retries. Recording failures never break the user's turn.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Callable, Protocol, runtime_checkable

LOGGER = logging.getLogger(__name__)
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_CATEGORY = re.compile(r"^[a-z0-9_]{1,40}$")
METADATA_KEYS = frozenset({"service_tier", "incomplete_reason", "attempt"})
OUTCOMES = frozenset({"completed", "incomplete", "contract_error", "transport_error", "error"})


@runtime_checkable
class ModelClient(Protocol):
    """The call shape every advisor model client already implements."""

    def count(self, payload: dict) -> int: ...

    def transport(self, payload: dict) -> dict: ...


class TraceSink(Protocol):
    def write(self, event: "TraceEvent") -> None: ...


@dataclass(frozen=True)
class TraceEvent:
    surface: str
    stage: str
    provider: str
    model: str
    operation: str  # "count" or "generate"
    outcome: str
    request_sha256: str
    latency_ms: int
    failure_category: str | None = None
    visit_ref: str | None = None
    decision_id: str | None = None
    input_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.operation not in {"count", "generate"}:
            raise ValueError("operation must be count or generate")
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome!r}")
        if not _HEX64.match(self.request_sha256):
            raise ValueError("request_sha256 must be a SHA-256 hex digest")
        if self.visit_ref is not None and not _HEX64.match(self.visit_ref):
            raise ValueError("visit_ref must be an opaque SHA-256 hex digest, never a name or ID")
        if self.failure_category is not None and not _CATEGORY.match(self.failure_category):
            raise ValueError("failure_category must be a short fixed category")
        extra = set(self.metadata) - METADATA_KEYS
        if extra:
            raise ValueError(f"trace metadata may not include {sorted(extra)}")

    def as_row(self) -> dict:
        return asdict(self)


def request_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stage_name(payload: Any) -> str:
    """The structured-output schema name identifies the stage without content."""
    try:
        name = payload["text"]["format"]["name"]
    except (KeyError, TypeError):
        return "unnamed"
    return name if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9:._-]{1,80}", name) else "unnamed"


def _category(error: BaseException) -> str:
    named = getattr(error, "transport_category", None)
    if isinstance(named, str) and _CATEGORY.match(named):
        return named
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).lower()
    return snake[:40] if _CATEGORY.match(snake[:40]) else "error"


def _usage(result: dict) -> dict:
    usage = result.get("usage") or {}
    details = usage.get("input_tokens_details") or {}

    def number(value):
        return value if isinstance(value, int) and value >= 0 else None

    return {"input_tokens": number(usage.get("input_tokens")),
            "output_tokens": number(usage.get("output_tokens")),
            "cached_tokens": number(details.get("cached_tokens")),
            "cache_write_tokens": number(details.get("cache_write_tokens"))}


def _outcome(result: dict) -> tuple[str, str | None, dict]:
    metadata = {}
    tier = result.get("service_tier")
    if isinstance(tier, str) and len(tier) <= 20:
        metadata["service_tier"] = tier
    if result.get("structured_output_error"):
        error = str(result["structured_output_error"])
        return "contract_error", error if _CATEGORY.match(error) else "contract_error", metadata
    if result.get("status") == "completed":
        return "completed", None, metadata
    reason = (result.get("incomplete_details") or {}).get("reason")
    if isinstance(reason, str) and _CATEGORY.match(reason):
        metadata["incomplete_reason"] = reason
    return "incomplete", None, metadata


class TracingClient:
    """Wraps a ``ModelClient``; other attributes pass through unchanged."""

    def __init__(self, client: ModelClient, sink: TraceSink, *, surface: str, provider: str,
                 model: str | None = None, visit_ref: str | None = None, decision_id: str | None = None,
                 clock: Callable[[], float] = time.monotonic):
        if not isinstance(client, ModelClient):
            raise TypeError("client must provide count(payload) and transport(payload)")
        self._client = client
        self._sink = sink
        self._surface = surface
        self._provider = provider
        self._model = model
        self._visit_ref = visit_ref
        self._decision_id = decision_id
        self._clock = clock
        self._lock = threading.Lock()
        self.dropped = 0

    def __getattr__(self, name):
        return getattr(self._client, name)

    def bind(self, *, visit_ref: str | None = None, decision_id: str | None = None) -> "TracingClient":
        """A wrapper for one visit or decision, sharing the same client and sink."""
        bound = TracingClient(self._client, self._sink, surface=self._surface, provider=self._provider,
                              model=self._model, visit_ref=visit_ref, decision_id=decision_id, clock=self._clock)
        return bound

    def count(self, payload: dict) -> int:
        start = self._clock()
        try:
            result = self._client.count(payload)
        except BaseException as error:
            self._record(payload, "count", start, outcome="transport_error", failure=_category(error))
            raise
        tokens = result if isinstance(result, int) and result >= 0 else None
        self._record(payload, "count", start, outcome="completed", usage={"input_tokens": tokens})
        return result

    def transport(self, payload: dict) -> dict:
        start = self._clock()
        try:
            result = self._client.transport(payload)
        except BaseException as error:
            self._record(payload, "generate", start, outcome="transport_error", failure=_category(error))
            raise
        if isinstance(result, dict):
            outcome, failure, metadata = _outcome(result)
            model = result.get("model") if isinstance(result.get("model"), str) else None
            self._record(payload, "generate", start, outcome=outcome, failure=failure,
                         usage=_usage(result), metadata=metadata, model=model)
        else:
            self._record(payload, "generate", start, outcome="error", failure="unexpected_result")
        return result

    def _record(self, payload, operation, start, *, outcome, failure=None, usage=None, metadata=None, model=None):
        try:
            latency = max(0, int(round((self._clock() - start) * 1000)))
            chosen = model or self._model or getattr(self._client, "model", None) or "unknown"
            event = TraceEvent(surface=self._surface, stage=stage_name(payload), provider=self._provider,
                               model=str(chosen)[:80], operation=operation, outcome=outcome,
                               request_sha256=request_digest(payload), latency_ms=latency,
                               failure_category=failure, visit_ref=self._visit_ref,
                               decision_id=self._decision_id, metadata=metadata or {}, **(usage or {}))
            self._sink.write(event)
        except Exception:  # tracing must never break the user's turn
            with self._lock:
                self.dropped += 1
            LOGGER.warning("model-call trace not recorded", exc_info=False)


class MemorySink:
    """Keeps events in memory; for tests and offline harnesses."""

    def __init__(self):
        self.events: list[TraceEvent] = []

    def write(self, event: TraceEvent) -> None:
        self.events.append(event)


TRACE_COLUMNS = ("surface", "stage", "provider", "model", "operation", "outcome", "failure_category",
                 "request_sha256", "visit_ref", "decision_id", "input_tokens", "cached_tokens",
                 "cache_write_tokens", "output_tokens", "latency_ms", "metadata")
INSERT_TRACE = ("INSERT INTO dl_ops.model_call_trace (" + ", ".join(TRACE_COLUMNS) + ") VALUES ("
                + ", ".join(["%s"] * len(TRACE_COLUMNS)) + ")")


class PostgresSink:
    """Writes to dl_ops.model_call_trace using a psycopg-style connection factory.

    ``connect`` returns a connection in autocommit mode (``psycopg.connect(dsn,
    autocommit=True)``). One short insert per call; no content columns exist.
    """

    def __init__(self, connect: Callable[[], Any]):
        self._connect = connect
        self._connection = None
        self._lock = threading.Lock()

    def write(self, event: TraceEvent) -> None:
        row = event.as_row()
        params = tuple(json.dumps(row[c]) if c == "metadata" else row[c] for c in TRACE_COLUMNS)
        with self._lock:
            if self._connection is None or getattr(self._connection, "closed", False):
                self._connection = self._connect()
            self._connection.execute(INSERT_TRACE, params)
