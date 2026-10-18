"""Source-bound educational and local-provider facts for the bounded demo."""

import re
import subprocess

import cms_slice as cms
from evidence_store import PublicSources, html_text

CONFIG = cms.ROOT / "data-sources/demo-knowledge.json"


def normalized(text):
    return " ".join(text.split()).casefold()


class Knowledge:
    def __init__(self, sources=None, config=CONFIG):
        self.sources = sources or PublicSources()
        self.config = cms.load_json(config)
        self.facts, self.source_specs, documents = {}, {}, {}
        for fact in self.config["facts"]:
            source = fact["source_id"]
            if source not in documents:
                spec, raw = self.sources.read(source)
                self.source_specs[source] = spec
                if raw.startswith(b"%PDF"):
                    result = subprocess.run(["pdftotext", "-layout", str(self.sources.raw / spec["sha256"]), "-"], capture_output=True, check=True)
                    documents[source] = result.stdout.decode("utf-8").split("\f")
                else:
                    documents[source] = [html_text(raw)]
            if fact["source_sha256"] != self.source_specs[source]["sha256"]:
                raise cms.SourceError("Knowledge source changed; facts need renewed review: " + source)
            pages = documents[source]
            text = pages[fact["pdf_page"] - 1] if "pdf_page" in fact else "\n".join(pages)
            if not all(normalized(anchor) in normalized(text) for anchor in fact["support"]):
                raise cms.SourceError("Knowledge support anchor changed: " + fact["id"])
            if fact["id"] in self.facts:
                raise cms.SourceError("Duplicate knowledge fact")
            self.facts[fact["id"]] = {k: v for k, v in fact.items() if k not in {"support", "source_sha256"}} | {
                "evidence": PublicSources.evidence(self.source_specs[source])}
        self.version = cms.file_hash(config)

    def topic(self, topic):
        if topic not in {f["topic"] for f in self.facts.values()}:
            raise cms.SourceError("Unsupported education/local-source topic")
        return {"status": "published_facts_with_scope_limits", "facts": [f for f in self.facts.values() if f["topic"] == topic],
                "knowledge_version": self.version, "qualified_domain_review": "pending"}

    def provider(self, name, plan_id=None):
        if not isinstance(name, str) or len(name) > 100:
            raise cms.SourceError("Specify a short provider or facility name")
        key = name.casefold()
        topic = "nch" if re.search(r"\bnch\b|naples (community|comprehensive)", key) else "physicians_regional" if "physicians regional" in key else None
        facts = self.topic(topic)["facts"] if topic else []
        return {"query": name, "plan_id": plan_id, "status": "published_notice_only_exact_network_unresolved" if facts else "exact_provider_plan_location_evidence_unavailable",
                "facts": facts, "exact_plan_participation": None, "accepting_new_patients": None,
                "limits": ["Carrier notices and facility lists do not verify an individual clinician or every plan product", "A missing directory result is not an out-of-network determination", "Confirm the exact address, plan/network, service setting, and effective date"]}
