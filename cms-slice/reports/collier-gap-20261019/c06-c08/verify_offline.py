"""Run from the root of an extracted demo bundle, with network and PATH disabled."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path.cwd() / "scripts"))
import cms_slice as cms
from chat import Chat, ResponsesClient
from demo_tools import DemoTools
from demo_release import verify
from evidence_store import PublicSources
from live_conversation import LiveConversation
from naples_catalog import NaplesCatalog


def no_network(*args, **kwargs):
    raise AssertionError("Offline replay attempted a network call")


socket.socket = socket.create_connection = no_network
assert not (cms.ROOT / "data-sources").exists(), "Use an isolated extracted bundle"
tools = DemoTools(release="snapshot")
chat = Chat(tools, ResponsesClient(key="", model=""))
resources = tools.local_resources()
pace, shine = (resources["resources"][k] for k in ("pace", "shine"))
assert pace["cms_identity"]["Contract Number"] == "H5934"
assert pace["coverage_path"] == "separate_conditional_program"
assert pace["eligibility_status"] == "not_determined"
assert pace["service_area"]["zip_codes"] is None
assert pace["service_area"]["address_confirmation_phone"] == "239-985-6400"
assert shine["sites"][0]["phone"] == "239-262-8388"
assert shine["sites"][1]["restriction"] == "Members only"
assert shine["phone"] == "1-800-963-5337"
assert resources["other_plan_types"]["records_searched"] == 70
assert not resources["other_plan_types"]["cost_plan_ids"]
assert not resources["other_plan_types"]["msa_plan_ids"]
questions = ["I am 54 and live in 34102. Do I qualify for Hope PACE?", "SHINE appointments", "I have union retiree coverage", "I have VA healthcare", "I have TRICARE For Life", "My Medigap policy is from 2001"]
answers = []
for question in questions:
    answer = LiveConversation(chat).answer(message=question)
    assert answer["facts"] and answer["conversation_mode"] == "source_only"
    assert not answer["personal_recommendation"] and not answer["model_request_completed"]
    answers.append({"question": question, "fact_ids": [f["id"] for f in answer["facts"]], "flags": answer["coordination_flags"]})
cleared = LiveConversation(chat).answer(message="I don't have TRICARE", history=[{"role": "user", "content": "I have TRICARE"}])
assert cleared["coordination_flags"] == []
local = [f for f in tools.knowledge.facts.values() if f.get("topic") in {"pace", "shine"} or f.get("topic", "").startswith("coordination_")]
assert len(local) == 11
sources = PublicSources(Path("snapshot/public-sources.json"), Path("snapshot/public"))
pins = {}
for fact in local:
    for evidence in fact["evidence"]:
        spec, raw = sources.read(evidence["id"])
        assert cms.sha256(raw) == evidence["sha256"] == spec["sha256"]
        pins[spec["id"]] = spec["sha256"]
assert len(pins) == 12
catalog = NaplesCatalog(tools).list()
assert len(catalog["plans"]) == 70
manifest = verify("snapshot")
assert manifest["source_receipt"]["packaged_pharmacy_networks"] == 61
receipt = {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(), "release_id": manifest["release_id"],
           "isolated": True, "network": "blocked", "model": "disabled", "pdf_tools": "unavailable (empty PATH)",
           "local_facts_checked": len(local), "source_pins_checked": pins, "answers": answers,
           "latest_negative_clears_flag": True, "catalog_records": 70, "packaged_pharmacy_networks": 61,
           "review_after_utc": tools.data_review["review_after_utc"], "qualified_domain_signoff": "pending"}
Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({k:v for k,v in receipt.items() if k not in {"answers", "source_pins_checked"}}, indent=2))
