"""Independent sizing/source-fidelity checks; tiny synthetic fixtures only."""
from contextlib import contextmanager
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from daylight_data.adapters.common import DomainProjection, SourceRecord, canonical_json, digest_json
from daylight_data.adapters import l03, l08, l10
from daylight_data.adapters.streaming import json_document_records, jsonl_records, unpack_sqlite
from daylight_data.storage import FileArchive


def source(raw, table="fixture", path="docs/data/fixture/build-r1/source.json"):
    return SourceRecord("L03", path, table, 1, "fixture", "a" * 64,
                        "b" * 64, "c" * 64, raw, "synthetic_ordinal", adapter_code_sha256="d" * 64)


def test_clone_capture_has_independent_identity_and_survives_source_mutation(tmp_path):
    original = tmp_path / "source"
    payload = b"independent immutable source bytes"
    original.write_bytes(payload)
    archive = FileArchive(tmp_path / "archive")
    captured = archive.put_file(original, hashlib.sha256(payload).hexdigest())
    target = archive.path(captured.sha256)
    assert target.stat().st_ino != original.stat().st_ino
    original.write_bytes(b"subsequent independent source edit")
    assert target.read_bytes() == payload
    assert archive.verify(captured.sha256) == len(payload)
    with pytest.raises(ValueError, match="hash mismatch"):
        archive.put_file(original, captured.sha256)


def test_clone_capture_rejects_wrong_hash_and_bound_without_partial_object(tmp_path):
    original = tmp_path / "source"
    original.write_bytes(b"synthetic bytes")
    archive = FileArchive(tmp_path / "archive")
    with pytest.raises(ValueError):
        archive.put_file(original, "0" * 64)
    with pytest.raises(ValueError):
        archive.put_file(original, hashlib.sha256(original.read_bytes()).hexdigest(), max_bytes=1)
    assert not [path for path in archive.root.rglob("*") if path.is_file()]


def test_expanded_sqlite_checks_frozen_hash_size_and_cleans_up(tmp_path):
    original = tmp_path / "fixture.sqlite3"
    with sqlite3.connect(original) as db:
        db.execute("CREATE TABLE fixture (id integer primary key,value text)")
        db.executemany("INSERT INTO fixture VALUES(?,?)", [(1, "first"), (2, "second")])
    payload = original.read_bytes()
    compressed = tmp_path / "fixture.sqlite3.gz"
    compressed_bytes = gzip.compress(payload)
    compressed.write_bytes(compressed_bytes)
    with unpack_sqlite(tmp_path, compressed, hashlib.sha256(payload).hexdigest(), len(payload)) as expanded:
        assert expanded.read_bytes() == payload
        location = expanded
    assert not location.exists()
    assert compressed.read_bytes() == compressed_bytes
    with pytest.raises(ValueError, match="hash"):
        with unpack_sqlite(tmp_path, compressed, "0" * 64, len(payload)):
            pytest.fail("Mismatched frozen hash must never reach SQLite reader")
    assert not list((tmp_path / "infrastructure/daylight-data/.state/sqlite-sizing-cache").glob("expanded-*"))


def test_streamed_json_keeps_decimal_unknown_none_and_blank_line_failure(tmp_path):
    path = tmp_path / "records.json"
    path.write_text('[{"id":"first","amount":0.1234,"unknown":null},{"id":"second","amount":"unknown"}]')
    records = list(json_document_records(tmp_path, path, "L03", "fixture"))
    assert records[0].raw["amount"] == Decimal("0.1234")
    assert records[0].raw["unknown"] is None
    assert records[1].raw["amount"] == "unknown"
    lines = tmp_path / "records.jsonl"
    lines.write_text('{"id":"first"}\n\n{"id":"third"}\n')
    reader = jsonl_records(tmp_path, lines, "L03", "fixture")
    assert next(reader).source_row_ordinal == 1
    with pytest.raises(ValueError):
        next(reader)


def test_l03_followup_projection_preserves_parent_context_and_stays_unaccepted():
    payload = {"id": "obligation", "context": {"network": "in"}, "parent_ids": ["parent"],
               "work_policy_id": "required-policy", "states": ["held"]}
    row = source({"id": "obligation", "kind": "predicate", "offering_id": "2026:H0001:001:000",
                  "payload": json.dumps(payload)}, "work_obligation")
    result = l03.project_record(row)
    assert result.entity_type == "ma_followup_predicate"
    assert result.fields["followup_obligation_id"] == "obligation"
    assert "required_obligation_id" not in result.fields
    assert result.conditions["parent_ids"] == ["parent"]
    assert result.conditions["context"] == {"network": "in"}
    assert result.fields["source_columns"]["kind"] == "predicate"
    assert result.fields["accepted_for_reference"] is False
    assert result.output_acceptance_state == "research_only"


@pytest.mark.parametrize("kind", ["claim", "condition"])
def test_l03_semantic_rows_are_representations_not_canonical_counts(kind):
    row = source({"id": "representation", "kind": kind, "offering_id": "2026:H0001:001:000",
        "payload": '{"parent_ids":["parent"],"accepted_for_reference":false}'}, "semantic_unit")
    result = l03.project_record(row)
    assert result.entity_type == "ma_semantic_" + kind + "_representation"
    assert result.fields["source_columns"]["id"] == "representation"
    assert result.fields["source_columns"]["kind"] == kind
    assert result.fields["accepted_for_reference"] is False
    assert result.conditions["parent_ids"] == ["parent"]
    assert result.output_acceptance_state == "research_only"


def test_l03_native_controls_count_distinct_canonical_ids_and_keep_alias_followups(tmp_path):
    path = tmp_path / "semantic.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE semantic_unit(id TEXT PRIMARY KEY,kind TEXT NOT NULL);
            CREATE TABLE canonical_unit(unit_id TEXT PRIMARY KEY,canonical_id TEXT NOT NULL);
            CREATE TABLE source_identity_alias(alias_unit_id TEXT PRIMARY KEY,target_unit_id TEXT NOT NULL);
            CREATE TABLE work_obligation(id TEXT PRIMARY KEY,kind TEXT NOT NULL);
            INSERT INTO semantic_unit VALUES ('claim','claim'),('claim-alias','claim'),('condition','condition');
            INSERT INTO canonical_unit VALUES ('claim','canonical-claim'),('claim-alias','canonical-claim'),('condition','canonical-condition');
            INSERT INTO source_identity_alias VALUES ('claim-alias','claim');
            INSERT INTO work_obligation VALUES ('followup','preserved_conflict');
        """)
    before = path.read_bytes()
    controls = l03.semantic_inventory_controls(path)
    assert controls["canonical_kind_counts"] == {"claim": 1, "condition": 1}
    assert controls["semantic_kind_counts"] == {"claim": 2, "condition": 1}
    assert controls["semantic_representation_rows"] == controls["canonical_mapping_rows"] == 3
    assert controls["canonical_identity_rows"] == 2
    assert controls["source_identity_alias_rows"] == controls["work_obligation_rows"] == 1
    assert controls["missing_canonical_mappings"] == 0
    assert path.read_bytes() == before
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO semantic_unit VALUES('orphan','condition')")
    # The audit may return the failure count or reject it immediately, but it
    # must never report complete canonical coverage for an unmapped source row.
    try:
        orphan_controls = l03.semantic_inventory_controls(path)
    except ValueError:
        pass
    else:
        assert orphan_controls["missing_canonical_mappings"] == 1


@pytest.mark.parametrize("cents", [0, 1, 12345])
def test_l10_annual_cents_remain_exact_with_period_and_source_conditions(cents):
    payload = {"source_status": "replaced", "rate_effective_from": "2025-01-01",
               "rate_effective_through": "2026-03-31", "benefit_year": 2025,
               "policy_issue_dates_are_not_rate_periods": True}
    row = source({"annual_premium_cents": cents, "payload": json.dumps(payload)}, "rate_cells",
                 "docs/data/l10-medigap-2026-10-28/targeted-filings-r5/build-r1/rates.json")
    result = l10.project_record(row)
    assert result.fields["amount_decimal"] == Decimal(cents) / 100
    assert result.fields["unit"] == "USD/year"
    assert result.fields["source_benefit_year"] == 2025
    assert "benefit_year" not in result.fields
    assert result.conditions["source_status"] == "replaced"
    assert result.conditions["policy_issue_dates_are_not_rate_periods"] is True
    assert result.fields["personal_quote"] is False


def test_l08_unknown_network_evidence_stays_unknown_and_keeps_native_identifiers():
    result = l08.project_record(source({"state": "unknown", "offering_id": "H1234-001",
        "qualifiers_json": '{"period":"2026","site":"exact-site"}'}, "observations"))
    assert result.value_state == "unknown"
    assert result.fields["source_offering_id"] == "H1234-001"
    assert "offering_id" not in result.fields
    assert result.conditions["qualifiers"] == {"period": "2026", "site": "exact-site"}
    assert result.fields["personal_network_status_determined"] is False


def test_l08_future_native_search_prefix_table_is_not_silently_omitted(tmp_path):
    path = tmp_path / "fixture.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE VIRTUAL TABLE directory_search USING fts5(content)")
        db.execute("CREATE TABLE directory_search_source_observation(id integer primary key, evidence text)")
        db.execute("INSERT INTO directory_search_source_observation VALUES(1,'future native source evidence')")
    assert "directory_search_source_observation" in l08.selected_tables(path)
    assert "directory_search" not in l08.selected_tables(path)


@pytest.mark.parametrize("value,expected", [("unknown", None), (True, None),
    (0, 0), (Decimal("0.1234"), Decimal("0.1234")), (0.125, None)])
def test_numeric_fallback_never_casts_unknown_bool_or_float_as_money(value, expected):
    from daylight_data.ingestion.loader import insert_projections
    captured = []
    class Copy:
        def __init__(self, keep):
            self.keep = keep
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def write_row(self, row):
            if self.keep:
                captured.append(row)
    class Cursor:
        def copy(self, command):
            return Copy(command.startswith("COPY projection_batch"))
    class Connection:
        @contextmanager
        def transaction(self):
            yield self
        def cursor(self):
            return Cursor()
        def execute(self, *args):
            return SimpleNamespace(fetchone=lambda: None)
    projection = DomainProjection(source({"amount": value}), "fixture", "fixture", {"amount": value})
    insert_projections(Connection(), [projection])
    assert captured[0][8] == expected
    assert captured[0][-1].obj["amount"] == value


def test_old_sizing_receipt_without_schema_driver_contract_is_not_reused(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "tools/benchmark_local_layers.py"
    spec = importlib.util.spec_from_file_location("independent_benchmark_review", path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    row = source({"synthetic": True})
    binding = {"layer_id": row.layer_id, "source_path": row.source_path,
        "source_sha256": row.source_sha256, "source_table": row.source_table,
        "derivation_id": row.derivation_id, "adapter_code_sha256": row.adapter_code_sha256}
    units = tmp_path / "units"
    units.mkdir()
    prior = {"binding": binding, "population_complete": True, "input_rows": 1,
             "stream_sha256": hashlib.sha256(canonical_json([row.record_id, row.raw]).encode() + b"\n").hexdigest()}
    (units / (digest_json(binding) + ".json")).write_text(json.dumps(prior))
    args = SimpleNamespace(output=tmp_path, repository=tmp_path, contract_hash="e" * 64,
                           reserve_bytes=0, window_rows=250000)
    monkeypatch.setattr(benchmark, "require_frozen_code", lambda args: None)
    monkeypatch.setattr(benchmark, "disk_guard", lambda *args: 100 * 1024**3)
    class NewMeasurementRequired(RuntimeError):
        pass
    class NoDatabaseCreated:
        def execute(self, *args):
            raise NewMeasurementRequired("New contract requires a new measurement")
    with pytest.raises(NewMeasurementRequired):
        benchmark.measure_unit(NoDatabaseCreated(), "", None, iter([row]), row, args, None)
    assert json.loads((units / (digest_json(binding) + ".json")).read_text()) == prior


def test_sizing_batch_byte_bound_is_real_and_large_single_rows_fail(tmp_path):
    path = Path(__file__).resolve().parents[1] / "tools/benchmark_local_layers.py"
    spec = importlib.util.spec_from_file_location("independent_bounded_batch_review", path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    rows = [source({"text": "x" * 100}) for _ in range(3)]
    batches = list(benchmark.bounded_batches(iter(rows), max_rows=1000, max_payload_bytes=150))
    assert list(map(len, batches)) == [1, 1, 1]
    with pytest.raises(ValueError, match="32MiB"):
        list(benchmark.bounded_batches(iter([source({"text": "x" * (33 * 1024**2)})]), max_rows=1000))


def test_ordinal_windows_preserve_lineage_cover_every_row_and_hash_full_stream():
    from dataclasses import replace
    path = Path(__file__).resolve().parents[1] / "tools/benchmark_local_layers.py"
    spec = importlib.util.spec_from_file_location("independent_window_lineage_review", path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    records = [replace(source({"ordinal": n}), source_row_ordinal=n, source_row_key=str(n)) for n in range(1, 6)]
    seen, spans, digest = [], [], hashlib.sha256()
    for first, window in benchmark.ordinal_windows(iter(records), 2):
        rows = list(window)
        assert rows[0] is first
        spans.append((first.source_row_ordinal, rows[-1].source_row_ordinal, len(rows)))
        seen.extend(rows)
        for row in rows:
            digest.update(canonical_json([row.record_id, row.raw]).encode() + b"\n")
    expected = hashlib.sha256(b"".join(canonical_json([row.record_id, row.raw]).encode() + b"\n" for row in records))
    assert spans == [(1, 2, 2), (3, 4, 2), (5, 5, 1)]
    assert seen == records
    assert len({row.record_id for row in seen}) == 5
    assert digest.hexdigest() == expected.hexdigest()


def test_unconsumed_sizing_window_cannot_be_skipped():
    path = Path(__file__).resolve().parents[1] / "tools/benchmark_local_layers.py"
    spec = importlib.util.spec_from_file_location("independent_window_consumption_review", path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    windows = benchmark.ordinal_windows(iter([1, 2, 3]), 2)
    first, window = next(windows)
    assert first == next(window) == 1
    with pytest.raises(ValueError, match="completely consumed"):
        next(windows)


def test_l08_structured_provider_period_preserves_full_conditions_without_money_period():
    period = {"start": "2025-01-01", "end": None, "status": "source_reported",
              "qualifiers": {"source_note": "participation period is not verified coverage"}}
    original = {"id": "entity", "period_json": json.dumps(period), "state": "unknown"}
    row = source(original, "entities")
    result = l08.project_record(row)
    assert result.fields["provider_period"] == period
    assert result.conditions["provider_period"] == period
    assert "period" not in result.fields
    assert "amount_period" not in result.fields
    assert row.raw == original
    assert result.output_acceptance_state == "research_only"


@pytest.fixture
def synthetic_sizing_rollup(tmp_path, monkeypatch):
    """Receipts have full control counts, but no source data or database writes."""
    path = Path(__file__).resolve().parents[1] / "tools/summarize_local_sizing.py"
    spec = importlib.util.spec_from_file_location("independent_sizing_rollup_review", path)
    summarizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summarizer)
    current_adapter = lambda layer_id: digest_json({"current_adapter": layer_id})
    monkeypatch.setattr(summarizer, "adapter_code_sha256", current_adapter)

    def build(*, shared_drift=False):
        small, large = tmp_path / "small", tmp_path / "large"
        (tmp_path / "source-sizing.json").write_text(json.dumps({"sqlite_files": []}))
        for directory in (small, large):
            (directory / "units").mkdir(parents=True)
        shared_path = "infrastructure/daylight-data/src/daylight_data/adapters/common.py"
        sibling_path = "infrastructure/daylight-data/src/daylight_data/adapters/l08.py"
        contract_hashes = {}
        for directory in (small, large):
            contract = {"postgres_settings": {"server_version_num": "180006"}, "files": {
                shared_path: "changed" if directory == large and shared_drift else "same-shared-helper",
                sibling_path: "new-l08-only" if directory == large else "old-l08-only",
                summarizer.DRIVER: "windows-driver" if directory == large else "table-driver",
                "infrastructure/daylight-data/migrations/001.sql": "same-schema"}}
            contract_hash = digest_json(contract)
            contract_hashes[directory] = contract_hash
            (directory / ("run-contract-" + contract_hash + ".json")).write_text(json.dumps(contract))

        populations = {
            "L02": [("docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json", "collier_offerings", [72])],
            "L03": [("docs/data/l03-ma-benefits-2026-10-25/bounded-reference-r4/entries.json", "entries", [535]),
                    ("docs/data/l03-ma-benefits-2026-10-25/bounded-reference-r4/held-claims.json", "held-claims", [153]),
                    ("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/inventory.sqlite3.gz", "semantic_unit", [392744]),
                    ("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/inventory.sqlite3.gz", "canonical_unit", [392744]),
                    ("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/inventory.sqlite3.gz", "source_identity_alias", [174]),
                    ("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/inventory.sqlite3.gz", "work_obligation", [230]),
                    ("docs/data/l03-ma-benefits-2026-10-25/inventory-r8/inventory.sqlite3.gz", "fixture_parent_context", [1])],
            "L04": [("docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json", "pdp_records", [10])],
            "L07": [("docs/data/fixture/network.sqlite3", "network", [1, 1])],
            "L10": [("docs/data/l10-medigap-2026-10-28/filing-reconciliation-r3/build-r1/rate-cells.json", "rate-cells", [22496]),
                    ("docs/data/l10-medigap-2026-10-28/targeted-filings-r5/build-r1/rate-cells.json", "rate-cells", [40700])]}
        for number in range(1, 16):
            layer_id = f"L{number:02}"
            directory = large if layer_id in summarizer.LARGE else small
            contract_hash = contract_hashes[directory]
            units, controls, total = [], [], 0
            for source_path, table, windows in populations.get(layer_id, [(f"docs/data/fixture/{layer_id}.json", "fixture", [1])]):
                first, window_controls = 1, []
                for rows in windows:
                    binding = {"layer_id": layer_id, "source_path": source_path, "source_table": table,
                        "source_sha256": "a" * 64, "derivation_id": "b" * 64,
                        "adapter_code_sha256": current_adapter(layer_id), "sizing_contract_sha256": contract_hash}
                    unit = {"binding": binding, "population_complete": True, "input_rows": rows,
                        "projection_counts": {"fixture": rows}, "baseline_relation_sizes": [
                            {"schema": "dl_evidence", "table": "observation", "total_bytes_including_toast": 100}],
                        "relation_sizes": [{"schema": "dl_evidence", "table": "observation", "total_bytes_including_toast": 100 + rows}],
                        "net_evidence_relation_bytes": rows, "process_peak_rss_bytes": 1000,
                        "minimum_observed_free_bytes": 8 * 1024**3, "schema_baseline_database_bytes": 1000}
                    if layer_id in summarizer.LARGE:
                        binding["window_first_ordinal"] = first
                        unit.update(window_first_ordinal=first, window_last_ordinal=first + rows - 1)
                        window_controls.append({"first": first, "last": first + rows - 1, "rows": rows})
                    if layer_id == "L03" and table == "semantic_unit":
                        unit["projection_counts"] = {"ma_semantic_claim_representation": 143679,
                                                     "ma_semantic_condition_representation": 249065}
                    if layer_id == "L03" and table == "work_obligation":
                        unit["projection_counts"] = {"ma_followup_amendment_applicability": 72,
                                                     "ma_followup_preserved_conflict": 153,
                                                     "ma_followup_rider_frequency": 5}
                    (directory / "units" / (digest_json(binding) + ".json")).write_text(json.dumps(unit))
                    units.append(binding)
                    first += rows
                    total += rows
                controls.append({"source_path": source_path, "source_table": table, "source_rows": sum(windows),
                    "unexplained_loss": 0, "windows": window_controls, "ordered_full_stream_sha256": "c" * 64})
            summary = {"layer_id": layer_id, "sizing_populations_complete": True, "new_acceptance": False,
                "sizing_contract_sha256": contract_hash, "units": units, "source_rows": total,
                "net_evidence_relation_bytes": total, "source_table_population_controls": controls}
            if layer_id == "L03":
                semantic_controls = {
                    "canonical_kind_counts": {"claim": 143505, "condition": 249065},
                    "semantic_kind_counts": {"claim": 143679, "condition": 249065},
                    "semantic_representation_rows": 392744, "canonical_mapping_rows": 392744,
                    "canonical_identity_rows": 392570, "source_identity_alias_rows": 174,
                    "work_obligation_rows": 230, "missing_canonical_mappings": 0}
                summary["frozen_r9_obligations"] = {"claim": 143505, "condition": 249065}
                summary["semantic_inventory_controls"] = semantic_controls
                summary["native_inventory_controls"] = []
                for component in ("semantic-inventory-r9", "inventory-r8"):
                    logical = "docs/data/l03-ma-benefits-2026-10-25/" + component + "/inventory.sqlite3.gz"
                    native = {"source_path": logical, "source_sha256": "a" * 64,
                        "expanded_sha256": "e" * 64, "expanded_bytes": 3405242368 if component == "semantic-inventory-r9" else 1282580480,
                        "native_table_counts": {table: sum(windows) for source_path, table, windows in populations["L03"] if source_path == logical}}
                    if component == "semantic-inventory-r9":
                        native["semantic_inventory_controls"] = semantic_controls
                        native["native_table_counts"]["question_scope_alias"] = 0
                    summary["native_inventory_controls"].append(native)
            if layer_id == "L08":
                summary["non_domain_source_table_dispositions"] = []
            (directory / (layer_id + ".json")).write_text(json.dumps(summary))
        return summarizer, small, large
    return build


def test_rollup_allows_unused_sibling_adapter_change_and_counts_one_baseline(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    report = summarizer.summarize(tmp_path, small, large)
    assert report["layers_measured"] == 15
    assert len(report["contracts"]) == 2
    assert report["frozen_r9_obligations"] == {"claim": 143505, "condition": 249065}
    assert report["net_evidence_relation_bytes"] == report["source_rows"]
    assert report["one_selected_representation_database_estimate_bytes"] == report["net_evidence_relation_bytes"] + 1000
    assert report["all_layers_simultaneously_integrated"] is False


def test_rollup_rejects_stale_own_layer_adapter(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    summary_path = large / "L07.json"
    summary = json.loads(summary_path.read_text())
    binding = summary["units"][0]
    old_unit = large / "units" / (digest_json(binding) + ".json")
    unit = json.loads(old_unit.read_text())
    binding["adapter_code_sha256"] = "d" * 64
    unit["binding"] = binding
    (large / "units" / (digest_json(binding) + ".json")).write_text(json.dumps(unit))
    summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="current exact layer adapter"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_shared_helper_drift(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup(shared_drift=True)
    with pytest.raises(ValueError, match="files differ"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_wrong_canonical_categories_even_with_same_total(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    path = large / "L03.json"
    summary = json.loads(path.read_text())
    native = next(c for c in summary["native_inventory_controls"] if "semantic_inventory_controls" in c)
    native["semantic_inventory_controls"]["canonical_kind_counts"] = {"claim": 143504, "condition": 249066}
    summary["semantic_inventory_controls"]["canonical_kind_counts"] = {"claim": 143504, "condition": 249066}
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="canonical|semantic|denominator"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_wrong_alias_count_without_dropping_source_rows(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    path = large / "L03.json"
    summary = json.loads(path.read_text())
    native = next(c for c in summary["native_inventory_controls"] if "semantic_inventory_controls" in c)
    native["semantic_inventory_controls"]["source_identity_alias_rows"] = 175
    summary["semantic_inventory_controls"]["source_identity_alias_rows"] = 175
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="alias|canonical|semantic"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_native_compressed_table_count_mismatch(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    path = large / "L03.json"
    summary = json.loads(path.read_text())
    native = next(c for c in summary["native_inventory_controls"] if "semantic_inventory_controls" in c)
    native["native_table_counts"]["semantic_unit"] = 392743
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="native|compressed|population"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_omitted_positive_native_parent_table(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    path = large / "L03.json"
    summary = json.loads(path.read_text())
    native = next(c for c in summary["native_inventory_controls"] if "/inventory-r8/" in c["source_path"])
    del native["native_table_counts"]["fixture_parent_context"]
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="native|compressed|table"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_native_parent_hash_not_bound_to_selected_receipts(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    path = large / "L03.json"
    summary = json.loads(path.read_text())
    native = next(c for c in summary["native_inventory_controls"] if "/semantic-inventory-r9/" in c["source_path"])
    native["source_sha256"] = "f" * 64
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="source|hash"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_reconciles_semantic_representation_categories_to_selected_units(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    summary = json.loads((large / "L03.json").read_text())
    binding = next(b for b in summary["units"] if b["source_table"] == "semantic_unit")
    path = large / "units" / (digest_json(binding) + ".json")
    unit = json.loads(path.read_text())
    unit["projection_counts"] = {"ma_semantic_claim_representation": 143680,
                                 "ma_semantic_condition_representation": 249064}
    path.write_text(json.dumps(unit))
    with pytest.raises(ValueError, match="representation|semantic"):
        summarizer.summarize(tmp_path, small, large)


def test_rollup_rejects_duplicated_window_even_when_summary_totals_match(synthetic_sizing_rollup, tmp_path):
    summarizer, small, large = synthetic_sizing_rollup()
    summary_path = large / "L07.json"
    summary = json.loads(summary_path.read_text())
    summary["units"][1] = dict(summary["units"][0])
    summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="windows differ"):
        summarizer.summarize(tmp_path, small, large)
