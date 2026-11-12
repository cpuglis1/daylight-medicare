#!/usr/bin/env python3
"""Run local Naples evidence chat with visible conversation text logs."""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

import cms_slice as cms
from chat import Chat, ModelUnavailable
from conversation import Conversation
from demo_tools import DemoTools
from identity_lookup import IdentityLookup
from naples_catalog import NaplesCatalog
from live_conversation import LiveConversation
from runtime_env import load_model_env
from usage_metrics import TurnUsage
from catalog_actions import match_catalog_action
from conversation_state import normalized
from naples_catalog import conversation_summary
from transcript_log import TranscriptLog, conversation_id
from starter_questions import starter_answer
from consumer_acceptance import ConsumerAcceptance, AcceptanceRequired, NOTICE

WEB = cms.ROOT / "apps/chat"


def make_server(chat, port=8766, debug_metrics=False, transcript_dir=None):
    # Never inherit the Python research flag at a consumer-facing boundary.
    upstream = getattr(chat.tools, "consumer_acceptance", None)
    acceptance = ConsumerAcceptance(getattr(upstream, "release", None))
    transcripts = TranscriptLog(transcript_dir) if transcript_dir is not None else TranscriptLog()
    conversation = Conversation(chat)
    catalog = NaplesCatalog(chat.tools) if hasattr(chat.tools, "snapshot") else None
    live = LiveConversation(chat) if catalog is not None else None
    slots, rate_lock, arrivals = threading.BoundedSemaphore(2), threading.Lock(), deque()
    assets = {"/": ((WEB / "index.html").read_bytes(), "text/html; charset=utf-8"),
              "/app.js": ((WEB / "app.js").read_bytes(), "text/javascript; charset=utf-8"),
              "/styles.css": ((WEB / "styles.css").read_bytes(), "text/css; charset=utf-8"),
              "/zip-counties.json": ((WEB / "zip-counties.json").read_bytes(), "application/json; charset=utf-8"),
              "/daylight.svg": ((WEB / "daylight.svg").read_bytes(), "image/svg+xml")}
    for font in sorted((WEB / "fonts").glob("*.woff2")):
        assets[f"/fonts/{font.name}"] = (font.read_bytes(), "font/woff2")
    for art in sorted((WEB / "art").glob("*.svg")):
        assets[f"/art/{art.name}"] = (art.read_bytes(), "image/svg+xml")

    def catalog_action(payload):
        if catalog is None:raise cms.SourceError("Catalog unavailable")
        action=payload.get("action","list")
        if action=="compare":return catalog.compare(payload.get("plan_ids"))
        if action=="plan":
            ids=payload.get("plan_ids")
            if not isinstance(ids,list) or len(ids)!=1 or not isinstance(ids[0],str):raise cms.SourceError("Choose one exact plan")
            record=catalog.record(ids[0])
            return {"kind":"plan","title":"Selected plan","plans":[record],"count":1,"facts":catalog.facts(record),"ordering":"Selected plan.","cost_scope":"Plan premium is not total Medicare cost.","scope":"Check missing evidence and plan conditions."}
        if action!="list":raise cms.SourceError("Unknown catalog action")
        return catalog.list(category=payload.get("category","all"),priorities=payload.get("priorities"),year=payload.get("year","2027"),county_fips=payload.get("county_fips","12021"))

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
                state = acceptance.status()
                return self.respond(200, {"scope": "Validated evidence is required before consumer data access",
                                          **state,
                                          "model_configured": chat.client.available, "snapshot_id": chat.tools.version,
                                          "model_id": chat.client.model if chat.client.available else None,
                                          "live_conversation_available": state["consumer_ready"] and live is not None and chat.client.available,
                                          "catalog_count": len(catalog.rows) if catalog and state["consumer_ready"] else 0,
                                          "conversation_available": state["consumer_ready"],
                                          "conversation_logging":True, "storage":"Visible conversations are saved as local .txt files; no persistent customer profile", "domain_signoff": "accepted" if state["consumer_ready"] else "pending"})
            if target.path == "/api/local-resources":
                try:
                    acceptance.require_release()
                    return self.respond(200, acceptance.require_output(chat.tools.local_resources()))
                except AcceptanceRequired:
                    return self.respond(503, {"error": NOTICE, "validation_status": "pending"})
            if target.path in assets:
                if not acceptance.status()["consumer_ready"]:
                    if target.path == "/":
                        page = ("<!doctype html><html lang='en'><meta charset='utf-8'>"
                                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                                "<title>Daylight — validation pending</title><main>"
                                "<h1>Data validation is in progress</h1><p>" + NOTICE + "</p></main></html>")
                        return self.respond(200, page.encode(), "text/html; charset=utf-8")
                    return self.respond(503, {"error": NOTICE, "validation_status": "pending"})
                body, mime = assets[target.path]
                return self.respond(200, body, mime)
            return self.respond(404, {"error": "No such resource"})

        def do_POST(self):
            if not self.local():
                return self.respond(403, {"error": "Local demo host only"})
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self.respond(403, {"error": "Request origin rejected"})
            if self.path not in {"/api/chat", "/api/conversation", "/api/live-chat", "/api/catalog", "/api/conversation-start", "/api/intake-answer"}:
                return self.respond(404, {"error": "No such action"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.respond(415, {"error": "Use a bounded JSON request"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit = 150000 if self.path == "/api/live-chat" else 30000 if self.path == "/api/conversation" else 16000
                if not 1 <= length <= limit:
                    return self.respond(413, {"error": "Request body is outside the demo size bound"})
                payload = json.loads(self.rfile.read(length))
                allowed = {"message", "intake", "history", "selections", "state"} if self.path == "/api/live-chat" else {"action", "category", "priorities", "plan_ids", "year", "county_fips"} if self.path == "/api/catalog" else {"message", "profile", "history", "selections"} if self.path == "/api/conversation" else {"message", "selections", "use_model"}
                allowed = {"conversation_id"} if self.path=="/api/conversation-start" else allowed | {"conversation_id"}
                if self.path=="/api/intake-answer":allowed={"conversation_id","field","value","recipient"}
                if self.path=="/api/catalog":allowed.add("user_message")
                if not isinstance(payload, dict) or set(payload) - allowed or (self.path not in {"/api/catalog","/api/conversation-start","/api/intake-answer"} and "message" not in payload):
                    raise cms.SourceError("Specify message and optional explicit selections/use_model only")
                if "user_message" in payload and (not isinstance(payload["user_message"],str) or len(payload["user_message"])>1200):raise cms.SourceError("Invalid catalog message")
                identifier=conversation_id(payload.get("conversation_id"))
                if self.path=="/api/intake-answer":
                    starter_question,starter_value=starter_answer(payload.get("field"),payload.get("value"),payload.get("recipient","self"))
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
            if self.path in {"/api/conversation-start","/api/intake-answer"}:
                try:
                    if self.path=="/api/intake-answer":
                        transcripts.append(identifier,starter_value,starter_question=starter_question)
                    else:
                        transcripts.append(identifier,opening=True)
                    self.respond(200,{"conversation_id":identifier,"conversation_log_saved":True})
                except OSError:
                    self.respond(503,{"error":"The local conversation log could not be created."})
                slots.release()
                return
            result = {}
            code = 200
            try:
                with TurnUsage(chat.client.model) as usage:
                    try:
                        acceptance.require_release()
                        if self.path == "/api/catalog":
                            result = catalog_action(payload)
                            result["tool_calls"] = ["compare_plans" if payload.get("action")=="compare" else "catalog_plan" if payload.get("action")=="plan" else "catalog"]
                        elif self.path == "/api/live-chat":
                            if live is None:
                                raise ModelUnavailable("Live conversation tools are unavailable")
                            current_state = normalized(payload.get("state"))
                            if isinstance(payload["message"],str) and re.search(r"\bI live in Collier County\b",payload["message"],re.I):
                                current_state["coverage_context"]["county"]="Collier County"
                            action = match_catalog_action(payload["message"],current_state["on_screen"])
                            if action:
                                view = catalog_action(action)
                                compact = conversation_summary(view)
                                question = "These plans cover Collier County, Florida. Is that where the person lives?" if current_state["path"]!="see_plans" and current_state["coverage_context"]["county"]!="Collier County" else ""
                                result = {"text":"Here are the published Collier County plans. This order isn't a recommendation.",
                                          "question":question,"catalogs":[view],"facts":compact["facts"],"fact_ids":[f["id"] for f in compact["facts"]],
                                          "tool_calls":["compare_plans" if view["kind"]=="comparison" else "catalog_plan" if view["kind"]=="plan" else "catalog"],"quick_replies":[],
                                          "state_update":{"path":"see_plans","coverage_context":current_state["coverage_context"]},
                                          "on_screen":{"view":view["kind"],"category":view.get("category"),"sorted_by":view.get("scored_criteria",[]),"unscored":view.get("unscored_priorities",[]),"plan_ids":[] if view["kind"]=="catalog" else [p["id"] for p in view["plans"]]}}
                                from live_conversation import validate_live
                                validate_live(payload.get("intake",{}),payload.get("history") or [],payload["message"],payload.get("selections") or {})
                                result.update(chat.tools.coordination([current_state['current_coverage']]+[i['content'] for i in (payload.get('history') or [])[-12:] if i['role']=='user']+[payload['message']]))
                            else:
                                result = live.answer(payload.get("intake",{}),payload.get("history"),payload["message"],payload.get("selections"),state=current_state)
                        elif self.path == "/api/conversation":
                            result = conversation.answer(payload.get("profile"),payload.get("history"),payload["message"],payload.get("selections"))
                        else:
                            result = chat.answer(payload["message"],selections=payload.get("selections"),use_model=payload.get("use_model",False))
                        acceptance.require_output(result)
                    except AcceptanceRequired:
                        code = 503
                        result = {"error": NOTICE, "validation_status": "pending"}
                    except ModelUnavailable as error:
                        code = 503
                        result = {"error":str(error),"source_only_mode_available":True}
                    except (cms.SourceError,OSError,ValueError,KeyError,TypeError,IndexError):
                        code = 422
                        result = {"error":"The requested source evidence is unavailable or outside the supported scope. No coverage conclusion was produced."}
                    metrics = usage.finish(result)
                if debug_metrics:
                    result["debug"] = metrics
                result["conversation_id"]=identifier
                try:
                    message=payload.get("message",payload.get("user_message"))
                    if message is None:
                        action=payload.get("action","list")
                        message="Compare selected plans" if action=="compare" else "View selected plan" if action=="plan" else "Browse published plans"
                    transcripts.append(identifier,message,result)
                    result["conversation_log_saved"]=True
                except OSError:
                    result["conversation_log_saved"]=False
                    result["notice"]="This reply is available, but the local conversation log could not be saved."
                self.respond(code,result)
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
    parser.add_argument("--env-file", help="Read only OPENAI_API_KEY and OPENAI_MODEL from this explicit local file; never source shell code")
    parser.add_argument("--reasoning-effort", choices=["none", "low"], default="none")
    parser.add_argument("--model-id", help="Temporary model override for evaluation; never writes configuration")
    parser.add_argument("--debug-metrics", action="store_true", help="Return content-free per-turn usage to local development clients")
    args = parser.parse_args()
    try:
        if args.env_file:
            load_model_env(args.env_file)
        if args.release and args.online:
            raise cms.SourceError("An immutable offline release cannot refresh identities; use the workspace --online mode")
        tools = DemoTools(identities=IdentityLookup(allow_network=args.online), release=args.release)
        chat = Chat(tools)
        chat.client.reasoning_effort = args.reasoning_effort
        if args.model_id:
            chat.client.model = args.model_id
        if args.command == "verify":
            print(json.dumps({**tools.consumer_acceptance.status(), "technical_verification_only": True,
                              "snapshot_id": tools.version, "source_records": len(tools.by_id), "supported_options": len(tools.by_id),
                              "historical_core_benefit_scope": len(tools.snapshot["options"]),
                              "drug_evidence_plans": sum(bool(j["selected_plan"]) for j in tools.joins.values()),
                              "packaged_pharmacy_networks": sum(n.endswith("-pharmacy.psv.gz") for n in tools.rx.manifest["cache_sha256"]),
                              "star_contracts": len(tools.star_ratings.get("contracts", {})),
                              "knowledge_facts": len(tools.knowledge.facts), "model_configured": chat.client.available}))
        elif args.command == "ask":
            print(json.dumps(chat.answer(args.message or "", use_model=args.model), indent=2))
        else:
            server = make_server(chat, args.port, debug_metrics=args.debug_metrics)
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
