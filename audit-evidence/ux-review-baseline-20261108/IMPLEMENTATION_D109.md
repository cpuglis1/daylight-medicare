# D109 implementation · November 8, 2026 · redirect, don't deflect

Owner direction (chat, Nov 8): "we are building an agent who people go to for
answers/support. we should be not deflecting, but re-directing… the default for
the tool should not be to tell users to talk to other people." Approved the full
plan including the §4 reviewed-statement fallback as an exception to D88.

## Backend (`alternatives/advisor-first/`)

| Change | Files | What it does |
| --- | --- | --- |
| Applicable rules (deterministic) | `applicable_rules.py` (new), `pilot-rules.json` (new), `natural_flow.py` compose_response | From resolved reports only, selects the general rules relevant to the person (working-coverage SEP, HSA, MA trial right, Part D penalty, Extra Help, Open Enrollment window, Original Medicare nationwide) and the approved question that would confirm the personal part. Passed as `applicable_rules` + `required_target`; rule statements are front-loaded into the evidence (bound raised 6 → 8). `DAYLIGHT_DISABLE_PILOT_RULES=1` turns the statements off. |
| Prompt | `natural_agent.py` COMPOSE_INSTRUCTIONS | Replaced the defensive scope block with: state the rule; name the personal gap; redirect, don't deflect; phrase rules as rules (never "you can enroll/switch", "you qualify"). Removed the "a question can stand on its own without preamble" licence; acknowledge every recorded fact in a clause. `required_target` contract and the yes/no-over-list rule added to the output contract. |
| Question guard | `natural_agent.py` `_validate_composition_core` | While `required_target` exists and the person has not paused: a third-party referral question is always replaced; outside a learning turn (explicit explain/clarify/revisit, a learner uncertainty signal, or "I just want to learn"), a null-target or offer-pattern question is replaced by the required meaning's approved wording. The reply is kept. A yes/no sentence over a ≥3-choice list uses the list's own question. |
| Never-blank floor | `natural_flow.py` compose_response except-branch, `recovery_statement()`, `conversation_output.py` | On any composition failure after the one repair: one reviewed statement (rule summary → evidence summary → fixed line) plus the server-selected approved question; `advisor.reason = 'recovery'` lets the output filter keep it. Notice: "I couldn't finish that answer. Here is the part I'm sure of." Recovery question falls back to `required_target` so `question_available` is no longer False. |
| Length | `natural_agent.py` `_compose_once` | `incomplete / max_output_tokens` becomes a repairable rejection with a shorter-length instruction (uses the existing one repair slot). Output allowances unchanged (900 gpt-5.4 / 2400 Sol) to keep the shared budget ledger compatible. |
| Rolling discourse brief | `natural_agent.py` extraction schema/validation, `narrative_agent.py` instruction, `advisor_memory.py` (`DISCOURSE_NOTES=10`, `DISCOURSE_CHARS=1200`), `natural_flow.py` | Stage 1 returns `discourse_note` (≤160 chars, no names/dates/amounts/identifiers); the server keeps a bounded list in the visit brief (RAM, 1-hour TTL, never saved) and composition receives it with profile and curriculum, so token packing can drop old exchanges without losing their gist. No extra model call. |
| Pilot year default | `plan_review.py` (`DEFAULT_YEAR = 2026`) | Unanswered coverage year defaults to 2026 (D108) so "Review your info" becomes reachable; a reported year still wins; two different years still hold. |

## Front end (`web-8894/` only; `web/` untouched)

Question kept in view after a reply (never pulls a reader who scrolled up); down cue hidden at the bottom; server notices persist inside the Daylight message; privacy dialog fits the viewport; progress track is sticky (no jump on a failed turn); T05 refinement label caregiver-neutral; Plans tab opens on "Two ways to get Medicare" (bullets from the existing teaching facts, "What you've told us" line, honest Medigap/Part D wording), "Check plans for me" shown only after the conversation's review produced a handoff, sticky Plans header; a handoff open goes straight to the checked list.

## Tests

- New: `tests/test_applicable_rules.py` (11), `tests/test_plan_review.py::test_unanswered_year_defaults_to_pilot_year`.
- Updated to the new contract (each with a dated comment): `test_plan_review` (RC03 no longer required), `test_advisor_planning` (2), `test_conversation_framework` (1), `test_decision_guidance` (2), `test_decision_progress_acceptance` (1), `test_explicit_stop` (1), `test_natural_agent` (wire: `discourse_note`), `test_timing_recovery` (3), `test_turn_contract` (3).
- Offline persona harness: 14/14 scenarios, 1,244 assertions, 0 paid calls.
- Suites run in the review sandbox (Python 3.10, old jsonschema, no 'Z' isoformat): every remaining failure/error is on the owner's `pilot-offline-evaluation-20261108` pre-existing list or is a sandbox environment artifact (`fromisoformat('…Z')`, `Draft202012Validator`, `test_comparison_http` setUpClass). Run the full suite on the Mac (Python 3.14) before the pilot build.

## Open for the owner

1. ~~Accept the seven statements~~ Accepted by the owner, Nov 8 12:48 ET ("approved"), with the §4 fallback exception to D88.
3. Copy D103–D108 from the Drive owner-decisions doc into `DAYLIGHT_REQUIREMENTS.md`.
