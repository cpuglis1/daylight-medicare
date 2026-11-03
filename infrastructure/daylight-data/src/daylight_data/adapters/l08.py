"""Composite provider/site/network evidence, preserving independent source grains."""
from decimal import Decimal
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .common import DomainProjection, sqlite_records
from .streaming import json_document_records

BASE = "docs/data/l08-provider-networks-2026-10-27"
DATABASES = (("wellcare-r5", "providers.sqlite3"),
             ("original-medicare-r6", "original-medicare.sqlite3"),
             ("hospital-reference-r7", "hospitals.sqlite3"))

FTS_TABLES = {"directory_search", "directory_search_data", "directory_search_idx",
              "directory_search_content", "directory_search_docsize", "directory_search_config"}


def excluded_fts_tables(db):
    definition = db.execute("SELECT sql FROM sqlite_master WHERE name='directory_search'").fetchone()
    if not definition or "CREATE VIRTUAL TABLE" not in definition[0].upper() or "USING FTS5" not in definition[0].upper():
        return set()
    return FTS_TABLES


def selected_tables(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        excluded = excluded_fts_tables(db)
        return tuple(name for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                     if name not in excluded)


def sizing_dispositions(root):
    path = Path(root).resolve() / BASE / "wellcare-r5/providers.sqlite3"
    result = []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        excluded = excluded_fts_tables(db)
        names = [name for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if name in excluded]
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            count = db.execute("SELECT count(*) FROM " + quoted).fetchone()[0]
            try:
                allocated = db.execute("SELECT coalesce(sum(pgsize),0) FROM dbstat WHERE name=?", (name,)).fetchone()[0]
            except sqlite3.OperationalError:
                allocated = None
            result.append({"source_path": str(path.relative_to(root)), "table": name,
                           "source_rows": count, "sqlite_btree_bytes": allocated,
                           "disposition": "derived_full_text_search_structure_retained_in_exact_raw_sqlite_archive",
                           "independent_source_facts": False,
                           "text_basis_imported_separately": "directory_pages"})
    return result


def iter_records(root):
    root = Path(root).resolve()
    for component, name in DATABASES:
        directory = root / BASE / component
        yield from sqlite_records(root, directory / name, "L08", selected_tables(directory / name))
        # Full raw SQLite capture retains FTS virtual/shadow bytes. Those are
        # derivative search structures, with no independent source facts.
        for extra in ("genuine-gaps.json", "sources.json", "catalog-selection.json",
                      "selection.json", "enrollment_resources.json", "optout_resources.json"):
            path = directory / extra
            if path.is_file():
                yield from json_document_records(root, path, "L08", path.stem)


def project_record(row):
    raw = dict(row.raw)
    fields = {}
    for key, value in raw.items():
        if key.endswith("_json") and isinstance(value, str):
            # A provider's structured participation period is not the loader's
            # scalar monetary amount_period. Preserve the complete object under
            # its domain name, with the native period_json retained in raw.
            target = "provider_period" if key == "period_json" else key[:-5]
            fields[target] = json.loads(value, parse_float=Decimal)
        else:
            fields[key] = value
    fields["reference_component"] = next(iter(row.source_path.split("/")[3:4]), "fixture_or_external_component")
    fields["identity_is_not_network_verification"] = True
    fields["personal_network_status_determined"] = False
    if fields.get("offering_id") and not str(fields["offering_id"]).startswith("2026:"):
        fields["source_offering_id"] = fields.pop("offering_id")
    conditions = {key: fields[key] for key in ("provider_period", "qualifiers", "state", "reason", "source_id", "source_row", "pointer") if key in fields}
    return DomainProjection(row, "provider_" + row.source_table.replace("-", "_"),
                            "L08:" + row.record_id, fields,
                            value_state=str(raw.get("state", "source_observed")),
                            conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
