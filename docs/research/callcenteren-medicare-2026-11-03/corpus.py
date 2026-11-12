#!/usr/bin/env python3
"""Offline, noncommercial exploration of the pinned CallCenterEN Medicare ZIP.

No model/API calls, product imports, or automatic advice-quality labels.
The archive is read in place; original word-level data remain in the ZIP.
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
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / "local"
SOURCE = LOCAL / "source"
DATABASE = LOCAL / "calls.sqlite3"
REPORTS = LOCAL / "analysis"

DOMAIN_PATTERNS = {
    "medicare_term": r"\b(?:medicare|medigap)\b",
    "advisory_language": r"\b(?:licensed (?:insurance )?agent|medicare advantage|medicare supplement|medigap|part [abcd]|enroll(?:ment|ing)?|switch(?:ing)? plans?|compare plans?|plan options?|coverage options?)\b",
    "veterinary": r"\b(?:veterinar\w*|pets?|dogs?|cats|pupp(?:y|ies)|kittens?|groom(?:ing|er)|spay(?:ed|ing)?|neuter(?:ed|ing)?|rabies|kennels?)\b",
    "dental": r"\b(?:dental|dentist|dentures?|tooth|teeth|crowns?|root canal)\b",
    "scheduling": r"\b(?:appointments?|reschedul\w*|schedul\w*|new patients?)\b",
}
TOPIC_PATTERNS = {
    "costs_billing_payment": r"\b(?:bills?|billing|charg(?:e|es|ed)|costs?|pay(?:ment|ments)?|out of pocket|co-?pay\w*|coinsurance|deductibles?|premiums?)\b",
    "coverage_acceptance_network": r"\b(?:accept\w* insurance|take\w* insurance|covered|coverage|in[ -]network|out[ -]of[ -]network|benefits?|insurance plan)\b",
    "enrollment_plan_choice": r"\b(?:enroll\w*|medigap|medicare advantage|medicare supplement|switch\w* plans?|compare\w* plans?|plan options?|coverage options?)\b",
    "appointments_access": r"\b(?:appointments?|schedul\w*|reschedul\w*|available|availability|new patient)\b",
    "prescriptions_pharmacy": r"\b(?:prescriptions?|pharmac\w*|refills?|medications?|drug plan|\[DRUG\])\b",
    "records_referrals_authorization": r"\b(?:records?|referrals?|authoriz\w*|prior authorization)\b",
    "understanding_explanation": r"\b(?:confus\w*|understand\w*|explain\w*|what does|what do you mean|difference between|questions?)\b",
    "handoff_wait_callback": r"\b(?:on hold|holding|transfer\w*|call (?:you |me |them )?back|disconnected|voicemail|voice mail|return\w* call)\b",
}
DOMAINS = {k: re.compile(v, re.I) for k, v in DOMAIN_PATTERNS.items()}
TOPICS = {k: re.compile(v, re.I) for k, v in TOPIC_PATTERNS.items()}
REDACTION = re.compile(r"\[[A-Z][A-Z_]+\]")
SENTENCES = re.compile(r"[^.!?]+[.!?]?")
EXPLANATION = re.compile(r"\b(?:because|means that|that means|in other words|for example|basically|let me explain|difference between|the reason|what happens is)\b", re.I)


def dump_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect():
    if not DATABASE.exists():
        raise SystemExit("Run build first; the local database does not exist.")
    db = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def build():
    if DATABASE.exists():
        raise SystemExit("Existing corpus preserved. Use a new research revision to rebuild.")
    meta = json.loads((SOURCE / "huggingface-metadata.json").read_text())
    entry = next(x for x in meta["siblings"] if x["rfilename"] == "medicare_inbound.zip")
    archive = SOURCE / entry["rfilename"]
    digest = sha256_file(archive)
    if archive.stat().st_size != entry["size"] or digest != entry["lfs"]["sha256"]:
        raise SystemExit("Archive size/hash differs from pinned publisher metadata.")
    temp = DATABASE.with_suffix(".building.sqlite3")
    if temp.exists():
        raise SystemExit("Incomplete build exists; inspect it before retrying.")
    db = sqlite3.connect(temp)
    db.executescript("""
        CREATE TABLE calls (
            call_id TEXT PRIMARY KEY, archive_member TEXT UNIQUE NOT NULL,
            source_sha256 TEXT NOT NULL, text_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            duration_seconds REAL, asr_confidence REAL, word_count INTEGER NOT NULL,
            text_characters INTEGER NOT NULL, redaction_token_count INTEGER NOT NULL,
            labeled_word_count INTEGER NOT NULL, speaker_label_count INTEGER NOT NULL,
            domain_signals TEXT NOT NULL, topic_signals TEXT NOT NULL,
            medicare_candidate INTEGER NOT NULL, advisory_candidate INTEGER NOT NULL
        );
        CREATE VIRTUAL TABLE calls_fts USING fts5(text, content='calls', content_rowid='rowid');
    """)
    errors = []
    schemas = collections.Counter()
    ignored = collections.Counter()
    crc_checked = 0
    count = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir():
                ignored["directory"] += 1
                continue
            # Reading each member to EOF also validates ZIP CRC, including metadata.
            raw = z.read(info)
            crc_checked += 1
            if info.filename.startswith("__MACOSX/") or Path(info.filename).name.startswith("._"):
                ignored["macos_resource_fork"] += 1
                continue
            if not info.filename.endswith(".json"):
                ignored["other_file"] += 1
                continue
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict) or not isinstance(obj.get("text"), str):
                    raise ValueError("Expected an object with string text")
                words = obj.get("words", [])
                if not isinstance(words, list):
                    raise ValueError("words is not a list")
                text = obj["text"]
                domains = [k for k, pattern in DOMAINS.items() if pattern.search(text)]
                topics = [k for k, pattern in TOPICS.items() if pattern.search(text)]
                labeled = [w.get("speaker") for w in words if isinstance(w, dict) and w.get("speaker") is not None]
                call_id = Path(info.filename).name.removesuffix("_transcript.json")
                db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    call_id, info.filename, hashlib.sha256(raw).hexdigest(),
                    hashlib.sha256(text.encode()).hexdigest(), text, obj.get("audio_duration"),
                    obj.get("confidence"), len(words), len(text), len(REDACTION.findall(text)),
                    len(labeled), len(set(map(str, labeled))), json.dumps(domains), json.dumps(topics),
                    int("medicare_term" in domains), int("medicare_term" in domains and "advisory_language" in domains),
                ))
                schemas[json.dumps({k: type(v).__name__ for k, v in sorted(obj.items())}, sort_keys=True)] += 1
                count += 1
                if count % 5000 == 0:
                    db.commit()
                    print(f"Indexed {count:,} transcript files", flush=True)
            except (ValueError, TypeError, sqlite3.Error) as exc:
                errors.append({"archive_member": info.filename, "error": str(exc)})
        db.commit()
        expected_json = sum(i.filename.endswith(".json") and not i.filename.startswith("__MACOSX/") and not Path(i.filename).name.startswith("._") for i in z.infolist() if not i.is_dir())
    db.execute("INSERT INTO calls_fts(calls_fts) VALUES ('rebuild')")
    db.execute("CREATE INDEX calls_text_hash ON calls(text_sha256)")
    db.execute("CREATE INDEX calls_medicare ON calls(medicare_candidate, advisory_candidate)")
    db.commit()
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    fts_rows = db.execute("SELECT count(*) FROM calls_fts").fetchone()[0]
    db.execute("INSERT INTO calls_fts(calls_fts, rank) VALUES ('integrity-check', 1)")
    db.commit()
    db.close()
    manifest = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "owner_requested_date": "2026-11-03", "purpose": "local noncommercial conversation-pattern research",
        "dataset": meta["id"], "source_revision": meta["sha"],
        "source_url": f"https://huggingface.co/datasets/{meta['id']}/resolve/{meta['sha']}/medicare_inbound.zip",
        "archive_size_bytes": archive.stat().st_size, "archive_sha256": digest,
        "publisher_sha256_match": True, "publisher_reported_medicare_calls": 61513,
        "observed_transcript_files": expected_json, "indexed_calls": count,
        "crc_checked_archive_members": crc_checked, "ignored_members": dict(ignored),
        "schema_counts": dict(schemas), "parse_or_insert_errors": errors,
        "sqlite_integrity": integrity, "fts_rows": fts_rows,
        "license": "CC-BY-NC-4.0; retain additional publisher card restrictions",
        "publisher_domain_label_independently_verified": False,
        "speaker_role_attribution": "not inferred", "product_use": "excluded",
    }
    dump_json(LOCAL / "inventory.json", manifest)
    finish_build()


def finish_build():
    """Account for malformed originals explicitly; never repair their text silently."""
    manifest_path = LOCAL / "inventory.json"
    manifest = json.loads(manifest_path.read_text())
    temp = DATABASE.with_suffix(".building.sqlite3")
    if DATABASE.exists() or not temp.exists():
        raise SystemExit("Expected only the pending build; existing final database is preserved.")
    db = sqlite3.connect(temp)
    members = {r[0] for r in db.execute("SELECT archive_member FROM calls")}
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    fts_rows = db.execute("SELECT count(*) FROM calls_fts").fetchone()[0]
    db.execute("INSERT INTO calls_fts(calls_fts, rank) VALUES ('integrity-check', 1)")
    db.commit()
    db.close()
    errors = manifest["parse_or_insert_errors"]
    excluded_members = {r["archive_member"] for r in errors}
    archive = SOURCE / "medicare_inbound.zip"
    if sha256_file(archive) != manifest["archive_sha256"]:
        raise SystemExit("Source archive changed after build")
    with zipfile.ZipFile(archive) as z:
        expected = {i.filename for i in z.infolist() if not i.is_dir() and i.filename.endswith(".json") and not i.filename.startswith("__MACOSX/") and not Path(i.filename).name.startswith("._")}
        if members & excluded_members or members | excluded_members != expected or len(errors) != len(excluded_members):
            raise SystemExit("Original transcript-member accounting is incomplete")
        for r in errors:
            raw = z.read(r["archive_member"])
            try:
                json.loads(raw)
            except (ValueError, UnicodeError):
                r.update({"source_bytes": len(raw), "source_sha256": hashlib.sha256(raw).hexdigest(), "disposition": "excluded from searchable corpus; malformed original retained unchanged in source ZIP"})
            else:
                raise SystemExit("A source exclusion is not malformed JSON; investigate before finalizing")
    if integrity != "ok" or fts_rows != len(members):
        raise SystemExit("Database/search-index validation failed")
    manifest.update({"status": "complete_with_source_exclusions" if errors else "complete", "excluded_malformed_original_files": len(errors), "accounted_original_files": len(members) + len(errors), "source_member_accounting": "indexed members and explicitly excluded originals partition all original transcript JSON members", "sqlite_integrity": integrity, "fts_rows": fts_rows, "publisher_card_sha256": sha256_file(SOURCE / "publisher-README.md"), "source_metadata_sha256": sha256_file(SOURCE / "huggingface-metadata.json")})
    dump_json(manifest_path, manifest)
    temp.rename(DATABASE)
    print(json.dumps({k: manifest[k] for k in ("status", "indexed_calls", "excluded_malformed_original_files", "accounted_original_files", "archive_sha256", "sqlite_integrity", "fts_rows")}, indent=2))


def cohort_clause(cohort):
    return {"all": "1=1", "medicare": "medicare_candidate=1", "advisory": "advisory_candidate=1"}[cohort]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze():
    db = connect()
    REPORTS.mkdir(parents=True, exist_ok=True)
    summary = {"created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "method": "Offline overlapping regex text signals; no inferred speakers, intent, correctness, or advice quality", "cohorts": {}, "rules": {"domains": DOMAIN_PATTERNS, "topics": TOPIC_PATTERNS}}
    for cohort in ("all", "medicare", "advisory"):
        domains = collections.Counter()
        topics = collections.Counter()
        durations = []
        words = []
        redactions = []
        zero_speakers = 0
        blank = 0
        count = 0
        source_words = 0
        questions = collections.Counter()
        for r in db.execute(f"SELECT * FROM calls WHERE {cohort_clause(cohort)} ORDER BY call_id"):
            count += 1
            domains.update(json.loads(r["domain_signals"]))
            topics.update(json.loads(r["topic_signals"]))
            if r["duration_seconds"] is not None:
                durations.append(r["duration_seconds"])
            words.append(r["word_count"])
            source_words += r["word_count"]
            redactions.append(r["redaction_token_count"])
            zero_speakers += r["labeled_word_count"] == 0
            blank += not r["text"].strip()
            normalized_questions = set()
            for m in SENTENCES.finditer(r["text"]):
                s = m.group().strip()
                if s.endswith("?") and 15 <= len(s) <= 350:
                    normalized_questions.add(re.sub(r"\s+", " ", s).casefold())
            questions.update(normalized_questions)
        distinct = db.execute(f"SELECT count(DISTINCT text_sha256) FROM calls WHERE {cohort_clause(cohort)}").fetchone()[0]
        summary["cohorts"][cohort] = {
            "calls": count, "distinct_exact_text_hashes": distinct, "duplicate_text_excess": count-distinct,
            "blank_text_calls": blank, "calls_without_any_word_speaker_label": zero_speakers,
            "source_word_entries": source_words,
            "source_duration_hours": round(sum(durations) / 3600, 3),
            "median_duration_seconds": statistics.median(durations) if durations else None,
            "median_word_entries": statistics.median(words) if words else None,
            "median_redaction_tokens": statistics.median(redactions) if redactions else None,
            "domain_signal_call_counts": dict(domains.most_common()),
            "topic_signal_call_counts": dict(topics.most_common()),
        }
        write_csv(REPORTS / f"{cohort}-question-patterns.csv", ["normalized_question", "calls_with_exact_question", "speaker_role", "review_status"], ({"normalized_question": q, "calls_with_exact_question": n, "speaker_role": "unknown", "review_status": "unreviewed; punctuation/ASR dependent"} for q, n in questions.most_common(250)))
    dump_json(REPORTS / "summary.json", summary)
    sample_rows = []
    question_rows = []
    explanation_rows = []
    for cohort in ("all", "medicare", "advisory"):
        ids = [r[0] for r in db.execute(f"SELECT call_id FROM calls WHERE {cohort_clause(cohort)} ORDER BY call_id")]
        chosen = random.Random(20261103).sample(ids, min(100, len(ids)))
        sample_dir = REPORTS / "review-calls" / cohort
        sample_dir.mkdir(parents=True, exist_ok=True)
        for call_id in chosen:
            r = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
            sample_rows.append({"cohort": cohort, "call_id": call_id, "archive_member": r["archive_member"], "duration_seconds": r["duration_seconds"], "domain_signals": r["domain_signals"], "topic_signals": r["topic_signals"], "reviewed_domain": "", "interaction_type": "", "caller_problem": "", "key_question": "", "explanation_strategy": "", "quality_concerns": "", "reviewer": ""})
            (sample_dir / f"{call_id}.txt").write_text("SOURCE: " + r["archive_member"] + "\nSPEAKER ROLES: unknown; do not infer from punctuation.\n\n" + r["text"] + "\n")
            for m in SENTENCES.finditer(r["text"]):
                sentence = m.group().strip()
                if len(sentence) < 15 or len(sentence) > 600:
                    continue
                row = {"cohort": cohort, "call_id": call_id, "character_start": m.start(), "character_end": m.end(), "text_span": m.group(), "speaker_role": "unknown", "review_status": "unreviewed"}
                if sentence.endswith("?"):
                    question_rows.append(row)
                if EXPLANATION.search(sentence):
                    explanation_rows.append(row)
    write_csv(REPORTS / "review-queue.csv", ["cohort", "call_id", "archive_member", "duration_seconds", "domain_signals", "topic_signals", "reviewed_domain", "interaction_type", "caller_problem", "key_question", "explanation_strategy", "quality_concerns", "reviewer"], sample_rows)
    span_fields = ["cohort", "call_id", "character_start", "character_end", "text_span", "speaker_role", "review_status"]
    write_csv(REPORTS / "sample-question-spans.csv", span_fields, question_rows)
    write_csv(REPORTS / "sample-explanation-spans.csv", span_fields, explanation_rows)
    brief = ["# Initial local corpus audit", "", "Noncommercial descriptive research. These are text-signal counts, not independently reviewed caller intents or agent/client conversations.", "", "| Cohort | Calls | Distinct exact texts | No speaker labels | Median seconds |", "| --- | ---: | ---: | ---: | ---: |"]
    for cohort, row in summary["cohorts"].items():
        brief.append(f"| {cohort} | {row['calls']:,} | {row['distinct_exact_text_hashes']:,} | {row['calls_without_any_word_speaker_label']:,} | {row['median_duration_seconds']} |")
    brief += ["", "`medicare` means an explicit Medicare/Medigap term. `advisory` additionally requires advisory-language regex. Both are candidates requiring review, not confirmed broker calls. Their absence does not prove a call is unrelated, especially after redaction.", "", "## Overlapping text signals", "", "| Signal | Full archive | Medicare candidates | Advisory candidates |", "| --- | ---: | ---: | ---: |"]
    for topic in TOPICS:
        counts = [summary["cohorts"][c]["topic_signal_call_counts"].get(topic, 0) for c in ("all", "medicare", "advisory")]
        brief.append(f"| {topic} | {counts[0]:,} | {counts[1]:,} | {counts[2]:,} |")
    brief += ["", "## Limits and next review", "", "- The publisher's Medicare folder contains off-domain material, including veterinary and dental-office calls in initial inspection. Do not equate folder membership with Medicare brokerage advice.", "- ASR punctuation is not a reliable speaker boundary. All exported questions/explanation candidates have unknown speaker role.", "- Signal categories overlap and include IVR, hold messages, staff speech, and caller speech. Counts do not measure population prevalence or advice correctness.", "- Exact text hashes expose duplicates, but near duplicates and repeated automated messages need separate review.", "- The source is historical and heavily redacted; current coverage rules cannot be learned or verified from these conversations.", "- Review the seeded 100-call samples per available cohort in review-queue.csv. Preserve evidence spans; manually assign domain, interaction type, caller problem, questions, and explanation strategies only after reading the full call.", "- No model-based classification, external analysis API, product integration, or training has been run."]
    (REPORTS / "FIRST_PASS.md").write_text("\n".join(brief) + "\n")
    print(json.dumps(summary["cohorts"], indent=2))
    print(f"Saved local analysis and review samples in {REPORTS}")


def search(query, cohort, limit):
    db = connect()
    rows = db.execute(f"SELECT c.call_id, c.duration_seconds, c.domain_signals, snippet(calls_fts, 0, '[', ']', ' … ', 28) AS excerpt FROM calls_fts JOIN calls c ON c.rowid=calls_fts.rowid WHERE calls_fts MATCH ? AND {cohort_clause(cohort)} ORDER BY rank LIMIT ?", (query, limit))
    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=False))


def show(call_id):
    row = connect().execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
    if row is None:
        raise SystemExit("Unknown call ID")
    print(json.dumps({k: row[k] for k in row.keys() if k != "text"}, indent=2))
    print("\n" + row["text"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    commands.add_parser("finish-build", help="Validate/finalize an indexed build with explicitly malformed originals")
    commands.add_parser("analyze")
    p = commands.add_parser("search")
    p.add_argument("query", help='SQLite FTS5 query, e.g. \'"medicare advantage"\'')
    p.add_argument("--cohort", choices=("all", "medicare", "advisory"), default="all")
    p.add_argument("--limit", type=int, default=10)
    p = commands.add_parser("show")
    p.add_argument("call_id")
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "finish-build":
        finish_build()
    elif args.command == "analyze":
        analyze()
    elif args.command == "search":
        search(args.query, args.cohort, args.limit)
    else:
        show(args.call_id)


if __name__ == "__main__":
    main()
