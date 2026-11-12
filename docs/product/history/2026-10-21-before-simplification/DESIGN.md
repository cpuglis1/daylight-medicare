---
name: Daylight
description: Your coverage, plain as day
colors:
  paper: "#fbf9f4"
  paper-raised: "#fffefa"
  ink: "#283b30"
  muted: "#596653"
  olive: "#40513d"
  olive-hover: "#2d422f"
  sage: "#e8eddf"
  selected-support: "#d5dfc9"
  line: "#ccd3c1"
  focus: "#91600c"
  illustrative-data: "#f2e9ce"
  choice-border: "#99a68e"
  composer-border: "#a8b19e"
  phase-border: "#8d9c80"
  ask-composer: "#f8f9f2"
  catalog-accent: "#4c5a46"
  catalog-accent-strong: "#3c4938"
  catalog-sage-border: "#b7beaa"
  white: "#fff"
typography:
  display:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "68px"
    fontWeight: 450
    lineHeight: 1.06
    letterSpacing: "-.035em"
  headline:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "48px"
    fontWeight: 450
    lineHeight: 1.1
    letterSpacing: "-.03em"
  body:
    fontFamily: "Atkinson Hyperlegible, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.5
  answer:
    fontFamily: "Atkinson Hyperlegible, Arial, sans-serif"
    fontSize: "23px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Atkinson Hyperlegible, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "7px"
  composer: "8px"
  picture-dialog: "12px"
  catalog-chip: "22px"
spacing:
  option-gap: "12px"
  phone-gutter: "20px"
  section-gap: "24px"
  tablet-gutter: "32px"
  picture-padding: "40px"
  desktop-gutter: "48px"
  workspace-gap: "86px"
  narrow-gutter: "16px"
components:
  button-primary:
    backgroundColor: "{colors.olive}"
    textColor: "{colors.paper-raised}"
    rounded: "{rounded.control}"
    padding: "13px 27px"
  button-primary-hover:
    backgroundColor: "{colors.olive-hover}"
  button-back:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "8px 0"
  button-ask:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "8px 0"
  answer-choice:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "14px 18px"
  answer-choice-selected:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "13px 17px"
  free-text-composer:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.composer}"
    padding: "13px 16px 6px"
  concept-picture:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.ink}"
    rounded: "{rounded.picture-dialog}"
    padding: "40px"
  catalog-chip:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.catalog-accent-strong}"
    rounded: "{rounded.catalog-chip}"
    padding: "9px 16px"
  catalog-chip-selected:
    backgroundColor: "{colors.catalog-accent}"
    textColor: "{colors.white}"
  plan-card:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.picture-dialog}"
    padding: "18px"
  ask-dialog:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.picture-dialog}"
    width: "466px"
---

# Design System: Daylight

## Overview

Approved reference · October 21, 2026 · Candidate02 layout and selected Option A. Preserve the warm paper, sage teaching surfaces, olive actions, readable Atkinson Hyperlegible body and Fraunces display relationship. This is a canonical record of the approved system, not a new aesthetic direction or a new slogan.

The only brand tagline is exactly **Your coverage, plain as day**. Keep the sun/name. Do not add a header kicker, secondary slogan, fabricated testimonial or decorative motion.

### Authority and scope

Use this definitive visual reference with [MASTER_DESIGN](docs/product/MASTER_DESIGN.md), [branching nodes](docs/product/BRANCHING_NODES.md), [flow contract](docs/product/flow-contract.json) and [acceptance/handoff](docs/product/ACCEPTANCE_AND_HANDOFF.md). Flow/state rules remain in the master package; styling cannot silently change them. Latest explicit owner decisions take precedence over historical centered-arrival proposals.

This documentation addresses D58's approved visual reference and supports D55/D57 and the bounded D59 implementation. It preserves D49–D54's agent-first, knowledge, stable progress, confirmed-text and planned-storage boundaries. Implementation authorization is scoped separately; this file does not approve storage, live services, source facts or production deployment.

**Key characteristics:**

- Warm, professional surfaces and meaningful photography.
- One visible task, a deliberate Continue and a growing teaching picture.
- Large readable type, explicit text labels and visible keyboard focus.
- Equal comparison emphasis and visible evidence/unknown distinctions.

### Token source and status

The frontmatter is the normative visual token record. Implemented values are extracted from [approved.css](cms-slice/apps/chat/approved.css), loaded after retained [styles.css](cms-slice/apps/chat/styles.css); font files remain self-hosted by the latter. Selected support and illustrative-data notice colors are retained from the approved reference, but are not currently emitted by those stylesheets. Their inclusion is approval evidence, not an implementation claim. The sidecar carries focus, shadow, responsive and component details that do not fit the frontmatter schema. Retained legacy styles do not supersede this approved direction.

## Colors

Warm paper supports quiet sage teaching areas and olive actions; the darker ink keeps the task readable without adding a new accent palette.

### Primary

- **Olive:** the primary Continue action, current phase and main concept block. Olive hover is the primary action's hover state.

### Secondary

- **Sage:** the arrival text surface, concept picture, local explanation and selected answer surface.
- **Selected support:** retained approved support color; not currently used by the active stylesheets.
- **Illustrative-data notice:** retained approved notice color; not currently used by the active stylesheets.
- **Focus:** a visible keyboard outline, with geometry specified under Components.

### Neutral

- **Paper / raised surface:** the page and readable control/dialog surfaces.
- **Ink / muted:** main content and secondary explanations.
- **Quiet rule:** dividers and boundaries; stronger choice/composer/phase borders distinguish interactive or current-state elements.
- **Ask composer:** the subtle help-entry surface inside the overlay.
- **Catalog accent / strong / sage border / white:** retained catalog-control colors from the incumbent stylesheet, recorded for preservation rather than as a replacement approved palette.

Use words and explicit states alongside color. A selected answer does not advance the page or establish mastery.

## Typography

**Display font:** self-hosted Fraunces at weight 450, with Georgia/serif fallbacks. **Body font:** self-hosted Atkinson Hyperlegible at weights 400/700, with Arial/sans-serif fallbacks for the approved workspace. Body, controls and numbers use the legible sans face; the retained sheet supplies tabular numerals. Preserve `/fonts/atkinson-400.woff2`, `/fonts/atkinson-700.woff2` and `/fonts/fraunces.woff2` and their SIL OFL provenance.

The frontmatter records desktop display, task headline, body, answer and label roles. The arrival display changes to 54px in the tablet range, 48px on phone and 43px at widths at or below 360px. Phone arrival line height is 1.05. Task headings are 46px in the tablet range and 42px on phone. These responsive exceptions are extracted from the approved sheet, not a replacement type scale.

Preserve generous readable line spacing and the distinction between the literal question, its reason, the answer and deeper explanation. Arrival support text is constrained to 29ch on desktop and 28ch on phone; task reason/answer/detail use a 520px maximum width. Do not shrink primary content to make all teaching fit above the fold.

## Layout

### Workspace

Use the existing 1184px container with minimum desktop gutters of 48px, tablet gutters of 32px, phone gutters of 20px and narrow gutters of 16px. Desktop task/picture columns are 1.02fr / 1fr with an 86px gap; the tablet gap is 44px. At 760px and below the layout stacks with a compact current concept close to the task; deeper reference follows. Preserve breathing room rather than replacing every content group with a card.

Common stable phases are **1 Your goal, 2 Your situation, 3 Your options, 4 Your next step**. No renumbering, mastery checkmarks or changing denominators. The four-column desktop phase track becomes two columns on phone while retaining the same labels and order.

Left: Daylight's contextual task, literal question, why asked, explicit choices and optional first-class text. One prominent Continue. Back, then Ask beneath task actions. Right: the growing Medicare picture, one concept at a time. Phone keeps a compact current concept close to the task. Local definitions remain in the picture; Ask more opens help.

### Approved arrival and asset

Retain the approved 46/54 sage text/photo composition; phone stacks actions before the image. The approved sheet uses a 47/53 split in the 761–1100px range. The hero spans at most 1440px and has a 600px desktop minimum height (560px in the tablet range).

Use Marcus Aurelius / [Pexels 6787568](https://www.pexels.com/photo/woman-smiling-at-the-camera-6787568/), copied unchanged from displayed Option A. [Pexels license](https://www.pexels.com/license/) reviewed October 21, 2026. Original 6720×4480; approved local 1400×933. Actual age is not verified; no health/customer status or endorsement is inferred. Preserve prior assets and metadata.

Desktop 1440px viewport: image 777.6×600, `object-position: 56% 50%`; phone: 390×290, `object-position: 58% 44%`. At widths at or below 360px, the approved stylesheet uses 260px image height. No retouch, generative replacement, tint, mask or crop change is implied by implementation.

Visual evidence: [desktop arrival](docs/product/visual-preview/screenshots/01-arrival-desktop.jpg), [phone arrival](docs/product/visual-preview/screenshots/04-arrival-phone.jpg), [desktop lesson/Ask](docs/product/visual-preview/screenshots/02-lesson-help-desktop.jpg), [phone lesson/Ask](docs/product/visual-preview/screenshots/05-lesson-help-phone.jpg), [desktop comparison](docs/product/visual-preview/screenshots/03-comparison-desktop.jpg), [phone comparison](docs/product/visual-preview/screenshots/06-comparison-phone.jpg). [Asset record](docs/product/visual-preview/ASSETS.md) and [provenance](docs/product/visual-preview/assets/provenance.json).

## Elevation & Depth

The approved workspace uses tonal surfaces and quiet rules. Primary actions, choices and progress carry no resting shadow. The Ask overlay and starting-profile dialog use the shared structural shadow (`0 16px 48px rgba(32,48,32,.19)`) to distinguish help from the unchanged task beneath. Scrims remain subtle: Ask uses `rgba(31,49,32,.11)` and the starting-profile dialog uses `rgba(31,49,32,.2)`. The sidecar records these exact extension values. Retained catalog plan cards use the incumbent low shadow (`0 1px 2px rgba(60,55,40,.05), 0 2px 8px rgba(60,55,40,.05)`). Preserve it within that component; do not convert all content groups into elevated cards.

## Shapes

Controls have gently rounded corners; the frontmatter records the shared control, composer and picture/dialog radii. Native phase markers remain circular. The choice's stronger selected border replaces the unselected border without changing the total padding footprint. Preserve readable DOM text and named concept pieces rather than baking labels into an image.

## Components

### Buttons and choices

The primary action is olive on a raised-paper text color, at least 54px tall, with the frontmatter's control radius and padding. It is bold, uses no resting shadow and becomes olive-hover on hover. Disabled styling is visibly reduced (`opacity: .48`). Keep one prominent Continue per guided page; answer choices are inputs.

Back and Ask are explicit text-labeled, lower-emphasis controls beneath the task action. Do not duplicate Ask in the header or lesson heading. Arrival retains a corresponding Ask entry beneath its actions. The task's Back/Ask group uses a 42px minimum control height; other help/secondary controls commonly retain at least 44px in their contexts.

Choices use a raised-paper surface, strong quiet border and generous full-area target. The selected state uses sage, a 2px olive border and bold text. Do not preselect fresh answers, click-and-advance, or hide edit/help behind gestures.

For buttons, links and fields, preserve the approved visible focus (`3px solid` focus color, `4px` outline offset). All labels and selected states remain visible in text and semantics.

### Free text

The task composer is a raised-paper, bordered surface with the composer radius. Its textarea has a 60px minimum height, vertical resize and no inner box treatment. Send/Review is explicit and separate from Continue. Proposed interpretations require confirmation; keep raw text, notes and unresolved facts. The starting-profile dialog uses the picture/dialog radius and structural overlay shadow.

### Growing Medicare picture

The sage picture canvas is a teaching area with named, interactive local pieces, not a decorative diagram. Introduce one relevant concept at a time; keep deeper explanations below the main task. Local explanations stay within the picture, with an explicit Ask more route. Preserve Show/Hide and the person's explicit presentation preference within the supported save scope. Do not expose the complete parts/routes diagram to a newcomer.

### Ask overlay

Ask is an overlay over the picture side, never a new grid column or reflow. Background inert, contained focus, no automatic keyboard when opening for reading, visible Return/Escape, exact opener/scroll/draft recovery. Single reading area, question before answer, sources and visible follow-ups. Phone sheet adapts to available height/keyboard. The approved desktop panel width is 466px; phone uses the viewport minus 24px with 12px side inset. The inherited overlay caps height relative to the available dynamic viewport.

### Comparison

Comparison retains consistent ruled dimensions, equal plan emphasis, source/unknown distinctions, no unsupported recommendation, and task actions before results. Live data remains behind existing admission gates. Retained plan cards use a raised-paper surface, quiet border, picture/dialog radius and 18px padding; catalog preference chips use their existing pill shape, selected accent and text labels. Keep catalog controls, source evidence, useful content and user-entered answers/notes; visual extraction does not approve changing result admission, ordering or behavior.

## Do's and Don'ts

### Do

- **Do** preserve the approved Candidate02 layout and exact Option A asset with its provenance, license and crop evidence.
- **Do** preserve the sun/name and the sole exact tagline **Your coverage, plain as day**.
- **Do** keep the current task, reason, compact lesson and deliberate Continue easy to find.
- **Do** preserve explicit Back, edit, help, actual answers/notes, adaptive branches and factual safeguards.
- **Do** record D IDs, nodes, state effects, checks, before-images and remaining limits for a scoped implementation.
- **Do** inspect desktop, tablet and phone behavior as part of implementation; document extraction does not establish rendered acceptance.

### Don't

- **Don't** add a header kicker, secondary slogan, fabricated testimonial, decorative motion or a new visual identity.
- **Don't** reopen the approved layout or replace the photograph without a new owner decision.
- **Don't** infer mastery, health/customer status, endorsement or personally suitable coverage from presentation or imagery.
- **Don't** remove lessons, adaptive branches, factual safeguards or catalog behavior to simplify the interface.
- **Don't** preselect answers, require age-65 arithmetic, use hidden gestures or make choices advance automatically.
- **Don't** treat styling, documentation or a test count as validation of participant comprehension, all accessibility criteria, live AI, secure guest persistence or personal insurance fit.

### Change control and limits

Owner approved layout and selected photograph; this is not validation of participant comprehension, all accessibility criteria, live AI, secure guest persistence or personal insurance fit. A scoped implementation records D IDs, nodes, state effects, checks, before-images and remaining limits. No broad visual exploration or layout replacement without a new decision. Existing factual and backend admission safeguards remain binding; no commit, push or deployment is authorized by this record.
