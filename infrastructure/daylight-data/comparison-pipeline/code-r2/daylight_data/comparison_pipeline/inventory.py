"""Verified, minimal SQLite index of the immutable L03 r9 inventory.

The cache transports source obligations; it never inherits evidence acceptance.
``ensure_inventory`` hashes the authoritative input bytes on *every* call. A
cold build additionally replays the sealed ASCII inventory digest, while warm
calls verify the much smaller cached metadata without decoding the master.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import tempfile
import time
from typing import Iterator


_PACKET = Path("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9")
_ALGORITHM = "daylight-r9-minimal-inventory/1"
_SCHEMA_VERSION = 1
_APPLICATION_ID = 0x444C4958  # DLIX; distinguishes this cache from other databases.
_HASH_ENCODING = "UTF-8 json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)"
_TRUSTED_RELEASE = {
    "freeze_sha256": "81e1a5f106f15db3a06a738fad0c315ec09ace99ae2908d80507904fb8df3e6d",
    "package_id": "L03-SEMANTIC-INVENTORY-COLLIER-2026-r9",
    "inventory_digest": "7010f371467e1ddc0ea8ab58af2d9d26a04803c844ae0829a8c271da1acd5cee",
    "required_claims": 143505,
    "required_conditions": 249065,
    "required_total": 392570,
    "offerings": 72,
}
_MEMBERS = (
    "inventory-binding.json", "denominator.json", "offering-inventory.json",
    "per-offering.csv", "master-inventory.jsonl.gz",
)
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_COLUMNS = "id,offering_id,kind,original_sha256,observation_ids_json"


class InventoryError(ValueError):
    """Inventory verification failed; no evidence or source text is exposed."""


class InventorySourceError(InventoryError):
    """The authoritative source no longer matches the pinned release."""


class InventoryCacheError(InventoryError):
    """An existing cache is corrupt, incomplete, or not owned by this module."""


class InventoryScopeError(InventoryError):
    """An offering is outside the verified inventory scope."""


def _canonical(value: object, *, ascii: bool = False) -> bytes:
    return json.dumps(value, ensure_ascii=ascii, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(data: bytes | str) -> object:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite JSON number")

    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)


def _positive_int(value: object) -> bool:
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class _Authority:
    directory: Path
    hashes: dict[str, str]
    offerings: dict[str, tuple[int, int]]
    fingerprint: str


def _regular_source(path: Path, repository: Path) -> None:
    if not path.is_file() or not path.resolve().is_relative_to(repository):
        raise InventorySourceError("INVENTORY_SOURCE_UNAVAILABLE")
    for parent in (path, *path.parents):
        if parent == repository:
            break
        if parent.is_symlink():
            raise InventorySourceError("INVENTORY_SOURCE_SYMLINK")


def _authority(repository: Path) -> _Authority:
    directory = repository / _PACKET
    hashes: dict[str, str] = {}
    data: dict[str, bytes] = {}
    try:
        # Small control bytes are parsed from the exact bytes hashed here.
        for name in ("freeze.json", *_MEMBERS):
            path = directory / name
            _regular_source(path, repository)
            if name == "master-inventory.jsonl.gz":
                hashes[name] = _file_hash(path)
            else:
                if path.stat().st_size > 8 * 1024**2:
                    raise InventorySourceError("INVENTORY_CONTROL_TOO_LARGE")
                data[name] = path.read_bytes()
                hashes[name] = _sha(data[name])
        if hashes["freeze.json"] != _TRUSTED_RELEASE["freeze_sha256"]:
            raise InventorySourceError("INVENTORY_FREEZE_MISMATCH")
        freeze = _json(data["freeze.json"])
        if not isinstance(freeze, dict):
            raise ValueError
        if (freeze.get("schema") != "l03-semantic-inventory-freeze/1"
                or freeze.get("semantic_claim_denominator_frozen") is not True
                or freeze.get("new_evidence_accepted") is not False
                or freeze.get("fully_verified_L03") is not False):
            raise InventorySourceError("INVENTORY_FREEZE_SCOPE_MISMATCH")
        for key in ("package_id", "inventory_digest", "required_claims",
                    "required_conditions", "required_total"):
            if freeze.get(key) != _TRUSTED_RELEASE[key]:
                raise InventorySourceError("INVENTORY_RELEASE_SCOPE_MISMATCH")
        for name in _MEMBERS:
            if freeze["files_sha256"].get(name) != hashes[name]:
                raise InventorySourceError("INVENTORY_MEMBER_HASH_MISMATCH")
        binding = _json(data["inventory-binding.json"])
        denominator = _json(data["denominator.json"])
        if (binding["required_record_count"] != _TRUSTED_RELEASE["required_total"]
                or binding["inventory_digest"] != _TRUSTED_RELEASE["inventory_digest"]
                or binding.get("new_acceptance_inherited") is not False
                or binding.get("algorithm") != "SHA256 of all canonical records sorted by ID, compact sorted-key JSON array"):
            raise InventorySourceError("INVENTORY_BINDING_MISMATCH")
        for key in ("package_id", "required_claims", "required_conditions", "required_total", "offerings"):
            if denominator.get(key) != _TRUSTED_RELEASE[key]:
                raise InventorySourceError("INVENTORY_DENOMINATOR_MISMATCH")
        offerings = {}
        for row in _json(data["offering-inventory.json"]):
            identifier = row["offering_id"]
            required = row["required"]
            if (not isinstance(identifier, str) or not identifier
                    or identifier in offerings or set(required) != {"claim", "condition"}
                    or not all(_positive_int(v) for v in required.values())):
                raise InventorySourceError("INVENTORY_OFFERING_SCOPE_MISMATCH")
            offerings[identifier] = (required["claim"], required["condition"])
        if (len(offerings) != _TRUSTED_RELEASE["offerings"]
                or sum(v[0] for v in offerings.values()) != _TRUSTED_RELEASE["required_claims"]
                or sum(v[1] for v in offerings.values()) != _TRUSTED_RELEASE["required_conditions"]):
            raise InventorySourceError("INVENTORY_OFFERING_COUNTS_MISMATCH")
        csv_counts = {}
        for row in csv.DictReader(io.StringIO(data["per-offering.csv"].decode("utf-8"))):
            identifier = row["offering_id"]
            counts = (int(row["required_claims"]), int(row["required_conditions"]))
            if identifier in csv_counts or int(row["required_total"]) != sum(counts):
                raise InventorySourceError("INVENTORY_OFFERING_CSV_MISMATCH")
            csv_counts[identifier] = counts
        if csv_counts != offerings:
            raise InventorySourceError("INVENTORY_OFFERING_CSV_MISMATCH")
    except InventoryError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, csv.Error):
        raise InventorySourceError("INVENTORY_CONTROL_INVALID") from None
    fingerprint = _sha(_canonical({"algorithm": _ALGORITHM,
                                   "implementation_sha256": _file_hash(Path(__file__)),
                                   "source_hashes": hashes}))
    return _Authority(directory, hashes, offerings, fingerprint)


def _update_rows_digest(digest, row: tuple) -> None:
    # Length prefixes make all boundaries unambiguous, without parsing cached
    # observation JSON or serializing full source originals on warm replay.
    for value in row:
        data = value.encode("utf-8")
        digest.update(struct.pack(">Q", len(data)))
        digest.update(data)


def _stream_originals(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rb") as handle:
        while line := handle.readline(16 * 1024**2 + 1):
            if len(line) > 16 * 1024**2 or not line.strip():
                raise InventorySourceError("INVENTORY_RECORD_INVALID")
            try:
                row = _json(line)
            except (ValueError, TypeError, UnicodeError):
                raise InventorySourceError("INVENTORY_RECORD_INVALID") from None
            if not isinstance(row, dict):
                raise InventorySourceError("INVENTORY_RECORD_INVALID")
            yield row


def _readonly(database: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error:
        raise InventoryCacheError("INVENTORY_CACHE_UNREADABLE") from None


def _metadata(connection: sqlite3.Connection) -> dict:
    try:
        if (connection.execute("PRAGMA application_id").fetchone()[0] != _APPLICATION_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != _SCHEMA_VERSION):
            raise InventoryCacheError("INVENTORY_CACHE_SCHEMA_MISMATCH")
        rows = connection.execute("SELECT payload FROM inventory_metadata").fetchall()
        if len(rows) != 1:
            raise InventoryCacheError("INVENTORY_CACHE_INCOMPLETE")
        metadata = _json(rows[0][0])
        if (metadata["state"] != "complete" or metadata["accepted_for_reference"] is not False
                or metadata["inventory_digest"] != _TRUSTED_RELEASE["inventory_digest"]
                or metadata["source_hashes"]["freeze.json"] != _TRUSTED_RELEASE["freeze_sha256"]
                or metadata["record_count"] != _TRUSTED_RELEASE["required_total"]
                or metadata["offering_count"] != _TRUSTED_RELEASE["offerings"]
                or metadata["original_sha256_encoding"] != _HASH_ENCODING):
            raise InventoryCacheError("INVENTORY_CACHE_INCOMPLETE")
        if (not isinstance(metadata["algorithm"], str)
                or not _SHA.fullmatch(metadata["implementation_sha256"])
                or set(metadata["source_hashes"]) != {"freeze.json", *_MEMBERS}
                or not all(isinstance(v, str) and _SHA.fullmatch(v)
                           for v in metadata["source_hashes"].values())
                or not _SHA.fullmatch(metadata["metadata_digest"])):
            raise InventoryCacheError("INVENTORY_CACHE_BINDING_INVALID")
        fingerprint = _sha(_canonical({"algorithm": metadata["algorithm"],
                                       "implementation_sha256": metadata["implementation_sha256"],
                                       "source_hashes": metadata["source_hashes"]}))
        if fingerprint != metadata["source_fingerprint"]:
            raise InventoryCacheError("INVENTORY_CACHE_FINGERPRINT_MISMATCH")
        return metadata
    except InventoryError:
        raise
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        raise InventoryCacheError("INVENTORY_CACHE_INVALID") from None


def _verify_rows(connection: sqlite3.Connection, expected: dict[str, tuple[int, int]]) -> str:
    digest = hashlib.sha256()
    per_offering = {key: hashlib.sha256() for key in expected}
    counts = Counter()
    total = 0
    for row in connection.execute(f"SELECT {_COLUMNS} FROM inventory_originals ORDER BY id"):
        identifier, offering, kind, original_hash, observations = row
        if (offering not in expected or kind not in {"claim", "condition"}
                or not isinstance(identifier, str) or not identifier
                or not isinstance(original_hash, str) or not _SHA.fullmatch(original_hash)
                or not isinstance(observations, str)):
            raise InventoryCacheError("INVENTORY_CACHE_ROW_INVALID")
        _update_rows_digest(digest, row)
        _update_rows_digest(per_offering[offering], row)
        counts[offering, kind] += 1
        total += 1
    if total != _TRUSTED_RELEASE["required_total"]:
        raise InventoryCacheError("INVENTORY_CACHE_COUNT_MISMATCH")
    actual = connection.execute("SELECT offering_id,claims,conditions,metadata_digest FROM inventory_offerings").fetchall()
    if len(actual) != len(expected):
        raise InventoryCacheError("INVENTORY_CACHE_OFFERING_MISMATCH")
    for offering, claims, conditions, row_digest in actual:
        if (offering not in expected or (claims, conditions) != expected[offering]
                or (counts[offering, "claim"], counts[offering, "condition"]) != expected[offering]
                or per_offering[offering].hexdigest() != row_digest):
            raise InventoryCacheError("INVENTORY_CACHE_OFFERING_MISMATCH")
    return digest.hexdigest()


def _validate_cache(database: Path, authority: _Authority) -> dict:
    connection = _readonly(database)
    try:
        metadata = _metadata(connection)
        if metadata["source_hashes"] != authority.hashes:
            raise InventoryCacheError("INVENTORY_CACHE_SOURCE_BINDING_MISMATCH")
        if (metadata["algorithm"] != _ALGORITHM
                or metadata["implementation_sha256"] != _file_hash(Path(__file__))):
            return {}  # Recognized complete cache, now stale; build a new file.
        if metadata["source_fingerprint"] != authority.fingerprint:
            raise InventoryCacheError("INVENTORY_CACHE_FINGERPRINT_MISMATCH")
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise InventoryCacheError("INVENTORY_CACHE_INTEGRITY_FAILURE")
        if _verify_rows(connection, authority.offerings) != metadata["metadata_digest"]:
            raise InventoryCacheError("INVENTORY_CACHE_DIGEST_MISMATCH")
        return metadata
    except sqlite3.Error:
        raise InventoryCacheError("INVENTORY_CACHE_INVALID") from None
    finally:
        connection.close()


@contextmanager
def _build_lock(database: Path):
    # A separate stable inode survives atomic replacement of the cache. The
    # standard-library lock serializes concurrent builders, including processes.
    lock = database.with_name(database.name + ".lock")
    if lock.is_symlink():
        raise InventoryCacheError("INVENTORY_CACHE_LOCK_SYMLINK")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":  # pragma: no cover - POSIX is the deployment target.
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _build(database: Path, repository: Path, authority: _Authority) -> dict:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{database.name}.build-", dir=database.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    connection = None
    try:
        connection = sqlite3.connect(temporary, isolation_level=None)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA cache_size=-8192")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
        connection.execute("CREATE TABLE inventory_metadata(payload TEXT NOT NULL)")
        connection.execute("CREATE TABLE inventory_offerings(offering_id TEXT PRIMARY KEY,claims INTEGER NOT NULL,conditions INTEGER NOT NULL,metadata_digest TEXT NOT NULL) WITHOUT ROWID")
        connection.execute("CREATE TABLE inventory_originals(id TEXT PRIMARY KEY,offering_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('claim','condition')),original_sha256 TEXT NOT NULL,observation_ids_json TEXT NOT NULL) WITHOUT ROWID")
        connection.execute("CREATE INDEX inventory_by_offering ON inventory_originals(offering_id,id)")
        digest = hashlib.sha256(b"[")
        minimal_digest = hashlib.sha256()
        per_offering = {key: hashlib.sha256() for key in authority.offerings}
        counts = Counter()
        previous = ""
        total = 0
        batch = []
        for original in _stream_originals(authority.directory / "master-inventory.jsonl.gz"):
            identifier = original.get("id")
            offering = original.get("offering_id")
            kind = original.get("kind")
            observations = original.get("observation_ids")
            if (not isinstance(identifier, str) or identifier <= previous
                    or offering not in authority.offerings or kind not in {"claim", "condition"}
                    or not isinstance(observations, list)
                    or not all(isinstance(item, str) and item for item in observations)
                    or original.get("accepted_for_reference") is not False):
                raise InventorySourceError("INVENTORY_RECORD_SCOPE_MISMATCH")
            if total:
                digest.update(b",")
            digest.update(_canonical(original, ascii=True))
            row = (identifier, offering, kind, _sha(_canonical(original)),
                   _canonical(observations).decode("utf-8"))
            batch.append(row)
            _update_rows_digest(minimal_digest, row)
            _update_rows_digest(per_offering[offering], row)
            counts[offering, kind] += 1
            total += 1
            previous = identifier
            if len(batch) == 1000:
                connection.executemany("INSERT INTO inventory_originals VALUES(?,?,?,?,?)", batch)
                batch.clear()
        connection.executemany("INSERT INTO inventory_originals VALUES(?,?,?,?,?)", batch)
        digest.update(b"]")
        if (total != _TRUSTED_RELEASE["required_total"]
                or digest.hexdigest() != _TRUSTED_RELEASE["inventory_digest"]):
            raise InventorySourceError("INVENTORY_ASCII_DIGEST_OR_COUNT_MISMATCH")
        for offering, expected in authority.offerings.items():
            if (counts[offering, "claim"], counts[offering, "condition"]) != expected:
                raise InventorySourceError("INVENTORY_RECORD_OFFERING_COUNTS_MISMATCH")
            connection.execute("INSERT INTO inventory_offerings VALUES(?,?,?,?)",
                               (offering, *expected, per_offering[offering].hexdigest()))
        metadata = {
            "state": "complete", "algorithm": _ALGORITHM,
            "implementation_sha256": _file_hash(Path(__file__)),
            "source_fingerprint": authority.fingerprint, "source_hashes": authority.hashes,
            "inventory_digest": digest.hexdigest(), "metadata_digest": minimal_digest.hexdigest(),
            "record_count": total, "offering_count": len(authority.offerings),
            "original_sha256_encoding": _HASH_ENCODING,
            "built_at_utc": datetime.now(timezone.utc).isoformat(), "accepted_for_reference": False,
        }
        connection.execute("INSERT INTO inventory_metadata VALUES(?)", (_canonical(metadata).decode("utf-8"),))
        connection.commit()
        connection.close()
        connection = None
        _validate_cache(temporary, authority)
        # Close the source-change-during-build window before publishing anything.
        if _authority(repository).fingerprint != authority.fingerprint:
            raise InventorySourceError("INVENTORY_SOURCE_CHANGED_DURING_BUILD")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, database)
        if os.name != "nt":
            directory = os.open(database.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        return metadata
    except InventoryError:
        raise
    except (OSError, sqlite3.Error, EOFError, ValueError, TypeError, UnicodeError):
        raise InventoryError("INVENTORY_BUILD_FAILED") from None
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-journal").unlink(missing_ok=True)


def ensure_inventory(repository: Path, database: Path) -> dict:
    """Return a verified index-build/cache-hit receipt; source mismatches fail.

    Corrupt or incomplete existing caches raise ``InventoryCacheError`` without
    replacing them. A complete cache from an older algorithm is atomically
    rebuilt. Returned timings are wall-clock seconds; no acceptance is granted.
    """
    started = time.perf_counter()
    repository = Path(repository).resolve()
    database = Path(database).absolute()
    if database.is_symlink() or database.resolve().is_relative_to(repository / _PACKET):
        raise InventoryCacheError("INVENTORY_CACHE_PATH_UNSAFE")
    authority = _authority(repository)
    source_seconds = time.perf_counter() - started
    database.parent.mkdir(parents=True, exist_ok=True)
    validation_seconds = build_seconds = 0.0
    with _build_lock(database):
        metadata = {}
        if database.exists():
            checked = time.perf_counter()
            metadata = _validate_cache(database, authority)
            validation_seconds = time.perf_counter() - checked
        hit = bool(metadata)
        if not hit:
            building = time.perf_counter()
            metadata = _build(database, repository, authority)
            build_seconds = time.perf_counter() - building
    return {
        "mode": "cache_hit" if hit else "index_build", "cache_hit": hit,
        "index_build": not hit, "database": str(database),
        "record_count": metadata["record_count"], "offering_count": metadata["offering_count"],
        "inventory_digest": metadata["inventory_digest"],
        "metadata_digest": metadata["metadata_digest"],
        "source_fingerprint": authority.fingerprint, "source_hashes": authority.hashes,
        "implementation_sha256": metadata["implementation_sha256"],
        "algorithm": _ALGORITHM, "original_sha256_encoding": _HASH_ENCODING,
        "timings": {"source_verification_seconds": source_seconds,
                    "cache_verification_seconds": validation_seconds,
                    "index_build_seconds": build_seconds,
                    "total_seconds": time.perf_counter() - started},
        "accepted_for_reference": False,
    }


def originals_for_offering(database: Path, offering_id: str) -> list[dict]:
    """Read original IDs/kinds/hashes/observations in deterministic ID order.

    Call ``ensure_inventory`` first to verify current authoritative source bytes.
    This read validates the cache metadata, global row count, and this offering's
    complete minimal-row digest/counts. Unknown offerings fail rather than yield
    an empty denominator. No source text or full original payload is stored.
    """
    database = Path(database)
    if database.is_symlink():
        raise InventoryCacheError("INVENTORY_CACHE_PATH_UNSAFE")
    connection = _readonly(database)
    try:
        metadata = _metadata(connection)
        if (metadata["algorithm"] != _ALGORITHM
                or metadata["implementation_sha256"] != _file_hash(Path(__file__))):
            raise InventoryCacheError("INVENTORY_CACHE_ALGORITHM_STALE")
        if connection.execute("SELECT count(*) FROM inventory_originals").fetchone()[0] != metadata["record_count"]:
            raise InventoryCacheError("INVENTORY_CACHE_COUNT_MISMATCH")
        if connection.execute("SELECT count(*) FROM inventory_offerings").fetchone()[0] != metadata["offering_count"]:
            raise InventoryCacheError("INVENTORY_CACHE_OFFERING_MISMATCH")
        expected = connection.execute("SELECT claims,conditions,metadata_digest FROM inventory_offerings WHERE offering_id=?", (offering_id,)).fetchone()
        if expected is None:
            raise InventoryScopeError("INVENTORY_OFFERING_OUTSIDE_SCOPE")
        rows = connection.execute(f"SELECT {_COLUMNS} FROM inventory_originals WHERE offering_id=? ORDER BY id", (offering_id,)).fetchall()
        digest = hashlib.sha256()
        counts = Counter()
        result = []
        for row in rows:
            _update_rows_digest(digest, row)
            identifier, offering, kind, original_hash, observation_json = row
            counts[kind] += 1
            observations = _json(observation_json)
            if (not isinstance(observations, list)
                    or not all(isinstance(item, str) and item for item in observations)):
                raise InventoryCacheError("INVENTORY_CACHE_ROW_INVALID")
            result.append({"id": identifier, "offering_id": offering, "kind": kind,
                           "original_sha256": original_hash, "observation_ids": observations})
        if ((counts["claim"], counts["condition"]) != expected[:2]
                or digest.hexdigest() != expected[2]):
            raise InventoryCacheError("INVENTORY_CACHE_OFFERING_MISMATCH")
        return result
    except InventoryError:
        raise
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        raise InventoryCacheError("INVENTORY_CACHE_INVALID") from None
    finally:
        connection.close()
