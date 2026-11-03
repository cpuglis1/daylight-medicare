"""Published Medigap listings and separate exact filing grids; no personal quotes."""
from decimal import Decimal
import json
from pathlib import Path

from .common import DomainProjection, sqlite_records
from .streaming import json_document_records

BASE = "docs/data/l10-medigap-2026-10-28"
OVERLAYS = ("filing-reconciliation-r3/build-r1", "gap-resolution-r4/build-r1",
            "targeted-filings-r5/build-r1")


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / "build-r2/inventory.sqlite3", "L10")
    for component in OVERLAYS:
        for path in sorted((root / BASE / component).glob("*.json")):
            if "manifest" not in path.name and "validation" not in path.name:
                yield from json_document_records(root, path, "L10", path.stem)


def project_record(row):
    raw = dict(row.raw)
    payload = json.loads(raw["payload"], parse_float=Decimal) if isinstance(raw.get("payload"), str) else raw
    fields = dict(payload) if isinstance(payload, dict) else {"source_value": payload}
    fields["source_columns"] = {k: v for k, v in raw.items() if k != "payload"}
    fields["reference_component"] = row.source_path.split("/")[3:-1]
    fields["personal_quote"] = False
    fields["personal_eligibility_determined"] = False
    cents = raw.get("annual_premium_cents", raw.get("annual_cents"))
    if cents is not None:
        fields.update(amount_decimal=Decimal(cents) / Decimal(100), unit="USD/year",
                      period="annual", basis="exact_source_annual_rate_observation",
                      source_zero_meaning=raw.get("zero_meaning"))
    # Source dates can describe past/replaced rates or future issue cohorts.
    # Retain them under their source names; do not relabel everything as 2026.
    if fields.get("benefit_year") != 2026 and "benefit_year" in fields:
        fields["source_benefit_year"] = fields.pop("benefit_year")
    conditions = {k: payload[k] for k in ("conditions", "qualifications", "rate_effective_from", "rate_effective_through",
                  "source_status", "schedule_id", "age_raw", "sex_raw", "class_raw", "fields", "policy_issue_dates_are_not_rate_periods")
                  if isinstance(payload, dict) and k in payload}
    return DomainProjection(row, "medigap_" + row.source_table.replace("-", "_"),
                            "L10:" + row.record_id, fields,
                            value_state="source_observed", conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
