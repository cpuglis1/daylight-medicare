# D93 :8894 UI refresh — implementation record

Owner direction (November 5, 2026): implement the approved *Daylight UI review and redesign plan* on a new :8894 window, keep the
landing and chat click paths, use Impeccable, and test with minimal API calls. Owner accepted all suggested decision defaults.
:8893 (`alternatives/advisor-first/web/`) is unchanged and remains the reference.

## How it runs

```
cd ~/daylight && python3 alternatives/advisor-first/ui-8894/serve.py      # needs :8893 running
```

`ui-8894/serve.py` serves `web-8894/` and forwards every other request unchanged to `http://127.0.0.1:8893` (Host/Origin rewritten
to :8893 so its same-origin check passes). It adds no backend, storage, cookie namespace, model access or logging. Session, saved
profile, plans catalog, plans-context permission and the provider budgets are exactly :8893's.

## What changed (all in `web-8894/` unless noted)

| Area | Change |
|---|---|
| Tokens | New `tokens.css` is the only `:root`. DESIGN.md colors kept; choice/composer/phase borders → one control edge `#7a8676` (3.78:1 on raised paper, was 2.2–2.9:1); retained catalog olive family aliased to `olive`; `ink-3` raised to `#667062` (4.9:1). The three competing `:root` blocks in styles/approved/advisor CSS were removed. |
| Type | Every font size below 15px raised (≈125 declarations); stray sizes folded onto 15/16/17/18/20/21/23/24 and display steps. Clickable labels 17px; fine print 15px. Chat question 23px bold. |
| Shape | Radii folded to DESIGN.md's 7/8/12/22px (≈46 declarations). |
| Components | `finish.css`: DESIGN.md primary/secondary/choice buttons with 3:1 edges and ≥48px targets, hover distinct from selected, header Plans button with current-page marker, framed landing spread, 680px chat reading column, visible stepper (no checkmarks), dialog checkbox rows. |
| Chat (`advisor.js`) | Staged word-by-word reveal off (text and buttons usable on first paint); waiting state in words with a 10-second reassurance; Send reads “Sending…”; previous choices hidden while a turn is pending; model picker shown only with `?models` (provider notice always visible). |
| Plans (`plans-workspace.js/.css`) | Rewritten view over the same API: groups by joining rule (39 / 33), filters (type, drug coverage), default sort lowest premium then name, plain card (name, type in words, drug coverage, joining rule, premium, in-network yearly limit, Part B giveback or deductible, two actions), details side sheet with every field/condition/hold/example/fine print, compare tray and grouped compare table folding identical rows, chat drawer with backdrop below 1280px, single “Back to my conversation”. Original notice, definitions, coverage counts and restrictions stay in “About this plan data” and “Fine print”. |
| Records | D93 entries in `DAYLIGHT_REQUIREMENTS.md`, `DESIGN.md`, `alternatives/advisor-first/AGENTS.md`. |

Gates unchanged: plans-context modes stay `all/recommended/compare/costs`; sorting, filtering and grouping are display only and never
enter recommendation logic (D64). Browsing makes no AI call.

## Checks so far

- `serve.py` smoke test against a stand-in backend: static files, POST pass-through with cookie and CSRF header, Origin/Host rewrite, 4xx pass-through.
- Plans page in a headless browser with seven synthetic plans in the real field shape at 1366, 768, 375px: no script errors, no page-level horizontal scroll, no text under 15px; list, compare and details sheet render. Screenshots reviewed.
- Live :8894 checks against :8893 and the Impeccable detector run: see below.
- Card height target was ~230px; real plan names and two-line labels give ~295px, so the page is 13.5k px rather than the ~9k planned.

## Live checks against :8893 (November 5, 2026)

Started with `Start Daylight 8894.command` (repository root), which runs the Impeccable detector and then `serve.py`.
API use: page-load reads, the free plans catalog, and **one** model call (Find coverage → Send, GPT-6.1 Sol).

| Check | Result |
|---|---|
| Impeccable `detect --json` on `web-8894/` and on `web/` | 0 findings for both (`impeccable-8894.json`, `impeccable-8893.json`) |
| Stylesheets / `:root` blocks | 11 loaded, tokens first and finish last; 1 `:root` |
| Landing → first question | 1 click (Get started); opening text and starting points visible on first paint, no staged reveal |
| Starting points | 52px tall, 3.78:1 edges; selected = sage, 2px olive, bold; hover no longer mimics selected (fixed during testing) |
| Send a starting point | 2 clicks; waiting state shows three rising dots and “Daylight is thinking…” (a reassurance line appears after 10s), earlier choices hidden, Send reads “Sending…”; reply in ~11s |
| Follow-up question | 28px Fraunces, balanced, 34ch max (later questions render as `h1`; rule covers both) |
| Model picker | hidden; provider notice visible (“Send shares … with OpenAI.”) |
| Plans, 1366px | 72 plans; 39 joinable open, 33 with joining rules closed; default sort lowest premium; 147 buttons (was 886); page 13,533px (was ~35,750); card ~295px; no text under 15px; no horizontal scroll |
| Compare (2 plans) | 7 differing rows shaded and grouped; 3 identical costs folded; banner hidden in compare |
| Details sheet | 560px side panel; plain labels with official term; 7 “Not confirmed yet” rows with conditions; joining rule with “not checked whether you qualify” |
| Tablet 768px | chat starts closed; Ask Daylight opens a 460px drawer with backdrop and Close; no horizontal scroll |
| Phone 375px | single column, amounts stack, chat closed by default; no horizontal scroll |

Impeccable context reported one `mention`: `.impeccable/design.json` predates the D93 DESIGN.md edit (refresh with `impeccable document`).

## Polish round (owner request: “more professional”, bring back thinking dots)

- Motion, all opt-in past the global `animation:none` and all off under `prefers-reduced-motion`: thinking dots (three 8px olive dots in a sage pill, 1.2s smooth rise, staggered), a fade-up when a new exchange arrives (not on redraws), 150ms control transitions with a 1px press, side-sheet and tablet-drawer slide-in.
- Daylight sun avatar beside replies and the thinking indicator.
- Questions set in Fraunces at 28px (24px on phone); reading column 720px so starting points sit two per row without wrapping.
- Plans: “Find a plan” search on its own row, filter selects with drawn chevrons, “Ask Daylight” panel title with Close, toggle reads “Hide chat”, compare-tray names truncate on one line, details sheet head stays visible while scrolling.
- Impeccable flagged `bounce-easing` (advisory) because the keyframe was named `daylight-bounce`; the motion never overshot. Renamed `daylight-thinking-rise`; re-scan returns `[]` for :8894 and :8893.
- Final desktop check (1366px): 72 plans, 147 buttons, page 13,253px, no horizontal scroll. No model calls in this round (thinking state checked with a simulated pending turn).

## Round 3 (owner feedback on the polish round)

- Bug fixed: Plans could not be scrolled with a mouse or trackpad when opened from the conversation. The conversation locks page scrolling (`body.chat-mode{overflow:hidden}`, it scrolls its own reading area) and the lock stayed on for Plans. Earlier checks scrolled from script, which ignores the lock, so they missed it. Plans now sets `body.plans-page` and the page scrolls; checked with real wheel input at 375px and 1366px, with the side chat staying pinned.
- Conversation column widened: `--reading` 720 → 880px (text lines capped at 70ch).
- One type family in the conversation: questions are Atkinson Hyperlegible 21px bold (20px on phone) instead of 28px Fraunces; display serif stays for page titles, the landing and plan amounts.
- The “more below” arrow moved from the centre (where it covered answer buttons) to the right edge of the column, with a raised edge.
- Soft 20–28px fades where the conversation scrolls under the progress bar and the composer, so half-cut buttons no longer show a hard edge. Off in print.
- No model calls; long-conversation state simulated in the page.

## Round 4 (owner feedback, November 6)

Owner decisions (scoped to :8894): remove the inline sharing notices in the chat (“About the plans you’re viewing. Sending shares…” and “Send shares relevant chat and profile details with OpenAI.”). Privacy & saving now names the provider and states that Send on the Plans page also shares the plans being viewed. No written requirement mandated the inline notices; this is recorded as an owner decision.

- Plans top reordered: Back to my conversation above the title; year in the title; chat toggle beside it; one short banner (“Want plans checked against your situation?”) with Continue my conversation; then filters and plans. The data-date / not-ranked / 2027 sentence and the “Not confirmed yet” explanation moved into About this plan data. Count line shows only when a filter narrows the list.
- First plan card top: 512px at 1440 (chat open), 709px at 768, 895px at 375 (was ~1,040 at 375).
- Toolbar: no surrounding card; one row of four from a 700px panel; two columns on phones. Removed older media rules that overrode the container queries.
- Compare: a single table, one column per plan with column dividers; differing rows shaded; identical costs as rows under “The same for both plans”, value centred across columns.
- Top matches: when the backend supports a recommendation, Plans opens on “Your top N” with numbered cards (1, 2, 3) in the backend order and a line naming the priority used. Display only; order comes from `recommendation.top_three`. Not exercised live (needs a completed conversation).
- Chat replies: simple Markdown tables, bullet and numbered lists, and **bold** render as real elements built from text nodes (no HTML parsing). Plain replies render as before. Checked with a stand-in DOM, including a table that begins with a stray divider line.
- Thinking dots: pill was shorter than the dots’ travel; now 32px tall, rise 4px, clipped to the pill.

Plans chat failure reproduced (1 Send = 2 model attempts): both attempts rejected with `missing_evidence` (“The insurance explanation needs reviewed evidence.” or the provider-access variant). Not a one-off. Backend wording/evidence validation, shared with :8893; not changed in this round pending owner decision.

## Round 5 (owner, November 6): Plans chat fix and results layout

**Backend (shared by :8893 and :8894; owner-approved).** Cause of the Plans chat failure: for compared plans the composer received only premium, deductible and yearly limit, and a reply could cite at most three facts, so a "what's the difference" answer could not cite what it compared and failed `missing_evidence`.
- `plans_context.rehydrate`: a selected or compared plan now carries every server-projected field shown in its details or the compare table, plus its published plan type. Other visible plans carry identity only (unchanged). Held fields still carry no value.
- `plans_context.context_evidence`: adds one citable `published_plan_listing` fact per selected/compared plan (`plan-type:<id>`), with the same dated-reference caveat and `review_state: reference` as the fields.
- `natural_agent`: on turns that include plan facts, `evidence_refs` may hold up to 8 (schema and validator); all other turns keep 3. Compose instructions: cite the plan facts behind each value or type stated; describe network rules only with cited educational evidence. No safety check was removed or loosened.
- New test `test_compared_plans_carry_displayed_fields_and_listing_type_only`. Plans tests 34/34 pass. The 29 test files that touch evidence_refs show no new failures: every failure seen also fails on an untouched copy of the original code (Python 3.10 environment gaps such as `fromisoformat('…Z')`).
- Takes effect after 8893 restarts (`Restart Daylight 8893.command`).

**:8894 Plans layout.** One-line title “Medicare Advantage plans” with “Collier County, Florida · 2026 plans” in smaller text beside it; left filter column (search, plan type and drug coverage as radio buttons, Clear filters); a results bar with the plan count and Sort by; cards unchanged. Ask Daylight is now a 640px panel over a dimmed page at every width (full screen on phones), opened from the header button, a floating “Ask Daylight” button, or “Ask Daylight about these plans” on the compare page (pre-fills the question). First plan card: 442px from the top at 1440px, 703px on a 375px phone.

Why only Medicare Advantage: the Plans page reads the approved D91 display catalog, the 72 Collier County 2026 MA offerings. Standalone PDP research data (D78) is not approved for display; there is no Medigap pricing data.

## Round 6 (owner, November 6): D97 Plans filters write the profile

**Backend (shared :8893/:8894, conversation path only; not the plan data layer).**
- `natural_flow`: a `choice` action may carry `source: "plans_filter"` only for `PLANS_FILTER_QUESTIONS` (T01, RC01, T03, RC03, T05, RC04, T06–T10) and only with `aiConsent` false; the label is checked, stripped before the existing flow, and recorded as provenance method `plans_filter` (`natural_state.METHODS`). Status stays `user_reported`, so readiness and ranking can use it.
- `natural_agent` compose instructions: a `plans_filter` report is the person's report; confirm it once in plain words the first time it matters.
- New `tests/test_plans_filters.py` (4 tests): free labelled answer with no model call; filter answers alone reach the plan-review checkpoint; the composer sees the label; the label is refused outside its narrow shape. Plans suites 38/38 pass; other suites show only failures that also occur on the untouched code.
- Needs the 8893 restart (`Restart Daylight 8893.command`); until then the old server refuses filter saves with “Unsupported conversation action”.

**:8894 Plans page.**
- Plan kinds above the title: Medicare Advantage (current), Medicare Supplement (Medigap) and Part D drug plans marked “Coming soon”.
- Header: title, ZIP chip (edit → T03, with county choice for multi-county ZIPs from the local ZIP reference), Save progress (opens Privacy & saving), Ask Daylight.
- Banner keeps “Want plans checked against your situation?” with **Check plans for me** (existing review checkpoint, no AI) and Continue my conversation.
- Filter pills: All filters, Add doctors (T06), Add Rx drugs (T07), Add pharmacy (visit only), Monthly premium (display filter with counts, plus T09 cost preference), Plan benefits (giveback, $0 deductible, $0 primary care, drug coverage; display only), Plan type (display only), Year: 2026 (RC03; 2027 coming soon). Each opens a panel with the control on the left and “Why it matters” / “Good to know” from the reviewed baseline and readiness content, plus “Ask Daylight about this”.
- Left column: company search and drug coverage (unchanged) plus “Your details” (ZIP, year, doctors, prescriptions, pharmacy, cost preference) with “Entered here · to confirm” on `plans_filter` items. Collapsed on phones.
- Plan cards list “Your doctor(s) / prescription(s) / pharmacy: not checked yet” once added.
- Check plans for me: sets goal T01 = compare if needed, then lists only the readiness items still missing with their reviewed questions and options; when complete, “Review and confirm” opens the existing review in the chat panel. Confirming yields the handoff, priorities and the numbered top picks.
- Checked: 1440px pills on one line, first plan 597px from top; 375px no horizontal scroll, first plan 932px. Premium $0 → 52 of 72; benefit counts 30/57/47/61.

## Remaining gaps (honest)

- Captured-details line (“Noted: …”) not built: accepted captures are backend-internal and not returned to the page.
- Conversation fixes the model calls exposed (asking for a year already given; acting on employer coverage) are backend/policy work, not UI; not changed.
- Screen font sizes: 17 px values plus 4 display clamps, not the plan's ≤12; remaining display steps belong to preserved views.
- `!important`: the decorative ones in the copied CSS are inert under the finish layer; those for hidden, print and reduced motion are kept.
- Landing trust line held for counsel (owner decision). Atkinson Hyperlegible 2019 kept (owner decision); key plan amounts use Fraunces.
- Privacy dialog wording unchanged (restyled only); essential privacy copy is not edited without owner review.
