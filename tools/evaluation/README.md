# Evaluation harness

Added November 5, 2026. One command runs the five suites from the stack
evaluation against the current code and writes a dated report:

```sh
python3 tools/evaluation/run_suites.py            # from the repository root, Python 3.11+
python3 tools/evaluation/run_suites.py --check    # confirm every referenced test exists
```

Reports go to `outputs/evaluation/<UTC time>/` as `report.json` and `REPORT.md`.
Every suite is offline and fictional: no network, no paid model calls and no
provider credentials (the runner strips them from the test environment). The
owner still assesses conversation quality; nothing here substitutes for that.

| Suite | What it runs | What it cannot tell you |
| --- | --- | --- |
| Persona journeys | `persona_runner.py`: 14 synthetic personas, injected model responses | Real-model conversation quality |
| Checklist coverage | Scoring of the 12 CMS pre-enrollment items in a decision receipt | The advisor emits no receipts yet, so no real decision is scored |
| Factual grounding | Pinned educational statements and published-reference verifiers | Each sentence a live model writes |
| Commission counterfactual | I01 payout variations on the ranking code; I02 output and decision-record leak checks | Canary checks on serialized model requests (rest of I02) |
| Abstention | Explicit stops, failed responses, comparison-engine holds | A live model choosing to abstain |

Most suites reuse tests that already existed. New on November 5:
`alternatives/advisor-first/tests/test_independence_counterfactual.py` and the
`infrastructure/daylight-operations` tests. Checklist and decision-record
suites need `pytest`; without it they report "unavailable", never "passed".

Run it whenever prompts, models, data or ranking code change, and keep the
report with the change's evidence packet.
