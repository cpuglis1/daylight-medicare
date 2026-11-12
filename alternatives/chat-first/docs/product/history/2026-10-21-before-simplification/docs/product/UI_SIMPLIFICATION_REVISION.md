# Focused UI simplification revision

October 21, 2026 · **Proposal only. Not implemented.** No app/data changes or paid AI calls. Preserve the approved arrival/photo, sun/name, fonts, palette and sole tagline **Your coverage, plain as day**. D65 records the owner's direction; exact grouping and transitions below await approval.

## 1. Recommended changes

| Owner feedback | Proposed revision |
|---|---|
| Header is too cluttered | Existing sun + Daylight Medicare only, then the stable four-phase track, then the question. Remove routine goal/familiarity/save chips, duplicate assistant identity, top utilities and generic goal-preface. Put concise relevant teaching beneath the question. |
| Remove Local AI warning | Remove consumer usage text from page **and** chat. Keep the persistent aggregate **$1/UTC-day cap**, reservations and no automatic retries unchanged. Usage remains available through developer diagnostics. An actual service/cap failure still gets a brief actionable message and preserves the draft. |
| Replace large inline Ask/input block | One compact authored sun-agent icon + **Ask Daylight · AI assistant** below Continue/Back. No default giant textarea, duplicate help heading or repeated processing paragraph. Something else still accepts an answer through the overlay. |
| Chat needs more room | Desktop 560–600px wide, up to viewport height minus 32px; overlay over the map, never a new column. Compact title/Return, transcript priority, reachable composer. Phone uses available visual-viewport height with 8–12px safe insets, instead of the current ~96px top gap. |
| Map should show coverage relationships | Only Medicare, A/B grouped as Original, D, C/Advantage, Medigap. Vocabulary stays inline or in optional explanations. Reveal taught pieces only. |
| Too many clicks/definition pages | Merge teaching with existing relevant questions; group naturally related fields under one Continue. No compulsory “Got it” pages, no invented health questions and no automatic selection-triggered advancement. |

Routine **Your guide & privacy** moves to one consistently labeled secondary utility below task content/footer. It retains answers/edit, save status, optional sensitive-note choice, delete and scoped **Start a new guide** confirmation. Do not replace it with a mystery icon. Active save failures/conflicts remain visible at the affected task; required privacy information cannot disappear.

## 2. Focused findings

- **Clutter is structural:** `guide-core.js:60` adds the context strip, assistant identity and explanation before the heading. `index.html:28` adds header utilities and the D63 spend row. `composer()`/`actions()` repeat input/help controls on most tasks (`guide-core.js:29–30,65`).
- **The little olive marks were reproduced:** `styles.css:154` retains the old empty circular `.choice::after`; `approved.css:4` changes choices from flex to block. In the current render the pseudo-element is **inline**, retaining a 21px circle's border/flex declarations. That produces the narrow mark after choice text. Scope-remove/rebuild this indicator; do not assume an icon-font failure.
- **Doubled track numbers were not reproduced:** at 1331×735 all four items had `list-style:none`, `display:flex` and one visible custom number. `app.js:415` creates one number per phase. Keep a regression guard against native/custom duplication without inventing an observed root cause.
- **Fonts loaded:** Atkinson and Fraunces were available; no replacement character was found in the inspected question. The tiny cropped “end re” fragment still cannot identify its exact control. The reproduced choice artifact is concrete; that fragment remains uncertain.
- **Lecture runs are real:** `guide-state.js` queues lessons, and contract `lesson_defaults` traverses L02–L11 through ten definitions before another question. Beginner drug browsing also inserts five teaching-only pages.

Inspection used a separate fresh question, entered/saved no answers and sent no AI requests; the owner's tab was preserved. This is not a new broad audit.

## 3. Before → proposed wireframes

### Question workspace

```text
CURRENT                                     PROPOSED
┌ sun Daylight Medicare  Info / Start over ┐ ┌ sun Daylight Medicare               ┐
│ AI spend / holds / cap / reset           │ │ 1 Goal 2 Situation 3 Options 4 Next │
│ 1 Goal 2 Situation 3 Options 4 Next      │ ├───────────────────┬────────────────┤
│ Goal / Familiarity / Visit / Review-edit │ │ Actual question   │ Core map       │
│ Daylight · AI assistant                  │ │ Short relevant    │ taught pieces  │
│ Generic preface                         │ │ explanation       │ only           │
│ Actual question                  Map    │ │ Choices           │                │
│ Choices                                 │ │ Something else    │                │
│ Continue / Back / Ask                    │ │ Continue   Back   │                │
│ Or tell Daylight…                       │ │ [sun] Ask Daylight · AI assistant  │
│ Large textarea / Review / long notice   │ └───────────────────┴────────────────┘
└──────────────────────────────────────────┘   Your guide & privacy [secondary]
```

Question is the first heading after the track. Relevant teaching/material reason follows it in one or two sentences; no obvious goal-preface. Phone order: brand → stable track → question → compact teaching/map → choices → Continue/Back → Ask. Do not reserve a large empty map before anything has been taught. Arrival keeps its approved hero, secondary resume and compact Ask; no new slogan or unnecessary arrival track.

### Ask overlay

```text
CURRENT: 466px, much fixed text              PROPOSED: 560–600px when available
┌ AI title + long Return button ┐           ┌ [sun] Ask Daylight · AI assistant [Return] ┐
│ repeated context / intro      │           ├───────────────────────────────────────────┤
│ Questions heading             │           │ Actual question / answer-mode context     │
│ large follow-up block         │           │ Answer first; source; useful follow-ups   │
│                               │           │ Conversation gets remaining height        │
├ composer / Send              ┤           ├ [message…………………………………] [Send]             ┤
│ long privacy paragraph        │           │ AI may make mistakes. Privacy details     │
│ long spend paragraph          │           └───────────────────────────────────────────┘
└───────────────────────────────┘
```

Use a static SVG based on the existing sun rays/disk, with restrained agent character; no Unicode sun, emoji or icon font. Retain the main brand mark. Give its labeled launcher a 44px target. Target compact header ~64px and resting composer/disclosure ~110–140px, leaving the rest for reading; verify these proposed dimensions on short screens and with keyboards.

**One overlay, two clear intents:** Ask opens “Ask about this step”; Something else opens “Answer this question.” Explanations do not silently change the profile. Answer mode shows editable extracted proposals and the named next task. One explicit **Confirm and continue** may replace today's Confirm receipt + separate Continue. It validates/commits then advances only because the user chose that clearly labeled action. Return/cancel records nothing. Structured choices use their existing Continue as confirmation; no AI round-trip or extra Review.

Before first transfer, retain explicit consent: submitted message/minimum context go to OpenAI, saving is separate, no ID numbers; **Privacy details** reveals actual fields/processors/limits. Offer Allow and send / Use manual choices. After consent retain AI identity, a short caution/privacy link and sources, not repeated paragraphs. Remove redundant intros/headings/spend text; keep up to two relevant follow-ups after the answer and accessible history. Opening Ask never calls a model. Preserve focus trap, Escape/Return, background inertness, exact task/input/draft/scroll/opener restoration and no guide reflow.

## 4. Core map and reveal

```text
                              MEDICARE
                     two main coverage arrangements
              ┌──────────────────┴───────────────────┐
       ORIGINAL MEDICARE                    MEDICARE ADVANTAGE
        ┌ Part A ┬ Part B ┐                        Part C
        └────────┴────────┘                   another way to get A/B
              │                               usually includes D*
        optional additions                    [no Medigap connector]
         ├ separate Part D
         └ Medigap
```

This is the **fully introduced reference**, not the newcomer's first picture. Proposed reveal: Medicare with A03; A+B/Original with enrollment/current-coverage or the requested foundation topic; D with the medicine/drug question; C with a requested route comparison; Medigap with supplement/route teaching. Introduce A+B as one concise relationship group rather than three acknowledgment pages. Use grouping, connectors and “alternative”/“optional” text, not color alone. Viewing/choosing a goal does not establish understanding or actual enrollment; reported facts remain separate.

Premium, deductible, copay, coinsurance, medical limits, extras and switching cautions remain contextual/optional explanations, **not map nodes**. Material warnings stay visible when relevant. Knowledgeable users may keep the map hidden and reopen it.

`*` Small disclosure: drug coverage depends on the exact plan. Most Advantage plans include D; only some arrangements permit a separate drug plan. Never imply universal C + standalone D or Medigap + C. Source basis checked October 21: [Medicare parts/arrangements](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/parts-of-medicare), [Original vs Advantage](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options/compare-original-medicare-medicare-advantage), [drug-plan exceptions](https://www.medicare.gov/health-drug-plans/part-d/basics/choose-coverage). This is teaching, not personal-fit evidence.

## 5. Lesson/question merge matrix

Old IDs/content remain source history. `R-*` names below are proposed presentation groups, not implemented nodes.

| Current nodes | Proposed question + teaching | Writes / picture / next |
|---|---|---|
| A01; A02/A02B | Keep four-choice goal, then recipient. Optional name appears inline for Someone I help, not on another page. | Same goal/subject fields; no map yet → A03 |
| A03 + L00 | How familiar are you with Medicare? Include one-sentence Medicare introduction. | Familiarity only; Medicare block; no mastery → goal route |
| A05 | **Recommended:** remove compulsory save stop; offer deliberate Save at utility/wrap-up with notice first. | Default unsaved, no invented answered “visit” fact; separate health-note choice |
| L02/L03/L04 + C00 | Do you have Medicare yet? Explain A/B/Original beside the question. | Same enrollment/unknown; A+B group → existing branches |
| L05 + N00 or O00 drug choice | Medicines question or browsing category, with concise D teaching. | Existing medicine status/category; introduced D → optional details or scope |
| L06 + N03; L07/L08/L09 + N04/N05 | Routine-care needs, then priorities. Explain extras and monthly vs care costs where those choices matter. | Same needs/priorities/order; no vocabulary map nodes → applicable provider/options task |
| L10–L13 + C03/O00/O11 | Current coverage/category/supplement question with route relationship and material cautions. | Existing coverage/category; only taught C/Medigap → relevant branch |
| O00/O01 → R-COMPARE | Category + browse vs personal review, two related fields, one Continue, neither preselected. | Same category/mode; selected-category teaching → intake or R-SCOPE |
| O03/O04/O04B/O05 → R-SCOPE | ZIP and year together; unique source-derived county inline. Ask county only for real ambiguity. | Same scope + reference provenance, no falsely claimed user report → held O06 or unsupported alternative |
| C03/C04 → R-CURRENT | Current coverage + understand/keep/change/add in one related unit. | Same reports; appropriate map → keep summary or change route |
| J00/J01 → R-JOB; J03/J04 → R-DATES | Current-job status + requested help; later two separately labeled employment/coverage end dates. | Existing separate fields; no assumed task/date → existing employer/creditable-drug logic |
| F00/F01/F03 | Useful summary, editable preparation, deliberate save/finish. | Same reports/receipts; no redundant final acknowledgment or contact claim |

**Education-only:** replace the automatic lecture train with requested topics: L01 choice → foundation + next-topic question → drug explanation + next-topic question → routes + next-step question. Finish after any useful piece. These are genuine learning-navigation choices, not quizzes or invented health questions; never force personal intake. Detailed teaching remains optional. No mandatory definition-only page.

Known/unknown/skipped remain distinct. Back restores each grouped task's actual inputs; edits retain independent entries and invalidate affected conclusions. Unknown location/year cannot unlock local results. A unique source lookup removes redundant confirmation, not necessary ambiguity resolution. Free-text interpretations still require explicit confirmation. Save failures/conflicts, privacy, economic independence and plan gates remain intact.

## 6. Click and screen targets

Baseline derived from the current pure `GuidePolicy` + runtime contract in memory, including actual lesson prerequisites. **Not usability measurement.** Count A01 → first F00 summary or O06 held-results state; exclude arrival Get started, typing/scrolling, optional help and endpoint actions. Selection + Continue = two clicks; two explicit choices in a group + Continue = three. Job example has both date fields filled. Proposed numbers are design targets, not measured implementation results.

| Representative route | Current screens / clicks | Proposed screens / clicks | Clicks saved |
|---|---:|---:|---:|
| Beginner: basics, finish | 6 / 11 | 4 / 8 | 3 |
| Beginner: full existing parts overview, finish | 17 / 23 | 7 / 14 | 9 |
| Beginner: browse drug plans, known unique ZIP/year | 14 / 21 | 5 / 11 | 10 |
| Comfortable: same published browse | 9 / 16 | 5 / 11 | 5 |
| Beginner: review A+B/Original and keep it | 14 / 21 | 5 / 11 | 10 |
| Beginner: current job, prepare, size unknown, dates known, drug notice unknown | 15 / 24 | 8 / 16 | 8 |
| Caregiver: beginner drug browse, optional name omitted | 15 / 22 | 5 / 11 | 11 |

Beginner browse baseline: `A01 A02 A03 A05 L00 L02 L03 L04 O00 L05 O01 O03 O04 O05 → O06`. Proposed: `A01 A02 A03 R-COMPARE R-SCOPE → O06`. Review's baseline includes the extra L05/L10/L11 prerequisite run before C03.

Overview target retains meaningful topic choices and wrap-up instead of ten definitions. Job savings remove A05/four lessons and group job context/dates. Unknown dates remain independent; an explicit “Continue with both dates unknown” is permitted, never an inferred date.

If compulsory A05 is retained, add one screen/two clicks to every proposed route. Choosing optional saving still costs that real privacy action; consent has not vanished. Free text does **not** magically become fewer clicks: today's direct inline Review → Confirm → Continue is three actions; proposed Open answer overlay → Review → Confirm and continue is also three, plus first-use AI consent in either design. Something else's extra current focus/open action can be saved. Most gains come from removing forced pages and persistent clutter.

## 7. Implementation boundary and acceptance

After approval only:

1. Patch the selected groups/teaching rules in master §§3/5/6/7, `BRANCHING_NODES.md`, `WIREFRAMES.md`, both flow-contract JSONs and acceptance cases. Amend approved DESIGN hierarchy/dimensions without changing tokens/photo/arrival.
2. Target `index.html`, `guide-core.js` render/actions/composer/proposal/utility, `app.js` Ask viewport/return, `approved.css` and the scoped legacy indicator. Keep budget enforcement in `ai_budget.py` and pricing/config unchanged; developer usage remains readable.
3. Update `guide-state.js` scheduler/grouped forms; retain source-linked facts, branch fields/unknowns and plan admission. Preserve useful old content/history, rather than deleting lessons to appear simpler.
4. Verify desktop/tablet/phone and short-height/keyboard states together; fix introduced defects in a bounded pass. Run relevant regressions and replace target counts with measured results before claiming savings.

Acceptance:

- Brand → four stable phases, one visible number each → question. No routine metadata/assistant/spend rows intervene.
- No consumer spend text in page/chat DOM; persistent shared cap, restart/concurrency safety and no automatic retries remain tested. Service failures keep the draft and a manual alternative.
- Choice marks are deliberate, no collapsed pseudo-circle; long labels and loaded/fallback fonts remain readable. Do not claim the unidentified clipped fragment fixed without evidence.
- One Continue confirms structured selections; no selection-triggered advance. Something else remains available where applicable; proposals stay editable and explicit combined confirmation names its next task.
- No mandatory consecutive definitions, invented intake or lost unknown branches. Optional learning stays optional; all stated route counts preserve required facts.
- Core-only incremental map has correct groups/alternatives; no Medigap+C or universal C+standalone-D connector; no implied enrollment/mastery.
- Labeled utility preserves review/save/reset/delete and scoped destructive confirmation. Consent before storage/transfer and active errors remain findable.
- Roomier Ask preserves focus/Escape/Return/drafts/scroll/inertness and guide geometry, with reachable composer on short/mobile viewports. Real mobile-keyboard and assistive-technology checks remain evidence to collect, not CSS assumptions.

No new framework, paid assets, model experiment, broad audit, recommendation release, commit or push is needed. **Approve this focused proposal before implementation.**
