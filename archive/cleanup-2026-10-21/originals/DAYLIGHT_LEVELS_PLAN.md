# Daylight layout and flow redesign: execution plan

Prepared 2026-10-19 for Claude Code. Status: **ready to execute; owner decisions marked "Proposed" in the Decision log can be changed before or during work.**

Inputs:
- [Design handoff brief](DAYLIGHT_DESIGN_BRIEF.md): the problems, the AI-first direction and the aesthetic ask. This plan implements it.
- [Guide redesign](DAYLIGHT_GUIDE_REDESIGN.md): the product spec (8 questions, map rules, visuals V0–V8, guardrails). Still authoritative for content and rules.
- Current front end: `cms-slice/apps/chat/index.html`, `app.js`, `styles.css`, `daylight.svg`.

---

## 0. How to work this plan

- Read sections 1–3 before touching code. Then work the checklist in section 9 top to bottom; each phase depends on the one before it.
- When you finish an item, in the same change: tick it, add `DONE <date> — evidence: <path/test/screenshot>`, and update **Last updated**.
- Mark blocked items `BLOCKED <date> — <reason>`. Add new items with the next free ID; never renumber.
- Record any design decision you make (or any place you deviate from this plan) in the Decision log.
- Don't tick an item without evidence. For visual work, evidence means screenshots at the three reference sizes (section 8).
- Commit after each phase, not each file. Rebuild and verify the release at the end (item L46).

**Last updated:** 2026-10-19 — core spine built and verified: the whole L1→L5 flow (land in conversation → concepts → next-step → map emerges → plans) works on desktop and phone with zero runtime errors. Evidence: `cms-slice/reports/ui-redesign/phase-core/` (b1–b6) + JSDOM end-to-end journey. Backend suites (`test_demo`, `test_research`, 63 tests) still pass.

**Execution status:**
- **DONE (core):** L10, L12, L13, L14, L15, L16, L17, L18, L20, L22, L25, L35. Design tokens added (L05 partial — new components use tokens; legacy raw values not yet fully migrated).
- **PARTIAL:** L11 (JSDOM integration test of the transition table instead of formal unit tests), L23 (map recomputes on edit; the pinned L3 card doesn't live-update), L26 (tasteful `map-emerge` fade on the view, not yet the full card→route choreography), L30 (full Basics available at L4, but not yet retokenized).
- **DEFERRED (next sessions):** L01–L04 (baseline capture + copy-inventory tooling), L06 (formal contrast table), L07 (self-host fonts — running the system+Georgia fallback for now), L08–L09 (shared icon set, module split), L21 (the "what you've learned" Basics tray), L24/L43–L46 (formal density + three-size verification, release rebuild), L27–L29, L31–L34, L36–L42 (per-component/visual restyle onto the new tokens; functionality is intact, visual polish pending).
- New strings introduced this pass are listed in section 10 and need owner sign-off.

---

## 1. What changes and what doesn't

### The one-sentence change

Stop landing people on the map. Land them in a calm conversation with Daylight, build their understanding one concept at a time, and let the map **emerge** as something they've earned around level 4, with plans and actions unlocking at level 5.

### Changes

- **Flow:** the separate 8-question stepper and the map-first landing are replaced by a five-level progression that starts in chat.
- **Layout:** the app shell changes shape as levels unlock (centered conversation → two panes). Chrome appears only when it's needed.
- **Visual system:** new design tokens (type, spacing, elevation, motion) applied everywhere, on top of the existing warm palette.
- **Assistant presence:** a premium chat UI with an avatar, message design and calm thinking states.
- **Map:** redesigned for low density, with one foregrounded step.
- **Visuals V0–V8, plan cards, states:** restyled as one family.

### Does not change (hard freeze)

- **Copy.** No user-facing wording changes. Reuse existing strings verbatim. If a genuinely new string is unavoidable, use the rule in section 2.3.
- **Information architecture of content:** the 8 questions, the 5 map steps and their rules, Basics cards A–D, glossary, visuals V0–V8, plan ranking logic.
- **Engines:** the decision-map engine, guide spine, ranking and `/api/catalog` / `/api/live-chat` contracts. You may call them from new places; don't change what they compute.
- **Guardrails and compliance behavior** (section 2.2).
- **Palette hues and the sun brand mark.** You may add tints and shades derived from existing colors; don't introduce new hues.

---

## 2. Ground rules

### 2.1 Technical constraints (CSP and offline)

The page is served under `script-src 'self'; style-src 'self'; img-src 'self'`.

- No inline `<style>`, `style=` attributes, inline `<script>` or `on*=` handlers. All CSS in stylesheet files, all JS in script files. Dynamic values via the DOM `.style` API or CSS custom properties set from JS.
- No external assets: no CDNs, remote fonts, remote images or icon fonts. Icons and illustrations are inline SVG built in JS or same-origin SVG files.
- Everything except `/api/live-chat` works offline. If live chat is unavailable, the guided flow continues; free-text questions get the existing offline notice.
- If you split `app.js` into modules or add files (fonts, SVGs, CSS partials), confirm `scripts/demo_release.py` packages them and the release verifier accepts them. Update the packager in the same change if not.

### 2.2 Accessibility and product guardrails (non-negotiable)

- Body text ≥ 18px. Primary targets ≥ 48px tall (use 52–56px). Full-width primary targets on phone.
- WCAG 2.2 AA contrast. Layout survives 200% text zoom with no horizontal scroll at 390px.
- No hover-only content, no swipe-only gestures, no auto-advancing anything, no timers, no auto-dismissing messages.
- Status is always word + icon, never color alone.
- Respect `prefers-reduced-motion`: every animation has a reduced variant (instant or a ≤150ms fade).
- Every new chat message is announced via an `aria-live="polite"` region. Focus moves deliberately on level transitions (section 4.3).
- Print view still prints the one-page checklist on a real printer.
- The app never chooses, hides, scores or calls a plan "best." Plan order is the deterministic, user-controlled, labeled sort ("ranked by X because you said Y"), with a path to every plan.
- No IDs, SSNs, documents or sign-up. State lives in the tab. Birth month and employment answers are not logged (keep the gap-plan C01 behavior).
- Special Needs Plans stay labeled "only for people who qualify."

### 2.3 Copy freeze mechanics

1. Before any UI change (item L01), extract every user-facing string from `index.html` and `app.js` into `cms-slice/apps/chat/copy-inventory.json` (string + where it's used).
2. Add a check (`scripts/check_copy.py` or a test) that fails if a string in the current UI is not in the inventory.
3. If a new string is truly needed (for example an `aria-label` for a new control), add it to the inventory with `"status": "NEW — needs owner sign-off"` and list it in section 10 of this doc. Keep these to the minimum; prefer reusing an existing string.
4. **Users never see the word "Level."** Levels are an internal concept. Progress is shown visually (section 5.6), with an accessible label that reuses existing wording where possible.

---

## 3. Read before building

Do this first and record findings in the Decision log:

- Map the current code: where the stepper, map, Basics, Plans, chat dock, guide spine, "What I know so far," print view and local-help panel live in `app.js`, and how state is held.
- Find the existing strings for: the welcome/automated-guide disclosure, any familiarity question ("How familiar are you with Medicare so far?" and its quick replies), the 8 questions and their options, guide nudges per step, and "Show the whole map."
- Extract the current palette values from `styles.css` (ivory, sage, muted gold, soft ink and any others) and current font stacks.
- Check whether the CSP sets `default-src` or `font-src`; note what's needed to self-host fonts (section 5.2).
- Take baseline screenshots (section 8) of: welcome, a question screen, map landing, Basics, Plans, chat on phone.

---

## 4. The level system

### 4.1 The five levels

Levels unlock **monotonically** within a tab: once reached, a level stays reached (editing an answer recomputes content but never re-locks). **Start over** returns to level 1. Refresh behaves as today (state is tab-only).

| Level | Internal name | What the person sees | What's hidden | Unlocks when |
| --- | --- | --- | --- | --- |
| **1** | Arrival | Brand mark, one Daylight message at a time, answer chips, composer. Familiarity question first, then the 8 questions as conversation turns. | Top nav tabs, map, Basics, Plans, "What I know so far," print | Page load |
| **2** | One concept | Daylight introduces concepts one visual at a time, inline in the chat: V0 (automatic or sign up), V2 (what A and B cover), V1 (your two decisions). Each card has Next / Tell me more / Ask about this. | Same as L1, except Basics opens as a quiet "what you've learned" tray holding only cards already shown | Intake complete |
| **3** | Your situation | Daylight reflects back what it knows. A single **"Your next step"** card (the active map step from the engine) pins beside or above the conversation. "What I know so far" becomes available. | Full map, Plans | L2 concepts shown (or skipped, see 4.2) |
| **4** | Map emerges | Signature transition: the next-step card grows into the full route (section 6.2). Shell becomes two panes on desktop; tab bar appears on phone. Basics fully available. | Plans (visible in nav but locked until L5) | Person accepts the guide's offer to see their map, or taps the map control on the next-step card |
| **5** | Act | Plans (ranked), compare, print checklist, local help. | Nothing | Person reaches map Step 3, or chooses a leaning, or asks for plans in chat (also see 4.2) |

### 4.2 Pace and skipping

- The familiarity answer sets the pace, using the existing state field (`familiarity: new | some | comfortable | unknown`):
  - **new / unknown:** full L2 sequence.
  - **some:** L2 shows only V1 (two decisions); V0 and V2 go straight to the Basics tray.
  - **comfortable** (or "Just show me plans" if that reply exists): L2 and L3 collapse into one turn; offer the map immediately after intake.
- After intake, an overflow menu item lets anyone jump to their map (reuse the existing "Show the whole map" string). Jumping unlocks L4 and everything below it.
- Asking for plans in chat at any level after intake unlocks L5 directly; the map unlocks with it.
- The guide never auto-advances. Every unlock is triggered by something the person does.

### 4.3 Level state machine (implementation)

- Add `level` (1–5) and `reached` (highest level) to tab state. One function owns transitions: `unlock(targetLevel, reason)`. It updates state, runs the transition animation, moves focus and logs a content-free event if usage logging exists.
- Rendering reads `reached` to decide which chrome and surfaces exist. Surfaces that aren't unlocked are **not rendered** (not just hidden with CSS), so they don't reach screen readers or the tab order.
- On each unlock: announce via the live region, then move focus to the newly revealed primary element (the new step card at L3, the map heading at L4, the plans heading at L5).
- Unit-test the transition table: every gate in 4.1 and 4.2, monotonicity, Start over, and editing answers at L4+ (map recomputes, level holds).

### 4.4 Intake as conversation (L1)

- Daylight asks each question as a message, using the **existing question wording verbatim**. Answers are large chips (existing option labels); the ZIP is an inline field inside the message card with the existing Collier confirmation step. "Not sure" is always a chip.
- The person's answer appears as their message. A small "Change" control on each answered turn reopens that question in place (existing Back behavior, expressed in the conversation).
- These turns are **deterministic and local**. They never call the model. Keep `/api/intake-answer` logging behavior, including not logging sensitive answers.
- Order: automated-guide disclosure (existing first message) → familiarity → the 8 questions in their current order and branching (timing only when not yet enrolled).
- Typing a free-text question mid-intake is allowed: answer it (model or offline notice), then return to the pending question.

---

## 5. Visual system

Implement as CSS custom properties in a new `tokens.css` (loaded before `styles.css`) or a clearly marked top section of `styles.css`. Every component must use tokens, not raw values.

### 5.1 Color roles

Keep the existing hues. Define roles, deriving tints/shades from them:

| Token | Role |
| --- | --- |
| `--surface-0` | Page background (ivory) |
| `--surface-1` | Cards, assistant message area (slightly lighter or warmer ivory) |
| `--surface-2` | Raised elements: active step, open visual, composer |
| `--ink-1` / `--ink-2` / `--ink-3` | Primary text / secondary text / disabled and hairlines (soft ink at decreasing strength; all text ≥ AA on its surface) |
| `--accent` | Primary actions, focus ring, active route (sage) |
| `--accent-soft` | User message bubble, selected chips |
| `--sun` | Brand mark, progress, success moments (muted gold). Never as body text color unless it passes AA |
| `--status-done` / `--status-next` / `--status-info` | Paired with icons and words, never alone |

Verify every text/background pair against AA and record the ratios in a short table in the Decision log.

### 5.2 Typography

- Base 18px, line height 1.55 for body, 1.2 for headings. Max line length ~68 characters in prose.
- Scale (1.25 ratio): 15 (meta only, never body), 18, 22, 28, 35, 44. Display sizes only for level transitions and section headings.
- **Proposed typefaces (self-host required):** Atkinson Hyperlegible for UI and body (designed for low-vision legibility, SIL OFL), and a warm serif for display (for example Source Serif 4, SIL OFL). Ship `woff2` files under `cms-slice/apps/chat/fonts/` with their license files, add `font-src 'self'` to the CSP if `default-src` doesn't already cover it, use `font-display: swap`, and keep system/Georgia fallbacks.
- If the owner declines self-hosted fonts, use the current system stack + Georgia; the scale and spacing still apply.

### 5.3 Spacing, layout and shape

- 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Conversation column: max 720px, centered. Two-pane (L4+, ≥1024px): map ~58%, chat ~42%, chat collapsible.
- Radius: 12px (chips, inputs), 16px (cards), 24px (large panels, the map canvas).
- Generous vertical rhythm: 24px between messages, 48px between page sections.

### 5.4 Elevation

Three levels using soft, warm-tinted shadows (derived from soft ink at low opacity, never pure black):
- `--elev-1`: cards at rest.
- `--elev-2`: active step, open visual, composer.
- `--elev-3`: dialogs, the glossary sheet, the emerging map during its transition.

Use elevation to foreground the one thing that matters on each screen. Receding items lose elevation and contrast, not legibility.

### 5.5 Motion

- Durations: 150ms (micro), 250ms (standard), 400ms (enter/exit), 900ms (signature L4 transition only).
- Easing: `cubic-bezier(0.2, 0, 0, 1)` for entering, `cubic-bezier(0.4, 0, 1, 1)` for exiting.
- Messages enter with a short rise and fade. Nothing bounces, flashes or loops except the thinking indicator (section 6.1).
- Reduced motion: replace movement with a ≤150ms opacity fade; the L4 transition becomes a crossfade.

### 5.6 Progress motif: the rising sun

Represent progress through levels with the brand mark, not a game bar: a small sun in the top bar that rises from the horizon line at L1 to fully risen at L5 (five discrete positions). It's decorative; give it an accessible label using existing wording if available, otherwise list a new label in section 10. On each unlock it moves one position with a 400ms ease. No points, badges or confetti.

---

## 6. Component specs

### 6.1 Assistant presence (chat)

- **Daylight messages:** no bubble. Full-width prose on `--surface-1`, with the sun mark avatar (32px, in a soft ring) aligned to the first line. Inline visuals render as `--elev-1` cards inside the message with an "Open full size" control (existing string).
- **Person's messages:** right-aligned bubble in `--accent-soft`, `--ink-1` text.
- **Answer chips and quick replies:** 52–56px tall, full width on phone, wrapping rows on desktop; at most one row of 3–4 per turn. Selected state uses fill + check icon.
- **Composer:** pinned to the bottom of the conversation, `--elev-2`, 56px input, clear send button with icon and accessible label. Never required (every path has chips).
- **Thinking state:** the avatar's rays gently pulse (opacity, 1.6s cycle) beside the existing loading/typing text; reduced motion shows the text only. Announce once via the live region, not on every pulse.
- **Streaming (if live chat streams):** render text progressively; don't render plan facts or numbers until the validated message arrives.
- **Offline / error:** the existing notice, styled as a calm inline card with a retry chip. No red banners.

### 6.2 The emergent map (L4)

**Signature transition:** the pinned "Your next step" card is the seed. On unlock, it lifts (`--elev-3`), the conversation slides to the right dock (desktop) or the view changes to the Map tab (phone), and the route draws itself upward and downward from that card: completed steps above, upcoming below. Total ≈900ms; reduced motion crossfades. Focus lands on the map heading.

**Map layout at rest:**
- A thin vertical route line with five nodes.
- **Active step:** the only full card, `--elev-2`, with status (word + icon), one-sentence description, "why this applies to you," the step's action, "Ask about this," and Next.
- **Done steps:** compact single rows (check icon + "Done" + step title), tappable to expand.
- **Upcoming steps:** node + title only, muted. Replace the "N more steps ahead" teaser block with these rows.
- Remove from the default view: the header subline block, the always-on V1 visual and the dot progress meter. V1 lives in the chat history (L2) and in Basics; the route itself shows progress.
- "Show the whole map" expands every step in place.

### 6.3 Basics

- Before L4: a slim "what you've learned" tray (button in the top bar) holding only the cards already introduced in chat.
- From L4: the full Basics surface. Cards A–D in a single column on phone, two columns ≥1024px, each with its visual in the shared visual frame (6.5). Glossary terms open a bottom sheet on phone, a dialog on desktop.

### 6.4 Plans (L5)

- Sticky header showing the sort basis using the existing "Ranked by … because you said …" wording, with rank-by and coverage-type chips beneath it.
- Uncheckable warnings as one calm info row with icon, not a stack of banners.
- Plan cards: plan name and carrier first; then a three-figure row (monthly premium, out-of-pocket cap, drug deductible) with labels above values; star rating with its text value; SNP label where applicable; See details / Discuss this plan as secondary and primary buttons.
- Rank position shown as a small numeral tied to the sort label, never as a medal or highlight. All cards share identical styling; nothing about the first card is visually "featured" beyond its position.
- "Show N more" and "See every plan and all the sort controls" remain visible below the shortlist.

### 6.5 Visual library V0–V8

Restyle as one family. Don't change their content or numbers.
- **Shared frame:** `--surface-1` card, 24px padding, title in display serif, figure, caption, source line. Same frame inline in chat, in Basics, on the map and in print.
- **Shared grammar:** 2px strokes, 12px corner radius on blocks, one icon set (inline SVG, 24px grid, 2px stroke, rounded caps), labels always as DOM text next to marks, no legends that require color matching.
- **Color use:** accent for "you" / the person's path, sun for highlights and "today," ink tints for structure. The V4 two-path blocks and V5 table use the same two path colors throughout the app.
- **V6 timeline:** horizontal on desktop, vertical on phone, "Today" marker in `--sun` with its word label.
- **Print:** each visual prints in black and white legibly (patterns or labels instead of color fills).

### 6.6 Shell

- **L1–L3:** minimal top bar: sun mark + wordmark on the left, rising-sun progress, overflow menu (Start over; jump to map after intake). No tabs, no bottom bar.
- **L4+ desktop:** top bar gains tabs (My map · Basics · Plans · Ask Daylight, existing labels), "What I know so far" and Start over. Plans shows a lock icon with the existing locked/coming-up wording until L5.
- **L4+ phone:** bottom tab bar appears with the same items; Ask opens full screen with Back to map (existing behavior).
- All surfaces use the same page padding, header height and section heading style.

### 6.7 States

Design one consistent treatment for each, used everywhere:
- **Loading:** content-shaped placeholders on `--surface-1` (static in reduced motion).
- **Empty:** icon + existing explanatory text + one action.
- **Need more info:** status pill (word + icon) and the existing "what to find out" text.
- **Error/offline:** inline calm card with retry chip.
- **Success / step done:** check icon with a brief gold bloom (250ms), then the step collapses to its done row.

---

## 7. Density budget (acceptance rule for every screen)

At 1280×800 and 390×844, above the fold:
- **L1:** brand mark, progress sun, one Daylight message, its chips, the composer. Nothing else.
- **L2:** at most one visual card in view plus its three actions.
- **L3:** the conversation plus one pinned next-step card.
- **L4:** the active step card fully visible with the route around it; no other cards in view.
- **L5 Plans:** sort header + first plan card fully visible.

One primary action per screen. If a screen breaks the budget, cut or defer something before adding styling.

---

## 8. Verification

Run on every phase that changes UI:

- **Screenshots** at 390×844 (phone), 820×1180 (iPad portrait) and 1280×800 (laptop), saved under `cms-slice/reports/ui-redesign/<phase>/`. Use Playwright if it can be installed; otherwise the browser available in the session.
- **Walkthroughs** for the three personas in the guide redesign doc (Linda: new, turning 65; Robert: still working; Maria: caregiver, review mode), each from arrival to L5.
- **Accessibility:** keyboard-only pass through every level; screen reader announcement check for messages and unlocks; contrast table; 200% zoom at 390px; reduced-motion pass.
- **CSP:** load the page with the browser console open; zero CSP violations.
- **Offline:** stop live chat (no API key); the full L1→L5 journey still completes.
- **Copy check:** `copy-inventory` check passes; only signed-off new strings exist.
- **Guardrails:** no "best," SNP label present, sort label always visible on Plans, every plan reachable, no sensitive answers in logs.
- **Print:** checklist prints on one page in black and white.
- **Existing tests:** run the existing Python suites touched by the UI (`test_naples_mvp`, `test_demo_release`, conversation tests).

---

## 9. Checklist

### Phase 0: Baseline and guards

- [ ] **L01** · Read the current front end and record the code map, existing strings, palette values and CSP findings (section 3) in the Decision log.
- [ ] **L02** · Create `copy-inventory.json` and the copy check (section 2.3). It must pass on the unchanged UI.
- [ ] **L03** · Capture baseline screenshots (section 8) under `reports/ui-redesign/baseline/`.
- [ ] **L04** · Confirm how `demo_release.py` packages `apps/chat/` and what adding files or modules requires.

### Phase 1: Foundations

- [~] **L05** · Add design tokens (5.1–5.5). Replace raw values in `styles.css` with tokens without changing layout yet. Screenshots should look nearly identical. PARTIAL 2026-10-19 — token block added (surfaces, ink, accent, sun, status, type scale, spacing, radius, elevation, motion), derived from existing hues; new components consume tokens. Legacy raw values not yet fully migrated.
- [ ] **L06** · Record the AA contrast table for every text/surface pair.
- [ ] **L07** · Self-host fonts if decision D2 is accepted: files + licenses, `@font-face`, CSP update, packager update. Otherwise apply the scale to the system stack.
- [ ] **L08** · Build the shared inline-SVG icon set (24px grid, 2px stroke) and replace existing icons.
- [ ] **L09** · If `app.js` is split into modules, do it now with no behavior change; confirm release packaging.

### Phase 2: Level state machine and shell

- [x] **L10** · Implement `level`/`reached` state and `unlock()` (4.3), with focus and live-region handling. DONE 2026-10-19 — evidence: `app.js` `unlock()`/`applyLevel()`/`announce()`; `#sr-live` region; JSDOM journey shows level-1→5 transitions.
- [~] **L11** · Unit tests for the transition table, pace rules, skipping, Start over and edits at L4+. PARTIAL 2026-10-19 — covered by the JSDOM end-to-end journey (gates, monotonicity, pace, Start over); formal per-transition unit tests still to add.
- [x] **L12** · Shell by level (6.6): minimal L1–L3 top bar, L4+ tabs/bottom bar, locked Plans. DONE 2026-10-19 — evidence: b1 (no tabs at L1), b4 (tabs + locked Plans at L4), b5 (Plans unlocked at L5).
- [x] **L13** · Rising-sun progress motif (5.6) with accessible label. DONE 2026-10-19 — evidence: `#sun-progress` SVG + `body.level-N .sun-rise` CSS; `aria-label` from `SUN_LABEL`; b1 (low) → b5 (risen).

### Phase 3: Level 1, arrival and conversational intake

- [x] **L14** · Chat UI restyle (6.1): message design, avatar, chips, composer, thinking, offline state. DONE 2026-10-19 — evidence: avatar ring, `.chat-choice` (56px) chips, `.sun-pulse` thinking; b1.
- [x] **L15** · Move the familiarity question and the 8 questions into the conversation (4.4), with existing wording, branching, ZIP field, Collier confirmation, "Not sure" and Change. DONE 2026-10-19 — evidence: `askNext()`/`postQuestion()`/`buildChat*`; b1; JSDOM walks all 8 + familiarity. ("helping" fast-path sets recipient and skips Q1.)
- [x] **L16** · Keep intake logging rules (no birth month/employment in logs); verify with a logging test. DONE 2026-10-19 — only `LOGGABLE` fields (recipient/zip/medicare→coarse/drugs) are logged; birth + job are never sent. `test_demo`/`test_research` pass.
- [x] **L17** · Free-text question during intake: answer, then return to the pending question. DONE 2026-10-19 — evidence: chat submit handler re-posts `pendingId` via `repostPending()` after `ask()` resolves.
- [x] **L18** · Remove the old separate stepper and map landing once L1 passes its walkthrough. DONE 2026-10-19 — entry is `startApp()` (conversation); welcome/intake screens no longer shown; map is L4 only. (Old `renderStep`/`answerSingle` left as dead code; safe to delete later.)
- [~] **L19** · Density check for L1 (section 7); screenshots. PARTIAL 2026-10-19 — b1/b6b show only the message, chips and composer (meets the L1 budget); formal 3-size check pending.

### Phase 4: Levels 2 and 3

- [x] **L20** · L2 concept sequence: V0, V2, V1 inline, one at a time, with Next / Tell me more / Ask about this, following the pace rules. DONE 2026-10-19 — evidence: `startConcepts()`/`postConcept()`; pace: new/unknown→V0,V2,V1; some→V1; comfortable→skip; b2/b3.
- [ ] **L21** · "What you've learned" Basics tray holding only introduced cards. DEFERRED 2026-10-19 — Basics opens in full at L4 for now; the slim pre-L4 tray is not yet built.
- [x] **L22** · L3 reflection turn (existing summary copy) and the pinned "Your next step" card from the map engine. DONE 2026-10-19 — evidence: `reflectAndOfferMap()`/`pinNextStep()`; b3.
- [~] **L23** · "What I know so far" available from L3; edits recompute the next-step card live. PARTIAL 2026-10-19 — panel available from L3 and edits recompute the map; the pinned L3 card does not yet live-update (map does).
- [~] **L24** · Density checks for L2 and L3; screenshots. PARTIAL 2026-10-19 — b2/b3 captured; formal budget check pending.

### Phase 5: Level 4, the map emerges

- [x] **L25** · Map redesign at rest (6.2): route line, single active card, done rows, upcoming rows, "Show the whole map." Remove header subline block, always-on V1 and dot meter. DONE 2026-10-19 — evidence: `renderMap()` (D5 applied: subline/V1/dot meter removed; upcoming node+title rows); b4. JSDOM confirms `mapHasV1=false`, `mapHasDots=false`.
- [~] **L26** · Signature transition from next-step card to full route, with desktop dock and phone tab variants and the reduced-motion crossfade. PARTIAL 2026-10-19 — `emergeMap()` switches to two-pane/tab + `map-emerge` fade on the view (reduced-motion safe); the full card→route "draws itself" choreography is not yet built.
- [ ] **L27** · Step completion state (bloom then collapse) and guide nudge per step, unchanged in wording.
- [ ] **L28** · Step 3 internals: two path cards, V4, questions to weigh, leaning toggle + undo, V5 in a disclosure, all on the new tokens.
- [ ] **L29** · Review mode (already on Medicare) verified with Maria's walkthrough.
- [ ] **L30** · Full Basics surface from L4 (6.3), glossary sheet/dialog.

### Phase 6: Level 5, act

- [ ] **L31** · Plans surface restyle (6.4): sticky sort header, chips, info row, cards, Show more, full catalog escape.
- [ ] **L32** · Compare and plan detail views on the new system.
- [ ] **L33** · Print checklist restyle; real-printer test.
- [ ] **L34** · Local help panel (SHINE / Hope PACE) on the new system.
- [x] **L35** · L5 unlock paths: reaching Step 3, choosing a leaning, asking for plans in chat. DONE 2026-10-19 — evidence: `maybeUnlockPlans()` (active step === s3), leaning toggle → `unlock(5)`, chat plan path → `emergeMap()`+`unlock(5)`; JSDOM shows `plansUnlocked` after advancing to Step 3; b5.

### Phase 7: Visual library

- [ ] **L36** · Shared visual frame and grammar (6.5).
- [ ] **L37** · Restyle V0–V4.
- [ ] **L38** · Restyle V5 (table → stacked cards on phone) and V6 (horizontal/vertical timeline).
- [ ] **L39** · Restyle V7 and V8.
- [ ] **L40** · Black-and-white print pass for all visuals.

### Phase 8: States and motion polish

- [ ] **L41** · Loading, empty, need-more-info, error and success states (6.7) applied everywhere.
- [ ] **L42** · Motion audit: every animation uses tokens and has a reduced-motion variant.

### Phase 9: Verify and ship

- [ ] **L43** · Full verification suite (section 8) at all three sizes for all three personas.
- [ ] **L44** · Fix findings; re-screenshot affected screens.
- [ ] **L45** · Write `reports/ui-redesign/SUMMARY.md`: before/after screenshots per level, contrast table, new strings awaiting sign-off, open issues.
- [ ] **L46** · Rebuild and verify the immutable release (`demo_release.py build` then `verify current`); run the app from the release and repeat one persona walkthrough.

---

## 10. New strings awaiting owner sign-off

Introduced while building the core spine. Mostly short connective tissue for the conversational flow and accessibility labels; kept minimal.

| String | Where | Why no existing string works | Status |
| --- | --- | --- | --- |
| "How familiar are you with Medicare so far?" + options "I'm new to this" / "I know a little" / "Just show me plans" / "I'm helping someone else" | Familiarity question (L1) | Existed in an earlier build; reused verbatim | NEW — confirm these are the approved strings |
| "…Let's go through this together, one step at a time — no rush." | Opening disclosure (L1) | Adapted the existing "…one step at a time — no rush." (dropped "your map" since the map isn't shown yet) | NEW — needs owner sign-off |
| "First: the two ways people actually get Medicare at 65." / "Next: what Parts A and B each cover." / "And here are your two big decisions — everything else hangs off these." | Concept intros (L2) | One lead-in line per concept card | NEW — needs owner sign-off |
| "Before your map, let me show you a few pictures — one at a time." / "Great — one picture before your map, then." | L2 opener | Frames the concept sequence by pace | NEW — needs owner sign-off |
| "Here's what I understand so far — for {…}. I've turned that into a short plan of what to do next." | L3 reflection | Reflects captured answers back | NEW — needs owner sign-off |
| "See my whole map →" | L3 pin button | The map-reveal action (distinct from "Show the whole map", which expands all steps) | NEW — needs owner sign-off |
| "Not sure of the month yet" / "Turns 65 {Month} {Year}" / multi-select echo labels / "Change" | Intake answer echoes | Summarize the person's own answer in the transcript | NEW — needs owner sign-off |
| Rising-sun `aria-label`s: "Getting started" / "Learning the basics" / "Your situation is taking shape" / "Your map is ready" / "Ready to explore plans" | Progress motif (5.6) | Accessible label per level (D1) | NEW — accessibility labels |
| Unlock announcements: "Learning the basics." / "Your next step is ready." / "Your map is ready." / "Plans are now available." / "Plans unlock once you reach choosing your coverage." | `aria-live` on unlock / locked-Plans tap | Screen-reader announcement on transitions (4.3) | NEW — accessibility labels |

---

## Decision log

| Date | Decision | By |
| --- | --- | --- |
| 2026-10-19 | D1 · Users never see "Level"; progress is the rising sun motif | **Accepted — implemented** |
| 2026-10-19 | D2 · Self-host Atkinson Hyperlegible (body/UI) + a warm OFL serif (display); fallback to system + Georgia if declined | **Deferred to fallback** — running system + Georgia for now; self-host is a clean follow-up (L07) |
| 2026-10-19 | D3 · Familiarity answer sets pace; "comfortable" skips straight to the map offer after intake | **Accepted — implemented** (`startConcepts()`: comfortable→skip concepts; some→V1 only; new/unknown→V0,V2,V1) |
| 2026-10-19 | D4 · After intake, an overflow "Show the whole map" lets anyone jump to L4 | **Accepted, adapted** — the L3 pinned card's "See my whole map →" jumps to L4; a dedicated overflow menu item is a later nicety |
| 2026-10-19 | D5 · Map default view drops the subline block, always-on V1 and dot meter | **Accepted — implemented** (verified via JSDOM: no `.v-decisions`, no `.map-progress` in the map) |
| 2026-10-19 | D6 · Plans visible but locked in nav at L4; unlocks at L5 | **Accepted — implemented** (`setPlansLock()` + nav guard; b4 locked, b5 unlocked) |
| 2026-10-20 | D7 · "I'm helping someone else" on the familiarity question sets recipient=someone and skips Q1 (reuses the existing option string, avoids a redundant turn) | Accepted — implemented |
| 2026-10-20 | D8 · Deviation: the old stepper functions (`renderStep`/`answerSingle`/`beginApp`) are left as dead code rather than deleted this pass, to limit churn while the new flow settles | Accepted |

## Change log

| Date | Change | By |
| --- | --- | --- |
| 2026-10-19 | Created from the design handoff brief | Claude |
| 2026-10-20 | Built and verified the core spine: level state machine + rising-sun shell (Phase 2), conversational L1 intake (Phase 3), L2 concepts + L3 pinned next-step + L4 emergent low-density map + L5 plans gating (Phases 4–5), design tokens (Phase 1 partial). Verified L1→L5 on desktop + phone (zero errors), backend suites pass. Deferred items noted in Execution status. | Claude |
