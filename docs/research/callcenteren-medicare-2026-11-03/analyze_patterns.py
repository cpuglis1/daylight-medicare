#!/usr/bin/env python3
"""Local noncommercial call-pattern research; reads calls.sqlite3 without changes.

Produces traceable rule-based call-type estimates, problem/question/explanation
signals, enrollment audit candidates, and review samples. No external services.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import random
import re
import sqlite3
import statistics
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / "local"
DEFAULT_OUTPUT = LOCAL / "pattern-analysis-r3"
VERSION = "call-patterns-r3"
SENTENCE = re.compile(r"[^.!?]+[.!?]?")
MENU = re.compile(r"\b(?:please press|press (?:\[PHONE_NUMBER\]|\[NUMBER_SEQUENCE\]|\d|one|two|three)|listen carefully|options (?:may |have )?changed|your call (?:is|will be|may be) recorded|your (?:queue|q) position|all (?:of )?(?:our )?.{0,25}(?:assisting|busy)|visit us on facebook|follow us on|leave (?:a |your )?(?:voice ?mail|message) after|please leave (?:a |your )?(?:message|name)|thank you for (?:calling|holding|your patience))\b", re.I)
INTENT = re.compile(r"\b(?:i(?:'m| am| was)? (?:just )?(?:call\w*|need|want|would like|wonder\w*|try\w*|look\w*|have a question)|we (?:need|want|would like)|can (?:i|we|you)|could (?:i|we|you)|do (?:you|i|we)|does (?:it|that|this|my)|how (?:much|can|do|does|long)|what (?:is|are|does|do|would|will|kind)|is (?:it|that|this|there)|are (?:you|there)|will (?:it|that|this|my|you))\b", re.I)
MEDICARE = re.compile(r"\b(?:medicare|medigap)\b", re.I)
INSURANCE = re.compile(r"\b(?:insurance|medicare|medigap|health plan|drug plan|part [abcd]|policy|policies)\b", re.I)
ENROLLMENT_WORD = re.compile(r"\b(?:enroll\w*|application|sign(?:ed|ing)? (?:you |me |them |us )?up)\b", re.I)
ENROLLMENT_PROCESS = re.compile(r"\b(?:let(?:'s| us) (?:start|complete|submit|fill out).{0,65}(?:(?:insurance|medicare|health plan|drug plan) (?:enrollment|application)|enrollment application|(?:enrollment|application) (?:for|in|into).{0,30}(?:plan|insurance|medicare))|i (?:authorize|consent|agree).{0,80}(?:enroll|submit.{0,30}application)|(?:submit|complete|fill out).{0,35}(?:your|the) (?:insurance |medicare |health plan )?(?:enrollment|application) (?:now|today|with you))\b", re.I)
ENROLLMENT_COMPLETE = re.compile(r"\b(?:we (?:have |just |successfully )*(?:submitted|completed|processed|accepted).{0,55}(?:your|the) (?:insurance |medicare |health plan )?(?:enrollment|application)|your (?:insurance |medicare |health plan )?(?:enrollment|application) (?:has (?:now |successfully )?been|is now) (?:submitted|completed|accepted|approved))\b", re.I)
HISTORY = re.compile(r"\b(?:already (?:enrolled|signed)|(?:i|she|he|they|we) (?:have |had |just )?(?:enrolled|signed up)|enrolled (?:in|with)|open enrollment|enrollment period|enrollee? (?:id|number))\b", re.I)
NON_INSURANCE_ENROLLMENT = re.compile(r"\b(?:doggy day\s?care|daycare|day camp|dog|pets?|boarding|grooming|job|employment|patient portal|care credit|carecredit|financing|discount (?:plan|program)|savings (?:plan|program))\b", re.I)
GREETING = re.compile(r"\bhow (?:can|may|could|do) i (?:help|assist|serve|make) (?:you|ya|y'all|yall)", re.I)
PERSONAL_REQUEST = re.compile(r"\bi(?:'m| am| was)? (?:just )?(?:calling|need|want|would like|wondering|looking)", re.I)
HOLD_START = re.compile(r"\b(?:put you on hold|place you (?:on (?:a )?|a )?(?:brief )?hold|put you (?:on )?a (?:brief )?hold|(?:put|place) you on a brief hold)\b", re.I)
HOLD_RETURN = re.compile(r"\b(?:thank(?:s| you) (?:so much )?for (?:holding|waiting)[.!?\s]{0,8}(?:this is|my name is|how can|how may)|thank you.{0,35}(?:on|the) (?:the )?line[.!?\s]{0,8}(?:sir|ma'am|can|are)|are you still there|(?:hi|hello)[,. ]{0,5}(?:this is|are you still|can you hear))", re.I)
CARE_PROGRAM = re.compile(r"\b(?:life program|pace program|all[ -]inclusive.{0,45}(?:program|care)|long[ -]?term.{0,30}program|medical and financial eligibility|community assessment)\b", re.I)
CARE_NEED = re.compile(r"\b(?:bathing|dressing|activities of daily living|adl'?s?|care plan|caregiver|home visit|home assessment|care services|home care|housekeeping)\b", re.I)
THIRD_PARTY_RESEARCH = re.compile(r"\b(?:my|our) beneficiar(?:y|ies)\b", re.I)


@dataclass(frozen=True)
class Rule:
    name: str
    anchors: tuple[str, ...]
    pattern: str


CALL_RULES = (
    Rule("insurance_plan_choice_or_enrollment_inquiry", ("enroll", "sign up", "compare", "choose", "switch", "medicare advantage", "recommend"), r"\b(?:(?:can you (?:help me )?|i (?:want|need|would like|am looking) to )(?:enroll|sign up|choose|compare|switch).{0,65}(?:medicare|medigap|insurance|health plan|drug plan)|(?:which|what) (?:medicare|medigap|insurance|health|drug) (?:plan|coverage).{0,45}(?:choose|recommend|better)|(?:looking|planning|trying|want).{0,25}(?:get|buy|choose|switch).{0,25}(?:a )?medicare advantage)\b"),
    Rule("coverage_or_provider_acceptance", ("insur", "medicare", "cover", "network", "benefit", "copay", "co-pay", "deduct", "hmo", "ppo"), r"\b(?:(?:accept\w*|take|takes|work with).{0,75}(?:insurance|medicare|medicaid|hmo|ppo|plan)|(?:insurance|medicare|medicaid|hmo|ppo|plan).{0,65}(?:accept\w*|take|network|cover\w*)|(?:be|is|was|get|it|that|this) covered|coverage|benefits?|in[ -]network|out[ -]of[ -]network|co-?pay\w*|deductibles?)\b"),
    Rule("billing_payment_claim", ("bill", "charg", "statement", "balance", "refund", "claim", "payment", "paid"), r"\b(?:bill(?:s|ing)?|charg(?:e|es|ed|ing)|statements?|balance|refund\w*|claims?|payment|paid)\b"),
    Rule("price_estimate_or_affordability", ("cost", "much", "price", "pricing", "estimate", "afford", "pocket", "financ"), r"\b(?:how much|what.{0,25}(?:cost|price|charge)|costs?|prices?|pricing|estimates?|afford\w*|out of pocket|financ\w*)\b"),
    Rule("records_referral_prescription_admin", ("record", "referr", "prescrip", "refill", "result", "paperwork", "authoriz", "fax", "forms"), r"\b(?:records?|referrals?|prescriptions?|refills?|results?|paperwork|authoriz\w*|fax\w*|forms)\b"),
    Rule("service_or_clinical_information", ("question", "symptom", "do you do", "do y'all", "do y all", "offer", "procedure", "pain", "problem", "medical_process", "medical_condition", "how long", "what happens", "how does"), r"\b(?:questions? (?:about|regarding)|do (?:you|y'all|y all) (?:do|offer|perform|treat)|symptoms?|pain|problem with|how (?:does|long)|what happens|what.{0,30}(?:procedure|treatment|exam)|need.{0,30}(?:exam|treatment|procedure))\b"),
    Rule("basic_scheduling_or_intake", ("appoint", "schedul", "reservation", "book", "opening", "available", "seen", "come in", "bring"), r"\b(?:(?:make|book|schedul\w*|reschedul\w*|cancel|change|confirm|set up|move).{0,65}(?:appointment|visit|consultation|reservation)|(?:appointment|visit|reservation).{0,45}(?:make|book|schedul\w*|reschedul\w*|cancel|change|confirm)|(?:next|earliest|any|have|something).{0,45}(?:available|availability|opening)|(?:come|bring|be seen).{0,30}(?:in|today|tomorrow)|have (?:you|him|her|them) (?:down|scheduled)|new patient)\b"),
    Rule("routing_message_callback", ("speak", "talk", "transfer", "call", "message", "voicemail", "voice mail", "hold"), r"\b(?:(?:speak|talk) (?:to|with)|transfer\w*|call (?:you |me |them |us )?back|return\w* (?:your|my|a) call|left (?:you |me |a )?message|voice ?mail|on hold)\b"),
    Rule("employment_vendor_other_business", ("job", "hiring", "employment", "vendor", "sales rep", "donation", "interview"), r"\b(?:appl\w*.{0,35}(?:job|position)|hiring|employment|job opening|job application|sales representative|vendor|donation|interview)\b"),
)
QUESTION_RULES = (
    Rule("appointment_availability_change", ("appoint", "available", "opening", "schedul", "come in", "book", "reservation"), r"\b(?:appointment|available|availability|opening|schedul\w*|come in|book|reservation)\b"),
    Rule("insurance_acceptance_network", ("insur", "medicare", "network", "hmo", "ppo", "plan"), r"\b(?:(?:accept|take|work with).{0,70}(?:insurance|medicare|medicaid|hmo|ppo|plan)|(?:insurance|medicare|plan).{0,60}(?:accept|take|network)|in[ -]network|out[ -]of[ -]network)\b"),
    Rule("insurance_identity_card_details", ("insur", "card", "member", "group", "policy", "medicare", "hmo", "ppo"), r"\b(?:(?:what|which).{0,45}(?:insurance|plan|medicare)|(?:member|group|policy|subscriber).{0,20}(?:number|id)|(?:on|have|bring).{0,20}(?:card|hmo|ppo)|primary insurance|secondary insurance)\b"),
    Rule("service_coverage_benefits", ("cover", "benefit", "copay", "co-pay", "deduct", "insurance pay"), r"\b(?:cover\w*|benefits?|co-?pay\w*|deductibles?|insurance pay)\b"),
    Rule("price_estimate_out_of_pocket", ("much", "cost", "price", "estimate", "pocket", "pay"), r"\b(?:how much|costs?|price\w*|estimates?|out of pocket|(?:have|need|going) to pay|what.{0,30}pay)\b"),
    Rule("billing_charge_or_claim_reason", ("bill", "charg", "statement", "claim", "balance", "refund"), r"\b(?:bill\w*|charg\w*|statements?|claims?|balance|refund)\b"),
    Rule("records_referrals_prescriptions", ("record", "referr", "prescrip", "refill", "result", "fax", "authoriz"), r"\b(?:records?|referrals?|prescriptions?|refills?|results?|fax\w*|authoriz\w*)\b"),
    Rule("service_process_or_eligibility", ("how", "what", "do you", "do y", "need", "procedure", "exam"), r"\b(?:how (?:does|do|long)|what (?:happens|should|would|do i need)|do (?:you|y'all|y all) (?:do|offer|perform|treat)|need.{0,30}(?:exam|procedure|treatment))\b"),
    Rule("understanding_or_clarification", ("mean", "understand", "explain", "difference", "confus", "say again"), r"\b(?:mean\w*|understand\w*|explain\w*|difference|confus\w*|say again)\b"),
    Rule("identity_contact_admin", ("name", "birth", "phone", "email", "address", "number", "new patient", "seen"), r"\b(?:name|date of birth|phone|email|address|number|new patient|(?:been|ever) seen)\b"),
    Rule("insurance_enrollment_or_choice", ("enroll", "sign", "plan", "medicare"), r"\b(?:enroll(?:ment|ing|ed)?|(?:choose|compare|switch|change).{0,35}(?:insurance|medicare|health|drug) plan|(?:insurance|medicare|health|drug) plan.{0,30}(?:choose|compare|switch|change))\b"),
)
EXPLANATION_RULES = (
    Rule("procedural_next_steps", ("need", "have to", "first", "then", "send", "call", "website", "verify", "check"), r"\b(?:you (?:will |would )?(?:need|have) to|first.{0,70}then|(?:i|we)(?:'ll| will| can) (?:send|check|verify|transfer)|go to (?:our|the) website|call (?:your|the) insurance)\b"),
    Rule("reason_or_causal_language", ("because", "reason", "so that"), r"\b(?:because|the reason|so that)\b"),
    Rule("conditional_or_dependency", ("depend", "until", "require", "only if", "once", "without"), r"\b(?:depend\w*|until|requir\w*|only if|once we|without (?:an? |the )?(?:exam|breakdown|insurance|information|verification))\b"),
    Rule("uncertainty_or_verification_needed", ("sure", "know", "confirm", "verify", "check", "guarantee"), r"\b(?:not sure|don'?t know|do not know|can'?t confirm|cannot confirm|need to (?:verify|check)|have to (?:verify|check)|can'?t guarantee)\b"),
    Rule("concept_or_option_distinction", ("difference", "instead", "same", "means", "different", "hmo", "ppo", "supplement", "adl", "stands for"), r"\b(?:difference between|instead of|not the same|that means|which means|stands for|adl'?s?.{0,35}activities of daily living|(?:hmo.{0,100}ppo|ppo.{0,100}hmo)|(?:supplement|secondary).{0,60}primary|primary.{0,60}(?:supplement|secondary))\b"),
    Rule("cost_or_coverage_mechanism", ("pay", "cover", "deduct", "copay", "co-pay", "percent", "portion", "discount"), r"\b(?:(?:insurance|plan|benefit).{0,65}(?:covers?|pays?|percent|portion)|(?:pay|paying).{0,55}(?:out of pocket|percent|portion|deductible|co-?pay)|discount.{0,55}(?:fee|price|pay)|(?:deductible|co-?pay|coinsurance).{0,50}(?:means|pay|portion))\b"),
    Rule("worked_example_or_analogy", ("example", "let's say", "lets say", "suppose", "for instance", "think of"), r"\b(?:for example|let'?s say|suppose|for instance|think of it (?:like|as))\b"),
    Rule("generic_understanding_check", ("sense", "understand", "clear", "questions"), r"\b(?:does that make sense|do you understand|is that clear|(?:any|other|further) questions)\b"),
    Rule("teach_back_request", ("own words", "understood", "explain back", "tell me back", "understand"), r"\b(?:in your own words|(?:tell|explain) (?:it )?back|what (?:did you understand|does that mean to you)|tell me what you understand)\b"),
    Rule("reassurance_language", ("worry", "covered", "fine", "problem"), r"\b(?:don'?t worry|should be (?:all )?covered|you(?:'ll| will) be fine|nothing to worry about)\b"),
)
COMPILED = {r.name: re.compile(r.pattern, re.I) for r in CALL_RULES + QUESTION_RULES + EXPLANATION_RULES}


def rule_match(rule, text, lower):
    if any(a in lower for a in rule.anchors):
        return COMPILED[rule.name].search(text)
    return None


def excluded_ranges(text):
    ranges = []
    greeting = GREETING.search(text, 0, min(len(text), 5000))
    if greeting and not PERSONAL_REQUEST.search(text[:greeting.start()]):
        ranges.append((0, greeting.start()))
    for hold in HOLD_START.finditer(text):
        back = HOLD_RETURN.search(text, hold.end())
        if back and back.start()-hold.end() >= 100:
            ranges.append((hold.start(), back.end()))
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def units(text, excluded=()):
    def retained():
        left = 0
        for start, end in excluded:
            if left < start:
                yield left, start
            left = end
        if left < len(text):
            yield left, len(text)
    for left, right in retained():
        for m in SENTENCE.finditer(text, left, right):
            raw = m.group()
            clean = raw.strip()
            if not clean:
                continue
            # A mixed unit containing a conversational request after a menu survives.
            menu = bool(MENU.search(clean))
            conversational_tail = re.search(r"\b(?:hi|hello|i(?:'m| am| was)? (?:calling|need|want|wondering))\b", raw, re.I)
            if menu and conversational_tail:
                start = m.start() + conversational_tail.start()
                yield start, m.end(), text[start:m.end()], False
            else:
                yield m.start(), m.end(), raw, menu


def enrollment_audit(text, excluded=()):
    results = []
    med = bool(MEDICARE.search(text))
    for match in ENROLLMENT_WORD.finditer(text):
        start, end = max(0, match.start()-180), min(len(text), match.end()+220)
        context = text[start:end]
        insurance_nearby = bool(INSURANCE.search(context))
        if not med and not insurance_nearby:
            continue
        noninsurance = bool(NON_INSURANCE_ENROLLMENT.search(context))
        status = "ambiguous_mention"
        if any(a <= match.start() < b for a, b in excluded):
            status = "automated_or_hold_mention"
        elif noninsurance:
            status = "possible_noninsurance_membership_or_application"
        elif insurance_nearby and ENROLLMENT_COMPLETE.search(context):
            status = "insurance_completion_statement_candidate"
        elif insurance_nearby and ENROLLMENT_PROCESS.search(context):
            status = "insurance_active_process_candidate"
        elif HISTORY.search(context):
            status = "history_timing_or_identifier_mention"
        results.append({"start": start, "end": end, "term_start": match.start(), "term_end": match.end(), "status": status, "insurance_context_nearby": insurance_nearby})
    return results


def classify(text):
    scores = collections.Counter()
    occurrences = collections.Counter()
    questions = collections.defaultdict(list)
    explanations = collections.defaultdict(list)
    evidence = collections.defaultdict(list)
    menu_count = 0
    body_count = 0
    question_count = 0
    exclusions = excluded_ranges(text)
    conversation_medicare = False
    conversational_parts = []
    for start, end, unit, is_menu in units(text, exclusions):
        if is_menu:
            menu_count += 1
            continue
        body_count += 1
        conversation_medicare |= bool(MEDICARE.search(unit))
        conversational_parts.append(unit)
        lower = unit.casefold()
        is_question = unit.rstrip().endswith("?")
        intent = bool(INTENT.search(unit))
        for rule in CALL_RULES:
            match = rule_match(rule, unit, lower)
            if match:
                occurrences[rule.name] += 1
                scores[rule.name] += 3 if intent or is_question else 1
                if len(evidence[rule.name]) < 3:
                    evidence[rule.name].append({"start": start + match.start(), "end": start + match.end(), "intent_or_question": intent or is_question})
        if is_question:
            question_count += 1
            for rule in QUESTION_RULES:
                if rule_match(rule, unit, lower):
                    if len(questions[rule.name]) < 3:
                        questions[rule.name].append({"start": start, "end": end})
        # Comprehension checks are questions, distinct from explanatory responses.
        if len(unit.strip()) >= 15:
            for rule in EXPLANATION_RULES:
                if is_question and rule.name not in ("generic_understanding_check", "teach_back_request"):
                    continue
                if rule_match(rule, unit, lower) and len(explanations[rule.name]) < 3:
                    explanations[rule.name].append({"start": start, "end": end})
    enrollment = enrollment_audit(text, exclusions)
    enrollment_statuses = {x["status"] for x in enrollment}
    conversational_text = ' '.join(conversational_parts)
    care_program = bool(CARE_PROGRAM.search(conversational_text) and CARE_NEED.search(conversational_text))
    third_party = bool(conversation_medicare and THIRD_PARTY_RESEARCH.search(conversational_text) and scores.get('coverage_or_provider_acceptance'))
    if "insurance_completion_statement_candidate" in enrollment_statuses:
        primary = "insurance_enrollment_completion_candidate"
    elif "insurance_active_process_candidate" in enrollment_statuses:
        primary = "insurance_enrollment_process_candidate"
    elif care_program:
        primary = "care_program_information_or_eligibility"
        scores[primary] = 3
    elif third_party:
        primary = "third_party_plan_network_research_candidate"
        scores[primary] = 3
    else:
        # Billing/coverage and pricing become primary only with conversational evidence.
        # Routine scheduling is the default when it is present and no stronger request wins.
        eligible = {k: v for k, v in scores.items() if v >= 3}
        if eligible:
            priority = {"employment_vendor_other_business": 1.25, "insurance_plan_choice_or_enrollment_inquiry": 1.25, "coverage_or_provider_acceptance": 1.2, "price_estimate_or_affordability": 1.1, "billing_payment_claim": 1.05, "basic_scheduling_or_intake": 1.0, "records_referral_prescription_admin": 1.0, "service_or_clinical_information": 0.9, "routing_message_callback": 0.65}
            # Cap repeated-topic contribution so long scripts cannot dominate by repetition.
            primary = max(eligible, key=lambda k: (min(eligible[k], 12)*priority[k], priority[k]))
        elif body_count <= 2 and menu_count:
            primary = "automated_or_no_clear_request"
        else:
            primary = "other_or_unclear"
    if care_program or third_party:
        special_pattern = CARE_PROGRAM if care_program else THIRD_PARTY_RESEARCH
        for start, end, unit, is_menu in units(text, exclusions):
            match = None if is_menu else special_pattern.search(unit)
            if match:
                evidence[primary].append({'start':start+match.start(),'end':start+match.end(),'intent_or_question':False})
                break
    return {"primary_type": primary, "type_scores": dict(scores), "type_occurrences": dict(occurrences), "type_evidence": dict(evidence), "questions": dict(questions), "explanations": dict(explanations), "question_unit_count": question_count, "suppressed_menu_units": menu_count, "suppressed_text_ranges": exclusions, "medicare_conversation_term_present": conversation_medicare, "remaining_units": body_count, "enrollment_audit": enrollment, "speaker_roles": "unknown", "classification_status": "rule_based_unvalidated"}


def percent(n, d):
    return round(100*n/d, 2) if d else None


def write_csv(path, rows, fields):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def new_counter():
    return {"records": 0, "primary_types": collections.Counter(), "type_signals": collections.Counter(), "question_families": collections.Counter(), "explanation_families": collections.Counter(), "enrollment_statuses": collections.Counter(), "durations_by_type": collections.defaultdict(list), "question_units": 0, "suppressed_menu_units": 0}


def remember_example(groups, family, candidate):
    examples = groups[family]
    examples.append(candidate)
    if len(examples) > 40:
        examples.sort(key=lambda x: (x[0], x[1], x[2], x[3]['start']))
        del examples[20:]


def run(output):
    output = output.resolve()
    if not output.is_relative_to(LOCAL.resolve()):
        raise SystemExit("Transcript-derived output must stay under the ignored local/ directory.")
    if output.exists():
        raise SystemExit("Output exists; use a new local revision to preserve earlier findings.")
    output.mkdir(parents=True)
    (output / "method.py").write_bytes(Path(__file__).read_bytes())
    db = sqlite3.connect(f"file:{LOCAL/'calls.sqlite3'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    counts = {k: new_counter() for k in ("all_records", "unique_texts", "medicare_mentions", "medicare_unique_texts", "medicare_conversation_mentions", "medicare_conversation_unique_texts")}
    seen = set()
    review_buckets = collections.defaultdict(list)
    family_examples = collections.defaultdict(list)
    question_examples = collections.defaultdict(list)
    enrollment_rows = []
    result_by_id = {}
    out_jsonl = output / "call-classifications.jsonl"
    with out_jsonl.open("w") as stream:
        for i, row in enumerate(db.execute("SELECT * FROM calls ORDER BY call_id"), 1):
            result = classify(row["text"])
            unique = row["text_sha256"] not in seen
            seen.add(row["text_sha256"])
            med = bool(row["medicare_candidate"])
            med_conversation = result['medicare_conversation_term_present']
            record = {"call_id": row["call_id"], "archive_member": row["archive_member"], "source_sha256": row["source_sha256"], "text_sha256": row["text_sha256"], "canonical_exact_text_record": unique, "medicare_term_present": med, "duration_seconds": row["duration_seconds"], **result}
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            memberships = ["all_records"] + (["unique_texts"] if unique else []) + (["medicare_mentions"] if med else []) + (["medicare_unique_texts"] if med and unique else [])
            memberships += (["medicare_conversation_mentions"] if med_conversation else []) + (["medicare_conversation_unique_texts"] if med_conversation and unique else [])
            for cohort in memberships:
                c = counts[cohort]
                c["records"] += 1
                c["primary_types"][result["primary_type"]] += 1
                c["type_signals"].update(result["type_scores"].keys())
                c["question_families"].update(result["questions"].keys())
                c["explanation_families"].update(result["explanations"].keys())
                c["enrollment_statuses"].update(set(x["status"] for x in result["enrollment_audit"]))
                c["durations_by_type"][result["primary_type"]].append(row["duration_seconds"])
                c["question_units"] += result["question_unit_count"]
                c["suppressed_menu_units"] += result["suppressed_menu_units"]
            if unique:
                review_buckets[("all", result["primary_type"])].append(row["call_id"])
                if med_conversation:
                    review_buckets[("medicare", result["primary_type"])].append(row["call_id"])
            # Prioritize Medicare examples, then shorter nontrivial spans, deterministically.
            for family, spans in result["questions"].items():
                for span in spans:
                    length = span["end"]-span["start"]
                    if 15 <= length <= 500:
                        remember_example(question_examples, family, (not med_conversation, length, row["call_id"], span))
            for family, spans in result["explanations"].items():
                for span in spans:
                    length = span["end"]-span["start"]
                    if 35 <= length <= 650:
                        remember_example(family_examples, family, (not med_conversation, length, row["call_id"], span))
            for audit in result["enrollment_audit"]:
                enrollment_rows.append({"call_id": row["call_id"], "medicare_term_present": med, "source_sha256": row["source_sha256"], "primary_type": result["primary_type"], **audit, "text_span": row["text"][audit["start"]:audit["end"]], "review_disposition": "", "review_notes": ""})
            if i % 5000 == 0:
                print(f"Classified {i:,} records", flush=True)
    for cohort in counts.values():
        cohort["median_duration_seconds_by_type"] = {k: statistics.median(v) for k, v in cohort.pop("durations_by_type").items()}
    rules = {"call_rules": [vars(r) for r in CALL_RULES], "question_rules": [vars(r) for r in QUESTION_RULES], "explanation_rules": [vars(r) for r in EXPLANATION_RULES], "menu": MENU.pattern, "intent": INTENT.pattern, "greeting": GREETING.pattern, "personal_request": PERSONAL_REQUEST.pattern, "hold_start": HOLD_START.pattern, "hold_return": HOLD_RETURN.pattern, "care_program": CARE_PROGRAM.pattern, "care_need": CARE_NEED.pattern, "third_party_research": THIRD_PARTY_RESEARCH.pattern, "enrollment": {"word": ENROLLMENT_WORD.pattern, "process": ENROLLMENT_PROCESS.pattern, "complete": ENROLLMENT_COMPLETE.pattern, "history": HISTORY.pattern, "noninsurance": NON_INSURANCE_ENROLLMENT.pattern}}
    rules_hash = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()
    summary = {"version": VERSION, "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "scope": "local noncommercial historical transcript research", "method": "Unvalidated deterministic evidence rules; primary detected work type is mutually exclusive; secondary signals overlap; all speaker roles unknown", "source_inventory": json.loads((LOCAL/'inventory.json').read_text()), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "rules_sha256": rules_hash, "cohorts": counts, "rules": rules, "completed_enrollments_externally_verified": None, "completed_enrollments_externally_verified_note": "No application receipts, carrier records, or labeled outcomes exist in this collection; transcript candidates are not verified enrollment outcomes."}
    json_write(output / "summary.json", summary)
    distribution = []
    for cohort, c in counts.items():
        for call_type, n in c["primary_types"].most_common():
            distribution.append({"cohort": cohort, "primary_detected_type": call_type, "calls": n, "denominator": c["records"], "percent": percent(n,c["records"]), "median_seconds": c["median_duration_seconds_by_type"][call_type], "status": "unvalidated_rule_based_estimate"})
    write_csv(output / "call-type-distribution.csv", distribution, ["cohort", "primary_detected_type", "calls", "denominator", "percent", "median_seconds", "status"])
    feature_rows = []
    for cohort, c in counts.items():
        for kind in ("type_signals", "question_families", "explanation_families", "enrollment_statuses"):
            for feature, n in c[kind].most_common():
                feature_rows.append({"cohort": cohort, "feature_kind": kind, "feature": feature, "calls": n, "denominator": c["records"], "percent": percent(n,c["records"]), "speaker_role": "unknown"})
    write_csv(output / "overlapping-pattern-counts.csv", feature_rows, ["cohort", "feature_kind", "feature", "calls", "denominator", "percent", "speaker_role"])
    audit_fields = ["call_id", "medicare_term_present", "source_sha256", "primary_type", "start", "end", "term_start", "term_end", "status", "insurance_context_nearby", "text_span", "review_disposition", "review_notes"]
    write_csv(output / "enrollment-audit.csv", enrollment_rows, audit_fields)
    sample_rows = []
    chosen_ids = set()
    for (cohort, call_type), ids in sorted(review_buckets.items()):
        chosen = random.Random(f"20261103:{cohort}:{call_type}").sample(ids, min(3,len(ids)))
        for call_id in chosen:
            sample_rows.append({"cohort": cohort, "call_id": call_id, "automatic_type": call_type, "reviewed_type": "", "domain": "", "problem": "", "question": "", "explanation": "", "review_notes": "", "reviewer": ""})
            chosen_ids.add(call_id)
    # Always include enrollment process/completion candidates in full-call review.
    for row in enrollment_rows:
        if row["status"] in ("insurance_active_process_candidate", "insurance_completion_statement_candidate"):
            chosen_ids.add(row["call_id"])
    (output / "review-calls").mkdir()
    for call_id in sorted(chosen_ids):
        row = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
        (output/'review-calls'/f'{call_id}.txt').write_text(f"Call: {call_id}\nSource: {row['archive_member']}\nNo speaker-role labels.\n\n{row['text']}\n")
    write_csv(output / "review-sample.csv", sample_rows, ["cohort", "call_id", "automatic_type", "reviewed_type", "domain", "problem", "question", "explanation", "review_notes", "reviewer"])
    span_examples = []
    for kind, groups in (("question",question_examples),("explanation",family_examples)):
        for family, candidates in groups.items():
            selected = []
            used = set()
            for _, _, call_id, span in sorted(candidates, key=lambda x:(x[0],x[1],x[2],x[3]['start'])):
                if call_id in used:
                    continue
                row = db.execute("SELECT text,archive_member FROM calls WHERE call_id=?", (call_id,)).fetchone()
                selected.append({"kind": kind, "family": family, "call_id": call_id, "archive_member": row['archive_member'], **span, "text_span": row['text'][span['start']:span['end']], "speaker_role": "unknown", "review_status": "unreviewed_language_signal"})
                used.add(call_id)
                if len(selected) >= 10:
                    break
            span_examples.extend(selected)
    write_csv(output/'question-explanation-examples.csv', span_examples, ['kind','family','call_id','archive_member','start','end','text_span','speaker_role','review_status'])
    render_report(output, summary)
    verify(output, db)
    print(json.dumps({"output": str(output), "records": counts['all_records']['records'], "unique_texts": counts['unique_texts']['records'], "medicare_mentions": counts['medicare_mentions']['records'], "enrollment_audit_calls": len(set(r['call_id'] for r in enrollment_rows)), "review_sample_rows": len(sample_rows)}, indent=2))


def render_report(output, summary):
    cohorts = summary['cohorts']
    med = cohorts['medicare_conversation_mentions']
    lines = ['# Call patterns and work-type distribution', '', 'Local noncommercial research. Version '+VERSION+'. Full machine outputs are reproducible; labels are rule-based estimates without independently measured classification accuracy.', '', '## Scope', '', f"Analyzed {cohorts['all_records']['records']:,} parsed source records / {cohorts['unique_texts']['records']:,} distinct exact transcript texts. Explicit Medicare/Medigap terms occur anywhere in {cohorts['medicare_mentions']['records']:,} records / {cohorts['medicare_unique_texts']['records']:,} distinct texts. After explicit menu, leading automated content, and bracketed hold-content suppression, {med['records']:,} records / {cohorts['medicare_conversation_unique_texts']['records']:,} distinct texts still contain those terms. This is still a lexical cohort, not verified Medicare clients or broker calls. Both denominators remain in summary.json and the CSVs. Nine malformed originals remain excluded and preserved. Speaker roles are unknown throughout.", '', 'All calls are labeled inbound by the publisher. Inbound is the channel, while scheduling, advice, and enrollment are work types that may occur within an inbound call. The table estimates the primary detected work type, not the channel or an externally verified outcome.', '', '## Primary work-type estimate', '', '| Detected primary type | All records | % of all | Medicare conversation-mention records | % of conversation mentions |', '| --- | ---: | ---: | ---: | ---: |']
    all_types = sorted(set(cohorts['all_records']['primary_types'])|set(med['primary_types'])|{'insurance_enrollment_process_candidate','insurance_enrollment_completion_candidate','insurance_plan_choice_or_enrollment_inquiry'},key=lambda k:cohorts['all_records']['primary_types'].get(k,0),reverse=True)
    for label in all_types:
        n=cohorts['all_records']['primary_types'].get(label,0);m=med['primary_types'].get(label,0)
        lines.append(f"| {label} | {n:,} | {percent(n,cohorts['all_records']['records']):.2f}% | {m:,} | {percent(m,med['records']):.2f}% |")
    for kind,title in [('type_signals','Overlapping problem/work signals'),('question_families','Question families'),('explanation_families','Explanation-language families'),('enrollment_statuses','Enrollment audit signals')]:
        lines += ['', '## '+title, '', 'Counts are calls with at least one non-menu matching passage; categories overlap. A question family is based on ASR question punctuation and cannot be assigned automatically to caller versus staff. Explanation-language markers do not establish a substantive, correct, or understood explanation. Enrollment audit includes raw-source contexts, with detected automated/hold mentions separately flagged.', '', '| Family | All records | Medicare conversation mentions | % of conversation mentions |', '| --- | ---: | ---: | ---: |']
        features=sorted(set(cohorts['all_records'][kind])|set(med[kind]),key=lambda k:med[kind].get(k,0),reverse=True)
        for key in features:
            a=cohorts['all_records'][kind].get(key,0);m=med[kind].get(key,0)
            lines.append(f"| {key} | {a:,} | {m:,} | {percent(m,med['records']):.2f}% |")
    lines += ['', '## Method and limits', '', '- A sentence/ASR-punctuation pass suppresses explicit IVR/menu/hold units. Mixed units with a conversational tail are retained from that tail onward. This cannot remove all automated content.', '- Primary labels use traceable request/response text rules with scores capped to reduce domination by repeated boilerplate. Primary labels are exclusive; secondary work/question/explanation labels overlap.', '- The Medicare cohort is lexical and includes provider-office calls. The source folder also contains veterinary and other unrelated calls. No market, county, current-year, or representative consumer inference is supported.', '- Exact-text duplicates are separately accounted for; near duplicates and repeated hold messages are not fully deduplicated.', '- Enrollment screening retains historical, timing, identifier, membership, and ambiguous mentions for audit. Strong process/completion phrases are only transcript candidates; no enrollment outcome can be externally verified.', '- Teaching quality, factual accuracy, caller comprehension, successful resolution, and causal effectiveness are not determined by this script.', '- Read enrollment-audit.csv and the stratified full-call sample before using the distribution as a substantive finding. Sampling does not establish independent classifier accuracy.', '- No external analysis service, model training, product integration, or current Medicare advice is involved.', '', '## Files', '', '- call-classifications.jsonl: call-level labels, scores, source hashes and evidence offsets.', '- call-type-distribution.csv: exclusive distribution with denominators and duplicate sensitivity.', '- overlapping-pattern-counts.csv: problem, question and explanation-language counts.', '- enrollment-audit.csv: enrollment-related contexts requiring review.', '- question-explanation-examples.csv: source-linked examples, without inferred speaker roles.', '- review-sample.csv and review-calls/: reproducible stratified full-call review material.', '- verification.json: accounting and evidence-span checks.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')


def verify(output, db):
    summary=json.loads((output/'summary.json').read_text())
    n=db.execute('SELECT count(*) FROM calls').fetchone()[0]
    assert summary['cohorts']['all_records']['records']==n
    for cohort in summary['cohorts'].values():
        assert sum(cohort['primary_types'].values())==cohort['records']
        for kind in ('type_signals','question_families','explanation_families','enrollment_statuses'):
            assert all(0<=v<=cohort['records'] for v in cohort[kind].values())
    records=0;spans=0
    for line in (output/'call-classifications.jsonl').open():
        r=json.loads(line)
        text=db.execute('SELECT text,text_sha256 FROM calls WHERE call_id=?',(r['call_id'],)).fetchone()
        assert text['text_sha256']==r['text_sha256']
        for group in ('type_evidence','questions','explanations'):
            for entries in r[group].values():
                for span in entries:
                    assert 0<=span['start']<span['end']<=len(text['text'])
                    spans+=1
        records+=1
    csv_spans=0
    for filename in ('enrollment-audit.csv','question-explanation-examples.csv'):
        for row in csv.DictReader((output/filename).open()):
            text=db.execute('SELECT text FROM calls WHERE call_id=?',(row['call_id'],)).fetchone()[0]
            assert text[int(row['start']):int(row['end'])]==row['text_span']
            csv_spans+=1
    assert records==n
    receipt={'status':'passed','call_records':records,'within_text_evidence_offsets_checked':spans,'exported_spans_checked_exactly':csv_spans,'exclusive_distribution_totals':'all cohorts reconcile','overlapping_counts':'all bounded by cohort denominator','source_database_readonly':True,'script_sha256':summary['script_sha256'],'rules_sha256':summary['rules_sha256'],'classification_accuracy':'not independently measured'}
    json_write(output/'verification.json',receipt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    run(args.output)


if __name__=='__main__':
    main()
