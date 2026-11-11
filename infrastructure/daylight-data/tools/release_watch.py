"""Discovery-only check for newer official releases of pinned public sources.

Reads release-watch.<year>.json, fetches each family's official listing page,
and reports links that differ from the file the layer was built from. It never
downloads a listed file, imports data or edits a pinned revision. Run it by
hand: routine network connectors stay off in scope.2026.json.

    python tools/release_watch.py --out reports/release-watch-<date>.json
    python tools/release_watch.py --page ma_pdp_landscape=/path/saved.html  # offline
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve()
DEFAULT_CONFIG = HERE.parents[1] / "config" / "release-watch.2026.json"
PAGE_BYTES = 5_000_000
TIMEOUT_SECONDS = 30
LIMITS = [
    "Discovery only: no listed file was downloaded or imported.",
    "A newer link is a candidate for review, not a verified, accepted or current release.",
    "A different coverage or rating year never substitutes for the pinned year.",
    "Pinned revisions, acceptance records and source STOPs are unchanged.",
]


class WatchError(Exception):
    """A family could not be checked; reported, never silently skipped."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text())
    if config.get("schema") != "daylight-release-watch/1":
        raise WatchError("Unsupported release-watch config schema")
    ids = [family["family_id"] for family in config["families"]]
    if len(ids) != len(set(ids)):
        raise WatchError("Duplicate family_id in release-watch config")
    for family in config["families"]:
        if family["method"] == "page_links":
            re.compile(family["link_pattern"])
            for key in ("page_url", "pinned_url"):
                host = urlsplit(family[key]).hostname
                if host not in config["allowed_hosts"]:
                    raise WatchError(f"{family['family_id']}: {key} host {host} is not allowed")
    return config


def fetch_page(url: str, allowed_hosts: list[str]) -> bytes:
    """Fetch one listing page with a host allowlist, size bound and timeout."""
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in allowed_hosts:
        raise WatchError(f"Refusing to fetch outside the allowlist: {url}")
    request = Request(url, headers={"User-Agent": "daylight-release-watch/1"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (allowlisted https)
        final = response.geturl()
        if urlsplit(final).hostname not in allowed_hosts:
            raise WatchError(f"Redirected outside the allowlist: {final}")
        data = response.read(PAGE_BYTES + 1)
    if len(data) > PAGE_BYTES:
        raise WatchError(f"Listing page exceeded {PAGE_BYTES} bytes: {url}")
    return data


def extract_links(page: bytes, page_url: str, pattern: str) -> list[dict]:
    text = html.unescape(page.decode("utf-8", errors="replace"))
    compiled = re.compile(pattern)
    found: dict[str, dict] = {}
    for href in re.findall(r"""href\s*=\s*["']([^"'#]+)""", text, flags=re.IGNORECASE):
        absolute = urljoin(page_url, href.strip())
        match = compiled.search(absolute)
        if match:
            groups = {k: v for k, v in match.groupdict().items() if v is not None}
            found[absolute] = {"url": absolute, **_version(groups)}
    return sorted(found.values(), key=lambda item: item["url"])


def _version(groups: dict) -> dict:
    year = next((v for k, v in groups.items() if k.startswith("year")), None)
    if year is not None:
        return {"year": int(year)}
    if "date" in groups:
        return {"release_date": datetime.strptime(groups["date"], "%m%d%Y").date().isoformat()}
    return {}


def _pinned_version(family: dict) -> dict:
    groups = re.search(family["link_pattern"], family["pinned_url"])
    if not groups:
        raise WatchError(f"{family['family_id']}: pinned_url does not match link_pattern")
    return _version({k: v for k, v in groups.groupdict().items() if v is not None})


def classify(family: dict, links: list[dict], coverage_year: int) -> dict:
    pinned = family["pinned_url"]
    pinned_version = _pinned_version(family)
    result = {
        "pinned_url": pinned,
        "pinned_listed": any(_same_file(link["url"], pinned) for link in links),
        "same_period_candidates": [],
        "newer_release_candidates": [],
        "other_year_candidates": [],
    }
    for link in links:
        if _same_file(link["url"], pinned):
            continue
        if "year" in link:
            bucket = ("same_period_candidates" if link["year"] == pinned_version.get("year", coverage_year)
                      else "other_year_candidates")
        elif "release_date" in link:
            bucket = ("newer_release_candidates"
                      if link["release_date"] > pinned_version["release_date"] else "same_period_candidates")
        else:
            bucket = "same_period_candidates"
        result[bucket].append(link)
    if result["same_period_candidates"] or result["newer_release_candidates"]:
        result["status"] = "candidate_requires_review"
    elif not result["pinned_listed"]:
        result["status"] = "pinned_not_listed_requires_review"
    else:
        result["status"] = "no_new_candidate_for_pinned_period"
    return result


def _same_file(a: str, b: str) -> bool:
    return urlsplit(a)._replace(scheme="https").geturl() == urlsplit(b)._replace(scheme="https").geturl()


def check_family(family: dict, config: dict, pages: dict[str, bytes], fetcher) -> dict:
    entry = {"family_id": family["family_id"], "layers": family["layers"], "label": family["label"],
             "method": family["method"]}
    if family["method"] == "delegated":
        return {**entry, "status": "delegated", "delegate": family["delegate"], "note": family.get("note")}
    try:
        page = pages.get(family["family_id"])
        source = "offline_file" if page is not None else "fetched"
        if page is None:
            page = fetcher(family["page_url"], config["allowed_hosts"])
        links = extract_links(page, family["page_url"], family["link_pattern"])
        if not links:
            raise WatchError("No matching links on the listing page; its layout may have changed")
        return {**entry, "page_url": family["page_url"], "page_source": source,
                "page_sha256": sha256_bytes(page), "links_found": len(links),
                **classify(family, links, config["coverage_year"])}
    except Exception as error:  # every family is reported; one failure never hides the rest
        return {**entry, "status": "check_failed", "page_url": family.get("page_url"),
                "error": f"{type(error).__name__}: {error}"}


def run(config_path: Path = DEFAULT_CONFIG, pages: dict[str, bytes] | None = None,
        fetcher=fetch_page, today: date | None = None) -> dict:
    config = load_config(config_path)
    pages = pages or {}
    unknown = set(pages) - {family["family_id"] for family in config["families"]}
    if unknown:
        raise WatchError(f"Offline pages for unknown families: {sorted(unknown)}")
    families = [check_family(family, config, pages, fetcher) for family in config["families"]]
    return {
        "schema": "daylight-release-watch-report/1",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked_on": (today or date.today()).isoformat(),
        "coverage_year": config["coverage_year"],
        "config_sha256": sha256_bytes(config_path.read_bytes()),
        "code_sha256": sha256_bytes(HERE.read_bytes()),
        "families": families,
        "not_yet_covered": config.get("not_yet_covered", []),
        "limits": LIMITS,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--page", action="append", default=[], metavar="FAMILY=PATH",
                        help="Use a saved listing page instead of fetching (repeatable)")
    parser.add_argument("--out", type=Path, help="Write the JSON report here; default prints it")
    args = parser.parse_args(argv)
    pages = {}
    for item in args.page:
        family_id, _, path = item.partition("=")
        if not path:
            parser.error("--page expects FAMILY=PATH")
        pages[family_id] = Path(path).read_bytes()
    report = run(args.config, pages)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return 1 if any(f["status"] == "check_failed" for f in report["families"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
