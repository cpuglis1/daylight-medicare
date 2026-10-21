# Daylight Medicare — Design handoff brief

**Purpose of this doc:** a self-contained summary to hand to a design-focused model. It captures (1) the product-direction conversation so far, (2) the current state of the tool/UI, (3) the two open problems, and (4) the new structural + aesthetic direction to design against. **This pass is aesthetic/interaction design only — copy, information architecture, and the compliance rules are already handled and are fixed. Do not rewrite language.**

Prepared 2026-10-19. Builds on `DAYLIGHT_GUIDE_REDESIGN.md` (the product spec) and the current implementation in `cms-slice/apps/chat/` (`index.html`, `app.js`, `styles.css`).

---

## 0. What Daylight is (one paragraph)

Daylight Medicare helps someone about to turn 65 (or an adult child helping a parent) understand their Medicare choices — calmly, visually, with an AI agent available instantly. Operating model: **self-directed research, licensed transaction** (no selling, no enrollment in this build). The competitive wedge versus Chapter (an advisor-callback company): **an AI agent the instant you arrive**, and **clean, personal visualizations you can't get over a phone call**. The product must feel trustworthy and premium while being usable by a 65-year-old on an iPad.

---

## 1. Product direction from the user (the two messages this doc summarizes)

### Message A — "build it one concept at a time; chat is the guide; beat Chapter with instant + visual"
- The decision flow (the "map") must be **dynamic, grow, and interactive** — not a static dashboard.
- The core problem: **it can't be too much too quickly.** Like a video game — Level 1 is a simple open field, then one new mechanic at a time.
- The **chat should be the tutorial guide** (a "fairy" metaphorically — no literal fairy): it walks the user through, introduces one concept at a time, reacts to what they do.
- **Plans need preference-based ranking + overhaul** (not a raw catalog dump).
- **Competitive advantage vs Chapter:** (1) information + an agent **immediately via chat**, and (2) **visualizations** — clean representations a phone call can't deliver.

**Decisions locked in response to Message A (via explicit choice):**
- **Map reveal → soft unlock.** One step active at a time; finished steps collapse; next reveals as you go; "show the whole map" escape always present.
- **Plans → preference-ranked, transparent.** Deterministic order by the user's stated priorities, always labeled "ranked by X because you said Y," one-tap reweight, nothing hidden, never the word "best."
- **Guide → proactive but calm.** One nudge per step, opens the matching visual, then waits. Never nags, never auto-advances.

### Message B — "the landing is still overwhelming; it doesn't look legit; invert to AI-first and let the map emerge later like a game"
- The progressive **steps are an improvement**, but the **landing map page is still overwhelming.** "Just asking you to do better" won't close the gap — needs a real design pass.
- **It doesn't look like a professional site yet.** Colors/palette are fine; the overall **aesthetic isn't "legit tech-startup, AI-for-aging-population"** yet. This design pass is **all aesthetic, no language.**
- **New structural direction:** build it out **one level at a time, chat / AI first** — a **"how much do you know?"** assessment up front. **"Let's explore your map" should NOT come off the rip** (not on arrival). The map should **emerge around level 4–5**, like a video game unlocking content as you progress.

---

## 2. Current state of the tool / UI (what exists today)

### Flow
`Welcome → 8 setup questions → App shell` with four surfaces: **My map · Basics · Plans · Ask Daylight.**

### App shell
- **Desktop:** two panes — left = current surface (map/basics/plans), right = **Ask Daylight** chat dock (collapsible). Top bar: brand, nav tabs, "What I know so far," "Start over."
- **Phone:** single column + bottom tab bar (Map · Basics · Plans · Ask). Ask opens full-screen.

### The 8 questions (kept, work well)
recipient → ZIP + "is this Collier County?" → Medicare status (5 options) → month turning 65 (only if not enrolled) → job-based coverage → prescriptions → priorities (multi-select) → extras (multi-select). Presented as a one-question-per-screen stepper with a progress bar.

### Map (currently the landing surface after questions — PROGRESSIVE, "soft unlock")
- Header ("Your Medicare map" / "Your coverage for 2027" in review mode) + subline (for you · Naples · turns 65 Mar 2027).
- A **V1 "two decisions" visual** (two cards: how you'll get coverage, whether to keep Part B).
- A **"Step X of 5" progress meter** (dots).
- A **vertical route of 5 steps.** Only the **active** step is expanded (full card); finished/behind steps **collapse to a tappable line**; upcoming steps are a **teaser** ("N more steps ahead" + "Show the whole map").
- Each step card: status pill (word + icon — Done / Your next step / Coming up / Need more info), "You are here" badge, one-sentence description, a "why this applies to you" quote, a step-specific action (dates / help contacts / the two paths / the timeline), an "Ask about this" chip, and a prominent **"Next →"** advance button.
- A deterministic **decision-map engine** computes the 5 steps and statuses from the answers (review mode for people already enrolled; "need more info" for unknowns; personal dates: initial enrollment window, coverage start, Medigap window, fall change period).
- **Step 3** ("Choose how to get coverage") holds the two paths (Original vs Advantage), a V4 "building blocks" visual, priority "questions to weigh," a leaning toggle (+undo), and a V5 comparison table in a disclosure.

### Basics (NOT gated — everything shown at once)
Four reviewed cards A–D (what Medicare is / what A & B cover / how Original Medicare works & costs / ways to get more coverage), each with a summary, bullets, one visual, tap-to-define term chips, a source link, and "Ask about this." Plus a ~13-term glossary (tap for a definition dialog).

### Plans (preference-ranked shortlist — new)
- "Ranked by [lowest monthly cost] — because you said [a low monthly cost matters]. Not a recommendation, nothing hidden."
- **Coverage-type chips** (Advantage+drugs / Advantage no drugs / Drug plans / Special needs) and **rank-by chips** (lowest monthly cost / fewer surprise bills / lower drug deductible / Medicare's order).
- **Uncheckable warnings** (doctors in-network, extras) stated plainly.
- **Top 3 ranked cards** (with #rank, premium, out-of-pocket cap, drug deductible, CMS star rating, "See details" / "Discuss this plan"), a **"Show N more"**, and a **"See every plan and all the sort controls"** escape to the full catalog.
- Backed by real 2027 Collier County data (70 plans) via `/api/catalog`. Never "best," deterministic, nothing hidden.

### Ask Daylight (chat) — now a tutorial conductor
- Docked on desktop, full-screen tab on phone.
- **Proactive, deterministic guide:** one scripted nudge per map step, tied to the active step. Can **render a reviewed visual inline in the chat** and can **advance the map**. Works offline (deterministic). Free-form questions go to the LLM.
- First message discloses it is automated (not a person, no ID numbers).

### Visual library (V0–V8)
Reviewed, deterministic DOM/SVG components: auto-vs-sign-up, two decisions, A&B coverage, "who pays what" bar, building blocks (two paths), Original-vs-Advantage side-by-side table, personal timeline, plan-list banner, Medigap lettered plans. Text lives in the DOM (scales, reads aloud). These are the "visual moat."

### Also present
- A printable one-page checklist.
- A "What I know so far" editable panel (editing recomputes the map live).
- A local-help panel (SHINE counseling / Hope PACE) surfaced from `/api/local-resources`.

---

## 3. The problems to solve (why we're bringing in design help)

1. **The landing is still overwhelming.** Even with progressive steps, arriving straight on the map presents a lot at once: header + subline + two decision cards + progress meter + the V1 visual + a dense active step card + a teaser + a footer. Too much density, too fast, for the target user.
2. **It doesn't look legit yet.** The palette is right, but the overall execution doesn't read as a **well-funded, modern AI health-tech product.** It needs a real visual system: type scale, spacing, depth, motion, a premium chat/assistant presence, and custom-feeling data viz — all tuned for 65+.

---

## 4. The new structural direction — "AI-first, map emerges later (level 4–5)"

**Invert the arrival.** Do NOT land on the map. Land on the **AI/chat**, assessing **"how much do you already know?"** The experience builds **one level at a time**, like a game where content unlocks as you progress. The map is an **earned artifact that emerges around level 4–5**, not a dashboard you're dropped into.

This is a proposed leveling curve (a starting frame for design to shape — the non-negotiable is: chat-first, no map on arrival, map emerges mid-journey):

- **Level 1 — Arrival / assessment (AI-first).** No map, minimal chrome. One calm conversational surface. Daylight gauges familiarity ("how much do you know about Medicare?") and begins to know the person. The 8 setup questions live here — ideally woven into the conversation, or a very light companion to it, rather than a separate form.
- **Level 2 — One concept at a time.** Introduce the two decisions / Parts A & B through dialogue + a single visual at a time. Still no full map.
- **Level 3 — Your situation takes shape.** Daylight reflects back what it has learned; a single "your next step" or proto-map element appears.
- **Level 4 — The map emerges.** "Let's look at your map" — the full route appears as something the user has earned, not been dumped into.
- **Level 5 — Mastery / act.** Plans (ranked), compare, print, enrollment-adjacent help. The user now understands and can explore confidently.

The leveling should feel like genuine progression/unlocking — **dignified and premium, not cartoonish or childish** (the audience is 65+). Transitions between levels are a key design surface.

---

## 5. Aesthetic brief (this is the design ask — aesthetics only, no copy)

**Target feeling:** a legit, well-funded **AI health-tech startup, designed for an aging population.** Trustworthy, calm, premium, modern. Reference the polish of modern health-tech and AI-assistant products, but up-tuned for 65+: larger type, higher contrast, generous spacing, nothing tiny or dense, no cleverness that sacrifices clarity.

Design these, as a cohesive system:

- **A visual system:** a deliberate type scale, a consistent spacing/rhythm system, intentional white space, and **tasteful depth** (soft, considered shadows and layering — not flat-and-cheap, not heavy skeuomorphism). Keep the current **warm palette** (ivory / sage / muted gold / soft ink) but elevate its execution.
- **A premium AI/assistant presence.** The chat is the product's front door now — give it the polish of a top-tier AI chat UI: a considered message design, an identity/avatar for Daylight (there's a sun brand mark), and calm "thinking"/typing/streaming states. It should feel alive and intelligent without being busy.
- **The leveling experience.** A visual and motion language for **progression / unlocking** across levels 1→5 — elegant and dignified, not gamified-childish. The **level-4 "map emerges"** moment is the signature transition; make it feel earned and satisfying.
- **The emergent map.** Redesign the map so that when it appears it is clear and calm, not dense. Rethink density, hierarchy, and how a single active step is foregrounded while the rest recede.
- **Custom, premium data visualizations.** The V0–V8 visuals are the moat ("clean representations you can't get on the phone"). Design them as one cohesive, custom-illustrated/diagram system — personal, clean, keepable. Avoid stock-chart or clip-art feel.
- **Plan cards + ranking surface.** Make the ranked shortlist feel like a confident, trustworthy product surface (transparent, never salesy).
- **States and motion.** Loading, empty, thinking, success, and transition states — all calm, legible, and consistent. Motion should feel alive but never anxious (respect reduced-motion).
- **Overall shell / layout.** The top bar, the two-pane↔single-column responsive system, and the phone tab bar should feel like one intentional product, not assembled parts.

**Explicitly out of scope for this pass:** copywriting/voice, information architecture, and the compliance behavior. Don't change wording or the rules below.

---

## 6. Hard constraints the design must respect

**Audience / accessibility (non-negotiable):**
- Body text ≥ 18px; primary tap targets ≥ 48px (we use 52–56); full-width targets on phone.
- WCAG 2.2 AA contrast. Text resizes to 200% without breaking.
- **No hover-only content**, no swipe-only gestures, no auto-advancing carousels.
- **Status is always word + icon, never color alone.**
- No timers / no auto-dismissing messages. Reduced-motion supported.
- Print view works on a real printer.

**Product guardrails (legal/ethical — cannot change):**
- The model/app never chooses, ranks, hides, scores, or calls a plan "best." **Plan ordering is deterministic and transparent;** commissions never affect what's shown.
- Preference ranking is allowed only as a **user-controlled, labeled, deterministic sort** ("ranked by X because you said Y"), with nothing hidden and a path to every plan.
- **No IDs, SSNs, documents, or account sign-up.** State lives in the browser tab only. Sensitive answers (birth month, employment) are not logged.
- Special Needs Plans are labeled "only for people who qualify."

**Technical substrate (what's feasible):**
- Front-end is **static `index.html` + `app.js` + `styles.css`** (plus `daylight.svg`), served by a local Python demo server under a **strict Content-Security-Policy**: `script-src 'self'; style-src 'self'; img-src 'self'`.
  - **No inline `<style>`, no inline `style=` attributes, no inline `<script>`, no `onclick`.** All CSS in `styles.css`; all JS in `app.js`; dynamic values set via the DOM `.style` API (allowed).
  - **No external assets** (CDNs, Google Fonts, remote images) — everything must be same-origin.
  - **Custom web fonts are possible but must be self-hosted** (added to the served assets and the CSP) — currently we use system fonts + Georgia for display. If the design calls for a specific typeface, note it as "self-host required."
  - Icons/illustrations must be **inline SVG** (no icon-font CDNs, no remote SVGs).
- Two live endpoints exist: `/api/live-chat` (LLM chat; may be offline — the UI must degrade gracefully) and `/api/catalog` (real 2027 Collier plan data). Everything else (map, basics, visuals, guide, print) is **client-side and works offline.**
- The map engine, guide spine, visuals, and ranking are all **deterministic** — design can rely on them being stable and predictable.

**Keep:** the warm "Daylight" palette and the sun brand motif.

---

## 7. Deliverables that would help (suggested)

- A visual system (type scale, spacing, color usage, elevation, motion principles) expressed as something implementable in vanilla CSS/SVG under the CSP above.
- High-fidelity direction for: the Level-1 AI arrival surface, the chat/assistant UI, the level-transition moments (esp. "map emerges" at L4), the emergent map, the ranked plan surface, and the V0–V8 visual family.
- Notes on any self-hosted fonts or assets required (so engineering can add them to the served bundle + CSP).

---

### Appendix — files to look at
- `DAYLIGHT_GUIDE_REDESIGN.md` — the full product spec (vision, 8 questions, visuals V0–V8, decision-map rules, guardrails).
- `cms-slice/apps/chat/index.html` · `app.js` · `styles.css` — the current implementation.
- `cms-slice/apps/chat/daylight.svg` — the sun brand mark.
