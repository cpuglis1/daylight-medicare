#!/usr/bin/env python3
"""Start a fictional advisor on an ephemeral loopback port and check its API."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import uuid


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "alternatives/advisor-first"))
    from server import build
    with tempfile.TemporaryDirectory(prefix="daylight-advisor-smoke-") as directory:
        service = build(0, fixture=True, database=Path(directory) / "fictional.sqlite3")
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        origin = "http://127.0.0.1:" + str(service.server_port)
        cookie = None

        def request(path, payload=None, csrf=None):
            nonlocal cookie
            connection = http.client.HTTPConnection("127.0.0.1", service.server_port, timeout=20)
            headers = {"Origin": origin}
            if cookie:
                headers["Cookie"] = cookie
            if payload is not None:
                headers["Content-Type"] = "application/json"
            if csrf:
                headers["X-Daylight-CSRF"] = csrf
            try:
                connection.request("POST" if payload is not None else "GET", path,
                                   None if payload is None else json.dumps(payload), headers)
                response = connection.getresponse()
                if response.getheader("Set-Cookie"):
                    cookie = response.getheader("Set-Cookie").split(";", 1)[0]
                body = response.read()
                if response.status != 200:
                    raise RuntimeError("FIXTURE_HTTP_CHECK_FAILED")
                return body
            finally:
                connection.close()

        try:
            page = request("/")
            if b"Daylight" not in page:
                raise RuntimeError("FIXTURE_PAGE_MISSING")
            assets = ["/advisor.js", "/advisor.css", "/fonts/atkinson-400.woff2",
                      "/fonts/fraunces.woff2", "/art/arrival-option-a.jpg"]
            for asset in assets:
                if not request(asset):
                    raise RuntimeError("FIXTURE_ASSET_EMPTY")
            session = json.loads(request("/api/guest/session"))
            initial = json.loads(request("/api/conversation/initial"))
            result = json.loads(request("/api/conversation/turn", {
                "guide": initial["guide"], "record": initial["record"],
                "requestId": str(uuid.uuid4()), "action": {"type": "start"}}, session["csrf"]))
            assessment = result["assessment"]
            if (assessment["personalizedRecommendationAllowed"] is not False
                    or assessment["externalVerificationReady"] is not False):
                raise RuntimeError("FIXTURE_RELEASE_GATE_CHANGED")
            print(json.dumps({"schema": "daylight-advisor-smoke/v1", "passed": True,
                "http_checks": len(assets) + 4, "fixture": True,
                "personal_recommendations": False, "external_verification": False,
                "real_model_calls": 0, "private_research_connected": False}, indent=2))
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
