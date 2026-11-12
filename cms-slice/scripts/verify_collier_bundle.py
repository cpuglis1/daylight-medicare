#!/usr/bin/env python3
"""Offline C04/C05 release replay against independent captured-row queries."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

import cms_slice as cms
import demo_release
from demo_tools import DemoTools
from naples_catalog import NaplesCatalog


def verify(release, out, require_isolated=False):
    if require_isolated and (cms.ROOT / "data-sources/raw/prescription").exists():
        raise cms.SourceError("Replay must run from the extracted bundle without workspace/national sources")
    started = time.perf_counter()
    with patch("socket.socket", side_effect=AssertionError("Offline bundle replay attempted network access")):
        tools = DemoTools(release=release)
        startup = time.perf_counter() - started
        manifest = demo_release.verify(release)
        ids, offset, pages, records = [], 0, [], []
        while offset is not None:
            begin = time.perf_counter()
            page = tools.drug_evidence("1551300", pharmacy_npi="1609197854", offset=offset)
            pages.append({**{k: v for k, v in page["pagination"].items() if k != "full_option_ids"}, "seconds": time.perf_counter() - begin})
            ids.extend(r["plan_id"] for r in page["results"])
            records.extend(page["results"])
            offset = page["pagination"]["next_offset"]
        if ids != sorted(tools.by_id) or len(ids) != 70:
            raise cms.SourceError("Pagination lost/duplicated/reordered captured plans")
        checks = []
        for result in records:
            pid = result["plan_id"]
            raw = tools.rx.lookup(pid, rxcui="1551300", npi="1609197854")
            if tools.by_id[pid]["category"] == "MA":
                if result["status"] != "not_applicable_non_part_d" or raw["status"] != result["status"] or result["products"]:
                    raise cms.SourceError("MA-only record acquired drug coverage")
                checks.append({"plan_id": pid, "status": "not_applicable_non_part_d"})
                continue
            expected = sorted((r["raw"]["NDC"], r["raw"]["TIER_LEVEL_VALUE"], r["raw"]["PRIOR_AUTHORIZATION_YN"], r["raw"]["STEP_THERAPY_YN"], r["raw"]["QUANTITY_LIMIT_YN"]) for r in raw["basic_formulary"])
            actual = sorted((r["ndc11"], r["tier"], r["prior_authorization"], r["step_therapy"], r["quantity_limit"]) for r in result["products"])
            if actual != expected or result["pharmacy"]["status"] != raw["pharmacy"]["status"]:
                raise cms.SourceError("Compact/captured-row evidence disagreement: " + pid)
            expected_network = [(r["raw"]["PREFERRED_STATUS_RETAIL"], r["raw"]["PHARMACY_RETAIL"], r["evidence"]) for r in raw["pharmacy"]["rows"]]
            actual_network = [(r["preferred_retail"], r["retail"], r["evidence"]) for r in result["pharmacy"]["rows"]]
            if actual_network != expected_network:
                raise cms.SourceError("Pharmacy row/evidence disagreement: " + pid)
            checks.append({"plan_id": pid, "status": "agrees", "products": len(actual), "pharmacy_rows": len(actual_network), "historical_comparison_scope": tools.by_id[pid]["comparison_available"]})
        begin = time.perf_counter()
        tools.drug_evidence("1551300", pharmacy_npi="1609197854")
        warm_page_seconds = time.perf_counter() - begin
        stars = NaplesCatalog(tools).list()["plans"]
        if len(stars) != 70 or any(p["star_rating"]["state"] not in {"rated", "not_enough_data", "too_new", "not_applicable"} for p in stars):
            raise cms.SourceError("Star rating coverage incomplete in extracted bundle")
        pharmacy_count = sum(n.endswith("-pharmacy.psv.gz") for n in manifest["files_sha256"])
        if pharmacy_count != 61 or sum(c["status"] == "agrees" for c in checks) != 61:
            raise cms.SourceError("Not all 61 drug plans were packaged and verified")
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "release_id": manifest["release_id"],
              "release_manifest_sha256": cms.file_hash(demo_release.resolve(release) / "manifest.json"),
              "network_disabled": True, "isolated_bundle": require_isolated, "synthetic_query": {"rxcui": "1551300", "pharmacy_npi": "1609197854"},
              "counts": {"catalog": len(ids), "drug_plans_independently_replayed": 61, "ma_only_not_applicable": 9,
                         "packaged_pharmacy_networks": pharmacy_count, "star_contracts": len(tools.star_ratings["contracts"]), "plans_with_star_states": len(stars)},
              "star_display_states": dict(Counter(p["star_rating"]["state"] for p in stars)),
              "performance": {"startup_seconds": startup, "pages": pages, "warm_20_plan_page_seconds": warm_page_seconds,
                              "total_replay_seconds": time.perf_counter() - started,
                              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                              "snapshot_bytes": sum((demo_release.resolve(release) / n).stat().st_size for n in manifest["files_sha256"])},
              "plan_checks": checks, "limits": ["Exact synthetic product/store evidence; no personal prices or eligibility determination.", "Qualified domain review and R1 release gates remain pending."]}
    cms.write_json(Path(out), result)
    return result["counts"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", default="snapshot")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-isolated", action="store_true")
    args = parser.parse_args()
    print(verify(args.release, args.out, args.require_isolated))
