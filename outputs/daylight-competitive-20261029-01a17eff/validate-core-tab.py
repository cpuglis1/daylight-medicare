import json
import pathlib
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def snapshot(path):
    archive = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        shared = ["".join(n.itertext()) for n in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    names = [s.attrib["name"] for s in workbook.find("m:sheets", NS)]
    sheets = []
    errors = []
    for index, name in enumerate(names, 1):
        xml = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
        values, formulas = {}, {}
        for cell in xml.findall(".//m:c", NS):
            address = cell.attrib["r"]
            value = cell.find("m:v", NS)
            kind = cell.attrib.get("t")
            if kind == "inlineStr":
                text = "".join(cell.find("m:is", NS).itertext())
            elif value is None:
                text = None
            elif kind == "s":
                text = shared[int(value.text)]
            else:
                text = value.text
            if text is not None:
                values[address] = text
            formula = cell.find("m:f", NS)
            if formula is not None:
                formulas[address] = formula.text
            if kind == "e":
                errors.append([name, address, text])
        cols = [dict(c.attrib) for c in xml.findall("m:cols/m:col", NS)]
        heights = {r.attrib["r"]: r.attrib["ht"] for r in xml.findall("m:sheetData/m:row", NS) if "ht" in r.attrib}
        panes = [dict(p.attrib) for p in xml.findall("m:sheetViews/m:sheetView/m:pane", NS)]
        sheet_views = [dict(v.attrib) for v in xml.findall("m:sheetViews/m:sheetView", NS)]
        sheets.append({"name": name, "values": values, "formulas": formulas, "columns": cols, "heights": heights, "panes": panes, "views": sheet_views})
    return archive, sheets, errors


before_zip, before, before_errors = snapshot(ROOT / "evidence/before-core-tab.xlsx")
after_zip, after, after_errors = snapshot(ROOT / "Daylight competitive matrix.xlsx")
assert not before_errors and not after_errors, [before_errors, after_errors]
assert len(before) == 5 and len(after) == 6
assert [s["name"] for s in after[:5]] == [s["name"] for s in before]
preservation = {}
for old, new in zip(before, after):
    checks = {field: old[field] == new[field] for field in ["values", "formulas", "columns", "heights", "panes", "views"]}
    preservation[old["name"]] = checks
    assert all(checks.values()), [old["name"], checks]
old_tables = [ET.fromstring(before_zip.read(n)) for n in before_zip.namelist() if n.startswith("xl/tables/") and n.endswith(".xml")]
new_tables = [ET.fromstring(after_zip.read(n)) for n in after_zip.namelist() if n.startswith("xl/tables/") and n.endswith(".xml")]
for old in old_tables:
    new = next(t for t in new_tables if t.attrib["name"] == old.attrib["name"])
    assert ET.tostring(old) == ET.tostring(new), old.attrib["name"]
core = after[-1]
assert core["name"] == "Core differentiators"
research = json.loads((ROOT / "research.json").read_text())
marks = json.loads((ROOT / "core-capabilities.json").read_text())
allowed = {"✓ O", "✓ C", "✓ L", "△ O", "△ C", "△ L", "× O", "× C", "× L", "?", "T"}
for row, original in enumerate(research["rows"], 8):
    assert core["values"][f"A{row}"] == original[0]
    assert core["values"][f"B{row}"] == original[1]
    for index, column in enumerate("CDEFGHIJKL"):
        assert core["values"][f"{column}{row}"] == marks["rows"][row - 8][1][index]
        assert core["values"][f"{column}{row}"] in allowed
    assert core["values"][f"M{row}"]
    assert core["values"][f"O{row}"]
assert all(core["values"][f"{c}28"] == "T" for c in "CDEFGHIJKL")
assert all(core["values"][f"I{r}"] == core["values"][f"J{r}"] == "?" for r in range(8, 27))
notes = []
for name in after_zip.namelist():
    if name.startswith("xl/comments") and name.endswith(".xml"):
        notes.extend(ET.fromstring(after_zip.read(name)).findall("m:commentList/m:comment", NS))
assert len(notes) == 210, [len(notes), after_zip.namelist()]
core_xml = ET.fromstring(after_zip.read("xl/worksheets/sheet6.xml"))
assert len(core_xml.findall("m:conditionalFormatting/m:cfRule", NS)) == 11
assert len(core_xml.findall("m:dataValidations/m:dataValidation", NS)) == 1
result = {"worksheets": [s["name"] for s in after], "originalSheets": preservation, "originalNativeTablesPreserved": True, "alternatives": 21, "criteria": 10, "markedCells": 210, "criterionNotes": 210, "formulaErrors": after_errors, "newBrowserTests": 0, "newSourcesOnAddedTab": 3}
(ROOT / "core-tab-validation.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
