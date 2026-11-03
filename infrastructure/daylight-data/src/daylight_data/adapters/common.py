"""Read-only source row contracts. No domain acceptance is inferred by parsing."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from contextlib import closing
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping
from urllib.parse import quote

ADAPTER_VERSION = "d85-adapters-r1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    before = path.stat()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError(f"Source changed while hashing: {path}")
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    """Decimal values use exact JSON strings; their typed field declares the encoding."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=lambda item: str(item) if isinstance(item, Decimal) else _unsupported(item))


def _unsupported(value: Any) -> None:
    raise TypeError(f"Unsupported JSON type: {type(value).__name__}")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def digest_json_streamed(value: Any) -> str:
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                               default=lambda item: str(item) if isinstance(item, Decimal) else _unsupported(item))
    for part in encoder.iterencode(value):
        digest.update(part.encode())
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle, parse_float=Decimal)


@lru_cache(maxsize=15)
def adapter_code_sha256(layer_id: str) -> str:
    """Pin the exact executable projection files; a code change is a derivation change."""
    directory = Path(__file__).resolve().parent
    names = ['common.py', '__init__.py', layer_id.lower() + '.py', 'streaming.py', '../ingestion/loader.py']
    bindings = {name: sha256_file(directory / name) for name in names if (directory / name).is_file()}
    return digest_json({'adapter_version': ADAPTER_VERSION, 'code_sha256': bindings})


def offering_parts(identifier: str) -> dict[str, Any]:
    if not isinstance(identifier, str) or not re.fullmatch(r"2026:[A-Z]\d{4}:\d{3}:\d{3}", identifier):
        raise ValueError(f"Unsupported or unpadded 2026 offering identity: {identifier!r}")
    year, contract, plan, segment = identifier.split(":")
    return {"offering_id": identifier, "benefit_year": int(year), "contract_id": contract,
            "plan_id": plan, "segment_id": segment}


@dataclass(frozen=True)
class SourceRecord:
    layer_id: str
    source_path: str
    source_table: str
    source_row_ordinal: int
    source_row_key: str
    source_sha256: str
    snapshot_id: str
    derivation_id: str
    raw: Mapping[str, Any]
    ordinal_basis: str
    disposition: str = "retained"
    adapter_code_sha256: str = ""

    @property
    def record_id(self) -> str:
        return digest_json([self.snapshot_id, self.source_table, self.source_row_ordinal])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DomainProjection:
    source: SourceRecord
    entity_type: str
    entity_id: str
    fields: Mapping[str, Any]
    value_state: str = "published_observation"
    evidence_state: str = "source_observed"
    semantic_review_state: str = "not_newly_reviewed"
    source_use_state: str = "existing_source_policy_applies"
    freshness_state: str = "historical_2026_snapshot"
    output_acceptance_state: str = "research_only"
    conditions: Any = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_source(root: Path, path: Path, layer_id: str, table: str, ordinal: int,
                key: Any, raw: Mapping[str, Any], basis: str,
                source_hash: str | None = None, disposition: str = "retained") -> SourceRecord:
    source_hash = source_hash or sha256_file(path)
    snapshot = digest_json({"layer": layer_id, "path": path.relative_to(root).as_posix(),
                            "sha256": source_hash})
    code_digest = adapter_code_sha256(layer_id)
    return SourceRecord(layer_id, path.relative_to(root).as_posix(), table, ordinal, str(key),
                        source_hash, snapshot,
                        digest_json([snapshot, ADAPTER_VERSION, code_digest, table, "2026-source-preserving"]),
                        raw, basis, disposition, code_digest)


def json_records(root: Path, path: Path, layer_id: str, table: str,
                 key_field: str = "id") -> Iterator[SourceRecord]:
    rows = load_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"Expected source array: {path}")
    source_hash = sha256_file(path)
    for ordinal, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Expected object at source row {ordinal}: {path}")
        yield make_source(root, path, layer_id, table, ordinal,
                          row.get(key_field, ordinal), row, "json_array_position_1_based", source_hash)


def sqlite_records(root: Path, path: Path, layer_id: str,
                   tables: tuple[str, ...] | None = None,
                   logical_path: Path | None = None) -> Iterator[SourceRecord]:
    """Read immutable SQLite with explicit primary-key/rowid order; duplicates survive."""
    source_path = logical_path or path
    source_hash = sha256_file(source_path)
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        found = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if tables is not None and set(tables) - set(found):
            raise ValueError(f"Missing SQLite tables: {set(tables) - set(found)}")
        for table in tables or tuple(found):
            escaped = '"' + table.replace('"', '""') + '"'
            info = connection.execute(f"PRAGMA table_info({escaped})").fetchall()
            primary = [row['name'] for row in sorted(info, key=lambda row: row['pk']) if row['pk']]
            if primary:
                ordering = ", ".join('"' + item.replace('"', '""') + '"' for item in primary)
                query = f"SELECT * FROM {escaped} ORDER BY {ordering}"
                basis = "sqlite_primary_key_order:" + ",".join(primary)
            else:
                query = f"SELECT rowid AS __source_rowid__, * FROM {escaped} ORDER BY rowid"
                basis = "sqlite_persisted_rowid_order_within_exact_hashed_database"
            for ordinal, row in enumerate(connection.execute(query), 1):
                raw = dict(row)
                key = [raw[name] for name in primary] if primary else raw.pop('__source_rowid__')
                disposition = "quarantined_source_row_retained" if table == "quarantine" else "retained"
                yield make_source(root, source_path, layer_id, table, ordinal, canonical_json(key), raw,
                                  basis, source_hash, disposition)


def account(records: Iterator[SourceRecord]) -> dict[str, Any]:
    """Control totals count every source row; this is not domain verification."""
    tables: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    derivations = set()
    code_hashes = set()
    for row in records:
        derivations.add(row.derivation_id)
        code_hashes.add(row.adapter_code_sha256)
        key = row.source_path + "#" + row.source_table
        bucket = tables.setdefault(key, {"input_rows": 0, "retained_rows": 0,
                                         "quarantine_rows": 0, "unexplained_loss": 0})
        bucket['input_rows'] += 1
        bucket['retained_rows'] += 1
        if row.disposition == "quarantined_source_row_retained":
            bucket['quarantine_rows'] += 1
        digest.update(canonical_json([row.record_id, row.raw]).encode())
        digest.update(b"\n")
    return {"tables": tables, "source_rows": sum(row['input_rows'] for row in tables.values()),
            "stream_digest": digest.hexdigest(), "unexplained_loss": 0,
            "derivation_ids": sorted(derivations), "adapter_code_hashes": sorted(code_hashes),
            "meaning": "Source row transport accounting only; no new acceptance or domain verification"}
