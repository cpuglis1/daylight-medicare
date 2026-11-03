"""Reconcile explicitly selected per-layer sizing receipts, without database writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from daylight_data.adapters.common import adapter_code_sha256, digest_json

LARGE = {"L03", "L07", "L08"}
DRIVER = "infrastructure/daylight-data/tools/benchmark_local_layers.py"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(repository, small, large):
    contracts, layers, relation_totals, all_source_controls = {}, [], Counter(), Counter()
    r9_representations = Counter()
    baselines, maximum_rss, minimum_free = [], 0, None
    for number in range(1, 16):
        layer_id = f"L{number:02}"
        directory = large if layer_id in LARGE else small
        path = directory / (layer_id + ".json")
        summary = read(path)
        if summary["layer_id"] != layer_id or not summary["sizing_populations_complete"] or summary["new_acceptance"]:
            raise ValueError("Incomplete or wrongly scoped layer sizing receipt")
        contract_hash = summary["sizing_contract_sha256"]
        contract_path = directory / ("run-contract-" + contract_hash + ".json")
        contract = read(contract_path)
        if digest_json(contract) != contract_hash:
            raise ValueError("Sizing contract hash differs")
        contracts[contract_hash] = {"path": str(contract_path.relative_to(repository)),
                                    "file_sha256": sha(contract_path), "contract": contract}
        net, count, projection_count, receipts, controls = 0, 0, 0, [], Counter()
        measured_windows = {}
        for binding in summary["units"]:
            unit_path = directory / "units" / (digest_json(binding) + ".json")
            unit = read(unit_path)
            if unit["binding"] != binding or not unit["population_complete"]:
                raise ValueError("Missing or incompatible unit receipt")
            if binding["sizing_contract_sha256"] != contract_hash:
                raise ValueError("Layer silently mixes sizing contracts")
            if binding["adapter_code_sha256"] != adapter_code_sha256(layer_id):
                raise ValueError("Selected receipt does not pin the current exact layer adapter and helpers")
            baseline = {(r["schema"],r["table"]):r for r in unit["baseline_relation_sizes"]}
            calculated = 0
            for row in unit["relation_sizes"]:
                if row["schema"] != "dl_evidence":
                    continue
                before = baseline[(row["schema"],row["table"])]
                delta = row["total_bytes_including_toast"] - before["total_bytes_including_toast"]
                calculated += delta
                relation_totals[row["table"]] += delta
            if calculated != unit["net_evidence_relation_bytes"]:
                raise ValueError("Relation baseline subtraction does not balance")
            net += calculated
            count += unit["input_rows"]
            projection_count += sum(unit["projection_counts"].values())
            controls[binding["source_path"] + "#" + binding["source_table"]] += unit["input_rows"]
            all_source_controls[binding["source_path"] + "#" + binding["source_table"]] += unit["input_rows"]
            if layer_id in LARGE:
                first,last=unit["window_first_ordinal"],unit["window_last_ordinal"]
                if first != binding["window_first_ordinal"] or last-first+1 != unit["input_rows"]:
                    raise ValueError("Unit window lineage/count does not balance")
                key=binding["source_path"]+"#"+binding["source_table"]
                measured_windows.setdefault(key,[]).append({"first":first,"last":last,"rows":unit["input_rows"]})
            if layer_id == "L03" and "/semantic-inventory-r9/" in binding["source_path"] and binding["source_table"] == "semantic_unit":
                r9_representations.update(unit["projection_counts"])
            maximum_rss = max(maximum_rss, unit["process_peak_rss_bytes"])
            minimum_free = min(minimum_free,unit["minimum_observed_free_bytes"]) if minimum_free is not None else unit["minimum_observed_free_bytes"]
            baselines.append(unit["schema_baseline_database_bytes"])
            receipts.append({"path":str(unit_path.relative_to(repository)),"sha256":sha(unit_path)})
        if count != summary["source_rows"] or net != summary["net_evidence_relation_bytes"]:
            raise ValueError("Layer and unit control totals differ")
        if layer_id in LARGE:
            for control in summary["source_table_population_controls"]:
                key = control["source_path"] + "#" + control["source_table"]
                if control["unexplained_loss"] or control["source_rows"] != controls.pop(key):
                    raise ValueError("Full source-table coverage differs from measured windows")
                if control["windows"] != measured_windows.pop(key):
                    raise ValueError("Source-table control windows differ from selected unit receipts")
                cursor = 0
                for window in control["windows"]:
                    if window["first"] != cursor+1 or window["last"]-window["first"]+1 != window["rows"]:
                        raise ValueError("Overlapping or missing source ordinals")
                    cursor = window["last"]
                if cursor != control["source_rows"] or len(control["ordered_full_stream_sha256"]) != 64:
                    raise ValueError("Incomplete full source-table control")
            if controls or measured_windows:
                raise ValueError("Measured table is missing its full source coverage control")
        layers.append({"layer_id":layer_id,"source_rows":count,"projection_rows":projection_count,
                       "net_evidence_relation_bytes":net,"net_evidence_gb":round(net/10**9,6),
                       "net_evidence_gib":round(net/1024**3,6),"sizing_contract_sha256":contract_hash,
                       "layer_receipt":str(path.relative_to(repository)),"layer_receipt_sha256":sha(path),
                       "unit_receipts":receipts})
    configurations = list(contracts.values())
    reference = configurations[0]["contract"]
    for config in configurations[1:]:
        candidate = config["contract"]
        if candidate["postgres_settings"] != reference["postgres_settings"]:
            raise ValueError("PostgreSQL settings differ between selected sizing runs")
        # Per-layer modules differ by design and are checked against each unit's
        # exact current adapter digest above. Unused modules in a run-wide freeze
        # do not make another layer's measurements incompatible.
        def shared(k):
            return k != DRIVER and not re.search(r"/adapters/l\d{2}\.py$",k)
        a = {k:v for k,v in candidate["files"].items() if shared(k)}
        b = {k:v for k,v in reference["files"].items() if shared(k)}
        if a != b:
            raise ValueError("Source/schema/dependency files differ between selected sizing runs")
    total = sum(layer["net_evidence_relation_bytes"] for layer in layers)
    l03 = read(large/"L03.json")
    if dict(r9_representations) != {"ma_semantic_claim_representation":143679,"ma_semantic_condition_representation":249065}:
        raise ValueError("Selected r9 semantic representation projection counts differ")
    r9_controls = l03["semantic_inventory_controls"]
    r9_obligations = r9_controls["canonical_kind_counts"]
    if r9_obligations != {"claim":143505,"condition":249065} or r9_obligations != l03["frozen_r9_obligations"]:
        raise ValueError("Frozen r9 canonical semantic denominator differs")
    if (r9_controls["semantic_kind_counts"] != {"claim":143679,"condition":249065}
        or r9_controls["semantic_representation_rows"] != 392744
        or r9_controls["canonical_mapping_rows"] != 392744
        or r9_controls["canonical_identity_rows"] != 392570
        or r9_controls["source_identity_alias_rows"] != 174
        or r9_controls["work_obligation_rows"] != 230
        or r9_controls["missing_canonical_mappings"] != 0):
        raise ValueError("Frozen r9 native representations, aliases or follow-up counts differ")
    native_inventories = l03["native_inventory_controls"]
    expected_parents = {"docs/data/l03-ma-benefits-2026-10-25/"+revision+"/inventory.sqlite3.gz"
                        for revision in ("semantic-inventory-r9","inventory-r8")}
    if {source["source_path"] for source in native_inventories} != expected_parents or len(native_inventories) != 2:
        raise ValueError("Both frozen L03 native parent controls are required")
    for source in native_inventories:
        bindings = [binding for binding in l03["units"] if binding["source_path"] == source["source_path"]]
        expected_tables = {table for table,count in source["native_table_counts"].items() if count}
        if {binding["source_table"] for binding in bindings} != expected_tables:
            raise ValueError("Frozen L03 native table-name set differs from selected receipts")
        if not bindings or any(binding["source_sha256"] != source["source_sha256"] for binding in bindings):
            raise ValueError("Frozen L03 native source hash differs from selected receipts")
        for table,count in source["native_table_counts"].items():
            if all_source_controls.get(source["source_path"]+"#"+table,0) != count:
                raise ValueError("Frozen L03 native table count differs from selected unit receipts")
        if "/semantic-inventory-r9/" in source["source_path"]:
            if source["semantic_inventory_controls"] != r9_controls:
                raise ValueError("Canonical source controls differ from selected L03 layer summary")
            for table,count in {"semantic_unit":392744,"canonical_unit":392744,"source_identity_alias":174,"work_obligation":230}.items():
                if source["native_table_counts"].get(table) != count:
                    raise ValueError("Frozen r9 native row grain differs from canonical controls")
    dispositions = read(large / "L08.json")["non_domain_source_table_dispositions"]
    excluded = {row["source_path"]+"#"+row["table"]:row for row in dispositions}
    inventory = read(small.parent / "source-sizing.json")
    comparisons = []
    for database in inventory["sqlite_files"]:
        for table in database["tables"]:
            key = database["path"] + "#" + table["name"]
            actual = all_source_controls.get(key,0)
            if key in excluded:
                if actual or excluded[key]["source_rows"] != table["rows"]:
                    raise ValueError("Excluded derivative search accounting differs")
                state = "explicit_derivative_search_disposition"
            else:
                if actual != table["rows"]:
                    raise ValueError("Independent SQLite source count differs: " + key)
                state = "all_native_rows_measured"
            comparisons.append({"source_table":key,"expected_rows":table["rows"],
                                "measured_rows":actual,"state":state})
    required_controls = {
        "docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json#collier_offerings":72,
        "docs/data/l03-ma-benefits-2026-10-25/bounded-reference-r4/entries.json#entries":535,
        "docs/data/l03-ma-benefits-2026-10-25/bounded-reference-r4/held-claims.json#held-claims":153,
        "docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json#pdp_records":10,
        "docs/data/l10-medigap-2026-10-28/filing-reconciliation-r3/build-r1/rate-cells.json#rate-cells":22496,
        "docs/data/l10-medigap-2026-10-28/targeted-filings-r5/build-r1/rate-cells.json#rate-cells":40700}
    for key,expected in required_controls.items():
        if all_source_controls[key] != expected:
            raise ValueError("Required selected JSON population differs: " + key)
    return {"schema":"daylight-local-sizing-summary/1","reference_year":2026,
            "observed_at":datetime.now(timezone.utc).isoformat(),"layers_measured":15,
            "source_rows":sum(layer["source_rows"] for layer in layers),
            "projection_rows":sum(layer["projection_rows"] for layer in layers),
            "net_evidence_relation_bytes":total,"net_evidence_gb":round(total/10**9,6),
            "net_evidence_gib":round(total/1024**3,6),"relation_bytes":dict(relation_totals),
            "one_empty_database_baseline_bytes":max(baselines),
            "one_selected_representation_database_estimate_bytes":total+max(baselines),
            "maximum_python_process_rss_bytes":maximum_rss,"minimum_observed_free_bytes":minimum_free,
            "contracts":configurations,"layers":layers,
            "independent_sqlite_population_comparisons":comparisons,
            "independent_source_inventory":{"path":str((small.parent/"source-sizing.json").relative_to(repository)),
                                            "sha256":sha(small.parent/"source-sizing.json")},
            "required_selected_json_controls":required_controls,
            "unexplained_native_sqlite_row_loss":0,
            "frozen_r9_obligations":dict(r9_obligations),
            "r9_semantic_inventory_controls":r9_controls,
            "l03_native_inventory_controls":native_inventories,
            "provider_non_domain_dispositions":dispositions,
            "all_layers_simultaneously_integrated":False,"full_domain_models_complete":False,
            "new_acceptance":False,"cloud_deployed":False,
            "limitations":["Sum of measured isolated table/window footprints estimates consolidated layout; it is not pg_database_size of a simultaneous fifteen-layer database.",
                           "One empty schema baseline is included separately; final control/profile rows, additional domain models/indexes, WAL, workspace, growth, backups and retained older derivations need headroom.",
                           "Python peak RSS excludes PostgreSQL shared/backend memory and operating-system cache; local throughput does not benchmark a cloud compute tier.",
                           "Source/projection rows are transport accounting, not unique consumer benefits or verified facts."]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository",required=True,type=Path)
    parser.add_argument("--small",required=True,type=Path)
    parser.add_argument("--large",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    report=summarize(args.repository.resolve(),args.small.resolve(),args.large.resolve())
    with args.output.open("x") as handle:
        json.dump(report,handle,indent=2,sort_keys=True)
        handle.write("\n")
    print(json.dumps({k:report[k] for k in ["layers_measured","source_rows","net_evidence_gb","net_evidence_gib"]}))


if __name__=="__main__":
    main()
