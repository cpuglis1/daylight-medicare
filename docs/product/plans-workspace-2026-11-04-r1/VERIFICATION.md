# Design and reference verification

November 4, 2026 · Work is limited to this design packet and additive owner-requirement records.

## Executed checks

- Existing profile adapter: **16 tests pass**, using `PYTHONPATH=alternatives/advisor-first:alternatives/chat-first/cms-slice/scripts python3 -B -m unittest discover -s alternatives/advisor-first/tests -p test_comparison_profile.py`. The first attempt omitted the shared import path and did not run; the corrected invocation passed.
- New fictional heuristic: **12 tests pass**, covering order changes, confirmation invalidation, unknown contenders, conflicts, fewer-than-three, ties crossing third, scope mismatches, real-ID rejection, economic-field rejection, invalid numeric data, duplicate IDs and input nonmutation.
- Exact r13 replay: `python3 -B docs/product/recommendation-scope-2026-11-04-r13/build_examples.py --check` passes with 69/47/42/42 numeric examples and 3/25/30/30 holds.
- Desktop design inspection at 1440×1000 and the actual 1280×720 viewport; tablet at 834×1112; phone at 390×844 and 320×740. Checked desktop/phone DOM overflow returned false. Local fonts loaded.
- Design interactions exercised: browse all 72 fictional records, exact-ID search reaching the 72nd record, two-plan comparison, field definition, Ask-about prompt staging, chat close/reopen retaining the draft and field context, tablet drawer, phone full-screen chat and held-recommendation state.

Screenshots are in [screenshots](screenshots/). They are design evidence with fictional data, not captures of released consumer results. The local study uses an isolated static server on port 8914; no :8893 runtime source or service configuration changed.

## Design hook triage

The primary-button hover inherited a pale background while retaining light text; it now retains the approved dark olive hover and light text. The local font-family alias was renamed to the exact **Atkinson Hyperlegible** name from DESIGN.md. The subsequent detector output had no low-contrast or font-family finding.

The cream-palette warning is an intentional, owner-confirmed brand choice. A file-scoped ignore records the existing `#fbf9f4` paper token; no global rule/file suppression was added. The preview-state control’s extra border color/radius were brought back to the established palette and 7px radius. The layout study’s new type sizes remain explicit design advisories for this new surface. The scrim is already specified in DESIGN.md. The documenter refreshed only the design sidecar’s source metadata, narrative and scope descriptions from existing DESIGN.md; all component HTML/CSS and root DESIGN.md bytes were preserved. [Design-system review and scoped differences](DESIGN_REVIEW.md).

## Independent design review

An Impeccable finish reviewer inspected the specification, reference code and required captures. Its initial **fix** verdict named three material study defects: repeated priority changes removed a required DOM label; the hidden catalog query incorrectly filtered recommendations; and the 1280×720 chat left no answer passage visible.

The corrections preserve a stable priority label, apply search only to All plans, and compact the short-height desktop chat header/composer. Browser verification exercised three priority changes (ending with C, A, D under medical-limit-first), then searched the 72nd fictional record and returned to three recommendations. The revised 1280×720 capture was made at scrollY 0 and shows the answer passage with the complete composer; desktop/tablet/phone were recaptured.

The reviewer's final disposition is **ship — design proposal scope**, with all three named findings scored resolved. This is not owner design acceptance, Medicare review, or permission to activate real recommendations.

## Limits

The HTML is a design study, not a production frontend. It uses 72 fictional records; its profile review, chat text and checks are illustrative. The context button shows the attached plan/field without calling a model. Some specified production behaviors (full ten-field detail, real evidence, dynamic visible-card tracking, filter panel, hover-only preview, server confirmation, check execution, stale-result handling and live AI) are defined in SPEC.md rather than implemented here. The reference Python policy refuses real IDs and has no acceptance or source loader.

No paid model conversation, consumer usability study, screen-reader certification, actual recommendation, source-use acceptance, outside sharing, intentional guest-record edit, commit, push or production activation occurred. The existing advisor was opened in a fresh browser session for visual inspection; no personal answers were entered. Independent Medicare review and owner assessment of conversation quality remain required for the actual product.

## Replay

```sh
python3 -B -m unittest discover -s docs/product/plans-workspace-2026-11-04-r1 -p test_reference_recommender.py
python3 -B docs/product/plans-workspace-2026-11-04-r1/reference_recommender.py
```
