#!/usr/bin/env python3
"""Capture the complete notice list linked by the pinned L04 CMS index.

Public CMS requests only. Existing L02 evidence is reused by exact URL/hash;
no stopped carrier or Plan Finder endpoint is accessed. No automatic retries.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import threading
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/data/l04-pdp-availability-2026-10-25"
INDEX = "https://www.cms.gov/medicare/audits-compliance/part-c-d/part-c-and-part-d-enforcement-actions"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class IndexRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = self.in_cell = self.skip_label = False
        self.rows = []
        self.cells = []
        self.parts = []
        self.href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == "dynamic_list_items_table":
            self.active = True
        if not self.active:
            return
        if tag == "tr":
            self.cells, self.href = [], None
        elif tag == "td":
            self.in_cell, self.parts = True, []
        elif tag == "label":
            self.skip_label = True
        elif tag == "a" and self.in_cell:
            self.href = urljoin(INDEX, attrs["href"])

    def handle_data(self, data):
        if self.active and self.in_cell and not self.skip_label:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag == "label":
            self.skip_label = False
        elif tag == "td":
            self.cells.append(" ".join(" ".join(self.parts).split()))
            self.in_cell = False
        elif tag == "tr" and self.cells:
            if len(self.cells) != 5 or not self.href:
                raise ValueError("Unexpected enforcement index row")
            self.rows.append(dict(zip(
                ["action_date", "organization", "action", "basis", "effective_date"], self.cells
            ), url=self.href))
        elif tag == "table":
            self.active = False


class DownloadLinks(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.urls = base, []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "field--name-field-downloads" in attrs.get("class", "").split():
                self.depth = 1
        href = attrs.get("href", "")
        if tag == "a" and self.depth and href:
            url = urljoin(self.base, href)
            if url not in self.urls:
                self.urls.append(url)

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1


def acquire(out):
    out.mkdir()  # Immutable acquisition revision; refuse an existing directory.
    (out / "raw").mkdir()
    (out / "text").mkdir()
    cached = {}
    for manifest in [BASE / "acquisition-r1/source-manifest.json",
                     ROOT / "docs/data/l02-ma-availability-2026-10-25/supplemental-r1/source-manifest.json",
                     *sorted(BASE.glob("restriction-acquisition-r*/source-manifest.json"))]:
        value = json.loads(manifest.read_text())
        records = value["sources"]
        records = records.values() if isinstance(records, dict) else records
        for record in records:
            url = record.get("requested_url", record.get("url"))
            digest = record.get("sha256")
            if not url or not digest:
                continue
            path = ROOT / record["path"] if record.get("path") else manifest.parent / "raw" / digest
            if path.exists() and sha(path.read_bytes()) == digest:
                cached[url] = (path, record)
    lock, stopped, sources = threading.Lock(), set(), {}

    def fetch(url):
        if urlparse(url).hostname != "www.cms.gov" or urlparse(url).scheme != "https":
            raise ValueError(f"Non-CMS URL refused: {url}")
        with lock:
            if url in sources:
                return sources[url]
            if "www.cms.gov" in stopped:
                raise RuntimeError("CMS access STOP; no further requests")
        if url in cached:
            path, old = cached[url]
            data = path.read_bytes()
            record = {"url": url, "status": "captured", "reused_from": str(path.relative_to(ROOT)),
                      "retrieved_at_utc": old.get("retrieved_at_utc", old.get("observed_at_utc")),
                      "http_status": old.get("http_status", 200)}
        else:
            try:
                request = Request(url, headers={"User-Agent": "Daylight public-reference evidence check"})
                with urlopen(request, timeout=40) as response:
                    if urlparse(response.url).hostname != "www.cms.gov":
                        raise ValueError("Unexpected redirect host")
                    data = response.read(20_000_001)
                    if len(data) > 20_000_000:
                        raise ValueError("Source size exceeds 20 MB capture limit")
                    record = {"url": url, "final_url": response.url, "status": "captured",
                              "http_status": response.status,
                              "content_type": response.headers.get("Content-Type"),
                              "last_modified": response.headers.get("Last-Modified"),
                              "retrieved_at_utc": datetime.now(timezone.utc).isoformat()}
            except HTTPError as exc:
                with lock:
                    if exc.code in (401, 403, 429):
                        stopped.add("www.cms.gov")
                record = {"url": url, "status": "stopped" if exc.code in (401, 403, 429) else "http_error",
                          "http_status": exc.code, "detail": str(exc)}
                with lock:
                    sources[url] = record
                return record
        digest = sha(data)
        path = out / "raw" / digest
        path.write_bytes(data)
        record.update(sha256=digest, bytes=len(data), path=str(path.relative_to(ROOT)))
        if data.startswith(b"%PDF-"):
            text_path = out / "text" / (digest + ".txt")
            result = subprocess.run(["pdftotext", "-layout", str(path), str(text_path)], capture_output=True)
            if result.returncode:
                raise ValueError(f"PDF extraction failed: {url}")
            body = text_path.read_text()
            record.update(text_path=str(text_path.relative_to(ROOT)), text_sha256=sha(text_path.read_bytes()),
                          pages=body.count("\f"), text_characters=len(body),
                          contract_tokens=sorted(set(re.findall(r"\b[HRS]\d{4}\b", body))))
        with lock:
            sources[url] = record
        return record

    errors = []
    try:
        index = fetch(INDEX)
        parser = IndexRows()
        parser.feed((ROOT / index["path"]).read_text())
        rows = parser.rows
        if not rows or len({r["url"] for r in rows}) != len(rows):
            raise ValueError("Empty or duplicated enforcement index")
        dump(out / "index-rows.json", rows)

        def notice(row):
            try:
                page = fetch(row["url"])
                if page["status"] != "captured":
                    return dict(row, downloads=[], error=page["status"])
                links = DownloadLinks(row["url"])
                links.feed((ROOT / page["path"]).read_text())
                if not links.urls:
                    return dict(row, downloads=[], source_limit="CMS page has no downloadable notice")
                for url in links.urls:
                    fetch(url)
                return dict(row, downloads=links.urls)
            except Exception as exc:
                return dict(row, downloads=[], error=str(exc))

        with ThreadPoolExecutor(max_workers=4) as pool:
            notices = list(pool.map(notice, rows))
        errors = [n for n in notices if n.get("error")]
        dump(out / "notices.json", notices)
    finally:
        dump(out / "source-manifest.json", {"schema": "l04-restriction-acquisition/1", "index_url": INDEX,
             "sources": [sources[k] for k in sorted(sources)], "stopped_hosts": sorted(stopped), "errors": errors})
    print(json.dumps({"out": str(out.relative_to(ROOT)), "index_rows": len(rows), "sources": len(sources),
                      "pdfs": sum("text_path" in r for r in sources.values()), "errors": len(errors),
                      "notice_pages_without_download": sum(bool(n.get("source_limit")) for n in notices),
                      "stopped_hosts": sorted(stopped)}))
    return 1 if errors or stopped or any(s["status"] != "captured" for s in sources.values()) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(acquire(args.out.resolve()))
