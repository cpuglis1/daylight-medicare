# D130: Medigap uses the shared chat profile

Implemented and activated locally on November 10, 2026 (America/New_York).
This follows the owner's request for automatic age/sex/tobacco reuse, immediate
price updates, missing-only questions, clear purpose and no unrelated app changes.

## Requirements and behavior

Addresses D130 and the retained D49/D54/D64/D86/D97/D129 requirements:
conversational capture, optional sensitive saving, independence, the common
question framework, free structured Plans answers and bounded source-price display.
Affected capabilities: CAP-02 profile and CAP-06 data integration.

- Chat can capture `MG_AGE`, `MG_SEX` and `MG_TOBACCO` in the same message as
  other reports. They are three local pricing meanings alongside the unchanged
  original 41, not changes to the pinned engine or its inventory.
- New fields are `medigap.ageOn20261110`, `medigap.pricingSex` and
  `medigap.tobaccoCategory`. Existing ZIP and sufficiently precise birthday
  reports are reused. A November birthday without enough day precision does not
  establish age on November 10. A current age on a later date is not silently
  substituted for the dated cache age.
- Questions are conditional on Medigap pricing. They explain the price date,
  source sex categories and tobacco categories. Unknown/deferred answers remain
  open; the question is not automatically repeated. Helper wording explicitly
  asks about the person receiving coverage.
- Supporting words, beneficiary scope, uncertainty, conflicts and corrections
  pass through the existing capture/provenance framework. Names, pronouns,
  gender identity and smoking-only/cessation statements do not establish a
  pricing category. No new live model stage was introduced.
- The initial state, resumed state and subsequent turns expose the same derived
  pricing profile. The Medigap tab automatically reads prices when that profile
  is complete. Corrections clear stale prices/comparisons and discard delayed
  responses; unrelated rerenders do not trigger repeated lookups. Failed reads
  retain answers and have a deliberate retry.
- Missing details entered on Plans use the existing free `plans_filter` path,
  updating the shared profile. New details are omitted from saved records unless
  sensitive saving is selected. Previously saved sensitive details enter AI
  context only under the existing permission and relevant Medigap scope. Rates
  never enter saved profiles or AI context.
- ZIPs 34101–34108, ages 65–74 and the November 10, 2026 date remain exact.
  Age 75+ removes prices and shows the unsupported message without requesting
  more pricing details. No nearby profile, estimated price or eligibility finding.

The existing MA/Part D behavior, cards, filters, comparison, source conditions,
CSG build and acquisition pause are preserved. Local access roles/schema are
unchanged. No hosted deployment or source/method acceptance is implied.

## Verification actually run

All data and conversation inputs in tests/previews were fictional. No paid probes
or live conversation tests were run. HTTP tests needed sandbox approval only for
temporary localhost listeners and disposable stores.

| Check | Command / evidence | Result |
| --- | --- | --- |
| Medigap source endpoint, chat/profile, helper, corrections, initial load, save permissions, stale-state rejection | `infrastructure/daylight-data/.venv/bin/python -m unittest discover -s alternatives/advisor-first/tests -p 'test_medigap*.py' -q` · [log](medigap-tests.log) | 18 passed |
| Automatic UI queries, missing-only input, delayed results, unknowns, age 75+, retry, comparison and existing handoff | `node --test tests/test_medigap_view.js tests/test_plans_handoff.js` from advisor-first · [log](frontend-tests.log) | 9 passed |
| Existing conversation, interpreter and state regression suite | `python3 -m unittest discover -s tests -p 'test_natural*.py' -q` from advisor-first · [log](natural-regression.log) | 214 passed; one pre-existing failure below |
| Existing Plans profile filters | `python3 -m unittest discover -s tests -p test_plans_filters.py -q` · [log](plans-filter-regression.log) | 4 passed |
| Existing visit-memory controls | `python3 -m unittest discover -s tests -p test_advisor_memory.py -q` · [log](memory-tests.log) | 12 passed |
| Existing HTTP/session/save/privacy behavior | `infrastructure/daylight-data/.venv/bin/python -m unittest discover -s alternatives/advisor-first/tests -p test_http.py -q` · [log](http-regression.log) | 12 passed |
| Real cache, read-only, two fictional boundary profiles | [receipt](live-cache-read-verification.json) | 34101/65/Female/Non-Tobacco: 178 rates; 34108/74/Male/Tobacco User: 166 rates; exact D128 build |
| Protected source and existing stores/budget | [before](before.json), [runtime before](runtime-before.json), [runtime after](runtime-after.json), [verification](verification.json) | 392 protected hashes unchanged; profile tables and AI ledger hashes unchanged; zero paid calls |

The original D129 all-320-profile/55,040-rate display parity receipt remains
unchanged. This task did not modify the rate projection/repository or repeat
acquisition.

The existing failing test is
`test_pending_ambiguity_does_not_leak_to_another_visit_with_matching_versions`.
Its setup expects two read-concept actions to produce record revision 2, while
the current original code produces revision 0. It fails identically when loading
the pre-task `natural_flow.py`; see [baseline reproduction](baseline-regression-check.log).
The failure is recorded and left outside this change, not treated as passing.

## Browser observations

Used the actual app UI over [a temporary fictional backend](preview.py), with
no real provider transport or user stores. Inspected 1280×900 desktop,
768×1024 tablet and 390×844 phone. No document-level horizontal overflow at
those widths. New fields retained native labels, visible keyboard focus,
unknown/defer controls and purpose text. No browser console errors were observed.

- A missing tobacco answer entered in chat populated the Medigap profile and
  fetched prices immediately on opening the tab.
- A landing-page entry showed the missing question without requiring a prior
  chat turn. A Plans answer updated the same profile and loaded prices.
- Sex and age edits refreshed the displayed matching profile. Age 75 removed
  rates/questions; correcting to 74 restored prices automatically.
- Editing retained the Plans navigation. The helper's age question named the
  coverage recipient and fit the phone viewport.

Screenshots: [desktop chat question](screenshots/desktop-chat-question.jpg),
[desktop prices](screenshots/desktop-final.jpg),
[tablet missing question](screenshots/tablet-missing-tobacco.jpg),
[phone 75+](screenshots/phone-75-unsupported.jpg),
[phone helper question](screenshots/phone-helper-question.jpg).
Prices in screenshots are clearly labeled fictional test-company values.
Temporary tabs/listeners were closed and viewport overrides reset.

## Activation and limits

The existing launchd :8893 service was restarted with the same
`--local-research --identity-research` configuration after checks. :8894's proxy
and the protected ports/stores were retained. [Runtime after](runtime-after.json)
records the final process start, configuration and store/budget hashes.
Before/after code copies are retained privately under
`infrastructure/daylight-data/.state/csg-medigap/2026-11-10-chat-profile-r1/`;
[the task diff](change.diff) and [source hashes](source-hashes.json) identify this change.

Technical verification does not establish conversational quality under real
models, owner approval of every wording, participant comprehension, independent
source/method acceptance or a binding insurance quote. Those remain separate.
