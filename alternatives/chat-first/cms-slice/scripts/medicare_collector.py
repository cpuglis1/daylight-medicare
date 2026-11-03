#!/usr/bin/env python3
"""Bounded Medicare.gov public observation collector. Dry-run is the default.

Fresh headless Chromium only; never attach to a beneficiary's browser/profile.
All actual requests go through one paced, cached, no-redirect transport. Unknown
paths stop the run before transmission. A STOP file persists until reviewed.
"""
import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import cms_slice as cms

VERSION = "medicare-collector/1"
CONFIG = cms.ROOT / "config/medicare_collector.json"
CONTROL = cms.ROOT / "var/medicare-collector"
UA = "DaylightMedicareCollector/0.1 (+mailto:chris@beaconfederaladvisory.com)"
BLOCK = re.compile(rb"verify you are human|captcha challenge|pardon our interruption|access denied|<title>[^<]*(?:captcha|blocked)", re.I)


class Halt(cms.SourceError):
    pass


def utc():
    return datetime.now(timezone.utc)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def canonical(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname != "www.medicare.gov" or p.username or p.password or p.port not in (None, 443):
        raise Halt("URL outside reviewed HTTPS Medicare.gov host")
    if unquote(p.path) != p.path or ".." in p.path.split("/") or "\\" in url:
        raise Halt("Encoded/ambiguous path is outside the reviewed manifest")
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def robots_denies(url, policy):
    path = urlsplit(canonical(url)).path
    query = urlsplit(url).query
    if query:
        path += "?" + query
    matches = []
    for allow, patterns in [(True, policy["robots"]["allow"]), (False, policy["robots"]["disallow"])]:
        for pattern in patterns:
            end = pattern.endswith("$")
            bare = pattern[:-1] if end else pattern
            expression = "^" + re.escape(bare).replace(r"\*", ".*") + ("$" if end else "")
            if re.search(expression, path):
                matches.append((len(pattern.replace("*", "").replace("$", "")), allow))
    return bool(matches) and not max(matches)[1]


def check_config(config, *, enforce_freshness=True):
    policy_path = cms.ROOT / config["policy_path"]
    if cms.file_hash(policy_path) != config["policy_sha256"]:
        raise Halt("Reviewed site policy changed; review config before collection")
    policy = cms.load_json(policy_path)
    if enforce_freshness and utc() > datetime.fromisoformat(policy["robots"]["review_due_at_utc"]):
        raise Halt("Site-policy review window expired; save a newly reviewed policy first")
    qpath = cms.ROOT / config["queries_path"]
    if cms.file_hash(qpath) != config["queries_sha256"]:
        raise Halt("Fixed synthetic query manifest changed")
    return policy, cms.load_json(qpath)


@contextmanager
def exclusive(control):
    control.mkdir(parents=True, exist_ok=True)
    with (control / "run.lock").open("a+b") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Halt("Another collector owns the global rate/cycle lock") from error
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Guard:
    def __init__(self, config, policy, cycle, control=CONTROL, now=utc, clock=time.time, sleeper=asyncio.sleep):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,60}", cycle):
            raise Halt("Invalid refresh-cycle identifier")
        self.config, self.policy, self.control = config, policy, Path(control)
        self.now, self.clock, self.sleep = now, clock, sleeper
        self.control.mkdir(parents=True, exist_ok=True)
        self.root = self.control / "cycles" / cycle
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache = cms.load_json(self.root / "cache.json") if (self.root / "cache.json").exists() else {}
        self.state = cms.load_json(self.control / "pace.json") if (self.control / "pace.json").exists() else {"last_request_unix": 0}
        self.cycle = cycle
        counts = self.state.setdefault("cycle_counts", {})
        if cycle not in counts:
            log = self.root / "events.jsonl"
            counts[cycle] = sum(json.loads(line)["kind"] == "request" for line in log.read_text().splitlines()) if log.exists() else 0
        self.count, self.lock = counts[cycle], asyncio.Lock()

    def event(self, kind, **kwargs):
        with (self.root / "events.jsonl").open("a") as f:
            f.write(json.dumps({"at_utc": self.now().isoformat(), "kind": kind, **kwargs}, ensure_ascii=False) + "\n")

    def halt(self, reason):
        if not (self.control / "STOP").exists():
            dump(self.control / "STOP", {"at_utc": self.now().isoformat(), "reason": reason, "parser_version": VERSION})
        self.event("stopped", reason=reason)
        raise Halt(reason)

    def alive(self):
        if (self.control / "STOP").exists():
            raise Halt("Kill switch is active: " + str(self.control / "STOP"))

    def boundary(self, url, method, post_data=None):
        self.alive()
        try:
            normalized = canonical(url)
        except Halt as error:
            self.halt(str(error))
        security_post = False
        if method == "POST" and normalized in self.config.get("reviewed_public_security_post_urls", []) and post_data and len(post_data) <= 1_000_000:
            try:
                body = json.loads(post_data)
                security_post = isinstance(body, dict) and set(body) == {"sensor_data"} and isinstance(body["sensor_data"], str)
            except (ValueError, UnicodeError):
                pass
        if method != "GET" and not security_post:
            self.event("unreviewed_method", url=normalized, method=method)
            self.halt("Unreviewed HTTP method; synthetic POST bodies require a separate exact manifest review")
        if robots_denies(normalized, self.policy):
            self.halt("Robots denied path: " + urlsplit(normalized).path)
        # Ordinary browser-generated public security initialization, after exact
        # path/parameter review. Never generate/solve a challenge or forge tokens.
        parsed = urlsplit(normalized)
        args = parse_qs(parsed.query)
        security_init = (self.config.get("reviewed_public_security_initialization") is True
                         and parsed.path == "/_bm/get_params" and set(args) == {"type", "v"}
                         and args["type"] == ["get-akid"] and len(args["v"]) == 1
                         and re.fullmatch(r"[A-Za-z0-9/+= ]{16,128}", args["v"][0]) is not None)
        if normalized not in self.config["reviewed_get_urls"] and not security_init and not security_post:
            self.halt("Unreviewed request path/query: " + normalized)
        return normalized

    async def wait_for_slot(self):
        # Check every <=250ms so a STOP file interrupts pacing promptly.
        while self.clock() - self.state["last_request_unix"] < 5:
            self.alive()
            await self.sleep(min(.25, 5 - (self.clock() - self.state["last_request_unix"])))
        self.alive()
        if self.count >= 2000:
            self.halt("2,000-request per-run cap reached")
        self.count += 1
        self.state["cycle_counts"][self.cycle] = self.count
        self.state["last_request_unix"] = self.clock()
        dump(self.control / "pace.json", self.state)

    def record(self, url, status, headers, body, *, method="GET", post_hash=None):
        if len(body) > 10_000_000:
            self.halt("Response exceeds inspected size bound")
        digest = cms.sha256(body)
        raw = self.root / "raw" / digest
        raw.parent.mkdir(exist_ok=True)
        raw.write_bytes(body)
        key = url if method == "GET" else method + ":" + url + ":" + post_hash
        receipt = {"url": url, "method": method, "request_body_sha256": post_hash,
                   "retrieved_at_utc": self.now().isoformat(), "http_status": status,
                   "sha256": digest, "bytes": len(body), "parser_version": VERSION,
                   "headers": {k: v for k, v in headers.items() if k.lower() in {"content-type", "last-modified", "etag", "location"}},
                   "user_agent": UA, "retries": 0, "label": "Medicare.gov observation, retrieved " + self.now().date().isoformat()}
        # Store failed responses as evidence too; never serve them as successful cached pages.
        dump(self.root / "receipts" / (cms.sha256(key.encode()) + ".json"), receipt)
        self.event("response", **receipt)
        if status in {403, 429} or ("text/html" in headers.get("content-type", "") and BLOCK.search(body[:200000])):
            self.halt("Origin stop response/block page: HTTP " + str(status))
        if not 200 <= status < 300:
            self.halt("Unexpected status/redirect; no automatic redirect or retry: HTTP " + str(status))
        pin = self.config.get("response_sha256", {}).get(url)
        if pin and digest != pin:
            self.halt("Pinned application response changed; review schema/assets before continuing")
        self.cache[key] = receipt
        dump(self.root / "cache.json", self.cache)
        return receipt

    async def fetch(self, url, method, transport, post_data=None):
        async with self.lock:
            url = self.boundary(url, method, post_data)
            post_hash = cms.sha256(post_data) if post_data is not None else None
            key = url if method == "GET" else method + ":" + url + ":" + post_hash
            if key in self.cache:
                receipt = self.cache[key]
                raw = self.root / "raw" / receipt["sha256"]
                if not raw.exists() or raw.stat().st_size != receipt["bytes"] or cms.file_hash(raw) != receipt["sha256"]:
                    self.halt("Changed/missing cycle cache; no silent refetch")
                self.event("cache_hit", url=url, original_retrieved_at_utc=receipt["retrieved_at_utc"])
                return receipt, raw.read_bytes()
            await self.wait_for_slot()
            self.event("request", url=url, method=method, request_body_sha256=post_hash, request_number=self.count)
            try:
                status, headers, body = await transport()
            except Exception as error:
                self.halt("Transport failure; no retry: " + type(error).__name__)
            # Inspect in-flight result even if STOP was set while awaiting it; admit no next request.
            receipt = self.record(url, status, {k.lower(): v for k, v in headers.items()}, body, method=method, post_hash=post_hash)
            self.alive()
            return receipt, body


def plan_run(config, queries, task):
    selected = [q for q in queries["queries"] if q["task"] == task]
    return {"mode": "dry_run", "parser_version": VERSION, "task": task, "network_requests": 0,
            "queries": selected, "logical_query_count": len(selected), "target_plan_count": len(queries["plan_ids"]),
            "limits": {"minimum_interval_seconds": 5, "maximum_requests": 2000, "off_peak_eastern": "00:00–06:00"},
            "ready": config["adapters"][task]["ready"], "blockers": config["adapters"][task]["blockers"],
            "scope": "Only this pinned manifest; no arbitrary URL, drug list, resident input or account session accepted."}


async def browser_capture(config, policy, cycle, out, query, *, preflight=False):
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise Halt("Install the pinned optional Playwright collector dependency; see docs/MEDICARE_COLLECTOR.md") from error
    if not preflight and utc().astimezone(ZoneInfo("America/New_York")).hour not in range(0, 6):
        raise Halt("Live batch is restricted to 00:00–06:00 Eastern; use dry-run now")
    control = CONTROL
    with exclusive(control):
        guard = Guard(config, policy, cycle, control)
        starting_count = guard.count
        guard.alive()
        out.mkdir(parents=True, exist_ok=True)
        result = {"query": query, "started_at_utc": utc().isoformat(), "parser_version": VERSION,
                  "mode": "single_entry_preflight" if preflight else "live", "status": "incomplete", "observations": []}
        # Preflight has no plan/drug scenario; at most ten fresh requests, all individually reviewed.
        errors = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context(user_agent=UA, service_workers="block", accept_downloads=False)

            async def route_request(route):
                request = route.request
                try:
                    # External fonts/images/analytics are deliberately excluded before transmission.
                    if urlsplit(request.url).hostname != "www.medicare.gov":
                        guard.event("excluded_external_resource", host=urlsplit(request.url).hostname, resource_type=request.resource_type)
                        await route.abort("blockedbyclient")
                        return
                    if preflight and guard.count - starting_count >= 10:
                        guard.halt("Single-entry preflight request budget reached")

                    async def transport():
                        response = await route.fetch(max_redirects=0, max_retries=0, timeout=30000)
                        try:
                            if int(response.headers.get("content-length", "0")) > 10_000_000:
                                guard.halt("Response Content-Length exceeds inspected size bound")
                            return response.status, response.headers, await response.body()
                        finally:
                            await response.dispose()
                    receipt, body = await guard.fetch(request.url, request.method, transport, request.post_data_buffer)
                    await route.fulfill(status=receipt["http_status"], headers={"content-type": receipt["headers"].get("content-type", "application/octet-stream")}, body=body)
                except Exception as error:
                    errors.append(str(error))
                    await route.abort("blockedbyclient")

            await context.route("**/*", route_request)
            await context.route_web_socket("**/*", lambda socket: socket.close())
            page = await context.new_page()
            try:
                await page.goto(query["url"], wait_until="domcontentloaded", timeout=90000)
                # Pacing applies to scripts/subresources too; an empty SPA shell is
                # never a successfully rendered observation.
                for _ in range(360):
                    if errors:
                        raise Halt(errors[0])
                    guard.alive()
                    root = page.locator("#mct-root")
                    if await root.count() and len((await root.inner_text()).strip()) >= 50:
                        break
                    await asyncio.sleep(.25)
                else:
                    guard.halt("App shell did not render expected public content before the bounded readiness timeout")
                html = (await page.content()).encode()
                if BLOCK.search(html[:200000]):
                    guard.halt("Rendered CAPTCHA/block page")
                raw_hash = cms.sha256(html)
                (out / (raw_hash + ".html")).write_bytes(html)
                await page.screenshot(path=str(out / "page.png"), full_page=True)
                if not await page.locator("#mct-root").count() or len((await page.locator("#mct-root").inner_text()).strip()) < 50:
                    guard.halt("Unexpected root/page shape")
                result.update(status="entry_only" if preflight else "raw_capture_requires_parser_review", rendered_html_sha256=raw_hash)
                # Raw capture is never promoted to plan facts or successful scenario coverage here.
            except Exception as error:
                result.update(status="stopped", reason=str(error))
                try:
                    await page.screenshot(path=str(out / "stopped.png"), full_page=True)
                except Exception:
                    pass
            finally:
                await context.close()
                await browser.close()
                result.update(finished_at_utc=utc().isoformat(), outgoing_requests=guard.count - starting_count,
                              cycle_requests=guard.count, event_log=str(guard.root / "events.jsonl"))
                dump(out / "run.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "preflight", "run", "stop", "status"])
    parser.add_argument("--task", choices=["C17", "C20", "C22"], default="C17")
    parser.add_argument("--cycle", default="20261020-review")
    parser.add_argument("--out", type=Path, default=cms.ROOT / "reports/collector-dry-run.json")
    args = parser.parse_args()
    if args.command == "stop":
        dump(CONTROL / "STOP", {"at_utc": utc().isoformat(), "reason": "Operator kill switch"})
        print("Collector stopped. Review STOP and source evidence before any manual restart.")
        return 0
    if args.command == "status":
        print(json.dumps({"stopped": (CONTROL / "STOP").exists(), "control": str(CONTROL)}))
        return 0
    try:
        config = cms.load_json(CONFIG)
        policy, queries = check_config(config, enforce_freshness=args.command != "plan")
        if args.command == "plan":
            result = plan_run(config, queries, args.task)
            dump(args.out, result)
        elif args.command == "preflight":
            result = asyncio.run(browser_capture(config, policy, args.cycle, args.out, {"url": "https://www.medicare.gov/plan-compare/", "task": "C16", "inputs": "No scenarios; approved entry only"}, preflight=True))
        else:
            if not config["adapters"][args.task]["ready"]:
                raise Halt("Scenario adapter not source-validated: " + "; ".join(config["adapters"][args.task]["blockers"]))
            jobs = [q for q in queries["queries"] if q["task"] == args.task]
            if not jobs or any("url" not in q for q in jobs):
                raise Halt("Reviewed browser workflow/URL missing from fixed task manifest")
            results = []
            for index, query in enumerate(jobs):
                capture = asyncio.run(browser_capture(config, policy, args.cycle, args.out / f"{index:04d}", query))
                results.append(capture)
                if capture["status"] == "stopped":
                    break
            result = {"mode": "live", "task": args.task,
                      "status": "stopped" if results[-1]["status"] == "stopped" else "raw_captures_require_parser_review",
                      "outgoing_requests": sum(r["outgoing_requests"] for r in results), "captures": results}
            dump(args.out / "batch.json", result)
        print(json.dumps({k: result[k] for k in ["mode", "task", "status", "reason", "logical_query_count", "network_requests", "outgoing_requests", "ready"] if k in result}))
        return 0 if result.get("status") != "stopped" else 2
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        print("STOP:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
