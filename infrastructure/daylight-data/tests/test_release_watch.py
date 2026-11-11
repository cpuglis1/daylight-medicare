"""Offline tests for the discovery-only release watch. No network is used."""
from datetime import date
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_watch", ROOT / "tools" / "release_watch.py")
rw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rw)
CONFIG = ROOT / "config" / "release-watch.2026.json"


def page(*hrefs):
    return ("<html><body>" + "".join(f'<a href="{h}">file</a>' for h in hrefs) + "</body></html>").encode()


def forbid_network(url, hosts):
    raise AssertionError(f"network forbidden in tests: {url}")


def offline_pages(**overrides):
    pages = {
        "ma_pdp_landscape": page("/files/zip/cy2026-landscape-202609.zip"),
        "pbp_benefits_json": page("/files/zip/pbp-benefits-2026-json.zip"),
        "star_ratings_tables": page("/files/zip/2026-star-ratings-data-tables.zip"),
        "rxnorm_prescribe": page("https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_10052026.zip"),
    }
    pages.update(overrides)
    return pages


def families(report):
    return {f["family_id"]: f for f in report["families"]}


def test_config_is_valid_and_every_pin_matches_its_pattern():
    config = rw.load_config(CONFIG)
    for family in config["families"]:
        if family["method"] == "page_links":
            assert rw._pinned_version(family)


def test_unchanged_pages_report_no_candidates():
    report = rw.run(CONFIG, offline_pages(), fetcher=forbid_network, today=date(2026, 11, 5))
    for family_id in ("ma_pdp_landscape", "pbp_benefits_json", "star_ratings_tables", "rxnorm_prescribe"):
        entry = families(report)[family_id]
        assert entry["status"] == "no_new_candidate_for_pinned_period", entry
        assert entry["pinned_listed"] is True
    assert families(report)["part_d_formulary_monthly_quarterly"]["status"] == "delegated"


def test_same_year_update_is_a_candidate_and_next_year_is_kept_separate():
    pages = offline_pages(ma_pdp_landscape=page(
        "/files/zip/cy2026-landscape-202609.zip",
        "/files/zip/cy2026-landscape-202611.zip",
        "/files/zip/cy2027-landscape-202610.zip",
    ))
    entry = families(rw.run(CONFIG, pages, fetcher=forbid_network))["ma_pdp_landscape"]
    assert entry["status"] == "candidate_requires_review"
    assert [c["url"] for c in entry["same_period_candidates"]] == [
        "https://www.cms.gov/files/zip/cy2026-landscape-202611.zip"]
    assert [c["year"] for c in entry["other_year_candidates"]] == [2027]


def test_both_pbp_naming_orders_are_recognized():
    pages = offline_pages(pbp_benefits_json=page(
        "/files/zip/pbp-benefits-2026-json.zip", "/files/zip/pbp-benefits-json-2027-zip.zip-0"))
    entry = families(rw.run(CONFIG, pages, fetcher=forbid_network))["pbp_benefits_json"]
    assert entry["status"] == "no_new_candidate_for_pinned_period"
    assert [c["year"] for c in entry["other_year_candidates"]] == [2027]


def test_next_rating_year_does_not_replace_the_pinned_ratings():
    pages = offline_pages(star_ratings_tables=page(
        "/files/zip/2026-star-ratings-data-tables.zip",
        "/files/zip/2027-star-ratings-data-tables-oct-8-2026.zip"))
    entry = families(rw.run(CONFIG, pages, fetcher=forbid_network))["star_ratings_tables"]
    assert entry["status"] == "no_new_candidate_for_pinned_period"
    assert entry["other_year_candidates"][0]["year"] == 2027


def test_newer_dated_release_is_flagged_and_older_is_not():
    pages = offline_pages(rxnorm_prescribe=page(
        "https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_09022026.zip",
        "https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_11022026.zip"))
    entry = families(rw.run(CONFIG, pages, fetcher=forbid_network))["rxnorm_prescribe"]
    assert entry["status"] == "candidate_requires_review"
    assert [c["release_date"] for c in entry["newer_release_candidates"]] == ["2026-11-02"]
    assert entry["pinned_listed"] is False


def test_pinned_file_missing_from_page_is_flagged():
    pages = offline_pages(star_ratings_tables=page("/files/zip/2027-star-ratings-data-tables.zip"))
    entry = families(rw.run(CONFIG, pages, fetcher=forbid_network))["star_ratings_tables"]
    assert entry["status"] == "pinned_not_listed_requires_review"


def test_layout_change_fails_loudly_without_hiding_other_families():
    pages = offline_pages(ma_pdp_landscape=b"<html><a href='/unrelated.pdf'>x</a></html>")
    report = rw.run(CONFIG, pages, fetcher=forbid_network)
    assert families(report)["ma_pdp_landscape"]["status"] == "check_failed"
    assert families(report)["star_ratings_tables"]["status"] == "no_new_candidate_for_pinned_period"


def test_only_listing_pages_are_ever_fetched():
    requested = []

    def recording_fetcher(url, hosts):
        requested.append(url)
        return page("/files/zip/cy2026-landscape-202609.zip", "/files/zip/2026-star-ratings-data-tables.zip",
                    "/files/zip/pbp-benefits-2026-json.zip",
                    "https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_10052026.zip")

    rw.run(CONFIG, {}, fetcher=recording_fetcher)
    config = json.loads(CONFIG.read_text())
    assert requested == [f["page_url"] for f in config["families"] if f["method"] == "page_links"]
    assert not any(url.endswith(".zip") for url in requested)


def test_fetch_refuses_hosts_outside_the_allowlist():
    with pytest.raises(rw.WatchError):
        rw.fetch_page("https://example.com/listing", ["www.cms.gov"])
    with pytest.raises(rw.WatchError):
        rw.fetch_page("http://www.cms.gov/listing", ["www.cms.gov"])


def test_offline_page_for_unknown_family_is_rejected():
    with pytest.raises(rw.WatchError):
        rw.run(CONFIG, {"not_a_family": b""}, fetcher=forbid_network)


def test_report_records_hashes_and_limits():
    report = rw.run(CONFIG, offline_pages(), fetcher=forbid_network)
    assert len(report["config_sha256"]) == 64 and len(report["code_sha256"]) == 64
    assert any("no listed file was downloaded" in limit for limit in report["limits"])
    assert report["not_yet_covered"]
