"""Build an additive, offline L03 audit inventory; never promote source matches.

The frozen roots are source-native assertion bundles and explicit unknowns.
They are not a claim that semantic deduplication/interpretation has finished.
All scalar/empty-array CMS instances and all carrier text lines are accounted.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import re
import sqlite3

from l03_comparison_contract import CONDITION_FAMILIES, fingerprint

REPO = pathlib.Path(__file__).resolve().parents[2]
DATA = REPO / "docs/data/l03-ma-benefits-2026-10-25"
R1 = DATA / "build-r1"
R7 = DATA / "source-reconciliation-r7"
ROOT = DATA / "inventory-r8"
PACKAGE = "L03-INVENTORY-CONTRACT-COLLIER-2026-r8"
TECH = {"status", "statusCode", "lastUpdatedAt", "contractId", "planId", "segmentId",
        "contractYear", "section", "categoryCode", "categoryTypeId"}
TRIGGERS = {
    "authorization": r"prior author|preauthor|precertif|authorization",
    "referral": r"referral|referred",
    "network_and_setting": r"network|provider|facility|setting|hospital|office",
    "deductible": r"deductible",
    "frequency_and_quantity": r"frequency|quantity|once|twice|every|per (?:year|month|quarter)|visits|pairs",
    "covered_days": r"days|day interval|benefit period|per stay",
    "shared_allowance": r"shared|combined|allowance|wallet|maximum|budget",
    "qualification": r"eligib|qualif|medically necessary|Medicaid|QMB|chronic",
    "exclusion": r"not covered|not cover|excluded|exclusion|not included",
    "waiver_and_replacement": r"waiv|except|unless|replac|instead|if you|if the",
}


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def load(path):
    return json.loads(pathlib.Path(path).read_text())


def dump(path, value):
    pathlib.Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def rows(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            yield json.loads(line)


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ident(prefix, *values):
    return prefix + "-" + fingerprint(values)[:28]


def blank(value):
    return value is None or value == "" or value == []


def table_key(x):
    s = x["source"]
    return x["offering_id"], s["member"], s["record_ordinal"], s["field"]


def source_id(layer, oid, locator):
    return ident("SRC", layer, oid, locator)


def cms_json_group(pointer):
    """Structural JSON container only; no inferred table/JSON equivalence."""
    match = re.match(r"(/pbp/0/benefitDetails/benefitDetailsInfo/\d+)(?:/|$)", pointer)
    if match:
        return match[1]
    # Keep entire array item and nested schedule together, including controls.
    parts = pointer.split("/")
    numeric = [i for i, p in enumerate(parts) if p.isdigit() and i > 2]
    if numeric:
        return "/".join(parts[:numeric[0] + 1])
    return pointer.rsplit("/", 1)[0]


def carrier_blocks(lines, owners):
    """Lossless runs: split at blank lines or changes of exact chart binding.

    A block is a source passage, not a sentence/unique benefit. Unclassified
    passages remain required unknowns until reviewed semantic decomposition.
    """
    start = None
    current = None
    for n, line in enumerate(lines, 1):
        owner = tuple(sorted(owners.get(n, [])))
        if not line.strip() or (start is not None and owner != current):
            if start is not None:
                yield start, n - 1, current
                start = None
        if line.strip() and start is None:
            start, current = n, owner
    if start is not None:
        yield start, len(lines), current


class Inventory:
    def __init__(self, root):
        self.root = root
        self.db = sqlite3.connect(root / "inventory.sqlite3")
        self.db.executescript("""
          PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
          CREATE TABLE offering(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE dictionary_entry(key TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE obligation(id TEXT PRIMARY KEY, offering_id TEXT NOT NULL,
            kind TEXT NOT NULL, basis TEXT NOT NULL, required INTEGER NOT NULL,
            parent_id TEXT, label TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);
          CREATE TABLE source_unit(id TEXT PRIMARY KEY, offering_id TEXT NOT NULL,
            layer TEXT NOT NULL, disposition TEXT NOT NULL, locator TEXT NOT NULL,
            payload TEXT NOT NULL);
          CREATE TABLE binding(source_id TEXT NOT NULL, obligation_id TEXT NOT NULL,
            PRIMARY KEY(source_id,obligation_id));
          CREATE TABLE carrier_page(document_sha256 TEXT NOT NULL, pdf_page INTEGER NOT NULL,
            text_sha256 TEXT NOT NULL, layout_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY(document_sha256,pdf_page));
          CREATE TABLE carrier_view(offering_id TEXT NOT NULL, document_sha256 TEXT NOT NULL,
            kind TEXT NOT NULL, pdf_page INTEGER NOT NULL, lines INTEGER NOT NULL,
            nonblank_lines INTEGER NOT NULL, view_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY(offering_id,document_sha256,kind,pdf_page));
          CREATE INDEX obligation_offering ON obligation(offering_id,kind);
          CREATE INDEX source_offering ON source_unit(offering_id,layer);
          CREATE INDEX binding_obligation ON binding(obligation_id);
        """)
        self.input_files = {}

    def pin(self, path):
        path = pathlib.Path(path)
        self.input_files[str(path.relative_to(REPO))] = sha(path)

    def obligation(self, oid, kind, basis, key, label, *, parent=None, payload=None,
                   required=True):
        identifier = ident("OBL", oid, kind, basis, key)
        detail = dict(payload or {})
        detail["work_policy_id"] = {"claim_bundle":"CLAIM", "condition":"CONDITION",
                                    "required_unknown":"UNKNOWN"}[kind]
        self.db.execute("INSERT OR IGNORE INTO obligation VALUES (?,?,?,?,?,?,?,?,?)",
                        (identifier, oid, kind, basis, int(required), parent, label,
                         "awaiting_semantic_reconciliation", packed(detail)))
        return identifier

    def source(self, oid, layer, locator, value, disposition, obligations=()):
        sid = source_id(layer, oid, locator)
        self.db.execute("INSERT INTO source_unit VALUES (?,?,?,?,?,?)",
                        (sid, oid, layer, disposition, packed(locator), packed(value)))
        for obligation in set(obligations):
            self.db.execute("INSERT INTO binding VALUES (?,?)", (sid, obligation))
        return sid

    def build_cms(self):
        definitions = load(R1 / "field-dictionary.json")
        dictionary = {(x["file"].lower(), x["name"].lower()): x for x in definitions["fields"]}
        for key, definition in sorted(dictionary.items()):
            self.db.execute("INSERT INTO dictionary_entry VALUES (?,?)", (packed(key), packed(definition)))
        services = list(rows(R7 / "service-reconciliation.jsonl.gz"))
        definition_gaps = load(R7 / "remaining-service-source-definitions.json")
        grouping = {x["id"] for x in definition_gaps["grouping_nodes_not_standalone_missing_benefits"]}
        service_root = {}
        for x in services:
            if x["id"] in grouping:
                continue
            service_root[x["id"]] = self.obligation(
                x["offering_id"], "claim_bundle", "cms_service", x["id"],
                x["service_name"], payload={
                    "service_record_id": x["id"], "category_code": x["category_code"],
                    "source": x["PBP_source"], "network": "unresolved_until_source_controls_reviewed",
                    "candidate_carrier_chart_ids": x["EOC_chart_row_ids"],
                    "candidate_bindings_are_not_agreement": True})
            self.source(x["offering_id"], "cms_service_record", x["PBP_source"],
                {"service_record_id":x["id"], "category_code":x["category_code"],
                 "original_record": "build-r1/benefit-instances.jsonl.gz; exact raw JSON pointer retained"},
                "required_service_presence_and_scope", [service_root[x["id"]]])
        self.service_root = service_root
        field_links = collections.defaultdict(set)
        for x in rows(R7 / "field-dispositions.jsonl.gz"):
            if x["benefit_record_id"] in service_root:
                field_links[table_key(x)].add(service_root[x["benefit_record_id"]])
        # No data value, including an explicit No or unknown code, disappears.
        for x in rows(R1 / "table-fields.jsonl.gz"):
            oid, member, ordinal, name = table_key(x)
            definition = dictionary.get(tuple(x["dictionary_key"]))
            if definition is None:
                if x["disposition"] != "retained_other_layer_L02":
                    raise ValueError("Missing official L03 dictionary definition: " + str(x["dictionary_key"]))
                definition = {"dictionary_rows": [], "owning_layer": "L02", "field_title": name}
            source = x["source"]
            locator = {**source, "dictionary_sha256": definitions["sha256"],
                       "dictionary_rows": definition["dictionary_rows"]}
            state = x["normalized"]["state"]
            value = {"raw": x["raw"], "normalized": x["normalized"],
                     "dictionary_key": x["dictionary_key"],
                     "dictionary_table": "dictionary_entry",
                     "owning_layer": definition.get("owning_layer", "L03")}
            if x["disposition"] in {"technical_metadata", "retained_other_layer_L02"}:
                self.source(oid, "cms_table", locator, value, x["disposition"])
                continue
            if blank(x["raw"]):
                self.source(oid, "cms_table", locator, value, "retained_blank_not_zero_or_no")
                continue
            label = " ".join(str(definition.get(k) or "") for k in ("field_title", "title"))
            # Published plan/tier/insulin schedules are part of the retained
            # PBP benefit scope. Do not exclude them merely because L05 owns
            # drug-list/clinical-policy work and individual pricing is held.
            targets = sorted(field_links.get(table_key(x), set()))
            if not targets:
                key = member, ordinal, definition.get("service_category") or "plan_context"
                targets = [self.obligation(oid, "claim_bundle", "cms_table_context", key,
                           label, payload={"table": member, "record_ordinal": ordinal,
                           "category": definition.get("service_category"),
                           "json_equivalence": "not_assumed"})]
            # A coded source control is an individual condition obligation; its
            # activation and meaning must be checked with its entire parent.
            if x["normalized"].get("type") in {"enum", "enum_set", "opaque_code"}:
                condition = self.obligation(oid, "condition", "cms_table_control",
                    source, label, payload={"source": locator, "raw": x["raw"],
                    "normalized": x["normalized"], "claim_roots": targets,
                    "source_No_does_not_prove_child_inapplicability": True})
                targets.append(condition)
            self.source(oid, "cms_table", locator, value,
                        "required_unknown_code" if state == "unresolved_code" else "required_observation",
                        targets)
        by_pointer = {(x["offering_id"], x["PBP_source"]["pointer"]): x["id"] for x in services}
        for x in rows(R1 / "json-leaves.jsonl.gz"):
            oid, pointer = x["offering_id"], x["pointer"]
            locator = {k: x[k] for k in ("member", "member_sha256", "pointer")}
            locator["archive_sha256"] = "65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3"
            if pointer.rsplit("/", 1)[-1] in TECH:
                self.source(oid, "cms_json", locator, x, "technical_identity_or_structure")
                continue
            if blank(x["raw"]):
                self.source(oid, "cms_json", locator, x, "retained_blank_not_zero_or_no")
                continue
            group = cms_json_group(pointer)
            record = by_pointer.get((oid, group))
            if record in grouping:
                self.source(oid, "cms_json", locator, x, "documented_grouping_control")
                continue
            target = service_root.get(record) or self.obligation(
                oid, "claim_bundle", "cms_json_context", group, group,
                payload={"json_container": group, "table_equivalence": "not_assumed"})
            self.source(oid, "cms_json", locator, x, "required_observation", [target])
        self.db.commit()

    def build_carrier(self):
        catalog = {x["sha256"]: x for x in load(R1 / "carrier-document-catalog.json")}
        catalog.update({x["sha256"]: x for x in load(R7 / "source-catalog.json")})
        for x in load(DATA / "reconciliation-r3/source-manifest.json")["sources"]:
            if x.get("content_type", "").startswith("application/pdf") and x.get("text_path"):
                text = pathlib.Path(x["text_path"]).read_text()
                body = text.split("\f")
                if not body[-1].strip():
                    body.pop()
                catalog.setdefault(x["sha256"], {**x, "pdf_pages": len(body),
                                                "document_kind": x["kind"]})
        matrix = load(R7 / "plan-document-matrix.json")
        wanted = collections.defaultdict(list)
        for p in matrix:
            for kind, document in p["document_matches"].items():
                wanted[document["sha256"]].append((p["offering_id"], kind))
        # Exact supplemental applicability links, not front-cover carrier guesses.
        for item in load(DATA / "reconciliation-r3/supplemental-document-reconciliation.json"):
            if item["sha256"] in catalog:
                for oid in item["linked_offerings"]:
                    wanted[item["sha256"]].append((oid, "supplemental"))
        for h in wanted:
            self.pin(catalog[h]["path"])
            assert sha(catalog[h]["path"]) == h, "Carrier bytes differ from recorded identity"
        self.catalog = catalog
        self.wanted = wanted
        pages = {}
        for p in rows(R1 / "carrier-pages.jsonl.gz"):
            if p["document_sha256"] in wanted:
                pages[(p["document_sha256"], p["pdf_page"])] = p
        for p in rows(R7 / "new-source-pages.jsonl.gz"):
            if p["document_sha256"] in wanted:
                pages[(p["document_sha256"], p["pdf_page"])] = p
        for h in wanted:
            if not any(hh == h for hh, _ in pages):
                self.pin(catalog[h]["text_path"])
                text = pathlib.Path(catalog[h]["text_path"]).read_text()
                assert sha(catalog[h]["text_path"]) == catalog[h]["text_sha256"]
                bodies = text.split("\f")
                if not bodies[-1].strip():
                    bodies.pop()
                for n, text in enumerate(bodies, 1):
                    pages[(h,n)] = {"document_sha256": h, "pdf_page": n,
                        "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
        self.page_keys = set(pages)
        # Hash every canonical page and retain the original text. Shared-plan
        # SB views are separately stored; excluded columns remain inspectable.
        for (h, n), p in sorted(pages.items()):
            text = p.get("layout_text", p["text"])
            assert hashlib.sha256(p["text"].encode()).hexdigest() == p["text_sha256"]
            layout_sha = hashlib.sha256(text.encode()).hexdigest()
            assert p.get("layout_text_sha256", layout_sha) == layout_sha
            self.db.execute("INSERT INTO carrier_page VALUES (?,?,?,?,?)",
                            (h, n, p["text_sha256"], layout_sha, text))
        views = {(p["offering_id"], p["source_evidence"]["document_sha256"],
                  p["source_evidence"]["pdf_page"]): p for p in rows(R7 / "SB-exact-plan-pages.jsonl.gz")}
        owners = collections.defaultdict(lambda: collections.defaultdict(list))
        self.chart_roots = {}
        for x in rows(R7 / "carrier-chart-rows.jsonl.gz"):
            root = self.obligation(x["offering_id"], "claim_bundle", "carrier_chart", x["id"],
                x["source_heading"], payload={"source_chart_id": x["id"],
                "service_family": x["section"], "subtype_network_and_columns": "require_exact_review",
                "short_heading_candidate": x["index_only_or_short_heading_candidate"],
                "source_evidence": x["source_evidence"]})
            self.chart_roots[x["id"]] = root
            for fragment in x["fragments"]:
                h = fragment["source_page"]["document_sha256"]
                owners[(x["offering_id"], h, fragment["pdf_page"])][fragment["line"]].append(root)
        self.carrier_coverage = []
        for h in sorted(wanted):
            numbers = sorted(n for hh, n in pages if hh == h)
            assert numbers == list(range(1, catalog[h]["pdf_pages"] + 1)), h
            for oid, kind in sorted(set(wanted[h])):
                for n in numbers:
                    p = pages[(h, n)]
                    view = views.get((oid, h, n)) if kind == "SB" else None
                    text = view["text"] if view else p.get("layout_text", p["text"])
                    lines = text.splitlines()
                    self.db.execute("INSERT INTO carrier_view VALUES (?,?,?,?,?,?,?,?)", (
                        oid, h, kind, n, len(lines), sum(bool(l.strip()) for l in lines),
                        hashlib.sha256(text.encode()).hexdigest(), text))
                    if view and text != p.get("layout_text", p["text"]):
                        self.source(oid, "carrier_original_shared_columns",
                            {"document_sha256": h, "pdf_page": n, "kind": kind},
                            {"column_binding": view["column_binding"],
                             "original_page_retained_in": "carrier_page", "exact_plan_view": "carrier_view"},
                            "retained_other_plan_columns_not_offering_claims")
                    for begin, end, targets in carrier_blocks(lines, owners[(oid, h, n)]):
                        passage = "\n".join(lines[begin-1:end])
                        locator = {"document_sha256": h, "pdf_page": n, "kind": kind,
                            "line_start": begin, "line_end": end,
                            "page_text_sha256": p["text_sha256"],
                            "view_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "passage_sha256": hashlib.sha256(passage.encode()).hexdigest()}
                        targets = list(targets)
                        if re.fullmatch(r"\s*\d+\s*", passage):
                            self.source(oid, "carrier_passage", locator, {"text": passage},
                                        "technical_page_number")
                            continue
                        if not targets:
                            # Do not declare medical exceptions out of scope on
                            # chapter numbers, dollar tokens or heading guesses.
                            targets = [self.obligation(oid, "required_unknown", "carrier_unclassified_passage",
                                locator, passage[:180].strip(), payload={"locator": locator,
                                "text": passage, "closure": "Review full context; decompose substantive medical claims/conditions or record exact out-of-scope rationale. Root cannot be dropped."})]
                        sid = self.source(oid, "carrier_passage", locator,
                            {"text": passage, "headers_and_footnotes": "entire_original_page_and_continuations_retained_not_yet_bound",
                             "extraction_method": p.get("extraction_method", "pdftotext_layout")},
                            "required_chart_passage" if owners[(oid,h,n)].get(begin) else "required_unclassified_passage",
                            targets)
                        # These are candidate source condition passages, each
                        # explicit obligation remains open; regex is not proof.
                        for family, pattern in TRIGGERS.items():
                            if re.search(pattern, passage, re.I):
                                condition = self.obligation(oid, "condition", "carrier_condition_passage",
                                    (sid, family), family, parent=targets[0],
                                    payload={"family": family, "source_passage_id": sid,
                                             "classification": "candidate_requires_context_review",
                                             "all_claim_roots": targets})
                                self.db.execute("INSERT INTO binding VALUES (?,?)", (sid, condition))
            self.carrier_coverage.append({"document_sha256": h, "pages": len(numbers),
                 "offering_document_views": len(set(wanted[h])), "source": catalog[h]})
        self.db.commit()

    def add_exceptions(self):
        gaps = load(R7 / "remaining-service-source-definitions.json")
        exceptions = []
        for x in gaps["unmodeled_supplemental_source_definitions"]:
            root = self.service_root[x["id"]]
            exceptions.append({"id": ident("EX", x["id"]), "offering_id": x["offering_id"],
                "obligation_ids": [root], "kind": "supplemental_definition",
                "state": "required_unknown", "owner": "L03 data maintainer",
                "next_action": "Establish exact applicable carrier definition; proposed unknown-only MVP treatment requires exact scope review.",
                "closure_evidence": "Exact applicable dated passage and reviewed interpretation, or explicit bound scope decision retaining unknown.",
                "permitted_unmodeled": False, "source": x})
        for x in load(R7 / "optional-dental-rider-reconciliation.json"):
            root = self.obligation(x["offering_id"], "required_unknown", "rider_frequency", x["id"],
                "Specific optional dental procedure frequencies and prior tooth history", payload={"source": x})
            exceptions.append({"id": ident("EX", x["id"]), "offering_id": x["offering_id"],
                "obligation_ids": [root], "kind": "optional_dental_frequencies",
                "state": "required_unknown", "owner": "L03 data maintainer",
                "next_action": "Obtain exact dated procedure guide through permitted route, or propose specific unknown-only scope disposition.",
                "closure_evidence": "Applicable procedure-level frequency/history guide with exact rider linkage, or exact scoped review receipt.",
                "permitted_unmodeled": False})
        dispositions = load(DATA / "bounded-reference-r4/dispositions.json")
        old_issues = {x["issue_id"]: x for x in load(DATA / "reconciliation-r3/amount-issue-decisions.json")}
        for disposition in dispositions:
            for issue_id in disposition["issue_ids"]:
                issue = old_issues[issue_id]
                oid = issue["offering_id"]
                root = self.obligation(oid, "required_unknown", "preserved_conflict", issue_id,
                    disposition["id"], payload={"issue": issue, "accepted_treatment": disposition,
                    "underlying_amount_verified": False})
                exceptions.append({"id": issue_id, "offering_id": oid, "obligation_ids": [root],
                    "kind": "preserved_r4_conflict", "state": "held_under_accepted_disposition",
                    "owner": "L03 data maintainer", "next_action": "Preserve exact accepted conservative treatment; factual equivalence requires new same-scope evidence.",
                    "closure_evidence": "Existing exact treatment receipt remains valid only for its original allowlist; new equivalence needs exact evidence and review.",
                    "permitted_unmodeled": True, "disposition_id": disposition["id"]})
        assert sum(x["kind"] == "preserved_r4_conflict" for x in exceptions) == 153
        dump(self.root / "exceptions.json", exceptions)
        # Known acquisition/notice boundaries cannot be turned into zero missing
        # material amendments merely because all main PDFs were supplied.
        dump(self.root / "source-boundaries.json", {
            "main_SB_EOC_slots": 144, "matched_slots": 144,
            "rider_amendment_completeness": "not_established",
            "member_specific_notices": "not_publicly_exhaustible; no private access authorized",
            "prior_access_stops": "preserved; no network request made in this build",
            "all_retained_documents_have_applicability_decision": False,
            "unselected_catalog_documents": [x for h, x in sorted(self.catalog.items()) if h not in self.wanted],
            "unselected_document_treatment": "retained historical catalog; applicability beyond matched main/supplemental relations remains an explicit scope obligation"})
        for p in load(R7 / "plan-document-matrix.json"):
            self.obligation(p["offering_id"], "required_unknown", "amendment_applicability",
                p["offering_id"], "Applicable riders, revisions and cross-referenced material",
                payload={"source": "source-boundaries.json", "closure": "Review observed references, applicable effective dates and retained alternate documents; document permitted source limits."})
        self.db.execute("UPDATE obligation SET state='held_source_conflict' WHERE basis='preserved_conflict'")
        self.db.execute("UPDATE obligation SET state='evidence_missing' WHERE basis='rider_frequency'")
        self.db.commit()

    def export(self):
        self.db.execute("ANALYZE")
        self.db.commit()
        summary = {"package_id": PACKAGE, "input_offerings": 72,
            "counting_unit": "source-native assertion bundles, individual candidate condition passages/controls, and required unknown roots; NOT deduplicated semantic benefits",
            "semantic_claim_denominator_frozen": False,
            "source_obligation_denominator_frozen": True,
            "reason_semantic_denominator_not_frozen": "Unclassified carrier passages and independently retained CMS representations still require semantic decomposition and reviewed equivalence. No extraction count is called a distinct benefit count.",
            "permitted_new_unmodeled_extras": 0, "new_verified_claims": 0,
            "new_accepted_entries": 0, "existing_r4_entries": 535,
            "full_L03_complete": False}
        summary["obligations"] = dict(self.db.execute("SELECT kind,count(*) FROM obligation GROUP BY kind"))
        summary["obligations_by_basis"] = dict(self.db.execute("SELECT basis,count(*) FROM obligation GROUP BY basis"))
        summary["progress_states"] = dict(self.db.execute("SELECT state,count(*) FROM obligation GROUP BY state"))
        summary["source_instances"] = dict(self.db.execute("SELECT layer,count(*) FROM source_unit GROUP BY layer"))
        summary["source_dispositions"] = dict(self.db.execute("SELECT disposition,count(*) FROM source_unit GROUP BY disposition"))
        summary["carrier_documents"] = len(self.carrier_coverage)
        summary["carrier_pages"] = self.db.execute("SELECT count(*) FROM carrier_page").fetchone()[0]
        summary["carrier_offering_page_views"] = self.db.execute("SELECT count(*) FROM carrier_view").fetchone()[0]
        summary["required_roots"] = self.db.execute("SELECT count(*) FROM obligation WHERE required=1").fetchone()[0]
        dump(self.root / "summary.json", summary)
        dump(self.root / "source-index.json", self.carrier_coverage)
        dump(self.root / "inputs.json", self.input_files)
        per_offering = []
        with (self.root / "per-offering.csv").open("w", newline="") as stream:
            out = csv.writer(stream)
            out.writerow(["offering_id", "claim_bundles", "condition_obligations", "required_unknowns", "sources"])
            for (oid,) in self.db.execute("SELECT id FROM offering ORDER BY id"):
                counts = dict(self.db.execute("SELECT kind,count(*) FROM obligation WHERE offering_id=? GROUP BY kind", (oid,)))
                sources = self.db.execute("SELECT count(*) FROM source_unit WHERE offering_id=?", (oid,)).fetchone()[0]
                out.writerow([oid, counts.get("claim_bundle",0), counts.get("condition",0), counts.get("required_unknown",0), sources])
                per_offering.append({"offering_id": oid, **counts, "sources": sources})
        dump(self.root / "per-offering.json", per_offering)
        with gzip.GzipFile(filename=str(self.root / "master-inventory.jsonl.gz"), mode="wb", mtime=0) as stream:
            for x in self.db.execute("SELECT id,offering_id,kind,basis,required,parent_id,label,state,payload FROM obligation ORDER BY id"):
                item = dict(zip(("id","offering_id","kind","basis","required","parent_id","label","state","payload"), x))
                item["payload"] = json.loads(item["payload"])
                item["source_ids"] = [r[0] for r in self.db.execute("SELECT source_id FROM binding WHERE obligation_id=? ORDER BY source_id", (item["id"],))]
                stream.write((packed(item)+"\n").encode())
        self.db.close()
        return summary


def build(root=ROOT):
    root = pathlib.Path(root)
    if any((root / name).exists() for name in ("freeze.json", "inventory.sqlite3", "inventory.sqlite3.gz")):
        raise ValueError("Existing inventory is immutable; use a new output revision")
    root.mkdir(parents=True, exist_ok=True)
    inv = Inventory(root)
    inputs = [R1 / n for n in ("field-dictionary.json", "table-fields.jsonl.gz", "json-leaves.jsonl.gz",
               "pbp-plan-manifest.json", "benefit-instances.jsonl.gz", "table-rows.jsonl.gz",
               "carrier-document-catalog.json", "carrier-pages.jsonl.gz", "package-manifest.json")]
    inputs += [R7 / n for n in ("manifest.json", "service-reconciliation.jsonl.gz", "field-dispositions.jsonl.gz",
                "plan-document-matrix.json", "source-catalog.json", "new-source-pages.jsonl.gz",
                "carrier-chart-rows.jsonl.gz", "SB-exact-plan-pages.jsonl.gz",
                "remaining-service-source-definitions.json", "optional-dental-rider-reconciliation.json")]
    inputs += [DATA / n for n in ("bounded-reference-r4/manifest.json", "bounded-reference-r4/dispositions.json",
                "reconciliation-r3/amount-issue-decisions.json", "reconciliation-r3/supplemental-document-reconciliation.json",
                "reconciliation-r3/source-manifest.json")]
    inputs += [REPO / "cms-slice/data-sources/l03-published-reference-review.json"]
    for p in inputs:
        inv.pin(p)
    for x in load(R7 / "plan-document-matrix.json"):
        inv.db.execute("INSERT INTO offering VALUES (?,?)", (x["offering_id"], packed(x)))
    assert inv.db.execute("SELECT count(*) FROM offering").fetchone()[0] == 72
    inv.build_cms()
    print("CMS source accounting built", flush=True)
    inv.build_carrier()
    print("Carrier reverse source accounting built", flush=True)
    inv.add_exceptions()
    return inv.export()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
