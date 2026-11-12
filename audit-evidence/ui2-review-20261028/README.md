# D79 UI2 delivery · October 28, 2026

Chris approved all five actions extracted from the 14:39 EDT review. Revision `D79-adaptive-20261028-r3` is deployed only to :8891. D49–D57, D64 independence, D73 self-service/minimal-intake/continuity, D75 isolation and the compatible ALT73/ALT74 gates remain binding.

## The five actions

1. **Contextual Send:** one persistent Send moves directly below selected choices. Typing moves that same button back beside the composer; it is never duplicated. Selection remains deliberate. The reading pane keeps Send visible on smaller screens.
2. **One typed-input surface:** ZIP, names, dates and grouped details use the bottom composer. There are no inline text fields or selects in the question area. Useful single-field enumerations become buttons. Compact dates still show a normalized preview before Send; mixed natural replies use the existing scoped AI adapter.
3. **Provider submission:** removed the competing field/draft paths and the branch requiring manual clearing of conflicting entered details. An obvious whole provider-name reply is an exact, unverified report with no AI call; questions/corrections/mixed facts still reach the language adapter. The deployed test submitted `Dr. Rivera at Example Clinic` once, advanced to prescriptions and cleared only the submitted text.
4. **Actual gating audit:** all 41 IDs retain their original question/field records, including internal checks, optional preferences and three shared-field aliases. [The coverage matrix](COVERAGE_MATRIX.md) is generated from observed HTTP traces, not from inventory presence alone. No external source/recommendation gate was released.
5. **Five personas end to end:** five main browser journeys and four additional HTTP variants exercise the cases below. Each main browser journey reached five explicitly labeled sample records and returned to its conversation.

| Persona | Browser turns before samples | Covered paths |
| --- | ---: | --- |
| P1 Current-job transition | 5 | Date precision, worker relationship, independent job/insurance ends, unknown insurance end; variant checks payer order, changed employer-size threshold and voluntary HSA report. |
| P2 COBRA transition | 6 | Reused coverage type, only missing insurance end, creditability/dependent-impact scope, unknown, volunteered move/date; variant public browsing needs only scope. |
| P3 Advantage / Medigap | 10 | Part B history, relevant episode start and prior Medigap in one parent, shared child aliases; variant keeps current supplement, ambiguous arrangement confirmation and optional preferences. |
| P4 Doctors / multiple medicines | 14 | Provider names/offices, two medicines, partial fill information, quantity units, two assistance programs, item-specific correction/staleness and defer; variant unknown strength does not become ready pricing. |
| P5 Caregiver / military / travel / budget | 20 | Person scope, actual multi-county ZIP, routine-care destination, payer-order/military reports, optional budget scope, program reports and source-held SNP/continuity contexts. |

The browser journeys used **scripted model outputs in an isolated fixture**. These outputs passed the actual strict language adapter and real HTTP/controller/report-validation layers. They isolate flow correctness and are not evidence of live-model accuracy on all five personas. Fixture message pacing uses a private virtual clock; the production rate policy is unchanged.

## Bugs exposed and fixed

- Duplicate entry paths required users to clear entered details. All typed answers now use one composer; successful submission clears the submitted text and advances.
- Multi-select assistance programs were rejected as one unsupported comma-separated choice. Multiple named positive programs now produce separate retained reports; None/decline cannot be combined with positives.
- A changed Medicare qualification basis could reuse an employer answer for the earlier threshold. The dependent employer-size report now becomes stale and is asked in its new context. This verifies report consistency, not an accepted payer-order determination.
- Confirming/rejecting an interpretation removed the server proposal but returned its stale pending ID. The response now clears it, allowing the ordinary conversation to continue.
- Initial mobile placement put the new contextual Send below the clipped reading pane. A bounded reading-pane adjustment now keeps it visible without moving the whole page.

## Evidence

- [151 targeted Python checks](test-summary.json) pass, including 12 new persona/regression checks covering nine HTTP journeys. A final focused 12-check run also passes after the conservative provider parser refinement. Test stores are temporary; no paid model transport is used.
- [All 41 matrix rows](coverage-matrix.json) have observed conversation-level coverage: **24 asked/exercised, 13 volunteered/reused, one integrity guard, three parent aliases**. These are mutually exclusive row labels, not counts of unique customer facts. A row labeled volunteered is not a claim that its source-specific missing-detail branch was activated.
- [Five browser journeys](browser-personas.json): 55 submitted persona turns, plus explicit sample/return actions, without inline fields, stuck drafts, duplicated Send controls or surfaced errors. [Phone/tablet/desktop layout checks](browser-layout.json) retain one composer and fit the app BODY to the viewport with no horizontal overflow. Physical keyboards and screen-reader execution were not tested.
- [Actual live chat](live-browser.json): one real GPT-5.4 generation handled the fictional message `I take metformin 500 mg tablets. What is Part D?`, retained the report, showed reviewed Part D teaching and continued to travel. Deterministic dates, ZIP, choices and the provider reply added zero generations. The live path reached the five labeled samples. No fictional report was saved live.
- [Live usage/status](live-verification.json) is an aggregate UTC-day snapshot, including earlier user/session calls. This task added **one settled generation**, estimated **$0.012725**; the shared cap stays $1/UTC-day with no automatic retry. The earlier alternative pricing review remains unchanged and expires November 4 at 00:00 UTC. Original :8890 pricing/configuration was not changed.
- [JavaScript syntax and four retained compatibility checks](javascript-checks.log) pass. The legacy DOM harnesses exercise their retained before-review fixture, not this renderer. The new renderer is covered by the browser journeys above.
- [Static detector](detector.log) reports no findings, but CSS/JS checks are regex-only and undercount parsed-page rules. The pre-existing `overused-font=fraunces` exception remains intentional for the approved identity; no new suppression was added.

One historical source-identity check remains explicitly excluded from the bounded suite because the relocated pinned `data-sources/release.json` / read-model package is unavailable. This is not passing source validation.

## Preservation and operations

[Read-only preservation evidence](store-preservation.json) confirms all three original and four alternative pre-existing guest rows, all pre-existing readiness rows and all **22 pre-existing AI-charge rows** remain byte-equivalent at the row level. Both guest database inodes and the shared ledger inode are retained. The additional settled charge is the authorized synthetic live check. No stores, credentials, environment, launch settings or ledger were copied/reset. All **236 captured original app/script/config files** are byte-identical. :8890 and :8891 both return HTTP 200; only the alternative source was deployed.

Source-only before-images are `runtime/backups/20261028T193038320923Z`, `20261028T193629360732Z` and `20261028T193924078461Z`. The existing sync verified the exact `gui/501/com.daylight.chat-alternative.8891` identity before each restart. [Runtime comparison](runtime-check.json) records 137 synchronized deployable files. The temporary :8892 fixture is stopped after browser testing. Before-images and [source accounting](source-after.json) preserve substantial unrelated uncommitted work.

## Remaining gaps and acceptance boundaries

- The **14 representation/evidence gaps are unchanged**; no external gap is closed. The original 41 question records, all 78 field records, 14 optional paths and named gap records remain byte-equivalent in [contract accounting](field-accounting.json).
- **RC08 event-date and RC16 history preparation still use task-level routing.** An independently accepted rule selecting the exact necessary date precision/history is not connected. Their preparation traces pass, but exact source-specific trigger necessity is not established. This is a real remaining precision gap before personal timing/Medigap-rights release.
- **RC19, RC21 and RC24 source-specific branches remain held.** No accepted candidate/qualification, provider-directory candidate or administration/device rule is connected. The tests prove volunteered reports survive and unrelated intake is suppressed; they do not claim a full accepted candidate-driven follow-up or a personal finding.
- **Model coverage is bounded.** The nine controller traces use scripted structured outputs. One real AI reply passed; exhaustive natural-language extraction, incomplete multi-item lists and all adversarial phrasings across 78 fields are not proven. Raw submitted lists remain available as unverified reports, not complete verified identity matches.
- Actual availability, benefit acceptance, payer order, enrollment timing/rights, provider fit, formulary/personal costs, SNP eligibility, Medigap rights, ranking, enrollment and a completed human referral retain their independent gates. A reported interruption never means a referral was completed. Unknown answers and sample browsing cannot release these gates.
- The previously deferred **2026/2027 sample-year mismatch** remains labeled and unchanged. No research dataset was relabeled or activated.
- Physical mobile keyboard, assistive-technology execution, sustained long-chat performance and an older-adult comprehension study remain unperformed. Existing browser annotation instrumentation can extend the outer document scroll area; the app BODY measurements are reported separately.

These are technical delivery and traceability results, not owner acceptance, independent insurance review or a measured consumer-completion improvement. Useful self-service, consequential minimal intake, inspectable decisions, independent coverage exploration and opt-in continuity are checked; their human comprehension and independent source acceptance remain separate.
