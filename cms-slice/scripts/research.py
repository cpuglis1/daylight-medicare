#!/usr/bin/env python3
"""Build and serve a bounded, local-only, read-only Naples research snapshot."""

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import cms_slice as cms
import validate_naples as validation
import prescription
import reference_evidence

ROOT = cms.ROOT
REPORTS = ROOT / "reports/work-package-2"
DIST = ROOT / "apps/research/dist"
LABELS = {
    "part_c_premium": "Published medical plan premium",
    "part_d_basic_premium": "Published basic drug-premium component",
    "part_d_supplemental_premium": "Published supplemental drug-premium component",
    "part_d_total_premium": "Published drug plan premium",
    "consolidated_premium": "Published medical + drug plan premium",
    "annual_part_d_deductible": "Annual Part D deductible",
    "in_network_medical_moop": "In-network medical spending limit",
}


def option_id(record):
    key = record["identity"]
    return f"{key['contract']}-{key['plan']}-{key['segment_join']}-{key['year']}"


def project(catalog, report):
    samples = {f"{s['identity']['contract']}-{s['identity']['plan']}-{s['identity']['segment_join']}-{s['identity']['year']}": s for s in report["samples"]}

    def record_view(record, excluded):
        oid = option_id(record)
        sample = samples.get(oid)
        view = {
            "id": oid, "name": record["landscape_raw"]["Plan Name"], "identity": record["identity"],
            "category": record["landscape_raw"]["Contract Category Type"], "plan_type": record["landscape_raw"]["Plan Type"],
            "source_geography": record["source_geography"], "exclusion_reasons": record.get("exclusion_reasons", []),
            "facts": record.get("facts", {}), "open_checks": record["open_checks"],
            "source": record["landscape_evidence"], "pbp": record["pbp"], "landscape_raw": record["landscape_raw"],
            "carrier_sample": {"sampled": sample is not None,
                               "checks": sample["money_checks"] if sample else [],
                               "scope": "Specific monetary fields only; not full-plan, eligibility, suitability or purchase verification"},
            "comparison_available": not excluded,
        }
        if not excluded:
            field = {"MA": "part_c_premium", "MA-PD": "consolidated_premium", "PDP": "part_d_total_premium"}[view["category"]]
            view["plan_premium"] = {"field": field, "label": LABELS[field], "fact": view["facts"][field]}
        return view

    options = [record_view(r, False) for r in catalog["options"]]
    exclusions = [record_view(r, True) for r in catalog["exclusions"]]
    return {
        "snapshot_id": "naples-read-" + cms.sha256(json.dumps(catalog, sort_keys=True).encode())[:16],
        "release_id": catalog["release_id"], "benefit_year": catalog["benefit_year"],
        "market": {k: catalog["market"][k] for k in ("county_fips", "state", "census_name", "requested_place")},
        "counts": catalog["counts"], "order": catalog["order"], "scope": catalog["scope"],
        "limitations": catalog["limitations"], "validation_counts": report["counts"], "field_labels": LABELS,
        "status": "local_research_preview; no personalized ranking or purchase",
        "source_data_updated": cms.Sources().manifest["landscape_data_last_updated"],
        "sources": {name: {"url": spec["url"], "sha256": spec["sha256"]} for name, spec in cms.Sources().manifest["artifacts"].items()},
        "options": options, "exclusions": exclusions,
    }


def build(out=REPORTS):
    sources = cms.Sources()
    cms.verify_report(sources, ROOT / "reports/work-package-1")
    config = cms.load_json(validation.CONFIG)
    catalog = cms.load_json(ROOT / "reports/work-package-1/market-12021-2027.json")
    report = validation.validate(config, catalog)
    if report["counts"]["monetary_conflicts"]:
        raise cms.SourceError("Carrier sample conflicts require review before building this comparison snapshot")
    snapshot = project(catalog, report)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temporary:
        staging = Path(temporary)
        cms.write_json(staging / "validation.json", report)
        cms.write_json(staging / "catalog.json", snapshot)
        manifest = {
            "purpose": "File-backed Naples read model; no private records, database migration or consumer-launch approval",
            "code_sha256": {str(Path(p).relative_to(ROOT)): cms.file_hash(p) for p in (Path(__file__), Path(validation.__file__), DIST / "index.html", DIST / "app.js", DIST / "styles.css")},
            "configuration_sha256": {str(validation.CONFIG.relative_to(ROOT)): cms.file_hash(validation.CONFIG)},
            "upstream_sha256": {"reports/work-package-1/run-manifest.json": cms.file_hash(ROOT / "reports/work-package-1/run-manifest.json"),
                                "reports/work-package-1/market-12021-2027.json": cms.file_hash(ROOT / "reports/work-package-1/market-12021-2027.json")},
            "outputs_sha256": {p.name: cms.file_hash(p) for p in sorted(staging.iterdir())},
        }
        cms.write_json(staging / "read-manifest.json", manifest)
        out.mkdir(parents=True, exist_ok=True)
        for p in sorted(staging.iterdir(), key=lambda p: p.name == "read-manifest.json"):
            os.replace(p, out / p.name)
    return snapshot


class ReadModel:
    def __init__(self, reports=REPORTS):
        reports = Path(reports)
        # Pin startup to the exact upstream release, source bytes, code and generated snapshot.
        with contextlib.redirect_stdout(io.StringIO()):
            cms.verify_report(cms.Sources(), ROOT / "reports/work-package-1")
        manifest = cms.load_json(reports / "read-manifest.json")
        for group in ("code_sha256", "configuration_sha256", "upstream_sha256"):
            for name, digest in manifest[group].items():
                if cms.file_hash(ROOT / name) != digest:
                    raise cms.SourceError(f"Read model input changed: {name}; rebuild and review")
        for name, digest in manifest["outputs_sha256"].items():
            if cms.file_hash(reports / name) != digest:
                raise cms.SourceError(f"Read model output changed: {name}")
        validation.verify_inputs(cms.load_json(validation.CONFIG))
        self._data = cms.load_json(reports / "catalog.json")
        self._by_id = {r["id"]: r for r in self._data["options"] + self._data["exclusions"]}

    def catalog(self, year, county):
        if year != self._data["benefit_year"] or county != self._data["market"]["county_fips"]:
            raise cms.SourceError("This read view supports only benefit year 2027 and Collier County 12021")
        return self._data

    def option(self, reference):
        if reference not in self._by_id:
            raise cms.SourceError("Option is outside this snapshot")
        return self._by_id[reference]

    def compare(self, references):
        if not 1 <= len(references) <= 3 or len(set(references)) != len(references):
            raise cms.SourceError("Choose one to three distinct records")
        for reference in references:
            if not self.option(reference)["comparison_available"]:
                raise cms.SourceError("An excluded source record can be inspected but is outside the comparison scope")
        # A consumer-selected comparison remains a view of source order, never an independent ranking.
        return {"snapshot_id": self._data["snapshot_id"], "order": self._data["order"],
                "options": [r for r in self._data["options"] if r["id"] in references], "field_labels": LABELS}


class PrescriptionModel:
    def __init__(self):
        self.config = cms.load_json(prescription.CONFIG)
        self.report = prescription.verify(self.config)
        self.manifest = cms.load_json(prescription.REPORTS / "manifest.json")
        reference_config = cms.load_json(reference_evidence.CONFIG)
        self.references = reference_evidence.verify(reference_config)
        pharmacies = cms.load_json(ROOT / reference_config["artifacts"]["npi_pharmacy_city_query"]["path"])
        candidates = [p for p in pharmacies["results"] if str(p["number"]) == "1609197854"]
        if len(candidates) != 1 or len(reference_evidence.locations(candidates[0])) != 1:
            raise cms.SourceError("Inspected pharmacy example is missing/ambiguous")
        self.pharmacy = {"npi": "1609197854", "organization": candidates[0]["basic"]["organization_name"],
                         "location": reference_evidence.locations(candidates[0])[0]["raw"],
                         "status": "public registry identity; current store operation unverified"}

    def context(self):
        return {"release_id": self.config["release_id"], "benefit_year": "2027", "county_fips": "12021",
                "plans": [{"id": row["id"], "name": row["selected_plan"]["raw"]["PLAN_NAME"]} for row in self.report["joins"] if row["comparison_scope"] and row["selected_plan"]],
                "medicine_example": self.references["vocabulary"]["brand_search"], "pharmacy_example": self.pharmacy,
                "nlm_attribution": self.references["vocabulary"]["nlm_attribution"], "date_discrepancy": self.config["date_discrepancy"],
                "status": "public evidence example; no personal medicine or pharmacy has been confirmed"}

    def lookup(self, plan, ndc=None, rxcui=None, npi=None):
        # Read captures only after verifying their startup-pinned hashes; a concurrent rebuild/tamper fails closed.
        matches = [row for row in self.report["joins"] if row["id"] == plan]
        if len(matches) != 1:
            raise cms.SourceError("Plan outside the pinned Collier snapshot")
        selected = matches[0]["selected_plan"]
        applicable = selected is not None and selected["raw"]["PLAN_SUPPRESSED_YN"] == "N"
        names = ["formulary.psv.gz", "beneficiary.psv.gz", "excluded.psv.gz", "indication.psv.gz", "insulin.psv.gz"] if applicable else []
        if npi is not None and applicable:
            names.append(plan + "-pharmacy.psv.gz")
        for name in names:
            if name not in self.manifest["cache_sha256"] or cms.file_hash(prescription.CACHE / name) != self.manifest["cache_sha256"][name]:
                raise cms.SourceError("Prescription capture unavailable/changed; rebuild and review")
        result = prescription.query(self.config, self.report, plan, ndc, rxcui, npi)
        result["carrier_product_example"] = self.references["carrier_sample"] if (rxcui == "1551300" or ndc == "00002143380") and plan in self.references["carrier_sample"]["plan_ids"] else None
        result["carrier_formulary_url"] = self.references["artifacts"]["carrier_formulary"]["url"] if result["carrier_product_example"] else None
        return result


def make_server(model, port=8765, prescription_model=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, body, mime="application/json; charset=utf-8"):
            raw = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) + "\n").encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed_hosts:
                return self.respond(403, {"error": "Local host only"})
            target = urlsplit(self.path)
            params = parse_qs(target.query, keep_blank_values=True)
            try:
                if any(len(v) != 1 for v in params.values()):
                    raise cms.SourceError("Duplicate query argument")
                if target.path == "/api/catalog":
                    if set(params) != {"year", "county_fips"}:
                        raise cms.SourceError("Specify exact year and county_fips")
                    return self.respond(200, model.catalog(params["year"][0], params["county_fips"][0]))
                if target.path == "/api/compare":
                    if set(params) != {"ids"}:
                        raise cms.SourceError("Specify ids only; no ranking preferences are accepted")
                    return self.respond(200, model.compare(params["ids"][0].split(",")))
                if target.path in {"/api/prescription/context", "/api/prescription/lookup"}:
                    if prescription_model is None:
                        return self.respond(503, {"error": "Prescription evidence is not loaded"})
                    if target.path.endswith("/context"):
                        if params:
                            raise cms.SourceError("Prescription context accepts no arguments")
                        return self.respond(200, prescription_model.context())
                    if not {"plan_id"} <= set(params) or not set(params) <= {"plan_id", "ndc11", "rxcui", "pharmacy_npi"}:
                        raise cms.SourceError("Specify exact plan_id and one ndc11/rxcui; optional pharmacy_npi only")
                    return self.respond(200, prescription_model.lookup(params["plan_id"][0], params.get("ndc11", [None])[0], params.get("rxcui", [None])[0], params.get("pharmacy_npi", [None])[0]))
                if re.fullmatch(r"/api/options/[A-Z]\d{4}-\d{3}-\d{3}-\d{4}", target.path):
                    if params:
                        raise cms.SourceError("Unexpected option arguments")
                    return self.respond(200, model.option(target.path.rsplit("/", 1)[1]))
                assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8")}
                if target.path in assets and not params:
                    name, mime = assets[target.path]
                    return self.respond(200, (DIST / name).read_bytes(), mime)
                return self.respond(404, {"error": "No such read-only resource"})
            except cms.SourceError as error:
                return self.respond(422, {"error": str(error)})

        def reject_write(self):
            self.respond(405, {"error": "Read-only preview; mutations and submission are unavailable"})

        do_POST = do_PUT = do_PATCH = do_DELETE = reject_write

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "serve", "verify"])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "build":
            snapshot = build()
            print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "counts": snapshot["counts"], "validation": snapshot["validation_counts"]}, indent=2))
        elif args.command == "verify":
            ReadModel()
            print("Verified local read model, source artifacts and carrier-validation artifacts")
        else:
            server = make_server(ReadModel(), args.port, PrescriptionModel() if (prescription.REPORTS / "manifest.json").exists() else None)
            print(f"Local: http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (cms.SourceError, OSError, KeyError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
