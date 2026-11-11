"""Pinned r9 replay and exact, source-bound mapping selection.

An outcome here checks stored meaning. It is never source interpretation,
whole-original completion, reference acceptance or personal applicability.
"""
from __future__ import annotations

import importlib.metadata
import hashlib
import sys
import threading
import decimal
from pathlib import Path
from types import ModuleType

from .common import digest, file_hash

R9 = Path("docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9")
PINNED = {
    "code/l03_comparison_contract.py": "a5440048e43f53447f46fd51c17a91422d34c8fd415b5ebf06c66a1e78108d47",
    "code/l03_r9_comparison.py": "0bd222621e4ede985505b7a70ba9f11a8dcf738ea66065ea7cc0bfb925414994",
    "comparison-record.schema.json": "37e66820165e819baf6113955c54e727615e440ad655ac8fbea1ef519740140d",
}
SUPPORTED = {"exact_agreement", "agreement_through_reviewed_mapping",
             "supported_carrier_statement", "documented_inapplicability"}
_IMPORT_LOCK = threading.Lock()


def load_engine(repository: Path):
    verified_bytes = {}
    for relative, expected in PINNED.items():
        path = repository / R9 / relative
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Sealed r9 rule changed; new revision and review required: {relative}")
        verified_bytes[relative] = raw

    def module(name, relative):
        result = ModuleType(name)
        result.__file__ = str(repository / R9 / relative)
        # Execute exactly the hashed bytes, never timestamp-based Python caches.
        exec(compile(verified_bytes[relative], result.__file__, "exec"), result.__dict__)
        return result

    with _IMPORT_LOCK:
        previous = sys.modules.get("l03_comparison_contract")
        try:
            base = module("_daylight_pipeline_r9_base", "code/l03_comparison_contract.py")
            sys.modules["l03_comparison_contract"] = base
            return module("_daylight_pipeline_r9_guard", "code/l03_r9_comparison.py")
        finally:
            if previous is None:
                sys.modules.pop("l03_comparison_contract", None)
            else:
                sys.modules["l03_comparison_contract"] = previous


def rule_fingerprint(repository: Path) -> str:
    local = {path.name: file_hash(path) for path in Path(__file__).parent.glob("*.py")}
    dependencies = {name: importlib.metadata.version(name) for name in (
        "jsonschema", "jsonschema-specifications", "referencing", "attrs", "rpds-py")}
    return digest({"sealed_r9": PINNED, "pipeline": local,
                   "dependencies": dependencies, "python": list(sys.version_info[:3]),
                   "decimal": decimal.__libmpdec_version__})


def select_mapping(component, registries, verified_sources):
    """No amount, alias or cross-plan matching: the entire observation pair binds.

    A registry cannot self-authorize by placing an arbitrary receipt hash in a
    row. The actual receipt bytes must also be among the verified dependencies.
    Optional exact-record and evidence-path bindings are enforced when present.
    """
    cms, carrier = component.get("cms"), component.get("carrier")
    cms_hash, carrier_hash = digest(cms), digest(carrier)
    matches = []
    for key, entry in registries.items():
        if entry.get("cms_sha256") != cms_hash or entry.get("carrier_sha256") != carrier_hash:
            continue
        if entry.get("review_decision") != "accepted_mapping" or not entry.get("reviewer") or not entry.get("evidence"):
            raise ValueError("Matching mapping lacks its source review")
        receipt = entry.get("review_receipt_sha256")
        if not any(source["sha256"] == receipt for source in verified_sources):
            raise ValueError("Matching mapping receipt is not byte-bound")
        proof = entry["evidence"]
        if isinstance(proof, dict):
            if proof.get("formal_record_id", component["id"]) != component["id"]:
                raise ValueError("Mapping belongs to another comparison")
            if proof.get("formal_record_sha256", digest(component)) != digest(component):
                raise ValueError("Mapping exact-record fingerprint drift")
            for field, relative in proof.items():
                if field.endswith("_path") and isinstance(relative, str):
                    expected = proof.get(field[:-5] + "_sha256")
                    if expected is not None and not any(
                            s["path"] == relative and s["sha256"] == expected for s in verified_sources):
                        raise ValueError("Mapping evidence path is not byte-bound")
        matches.append((key, entry))
    if len(matches) > 1:
        raise ValueError("Ambiguous exact mapping registry")
    return matches[0] if matches else (None, None)


def evaluate(engine, task, mappings):
    results = []
    for component in task["components"]:
        mapping_id, entry = mappings.get(component["id"], (None, None))
        kwargs = {"mapping": mapping_id, "mapping_registry": {mapping_id: entry}} if entry else {}
        actual = engine.compare(component.get("cms"), component.get("carrier"), **kwargs)
        if actual.get("accepted_for_reference") is not False:
            raise ValueError("Mechanical comparator crossed its acceptance boundary")
        results.append({"component_id": component["id"], **actual})
    return results
