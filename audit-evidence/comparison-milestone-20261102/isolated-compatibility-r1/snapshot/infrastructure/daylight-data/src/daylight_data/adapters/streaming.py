"""Bounded JSON/JSONL readers for immutable local evidence files."""
from __future__ import annotations

import gzip
import json
import hashlib
import shutil
import tempfile
import os
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import ijson

from .common import make_source, sha256_file


def json_array_records(root, path, layer_id, table, prefix="item", key_field="id"):
    root, path = Path(root), Path(path)
    source_hash = sha256_file(path)
    with path.open("rb") as handle:
        for ordinal, raw in enumerate(ijson.items(handle, prefix), 1):
            if not isinstance(raw, dict):
                raw = {"source_value": raw}
            yield make_source(root, path, layer_id, table, ordinal,
                              raw.get(key_field, ordinal), raw,
                              "json_array_position_1_based:" + prefix, source_hash)


def jsonl_records(root, path, layer_id, table, key_field="id"):
    root, path = Path(root), Path(path)
    source_hash = sha256_file(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig") as handle:
        for ordinal, line in enumerate(handle, 1):
            # Blank source lines are invalid, rather than silently changing ordinals.
            raw = json.loads(line, parse_float=Decimal)
            if not isinstance(raw, dict):
                raise ValueError(f"Expected JSONL object: {path}:{ordinal}")
            yield make_source(root, path, layer_id, table, ordinal,
                              raw.get(key_field, ordinal), raw,
                              "jsonl_physical_line_1_based", source_hash)


def json_document_records(root, path, layer_id, table):
    """Stream array records; retain an object/scalar document as one envelope."""
    path = Path(path)
    with path.open("rb") as handle:
        first = handle.read(4096).lstrip(b"\xef\xbb\xbf \t\r\n")[:1]
    if first == b"[":
        yield from json_array_records(root, path, layer_id, table)
    else:
        with path.open(encoding="utf-8-sig") as handle:
            value = json.load(handle, parse_float=Decimal)
        raw = value if isinstance(value, dict) else {"source_value": value}
        yield make_source(Path(root), path, layer_id, table, 1, "document", raw,
                          "complete_json_document", sha256_file(path))


@contextmanager
def unpack_sqlite(root, compressed_path, expected_sha256=None, expected_bytes=None):
    """Read-only compressed source; disposable expansion is not a second archive.

    Expanded bytes are checked and deleted when the reader closes. The original
    compressed source remains the snapshot identity/archive object.
    """
    root, compressed_path = Path(root), Path(compressed_path)
    cache = root / "infrastructure/daylight-data/.state/sqlite-sizing-cache"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    reserve = 7 * 1024**3
    if expected_bytes and shutil.disk_usage(cache).free < reserve + expected_bytes:
        raise RuntimeError("Insufficient disk reserve to expand immutable SQLite source")
    with tempfile.TemporaryDirectory(prefix="expanded-", dir=cache) as directory:
        target = Path(directory) / "source.sqlite3"
        digest, size = hashlib.sha256(), 0
        with gzip.open(compressed_path, "rb") as source, target.open("wb") as output:
            for block in iter(lambda: source.read(1024**2), b""):
                if shutil.disk_usage(cache).free < reserve + len(block):
                    raise RuntimeError("SQLite expansion reached configured disk reserve")
                size += len(block)
                if expected_bytes and size > expected_bytes:
                    raise ValueError("Expanded SQLite exceeds frozen byte count")
                digest.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        if expected_sha256 and digest.hexdigest() != expected_sha256:
            raise ValueError("Expanded SQLite differs from frozen hash")
        if expected_bytes and size != expected_bytes:
            raise ValueError("Expanded SQLite differs from frozen byte count")
        receipt = {"compressed_path": str(compressed_path.relative_to(root)),
                   "compressed_sha256": sha256_file(compressed_path),
                   "observed_expanded_sha256": digest.hexdigest(), "observed_expanded_bytes": size,
                   "expanded_hash_authority": "frozen_manifest" if expected_sha256 else "observed_decompression",
                   "expanded_size_check": "frozen_manifest" if expected_sha256 else "gzip_ISIZE_check_only"}
        receipt_dir = root / "infrastructure/daylight-data/.state/expanded-source-receipts"
        receipt_dir.mkdir(exist_ok=True, mode=0o700)
        receipt_path = receipt_dir / (receipt["compressed_sha256"] + ".json")
        encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if receipt_path.exists():
            if receipt_path.read_text() != encoded:
                raise ValueError("Expanded source receipt differs")
        else:
            with receipt_path.open("x") as handle:
                handle.write(encoded)
        target.chmod(0o400)
        yield target
