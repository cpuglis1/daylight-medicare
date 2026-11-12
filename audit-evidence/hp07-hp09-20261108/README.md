# HP-07 and HP-09 implementation evidence

November 8, 2026 · Owner request in chat: "implement hp-07 and hp-09." Variant: advisor-first (:8893). Requirement IDs: HP-07 (launch security spec §5.3, §6.6), HP-09 (spec §5.2.7; SPEC-D5 recorded in D101). Fictional data only; no live model calls or paid probes. Changes are uncommitted and need founder review (OP-09) before merge.

## What changed

| File | Change |
| --- | --- |
| `identifier_guard.py` (new) | Detects SSNs (separated and plain, with validity rules), Medicare numbers (exact MBI alphabet, with or without dashes or spaces) and card numbers (13–19 digits, Luhn). Returns categories only, never values. A narrower transport check uses only high-confidence shapes. |
| `natural_flow.py` | Refuses any submitted action (message or answer) containing an identifier, with a plain message, before validation of content, model calls, storage or logging. Also checks `message()` directly. Installs the log guard. |
| `provider_transport.py` | Backstop: refuses to send a model request whose body contains an identifier; raises `ProviderTransportError('identifier_blocked')`. |
| `transport_diagnostics.py` | Allows the fixed `identifier_blocked` category in content-free failure logs. |
| `log_guard.py` (new) | Last-line filter on Daylight loggers: a rendered line containing an identifier shape is replaced by a fixed notice. |
| `tests/test_identifier_guard.py` (new) | 9 tests: detector positives and negatives, transport backstop, HTTP refusal of messages and answers, nothing stored, no identifiers in logs. |
| `tests/test_content_free_logs.py` (new) | 6 tests: static check of all 16 log calls (fixed format strings, no content variables), provider error bodies and exception messages never logged, filter behavior, and a fictional journey with canary doctor, drug, pharmacy and condition names whose captured logs and console output contain none of them. |

## What ran

- `python3 -m unittest discover -s alternatives/advisor-first/tests -p test_identifier_guard.py` and `-p test_content_free_logs.py`: 15 tests, OK.
- False-positive scan of the transport check over 1,565 catalog, data and code files in advisor-first, chat-first/cms-slice and cms-slice: 0 hits.
- Full suite, module by module, in this sandbox (Python 3.10): 94 modules. 21 modules fail, and every one fails identically on an unmodified snapshot taken before these changes (or fails less). The failures are environment artifacts here: `datetime.fromisoformat` needs Python 3.11+ for `Z` timestamps, and some modules import siblings that are only on `sys.path` when the whole suite runs in one process. No test fails only with these changes. Re-run the full suite on the founder's machine.

## Verified by inspection

- Structured-output schemas use server IDs only (question IDs, report IDs with `doctor-N`/`medicine-N` entities validated by regex, catalog evidence IDs, fixed enums). No user text enters schema enums.
- The AI-transfer choice (`aiConsent`) and saving remain separate gates (existing behavior, unchanged).
- Existing log calls already carry fixed codes, counts, byte sizes and allowlisted diagnostics.

## Open

- SPEC-D5 usage ledger (`pilot-usage-v1`, budget reservations) is SA-17/SA-06 work in `pilot_budget.py`, in progress in a parallel workstream; not part of this change.
- Saved transcripts (HP-08) need their own numbered decision in the repo before building. The Drive decision log's D100–D107 numbering collides with repo D100–D102 and must be reconciled.
