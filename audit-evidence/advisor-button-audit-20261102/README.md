# Button-by-button routing and gating audit

November 2, 2026 · :8893 · D49 / D54 / D55 / D57 / D64 / D73 / D86

The owner requested a code/backend audit after selecting Medicaid left a Medicare refinement open. This audit uses the production descriptors, rendering/payload functions and controllers. It makes no browser interactions or live model calls and changes no visual styles.

## The screenshot

The Medicare family was an expanded local disclosure, separate from the selected Medicaid answer. Selecting another direct insurance choice did not close that disclosure. It was not a Medicaid-to-Medicare report conversion, but the stale display implied a relationship that the selection did not establish.

Direct insurance selections now close an unrelated open family. Unknown, Check later and Clear selection reset the local refinement and finite draft fields. Explicitly selected Medicare plus Medicaid remains supported; the fix never silently removes a reported coverage item.

| Visible insurance control | Exact meaning and route |
| --- | --- |
| Through a current job | Selects `T05=employer`; timing work asks whose job before the applicable date questions. |
| From a former job | Local disclosure only; it supplies no coverage report. |
| Retiree health plan / COBRA | Selects the exact `retiree` / `cobra` value. Timing work asks coverage end, with job end collected only when a separately requested check needs it. |
| Medicare | Local disclosure only; it does not assert enrollment or a coverage path. |
| Original Medicare / Medicare Advantage / Medigap / Separate drug plan | Selects the exact named reported coverage. Ambiguous current path combinations require clarification; no path is silently chosen. Enrollment, dates, fit and policy evidence remain separate. |
| VA, TRICARE or military coverage | Selects `military`; the particular program is a separate dependency only for the relevant requested check. |
| Medicaid | Selects `medicaid`; establishes neither Medicare enrollment nor current-job insurance. In the comparison branch, continuation is the missing location information; an obsolete employer-date target cannot return. |
| No health insurance | Selects `none` exclusively, replacing competing unsent coverage choices. |
| I don’t know / Check later | Explicit unresolved disposition for the current target, with precise field/item scope when clarification is pending. They are not a coverage choice or verification. |
| Send / Clear selection | Send submits the selected precise value(s) once; Clear selection affects only the unsent draft. Opening a family or selecting a button never sends. |

## Complete inventory and audit method

- [Question registry](question-button-registry.json): **41 approved meanings**, including three documented child aliases mapped to **38 parent questions**. It contains **88 descriptor variants**, including conditional county, work-date, prior-Medigap and medicine-fill field presentations.
- [Production payload audit](frontend-payload-audit.md): **98 distinct visible precise choices** and **16 finite field options**, select/deselect/reselect, exact payload/entity, exclusive options, unknown/defer/clear and typed-draft protection. The Python wrapper runs **192 Node checks** against the actual production functions, not a duplicate implementation.
- [Backend inventory](backend-question-audit.json) and [backend findings](backend-review.md): all **103 default constructor choice entries** through actual `NaturalConversation.turn`, plus Unknown/Check later across every parent. The constructor count includes unknown entries that the renderer replaces with the common disposition control. Consequential branches have explicit expected-question, field, entity, stale-report and held-authority assertions.
- [Utility controls](UTILITY_BUTTONS.md): opening goals, concepts, suggested questions, Sources, scroll/draft controls, settings, profile/preparation/sample views, saving/resume/delete, comparison and identity controls, retained dormant controls and the separate internal research page. Disabled/held capabilities are distinguished from broken routes.
- [Independent review](independent-review.md): rechecks lifecycle failures spanning renderer, backend and utility boundaries rather than relying only on individual handler acceptance.

## Confirmed defects corrected

| Defect | Resulting behavior |
| --- | --- |
| Unrelated insurance subchoices remained open | Changing the precise choice closes irrelevant refinement; deliberate dual coverage is retained. |
| Ambiguous current Medicare paths could remain active | Finite controls ask for clarification without changing the previous report. Typed ambiguities remain pending. Legacy envelopes remain intact while model context/comparison hold them unusable and the existing T05 question requests clarification. |
| Whole-question unknown/defer retained stale field selections | The unresolved intent is displayed alone and no stale field value is submitted. |
| Another amount submitted `daysSupply=other` to a numeric field | It focuses the one composer for an actual number; no placeholder is recorded. |
| Prefer not to say could combine with named programs | Decline/none remain exclusive finite intents; legitimate named programs can coexist. |
| Assistance-program edits displayed only one program and accumulated removed programs | The full selection is seeded and finite submission replaces that set. Typed additions remain additive. Decline/unknown do not retract earlier positive reports. |
| The three-priority maximum disappeared | Service metadata, finite selection, submission and backend validation enforce three. A longer spoken report remains retained and can be reduced one choice at a time. |
| Pending Unknown/Check later lost sibling clarifications | They resolve or leave open only the addressed fields/item; siblings and aggregate holds survive. |
| A partial clarification saved but repeated forever | Committed keys are removed incrementally from the pending target; unreported proposed values are never accepted automatically. |
| A second item's visible question could become the first item's default | The current item and missing-field target survive assessment. Fill data cannot attach to an invented or retired medicine. |
| Dependency corrections revived obsolete work/travel/medicine questions | Historical targets are checked against the current explicit dependency before reuse. |
| Research-only or unknown/deferred subject repeated who-this-is-for | Those dispositions are respected without inferring a beneficiary. |
| No doctors/no prescriptions left old details usable | Superseded names/details leave active model/comparison context while recoverable history/provenance remains. Typed and finite retractions share the same handling. |
| Starting a new list revived retired names | Only new reports enter the new active collection, with separate entity allocation and retained old history. |
| Lesson/settings/sample navigation resumed intake or erased pending queues | Trusted current server presentation and pending revisions are retained across non-report utilities. Explicit explanation settings have their own bounded action and structured provenance. |
| Pending save could replay an older sensitive permission | Checking uncertainty is read-only. A subsequent save uses current permissions and current reports. |
| Delete/resume left stale owner or request tokens | Subsequent actions bind to the current session; uncertain deletion is checked without automatic destructive retries. Reports and drafts remain local, and old session RAM is not migrated. |

## Verification and activation

- [Final full regression suite](tests-final.log): **577 Python tests passed in 92.271 seconds**, including the production-JavaScript wrappers. The separate payload matrix contains 192 nested Node checks; those checks are not another 192 Python tests. The suite covers the current identity/comparison additions as well as this button audit.
- The backend-specific increment passed 25 new tests, including every constructor choice and parent disposition, precise queue progression, retractions, ambiguity and legacy holds. Utility-specific tests passed 11 backend checks and a Python wrapper for 13 JavaScript utility checks. Earlier logs retain their actual narrower counts.
- [Preservation](preservation.json): all stylesheets and the engine-lock file are unchanged from the start of this audit; all **58 pinned shared-engine files** still match their retained hashes. No browser walkthrough was performed, as requested. Production functions were executed directly through the deterministic code/backend harnesses.
- [Activation](activation.json): restarted only the existing :8893 job. Final index, JavaScript and adapter CSS each return HTTP 200 and match workspace bytes. Health reports GPT-5.4 available with automatic retries disabled. Backend/source hashes are recorded alongside the served assets. No guest-store migration, live-profile deletion, budget change or AI request occurred.
- **Live model calls: 0. Browser actions: 0.** Controlled transports and synthetic temporary fixtures supplied all model-shaped setup responses. No real-model behavior or consumer approval is inferred from these checks.

The restart clears old temporary visit memory and signed continuations. Refresh [8893](http://127.0.0.1:8893/) for a new test; copy unsent text first. Existing saved reports remain available through the existing deliberate resume control. The user-owned tab was not reloaded by the audit.

## Preservation and limits

The visual shell, all stylesheets, validated reveal/typing animation, one composer, Sources, drafts, approved question meanings, budget/model settings, versioned Send permission and separate saving remain. Protected :8890/:8891, pinned shared-engine files, guest-store schemas, sealed evidence and source/recommendation release gates are not changed.

This is a deterministic code/backend audit of every offered control definition and selected consequential state transitions. It is not an exhaustive test of every possible sequence, a beneficiary comprehension study or evidence of live-model conversation quality. The model can still select among permitted next moves on a deliberate Send; no provider calls were used to observe that behavior here. The exact source, personal-method and output gates remain independently held.

Deleting the saved guest session intentionally revokes its old authority and bounded raw-conversation/agenda memory. Current browser reports/drafts and a paused screen can remain local; this does not migrate the old private server dialogue to a new guest. No real saved profile was deleted in the audit.
