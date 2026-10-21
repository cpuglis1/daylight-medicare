# Daylight aesthetic plan: warm, helpful, trustworthy AI for older adults

Prepared 2026-10-20 for Claude Code. Status: **core implemented and verified (2026-10-20).**

**Last updated:** 2026-10-20 — the aesthetic layer is live on top of the levels workflow: the Daylight character (sun + reading glasses) with 7 expressions and 4 sizes; self-hosted Atkinson Hyperlegible + Fraunces; illustration palette + paper grain; printed-material vs speech surfaces; stamps / reviewed seals / source tags; spot illustrations; the working card; the folded-paper map; the serious plans room; the notepad. Verified L1→L5 on desktop + phone with **zero runtime errors** and no CSP violations; **63 backend tests pass**. Evidence: `cms-slice/reports/ui-aesthetic/phase-core/` (d1–d7).

**Execution status:**
- **DONE:** A01 (character A), A02 (7 expressions), A03 (4 sizes), A06 (paper grain), A07 (illustration palette), A08 (self-hosted fonts + CSP + demo.py serving), A09 (shape/texture/depth + printed/speech classes), A12 (arrival + hero), A13 (working card), A16 (notepad lined paper), A19 (plans serious room), A22 (character `aria-hidden`, automated-guide chip visible, stamps are word+icon), A23 (no character/illustration on any plan surface; identical plan cards).
- **PARTIAL:** A04 (8 spot illustrations built; broader icon set still reuses existing glyphs), A14 (message design + reviewed-in-speech done; paragraph-by-paragraph paced reveal not yet), A15 (seal+source tag on Basics, field stamps on plans, "Done" stamp on map; not yet on every fact), A17 (map paper + dashed trail + done stamps + pencil-sketch upcoming done; literal per-step landmark illustrations, faceless sun "you are here" pin, and the unfold animation still to add), A18 (Basics booklet done; V0–V8 share the palette but aren't each re-illustrated), A20 (bloom CSS ready; checklist corner art not added), A21 (reduced-motion global in place; formal audit pending).
- **DEFERRED:** A05 (3 people illustrations), A10–A11 (static A/B/C test screens + the five-person test — a human step; built on direction A per D1), A24 (formal SUMMARY.md). For a distributed immutable release, add the fonts/art to `demo_release.py` packaging and ship full upstream OFL.txt files (the running workspace demo already serves them via `demo.py`).
- New strings introduced are in section 11.

**Scope: aesthetics only.** This plan changes how Daylight looks and feels. It doesn't change the workflow, the level system, the questions, the copy, the engines or the guardrails. Those stay exactly as defined in:
- [Levels plan](DAYLIGHT_LEVELS_PLAN.md): flow, level gates, density budget and verification. **This plan replaces its section 5 (visual system) and the visual parts of section 6 (component specs).** Where the two disagree on looks, this plan wins; on everything else, the levels plan wins.
- [Design brief](DAYLIGHT_DESIGN_BRIEF.md) and [guide redesign](DAYLIGHT_GUIDE_REDESIGN.md): product direction, hard constraints and content.

---

## 1. The idea in one paragraph

The biggest risks for this demo are **trust** and **education**: a 65-year-old has to believe the AI is honest and has to come away understanding Medicare. So we make the AI **approachable the way a good person is**: it has a friendly face, it shows its work, it shows its sources, it admits what it can't check, and it never makes you type. The look borrows Town's **cartoony helpfulness**: a named character who feels like a capable helper, rounded illustration and warm off-white space. We tune it toward **a kind, well-organized librarian, not a party.** The fun comes from warmth, tactile paper-and-map metaphors and small moments of delight, never from jokes, confetti or anything that feels childish.

---

## 2. What we take from Town, and what we change

Town's AI is an animal or object character with one small accessory (a bowtie, glasses). It talks in the first person, shows sample messages as tidy cards, and keeps its security and trust claims in calm, icon-led blocks on a warm off-white page. That's the right instinct for us: **a character makes an invisible AI feel like someone you can ask.** We don't copy Town's characters, illustrations or layouts; we build an original system on the same instinct.

| Dial | Town (AI coworker for teams) | Daylight (Medicare guide for 65+) |
| --- | --- | --- |
| Character | A cast of playful animals and objects | **One** character, clearly Daylight, warm but composed |
| Humor | Light, a little cheeky | Warm, never jokey. Smiles, not punchlines |
| Energy | Busy product mockups, phrase animations | One thing at a time, slow, calm motion |
| Trust signals | Security badges | Sources, "checked / not checked yet" stamps, visible memory, plain promises |
| Imagery | Photo portraits next to characters | Illustrated, dignified older adults and caregivers. No stock photos, no fake testimonials |
| Reading distance | Laptop at arm's length | iPad on a lap, often two people on a couch |

**Seriousness rule of thumb:** if a pharmacist would find it too cute to put on the counter, it's too much.

---

## 3. Eight principles for making AI accessible to older adults

These are the core of the plan. Every component in section 6 traces back to at least one.

1. **Give it a face, but never a human one.** A drawn character makes the AI approachable and makes "this is automated" obvious at a glance. No photos, no realistic faces, no human names. The character *is* Daylight.
2. **Show its hands.** When Daylight is working, show what it's doing in plain visual steps (looking at the plan list, checking the Medicare source), not a mysterious spinner.
3. **Show its receipts.** Facts come with a visible source tag that looks like a library card or a stamped receipt: where it came from, and when it was checked.
4. **Show its limits.** "Not checked yet" is a first-class visual state with its own stamp and icon, as visible as "Checked." Honesty about gaps builds more trust than polish.
5. **Separate the reviewed from the conversational.** Reviewed content (Basics cards, visuals, map steps, plan data) looks like **printed material**: crisp, carded, sealed. Daylight's conversational explanations look like **the character speaking**. A person can always tell "official reviewed fact" from "Daylight explaining it."
6. **Never make anyone type.** Every turn offers big answer chips. The text box is present and friendly but optional.
7. **Show what it remembers.** "What I know so far" looks like Daylight's notepad, open and editable. Seeing exactly what the AI knows, and being able to cross it out, removes the creepiness.
8. **Use familiar objects.** Paper booklets, a folded map, a checklist, sticky notes, a calendar, stamps. People 65+ already trust these; they turn abstract AI output into things they recognize.

---

## 4. The character: Daylight

### 4.1 Recommended direction (Proposed, D1)

**A small, rounded sun with a calm face and reading glasses.** It grows directly out of the existing sun brand mark, so it reinforces the brand rather than adding a mascot beside it.

- **Shape:** a soft circle with 8 short, rounded rays (the brand mark's rays, softened). Proportions are slightly wider than tall, so it reads as friendly and grounded, not bouncy.
- **Face:** two dot eyes, a small curved smile, gently rosy cheeks. No mouth movement or lip sync.
- **The serious accessory:** round reading glasses in soft ink. It says "I've read the fine print" and keeps the character from feeling childish.
- **Props (used sparingly):** a clipboard (showing sources), a folded map (map moments), a magnifying glass (checking), a pencil (notepad and memory). Props explain what Daylight is doing; they're never decoration.
- **Line and fill:** 2.5px soft-ink outline, flat fills from the palette (muted gold body, ivory highlights), one soft inner shadow. No gradients beyond a gentle glow.

**Alternatives considered** (for the owner's choice; build A unless told otherwise):
- **B · Lighthouse keeper's lighthouse:** a friendly lighthouse with a warm lamp. Strong "guidance" metaphor, more serious, but weaker brand tie.
- **C · Faceless sun orb:** the sun mark animated with light only, no face. Most serious and most "tech," but loses the approachability that is the point of this plan.

### 4.2 Expression set

Built as one SVG with swappable eye, mouth, ray and prop groups, so Claude Code can draw and maintain it in code. Each state is static; movement happens only in transitions.

| State | Look | Used when |
| --- | --- | --- |
| **Hello** | Soft smile, one ray slightly raised like a small wave | First message, returning to the conversation |
| **Listening** | Eyes looking toward the chips, head tilted 5° | Waiting for an answer |
| **Thinking** | Glasses pushed up, eyes up and to the side, magnifying glass | Working state (section 6.2) |
| **Explaining** | Holding a card or pointing gently to one side | Showing a visual or a Basics card |
| **Showing sources** | Holding a clipboard | Source tag expanded |
| **Not sure / can't check** | Gentle apologetic smile, small shrug of two rays | "Not checked yet" and offline states |
| **Pleased** | Closed happy eyes, rays slightly extended, warm glow | Finishing a step, the map emerging |

### 4.3 Sizes

- **Hero (160–200px):** arrival only, and the map-emerges moment.
- **Companion (64px):** beside the current Daylight message in levels 1–3.
- **Avatar (32px):** beside each message in history, and in the chat dock from level 4.
- **Mark (24px):** top bar, which keeps the brand sun without a face.

The character gets smaller as the person gets more confident. Daylight steps back as they take over.

### 4.4 Character rules (guardrails in visual form)

- **Never next to a specific plan.** The character doesn't appear on plan cards, the ranked list or plan detail. It never points at, holds or reacts to a plan. This keeps any visual "endorsement" out of the most sensitive surface.
- **Never excited about money.** No "pleased" state on prices, savings or cost visuals.
- **Always labeled automated.** A small "Automated guide" chip (existing disclosure wording, or listed as a new string) sits beside the companion and avatar sizes.
- **Never carries information alone.** Expressions are mood, not meaning. Every status is still word + icon.
- **Decorative to assistive technology.** The character SVG is `aria-hidden="true"`; the message text carries the meaning.

---

## 5. Visual system

### 5.1 Color

Keep the existing palette roles from the levels plan (ivory, sage, muted gold, soft ink) and add an **illustration palette** derived from them:

| Token | Use |
| --- | --- |
| `--paper` | Page background: warm off-white, close to today's ivory |
| `--paper-raised` | Printed-material cards (reviewed content) |
| `--speech` | Daylight's message area: a slightly warmer, softer tint than `--paper-raised` |
| `--sun-body`, `--sun-glow` | Character body and glow (muted gold and a pale tint of it) |
| `--sage-path`, `--sage-wash` | "You" / your path, selected chips, focus, route line |
| `--ink-line` | Illustration outlines and hairlines (soft ink) |
| `--cheek` (Proposed, D3) | Character cheeks only: a muted rose tint. The one new hue, used nowhere else |
| `--stamp-checked`, `--stamp-notyet` | Stamp inks: sage for checked, warm gray for not checked yet. Always paired with words and icons |

All text keeps WCAG AA on its surface. Illustration fills don't need text contrast, but their outlines must stay visible (≥3:1 against the background).

### 5.2 Type

- **Body and UI: Atkinson Hyperlegible** (self-hosted, SIL OFL). Designed for low-vision readers; distinctive letterforms prevent the l/I/1 and O/0 confusion that matters for dates, ZIPs and dollar amounts.
- **Display: Fraunces** (self-hosted, SIL OFL; Proposed, D2) at a soft, rounded setting. It gives headings warmth and a little personality that matches the character, while staying bookish and serious. Use it only for headings, level moments and visual titles, never for body or numbers.
- **Numbers:** always Atkinson with tabular figures, so prices and dates line up and never look decorative.
- Base size 18px, **20px on tablets** (two people reading from a couch). Scale and spacing as in the levels plan.

### 5.3 Shape, texture and depth

- **Rounded everything:** 14px radius on chips, 20px on cards, 28px on large panels. Corners echo the character's softness.
- **Paper grain:** a very faint same-origin SVG noise texture on `--paper` (≤3% opacity), so the page feels like good stationery instead of flat digital white. Turn it off in print and high-contrast modes.
- **Printed-material cards:** crisp 1px `--ink-line` border, small soft shadow and a subtle top "fold" highlight, like a card set on a desk.
- **Speech area:** no border, softer shadow, rounded more generously. It reads as the character talking, not a document.

### 5.4 Iconography and spot illustrations

- **Icons:** one inline-SVG set on a 24px grid with a 2px rounded stroke, slightly chunky and friendly. Every icon sits next to a word.
- **Spot illustrations** (64–120px, same line and fill style as the character) for recurring concepts: hospital (Part A), stethoscope (Part B), pill bottle (Part D), a bundled box (Medicare Advantage), an umbrella over a house (Medigap), a calendar page (dates), a phone with a heart (free help), a folded map (your map).
- **People:** illustrated older adults and caregivers, shown active and capable (gardening, walking, at a kitchen table with papers). Varied ages, bodies, skin tones and abilities, including a cane or hearing aid shown naturally. They appear only in Basics and help moments, never near plans and never as "customers."

---

## 6. Component direction

### 6.1 Arrival (level 1)

- A big, calm paper page with lots of breathing room. Hero character in "Hello," with the first message beside it in a speech area and the automated-guide chip visible.
- Answer chips look like **sturdy paper tabs**: tall, rounded, with a gentle lift on press (and a check mark when chosen).
- The composer looks like a **notepad line** with a pencil icon: inviting, clearly optional, never the visual focus.
- The character only shrinks to companion size after the first answer, so the transition feels like "let's get going together."

### 6.2 Thinking and working ("show its hands")

Replace the generic spinner with a **working card**: the character in "Thinking" plus up to three plain step rows with icons, filling in as they happen (for example a list icon, then a magnifying glass, then a check). Reuse existing status wording; if new labels are needed, list them for sign-off. Reduced motion: the rows appear without animation. No fake progress: a row only appears when that work actually happened.

### 6.3 Messages

- **Daylight's messages:** text in the `--speech` area beside the companion or avatar. Short paragraphs, 20px on tablets, max ~60 characters per line.
- **Paced reveal:** long replies appear one paragraph at a time with a 250ms fade, so they read like someone talking rather than a wall arriving at once. With reduced motion, the whole message appears instantly.
- **Person's messages:** sage-wash bubble on the right, plain and quiet.
- **Reviewed content inside chat** (a visual, a Basics card) renders as a printed-material card *inside* the speech, with the character in "Explaining" holding its corner. That makes rule 5 visible: Daylight is handing you something official.

### 6.4 Receipts and stamps ("show its receipts", "show its limits")

- **Source tag:** a small library-card tab under any fact: source name, a calendar icon and the checked date. Tapping opens a card showing the character with its clipboard and the full source details.
- **Stamps:** "Checked" (sage ink, check icon) and "Not checked yet" (warm gray ink, dotted-circle icon) look like gently rotated rubber stamps (−3°). They're used on map steps, plan fields and doctor or drug notes. Same size and weight for both, so the gap is never hidden.
- **Reviewed seal:** a small round seal on Basics cards and visuals ("reviewed" wording reused or listed for sign-off). It distinguishes reviewed material from conversation.

### 6.5 Daylight's notepad ("show what it remembers")

"What I know so far" becomes a **notepad page**: lined paper, each remembered item handwritten-*looking* (but set in Atkinson for legibility) with a pencil "edit" and a strike-through "remove." The character in "Listening" sits at the top corner. When an item is edited, the line briefly highlights in sage so the person sees the AI took the change.

### 6.6 The map (level 4)

- The map is a **folded paper map** that unfolds when it emerges: the "Your next step" card opens like a fold to reveal the route. The character ("Pleased," hero size) holds the corner for the first view, then steps down to avatar size.
- The route is a soft dashed trail across paper with small landmark illustrations at each step (calendar, Part B card, a fork in the path for the two choices, a phone for help).
- "You are here" is a **small sun pin**, the character's mark without a face, so the map is about the person, not the guide.
- Done steps get a "Checked"-style stamp; upcoming steps are faint pencil sketches that ink in as they're reached. It's a satisfying, dignified "drawing in" of your journey.
- Reduced motion: the unfold becomes a crossfade; pencil-to-ink becomes an instant swap.

### 6.7 Basics cards and the visual library (V0–V8)

- Basics cards look like **pages from a well-made booklet**: Fraunces title, a spot illustration, bullets, term chips and the reviewed seal and source tag at the bottom.
- The V0–V8 visuals share the illustration style: same line weight, palette and rounded blocks, with spot illustrations replacing generic boxes where they help. V4 "building blocks" become literal stackable blocks with the Part A/B/D and Medigap icons; V6 timeline becomes a calendar strip with the sun pin at "Today."
- Every visual stays text-in-DOM, prints in black and white, and keeps its reviewed content unchanged.

### 6.8 Plans (level 5): the serious room

Plans are where trust is most fragile, so the fun dials **down** here on purpose:
- No character, no spot illustrations of people, no stamps of excitement. The chat dock avatar is the only Daylight presence.
- Cards look like **neat index cards**: plan name, carrier, three labeled figures in tabular numbers, the star rating with its text value, the SNP label where needed, and "Checked" / "Not checked yet" stamps on fields like doctors.
- The "ranked by … because you said …" header looks like a **sticky note** stuck at the top of the stack: honest, handwritten-feeling and clearly the person's own preference.
- All cards are visually identical. Nothing about the first card is featured beyond its position.

### 6.9 Small moments of delight (dignified)

- The top-bar sun rises one notch at each level (from the levels plan), with the character's glow briefly brightening.
- Finishing a map step: a soft gold bloom behind the stamp, 250ms.
- The printed checklist gets a small character illustration in the corner and the person's own "ready" stamp, something they'd happily stick on the fridge.
- No confetti, points, badges, sound effects, streaks or animated celebrations.

---

## 7. Motion

- Default posture: **still.** The character doesn't idle-animate, bob or blink on its own; looping motion is distracting and reads as anxious.
- Movement happens only on change: expression swaps crossfade over 150ms, messages fade in over 250ms, the map unfolds over ~900ms.
- One exception: the "Thinking" glow can breathe slowly (opacity only, 1.6s) while work is actually happening, and stops the moment it finishes.
- Every motion has a reduced-motion variant: instant or a ≤150ms fade.

---

## 8. Constraints check

Everything here works under the existing CSP and offline rules:
- Character, icons, spot illustrations and paper grain are **same-origin SVG**, built in `app.js` or as files in `apps/chat/` (for example `apps/chat/art/`). No external images.
- Fonts are **self-hosted** `woff2` with license files; add `font-src 'self'` to the CSP if `default-src` doesn't cover it; update `demo_release.py` packaging.
- No inline styles or scripts; expression changes swap classes or SVG `<use>` references.
- Accessibility rules from the levels plan still apply in full: ≥18px body, ≥48px targets, AA contrast, 200% zoom, no hover-only content, word + icon status, reduced motion, print.
- Illustration is decorative (`aria-hidden`); no information lives only in a picture.
- Copy freeze still applies. Any new label (for example "Automated guide," working-card steps, stamp words, seal text) is reused from existing strings or listed in section 11 for sign-off.

---

## 9. Checking it works with real people (lightweight)

Before polishing everything, test the character and trust signals with **five people aged 63–75** (plus one or two caregivers), using static screens:
- **Five-second test:** show the arrival screen for five seconds, then ask: "What is this? Is it a person or a computer? Would you trust it with a Medicare question?"
- **Character choice:** show directions A, B and C side by side on the same screen. Ask which feels most trustworthy, and which feels too silly or too cold.
- **Reviewed vs conversational:** show a chat turn containing a Basics card. Ask: "Which part did Daylight write, and which part is official information?"
- **Stamps:** show a plan card with one "Not checked yet" stamp. Ask what it means and what they'd do next.

**Pass bar:** 4 of 5 correctly say it's automated; 4 of 5 tell reviewed content from conversation; no one calls it "childish" or "for kids"; no one thinks Daylight is recommending a plan. Adjust before continuing if any bar fails.

---

## 10. Checklist

Same protocol as the levels plan: work top to bottom, tick with `DONE <date> — evidence: <path/screenshot>`, record decisions in the log, never renumber. Screenshots at 390×844, 820×1180 and 1280×800 go under `cms-slice/reports/ui-aesthetic/<item>/`.

### Phase A: Character and assets

- [x] **A01** · Draw character direction A as layered SVG (body, rays, face, glasses, props), plus quick sketches of B and C for the test in section 9. DONE 2026-10-20 — `app.js` `daylightSVG()` (layered: glow, rays, body, cheeks, glasses, eyes, mouth, props). B/C not sketched (built A per D1). Evidence: d1/d7.
- [x] **A02** · Build the expression set (4.2) as swappable groups; render all seven states on one review sheet. DONE 2026-10-20 — `DL_EXPR` with hello, listening, thinking, explaining, sources, notsure, pleased (swappable eye/mouth/prop groups).
- [x] **A03** · Build the four sizes (4.3); check legibility of the face at 32px and drop facial details at 24px. DONE 2026-10-20 — `.dl-hero`/`.dl-companion`/`.dl-avatar`/`.dl-mini`; props + cheeks drop at mini; 24px mark stays the faceless brand sun.
- [~] **A04** · Build the icon set and the eight spot illustrations (5.4). PARTIAL 2026-10-20 — eight spots built (`SPOTS`: hospital, stethoscope, pill, bundle, umbrella, calendar, phone, map); a dedicated 24px icon set still reuses existing glyphs.
- [ ] **A05** · Draw three people illustrations (older adult, couple, caregiver with parent) in the same style. DEFERRED 2026-10-20.
- [x] **A06** · Paper grain texture as a same-origin SVG; verify it's off in print and in forced-colors mode. DONE 2026-10-20 — `apps/chat/art/grain.svg` (feTurbulence ~3.5%), served by `demo.py`; off in `@media print` and `forced-colors`.

### Phase B: Foundations

- [x] **A07** · Add color tokens (5.1), including the illustration palette; record the contrast table. DONE 2026-10-20 — illustration palette tokens added (`--paper`, `--speech`, `--sun-body`, `--sage-path`, `--ink-line`, `--cheek`, `--stamp-*`). Formal contrast table still to record.
- [x] **A08** · Self-host Atkinson Hyperlegible and Fraunces with licenses; update the CSP and packaging; tabular figures for numbers. DONE 2026-10-20 — `apps/chat/fonts/*.woff2` (Latin subsets) + `LICENSE.txt`; `@font-face` with `font-display:swap`; `font-variant-numeric:tabular-nums`; CSP `default-src 'self'` already covers `font-src`; `demo.py` serves `/fonts/*`. (Release packaging = follow-up.)
- [x] **A09** · Shape, texture and depth tokens (5.3); define printed-material and speech surfaces as reusable classes. DONE 2026-10-20 — `--r-soft*`, `--elev-*`; `.printed` and `.message.assistant`/`--speech` surfaces.

### Phase C: Test before polishing

- [ ] **A10** · Build static screens for the section 9 test (arrival, chat with Basics card, plan card with stamps, A/B/C comparison).
- [ ] **A11** · Run or hand off the five-person test; record results against the pass bar; pick the character direction in the Decision log.

### Phase D: Components

- [x] **A12** · Arrival screen (6.1). DONE 2026-10-20 — hero character + automated-guide chip + first message in speech; big paper-tab chips; optional notepad-style composer. Evidence: d1/d7.
- [x] **A13** · Working card and thinking state (6.2). DONE 2026-10-20 — `workingCard()`: thinking character + plain step rows (no spinner), reduced-motion safe.
- [~] **A14** · Message design and paced reveal (6.3), including reviewed cards inside speech. PARTIAL 2026-10-20 — speech surface + character avatar + reviewed content rendered inside speech (d2); paragraph-by-paragraph paced reveal not yet.
- [~] **A15** · Source tags, stamps and reviewed seal (6.4) applied everywhere facts appear. PARTIAL 2026-10-20 — `stamp()`, `sourceTag()`, `reviewedSeal()` built; applied to Basics (seal+tag), plans (field stamps, d5) and map (Done stamp, d3). Not yet on every fact.
- [x] **A16** · Daylight's notepad (6.5). DONE 2026-10-20 — lined-paper "What I know so far" (d6); Fraunces head; sage flash class ready.
- [~] **A17** · Folded paper map, landmarks, sun pin and pencil-to-ink (6.6), including the unfold transition. PARTIAL 2026-10-20 — `.map-paper` + dashed route trail + "Done" stamps + pencil-sketch (italic/dashed) upcoming rows (d3); per-step landmark illustrations, faceless sun "you are here" pin, and the unfold animation still to add.
- [~] **A18** · Basics booklet pages and V0–V8 restyle (6.7); black-and-white print check. PARTIAL 2026-10-20 — Basics booklet pages with spot + seal + source tag done (d4); V0–V8 inherit the palette but aren't each re-illustrated; B/W print still to check.
- [x] **A19** · Plans serious room (6.8); confirm the character appears nowhere on plan surfaces. DONE 2026-10-20 — sticky-note rank header, identical index cards, honest field stamps, tabular numerals, no character on plan surfaces (d5).
- [~] **A20** · Delight moments and printable checklist art (6.9). PARTIAL 2026-10-20 — `.bloom` keyframe ready and sun-progress glow; checklist corner art not added.

### Phase E: Verify

- [~] **A21** · Motion audit (section 7): no idle loops; every animation has a reduced-motion variant. PARTIAL 2026-10-20 — character is still by default (only the Thinking glow breathes while working); global `prefers-reduced-motion` disables animation; formal per-animation audit pending.
- [x] **A22** · Accessibility and CSP pass from the levels plan section 8, plus: character is `aria-hidden`, automated-guide chip is always visible, stamps read correctly in screen readers. DONE 2026-10-20 — character SVG `aria-hidden`; `.automated-chip` beside every avatar + hero; stamps are real text (word + icon); zero CSP console violations across L1–L5 (desktop + phone).
- [x] **A23** · Guardrail visual audit: character never near a plan or price; no "pleased" state on money; every plan card identical in styling. DONE 2026-10-20 — verified in d5: no character/illustration on plan surfaces, no "pleased" on cost, all plan cards identical.
- [ ] **A24** · Before/after summary in `reports/ui-aesthetic/SUMMARY.md` with screenshots per level and new strings awaiting sign-off. DEFERRED 2026-10-20 — screenshots are in `reports/ui-aesthetic/phase-core/`; a formal SUMMARY.md is the remaining write-up.

---

## 11. New strings awaiting owner sign-off

| String | Where | Why no existing string works | Status |
| --- | --- | --- | --- |
| "Automated guide" | Chip beside the hero + every Daylight avatar (§4.4) | Short always-visible "this is automated" label | NEW — anticipated by the plan; needs owner sign-off |
| "Reading what's on your screen" / "Checking the Medicare sources" | Working card step rows (§6.2) | Plain-language "show its hands" steps | NEW — needs owner sign-off |
| Stamp words: "Checked" / "Done" / "Not checked yet" / "Published figures" / "Doctors in-network" | Stamps on map steps and plan fields (§6.4, §6.8) | Rubber-stamp status labels | NEW — needs owner sign-off |
| "Reviewed" | Reviewed seal on Basics cards / visuals (§6.4) | Seal text marking reviewed content | NEW — needs owner sign-off |
| "Reviewed content" | Source-tag note on Basics cards | Distinguishes reviewed from conversational | NEW — needs owner sign-off |

---

## Decision log

| Date | Decision | By |
| --- | --- | --- |
| 2026-10-20 | D1 · Character direction A: a rounded sun with reading glasses, grown from the brand mark; B and C kept for the test | **Accepted — built A** (B/C sketches + 5-person test deferred; revisit if the test flags issues) |
| 2026-10-20 | D2 · Display typeface Fraunces (soft setting) + Atkinson Hyperlegible for body, both self-hosted | **Accepted — implemented** (Latin woff2 self-hosted; variable Fraunces opsz+wght) |
| 2026-10-20 | D3 · One new hue, a muted rose, for character cheeks only | **Accepted — implemented** (`--cheek`, used only on `.dl-cheek`) |
| 2026-10-20 | D4 · The character is Daylight; no separate mascot name | **Accepted — implemented** |
| 2026-10-20 | D5 · No character or people illustrations on any plan surface | **Accepted — implemented & audited** (A23) |
| 2026-10-20 | D6 · This plan replaces the visual sections of the levels plan; workflow untouched | **Accepted** — aesthetic layered on the levels flow; L1→L5 behavior unchanged |

## Change log

| Date | Change | By |
| --- | --- | --- |
| 2026-10-20 | Created | Claude |
| 2026-10-20 | Implemented the core aesthetic: Daylight character (7 expressions, 4 sizes), self-hosted Atkinson Hyperlegible + Fraunces, illustration palette + paper grain, printed-material vs speech surfaces, stamps/seals/source tags, 8 spot illustrations, working card, folded-paper map, serious plans room, notepad. Verified L1→L5 desktop + phone (zero errors, no CSP violations); 63 backend tests pass. Evidence in reports/ui-aesthetic/phase-core/. Deferred items noted in Execution status. | Claude |

## Sources

- [Town](https://www.town.com/): reference for character-led, helpful AI presentation (named characters with one accessory, first-person sample messages, warm off-white page, calm trust section).
- [Atkinson Hyperlegible](https://www.brailleinstitute.org/freefont/) (Braille Institute) and [Fraunces](https://github.com/undercasetype/Fraunces): both SIL Open Font License.
