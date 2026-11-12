# VE-03 independent decision-case review

Status: prepared for authoring. DQ-02 reviewer assignment and DQ-25 exact P0 materials approval remain open. This packet contains fictional inputs and a blank answer key.

Start with [case inputs](reviewer-inputs.json) and the [blank answer key](reviewer-answer-key.blank.json). The actions preserve the original profile reports, choices and corrections in sequence. Write and freeze the expected decisions before opening any Daylight test results, assertions or sample outputs. The existing controller fixtures are kept separately for regression testing.

## Cases and checkpoints to consider

| Case | Decision checkpoint |
| --- | --- |
| P1 | Spouse's job ends in November. Identify what the missing insurance end date changes for the requested December transition. |
| P1-payer | Payer order and HSA timing after correction of the original Medicare eligibility basis. Consider each employer-size answer under the threshold it refers to. |
| P2 | Separate the COBRA end date, the move, dependent coverage and drug gap. Evaluate the requested 2027 scope on its own terms. |
| P2-browse | Describe the scope of 2026 Collier published research and whether the requested use needs any personal conclusion. |
| P3 | Distinguish leaving MA, enrollment timing, Medigap rights and what the reported plan-ending notice establishes. |
| P3-replacement | Compare the case for keeping the current policy and investigating replacement. Identify any material unresolved rights, terms or price. |
| P4 | Separate the two provider sites and the exact drug, fill and pharmacy checks. Identify which conclusions change when assistance or other inputs change. |
| P4-unknown | Decide what can be said about the reported medicine when the strength is missing. |
| P5 | Keep the beneficiary's military coverage, travel, budget and assistance separate from the helper. Distinguish reported program participation from plan-specific eligibility. |
| P6 | Evaluate the output before and after the explicit COBRA date correction. Identify which prior conclusions must be rechecked. |
| P7 | Decide what research and comparison steps are supportable with the facts still unknown. |
| P8 | Distinguish education, medicine-cost preparation and the return to comparison as the person's request changes. |
| P9 | Evaluate which facts belong to the helper and which belong to the beneficiary at each requested or corrected change of subject. |
| P10 | Distinguish both strengths and fills. Evaluate what changes after the ambiguous request and after its exact clarification. |

## Write the expected result

For each case, record one or more checkpoints by action number. Use a structured entry with these fields.

| Field | What to record |
| --- | --- |
| `after_action` | One-based action number and, when useful, the before/after correction pair. |
| `paths` | Relevant coverage or research paths and conditions for each. Include keep or defer when applicable. Use an empty list with a reason when no path decision applies. |
| `eligibility` | The exact eligibility or applicability question and its supported, ineligible, unresolved or out-of-scope disposition. Distinguish reported facts from verified facts. |
| `holds` | Each missing, stopped, unaccepted or conflicting input or source, the conclusion it affects, and the check that could resolve it. |
| `abstentions` | Each conclusion or action that must be withheld and what the person can do next. |
| `expected_output` | Material statements, required qualifications, and statements the sample must avoid. Use substantive conditions so equivalent wording can pass. |
| `evidence_and_methods` | Exact source release, claim or page, applicable year/scope, approved purpose, method version, and any validity window, hold or STOP. |

Record what is in scope for P0 separately from any desired later capability. A 2027 request can test an out-of-scope boundary without importing 2026 evidence. If the P0 study claims a supported end-to-end path and the existing inputs lack one, extend an existing profile with only the exact evidence and facts needed. Pair it with a variant that removes or invalidates one consequential input. Independently review the extension before using it as an expected result.

## Bind and approve the exact study materials

1. The founder records the DQ-02 reviewer and scope and identifies the exact DQ-25 P0 materials for review. Use the [federal reference receipt](../../cms-slice/data-sources/l01-published-reference-review.json) within its stated scope. The [r13 Collier review](../../docs/product/recommendation-scope-2026-11-04-r13/REVIEW.md) is an offline candidate with consumer approval pending. Check the [Plans acceptance record](../../cms-slice/data-sources/plans-workspace-acceptance.json) for the actual scope and status.
2. In a copy of the blank key, the reviewer records exact source and method manifests, the approved scope, the merged build commit, the engine lock and model policy hashes, and the configured model IDs. Freeze the authored key with its hash, reviewer identity and date before comparing it with Daylight outputs.
3. Separately record the exact sample ID and SHA-256, case and checkpoint, frozen key SHA-256, build and evidence bindings, allowed purpose, disposition, reviewer and date for each P0 sample shown to participants. A changed sample, source, method or build needs a new bound review. Complete the exact sample review before any participant session.

Daylight requirements addressed here are D86 for reported facts, corrections and holds, D91 for scoped evidence and acceptance, and D64 for decision independence. See the [advisor handoff contract](../../docs/product/plan-review-2026-11-04/HANDOFF.md) and [independence acceptance](../../docs/product/INDEPENDENCE_ACCEPTANCE.md).
