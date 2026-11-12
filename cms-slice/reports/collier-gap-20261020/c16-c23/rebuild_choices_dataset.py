"""Rebuild the CHOICES derivative and add the single verified IRFS identity link."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "scripts"))
import cms_slice as cms
from florida_medigap import build

out = ROOT / "c23-florida-medigap.json"
result = build(ROOT / "choices-source-index.json", out)
metadata = cms.load_json(ROOT / "c23-irfs-review.json")
capture = ROOT / "c23-irfs-filing-26018953.html"
evidence = {"source_url": metadata["source_url"], "capture": capture.name,
            "sha256": cms.file_hash(capture), "filing_reference": metadata["filing_reference"],
            "company_naic_display": metadata["company_naic_display"],
            "scope": "Same insurer identity verified in the public filing metadata. No row-level premium, form or effective-date link established."}
for row in result["records"]:
    if row["insurer_legal_name_raw"] == metadata["company"]:
        row["naic"] = metadata["company_naic_display"]
        row["naic_evidence"] = evidence
names = {r["insurer_legal_name_raw"] for r in result["records"] if r["naic"]}
result["insurers_with_naic_verified_from_irfs"] = len(names)
result["insurers_missing_naic"] = result["insurer_count"] - len(names)
result["oir_request"] = {"tracking_number": "26-045612", "acknowledgment": "c23-oir-acknowledgment.json",
                         "state": "Acknowledged; responsive records pending; no fees authorized"}
cms.write_json(out, result)
print(json.dumps({k: result[k] for k in ["rate_count", "scenario_count", "insurer_count", "insurers_missing_naic"]}))
