# Enrollment record v2

November 13, 2026 · D164 follow-up · Backend contract for :8895.

```python
journey = enrollment_journey.status(flow, guide, record, today=None)
```

Call with validated, beneficiary-bound reports. Pin `today` with a
`datetime.date` in tests. The function returns a JSON-compatible view and
recomputes it on each call. It uses no model, network, persistence or mutation.

## Exact test-person output

Fictional replay pinned to November 13, 2026. The person turned 65 on October
20, 2026, has coverage through their own current job, and reported retirement
in December 2026. Before the application there was no RC04 or per-part report.
The existing birthday field holds month/year and the first-day flag. This
replay seeds the reported retirement month, then uses the existing capture
for “I applied.”

Before “I applied”:

```json
{
  "version": "enrollment-journey-v2",
  "parts": {
    "A": {"state": "unknown", "start": {"date": null, "basis": null}},
    "B": {"state": "unknown", "start": {"date": null, "basis": null}}
  },
  "window": {"start": "2026-07-01", "end": "2027-01-31", "phase": "inside"},
  "route": "confirm_with_social_security",
  "next_step": {"id": "confirm_with_social_security", "by": null, "basis": null},
  "components": {"medigap": "unknown", "part_d": "unknown"},
  "finish": null,
  "unsupported": ["current_work_coverage"],
  "coverage_end": {"date": "2026-12-31", "precision": "month", "basis": "reported", "source": "S_RETIREMENT"}
}
```

After “I applied”:

```json
{
  "version": "enrollment-journey-v2",
  "parts": {
    "A": {"state": "pending", "start": {"date": null, "basis": null}},
    "B": {"state": "pending", "start": {"date": null, "basis": null}}
  },
  "window": {"start": "2026-07-01", "end": "2027-01-31", "phase": "inside"},
  "route": "none_needed",
  "next_step": {"id": "wait_for_decision", "by": null, "basis": null},
  "components": {"medigap": "unknown", "part_d": "unknown"},
  "finish": null,
  "unsupported": ["current_work_coverage"],
  "coverage_end": {"date": "2026-12-31", "precision": "month", "basis": "reported", "source": "S_RETIREMENT"}
}
```

## Reads and precedence

| Read | Use |
| --- | --- |
| `flow.report(record, 'RC04').choice` | Baseline per-part states |
| `flow.value(guide, 'situation.age65')` | Existing birthday-month timing helper |
| `flow.value(guide, 'coverage.current')`, RC09 `choice` | Current-work and coverage holds |
| RC06 `choice`, `flow.value(guide, 'coverage.socialBenefits')` | Non-age or Railroad holds. Generic benefits receipt does not establish automatic enrollment |
| `flow.value(guide, 'enrollment.partA')` / `enrollment.partB` | Reported per-part status and date. A usable ISO date with `date_kind: start` is a reported start |
| `flow.value(guide, 'intent.coveragePath')` / `intent.components` | Path, component decisions and finish |
| `flow.report(record, 'RC11').coverageEnd` | First usable end-date report. Source `RC11.coverageEnd` |
| `flow.report(record, 'RC11').jobEnd` | Second choice. Source `RC11.jobEnd` |
| `flow.value(guide, 'situation.retirement').when` | Last choice, for `retired` or `retiring`. Source `S_RETIREMENT` |

The end-date parser reuses the RC11 normalizer. An explicit month and year
such as `2026-12` or `December 2026` returns the month's last day with
`precision: month`. An explicit calendar day gives `precision: day`.
Missing, stale, invalid, unresolved and relative-only values supply no date.
A fallback describes the job or retirement report, so the caller should
keep that provenance when rendering it. The current-work hold, Part B
estimate and deadlines are independent of `coverage_end`.

With a hold and a denial or any `needed` or `unknown` part, both `route` and
`next_step.id` are `confirm_with_social_security`. Otherwise a held record
uses route `none_needed` and this order: `answer_request`, conflicting
reported start (`confirm_start_date`), `wait_for_decision`, future approved
start (`confirm_start_date`), then `nothing_needed`. Held `next_step.by`
and its basis are null. The window and reported starts stay available.
For a held future approval, render the reported date from the corresponding
`parts.*.start`. The window is the existing birthday-derived Initial
Enrollment Period, even when a hold prevents personal timing.

| Field | Values |
| --- | --- |
| `parts.*.state` | `active`, `pending`, `approved_future`, `expected_automatically`, `needed`, `needs_info`, `unknown` |
| `parts.*.start.basis`, `next_step.basis` | `reported`, `estimated`, null |
| `window.phase` | `before`, `inside`, `after`. The entire window may be null |
| `route` | `sign_up_a_and_b`, `add_part_b`, `add_part_a`, `automatic`, `none_needed`, `confirm_with_social_security` |
| `next_step.id` | `sign_up`, `wait_for_decision`, `answer_request`, `confirm_start_date`, `choose_path`, `choose_medigap`, `choose_part_d`, `choose_advantage_plan`, `nothing_needed`, `confirm_with_social_security` |
| `components.*` | `chosen`, `not_needed`, `keep_existing`, `decide_later`, `unknown` |
| `finish` | null, `ab_only`, `original_plus`, `medicare_advantage`, `keep_current`, `wait` |
| `unsupported[]` | `current_work_coverage`, `window_passed`, `not_age_based`, `railroad`, `unclear_status` |

For an unheld record, next-action precedence stays as in v1: information
request, missing/conflicting approved start, keep/wait, chosen Advantage path,
application pending, future approval, needed sign-up, finish or component
decisions. An application date remains in the underlying report. Pending
reports never advance to active from elapsed time. Without any reports,
`none_needed` and `nothing_needed` with unknown parts and a null finish
are the quiet state. `expected_automatically`, `automatic` and the
`medicare_advantage` finish remain reserved. Explicit keep/wait choices
are valid finishes. Original Medicare with both parts active or pending and
resolved components yields `ab_only` when both components are `not_needed`,
otherwise `original_plus`.

## Claude adoption

1. `enrollment_flow.journey` already calls this function. The existing
   `enrollment.record` now carries `enrollment-journey-v2`; the outer
   `enrollment-view-v1` stays the same. Read the next action from
   `record.next_step.id` even if `unsupported` remains populated. For
   `confirm_start_date` during a hold, distinguish `approved_future`
   with a reported `parts.*.start.date` from a missing or conflicting date.
2. `enrollment_flow.call_notes` already reads `record.coverage_end`.
   Capture an explicit insurance end in RC11 `coverageEnd`, an explicit
   job end in RC11 `jobEnd`, or retirement in `situation.retirement`
   (`S_RETIREMENT`). For “retiring at the end of the year” or “retiring at
   EOY”, validate the phrase as the beneficiary's report and resolve its
   calendar year at capture, then retain the resolved month with the report.
   Current capture requires a literal substring for the model's `when`
   proposal, so normalize after validating it. Avoid normalizing on replay
   against a different calendar year. Keep the date reported and preserve the
   difference between an insurance end and a job or retirement date.

## Doctor candidate contract

`conversationCheck.question.candidates` is present on `field: doctor`.
The candidate ID is the existing `choices[].value`. The two office previews
per candidate come from the same matching directory rows as the legacy
labels. Matching published cities sort first before pagination, followed by
existing name relevance. An explicit city can match regardless of the
regional hint. The optional state abbreviation and ZIP narrow the place
match. Each preview carries a boolean. A city in the street or practice
name alone does not count.

```json
{
  "candidate_id": "fictional-clinician",
  "label": "Fictional Smith, MD",
  "offices": [
    {"line": "1 Example Ave", "city": "FORT MYERS", "state": "FL", "zip5": "33901", "zip4": "9311", "place_match": false}
  ]
}
```

The office question has `question.offices[]` with the same address fields
and `site_id`. The checked office has `results[].office_parts`. Without a
stated place, the boolean is false. A missing or unparseable ZIP part is
null. Existing choice values, refine, more and widen actions still apply.

Claude: update the doctor and office choice renderers in
`web-8894/conversation-checks.js` to use these structured fields when
present, format ZIP+4, label other towns as different, and keep “None of
these.” Keep the existing fallback for payloads without structured fields.
An Original Medicare check also returns
`result.original_medicare = {state, record_date}` for the closing summary.

## Closing options contract

```python
summary = closing_options.status(
    flow, guide, record,
    medigap_result=plans_price_response,
    doctor_results=current_conversation_check_results,
)
```

Call at the closing summary from the :8895 conversation, after assembling
current reported state and revalidating current-visit doctor results.
`medigap_result` is the existing exact Plans price payload from
`medigap_pilot.prices` for `medigap_profile.profile(guide)['inputs']` and
its effective date. Keep any database fetch outside the pure function. Use
`None` when unavailable. Recompute after profile corrections and pass the
current response; a different profile is rejected. The fixed Plans source
snapshot determines pricing age and date, independent of optional `today`.
Use the version field `closing-options-v1`. No model is needed.

The rule applies to Original Medicare with Medigap and reported predictable
costs (`needs.costPreference`, or the existing unambiguous `bills`
priority). The existing path resolver supplies path and state from the
reports. `intent.coveragePath` records an explicit choice and
`intent.pathStart` records a start-with preference, including `both`.
Advantage and cases outside the approved rule yield
`{"version":"closing-options-v1","options":null,"reason":"no_rule_yet"}`.
Within the rule, list the lowest regular monthly premium for each letter
with a usable rate. Ties sort by company name and then rate ID.
`company_count` counts distinct companies with usable listed rates for the
letter. `excluded_count` counts rate rows set aside by the existing
pre-2020 eligibility filter, including unresolved eligibility. It does not
remove anything from Plans. A missing input yields `missing` and
`still_needed` IDs from the existing profile. An unavailable/mismatched
price response or missing letter yields `unsupported`; any available
letter stays in the result. Use “lowest listed premium” for display. The
rate date is the source effective date.

Doctor states use published assignment for the checked office. Billing
enrollment alone, conflicting or stale evidence, and applicable or
unresolved opt-out evidence cannot supply `accepts`. Dates come from
source records, not the requested check date. Reported doctors without
current Original Medicare evidence return `unknown`. The caller must
pass only current reconciled results for the same beneficiary, not cached
results from before a correction.

Part D always has `address: true` and `named: null` in this version.
Naming one requires a current, confirmed medicine list, exact drug
identities where needed, a completed check against each applicable plan's
current drug list for the person's area and year, and a rule for choosing
among checked plans. Missing and unresolved checks stay visible.

Exact example (fictional companies, rate rows and doctor IDs):

```json
{
  "version": "closing-options-v1",
  "reason": null,
  "options": {
    "basis": {"path": "original_medigap", "path_state": "leaning", "cost_preference": "predictable", "priorities": ["bills", "doctors"]},
    "medigap": {
      "status": "ready", "still_needed": [], "excluded_count": 1,
      "first": {"letter": "G", "company": "Acme Mutual", "rate_id": "g-a", "monthly_cents": 16000, "rate_date": "2026-10-01", "company_count": 2},
      "alternative": {"letter": "N", "company": "Zeta Mutual", "rate_id": "n-z", "monthly_cents": 13000, "rate_date": "2026-10-01", "company_count": 1}
    },
    "part_d": {"address": true, "named": null, "reason": "medicines_not_checked"},
    "doctors": [
      {"id": "doctor-1", "state": "may_accept", "record_date": "2026-10-02"},
      {"id": "doctor-2", "state": "unknown", "record_date": null}
    ]
  }
}
```
