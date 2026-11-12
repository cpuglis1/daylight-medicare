# Daylight visual preview · candidate 01

**For owner aesthetic approval. Isolated prototype; the working app is unchanged.**

Open the [clickable preview](http://127.0.0.1:8897/) or [six-view screenshot gallery](http://127.0.0.1:8897/review.html). The local server must be running. The preview has no remote model, data service, storage, enrollment or contact integration.

## Review the three sample states

| Screen | Clickable state | Desktop capture | Phone capture |
|---|---|---|---|
| Arrival | [Open arrival](http://127.0.0.1:8897/?screen=arrival) | [Desktop](screenshots/01-arrival-desktop.jpg) | [Phone](screenshots/04-arrival-phone.jpg) |
| Beginner lesson + Ask | [Open lesson with Ask](http://127.0.0.1:8897/?screen=lesson&help=1) | [Desktop](screenshots/02-lesson-help-desktop.jpg) | [Phone](screenshots/05-lesson-help-phone.jpg) |
| Comparison | [Open comparison](http://127.0.0.1:8897/?screen=compare) | [Desktop](screenshots/03-comparison-desktop.jpg) | [Phone](screenshots/06-comparison-phone.jpg) |

Additional evidence: closed lesson [desktop](screenshots/02a-lesson-desktop.jpg), [phone](screenshots/05a-lesson-phone.jpg), and [local phone definition](screenshots/07-local-explanation-phone.jpg). Captures use 1440×1000 and 390×844 browser viewports; most pages are captured at full document height. Ask captures show the viewport and fixed overlay.

## What to try

- Use the preview navigation to inspect independent states. Get started and the experienced shortcut demonstrate visual entry, not a complete onboarding route.
- In the lesson, Continue introduces Part A, then Part B. Back reverses that demonstration. I know this takes the same voluntary shortcut. Hide/Show retains the concept state.
- Open a named picture piece for its local explanation. Ask more opens Ask Daylight. Close/Return or Escape restores the task; the task draft and unsent help draft remain while this page is open.
- In comparison, search and sort the three invented fixtures, save two candidates, and compare saved candidates. No selection produces a recommendation. Continue opens a sample verification-next-step explanation.
- Type only sample text. Replies are scripted. Reloading resets this local preview; it does not demonstrate the future backend guest profile.

## Three owner review questions

1. Does this combination of photography, editorial type, warmth and restraint feel like Daylight?
2. Does the lesson feel like an agent helping you understand, and does Ask feel comfortably connected to the picture?
3. Is the comparison easy to scan without appearing to recommend an unchecked plan?

Approval here selects an aesthetic reference. It does not approve production readiness, clinical/insurance claims, privacy policy, live data, or every journey branch. Requested visual changes should preserve the master flow and factual boundaries.

## Files and boundaries

[Candidate visual guide](CANDIDATE_VISUAL_GUIDE.md), [photo origins/license record](ASSETS.md), [review and verification](REVIEW.md), [master specification](../MASTER_DESIGN.md).

No root DESIGN.md or Impeccable configuration is changed. This folder is the complete preview package. No application build, runtime file, user profile or data fixture outside it is changed. No commit or push is made.

To reopen later from the repository:

```sh
python3 -m http.server 8897 --bind 127.0.0.1 --directory /Users/cep4u/daylight/docs/product/visual-preview
```

This serves only on the local computer. Stop that process before starting another server on port 8897. It is a review server, not deployment.
