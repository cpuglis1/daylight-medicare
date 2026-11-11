"""Evidence capture and streaming safeguards needed by local sizing."""
import gzip
import hashlib
import json
from decimal import Decimal

import pytest

from daylight_data.storage import FileArchive
from daylight_data.adapters.streaming import json_array_records, jsonl_records
from daylight_data.adapters.l03 import project_record as ma_project
from daylight_data.adapters.l08 import project_record as provider_project
from daylight_data.adapters.l10 import project_record as medigap_project
from daylight_data.adapters.common import make_source


def test_captured_file_survives_source_mutation_with_independent_inode(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"published evidence before edit")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    archive = FileArchive(tmp_path / "archive")
    captured = archive.put_file(source, digest)
    assert captured.sha256 == digest
    assert archive.path(digest).stat().st_ino != source.stat().st_ino
    source.write_bytes(b"source changes after capture")
    assert archive.open(digest).read() == b"published evidence before edit"
    assert archive.verify(digest) == captured.byte_length


def test_file_capture_rejects_wrong_hash_and_reused_source_mismatch(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"original")
    archive = FileArchive(tmp_path / "archive")
    with pytest.raises(ValueError, match="hash mismatch"):
        archive.put_file(source, "0" * 64)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    archive.put_file(source, digest)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        archive.put_file(source, digest)
    assert archive.verify(digest) == len(b"original")


def test_streams_keep_decimal_duplicate_ordinals_and_physical_lines(tmp_path):
    source = tmp_path / "array.json"
    source.write_text('[{"id":"same","amount":0.0001},{"id":"same","amount":0.0001}]')
    rows = list(json_array_records(tmp_path, source, "L10", "rates"))
    assert rows[0].raw["amount"] == Decimal("0.0001")
    assert rows[0].record_id != rows[1].record_id
    lines = tmp_path / "rows.jsonl.gz"
    with gzip.open(lines, "wt") as handle:
        handle.write('{"id":"a"}\n\n')
    reader = jsonl_records(tmp_path, lines, "L03", "work")
    assert next(reader).source_row_ordinal == 1
    with pytest.raises(json.JSONDecodeError):
        next(reader)


def test_l03_condition_parent_and_held_state_are_not_acceptance(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{}')
    raw = {"id": "obligation-1", "offering_id": "2026:H0710:010:000", "kind": "condition",
           "payload": json.dumps({"parent_id": "claim-1", "accepted_for_reference": False,
                                   "context": {"network": "out_of_network"}})}
    row = make_source(tmp_path, source, "L03", "semantic_unit", 1, "id", raw, "fixture")
    projected = ma_project(row)
    assert projected.entity_type == "ma_semantic_condition_representation"
    assert projected.conditions["parent_id"] == "claim-1"
    assert projected.fields["accepted_for_reference"] is False
    assert projected.output_acceptance_state == "research_only"


def test_provider_identity_and_rate_zero_never_imply_network_or_quote(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{}')
    row = make_source(tmp_path, source, "L08", "observations", 1, "id",
                      {"npi": "1234567890", "fields_json": '{"state":"unknown"}'}, "fixture")
    provider = provider_project(row)
    assert provider.fields["personal_network_status_determined"] is False
    row = make_source(tmp_path, source, "L10", "rate-cells", 1, "id",
                      {"annual_premium_cents": 0, "zero_meaning": "source_placeholder",
                       "source_status": "REPLACED", "rate_effective_from": "2017-01-01"}, "fixture")
    rate = medigap_project(row)
    assert rate.fields["amount_decimal"] == Decimal(0)
    assert rate.fields["source_zero_meaning"] == "source_placeholder"
    assert rate.fields["personal_quote"] is False
    assert rate.conditions["source_status"] == "REPLACED"


def test_provider_structured_period_remains_separate_from_amount_period(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{}')
    row = make_source(tmp_path, source, "L08", "entities", 1, "provider",
                      {"period_json": '{"start":"2026-01-01","end":null}'}, "fixture")
    projected = provider_project(row)
    assert projected.fields["provider_period"] == {"start":"2026-01-01","end":None}
    assert "period" not in projected.fields
    assert projected.conditions["provider_period"] == projected.fields["provider_period"]
    assert row.raw["period_json"] == '{"start":"2026-01-01","end":null}'
