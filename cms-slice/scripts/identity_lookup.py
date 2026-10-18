"""Public vocabulary and pharmacy identity lookups; never confirm a person's medicine."""

import argparse
import json
import re
from urllib.parse import urlencode

import cms_slice as cms
from evidence_store import PublicSources


def search_text(value, label):
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 100 or any(ord(c) < 32 for c in value) or re.search(r"https?://", value):
        raise cms.SourceError(label + " must be 2–100 ordinary text characters")
    return " ".join(value.split())


class IdentityLookup:
    def __init__(self, sources=None, allow_network=False):
        self.sources = sources or PublicSources()
        self.allow_network = allow_network

    def public_json(self, kind, url, refresh=False):
        source_id = kind + "-" + cms.sha256(url.encode())[:16]
        if self.allow_network:
            return self.sources.json(source_id, url, review_days=7, refresh=refresh)
        return self.sources.json(source_id)

    def medicines(self, name, refresh=False):
        name = search_text(name, "Medicine name")
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json?" + urlencode({"name": name.casefold()})
        spec, payload = self.public_json("rxnorm", url, refresh)
        candidates = {}
        for group in payload.get("drugGroup", {}).get("conceptGroup", []):
            for row in group.get("conceptProperties") or []:
                code = row.get("rxcui", "")
                if not re.fullmatch(r"[1-9]\d{0,7}", code) or not row.get("name"):
                    raise cms.SourceError("RxNorm returned an uninspected product identity")
                if row.get("tty") not in {"SBD", "SCD", "BPCK", "GPCK"}:
                    continue
                candidates[code] = {k: row.get(k) for k in ("rxcui", "name", "synonym", "tty")}
        values = sorted(candidates.values(), key=lambda row: (row["name"].casefold(), row["rxcui"]))
        return {"query": name, "status": "choose_and_confirm_exact_product" if values else "no_vocabulary_candidate_not_a_noncoverage_conclusion",
                "candidates": values[:200], "candidate_count": len(values), "truncated": len(values) > 200,
                "confirmed_rxcui": None, "coverage": None, "price": None,
                "evidence": PublicSources.evidence(spec),
                "limits": ["Vocabulary identity only; strength/form/brand and packaging must be confirmed", "Quantity and days supply remain unset", "No drug substitution or treatment advice"],
                "attribution": "This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse it."}

    def pharmacies(self, name, city="Naples", refresh=False):
        name = search_text(name, "Pharmacy name")
        city = search_text(city, "Pharmacy city")
        if city.casefold() not in {"naples", "marco island", "immokalee", "bonita springs"}:
            raise cms.SourceError("Only explicitly named southwest Florida cities are supported; city is not county/residence proof")
        query = {"version": "2.1", "enumeration_type": "NPI-2", "taxonomy_description": "Pharmacy",
                 "address_purpose": "LOCATION", "state": "FL", "city": city, "limit": 200}
        # Filter locally so a familiar store brand can match a differently named legal organization.
        url = "https://npiregistry.cms.hhs.gov/api/?" + urlencode(query)
        spec, payload = self.public_json("pharmacies", url, refresh)
        if "Errors" in payload:
            raise cms.SourceError("NPPES rejected the public identity request")
        candidates = []
        for provider in payload.get("results", []):
            number = str(provider.get("number", ""))
            if not re.fullmatch(r"\d{10}", number) or provider.get("basic", {}).get("status") != "A":
                continue
            organization = provider.get("basic", {}).get("organization_name", "")
            other_names = [x.get("organization_name", "") for x in provider.get("other_names", [])]
            addresses = [a for a in provider.get("addresses", []) if a.get("address_purpose") == "LOCATION"]
            addresses += provider.get("practiceLocations", [])
            for address in addresses:
                if address.get("state") != "FL" or address.get("city", "").casefold() != city.casefold():
                    continue
                haystack = " ".join([organization, *other_names, address.get("address_1", ""), address.get("address_2", "")]).casefold()
                if not all(token in haystack for token in name.casefold().split()):
                    continue
                candidates.append({"npi": number, "organization": organization, "other_names": other_names,
                                   "address": {k: address.get(k) for k in ("address_1", "address_2", "city", "state", "postal_code", "telephone_number")},
                                   "registry_last_updated": provider.get("basic", {}).get("last_updated"),
                                   "current_store_operation_confirmed": False})
        unique = {(p["npi"], json.dumps(p["address"], sort_keys=True)): p for p in candidates}
        return {"query": name, "city": city, "status": "choose_exact_store" if unique else "no_matching_registry_location_not_a_network_conclusion",
                "candidates": sorted(unique.values(), key=lambda p: (p["organization"], p["address"].get("address_1") or "", p["npi"])),
                "source_result_count": payload.get("result_count"), "source_limit": 200,
                "may_be_truncated": payload.get("result_count", 0) >= 200,
                "confirmed_pharmacy_npi": None, "network_participation": None,
                "evidence": PublicSources.evidence(spec),
                "limits": ["Registry identity only; not proof of current operation or plan participation", "City query is not a complete Collier County pharmacy census", "Exact store must be confirmed before network lookup"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["medicine", "pharmacy"])
    parser.add_argument("name")
    parser.add_argument("--city", default="Naples")
    parser.add_argument("--network", action="store_true", help="Permit public reference requests; no beneficiary identity is sent")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        lookup = IdentityLookup(allow_network=args.network)
        result = lookup.medicines(args.name, args.refresh) if args.kind == "medicine" else lookup.pharmacies(args.name, args.city, args.refresh)
        print(json.dumps(result, indent=2))
    except (cms.SourceError, OSError, ValueError) as error:
        parser.exit(2, "Identity evidence unavailable: " + str(error) + "\n")


if __name__ == "__main__":
    main()
