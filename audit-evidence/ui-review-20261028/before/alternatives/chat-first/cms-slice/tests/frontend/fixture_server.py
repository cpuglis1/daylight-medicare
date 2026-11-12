"""Chrome UI QA with conspicuously synthetic records; no real evidence or gate bypass.

Run: python3 tests/frontend/fixture_server.py --port 8876
This server is only a deterministic UI test double. Never use it to serve a demo
of real plans. Runtime consumer admission is tested separately without a double.
"""
import argparse
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps" / "chat"


def cell(amount):
    return {"state": "not_applicable", "value_cents": None} if amount is None else {"state": "value", "value_cents": amount}


def record(index, category, premium, limit, deductible):
    return {"id": f"synthetic-{index}", "name": f"TEST {index} — invented {category} record", "category": category,
            "plan_type": "Synthetic fixture", "metrics": {"monthly_premium": cell(premium), "medical_limit": cell(limit), "drug_deductible": cell(deductible)},
            "star_rating": {"state": "rated", "value": 3}, "premium_source_conflict": index == "D",
            "eligibility": "restricted_unconfirmed" if category == "SNP" else "not_assessed", "snp_type": "Synthetic eligibility condition",
            "notes": ["SYNTHETIC UI TEST ONLY. This is not a real plan and cannot be used for enrollment.", "Invented fields test layout, source conditions and missing-value behavior."],
            "source": {"url": "https://www.medicare.gov/plan-compare/"}}


RECORDS = [record("A", "MA-PD", 0, 500000, 30000), record("B", "MA-PD", 1200, 300000, 0),
           record("C", "MA-PD", 700, 600000, 10000), record("D", "MA-PD", 500, 400000, 20000),
           record("E", "PDP", 730, None, 10000), record("F", "MA", 100, 450000, None), record("G", "SNP", 0, 200000, 0)]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            return self.send_json({"consumer_ready": True, "live_conversation_available": False, "synthetic_ui_test": True})
        if self.path == "/":
            body = (WEB / "index.html").read_text().replace("<title>", "<title>SYNTHETIC UI QA · ")
            body = body.replace("<body>", '<body><aside style="padding:10px;background:#751c1c;color:white;text-align:center;font-weight:bold">SYNTHETIC UI TEST — invented records, not real coverage or enrollment options.</aside>')
            encoded = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            return self.wfile.write(encoded)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/catalog":
            return self.send_json({"error": "No conversation service in the synthetic UI test"}, 503)
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        category = payload.get("category", "all")
        records = [copy.deepcopy(p) for p in RECORDS if category == "all" or p["category"] == category]
        if payload.get("action") == "compare":
            ids = payload.get("plan_ids", [])
            records = [copy.deepcopy(p) for p in RECORDS if p["id"] in ids]
            return self.send_json({"kind": "comparison", "plans": records, "scope": "SYNTHETIC TEST. Roles differ; no personal fit established."})
        criteria = payload.get("priorities", [])

        def order(p):
            keys = []
            for key in criteria:
                c = p["metrics"][key]
                known = c["state"] == "value" and not (key == "monthly_premium" and p["premium_source_conflict"])
                keys.extend((not known, c["value_cents"] if known else 0))
            return (*keys, p["id"])

        records.sort(key=order)
        return self.send_json({"kind": "catalog", "plans": records, "category": category, "scored_criteria": criteria,
                               "scope": "SYNTHETIC UI TEST ONLY: invented records. No genuine coverage facts."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(WEB)))
    print(f"Synthetic UI QA only: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
