# CallCenterEN Medicare conversation research

Owner-requested November 3, 2026: add the Medicare subset for noncommercial exploration of caller problems, questions, and explanations. The owner will review the role-play and sales videos separately.

This is a separate historical conversation-research collection, outside the L01–L15 plan-evidence layers, product retrieval, recommendation logic, model training, and consumer-release work. The dataset is not an accepted source of Medicare facts or an example of independently reviewed advice. Adding it does not change any product requirement or evidence acceptance.

## Source and use

- Publisher: AIxBlock, with Ha Dao, Gaurav Chawla, Raghu Banda, and Caleb DeLeeuw.
- Dataset: [CallCenterEN / 92k real-world call-center scripts](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english).
- Paper: [Real-World En Call Center Transcripts Dataset with PII Redaction](https://arxiv.org/abs/2507.02958), 2025, arXiv:2507.02958.
- Selected archive: `medicare_inbound.zip`; the paper reports 61,513 Medicare inbound conversations within 91,706 total conversations. Those are publisher-reported counts until the local inventory is complete.
- Public terms: CC BY-NC 4.0; the dataset card additionally states commercial use, resale, or redistribution is prohibited. Preserve the exact downloaded card and metadata with the source.
- Authorized purpose here: local, noncommercial descriptive research only. This record does not establish that downstream product development, evaluation, or training is licensed. Any changed purpose requires separate rights review/permission.

Calls were reportedly collected around 2020. Public files contain machine transcripts without audio. Publisher redaction covers names, dates, medicines, conditions, organizations, amounts, and other categories. Redaction and transcription quality have not been independently certified here. Treat individual records as potentially sensitive and keep transcripts, excerpts, indexes, and derived reports in the ignored `local/` directory. Do not publish or send them to external AI services.

## Research questions

1. What problems and uncertainties do callers bring into the conversation?
2. Which questions recur, and which follow-ups clarify the underlying need?
3. What explanations, comparisons, examples, and checks for understanding appear?
4. How much of this archive is actual advice versus qualification, transfers, scripted sales, or administration?
5. Which observations are limited by missing speaker labels, heavy redaction, duplicates, dated content, or selection bias?

Counts of keywords are exploratory text signals, not verified caller intents, question authorship, advice quality, or population prevalence. Keep agent and caller attribution unknown unless the record supports it. No enrollment/conversion outcome is a quality label.

## Local layout

`local/source/` retains the pinned source metadata, publisher card, and original archive. The archive is processed directly rather than expanding tens of thousands of original files.

Pinned source revision: `9d40ca13f3e173ad815c89bb8fff144be3ae3146`. Archive size: 826,517,526 bytes. Publisher SHA-256: `50d8da9f556c48951cca27360771cd0564004fd7eed4e8f640236173b8b295ea`.

| Local artifact | Purpose |
| --- | --- |
| `local/source/medicare_inbound.zip` | Original downloaded archive, retained without modification. |
| `local/source/huggingface-metadata.json` | Exact revision, publisher file size/hash, and source metadata. |
| `local/source/publisher-README.md` | Original dataset card and stated use restrictions. |
| `local/inventory.json` | Hash/CRC, parse, row-count, schema, and search-index checks, including nine malformed source exclusions. |
| `local/calls.sqlite3` | Full-text-searchable original transcript text with source-member references and unreviewed text signals. |
| [First-pass audit](local/analysis/FIRST_PASS.md) | Corpus audit and descriptive signal counts, with explicit limitations. |
| [Qualitative notes](local/analysis/QUALITATIVE_NOTES.md) | Four fully read targeted provider-office examples; tentative observations, not verified advice or a representative sample. |
| `local/analysis/qualitative-examples.json` | Example source members/hashes, exact excerpt offsets, and unreviewed qualitative annotations. |
| `local/analysis/summary.json` | Machine-readable corpus/cohort counts and exact regex rules. |
| `local/analysis/*-question-patterns.csv` | Repeated question-text candidates, with unknown speaker role. |
| `local/analysis/sample-question-spans.csv` | Question candidates in seeded review samples, with exact character offsets. |
| `local/analysis/sample-explanation-spans.csv` | Explanation-language candidates in seeded review samples, with exact character offsets. |
| `local/analysis/review-queue.csv` | Up to 100 seeded calls per cohort, with blank human-review columns. |
| `local/analysis/review-calls/` | Complete text for the review samples; raw word metadata remain in the ZIP. |

## Offline tools

No dependencies beyond Python's standard library and SQLite with FTS5. Run from the repository root:

```sh
python3 docs/research/callcenteren-medicare-2026-11-03/corpus.py build
python3 docs/research/callcenteren-medicare-2026-11-03/corpus.py analyze
python3 docs/research/callcenteren-medicare-2026-11-03/corpus.py search '"medicare advantage"' --limit 10
python3 docs/research/callcenteren-medicare-2026-11-03/corpus.py search 'deductible OR premium' --cohort medicare
python3 docs/research/callcenteren-medicare-2026-11-03/corpus.py show CALL_ID
```

`build` preserves an existing database and refuses to overwrite it. `analyze` regenerates the machine-created first-pass reports and seeded review queue; preserve any manually edited queue under a separate filename before rerunning. No external analysis API is invoked. All search/excerpt output is for local research.

The `medicare` cohort requires an explicit Medicare/Medigap term. The `advisory` cohort additionally requires an advisory-language signal. Neither is a confirmed broker-call classification. Redaction can hide relevant terms; IVR/hold material can introduce irrelevant ones. Topic signals overlap and include both parties and automated speech.

## Source-quality finding from initial inspection

The publisher's `medicare_inbound` folder is not a clean collection of Medicare broker consultations. A deterministic six-record random inspection (seed `20261103`, sampled over archive transcript-member order) included veterinary scheduling/grooming, dental billing/insurance questions, and clinic scheduling. These six records have no non-null word-level speaker labels. This is a sample finding, not a population estimate; use the full inventory and review queue to assess the collection further.

Manually review domain and interaction type before describing any pattern as a Medicare-advice pattern. The presence of a question or an explanation marker does not establish who spoke, factual accuracy, a successful resolution, or good advisory behavior.

## Observed inventory and first pass

Acquisition and local indexing completed November 3, 2026. All 61,513 original transcript-file slots are accounted for: **61,504 parsed/indexed records and nine malformed JSON originals** retained unchanged in the ZIP and listed individually in `local/inventory.json`. The archive's 123,011 non-directory members passed CRC checks, and its SHA-256 matches the publisher's metadata. SQLite and FTS consistency checks passed.

The searchable corpus has 60,858 distinct exact transcript-text hashes (646 excess duplicate-text records); none of its 61,504 records contains a non-null word-level speaker label. Explicit Medicare/Medigap terms occur in **1,602 records**; **237** of those also match the exploratory advisory-language rules. These are overlapping lexical filters, not confirmed Medicare-advice counts. Redaction can hide relevant terms. Full rules and cohort-specific denominators are in `local/analysis/summary.json`.

The full scan also flags 24,684 records with veterinary-related terms and 14,886 with dental-related terms. These counts overlap and may include automated announcements. They reinforce the source-label limitation; they do not supply validated domain classifications. Four targeted Medicare-related examples read in full appear to be provider-office interactions, not brokerage consultations.

The initial qualitative examples concern prospective-plan acceptance, a directory/plan-type/site mismatch, requests for procedure-price estimates, insurance-card confusion, and reassurance without visible completed verification. These are tentative observations with source spans, suitable for further noncommercial inquiry only. They do not demonstrate patterns among Medicare brokers or establish current coverage facts.

The collection is deliberately separate from the live advisor and existing research databases. No application imports or production ingestion registrations are added.

## Call-pattern analysis requested November 3, 2026

[`analyze_patterns.py`](analyze_patterns.py) extends the initial keyword inventory with a reproducible, offline call-workflow analysis. It reads the existing database without changing it, preserves source hashes and evidence offsets, suppresses explicit menu/hold passages where detectable, and reports:

- Exclusive estimates of the primary detected work type, including basic scheduling/intake, coverage/provider acceptance, prices, billing, records/referrals/prescriptions, service questions, routing, and unclear calls.
- Overlapping problem/work signals, question families, and explanation-language families. Question authorship remains unknown. Procedural guidance, uncertainty, examples, concept distinctions, reassurance, generic understanding checks, and teach-back requests remain separate signals.
- Enrollment-related contexts, distinguishing history/timing/identifier mentions, possible noninsurance memberships/applications, ambiguous mentions, and strong process/completion-language candidates. A candidate never constitutes externally verified enrollment.
- All-record and exact-text-deduplicated denominators, plus the explicit Medicare/Medigap-mention cohort and its deduplicated denominator.
- A reproducible stratified full-call review sample and source-linked question/explanation examples.

Run from the repository root:

```sh
python3 docs/research/callcenteren-medicare-2026-11-03/analyze_patterns.py
python3 -m unittest discover -s docs/research/callcenteren-medicare-2026-11-03 -p 'test_analyze_patterns.py' -v
```

The current default report destination is [local/pattern-analysis-r3/REPORT.md](local/pattern-analysis-r3/REPORT.md). The [findings and qualitative audit](local/pattern-analysis-r3/FINDINGS.md) explain the main results, failure modes, and more substantive calls to inspect. Outputs also include `summary.json`, `call-type-distribution.csv`, `overlapping-pattern-counts.csv`, `call-classifications.jsonl`, `enrollment-audit.csv`, `question-explanation-examples.csv`, `review-sample.csv`, `review-calls/`, `method.py`, and `verification.json`. Existing output directories are preserved: pass `--output docs/research/callcenteren-medicare-2026-11-03/local/pattern-analysis-r4` for a new run. All transcript-derived outputs must remain under this collection's ignored `local/` directory.

These are rule-based research estimates, not validated semantic labels. Full-call spot checks can expose errors; they do not establish independent classifier accuracy. The fictional tests exercise substantive boundaries such as past enrollment versus active submission, pet membership versus insurance enrollment, menu prompts versus requests, and unknown speaker roles. They do not certify real-call classification quality.

### Completed r3 run and scope accounting

The r3 run covers all 61,504 parsed records, with exclusive automatic distributions reconciling for every cohort. It checks 674,464 evidence-span bounds and 730 exact exported snippets. Sixteen fictional boundary tests pass. Sixteen full calls received assistant qualitative reading; 92 first enrollment contexts from the raw Medicare-mention cohort were screened. These are explicitly not independent domain review or representative classifier validation.

The r1 and r2 outputs remain in place with exact method snapshots. Full-call reading rejected r1's sole apparent active-insurance-enrollment case as existing-insurance data entry. r2 tightened that boundary. r3 additionally suppresses detectable leading automated/hold passages, distinguishes care-program inquiries and third-party research candidates, and reports both the original 1,602-record lexical Medicare cohort and a 1,596-record cohort with Medicare terms outside the detected suppressed content. This does not remove the six records from the original archive or change the source denominator.

The r3 automatic results contain 25 care-program-information/eligibility candidates, two third-party research candidates, and no strong live-insurance-enrollment process/completion candidates. Full reading confirms one third-party research example and rejects the second as beneficiary-ID/referral intake. The sole full-archive teach-back-language marker is also a false positive; zero such markers occur in the conversational Medicare cohort. Those failures remain visible in [review-observations.json](local/pattern-analysis-r3/review-observations.json); raw automatic counts are not silently relabeled as reviewed facts.

The [casebook index](local/pattern-analysis-r3/casebook-index.csv) links 36 local full transcripts covering the program/research candidates and reviewed examples. Unread candidates are marked unreviewed. The files remain local, noncommercial research material; no customer outcomes, current Medicare-rule findings, or released product capabilities are established.
