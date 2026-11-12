# Core extension visual notes

October 21, 2026 · bounded ordinary-extension comparison · D60–D62, preserving D58/D59 and D49–D57.

The core additions continue the owner-approved Candidate02/Option A visual system. No replacement palette, fonts, tagline, imagery or aesthetic direction is needed. This note is staged evidence; it does not refresh or overwrite the canonical root `DESIGN.md` or `.impeccable/design.json`.

## Evidence checked

- Read project `PRODUCT.md`, `DESIGN.md`, the D60–D62 register/change entry in `DAYLIGHT_REQUIREMENTS.md`, the master authority/workspace contract, `docs/product/CORE_SERVICE.md`, and Impeccable's `reference/document.md`.
- Compared the approved preview's `01-arrival-desktop.jpg` and `02-lesson-help-desktop.jpg` with current [arrival desktop](screenshots/arrival-desktop.jpg), [tablet lesson](screenshots/lesson-tablet.jpg), [phone lesson](screenshots/lesson-phone.jpg), and [phone Ask](screenshots/ask-phone.jpg). The sage/photo arrival, sun/name, typography relationship, stable phases, task/picture arrangement and contained help remain recognizable.
- Inspected new [phone privacy](screenshots/profile-phone.jpg), [saved-version conflict review](screenshots/save-conflict-review.jpg), [live proposal review](screenshots/live-agent-confirm-desktop.jpg), and [desktop samples](screenshots/samples-desktop.jpg). Captures cover 1440px desktop, 820px tablet and 390px phone; the conflict capture is 785px wide. These are supplied rendered captures, not a new interactive test or comprehensive accessibility/usability acceptance.
- Read `guide-core.js` and the appended D60–D62 CSS, the canonical sidecar, and supplied `detector.json`. Compared current CSS with `before/cms-slice/apps/chat/approved.css`: the earlier sheet is an exact prefix; this extension is appended.

## Added components and reuse

- Save receipt/status and resume/review controls use muted text, a quiet rule and existing text-button patterns. Save, visit-only, pending and attention states are explicit words rather than color alone.
- AI progress/cancel uses the sage teaching surface; editable proposed answers use the existing raised-paper inputs, choice border and control radius. Confirmation remains distinct from a saved receipt.
- Privacy, deletion and conflict review reuse the existing starting-profile dialog, structural shadow/scrim, readable labels and olive primary action. Optional sensitive-note saving has a separate checkbox.
- Five sample records use a sage scope notice and flat ruled rows, Fraunces titles, Atkinson body text, visible provenance/unknown fit, and disabled personalized-comparison actions. This is an additional source-record presentation, not a replacement for the retained catalog cards.

Existing primitives reused include paper/raised paper, ink/muted, olive, sage and line; choice border `#99a68e`; 7px/8px control/composer corners; and the existing 17px/18px body/label roles. Added status/sample rules also reuse incumbent 14px, 16px, 27px and 29px sizes. No new visual primitive is required by this extension.

## Residual documentation and composition differences

- The supplied detector reports 32 findings: one Fraunces warning and 31 advisories. Fraunces is explicitly approved. Off-ramp sizes, error colors/radius and overlay-color notices already occur in the pre-extension sheet; the three appended-line advisories (14px, 16px, 27px) reuse those incumbent values. Overlay scrims and responsive exceptions are also documented in prose/sidecar. Do not restyle these merely to silence the detector.
- Root design documentation still describes its D59 scope and does not catalogue the new status/privacy/sample-row patterns individually. D60–D62 and `CORE_SERVICE.md` supply current implementation/authorization boundaries. A future requested documentation merge can add these patterns while retaining the approved normative tokens.
- In the inspected sample capture and `samples()` implementation, Continue/Back/Ask follow all five records. `DESIGN.md` says comparison task actions precede results, and owner guidance keeps Continue near the top. Record this as a composition gap; it was not repaired in this documentation-only pass.

No project files were changed by this pass. Live-provider, persistence, production privacy and deployment acceptance remain separate evidence and gates; screenshots alone do not establish them.

## Final correction

The implementation pass subsequently moved the existing sample Continue/Back/Ask group above records, recaptured desktop and phone, and obtained independent reviewer disposition ship. The earlier observation above is historical and resolved; see FINISH_REVIEW.md.
