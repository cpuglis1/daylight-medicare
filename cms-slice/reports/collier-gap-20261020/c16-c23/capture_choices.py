"""Fixed public CHOICES comparison grid; no personal input or outbound messages."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
BASE = "https://choices.floir.gov/mcws/api/MCWSSearch/GetSearchResults"
UA = "DaylightMedicareEvidenceReview/0.1 (+mailto:chris@beaconfederaladvisory.com)"


def capture():
    scenarios = [{"age": str(age), "gender": sex, "smoker": smoker} for age in [65, 70, 75, 80] for sex in ["f", "m"] for smoker in ["o", "s"]]
    scenarios.append({"age": "0-64", "gender": "f", "smoker": "o"})
    out = ROOT / "choices"
    out.mkdir(exist_ok=True)
    index = []
    for scenario in scenarios:
        key = "-".join(scenario.values())
        receipt_path = out / (key + ".json")
        if receipt_path.exists():
            index.append(json.loads(receipt_path.read_text()))
            continue
        params = {**scenario, "zipCode": "34102", "insuranceType": "0", "plans": "A,B,C,D,F,G,K,L,M,N,F*,G*", "effectiveDate": "01/01/2027", "groupCode": "B"}
        url = BASE + "?" + urlencode(params)
        # First browser-observed result is reused without inventing another retrieval.
        prior = json.loads((ROOT / "c23-choices-first-search.json").read_text())
        if scenario == {"age": "65", "gender": "f", "smoker": "o"}:
            record = {**prior, "id": key, "inputs": params, "adopted_browser_receipt": "c23-choices-first-search.json"}
        else:
            time.sleep(5)
            try:
                response = urlopen(Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(4_000_001)
                record = {"id": key, "url": url, "http_status": response.code, "inputs": params,
                          "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "retries": 0}
            (ROOT / "raw" / record["sha256"]).write_bytes(raw)
            if record["http_status"] != 200 or len(raw) > 4_000_000:
                receipt_path.write_text(json.dumps(record, indent=2) + "\n")
                raise ValueError("CHOICES source status/size changed; stop without retry")
            payload = json.loads(raw)
            if set(payload) != {"rates", "rateDisplays"} or not all(isinstance(payload[k], list) for k in payload):
                raise ValueError("CHOICES schema changed")
        receipt_path.write_text(json.dumps(record, indent=2) + "\n")
        index.append(record)
        print(json.dumps({"scenario": key, "bytes": record["bytes"], "http_status": record["http_status"]}), flush=True)
    (ROOT / "choices-source-index.json").write_text(json.dumps({"scope": "17 fixed synthetic 34102 Collier scenarios; annual illustrative rates, both standard/SELECT and individual/group; request date does not establish actual filed effective date. Household discount and guaranteed-issue entitlement are not input controls in this public form.", "captures": index}, indent=2) + "\n")


if __name__ == "__main__":
    capture()
