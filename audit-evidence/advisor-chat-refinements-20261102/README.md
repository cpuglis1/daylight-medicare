# Chat refinements and timing selection

November 2, 2026 · D49 / D54 / D55 / D57 / D86 · :8893 only

The owner requested correcting an ASAP selection that remained selected while typing a month/year, moving the OpenAI notice into Privacy & saving, showing assistant-side typing dots, growing the composer with a longer draft, and replacing guide dropdowns with a coherent display. The owner confirmed **contextual inline visuals**. Sources should retain their existing expandable treatment.

## Implemented

**Unsent choice versus typed answer.** Send already prioritized a nonempty typed message; the old UI retained the unsent choice highlight. Nonempty typing now clears the current unsent choice, finite fields, unknown/defer and local refinement state without deleting the draft or changing the profile. Send moves beside the text being submitted. Answer buttons cannot silently compete with an existing typed draft: they leave it intact and explain that it will be sent. An empty composer retains normal deliberate finite-answer Send behavior. Typing/selection never makes an AI request.

**Previously submitted ASAP.** An explicit, validated beneficiary/intended month and year can refine the open-ended soonest preference without another confirmation. The old revision remains in provenance. Uncertain dates still clarify; a new conflicting exact date retains the existing correction guard. Birthday, current insurance end, desired start and actual enrollment remain distinct. Seven new backend regressions cover these boundaries. The interpreter prompt describes this distinction; no stored conversational reply was added.

**Composer and pending state.** The textarea begins at 80px on desktop/tablet and 76px on phone. It expands and shrinks with the draft, capped at 30% of the visible viewport or 240px, then scrolls internally. The flex reading area yields space while preserving a reader's position when they are above the end. The visible duplicate entry label and empty disclosure/tools row no longer consume space; the accessible label remains.

While an AI Send is pending, an ephemeral submitted-user bubble and three dots appear in the reading pane. The dots are decorative to assistive technology; the existing single status region announces that Daylight is preparing a reply without occupying a bottom row. Reduced motion uses static dots. Completion/error removes pending UI, and a newer unsent draft stays intact. This is pending feedback, not raw model streaming; the existing validated word reveal remains.

**Guide and Sources.** A compact inline visual belongs to the assistant explanation that introduced it. Current-turn reviewed concept IDs determine the visual; historical `learningSeen` no longer leaves two paths under unrelated COBRA/timing questions. Existing concept names still open their reviewed explanations. Parts/path content is retained, with columns on wider screens and a stack on phone. A final reported timeline requires relevant current date teaching, no open/pending intake and at least two known reports; its reported/not-verified caption remains. Guides use no dropdown. Sources remain native expandable footnotes, merged and URL-deduplicated at the end of the full answer, with the existing HTTPS-only filtering.

**Privacy.** “Send uses OpenAI” and the full transfer explanation are now inside Privacy & saving. This placement change is explicitly authorized by the November 2 instruction. Versioned Send permission, relevant-context scope, no transfer while typing, optional saving, sensitive saving and retention behavior are unchanged. No extra consent dialog, questionnaire, model stage or persistent transcript was added.

## Verification and activation

- [Full suite](tests.log): **481 Python tests passed** in 45.088 seconds, including the existing Node wrappers. The separate Node run passed **75 checks**; these are nested checks, not another 75 Python tests.
- After the final CSS containment refinement, [the presentation wrapper](final-presentation-check.log) passed again. Browser inspection found that absolute screen-reader reveal spans could escape the reading area's containing block and create outer-page scrolling. Anchoring them in the reading area keeps the word reveal/accessibility content while preventing focus from pulling the whole page.
- Mocked disposable browser visits verified selecting ASAP, typing “December 2026,” clearing the pressed state and retaining the exact typed draft. A delayed fixture verified three dots, the single accessible pending status and cleanup. No existing customer visit was submitted or changed.
- A longer desktop draft grew the textarea from 80px to 216px at a 720px viewport; the reading pane yielded the same space. Privacy opened with the OpenAI explanation first; closing it preserved an unsent draft.
- [Responsive measurements](browser-checks.json) record desktop 1280×720, tablet 768×1024 and phone 390×844. Body width matches viewport width; document height matches viewport height and outer scroll stays zero in each final check. Phone concepts stack; wider concepts remain adjacent. The guide contains no dropdown and one Sources footer remains. These are browser checks, not physical-device keyboard or assistive-technology certification.
- [Activation](activation.json): restarted only the existing :8893 job, retaining its infrastructure virtualenv and `--local-research`. All three served UI files return 200 and match the final workspace bytes; the configured model remains available. Existing saved guest records, other variants and the shared ledger were not migrated/reset.
- **Paid AI calls for this change: 0.** Preview responses were explicitly mocked; temporary databases stayed separate. No credit purchase, budget change or hidden retry occurred.

| Browser evidence | Capture |
| --- | --- |
| Typed date clears the unsent ASAP highlight | [typed-date.png](typed-date.png) |
| Three assistant-side dots during a simulated wait | [typing-desktop.png](typing-desktop.png) |
| Expanded composer | [composer-expanded.png](composer-expanded.png) |
| Contextual paths, desktop | [guide-desktop.png](guide-desktop.png) |
| Contextual paths, tablet | [guide-tablet.png](guide-tablet.png) |
| Contextual paths, phone | [guide-phone.png](guide-phone.png) |
| OpenAI disclosure inside privacy | [privacy-phone.png](privacy-phone.png) |

The first three captures predate the final reading-area containment refinement; they prove the specific input/pending/resize states, not the final overall layout. Final responsive guide captures include that refinement.

## Preservation and limits

Before-images retain the three changed UI assets. The before/after inventories show only the expected adapter stylesheet change among CSS files, with the engine lock unchanged. The incumbent brand, typography, greeting/reveal, one composer, history, unknown/defer, Sources, final review, source/recommendation gates and protected :8890/:8891 remain. The change improves consequential intake and permissioned continuity without changing economic independence or source authority. Technical tests do not establish consumer comprehension or recommendation readiness.

The separately reported PCP-submission HTTP 500 remains a distinct unresolved incident. These timing/UI checks do not identify its cause or claim it fixed. The existing value-free controller diagnostic is retained; no raw dialogue/profile/exception message logging was introduced.

Reload :8893 to load the new frontend; copy any unsent text before reloading. The user-owned browser tab was not reloaded by this verification.
