"""Offline, exact-input preparation; no network, PDF parsing or acceptance writes."""
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import ijson

from . import VERSION, SCOPE, PlanTypeError
from .common import canonical, cents, check_cms_id, code_binding, contained, digest, exact_date, file_sha, read_json
from .common import rate_holds, runtime_binding


def base_item(source, pointer, kind, payload, key=None, **typed):
    item = dict(kind=kind, entity_key=str(key if key is not None else pointer),
                source_pointer=pointer, payload=payload, payload_sha256=digest(payload),
                value_state="source_observed", holds=[], conditions={})
    item.update(typed)
    item["item_id"] = digest([source["source_id"], pointer, kind])
    return item


def normalize(source, pointer, role, raw):
    """Preserve the whole native payload; typed values never establish applicability."""
    key = raw.get("id", pointer) if isinstance(raw, dict) else pointer
    if not isinstance(raw, dict):
        raw = {"source_value": raw}
    if role == "pdp":
        identifier = check_cms_id(raw["offering_id"])
        yield base_item(source, pointer, "pdp_offering", raw, identifier,
                        cms_offering_id=identifier, region=str(raw["region"]))
        for name, value in raw["fields"].items():
            amount = cents(value["value"]) if value.get("value_encoding") == "integer_cents" else None
            yield base_item(source, pointer+"/fields/"+name, "pdp_field", value,
                identifier+":"+name, cms_offering_id=identifier, region=str(raw["region"]),
                amount_cents=amount, unit=value.get("unit") if amount is not None else None,
                basis=value.get("basis"), value_state=value["state"])
        return
    if role == "pdp_county":
        yield base_item(source, pointer, role, raw, raw["fips"],
                        county_fips=raw["fips"], region=str(raw["region"]))
        return
    if role == "pdp_restriction":
        identifier = check_cms_id(raw["offering_id"])
        yield base_item(source, pointer, role, raw, identifier, cms_offering_id=identifier)
        return
    if role in {"medigap_variant", "medigap_benefit", "medigap_condition"}:
        variant = raw.get("variant")
        key = key if role != "medigap_variant" else variant
        if role == "medigap_benefit":
            key = variant+":"+raw["benefit"]
        yield base_item(source, pointer, role, raw, key, variant=variant,
                        conditions={"condition_ids": raw.get("condition_ids", [])})
        return
    if role == "medigap_product_lead":
        yield base_item(source, pointer, role, raw, key, variant=raw["variant"],
            company_name=raw["company_name_raw"], naic=raw.get("naic"),
            policy_form=raw.get("policy_form"),
            holds=["current_sale_unknown", "complete_product_identity_unresolved"],
            conditions={k: raw.get(k) for k in ("source_group_type","select","listing_ids","evidence_basis")})
        return
    if role in {"medigap_listing", "medigap_insurer", "medigap_illustration"}:
        payload = json.loads(raw["payload"], parse_float=Decimal)
        payload["source_columns"] = {k:v for k,v in raw.items() if k!='payload'}
        if role == "medigap_illustration":
            yield base_item(source, pointer, role, payload, raw["id"],
                amount_cents=cents(raw["annual_cents"]), unit="USD/year",
                basis="illustrative_public_comparison", holds=["illustration_only","exact_form_and_rate_period_unknown"],
                conditions={"listing_id": raw["listing_id"], "synthetic_inputs": payload["synthetic_inputs"],
                            "county_context": "12021", "county_basis": "selected_OIR_Collier_sample_not_residency_or_sale"})
        else:
            yield base_item(source, pointer, role, payload, raw.get("id", raw.get("name")),
                variant=payload.get("variant"), naic=payload.get("naic",payload.get("exact_name_unique_naic")),
                company_name=payload.get("company_name_raw"), policy_form=payload.get("policy_form"),
                holds=["current_sale_unknown"])
        return
    if role == "medigap_monthly_rate":
        yield base_item(source, pointer, role, raw, pointer, variant=raw["variant"],
            county_fips=raw["county_fips"], rating_area=raw["rating_area"],
            amount_cents=cents(raw["premium_cents"]), unit="USD/month", basis=raw["payment_basis"],
            holds=["published_table_only","exact_form_and_approved_rate_period_unresolved"] +
                  (["automatic_payment_precision_and_conditions_unresolved"] if raw["payment_basis"] != "regular_monthly" else []),
            conditions={k: raw.get(k) for k in ("age_band_raw","tobacco","select","source_edition_year","actual_filed_rate_effective_date")})
        return
    if role == "medigap_schedule":
        fields = raw["fields"]
        start, end = raw.get("rate_effective_from"), raw.get("rate_effective_through")
        yield base_item(source, pointer, role, raw, raw["id"],
            company_name=fields.get("Issuing Carrier",fields.get("Filing Company")), policy_form=fields.get("Form Number"),
            rating_area=fields.get("Region"), source_status=raw["status"],
            effective_from=exact_date(start) if start else None,
            effective_through=exact_date(end) if end else None,
            conditions={"policy_issue_dates_are_not_rate_periods": True,
                        "fields": fields, "form_edition": "unresolved", "county_applicability": "unknown"})
        return
    if role == "medigap_filed_rate":
        start, end = raw.get("rate_effective_from"), raw.get("rate_effective_through")
        item = base_item(source, pointer, role, raw, raw["id"],
            schedule_key=raw["schedule_id"], source_status=raw["source_status"],
            amount_cents=cents(raw["annual_premium_cents"]), unit="USD/year", basis="filed_annual_source_cell",
            effective_from=exact_date(start) if start else None,
            effective_through=exact_date(end) if end else None,
            conditions={k: raw.get(k) for k in ("age_raw","sex_raw","class_raw","source_page","source_pdf_sha256","zero_meaning")})
        item['holds'] = rate_holds(item)
        yield item
        return
    yield base_item(source, pointer, "source_document" if role == "document" else "research_item", raw, key)


def input_rows(root, spec):
    path = contained(root, spec["path"])
    if spec["format"] == "sqlite":
        with sqlite3.connect("file:"+str(path)+"?mode=ro&immutable=1", uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            for table, role in spec["tables"].items():
                if table not in {"counties","illustrations","listings","insurers","filing_metadata"}:
                    raise PlanTypeError("UNSUPPORTED_SOURCE_TABLE")
                columns = db.execute('PRAGMA table_info("'+table+'")').fetchall()
                keys = [c["name"] for c in sorted(columns,key=lambda c:c["pk"]) if c["pk"]]
                order = ",".join('"'+k+'"' for k in keys) or "rowid"
                for n, row in enumerate(db.execute('SELECT * FROM "'+table+'" ORDER BY '+order)):
                    yield "/tables/"+table+"/"+str(n), role, dict(row)
    elif spec["format"] == "array":
        with path.open("rb") as handle:
            for n, raw in enumerate(ijson.items(handle,"item")):
                yield "/"+str(n), spec["role"], raw
    elif spec["format"] == "object":
        raw = read_json(path)
        yield "", "document", raw
        for key, role in spec.get("children", {}).items():
            for n, child in enumerate(raw[key]):
                yield "/"+key+"/"+str(n), role, child
    else:
        raise PlanTypeError("UNSUPPORTED_SOURCE_FORMAT")


def verify_selection(root, selection):
    if selection["scope"] != SCOPE or selection["consumer_release"] != "held":
        raise PlanTypeError("UNSUPPORTED_SELECTION_SCOPE")
    if len({s["path"] for s in selection["sources"]}) != len(selection["sources"]):
        raise PlanTypeError("DUPLICATE_SOURCE_PATH")
    for spec in selection["parents"] + selection["sources"]:
        if file_sha(contained(root,spec["path"])) != spec["sha256"]:
            raise PlanTypeError("SOURCE_HASH_MISMATCH:"+spec["path"])


def prepare(root, selection_path, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    selection = read_json(selection_path)
    verify_selection(root, selection)
    execution_code, execution_runtime = code_binding(), runtime_binding()
    if shutil.disk_usage(output.parent).free < 7*1024**3:
        raise PlanTypeError("SEVEN_GIB_RESERVE_REQUIRED")
    output.mkdir(mode=0o700)  # Existing output is never overwritten.
    counts, sources = Counter(), []
    for spec in selection["sources"]:
        source = dict(spec, source_id=digest([spec["path"],spec["sha256"]]))
        stream = source["source_id"]+".jsonl.gz"
        stream_hash, total, raw_rows = hashlib.sha256(), 0, 0
        with (output/stream).open("xb") as target, gzip.GzipFile(filename="",fileobj=target,mode="wb",mtime=0) as handle:
            for pointer, role, raw in input_rows(root,spec):
                raw_rows += 1
                for item in normalize(source,pointer,role,raw):
                    encoded = (canonical(item)+"\n").encode()
                    handle.write(encoded); stream_hash.update(encoded)
                    total += 1; counts[item["kind"]] += 1
        sources.append(dict(source,stream=stream,stream_sha256=stream_hash.hexdigest(),
                            compressed_sha256=file_sha(output/stream),item_count=total,source_rows=raw_rows))
    verify_selection(root,selection)  # Detect changed inputs during preparation.
    if code_binding()!=execution_code or runtime_binding()!=execution_runtime:
        raise PlanTypeError('EXECUTION_CHANGED_DURING_PREPARATION')
    if any(counts.get(k,0)!=n for k,n in selection.get('expected_counts',{}).items()):
        raise PlanTypeError('SELECTED_POPULATION_MISMATCH')
    manifest = {"contract":VERSION,"scope":dict(SCOPE),"consumer_release":"held",
                "selection_sha256":file_sha(selection_path),"parents":selection["parents"],
                "source_policy":selection["source_policy"],"code":execution_code,"runtime":execution_runtime,
                "sources":sources,"counts":dict(sorted(counts.items())),
                "review_due":selection["review_due"],"all_market_complete":False}
    manifest["build_id"] = digest(manifest)
    with (output/"manifest.json").open("x") as handle:
        handle.write(canonical(manifest)+"\n")
    return manifest


def verify_bundle(bundle, *, verify_code=True):
    bundle = Path(bundle)
    manifest = read_json(bundle/"manifest.json")
    unsigned = {k:v for k,v in manifest.items() if k != "build_id"}
    if (digest(unsigned) != manifest["build_id"] or manifest["contract"] != VERSION
            or manifest["scope"] != SCOPE or manifest["consumer_release"] != "held"
            or (verify_code and (manifest["code"] != code_binding() or manifest['runtime']!=runtime_binding()))):
        raise PlanTypeError("BUNDLE_BINDING_MISMATCH")
    for source in manifest["sources"]:
        if file_sha(contained(bundle,source["stream"])) != source["compressed_sha256"]:
            raise PlanTypeError("BUNDLE_STREAM_CHANGED")
    return manifest


def stream_items(bundle, source):
    checksum, count = hashlib.sha256(), 0
    with gzip.open(contained(bundle,source["stream"]),"rb") as handle:
        for line in handle:
            checksum.update(line); count += 1
            item = json.loads(line)
            if item["payload_sha256"] != digest(item["payload"]):
                raise PlanTypeError("PAYLOAD_HASH_MISMATCH")
            yield item
    if count != source["item_count"] or checksum.hexdigest() != source["stream_sha256"]:
        raise PlanTypeError("STREAM_ACCOUNTING_MISMATCH")
