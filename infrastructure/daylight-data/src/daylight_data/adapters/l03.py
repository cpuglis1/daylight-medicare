"""Full frozen L03 obligation/lineage transport; semantic review stays held."""
from decimal import Decimal
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import struct

from .common import DomainProjection, load_json, sha256_file, sqlite_records
from .streaming import json_document_records, jsonl_records, unpack_sqlite

BASE = "docs/data/l03-ma-benefits-2026-10-25"
COMPONENTS = ("bounded-reference-r4", "source-reconciliation-r7",
              "semantic-inventory-r9", "inventory-r8")


def iter_records(root):
    root = Path(root).resolve()
    for component in COMPONENTS:
        directory = root / BASE / component
        if component in ("semantic-inventory-r9", "inventory-r8"):
            freeze = load_json(directory / "freeze.json")
            compressed = directory / "inventory.sqlite3.gz"
            if sha256_file(compressed) != freeze["files_sha256"]["inventory.sqlite3.gz"]:
                raise ValueError("L03 compressed inventory differs from frozen source hash")
            with compressed.open("rb") as handle:
                handle.seek(-4, 2)
                expanded_size = struct.unpack("<I", handle.read(4))[0]
            with unpack_sqlite(root, compressed,
                               freeze.get("sqlite_uncompressed_sha256"),
                               freeze.get("sqlite_uncompressed_bytes", expanded_size)) as path:
                yield from sqlite_records(root, path, "L03", logical_path=compressed)
            # SQLite contains all source/lineage/obligation rows. Parallel JSONL
            # exports are mirrors, not extra claims or a second denominator.
            controls = ("freeze.json", "denominator.json", "pilot-contract.json",
                        "scope-policy.json", "source-boundaries.json", "exceptions.json")
            for name in controls:
                yield from json_document_records(root, directory / name, "L03", name[:-5])
        else:
            for path in sorted(directory.iterdir()):
                if not path.is_file():
                    continue
                if path.name.endswith(".jsonl.gz"):
                    yield from jsonl_records(root, path, "L03", path.name[:-9])
                elif path.suffix == ".json":
                    yield from json_document_records(root, path, "L03", path.stem)


def project_record(row):
    raw = dict(row.raw)
    payload = json.loads(raw["payload"], parse_float=Decimal) if isinstance(raw.get("payload"), str) else raw
    fields = dict(payload) if isinstance(payload, dict) else {"source_payload": payload}
    # Retain explicit columns beside parsed payload without overwriting source facts.
    fields["source_columns"] = {k: v for k, v in raw.items() if k != "payload"}
    fields["reference_component"] = next(iter(row.source_path.split("/")[3:4]), "fixture_or_external_component")
    fields["personal_applicability_determined"] = False
    if "offering_id" in raw:
        fields["offering_id"] = raw["offering_id"]
    entity_type = "ma_benefit_" + row.source_table.replace("-", "_")
    if row.source_table == "entries":
        fields["amount_decimal"] = Decimal(raw["value"]) if raw.get("value") is not None else None
        fields["unit"] = raw.get("unit")
        entity_type = "ma_published_reference_entry"
    if row.source_table == "semantic_unit":
        entity_type = "ma_semantic_" + raw["kind"] + "_representation"
        fields["semantic_unit_id"] = raw["id"]
        fields["accepted_for_reference"] = False
    if row.source_table == "work_obligation":
        entity_type = "ma_followup_" + raw["kind"]
        fields["followup_obligation_id"] = raw["id"]
        fields["accepted_for_reference"] = False
    conditions = {key: payload[key] for key in ("context", "qualifications", "parent_id", "parent_ids", "states", "work_policy_id")
                  if isinstance(payload, dict) and key in payload}
    # Source/table/ordinal identify every row, including repeated text and links.
    return DomainProjection(row, entity_type, "L03:" + row.record_id, fields,
                            value_state=str(raw.get("state", "source_observed")),
                            conditions=conditions,
                            output_acceptance_state="exact_existing_receipt_gate_required" if row.source_table == "entries" else "research_only")


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)


def native_table_counts(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-8192")
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                for name in names}


def semantic_inventory_controls(path):
    """Use r9's sealed canonical grain; retain every native alias representation."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-8192")
        canonical = dict(db.execute("""SELECT u.kind,count(DISTINCT c.canonical_id)
            FROM semantic_unit u JOIN canonical_unit c ON c.unit_id=u.id GROUP BY u.kind"""))
        semantic = dict(db.execute("SELECT kind,count(*) FROM semantic_unit GROUP BY kind"))
        return {"canonical_kind_counts": canonical, "semantic_kind_counts": semantic,
                "semantic_representation_rows": db.execute("SELECT count(*) FROM semantic_unit").fetchone()[0],
                "canonical_mapping_rows": db.execute("SELECT count(*) FROM canonical_unit").fetchone()[0],
                "canonical_identity_rows": db.execute("SELECT count(DISTINCT canonical_id) FROM canonical_unit").fetchone()[0],
                "source_identity_alias_rows": db.execute("SELECT count(*) FROM source_identity_alias").fetchone()[0],
                "work_obligation_rows": db.execute("SELECT count(*) FROM work_obligation").fetchone()[0],
                "missing_canonical_mappings": db.execute("""SELECT count(*) FROM semantic_unit u
                    LEFT JOIN canonical_unit c ON c.unit_id=u.id WHERE c.unit_id IS NULL""").fetchone()[0]}


def sizing_controls(root):
    """Independently count both frozen SQLite parents after their complete transport."""
    root = Path(root).resolve()
    controls = []
    for component in ("semantic-inventory-r9", "inventory-r8"):
        directory = root / BASE / component
        freeze = load_json(directory / "freeze.json")
        compressed = directory / "inventory.sqlite3.gz"
        compressed_sha = sha256_file(compressed)
        if compressed_sha != freeze["files_sha256"]["inventory.sqlite3.gz"]:
            raise ValueError("L03 compressed inventory differs from frozen source hash")
        with compressed.open("rb") as handle:
            handle.seek(-4, 2)
            expanded_size = struct.unpack("<I", handle.read(4))[0]
        with unpack_sqlite(root, compressed, freeze.get("sqlite_uncompressed_sha256"),
                           freeze.get("sqlite_uncompressed_bytes", expanded_size)) as path:
            item = {"source_path": str(compressed.relative_to(root)), "source_sha256": compressed_sha,
                    "expanded_sha256": sha256_file(path), "expanded_bytes": path.stat().st_size,
                    "native_table_counts": native_table_counts(path)}
            if component == "semantic-inventory-r9":
                item["semantic_inventory_controls"] = semantic_inventory_controls(path)
            controls.append(item)
    return controls
