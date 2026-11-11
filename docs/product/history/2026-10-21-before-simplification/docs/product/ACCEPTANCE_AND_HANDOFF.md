# Acceptance, implementation increments and Codex handoff

Design version 1.0 · October 21, 2026. This document specifies future evidence; it does not claim tests, participant sessions, production storage or live services have passed. The [master](MASTER_DESIGN.md) owns decisions; [nodes](BRANCHING_NODES.md) and [JSON](flow-contract.json) enumerate proposed state and transitions.

## 1. Traceable outcomes

| Outcome | Requirement IDs | Primary evidence |
|---|---|---|
| Agent orchestrates contextual task rather than bolted-on help | D49, D41, D25 | Multi-fact typed entry and spontaneous topic change demonstrated without duplicate questions or silent writes |
| Goal and voluntary knowledge independently shape depth | D50, D29–D31 | All four goals × new/some/comfortable/unknown; per-topic Explain/I know; free-text interpretation confirmed |
| Stable progress and reversible navigation | D51, D06–D13 | Same four phase IDs/labels/order before/after each branch/edit; actual history Back and truthful phase states |
| Something else is meaningful and safe | D52, D22 | Raw text preserved; typed proposal editable/rejectable; unknowns retained; injection cannot create a rule/tool |
| Guest save/resume without account | D53, D17 | Cross-profile isolation, acknowledged saving, same-browser resume/expiry, recovery limits and deletion evidence |
| Minimal private context and optional sensitive saving | D54, D23, D44 | Inspect requests/storage/logs with synthetic canaries; separate save/AI/human-share choices and purge history/caches |
| One concept at a time plus professional people/photography | D55, D01–D02, D20, D26, D32 | Content inventory + concept reveal sequence + rendered art/composition review on all devices |
| Useful honest dashboard and next step | D56, D22, D47–D48 | Comparable dimensions, zero/unknown/conflict cases, stale results, keep/undecided, actual preparation output |
| Repeatable implementation | D57, D24, D36 | Versioned node/field/acceptance mapping and limited increments; recorded deviations, gaps and observed comprehension |

## 2. COGA and accessibility mapping

COGA is supplemental guidance. WCAG conformance is a separate assessment against all applicable criteria; the following selected mapping is not a complete audit or certification.

| Reference | Daylight design obligation | Observable acceptance |
|---|---|---|
| COGA §4.2: understand purpose | Literal task/goal and clear role | Person identifies the current task and what Daylight does |
| COGA §4.3: find needed content | Stable track and visible controls | Find Back/help/profile without discovering hidden gestures |
| COGA §4.4: clear content | One concept and plain terms | Explain the introduced concept; inline definition available |
| COGA §4.5: prevent/correct mistakes | Confirm interpretation and retain entries | Correct an extracted fact without re-entering others |
| COGA §4.6: maintain focus | One task; contained help | Return from help to the same question |
| COGA §4.7: avoid memory demands | Visible summary and saved context | Resume/correct using recognition, not transcript reconstruction |
| COGA §4.8: help and support | Contextual agent, useful preparation | Find an answer and identify a usable next action |
| COGA §4.9: adaptation | Voluntary depth and guide visibility | Change depth without losing data or required warnings |
| COGA §5: include users | Observe diverse comprehension/recovery | Record misunderstandings and resulting revisions |
| WCAG 1.1.1 / 1.3.1 | Meaningful text alternatives/structure | Diagrams/tables understandable with assistive technology |
| WCAG 1.4.3 / 1.4.11 | Contrast for text and controls | Measure actual rendered states |
| WCAG 1.4.4 / 1.4.10 / 1.4.12 | Enlargement/reflow/spacing | No lost content or controls under applicable tests |
| WCAG 2.1.1 / 2.1.2 | Keyboard operation/no trap | Complete tasks and leave help using keyboard |
| WCAG 2.4.3 / 2.4.7 / 2.4.11 | Logical visible/unobscured focus | Focus survives entry/return/errors/zoom |
| WCAG 2.5.3 / 2.5.8 | Visible labels and target sizing | Names match labels; measure applicable targets/exceptions |
| WCAG 3.2.2 / 3.2.6 | Predictable input and consistent help | Selection never advances; help location consistent |
| WCAG 3.3.1 / 3.3.2 / 3.3.3 / 3.3.7 | Usable errors/instructions/no redundant entry | Invalid input identified; retained information reused |
| WCAG 4.1.2 / 4.1.3 | Semantics and status | Screen reader announces state/replies appropriately |

Sources: [COGA](https://www.w3.org/TR/coga-usable/), [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [WAI-ARIA modal dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/). The specific interface and test cases below are Daylight's proposed acceptance design.

## 3. Device and assistive-technology checks

Use synthetic data. Inspect desktop 1440×1000 and an ordinary short desktop around 1500×708; tablet portrait around 820×1180 and landscape around 1024×768; phone around 390×844; 320 CSS-pixel reflow; short/landscape phone; browser zoom/text enlargement 200% and applicable reflow at higher zoom; text-spacing overrides; forced colors; reduced motion. Preserve all meaningful content and controls, with no horizontal page overflow except genuinely two-dimensional content given an accessible treatment.

Keyboard-only walkthrough: arrive → choose goal/depth → free-text confirmation → Continue/Back → local definition → Ask modal → follow-up → Escape → edit → dashboard → print preview → privacy/delete cancel. Check no unexpected focus moves while typing, no hidden background advancement, visible focus, correct selected state, logical headings/labels and invalid-field identification.

Real VoiceOver/Safari on iOS/macOS and at least one independently configured desktop screen reader/browser pairing such as NVDA/Firefox or Chrome: hear task purpose/current phase, chosen answer and why asked; operate picture terms and compare rows; announce reply ready once; read source/unknown distinctions; enter/exit dialog; confirm deletion cancellation focus. Record versions and actual speech observations, not only ARIA attributes.

Real iPad/iPhone/Android keyboard and touch tests: no automatic keyboard for a reading entry; Return/composer usable with keyboard; notes preserve newlines; composition does not submit; tap edges select full cards; sheet avoids obscured current input. Screenshot resize emulation is not a substitute. Print/PDF: same facts/unknowns/candidates/notes/edited drafts/date as screen, meaningful page breaks, no duplicate numbering or forced tiny one-page content.

## 4. Branch and state regression matrix

Each node's `-A/-B/-C` assertions and every option/next target in the JSON are minimum coverage, not app tests already run. Add the following behavior-specific cases during the authorized slice:

| Case ID | Scenario | Required assertion |
|---|---|---|
| R01 | Four goals × four knowledge states plus text | Goal unchanged by expertise; depth doesn't modify facts; no default selection |
| R02 | Learn → useful finish | No ZIP/birth/current coverage gate; summary names explored concepts only |
| R03 | Shortcut → browsing | No forced full intake; skipped facts remain unknown; picture hidden until shown |
| R04 | New user chooses Compare | Compare is not expertise; selected-category vocabulary taught one concept at a time |
| R05 | Per-topic I know / Explain | Explicit self-report and seen independent; return to same question/draft |
| R06 | C00 every enrollment option + B-only text | No conflation of A-only/B-only/no/parts-unknown/enrollment-unknown; optional conditional card help |
| R07 | Current coverage multiple components/conflict | Keep raw components; incompatible set asks clarification; no silent overwrite |
| R08 | Keep/replace/add/unknown review | Keep reaches useful result; replace/add clarifies category; no automatic cancellation |
| R09 | Active/recent/no/unknown job coverage | No automatic Part B delay or invented deadlines; correct relevant next facts |
| R10 | Age-based dates/first-day/other eligibility | Direct inputs, verified rules, unknown blocks exact derived window; no age-65 arithmetic |
| R11 | Birth vs actual/scheduled B start | Distinct fields; supplement window not derived from birthday alone |
| R12 | Forecast/unknown employment and coverage ends | Separate dates/provenance; forecast never labeled confirmed legal deadline |
| R13 | Medicine yes/no/unknown + optional list | No⇒no coverage conclusion; unknown⇒open task; original text and unresolved identity preserved |
| R14 | Extras/priorities none/unknown/multiple | Mutual exclusions correct; no forced top priority; no unverified plan fit |
| R15 | 34102/34134/missing/invalid/outside lookup | Unique sourced result; all ambiguous matches; invalid stays; unknown not outside |
| R16 | Year/category unsupported/data pending | Requested scope retained; no substituted records; official/local education alternative |
| R17 | Candidate name ambiguity | Exact ID confirmed; no first match auto-selected |
| R18 | Catalog sorts/filters/ties/unknown/conflict/$0 | Exact deterministic order/rationale; records reachable; no favoritism or fabricated amount |
| R19 | Current vs prospective coverage | Baseline gaps explicit; Keep valid; PDP-only not presented as total Original cost |
| R20 | Provider/drug/Medigap unsupported | No network badge from name, no personal price/insurer quote, no guaranteed buying right |
| R21 | Edit goal/location/enrollment/priorities | Preserve independent entries; affected comparison/dates/drafts stale; no silent old result |
| R22 | Ask at arrival/lesson/question/result | No reflow; literal question/answer first; visible follow-ups; exact return/draft |
| R23 | Long answer/short viewport/keyboard | One usable reading area; Return/composer reachable; no auto keyboard for reading |
| R24 | Model fail/timeout/offline | Local reviewed fallback; typed text retained; no fake live success; no route mutation |
| R25 | Storage fail/conflict/delayed reply | Not saved shown; revision merge; idempotent receipt check; no stale response overwrites edit |
| R26 | Different guest/subject/session | Authorization rejects cross-profile access; no subject data mixing; IDs alone insufficient |
| R27 | Visit-only/sensitive opt-out/AI context | Inspect canary fields absent from backend/logs/model context; permitted fields only |
| R28 | Resume/expiry/forget/delete/cancel | Masked preview; exact state/version recheck; access removal != server deletion; cancel retains guide |
| R29 | Raw-chat logging/deletion | Actual notice matches logs; no hidden raw logging; scoped deletion reaches histories/summaries/caches |
| R30 | Preparation/print/handoff future gate | Edited draft preserved and flagged on changes; print parity; prepared never sent; no unavailable human promise |
| R31 | Injection in text/notes/source document | No new command/rule, secret disclosure, cross-profile read or unapproved URL/tool execution |
| R32 | Same phases across every case | Four IDs/labels/order fixed; visited/recorded/unknown/optional distinguishable; no mastery checkmark |

For dynamic answer sets, enumerate actual source/confirmed-state values in tests: each selected priority, every returned county, exact plan candidate ID, and all record statuses. Contract validation only checks that the expansion source is defined; actual app tests must exercise representative and boundary expansions.

## 5. Formative user sessions and comprehension

Begin with the already proposed 6–8 formative sessions, with varied Medicare familiarity, LLM/device confidence and cognitive needs; include caregiver, unsure enrollment, job transition and experienced browsing. Use informed participation and synthetic/participant-chosen nonidentifying data; do not collect Medicare numbers. Include participants with relevant access needs in design/testing rather than assuming older age represents disability.

Observe whether the person can: explain Medicare/A/B and a relevant tradeoff; distinguish a reported fact from a verified check; use free text and correct an interpretation; reopen an explanation; recover the same task from help; change an answer without losing notes; recognize saved versus unsaved state; find one next step; understand that a shortlist/preference did not enroll them. Record wrong turns, prompts for assistance, false certainty, lost context, data-sharing misunderstandings and practical next-action explanation. Have a qualified reviewer assess the factual teach-back.

A session is a problem-finding exercise, not statistical market validation or accessibility certification. Pre-agree the task-specific evaluation rubric before testing. Severe misleading coverage conclusions, inaccessible critical controls, silent data loss/disclosure or unapproved transmission block promotion regardless of task speed. Record remediation and re-test the affected task; do not fabricate a universal “4/5 proves usable” threshold from older proposals.

## 6. Implementation increments: future authorization only

| Increment | Scope and prerequisites | Reviewable deliverable / stop boundary |
|---|---|---|
| I0 · Freeze contract and source baseline | Owner reviews this package and remaining policy list; inventory existing content/state | Accepted flow version, node/field mapping, archived before-images. No app implementation from documentation approval alone. |
| I1 · State/command prototype | Typed envelopes, revisions, G1, dependency rules; synthetic local tests | Replayable state transitions + flow tests; no production persistence, model deployment or real plan promotion |
| I2 · Agent orchestration | Allowlist, confirmed extraction, eligible-task planner, reviewed fallback, injection handling | Multi-fact free-text and five example journeys with proposed/confirmed distinction; no arbitrary generated policy |
| I3 · Guest persistence | Approved retention/processor/privacy/security decisions; I1 concurrency contract | Secure guest auth, same-browser resume, save status, deletion/isolation tests with synthetic data; release storage only after explicit review |
| I4 · Task/picture/help composition | I1–I2 stable; retain all lesson inventory | Four-phase shell, one-concept lessons, local explanations, real overlay behavior on target devices; no loss of notes/routes |
| I5 · Dashboard and preparation | Existing exact-release/data acceptance; scoped supported fields | Consistent records/comparison/stale-state/Keep/uncertainty; useful editable output and print parity; unsupported capabilities labeled |
| I6 · Art and visual finish | Behavior accepted; photography licensing/source/alt/crop decisions | Meaningful representative people and coherent warm type/spacing/form system; no route or data change |
| I7 · Accessibility/comprehension | Device/AT access and participants available | Actual evidence from checks/session tasks, repairs to observed problems and named remaining limits; no false certification |
| I8 · Human handoff, if separately requested | Qualified operator, recipient/authority/privacy/receipt model | Exact preview/authorization and real statuses; no unapproved contact or enrollment connection |

Per increment: one planned implementation pass, one batched inspection across desktop/tablet/phone, one targeted correction pass and confirmation. Expand only for a named unresolved defect or new explicit owner decision. No 40-minute exploratory restyling loop. Meaningful automated regression checks accompany behavioral changes; do not add tests that merely mirror cosmetic implementation.

## 7. Definition of done

An authorized increment is done only when: affected D IDs/nodes/components named; no unrelated work discarded; relevant content preserved or explicitly migrated; typed state and branch contracts exercised; unknown/back/edit/return/failure cases work; scoped data/source gates remain intact; actual save/disclosure behavior matches notice; applicable rendered/keyboard/device evidence recorded; no claim of participant acceptance from test counts. Domain facts and external actions retain their separate reviews. Remaining blockers and the exact unverified states are reported honestly.

The whole target service is not “complete” while retention/guest security or source acceptance remains unresolved. A documentation-only slice can be complete with those explicitly identified as dependent implementation gates.

## 8. Reusable Codex handoff

Copy this scoped instruction into a future authorized implementation task:

> Read AGENTS.md, PRODUCT.md, DAYLIGHT_REQUIREMENTS.md and docs/product/MASTER_DESIGN.md before editing. Implement only increment [I#], requirement IDs [D#], nodes [IDs], components [names]. Respect flow-contract version [version]; exact proposed copy/options and transitions are in BRANCHING_NODES.md; composition is in WIREFRAMES.md. Treat agent-first orchestration, explicit confirmation, four stable phases, growing visual teaching, overlay continuity and backend guest privacy boundaries as invariants. Preserve unrelated uncommitted work, notes, sources and backend acceptance gates. Do not revive archived flow/identity decisions. If a new preference conflicts with the contract, name the conflict and update the decision/requirement first. State/profile/routing/meaning changes require an explicit decision; a styling task cannot authorize them. Complete meaningful scoped tests and one batched device inspection, correct identified defects, then report evidence and remaining limits. Do not commit, push, deploy, collect real personal data or contact anyone unless this task expressly authorizes it.

### Before changing code

- Name requirement IDs, node/field dependencies and exact increment; inspect current code only for those touchpoints.
- Record current behavior/content and expected after behavior; use synthetic data.
- Resolve any policy prerequisite; do not invent service availability or retention terms.
- Define meaningful acceptance cases including error/unknown/Back/help-return; pin source/admission state.

### Before reporting completion

- Reconcile node transitions and displayed labels; state what remains unknown/unverified.
- Verify inputs/notes/candidates/drafts survive edits/help and affected conclusions become stale.
- Inspect actual target device layouts and keyboard/assistive behavior appropriate to scope.
- Record commands/results/screenshots as dated evidence; no owner-approval claim from a test total.
- Update this contract only for an authorized product change, keep IDs stable, bump version and preserve prior version.

## 9. Documentation verification and limits

Run `python3 docs/product/validate_contract.py` to check inventory IDs, targets, shared event coverage, metadata, every option, template coverage and example routes. It validates documentation consistency; it does not execute the app or validate insurance advice. Markdown file links are checked by the document build/review process. Snapshot hashes of pre-existing authority files are retained in `history/2026-10-21-before-master/manifest.json`.
