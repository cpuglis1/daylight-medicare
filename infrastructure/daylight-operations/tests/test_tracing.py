"""Offline tests for the provider interface and metadata-only traces."""
import json

import pytest

from daylight_operations.tracing import (INSERT_TRACE, TRACE_COLUMNS, MemorySink, ModelClient,
                                         PostgresSink, TraceEvent, TracingClient, request_digest)

SECRET = "My doctor is Dr. Ana Ruiz and I take apixaban 5 mg"
PAYLOAD = {"instructions": "system text", "input": [{"role": "user", "content": SECRET}],
           "text": {"format": {"name": "daylight_resolved_conversation", "schema": {}}},
           "max_output_tokens": 900}


class FakeClaude:
    """Mirrors ClaudeClient.transport's Responses-shaped result."""
    model = "claude-opus-5-5"
    key = "sk-fake"

    def __init__(self, result=None, error=None, tokens=1234):
        self.result, self.error, self.tokens = result, error, tokens

    @property
    def available(self):
        return True

    def count(self, payload):
        if self.error:
            raise self.error
        return self.tokens

    def transport(self, payload):
        if self.error:
            raise self.error
        return self.result


def completed(text=SECRET, **extra):
    return {"status": "completed", "model": "claude-opus-5-5", "service_tier": "standard",
            "usage": {"input_tokens": 1500, "output_tokens": 320, "total_tokens": 1820,
                      "input_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 200}},
            "output": [{"content": [{"type": "output_text", "text": text}]}], **extra}


class TransportFailure(Exception):
    transport_category = "timeout"


def ticking_clock(step=0.25):
    state = {"t": 100.0}

    def clock():
        state["t"] += step
        return state["t"]
    return clock


def wrap(client, sink=None, **kwargs):
    sink = sink or MemorySink()
    return TracingClient(client, sink, surface="advisor-8893", provider="Anthropic",
                         clock=ticking_clock(), **kwargs), sink


def test_both_client_shapes_satisfy_the_protocol():
    assert isinstance(FakeClaude(), ModelClient)
    assert not isinstance(object(), ModelClient)
    with pytest.raises(TypeError):
        TracingClient(object(), MemorySink(), surface="s", provider="P")


def test_generate_returns_the_result_unchanged_and_records_usage():
    result = completed()
    client, sink = wrap(FakeClaude(result))
    assert client.transport(PAYLOAD) is result
    (event,) = sink.events
    assert (event.operation, event.outcome, event.stage) == ("generate", "completed", "daylight_resolved_conversation")
    assert (event.input_tokens, event.output_tokens, event.cached_tokens, event.cache_write_tokens) == (1500, 320, 1000, 200)
    assert event.model == "claude-opus-5-5" and event.latency_ms == 250
    assert event.request_sha256 == request_digest(PAYLOAD)
    assert event.metadata == {"service_tier": "standard"}


def test_no_content_ever_reaches_a_trace():
    client, sink = wrap(FakeClaude(completed()))
    client.transport(PAYLOAD)
    client.count(PAYLOAD)
    serialized = json.dumps([e.as_row() for e in sink.events])
    for fragment in ("Ruiz", "apixaban", "system text", "sk-fake"):
        assert fragment not in serialized


def test_count_records_input_tokens():
    client, sink = wrap(FakeClaude(tokens=777))
    assert client.count(PAYLOAD) == 777
    assert (sink.events[0].operation, sink.events[0].input_tokens) == ("count", 777)


def test_incomplete_and_contract_errors_are_distinguished():
    client, sink = wrap(FakeClaude({**completed(), "status": "incomplete",
                                    "incomplete_details": {"reason": "max_output_tokens"}}))
    client.transport(PAYLOAD)
    client._client.result = completed(structured_output_error="schema_constraints")
    client.transport(PAYLOAD)
    first, second = sink.events
    assert (first.outcome, first.metadata["incomplete_reason"]) == ("incomplete", "max_output_tokens")
    assert (second.outcome, second.failure_category) == ("contract_error", "schema_constraints")


def test_transport_failure_is_recorded_and_reraised_unchanged():
    error = TransportFailure("connection dropped near Dr. Ruiz")
    client, sink = wrap(FakeClaude(error=error))
    with pytest.raises(TransportFailure) as raised:
        client.transport(PAYLOAD)
    assert raised.value is error
    (event,) = sink.events
    assert (event.outcome, event.failure_category) == ("transport_error", "timeout")
    assert "Ruiz" not in json.dumps(event.as_row())


def test_unnamed_exception_gets_a_safe_category():
    client, sink = wrap(FakeClaude(error=ValueError("bad")))
    with pytest.raises(ValueError):
        client.count(PAYLOAD)
    assert sink.events[0].failure_category == "value_error"


def test_a_broken_sink_never_breaks_the_turn():
    class Broken:
        def write(self, event):
            raise RuntimeError("database down")

    result = completed()
    client, _ = wrap(FakeClaude(result), sink=Broken())
    assert client.transport(PAYLOAD) is result
    assert client.dropped == 1


def test_other_attributes_pass_through():
    client, _ = wrap(FakeClaude(completed()))
    assert client.available is True and client.model == "claude-opus-5-5"


def test_bind_attaches_opaque_visit_and_decision_refs():
    client, sink = wrap(FakeClaude(completed()))
    visit = "a" * 64
    client.bind(visit_ref=visit, decision_id="00000000-0000-0000-0000-000000000001").transport(PAYLOAD)
    assert sink.events[0].visit_ref == visit
    with pytest.raises(ValueError):
        TraceEvent(surface="s", stage="x", provider="P", model="m", operation="generate", outcome="completed",
                   request_sha256="b" * 64, latency_ms=1, visit_ref="Jane Doe")


def test_trace_event_rejects_unapproved_metadata():
    with pytest.raises(ValueError):
        TraceEvent(surface="s", stage="x", provider="P", model="m", operation="generate", outcome="completed",
                   request_sha256="b" * 64, latency_ms=1, metadata={"prompt": SECRET})


def test_postgres_sink_matches_the_table_columns():
    executed = []

    class FakeConnection:
        closed = False

        def execute(self, sql, params):
            executed.append((sql, params))

    sink = PostgresSink(lambda: FakeConnection())
    client, _ = wrap(FakeClaude(completed()), sink=sink)
    client.transport(PAYLOAD)
    sql, params = executed[0]
    assert sql == INSERT_TRACE and len(params) == len(TRACE_COLUMNS) == sql.count("%s")
    row = dict(zip(TRACE_COLUMNS, params))
    assert json.loads(row["metadata"]) == {"service_tier": "standard"}
    assert row["provider"] == "Anthropic" and row["surface"] == "advisor-8893"
