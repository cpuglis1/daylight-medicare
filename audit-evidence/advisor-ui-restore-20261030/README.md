# D86: restore the accepted chat layout in :8893

October 30, 2026 · Local UI correction · http://127.0.0.1:8893/

The owner clarified that the new variant was intended to change question flow and text while preserving :8891's accepted chat design. The attached historical review was read as reference evidence; it did not independently authorize every historical suggestion. This correction addresses D86 with D06/D08–D12/D19/D21–D24, D49/D52–D54, D64 and D73.

## What changed

- Copied the five existing :8891 stylesheets unchanged into :8893. Their hashes match the canonical incumbent files. Reused its landing composition, brand, wide chat, readable typography, compact centered progress and lower composer/utility structure.
- Restored normal conversational question type: bold 18px Atkinson Hyperlegible. Kept the revised Medicare-specific invitation and brief examples.
- Restored right-aligned user replies, including structured answers, with the submitted answer visible above the response. The complete transcript remains scrollable; older replies are no longer folded after three exchanges. Rendering appends new exchanges without replacing the existing log.
- Replaced competing form Continue/composer Send controls with one persistent Send, moving it beside the selected input as in :8891. Selection waits for Send. The same control retains the explicit confirmation/action label for reviewing reports or preparing next steps.
- Kept new hybrid forms, individual unknown/defer values, interpretation review, edit/discard, the optional employer transition task, timeline, teaching diagrams, preparation receipts/checklists, sample scope and privacy behavior. The teaching reference is inline rather than a second column. Sources remain expandable footnotes.
- Recorded the owner's correction in the requirements change log, master design, plan and scoped design/operations files.

The narrative/controller, engine lock, shared engine, model configuration, source/data acceptance and profile/storage logic are unchanged. No service restart, paid generation, source release or public deployment was needed. Existing open user tabs were not reloaded; refresh :8893 to load the restored frontend.

## Actual verification

The canonical :8891 implementation was inspected in an isolated temporary fixture on :8894; :8891 itself was not changed or restarted. The revised substantive flow was exercised on a separate :8892 fixture with temporary storage, then the real :8893 frontend was checked without paid AI. Both fixture servers were stopped after review.

| Check | Observed result |
| --- | --- |
| Existing advisor tests | All 30 pass: 23 controller tests and seven actual loopback HTTP/session/save tests using temporary databases. No new tests were introduced for the layout correction. |
| JavaScript parse | `node --check alternatives/advisor-first/web/advisor.js` passes. |
| Real desktop opening | 1280×720; 1216px main width; no horizontal overflow; body-size bold question; one Send; composer and utility bar within viewport. |
| Real phone opening | 390×844; no horizontal overflow; one Send; utility bar bottom 838px. |
| Real tablet opening | 768×1024; no horizontal overflow; one Send; utility bar bottom 1016px. |
| Explicit selection | Goal, recipient and employer choices remain unsubmitted until Send. Selected answer appears on the right. |
| Inline form/review | Preferred start April 2027 survives a Medicare explanation; Send stages the date; Make edits restores the draft; confirmation advances the conditional route. |
| Complex branch | Current-job coverage → optional transition task → whose job → grouped job/insurance end dates. March 2027 job end and unknown insurance end are reviewed separately; no insurance date was invented. |
| Supported operation | Separate named preparation confirmation produces the actual editable checklist. Unknown insurance timing remains an open check; nothing is sent or enrolled. |
| AI permission and drafts | The real service asks permission before processing an ambiguous message. Declining parks the exact draft in the tab. Local learning still works. Restore draft recovers the original text. |
| Samples/return | Five unvalidated 2027 Collier samples retain their scope; return and browsing preserve the unsent message. |
| Browser diagnostics | No error/warning console entries returned for the live walkthrough. |
| Design hook | The initial contrast finding was resolved with explicit primary/disabled button colors. Final targeted scan returns `[]`. No new detector exceptions were added. |
| Preservation | All 465 protected source files match the before-image, including both incumbent UI trees and the advisor backend. Historical customer/charge rows and store inodes are preserved. Shared ledger still has 31 charges, the same count as the prior delivery. Zero new model calls for this correction. |

See [geometry](responsive-measurements.json), [preservation](preservation.json), [targeted design scan](design-check.json), [incumbent reference](incumbent-opening.png), [regressed opening](before-opening.png), [restored desktop](restored-final.png), [phone](restored-opening-phone.png), [tablet](restored-opening-tablet.png) and [grouped phone form](grouped-form-phone.png). `before/` retains the edited frontend and document before-images. The grouped-form capture precedes the final compact-choice row CSS refinement; its field/review behavior is unchanged.

## D73 review and remaining limits

The consumer task is restored to the accepted familiar chat composition, while consequential intake, optional learning, conditional dependencies, teaching and correction remain. Coverage paths, reviewed facts, sample ordering and commercial independence are unchanged. Reported-input sufficiency still cannot supply external source acceptance or unlock recommendations. Preparation remains preparation, not verified eligibility or outside action. Saving and AI transfer retain separate permissions and the shared budget/no-retry guard.

These are local functional/visual observations, not evidence of older-adult comprehension, usability superiority or staff savings. Physical phone keyboards, screen-reader execution and consumer testing remain unperformed. Broader natural-language/model coverage and all source/eligibility/provider/drug/price/Medigap/recommendation/enrollment holds remain as recorded in the original delivery packet. No new insurance claims were researched or introduced.
