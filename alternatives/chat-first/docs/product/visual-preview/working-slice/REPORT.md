# First working slice — October 21, 2026

The approved Candidate02 layout and selected Option A are implemented in the active frontend. This completes the bounded guide-entry and first-lesson deliverable, not the full agent, backend guest profile, comparison dashboard or production launch.

- [Open working guide](http://127.0.0.1:8880/)
- [Browser review and screenshots](http://127.0.0.1:8897/working-slice/)
- [Machine-readable evidence](evidence.json)
- [Scoped patch against preserved uncommitted originals](scoped-existing-files.patch)

## What changed

D58–D59 finalize root DESIGN.md, retain the sun/name and exact tagline “Your coverage, plain as day”, and copy the selected Pexels 6787568 asset unchanged with provenance. D50–D52 add voluntary knowledge and free-text proposals, confirmed reports with raw words/provenance, stable four-phase progress, separate unknown/skipped states, and no automatic advancement. The state module allows only reviewed starting fields; text cannot invent enrollment, insurance rules or tool commands. D55 adds first concepts in order, local definitions, picture visibility and Ask overlay with preserved return state. D49 is a partial local fallback foundation, not completed live agent orchestration.

Nodes delivered: A01 goal; A02 recipient; A02B optional wording; A03 knowledge; A04 own words; A05 truthful unavailable-saving/visit choice; X01 interpretation review/edit/confirmation; L00 Medicare; L01 learning intent; L02 Part A; L03 Part B; L04 Original Medicare; L05 drugs; F00 useful learning summary. O00/C00 hand off to existing comparison and personal-context routes. Existing source content, checklists, catalog safeguards and user notes remain in the original app. Goal edits invalidate old comparisons without discarding independent entries. Recipient changes on a populated guide are guarded rather than mixing people.

## Verification

- **92 frontend tests passed**, including the original 61 and 31 new state/branch checks. [Log](frontend-tests.log).
- **201 Python tests passed** on the approved run with local HTTP fixture binding. The first restricted run failed to bind loopback servers; that environmental failure was resolved for the rerun. [Log](python-tests.log).
- JS syntax passed for the three modules. No source/data acceptance gate changed.
- Chrome walkthroughs covered desktop 1440×1000, phone 390×844, tablet 820×1180, narrow 320×720 and short desktop 1501×708. Measured page widths matched viewport widths.
- Multi-fact text proposed three editable details, remained uncommitted before confirmation, stayed on its receipt, then skipped duplicate questions. Back retained the exact original words and confirmed values. A recovery defect in proposal history was fixed and retested. The fresh reviewer also found a consumed teaching queue; next lessons now resolve deterministically from the current node. Repeated Back/Continue was retested through Part A, Part B, Original Medicare and the comparison handoff.
- Beginner picture showed only Medicare, then Part A, then Part B. No enrollment inferred. Experienced comparison kept familiarity separate and reached the retained category screen with picture collapsed.
- Ask preserved task width/position, used inert background and contained keyboard focus, did not focus the composer on reading entry, and restored opener, scroll and both drafts. Send→Tab returned to the close control. Sources and unavailable-live status remained visible.
- One Impeccable detector warning concerns approved Fraunces. Retaining the owner-approved font is intentional; no detector settings were weakened. [Fresh finish review](FINISH_REVIEW.md) found one material Back/Continue issue; its verdict pass scored that named fix resolved with disposition **ship**. Canonical root DESIGN.md and its nine-component sidecar are installed.

## Boundaries and remaining work

The running link is guide-only frontend mode. The existing backend reports **validation pending** and its data admission gate remains intact. Real catalog comparisons and live replies are unavailable at this link. No live AI response or paid service was called or verified. The explicit local interpreter only proposes allowlisted starting details; the full agent orchestrator remains a later slice.

Secure backend guest profiles/resume are not connected. The interface says this visit only and does not claim a server save. Exact retention, logging, vendor and guest-security policy still needs its planned implementation/review. Legacy route handoffs retain prior UI and need their own bounded migration. Physical mobile keyboards, screen-reader speech, full accessibility conformance and user comprehension have not been validated; COGA is supplemental guidance, not certification.

No commit, push, deployment, private-profile collection or outbound communication occurred. Before-images match the recorded hashes under docs/product/history/2026-10-21-before-first-working-slice. Existing styles.css is byte-identical to its pre-slice state. New code is isolated in approved.css, flow-state.js and first-slice.js with targeted index/app hooks. Substantial unrelated work remains untouched.
