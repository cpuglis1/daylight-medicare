#!/usr/bin/env python3
"""Retain the public SHINE directory without submitting forms or fetching challenges."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "P26-S57": "https://www.floridashine.org/Contact-Us.aspx",
    "P26-S58": "https://www.floridashine.org/Counseling-Sites/Collier.aspx",
    "L15-S03": "https://www.floridashine.org/Home.aspx",
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Output is not empty; use a new acquisition revision")
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for sid, url in SOURCES.items():
        with urlopen(Request(url, headers={"User-Agent": "Daylight public-source verification"}), timeout=45) as response:
            raw = response.read()
            digest = hashlib.sha256(raw).hexdigest()
            final_url = response.url
            if response.status != 200 or not final_url.startswith("https://www.floridashine.org/"):
                raise ValueError("Unexpected source response: " + sid)
            if b"SHINE" not in raw or any(x in raw.lower() for x in (b"verify you are human", b"access denied", b"cf-chl-")):
                raise ValueError("Source unavailable; do not bypass: " + sid)
            target = args.output / (sid + ".html")
            target.write_bytes(raw)
            records.append({"id": sid, "url": url, "final_url": final_url,
                            "http_status": response.status, "content_type": response.headers.get("Content-Type"),
                            "last_modified": response.headers.get("Last-Modified"),
                            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                            "sha256": digest, "bytes": len(raw), "path": str(target.relative_to(ROOT)),
                            "method": "GET", "form_submitted": False})
    (args.output / "receipts.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps({"sources": len(records), "bytes": sum(r["bytes"] for r in records)}))


if __name__ == "__main__":
    main()
