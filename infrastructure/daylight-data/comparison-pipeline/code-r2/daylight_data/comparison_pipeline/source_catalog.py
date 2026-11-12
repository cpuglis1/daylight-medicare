"""Discover exact source bytes through explicit, local manifest references.

This is a preparation utility, not a source interpreter or acceptance registry.
Manifest claims are hints: only the actual SHA256 of a concrete repository file
can resolve a wanted hash. No directory traversal, archive inflation, network
lookup, basename search, or inference of a missing source occurs here.
"""
from __future__ import annotations

from collections import Counter, deque
import hashlib
from pathlib import Path
import re
from typing import Any

from .common import canonical, file_hash, repository_path, safe_json


_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_HASH_FIELDS = ("sha256", "file_sha256", "source_sha256")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")


def _hash_value(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and _SHA256.fullmatch(value) else None


def _pointer(path: str, key: Any) -> str:
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


def resolve_source_bindings(
    repository: Path,
    wanted_hashes: set[str],
    manifest_paths: list[str],
    *,
    max_manifest_bytes: int = 8 * 1024 * 1024,
    max_manifests: int = 256,
    max_total_manifest_bytes: int = 64 * 1024 * 1024,
    max_candidate_files: int = 10_000,
) -> dict:
    """Resolve hashes from bounded, explicit local candidates, preserving lineage.

    Root manifest paths are explicitly selected by the caller. Child ``.json``
    files are parsed only when an explicit path/hash claim matches their actual
    bytes. Bare path strings are untrusted file candidates, not authorization to
    recurse. Relative references are tried at the repository root and relative
    to the declaring manifest; every existing safe match retains its provenance.
    Absolute paths are usable only when already inside this exact repository.

    Limits constrain parsing and candidate counts; candidate file hashing is
    streamed and never decompresses referenced archives or JSONL collections.
    Limit/access/format diagnostics mean discovery is incomplete, not that a
    source does not exist. Returned sources confer no semantic review/acceptance.
    """
    root = Path(repository).resolve()
    if not root.is_dir():
        raise ValueError("repository must be an existing directory")
    if not isinstance(wanted_hashes, set) or any(_hash_value(v) is None for v in wanted_hashes):
        raise ValueError("wanted_hashes must be a set of 64-hex SHA256 values")
    if not isinstance(manifest_paths, list) or any(not isinstance(p, str) or not p for p in manifest_paths):
        raise ValueError("manifest_paths must be a list of nonempty explicit paths")
    for name, limit in (("max_manifest_bytes", max_manifest_bytes), ("max_manifests", max_manifests),
                        ("max_total_manifest_bytes", max_total_manifest_bytes),
                        ("max_candidate_files", max_candidate_files)):
        if type(limit) is not int or limit < 1:
            raise ValueError(f"{name} must be a positive integer")
    wanted = {value.lower() for value in wanted_hashes}
    counts: Counter = Counter()
    diagnostics: list[dict] = []
    provenance: list[dict] = []
    manifest_bindings: list[dict] = []
    # Keys are canonical, resolved repository-relative paths, so aliases do not
    # cause repeated hashing or recursion. Distinct files with equal bytes stay.
    candidates: dict[str, dict] = {}
    pending: deque[str] = deque()
    queued: set[str] = set()
    visited: set[str] = set()
    invalidated: set[str] = set()
    path_cache: dict[tuple[str, str | None], tuple[list[tuple[str, str]], list[str]]] = {}

    def diagnostic(code: str, **details: Any) -> None:
        diagnostics.append({"code": code, **details})

    def safe_candidates(raw: str, manifest: str | None) -> tuple[list[tuple[str, str]], list[str]]:
        key = (raw, manifest)
        if key in path_cache:
            return path_cache[key]
        existing, rejected = [], []
        if not raw or "\x00" in raw or "\n" in raw or "\r" in raw or _SCHEME.match(raw):
            result = ([], ["unsupported_path"])
            path_cache[key] = result
            return result
        supplied = Path(raw)
        if supplied.is_absolute():
            try:
                # macOS exposes the same in-repository file via /var and
                # /private/var. Resolve first, then still pass the relative
                # result through the shared repository boundary guard.
                possibilities = [(str(supplied.resolve().relative_to(root)), "repository_absolute")]
            except (ValueError, OSError, RuntimeError):
                result = ([], ["outside_repository"])
                path_cache[key] = result
                return result
        else:
            possibilities = [(raw, "repository_relative")]
            if manifest and Path(manifest).parent != Path("."):
                possibilities.append((str(Path(manifest).parent / supplied), "manifest_relative"))
        for relative, anchor in possibilities:
            try:
                path = repository_path(root, relative)
                if path.is_file():
                    match = (str(path.relative_to(root)), anchor)
                    if match not in existing:
                        existing.append(match)
            except (ValueError, OSError, RuntimeError):
                rejected.append(anchor)
        result = (sorted(existing), sorted(set(rejected)))
        path_cache[key] = result
        return result

    def enqueue(relative: str) -> None:
        if relative not in visited and relative not in queued:
            pending.append(relative)
            queued.add(relative)

    def reference(raw: str, manifest: str | None, pointer: str,
                  claims: list[tuple[str, str]], *, explicit: bool = False, seed: bool = False) -> None:
        matches, rejected = safe_candidates(raw, manifest)
        if not matches:
            if explicit or seed:
                code = "REJECTED_PATH" if rejected else "REFERENCED_FILE_UNAVAILABLE"
                counts["rejected_path_count" if rejected else "unavailable_path_count"] += 1
                diagnostic(code, manifest=manifest, pointer=pointer, referenced_path=raw,
                           rejected_anchors=rejected, claimed_sha256=sorted({h for _, h in claims}))
            return
        counts["candidate_reference_count"] += 1
        for relative, anchor in matches:
            if relative not in candidates:
                if len(candidates) >= max_candidate_files:
                    counts["candidate_limit_count"] += 1
                    diagnostic("CANDIDATE_FILE_LIMIT_REACHED", path=relative, manifest=manifest, pointer=pointer)
                    continue
                path = repository_path(root, relative)
                try:
                    size = path.stat().st_size
                    actual = file_hash(path)
                except (OSError, ValueError, RuntimeError):
                    diagnostic("CANDIDATE_FILE_UNREADABLE", path=relative, manifest=manifest, pointer=pointer)
                    continue
                candidates[relative] = {"sha256": actual, "bytes": size}
                counts["files_hashed"] += 1
                counts["bytes_hashed"] += size
            actual = candidates[relative]["sha256"]
            matched_pin = any(expected == actual for _, expected in claims)
            provenance.append({
                "path": relative, "actual_sha256": actual,
                "declaring_manifest": manifest, "pointer": pointer,
                "referenced_path": raw, "resolution_anchor": anchor,
                "claims": [{"field": field, "sha256": value, "matches_actual_bytes": value == actual}
                           for field, value in claims],
                "untrusted_path_only": not claims and not seed,
            })
            for field, expected in claims:
                if expected != actual:
                    counts["declared_hash_mismatch_count"] += 1
                    diagnostic("DECLARED_HASH_MISMATCH", path=relative, manifest=manifest, pointer=pointer,
                               hash_field=field, declared_sha256=expected, actual_sha256=actual)
            if seed or (matched_pin and Path(relative).suffix.lower() == ".json"):
                enqueue(relative)

    def walk(value: Any, manifest: str, pointer: str = "") -> None:
        if isinstance(value, dict):
            path = value.get("path")
            claims = [(field, _hash_value(value[field])) for field in _HASH_FIELDS
                      if field in value and _hash_value(value[field]) is not None]
            if isinstance(path, str):
                reference(path, manifest, _pointer(pointer, "path"), claims, explicit=True)
            for key in sorted(value):
                item = value[key]
                child = _pointer(pointer, key)
                expected = _hash_value(item)
                if expected is not None:
                    # Explicit path -> hash maps (including freeze member maps).
                    # A hash-valued metadata field is not itself a file path.
                    if key not in _HASH_FIELDS and (
                            "/" in key or "\\" in key or bool(Path(key).suffix)
                            or bool(safe_candidates(key, manifest)[0])):
                        reference(key, manifest, child, [("path_map_value", expected)], explicit=True)
                elif key != "path":
                    walk(item, manifest, child)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, manifest, _pointer(pointer, index))
        elif isinstance(value, str):
            # A path string is only interesting when it concretely names a file.
            # safe_candidates performs no directory/basename search.
            reference(value, manifest, pointer, [], explicit=False)

    for manifest in sorted(set(manifest_paths)):
        reference(manifest, None, "", [], explicit=True, seed=True)
    while pending:
        relative = pending.popleft()
        queued.discard(relative)
        if relative in visited:
            continue
        if len(visited) >= max_manifests:
            counts["manifest_limit_count"] += 1
            diagnostic("MANIFEST_COUNT_LIMIT_REACHED", path=relative)
            continue
        visited.add(relative)
        metadata = candidates[relative]
        if metadata["bytes"] > max_manifest_bytes:
            counts["manifest_limit_count"] += 1
            diagnostic("MANIFEST_BYTE_LIMIT_REACHED", path=relative, bytes=metadata["bytes"])
            continue
        if counts["manifest_bytes_read"] + metadata["bytes"] > max_total_manifest_bytes:
            counts["manifest_limit_count"] += 1
            diagnostic("MANIFEST_TOTAL_BYTE_LIMIT_REACHED", path=relative)
            continue
        try:
            path = repository_path(root, relative)
            with path.open("rb") as stream:
                raw = stream.read(max_manifest_bytes + 1)
            counts["manifest_bytes_read"] += len(raw)
            if len(raw) > max_manifest_bytes:
                raise ValueError("manifest grew past its byte bound")
            if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
                invalidated.add(relative)
                diagnostic("MANIFEST_CHANGED_DURING_RESOLUTION", path=relative)
                continue
            payload = safe_json(raw)
        except (ValueError, OSError, RuntimeError, RecursionError):
            diagnostic("MANIFEST_UNREADABLE_OR_INVALID_JSON", path=relative)
            continue
        manifest_bindings.append({"path": relative, "sha256": metadata["sha256"],
                                  "role": "source_catalog_manifest"})
        counts["manifests_parsed"] += 1
        try:
            walk(payload, relative)
        except RecursionError:
            diagnostic("MANIFEST_NESTING_LIMIT_REACHED", path=relative)

    sources = [{"path": path, "sha256": row["sha256"], "role": "exact_cited_source_bytes"}
               for path, row in sorted(candidates.items())
               if row["sha256"] in wanted and path not in invalidated]
    resolved = {row["sha256"] for row in sources}
    # Repeated references remain provenance, not an extra source or inventory ID.
    provenance = sorted({canonical(row): row for row in provenance}.values(), key=canonical)
    diagnostics = sorted({canonical(row): row for row in diagnostics}.values(), key=canonical)
    metrics = {key: counts[key] for key in (
        "candidate_reference_count", "files_hashed", "bytes_hashed", "manifests_parsed",
        "manifest_bytes_read", "declared_hash_mismatch_count", "unavailable_path_count",
        "rejected_path_count", "manifest_limit_count", "candidate_limit_count")}
    metrics.update(wanted_hash_count=len(wanted), resolved_hash_count=len(resolved),
                   unresolved_hash_count=len(wanted - resolved), verified_source_path_count=len(sources),
                   visited_manifest_count=len(visited))
    return {
        "sources": sources, "unresolved_hashes": sorted(wanted - resolved),
        "candidate_provenance": provenance, "manifest_bindings": sorted(manifest_bindings, key=lambda row: row["path"]),
        "diagnostics": diagnostics, "metrics": metrics,
        "all_wanted_hashes_resolved": wanted <= resolved,
        "verification_scope": "actual_local_file_bytes_only_not_source_meaning_or_acceptance",
        "source_inventory_mutated": False, "accepted_for_reference": False,
    }
