"""Small, content-addressed public-source cache with receipts and bounded HTTP reads."""

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import cms_slice as cms

REGISTRY = cms.ROOT / "data-sources/demo-sources.json"
RAW = cms.ROOT / "data-sources/raw/demo"
PUBLIC_HOSTS = {"nchmd.org", "www.physiciansregional.com", "www.physiciansregionalmedicalgroup.com",
                "www.medicare.gov", "www.cms.gov", "data.cms.gov", "rxnav.nlm.nih.gov",
                "npiregistry.cms.hhs.gov", "directory.cms.gov", "assets.humana.com",
                "www.devoted.com", "cdn.devoted.com", "assets.devoted.com", "www.aetnamedicare.com",
                "www.uhc.com", "www.wellcare.com", "files.guidewell.com", "www.floridablue.com"}


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if not self.skip and tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"}:
            self.parts.append("\n")
        if tag == "a":
            attrs = dict(attrs)
            if attrs.get("href"):
                self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    @property
    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


class PublicSources:
    def __init__(self, registry=REGISTRY, raw=RAW, opener=urlopen):
        self.registry, self.raw, self.opener = Path(registry), Path(raw), opener
        self.lock = threading.RLock()

    def inventory(self):
        return cms.load_json(self.registry) if self.registry.exists() else {"version": 1, "sources": {}}

    def read(self, source_id):
        with self.lock:
            spec = self.inventory()["sources"].get(source_id)
            if spec is None:
                raise cms.SourceError("Public source has not been captured: " + source_id)
            path = self.raw / spec["sha256"]
            if not path.is_file() or path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
                raise cms.SourceError("Public source snapshot is missing or changed: " + source_id)
            return spec, path.read_bytes()

    def capture(self, source_id, url, *, review_days=7, refresh=False, max_bytes=12_000_000):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in PUBLIC_HOSTS or parsed.username or parsed.port not in {None, 443}:
            raise cms.SourceError("Public-source URL is outside the explicit source allowlist")
        with self.lock:
            if not refresh and source_id in self.inventory()["sources"]:
                spec, raw = self.read(source_id)
                if spec["requested_url"] != url:
                    raise cms.SourceError("Source ID already belongs to a different request")
                return spec, raw
            request = Request(url, headers={"User-Agent": "NaplesMedicareResearch/1.0", "Accept": "application/json,text/html,application/pdf"})
            with self.opener(request, timeout=20) as response:
                if urlsplit(response.url).scheme != "https" or urlsplit(response.url).hostname not in PUBLIC_HOSTS:
                    raise cms.SourceError("Source redirected outside its approved public hosts")
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise cms.SourceError("Public source exceeds the inspected size bound")
                now = datetime.now(timezone.utc)
                spec = {"id": source_id, "requested_url": url, "final_url": response.url,
                        "sha256": cms.sha256(raw), "bytes": len(raw), "retrieved_at_utc": now.isoformat(),
                        "review_after_utc": (now + timedelta(days=review_days)).isoformat(),
                        "content_type": response.headers.get("Content-Type", ""),
                        "last_modified": response.headers.get("Last-Modified"),
                        "scope": "Public reference snapshot; no personal coverage confirmation or rights approval implied"}
            self.raw.mkdir(parents=True, exist_ok=True)
            path = self.raw / spec["sha256"]
            if not path.exists():
                path.write_bytes(raw)
            self.registry.parent.mkdir(parents=True, exist_ok=True)
            with self.registry.with_suffix(".lock").open("a+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                inventory = self.inventory()
                previous = inventory["sources"].get(source_id)
                spec["previous_sha256"] = previous["sha256"] if previous else None
                inventory["sources"][source_id] = spec
                with tempfile.NamedTemporaryFile(mode="w", dir=self.registry.parent, delete=False, encoding="utf-8") as tmp:
                    json.dump(inventory, tmp, indent=2, ensure_ascii=False)
                    tmp.write("\n")
                    temporary = Path(tmp.name)
                os.replace(temporary, self.registry)
            return spec, raw

    @staticmethod
    def evidence(spec):
        expired = datetime.now(timezone.utc) > datetime.fromisoformat(spec["review_after_utc"])
        return {k: spec[k] for k in ("id", "requested_url", "sha256", "retrieved_at_utc", "review_after_utc")} | {
            "freshness": "review_overdue" if expired else "within_review_window"}

    def json(self, source_id, url=None, **kwargs):
        spec, raw = self.capture(source_id, url, **kwargs) if url else self.read(source_id)
        try:
            return spec, json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise cms.SourceError("Public endpoint returned an invalid JSON document") from error


def html_text(raw):
    parser = VisibleHTML()
    parser.feed(raw.decode("utf-8", errors="strict"))
    return parser.text
