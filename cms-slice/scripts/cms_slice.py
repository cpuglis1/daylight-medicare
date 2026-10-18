#!/usr/bin/env python3
"""Pinned, read-only CMS source experiment. Standard library; no customer data."""

import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
ABSENT = object()
KEY_COLUMNS = ("Contract Year", "Contract ID", "Plan ID", "Segment ID")
GEO_COLUMNS = ("State Territory Abbreviation", "County Name")
FILENAME = re.compile(r"([A-Z]\d{4})-(\d{3})-(\d{3})-(\d{4})\.json")
CURRENCY = re.compile(r"\$(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{2})")


class SourceError(ValueError):
    """An input is unsupported, corrupt, ambiguous, or structurally changed."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def identity(year, contract, plan, segment):
    # Only segment encoding differs in the observed files. Never integer-cast plan IDs.
    if not isinstance(year, (str, int)) or isinstance(year, bool) or not re.fullmatch(r"\d{4}", str(year)):
        raise SourceError(f"Invalid contract year: {year!r}")
    if not isinstance(contract, str) or not re.fullmatch(r"[A-Z]\d{4}", contract):
        raise SourceError(f"Invalid contract ID: {contract!r}")
    if not isinstance(plan, str) or not re.fullmatch(r"\d{3}", plan):
        raise SourceError(f"Plan ID must preserve three source characters: {plan!r}")
    if not isinstance(segment, (str, int)) or isinstance(segment, bool) or not re.fullmatch(r"\d{1,3}", str(segment)):
        raise SourceError(f"Invalid segment: {segment!r}")
    return (str(year), contract, plan, str(segment).zfill(3))


def member_for(key):
    year, contract, plan, segment = key
    return f"{contract}-{plan}-{segment}-{year}.json"


def key_object(key):
    return dict(zip(("year", "contract", "plan", "segment_join"), key))


def pointer(document, path):
    item = document
    for token in path.removeprefix("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(item, dict) and token in item:
            item = item[token]
        elif isinstance(item, list) and token.isdigit() and int(token) < len(item):
            item = item[int(token)]
        else:
            return ABSENT
    return item


def cell(raw, evidence=None):
    if raw is ABSENT:
        result = {"state": "absent"}
    elif raw is None:
        result = {"raw": None, "state": "json_null"}
    elif isinstance(raw, str) and not raw.strip():
        result = {"raw": raw, "state": "empty"}
    elif isinstance(raw, str) and raw.strip() in ("Not Applicable", "Not Available"):
        result = {"raw": raw, "state": {"Not Applicable": "not_applicable", "Not Available": "not_available"}[raw.strip()]}
    else:
        result = {"raw": raw, "state": "value", "value": raw}
    if evidence is not None:
        result["evidence"] = evidence
    return result


def money(raw, evidence=None, allow_negative=False):
    result = cell(raw, evidence)
    result["value_cents"] = None
    result.pop("value", None)
    if result["state"] != "value":
        return result
    token = raw.strip() if isinstance(raw, str) else ""
    negative = token.startswith("(") and token.endswith(")")
    if negative:
        token = token[1:-1]
    if not CURRENCY.fullmatch(token):
        result.update(state="rejected", reason="unrecognized_currency_encoding")
    elif negative and not allow_negative:
        result.update(state="rejected", reason="unexpected_negative_amount")
    else:
        result["value_cents"] = int(Decimal(token.replace("$", "").replace(",", "")) * 100) * (-1 if negative else 1)
    return result


class Sources:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.manifest = load_json(self.root / "data-sources/release.json")
        self.markets = load_json(self.root / "data-sources/markets.json")
        self.mapping = load_json(self.root / "data-sources/field-mapping.json")

    def path(self, artifact):
        return self.root / self.manifest["artifacts"][artifact]["path"]

    def verify_artifact(self, artifact):
        spec = self.manifest["artifacts"][artifact]
        path = self.path(artifact)
        if not path.is_file():
            raise SourceError(f"Missing {artifact}: {path}. Run fetch, or copy the pinned archive here.")
        if path.stat().st_size != spec["bytes"] or file_hash(path) != spec["sha256"]:
            raise SourceError(f"Checksum/size mismatch for {artifact}; refusing changed release: {path}")

    def verify(self):
        for artifact in self.manifest["artifacts"]:
            self.verify_artifact(artifact)

    def fetch(self):
        # Never overwrite a changed cache or accept whatever a mutable URL now returns.
        for artifact, spec in self.manifest["artifacts"].items():
            path = self.path(artifact)
            if path.exists():
                self.verify_artifact(artifact)
                print(f"Verified cached {artifact}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "MedicareCMSResearchSlice/1.0"})
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
                temporary = Path(tmp.name)
            try:
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                    received_at = datetime.now(timezone.utc).isoformat()
                    headers = {k: response.headers.get(k) for k in ("Last-Modified", "ETag", "Content-Type")}
                    actual_url = response.url
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > spec["bytes"]:
                            raise SourceError(f"Download larger than pinned {artifact}; release review required")
                        output.write(chunk)
                if temporary.stat().st_size != spec["bytes"] or file_hash(temporary) != spec["sha256"]:
                    raise SourceError(f"Downloaded {artifact} differs from pinned release; not installed")
                os.replace(temporary, path)
                write_json(path.with_suffix(".receipt.json"), {
                    "requested_url": spec["url"], "final_url": actual_url, "received_at_utc": received_at,
                    "headers": headers, "sha256": spec["sha256"], "bytes": spec["bytes"],
                })
                print(f"Downloaded and verified {artifact}")
            finally:
                temporary.unlink(missing_ok=True)

    def archive(self, artifact):
        return zipfile.ZipFile(self.path(artifact))

    def locator(self, artifact, member, member_hash, **extra):
        return {"artifact": artifact, "archive_sha256": self.manifest["artifacts"][artifact]["sha256"],
                "member": member, "member_sha256": member_hash, **extra}

    def landscape(self):
        spec = self.manifest["artifacts"]["landscape"]
        with self.archive("landscape") as archive:
            # Hash the exact uncompressed CSV, not a reserialized row.
            h = hashlib.sha256()
            with archive.open(spec["member"]) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            basis = self.locator("landscape", spec["member"], h.hexdigest())
            with archive.open(spec["member"]) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                if reader.fieldnames != self.manifest["landscape_columns"]:
                    raise SourceError("Landscape layout changed (including order); inspect before mapping")
                for ordinal, row in enumerate(reader, 2):
                    if None in row or any(v is None for v in row.values()):
                        raise SourceError(f"Malformed CSV record {ordinal}")
                    key = identity(*(row[c] for c in KEY_COLUMNS))
                    if key[0] != self.manifest["benefit_year"]:
                        raise SourceError(f"Unexpected year at CSV record {ordinal}")
                    if row["Contract Plan ID"] != f"{key[1]}_{key[2]}" or row["Contract Plan Segment ID"] != f"{key[1]}_{key[2]}_{row['Segment ID']}":
                        raise SourceError(f"Composite identifier disagrees at CSV record {ordinal}")
                    yield key, row, {**basis, "record_ordinal": ordinal}

    def pbp_members(self, archive):
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not FILENAME.fullmatch(n) for n in names):
            raise SourceError("Unexpected/duplicate PBP members; inspect layout before continuing")
        return sorted(names)

    def pbp_record(self, archive, name):
        raw = archive.read(name)
        doc = json.loads(raw)
        if set(doc) != {"contractYear", "section", "pbp"} or not isinstance(doc["pbp"], list) or len(doc["pbp"]) != 1:
            raise SourceError(f"Uninspected PBP root/cardinality: {name}")
        p = doc["pbp"][0]
        key = identity(doc["contractYear"], p.get("contractId"), p.get("planId"), p.get("segmentId"))
        if member_for(key) != name or key[0] != self.manifest["benefit_year"]:
            raise SourceError(f"PBP payload/filename/year disagreement: {name}")
        if not isinstance(p.get("planCharacteristics"), dict):
            raise SourceError(f"Missing PBP characteristics: {name}")
        return key, doc, self.locator("pbp", name, sha256(raw))

    def market(self, fips):
        alias = self.markets["markets"].get(fips)
        if alias is None:
            raise SourceError(f"Unsupported county {fips!r}; only explicit inspected aliases are supported")
        spec = self.manifest["artifacts"]["counties"]
        with self.archive("counties") as archive:
            raw = archive.read(spec["member"])
        matches = []
        for ordinal, row in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter=spec["delimiter"]), 2):
            if row["GEOID"] == fips:
                matches.append((ordinal, row))
        if len(matches) != 1:
            raise SourceError(f"Census county identity not unique/present: {fips}")
        ordinal, row = matches[0]
        if row["USPS"] != alias["state"] or row["NAME"] != alias["census_name"]:
            raise SourceError(f"County alias disagrees with Census: {fips}")
        return {"county_fips": fips, **alias, "mapping_version": self.markets["mapping_version"],
                "census_raw": row, "evidence": self.locator("counties", spec["member"], sha256(raw), record_ordinal=ordinal)}


def in_market(row, market):
    if row["State Territory Abbreviation"] != market["state"]:
        return False
    if row["County Name"] == market["landscape_county"]:
        return True
    if row["County Name"] == "All Counties":
        if (row["Contract Category Type"], row["Plan Type"]) != ("PDP", "PDP"):
            raise SourceError("Uninspected All Counties scope; refusing to expand geography")
        return True
    return False


def query(sources, year, fips):
    if year != sources.manifest["benefit_year"]:
        raise SourceError(f"Unsupported benefit year {year}; pinned release is {sources.manifest['benefit_year']}")
    market = sources.market(fips)
    selected, excluded, seen = [], [], set()
    scope = sources.markets["scope"]
    with sources.archive("pbp") as archive:
        members = set(sources.pbp_members(archive))
        for key, row, loc in sources.landscape():
            if not in_market(row, market):
                continue
            geo_key = key + tuple(row[c] for c in GEO_COLUMNS)
            if geo_key in seen:
                raise SourceError(f"Duplicate market offering: {geo_key}")
            seen.add(geo_key)
            result = {"identity": key_object(key), "landscape_raw": row, "landscape_evidence": loc,
                      "source_geography": {"state": row[GEO_COLUMNS[0]], "county_label": row[GEO_COLUMNS[1]],
                                           "scope": "statewide_pdp" if row[GEO_COLUMNS[1]] == "All Counties" else "county"}}
            reasons = []
            if row["Contract Category Type"] not in scope["categories"]:
                reasons.append("category_outside_experiment")
            if row["Plan Type"] not in scope["plan_types"]:
                reasons.append("plan_type_outside_experiment")
            # Sanction is surfaced, never converted into a generic eligibility verdict.
            if row["Sanctioned Plan"] != "No":
                reasons.append("sanction_status_requires_review")
            name = member_for(key)
            result["open_checks"] = ["Published data only; eligibility, access, personalized costs and transaction availability not assessed"]
            if name not in members:
                result["pbp"] = {"join_status": "missing", "expected_member": name}
                result["open_checks"].append("Landscape identity has no PBP member in this release; cause unresolved")
            else:
                _, doc, ploc = sources.pbp_record(archive, name)
                result["pbp"] = {"join_status": "payload_identity_verified", "evidence": ploc,
                                 "raw_identity": {"contractYear": doc["contractYear"], **{k: doc["pbp"][0][k] for k in ("contractId", "planId", "segmentId")}},
                                 "source_facts": {out: cell(pointer(doc, path), {**ploc, "json_pointer": path}) for out, path in sources.mapping["pbp_raw_fields"].items()}}
                if pointer(doc, "/pbp/0/planCharacteristics/planName") != row["Plan Name"]:
                    result["open_checks"].append("PBP and landscape names disagree; no automatic substitution")
            if reasons:
                result["exclusion_reasons"] = reasons
                excluded.append(result)
                continue
            result["facts"] = {out: cell(row[col], {**loc, "column": col}) for out, col in sources.mapping["text_fields"].items()}
            for out, spec in sources.mapping["money_fields"].items():
                result["facts"][out] = {**money(row[spec["column"]], {**loc, "column": spec["column"]}, spec.get("allow_negative", False)), "unit": spec["unit"]}
            selected.append(result)
    if not seen:
        raise SourceError("No source geography rows matched; not a supported empty-market conclusion")
    order = lambda item: tuple(item["identity"].values()) + (item["source_geography"]["county_label"],)
    selected.sort(key=order)
    excluded.sort(key=order)
    return {"release_id": sources.manifest["release_id"], "benefit_year": year, "market": market,
            "status": "bounded_source_query", "order": "lexicographic source identity; no suitability ranking",
            "scope": scope, "counts": {"source_market_rows": len(seen), "included": len(selected), "excluded": len(excluded),
                                       "missing_pbp_included": sum(x["pbp"]["join_status"] == "missing" for x in selected)},
            "limitations": ["No Medigap or Original Medicare bundle comparison", "No residence, election or SNP eligibility assessment",
                            "No drug-specific coverage/pricing or exact provider-network verification", "No personalized quote, ranking, purchase or enrollment authority",
                            "Published premiums exclude other Medicare obligations and personal adjustments; no all-in cost assertion",
                            "PBP workflow tokens and nested codes are source evidence only"],
            "options": selected, "exclusions": excluded}


def export_market(sources, result, out):
    """Export all market rows and exact PBP bytes, regardless of comparison scope."""
    records = sorted(result["options"] + result["exclusions"], key=lambda r: r["landscape_evidence"]["record_ordinal"])
    files = {}
    encoded = lambda value: (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    files["market-query.json"] = encoded(result)
    # Derived CSV serialization preserves all field strings, including whitespace and IDs.
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=sources.manifest["landscape_columns"])
    writer.writeheader()
    writer.writerows(r["landscape_raw"] for r in records)
    files["landscape.csv"] = buffer.getvalue().encode("utf-8")
    files["landscape-lineage.json"] = encoded([
        {"identity": r["identity"], "source": r["landscape_evidence"],
         "disposition": "excluded_from_comparison_scope" if "exclusion_reasons" in r else "included_in_comparison_scope",
         "exclusion_reasons": r.get("exclusion_reasons", [])} for r in records
    ])
    missing = []
    with sources.archive("pbp") as archive:
        for record in records:
            if record["pbp"]["join_status"] == "missing":
                missing.append({"identity": record["identity"], "expected_member": record["pbp"]["expected_member"]})
                continue
            loc = record["pbp"]["evidence"]
            raw = archive.read(loc["member"])
            if sha256(raw) != loc["member_sha256"]:
                raise SourceError(f"PBP changed while exporting {loc['member']}")
            files["pbp/" + loc["member"]] = raw
    with sources.archive("landscape") as archive:
        files["landscape-readme.txt"] = archive.read(sources.manifest["artifacts"]["landscape"]["readme_member"])
    files["release.json"] = encoded(sources.manifest)
    files["field-mapping.json"] = (sources.root / "data-sources/field-mapping.json").read_bytes()
    profile = {
        "release_id": result["release_id"], "benefit_year": result["benefit_year"], "market": result["market"],
        "counts": result["counts"],
        "source_county_label_counts": dict(collections.Counter(r["landscape_raw"]["County Name"] for r in records)),
        "category_counts": dict(collections.Counter(r["landscape_raw"]["Contract Category Type"] for r in records)),
        "plan_type_counts": dict(collections.Counter(r["landscape_raw"]["Plan Type"] for r in records)),
        "pbp_payload_count": sum(name.startswith("pbp/") for name in files),
        "pbp_uncompressed_bytes": sum(len(raw) for name, raw in files.items() if name.startswith("pbp/")),
        "missing_pbp": missing,
        "plan_name_conflicts": [r["identity"] for r in records if any("names disagree" in check for check in r["open_checks"])],
        "limitations": result["limitations"],
    }
    files["market-profile.json"] = encoded(profile)
    manifest = {
        "purpose": "Complete source capture for this market within pinned CMS landscape/PBP sources; not every Medicare data family",
        "release_id": result["release_id"], "market": result["market"], "counts": result["counts"],
        "script_sha256": file_hash(__file__),
        "configuration_sha256": {n: file_hash(sources.root / "data-sources" / n) for n in ("release.json", "markets.json", "field-mapping.json")},
        "files_sha256": {name: sha256(raw) for name, raw in sorted(files.items())},
        "encoding_notes": "PBP files and README are exact archive-member bytes. CSV is a derived serialization preserving all 53 raw field strings. Original CSV locators remain in landscape-lineage.json.",
        "missing_pbp": missing,
    }
    files["manifest.json"] = encoded(manifest)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=out.parent, delete=False) as temporary:
        path = Path(temporary.name)
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, raw, compresslevel=9)
        os.replace(path, out)
    finally:
        path.unlink(missing_ok=True)
    return profile


def inspect(sources):
    counts = collections.Counter()
    categories, plan_types = collections.Counter(), collections.Counter()
    empty, na, unavailable, negative = (collections.Counter() for _ in range(4))
    money_states, arithmetic = collections.Counter(), collections.Counter()
    plans, offerings, premiums, missing = {}, set(), collections.defaultdict(set), []
    rejected = []
    with sources.archive("pbp") as archive:
        members = set(sources.pbp_members(archive))
    for key, row, loc in sources.landscape():
        counts["rows"] += 1
        plans.setdefault(key, (row, loc))
        geo = key + tuple(row[c] for c in GEO_COLUMNS)
        if geo in offerings:
            raise SourceError(f"Duplicate national offering {geo}")
        offerings.add(geo)
        categories[row["Contract Category Type"]] += 1
        plan_types[row["Plan Type"]] += 1
        counts["literal_zero_segments"] += row["Segment ID"] == "0"
        if row["County Name"] == "All Counties":
            counts["all_counties_rows"] += 1
            if (row["Contract Category Type"], row["Plan Type"]) != ("PDP", "PDP"):
                raise SourceError("All Counties population changed; scope review required")
        for col, value in row.items():
            empty[col] += not value.strip()
            na[col] += value.strip() == "Not Applicable"
            unavailable[col] += value.strip() == "Not Available"
        parsed = {}
        for field, spec in sources.mapping["money_fields"].items():
            parsed[field] = money(row[spec["column"]], allow_negative=spec.get("allow_negative", False))
            value = parsed[field]
            money_states[f"{field}:{value['state']}"] += 1
            if value["state"] == "rejected":
                rejected.append({"field": field, "cell": value, "evidence": {**loc, "column": spec["column"]}})
            if value["value_cents"] is not None and value["value_cents"] < 0:
                negative[spec["column"]] += 1
        for label, terms in {
            "part_d_total": ("part_d_basic_premium", "part_d_supplemental_premium", "part_d_total_premium"),
            "consolidated": ("part_c_premium", "part_d_total_premium", "consolidated_premium"),
        }.items():
            values = [parsed[t]["value_cents"] for t in terms]
            if any(v is None for v in values):
                arithmetic[label + ":not_comparable"] += 1
            elif values[0] + values[1] == values[2]:
                arithmetic[label + ":agrees"] += 1
            else:
                arithmetic[label + ":disagrees"] += 1
                rejected.append({"reason": label + "_arithmetic_disagreement", "evidence": loc, "values_cents": values})
        premiums[key].add(tuple(row[c] for c in ("Part C Premium", "Part D Total Premium", "Monthly Consolidated Premium (Part C + D)")))
        if member_for(key) not in members:
            missing.append({"identity": key_object(key), "expected_member": member_for(key), "landscape_raw": row,
                            "evidence": loc, "status": "unresolved_source_gap; not proof of withdrawal or unavailable coverage"})
    pbp_counts, extra_groups, extra_types = collections.Counter(), collections.Counter(), collections.Counter()
    extras, name_conflicts, samples = [], [], {}
    plan_keys = set(plans)
    with sources.archive("pbp") as archive:
        for name in sources.pbp_members(archive):
            key, doc, loc = sources.pbp_record(archive, name)
            p = doc["pbp"][0]
            pc = p["planCharacteristics"]
            side = "matched" if key in plan_keys else "pbp_only"
            pbp_counts[side] += 1
            pbp_counts["status:" + str(p.get("status"))] += 1
            pbp_counts["segment_json_type:" + type(p["segmentId"]).__name__] += 1
            pbp_counts["section:" + str(doc["section"])] += 1
            for field, path in sources.mapping["pbp_raw_fields"].items():
                pbp_counts[f"field_state:{field}:{cell(pointer(doc, path))['state']}"] += 1
            if key in plan_keys:
                if pc.get("planName") != plans[key][0]["Plan Name"]:
                    name_conflicts.append({"identity": key_object(key), "pbp_name": pc.get("planName"),
                                           "landscape_name": plans[key][0]["Plan Name"], "pbp_evidence": loc,
                                           "landscape_evidence": plans[key][1]})
            else:
                employer = pc.get("isEmployerOnlyPlan") == "Yes" and int(key[2]) >= 800
                pace = pc.get("planTypeLabel") == "National PACE"
                bucket = "documented_employer_exclusion" if employer else "documented_national_pace_exclusion" if pace else "unexplained_population"
                extra_groups[bucket] += 1
                extra_types[str(pc.get("planTypeLabel"))] += 1
                entry = {"identity": key_object(key), "population": bucket, "evidence": loc,
                         "raw_identity": {"contractYear": doc["contractYear"], **{k: p[k] for k in ("contractId", "planId", "segmentId")}},
                         "source_facts": {k: cell(pc.get(k, ABSENT)) for k in ("planName", "isEmployerOnlyPlan", "planTypeLabel")},
                         "paths": {k: "/pbp/0/planCharacteristics/" + k for k in ("planName", "isEmployerOnlyPlan", "planTypeLabel")}}
                extras.append(entry)
                samples.setdefault(bucket, [])
                if len(samples[bucket]) < 3:
                    samples[bucket].append(entry)
    with sources.archive("landscape") as archive:
        member = sources.manifest["artifacts"]["landscape"]["readme_member"]
        raw = archive.read(member)
        readme = {"evidence": sources.locator("landscape", member, sha256(raw)), "text": raw.decode("utf-8-sig")}
    nonzero = lambda counter: {k: v for k, v in sorted(counter.items()) if v}
    missing_investigation = []
    for expected in sorted({m["expected_member"] for m in missing}):
        contract, plan, _, _ = FILENAME.fullmatch(expected).groups()
        related = sorted(n for n in members if n.startswith(contract + "-"))
        missing_investigation.append({
            "expected_member": expected,
            "affected_landscape_records": [m["evidence"]["record_ordinal"] for m in missing if m["expected_member"] == expected],
            "related_contract_members": related,
            "same_contract_plan_other_segment_or_year": [n for n in related if n.startswith(f"{contract}-{plan}-")],
            "interpretation": "Not a filename-padding or payload-identity mismatch. Cause of source absence remains unconfirmed; do not substitute a different plan.",
        })
    with sources.archive("pbp") as archive:
        sizes = [info.file_size for info in archive.infolist()]
    report = {
        "release_id": sources.manifest["release_id"], "artifact_hashes_verified": True,
        "acceptance_scope": "Structural inspection and source replay only; domain/consumer publication approval remains open",
        "landscape": {**dict(counts), "columns": len(sources.manifest["landscape_columns"]), "plan_segment_keys": len(plans),
                      "contract_plan_keys": len({key[:3] for key in plans}), "offering_keys": len(offerings), "duplicate_offering_keys": 0,
                      "category_row_counts": dict(categories), "plan_type_row_counts": dict(plan_types),
                      "empty_counts": nonzero(empty), "not_applicable_counts": nonzero(na), "not_available_counts": nonzero(unavailable),
                      "negative_amount_counts": dict(negative), "money_states": dict(money_states),
                      "premium_arithmetic": dict(arithmetic), "multiple_premium_tuples_per_plan_segment": sum(len(v) > 1 for v in premiums.values())},
        "pbp": {"members": len(members), "uncompressed_bytes": sum(sizes), "min_member_bytes": min(sizes), "max_member_bytes": max(sizes),
                "payloads_parsed": sum(pbp_counts[s] for s in ("matched", "pbp_only")),
                "payload_filename_identity_errors": 0, "one_pbp_entry_per_member": True, "observed": dict(pbp_counts)},
        "join": {"matched_plan_segments": pbp_counts["matched"], "landscape_without_pbp_keys": len({m["expected_member"] for m in missing}),
                 "landscape_without_pbp_rows": len(missing), "pbp_only_keys": len(extras), "pbp_only_population": dict(extra_groups),
                 "pbp_only_plan_type_labels": dict(extra_types), "representative_samples": samples, "plan_name_conflicts": name_conflicts,
                 "missing_identity_investigation": missing_investigation},
        "rejected_values_or_arithmetic_conflicts": rejected,
        "known_gaps": ["H3931-143-000-2027 has no PBP payload in this archive; root cause unconfirmed",
                       "Submitted status and nested benefit-code meanings are not independently documented here",
                       "No independent Medicare Plan Finder/carrier value cross-check or domain sign-off completed",
                       f"Only {len(sources.markets['markets'])} county aliases are resolved; no national geography certification",
                       "Public downloads are not a complete display/LLM/retention rights assessment or operating approval"],
    }
    return report, extras, missing, readme


def run(sources, out):
    sources.verify()
    quality, extras, missing, readme = inspect(sources)
    markets = {fips: query(sources, sources.manifest["benefit_year"], fips) for fips in sources.markets["markets"]}
    # Finish all source processing before replacing any review artifact.
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temporary:
        staging = Path(temporary)
        write_json(staging / "quality.json", quality)
        write_json(staging / "field-mapping.json", sources.mapping)
        write_json(staging / "landscape-readme.json", readme)
        for name, entries in (("pbp-only.jsonl", extras), ("landscape-without-pbp.jsonl", missing)):
            (staging / name).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        for fips, result in markets.items():
            write_json(staging / f"market-{fips}-{sources.manifest['benefit_year']}.json", result)
        for fips in sources.markets.get("full_payload_exports", []):
            profile = export_market(sources, markets[fips], staging / f"market-{fips}-{sources.manifest['benefit_year']}-sources.zip")
            write_json(staging / f"market-{fips}-{sources.manifest['benefit_year']}-profile.json", profile)
        manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                    "release": sources.manifest, "script_sha256": file_hash(__file__),
                    "configuration_sha256": {n: file_hash(sources.root / "data-sources" / n) for n in ("release.json", "markets.json", "field-mapping.json")},
                    "outputs_sha256": {p.name: file_hash(p) for p in sorted(staging.iterdir())}}
        write_json(staging / "run-manifest.json", manifest)
        out.mkdir(parents=True, exist_ok=True)
        for path in sorted(staging.iterdir(), key=lambda p: p.name == "run-manifest.json"):
            os.replace(path, out / path.name)
    print(json.dumps({"reports": str(out), "landscape_rows": quality["landscape"]["rows"], "pbp_payloads": quality["pbp"]["payloads_parsed"],
                      "markets": {f: r["counts"] for f, r in markets.items()}}, indent=2))


def verify_report(sources, out):
    sources.verify()
    manifest = load_json(Path(out) / "run-manifest.json")
    if manifest["release"] != sources.manifest or manifest["script_sha256"] != file_hash(__file__):
        raise SourceError("Report code/release differs from current inputs; reproduce and review")
    for name, digest in manifest["configuration_sha256"].items():
        if file_hash(sources.root / "data-sources" / name) != digest:
            raise SourceError(f"Configuration changed since report: {name}")
    for name, digest in manifest["outputs_sha256"].items():
        if file_hash(Path(out) / name) != digest:
            raise SourceError(f"Report changed or incomplete: {name}")
    print("Verified source, code, configuration and report hashes")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="Download only exact pinned artifacts; network required")
    for command in ("run", "verify"):
        p = commands.add_parser(command)
        p.add_argument("--out", type=Path, default=ROOT / "reports/work-package-1")
    p = commands.add_parser("query", help="Read-only query, preserving excluded source rows")
    p.add_argument("--year", required=True)
    p.add_argument("--county-fips", required=True)
    p.add_argument("--out", required=True, type=Path)
    p = commands.add_parser("export-market", help="Export all matching raw landscape fields and complete PBP payloads, including exclusions")
    p.add_argument("--year", required=True)
    p.add_argument("--county-fips", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    sources = Sources()
    try:
        if args.command == "fetch":
            sources.fetch()
        elif args.command == "run":
            run(sources, args.out)
        elif args.command == "verify":
            verify_report(sources, args.out)
        else:
            sources.verify()
            result = query(sources, args.year, args.county_fips)
            if args.command == "export-market":
                print(json.dumps(export_market(sources, result, args.out), indent=2))
            else:
                write_json(args.out, result)
                print(json.dumps(result["counts"], indent=2))
    except (SourceError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
