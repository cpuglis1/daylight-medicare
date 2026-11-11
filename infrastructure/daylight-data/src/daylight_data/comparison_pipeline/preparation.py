"""Prepare pinned comparison catalogs without making source-meaning decisions.

The public ``prepare_batch`` accepts repository-relative, byte-pinned catalogs
and publishes a new runner-compatible batch directory. JSON is one record or a
record array; JSONL has one record per nonblank line. Either may be gzip wrapped.
Only valid strict-r9 records with the SAME offering and complete original-ID set
are optionally bundled. Components, their order and all original fields survive.
Other registered artifact families pass through unchanged and are never bundled.
Invalid object records stay separate for runner quarantine, with diagnostics in
the provenance report. Duplicate identities and scope conflicts fail closed.

Preparation never infers equivalence, complete parent coverage, review, source
acceptance or release. Original catalogs remain globally pinned provenance,
rather than being replaced by the derived transport artifacts. A container byte
change does not make every unchanged component a new semantic evaluation.
"""
from __future__ import annotations

import ctypes
import errno
import gzip
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

from .adapters import ADAPTER_REGISTRY, normalize_task
from .common import canonical, digest, file_hash, repository_path, safe_json

PREPARATION_SCHEMA = "daylight-comparison-preparation/1"
BATCH_SCHEMA = "daylight-comparison-batch/1"
_ALGORITHM = "strict-r9-catalog-preparation/1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class PreparationError(ValueError):
    """An input, scope or publication binding cannot be preserved safely."""


def _pin(repository: Path, entry: dict) -> tuple[Path, dict]:
    if type(entry) is not dict or not {"path", "sha256"} <= entry.keys():
        raise PreparationError("Every input requires a repository path and byte SHA256")
    if type(entry["sha256"]) is not str or not _SHA.fullmatch(entry["sha256"]):
        raise PreparationError("Input SHA256 must be 64 lowercase hexadecimal characters")
    path = repository_path(repository, entry["path"])
    if not path.is_file() or file_hash(path) != entry["sha256"]:
        raise PreparationError(f"Artifact byte binding changed: {entry['path']}")
    return path, dict(entry)


def _records(path: Path):
    """Yield exact JSON values and source positions, never guesses at wrappers."""
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as stream:
        if path.name.endswith((".jsonl", ".jsonl.gz")):
            ordinal = 0
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    ordinal += 1
                    yield safe_json(line, exact_decimals=True), {
                        "record_ordinal": ordinal, "line_number": line_number}
        else:
            value = safe_json(stream.read(), exact_decimals=True)
            if type(value) is list:
                for index, record in enumerate(value):
                    yield record, {"record_ordinal": index + 1, "json_pointer": f"/{index}"}
            else:
                yield value, {"record_ordinal": 1, "json_pointer": ""}


def _scope(raw: dict, offering: str) -> None:
    # Inspect explicit identities BEFORE schema validation. A malformed record
    # may be quarantined, but cannot conceal a complete foreign source identity.
    if "offering_id" in raw and raw["offering_id"] != offering:
        raise PreparationError("Offering scope mismatch in catalog record")
    for side in ("cms", "carrier"):
        observation = raw.get(side)
        identity = observation.get("identity") if type(observation) is dict else None
        fields = ("year", "contract", "plan", "segment")
        if type(identity) is dict and all(k in identity for k in fields):
            if all(type(identity[k]) in (str, int) for k in fields):
                actual = ":".join(str(identity[k]) for k in fields)
                if actual != offering:
                    raise PreparationError(f"Offering scope mismatch in {side} identity: {actual}")
    for key in ("inventory_root_ids", "original_ids"):
        roots = raw.get(key)
        if type(roots) is list and all(type(r) is str for r in roots) and len(roots) != len(set(roots)):
            raise PreparationError("Duplicate original IDs in catalog record")
    if raw.get("artifact_type") == "r9_component_bundle" and type(raw.get("components")) is list:
        for component in raw["components"]:
            if type(component) is dict:
                _scope(component, offering)


def _source_id(raw: dict) -> str:
    identifier = raw.get("id")
    return identifier if type(identifier) is str and identifier.strip() else "INVALID-" + digest(raw)


def _bundle_id(identity: dict, roots: list[str]) -> str:
    # Content hashes are deliberately NOT identity: changed conditions invalidate
    # evaluation, while the same selected original group remains the same task.
    return "prepared-r9-bundle-" + digest({"algorithm": _ALGORITHM,
        "catalog_identity": identity, "original_ids": roots})


def _write_json(path: Path, value) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_records(path: Path, records: list[dict]) -> None:
    with path.open("xb") as raw:
        # No temporary filename or wall clock leaks into gzip output identity.
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            for record in records:
                stream.write(canonical(record) + b"\n")
        raw.flush()
        os.fsync(raw.fileno())


def _publish(staging: Path, output: Path) -> None:
    """Atomic directory publication with no replacement, including empty dirs.

    POSIX rename() alone would overwrite an empty destination created after the
    initial existence check. Use the operating system's exclusive rename flag.
    All APIs here are standard-library bindings to the local filesystem only.
    """
    if os.name == "nt":
        os.rename(staging, output)  # Windows rename refuses an existing target.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = getattr(libc, "renamex_np", None)
        arguments = (os.fsencode(staging), os.fsencode(output), 4)  # RENAME_EXCL
        if rename is not None:
            rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    else:
        rename = getattr(libc, "renameat2", None)
        arguments = (-100, os.fsencode(staging), -100, os.fsencode(output), 1)  # NOREPLACE
        if rename is not None:
            rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    if rename is None:
        raise PreparationError("This platform lacks an atomic no-replacement directory rename")
    rename.restype = ctypes.c_int
    if rename(*arguments) != 0:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise PreparationError("Preparation destination already exists")
        raise OSError(error, os.strerror(error), str(output))


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def prepare_batch(repository: Path, spec: dict, output: Path) -> dict:
    """Publish a new pinned batch and return its paths, counts and byte bindings.

    ``spec`` requires unique ``offerings`` and ``catalogs`` with path, SHA256,
    offering_id and optional literal-bool bundle_by_original_ids. Optional catalog
    dependency_paths names substantive context sources, not input containers.
    ``sources``,
    ``mapping_registries`` and ``source_reviews`` are byte-verified and passed
    through; optional title/metadata are retained in the provenance report.
    Relative output paths are relative to repository. No existing target is
    overwritten, even on failure or a concurrent publication attempt.
    """
    started = time.perf_counter()
    repository = Path(repository).resolve(strict=True)
    if not repository.is_dir():
        raise PreparationError("Repository must be a directory")
    # Also rejects NaN, non-JSON values and duplicate/nonfinite JSON transports.
    spec = safe_json(canonical(spec), exact_decimals=True)
    allowed = {"offerings", "catalogs", "sources", "mapping_registries", "source_reviews", "title", "metadata"}
    if type(spec) is not dict or set(spec) - allowed:
        raise PreparationError("Unsupported preparation specification")
    offerings = spec.get("offerings")
    if (type(offerings) is not list or not offerings or
            any(type(o) is not str or not o.strip() for o in offerings) or len(set(offerings)) != len(offerings)):
        raise PreparationError("Preparation requires unique exact offering identities")
    catalogs = spec.get("catalogs")
    if type(catalogs) is not list or not catalogs:
        raise PreparationError("Preparation requires at least one catalog")
    for key in ("sources", "mapping_registries", "source_reviews"):
        if type(spec.get(key, [])) is not list:
            raise PreparationError(f"{key} must be a list of pinned artifacts")
    output = Path(output)
    requested_output = output if output.is_absolute() else repository / output
    if os.path.lexists(requested_output):
        raise PreparationError("Preparation destination already exists")
    output = repository_path(repository, str(output)) if not output.is_absolute() else output.resolve()
    if not output.is_relative_to(repository) or output == repository:
        raise PreparationError("Preparation output must be a new directory under the repository")
    if os.path.lexists(output):
        raise PreparationError("Preparation destination already exists")

    verified, catalog_inputs, catalog_paths = {}, [], set()
    for entry in catalogs:
        if type(entry) is not dict or set(entry) - {"path", "sha256", "offering_id", "bundle_by_original_ids", "dependency_paths", "metadata"}:
            raise PreparationError("Unsupported catalog configuration")
        if entry.get("offering_id") not in offerings:
            raise PreparationError("Catalog offering is outside the preparation scope")
        if type(entry.get("bundle_by_original_ids", False)) is not bool:
            raise PreparationError("bundle_by_original_ids must be a literal boolean")
        dependencies = entry.get("dependency_paths", [])
        if type(dependencies) is not list or any(type(p) is not str or not p for p in dependencies):
            raise PreparationError("Catalog dependency_paths must be a list of substantive source paths")
        if len(dependencies) != len(set(dependencies)):
            raise PreparationError("Duplicate catalog dependency path")
        path, bound = _pin(repository, entry)
        if not path.name.endswith((".json", ".json.gz", ".jsonl", ".jsonl.gz")):
            raise PreparationError("Catalog must be JSON or JSONL, optionally gzip compressed")
        identity = {"path": path.relative_to(repository).as_posix(), "offering_id": entry["offering_id"]}
        key = (identity["path"], identity["offering_id"])
        if key in catalog_paths:
            raise PreparationError("Duplicate catalog selection")
        catalog_paths.add(key)
        catalog_inputs.append((path, bound, identity))
        if entry["path"] in verified and verified[entry["path"]] != bound["sha256"]:
            raise PreparationError("Conflicting artifact byte bindings")
        verified[entry["path"]] = bound["sha256"]
    for key in ("sources", "mapping_registries", "source_reviews"):
        for entry in spec.get(key, []):
            pin = entry
            if "member" in entry:
                if key != "sources":
                    raise PreparationError("Archive-member bindings are source dependencies only")
                from .runner import verify_binding
                verify_binding(repository, entry)
                # The complete ZIP bytes bind the member through publication;
                # keep the full member descriptor in the manifest/provenance.
                pin = {**entry, "sha256": entry["archive_sha256"]}
            path, bound = _pin(repository, pin)
            if entry["path"] in verified and verified[entry["path"]] != bound["sha256"]:
                raise PreparationError("Conflicting artifact byte bindings")
            verified[entry["path"]] = bound["sha256"]
            if key != "sources":
                # Their roles/decisions pass through; parsing grants no review.
                list(_records(path))
    source_paths = {s["path"] for s in spec.get("sources", [])}
    for _, entry, _ in catalog_inputs:
        if set(entry.get("dependency_paths", [])) - source_paths:
            raise PreparationError("Catalog dependency is absent from the pinned substantive sources")

    prepared, lineage, seen, emitted = [], [], set(), set()
    quarantined = components = bundles = 0
    for path, entry, identity in catalog_inputs:
        offering = entry["offering_id"]
        rows, groups, records = [], {}, []
        for raw, position in _records(path):
            if type(raw) is not dict:
                raise PreparationError(f"Catalog record must be an object: {entry['path']} {position}")
            kind = raw.get("artifact_type", "strict_r9")
            registered = type(kind) is str and kind in ADAPTER_REGISTRY
            _scope(raw, offering)
            identifier = _source_id(raw)
            key = (offering, identifier)
            if key in seen:
                raise PreparationError(f"Duplicate catalog comparison identity: {identifier}")
            seen.add(key)
            error = None
            try:
                normalize_task(raw, offering_id=offering)
            except ValueError as exc:
                if str(exc).split(" at ", 1)[0] in {
                        "strict_validator_unavailable", "sealed_authority_unavailable", "sealed_authority_changed"}:
                    raise PreparationError(f"Preparation authority unavailable: {exc}") from exc
                error = str(exc)
            item = {"catalog": dict(entry), "catalog_identity": identity,
                    **position, "record_id": raw.get("id"), "record_sha256": digest(raw),
                    "artifact_type": kind,
                    "normalization": ("quarantine_pending" if error else
                                      "strict_r9_valid" if kind == "strict_r9" else "registered_artifact_valid"),
                    "normalization_error": error}
            rows.append(item)
            if error:
                quarantined += 1
            roots = raw.get("inventory_root_ids")
            groupable = (registered and kind == "strict_r9" and not error and
                         type(roots) is list and bool(roots) and all(type(r) is str for r in roots))
            if entry.get("bundle_by_original_ids", False) and groupable:
                group = tuple(sorted(roots))
                if group not in groups:
                    envelope = {"artifact_type": "r9_component_bundle", "id": _bundle_id(identity, list(group)),
                                "offering_id": offering, "original_ids": list(group), "components": []}
                    groups[group] = envelope
                    records.append(envelope)
                    bundles += 1
                envelope = groups[group]
                item.update(output_record_id=envelope["id"], component_index=len(envelope["components"]))
                envelope["components"].append(raw)
            else:
                records.append(raw)
                item.update(output_record_id=identifier, component_index=None)
            components += 1
        for record in records:
            key = (offering, _source_id(record))
            if key in emitted:
                raise PreparationError(f"Duplicate prepared task identity: {key[1]}")
            emitted.add(key)
        prepared.append((entry, records))
        lineage.extend(rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    # Resolve again after parent creation; existing symlinks must still be bounded.
    if output.parent.resolve() != output.parent or not output.parent.is_relative_to(repository):
        raise PreparationError("Preparation output parent changed")
    staging = Path(tempfile.mkdtemp(prefix=".comparison-prepare-", dir=output.parent))
    try:
        (staging / "inputs").mkdir()
        sources = [dict(s) for s in spec.get("sources", [])]
        for _, entry, _ in catalog_inputs:
            sources.append({"path": entry["path"], "sha256": entry["sha256"], "role": "comparison_catalog_provenance"})
        manifest = {"schema": BATCH_SCHEMA, "offerings": offerings, "inputs": [], "sources": sources,
                    "mapping_registries": spec.get("mapping_registries", []), "source_reviews": spec.get("source_reviews", [])}
        if "title" in spec:
            manifest["title"] = spec["title"]
        for index, (entry, records) in enumerate(prepared):
            relative = f"inputs/catalog-{index:04d}.jsonl.gz"
            _write_records(staging / relative, records)
            manifest["inputs"].append({"path": (output / relative).relative_to(repository).as_posix(),
                "sha256": file_hash(staging / relative), "offering_id": entry["offering_id"],
                "dependency_paths": entry.get("dependency_paths", [])})
        provenance = {"schema": PREPARATION_SCHEMA, "algorithm": _ALGORITHM, "spec": spec,
            "implementation_sha256": file_hash(Path(__file__)),
            "spec_sha256": digest(spec), "records": lineage, "input_byte_bindings": verified,
            "catalog_record_count": components, "prepared_task_count": len(emitted),
            "bundle_count": bundles, "quarantine_pending_count": quarantined,
            "semantic_completeness_inferred": False, "research_only": True,
            "accepted_for_reference": False, "consumer_usable": False}
        _write_json(staging / "preparation-provenance.json", provenance)
        _write_json(staging / "batch-manifest.json", manifest)
        # Detect inputs changing during decoding or staging; never publish a batch
        # whose named dependencies no longer match its exact byte pins.
        for relative, expected in verified.items():
            if file_hash(repository_path(repository, relative)) != expected:
                raise PreparationError(f"Artifact byte binding changed during preparation: {relative}")
        _sync_directory(staging / "inputs")
        _sync_directory(staging)
        manifest_sha = file_hash(staging / "batch-manifest.json")
        provenance_sha = file_hash(staging / "preparation-provenance.json")
        _publish(staging, output)
        _sync_directory(output.parent)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"schema": PREPARATION_SCHEMA, "output": str(output),
        "manifest_path": (output / "batch-manifest.json").relative_to(repository).as_posix(),
        "manifest_sha256": manifest_sha,
        "provenance_path": (output / "preparation-provenance.json").relative_to(repository).as_posix(),
        "provenance_sha256": provenance_sha, "catalog_record_count": components,
        "prepared_task_count": len(emitted), "bundle_count": bundles,
        "quarantine_pending_count": quarantined, "offerings": offerings,
        "timings": {"total_seconds": time.perf_counter() - started},
        "research_only": True, "accepted_for_reference": False, "consumer_usable": False}
