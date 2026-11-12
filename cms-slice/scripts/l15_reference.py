#!/usr/bin/env python3
"""Build and read a dated SHINE public directory, separate from service execution."""
import argparse
import copy
from datetime import date
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/data/l15-local-counseling-2026-10-29"
ACQUISITION = BASE / "acquisition-r2"
BUILD = BASE / "build-r1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def norm(s):
    return " ".join(s.split())


class Node:
    def __init__(self, tag="root", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        if self.tag in {"script", "style"}:
            return ""
        return norm(" ".join(x.text() if isinstance(x, Node) else x for x in self.children))

    def find(self, tag=None, cls=None):
        out = []
        for node in self.children:
            if isinstance(node, Node):
                if (tag is None or node.tag == tag) and (cls is None or cls in node.attrs.get("class", "").split()):
                    out.append(node)
                out.extend(node.find(tag, cls))
        return out


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def flat(html):
    """Independent tag-stripping path for whole-field comparisons."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", html, flags=re.S | re.I)
    return norm(unescape(re.sub(r"<[^>]*>", " ", html)))


def load_sources():
    records = json.loads((ACQUISITION / "receipts.json").read_text())
    for r in records:
        path = ROOT / r["path"]
        if digest(path) != r["sha256"] or path.stat().st_size != r["bytes"]:
            raise ValueError("Source integrity mismatch: " + r["id"])
    return {r["id"]: r for r in records}, {r["id"]: (ROOT / r["path"]).read_text() for r in records}


def derive():
    sources, raw = load_sources()
    trees = {sid: Tree(html).root for sid, html in raw.items()}
    checked = sources["P26-S58"]["retrieved_at_utc"][:10]
    if {r["retrieved_at_utc"][:10] for r in sources.values()} != {checked}:
        raise ValueError("Mixed observation dates")
    state_text = trees["P26-S57"].text()

    def exact(sid, value, location):
        if norm(value) not in trees[sid].text():
            raise ValueError("Missing source value: " + value)
        return {"value": value, "source_id": sid, "source_sha256": sources[sid]["sha256"], "location": location}

    state = {key: exact("P26-S57", value, "SHINE Program contact block / " + key) for key, value in {
        "phone": "1-800-963-5337", "phone_mnemonic": "1-800-96-ELDER", "tty": "1-800-955-8770",
        "agency": "Department of Elder Affairs", "address": "4040 Esplanade Way, Suite 270 Tallahassee, FL 32399-7000",
        "fax": "850-414-2150", "email": "information@elderaffairs.org"}.items()}
    state["administrative_contact_limit"] = "Mailing address, fax and general email are not represented as a local appointment route."
    containers = trees["P26-S58"].find("div", "csites")
    if len(containers) != 1:
        raise ValueError("County directory table ambiguous")
    rows = containers[0].find("tr")
    columns = [n.text() for n in rows[0].find("td")]
    if columns != ["Site Name", "Address", "County", "Date", "Time", "More Information"]:
        raise ValueError("Directory schema changed")
    sites = []
    for number, row in enumerate(rows[1:], 1):
        cells = row.find("td")
        if len(cells) != 6 or cells[2].text() != "Collier":
            raise ValueError("Unaccounted county directory row")
        native = {column: exact("P26-S58", cell.text(), f"div.csites table row {number} / {column}") for column, cell in zip(columns, cells)}
        phones = re.findall(r"\b\d{3}-\d{3}-\d{4}\b", cells[5].text())
        if len(phones) != 1:
            raise ValueError("Appointment phone ambiguous")
        if cells[3].text() != "By appointment only." or cells[4].text() != "By appointment only.":
            raise ValueError("Appointment condition changed")
        sites.append({"id": f"collier-shine-site-{number}", "native_fields": native,
                      "name": cells[0].text(), "address": cells[1].text(), "county_fips": "12021",
                      "phone": phones[0], "appointment_only": True,
                      "member_restriction": "members_only" if "members only" in cells[5].text().lower() else "not_stated",
                      "website": [{"label": a.text(), "url": a.attrs["href"]} for a in cells[5].find("a")],
                      "availability": "not_confirmed", "appointment_booked": False,
                      "hours": None, "membership_eligibility": "not_determined"})
    if len(sites) != 2 or sites[1]["member_restriction"] != "members_only":
        raise ValueError("New directory population needs review")
    liaison = {key: exact("P26-S58", value, "#contact_rptr / " + key) for key, value in {
        "name": "Camilita Aldridge", "phone": "239-652-6900 ext. 58259",
        "address": "2830 Winkler Avenue, Suite 112 , Fort Myers, FL 33916",
        "purpose": "If you are interested in hosting a counseling site at your facility or are interested in volunteering for SHINE in your community, please contact the liaison listed above."}.items()}
    liaison["appointment_route"] = False
    labels = trees["P26-S57"].find(cls="EditingFormLabel")
    fields = [{"published_label": n.text(), "marked_required": n.text().startswith("*"),
               "location": "#" + n.attrs["id"]} for n in labels]
    if len(fields) != 13 or sum(f["marked_required"] for f in fields) != 6:
        raise ValueError("Form field inventory changed")
    form = {"url": sources["P26-S57"]["url"], "source_id": "P26-S57", "fields": fields,
            "purpose": exact("P26-S57", "The best resource is a SHINE Counselor. Please complete and submit the form below so that we can connect you with a SHINE Counselor in your area.", "Contact Us introduction"),
            "select_options": [[o.text() for o in n.find("option")] for n in trees["P26-S57"].find("select")],
            "security_code_required": "Enter security code:" in state_text,
            "submission_executed": False, "delivery_confirmed": False,
            "personal_data_sent": False, "security_image_requested": False,
            "limit": "Published required markers only; server validation and counselor response untested. Enter personal details directly on SHINE only if you choose to request help."}
    program = exact("L15-S03", "SHINE services are free, unbiased, and confidential.", "Who We Are")
    return {"reference_id": "L15-PUBLISHED-COLLIER-2026-10-29-r1", "layer": "L15", "county_fips": "12021",
            "as_of_date": checked, "coverage": "All site rows on the official Collier directory and the statewide published contact/request routes on this date.",
            "site_count": len(sites), "counseling_contact_route_count": 5,
            "statewide": state, "sites": sites, "liaison": liaison, "online_request": form,
            "program_description": program, "sources": list(sources.values()),
            "status": {"published_directory_collection": "complete", "technical_validation": "pending",
                       "R20": "mechanical_comparison_pending; human_only_if_material_conflict",
                       "human_acceptance": None, "consumer_release": False, "service_outcome": "not_observed"},
            "refresh": "Recheck the official pages before a later demo/release; changed source content requires a new revision and field diff.",
            "limits": ["A published contact is not evidence of a working phone, available appointment, response time or completed counseling.",
                       "Not a historical full-year list or a census of every counselor in Collier.",
                       "Baker membership is not inferred; an unstated restriction at the other site is not a personal eligibility finding."]}


def validate(data):
    sources, raw = load_sources()
    comparisons = []
    for sid, html in raw.items():
        tree_text = Tree(html).root.text()
        if tree_text != flat(html):
            raise ValueError("Independent full-page extraction differs: " + sid)
    county_table = re.search(r'<div class="csites">\s*<table>(.*?)</table>', raw["P26-S58"], re.S | re.I).group(1)
    independent_rows = [[flat(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S | re.I)] for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", county_table, re.S | re.I)]
    row_html = re.findall(r"<tr\b[^>]*>(.*?)</tr>", county_table, re.S | re.I)
    if len(independent_rows) - 1 != data["site_count"] or data["site_count"] != len(data["sites"]):
        raise ValueError("Dropped or added site")
    for index, site in enumerate(data["sites"], 1):
        values = [site["native_fields"][k]["value"] for k in independent_rows[0]]
        if values != independent_rows[index]:
            raise ValueError("Independent site-row mismatch")
        if site["name"] != values[0] or site["address"] != values[1] or site["phone"] != re.search(r"\d{3}-\d{3}-\d{4}", values[5])[0]:
            raise ValueError("Derived site identity/contact mismatch")
        if not site["appointment_only"] or site["appointment_booked"] or site["availability"] != "not_confirmed":
            raise ValueError("Unsupported appointment assertion")
        expected_restriction = "members_only" if "members only" in values[5].lower() else "not_stated"
        if site["member_restriction"] != expected_restriction or site["county_fips"] != "12021" or site["hours"] is not None:
            raise ValueError("Lost restriction or invented scope/hours")
        links = [{"url": unescape(url), "label": flat(label)} for url, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row_html[index], re.S | re.I)]
        if links != site["website"]:
            raise ValueError("Host link mismatch")
        comparisons.extend({"row": index, "column": col, "value": val, "result": "exact"} for col, val in zip(independent_rows[0], values))

    def evidence_walk(value):
        if isinstance(value, dict):
            if {"value", "source_id", "source_sha256", "location"} <= value.keys():
                sid = value["source_id"]
                if value["source_sha256"] != sources[sid]["sha256"] or norm(value["value"]) not in flat(raw[sid]):
                    raise ValueError("Unsupported field/source binding")
                comparisons.append({"source_id": sid, "location": value["location"], "value": value["value"], "result": "exact"})
            for v in value.values():
                evidence_walk(v)
        elif isinstance(value, list):
            for v in value:
                evidence_walk(v)
    evidence_walk(data)
    independent_labels = re.findall(r'<(?:label|span)\b[^>]*class="EditingFormLabel"[^>]*>(.*?)</(?:label|span)>', raw["P26-S57"], re.S | re.I)
    if [flat(label) for label in independent_labels] != [f["published_label"] for f in data["online_request"]["fields"]]:
        raise ValueError("Form field mismatch")
    for field in data["online_request"]["fields"]:
        if field["marked_required"] != field["published_label"].startswith("*"):
            raise ValueError("Required marker changed")
        ident = re.escape(field["location"][1:])
        located = re.search(r'<(?:label|span)\b[^>]*id="' + ident + r'"[^>]*>(.*?)</(?:label|span)>', raw["P26-S57"], re.S | re.I)
        if not located or flat(located[1]) != field["published_label"]:
            raise ValueError("Form field locator changed")
    independent_options = [[flat(o) for o in re.findall(r"<option\b[^>]*>(.*?)</option>", select, re.S | re.I)] for select in re.findall(r"<select\b[^>]*>(.*?)</select>", raw["P26-S57"], re.S | re.I)]
    if independent_options != data["online_request"]["select_options"]:
        raise ValueError("Form choices changed")
    if data["online_request"]["url"] != sources["P26-S57"]["url"] or not data["online_request"]["security_code_required"]:
        raise ValueError("Request URL or security requirement changed")
    if data["liaison"]["appointment_route"] or any(data["online_request"][k] for k in ("submission_executed", "personal_data_sent", "delivery_confirmed", "security_image_requested")):
        raise ValueError("Unsupported handoff assertion")
    if data["status"]["human_acceptance"] is not None or data["status"]["consumer_release"]:
        raise ValueError("No acceptance receipt exists")
    if data["county_fips"] != "12021" or data["as_of_date"] != sources["P26-S58"]["retrieved_at_utc"][:10]:
        raise ValueError("Wrong county/date")
    if data["sources"] != list(sources.values()) or data["reference_id"] != "L15-PUBLISHED-COLLIER-2026-10-29-r1" or data["counseling_contact_route_count"] != 5:
        raise ValueError("Reference/source inventory changed")
    return {"result": "pass", "comparison_method": "HTML tree versus independent regex/tag stripping; whole pages and every table cell; all modeled source-bound fields and form labels",
            "site_rows_compared": len(data["sites"]), "native_site_cells_compared": len(independent_rows[0]) * len(data["sites"]),
            "form_labels_compared": len(independent_labels), "comparisons": comparisons,
            "R20": "No unresolved contact semantics found; human review not currently required by the issued R20 scope. No human acceptance fabricated."}


def build(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new build revision; existing output must remain unchanged")
    output.mkdir(parents=True, exist_ok=True)
    data = derive()
    receipt = validate(data)
    data["status"]["technical_validation"] = "passed"
    data["status"]["R20"] = "mechanical_comparison_complete; no_material_contact_conflict"
    save(output / "directory.json", data)
    save(output / "validation.json", receipt)
    return data


def load(*, research_mode=False, county_fips="12021", as_of="2026-10-29", base=BASE):
    if not research_mode:
        raise ValueError("Exact consumer release acceptance is not recorded")
    if county_fips != "12021" or as_of != "2026-10-29":
        raise ValueError("This is a dated Collier directory; recheck the source for another date/county")
    date.fromisoformat(as_of)
    manifest = json.loads((base / "manifest.json").read_text())
    selector = json.loads((base / "CURRENT_REFERENCE.json").read_text())
    if digest(base / "manifest.json") != selector["manifest_sha256"] or selector["consumer_release"]:
        raise ValueError("L15 selector mismatch")
    expected = str((base / "build-r1/directory.json").relative_to(ROOT))
    if expected not in manifest["files"]:
        raise ValueError("Directory is not bound by the manifest")
    for name, value in manifest["files"].items():
        if digest(ROOT / name) != value:
            raise ValueError("L15 reference integrity mismatch: " + name)
    data = json.loads((base / "build-r1/directory.json").read_text())
    validate(data)
    return copy.deepcopy(data)


def audit():
    """Compare existing references without mutating either interface or any source."""
    data = json.loads((BUILD / "directory.json").read_text())
    current = json.loads((ROOT / "cms-slice/data-sources/local-programs.json").read_text())["resources"]["shine"]
    checks = []
    for key in ("phone", "tty"):
        if current[key] != data["statewide"][key]["value"]:
            raise ValueError("Existing statewide contact conflict")
        checks.append({"field": key, "result": "same", "value": current[key]})
    for before, after in zip(current["sites"], data["sites"], strict=True):
        if before["name"] != after["name"] or before["phone"] != after["phone"]:
            raise ValueError("Existing site identity/contact conflict")
        checks.append({"site": after["id"], "name_phone": "same", "old_address": before["address"], "new_address": after["address"],
                       "address_delta": "Retain source-native spelling and ZIP; earlier abbreviated address is less detailed.",
                       "old_appointment": before["appointment"], "new_date_and_time": "By appointment only.",
                       "restriction": after["member_restriction"], "meaning": "No contact conflict; exact current appointment wording and ZIP captured in this reference."})
    surfaces = []
    surface_paths = ["cms-slice/apps/ten-question/readiness-content.json", "alternatives/chat-first/docs/product/readiness-triggers.json"]
    for path in surface_paths:
        obj = json.loads((ROOT / path).read_text())
        def records(v):
            if isinstance(v, dict):
                if v.get("id") == "S27" and v.get("title") == "Florida SHINE":
                    yield v
                for x in v.values():
                    yield from records(x)
            elif isinstance(v, list):
                for x in v:
                    yield from records(x)
        matches = list(records(obj))
        if len(matches) != 1 or matches[0]["url"] != "https://www.floridashine.org/":
            raise ValueError("Unexpected surface source route")
        surfaces.append({"path": path, "sha256": digest(ROOT / path), "source": matches[0],
                         "comparison": "Generic SHINE Who We Are reference agrees with captured homepage; exact current L15 reference is not bound into either UI.",
                         "ui_edited": False, "rendered_ui_checked": False})
    prior = ROOT / "docs/data/l12-help-with-costs-2026-10-28/acquisition-r1"
    rechecks = []
    protected = [ROOT / "cms-slice/data-sources/local-programs.json", ROOT / "cms-slice/scripts/local_programs.py", ROOT / "cms-slice/tests/test_local_programs.py"]
    protected += [ROOT / path for path in surface_paths]
    for sid, oldid in (("P26-S57", "shine-contact"), ("P26-S58", "shine-collier")):
        receipt_path = prior / "receipts" / (oldid + ".json")
        receipt = json.loads(receipt_path.read_text())
        old_raw = ROOT / receipt["path"]
        if digest(old_raw) != receipt["sha256"]:
            raise ValueError("Prior source changed")
        before = Tree(old_raw.read_text()).root.text()
        after = Tree((ACQUISITION / (sid + ".html")).read_text()).root.text()
        if before != after:
            raise ValueError("Yesterday's source text differs; inspect before closing")
        rechecks.append({"source_id": sid, "prior_checked_at_utc": receipt["retrieved_at_utc"], "current_checked_at_utc": next(r["retrieved_at_utc"] for r in data["sources"] if r["id"] == sid),
                         "visible_text": "identical", "raw_bytes": "different ASP.NET state bytes; source text unchanged"})
        protected += [receipt_path, old_raw, prior / "text" / (oldid + ".txt"), prior / "text" / (oldid + ".json")]
    result = {"contact_comparisons": checks, "surface_comparisons": surfaces, "prior_source_comparisons": rechecks,
              "R20": "mechanical comparison complete; no unresolved material contact semantics; actual human fields remain empty",
              "source_use": {"access": "Public GET, no login, form submission or challenge-image request", "copyright": "Publisher copyright notice retained. Footer speech-widget licensing is not treated as a license for the whole directory.",
                             "consumer_reuse_decision": "pending exact release review; public access does not supply acceptance"},
              "protected_files": {str(path.relative_to(ROOT)): digest(path) for path in protected}}
    save(BUILD / "reuse-audit.json", result)
    return result


def seal():
    if (BASE / "manifest.json").exists():
        raise ValueError("Reference already sealed; use a new revision")
    validate(json.loads((BUILD / "directory.json").read_text()))
    if json.loads((BUILD / "tests.json").read_text())["result"] != "pass":
        raise ValueError("Tests must pass before sealing")
    protected = json.loads((BUILD / "reuse-audit.json").read_text())["protected_files"]
    if any(digest(ROOT / path) != value for path, value in protected.items()):
        raise ValueError("A preserved input changed")
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "replay"
        build(out)
        replay = {name: {"original": digest(BUILD / name), "replay": digest(out / name)} for name in ("directory.json", "validation.json")}
        if any(v["original"] != v["replay"] for v in replay.values()):
            raise ValueError("Replay differs")
    save(BUILD / "replay.json", {"result": "pass", "files": replay})
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name not in {"manifest.json", "CURRENT_REFERENCE.json"})
    files += [Path(__file__), ROOT / "cms-slice/scripts/l15_acquire.py", ROOT / "cms-slice/tests/test_l15_reference.py"]
    save(BASE / "manifest.json", {"reference_id": "L15-PUBLISHED-COLLIER-2026-10-29-r1", "human_acceptance": None, "consumer_release": False,
                                  "files": {str(p.relative_to(ROOT)): digest(p) for p in files}})
    save(BASE / "CURRENT_REFERENCE.json", {"reference_id": "L15-PUBLISHED-COLLIER-2026-10-29-r1", "manifest_sha256": digest(BASE / "manifest.json"),
                                           "directory": "build-r1/directory.json", "published_directory_collection_complete": True, "consumer_release": False, "human_acceptance": None})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["build", "verify", "audit", "seal"])
    p.add_argument("--output", type=Path, default=BUILD)
    a = p.parse_args()
    if a.command == "audit":
        result = audit()
        print(json.dumps({"R20": result["R20"], "protected_files": len(result["protected_files"])}))
        raise SystemExit(0)
    if a.command == "seal":
        seal()
    data = build(a.output) if a.command == "build" else load(research_mode=True)
    print(json.dumps({"reference_id": data["reference_id"], "sites": data["site_count"], "technical_validation": data["status"]["technical_validation"]}))
