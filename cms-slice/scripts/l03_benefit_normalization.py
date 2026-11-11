"""Source-local hospital/office normalization candidates, never personal costs.

CMS native control readings are explicitly proposed, not universal enum decodes.
Carrier parsing accepts complete price-cell grammars, never a nearby number.
Full source bodies, selectors and unresolved conditions remain attached.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import re

SCHEMA = "l03-benefit-normalization/1"
VERSION = "hospital-office-r1"
FAMILIES = {"1a": "inpatient_hospital", "7a": "primary_care", "7d": "specialist"}
CONDITIONS = ("authorization", "referral", "network_and_setting", "deductible",
              "frequency_and_quantity", "covered_days", "shared_allowance",
              "qualification", "exclusion", "waiver_and_replacement")
MONEY = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
DAILY = re.compile(r"\$(?P<amount>" + MONEY + r")\s+copay\s+per\s+day"
                   r"(?::\s*days\s*|\s+for\s+days\s*)(?P<begin>\d+)"
                   r"(?:\s*-\s*(?P<end>\d+)|(?P<open>\s+and\s+beyond))", re.I)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def decimal_text(value):
    """Exact nonnegative decimal, without floats or context-dependent rounding."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Expected an exact decimal string or integer")
    text = str(value)
    if not re.fullmatch(MONEY, text):
        raise ValueError("Unsupported/empty decimal literal")
    digits = text.replace(",", "").split(".")
    whole = digits[0].lstrip("0") or "0"
    fraction = digits[1].rstrip("0") if len(digits) == 2 else ""
    return whole + ("." + fraction if fraction else "")


def day_number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError("Day boundary must be an explicit positive integer")
    result = int(value)
    if result < 1:
        raise ValueError("Day boundary must be positive")
    return result


def bind_native_identity(obj, offering):
    """Bridge only the source's numeric segment to its three-digit member ID."""
    year, contract, plan_id, segment = offering.split(":")
    if len(obj.get("pbp", [])) != 1:
        raise ValueError("Unexpected native plan container")
    plan = obj["pbp"][0]
    raw_segment = plan.get("segmentId")
    if type(raw_segment) is int and 0 <= raw_segment <= 999:
        canonical_segment = f"{raw_segment:03d}"
    elif isinstance(raw_segment, str) and re.fullmatch(r"\d{3}", raw_segment):
        canonical_segment = raw_segment
    else:
        raise ValueError("Unsupported native segment representation")
    if (year != "2026" or type(obj.get("contractYear")) is not int or obj["contractYear"] != 2026
            or plan.get("contractId") != contract or plan.get("planId") != plan_id or canonical_segment != segment):
        raise ValueError("Native plan identity mismatch")
    return {"offering_id": offering, "contract_year_raw": obj["contractYear"],
            "contract_raw": plan["contractId"], "plan_raw": plan["planId"],
            "segment_raw": raw_segment, "canonical_segment": canonical_segment,
            "bridge": "Only numeric segment zero-padding; no geographic applicability inferred"}


def schedule_issues(bands):
    issues, previous = [], None
    for index, band in enumerate(bands):
        begin, end = band["begin_day"], band["end_day"]
        if previous is not None:
            if previous.get("state") != "finite" or begin <= previous["value"]:
                issues.append("overlapping_or_unordered_day_bands")
            elif begin != previous["value"] + 1:
                issues.append("gap_in_day_bands")
        if end["state"] == "finite" and begin > end["value"]:
            issues.append("reversed_day_band")
        if end["state"] != "finite" and index != len(bands) - 1:
            issues.append("open_band_must_be_last")
        previous = end
    return sorted(set(issues))


def price_cell(text):
    """Parse the WHOLE cell. Unsupported qualifiers retain the whole unknown cell."""
    clean = re.sub(r"\s+", " ", text).strip().replace("\u2013", "-").replace("\u2014", "-")
    unknown = {"form": "unresolved", "raw_text": text,
               "issues": ["unsupported_complete_price_cell"], "amount": None}
    matches = list(DAILY.finditer(clean))
    if matches:
        position, bands = 0, []
        for match in matches:
            if clean[position:match.start()].strip():
                return unknown
            bands.append({"begin_day": day_number(match["begin"]),
                "end_day": {"state": "finite", "value": day_number(match["end"])} if match["end"] else {
                    "state": "open_source_phrase", "source_phrase": "and beyond",
                    "coverage_entitlement_established": False},
                "amount": decimal_text(match["amount"]), "unit": "USD/day"})
            position = match.end()
        if clean[position:].strip():
            return unknown
        return {"form": "day_schedule", "kind": "copayment", "bands": bands,
                "raw_text": text, "issues": schedule_issues(bands),
                "covered_day_limit": None, "reset_rule": {"state": "unresolved"}}
    match = re.fullmatch(r"\$(" + MONEY + r")\s*-\s*\$(" + MONEY + r")\s+copay", clean, re.I)
    if match:
        low, high = decimal_text(match[1]), decimal_text(match[2])
        return {"form": "range", "kind": "copayment", "minimum": low, "maximum": high,
                "unit": "USD", "denominator": {"state": "unresolved"}, "raw_text": text,
                "issues": ["range_requires_setting_and_condition_mapping"] + (
                    ["reversed_range"] if Decimal(low) > Decimal(high) else [])}
    match = re.fullmatch(r"\$(" + MONEY + r")\s+copay(?:\s+per\s+(visit|stay|day))?", clean, re.I)
    if match:
        return {"form": "amount", "kind": "copayment", "amount": decimal_text(match[1]),
                "unit": "USD", "denominator": match[2].lower() if match[2] else {"state": "unresolved"},
                "raw_text": text, "issues": []}
    match = re.fullmatch(r"(" + MONEY + r")%\s+coinsurance(?:\s+per\s+(visit|stay|day))?", clean, re.I)
    if match:
        amount = decimal_text(match[1])
        return {"form": "amount", "kind": "coinsurance", "amount": amount, "unit": "percent",
                "denominator": match[2].lower() if match[2] else {"state": "unresolved"},
                "charge_base": {"state": "unresolved"}, "raw_text": text,
                "issues": ["percentage_over_100"] if Decimal(amount) > 100 else []}
    return unknown


def native_flat(body, kind):
    """Component-specific proposal; control 2 never creates amount zero."""
    prefix = "bd" + ("Copayment" if kind == "copayment" else "Coinsurance")
    control = body.get(prefix + "AmountYesNoMinMax")
    result = {"kind": kind, "raw_component": copy.deepcopy(body), "control_raw": control,
              "control_interpretation": "proposed_component_specific_reading_requires_review",
              "unit": "USD" if kind == "copayment" else "percent",
              "denominator": {"state": "unresolved"}, "issues": []}
    try:
        if control == "1":
            result.update(form="amount", amount=decimal_text(body.get(prefix + "Amount")))
        elif control == "3":
            low, high = decimal_text(body.get(prefix + "MinAmount")), decimal_text(body.get(prefix + "MaxAmount"))
            result.update(form="range", minimum=low, maximum=high)
            result["issues"].append("range_requires_setting_and_condition_mapping")
            if Decimal(low) > Decimal(high):
                result["issues"].append("reversed_range")
        elif control == "2":
            result.update(form="cost_type_not_selected_candidate", amount=None)
            if any(body.get(prefix + suffix) not in (None, "") for suffix in ("Amount", "MinAmount", "MaxAmount")):
                result["issues"].append("populated_fields_under_no_cost_type_control")
        else:
            result.update(form="unresolved", amount=None)
            result["issues"].append("unsupported_or_missing_component_control")
        if result["unit"] == "percent" and any(Decimal(result[k]) > 100 for k in
                ("amount", "minimum", "maximum") if result.get(k) is not None):
            result["issues"].append("percentage_over_100")
    except ValueError as exc:
        result.update(form="unresolved", amount=None)
        result["issues"].append(str(exc))
    return result


def native_intervals(body, amount_field):
    """Read literal numbered fields; a native 999 endpoint always remains 999."""
    slots = sorted({int(m[1]) for key in body if (m := re.fullmatch(
        r"bdDayInterval(\d+)(?:BeginDay|EndDay|CopaymentAmount|CoinsurancePercentage)", key))})
    bands, issues = [], []
    other_amount = "CoinsurancePercentage" if amount_field == "CopaymentAmount" else "CopaymentAmount"
    if any(re.fullmatch(r"bdDayInterval\d+" + other_amount, key) and value not in (None, "")
           for key, value in body.items()):
        issues.append("unexpected_populated_interval_amount_type")
    for slot in slots:
        prefix = f"bdDayInterval{slot}"
        fields = [prefix + suffix for suffix in ("BeginDay", "EndDay", amount_field)]
        if all(body.get(field) in (None, "") for field in fields):
            continue
        try:
            bands.append({"slot": slot, "begin_day": day_number(body.get(fields[0])),
                          "end_day": {"state": "finite", "value": day_number(body.get(fields[1]))},
                          "amount": decimal_text(body.get(fields[2])),
                          "unit": "USD/day" if amount_field == "CopaymentAmount" else "percent/day"})
        except ValueError as exc:
            issues.append(f"incomplete_or_invalid_day_slot_{slot}: {exc}")
    issues.extend(schedule_issues(bands))
    return {"form": "day_schedule" if bands and not issues else "unresolved",
            "bands": bands, "issues": issues, "raw_component": copy.deepcopy(body),
            "covered_day_limit": None, "interval_count_interpretation": "unresolved_native_code",
            "reset_rule": {"state": "unresolved"}}


def native_hospital_component(body, kind):
    title = "Copayment" if kind == "copayment" else "Coinsurance"
    amount_field = "CopaymentAmount" if kind == "copayment" else "CoinsurancePercentage"
    result = {"form": "controlled_alternatives", "kind": kind,
              "raw_component": copy.deepcopy(body), "selection": {"state": "unresolved"},
              "alternatives_are_additive": False, "alternatives": [], "issues": []}
    for key, value in body.items():
        if re.fullmatch(f"bd{title}Tier\\d+(Amt|Percentage)", key) and value not in (None, ""):
            try:
                alternative = {"source_field": key, "form": "amount", "amount": decimal_text(value),
                    "unit": "USD" if kind == "copayment" else "percent",
                    "denominator": {"state": "unresolved"}, "activation": {"state": "unresolved"}}
            except ValueError as exc:
                alternative = {"source_field": key, "form": "unresolved", "raw_value": value, "issues": [str(exc)]}
            result["alternatives"].append(alternative)
        elif isinstance(value, dict) and re.fullmatch(f"bd{title}Tier\\d+DayInterval(Stay|Reserve)", key):
            schedule = native_intervals(value, amount_field)
            # Retain even blank schedules: absence is not interpreted as zero.
            schedule.update(source_field=key, stay_or_reserve="reserve" if key.endswith("Reserve") else "stay",
                            activation={"state": "unresolved"})
            result["alternatives"].append(schedule)
    if not result["alternatives"]:
        result["issues"].append("no_populated_scalar_or_interval_candidate")
    return result


def base_record(offering, side, family, source, raw, context):
    return {"schema": SCHEMA, "adapter_version": VERSION,
            "id": "NORM-" + fingerprint([offering, side, family, source, raw])[:28],
            "offering_id": offering, "source_side": side, "family": family,
            "source": copy.deepcopy(source), "raw_source": copy.deepcopy(raw),
            "context": copy.deepcopy(context), "cost_components": [],
            "conditions": {key: {"state": "unresolved", "reason": "Full source-specific interpretation/review required"}
                           for key in CONDITIONS},
            "exceptions": {"state": "unresolved"}, "shared_budgets": {"state": "unresolved"},
            "holds": ["independent_source_interpretation_review_required", "complete_material_conditions_required",
                      "geographic_applicability_unresolved"],
            "normalization_scope": "source_local_parser_candidate",
            "originals_completed": 0, "accepted_for_reference": False,
            "consumer_usable": False, "calculation_ready": False}


def normalize_native(offering, row, source, plan_context):
    if source.get("raw_object_sha256") != fingerprint(row):
        raise ValueError("Native object does not match its provenance fingerprint")
    category = row.get("categoryCode")
    if category not in FAMILIES:
        raise ValueError("Unsupported service category; keep it outside this adapter scope")
    details = row.get("benefitDetails")
    if not isinstance(details, dict):
        raise ValueError("Missing native benefit object")
    record = base_record(offering, "cms", FAMILIES[category], source, row,
        {"network": {"state": "unresolved", "source_scope": "default_native_component"},
         "setting": {"state": "unresolved"}, "category_code": category,
         "category_type_raw": row.get("categoryTypeId")})
    record["plan_context_raw"] = copy.deepcopy(plan_context)
    record["holds"].append("native_control_and_parent_activation_mapping_requires_review")
    handled = set()
    for component, body in details.items():
        if not isinstance(body, dict):
            continue
        if category == "1a" and component in {"TierCopaymentComponent", "TierCoinsuranceComponent"}:
            value = native_hospital_component(body, "copayment" if component == "TierCopaymentComponent" else "coinsurance")
        elif category in {"7a", "7d"} and component in {"CopaymentComponent", "CoinsuranceComponent"}:
            value = native_flat(body, "copayment" if component == "CopaymentComponent" else "coinsurance")
        else:
            continue
        handled.add(component)
        value["source_pointer"] = source["pointer"] + "/benefitDetails/" + component
        value["component"] = component
        record["cost_components"].append(value)
    record["retained_uninterpreted_components"] = sorted(set(details) - handled)
    if record["retained_uninterpreted_components"]:
        record["holds"].append("additional_native_components_retained_for_interpretation")
    if not record["cost_components"]:
        record["holds"].append("no_supported_cost_component")
    record["condition_source_index"] = {
        "authorization": [source["pointer"] + "/benefitDetails/PriorAuthorizationReferralNmBenefitComponent",
                          "/pbp/0/priorAuthorizationAndReferral"],
        "referral": [source["pointer"] + "/benefitDetails/PriorAuthorizationReferralNmBenefitComponent",
                     "/pbp/0/priorAuthorizationAndReferral"],
        "deductible": ["/pbp/0/planLevelCostSharing", source["pointer"] + "/benefitDetails"],
        "shared_allowance": ["/pbp/0/costShareGroups"],
        "qualification": ["/pbp/0/vbid", "/pbp/0/benefitOfferings"],
    }
    record["condition_source_index_scope"] = "Navigation to retained source containers; paths may be absent and do not prove applicability or complete conditions"
    validate_record(record)
    return record


def unique_line(lines, pattern, *, start=0, end=None, label="anchor"):
    matches = [i for i in range(start, len(lines) if end is None else end) if re.search(pattern, lines[i])]
    if len(matches) != 1:
        raise ValueError(f"Expected one {label}, found {len(matches)}")
    return matches[0]


def cell_record(profile, page, family, start, end, left, right, network, setting=None):
    field = profile["text_field"]
    lines = page[field].splitlines()
    cells = [line[left:right] for line in lines[start:end]]
    quote = "\n".join(cells)
    source = {"document_sha256": page["document_sha256"], "pdf_page": page["pdf_page"],
        "page_record_sha256": fingerprint(page), "text_field": field,
        "text_field_sha256": hashlib.sha256(page[field].encode()).hexdigest(),
        "line_start": start + 1, "line_end": end, "column_start": left, "column_end": right,
        "price_cell_quote": quote, "price_cell_sha256": hashlib.sha256(quote.encode()).hexdigest(),
        "full_row_quote": "\n".join(lines[start:end]), "layout_profile_id": profile["id"]}
    record = base_record(profile["offering_id"], "carrier", family, source, {"text": quote},
        {"network": network, "setting": setting or {"state": "unresolved"}})
    record["cost_components"] = [price_cell(quote)]
    record["holds"] += ["SB_summary_requires_EOC_and_footnote_reconciliation",
                        "source_column_and_layout_profile_requires_independent_review"]
    validate_record(record)
    return record


def normalize_carrier(profile, page):
    """Only the carrier page/profile is accepted; no CMS expectations argument."""
    if page["document_sha256"] != profile["document_sha256"] or page["pdf_page"] != profile["pdf_page"]:
        raise ValueError("Carrier page identity mismatch")
    if profile["text_field"] not in page:
        raise ValueError("Required source layout text unavailable")
    lines = page[profile["text_field"]].splitlines()
    records = []
    if profile["layout"] == "network_columns":
        header = unique_line(lines, r"^\s*In-network\s+Out-of-network\s*$", label="network header")
        padding = profile.get("header_padding", 0)
        if type(padding) is not int or not 0 <= padding <= 3:
            raise ValueError("Unsupported source header padding")
        left = lines[header].index("In-network") - padding
        middle = lines[header].index("Out-of-network") - padding
        if left < 0 or middle <= left:
            raise ValueError("Invalid source column bounds")
        for family, anchors in profile["rows"].items():
            labels = [line[:left] for line in lines]
            start = unique_line(labels, anchors["start"], start=header + 1)
            end = unique_line(labels, anchors["end"], start=start + 1)
            # Cell slicing is only safe when each first price starts under its header.
            for column_start, column_end, network in ((left, middle, "in_network"), (middle, None, "out_of_network")):
                first = lines[start][column_start:column_end].lstrip()
                if not re.match(r"(?:\$|\d+%)", first):
                    raise ValueError("Price cell shifted outside its named network column")
                records.append(cell_record(profile, page, family, start, end, column_start, column_end,
                    {"state": "source_header", "value": network, "header_line": header + 1}))
    elif profile["layout"] == "label_value_rows":
        # Bounds come from a source layout profile, never a CMS expected amount.
        for family, anchors in profile["rows"].items():
            start = unique_line(lines, anchors["start"])
            if anchors.get("end_at_blank"):
                end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), None)
                if end is None:
                    raise ValueError("Missing end of source row")
            else:
                end = unique_line(lines, anchors["end"], start=start + 1)
            column = anchors["price_column"]
            if family == "inpatient_hospital":
                if any("$" in line[:column] for line in lines[start:end]):
                    raise ValueError("Price outside selected source column")
                records.append(cell_record(profile, page, family, start, end, column, None,
                    {"state": "proposed_document_scope", "value": "in_network", "review_complete": False}))
            else:
                for index in range(start, end):
                    cell = lines[index][column:]
                    match = re.fullmatch(r"\s*•\s*(PCP's office|Specialist's office|Telehealth):\s*(.+?)\s*", cell)
                    if not match:
                        raise ValueError("Unsupported office/telehealth row; do not select a nearby amount")
                    offset = column + match.start(2)
                    record = cell_record(profile, page, family, index, index + 1, offset, None,
                        {"state": "proposed_document_scope", "value": "in_network", "review_complete": False},
                        {"state": "source_label", "value": match[1]})
                    record["source"]["setting_cell_quote"] = cell
                    records.append(record)
    else:
        raise ValueError("Unsupported carrier layout profile")
    return records


def validate_record(record):
    if record["schema"] != SCHEMA or record["family"] not in FAMILIES.values():
        raise ValueError("Unsupported normalization record")
    if set(record["conditions"]) != set(CONDITIONS) or not record["holds"]:
        raise ValueError("Missing material-condition/review boundary")
    if any(v.get("state") != "unresolved" for v in record["conditions"].values()):
        raise ValueError("This parser revision cannot establish condition dispositions")
    if record.get("exceptions") != {"state": "unresolved"} or record.get("shared_budgets") != {"state": "unresolved"}:
        raise ValueError("Exceptions and shared budgets require separate complete interpretation")
    if any(record.get(k) is not False for k in ("accepted_for_reference", "consumer_usable", "calculation_ready")):
        raise ValueError("Normalization cannot grant release or calculation readiness")
    if record.get("originals_completed") != 0:
        raise ValueError("Source parser cannot complete canonical originals")
    if not record.get("raw_source") or not record.get("source"):
        raise ValueError("Complete raw source and provenance are required")


def family_diagnostics(records):
    """Inspection aid only. Never equate a range endpoint with a headline price."""
    result = []
    for offering in sorted({r["offering_id"] for r in records}):
        for family in FAMILIES.values():
            group = [r for r in records if r["offering_id"] == offering and r["family"] == family]
            result.append({"offering_id": offering, "family": family,
                "cms_candidate_ids": [r["id"] for r in group if r["source_side"] == "cms"],
                "carrier_candidate_ids": [r["id"] for r in group if r["source_side"] == "carrier"],
                "outcome": "insufficient_evidence", "reason": "Complete context, conditions and independently reviewed mapping remain required",
                "numeric_agreement_asserted": False, "accepted_for_reference": False,
                "originals_completed": 0})
    return result
