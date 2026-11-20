"""Audit synthetic D79 design traces; no runtime, model, network or customer data.

These are declared conversation segments for design review, not an intake engine,
accepted Medicare policy, observed user sessions or measured completion times.
"""
from pathlib import Path
import json

P = Path(__file__).resolve().parent
MAP = json.loads((P / "CRITICAL_INFORMATION_FIELD_MAP.json").read_text())
FIELDS = MAP["fields"]
GAPS = {g["id"] for g in MAP["additional_fact_gaps"]}

def fact(path, state="confirmed", entity=""):
    return {"fact": path, "state": state, "entity": entity}

def user(summary, *facts):
    return {"speaker": "user", "summary": summary, "facts": list(facts)}

def ask(summary, *requests):
    return {"speaker": "assistant", "summary": summary, "question_prompts": 1,
            "information_requests": list(requests)}

def request(path, entity="", kind="missing_detail"):
    return {"fact": path, "entity": entity, "kind": kind}

def result(summary):
    return {"speaker": "assistant", "summary": summary, "question_prompts": 0, "information_requests": []}

TRACES = [
    {"id": "S01", "task": "Direct general-learning question", "required": [],
     "messages": [user("A specific Medicare concept question already establishes the task.", fact("guide.fields.intent.goal")),
                  result("Answer within supported general-source scope; no ZIP, medicines or preference interview.")],
     "holds": ["No real answer/source execution is asserted by this trace."], "expected": [0, 0, 2]},
    {"id": "S02", "task": "Published local/year browsing with scope already supplied", "required": [fact("guide.fields.comparison.scope.zip"), fact("guide.fields.comparison.scope.county"), fact("readiness.facts.RC03.value.choice")],
     "messages": [user("Research-only request explicitly supplies beneficiary-home reference geography and year.", fact("guide.fields.comparison.scope.zip"), fact("guide.fields.comparison.scope.county"), fact("readiness.facts.RC03.value.choice")),
                  result("Do not ask current coverage, doctors or drugs; state exact source/sample boundary.")],
     "holds": ["Exact published scope/source acceptance; no personal recommendation."], "expected": [0, 0, 2]},
    {"id": "S03", "task": "Prepare two provider identities with one grouped echo", "required": [fact("G05", entity="provider-a"), fact("G05", entity="provider-b")],
     "messages": [user("Two names/offices explicitly supplied; new external identity bindings remain candidates.", fact("guide.fields.needs.providers"), fact("G05", "tentative", "provider-a"), fact("G05", "tentative", "provider-b")),
                  ask("Echo two synthetic candidate records together for explicit identity confirmation.", request("G05", "provider-a", "identity_confirmation"), request("G05", "provider-b", "identity_confirmation")),
                  user("Both intended office identities confirmed.", fact("G05", entity="provider-a"), fact("G05", entity="provider-b")),
                  result("Identity preparation only; no repeated practice/city questionnaire or access guarantee.")],
     "holds": ["Trusted real source bindings and exact plan/year access verification are not executed."], "expected": [1, 2, 4]},
    {"id": "S04", "task": "Prepare exact medicine identity for coverage; no price request", "required": [fact("G05", entity="medicine-a")],
     "messages": [user("Reported medicine name/strength/form already supplied.", fact("guide.fields.needs.medications"), fact("readiness.facts.RC22.value.items[].name", entity="medicine-a"), fact("readiness.facts.RC22.value.items[].strength", entity="medicine-a"), fact("readiness.facts.RC22.value.items[].form", entity="medicine-a"), fact("G05", "tentative", "medicine-a")),
                  ask("Confirm the intended synthetic exact-product interpretation.", request("G05", "medicine-a", "identity_confirmation")),
                  user("Intended product interpretation confirmed.", fact("G05", entity="medicine-a")),
                  result("Do not ask quantity/days supply/store/channel for this narrower task.")],
     "forbidden_asks": ["readiness.facts.RC23.value.items[].quantity", "readiness.facts.RC23.value.items[].daysSupply", "readiness.facts.RC23.value.items[].pharmacy", "readiness.facts.RC23.value.items[].channel"],
     "holds": ["Exact accepted plan/year formulary and restrictions remain separate."], "expected": [1, 1, 4]},
    {"id": "S05", "task": "Prepare one price scenario with only missing fill facts", "required": [fact("readiness.facts.RC23.value.items[].quantity", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].daysSupply", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].pharmacy", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].channel", entity="medicine-a")],
     "messages": [user("Price request; exact product already confirmed in prior context.", fact("readiness.facts.RC22.value.items[].name", entity="medicine-a"), fact("readiness.facts.RC22.value.items[].strength", entity="medicine-a"), fact("readiness.facts.RC22.value.items[].form", entity="medicine-a")),
                  ask("One coherent fill request seeks quantity, days supply, exact store and channel.", request("readiness.facts.RC23.value.items[].quantity", "medicine-a"), request("readiness.facts.RC23.value.items[].daysSupply", "medicine-a"), request("readiness.facts.RC23.value.items[].pharmacy", "medicine-a"), request("readiness.facts.RC23.value.items[].channel", "medicine-a")),
                  user("All four requested fill facts explicitly supplied.", fact("readiness.facts.RC23.value.items[].quantity", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].daysSupply", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].pharmacy", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].channel", entity="medicine-a")),
                  result("Scenario input segment prepared; no guessed price or repeat medicine-identity ask.")],
     "holds": ["Trusted pharmacy/network/pricing adapter and accepted exact cost evidence."], "expected": [1, 4, 4]},
    {"id": "S06", "task": "Unknown days supply stops the price conclusion without a loop", "required": [fact("readiness.facts.RC23.value.items[].quantity", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].daysSupply", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].pharmacy", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].channel", entity="medicine-a")],
     "messages": [user("Same pricing-only input segment requested."),
                  ask("Seek the missing fill facts once.", request("readiness.facts.RC23.value.items[].quantity", "medicine-a"), request("readiness.facts.RC23.value.items[].daysSupply", "medicine-a"), request("readiness.facts.RC23.value.items[].pharmacy", "medicine-a"), request("readiness.facts.RC23.value.items[].channel", "medicine-a")),
                  user("Quantity/store/channel supplied; days supply explicitly unknown.", fact("readiness.facts.RC23.value.items[].quantity", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].daysSupply", "unknown", "medicine-a"), fact("readiness.facts.RC23.value.items[].pharmacy", entity="medicine-a"), fact("readiness.facts.RC23.value.items[].channel", entity="medicine-a")),
                  result("Explain that exact fill price is unresolved; preserve other facts and do not re-ask unchanged unknown.")],
     "expected_missing": ["readiness.facts.RC23.value.items[].daysSupply|medicine-a"],
     "holds": ["Missing days supply plus independent pricing evidence; no estimate fabricated."], "expected": [1, 4, 4]},
    {"id": "S07", "task": "One specific current-versus-future arrangement conflict", "required": [fact("readiness.facts.RC07.value.choice")],
     "messages": [user("Current/future Original/Advantage reports conflict for the intended comparison.", fact("readiness.facts.RC07.value.choice", "conflicted")),
                  ask("Clarify only the current arrangement/period.", request("readiness.facts.RC07.value.choice", kind="conflict_correction")),
                  user("Current arrangement and prospective change distinguished.", fact("readiness.facts.RC07.value.choice")),
                  result("Retain revisions and reassess affected conclusions; no profile reset.")],
     "holds": ["Corrected report is not verified enrollment or accepted plan evidence."], "expected": [1, 1, 4]},
    {"id": "S08", "task": "Known identity; unavailable external access source", "required": [fact("readiness.facts.RC21.value.items[].practice", entity="provider-a"), fact("readiness.facts.RC21.value.items[].city", entity="provider-a")],
     "messages": [user("Exact intended provider office already confirmed.", fact("readiness.facts.RC21.value.items[].practice", entity="provider-a"), fact("readiness.facts.RC21.value.items[].city", entity="provider-a")),
                  result("Report the source/access hold; do not open RC21 again merely because verification failed.")],
     "holds": ["Unavailable exact access/network evidence; no source-stop bypass."], "expected": [0, 0, 2]},
    {"id": "S09", "task": "Reuse explicit priorities; no routine T09/T10 closing asks", "required": [fact("guide.fields.needs.costPreference"), fact("guide.fields.needs.priorities")],
     "messages": [user("An explicit predictable-cost preference and doctor priority already supplied.", fact("guide.fields.needs.costPreference"), fact("guide.fields.needs.priorities")),
                  result("Use those reports for emphasis; no new seven-option menu or implied numeric weights.")],
     "holds": ["No priority satisfaction/personal recommendation is asserted without exact evidence."], "expected": [0, 0, 2]},
    {"id": "S10", "task": "Prepare distinct employment and health-coverage end chronology", "required": [fact("readiness.facts.RC11.value.jobEnd"), fact("readiness.facts.RC11.value.coverageEnd")],
     "messages": [user("Own-current-job transition context already stated; only the chronology segment is tested.", fact("readiness.facts.RC09.value.choice")),
                  ask("Ask for the job end and health-coverage end together, keeping them distinct.", request("readiness.facts.RC11.value.jobEnd"), request("readiness.facts.RC11.value.coverageEnd")),
                  user("Two distinct end dates explicitly supplied.", fact("readiness.facts.RC11.value.jobEnd"), fact("readiness.facts.RC11.value.coverageEnd")),
                  result("No extra RC11.C1 question. Other needed timing/HSA/basis evidence is not presumed complete.")],
     "holds": ["Other consequential timing facts, official evidence and reviewed policy remain separate."], "expected": [1, 2, 4]},
]

def key(item):
    return item["fact"]+"|"+item.get("entity", "")

def validate_ref(item):
    assert item["fact"] in FIELDS or item["fact"] in GAPS, item["fact"]

def audit():
    results = []
    for trace in TRACES:
        state = {}
        asked = set()
        prompts = details = 0
        forbidden = set(trace.get("forbidden_asks", []))
        for message in trace["messages"]:
            if message["speaker"] == "user":
                for item in message.get("facts", []):
                    validate_ref(item)
                    state[key(item)] = item["state"]
            else:
                reqs = message.get("information_requests", [])
                prompts += message.get("question_prompts", 0)
                details += len(reqs)
                assert bool(reqs) == bool(message.get("question_prompts", 0))
                for req in reqs:
                    validate_ref(req)
                    assert req["fact"] not in forbidden
                    row = FIELDS.get(req["fact"])
                    assert not row or row["field_role"] not in {"internal_link", "legacy_detail", "reference_provenance"}, req
                    assert state.get(key(req)) not in {"confirmed", "unknown", "deferred"}, (trace["id"], "duplicate/unknown-loop", req)
                    assert key(req) not in asked, (trace["id"], "repeat", req)
                    asked.add(key(req))
        missing = []
        for item in trace["required"]:
            validate_ref(item)
            if state.get(key(item)) != "confirmed":
                missing.append(key(item))
        assert sorted(missing) == sorted(trace.get("expected_missing", [])), trace["id"]
        assert [prompts, details, len(trace["messages"])] == trace["expected"], trace["id"]
        results.append({"id": trace["id"], "task": trace["task"], "questions_asked_prompts": prompts,
                        "atomic_information_requests": details, "conversation_turns": len(trace["messages"]),
                        "elapsed_time_ms": None, "elapsed_time_status": "human_not_measured",
                        "trace_segment_missing_facts": missing, "independent_holds": trace["holds"],
                        "personalized_recommendation_allowed": False})
    output = {"status": "synthetic_design_segments_not_runtime_or_consumer_evidence",
              "no_timing_claim": "No elapsed time, savings or human comprehension was measured.",
              "limits": "Required facts describe each narrow trace segment only, not a complete adjudicated eligibility/intake policy.",
              "checks": ["field/gap references exist", "no internal-link/legacy-detail questions", "no repeat known/unknown asks", "no pricing-only ask in coverage-only trace", "explicit unresolved facts and external holds", "declared questions/details/turns counted"],
              "trace_definitions": TRACES, "results": results}
    (P / "CONVERSATION_TRACE_AUDIT.json").write_text(json.dumps(output, indent=2)+"\n")
    lines = ["# Synthetic conversation design trace audit", "", "October 25, 2026 · D79. **Declared design segments, not runtime tests, real customer sessions or accepted Medicare policy. Human elapsed time is not measured.**", "", "See [conversation design](SHORTEST_SUFFICIENT_CONVERSATION.md), [field map](CRITICAL_INFORMATION_FIELD_MAP.md) and [trace definitions/results](CONVERSATION_TRACE_AUDIT.json). Each segment tests its stated input boundary only; missing wider eligibility/coverage facts are not presumed satisfied.", "", "| Trace | Narrow design segment | Questions/prompts | Atomic information requests | Turns | Human elapsed time |", "| --- | --- | ---: | ---: | ---: | --- |"]
    for r in results:
        lines.append(f"| {r['id']} | {r['task']} | {r['questions_asked_prompts']} | {r['atomic_information_requests']} | {r['conversation_turns']} | Not measured |")
    lines += ["", "Every segment keeps independent source/policy/release holds visible; no personal recommendation is allowed by this audit. S06 retains unknown days supply, S08 does not turn a source failure into another provider ask, and S10 does not repeat the child coverage-end ask after the parent answer supplies it. S03 counts two identity requests even though one grouped question collects them.", "", "Audit checks: all references resolve; internal-link/legacy wording does not become an intake question; known/unknown items are not re-asked; the coverage-only drug segment requests no pricing-only fields; unresolved facts and holds remain explicit. Counts are audited from the trace definitions. They do not establish an optimal real-world question count, time improvement, usable UI or actual source verification."]
    (P / "CONVERSATION_TRACE_AUDIT.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"synthetic_segments": len(results), "questions": sum(r["questions_asked_prompts"] for r in results), "atomic_requests": sum(r["atomic_information_requests"] for r in results), "turns": sum(r["conversation_turns"] for r in results), "human_elapsed_time": "not_measured", "status": "audit_passed"}, indent=2))

if __name__ == "__main__":
    audit()
