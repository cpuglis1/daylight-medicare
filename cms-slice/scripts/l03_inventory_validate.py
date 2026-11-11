"""Read-only r8 accounting checks; sealing never records source acceptance."""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import sqlite3
import shutil
import tempfile
import zipfile

from l03_inventory import DATA, REPO, ROOT, R1, R7, dump, load, rows, sha


def open_inventory(root):
    path = pathlib.Path(root) / "inventory.sqlite3"
    temporary = None
    if not path.exists():
        temporary = tempfile.TemporaryDirectory(prefix="l03-r8-inspect-")
        path = pathlib.Path(temporary.name) / "inventory.sqlite3"
        with gzip.open(pathlib.Path(root)/"inventory.sqlite3.gz", "rb") as src, path.open("wb") as dest:
            shutil.copyfileobj(src, dest)
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True), temporary


def raw_leaves(value, path=""):
    # Separate raw-source traversal, independent of prior retained row counts.
    if isinstance(value, dict):
        for key in value:
            yield from raw_leaves(value[key], path + "/" + key.replace("~","~0").replace("/","~1"))
    elif isinstance(value, list) and value:
        for index in range(len(value)):
            yield from raw_leaves(value[index], path + "/" + str(index))
    else:
        yield path, value


def validate(root=ROOT, check_inputs=True):
    root = pathlib.Path(root)
    db, temporary = open_inventory(root)
    checks = []
    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
    check("SQLite integrity", db.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    ids = {r[0] for r in db.execute("SELECT id FROM offering")}
    expected_ids = {x["offering_id"] for x in load(R1 / "pbp-plan-manifest.json")}
    check("Exact 72 pinned offering identities", ids == expected_ids and len(ids) == 72)
    check("No bindings to missing source/obligation", db.execute("""SELECT count(*) FROM binding b
        LEFT JOIN source_unit s ON b.source_id=s.id LEFT JOIN obligation o ON b.obligation_id=o.id
        WHERE s.id IS NULL OR o.id IS NULL""").fetchone()[0] == 0)
    check("Required observations cannot disappear", db.execute("""SELECT count(*) FROM source_unit s
        WHERE disposition LIKE 'required_%' AND NOT EXISTS
        (SELECT 1 FROM binding b WHERE b.source_id=s.id)""").fetchone()[0] == 0)
    check("Bindings cannot cross offering identity", db.execute("""SELECT count(*) FROM binding b
        JOIN source_unit s ON s.id=b.source_id JOIN obligation o ON o.id=b.obligation_id
        WHERE s.offering_id != o.offering_id""").fetchone()[0] == 0)
    check("No unknown offering IDs", db.execute("""SELECT count(*) FROM obligation o
        LEFT JOIN offering p ON p.id=o.offering_id WHERE p.id IS NULL""").fetchone()[0] == 0)
    input_bad = []
    if check_inputs:
        for name, expected in load(root / "inputs.json").items():
            if not (REPO / name).exists() or sha(REPO / name) != expected:
                input_bad.append(name)
    check("Pinned input bytes unchanged", not input_bad, input_bad)
    for layer, filename in (("cms_json", "json-leaves.jsonl.gz"), ("cms_table", "table-fields.jsonl.gz")):
        expected_count = 0
        bad = []
        index = {}
        for oo, ll, vv in db.execute("SELECT offering_id,locator,payload FROM source_unit WHERE layer=?", (layer,)):
            ll, vv = json.loads(ll), json.loads(vv)
            kk = (oo,ll.get("member"),ll.get("pointer"),ll.get("record_ordinal"),ll.get("field"))
            if kk in index:
                bad.append(["duplicate",kk])
            index[kk] = (ll,vv)
        for x in rows(R1 / filename):
            expected_count += 1
            oid = x["offering_id"]
            locator = {k: x[k] for k in ("member", "member_sha256", "pointer")} if layer == "cms_json" else x["source"]
            # DB locator adds dictionary rows/archive identity; match the raw
            # retained source tuple without depending on the builder ID logic.
            key = (oid, locator.get("member"), locator.get("pointer"),
                   locator.get("record_ordinal"), locator.get("field"))
            result = index.get(key)
            if result is None or result[1].get("raw") != x["raw"] or result[0]["member_sha256"] != locator["member_sha256"]:
                bad.append(key)
            elif layer == "cms_table" and result[1]["normalized"] != x["normalized"]:
                bad.append(key)
        check(layer + " exhaustive source-instance identity/value equality",
              len(index) == expected_count and not bad, {"expected":expected_count,"stored":len(index),"errors":bad[:5]})
        if layer == "cms_table":
            row_count = 0; row_errors = []
            for x in rows(R1 / "table-rows.jsonl.gz"):
                s = x["source"]
                for name,value in x["raw"].items():
                    row_count += 1
                    kk = (x["offering_id"],s["member"],None,s["record_ordinal"],name)
                    if kk not in index or index[kk][1]["raw"] != value:
                        row_errors.append(kk)
            check("Tabular coverage independently checked against full raw rows",
                  row_count == len(index) and not row_errors,
                  {"raw_fields":row_count,"errors":row_errors[:5]})
        del index
    # Independently check JSON against original archive bytes, not only against
    # an earlier extraction that could have omitted a field itself.
    manifest = load(R1 / "pbp-plan-manifest.json")
    archive = REPO / "docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw" / manifest[0]["archive_sha256"]
    raw_bad = []; raw_count = 0
    with zipfile.ZipFile(archive) as source:
        for item in manifest:
            data = source.read(item["member"])
            if hashlib.sha256(data).hexdigest() != item["member_sha256"]:
                raw_bad.append(item["member"])
            expected = dict(raw_leaves(json.loads(data)))
            actual = {json.loads(l)["pointer"]: json.loads(v)["raw"] for l,v in db.execute(
                "SELECT locator,payload FROM source_unit WHERE layer='cms_json' AND offering_id=?",(item["offering_id"],))}
            if actual != expected:
                raw_bad.append(item["member"])
            raw_count += len(expected)
    check("JSON coverage rederived from all 72 original archive members", not raw_bad,
          {"source_instances":raw_count,"errors":raw_bad[:5]})
    # Reconstruct expected offering/document page coverage from the pinned
    # applicability inputs, so omission of a whole view also fails the audit.
    catalog = {x["sha256"]:x for x in load(R1/"carrier-document-catalog.json")}
    catalog.update({x["sha256"]:x for x in load(R7/"source-catalog.json")})
    for item in load(DATA/"reconciliation-r3/source-manifest.json")["sources"]:
        if item.get("content_type","").startswith("application/pdf") and item.get("text_path"):
            body = pathlib.Path(item["text_path"]).read_text().split("\f")
            if not body[-1].strip():body.pop()
            catalog.setdefault(item["sha256"],{**item,"pdf_pages":len(body)})
    expected_views = set()
    for p in load(R7/"plan-document-matrix.json"):
        for kind,item in p["document_matches"].items():
            expected_views.update((p["offering_id"],item["sha256"],kind,n)
                for n in range(1,catalog[item["sha256"]]["pdf_pages"]+1))
    for item in load(DATA/"reconciliation-r3/supplemental-document-reconciliation.json"):
        if item["sha256"] in catalog:
            for oid in item["linked_offerings"]:
                expected_views.update((oid,item["sha256"],"supplemental",n)
                    for n in range(1,catalog[item["sha256"]]["pdf_pages"]+1))
    actual_views = set(db.execute("SELECT offering_id,document_sha256,kind,pdf_page FROM carrier_view"))
    check("Every main and linked supplemental document page view exists",
          actual_views == expected_views,{"expected":len(expected_views),"actual":len(actual_views)})
    # Per-line provenance requires exact text, not occurrence of a money token.
    spans = collections.defaultdict(list)
    for oid,loc,val in db.execute("SELECT offering_id,locator,payload FROM source_unit WHERE layer='carrier_passage'"):
        loc, val = json.loads(loc), json.loads(val)
        spans[(oid,loc["document_sha256"],loc["kind"],loc["pdf_page"])].append((loc,val))
    errors = []; views = 0; source_lines = 0; covered_lines = 0
    for oid,h,kind,n,text in db.execute("SELECT offering_id,document_sha256,kind,pdf_page,text FROM carrier_view"):
        views += 1
        lines = text.splitlines()
        expected = {i for i,line in enumerate(lines,1) if line.strip()}
        actual = collections.Counter()
        view_sha = hashlib.sha256(text.encode()).hexdigest()
        for loc,val in spans.pop((oid,h,kind,n),[]):
            a,b = loc["line_start"],loc["line_end"]
            passage = "\n".join(lines[a-1:b])
            if (val["text"] != passage or hashlib.sha256(passage.encode()).hexdigest() != loc["passage_sha256"] or
                    view_sha != loc["view_sha256"]):
                errors.append([oid,h,n,a,"passage mismatch"])
            actual.update(range(a,b+1))
        if set(actual) != expected or any(v != 1 for v in actual.values()):
            errors.append([oid,h,n,"omitted/duplicated lines"])
        source_lines += len(expected); covered_lines += len(actual)
    check("Every nonblank line in every exact offering-document view covered exactly once",
          not errors and not spans, {"views":views,"source_lines":source_lines,"covered_lines":covered_lines,"errors":errors[:5]})
    orphan_claims = db.execute("""SELECT count(*) FROM obligation o WHERE kind='claim_bundle'
        AND NOT EXISTS(SELECT 1 FROM binding b WHERE b.obligation_id=o.id)""").fetchone()[0]
    check("Every counted claim bundle has source evidence", orphan_claims == 0, orphan_claims)
    exceptions = load(root / "exceptions.json")
    check("All 153 prior disputed groups and 11 definition + 5 dental gaps remain",
          collections.Counter(x["kind"] for x in exceptions) == {
              "preserved_r4_conflict":153,"supplemental_definition":11,"optional_dental_frequencies":5})
    check("Every explicit exception has owner/action/closure evidence", all(
        x.get("owner") and x.get("next_action") and x.get("closure_evidence") and x.get("obligation_ids")
        for x in exceptions))
    policies = load(root/"work-policies.json")
    bad_policy = []
    for identifier,payload in db.execute("SELECT id,payload FROM obligation"):
        policy = policies.get(json.loads(payload).get("work_policy_id"),{})
        if not all(policy.get(k) for k in ("owner","next_action","closure_evidence")):
            bad_policy.append(identifier)
    check("Every unresolved root has a pinned owner/action/closure policy",not bad_policy,bad_policy[:5])
    check("Published Rx PBP observations were not silently excluded as another layer",
          db.execute("SELECT count(*) FROM source_unit WHERE disposition='retained_L05_PartD'").fetchone()[0] == 0)
    receipt = load(REPO / "cms-slice/data-sources/l03-published-reference-review.json")
    check("r4 accepted exact entry list remains 535", receipt["decision"] == "accepted" and len(receipt["accepted_entry_ids"]) == 535)
    summary = load(root / "summary.json")
    check("New source counts are not passed off as semantic verification/acceptance",
          summary["new_verified_claims"] == summary["new_accepted_entries"] == 0 and
          not summary["semantic_claim_denominator_frozen"] and not summary["full_L03_complete"])
    check("No new unmodeled exception is silently permitted", summary["permitted_new_unmodeled_extras"] == 0)
    db.close()
    if temporary:
        temporary.cleanup()
    return {"package_id": summary["package_id"], "passed":all(x["passed"] for x in checks),
            "checks":checks, "limits":"Accounting/schema checks do not establish complete semantic inventory, independent source review, or acceptance."}


def seal(root=ROOT):
    root = pathlib.Path(root)
    if (root / "freeze.json").exists():
        raise ValueError("Already sealed; validate without --seal")
    result = validate(root)
    dump(root / "validation.json", result)
    if not result["passed"]:
        raise ValueError("Cannot seal failing inventory")
    code = {}
    code_dir = root / "code"
    code_dir.mkdir(exist_ok=True)
    for name,folder in (("l03_inventory.py","scripts"), ("l03_inventory_validate.py","scripts"),
                        ("l03_comparison_contract.py","scripts"),
                        ("test_l03_inventory_contract.py","tests")):
        source = REPO / "cms-slice" / folder / name
        (code_dir / name).write_bytes(source.read_bytes())
        code[str(source.relative_to(REPO))] = sha(source)
    # The complete provenance DB is large. Ship losslessly compressed; normal
    # validation transparently expands a temporary read-only copy.
    database = root / "inventory.sqlite3"
    if database.exists():
        with database.open("rb") as src, gzip.GzipFile(filename=str(root/"inventory.sqlite3.gz"), mode="wb", mtime=0) as dest:
            shutil.copyfileobj(src,dest)
        database.unlink()
    files = {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != "freeze.json"}
    manifest = {"schema":"l03-inventory-freeze/1", "package_id":load(root/"summary.json")["package_id"],
                "frozen":"source_obligation_inventory_and_comparison_contract",
                "semantic_claim_denominator_frozen":False,"milestone_1_complete":False,
                "new_evidence_accepted":False,"files_sha256":files,"code_sha256":code}
    dump(root / "freeze.json", manifest)
    return manifest


def verify_freeze(root=ROOT):
    root = pathlib.Path(root)
    manifest = load(root / "freeze.json")
    errors = [name for name, expected in manifest["files_sha256"].items()
              if not (root/name).exists() or sha(root/name) != expected]
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name != "freeze.json"}
    extra = sorted(actual-set(manifest["files_sha256"]))
    changed_code = [name for name,expected in manifest["code_sha256"].items()
                    if not (REPO/name).exists() or sha(REPO/name) != expected]
    return {"passed":not errors and not extra and not changed_code,"changed_files":errors,
            "extra_files":extra,"changed_current_code":changed_code,"freeze_sha256":sha(root/"freeze.json"),
            "milestone_1_complete":manifest["milestone_1_complete"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--verify-freeze", action="store_true")
    args = parser.parse_args()
    result = verify_freeze(args.root) if args.verify_freeze else seal(args.root) if args.seal else validate(args.root)
    if not args.seal:
        print(json.dumps(result,indent=2))
    else:
        print(json.dumps({"sealed":True,"semantic_denominator_frozen":False}))
    if result.get("passed") is False:
        raise SystemExit(1)
