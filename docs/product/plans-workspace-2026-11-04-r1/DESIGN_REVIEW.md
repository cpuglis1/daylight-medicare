# Plans workspace design authority review

November 4, 2026 · D92 design study · Impeccable documentation pass

The Plans study extends Daylight’s existing warm paper, sage and olive identity. It is a new Operate/Read surface within the proposed :8893 advisor, not a replacement global design system. The owner confirmed the destination, stacked cards and closable desktop chat; detailed geometry, recommendation method, consumer comprehension and release remain separate review matters.

This review compares [PRODUCT.md](../../../PRODUCT.md), [DESIGN.md](../../../DESIGN.md), the [surface specification](SPEC.md) and [layout study](layout.html). The [verification record](VERIFICATION.md) supplies the existing rendered evidence. This documentation pass did not open a browser, rerun those interactions, call a model or modify the study or runtime.

## Inherited visual authority

| Element | Inherited rule and study expression |
| --- | --- |
| Identity | Existing sun/Daylight asset and name; no new slogan, mascot or photograph. The :8893 landing copy exception remains landing-specific. |
| Main palette | Paper `#fbf9f4`, raised paper `#fffefa`, ink `#283b30`, muted `#596653`, olive `#40513d`, olive hover `#2d422f`, sage `#e8eddf` and rule `#ccd3c1` match root tokens. The study’s `--raised` is a local alias for `paper-raised`. |
| Supporting colors | Text selection uses the approved `#d5dfc9`; the fictional-study notice uses `#f2e9ce`. Composer and preview-control borders reuse `#a8b19e` and `#99a68e`. Root records the support/notice colors as approval evidence previously unused in the incumbent stylesheets; their use here does not alter that incumbent status. |
| Type and numbers | Self-hosted Fraunces with Georgia/serif fallbacks for the workspace title and wordmark; Atkinson Hyperlegible with Arial/sans-serif fallbacks for readable content, controls and facts. Numeric comparison values use tabular figures. |
| Shape and focus | Controls retain 7px corners, composer 8px, and cards/panels/popover 12px. Keyboard focus retains a 3px `#91600c` outline with 4px offset. Explicit labels accompany actions and states. |
| Depth | Tonal surfaces and quiet rules organize the page. The definition popover and tablet drawer reuse `0 16px 48px rgba(32,48,32,.19)`; the drawer scrim reuses `rgba(31,49,32,.2)`. No decorative animation is added. |
| Comparison language | Equal card treatment, consistent cost dimensions, distinct units, visible checks and explicit fictional-data notices preserve the incumbent comparison principles. Visual prominence does not supply recommendation authority. |

The neutral cream is intentional, owner-confirmed brand material. A detector’s saturated-pattern warning does not authorize replacing it. The already-recorded hover fix restores dark olive behind light primary-button text, and the local font alias now names Atkinson Hyperlegible exactly.

## Surface-specific choices

These choices belong to this study and its specification. They were not copied into the global sidecar as primitives, breakpoints or reusable components.

| Choice | Purpose and boundary |
| --- | --- |
| Stacked cards beside a closable chat | Supports reading comparable facts while discussing the current plan or field. This is D92’s scoped alternative to the guided workspace’s task/picture columns and Ask overlay. It does not change Conversation or the protected variants. |
| Responsive shell | The study uses two columns from 1180px, a right-side 440px drawer below that width, and a full-height chat sheet below 768px. Its maximum-width rule begins at 1600px. These are local composition choices, not replacements for root’s 760/1100px responsive rules. |
| Desktop measurements | Study CSS uses 40px outer gutters, a 32px gap and `minmax(380px,33.3%)` chat. SPEC proposes a 24px gap, 24px gutters at 1280px and a 400px chat minimum. This remains study-versus-target measurement drift, not a global token change. The closed-chat 1200px shell includes 80px padding, leaving the specified 1120px content width. |
| Short desktop adjustment | At desktop widths and heights up to 800px, the study compacts header, transcript padding and idle composer; the 58px textarea protects useful answer space. The existing verification records the 1280×720 inspection. This height allocation is specific to Plans. |
| Type hierarchy | The title uses `clamp(34px,3.3vw,48px)`, line-height 1.12 and tracking `-.025em`; phone title is 36px. Body line-height is 1.45 rather than root’s 1.5. Plan names use 25px sans; key amounts use 27px desktop/24px phone. Supporting text uses 16–17px, with some preview/compact text at 14–15px. These remain design advisories requiring actual reading/accessibility validation, not a new global type scale. |
| Card and control density | Flat plan cards use 24px padding, 20px on phone, while root’s retained card has 18px padding and a low shadow. Study controls have a 44px minimum rather than the guided primary Continue’s 54px. Disabled study controls use .6 opacity rather than root’s .48. These local choices do not revise the incumbent component tokens. |
| Two additional chat tints | `#f4f5ed` on the chat panel and `#e4e9dc` on the fictional user utterance are study-only values. They are compatible tonal proposals, not exact inherited tokens or approved additions to the palette. They remain outside the global sidecar. |
| Navigation and teaching | Conversation/Plans navigation, Recommended/All plans/Compare views, the comparison tray, named field definitions and the Discussing line serve this workspace. Local explanations do not introduce a second questionnaire or a fixed conversation lesson sequence. |

The study demonstrates a subset of the specification. Full details, real source findings, filtering, dynamic view tracking, profile confirmation, live checks, stale-result handling and AI integration remain implementation work as recorded in VERIFICATION.md. A functional preview is not a claim that those behaviors exist in :8893.

## Sidecar-only synchronization

[`.impeccable/design.json`](../../../.impeccable/design.json) was refreshed from the current root DESIGN.md under Impeccable document Step 4b. The root document was preserved byte-for-byte. Its SHA-256 before and after is:

`01b1d878fc914ecc2e3a7fb11cb64a74312e376e53020b0856012e51708d1ce4`

Exact sidecar changes:

- Refreshed `generatedAt` and added source path, modification time, SHA-256 and explicit sidecar-only scope metadata.
- Replaced the paraphrased `narrative.overview`, `narrative.dos` and `narrative.donts` with the corresponding source prose/bullets, preserving their wording and Markdown.
- Added `extensions.scopeNotes` with the exact source passages for the D58/D86 landing exception, D73 review boundary, D65 free-text placement and D65 Ask geometry. Scope labels distinguish those exceptions from global primitives and D92’s proposed chat layout.
- Clarified descriptions of the existing Ask Daylight and Free-text composer previews: their retained styling is not evidence of the complete current launcher or permission to restore the superseded permanent task composer.

All nine component entries remain. Every component HTML/CSS snippet, existing color/type metadata, shadow, breakpoint, focus, scrim and motion extension was preserved. No Plans component, tint, dimension, breakpoint or typography token was promoted into the sidecar. No creative north star, tonal ramp or new global identity was invented.

The root frontmatter still contains the historical 466px Ask width while its D65 prose explicitly supersedes it with 600px desktop and viewport-bounded phone geometry. This synchronization records that source precedence instead of editing root authority. The preserved help snippets remain partial/historical previews; recreating the complete current launcher/overlay is outside this bounded metadata refresh. The earlier VERIFICATION.md statement that sidecar timestamp drift was merely recorded describes the state before this pass; this section supersedes that statement for the sidecar only.

## Requirement bounds and evidence gaps

| Review concern | Evidence and remaining boundary |
| --- | --- |
| D92 useful task | Stacked comparable facts, details, a selected-plan comparison and contextual explanation support the proposed decision workspace. Consumer task comprehension remains unmeasured. |
| D86/D87 consequential intake and continuity | SPEC reuses confirmed reports, one end review and existing conversation; it distinguishes view state from preference. This study does not implement the production confirmation/context seams. |
| D64/D73 coverage paths and tradeoffs | SPEC preserves path-first decisions, current coverage, keep/defer outcomes, concrete cost/access tradeoffs and neutral all-plan access. The study’s 72 fictional Advantage entries do not prove a complete market or path comparison. |
| D91/D73 two gates and scope | Retained identities, field preparation, consumer source/method/purpose acceptance and app access remain separate. Neither rendered fictional recommendations nor a complete reported profile accepts real evidence. |
| D64 independence and challenge | Equal visual treatment and the proposed inspectable priority method carry no commercial preference. Production counterfactual, source-use and independent method review remain required. |
| D55/D57/D73 permission and control | The study stages draft text and displays context without sending it. The proposed server-owned evidence, visit memory and separately permissioned Send payload are specified, not activated. Protected variants and guest records are untouched. |
| D49/D54 teaching and correction | Definitions remain near the relevant field; explanations preserve cost bases, unknowns and correction paths. No source-verified plan fact or personal fit is created by this document. |
| D73 actual capability and proof | Existing responsive captures and controlled design interactions support proposal review. This pass adds source/document consistency checks only; it is not a new browser audit, paid conversation, screen-reader certification, consumer study, owner acceptance or production release. |

The independent finish review is recorded separately. Its design-proposal verdict does not accept data, recommend real plans, certify the production interface or replace the owner’s assessment of conversation quality.
