"""Canonical bytes and bounded repository paths shared by the batch backend."""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path


def canonical(value) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except TypeError:
        # Source JSON decimals use Decimal before normalization. Emit a JSON
        # number, preserving its exact value/type instead of passing via float.
        def exact(item):
            if isinstance(item, Decimal):
                if not item.is_finite():
                    raise ValueError("Non-finite exact JSON decimal")
                return str(item)
            if isinstance(item, dict):
                if any(not isinstance(k, str) for k in item):
                    raise ValueError("JSON keys must be strings")
                return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + exact(item[k])
                                      for k in sorted(item)) + "}"
            if isinstance(item, list):
                return "[" + ",".join(exact(v) for v in item) + "]"
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        text = exact(value)
    return text.encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def repository_path(repository: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a relative repository path")
    root = repository.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path escapes the repository")
    return path


def safe_json(raw: str | bytes, *, exact_decimals=False):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON decimal")
        return result

    return json.loads(raw, parse_constant=reject_constant,
                      parse_float=Decimal if exact_decimals else finite_float,
                      object_pairs_hook=unique_pairs)


def quarantine_tree(value):
    """Keep exact numeric source values inspectable in a rejected input.

    The tagged node is explicitly a quarantine transport encoding, never a
    normalized source assertion. Original artifact bytes and hashes remain bound.
    """
    if isinstance(value, Decimal):
        return {"quarantined_json_decimal_lexeme": str(value)}
    if isinstance(value, dict):
        return {k: quarantine_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [quarantine_tree(v) for v in value]
    return value
