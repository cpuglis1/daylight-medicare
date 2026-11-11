# Daylight Plans product specification

November 4, 2026 · D92 · Proposed for the :8893 advisor · Operate and Read modes

## Product decision

Build **Plans** as a second workspace in the existing advisor. The person arrives with their conversation and profile intact, confirms one editable decision summary, and sees up to three supported recommendations with concrete reasons and tradeoffs. A prominent **All 72 retained plans** view keeps the rest inspectable. Chat remains alongside the work and can close without losing the draft, history, selected plans or scroll position.

The interface should help someone answer four questions: **Why consider this plan? What would I give up? What still needs checking? What can I do next?** A result that helps someone keep their coverage or defer a change is a successful outcome.

The 72 identities are retained 2026 Collier Medicare Advantage offerings, not a verified complete market and not 72 personally available options. Original Medicare, Medigap, standalone Part D and other coverage paths remain visible in the earlier path decision and through **Revisit coverage paths**. This workspace cannot silently make Advantage the recommendation because it has the most prepared data.

## Current evidence and release modes

The [assessment](ASSESSMENT.md) records the inspected implementation. The exact r13 candidate has 720 published-field dispositions: 568 published candidates, 141 held cells, and 11 not-applicable cells. Its 288 fictional-example dispositions contain 200 numeric candidates and 88 holds. All 229 held benefit/example cells suppress amounts. These are preparation and mechanical verification results, not consumer acceptance.

| Mode | What the person sees | Ordering and actions |
| --- | --- | --- |
| Design study, this packet | Fictional plans and explicitly labeled example conversation | Demonstrates the intended interaction only |
| Current unaccepted catalog | Internal research access; consumer entry explains that plan results are being prepared | No consumer rendering of candidate amounts or real personal ranking |
| Published display accepted | Dated 2026 catalog, released terms, explicit held cells and separately labeled fictional examples | Exact ID order by default; only separately permitted explicit sorts; browsing is not fit |
| Personal comparison accepted | Accepted findings for the confirmed person, scope and checks | User-selected comparison, with affected conclusions held |
| Recommendation accepted | Up to three recommendations within the disclosed retained universe, reproducible reasons, tradeoffs and open nonmaterial details | Simple priority rule below; no automatic enrollment |

Display acceptance never grants personal comparison, ranking, recommendation, quote or enrollment. A known material conflict holds its dependent conclusion. A missing optional extra does not freeze an otherwise supported decision. The backend maintains the field/capability distinction; the consumer sees a concise explanation of the consequence.

## Journey and navigation

1. **Continue the existing conversation.** Capture clear reports naturally, clarify consequential ambiguity, and preserve subject/time scope. Use all 41 meanings conditionally; do not add a second questionnaire.
2. **Review before seeing recommendations.** “Use this information to compare plans” opens one editable summary: beneficiary, county and intended year, current coverage/path, doctors/sites, medicines/fills/pharmacy, relevant eligibility/assistance/travel, must-haves, priorities, and unresolved items. Present supplied values first. Unknown is a real state, never a selected default.
3. **Confirm and see plans.** This named action confirms the displayed profile revision and priority order. It is not permission to save, contact someone, share a family member’s data or enroll. An unsent draft stays available with **Return to draft**; do not silently omit an unfinished correction from a confirmed case.
4. **Orient in the Plans workspace.** Show “Plans for your priorities,” Collier County · 2026, the relevant confirmed priorities, **Edit profile**, and a one-line scope/status. Open the existing conversation in the right panel on first arrival; preserve the person’s later close preference for this visit.
5. **Inspect, compare and learn.** Read the three recommendations, open a detail, compare up to three plans, inspect a definition, or ask about a field. The plan and the active question stay associated.
6. **Resolve a consequential check.** A doctor, drug, eligibility or condition gap offers its specific supported check or an official/manual next step. A check returns a receipt, result, date and limitation. No “checking” animation without a real job.
7. **Choose a next step.** Review one plan’s decision summary; inspect evidence and outstanding checks; prepare a checklist or follow an approved official route. Enrollment/transfer becomes available only through an actually supported, separately authorized service. Keeping coverage and deferring remain available.

Top-level navigation is **Conversation | Plans**. Profile review opens within either workspace, not as a third workflow. On Plans, secondary navigation is **Recommended | All plans (72) | Compare (n)**. The recommendation tab can remain visible with a helpful held state; the number shown in All plans is the actual retained denominator, independent of filters or current eligibility.

## Desktop layout

At 1440px, use 40px outer gutters, a 24px divider/gap, roughly 880px for plans and 456px for chat. At 1280px use 24px gutters and a 400px chat minimum. Two columns apply from 1180px upward; do not squeeze three plan cards across the left side. Cards stack vertically, providing a stable sequence of comparable facts. When chat closes, the plan list grows to a comfortable maximum reading width of 1120px and centers; it does not transform into a different card grid.

```text
Daylight                 Conversation   Plans              Privacy & saving
──────────────────────────────────────────────────────────────────────────
Plans for your priorities                         Daylight · AI assistant
Collier County · 2026       Edit profile           Close chat
Lower monthly cost → lower medical limit          Discussing: Plan A / costs
Scope + current decision state                    ────────────────────────
                                                  Existing conversation
Recommended | All plans (72) | Compare (2)          + current grounded answer
Search plans                 Filters · Sort
                                                  Sources / checks
┌ Plan A · HMO · exact ID / year ──────────────┐
│ Why it appears here     Meaningful tradeoff │    Ask about this plan…
│ Premium    Medical limit    Primary care    │    [editable composer]
│ Doctors/site checks    Medicines/pharmacy   │    Send
│ Open checks with consequence                │    Privacy & saving
│ View details   Add to compare   Ask about   │
└────────────────────────────────────────────┘
  Plan B …                         Plan C …
──────────────────────────────────────────────────────────────────────────
Compare tray: Plan A · Plan B          Compare 2 plans      Clear selection
```

The plan list uses the document’s main scroll. The desktop chat is a sticky panel beneath the global navigation, with one transcript scroller and a stable composer. The comparison tray occupies only the plan side while chat is open and reserves layout space; it must not cover the last card, its action row or keyboard focus. Closing chat returns focus to **Open chat** in the Plans toolbar. This is the sole global chat launcher on this surface; field-level **Ask about** actions remain contextual.

On short desktop viewports such as 1280×720, compact the chat header and idle composer instead of sacrificing the answer area. Keep an approximately 58px idle textarea, a single-line action and a useful answer passage visible; the draft can grow when needed while retaining transcript access. The first design review found and corrected this height-allocation issue in the study.

The visual hierarchy is task → decision basis → recommendation reasons → comparable facts → deeper evidence. Avoid a large marketing hero, match-score gauges, insurer-colored cards, “best seller” badges or promotional benefits overpowering access and costs.

## Card anatomy and information hierarchy

Use raised paper, a quiet 1px border and 12px corners. Reserve pills for the small filters or state controls; the plan itself is a spacious rectangular card. Use Fraunces for the workspace title and Atkinson Hyperlegible for facts, actions and numbers. Body text is 18px; supporting labels at least 16px; numbers use tabular figures. Display no carrier logo until its actual asset/use requirements are settled; names are sufficient.

| Layer | Required content | Interaction |
| --- | --- | --- |
| Identity | Exact plan name, carrier, HMO/PPO/etc., drug-coverage category, year and full offering ID | View details; restrictions visible next to identity |
| Decision | One evidence-backed fit reason, one meaningful tradeoff, applicable restriction, next material check | “Why this plan?” opens reasoning and evidence; no percentage fit |
| At-a-glance costs | Monthly plan premium; annual in-network medical spending limit; ordinary in-network primary care | Qualifiers remain visible; “plan premium” never implies all Medicare cost |
| Personal access | Named doctor/site status; exact medicine/fill/pharmacy status; relevant travel/access status | Expand item-level findings; unknown and failed are different |
| Action row | View details; Add to compare; Ask about this plan | Whole card is not one ambiguous click target |

The first card should begin in the first viewport at common desktop sizes. Show approximately one full card and a useful start of the next, rather than shrinking text to force all three on screen. All three have equal visual treatment. Numbering denotes the current ordering only; stable reason labels explain what changed when priorities change.

**All ten prepared fields belong in details**, in consistent groups: monthly premium and separate Part B reduction; medical deductible and medical spending limits; Part D deductible; primary care, specialist, hospital, emergency and urgent care. Medical limits retain in-network versus combined scope. Drug deductible restrictions retain applicable tiers/conditions. A held range, cost or deductible shows **Needs verification** with its reason and a useful check, never $0, a dash implying no cost, or a concealed nominal amount.

Hospital terms retain the charge unit, counted day bands, admission scope, authorization/referral assumptions, deductible issues and exclusions. A $2,200 per-admission term cannot be multiplied by days. A Part B reduction is shown separately, not subtracted into a universal net-premium claim.

Dentist, hearing, vision, OTC and other supplemental benefit details, referrals/authorization, out-of-network routine care, travel and quality context are progressively disclosed **when released and relevant**. They are not established by the ten-field packet. Contract-level quality is labeled with its year and grain, never a doctor-network proxy or automatic ranking bonus.

## Detail, comparison and teaching

**View details** replaces the list within the left pane, with **Back to plans** restoring the same card, filters, compare selection and scroll anchor. Chat stays in place. Detail sections are **Overview · Costs · Doctors & medicines · Rules & extras · Sources**; every section remains reachable without chat. A visible material restriction belongs in Overview as well as its detailed section.

**Compare** aligns the same rows for two or three chosen plans. Lead with the person’s ordered priorities and the largest supported tradeoffs, then access, recurring cost, medical exposure, scenario costs, restrictions, extras and sources. “Show differences” may reduce repeated detail but never hides unknowns, restrictions or noncomparable bases. The current plan can be included when its exact identity/year is resolved; it is not automatically displaced by the top three.

**Cost examples** are a distinct section labeled “Fictional examples, not your expected spending.” Initially preserve the existing 12-month premium, four-visit, three-day-admission and four-day-admission methods exactly. Show assumptions alongside each result. Do not add them into an annual total, forecast utilization or relabel them as a personalized quote. The design may compare the third and fourth hospital day visually after the exact display/method scope is accepted.

**Definition behavior:** underline the term with a restrained dotted rule and provide a text-labeled explanation control. On fine pointers, hover or keyboard focus opens a short definition; tap/click pins an accessible popover. Escape dismisses it; moving into its content does not close it. Essential conditions stay on the card. No action is hover-only. A simple tooltip has no interactive children; a pinned popover with **Ask about this** is a labeled nonmodal dialog with a visible Close control and predictable focus return.

Each definition contains the plain-language meaning, the relevant scope/exclusion, and **Ask how this affects my decision**. For example, medical spending limit explains its medical/network scope and what is excluded; premium explains the recurring plan charge and separate Part B obligations. This newly requested glossary is local reference material, not an automatically inserted conversation lesson. Generated conversational explanations continue through the existing D86 model and validation pipeline.

Clicking **Ask about** opens chat and stages an editable prompt such as “Explain this plan’s medical spending limit and what it excludes.” It attaches the exact plan/field/year reference and preserves any existing draft, offering **Add to draft** or **Keep my draft** when needed. It never sends automatically.

## A chat that knows what is on screen

Use explicit structured view context, not screenshots or a stream of raw page content. The browser updates a small local context store immediately on plan focus, visible-card changes, section changes, comparison selection and scenario selection. This supplies the visible **Discussing** line. It does not transmit to an AI provider during scrolling, hovering, typing or navigation.

On deliberate **Send**, attach a bounded snapshot under a new versioned permission, proposed as `plans-context-v1`, alongside the existing permitted conversation/profile context. The first send’s inline privacy wording explains that the current plans, selected comparison and question context are included; do not add a confirmation modal. Existing natural-context consent alone does not silently cover this new view payload.

```json
{
  "context_version": "plans-context-v1",
  "view_revision": 23,
  "route": "plans/detail",
  "scope": {"year": 2026, "county_fips": "12021"},
  "catalog_release_ref": "server-issued reference",
  "decision_ref": "server-issued reference",
  "profile_confirmation_ref": "server-issued reference",
  "focused_offering_id": "2026:Hxxxx:xxx:xxx",
  "visible_offering_ids": ["bounded to six"],
  "compare_offering_ids": ["bounded to three"],
  "active_section": "costs",
  "selected_field": "medical_maximums",
  "scenario_id": null
}
```

These fields are UI hints, never source authority. The server authenticates the visit/owner/CSRF, validates IDs against the exact allowed manifest, rehydrates permitted evidence, verifies confirmed profile and decision revisions, and drops any client-supplied amounts, benefit text, arbitrary URLs or approval claims. Evidence retrieval is bounded to relevant plans/fields. Do not send all 72 rows or all raw profile facts every turn.

Resolve “this plan” by explicit field attachment, then focused detail, then single selected plan. When several visible plans make the reference ambiguous, ask a short clarification naming them. Scroll position alone cannot choose someone’s intent. Compare selections represent view state; favorites, dwell time and clicks do not become preferences, must-haves or consent.

An in-flight response is bound to the submitted context, even if the person scrolls or switches plans. Label it “About Plan A” and offer **Use current view**; do not relabel it as an answer about Plan B. If material profile/evidence authority changes, suppress stale personal conclusions and show a refresh action. The model can explain a deterministic result but cannot reorder plans, approve a held fact or invent a completed lookup.

Closing chat hides the panel only. Same-visit history and draft remain; reopening restores them. Sensitive view state and conversation remain within the existing visit-memory policy, cleared with visit expiry/reset. No new raw-chat persistence, analytics payload of medicine/provider names, or family/human sharing is authorized. New independent fact checks execute only through accepted capability tools and the existing permission/budget boundaries. No paid model work is triggered by card browsing.

## The simple recommendation method

**Use constraints first, then compare accepted values in the person’s explicit priority order.** This is lexicographic ordering: the first priority decides; the next resolves equality; exact offering ID resolves remaining ties only for display. It is easy to reproduce and explain. It is deliberately not a prediction of the best future outcome or a weighted fit score.

### Inputs

Reuse `build_comparison_profile(guide, record)` and its normalized digest, item revisions, report provenance, subject and time scope. New metadata stores a **confirmed decision snapshot** and an **explicit ordered priority list** with existing report references. This does not add new intake meanings. T10 is presently unordered: capture an order only when the person actually stated it, or let them review **Move up / Move down** controls at the end. No preselected financial preference and no ordering inferred from answer order, click order or phrasing confidence.

Must-haves require explicit confirmation. Naming a doctor is not automatically an instruction to exclude every other network; distinguish “must keep” from “would prefer.” Clinical needs and required coverage still receive material checks even if not hard filters. Unknown mandatory dependencies create pending checks, never failed fit.

### Procedure

1. Bind subject, intended year, county, coverage path, current arrangement and confirmed report revision. A 2027 request cannot use 2026 facts. “Soonest” cannot supply an invented year.
2. Use the exact retained universe and evaluate applicable restrictions and material personal checks: service area/enrollment eligibility, SNP/residence rules, drug-coverage arrangement, doctors/sites, medicines/fills/pharmacy, travel and other consequential constraints. Separate `meets`, `known_conflict`, `needs_check`, and `outside_scope`, preserving every identity and reason.
3. Require current accepted findings and method/purpose authority for each dimension actually used. Published-display acceptance cannot supply ranking authority. Never rank an assistance-dependent nominal charge as the person’s cost.
4. Select comparable, numeric, accepted dimensions in the confirmed order. V1 supports plan premium and in-network medical spending limit; a later approved extension may add an exact ordinary-visit or hospital scenario dimension. Access and eligibility are checked conditions, not point bonuses. An unsupported preference such as dental coverage creates a targeted evidence task before an affected recommendation.
5. Sort the supported candidate set using that ordered vector, all lower-is-preferred in v1, then ID. Return up to three. If one or two qualify, show one or two. If none qualify, show the concrete conflict/check and the complete catalog. Never pad the list.
6. An unresolved potentially qualifying offering can change the top three. In v1, hold the **global top-three claim** until that material uncertainty is resolved; optionally show a neutrally ordered **Plans ready to compare** group clearly separated from recommendations. Do not quietly drop unknowns and call the remainder “best.” Later certified bounds could prove that a missing value cannot affect the result, under a separately reviewed method.
7. Return the chosen order, per-dimension values and sources, must-have results, reasons for inclusion, meaningful tradeoffs, tie groups including those crossing third place, all-plan dispositions, and exact dependency versions. Equal vectors are equal under this method; disclose the ID tie-break and link **See equally ranked plans**.

A low-premium-first ordering may place a $0-premium plan ahead of a $1-premium plan even when the medical limit is much higher. The review must make this consequence explicit. If the person wants a balanced tradeoff rather than strict priority, show the comparison and ask which dimension should lead; do not invent a mathematical exchange rate. This is a scoped, explainable starting heuristic, not a universal fit model.

### Explanation

Each recommendation has a short explanation assembled from deterministic reason records, then optionally explained conversationally with the same sources. A synthetic example: “You put monthly plan cost first. A and B tie at $0, and A has the lower in-network medical limit. C costs more each month but has a lower medical limit.” The interface shows that tradeoff before an enrollment action. **Why not this plan?** explains a known conflict, lower position on the agreed priority, equal-rank tie or open check without asserting poor fit from missing data.

No carrier compensation, appointment, referral fee, conversion signal, enrollment likelihood, commercial availability or related proxy is an input, tie-break or explanation feature. Keep fulfillment downstream of the decision. Ranking and neutral sorting are different controls: choosing a sort changes the catalog view, not the stored recommendation or profile.

The packet’s [executable reference](reference_recommender.py) demonstrates this procedure with fictional IDs only and always returns `consumer_usable: false`. Production admission, exact source loading, individual verification and confirmation tokens remain explicit implementation work; no boolean supplied by a browser can unlock them.

## Catalog, filters and recovery states

Search matches name, carrier and exact ID. Filters are explicit controls for plan type, drug inclusion and stated constraints, with counts and **Clear filters**. Special-needs/residence offerings remain inspectable with qualification wording. A default All plans view has no hidden commercial or eligibility filter. Show “18 of 72 shown” and separate known conflicts, pending checks and scope exclusions. Searching all plans is available even when fewer are displayed.

| State | Presentation and recovery |
| --- | --- |
| Unconfirmed profile | Browse permitted facts; **Review and confirm** before personal ranking |
| Year unsupported | Keep requested year; explain available 2026 research; offer official research path; no automatic fallback |
| Held field | “Needs verification,” exact practical consequence, evidence/check action; amount absent |
| No released catalog | Useful preparation/official next action; do not show 72 “available” consumer results |
| Pending personal check | Identify item and check status; usable unaffected facts remain readable |
| Zero or fewer than three results | Show actual count and reasons; no fabricated alternatives or forced relaxation |
| Tied third place | Label equal under the method and expose every tied option |
| Empty filter result | Explain active filters and offer Clear filters; preserve all-plan count |
| Profile correction | Mark affected recommendation stale; keep draft/selection; reconfirm changed inputs then recompute |
| Source revoked/expired | Suppress dependent amount and result immediately; retain historical record separately |
| AI unavailable | Browsing, definitions, comparison and deterministic explanations still work; retain draft |
| Check transport failure | “Could not complete this check”; retry only under actual tool policy; no guessed result |
| Session expired/deletion | Preserve safe local unsent text where permitted; rebind/review before personal results; no cross-session leak |
| Existing plan unresolved | Show reported current coverage and the missing identity/check; do not assert switching saves money |

## Tablet, phone and accessibility

At 768–1179px, plans use the full width and chat opens as a labeled overlay drawer up to 440px wide. Give it a Close control, Escape, focus containment while modal, and return to the opener. At less than 768px, chat becomes a full-height sheet with “About Plan A / field” at the top and **Back to plans**. Retain the underlying card anchor, selection and draft. Avoid a narrow one-third chat column on a phone.

Cards become one column with cost rows in consistent label/value pairs, actions wrapping naturally, and no clipped plan names. The mobile compare view stacks each dimension with the two or three named plan values, rather than shrinking a desktop table. Keep a compact **Compare (n)** action and **Open chat** within reach without obscuring content. Use dynamic viewport height and safe-area padding for the keyboard.

Design for 200% zoom and 320px reflow, 44px touch targets, visible 3px focus outlines, semantic headings/list/table controls and descriptive names. Maintain ≥4.5:1 body contrast and ≥3:1 large-text/control contrast. Use text plus color for held/verified/selected states. Honor reduced motion; no decorative animation. Announce only meaningful result/count/status changes, not scrolling or each context update. Hover content must remain accessible on keyboard and touch.

The visual study is responsive design evidence, not a completed accessibility audit. Implementation requires actual keyboard, screen-reader, zoom, tablet/phone, long-name, failure and focus-restoration checks.

The definition interaction follows W3C’s dismissible, hoverable and persistent content guidance, and the narrow layout follows its 320 CSS-pixel reflow criterion. [W3C hover/focus guidance](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html), [W3C reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).

## Implementation boundaries and sequence

| Increment | Concrete implementation | Exit evidence |
| --- | --- | --- |
| 1. Profile-to-decision seam | Add a confirmation service over the current adapter; bind subject, scope, ordered priorities, constraints and normalized digest; confirm via existing owner/chain/CSRF flow | Correction, stale-tab, helper/beneficiary and unknown tests; no new questionnaire or persistent raw transcript |
| 2. Catalog projection | New exact r13-derived serving revision plus purpose-authority loader; retain every identity, hold and source/method dependency | 72-ID parity; all 229 held amounts absent; expiry/revocation/mismatch fail closed; consumer-display decision recorded |
| 3. Plans shell | Add scoped Plans view to :8893; reusable cards/details/compare/definitions; existing chat mounted once in the right panel | Desktop/tablet/phone and keyboard behavior; drafts, history, scroll and profile preservation; no protected-variant changes |
| 4. Context bridge | Local view state + minimized Send-bound payload; server rehydrates permitted facts and binds responses to view/profile versions | Forged IDs/amounts, wrong owner/year, stale response, prompt injection, no navigation-to-provider traffic |
| 5. Personal checks and heuristic | Bind accepted relevant eligibility/access/drug/condition findings; implement reviewed strict-priority ordering as separate method revision | Deterministic top three or explicit hold; ties, fewer-than-three, candidate coverage, baseline and commercial invariance |
| 6. Focused release | Exact product, source-use, independent domain/method and serving review for named capabilities | Approved receipts, dates/expiry and rollback; observed consumer decision understanding and owner conversational review |

Proposed application files belong under `alternatives/advisor-first/` (for example `plans_service.py`, `plans_context.py`, `recommendation_policy.py`, and scoped `web/plans-view.js/css`). These are proposed names, not current components. Reuse `ComparisonService`, `comparison_profile`, existing identity/verification seams and rendering/session machinery. Do not change the pinned shared engine or load research rows directly into the model.

Suggested service contract: server-owned catalog read; confirm-decision action; recommendation read/refresh bound to confirmation; explicit check execution; chat Send with bounded view context. Personal data stays in request bodies/private owner-bound memory, never URLs or public caches. Cache public facts by exact accepted release and scope. Use no LLM on the catalog or ranking critical path. Target warm catalog p95 <300ms and local deterministic ordering <50ms for 72 rows; these are proposed budgets to measure, not observed claims.

## Acceptance and product proof

Functional release requires profile reuse without re-entry, up to three supported recommendations, all 72 retained identities accessible, full key-term/hold preservation, item-level access checks, sources, working compare/details/popovers, context-correct chat, draft retention and correction invalidation. Supported sorts and recommendation priority order must be visibly distinct.

Safety/reliability tests include all-unknown profiles, missing priority order, wrong year/county/subject, SNP and five Erickson residence restrictions, MA-only with unmet drug arrangement, assistance-dependent costs, the three premium disputes, selective hospital deductible, daily versus per-admission charges, duplicate medicine names/different strengths, clinician versus site identity, stale evidence, revoked authority, a fourth plan with missing data, exact-rank ties, commercial payload rejection and unapproved AI context.

Use the existing two r7 cases as regression examples within the all-72 scope, not as the new product denominator. Preserve the sealed two-plan pilot and r9/r4 obligations.

For owner review, demonstrate: arriving from chat; correcting a priority; understanding one cost/access tradeoff; seeing why a missing check matters; finding a non-shortlisted plan; comparing two plans; asking “what does this mean?” about the actual field; closing/reopening chat; and selecting a useful next step or keeping coverage. Participant understanding, correction success, effort, supported task completion and staff minutes are the product measures. Conversion is not the ranking objective. No agent-run paid conversations or claim of conversational naturalness accompanies this design packet.

## Requirement trace and decisions

**D92** adds the confirmed in-app Plans destination, stacked cards, closable right-third chat, view-aware discussion, all-plan access, contextual explanations and a simple top-three design. **D86/D87** preserve natural capture, one end confirmation, chat continuity and profile/evidence separation. **D91** preserves exact all-72 scope, the r13 display candidate, capability-specific acceptance and material holds. **D64/D73** preserve economic independence, path-first decisions, minimal consequential intake, inspectable reasons, permissioned continuity and keep/defer outcomes. **D49/D54/D55/D57** preserve teaching, confirmed consequential reports, stable progress and storage boundaries.

This proposal changes the Plans surface’s layout relative to the earlier Ask overlay and adds the requested local definitions. It does not replace the existing Conversation surface or reintroduce canned chat lessons. The owner has confirmed the destination and general composition; detailed design/method and actual consumer release are not recorded as accepted. Source-use owner and independent qualified Medicare reviewer remain unassigned in the inspected acceptance registry.
