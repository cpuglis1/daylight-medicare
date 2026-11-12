from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import platform
from importlib.metadata import version

from . import PlanTypeError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(), parse_float=Decimal)


def contained(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative,str):
        raise PlanTypeError("UNSAFE_ARTIFACT_PATH")
    path = root / relative
    if (not isinstance(relative, str) or Path(relative).is_absolute()
            or ".." in Path(relative).parts or not path.resolve().is_relative_to(root)
            or any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root))):
        raise PlanTypeError("UNSAFE_ARTIFACT_PATH")
    return path


def exact_date(value):
    if not isinstance(value, str):
        raise PlanTypeError("EXACT_ISO_DATE_REQUIRED")
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise PlanTypeError("EXACT_ISO_DATE_REQUIRED") from error
    if result.isoformat() != value:
        raise PlanTypeError("EXACT_ISO_DATE_REQUIRED")
    return value


def cents(value):
    if value is not None and type(value) is not int:
        raise PlanTypeError("INTEGER_CENTS_REQUIRED")
    return value


def code_binding():
    package = Path(__file__).parent
    return {p.name: file_sha(p) for p in sorted(package.glob("*.py"))} | {
        "schema.sql": file_sha(package / "schema.sql"),
        "runtime-requirements.lock":file_sha(package / "runtime-requirements.lock")}


def runtime_binding():
    pins={}
    for line in Path(__file__).with_name('runtime-requirements.lock').read_text().splitlines():
        name,expected=line.split('==')
        actual=version(name)
        if actual!=expected:
            raise PlanTypeError('RUNTIME_DEPENDENCY_MISMATCH:'+name)
        pins[name]=actual
    return {'python':platform.python_version(),'dependencies':pins}


def rate_holds(row, on_date=None):
    holds = set(row.get("holds") or [])
    if row["kind"] == "medigap_filed_rate":
        if row.get("source_status") != "APPROVED":
            holds.add("unapproved_or_replaced_source")
        if row.get("amount_cents") == 0:
            holds.add("source_zero_meaning_unresolved")
        start, end = row.get("effective_from"), row.get("effective_through")
        if not start or not end:
            holds.add("approved_rate_period_unresolved")
        if on_date:
            exact_date(on_date)
            if not on_date.startswith("2026-"):
                raise PlanTypeError("UNSUPPORTED_RESEARCH_DATE")
            if (start and on_date < str(start)) or (end and on_date > str(end)):
                holds.add("outside_sourced_rate_period")
    return sorted(holds)


def public_research_row(row, on_date=None):
    result = dict(row)
    result["holds"] = rate_holds(row, on_date)
    result["supported_rate_cents"] = (
        row.get("amount_cents") if row["kind"] == "medigap_filed_rate" and not result["holds"] else None)
    result.update(personal_quote=False, personal_eligibility="not_determined",
                  output_authority="held", current_sale="unknown")
    return json.loads(canonical(result))


def check_cms_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"2026:S\d{4}:\d{3}:\d{3}", value):
        raise PlanTypeError("INVALID_2026_PDP_ID")
    return value
