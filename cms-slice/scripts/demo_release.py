#!/usr/bin/env python3
"""Build, verify, bundle and select an immutable, small, offline demo release."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

import cms_slice as cms
from evidence_store import PublicSources
from identity_lookup import IdentityLookup
from knowledge import Knowledge
import prescription as rx
import research

RELEASES = cms.ROOT / "releases"


def code_files():
    return sorted((cms.ROOT / "scripts").glob("*.py")) + sorted((cms.ROOT / "apps/chat").glob("*"))


def resolve(path):
    if str(path) == "current":
        return RELEASES / cms.load_json(RELEASES / "current.json")["release_id"]
    return Path(path).resolve()


def verify(path):
    path = resolve(path)
    manifest = cms.load_json(path / "manifest.json")
    expected_id = "naples-" + cms.sha256(json.dumps({k: manifest[k] for k in ("files_sha256", "code_sha256", "source_receipt")}, sort_keys=True).encode())[:20]
    if manifest["release_id"] != expected_id:
        raise cms.SourceError("Demo release manifest identity changed")
    for name, digest in manifest["files_sha256"].items():
        candidate = path / name
        if candidate.resolve().is_relative_to(path.resolve()) is False or cms.file_hash(candidate) != digest:
            raise cms.SourceError("Demo release file changed: " + name)
    for name, digest in manifest["code_sha256"].items():
        if cms.file_hash(cms.ROOT / name) != digest:
            raise cms.SourceError("Demo runtime changed since release; build a new release: " + name)
    return manifest


class FrozenReadModel:
    def __init__(self, data):
        self._data = data

    def catalog(self, year, county):
        if year != self._data["benefit_year"] or county != self._data["market"]["county_fips"]:
            raise cms.SourceError("This demo release supports only 2027 Collier County")
        return self._data


class FrozenKnowledge(Knowledge):
    def __init__(self, export):
        self.facts = export["facts"]
        self.version = export["version"]


class FrozenPrescription:
    def __init__(self, export, cache):
        self.config, self.report, self.manifest = export["config"], export["report"], export["manifest"]
        self.cache = cache

    def lookup(self, plan, ndc=None, rxcui=None, npi=None):
        return rx.query(self.config, self.report, plan, ndc, rxcui, npi, cache=self.cache)


def load(path):
    path = resolve(path)
    manifest = verify(path)
    public = PublicSources(path / "public-sources.json", path / "public")
    return {"model": FrozenReadModel(cms.load_json(path / "catalog.json")),
            "prescription_model": FrozenPrescription(cms.load_json(path / "prescription.json"), path / "captures"),
            "knowledge": FrozenKnowledge(cms.load_json(path / "knowledge.json")),
            "identities": IdentityLookup(public, allow_network=False), "release_manifest": manifest, "quality": cms.load_json(path / "quality.json"),
            "data_review": cms.load_json(path / "data-review.json")}


def build():
    # The portable query artifact is built only after full upstream/source verification.
    from demo_tools import DemoTools
    import carrier_quality
    import drug_validation
    import validate_devoted_drugs
    quality = carrier_quality.build()
    drug_sample = drug_validation.build()
    second_drug_sample = validate_devoted_drugs.build()
    tools = DemoTools()
    RELEASES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RELEASES, prefix="staging-") as directory:
        staging = Path(directory)
        cms.write_json(staging / "catalog.json", tools.snapshot)
        cms.write_json(staging / "knowledge.json", {"version": tools.knowledge.version, "facts": tools.knowledge.facts})
        needed = {"formulary.psv.gz", "beneficiary.psv.gz", "excluded.psv.gz", "indication.psv.gz", "insulin.psv.gz"}
        needed |= {p["id"] + "-pharmacy.psv.gz" for p in tools.snapshot["options"] if tools.joins[p["id"]]["selected_plan"]}
        (staging / "captures").mkdir()
        for name in sorted(needed):
            shutil.copy2(rx.CACHE / name, staging / "captures" / name)
            if cms.file_hash(staging / "captures" / name) != tools.rx.manifest["cache_sha256"][name]:
                raise cms.SourceError("Capture changed during release build")
        frozen_manifest = {**tools.rx.manifest, "cache_sha256": {name: tools.rx.manifest["cache_sha256"][name] for name in sorted(needed)}}
        cms.write_json(staging / "prescription.json", {"config": tools.rx.config, "report": tools.rx.report, "manifest": frozen_manifest})
        public = tools.identities.sources
        registry = {"version": 1, "sources": {}}
        (staging / "public").mkdir()
        for source_id in public.inventory()["sources"]:
            if source_id.startswith(("rxnorm-", "pharmacies-")):
                spec, raw = public.read(source_id)
                registry["sources"][source_id] = spec
                (staging / "public" / spec["sha256"]).write_bytes(raw)
        cms.write_json(staging / "public-sources.json", registry)
        cms.write_json(staging / "quality.json", quality)
        cms.write_json(staging / "drug-validation.json", drug_sample)
        cms.write_json(staging / "devoted-drug-validation.json", second_drug_sample)
        cms.write_json(staging / "data-review.json", tools.data_review)
        source_receipt = {"built_at_utc": datetime.now(timezone.utc).isoformat(), "upstream_full_source_verification": True,
                          "catalog_version": tools.snapshot["snapshot_id"], "source_archive_sha256": tools.rx.config["source"]["sha256"],
                          "knowledge_version": tools.knowledge.version, "carrier_records_checked": quality["carrier_records_checked"],
                          "carrier_parent_organizations_checked": quality["carrier_parent_organizations_checked"],
                          "drug_product_cases_checked": drug_sample["product_cases"],
                          "drug_sample_check_status_counts": drug_sample["check_status_counts"],
                          "second_carrier_drug_product_cases_checked": second_drug_sample["product_cases"],
                          "second_carrier_drug_check_status_counts": second_drug_sample["check_status_counts"],
                          "data_review_after_utc": tools.data_review["review_after_utc"],
                          "domain_signoff": "pending", "live_model_evaluation": "not_performed",
                          "scope": "Immutable derived evidence for facilitated factual research; not a quote, recommendation or consumer release approval"}
        files = {str(p.relative_to(staging)): cms.file_hash(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        code = {str(p.relative_to(cms.ROOT)): cms.file_hash(p) for p in code_files()}
        basis = {"files_sha256": files, "code_sha256": code, "source_receipt": source_receipt}
        release_id = "naples-" + cms.sha256(json.dumps(basis, sort_keys=True).encode())[:20]
        cms.write_json(staging / "manifest.json", {"release_id": release_id, **basis})
        destination = RELEASES / release_id
        if destination.exists():
            raise cms.SourceError("Release already exists; immutable snapshots are never overwritten")
        os.replace(staging, destination)
        # TemporaryDirectory may already have moved; cleanup accepts its absent original path.
    select(destination)
    return destination


def select(path):
    path = resolve(path)
    manifest = verify(path)
    if path.parent.resolve() != RELEASES.resolve() or path.name != manifest["release_id"]:
        raise cms.SourceError("Select a verified release inside the local releases directory")
    pointer = RELEASES / "current.json"
    temporary = RELEASES / "current.partial"
    cms.write_json(temporary, {"release_id": manifest["release_id"]})
    os.replace(temporary, pointer)


def bundle(path, out=None):
    path = resolve(path)
    manifest = verify(path)
    out = Path(out) if out else RELEASES / (manifest["release_id"] + ".tar.gz")
    if out.exists():
        raise cms.SourceError("Bundle exists; choose a new output instead of overwriting evidence")
    with tarfile.open(out, "w:gz") as archive:
        for source in code_files():
            archive.add(source, arcname=str(source.relative_to(cms.ROOT)), recursive=False)
        archive.add(path, arcname="snapshot")
        readme = b"Run: python3 scripts/demo.py serve --release snapshot\nOpen http://127.0.0.1:8766/\nOffline public-source demo. No model key or conversation data is included.\n"
        import io
        info = tarfile.TarInfo("START.txt"); info.size = len(readme)
        archive.addfile(info, io.BytesIO(readme))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify", "select", "bundle"])
    parser.add_argument("release", nargs="?", default="current")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "build":
            print(build())
        elif args.command == "bundle":
            print(bundle(args.release, args.out))
        elif args.command == "select":
            select(args.release); print("Verified release selected")
        else:
            print(json.dumps(verify(args.release)["source_receipt"], indent=2))
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        parser.exit(2, "Release unavailable: " + str(error) + "\n")


if __name__ == "__main__":
    main()
