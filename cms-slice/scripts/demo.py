#!/usr/bin/env python3
"""Run the simple, local, session-only Naples evidence chat."""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

import cms_slice as cms
from chat import Chat, ModelUnavailable
from demo_tools import DemoTools
from identity_lookup import IdentityLookup

WEB = cms.ROOT / "apps/chat"


def make_server(chat, port=8766):
    slots, rate_lock, arrivals = threading.BoundedSemaphore(2), threading.Lock(), deque()
    assets = {"/": ((WEB / "index.html").read_bytes(), "text/html; charset=utf-8"),
              "/app.js": ((WEB / "app.js").read_bytes(), "text/javascript; charset=utf-8"),
              "/styles.css": ((WEB / "styles.css").read_bytes(), "text/css; charset=utf-8")}

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass

        def local(self):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in hosts

        def respond(self, code, value, mime="application/json; charset=utf-8"):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            for name, val in {"Content-Type": mime, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                              "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                              "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
                self.send_header(name, val)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local():
                return self.respond(403, {"error": "Local demo host only"})
            target = urlsplit(self.path)
            if target.query:
                return self.respond(422, {"error": "No health or conversation details in query URLs"})
            if target.path == "/api/status":
                return self.respond(200, {"scope": "Published 2027 Collier County evidence; no personal ranking, quote or enrollment",
                                          "model_configured": chat.client.available, "snapshot_id": chat.tools.version,
                                          "storage": "No chat history or profiles saved by this server", "domain_signoff": "pending"})
            if target.path in assets:
                body, mime = assets[target.path]
                return self.respond(200, body, mime)
            return self.respond(404, {"error": "No such resource"})

        def do_POST(self):
            if not self.local():
                return self.respond(403, {"error": "Local demo host only"})
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self.respond(403, {"error": "Request origin rejected"})
            if self.path != "/api/chat":
                return self.respond(404, {"error": "No such action"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.respond(415, {"error": "Use a bounded JSON request"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 16000:
                    return self.respond(413, {"error": "Request body is outside the demo size bound"})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) - {"message", "selections", "use_model"} or "message" not in payload:
                    raise cms.SourceError("Specify message and optional explicit selections/use_model only")
                if not isinstance(payload.get("use_model", False), bool):
                    raise cms.SourceError("use_model must be a boolean")
            except (ValueError, UnicodeError, cms.SourceError):
                return self.respond(422, {"error": "Invalid bounded chat request"})
            with rate_lock:
                now = time.monotonic()
                while arrivals and arrivals[0] < now - 60:
                    arrivals.popleft()
                if len(arrivals) >= 30:
                    return self.respond(429, {"error": "Demo request limit reached; try again shortly"})
                arrivals.append(now)
            if not slots.acquire(blocking=False):
                return self.respond(429, {"error": "The demo is answering two questions; try again shortly"})
            try:
                result = chat.answer(payload["message"], selections=payload.get("selections"), use_model=payload.get("use_model", False))
                self.respond(200, result)
            except ModelUnavailable as error:
                self.respond(503, {"error": str(error), "source_only_mode_available": True})
            except (cms.SourceError, OSError, ValueError, KeyError):
                self.respond(422, {"error": "The requested source evidence is unavailable or outside the supported scope. No coverage conclusion was produced."})
            finally:
                slots.release()

        def reject(self):
            self.respond(405, {"error": "This demo cannot save profiles or submit applications"})

        do_PUT = do_PATCH = do_DELETE = reject

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "verify", "ask"])
    parser.add_argument("message", nargs="?")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--release", help="Verified immutable release directory, or current; works without national source archives")
    parser.add_argument("--online", action="store_true", help="Allow public NLM/NPPES reference requests when not already captured")
    parser.add_argument("--model", action="store_true", help="Use the configured OpenAI adapter for ask; requires server-side environment values")
    args = parser.parse_args()
    try:
        if args.release and args.online:
            raise cms.SourceError("An immutable offline release cannot refresh identities; use the workspace --online mode")
        tools = DemoTools(identities=IdentityLookup(allow_network=args.online), release=args.release)
        chat = Chat(tools)
        if args.command == "verify":
            print(json.dumps({"snapshot_id": tools.version, "source_records": 70, "supported_options": 38, "knowledge_facts": len(tools.knowledge.facts), "model_configured": chat.client.available}))
        elif args.command == "ask":
            print(json.dumps(chat.answer(args.message or "", use_model=args.model), indent=2))
        else:
            server = make_server(chat, args.port)
            print(f"Naples research demo: http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        parser.exit(2, "Demo unavailable: " + str(error) + "\n")


if __name__ == "__main__":
    main()
